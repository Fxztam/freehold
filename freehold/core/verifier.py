from __future__ import annotations
from dataclasses import dataclass
import json
from freehold.core.ast import *
from freehold.core.string_templates import validate_template

BUILTIN_TYPE_NAMES = {"Integer", "Boolean", "Double", "String", "BigInteger", "BigFloat"}

RESERVED_NAMES = {
    "Array", "BigFloat", "BigInteger", "Boolean", "Double", "Integer", "Result", "String",
    "and", "call", "case", "default", "do", "else", "end", "ensures",
    "error", "exposing", "failure", "false", "function", "if", "import",
    "invariant", "is", "let", "module", "not", "ok", "or", "procedure",
    "record", "requires", "return", "returns", "success", "then", "true",
    "type", "value", "variant", "when", "while",
}

@dataclass
class VerifiedProgram:
    ast: Program
    types: dict[str, TypeDef]
    records: dict[str, RecordDef]
    errors: set[str]
    routines: dict[str, RoutineDecl]
    proof_obligations: list[dict[str, str]]

class Verifier:
    def verify(self, program: Program) -> VerifiedProgram:
        self.validate_imports(program)
        self.validate_qualified_name(program.module_name, program.pos)
        types = {name: TypeDef(name, name) for name in BUILTIN_TYPE_NAMES}
        records, errors, routines = {}, set(), {}
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
                seen, fields = set(), {}
                for f in d.fields:
                    self.validate_identifier(f.name, f.pos)
                    if f.name in seen: raise TypeCheckError(f"{f.pos.text()}: duplicate record field: {f.name}")
                    seen.add(f.name); fields[f.name] = f.type_name
                records[d.name] = RecordDef(d.name, fields)
            elif isinstance(d, ErrorDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "error")
                declared_names[d.name] = "error"
                errors.add(d.name)
            elif isinstance(d, RoutineDecl):
                self.validate_declaration_name(d.name, declared_names, d.pos, "routine")
                declared_names[d.name] = "routine"
                routines[d.name] = d
        ctx = Ctx(program.module_name, types, records, errors, routines)
        for rd in [d for d in program.declarations if isinstance(d, RecordTypeDecl)]:
            for f in rd.fields: ctx.require_type_or_record(f.type_name, f.pos)
        obs = []
        for r in routines.values(): self.routine(r, ctx, obs)
        return VerifiedProgram(program, types, records, errors, routines, obs)

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
        if name in BUILTIN_TYPE_NAMES:
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

    def std_procedure_call(self, name, args, env, ctx, pos) -> bool:
        def infer_arg(i):
            if i >= len(args):
                raise TypeCheckError(f"{pos.text()}: {name} expects more arguments")
            return self.infer(args[i], env, ctx, False, None)
        def expect_count(n):
            if len(args) != n:
                raise TypeCheckError(f"{pos.text()}: {name} expects {n} argument(s)")
        def expect_base(i, base):
            t = infer_arg(i)
            if self.base(t, ctx) != base:
                raise TypeCheckError(f"{args[i].pos.text()}: {name} argument {i+1} expected {base}, got {type_to_string(t)}")
        def expect_template_values(start):
            for index in range(start, len(args)):
                t = infer_arg(index)
                if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                    raise TypeCheckError(f"{args[index].pos.text()}: {name} template value {index} expected String, Integer, Boolean, or Double, got {type_to_string(t)}")
        if name == "Std.IO.log":
            expect_count(1)
            t = infer_arg(0)
            if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                raise TypeCheckError(f"{args[0].pos.text()}: Std.IO.log supports String, Integer, Boolean, Double")
            return True
        if name == "Std.IO.logf":
            if len(args) < 1:
                raise TypeCheckError(f"{pos.text()}: Std.IO.logf expects at least 1 argument")
            expect_base(0, "String")
            expect_template_values(1)
            if isinstance(args[0], StringExpr):
                try:
                    validate_template(args[0].value, len(args) - 1)
                except ValueError as exc:
                    raise TypeCheckError(f"{args[0].pos.text()}: Std.IO.logf {exc}") from exc
            return True
        if name == "Std.IO.log_int":
            expect_count(1); expect_base(0, "Integer"); return True
        if name == "Std.IO.log_bool":
            expect_count(1); expect_base(0, "Boolean"); return True
        if name == "Std.IO.log_double":
            expect_count(1); expect_base(0, "Double"); return True
        return False

    def routine(self, r, ctx, obs):
        env = {}
        seen_params = set()
        for p in r.params:
            self.validate_identifier(p.name, p.pos)
            if p.name in seen_params:
                raise TypeCheckError(f"{p.pos.text()}: duplicate parameter name: {p.name}")
            seen_params.add(p.name)
            ctx.require_type_or_record(p.type_name, p.pos); env[p.name] = TypeName(p.type_name)
        if r.return_type: ctx.require_return_type(r.return_type, r.pos)
        for e in r.requires: self.contract_bool("requires", e, env, ctx, False, None)
        for e in r.ensures: self.contract_bool("ensures", e, env, ctx, True, r.return_type)
        ret = self.block(r.body, r, env, ctx)
        if r.kind == "function" and not ret: raise TypeCheckError(f"{r.pos.text()}: function {r.name} has no guaranteed return")

    def block(self, body, r, env, ctx):
        saw = False
        for s in body:
            if isinstance(s, LetStmt):
                self.validate_identifier(s.name, s.pos)
                ctx.require_return_type(s.type_ref, s.pos)
                self.assign(self.infer(s.expr, env, ctx, False, None), s.type_ref, ctx, s.pos); env[s.name]=s.type_ref
            elif isinstance(s, AssignStmt):
                if s.name not in env:
                    raise TypeCheckError(f"{s.pos.text()}: unknown assignment target: {s.name}")
                self.assign(self.infer(s.expr, env, ctx, False, None), env[s.name], ctx, s.pos)
            elif isinstance(s, FieldAssignStmt):
                target_type = self.infer_field_path_obj(s.path, s.pos, env, ctx, False, None)
                self.assign(self.infer(s.expr, env, ctx, False, None), target_type, ctx, s.pos)
            elif isinstance(s, ReturnStmt):
                self.ret(s.value, r.return_type, env, ctx); saw = True
            elif isinstance(s, CheckStmt):
                self.statement_bool("check", s.expr, env, ctx, False, None)
            elif isinstance(s, IfStmt):
                self.statement_bool("if condition", s.condition, env, ctx, False, None)
                saw = saw or (self.block(s.then_body, r, dict(env), ctx) and self.block(s.else_body, r, dict(env), ctx))
            elif isinstance(s, WhileStmt):
                self.statement_bool("while condition", s.condition, env, ctx, False, None)
                for invariant in s.invariants:
                    self.statement_bool("while invariant", invariant, env, ctx, False, None)
                if s.variant is not None:
                    variant_type = self.infer(s.variant, env, ctx, False, None)
                    if self.base(variant_type, ctx) != "Integer":
                        raise TypeCheckError(f"{s.variant.pos.text()}: while variant must be Integer, got {type_to_string(variant_type)}")
                self.block(s.body, r, dict(env), ctx)
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
                    branch_returns.append(self.block(br.body, r, dict(env), ctx))
                default_returns = self.block(s.default_body, r, dict(env), ctx)
                saw = saw or (all(branch_returns) and default_returns)
            elif isinstance(s, CallStmt):
                if self.std_procedure_call(s.name, s.args, env, ctx, s.pos):
                    continue
                cal = ctx.routine(s.name, s.pos)
                if cal.kind != "procedure": raise TypeCheckError(f"{s.pos.text()}: call requires procedure")
                self.args(cal, s.args, env, ctx, s.pos)
        return saw

    def statement_bool(self, label, expr, env, ctx, allow_result, result_type):
        actual = self.infer(expr, env, ctx, allow_result, result_type)
        if self.base(actual, ctx) != "Boolean":
            raise TypeCheckError(f"{expr.pos.text()}: {label} requires Boolean, got {type_to_string(actual)}")

    def contract_bool(self, label, expr, env, ctx, allow_result, result_type):
        actual = self.infer(expr, env, ctx, allow_result, result_type)
        if self.base(actual, ctx) != "Boolean":
            raise TypeCheckError(f"{expr.pos.text()}: contract {label} requires Boolean, got {type_to_string(actual)}")

    def ret(self, rv, expected, env, ctx):
        if expected is None:
            raise TypeCheckError(f"{rv.pos.text()}: procedure cannot return a value")
        if isinstance(expected, ResultTypeName):
            if isinstance(rv, ReturnOk):
                actual = self.infer(rv.expr, env, ctx, False, None)
                ok_type = TypeName(expected.ok_type)
                if self.base(actual, ctx) != self.base(ok_type, ctx):
                    raise TypeCheckError(f"{rv.pos.text()}: Result ok type mismatch: expected {expected.ok_type}, got {type_to_string(actual)}")
                self.assign(actual, ok_type, ctx, rv.pos)
            elif isinstance(rv, ReturnError):
                if rv.error_name not in ctx.errors:
                    raise TypeCheckError(f"{rv.pos.text()}: unknown error: {rv.error_name}")
                if rv.error_name != expected.error_type:
                    raise TypeCheckError(f"{rv.pos.text()}: Function returns {type_to_string(expected)}, cannot return error {rv.error_name}")
            else: raise TypeCheckError(f"{rv.pos.text()}: Result function must return ok or error")
        else:
            if not isinstance(rv, ReturnPlain): raise TypeCheckError(f"{rv.pos.text()}: plain function must return expression")
            actual = self.infer(rv.expr, env, ctx, False, None)
            if self.base(actual, ctx) != self.base(expected, ctx):
                raise TypeCheckError(f"{rv.pos.text()}: function return type mismatch: expected {type_to_string(expected)}, got {type_to_string(actual)}")
            self.assign(actual, expected, ctx, rv.pos)

    def infer_field_path_obj(self, path, pos, env, ctx, allow_result, result_type):
        root = path[0]
        if root == "result" and allow_result and result_type is not None:
            t = result_type
        else:
            if root not in env: raise TypeCheckError(f"{pos.text()}: unknown record variable: {root}")
            t = env[root]
        for field in path[1:]:
            if not isinstance(t, TypeName) or t.name not in ctx.records:
                raise TypeCheckError(f"{pos.text()}: field access requires record before .{field}, got {type_to_string(t)}")
            rec = ctx.records[t.name]
            if field not in rec.fields:
                raise TypeCheckError(f"{pos.text()}: unknown field {field} for record {t.name}")
            t = TypeName(rec.fields[field])
        return t

    def infer_field_path(self, e, env, ctx, allow_result=False, result_type=None):
        return self.infer_field_path_obj(e.path, e.pos, env, ctx, allow_result, result_type)

    def builtin_call_type(self, e, env, ctx, allow_result, result_type):
        def expect_arg(i, base):
            if i >= len(e.args):
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects more arguments")
            t = self.infer(e.args[i], env, ctx, allow_result, result_type)
            if self.base(t, ctx) != base:
                raise TypeCheckError(f"{e.args[i].pos.text()}: {e.name} argument {i+1} expected {base}, got {type_to_string(t)}")
        def infer_arg(i):
            if i >= len(e.args):
                raise TypeCheckError(f"{e.pos.text()}: {e.name} expects more arguments")
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
        if e.name == "String.template":
            if len(e.args) < 1:
                raise TypeCheckError(f"{e.pos.text()}: String.template expects at least 1 argument")
            expect_arg(0, "String")
            for index in range(1, len(e.args)):
                t = infer_arg(index)
                if self.base(t, ctx) not in ("String", "Integer", "Boolean", "Double"):
                    raise TypeCheckError(f"{e.args[index].pos.text()}: String.template template value {index} expected String, Integer, Boolean, or Double, got {type_to_string(t)}")
            if isinstance(e.args[0], StringExpr):
                try:
                    validate_template(e.args[0].value, len(e.args) - 1)
                except ValueError as exc:
                    raise TypeCheckError(f"{e.args[0].pos.text()}: String.template {exc}") from exc
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
        if isinstance(e, RecordLiteralExpr):
            if e.type_name not in ctx.records: raise TypeCheckError(f"{e.pos.text()}: unknown record type: {e.type_name}")
            rec, seen = ctx.records[e.type_name], set()
            for a in e.args:
                if a.name in seen: raise TypeCheckError(f"{a.pos.text()}: duplicate record literal field: {a.name}")
                seen.add(a.name)
                if a.name not in rec.fields: raise TypeCheckError(f"{a.pos.text()}: unknown field for {e.type_name}: {a.name}")
                self.assign(self.infer(a.expr, env, ctx, allow_result, result_type), TypeName(rec.fields[a.name]), ctx, a.pos)
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
            if e.name not in env:
                raise TypeCheckError(f"{e.pos.text()}: unknown array: {e.name}")
            arr_t = env[e.name]
            if not isinstance(arr_t, ArrayTypeName):
                raise TypeCheckError(f"{e.pos.text()}: index access requires Array, got {type_to_string(arr_t)}")
            index_type = self.infer(e.index, env, ctx, allow_result, result_type)
            if self.base(index_type, ctx) != "Integer":
                raise TypeCheckError(f"{e.index.pos.text()}: array index must be Integer, got {type_to_string(index_type)}")
            if isinstance(e.index, NumberExpr) and not (0 <= e.index.value < arr_t.size):
                raise TypeCheckError(f"{e.pos.text()}: array index out of bounds: {e.index.value} for size {arr_t.size}")
            return TypeName(arr_t.element_type)
        if isinstance(e, SpecialResultExpr):
            if not allow_result or not isinstance(result_type, ResultTypeName):
                raise TypeCheckError(f"{e.pos.text()}: Result contract expression {e.name} is only available in Result ensures")
            if e.name in ("success","failure"): return TypeName("Boolean")
            return TypeName(result_type.ok_type if e.name == "value" else result_type.error_type)
        if isinstance(e, VarExpr):
            if e.name in ctx.errors: return TypeName(e.name)
            if e.name == "result" and allow_result and result_type: return result_type
            if e.name not in env:
                raise TypeCheckError(f"{e.pos.text()}: unknown variable: {e.name}")
            return env[e.name]
        if isinstance(e, CallExpr):
            bt = self.builtin_call_type(e, env, ctx, allow_result, result_type)
            if bt is not None:
                return bt
            r = ctx.routine(e.name, e.pos)
            if r.kind != "function":
                raise TypeCheckError(f"{e.pos.text()}: function call requires function")
            self.args(r, e.args, env, ctx, e.pos); return r.return_type
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
                if self.base(a, ctx) != self.base(b, ctx):
                    raise TypeCheckError(f"{e.pos.text()}: cannot compare {type_to_string(a)} with {type_to_string(b)}")
                return TypeName("Boolean")
            if e.op in ("and", "or"):
                a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
                if self.base(a, ctx) != "Boolean" or self.base(b, ctx) != "Boolean":
                    raise TypeCheckError(f"{e.pos.text()}: boolean operator {e.op} requires Boolean operands, got {type_to_string(a)} and {type_to_string(b)}")
                return TypeName("Boolean")
            if e.op in ("<","<=",">",">="):
                a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
                if self.base(a, ctx) not in ("Integer", "Double") or self.base(b, ctx) not in ("Integer", "Double"):
                    raise TypeCheckError(f"{e.pos.text()}: comparison operator {e.op} requires numeric operands, got {type_to_string(a)} and {type_to_string(b)}")
                return TypeName("Boolean")
            a,b = self.infer(e.left, env, ctx, allow_result, result_type), self.infer(e.right, env, ctx, allow_result, result_type)
            if self.base(a,ctx) not in ("Integer","Double") or self.base(b,ctx) not in ("Integer","Double"):
                raise TypeCheckError(f"{e.pos.text()}: arithmetic operator {e.op} requires numeric operands, got {type_to_string(a)} and {type_to_string(b)}")
            return TypeName("Double" if self.base(a,ctx)=="Double" or self.base(b,ctx)=="Double" else "Integer")
        raise TypeCheckError(f"unsupported expression {e}")

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
            if self.base(TypeName(s.ok_type), ctx) != self.base(TypeName(t.ok_type), ctx) or s.error_type != t.error_type:
                raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
            return
        if self.base(s,ctx) != self.base(t,ctx): raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
        if isinstance(t, TypeName) and t.name in ctx.records and (not isinstance(s, TypeName) or s.name != t.name):
            raise TypeCheckError(f"{pos.text()}: cannot assign {type_to_string(s)} to {type_to_string(t)}")
    def base(self,t,ctx):
        if isinstance(t, ResultTypeName): return "Result"
        if isinstance(t, ArrayTypeName) or isinstance(t, ArrayLiteralType): return "Array"
        if t.name in ctx.records: return "Record"
        if t.name in ctx.errors: return t.name
        return ctx.types[t.name].base
    def args(self,r,args,env,ctx,pos):
        if len(args) != len(r.params):
            raise TypeCheckError(f"{pos.text()}: routine {r.name} expects {len(r.params)} argument(s), got {len(args)}")
        for index, (a,p) in enumerate(zip(args,r.params), start=1):
            actual = self.infer(a,env,ctx,False,None)
            expected = TypeName(p.type_name)
            if self.base(actual, ctx) != self.base(expected, ctx):
                raise TypeCheckError(f"{a.pos.text()}: routine argument {index} type mismatch for {r.name}: expected {p.type_name}, got {type_to_string(actual)}")
            self.assign(actual, expected, ctx, a.pos)

class Ctx:
    def __init__(self, module_name, types, records, errors, routines):
        self.module_name=module_name; self.types=types; self.records=records; self.errors=errors; self.routines=routines
    def require_type_or_record(self,n,pos):
        if n not in self.types and n not in self.records: raise TypeCheckError(f"{pos.text()}: unknown type: {n}")
    def require_return_type(self,t,pos):
        if isinstance(t, TypeName): self.require_type_or_record(t.name,pos)
        elif isinstance(t, ArrayTypeName): self.require_type_or_record(t.element_type,pos)
        elif isinstance(t, ResultTypeName):
            self.require_type_or_record(t.ok_type,pos)
            if t.error_type not in self.errors:
                raise TypeCheckError(f"{pos.text()}: unknown result error type: {t.error_type}")
    def routine(self,n,pos):
        local_name = self.local_routine_name(n)
        if local_name not in self.routines: raise TypeCheckError(f"{pos.text()}: unknown routine: {n}")
        return self.routines[local_name]
    def local_routine_name(self,n):
        prefix = f"{self.module_name}."
        return n[len(prefix):] if n.startswith(prefix) else n

def verify_program(program: Program) -> VerifiedProgram: return Verifier().verify(program)
def proof_json(vp: VerifiedProgram) -> str: return json.dumps(vp.proof_obligations, indent=2)
