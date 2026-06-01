from __future__ import annotations
import re
from typing import Any
from freehold.core.ast import *
from freehold.core.verifier import VerifiedProgram

def get_smt_type(type_name: str | None) -> str:
    if not type_name:
        return "Int"
    if type_name.startswith("Array<"):
        parts = type_name[6:-1].split(",")
        elem = parts[0].strip()
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "Int"
        return f"(Array Int {elem_smt})"
    if type_name == "Boolean":
        return "Bool"
    if type_name == "Double":
        return "Real"
    return "Int"

def get_flat_var_types(env: dict[str, str], records: dict[str, Any]) -> dict[str, str]:
    flat = {}
    for var, type_name in env.items():
        if not type_name:
            flat[var] = type_name
            continue
        if type_name.startswith("Array<"):
            parts = type_name[6:-1].split(",")
            elem = parts[0].strip()
            size = parts[1].strip() if len(parts) > 1 else "10"
            if elem in records:
                expand_array_record_fields(var, elem, size, records, flat)
            else:
                flat[var] = type_name
        elif type_name in records:
            expand_record_fields(var, type_name, records, flat)
        else:
            flat[var] = type_name
    return flat

def expand_record_fields(prefix: str, rec_name: str, records: dict[str, Any], flat: dict[str, str]):
    rec = records[rec_name]
    for field_name, field_type in rec.fields.items():
        path_name = f"{prefix}_{field_name}"
        if field_type in records:
            expand_record_fields(path_name, field_type, records, flat)
        else:
            flat[path_name] = field_type

def expand_array_record_fields(prefix: str, rec_name: str, size: str, records: dict[str, Any], flat: dict[str, str]):
    rec = records[rec_name]
    for field_name, field_type in rec.fields.items():
        path_name = f"{prefix}_{field_name}"
        if field_type in records:
            expand_array_record_fields(path_name, field_type, size, records, flat)
        else:
            flat[path_name] = f"Array<{field_type}, {size}>"

def substitute_expr(e: Any, var_name: str, replacement: Any) -> Any:
    if isinstance(e, VarExpr) and e.name == var_name:
        return replacement
    if isinstance(e, SpecialResultExpr) and var_name in ("result", "value") and e.name in ("result", "value"):
        return replacement
    if isinstance(e, FieldAccessExpr):
        if e.path and e.path[0] == var_name:
            if isinstance(replacement, RecordLiteralExpr):
                field_name = e.path[1]
                field_expr = None
                for arg in replacement.args:
                    if arg.name == field_name:
                        field_expr = arg.expr
                        break
                if field_expr is not None:
                    if len(e.path) > 2:
                        dummy_name = f"_tmp_{field_name}"
                        nested = FieldAccessExpr([dummy_name] + e.path[2:], e.pos)
                        return substitute_expr(nested, dummy_name, field_expr)
                    return field_expr
            elif isinstance(replacement, VarExpr):
                return FieldAccessExpr([replacement.name] + e.path[1:], e.pos)
            elif isinstance(replacement, FieldAccessExpr):
                return FieldAccessExpr(replacement.path + e.path[1:], e.pos)
        return e
    if isinstance(e, UnaryExpr):
        return UnaryExpr(e.op, substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, BinaryExpr):
        return BinaryExpr(e.op, substitute_expr(e.left, var_name, replacement), substitute_expr(e.right, var_name, replacement), e.pos)
    if isinstance(e, CallExpr):
        return CallExpr(e.name, [substitute_expr(arg, var_name, replacement) for arg in e.args], e.type_args, getattr(e, "invariant", None), e.pos)
    if isinstance(e, IndexExpr):
        new_name = replacement.name if (isinstance(replacement, VarExpr) and e.name == var_name) else e.name
        return IndexExpr(new_name, substitute_expr(e.index, var_name, replacement), e.pos)
    if isinstance(e, IndexedFieldAccessExpr):
        new_name = replacement.name if (isinstance(replacement, VarExpr) and e.name == var_name) else e.name
        return IndexedFieldAccessExpr(new_name, substitute_expr(e.index, var_name, replacement), e.fields, e.pos)
    if isinstance(e, ForAllExpr):
        if e.var_name == var_name:
            return e
        return ForAllExpr(e.var_name, substitute_expr(e.lower, var_name, replacement), substitute_expr(e.upper, var_name, replacement), substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, ExistsExpr):
        if e.var_name == var_name:
            return e
        return ExistsExpr(e.var_name, substitute_expr(e.lower, var_name, replacement), substitute_expr(e.upper, var_name, replacement), substitute_expr(e.expr, var_name, replacement), e.pos)
    return e

def substitute_params(expr: Any, params: list[Param], args: list[Any]) -> Any:
    res = expr
    for param, arg in zip(params, args):
        arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
        res = substitute_expr(res, param.name, arg_expr)
    return res

def expr_to_smt(e: Any) -> str:
    if isinstance(e, NumberExpr): return str(e.value)
    if isinstance(e, DoubleExpr): return str(e.value)
    if isinstance(e, BoolExpr): return "true" if e.value else "false"
    if isinstance(e, StringExpr): return f'"{e.value}"'
    if isinstance(e, VarExpr): return e.name
    if isinstance(e, SpecialResultExpr): return e.name
    if isinstance(e, FieldAccessExpr): return "_".join(e.path)
    if isinstance(e, IndexExpr):
        idx = expr_to_smt(e.index)
        return f"(select {e.name} {idx})"
    if isinstance(e, IndexedFieldAccessExpr):
        idx = expr_to_smt(e.index)
        arr = e.name + "_" + "_".join(e.fields)
        return f"(select {arr} {idx})"
    if isinstance(e, ArrayLiteralExpr):
        res = "((as const (Array Int Int)) 0)"
        for idx, item in enumerate(e.items):
            val = expr_to_smt(item)
            res = f"(store {res} {idx} {val})"
        return res
    if isinstance(e, ForAllExpr):
        l = expr_to_smt(e.lower)
        u = expr_to_smt(e.upper)
        body = expr_to_smt(e.expr)
        return f"(forall (({e.var_name} Int)) (=> (and (>= {e.var_name} {l}) (<= {e.var_name} {u})) {body}))"
    if isinstance(e, ExistsExpr):
        l = expr_to_smt(e.lower)
        u = expr_to_smt(e.upper)
        body = expr_to_smt(e.expr)
        return f"(exists (({e.var_name} Int)) (and (>= {e.var_name} {l}) (<= {e.var_name} {u}) {body}))"
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

def smt_validity_query(path: list[str], obligation: str, var_types: dict[str, str] = None) -> str:
    lines = ["; Freehold SMT-LIB query", "(set-logic ALL)"]
    used_vars = set()
    excluded = {
        "true", "false", "and", "or", "not", "div", "mod", "forall", 
        "exists", "select", "store", "Array", "Int", "Bool", "Real", 
        "=>", "<=", ">="
    }
    bound_vars = set()
    for s in path + [obligation]:
        for m in re.finditer(r"\b(forall|exists)\s*\(\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+Int\)\)", s):
            bound_vars.add(m.group(2))
    for s in path + [obligation]:
        for word in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", s):
            if word not in excluded and word not in bound_vars:
                used_vars.add(word)
    for var in sorted(used_vars):
        type_name = var_types.get(var) if var_types else None
        smt_type = get_smt_type(type_name)
        lines.append(f"(declare-const {var} {smt_type})")
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

def find_routine(name: str, local_routines: dict[str, RoutineDecl], imports: list[ImportDecl] | None, imported_modules: dict[str, Any] | None) -> RoutineDecl | None:
    if name in local_routines:
        return local_routines[name]
    
    if "." in name and imported_modules:
        for mod_name, verified in sorted(imported_modules.items(), key=lambda item: len(item[0]), reverse=True):
            prefix = f"{mod_name}."
            if name.startswith(prefix):
                routine_name = name[len(prefix):]
                if "." not in routine_name:
                    if routine_name in verified.routines:
                        return verified.routines[routine_name]
    
    if imports and imported_modules:
        for import_decl in imports:
            imported = imported_modules.get(import_decl.module_name)
            if imported is None:
                continue
            if name in import_decl.exposing:
                if name in imported.routines:
                    return imported.routines[name]
                    
    return None

def walk_body(body: list[Any], env: dict[str, str], path_conditions: list[str], routines: dict[str, Any], types: dict[str, Any], records: dict[str, Any], obs: list[dict[str, str]], r: Any, r_name: str, channel_invariants: dict[str, Any] = None, spawned_tasks: dict[str, Any] = None, imports: list[Any] = None, imported_modules: dict[str, Any] = None):
    if channel_invariants is None:
        channel_invariants = {}
    if spawned_tasks is None:
        spawned_tasks = {}

    for stmt in body:
        for call in find_calls(stmt):
            cal = find_routine(call.name, routines, imports, imported_modules)
            if cal is not None:
                for arg, param in zip(call.args, cal.params):
                    arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                    param_type = param.type_name
                    if param_type in types:
                        td = types[param_type]
                        if td.min_value is not None:
                            expr_smt = expr_to_smt(arg_expr)
                            obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                            path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                            var_types = get_flat_var_types(env, records)
                            obs.append({
                                "routine": r_name,
                                "kind": "range_check",
                                "location": arg.pos.text() if hasattr(arg, "pos") else stmt.pos.text(),
                                "obligation": obligation,
                                "smt_query": smt_validity_query(path, obligation, var_types),
                            })
            if call.name == "channel_send":
                sender_name = call.args[0].name if isinstance(call.args[0], VarExpr) else None
                val_arg = call.args[1]
                if sender_name in channel_invariants and channel_invariants[sender_name] is not None:
                    inv = channel_invariants[sender_name]
                    if isinstance(inv, ForAllExpr):
                        subst_pred = substitute_expr(inv.expr, inv.var_name, val_arg)
                    else:
                        subst_pred = substitute_expr(inv, "value", val_arg)
                        subst_pred = substitute_expr(subst_pred, "result", val_arg)
                    obligation = expr_to_smt(subst_pred)
                    path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "channel_invariant",
                        "location": call.pos.text() if hasattr(call, "pos") else stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

        if isinstance(stmt, LetStmt):
            type_name = stmt.type_ref.name if isinstance(stmt.type_ref, TypeName) else ""
            env[stmt.name] = type_name
            
            expr = stmt.expr
            is_awaited = False
            if isinstance(expr, AwaitExpr):
                is_awaited = True
                expr = expr.expr
            
            # 1. Channel Creation
            if isinstance(expr, CallExpr) and expr.name == "channel":
                channel_invariants[stmt.name] = getattr(expr, "invariant", None)
            # 2. Channel Endpoint Association
            elif isinstance(expr, CallExpr) and expr.name in ("channel_sender", "channel_receiver"):
                if isinstance(expr.args[0], VarExpr):
                    chan_name = expr.args[0].name
                    channel_invariants[stmt.name] = channel_invariants.get(chan_name)
            # Alias Copying
            elif isinstance(expr, VarExpr) and expr.name in channel_invariants:
                channel_invariants[stmt.name] = channel_invariants[expr.name]
            
            # Channel Send Check
            is_send = False
            sender_name = None
            val_arg = None
            if isinstance(expr, CallExpr) and expr.name == "channel_send":
                is_send = True
                if isinstance(expr.args[0], VarExpr):
                    sender_name = expr.args[0].name
                val_arg = expr.args[1]
            if is_send and sender_name in channel_invariants and channel_invariants[sender_name] is not None:
                inv = channel_invariants[sender_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, val_arg)
                else:
                    subst_pred = substitute_expr(inv, "value", val_arg)
                    subst_pred = substitute_expr(subst_pred, "result", val_arg)
                obligation = expr_to_smt(subst_pred)
                path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types) + path_conditions
                var_types = get_flat_var_types(env, records)
                obs.append({
                    "routine": r_name,
                    "kind": "channel_invariant",
                    "location": expr.pos.text() if hasattr(expr, "pos") else stmt.pos.text(),
                    "obligation": obligation,
                    "smt_query": smt_validity_query(path, obligation, var_types),
                })
            
            # Normal Routine Call Ensures Propagation
            if isinstance(expr, CallExpr):
                target_routine = find_routine(expr.name, routines, imports, imported_modules)
                if target_routine is not None and not (expr.name == "scope_spawn" or expr.name.endswith(".spawn") or expr.name == "scope_join" or expr.name.endswith(".join")):
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, expr.args)
                        ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "value", VarExpr(stmt.name, stmt.pos))
                        ens_smt = expr_to_smt(ens_subst)
                        path_conditions = path_conditions + [ens_smt]
            
            # 3. Task Spawn
            if isinstance(expr, CallExpr) and (expr.name == "scope_spawn" or expr.name.endswith(".spawn")):
                task_arg_idx = 1 if expr.name == "scope_spawn" else 0
                task_call = expr.args[task_arg_idx]
                spawned_tasks[stmt.name] = task_call
                target_routine = None
                if isinstance(task_call, CallExpr):
                    target_routine = find_routine(task_call.name, routines, imports, imported_modules)
                if target_routine is not None:
                    for req in target_routine.requires:
                        req_subst = substitute_params(req, target_routine.params, task_call.args)
                        obligation = expr_to_smt(req_subst)
                        path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types) + path_conditions
                        var_types = get_flat_var_types(env, records)
                        obs.append({
                            "routine": r_name,
                            "kind": "precondition",
                            "location": stmt.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation, var_types),
                        })
            # Task Alias Copying
            elif isinstance(expr, VarExpr) and expr.name in spawned_tasks:
                spawned_tasks[stmt.name] = spawned_tasks[expr.name]
            
            # 4. Task Join / Await
            is_join = False
            handle_name = None
            if isinstance(expr, CallExpr) and (expr.name == "scope_join" or expr.name.endswith(".join")):
                is_join = True
                handle_arg_idx = 1 if expr.name == "scope_join" else 0
                if isinstance(expr.args[handle_arg_idx], VarExpr):
                    handle_name = expr.args[handle_arg_idx].name
            elif is_awaited and isinstance(expr, VarExpr):
                is_join = True
                handle_name = expr.name
            
            if is_join and handle_name in spawned_tasks:
                task_call = spawned_tasks[handle_name]
                target_routine = None
                if isinstance(task_call, CallExpr):
                    target_routine = find_routine(task_call.name, routines, imports, imported_modules)
                if target_routine is not None:
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, task_call.args)
                        ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "value", VarExpr(stmt.name, stmt.pos))
                        ens_smt = expr_to_smt(ens_subst)
                        path_conditions = path_conditions + [ens_smt]
            
            # 5. Channel Receive
            is_receive = False
            receiver_name = None
            if isinstance(expr, CallExpr) and expr.name == "channel_receive":
                is_receive = True
                if isinstance(expr.args[0], VarExpr):
                    receiver_name = expr.args[0].name
            if is_receive and receiver_name in channel_invariants and channel_invariants[receiver_name] is not None:
                inv = channel_invariants[receiver_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, VarExpr(stmt.name, stmt.pos))
                else:
                    subst_pred = substitute_expr(inv, "value", VarExpr(stmt.name, stmt.pos))
                    subst_pred = substitute_expr(subst_pred, "result", VarExpr(stmt.name, stmt.pos))
                pred_smt = expr_to_smt(subst_pred)
                path_conditions = path_conditions + [pred_smt]

            if type_name in types:
                td = types[type_name]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })
        elif isinstance(stmt, AssignStmt):
            expr = stmt.expr
            is_awaited = False
            if isinstance(expr, AwaitExpr):
                is_awaited = True
                expr = expr.expr
            
            # Alias Copying
            if isinstance(expr, VarExpr) and expr.name in channel_invariants:
                channel_invariants[stmt.name] = channel_invariants[expr.name]
            if isinstance(expr, VarExpr) and expr.name in spawned_tasks:
                spawned_tasks[stmt.name] = spawned_tasks[expr.name]
            
            # Channel Send Check
            is_send = False
            sender_name = None
            val_arg = None
            if isinstance(expr, CallExpr) and expr.name == "channel_send":
                is_send = True
                if isinstance(expr.args[0], VarExpr):
                    sender_name = expr.args[0].name
                val_arg = expr.args[1]
            if is_send and sender_name in channel_invariants and channel_invariants[sender_name] is not None:
                inv = channel_invariants[sender_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, val_arg)
                else:
                    subst_pred = substitute_expr(inv, "value", val_arg)
                    subst_pred = substitute_expr(subst_pred, "result", val_arg)
                obligation = expr_to_smt(subst_pred)
                path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types) + path_conditions
                var_types = get_flat_var_types(env, records)
                obs.append({
                    "routine": r_name,
                    "kind": "channel_invariant",
                    "location": expr.pos.text() if hasattr(expr, "pos") else stmt.pos.text(),
                    "obligation": obligation,
                    "smt_query": smt_validity_query(path, obligation, var_types),
                })
            
            # Normal Routine Call Ensures Propagation
            if isinstance(expr, CallExpr):
                target_routine = find_routine(expr.name, routines, imports, imported_modules)
                if target_routine is not None and not (expr.name == "scope_spawn" or expr.name.endswith(".spawn") or expr.name == "scope_join" or expr.name.endswith(".join")):
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, expr.args)
                        ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "value", VarExpr(stmt.name, stmt.pos))
                        ens_smt = expr_to_smt(ens_subst)
                        path_conditions = path_conditions + [ens_smt]
            
            # Task Join / Await
            is_join = False
            handle_name = None
            if isinstance(expr, CallExpr) and (expr.name == "scope_join" or expr.name.endswith(".join")):
                is_join = True
                handle_arg_idx = 1 if expr.name == "scope_join" else 0
                if isinstance(expr.args[handle_arg_idx], VarExpr):
                    handle_name = expr.args[handle_arg_idx].name
            elif is_awaited and isinstance(expr, VarExpr):
                is_join = True
                handle_name = expr.name
            
            if is_join and handle_name in spawned_tasks:
                task_call = spawned_tasks[handle_name]
                target_routine = None
                if isinstance(task_call, CallExpr):
                    target_routine = find_routine(task_call.name, routines, imports, imported_modules)
                if target_routine is not None:
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, task_call.args)
                        ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "value", VarExpr(stmt.name, stmt.pos))
                        ens_smt = expr_to_smt(ens_subst)
                        path_conditions = path_conditions + [ens_smt]
            
            # Channel Receive
            is_receive = False
            receiver_name = None
            if isinstance(expr, CallExpr) and expr.name == "channel_receive":
                is_receive = True
                if isinstance(expr.args[0], VarExpr):
                    receiver_name = expr.args[0].name
            if is_receive and receiver_name in channel_invariants and channel_invariants[receiver_name] is not None:
                inv = channel_invariants[receiver_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, VarExpr(stmt.name, stmt.pos))
                else:
                    subst_pred = substitute_expr(inv, "value", VarExpr(stmt.name, stmt.pos))
                    subst_pred = substitute_expr(subst_pred, "result", VarExpr(stmt.name, stmt.pos))
                pred_smt = expr_to_smt(subst_pred)
                path_conditions = path_conditions + [pred_smt]

            type_name = env.get(stmt.name, "")
            if type_name in types:
                td = types[type_name]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })
        elif isinstance(stmt, FieldAssignStmt):
            target_type = resolve_field_path_type(stmt.path, env, records)
            if target_type in types:
                td = types[target_type]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(stmt.expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
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
                        var_types = get_flat_var_types(env, records)
                        obs.append({
                            "routine": r_name,
                            "kind": "range_check",
                            "location": stmt.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation, var_types),
                        })

            if r.kind == "function":
                path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types) + path_conditions
                var_types = get_flat_var_types(env, records)
                ret_expr = None
                if isinstance(stmt.value, ReturnPlain):
                    ret_expr = stmt.value.expr
                elif isinstance(stmt.value, ReturnOk):
                    ret_expr = stmt.value.expr
                if ret_expr is not None:
                    for ens in r.ensures:
                        ens_subst = substitute_expr(ens, "result", ret_expr)
                        ens_subst = substitute_expr(ens_subst, "value", ret_expr)
                        obligation = expr_to_smt(ens_subst)
                        obs.append({
                            "routine": r_name,
                            "kind": "ensures",
                            "location": ens.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation, var_types),
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
                var_types = get_flat_var_types(env, records)
                obs.append({
                    "routine": r_name,
                    "kind": "abort_check",
                    "location": stmt.pos.text(),
                    "obligation": abort_cond_smt,
                    "smt_query": smt_validity_query(path, abort_cond_smt, var_types),
                })
        elif isinstance(stmt, IfStmt):
            cond_smt = expr_to_smt(stmt.condition)
            walk_body(stmt.then_body, dict(env), path_conditions + [cond_smt], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules)
            walk_body(stmt.else_body, dict(env), path_conditions + [f"(not {cond_smt})"], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules)
        elif isinstance(stmt, WhileStmt):
            walk_body(stmt.body, dict(env), path_conditions + [expr_to_smt(stmt.condition)], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules)
        elif isinstance(stmt, CaseStmt):
            expr_smt = expr_to_smt(stmt.expr)
            negated_conds = []
            for branch in stmt.branches:
                val_smt = expr_to_smt(branch.value)
                branch_cond = f"(= {expr_smt} {val_smt})"
                negated_conds.append(f"(not {branch_cond})")
                walk_body(branch.body, dict(env), path_conditions + [branch_cond], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules)
            if stmt.default_body:
                default_cond = f"(and {' '.join(negated_conds)})" if len(negated_conds) > 1 else negated_conds[0] if negated_conds else "true"
                walk_body(stmt.default_body, dict(env), path_conditions + [default_cond], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules)
        elif isinstance(stmt, ScopeStmt):
            path_conditions = walk_body(stmt.spawn_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules)
            path_conditions = walk_body(stmt.join_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules)
            path_conditions = walk_body(stmt.result_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules)
    return path_conditions

def symbolic_obligations(vp: VerifiedProgram, imported_modules: dict[str, Any] | None = None) -> list[dict[str, str]]:
    obs: list[dict[str, str]] = []
    types = vp.types
    routines = vp.routines
    records = vp.records
    imports = vp.ast.imports if hasattr(vp, "ast") and vp.ast else None
    for r in routines.values():
        env = {}
        for p in r.params:
            env[p.name] = p.type_name
        path = [expr_to_smt(req) for req in r.requires]
        walk_body(r.body, env, [], routines, types, records, obs, r, r.name, {}, {}, imports, imported_modules)
    return obs

def solve_smt_query(smt_query: str, prover: str | None = None, timeout: int | None = None) -> str:
    import os
    import shutil
    import tempfile
    import subprocess

    # 1. Parse provers list (from argument, or FREEHOLD_PROVER, default to "z3")
    prover_str = prover or os.environ.get("FREEHOLD_PROVER", "z3")
    provers = [p.strip().lower() for p in prover_str.split(",") if p.strip()]
    if not provers:
        provers = ["z3"]

    # 2. Parse timeout (from argument, or FREEHOLD_TIMEOUT, default to 2)
    if timeout is not None:
        timeout_sec = timeout
    else:
        try:
            timeout_sec = int(os.environ.get("FREEHOLD_TIMEOUT", "2"))
        except ValueError:
            timeout_sec = 2

    # 3. Solver implementations
    def run_z3_api(query_str: str) -> str | None:
        try:
            import z3
            s = z3.Solver()
            s.set("timeout", timeout_sec * 1000)
            s.from_string(query_str)
            res = s.check()
            if res == z3.unsat:
                return "unsat"
            elif res == z3.sat:
                return "sat"
            else:
                return "unknown"
        except (ImportError, Exception):
            return None

    def run_cmd_solver(binary_name: str, query_str: str) -> str:
        bin_path = shutil.which(binary_name)
        if not bin_path:
            return "unknown"
        fd, path = tempfile.mkstemp(suffix=".smt2")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(query_str)
            res = subprocess.run([bin_path, path], capture_output=True, text=True, timeout=timeout_sec)
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

    # 4. Sequential search over configured provers
    results = []
    for p in provers:
        if p == "z3":
            api_res = run_z3_api(smt_query)
            if api_res == "unsat":
                return "unsat"
            if api_res is not None:
                results.append(api_res)
                continue
            cmd_res = run_cmd_solver("z3", smt_query)
            if cmd_res == "unsat":
                return "unsat"
            results.append(cmd_res)
        elif p == "cvc5":
            cmd_res = run_cmd_solver("cvc5", smt_query)
            if cmd_res == "unsat":
                return "unsat"
            results.append(cmd_res)
        elif p == "alt-ergo":
            cmd_res = run_cmd_solver("alt-ergo", smt_query)
            if cmd_res == "unsat":
                return "unsat"
            results.append(cmd_res)
        else:
            cmd_res = run_cmd_solver(p, smt_query)
            if cmd_res == "unsat":
                return "unsat"
            results.append(cmd_res)

    # 5. Determine final verdict if no solver proved unsat
    if "sat" in results:
        return "sat"
    return "unknown"
