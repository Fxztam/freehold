from __future__ import annotations
import re
from typing import Any
from freehold.core.ast import *
from freehold.core.verifier import VerifiedProgram

def expr_to_smt(e: Any) -> str:
    if isinstance(e, NumberExpr): return str(e.value)
    if isinstance(e, DoubleExpr): return str(e.value)
    if isinstance(e, BoolExpr): return "true" if e.value else "false"
    if isinstance(e, VarExpr): return e.name
    if isinstance(e, SpecialResultExpr): return e.name
    if isinstance(e, FieldAccessExpr): return "_".join(e.path)
    if isinstance(e, UnaryExpr):
        inner = expr_to_smt(e.expr)
        return f"(not {inner})" if e.op == "not" else f"(- {inner})"
    if isinstance(e, BinaryExpr):
        a, b = expr_to_smt(e.left), expr_to_smt(e.right)
        if e.op == "=": return f"(= {a} {b})"
        if e.op == "!=": return f"(not (= {a} {b}))"
        if e.op == "and": return f"(and {a} {b})"
        if e.op == "or": return f"(or {a} {b})"
        if e.op == "/": return f"(div {a} {b})"
        return f"({e.op} {a} {b})"
    if isinstance(e, CallExpr):
        return f"({e.name} {' '.join(expr_to_smt(a) for a in e.args)})"
    return "UNSUPPORTED"

def smt_validity_query(path: list[str], obligation: str) -> str:
    lines = ["; Freehold SMT-LIB query", "(set-logic ALL)"]
    used_vars = set()
    for s in path + [obligation]:
        for word in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", s):
            if word not in ("true", "false", "and", "or", "not", "div", "mod"):
                used_vars.add(word)
    for var in sorted(used_vars):
        lines.append(f"(declare-const {var} Int)")
    for pc in path:
        lines.append(f"(assert {pc})")
    lines.append(f"(assert (not {obligation}))")
    lines.append("(check-sat)")
    lines.append("; unsat means proved")
    return "\n".join(lines)

def get_range_assertions(env: dict[str, str], types: dict[str, Any]) -> list[str]:
    assertions = []
    for var_name, type_name in env.items():
        if type_name in types:
            td = types[type_name]
            if td.min_value is not None:
                assertions.append(f"(>= {var_name} {td.min_value})")
                assertions.append(f"(<= {var_name} {td.max_value})")
    return assertions

def find_calls(node: Any) -> list[CallExpr | CallStmt]:
    calls = []
    if isinstance(node, (CallExpr, CallStmt)):
        calls.append(node)
    if hasattr(node, "__dict__"):
        for val in node.__dict__.values():
            if isinstance(val, list):
                for item in val:
                    calls.extend(find_calls(item))
            elif val is not None:
                calls.extend(find_calls(val))
    return calls

def resolve_field_path_type(path: list[str], env: dict[str, str], records: dict[str, Any]) -> str | None:
    if not path:
        return None
    root = path[0]
    if root not in env:
        return None
    curr_type = env[root]
    for field in path[1:]:
        if curr_type not in records:
            return None
        rec = records[curr_type]
        if field not in rec.fields:
            return None
        curr_type = rec.fields[field]
    return curr_type

def walk_body(body: list[Any], env: dict[str, str], path_conditions: list[str], routines: dict[str, Any], types: dict[str, Any], records: dict[str, Any], obs: list[dict[str, str]], r: Any, r_name: str):
    for stmt in body:
        for call in find_calls(stmt):
            if call.name in routines:
                cal = routines[call.name]
                for arg, param in zip(call.args, cal.params):
                    arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                    param_type = param.type_name
                    if param_type in types:
                        td = types[param_type]
                        if td.min_value is not None:
                            expr_smt = expr_to_smt(arg_expr)
                            obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                            path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                            obs.append({
                                "routine": r_name,
                                "kind": "range_check",
                                "location": arg.pos.text() if hasattr(arg, "pos") else stmt.pos.text(),
                                "obligation": obligation,
                                "smt_query": smt_validity_query(path, obligation),
                            })

        if isinstance(stmt, LetStmt):
            type_name = stmt.type_ref.name if isinstance(stmt.type_ref, TypeName) else ""
            env[stmt.name] = type_name
            if type_name in types:
                td = types[type_name]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation),
                    })
        elif isinstance(stmt, AssignStmt):
            type_name = env.get(stmt.name, "")
            if type_name in types:
                td = types[type_name]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation),
                    })
        elif isinstance(stmt, FieldAssignStmt):
            target_type = resolve_field_path_type(stmt.path, env, records)
            if target_type in types:
                td = types[target_type]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation),
                    })
        elif isinstance(stmt, ReturnStmt):
            return_types = []
            exprs = []
            if isinstance(r.return_type, ResultTypeName):
                if isinstance(stmt.value, ReturnOk):
                    return_types.append(r.return_type.ok_type)
                    exprs.append(stmt.value.expr)
            elif isinstance(r.return_type, TypeName):
                if isinstance(stmt.value, ReturnPlain):
                    return_types.append(r.return_type)
                    exprs.append(stmt.value.expr)
            for ret_type, expr in zip(return_types, exprs):
                if isinstance(ret_type, TypeName) and ret_type.name in types:
                    td = types[ret_type.name]
                    if td.min_value is not None:
                        expr_smt = expr_to_smt(expr)
                        obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                        path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                        obs.append({
                            "routine": r_name,
                            "kind": "range_check",
                            "location": stmt.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation),
                        })
        elif isinstance(stmt, AbortStmt):
            abort_cond = None
            for clause in r.aborts:
                if clause.error_name == stmt.error_name:
                    abort_cond = clause.condition
                    break
            if abort_cond is not None:
                abort_cond_smt = expr_to_smt(abort_cond)
                path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                obs.append({
                    "routine": r_name,
                    "kind": "abort_check",
                    "location": stmt.pos.text(),
                    "obligation": abort_cond_smt,
                    "smt_query": smt_validity_query(path, abort_cond_smt),
                })
        elif isinstance(stmt, IfStmt):
            cond_smt = expr_to_smt(stmt.condition)
            walk_body(stmt.then_body, dict(env), path_conditions + [cond_smt], routines, types, records, obs, r, r_name)
            walk_body(stmt.else_body, dict(env), path_conditions + [f"(not {cond_smt})"], routines, types, records, obs, r, r_name)
        elif isinstance(stmt, WhileStmt):
            walk_body(stmt.body, dict(env), path_conditions + [expr_to_smt(stmt.condition)], routines, types, records, obs, r, r_name)
        elif isinstance(stmt, CaseStmt):
            expr_smt = expr_to_smt(stmt.expr)
            negated_conds = []
            for branch in stmt.branches:
                val_smt = expr_to_smt(branch.value)
                branch_cond = f"(= {expr_smt} {val_smt})"
                negated_conds.append(f"(not {branch_cond})")
                walk_body(branch.body, dict(env), path_conditions + [branch_cond], routines, types, records, obs, r, r_name)
            if stmt.default_body:
                default_cond = f"(and {' '.join(negated_conds)})" if len(negated_conds) > 1 else negated_conds[0] if negated_conds else "true"
                walk_body(stmt.default_body, dict(env), path_conditions + [default_cond], routines, types, records, obs, r, r_name)

def symbolic_obligations(vp: VerifiedProgram) -> list[dict[str, str]]:
    obs: list[dict[str, str]] = []
    types = vp.types
    routines = vp.routines
    records = vp.records
    for r in routines.values():
        env = {}
        for p in r.params:
            env[p.name] = p.type_name
        path = [expr_to_smt(req) for req in r.requires]
        walk_body(r.body, env, [], routines, types, records, obs, r, r.name)
        if r.kind == "function":
            path_with_ranges = path + get_range_assertions(env, types)
            for ens in r.ensures:
                obligation = expr_to_smt(ens)
                obs.append({
                    "routine": r.name,
                    "kind": "ensures",
                    "location": ens.pos.text(),
                    "obligation": obligation,
                    "smt_query": smt_validity_query(path_with_ranges, obligation),
                })
    return obs

def solve_smt_query(smt_query: str) -> str:
    try:
        import z3
        s = z3.Solver()
        s.from_string(smt_query)
        res = s.check()
        if res == z3.unsat:
            return "unsat"
        elif res == z3.sat:
            return "sat"
        else:
            return "unknown"
    except (ImportError, Exception):
        pass

    import shutil
    import os
    import tempfile
    import subprocess

    z3_bin = shutil.which("z3")
    if z3_bin:
        fd, path = tempfile.mkstemp(suffix=".smt2")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(smt_query)
            res = subprocess.run([z3_bin, path], capture_output=True, text=True, timeout=2)
            output = res.stdout.strip()
            if "unsat" in output:
                return "unsat"
            elif "sat" in output:
                return "sat"
            else:
                return "unknown"
        except Exception:
            return "unknown"
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    return "unknown"
