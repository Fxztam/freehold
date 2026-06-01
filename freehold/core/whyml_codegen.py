from __future__ import annotations
from typing import Any
from freehold.core.ast import *

def has_returns(body: list[Any]) -> bool:
    for stmt in body:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, IfStmt):
            if has_returns(stmt.then_body) or has_returns(stmt.else_body):
                return True
        if isinstance(stmt, WhileStmt):
            if has_returns(stmt.body):
                return True
        if isinstance(stmt, CaseStmt):
            for b in stmt.branches:
                if has_returns(b.body):
                    return True
            if stmt.default_body and has_returns(stmt.default_body):
                return True
        if isinstance(stmt, ScopeStmt):
            if has_returns(stmt.spawn_body) or has_returns(stmt.join_body) or has_returns(stmt.result_body):
                return True
    return False

def is_param_mutable(routine: RoutineDecl, param_name: str) -> bool:
    if not routine.global_specs:
        return False
    for g in routine.global_specs:
        if g.name == param_name and g.mode in ("In_Out", "Output"):
            return True
    return False

class WhyMLGenerator:
    def __init__(self, program: Program):
        self.program = program
        self.refs: set[str] = set()
        self.routines = {d.name: d for d in program.declarations if isinstance(d, RoutineDecl)}

    def generate(self) -> str:
        lines = []
        lines.append(f"module {self.program.module_name}")
        lines.append("  use int.Int")
        lines.append("  use ref.Ref")
        lines.append("  use array.Array")
        lines.append("  use string.String")
        lines.append("  use seq.Seq")
        lines.append("")
        lines.append("  (* Generic Result type definition *)")
        lines.append("  type result 'ok 'err = Ok 'ok | Err 'err")
        lines.append("")
        lines.append("  (* Concurrency support definitions *)")
        lines.append("  type joinHandle 'a = {")
        lines.append("    mutable value: 'a;")
        lines.append("  }")
        lines.append("")
        lines.append("  type channel 'a = {")
        lines.append("    mutable history: seq 'a;")
        lines.append("    mutable read_cursor: int;")
        lines.append("  } invariant { 0 <= read_cursor <= length history }")
        lines.append("")
        lines.append("  let channel (_capacity: int) : channel 'a")
        lines.append("    ensures { length result.history = 0 }")
        lines.append("    ensures { result.read_cursor = 0 }")
        lines.append("  =")
        lines.append("    { history = empty; read_cursor = 0 }")
        lines.append("")
        lines.append("  let channel_sender (c: channel 'a) : channel 'a = c")
        lines.append("  let channel_receiver (c: channel 'a) : channel 'a = c")
        lines.append("")
        lines.append("  let channel_send (c: channel 'a) (x: 'a) : joinHandle bool")
        lines.append("    writes { c.history }")
        lines.append("    ensures { c.history = snoc (old c.history) x }")
        lines.append("    ensures { result.value = true }")
        lines.append("  =")
        lines.append("    c.history <- snoc c.history x;")
        lines.append("    { value = true }")
        lines.append("")
        lines.append("  let channel_receive (c: channel 'a) : joinHandle 'a")
        lines.append("    requires { c.read_cursor < length c.history }")
        lines.append("    writes { c.read_cursor }")
        lines.append("    ensures { result.value = c.history[old c.read_cursor] }")
        lines.append("    ensures { c.read_cursor = old c.read_cursor + 1 }")
        lines.append("  =")
        lines.append("    let res = c.history[c.read_cursor] in")
        lines.append("    c.read_cursor <- c.read_cursor + 1;")
        lines.append("    { value = res }")
        lines.append("")
        lines.append("  let scope_spawn (s: unit) (x: 'a) : joinHandle 'a =")
        lines.append("    { value = x }")
        lines.append("")
        lines.append("  let scope_join (s: unit) (h: joinHandle 'a) : joinHandle 'a =")
        lines.append("    h")
        lines.append("")
        lines.append("  let await (h: joinHandle 'a) : 'a =")
        lines.append("    h.value")
        lines.append("")
        
        # Translate type/record/error declarations
        for d in self.program.declarations:
            if isinstance(d, TypeDecl):
                typename = d.name[0].lower() + d.name[1:]
                lines.append(f"  type {typename} = int")
            elif isinstance(d, RecordTypeDecl):
                typename = d.name[0].lower() + d.name[1:]
                fields_str = []
                for f in d.fields:
                    f_name = f.name[0].lower() + f.name[1:]
                    f_type = self.map_type_name(f.type_name)
                    fields_str.append(f"mutable {f_name}: {f_type}")
                fields_body = "; ".join(fields_str)
                lines.append(f"  type {typename} = {{ {fields_body} }}")
            elif isinstance(d, ErrorDecl):
                lines.append(f"  exception {d.name}")
        lines.append("")
        
        # Translate routines
        for d in self.program.declarations:
            if isinstance(d, RoutineDecl):
                lines.append(self.routine_to_whyml(d))
                lines.append("")
                
        lines.append("end")
        return "\n".join(lines)

    def map_type_name(self, n: str) -> str:
        if n == "Integer": return "int"
        if n == "Boolean": return "bool"
        if n == "Float": return "real"
        if n == "String": return "string"
        if n.startswith("Channel<") and n.endswith(">"):
            inner = n[len("Channel<"):-1]
            return f"(channel {self.map_type_name(inner)})"
        if n.startswith("Sender<") and n.endswith(">"):
            inner = n[len("Sender<"):-1]
            return f"(channel {self.map_type_name(inner)})"
        if n.startswith("Receiver<") and n.endswith(">"):
            inner = n[len("Receiver<"):-1]
            return f"(channel {self.map_type_name(inner)})"
        if n.startswith("JoinHandle<") and n.endswith(">"):
            inner = n[len("JoinHandle<"):-1]
            return f"(joinHandle {self.map_type_name(inner)})"
        return n[0].lower() + n[1:]

    def map_type(self, t: TypeRef | None) -> str:
        if t is None:
            return "unit"
        if isinstance(t, TypeName):
            return self.map_type_name(t.name)
        if isinstance(t, ResultTypeName):
            ok_str = self.map_type(t.ok_type)
            err_str = t.error_type[0].lower() + t.error_type[1:]
            return f"(result {ok_str} {err_str})"
        if isinstance(t, ArrayTypeName):
            elem = self.map_type_name(t.element_type)
            return f"(array {elem})"
        return "unit"

    def expr_to_whyml(self, e: Any) -> str:
        if isinstance(e, NumberExpr): return str(e.value)
        if isinstance(e, DoubleExpr): return str(e.value)
        if isinstance(e, BoolExpr): return "true" if e.value else "false"
        if isinstance(e, StringExpr): return f'"{e.value}"'
        if isinstance(e, VarExpr):
            if e.name in self.refs:
                return f"!{e.name}"
            return e.name
        if isinstance(e, SpecialResultExpr):
            return "result"
        if isinstance(e, FieldAccessExpr):
            root = e.path[0]
            if root in self.refs:
                res = f"!{root}"
            else:
                res = root
            for field in e.path[1:]:
                res = f"({res}).{field}"
            return res
        if isinstance(e, UnaryExpr):
            inner = self.expr_to_whyml(e.expr)
            return f"(not {inner})" if e.op == "not" else f"(- {inner})"
        if isinstance(e, BinaryExpr):
            a = self.expr_to_whyml(e.left)
            b = self.expr_to_whyml(e.right)
            op = e.op
            if op == "=": return f"({a} = {b})"
            if op == "!=": return f"({a} <> {b})"
            if op == "and": return f"({a} && {b})"
            if op == "or": return f"({a} || {b})"
            if op == "/": return f"({a} / {b})"
            return f"({a} {op} {b})"
        if isinstance(e, IndexExpr):
            base = f"!{e.name}" if e.name in self.refs else e.name
            idx = self.expr_to_whyml(e.index)
            return f"({base})[{idx}]"
        if isinstance(e, IndexedFieldAccessExpr):
            base = f"!{e.name}" if e.name in self.refs else e.name
            idx = self.expr_to_whyml(e.index)
            res = f"({base})[{idx}]"
            for field in e.fields:
                res = f"({res}).{field}"
            return res
        if isinstance(e, ForAllExpr):
            l = self.expr_to_whyml(e.lower)
            u = self.expr_to_whyml(e.upper)
            body = self.expr_to_whyml(e.expr)
            return f"(forall {e.var_name}: int. {l} <= {e.var_name} <= {u} -> {body})"
        if isinstance(e, ExistsExpr):
            l = self.expr_to_whyml(e.lower)
            u = self.expr_to_whyml(e.upper)
            body = self.expr_to_whyml(e.expr)
            return f"(exists {e.var_name}: int. {l} <= {e.var_name} <= {u} && {body})"
        if isinstance(e, AwaitExpr):
            inner = self.expr_to_whyml(e.expr)
            if isinstance(e.expr, CallExpr) and e.expr.name not in ("channel_receive", "channel_send", "scope_spawn", "scope_join") and not e.expr.name.endswith(".spawn") and not e.expr.name.endswith(".join"):
                return inner
            return f"(await {inner})"
        if isinstance(e, CallExpr):
            if e.name == "scope_spawn" or e.name.endswith(".spawn"):
                if e.name == "scope_spawn":
                    scope_var = self.expr_to_whyml(e.args[0])
                    task_arg = self.expr_to_whyml(e.args[1])
                else:
                    scope_var = e.name.split(".")[0]
                    task_arg = self.expr_to_whyml(e.args[0])
                return f"(scope_spawn {scope_var} {task_arg})"
            if e.name == "scope_join" or e.name.endswith(".join"):
                if e.name == "scope_join":
                    scope_var = self.expr_to_whyml(e.args[0])
                    handle_arg = self.expr_to_whyml(e.args[1])
                else:
                    scope_var = e.name.split(".")[0]
                    handle_arg = self.expr_to_whyml(e.args[0])
                return f"(scope_join {scope_var} {handle_arg})"
            args = " ".join(self.expr_to_whyml(arg) for arg in e.args)
            return f"({e.name} {args})"
        return "UNSUPPORTED"

    def stmt_to_whyml(self, stmt: Any) -> str:
        if isinstance(stmt, AssignStmt):
            expr_val = self.expr_to_whyml(stmt.expr)
            return f"{stmt.name} := {expr_val}"
        elif isinstance(stmt, FieldAssignStmt):
            root = stmt.path[0]
            if root in self.refs:
                lhs = f"!{root}"
            else:
                lhs = root
            for field in stmt.path[1:-1]:
                lhs = f"({lhs}).{field}"
            last_field = stmt.path[-1]
            expr_val = self.expr_to_whyml(stmt.expr)
            return f"({lhs}).{last_field} <- {expr_val}"
        elif isinstance(stmt, ReturnStmt):
            if isinstance(stmt.value, ReturnPlain):
                val = self.expr_to_whyml(stmt.value.expr)
                return f"raise (Return ({val}))"
            elif isinstance(stmt.value, ReturnOk):
                val = self.expr_to_whyml(stmt.value.expr)
                return f"raise (Return (Ok ({val})))"
            elif isinstance(stmt.value, ReturnError):
                return f"raise (Return (Err {stmt.value.error_name}))"
            return "raise (Return ())"
        elif isinstance(stmt, AbortStmt):
            return f"raise {stmt.error_name}"
        elif isinstance(stmt, CheckStmt):
            expr_val = self.expr_to_whyml(stmt.expr)
            return f"assert {{ {expr_val} }}"
        elif isinstance(stmt, CallStmt):
            if stmt.name in ("channel_send", "channel_receive") or stmt.name.endswith(".spawn") or stmt.name.endswith(".join") or stmt.name in ("scope_spawn", "scope_join"):
                expr = CallExpr(stmt.name, stmt.args, stmt.pos, stmt.type_args)
                return self.expr_to_whyml(expr)
            callee = self.routines.get(stmt.name)
            args_str = []
            for i, arg in enumerate(stmt.args):
                arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                is_mut = False
                if callee and i < len(callee.params):
                    param_name = callee.params[i].name
                    is_mut = is_param_mutable(callee, param_name)
                
                if is_mut and isinstance(arg_expr, VarExpr):
                    args_str.append(arg_expr.name)
                else:
                    args_str.append(self.expr_to_whyml(arg_expr))
            args_val = " ".join(args_str)
            return f"({stmt.name} {args_val})"
        elif isinstance(stmt, IfStmt):
            cond = self.expr_to_whyml(stmt.condition)
            then_body = self.stmts_to_whyml(stmt.then_body)
            else_body = self.stmts_to_whyml(stmt.else_body)
            then_indented = "\n".join("  " + l for l in then_body.splitlines())
            else_indented = "\n".join("  " + l for l in else_body.splitlines())
            return f"if {cond} then begin\n{then_indented}\nend else begin\n{else_indented}\nend"
        elif isinstance(stmt, WhileStmt):
            cond = self.expr_to_whyml(stmt.condition)
            inv_lines = []
            for inv in stmt.invariants:
                inv_expr = self.expr_to_whyml(inv)
                inv_lines.append(f"  invariant {{ {inv_expr} }}")
            if stmt.variant:
                var_expr = self.expr_to_whyml(stmt.variant)
                inv_lines.append(f"  variant {{ {var_expr} }}")
            
            body_val = self.stmts_to_whyml(stmt.body)
            body_indented = "\n".join("  " + l for l in body_val.splitlines())
            inv_str = "\n".join(inv_lines)
            if inv_str:
                return f"while {cond} do\n{inv_str}\n{body_indented}\ndone"
            return f"while {cond} do\n{body_indented}\ndone"
        elif isinstance(stmt, CaseStmt):
            expr_val = self.expr_to_whyml(stmt.expr)
            branches_str = []
            for branch in stmt.branches:
                val_val = self.expr_to_whyml(branch.value)
                branch_body = self.stmts_to_whyml(branch.body)
                branch_body_indented = "\n".join("    " + l for l in branch_body.splitlines())
                branches_str.append(f"  | {val_val} ->\n{branch_body_indented}")
            if stmt.default_body:
                default_body = self.stmts_to_whyml(stmt.default_body)
                default_body_indented = "\n".join("    " + l for l in default_body.splitlines())
                branches_str.append(f"  | _ ->\n{default_body_indented}")
            branches_val = "\n".join(branches_str)
            return f"match {expr_val} with\n{branches_val}\nend"
        elif isinstance(stmt, ScopeStmt):
            combined = stmt.spawn_body + stmt.join_body + stmt.result_body
            body_val = self.stmts_to_whyml(combined)
            return f"let {stmt.name} = () in\nbegin\n{body_val}\nend"
        return f"(* UNSUPPORTED STATEMENT: {type(stmt).__name__} *)"

    def stmts_to_whyml(self, stmts: list[Any]) -> str:
        if not stmts:
            return "()"
        first = stmts[0]
        rest = stmts[1:]
        
        if isinstance(first, LetStmt):
            expr_val = self.expr_to_whyml(first.expr)
            name = first.name
            old_refs = set(self.refs)
            self.refs.add(name)
            rest_val = self.stmts_to_whyml(rest)
            self.refs = old_refs
            return f"let {name} = ref ({expr_val}) in\n{rest_val}"
            
        first_val = self.stmt_to_whyml(first)
        if rest:
            rest_val = self.stmts_to_whyml(rest)
            return f"{first_val};\n{rest_val}"
        return first_val

    def collect_mutated_params(self, body: list[Any], param_names: set[str]) -> set[str]:
        mutated = set()
        for stmt in body:
            if isinstance(stmt, AssignStmt):
                if stmt.name in param_names:
                    mutated.add(stmt.name)
            elif isinstance(stmt, FieldAssignStmt):
                root = stmt.path[0]
                if root in param_names:
                    mutated.add(root)
            elif isinstance(stmt, CallStmt):
                callee = self.routines.get(stmt.name)
                if callee:
                    for i, arg in enumerate(stmt.args):
                        arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                        if isinstance(arg_expr, VarExpr) and arg_expr.name in param_names:
                            if i < len(callee.params):
                                param_name = callee.params[i].name
                                if is_param_mutable(callee, param_name):
                                    mutated.add(arg_expr.name)
            elif isinstance(stmt, IfStmt):
                mutated.update(self.collect_mutated_params(stmt.then_body, param_names))
                mutated.update(self.collect_mutated_params(stmt.else_body, param_names))
            elif isinstance(stmt, WhileStmt):
                mutated.update(self.collect_mutated_params(stmt.body, param_names))
            elif isinstance(stmt, CaseStmt):
                for b in stmt.branches:
                    mutated.update(self.collect_mutated_params(b.body, param_names))
                if stmt.default_body:
                    mutated.update(self.collect_mutated_params(stmt.default_body, param_names))
            elif isinstance(stmt, ScopeStmt):
                mutated.update(self.collect_mutated_params(stmt.spawn_body, param_names))
                mutated.update(self.collect_mutated_params(stmt.join_body, param_names))
                mutated.update(self.collect_mutated_params(stmt.result_body, param_names))
        return mutated

    def routine_to_whyml(self, r: RoutineDecl) -> str:
        # Collect mutable params/globals
        mutated_names = set()
        if r.global_specs:
            for g in r.global_specs:
                if g.mode in ("In_Out", "Output"):
                    mutated_names.add(g.name)
        param_names = {p.name for p in r.params}
        mutated_names.update(self.collect_mutated_params(r.body, param_names))

        params_str = []
        self.refs = set()
        for p in r.params:
            p_type = self.map_type_name(p.type_name)
            if p.name in mutated_names:
                params_str.append(f"({p.name}: ref {p_type})")
                self.refs.add(p.name)
            else:
                params_str.append(f"({p.name}: {p_type})")
        params_val = " ".join(params_str) if params_str else "()"
        
        ret_type_str = self.map_type(r.return_type)
        
        # Build signature
        lines = []
        lines.append(f"  let {r.name} {params_val} : {ret_type_str}")
        
        # Contracts
        for req in r.requires:
            req_expr = self.expr_to_whyml(req)
            lines.append(f"    requires {{ {req_expr} }}")
        for ens in r.ensures:
            ens_expr = self.expr_to_whyml(ens)
            lines.append(f"    ensures  {{ {ens_expr} }}")
        for clause in r.aborts:
            if clause.condition:
                cond_expr = self.expr_to_whyml(clause.condition)
                lines.append(f"    raises   {{ {clause.error_name} -> {cond_expr} }}")
            else:
                lines.append(f"    raises   {{ {clause.error_name} }}")
                
        lines.append("  =")
        
        # Handle early returns with local exception
        has_ret = has_returns(r.body)
        if has_ret:
            if r.return_type is not None:
                lines.append(f"    exception Return {ret_type_str}")
            else:
                lines.append(f"    exception Return")
                
        body_val = self.stmts_to_whyml(r.body)
        if has_ret:
            # Wrap body in try-catch
            body_indented = "\n".join("      " + l for l in body_val.splitlines())
            lines.append("    try")
            lines.append(body_indented)
            if r.return_type is not None:
                lines.append("    with Return val -> val")
            else:
                lines.append("    with Return -> ()")
            lines.append("    end")
        else:
            body_indented = "\n".join("    " + l for l in body_val.splitlines())
            lines.append(body_indented)
            
        return "\n".join(lines)

def generate_whyml(program: Program) -> str:
    return WhyMLGenerator(program).generate()
