from __future__ import annotations
from dataclasses import dataclass
import json
import re
from freehold.core.ast import *
from freehold.core.control_flow import ControlFlowAnalyzer, RoutineFlowSummary
from freehold.core.string_templates import validate_template

BUILTIN_TYPE_NAMES = {"Integer", "Boolean", "Double", "String", "BigInteger", "BigFloat", "Executor", "Scope"}
BUILTIN_GENERIC_TYPE_ARITY = {
    "Array": 2,
    "JoinHandle": 1,
    "Channel": 1,
    "Sender": 1,
    "Receiver": 1,
}

RESERVED_NAMES = {
    "Array", "BigFloat", "BigInteger", "Boolean", "Double", "Integer", "Result", "String",
    "and", "call", "case", "default", "do", "else", "end", "ensures",
    "error", "exposing", "failure", "false", "function", "if", "import",
    "invariant", "is", "let", "module", "not", "ok", "or", "procedure",
    "record", "requires", "aborts", "return", "abort", "returns", "success", "then", "true",
    "type", "value", "variant", "when", "while", "async", "await", "scope", "spawn", "join", "result",
    "service", "rpc", "proto", "global", "depends", "Input", "Output", "In_Out",
}

@dataclass
class VerifiedProgram:
    ast: Program
    types: dict[str, TypeDef]
    records: dict[str, RecordDef]
    errors: set[str]
    routines: dict[str, RoutineDecl]
    services: dict[str, ServiceDecl]
    proof_obligations: list[dict[str, str]]
    flow_summaries: dict[str, RoutineFlowSummary]

class Verifier:
    def verify(self, program: Program, imported_modules: dict[str, VerifiedProgram] | None = None, prover: str | None = None, timeout: int | None = None) -> VerifiedProgram:
        imported_modules = imported_modules or {}
        self.validate_imports(program)
        self.validate_qualified_name(program.module_name, program.pos)
        types = {name: TypeDef(name, name) for name in BUILTIN_TYPE_NAMES}
        records, generic_records, errors, routines, services = {}, {}, set(), {}, {}
        declared_names = {name: "builtin" for name in types}
        for d in program.declarations:
            if isinstance(d, TypeDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "type")
                self.validate_type_decl(d)
                declared_names[d.name] = "type"
                types[d.name] = TypeDef(d.name, d.base, d.min_value, d.max_value)
            elif isinstance(d, RecordTypeDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "record")
                declared_names[d.name] = "record"
                if d.type_params:
                    self.validate_type_params(d.type_params, d.pos)
                    generic_records[d.name] = d
                    continue
                seen, fields = set(), {}
                for f in d.fields:
                    self.validate_identifier(f.name, f.pos)
                    if f.name in seen: raise TypeCheckError(f"{f.pos.text()}: duplicate record field: {f.name}")
                    seen.add(f.name); fields[f.name] = f.type_name
                proto_fields = self.validate_proto_fields(d)
                records[d.name] = RecordDef(d.name, fields, proto_fields)
            elif isinstance(d, ErrorDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "error")
                declared_names[d.name] = "error"
                errors.add(d.name)
            elif isinstance(d, ServiceDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "service")
                declared_names[d.name] = "service"
                services[d.name] = d
            elif isinstance(d, RoutineDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "routine")
                if d.type_params:
                    self.validate_type_params(d.type_params, d.pos)
                declared_names[d.name] = "routine"
                routines[d.name] = d
        ctx = Ctx(program.module_name, types, records, generic_records, errors, routines, program.imports or [], imported_modules)
        ctx.services = services
        for rd in [d for d in program.declarations if isinstance(d, RecordTypeDecl)]:
            previous_type_params = ctx.current_type_params
            ctx.current_type_params = set(rd.type_params or [])
            try:
                for f in rd.fields:
                    ctx.require_type_or_record(f.type_name, f.pos)
            finally:
                ctx.current_type_params = previous_type_params
        obs = []
        for r in routines.values(): self.routine(r, ctx, obs)
        self.services(services, records)
        flow_summaries = ControlFlowAnalyzer(routines, program.module_name).analyze_routines()
        vp = VerifiedProgram(program, types, records, errors, routines, services, obs, flow_summaries)
        from freehold.core.symbolic import symbolic_obligations, solve_smt_query
        new_obs = symbolic_obligations(vp, imported_modules=imported_modules)
        failed_obs = []
        for ob in new_obs:
            res = solve_smt_query(ob["smt_query"], prover=prover, timeout=timeout)
            if res == "sat":
                failed_obs.append(ob)
        if failed_obs:
            first = failed_obs[0]
            raise VerificationError(f"{first['location']}: verification failed: {first['kind']} obligation is satisfiable (violated)")
        obs.extend(new_obs)
        return vp

    def validate_proto_fields(self, declaration: RecordTypeDecl) -> dict[str, int]:
        proto_fields: dict[str, int] = {}
        seen_ids: dict[int, str] = {}
        for field in declaration.fields:
            if field.proto_id is None:
                continue
            if field.proto_id <= 0:
                raise TypeCheckError(f"{field.pos.text()}: invalid proto field id: {field.proto_id}")
            if field.proto_id in seen_ids:
                raise TypeCheckError(f"{field.pos.text()}: duplicate proto field id: {field.proto_id}")
            seen_ids[field.proto_id] = field.name
            proto_fields[field.name] = field.proto_id
        return proto_fields

    def services(self, services: dict[str, ServiceDecl], records: dict[str, RecordDef]) -> None:
        for service in services.values():
            seen_rpc_names = set()
            for rpc in service.rpcs:
                self.validate_identifier(rpc.name, rpc.pos)
                self.validate_identifier(rpc.request_name, rpc.pos)
                if rpc.name in seen_rpc_names:
                    raise TypeCheckError(f"{rpc.pos.text()}: duplicate rpc name: {rpc.name}")
                seen_rpc_names.add(rpc.name)
                self.require_grpc_record(rpc.request_type, records, rpc.pos, "request", set())
                self.require_grpc_record(rpc.response_type, records, rpc.pos, "response", set())

    def require_grpc_record(self, type_name: str, records: dict[str, RecordDef], pos: SourcePos, role: str, seen: set[str]) -> None:
        if "<" in type_name or type_name not in records:
            raise TypeCheckError(f"{pos.text()}: unknown rpc {role} type: {type_name}")
        if type_name in seen:
            return
        seen.add(type_name)
        record = records[type_name]
        proto_fields = record.proto_fields or {}
        for field_name, field_type in record.fields.items():
            if field_name not in proto_fields:
                raise TypeCheckError(f"{pos.text()}: missing proto field id in grpc message: {type_name}.{field_name}")
            self.require_grpc_proto_field_type(field_type, records, pos, seen)

    def require_grpc_proto_field_type(self, type_name: str, records: dict[str, RecordDef], pos: SourcePos, seen: set[str]) -> None:
        array_match = re.fullmatch(r"Array<\s*([^<>]+?)\s*>", type_name)
        if array_match:
            self.require_grpc_proto_field_type(array_match.group(1).strip(), records, pos, seen)
            return
        if type_name in {"String", "Integer", "Boolean", "Double"}:
            return
        if type_name in records:
            self.require_grpc_record(type_name, records, pos, "field", seen)
            return
        raise TypeCheckError(f"{pos.text()}: unsupported grpc proto field type: {type_name}")

    def validate_imports(self, program: Program) -> None:
        seen = set()
        for imp in (program.imports or []):
            self.validate_qualified_name(imp.module_name, imp.pos)
            if imp.module_name == program.module_name:
                raise TypeCheckError(f"{imp.pos.text()}: module cannot import itself: {imp.module_name}")
            if imp.module_name in seen:
                raise TypeCheckError(f"{imp.pos.text()}: duplicate import: {imp.module_name}")
            seen.add(imp.module_name)
            exposed = set()
            for name in imp.exposing:
                self.validate_identifier(name, imp.pos)
                if name in exposed:
                    raise TypeCheckError(f"{imp.pos.text()}: duplicate exposing symbol {name} in import {imp.module_name}")
                exposed.add(name)

    def validate_declaration_name(self, name: str, declared_names: dict[str, str], pos: SourcePos, kind: str) -> None:
        if name in BUILTIN_TYPE_NAMES or name in BUILTIN_GENERIC_TYPE_ARITY:
            raise TypeCheckError(f"{pos.text()}: built-in type name already defined: {name}")
        self.validate_identifier(name, pos)
        existing_kind = declared_names.get(name)
        if existing_kind in {"type", "record"} and kind in {"type", "record"}:
            raise TypeCheckError(f"{pos.text()}: type already defined: {name}")
        if existing_kind is not None:
            raise TypeCheckError(f"{pos.text()}: declaration name already defined: {name}")

    def validate_identifier(self, name: str, pos: SourcePos) -> None:
        if name in RESERVED_NAMES:
            raise TypeCheckError(f"{pos.text()}: reserved keyword cannot be used as name: {name}")

    def validate_qualified_name(self, name: str, pos: SourcePos) -> None:
        for part in name.split("."):
            self.validate_identifier(part, pos)

    def validate_type_decl(self, declaration: TypeDecl) -> None:
        if declaration.min_value is None or declaration.max_value is None:
            return
        if declaration.base not in {"Integer", "Double"}:
            raise TypeCheckError(f"{declaration.pos.text()}: range requires numeric base type: {declaration.base}")
        if declaration.base == "Integer" and (
            not isinstance(declaration.min_value, int) or not isinstance(declaration.max_value, int)
        ):
            raise TypeCheckError(f"{declaration.pos.text()}: integer range bounds must be integers")
        if declaration.min_value > declaration.max_value:
            raise TypeCheckError(
                f"{declaration.pos.text()}: invalid range bounds: {declaration.min_value}..{declaration.max_value}"
            )

    def validate_type_params(self, type_params: list[str], pos: SourcePos) -> None:
        seen = set()
        for name in type_params:
            self.validate_identifier(name, pos)
            if name in seen:
                raise TypeCheckError(f"{pos.text()}: duplicate type parameter: {name}")
            seen.add(name)

    def type_name_root(self, name: str) -> str:
        return name.split("<", 1)[0].strip()

    def std_procedure_call(self, name, args, env, ctx, pos) -> bool:
        def infer_arg(i):
            if i >= len(args):
                raise TypeCheckError(f"{pos.text()}: {name} expects more arguments")
            if isinstance(args[i], NamedArg):
                raise TypeCheckError(f"{args[i].pos.text()}: {name} does not accept named argument: {args[i].name}")
            return self.infer(args[i], env, ctx, False, None)
        def expect_count(n):
            if len(args) != n:
                raise TypeCheckError(f"{pos.text()}: {name} expects {n} argument(s)")
        def expect_base(i, base):
            t = infer_arg(i)
            if self.base(t, ctx) != base:
                raise TypeCheckError(f"{args[i].pos.text()}: {name} argument {i+1} expected {base}, got {type_to_string(t)}")
        def template_values():
            if len(args) < 1:
                raise TypeCheckError(f"{pos.text()}: {name} expects at least 1 argument")
            if isinstance(args[0], NamedArg):
                raise TypeCheckError(f"{args[0].pos.text()}: {name} template argument must be positional")
            positional = []
            named = []
            saw_named = False
            for arg in args[1:]:
                if isinstance(arg, NamedArg):
                    saw_named = True
                    named.append(arg)
                else:
                    if saw_named:
                        raise TypeCheckError(f"{arg.pos.text()}: {name} positional template value after named binding")
                    positional.append(arg)
            if positional and named:
                raise TypeCheckError(f"{pos.text()}: {name} cannot mix positional and named template arguments")
            return args[0], positional, named
        def expect_template_values(values):
            for index, arg in enumerate(values, start=1):
                value_expr = arg.expr if isinstance(arg, NamedArg) else arg
                t = self.infer(value_expr, env, ctx, False, None)
                if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                    label = arg.name if isinstance(arg, NamedArg) else str(index)
                    raise TypeCheckError(f"{value_expr.pos.text()}: {name} template value {label} expected String, Integer, Boolean, or Double, got {type_to_string(t)}")
        if name == "Std.IO.log":
            expect_count(1)
            t = infer_arg(0)
            if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                raise TypeCheckError(f"{args[0].pos.text()}: Std.IO.log supports String, Integer, Boolean, Double")
            return True
        if name == "Std.IO.logf":
            template_arg, positional_values, named_values = template_values()
            expect_base(0, "String")
            expect_template_values(positional_values)
            expect_template_values(named_values)
            if isinstance(template_arg, StringExpr):
                try:
                    validate_template(template_arg.value, len(positional_values), [a.name for a in named_values])
                except ValueError as exc:
                    raise TypeCheckError(f"{template_arg.pos.text()}: Std.IO.logf {exc}") from exc
            return True
        if name == "Std.IO.log_int":
            expect_count(1); expect_base(0, "Integer"); return True
        if name == "Std.IO.log_bool":
            expect_count(1); expect_base(0, "Boolean"); return True
        if name == "Std.IO.log_double":
            expect_count(1); expect_base(0, "Double"); return True
        return False

    def routine(self, r, ctx, obs):
        ctx.current_routine = r
        previous_type_params = ctx.current_type_params
        previous_async = ctx.current_async
        previous_scopes = ctx.scope_vars
        previous_scope_handles = ctx.scope_handles
        previous_constraints = ctx.type_param_constraints
        ctx.current_type_params = set(r.type_params or [])
        ctx.current_async = r.is_async
        ctx.scope_vars = set()
        ctx.scope_handles = {}
        ctx.type_param_constraints = {}
        env = {}
        try:
            seen_params = set()
            for p in r.params:
                self.validate_identifier(p.name, p.pos)
                if p.name in seen_params:
                    raise TypeCheckError(f"{p.pos.text()}: duplicate parameter name: {p.name}")
                seen_params.add(p.name)
                param_type = self.param_type_ref(p, ctx)
                ctx.require_return_type(param_type, p.pos); env[p.name] = param_type
            if r.return_type: ctx.require_return_type(r.return_type, r.pos)
            if r.name == "main" and r.requires:
                raise TypeCheckError(f"{r.requires[0].pos.text()}: main requires clause is not allowed")
            for e in r.requires: self.contract_bool("requires", e, env, ctx, False, None)
            declared_aborts = set()
            for clause in r.aborts:
                if clause.error_name not in ctx.errors:
                    raise TypeCheckError(f"{clause.pos.text()}: unknown abort error: {clause.error_name}")
                if clause.error_name in declared_aborts:
                    raise TypeCheckError(f"{clause.pos.text()}: duplicate abort declaration: {clause.error_name}")
                declared_aborts.add(clause.error_name)
                if clause.condition is not None:
                    self.contract_bool("aborts", clause.condition, env, ctx, False, None)
            for e in r.ensures: self.contract_bool("ensures", e, env, ctx, True, r.return_type)
            self.validate_flow_contracts(r, env, ctx)
            ret = self.block(r.body, r, env, ctx, list(r.requires))
            ctx.require_no_unjoined_scope_handles(r.pos)
            if r.kind == "function" and not ret: raise TypeCheckError(f"{r.pos.text()}: function {r.name} has no guaranteed return")
        finally:
            ctx.current_type_params = previous_type_params
            ctx.current_async = previous_async
            ctx.scope_vars = previous_scopes
            ctx.scope_handles = previous_scope_handles
            ctx.type_param_constraints = previous_constraints

    def collect_mutated_vars(self, body: list[Any], env: dict[str, Any], ctx: Any) -> set[str]:
        mutated = set()
        def visit(stmt):
            if isinstance(stmt, AssignStmt):
                mutated.add(stmt.name)
            elif isinstance(stmt, FieldAssignStmt):
                if stmt.path:
                    mutated.add(stmt.path[0])
            elif isinstance(stmt, CallStmt):
                callee = None
                try:
                    callee = ctx.routine(stmt.name, stmt.pos)
                except TypeCheckError:
                    pass
                if callee:
                    callee_params = [p.name for p in callee.params]
                    if hasattr(callee, "depends_specs") and callee.depends_specs:
                        for d_callee in callee.depends_specs:
                            target_root = d_callee.target.split('.')[0]
                            if target_root in callee_params:
                                idx = callee_params.index(target_root)
                                if idx < len(stmt.args):
                                    arg = stmt.args[idx]
                                    if isinstance(arg, VarExpr):
                                        mutated.add(arg.name)
                                    elif isinstance(arg, (FieldAccessExpr, IndexExpr, IndexedFieldAccessExpr)):
                                        mutated.add(getattr(arg, "name", None) or getattr(arg, "path", [None])[0])
                            else:
                                # Global target
                                mutated.add(target_root)
                    elif callee.kind == "procedure":
                        for arg in stmt.args:
                            if isinstance(arg, VarExpr):
                                mutated.add(arg.name)
                            elif isinstance(arg, (FieldAccessExpr, IndexExpr, IndexedFieldAccessExpr)):
                                mutated.add(getattr(arg, "name", None) or getattr(arg, "path", [None])[0])
                        if hasattr(callee, "global_specs") and callee.global_specs:
                            for cg in callee.global_specs:
                                if cg.name not in callee_params and cg.mode in ("Output", "In_Out"):
                                    mutated.add(cg.name)
            elif isinstance(stmt, IfStmt):
                for s in stmt.then_body: visit(s)
                for s in stmt.else_body: visit(s)
            elif isinstance(stmt, WhileStmt):
                for s in stmt.body: visit(s)
            elif isinstance(stmt, CaseStmt):
                for branch in stmt.branches:
                    for s in branch.body: visit(s)
                if stmt.default_body:
                    for s in stmt.default_body: visit(s)
            elif isinstance(stmt, ScopeStmt):
                for s in stmt.spawn_body: visit(s)
                for s in stmt.join_body: visit(s)
                for s in stmt.result_body: visit(s)
        for stmt in body:
            visit(stmt)
        return {m for m in mutated if m is not None}

    def validate_flow_contracts(self, r, env, ctx):
        seen_globals = set()
        if r.global_specs:
            for g in r.global_specs:
                if g.mode not in ("Input", "Output", "In_Out", None):
                    raise TypeCheckError(f"{g.pos.text()}: invalid global mode: {g.mode}")
                if g.name in seen_globals:
                    raise TypeCheckError(f"{g.pos.text()}: duplicate global variable: {g.name}")
                seen_globals.add(g.name)
                if g.name not in env and g.name not in ctx.services:
                    raise TypeCheckError(f"{g.pos.text()}: unknown global variable or service: {g.name}")

        param_names = {p.name for p in r.params}
        actual_globals = seen_globals - param_names

        # Always check transitive global variable accesses from calls
        def check_transitive_globals(node):
            if node is None:
                return
            if isinstance(node, list):
                for child in node:
                    check_transitive_globals(child)
                return

            if isinstance(node, (CallStmt, CallExpr)):
                callee = None
                try:
                    callee = ctx.routine(node.name, node.pos)
                except TypeCheckError:
                    pass
                if callee:
                    callee_param_names = {p.name for p in callee.params}
                    if hasattr(callee, "global_specs") and callee.global_specs:
                        r_globals = {g.name: g.mode for g in r.global_specs} if r.global_specs else {}
                        for cg in callee.global_specs:
                            if cg.name not in callee_param_names:
                                # It's an actual global accessed by callee
                                if cg.name not in r_globals:
                                    raise TypeCheckError(f"{node.pos.text()}: transitive global variable '{cg.name}' accessed by '{node.name}' must be declared in global contract of '{r.name}'")
                                # Verify mode compatibility
                                r_mode = r_globals[cg.name]
                                if cg.mode == "In_Out" and r_mode != "In_Out":
                                    raise TypeCheckError(f"{node.pos.text()}: transitive global variable '{cg.name}' with In_Out mode requires In_Out mode in '{r.name}' (got {r_mode})")
                                elif cg.mode == "Output" and r_mode not in ("Output", "In_Out"):
                                    raise TypeCheckError(f"{node.pos.text()}: transitive global variable '{cg.name}' with Output mode requires Output or In_Out mode in '{r.name}' (got {r_mode})")
                                elif cg.mode == "Input" and r_mode not in ("Input", "In_Out"):
                                    raise TypeCheckError(f"{node.pos.text()}: transitive global variable '{cg.name}' with Input mode requires Input or In_Out mode in '{r.name}' (got {r_mode})")

            if hasattr(node, "__dict__"):
                for k, v in node.__dict__.items():
                    if k == "pos":
                        continue
                    check_transitive_globals(v)

        check_transitive_globals(r.body)

        if r.depends_specs:
            seen_targets = set()
            
            # Valid targets and sources
            valid_targets = set(param_names)
            if r.kind == "function":
                valid_targets.add("result")
            for name in actual_globals:
                g_spec = next(g for g in r.global_specs if g.name == name)
                if g_spec.mode in ("Output", "In_Out"):
                    valid_targets.add(name)

            valid_sources = set(param_names)
            for name in actual_globals:
                g_spec = next(g for g in r.global_specs if g.name == name)
                if g_spec.mode in ("Input", "In_Out"):
                    valid_sources.add(name)

            mutated_vars = self.collect_mutated_vars(r.body, env, ctx)
            mutated_targets = (mutated_vars & param_names) | (mutated_vars & actual_globals)

            for d in r.depends_specs:
                if d.target in seen_targets:
                    raise TypeCheckError(f"{d.pos.text()}: duplicate dependency target: {d.target}")
                seen_targets.add(d.target)

                target_root = d.target.split('.')[0]
                if target_root not in valid_targets:
                    raise TypeCheckError(f"{d.pos.text()}: dependency target '{d.target}' not allowed or not declared as Output/In_Out")

                for src in d.sources:
                    if src == "+":
                        if target_root not in param_names and target_root not in actual_globals:
                            raise TypeCheckError(f"{d.pos.text()}: '+' source is only allowed for parameter/global targets")
                    else:
                        src_root = src.split('.')[0]
                        if src_root not in valid_sources:
                            raise TypeCheckError(f"{d.pos.text()}: dependency source '{src}' not allowed or not declared as Input/In_Out")

            seen_target_roots = {t.split('.')[0] for t in seen_targets}
            for mt in mutated_targets:
                if mt not in seen_target_roots:
                    raise TypeCheckError(f"{r.pos.text()}: target '{mt}' is modified in body but missing from depends clause")

            for target in seen_targets:
                target_root = target.split('.')[0]
                if target_root != "result" and target_root not in mutated_targets:
                    raise TypeCheckError(f"{r.pos.text()}: dependency target '{target}' is not modified in body")

            if r.kind == "function" and "result" not in seen_targets:
                raise TypeCheckError(f"{r.pos.text()}: function dependency contract must specify 'result'")

            # Information Flow Analysis
            dependencies = {}
            for name in valid_sources:
                dependencies[name] = {name}
            
            control_deps = []
            
            def get_active_control_deps():
                union_set = set()
                for s in control_deps:
                    union_set |= s
                return union_set
            
            def dependencies_of(expr) -> set[str]:
                if expr is None:
                    return set()
                if isinstance(expr, VarExpr):
                    if expr.name in dependencies:
                        return set(dependencies[expr.name])
                    if expr.name in param_names or expr.name in seen_globals:
                        return {expr.name}
                    return set()
                elif isinstance(expr, FieldAccessExpr):
                    root = expr.path[0]
                    if root in dependencies:
                        return set(dependencies[root])
                    if root in param_names or root in seen_globals:
                        return {root}
                    return set()
                elif isinstance(expr, IndexExpr):
                    return dependencies_of(VarExpr(expr.name, expr.pos)) | dependencies_of(expr.index)
                elif isinstance(expr, IndexedFieldAccessExpr):
                    return dependencies_of(VarExpr(expr.name, expr.pos)) | dependencies_of(expr.index)
                elif isinstance(expr, UnaryExpr):
                    return dependencies_of(expr.expr)
                elif isinstance(expr, BinaryExpr):
                    return dependencies_of(expr.left) | dependencies_of(expr.right)
                elif isinstance(expr, CallExpr):
                    deps = set()
                    for arg in expr.args:
                        deps |= dependencies_of(arg)
                    return deps
                elif isinstance(expr, RecordLiteralExpr):
                    deps = set()
                    for arg in expr.args:
                        deps |= dependencies_of(arg.expr)
                    return deps
                elif isinstance(expr, ArrayLiteralExpr):
                    deps = set()
                    for item in expr.items:
                        deps |= dependencies_of(item)
                    return deps
                elif isinstance(expr, AwaitExpr):
                    return dependencies_of(expr.expr)
                elif isinstance(expr, IsExpr):
                    return dependencies_of(expr.left)
                elif isinstance(expr, SpecialResultExpr):
                    return {"result"}
                return set()

            def collect_read_vars(nodes) -> set[str]:
                reads = set()
                visited = set()
                def visit(node):
                    if node is None:
                        return
                    node_id = id(node)
                    if node_id in visited:
                        return
                    visited.add(node_id)
                    
                    if isinstance(node, VarExpr):
                        reads.add(node.name)
                    elif isinstance(node, FieldAccessExpr):
                        reads.add(node.path[0])
                    elif isinstance(node, IndexExpr):
                        reads.add(node.name)
                        visit(node.index)
                    elif isinstance(node, IndexedFieldAccessExpr):
                        reads.add(node.name)
                        visit(node.index)
                    elif isinstance(node, list):
                        for child in node: 
                            visit(child)
                    elif hasattr(node, "__dict__"):
                        for k, v in node.__dict__.items():
                            if k == "pos":
                                continue
                            visit(v)
                visit(nodes)
                return reads

            def walk_body(stmts):
                for stmt in stmts:
                    if isinstance(stmt, LetStmt):
                        dependencies[stmt.name] = dependencies_of(stmt.expr) | get_active_control_deps()
                    elif isinstance(stmt, AssignStmt):
                        dependencies[stmt.name] = dependencies_of(stmt.expr) | get_active_control_deps()
                    elif isinstance(stmt, FieldAssignStmt):
                        root = stmt.path[0]
                        dependencies[root] = dependencies.get(root, set()) | dependencies_of(stmt.expr) | get_active_control_deps()
                    elif isinstance(stmt, (ReturnStmt, ReturnPlain, ReturnOk)):
                        expr_val = getattr(stmt, "value", getattr(stmt, "expr", None))
                        dependencies["result"] = dependencies.get("result", set()) | dependencies_of(expr_val) | get_active_control_deps()
                    elif isinstance(stmt, CallStmt):
                        callee = None
                        try:
                            callee = ctx.routine(stmt.name, stmt.pos)
                        except TypeCheckError:
                            pass
                        if callee:
                            callee_param_names = {p.name for p in callee.params}
                            if hasattr(callee, "depends_specs") and callee.depends_specs:
                                callee_params = [p.name for p in callee.params]
                                new_arg_deps = {}
                                
                                for d_callee in callee.depends_specs:
                                    target_var = None
                                    is_global_target = False
                                    d_target_root = d_callee.target.split('.')[0]
                                    if d_target_root in callee_params:
                                        t_idx = callee_params.index(d_target_root)
                                        if t_idx < len(stmt.args):
                                            arg_target = stmt.args[t_idx]
                                            if isinstance(arg_target, VarExpr):
                                                target_var = arg_target.name
                                            elif isinstance(arg_target, (FieldAccessExpr, IndexExpr, IndexedFieldAccessExpr)):
                                                target_var = getattr(arg_target, "name", None) or getattr(arg_target, "path", [None])[0]
                                    else:
                                        target_var = d_target_root
                                        is_global_target = True
                                        
                                    if target_var:
                                        accumulated = set()
                                        for src in d_callee.sources:
                                            if src == "+":
                                                if is_global_target:
                                                    accumulated |= dependencies.get(target_var, set())
                                                else:
                                                    accumulated |= dependencies_of(arg_target)
                                            else:
                                                src_root = src.split('.')[0]
                                                if src_root in callee_params:
                                                    s_idx = callee_params.index(src_root)
                                                    if s_idx < len(stmt.args):
                                                        accumulated |= dependencies_of(stmt.args[s_idx])
                                                else:
                                                    accumulated |= dependencies.get(src_root, set())
                                        new_arg_deps[target_var] = accumulated | get_active_control_deps()
                                for t_var, deps in new_arg_deps.items():
                                    dependencies[t_var] = deps
                            else:
                                all_args_deps = set()
                                for arg in stmt.args:
                                    all_args_deps |= dependencies_of(arg)
                                all_args_deps |= get_active_control_deps()
                                
                                for arg in stmt.args:
                                    target_var = None
                                    if isinstance(arg, VarExpr):
                                        target_var = arg.name
                                    elif isinstance(arg, (FieldAccessExpr, IndexExpr, IndexedFieldAccessExpr)):
                                        target_var = getattr(arg, "name", None) or getattr(arg, "path", [None])[0]
                                    if target_var:
                                        dependencies[target_var] = all_args_deps
                                        
                                if hasattr(callee, "global_specs") and callee.global_specs:
                                    for cg in callee.global_specs:
                                        if cg.name not in callee_param_names and cg.mode in ("Output", "In_Out"):
                                            dependencies[cg.name] = all_args_deps | dependencies.get(cg.name, set())
                    elif isinstance(stmt, IfStmt):
                        before_deps = {k: set(v) for k, v in dependencies.items()}
                        control_deps.append(dependencies_of(stmt.condition))
                        
                        walk_body(stmt.then_body)
                        then_deps = {k: set(v) for k, v in dependencies.items()}
                        
                        dependencies.clear()
                        for k, v in before_deps.items():
                            dependencies[k] = set(v)
                        walk_body(stmt.else_body)
                        else_deps = {k: set(v) for k, v in dependencies.items()}
                        
                        dependencies.clear()
                        all_keys = set(then_deps.keys()) | set(else_deps.keys()) | set(before_deps.keys())
                        for k in all_keys:
                            dependencies[k] = then_deps.get(k, before_deps.get(k, set())) | else_deps.get(k, before_deps.get(k, set()))
                        
                        control_deps.pop()
                    elif isinstance(stmt, CaseStmt):
                        before_deps = {k: set(v) for k, v in dependencies.items()}
                        control_deps.append(dependencies_of(stmt.expr))
                        
                        branch_deps_list = []
                        for branch in stmt.branches:
                            dependencies.clear()
                            for k, v in before_deps.items():
                                dependencies[k] = set(v)
                            walk_body(branch.body)
                            branch_deps_list.append({k: set(v) for k, v in dependencies.items()})
                        
                        if stmt.default_body:
                            dependencies.clear()
                            for k, v in before_deps.items():
                                dependencies[k] = set(v)
                            walk_body(stmt.default_body)
                            branch_deps_list.append({k: set(v) for k, v in dependencies.items()})
                        else:
                            branch_deps_list.append(before_deps)
                            
                        dependencies.clear()
                        all_keys = set(before_deps.keys())
                        for bd in branch_deps_list:
                            all_keys |= set(bd.keys())
                        for k in all_keys:
                            union_k = set()
                            for bd in branch_deps_list:
                                union_k |= bd.get(k, before_deps.get(k, set()))
                            dependencies[k] = union_k
                        
                        control_deps.pop()
                    elif isinstance(stmt, WhileStmt):
                        control_deps.append(dependencies_of(stmt.condition))
                        loop_reads = collect_read_vars(stmt.condition) | collect_read_vars(stmt.body)
                        loop_mutated = self.collect_mutated_vars(stmt.body, env, ctx)
                        
                        loop_read_deps = set()
                        for r_var in loop_reads:
                            if r_var in dependencies:
                                loop_read_deps |= dependencies[r_var]
                            elif r_var in param_names or r_var in seen_globals:
                                loop_read_deps.add(r_var)
                        
                        loop_deps = loop_read_deps | dependencies_of(stmt.condition) | get_active_control_deps()
                        walk_body(stmt.body)
                        for v in loop_mutated:
                            dependencies[v] = dependencies.get(v, set()) | loop_deps
                        
                        control_deps.pop()
                    elif isinstance(stmt, ScopeStmt):
                        walk_body(stmt.spawn_body)
                        walk_body(stmt.join_body)
                        walk_body(stmt.result_body)

            walk_body(r.body)
            
            for d in r.depends_specs:
                target = d.target
                target_root = target.split('.')[0]
                actual_sources = dependencies.get(target_root, set())
                declared_sources = {s.split('.')[0] for s in d.sources if s != "+"}
                if "+" in d.sources:
                    declared_sources.add(target_root)
                
                extra_sources = actual_sources - declared_sources
                extra_sources = {s for s in extra_sources if s in param_names or s in seen_globals}
                if extra_sources:
                    raise TypeCheckError(f"{d.pos.text()}: dependency violation: target '{target}' depends on undeclared source(s): {', '.join(sorted(extra_sources))}")

    def abort_names(self, r):
        return {clause.error_name for clause in r.aborts}

    def require_abort_propagation(self, caller, callee, pos):
        missing = sorted(self.abort_names(callee) - self.abort_names(caller))
        if missing:
            error_name = missing[0]
            raise TypeCheckError(f"{pos.text()}: caller does not handle or propagate abort: {callee.name} may abort {error_name}")

    def abort_condition(self, r, error_name):
        for clause in r.aborts:
            if clause.error_name == error_name:
                return clause.condition
        return None

    def require_abort_condition_covered(self, stmt, r, path_conditions):
        condition = self.abort_condition(r, stmt.error_name)
        if condition is None:
            return
        if any(self.same_expr(condition, path_condition) for path_condition in path_conditions):
            return
        raise TypeCheckError(f"{stmt.pos.text()}: abort condition not covered by abort contract: {stmt.error_name}")

    def same_expr(self, left, right):
        if type(left) is not type(right):
            return False
        if isinstance(left, (NumberExpr, DoubleExpr, BoolExpr, StringExpr)):
            return left.value == right.value
        if isinstance(left, VarExpr):
            return left.name == right.name
        if isinstance(left, FieldAccessExpr):
            return left.path == right.path
        if isinstance(left, IndexedFieldAccessExpr):
            return left.name == right.name and left.fields == right.fields and self.same_expr(left.index, right.index)
        if isinstance(left, SpecialResultExpr):
            return left.name == right.name
        if isinstance(left, UnaryExpr):
            return left.op == right.op and self.same_expr(left.expr, right.expr)
        if isinstance(left, BinaryExpr):
            if left.op != right.op:
                return False
            if self.same_expr(left.left, right.left) and self.same_expr(left.right, right.right):
                return True
            return left.op in {"=", "!="} and self.same_expr(left.left, right.right) and self.same_expr(left.right, right.left)
        return False

    def negated_condition(self, condition):
        return UnaryExpr("not", condition, condition.pos)

    def block(self, body, r, env, ctx, path_conditions=None):
        path_conditions = path_conditions or []
        saw = False
        for s in body:
            if saw:
                raise TypeCheckError(f"{s.pos.text()}: unreachable statement after guaranteed exit")
            if isinstance(s, LetStmt):
                self.validate_identifier(s.name, s.pos)
                ctx.require_return_type(s.type_ref, s.pos)
                actual = self.infer(s.expr, env, ctx, False, None)
                self.assign(actual, s.type_ref, ctx, s.pos); env[s.name]=s.type_ref
                self.check_range_bounds(s.expr, s.type_ref, ctx, s.pos)
                ctx.note_let(s.name, s.type_ref, s.expr, s.pos)
            elif isinstance(s, AssignStmt):
                if s.name not in env:
                    raise TypeCheckError(f"{s.pos.text()}: unknown assignment target: {s.name}")
                self.assign(self.infer(s.expr, env, ctx, False, None), env[s.name], ctx, s.pos)
                self.check_range_bounds(s.expr, env[s.name], ctx, s.pos)
            elif isinstance(s, FieldAssignStmt):
                target_type = self.infer_field_path_obj(s.path, s.pos, env, ctx, False, None)
                self.assign(self.infer(s.expr, env, ctx, False, None), target_type, ctx, s.pos)
                self.check_range_bounds(s.expr, target_type, ctx, s.pos)
            elif isinstance(s, ReturnStmt):
                ctx.reject_scope_handle_escape(s.value)
                ctx.require_no_unjoined_scope_handles(s.pos)
                self.ret(s.value, r.return_type, env, ctx); saw = True
            elif isinstance(s, AbortStmt):
                if s.error_name not in ctx.errors:
                    raise TypeCheckError(f"{s.pos.text()}: unknown abort error: {s.error_name}")
                if s.error_name not in {clause.error_name for clause in r.aborts}:
                    raise TypeCheckError(f"{s.pos.text()}: abort not declared by routine: {s.error_name}")
                self.require_abort_condition_covered(s, r, path_conditions)
                saw = True
            elif isinstance(s, CheckStmt):
                self.statement_bool("check", s.expr, env, ctx, False, None)
            elif isinstance(s, IfStmt):
                self.statement_bool("if condition", s.condition, env, ctx, False, None)
                then_path = [*path_conditions, s.condition]
                else_path = [*path_conditions, self.negated_condition(s.condition)]
                saw = saw or (self.block(s.then_body, r, dict(env), ctx, then_path) and self.block(s.else_body, r, dict(env), ctx, else_path))
            elif isinstance(s, WhileStmt):
                self.statement_bool("while condition", s.condition, env, ctx, False, None)
                for invariant in s.invariants:
                    self.statement_bool("while invariant", invariant, env, ctx, False, None)
                if s.variant is not None:
                    variant_type = self.infer(s.variant, env, ctx, False, None)
                    if self.base(variant_type, ctx) != "Integer":
                        raise TypeCheckError(f"{s.variant.pos.text()}: while variant must be Integer, got {type_to_string(variant_type)}")
                self.block(s.body, r, dict(env), ctx, path_conditions)
            elif isinstance(s, CaseStmt):
                case_t = self.infer(s.expr, env, ctx, False, None)
                seen_literals = set()
                branch_returns = []
                for br in s.branches:
                    br_t = self.infer(br.value, env, ctx, False, None)
                    if self.base(case_t, ctx) != self.base(br_t, ctx):
                        raise TypeCheckError(f"{br.pos.text()}: case branch type {type_to_string(br_t)} does not match case expression {type_to_string(case_t)}")
                    if isinstance(br.value, NumberExpr):
                        key = ("number", br.value.value)
                    elif isinstance(br.value, DoubleExpr):
                        key = ("double", br.value.value)
                    elif isinstance(br.value, BoolExpr):
                        key = ("bool", br.value.value)
                    elif isinstance(br.value, VarExpr):
                        key = ("var", br.value.name)
                    else:
                        key = None
                    if key is not None:
                        if key in seen_literals:
                            raise TypeCheckError(f"{br.pos.text()}: duplicate case branch value")
                        seen_literals.add(key)
                    branch_returns.append(self.block(br.body, r, dict(env), ctx, path_conditions))
                default_returns = self.block(s.default_body, r, dict(env), ctx, path_conditions)
                saw = saw or (all(branch_returns) and default_returns)
            elif isinstance(s, ScopeStmt):
                self.validate_identifier(s.name, s.pos)
                scope_env = dict(env)
                scope_env[s.name] = TypeName("Scope")
                ctx.scope_vars.add(s.name)
                try:
                    self.block(s.spawn_body, r, scope_env, ctx, path_conditions)
                    self.block(s.join_body, r, scope_env, ctx, path_conditions)
                    saw = saw or self.block(s.result_body, r, scope_env, ctx, path_conditions)
                    ctx.require_no_unjoined_scope_handles(s.pos, s.name)
                finally:
                    ctx.scope_vars.discard(s.name)
            elif isinstance(s, CallStmt):
                if self.std_procedure_call(s.name, s.args, env, ctx, s.pos):
                    continue
                cal = ctx.routine(s.name, s.pos)
                if cal.kind != "procedure": raise TypeCheckError(f"{s.pos.text()}: call requires procedure")

                # Enforce anti-aliasing rules for parameters and globals
                if len(s.args) == len(cal.params):
                    def get_root_var(expr):
                        if isinstance(expr, VarExpr):
                            return expr.name
                        elif isinstance(expr, (FieldAccessExpr, IndexExpr, IndexedFieldAccessExpr)):
                            if isinstance(expr, FieldAccessExpr):
                                return expr.path[0] if expr.path else None
                            else:
                                return expr.name
                        return None

                    def get_param_mode(param_name):
                        if hasattr(cal, "global_specs") and cal.global_specs:
                            for g in cal.global_specs:
                                if g.name == param_name:
                                    return g.mode
                        return "Input"

                    arg_roots = [get_root_var(arg) for arg in s.args]
                    mutable_param_indices = [
                        idx for idx, param in enumerate(cal.params)
                        if get_param_mode(param.name) in ("Output", "In_Out")
                    ]

                    callee_globals = set()
                    callee_mut_globals = set()
                    callee_param_names = {p.name for p in cal.params}
                    if hasattr(cal, "global_specs") and cal.global_specs:
                        for cg in cal.global_specs:
                            if cg.name not in callee_param_names:
                                callee_globals.add(cg.name)
                                if cg.mode in ("Output", "In_Out"):
                                    callee_mut_globals.add(cg.name)

                    # 1. Parameter-Parameter Aliasing:
                    for i in range(len(s.args)):
                        root_i = arg_roots[i]
                        if not root_i:
                            continue
                        is_i_mutable = (i in mutable_param_indices)
                        for j in range(i + 1, len(s.args)):
                            root_j = arg_roots[j]
                            if not root_j:
                                continue
                            is_j_mutable = (j in mutable_param_indices)
                            if (is_i_mutable or is_j_mutable) and root_i == root_j:
                                param_i = cal.params[i].name
                                param_j = cal.params[j].name
                                raise TypeCheckError(
                                    f"{s.pos.text()}: aliasing detected in call to '{s.name}': "
                                    f"both '{param_i}' and '{param_j}' resolve to the same variable '{root_i}' "
                                    f"(at least one is mutable)"
                                )

                    # 2. Parameter-Global Aliasing:
                    for idx in mutable_param_indices:
                        root_arg = arg_roots[idx]
                        if root_arg and root_arg in callee_globals:
                            param_name = cal.params[idx].name
                            raise TypeCheckError(
                                f"{s.pos.text()}: aliasing detected in call to '{s.name}': "
                                f"mutable parameter '{param_name}' is passed global variable '{root_arg}' "
                                f"which is also accessed directly/transitively by '{s.name}'"
                            )

                    # 3. Argument-Global Aliasing:
                    for idx, root_arg in enumerate(arg_roots):
                        if root_arg and root_arg in callee_mut_globals:
                            param_name = cal.params[idx].name
                            raise TypeCheckError(
                                f"{s.pos.text()}: aliasing detected in call to '{s.name}': "
                                f"argument '{param_name}' resolves to global variable '{root_arg}' "
                                f"which is mutated by '{s.name}'"
                            )

                substitutions = self.routine_type_substitutions(cal, s.type_args, s.pos, s.args, env, ctx)
                self.args(cal, s.args, env, ctx, s.pos, substitutions)
                self.require_abort_propagation(r, cal, s.pos)
        return saw

    def statement_bool(self, label, expr, env, ctx, allow_result, result_type):
        actual = self.infer(expr, env, ctx, allow_result, result_type)
        if self.base(actual, ctx) != "Boolean":
            raise TypeCheckError(f"{expr.pos.text()}: {label} requires Boolean, got {type_to_string(actual)}")

    def contract_bool(self, label, expr, env, ctx, allow_result, result_type):
        actual = self.infer(expr, env, ctx, allow_result, result_type)
        if self.base(actual, ctx) != "Boolean":
            raise TypeCheckError(f"{expr.pos.text()}: contract {label} requires Boolean, got {type_to_string(actual)}")

    def contract_value_type(self, name, pos, allow_result, result_type):
        if not allow_result or result_type is None:
            if name != "value":
                raise TypeCheckError(f"{pos.text()}: Result contract expression {name} is only available in Result ensures")
            raise TypeCheckError(f"{pos.text()}: contract expression {name} is only available in function ensures")
        if name == "value":
            return result_type.ok_type if isinstance(result_type, ResultTypeName) else result_type
        if isinstance(result_type, ResultTypeName):
            if name in ("success", "failure"):
                return TypeName("Boolean")
            if name == "error":
                return TypeName(result_type.error_type)
        raise TypeCheckError(f"{pos.text()}: Result contract expression {name} is only available in Result ensures")

    def ret(self, rv, expected, env, ctx):
        if expected is None:
            raise TypeCheckError(f"{rv.pos.text()}: procedure cannot return a value")
        if isinstance(expected, ResultTypeName):
            if isinstance(rv, ReturnOk):
                actual = self.infer(rv.expr, env, ctx, False, None)
                ok_type = expected.ok_type
                if self.base(actual, ctx) != self.base(ok_type, ctx):
                    raise TypeCheckError(f"{rv.pos.text()}: Result ok type mismatch: expected {type_to_string(ok_type)}, got {type_to_string(actual)}")
                self.assign(actual, ok_type, ctx, rv.pos)
                self.check_range_bounds(rv.expr, ok_type, ctx, rv.pos)
            elif isinstance(rv, ReturnError):
                if rv.error_name not in ctx.errors:
                    raise TypeCheckError(f"{rv.pos.text()}: unknown error: {rv.error_name}")
                if rv.error_name != expected.error_type:
                    raise TypeCheckError(f"{rv.pos.text()}: Function returns {type_to_string(expected)}, cannot return error {rv.error_name}")
            elif isinstance(rv, ReturnPlain):
                actual = self.infer(rv.expr, env, ctx, False, None)
                if not isinstance(actual, ResultTypeName):
                    raise TypeCheckError(f"{rv.pos.text()}: Result function must return ok or error")
                self.assign(actual, expected, ctx, rv.pos)
            else: raise TypeCheckError(f"{rv.pos.text()}: Result function must return ok or error")
        else:
            if not isinstance(rv, ReturnPlain): raise TypeCheckError(f"{rv.pos.text()}: plain function must return expression")
            actual = self.infer(rv.expr, env, ctx, False, None)
            if self.base(actual, ctx) != self.base(expected, ctx):
                raise TypeCheckError(f"{rv.pos.text()}: function return type mismatch: expected {type_to_string(expected)}, got {type_to_string(actual)}")
            self.assign(actual, expected, ctx, rv.pos)
            self.check_range_bounds(rv.expr, expected, ctx, rv.pos)

    def infer_field_path_obj(self, path, pos, env, ctx, allow_result, result_type):
        root = path[0]
        if root == "result" and allow_result and result_type is not None:
            t = result_type
        elif root == "value" and allow_result and result_type is not None:
            t = self.contract_value_type(root, pos, allow_result, result_type)
        elif root == "error" and allow_result and isinstance(result_type, ResultTypeName):
            t = TypeName(result_type.error_type)
        elif root in {"result", "value", "error"}:
            raise TypeCheckError(f"{pos.text()}: Result contract expression {root} is only available in ensures")
        else:
            if root not in env: raise TypeCheckError(f"{pos.text()}: unknown record variable: {root}")
            t = env[root]
        for field in path[1:]:
            if isinstance(t, ResultTypeName):
                if field == "ok":
                    t = TypeName("Boolean")
                    continue
                if field == "value":
                    t = t.ok_type
                    continue
                if field == "error":
                    t = TypeName(t.error_type)
                    continue
                raise TypeCheckError(f"{pos.text()}: unknown Result field {field}")
            if not isinstance(t, TypeName) or t.name not in ctx.records:
                raise TypeCheckError(f"{pos.text()}: field access requires record before .{field}, got {type_to_string(t)}")
            rec = ctx.records[t.name]
            if field not in rec.fields:
                raise TypeCheckError(f"{pos.text()}: unknown field {field} for record {t.name}")
            t = self.parse_type_ref(rec.fields[field], ctx)
        return t

    def infer_field_path(self, e, env, ctx, allow_result=False, result_type=None):
        return self.infer_field_path_obj(e.path, e.pos, env, ctx, allow_result, result_type)

    def infer_index_target(self, name, index, pos, env, ctx, allow_result, result_type):
        if name == "value" and allow_result and result_type is not None:
            arr_t = self.contract_value_type(name, pos, allow_result, result_type)
        elif name in {"result", "value", "error"}:
            raise TypeCheckError(f"{pos.text()}: Result contract expression {name} is only available in ensures")
        else:
            if name not in env:
                raise TypeCheckError(f"{pos.text()}: unknown array: {name}")
            arr_t = env[name]
        if not isinstance(arr_t, ArrayTypeName):
            raise TypeCheckError(f"{pos.text()}: index access requires Array, got {type_to_string(arr_t)}")
        index_type = self.infer(index, env, ctx, allow_result, result_type)
        if self.base(index_type, ctx) != "Integer":
            raise TypeCheckError(f"{index.pos.text()}: array index must be Integer, got {type_to_string(index_type)}")
        if isinstance(index, NumberExpr) and not (0 <= index.value < arr_t.size):
            raise TypeCheckError(f"{pos.text()}: array index out of bounds: {index.value} for size {arr_t.size}")
        return TypeName(arr_t.element_type)

    def infer_indexed_field_access(self, e, env, ctx, allow_result, result_type):
        t = self.infer_index_target(e.name, e.index, e.pos, env, ctx, allow_result, result_type)
        for field in e.fields:
            if not isinstance(t, TypeName) or t.name not in ctx.records:
                raise TypeCheckError(f"{e.pos.text()}: field access requires record before .{field}, got {type_to_string(t)}")
            rec = ctx.records[t.name]
            if field not in rec.fields:
                raise TypeCheckError(f"{e.pos.text()}: unknown field {field} for record {t.name}")
            t = self.parse_type_ref(rec.fields[field], ctx)
        return t

    def builtin_call_type(self, e, env, ctx, allow_result, result_type):
        def expect_count(n):
            if len(e.args) != n:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects {n} arguments")
        def expect_arg(i, base):
            if i >= len(e.args):
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects more arguments")
            if isinstance(e.args[i], NamedArg):
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} does not accept named argument: {e.args[i].name}")
            t = self.infer(e.args[i], env, ctx, allow_result, result_type)
            if self.base(t, ctx) != base:
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} argument {i+1} expected {base}, got {type_to_string(t)}")
        def infer_arg(i):
            if i >= len(e.args):
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects more arguments")
            if isinstance(e.args[i], NamedArg):
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} does not accept named argument: {e.args[i].name}")
            return self.infer(e.args[i], env, ctx, allow_result, result_type)
        def expect_numeric(i):
            t = infer_arg(i)
            base = self.base(t, ctx)
            if base not in ("Integer", "Double"):
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} argument {i+1} expected numeric, got {type_to_string(t)}")
            return base
        def expect_type(i, expected):
            t = infer_arg(i)
            if self.base(t, ctx) != expected:
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} argument {i+1} expected {expected}, got {type_to_string(t)}")
        def expect_exact_type(i, expected):
            t = infer_arg(i)
            expected_type = TypeName(expected)
            if self.base(t, ctx) != self.base(expected_type, ctx):
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} argument {i+1} expected {expected}, got {type_to_string(t)}")
            self.assign(t, expected_type, ctx, e.args[i].pos)
        def require_builtin_type_arg(count=1):
            if not e.type_args:
                raise TypeCheckError(f"{e.pos.text()}: generic routine requires {count} type argument(s): {e.name}")
            if len(e.type_args) != count:
                raise TypeCheckError(f"{e.pos.text()}: generic routine {e.name} expects {count} type argument(s), got {len(e.type_args)}")
            for type_arg in e.type_args:
                ctx.require_type_or_record(type_arg, e.pos)
            return e.type_args[0]
        def expect_json_serializable(t, pos, path, top_level=False):
            if isinstance(t, TypeName) and t.name in ctx.records:
                for field_name, field_type in ctx.records[t.name].fields.items():
                    expect_json_serializable(TypeName(field_type), pos, f"{path}.{field_name}")
                return
            if top_level:
                raise TypeCheckError(f"{pos.text()}: Json.stringify argument 1 expected record, got {type_to_string(t)}")
            if isinstance(t, ArrayTypeName):
                expect_json_serializable(TypeName(t.element_type), pos, f"{path}[]")
                return
            if isinstance(t, TypeName) and self.base(t, ctx) in ("String", "Integer", "Boolean", "Double"):
                return
            raise TypeCheckError(f"{pos.text()}: Json.stringify cannot serialize {type_to_string(t)} at {path}")
        if e.name == "channel":
            item_type = require_builtin_type_arg()
            expect_count(1)
            expect_type(0, "Integer")
            if getattr(e, "invariant", None) is not None:
                inv_t = self.infer(e.invariant, env, ctx, allow_result, result_type)
                if self.base(inv_t, ctx) != "Boolean":
                    raise TypeCheckError(f"{e.invariant.pos.text()}: channel invariant must be Boolean, got {type_to_string(inv_t)}")
            return TypeName(f"Channel<{item_type}>")
        if e.name == "channel_sender":
            item_type = require_builtin_type_arg()
            expect_count(1)
            expect_exact_type(0, f"Channel<{item_type}>")
            return TypeName(f"Sender<{item_type}>")
        if e.name == "channel_receiver":
            item_type = require_builtin_type_arg()
            expect_count(1)
            expect_exact_type(0, f"Channel<{item_type}>")
            return TypeName(f"Receiver<{item_type}>")
        if e.name == "channel_send":
            item_type = require_builtin_type_arg()
            expect_count(2)
            expect_exact_type(0, f"Sender<{item_type}>")
            expect_exact_type(1, item_type)
            return AwaitableType(TypeName("Boolean"))
        if e.name == "channel_receive":
            item_type = require_builtin_type_arg()
            expect_count(1)
            expect_exact_type(0, f"Receiver<{item_type}>")
            return AwaitableType(TypeName(item_type))
        if e.name == "scope":
            if e.type_args:
                raise TypeCheckError(f"{e.pos.text()}: non-generic routine used with type arguments: {e.name}")
            expect_count(0)
            return TypeName("Scope")
        if e.name == "scope_spawn":
            item_type = require_builtin_type_arg()
            expect_count(2)
            expect_exact_type(0, "Scope")
            expect_exact_type(1, f"JoinHandle<{item_type}>")
            if not isinstance(e.args[0], VarExpr) or e.args[0].name not in ctx.scope_vars:
                raise TypeCheckError(f"{e.args[0].pos.text()}: scope_spawn requires a local Scope created by scope(), got {type_to_string(self.infer(e.args[0], env, ctx, allow_result, result_type))}")
            return TypeName(f"JoinHandle<{item_type}>")
        if e.name == "scope_join":
            item_type = require_builtin_type_arg()
            expect_count(2)
            expect_exact_type(0, "Scope")
            expect_exact_type(1, f"JoinHandle<{item_type}>")
            if isinstance(e.args[0], VarExpr) and isinstance(e.args[1], VarExpr):
                ctx.mark_scope_handle_joined(e.args[0].name, e.args[1].name, e.args[1].pos)
            return AwaitableType(TypeName(item_type))
        method_owner, method_name = ctx.scope_method_name(e.name)
        if method_name == "spawn":
            item_type = require_builtin_type_arg()
            expect_count(1)
            if method_owner not in ctx.scope_vars:
                raise TypeCheckError(f"{e.pos.text()}: scope spawn requires a local Scope created by scope block: {method_owner}")
            task_type = infer_arg(0)
            if not isinstance(task_type, AwaitableType):
                raise TypeCheckError(f"{e.args[0].pos.text()}: scope spawn requires an awaitable expression, got {type_to_string(task_type)}")
            self.assign(task_type.inner_type, TypeName(item_type), ctx, e.args[0].pos)
            return TypeName(f"JoinHandle<{item_type}>")
        if method_name == "join":
            item_type = require_builtin_type_arg()
            expect_count(1)
            if method_owner not in ctx.scope_vars:
                raise TypeCheckError(f"{e.pos.text()}: scope join requires a local Scope created by scope block: {method_owner}")
            expect_exact_type(0, f"JoinHandle<{item_type}>")
            if isinstance(e.args[0], VarExpr):
                ctx.mark_scope_handle_joined(method_owner, e.args[0].name, e.args[0].pos)
            return AwaitableType(TypeName(item_type))
        if e.name == "String.concat":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: String.concat expects 2 arguments")
            expect_arg(0, "String"); expect_arg(1, "String")
            return TypeName("String")
        if e.name == "String.substr":
            if len(e.args) != 3:
                raise TypeCheckError(f"{e.pos.text()}: String.substr expects 3 arguments")
            expect_arg(0, "String"); expect_arg(1, "Integer"); expect_arg(2, "Integer")
            return TypeName("String")
        if e.name == "String.replace":
            if len(e.args) != 3:
                raise TypeCheckError(f"{e.pos.text()}: String.replace expects 3 arguments")
            expect_arg(0, "String"); expect_arg(1, "String"); expect_arg(2, "String")
            return TypeName("String")
        if e.name == "String.instr":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: String.instr expects 2 arguments")
            expect_arg(0, "String"); expect_arg(1, "String")
            return TypeName("Integer")
        if e.name == "String.length":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: String.length expects 1 arguments")
            expect_arg(0, "String")
            return TypeName("Integer")
        if e.name == "String.template":
            if len(e.args) < 1:
                raise TypeCheckError(f"{e.pos.text()}: String.template expects at least 1 argument")
            if isinstance(e.args[0], NamedArg):
                raise TypeCheckError(f"{e.args[0].pos.text()}: String.template template argument must be positional")
            expect_arg(0, "String")
            positional_values = []
            named_values = []
            saw_named = False
            for arg in e.args[1:]:
                if isinstance(arg, NamedArg):
                    saw_named = True
                    named_values.append(arg)
                else:
                    if saw_named:
                        raise TypeCheckError(f"{arg.pos.text()}: String.template positional template value after named binding")
                    positional_values.append(arg)
            if positional_values and named_values:
                raise TypeCheckError(f"{e.pos.text()}: String.template cannot mix positional and named template arguments")
            for index, arg in enumerate(positional_values, start=1):
                t = self.infer(arg, env, ctx, allow_result, result_type)
                if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                    raise TypeCheckError(f"{arg.pos.text()}: String.template template value {index} expected String, Integer, Boolean, or Double, got {type_to_string(t)}")
            for arg in named_values:
                t = self.infer(arg.expr, env, ctx, allow_result, result_type)
                if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                    raise TypeCheckError(f"{arg.expr.pos.text()}: String.template template value {arg.name} expected String, Integer, Boolean, or Double, got {type_to_string(t)}")
            if isinstance(e.args[0], StringExpr):
                try:
                    validate_template(e.args[0].value, len(positional_values), [arg.name for arg in named_values])
                except ValueError as exc:
                    raise TypeCheckError(f"{e.args[0].pos.text()}: String.template {exc}") from exc
            return TypeName("String")
        if e.name == "Json.stringify":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Json.stringify expects 1 arguments")
            actual = infer_arg(0)
            expect_json_serializable(actual, e.args[0].pos, "value", top_level=True)
            return TypeName("String")
        if e.name in {"Math.sin", "Math.cos", "Math.tan", "Math.sqrt"}:
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 1 arguments")
            expect_numeric(0)
            return TypeName("Double")
        if e.name == "Math.pow":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: Math.pow expects 2 arguments")
            expect_numeric(0); expect_numeric(1)
            return TypeName("Double")
        if e.name == "Math.abs":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Math.abs expects 1 arguments")
            return TypeName(expect_numeric(0))
        if e.name in {"Math.min", "Math.max"}:
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 2 arguments")
            left = expect_numeric(0); right = expect_numeric(1)
            return TypeName("Double" if "Double" in (left, right) else "Integer")
        if e.name in {"Math.floor", "Math.ceil"}:
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 1 arguments")
            expect_numeric(0)
            return TypeName("Integer")
        if e.name in {"Big.int", "Big.integer"}:
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 1 arguments")
            expect_type(0, "String")
            return TypeName("BigInteger")
        if e.name == "Big.fromInteger":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Big.fromInteger expects 1 arguments")
            expect_type(0, "Integer")
            return TypeName("BigInteger")
        if e.name == "Big.float":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: Big.float expects 2 arguments")
            expect_type(0, "String"); expect_type(1, "Integer")
            return TypeName("BigFloat")
        if e.name == "Big.floatFromInteger":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: Big.floatFromInteger expects 2 arguments")
            expect_type(0, "BigInteger"); expect_type(1, "Integer")
            return TypeName("BigFloat")
        if e.name in {"Big.addInt", "Big.subInt", "Big.mulInt", "Big.divInt"}:
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 2 arguments")
            expect_type(0, "BigInteger"); expect_type(1, "BigInteger")
            return TypeName("BigInteger")
        if e.name in {"Big.negInt", "Big.absInt"}:
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 1 arguments")
            expect_type(0, "BigInteger")
            return TypeName("BigInteger")
        if e.name == "Big.signInt":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Big.signInt expects 1 arguments")
            expect_type(0, "BigInteger")
            return TypeName("Integer")
        if e.name in {"Big.addFloat", "Big.subFloat", "Big.mulFloat", "Big.divFloat"}:
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 2 arguments")
            expect_type(0, "BigFloat"); expect_type(1, "BigFloat")
            return TypeName("BigFloat")
        if e.name in {"Big.sqrt", "Big.absFloat"}:
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects 1 arguments")
            expect_type(0, "BigFloat")
            return TypeName("BigFloat")
        if e.name == "Big.signFloat":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Big.signFloat expects 1 arguments")
            expect_type(0, "BigFloat")
            return TypeName("Integer")
        if e.name == "Big.toString":
            if len(e.args) != 1:
                raise TypeCheckError(f"{e.pos.text()}: Big.toString expects 1 arguments")
            expect_type(0, "BigInteger")
            return TypeName("String")
        if e.name == "Big.format":
            if len(e.args) != 2:
                raise TypeCheckError(f"{e.pos.text()}: Big.format expects 2 arguments")
            expect_type(0, "BigFloat"); expect_type(1, "Integer")
            return TypeName("String")
        return None

    def infer(self, e, env, ctx, allow_result, result_type):
        if isinstance(e, StringExpr): return TypeName("String")
        if isinstance(e, NumberExpr): return TypeName("Integer")
        if isinstance(e, DoubleExpr): return TypeName("Double")
        if isinstance(e, BoolExpr): return TypeName("Boolean")
        if isinstance(e, FieldAccessExpr): return self.infer_field_path(e, env, ctx, allow_result, result_type)
        if isinstance(e, IndexedFieldAccessExpr): return self.infer_indexed_field_access(e, env, ctx, allow_result, result_type)
        if isinstance(e, RecordLiteralExpr):
            if e.type_name not in ctx.records:
                ctx.require_type_or_record(e.type_name, e.pos)
            if e.type_name not in ctx.records: raise TypeCheckError(f"{e.pos.text()}: unknown record type: {e.type_name}")
            rec, seen = ctx.records[e.type_name], set()
            for a in e.args:
                if a.name in seen: raise TypeCheckError(f"{a.pos.text()}: duplicate record literal field: {a.name}")
                seen.add(a.name)
                if a.name not in rec.fields:
                    raise TypeCheckError(f"{a.pos.text()}: unknown field for {e.type_name}: {a.name}")
                field_type = self.parse_type_ref(rec.fields[a.name], ctx)
                self.assign(self.infer(a.expr, env, ctx, allow_result, result_type), field_type, ctx, a.pos)
                self.check_range_bounds(a.expr, field_type, ctx, a.pos)
            missing = set(rec.fields) - seen
            if missing: raise TypeCheckError(f"{e.pos.text()}: missing record field(s) for {e.type_name}: {', '.join(sorted(missing))}")
            return TypeName(e.type_name)
        if isinstance(e, ArrayLiteralExpr):
            if not e.items:
                return ArrayLiteralType("Empty", 0)
            first = self.infer(e.items[0], env, ctx, allow_result, result_type)
            if not isinstance(first, TypeName):
                raise TypeCheckError(f"{e.pos.text()}: array literal elements must be scalar")
            for item in e.items[1:]:
                t = self.infer(item, env, ctx, allow_result, result_type)
                if not isinstance(t, TypeName) or self.base(t, ctx) != self.base(first, ctx):
                    raise TypeCheckError(f"{e.pos.text()}: array literal has mixed element types")
            return ArrayLiteralType(first.name, len(e.items))
        if isinstance(e, IndexExpr):
            return self.infer_index_target(e.name, e.index, e.pos, env, ctx, allow_result, result_type)
        if isinstance(e, ForAllExpr) or isinstance(e, ExistsExpr):
            lower_t = self.infer(e.lower, env, ctx, allow_result, result_type)
            upper_t = self.infer(e.upper, env, ctx, allow_result, result_type)
            if self.base(lower_t, ctx) != "Integer":
                raise TypeCheckError(f"{e.lower.pos.text()}: quantifier lower bound must be Integer, got {type_to_string(lower_t)}")
            if self.base(upper_t, ctx) != "Integer":
                raise TypeCheckError(f"{e.upper.pos.text()}: quantifier upper bound must be Integer, got {type_to_string(upper_t)}")
            new_env = dict(env)
            new_env[e.var_name] = TypeName("Integer")
            body_t = self.infer(e.expr, new_env, ctx, allow_result, result_type)
            if self.base(body_t, ctx) != "Boolean":
                raise TypeCheckError(f"{e.expr.pos.text()}: quantifier body must be Boolean, got {type_to_string(body_t)}")
            return TypeName("Boolean")
        if isinstance(e, SpecialResultExpr):
            return self.contract_value_type(e.name, e.pos, allow_result, result_type)
        if isinstance(e, VarExpr):
            if e.name in ctx.errors: return TypeName(e.name)
            if e.name == "result" and allow_result and result_type: return result_type
            if e.name not in env:
                raise TypeCheckError(f"{e.pos.text()}: unknown variable: {e.name}")
            return env[e.name]
        if isinstance(e, CallExpr):
            return self.call_expr_type(e, env, ctx, allow_result, result_type)
        if isinstance(e, AwaitExpr):
            if not ctx.current_async:
                raise TypeCheckError(f"{e.pos.text()}: await is only allowed inside async routines")
            awaited = self.infer(e.expr, env, ctx, allow_result, result_type)
            if not isinstance(awaited, AwaitableType):
                join_inner = ctx.join_handle_inner_type(awaited)
                if join_inner is not None:
                    return TypeName(join_inner)
                raise TypeCheckError(f"{e.pos.text()}: await requires an awaitable expression, got {type_to_string(awaited)}")
            return awaited.inner_type
        if isinstance(e, IsExpr):
            left_name = None
            if isinstance(e.left, VarExpr): left_name = e.left.name
            elif isinstance(e.left, TypeName): left_name = e.left.name
            if left_name in ctx.current_type_params:
                if e.right not in ("Comparable", "Equatable", "Numeric"):
                    raise TypeCheckError(f"{e.pos.text()}: unknown type constraint: {e.right}")
                ctx.type_param_constraints[left_name] = e.right
                return TypeName("Boolean")
            else:
                if left_name in ctx.types or left_name in ctx.records:
                    if e.right not in ("Comparable", "Equatable", "Numeric"):
                        raise TypeCheckError(f"{e.pos.text()}: unknown type constraint: {e.right}")
                    if e.right == "Comparable" and left_name not in ("Integer", "Double"):
                        raise TypeCheckError(f"{e.pos.text()}: type {left_name} is not Comparable")
                    if e.right == "Numeric" and left_name not in ("Integer", "Double"):
                        raise TypeCheckError(f"{e.pos.text()}: type {left_name} is not Numeric")
                    return TypeName("Boolean")
                raise TypeCheckError(f"{e.pos.text()}: type parameter {left_name} not found in scope")
        if isinstance(e, UnaryExpr):
            operand = self.infer(e.expr, env, ctx, allow_result, result_type)
            if e.op == "not":
                if self.base(operand, ctx) != "Boolean":
                    raise TypeCheckError(f"{e.pos.text()}: unary not requires Boolean, got {type_to_string(operand)}")
                return TypeName("Boolean")
            if self.base(operand, ctx) not in ("Integer", "Double"):
                raise TypeCheckError(f"{e.pos.text()}: unary - requires numeric operand, got {type_to_string(operand)}")
            return operand
        if isinstance(e, BinaryExpr):
            if e.op in ("=","!="):
                a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
                base_a = self.base(a, ctx)
                base_b = self.base(b, ctx)
                is_a_param = isinstance(a, TypeName) and a.name in ctx.current_type_params
                is_b_param = isinstance(b, TypeName) and b.name in ctx.current_type_params
                if is_a_param and is_b_param and a.name == b.name:
                    constraint = ctx.type_param_constraints.get(a.name)
                    if constraint not in ("Equatable", "Comparable", "Numeric"):
                        raise TypeCheckError(f"{e.pos.text()}: type parameter {a.name} does not support equality comparison (requires Equatable, Comparable, or Numeric)")
                elif base_a != base_b:
                    raise TypeCheckError(f"{e.pos.text()}: cannot compare {type_to_string(a)} with {type_to_string(b)}")
                return TypeName("Boolean")
            if e.op in ("and", "or"):
                a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
                if self.base(a, ctx) != "Boolean" or self.base(b, ctx) != "Boolean":
                    raise TypeCheckError(f"{e.pos.text()}: boolean operator {e.op} requires Boolean operands, got {type_to_string(a)} and {type_to_string(b)}")
                return TypeName("Boolean")
            if e.op in ("<","<=",">",">="):
                a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
                base_a = self.base(a, ctx)
                base_b = self.base(b, ctx)
                is_a_param = isinstance(a, TypeName) and a.name in ctx.current_type_params
                is_b_param = isinstance(b, TypeName) and b.name in ctx.current_type_params
                if is_a_param and is_b_param and a.name == b.name:
                    constraint = ctx.type_param_constraints.get(a.name)
                    if constraint not in ("Comparable", "Numeric"):
                        raise TypeCheckError(f"{e.pos.text()}: type parameter {a.name} does not support ordering comparison (requires Comparable or Numeric)")
                elif base_a not in ("Integer", "Double") or base_b not in ("Integer", "Double"):
                    raise TypeCheckError(f"{e.pos.text()}: comparison operator {e.op} requires numeric operands, got {type_to_string(a)} and {type_to_string(b)}")
                return TypeName("Boolean")
            a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
            base_a = self.base(a, ctx)
            base_b = self.base(b, ctx)
            is_a_param = isinstance(a, TypeName) and a.name in ctx.current_type_params
            is_b_param = isinstance(b, TypeName) and b.name in ctx.current_type_params
            if is_a_param and is_b_param and a.name == b.name:
                constraint = ctx.type_param_constraints.get(a.name)
                if constraint != "Numeric":
                    raise TypeCheckError(f"{e.pos.text()}: type parameter {a.name} does not support arithmetic (requires Numeric)")
            elif base_a not in ("Integer", "Double") or base_b not in ("Integer", "Double"):
                raise TypeCheckError(f"{e.pos.text()}: arithmetic operator {e.op} requires numeric operands, got {type_to_string(a)} and {type_to_string(b)}")
            return TypeName("Double" if base_a=="Double" or base_b=="Double" else "Integer")
        raise TypeCheckError(f"unsupported expression {e}")

    def call_expr_type(self, e, env, ctx, allow_result, result_type):
        bt = self.builtin_call_type(e, env, ctx, allow_result, result_type)
        if bt is not None:
            return bt
        r = ctx.routine(e.name, e.pos)
        if r.kind != "function":
            raise TypeCheckError(f"{e.pos.text()}: function call requires function")
        substitutions = self.routine_type_substitutions(r, e.type_args, e.pos, e.args, env, ctx)
        self.args(r, e.args, env, ctx, e.pos, substitutions)
        self.require_abort_propagation(ctx.current_routine, r, e.pos)
        return_type = ctx.substitute_type_ref(r.return_type, substitutions)
        if r.is_async:
            return AwaitableType(return_type)
        return return_type

    def expect(self,e,env,base,ctx,allow,result):
        t = self.infer(e, env, ctx, allow, result)
        if self.base(t, ctx) != base: raise TypeCheckError(f"{e.pos.text()}: Expected {base}, got {type_to_string(t)}")
    def assign(self,s,t,ctx,pos):
        if isinstance(s, ArrayLiteralType) and isinstance(t, ArrayTypeName):
            if s.size != t.size:
                raise TypeCheckError(f"{pos.text()}: array length mismatch: expected {t.size}, got {s.size}")
            if s.size != 0 and self.base(TypeName(s.element_type), ctx) != self.base(TypeName(t.element_type), ctx):
                raise TypeCheckError(f"{pos.text()}: array element type mismatch")
            return
        if isinstance(s, ArrayTypeName) and isinstance(t, ArrayTypeName):
            if s.size != t.size or self.base(TypeName(s.element_type), ctx) != self.base(TypeName(t.element_type), ctx):
                raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
            return
        if isinstance(s, ResultTypeName) and isinstance(t, ResultTypeName):
            if self.base(s.ok_type, ctx) != self.base(t.ok_type, ctx) or s.error_type != t.error_type:
                raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
            self.assign(s.ok_type, t.ok_type, ctx, pos)
            return
        if isinstance(s, TypeName) and isinstance(t, TypeName) and (ctx.is_builtin_generic_instance(s.name) or ctx.is_builtin_generic_instance(t.name)):
            if s.name != t.name:
                raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
            return
        if self.base(s,ctx) != self.base(t,ctx): raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
        if isinstance(t, TypeName) and t.name in ctx.records and (not isinstance(s, TypeName) or s.name != t.name):
            raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
    def get_constant_value(self, e):
        if isinstance(e, NumberExpr):
            return e.value
        if isinstance(e, DoubleExpr):
            return e.value
        if isinstance(e, UnaryExpr):
            val = self.get_constant_value(e.expr)
            if val is not None:
                if e.op == "-":
                    return -val
        if isinstance(e, BinaryExpr):
            l = self.get_constant_value(e.left)
            r = self.get_constant_value(e.right)
            if l is not None and r is not None:
                if e.op == "+": return l + r
                if e.op == "-": return l - r
                if e.op == "*": return l * r
                if e.op == "/":
                    if r == 0:
                        return None
                    return l / r if (isinstance(l, float) or isinstance(r, float)) else l // r
        return None

    def check_range_bounds(self, expr, target_type, ctx, pos):
        if isinstance(target_type, TypeName) and target_type.name in ctx.types:
            td = ctx.types[target_type.name]
            if td.min_value is not None:
                val = self.get_constant_value(expr)
                if val is not None:
                    if val < td.min_value or val > td.max_value:
                        raise TypeCheckError(f"{pos.text()}: value {val} out of range for type {target_type.name} ({td.min_value}..{td.max_value})")

    def base(self,t,ctx):
        if isinstance(t, AwaitableType): return "Awaitable"
        if isinstance(t, ResultTypeName): return "Result"
        if isinstance(t, ArrayTypeName) or isinstance(t, ArrayLiteralType): return "Array"
        if isinstance(t, TypeName) and ctx.is_builtin_generic_instance(t.name): return t.name
        if t.name in ctx.current_type_params: return f"TypeParam:{t.name}"
        if t.name in ctx.records: return "Record"
        if t.name in ctx.errors: return t.name
        return ctx.types[t.name].base
    def match_types(self, formal: TypeRef, actual: TypeRef, type_params: set[str], inferred: dict[str, set[str]], ctx: Any) -> None:
        if isinstance(formal, TypeName):
            if formal.name in type_params:
                inferred[formal.name].add(type_to_string(actual))
                return
            generic_formal = ctx.parse_generic_instance(formal.name)
            if generic_formal is not None:
                if not isinstance(actual, TypeName):
                    return
                generic_actual = ctx.parse_generic_instance(actual.name)
                if generic_actual is not None:
                    base_formal, args_formal = generic_formal
                    base_actual, args_actual = generic_actual
                    if base_formal == base_actual and len(args_formal) == len(args_actual):
                        for f_arg, a_arg in zip(args_formal, args_actual):
                            self.match_types(self.parse_type_ref(f_arg, ctx), self.parse_type_ref(a_arg, ctx), type_params, inferred, ctx)
        elif isinstance(formal, ArrayTypeName):
            if isinstance(actual, (ArrayTypeName, ArrayLiteralType)):
                self.match_types(self.parse_type_ref(formal.element_type, ctx), self.parse_type_ref(actual.element_type, ctx), type_params, inferred, ctx)
        elif isinstance(formal, ResultTypeName):
            if isinstance(actual, ResultTypeName):
                self.match_types(formal.ok_type, actual.ok_type, type_params, inferred, ctx)
                if formal.error_type in type_params:
                    inferred[formal.error_type].add(actual.error_type)

    def routine_type_substitutions(self, routine: RoutineDecl, type_args: list[str] | None, pos: SourcePos, args: list[Any], env: dict[str, Any], ctx: Any) -> dict[str, str]:
        params = routine.type_params or []
        if not params:
            if type_args:
                raise TypeCheckError(f"{pos.text()}: non-generic routine used with type arguments: {routine.name}")
            return {}
        if len(args) != len(routine.params):
            raise TypeCheckError(f"{pos.text()}: routine {routine.name} expects {len(routine.params)} argument(s), got {len(args)}")
        routine_constraints = {}
        for req in routine.requires:
            if isinstance(req, IsExpr):
                if isinstance(req.left, VarExpr) and req.left.name in params:
                    routine_constraints[req.left.name] = req.right
        if type_args:
            if len(type_args) != len(params):
                raise TypeCheckError(f"{pos.text()}: generic routine {routine.name} expects {len(params)} type argument(s), got {len(type_args)}")
            for arg in type_args:
                ctx.require_type_or_record(arg, pos)
            resolved = dict(zip(params, type_args))
        else:
            inferred = {p: set() for p in params}
            for index, (a, p) in enumerate(zip(args, routine.params)):
                actual_type = self.infer(a, env, ctx, False, None)
                formal_type_ref = self.param_type_ref(p, ctx)
                self.match_types(formal_type_ref, actual_type, set(params), inferred, ctx)
            resolved = {}
            for p in params:
                types_set = inferred[p]
                if not types_set:
                    raise TypeCheckError(f"{pos.text()}: cannot infer type parameter {p} for generic routine {routine.name}")
                if len(types_set) == 1:
                    resolved[p] = list(types_set)[0]
                else:
                    bases = {self.base(self.parse_type_ref(t, ctx), ctx) for t in types_set}
                    if len(bases) == 1:
                        resolved[p] = list(bases)[0]
                    else:
                        raise TypeCheckError(f"{pos.text()}: cannot infer type parameter {p} due to conflicting types: {', '.join(sorted(types_set))}")
        for p in params:
            if p in routine_constraints:
                const = routine_constraints[p]
                arg_type = resolved[p]
                if const in ("Comparable", "Numeric"):
                    if arg_type not in ("Integer", "Double"):
                        raise TypeCheckError(f"{pos.text()}: type {arg_type} does not satisfy constraint {const}")
        return resolved

    def args(self,r,args,env,ctx,pos,substitutions=None):
        substitutions = substitutions or {}
        if len(args) != len(r.params):
            raise TypeCheckError(f"{pos.text()}: routine {r.name} expects {len(r.params)} argument(s), got {len(args)}")
        for index, (a,p) in enumerate(zip(args,r.params), start=1):
            if isinstance(a, NamedArg):
                raise TypeCheckError(f"{a.pos.text()}: routine {r.name} does not accept named argument: {a.name}")
            actual = self.infer(a,env,ctx,False,None)
            expected = ctx.substitute_type_ref(self.param_type_ref(p, ctx), substitutions)
            if self.base(actual, ctx) != self.base(expected, ctx):
                raise TypeCheckError(f"{a.pos.text()}: routine argument {index} type mismatch for {r.name}: expected {type_to_string(expected)}, got {type_to_string(actual)}")
            self.assign(actual, expected, ctx, a.pos)
            self.check_range_bounds(a, expected, ctx, a.pos)

    def parse_type_ref(self, type_name: str, ctx) -> TypeRef:
        generic = ctx.parse_generic_instance(type_name)
        if generic is not None:
            base, args = generic
            if base == "Array" and len(args) == 2 and args[1].isdigit():
                return ArrayTypeName(args[0], int(args[1]))
            if base == "Result" and len(args) == 2:
                return ResultTypeName(self.parse_type_ref(args[0], ctx), args[1])
        return TypeName(type_name)

    def param_type_ref(self, param: Param, ctx):
        return self.parse_type_ref(param.type_name, ctx)

class Ctx:
    def __init__(self, module_name, types, records, generic_records, errors, routines, imports=None, imported_modules=None):
        self.module_name=module_name; self.types=types; self.records=records; self.generic_records=generic_records; self.errors=errors; self.routines=routines
        self.services={}
        self.imports=imports or []; self.imported_modules=imported_modules or {}; self.validate_exposing_conflicts(); self.exposed_routines=self.build_exposed_routines()
        self.add_exposed_types_records_and_errors()
        self.current_routine=None; self.current_type_params=set(); self.current_async=False
        self.scope_vars=set(); self.scope_handles={}; self.type_param_constraints={}

    def validate_exposing_conflicts(self) -> None:
        exposed_modules: dict[str, str] = {}
        for import_decl in self.imports:
            imported = self.imported_modules.get(import_decl.module_name)
            if imported is None:
                continue
            exported = set(imported.routines) | set(imported.types) | set(imported.records) | set(imported.errors)
            for symbol_name in import_decl.exposing:
                if symbol_name not in exported:
                    continue
                previous_module = exposed_modules.get(symbol_name)
                if previous_module is not None and previous_module != import_decl.module_name:
                    raise TypeCheckError(f"{import_decl.pos.text()}: ambiguous exposed symbol {symbol_name}: {previous_module} and {import_decl.module_name}")
                exposed_modules[symbol_name] = import_decl.module_name

    def build_exposed_routines(self):
        exposed = {}
        for import_decl in self.imports:
            imported = self.imported_modules.get(import_decl.module_name)
            if imported is None:
                continue
            for symbol_name in import_decl.exposing:
                routine = imported.routines.get(symbol_name)
                if routine is None:
                    continue
                if symbol_name in exposed and exposed[symbol_name] is not routine:
                    exposed[symbol_name] = None
                else:
                    exposed[symbol_name] = routine
        return exposed

    def add_exposed_types_records_and_errors(self) -> None:
        for import_decl in self.imports:
            imported = self.imported_modules.get(import_decl.module_name)
            if imported is None:
                continue
            for symbol_name in import_decl.exposing:
                if symbol_name in imported.types and symbol_name not in self.types:
                    self.types[symbol_name] = imported.types[symbol_name]
                if symbol_name in imported.records and symbol_name not in self.records:
                    self.add_imported_record_with_dependencies(symbol_name, imported, set())
                if symbol_name in imported.errors:
                    self.errors.add(symbol_name)

    def add_imported_record_with_dependencies(self, name: str, imported: VerifiedProgram, seen: set[str]) -> None:
        seen_key = f"{imported.ast.module_name}.{name}"
        if seen_key in seen or name not in imported.records:
            return
        seen.add(seen_key)
        record_name = self.imported_record_context_name(name, imported)
        if record_name not in self.records:
            record = imported.records[name]
            fields = {
                field_name: self.imported_type_context_name(field_type, imported, seen)
                for field_name, field_type in record.fields.items()
            }
            self.records[record_name] = RecordDef(record_name, fields, record.proto_fields)
        for field_type in imported.records[name].fields.values():
            self.add_imported_type_dependencies(field_type, imported, seen)

    def imported_record_context_name(self, name: str, imported: VerifiedProgram) -> str:
        if name not in self.records or self.records.get(name) == imported.records.get(name):
            return name
        return f"{imported.ast.module_name}.{name}"

    def imported_type_context_name(self, type_name: str, imported: VerifiedProgram, seen: set[str]) -> str:
        generic = self.parse_generic_instance(type_name)
        if generic is not None:
            base, args = generic
            rewritten = [self.imported_type_context_name(arg, imported, seen) for arg in args]
            return f"{base}<{', '.join(rewritten)}>"
        if type_name in imported.records:
            record_name = self.imported_record_context_name(type_name, imported)
            self.add_imported_record_with_dependencies(type_name, imported, seen)
            return record_name
        return type_name

    def add_imported_type_dependencies(self, type_name: str, imported: VerifiedProgram, seen: set[str]) -> None:
        generic = self.parse_generic_instance(type_name)
        if generic is not None:
            _, args = generic
            for arg in args:
                self.add_imported_type_dependencies(arg, imported, seen)
            return
        if type_name in imported.types and type_name not in self.types:
            self.types[type_name] = imported.types[type_name]
        if type_name in imported.records:
            self.add_imported_record_with_dependencies(type_name, imported, seen)
        if type_name in imported.errors:
            self.errors.add(type_name)

    def note_let(self, name: str, type_ref, expr, pos: SourcePos) -> None:
        if isinstance(expr, CallExpr) and expr.name == "scope" and isinstance(type_ref, TypeName) and type_ref.name == "Scope":
            self.scope_vars.add(name)
            return
        if isinstance(expr, CallExpr) and expr.name == "scope_spawn":
            scope_name = expr.args[0].name if expr.args and isinstance(expr.args[0], VarExpr) else "<unknown>"
            self.scope_handles[name] = (scope_name, pos)
            return
        if isinstance(expr, CallExpr):
            scope_name, method_name = self.scope_method_name(expr.name)
            if method_name == "spawn" and scope_name in self.scope_vars:
                self.scope_handles[name] = (scope_name, pos)

    def reject_scope_handle_escape(self, return_value) -> None:
        if isinstance(return_value, ReturnPlain) and isinstance(return_value.expr, VarExpr):
            handle_name = return_value.expr.name
            if handle_name in self.scope_handles:
                scope_name, _ = self.scope_handles[handle_name]
                raise TypeCheckError(f"{return_value.expr.pos.text()}: scope JoinHandle cannot escape its scope: {handle_name} from {scope_name}")

    def require_no_unjoined_scope_handles(self, pos: SourcePos, scope_name: str | None = None) -> None:
        open_handles = self.scope_handles
        if scope_name is not None:
            open_handles = {name: data for name, data in self.scope_handles.items() if data[0] == scope_name}
        if open_handles:
            handle_name = sorted(open_handles)[0]
            scope_name, handle_pos = self.scope_handles[handle_name]
            raise TypeCheckError(f"{handle_pos.text()}: scope JoinHandle must be joined before leaving scope: {handle_name} from {scope_name}")

    def mark_scope_handle_joined(self, scope_name: str, handle_name: str, pos: SourcePos) -> None:
        if handle_name not in self.scope_handles:
            raise TypeCheckError(f"{pos.text()}: JoinHandle is not owned by this scope: {handle_name}")
        owner_scope, _ = self.scope_handles[handle_name]
        if owner_scope != scope_name:
            raise TypeCheckError(f"{pos.text()}: JoinHandle is not owned by this scope: {handle_name}")
        del self.scope_handles[handle_name]

    def scope_method_name(self, name: str) -> tuple[str, str]:
        if "." not in name:
            return "", ""
        owner, method = name.rsplit(".", 1)
        return owner, method

    def require_type_or_record(self,n,pos):
        if n in self.current_type_params:
            return
        if n in self.types or n in self.records:
            return
        generic = self.parse_generic_instance(n)
        if generic is not None:
            base, args = generic
            if base in BUILTIN_GENERIC_TYPE_ARITY:
                expected = BUILTIN_GENERIC_TYPE_ARITY[base]
                if base == "Array" and len(args) == 1:
                    self.require_type_or_record(args[0], pos)
                    return
                if len(args) != expected:
                    raise TypeCheckError(f"{pos.text()}: generic type {base} expects {expected} type argument(s), got {len(args)}")
                for arg in args:
                    if base == "Array" and arg.isdigit():
                        continue
                    self.require_type_or_record(arg, pos)
                return
            if base in self.types or base in self.records:
                raise TypeCheckError(f"{pos.text()}: non-generic type used with type arguments: {base}")
            if base not in self.generic_records:
                raise TypeCheckError(f"{pos.text()}: unknown type: {base}")
            declaration = self.generic_records[base]
            expected = len(declaration.type_params or [])
            if len(args) != expected:
                raise TypeCheckError(f"{pos.text()}: generic type {base} expects {expected} type argument(s), got {len(args)}")
            for arg in args:
                self.require_type_or_record(arg, pos)
            self.instantiate_record(n, declaration, args)
            return
        if n in self.generic_records:
            expected = len(self.generic_records[n].type_params or [])
            raise TypeCheckError(f"{pos.text()}: generic type requires {expected} type argument(s): {n}")
        if n in BUILTIN_GENERIC_TYPE_ARITY:
            expected = BUILTIN_GENERIC_TYPE_ARITY[n]
            raise TypeCheckError(f"{pos.text()}: generic type requires {expected} type argument(s): {n}")
        raise TypeCheckError(f"{pos.text()}: unknown type: {n}")

    def is_builtin_generic_instance(self, name: str) -> bool:
        generic = self.parse_generic_instance(name)
        return generic is not None and generic[0] in BUILTIN_GENERIC_TYPE_ARITY

    def join_handle_inner_type(self, type_ref) -> str | None:
        if not isinstance(type_ref, TypeName):
            return None
        generic = self.parse_generic_instance(type_ref.name)
        if generic is None:
            return None
        base, args = generic
        if base == "JoinHandle" and len(args) == 1:
            return args[0]
        return None

    def parse_generic_instance(self, name: str):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)<(.+)>", name.strip())
        if not match:
            return None
        return match.group(1), self.split_type_args(match.group(2))

    def split_type_args(self, text: str) -> list[str]:
        args: list[str] = []
        depth = 0
        start = 0
        for index, char in enumerate(text):
            if char == "<":
                depth += 1
            elif char == ">":
                depth -= 1
            elif char == "," and depth == 0:
                args.append(text[start:index].strip())
                start = index + 1
        args.append(text[start:].strip())
        return args

    def instantiate_record(self, concrete_name: str, declaration: RecordTypeDecl, args: list[str]) -> None:
        if concrete_name in self.records:
            return
        substitutions = dict(zip(declaration.type_params or [], args))
        fields = {field.name: self.substitute_type(field.type_name, substitutions) for field in declaration.fields}
        self.records[concrete_name] = RecordDef(concrete_name, fields)

    def substitute_type(self, name: str, substitutions: dict[str, str]) -> str:
        if name in substitutions:
            return substitutions[name]
        generic = self.parse_generic_instance(name)
        if generic is None:
            return name
        base, args = generic
        replaced = [self.substitute_type(arg, substitutions) for arg in args]
        return f"{base}<{', '.join(replaced)}>"
    def substitute_type_ref(self, type_ref, substitutions: dict[str, str]):
        if type_ref is None:
            return None
        if isinstance(type_ref, TypeName):
            return TypeName(self.substitute_type(type_ref.name, substitutions))
        if isinstance(type_ref, ArrayTypeName):
            return ArrayTypeName(self.substitute_type(type_ref.element_type, substitutions), type_ref.size)
        if isinstance(type_ref, ResultTypeName):
            return ResultTypeName(self.substitute_type_ref(type_ref.ok_type, substitutions), self.substitute_type(type_ref.error_type, substitutions))
        return type_ref
    def require_return_type(self,t,pos):
        if isinstance(t, TypeName): self.require_type_or_record(t.name,pos)
        elif isinstance(t, ArrayTypeName): self.require_type_or_record(t.element_type,pos)
        elif isinstance(t, ResultTypeName):
            if isinstance(t.ok_type, ResultTypeName):
                raise TypeCheckError(f"{pos.text()}: nested Result payloads are forbidden in v1")
            self.require_return_type(t.ok_type,pos)
            if t.error_type not in self.errors and t.error_type != "String":
                raise TypeCheckError(f"{pos.text()}: unknown result error type: {t.error_type}")
    def routine(self,n,pos):
        local_name = self.local_routine_name(n)
        if local_name in self.routines:
            return self.routines[local_name]
        imported = self.imported_routine(n)
        if imported is not None:
            return imported
        raise TypeCheckError(f"{pos.text()}: unknown routine: {n}")

    def imported_routine(self, name):
        if "." in name:
            for module_name, verified in sorted(self.imported_modules.items(), key=lambda item: len(item[0]), reverse=True):
                prefix = f"{module_name}."
                if not name.startswith(prefix):
                    continue
                routine_name = name[len(prefix):]
                if "." in routine_name:
                    return None
                return verified.routines.get(routine_name)
            return None
        exposed = self.exposed_routines.get(name)
        if exposed is None:
            return None
        return exposed
    def local_routine_name(self,n):
        prefix = f"{self.module_name}."
        return n[len(prefix):] if n.startswith(prefix) else n

def verify_program(program: Program, imported_modules: dict[str, VerifiedProgram] | None = None, prover: str | None = None, timeout: int | None = None) -> VerifiedProgram: return Verifier().verify(program, imported_modules, prover=prover, timeout=timeout)
def proof_json(vp: VerifiedProgram) -> str: return json.dumps(vp.proof_obligations, indent=2)
