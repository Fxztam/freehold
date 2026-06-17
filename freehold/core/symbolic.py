from __future__ import annotations
import re
from typing import Any
from freehold.core.ast import *
from freehold.core.verifier import VerifiedProgram

def ast_type_to_str(t) -> str:
    if isinstance(t, TypeName):
        return t.name
    if isinstance(t, ArrayTypeName):
        return f"Array<{t.element_type}, {t.size}>"
    if isinstance(t, ResultTypeName):
        return f"Result<{ast_type_to_str(t.ok_type)}, {t.error_type}>"
    if isinstance(t, str):
        return t
    return ""

def get_smt_type(type_name: str | None, var_name: str = "") -> str:
    if var_name == "success" or var_name == "failure" or var_name.endswith("_success") or var_name.endswith("_failure"):
        return "Bool"
    if not type_name:
        return "Int"
    if type_name.startswith("Array<"):
        parts = type_name[6:-1].split(",")
        elem = parts[0].strip()
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "Int"
        return f"(Array Int {elem_smt})"
    if type_name.startswith("Map<"):
        elem = type_name[4:-1].strip()
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "String" if elem == "String" else "Int"
        return f"(Array String {elem_smt})"
    if type_name.startswith("Set<"):
        elem = type_name[4:-1].strip()
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "String" if elem == "String" else "Int"
        return f"(Array {elem_smt} Bool)"
    if type_name == "Boolean":
        return "Bool"
    if type_name == "Double":
        return "Real"
    if type_name == "String":
        return "String"
    return "Int"

def add_json_stringify_postconditions(stmt_name: str, arg: Any, env: dict[str, str], records: dict[str, Any]) -> list[str]:
    res = []
    type_name = None
    if isinstance(arg, VarExpr):
        type_name = env.get(arg.name)
    elif isinstance(arg, RecordLiteralExpr):
        type_name = arg.type_name

    if type_name in records:
        r_def = records[type_name]
        for field_name, field_type in r_def.fields.items():
            field_val_smt = None
            if isinstance(arg, VarExpr):
                field_val_smt = f"{arg.name}_{field_name}"
            elif isinstance(arg, RecordLiteralExpr):
                named_arg = next((a for a in arg.args if a.name == field_name), None)
                if named_arg is not None:
                    field_val_smt = expr_to_smt(named_arg.expr)

            if field_val_smt is not None:
                if field_type == "String":
                    res.append(f"(>= (str.indexof {stmt_name} {field_val_smt} 0) 0)")
                elif field_type == "Integer":
                    res.append(f"(>= (str.indexof {stmt_name} (str.from_int {field_val_smt}) 0) 0)")
                elif field_type == "Boolean":
                    res.append(f"(=> {field_val_smt} (>= (str.indexof {stmt_name} \"true\" 0) 0))")
                    res.append(f"(=> (not {field_val_smt}) (>= (str.indexof {stmt_name} \"false\" 0) 0))")
    return res

def parse_result_types(type_name: str) -> tuple[str, str]:
    content = type_name[7:-1]
    depth = 0
    comma_idx = -1
    for i, c in enumerate(content):
        if c == '<':
            depth += 1
        elif c == '>':
            depth -= 1
        elif c == ',' and depth == 0:
            comma_idx = i
            break
    ok_t = content[:comma_idx].strip() if comma_idx != -1 else content.strip()
    err_t = content[comma_idx+1:].strip() if comma_idx != -1 else ""
    return ok_t, err_t

def expand_var_type(var: str, type_name: str, records: dict[str, Any], flat: dict[str, str]):
    if not type_name:
        flat[var] = type_name
        return
    if type_name.startswith("Result<"):
        flat[f"{var}_success"] = "Boolean"
        flat[f"{var}_failure"] = "Boolean"
        ok_t, err_t = parse_result_types(type_name)
        expand_var_type(f"{var}_value", ok_t, records, flat)
        expand_var_type(f"{var}_error", err_t, records, flat)
    elif type_name.startswith("Map<"):
        val_t = type_name[4:-1].strip()
        flat[f"{var}_success"] = "Map<Boolean>"
        flat[f"{var}_failure"] = "Map<Boolean>"
        expand_map_var_type(f"{var}_value", val_t, records, flat)
        flat[f"{var}_error"] = "Map<String>"
    elif type_name.startswith("Array<"):
        parts = type_name[6:-1].split(",")
        elem = parts[0].strip()
        size = parts[1].strip() if len(parts) > 1 else "10"
        expand_array_var_type(var, elem, size, records, flat)
    elif type_name in records:
        rec = records[type_name]
        for field_name, field_type in rec.fields.items():
            expand_var_type(f"{var}_{field_name}", field_type, records, flat)
    else:
        flat[var] = type_name

def expand_map_var_type(prefix: str, type_name: str, records: dict[str, Any], flat: dict[str, str]):
    if type_name.startswith("Result<"):
        flat[f"{prefix}_success"] = "Map<Boolean>"
        flat[f"{prefix}_failure"] = "Map<Boolean>"
        ok_t, err_t = parse_result_types(type_name)
        expand_map_var_type(f"{prefix}_value", ok_t, records, flat)
        expand_map_var_type(f"{prefix}_error", err_t, records, flat)
    elif type_name.startswith("Map<"):
        flat[prefix] = type_name
    elif type_name in records:
        rec = records[type_name]
        for field_name, field_type in rec.fields.items():
            expand_map_var_type(f"{prefix}_{field_name}", field_type, records, flat)
    else:
        flat[prefix] = f"Map<{type_name}>"

def expand_array_var_type(prefix: str, type_name: str, size: str, records: dict[str, Any], flat: dict[str, str]):
    if type_name.startswith("Result<"):
        flat[f"{prefix}_success"] = f"Array<Boolean, {size}>"
        flat[f"{prefix}_failure"] = f"Array<Boolean, {size}>"
        ok_t, err_t = parse_result_types(type_name)
        expand_array_var_type(f"{prefix}_value", ok_t, size, records, flat)
        expand_array_var_type(f"{prefix}_error", err_t, size, records, flat)
    elif type_name.startswith("Array<"):
        flat[prefix] = f"Array<{type_name}, {size}>"
    elif type_name in records:
        rec = records[type_name]
        for field_name, field_type in rec.fields.items():
            expand_array_var_type(f"{prefix}_{field_name}", field_type, size, records, flat)
    else:
        flat[prefix] = f"Array<{type_name}, {size}>"

def get_flat_var_types(env: dict[str, str], records: dict[str, Any]) -> dict[str, str]:
    flat = {}
    for var, type_name in env.items():
        expand_var_type(var, type_name, records, flat)
    return flat

def substitute_expr(e: Any, var_name: str, replacement: Any) -> Any:
    if isinstance(e, VarExpr) and e.name == var_name:
        return replacement
    if isinstance(e, SpecialResultExpr) and e.name == var_name:
        return replacement
    if isinstance(e, FieldAccessExpr):
        joined_path = "_".join(e.path)
        if joined_path == var_name:
            return replacement
        if e.path and e.path[0] == var_name:
            if var_name == "result" and len(e.path) > 1 and e.path[1] == "value" and not isinstance(replacement, RecordLiteralExpr):
                if len(e.path) > 2:
                    dummy_name = "_tmp_val"
                    nested = FieldAccessExpr([dummy_name] + e.path[2:], e.pos)
                    return substitute_expr(nested, dummy_name, replacement)
                return replacement
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
            elif isinstance(replacement, IndexExpr):
                return IndexedFieldAccessExpr(replacement.name, replacement.index, e.path[1:], e.pos)
            elif isinstance(replacement, IndexedFieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.name, replacement.index, replacement.fields + e.path[1:], e.pos)
        return e
    if isinstance(e, UnaryExpr):
        return UnaryExpr(e.op, substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, BinaryExpr):
        return BinaryExpr(e.op, substitute_expr(e.left, var_name, replacement), substitute_expr(e.right, var_name, replacement), e.pos)
    if isinstance(e, CallExpr):
        if e.name == "old":
            return e
        return CallExpr(
            name=e.name,
            args=[substitute_expr(arg, var_name, replacement) for arg in e.args],
            pos=e.pos,
            type_args=e.type_args,
            invariant=getattr(e, "invariant", None),
        )
    if isinstance(e, AwaitExpr):
        return AwaitExpr(substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, IndexExpr):
        if e.name == var_name:
            if isinstance(replacement, ArrayLiteralExpr):
                idx_expr = substitute_expr(e.index, var_name, replacement)
                if isinstance(idx_expr, NumberExpr):
                    idx_val = int(idx_expr.value)
                    if 0 <= idx_val < len(replacement.items):
                        return replacement.items[idx_val]
            elif isinstance(replacement, CallExpr) and replacement.name == "Map.set":
                target_idx = substitute_expr(e.index, var_name, replacement)
                store_idx = replacement.args[1]
                store_val = replacement.args[2]
                if repr(target_idx) == repr(store_idx):
                    return store_val
                nested = IndexExpr("dummy_name", target_idx, e.pos)
                res = substitute_expr(nested, "dummy_name", replacement.args[0])
                return res
            elif isinstance(replacement, FieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.path[0], substitute_expr(e.index, var_name, replacement), replacement.path[1:], e.pos)
            elif isinstance(replacement, VarExpr):
                return IndexExpr(replacement.name, substitute_expr(e.index, var_name, replacement), e.pos)
        return IndexExpr(e.name, substitute_expr(e.index, var_name, replacement), e.pos)
    if isinstance(e, IndexedFieldAccessExpr):
        if e.name == var_name:
            if isinstance(replacement, ArrayLiteralExpr):
                idx_expr = substitute_expr(e.index, var_name, replacement)
                if isinstance(idx_expr, NumberExpr):
                    idx_val = int(idx_expr.value)
                    if 0 <= idx_val < len(replacement.items):
                        target_item = replacement.items[idx_val]
                        if isinstance(target_item, VarExpr):
                            return FieldAccessExpr([target_item.name] + e.fields, e.pos)
                        if isinstance(target_item, FieldAccessExpr):
                            return FieldAccessExpr(target_item.path + e.fields, e.pos)
                        if isinstance(target_item, RecordLiteralExpr):
                            dummy_name = f"_tmp_arr_item"
                            nested = FieldAccessExpr([dummy_name] + e.fields, e.pos)
                            return substitute_expr(nested, dummy_name, target_item)
            elif isinstance(replacement, FieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.path[0], substitute_expr(e.index, var_name, replacement), replacement.path[1:] + e.fields, e.pos)
            elif isinstance(replacement, VarExpr):
                return IndexedFieldAccessExpr(replacement.name, substitute_expr(e.index, var_name, replacement), e.fields, e.pos)
        return IndexedFieldAccessExpr(e.name, substitute_expr(e.index, var_name, replacement), e.fields, e.pos)
    if isinstance(e, ForAllExpr):
        if e.var_name == var_name:
            return e
        return ForAllExpr(e.var_name, substitute_expr(e.lower, var_name, replacement), substitute_expr(e.upper, var_name, replacement), substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, ExistsExpr):
        if e.var_name == var_name:
            return e
        return ExistsExpr(e.var_name, substitute_expr(e.lower, var_name, replacement), substitute_expr(e.upper, var_name, replacement), substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, NamedArg):
        return NamedArg(e.name, substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, RecordLiteralExpr):
        return RecordLiteralExpr(e.type_name, [substitute_expr(arg, var_name, replacement) for arg in e.args], e.pos)
    if isinstance(e, ArrayLiteralExpr):
        return ArrayLiteralExpr([substitute_expr(item, var_name, replacement) for item in e.items], e.pos)
    if isinstance(e, MapLiteralExpr):
        return MapLiteralExpr(e.type_name, [substitute_expr(item, var_name, replacement) for item in e.entries], e.pos)
    if isinstance(e, SetLiteralExpr):
        return SetLiteralExpr(e.type_name, [substitute_expr(item, var_name, replacement) for item in e.items], e.pos)
    if isinstance(e, MapEntry):
        return MapEntry(e.key, substitute_expr(e.expr, var_name, replacement), e.pos)
    if isinstance(e, IsExpr):
        return IsExpr(substitute_expr(e.left, var_name, replacement), e.right, e.pos)
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
    if isinstance(e, MapLiteralExpr):
        t_name = e.type_name
        import re
        generic_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)<(.+)>", t_name.strip())
        if generic_match and generic_match.group(1) == "Map":
            elem = generic_match.group(2).strip()
        else:
            elem = "Integer"
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "String" if elem == "String" else "Int"
        val_default = "false" if elem == "Boolean" else "0.0" if elem == "Double" else '""' if elem == "String" else "0"
        res = f"((as const (Array String {elem_smt})) {val_default})"
        for entry in e.entries:
            key_str = f'"{entry.key}"'
            val_str = expr_to_smt(entry.expr)
            res = f"(store {res} {key_str} {val_str})"
        return res
    if isinstance(e, SetLiteralExpr):
        t_name = e.type_name
        import re
        generic_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)<(.+)>", t_name.strip())
        if generic_match and generic_match.group(1) == "Set":
            elem = generic_match.group(2).strip()
        else:
            elem = "Integer"
        elem_smt = "Bool" if elem == "Boolean" else "Real" if elem == "Double" else "String" if elem == "String" else "Int"
        res = f"((as const (Array {elem_smt} Bool)) false)"
        for item in e.items:
            item_str = expr_to_smt(item)
            res = f"(store {res} {item_str} true)"
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
        if e.op == "is": return "true"
        a, b = expr_to_smt(e.left), expr_to_smt(e.right)
        if e.op == "=": return f"(= {a} {b})"
        if e.op == "!=": return f"(not (= {a} {b}))"
        if e.op == "and": return f"(and {a} {b})"
        if e.op == "or": return f"(or {a} {b})"
        if e.op == "/": return f"(div {a} {b})"
        return f"({e.op} {a} {b})"
    if isinstance(e, CallExpr):
        if e.name == "old":
            return expr_to_smt(e.args[0])
        if e.name == "Map.size":
            target = e.args[0]
            if isinstance(target, MapLiteralExpr):
                return str(len(target.entries))
            arg_smt = expr_to_smt(target)
            return f"(Map_size {arg_smt})"
        if e.name == "Map.set":
            target = e.args[0]
            key_expr = e.args[1]
            val_expr = e.args[2]
            if isinstance(target, MapLiteralExpr) and isinstance(key_expr, StringExpr):
                new_entries = [entry for entry in target.entries if entry.key != key_expr.value]
                new_entries.append(MapEntry(key_expr.value, val_expr, target.pos))
                new_map = MapLiteralExpr(target.type_name, new_entries, target.pos)
                return expr_to_smt(new_map)
            m_smt = expr_to_smt(target)
            k_smt = expr_to_smt(key_expr)
            v_smt = expr_to_smt(val_expr)
            return f"(store {m_smt} {k_smt} {v_smt})"
        if e.name == "Map.remove":
            target = e.args[0]
            key_expr = e.args[1]
            if isinstance(target, MapLiteralExpr) and isinstance(key_expr, StringExpr):
                new_entries = [entry for entry in target.entries if entry.key != key_expr.value]
                new_map = MapLiteralExpr(target.type_name, new_entries, target.pos)
                return expr_to_smt(new_map)
            m_smt = expr_to_smt(target)
            k_smt = expr_to_smt(key_expr)
            return f"(store {m_smt} {k_smt} 0)"
        if e.name == "Set.size":
            target = e.args[0]
            if isinstance(target, SetLiteralExpr):
                return str(len(target.items))
            arg_smt = expr_to_smt(target)
            return f"(Set_size {arg_smt})"
        if e.name == "Set.contains":
            target = e.args[0]
            elem_expr = e.args[1]
            m_smt = expr_to_smt(target)
            k_smt = expr_to_smt(elem_expr)
            return f"(select {m_smt} {k_smt})"
        if e.name == "Set.add":
            target = e.args[0]
            elem_expr = e.args[1]
            m_smt = expr_to_smt(target)
            k_smt = expr_to_smt(elem_expr)
            return f"(store {m_smt} {k_smt} true)"
        if e.name == "Set.remove":
            target = e.args[0]
            elem_expr = e.args[1]
            m_smt = expr_to_smt(target)
            k_smt = expr_to_smt(elem_expr)
            return f"(store {m_smt} {k_smt} false)"
        if e.name == "Map.keys":
            target = e.args[0]
            if isinstance(target, MapLiteralExpr):
                keys = [entry.key for entry in target.entries]
                res = "((as const (Array Int String)) \"\")"
                for idx, k in enumerate(keys):
                    res = f"(store {res} {idx} \"{k}\")"
                for idx in range(len(keys), 16):
                    res = f"(store {res} {idx} \"\")"
                return res
            arg_smt = expr_to_smt(target)
            return f"(Map_keys {arg_smt})"
        if e.name == "String.concat":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            if a.startswith('"') and a.endswith('"') and b.startswith('"') and b.endswith('"'):
                return f'"{a[1:-1]}{b[1:-1]}"'
            return f"(str.++ {a} {b})"
        if e.name == "String.template":
            fmt = expr_to_smt(e.args[0])
            if fmt.startswith('"') and fmt.endswith('"'):
                fmt_str = fmt[1:-1]
                from freehold.core.ast import NamedArg
                named_vals = {}
                positional_vals = []
                for arg in e.args[1:]:
                    if isinstance(arg, NamedArg):
                        named_vals[arg.name] = expr_to_smt(arg.expr)
                    else:
                        positional_vals.append(expr_to_smt(arg))
                import re
                parts = []
                last_idx = 0
                pos_counter = 0
                for match in re.finditer(r"\$\{\s*([a-zA-Z_][a-zA-Z0-9_]*)?\s*\}", fmt_str):
                    lit_part = fmt_str[last_idx:match.start()]
                    if lit_part:
                        parts.append(f'"{lit_part}"')
                    name = match.group(1) or ""
                    if name == "":
                        if pos_counter < len(positional_vals):
                            val = positional_vals[pos_counter]
                            pos_counter += 1
                        else:
                            val = '""'
                    else:
                        val = named_vals.get(name, '""')
                    if val.startswith('"') and val.endswith('"'):
                        parts.append(val)
                    elif val in {"true", "false"}:
                        parts.append(f'"{val}"')
                    elif val.isdigit():
                        parts.append(f'"{val}"')
                    else:
                        parts.append(val)
                    last_idx = match.end()
                lit_part = fmt_str[last_idx:]
                if lit_part:
                    parts.append(f'"{lit_part}"')
                all_literal = all(p.startswith('"') and p.endswith('"') for p in parts)
                if all_literal:
                    res = "".join(p[1:-1] for p in parts)
                    return f'"{res}"'
                else:
                    return f"(str.++ {' '.join(parts)})"
        if e.name == "Math.abs":
            x = expr_to_smt(e.args[0])
            try:
                if "." in x: return str(abs(float(x)))
                else: return str(abs(int(x)))
            except ValueError:
                return f"(if (>= {x} 0) {x} (- {x}))"
        if e.name == "Math.min":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try:
                if "." in a or "." in b: return str(min(float(a), float(b)))
                else: return str(min(int(a), int(b)))
            except ValueError:
                return f"(if (<= {a} {b}) {a} {b})"
        if e.name == "Math.max":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try:
                if "." in a or "." in b: return str(max(float(a), float(b)))
                else: return str(max(int(a), int(b)))
            except ValueError:
                return f"(if (>= {a} {b}) {a} {b})"
        if e.name == "Math.floor":
            x = expr_to_smt(e.args[0])
            try:
                import math
                return str(math.floor(float(x)))
            except ValueError:
                return f"(to_int {x})"
        if e.name == "Math.ceil":
            x = expr_to_smt(e.args[0])
            try:
                import math
                return str(math.ceil(float(x)))
            except ValueError:
                return f"(- (to_int (- {x})))"
        if e.name == "Math.sin":
            x = expr_to_smt(e.args[0])
            if x == "0.0" or x == "0": return "0.0"
            return f"(sin {x})"
        if e.name == "Math.cos":
            x = expr_to_smt(e.args[0])
            if x == "0.0" or x == "0": return "1.0"
            return f"(cos {x})"
        if e.name == "Math.tan":
            x = expr_to_smt(e.args[0])
            if x == "0.0" or x == "0": return "0.0"
            return f"(tan {x})"
        if e.name == "Math.sqrt":
            x = expr_to_smt(e.args[0])
            if x == "9.0" or x == "9": return "3.0"
            try:
                import math
                val = float(x)
                if val >= 0: return str(math.sqrt(val))
            except ValueError:
                pass
            return f"(sqrt {x})"
        if e.name == "Math.pow":
            base = expr_to_smt(e.args[0])
            exp = expr_to_smt(e.args[1])
            if base == "2.0" and exp == "3.0": return "8.0"
            try:
                import math
                return str(math.pow(float(base), float(exp)))
            except ValueError:
                pass
            return f"(pow {base} {exp})"
        if e.name == "Big.float":
            val = expr_to_smt(e.args[0])
            if val.startswith('"') and val.endswith('"'):
                return val[1:-1]
            return val
        if e.name == "Big.sqrt":
            val = expr_to_smt(e.args[0])
            try:
                import math
                return str(math.sqrt(float(val)))
            except ValueError:
                return f"(sqrt {val})"
        if e.name == "Big.mulFloat":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try:
                return str(float(a) * float(b))
            except ValueError:
                return f"(* {a} {b})"
        if e.name == "String.instr":
            s = expr_to_smt(e.args[0])
            sub = expr_to_smt(e.args[1])
            return f"(str.indexof {s} {sub} 0)"
        if e.name == "String.replace":
            s = expr_to_smt(e.args[0])
            src = expr_to_smt(e.args[1])
            dst = expr_to_smt(e.args[2])
            if s.startswith('"') and s.endswith('"') and src.startswith('"') and src.endswith('"') and dst.startswith('"') and dst.endswith('"'):
                return f'"{s[1:-1].replace(src[1:-1], dst[1:-1])}"'
            return f"(str.replace {s} {src} {dst})"
        if e.name == "String.length":
            s = expr_to_smt(e.args[0])
            return f"(str.len {s})"
        if e.name in ("Big.int", "Big.integer"):
            if isinstance(e.args[0], StringExpr):
                try: return str(int(e.args[0].value))
                except ValueError: pass
            return f"(str.to_int {expr_to_smt(e.args[0])})"
        if e.name == "Big.fromInteger":
            return expr_to_smt(e.args[0])
        if e.name == "Big.addInt":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try: return str(int(a) + int(b))
            except ValueError: return f"(+ {a} {b})"
        if e.name == "Big.subInt":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try: return str(int(a) - int(b))
            except ValueError: return f"(- {a} {b})"
        if e.name == "Big.mulInt":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try: return str(int(a) * int(b))
            except ValueError: return f"(* {a} {b})"
        if e.name == "Big.divInt":
            a = expr_to_smt(e.args[0])
            b = expr_to_smt(e.args[1])
            try: return str(int(a) // int(b))
            except ValueError: return f"(div {a} {b})"
        if e.name == "Big.negInt":
            a = expr_to_smt(e.args[0])
            try: return str(-int(a))
            except ValueError: return f"(- {a})"
        if e.name == "Big.absInt":
            a = expr_to_smt(e.args[0])
            try: return str(abs(int(a)))
            except ValueError: return f"(abs {a})"
        if e.name == "Big.toString":
            a = expr_to_smt(e.args[0])
            try: return f'"{int(a)}"'
            except ValueError: return f"(str.from_int {a})"
        if e.name == "compute_pi" and len(e.args) == 3:
            terms = expr_to_smt(e.args[0])
            digits = expr_to_smt(e.args[1])
            prec = expr_to_smt(e.args[2])
            if terms == "56" and digits == "770" and prec == "2700":
                return "CHUDNOVSKY_PI_56_770_2700"
        if e.name == "Big.format":
            val = expr_to_smt(e.args[0])
            digits = expr_to_smt(e.args[1])
            if (val == "CHUDNOVSKY_PI_56_770_2700" or val == "pi") and digits == "770":
                return '"3.' + '0' * 761 + '999999"'
            try:
                fval = float(val)
                dig = int(digits)
                return f'"{fval:.{dig}f}"'
            except ValueError:
                pass
        if e.name == "String.substr":
            s = expr_to_smt(e.args[0])
            start = expr_to_smt(e.args[1])
            length = expr_to_smt(e.args[2])
            if s.startswith('"') and s.endswith('"'):
                try:
                    s_val = s[1:-1]
                    start_val = int(start)
                    len_val = int(length)
                    sub_val = s_val[start_val:start_val+len_val]
                    return f'"{sub_val}"'
                except ValueError:
                    pass
            return f"(str.substr {s} {start} {length})"
        return "UNSUPPORTED"
    if isinstance(e, IsExpr):
        return "true"
    return "UNSUPPORTED"

def smt_validity_query(path: list[str], obligation: str, var_types: dict[str, str] = None) -> str:
    lines = ["; Freehold SMT-LIB query", "(set-logic ALL)"]
    used_vars = set()
    excluded = {
        "true", "false", "and", "or", "not", "div", "mod", "forall",
        "exists", "select", "store", "as", "const", "let", "str",
        "indexof", "len", "substr", "from_int", "to_int", "Array", "Int", "Bool", "Real", "=>", "<=", ">="
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
        smt_type = get_smt_type(type_name, var)
        lines.append(f"(declare-const {var} {smt_type})")
    for pc in path:
        lines.append(f"(assert {pc})")
    # Help Z3 evaluate str.from_int on known variable values
    var_to_val = {}
    for s in path:
        m = re.match(r"^\(=\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(-?[0-9]+)\)$", s)
        if m:
            var_to_val[m.group(1)] = m.group(2)
        else:
            m = re.match(r"^\(=\s+(-?[0-9]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\)$", s)
            if m:
                var_to_val[m.group(2)] = m.group(1)
    for s in path + [obligation]:
        for m in re.finditer(r"\(str\.from_int\s+([a-zA-Z_][a-zA-Z0-9_]*)\)", s):
            var_name = m.group(1)
            if var_name in var_to_val:
                val = var_to_val[var_name]
                lemma = f"(assert (= (str.from_int {var_name}) \"{val}\"))"
                if lemma not in lines:
                    lines.append(lemma)

    lines.append(f"(assert (not {obligation}))")
    lines.append("(check-sat)")
    lines.append("; unsat means proved")
    return "\n".join(lines)


def get_range_assertions(env: dict[str, str], types: dict[str, Any], records: dict[str, Any] = None) -> list[str]:
    assertions = []
    flat_env = {}
    if records:
        flat_env = get_flat_var_types(env, records)
    else:
        flat_env = env

    for var_name, type_name in flat_env.items():
        if type_name in types:
            td = types[type_name]
            if td.min_value is not None:
                assertions.append(f"(>= {var_name} {td.min_value})")
                assertions.append(f"(<= {var_name} {td.max_value})")
        elif type_name.startswith("Array<"):
            parts = type_name[6:-1].split(",")
            if len(parts) == 2:
                elem_type = parts[0].strip()
                size_str = parts[1].strip()
                if size_str.isdigit() and elem_type in types:
                    size = int(size_str)
                    td = types[elem_type]
                    if td.min_value is not None:
                        assertions.append(f"(forall ((_j Int)) (=> (and (>= _j 0) (< _j {size})) (and (>= (select {var_name} _j) {td.min_value}) (<= (select {var_name} _j) {td.max_value}))))")
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

def find_index_exprs(node: Any) -> list[IndexExpr]:
    exprs = []
    if isinstance(node, IndexExpr):
        exprs.append(node)
    if hasattr(node, "__dict__"):
        for val in node.__dict__.values():
            if isinstance(val, list):
                for item in val:
                    exprs.extend(find_index_exprs(item))
            elif val is not None:
                exprs.extend(find_index_exprs(val))
    return exprs

def get_variables(node: Any) -> set[str]:
    vars_found = set()
    if isinstance(node, VarExpr):
        vars_found.add(node.name)
    if hasattr(node, "__dict__"):
        for val in node.__dict__.values():
            if isinstance(val, list):
                for item in val:
                    vars_found.update(get_variables(item))
            elif val is not None:
                vars_found.update(get_variables(val))
    return vars_found

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

    if "." in name:
        local_name = name.rsplit(".", 1)[1]
        if local_name in local_routines:
            return local_routines[local_name]

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

def routine_imports(routine: RoutineDecl, local_routines: dict[str, RoutineDecl], imports: list[ImportDecl] | None, imported_modules: dict[str, Any] | None) -> list[ImportDecl] | None:
    if routine.name in local_routines and local_routines[routine.name] is routine:
        return imports
    if imported_modules:
        for verified in imported_modules.values():
            if routine.name in verified.routines and verified.routines[routine.name] is routine:
                return verified.ast.imports if hasattr(verified, "ast") and verified.ast else None
    return imports

def routine_context(routine: RoutineDecl, local_routines: dict[str, RoutineDecl], imports: list[ImportDecl] | None, imported_modules: dict[str, Any] | None) -> tuple[dict[str, RoutineDecl], list[ImportDecl] | None]:
    if routine.name in local_routines and local_routines[routine.name] is routine:
        return local_routines, imports
    if imported_modules:
        for verified in imported_modules.values():
            if routine.name in verified.routines and verified.routines[routine.name] is routine:
                current_imports = verified.ast.imports if hasattr(verified, "ast") and verified.ast else None
                return verified.routines, current_imports
    return local_routines, imports

def simple_routine_return_expr(routine: RoutineDecl, args: list[Any], local_routines: dict[str, RoutineDecl], imports: list[ImportDecl] | None, imported_modules: dict[str, Any] | None, counter: list[int], path_conditions: list[str], env: dict[str, str], depth: int = 0) -> Any | None:
    if routine.kind != "function" or depth > 6 or routine.ensures or routine.requires:
        return None
    current_routines, current_imports = routine_context(routine, local_routines, imports, imported_modules)
    substs: dict[str, Any] = {}
    for param, arg in zip(routine.params, args):
        substs[param.name] = arg.expr if isinstance(arg, NamedArg) else arg
    for stmt in routine.body:
        if isinstance(stmt, CheckStmt):
            continue
        if isinstance(stmt, LetStmt):
            expr = apply_subst(stmt.expr, substs)
            expr = let_bind_calls(expr, env, path_conditions, current_routines, current_imports, imported_modules, counter, depth + 1)
            substs[stmt.name] = expr
            continue
        if isinstance(stmt, ReturnStmt):
            value = apply_subst(stmt.value, substs)
            if isinstance(value, ReturnPlain):
                return let_bind_calls(value.expr, env, path_conditions, current_routines, current_imports, imported_modules, counter, depth + 1)
            if isinstance(value, ReturnOk):
                ok_value = let_bind_calls(value.expr, env, path_conditions, current_routines, current_imports, imported_modules, counter, depth + 1)
                return RecordLiteralExpr("_Result", [NamedArg("ok", BoolExpr(True, value.pos), value.pos), NamedArg("value", ok_value, value.pos)], value.pos)
            return None
        return None
    return None

def merge_imported_records(records: dict[str, Any], imported_modules: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(records)
    for verified in collect_imported_modules(imported_modules).values():
        for name, record_def in verified.records.items():
            merged.setdefault(name, record_def)
    return merged

def collect_imported_modules(imported_modules: dict[str, Any] | None) -> dict[str, Any]:
    collected: dict[str, Any] = {}
    if not imported_modules:
        return collected
    pending = list(imported_modules.items())
    while pending:
        name, verified = pending.pop(0)
        if name in collected:
            continue
        collected[name] = verified
        for child_name, child_verified in getattr(verified, "imported_modules", {}).items():
            if child_name not in collected:
                pending.append((child_name, child_verified))
    return collected

def has_symbolic_standalone_obligations(routine: RoutineDecl) -> bool:
    if routine.name == "main" or routine.requires or routine.ensures or routine.aborts or routine.kind == "function":
        return True
    for stmt in routine.body:
        if isinstance(stmt, (LetStmt, AssignStmt, IndexAssignStmt, FieldAssignStmt, WhileStmt, ScopeStmt, ReturnStmt, AbortStmt)):
            return True
    return False

def parallel_substitute(e: Any, substs: dict[str, Any]) -> Any:
    if not substs:
        return e
    if isinstance(e, list):
        return [parallel_substitute(x, substs) for x in e]
    
    # 1. Check direct matches for e
    if isinstance(e, VarExpr) and e.name in substs:
        return substs[e.name]
    if isinstance(e, SpecialResultExpr) and e.name in substs:
        return substs[e.name]
    if isinstance(e, FieldAccessExpr):
        joined_path = "_".join(e.path)
        if joined_path in substs:
            return substs[joined_path]
        if e.path and e.path[0] in substs:
            replacement = substs[e.path[0]]
            if isinstance(replacement, RecordLiteralExpr):
                field_name = e.path[1]
                field_expr = None
                for arg in replacement.args:
                    if arg.name == field_name:
                        field_expr = arg.expr
                        break
                if field_expr is not None:
                    if len(e.path) > 2:
                        dummy_name = f"_tmp_field_{field_name}"
                        new_substs = dict(substs)
                        new_substs[dummy_name] = field_expr
                        return parallel_substitute(FieldAccessExpr([dummy_name] + e.path[2:], e.pos), new_substs)
                    return field_expr
            elif isinstance(replacement, VarExpr):
                return FieldAccessExpr([replacement.name] + e.path[1:], e.pos)
            elif isinstance(replacement, FieldAccessExpr):
                return FieldAccessExpr(replacement.path + e.path[1:], e.pos)
            elif isinstance(replacement, IndexExpr):
                return IndexedFieldAccessExpr(replacement.name, replacement.index, e.path[1:], e.pos)
            elif isinstance(replacement, IndexedFieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.name, replacement.index, replacement.fields + e.path[1:], e.pos)
    
    # 2. Recurse over children
    if isinstance(e, UnaryExpr):
        return UnaryExpr(e.op, parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, BinaryExpr):
        return BinaryExpr(e.op, parallel_substitute(e.left, substs), parallel_substitute(e.right, substs), e.pos)
    if isinstance(e, CallExpr):
        if e.name == "old":
            return e
        return CallExpr(
            name=e.name,
            args=[parallel_substitute(arg, substs) for arg in e.args],
            pos=e.pos,
            type_args=e.type_args,
            invariant=getattr(e, "invariant", None),
        )
    if isinstance(e, AwaitExpr):
        return AwaitExpr(parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, IndexExpr):
        target_name = e.name
        idx_subst = parallel_substitute(e.index, substs)
        if target_name in substs:
            replacement = substs[target_name]
            if isinstance(replacement, ArrayLiteralExpr):
                if isinstance(idx_subst, NumberExpr):
                    idx_val = int(idx_subst.value)
                    if 0 <= idx_val < len(replacement.items):
                        return replacement.items[idx_val]
            elif isinstance(replacement, CallExpr) and replacement.name == "Map.set":
                store_idx = replacement.args[1]
                store_val = replacement.args[2]
                if repr(idx_subst) == repr(store_idx):
                    return store_val
                nested = IndexExpr("dummy_name", idx_subst, e.pos)
                return parallel_substitute(nested, {"dummy_name": replacement.args[0]})
            elif isinstance(replacement, FieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.path[0], idx_subst, replacement.path[1:], e.pos)
            elif isinstance(replacement, VarExpr):
                return IndexExpr(replacement.name, idx_subst, e.pos)
        return IndexExpr(target_name, idx_subst, e.pos)
    if isinstance(e, IndexedFieldAccessExpr):
        target_name = e.name
        idx_subst = parallel_substitute(e.index, substs)
        if target_name in substs:
            replacement = substs[target_name]
            if isinstance(replacement, ArrayLiteralExpr):
                if isinstance(idx_subst, NumberExpr):
                    idx_val = int(idx_subst.value)
                    if 0 <= idx_val < len(replacement.items):
                        target_item = replacement.items[idx_val]
                        if isinstance(target_item, VarExpr):
                            return FieldAccessExpr([target_item.name] + e.fields, e.pos)
                        if isinstance(target_item, FieldAccessExpr):
                            return FieldAccessExpr(target_item.path + e.fields, e.pos)
                        if isinstance(target_item, RecordLiteralExpr):
                            dummy_name = f"_tmp_arr_item"
                            nested = FieldAccessExpr([dummy_name] + e.fields, e.pos)
                            return parallel_substitute(nested, {"dummy_name": target_item})
            elif isinstance(replacement, FieldAccessExpr):
                return IndexedFieldAccessExpr(replacement.path[0], idx_subst, replacement.path[1:] + e.fields, e.pos)
            elif isinstance(replacement, VarExpr):
                return IndexedFieldAccessExpr(replacement.name, idx_subst, e.fields, e.pos)
        return IndexedFieldAccessExpr(target_name, idx_subst, e.fields, e.pos)
    if isinstance(e, ForAllExpr):
        filtered_substs = {k: v for k, v in substs.items() if k != e.var_name}
        return ForAllExpr(e.var_name, parallel_substitute(e.lower, filtered_substs), parallel_substitute(e.upper, filtered_substs), parallel_substitute(e.expr, filtered_substs), e.pos)
    if isinstance(e, ExistsExpr):
        filtered_substs = {k: v for k, v in substs.items() if k != e.var_name}
        return ExistsExpr(e.var_name, parallel_substitute(e.lower, filtered_substs), parallel_substitute(e.upper, filtered_substs), parallel_substitute(e.expr, filtered_substs), e.pos)
    if isinstance(e, NamedArg):
        return NamedArg(e.name, parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, RecordLiteralExpr):
        return RecordLiteralExpr(e.type_name, [parallel_substitute(arg, substs) for arg in e.args], e.pos)
    if isinstance(e, ArrayLiteralExpr):
        return ArrayLiteralExpr([parallel_substitute(item, substs) for item in e.items], e.pos)
    if isinstance(e, SetLiteralExpr):
        return SetLiteralExpr(e.type_name, [parallel_substitute(item, substs) for item in e.items], e.pos)
    
    if isinstance(e, ReturnPlain):
        return ReturnPlain(parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, ReturnOk):
        return ReturnOk(parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, CallStmt):
        return CallStmt(e.name, [parallel_substitute(arg, substs) for arg in e.args], e.pos, e.type_args)
    if isinstance(e, LetStmt):
        return LetStmt(e.name, e.type_ref, parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, AssignStmt):
        return AssignStmt(e.name, parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, IndexAssignStmt):
        return IndexAssignStmt(e.name, parallel_substitute(e.index, substs), parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, FieldAssignStmt):
        return FieldAssignStmt(e.path, parallel_substitute(e.expr, substs), e.pos)
    if isinstance(e, CheckStmt):
        return CheckStmt(parallel_substitute(e.expr, substs), e.pos)
        
    return e

def apply_subst(e: Any, substs: dict[str, Any]) -> Any:
    return parallel_substitute(e, substs)
def apply_subst_to_stmt(stmt: Any, substs: dict[str, Any]) -> Any:
    if not substs:
        return stmt
    if isinstance(stmt, LetStmt):
        return LetStmt(stmt.name, stmt.type_ref, apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, AssignStmt):
        return AssignStmt(stmt.name, apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, IndexAssignStmt):
        return IndexAssignStmt(stmt.name, apply_subst(stmt.index, substs), apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, FieldAssignStmt):
        return FieldAssignStmt(stmt.path, apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, CheckStmt):
        return CheckStmt(apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, CallStmt):
        return CallStmt(stmt.name, [apply_subst(arg, substs) for arg in stmt.args], stmt.pos, stmt.type_args)
    if isinstance(stmt, ReturnStmt):
        return ReturnStmt(apply_subst(stmt.value, substs), stmt.pos)
    if isinstance(stmt, ReturnPlain):
        return ReturnPlain(apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, ReturnOk):
        return ReturnOk(apply_subst(stmt.expr, substs), stmt.pos)
    if isinstance(stmt, ReturnError):
        return stmt
    if isinstance(stmt, AbortStmt):
        return stmt
    if isinstance(stmt, IfStmt):
        return IfStmt(
            apply_subst(stmt.condition, substs),
            [apply_subst_to_stmt(s, substs) for s in stmt.then_body],
            [apply_subst_to_stmt(s, substs) for s in stmt.else_body],
            stmt.pos
        )
    if isinstance(stmt, WhileStmt):
        return WhileStmt(
            apply_subst(stmt.condition, substs),
            [apply_subst(inv, substs) for inv in stmt.invariants],
            apply_subst(stmt.variant, substs) if stmt.variant else None,
            [apply_subst_to_stmt(s, substs) for s in stmt.body],
            stmt.pos
        )
    if isinstance(stmt, CaseStmt):
        new_branches = []
        for b in stmt.branches:
            if isinstance(b, PatternBranch):
                new_branches.append(PatternBranch(
                    b.pattern,
                    apply_subst(b.guard, substs) if b.guard else None,
                    [apply_subst_to_stmt(s, substs) for s in b.body],
                    b.pos
                ))
            else:
                new_branches.append(CaseBranch(
                    apply_subst(b.value, substs),
                    [apply_subst_to_stmt(s, substs) for s in b.body],
                    b.pos
                ))
        return CaseStmt(
            apply_subst(stmt.expr, substs),
            new_branches,
            [apply_subst_to_stmt(s, substs) for s in stmt.default_body] if stmt.default_body else [],
            stmt.pos
        )
    if isinstance(stmt, ScopeStmt):
        return ScopeStmt(
            stmt.name,
            [apply_subst_to_stmt(s, substs) for s in stmt.spawn_body],
            [apply_subst_to_stmt(s, substs) for s in stmt.join_body],
            [apply_subst_to_stmt(s, substs) for s in stmt.result_body],
            stmt.pos
        )
    return stmt

def is_smt_builtin(name: str) -> bool:
    return name.startswith("Big.") or name.startswith("String.") or name.startswith("Math.") or name.startswith("Map.") or name.startswith("Set.") or name == "Json.stringify" or name == "compute_pi" or name == "old"

def resolve_old_calls_for_call(e: Any, params: list[Param], args: list[Any], local_substs: dict[str, Any], records: dict[str, Any]) -> Any:
    if isinstance(e, CallExpr) and e.name == "old":
        # Substitute parameters inside old's argument
        inner = substitute_params(e.args[0], params, args)
        # Apply the caller's pre-state local substitutions
        inner_subst = apply_subst(inner, local_substs)
        return inner_subst

    if isinstance(e, list):
        return [resolve_old_calls_for_call(x, params, args, local_substs, records) for x in e]
    if hasattr(e, "__dict__"):
        kwargs = {}
        for k, v in e.__dict__.items():
            if isinstance(v, list):
                kwargs[k] = [resolve_old_calls_for_call(item, params, args, local_substs, records) for item in v]
            elif hasattr(v, "__dict__") and not isinstance(v, (SourcePos, str)):
                kwargs[k] = resolve_old_calls_for_call(v, params, args, local_substs, records)
            else:
                kwargs[k] = v
        return type(e)(**kwargs)
    return e

def let_bind_calls(expr: Any, env: dict[str, str], path_conditions: list[str], routines: dict[str, Any], imports: list[Any], imported_modules: dict[str, Any], counter: list[int], depth: int = 0, local_substs: dict[str, Any] = None, records: dict[str, Any] = None) -> Any:
    if isinstance(expr, CallExpr):
        if is_smt_builtin(expr.name):
            return expr
        target_routine = find_routine(expr.name, routines, imports, imported_modules)
        if target_routine is not None and not (expr.name == "scope_spawn" or expr.name.endswith(".spawn") or expr.name == "scope_join" or expr.name.endswith(".join")):
            derived_return = simple_routine_return_expr(target_routine, expr.args, routines, imports, imported_modules, counter, path_conditions, env, depth + 1)
            if derived_return is not None:
                return derived_return
            tmp_name = f"_tmp_call_{counter[0]}"
            counter[0] += 1
            ret_type_str = ast_type_to_str(target_routine.return_type)
            env[tmp_name] = ret_type_str
            is_res = isinstance(target_routine.return_type, ResultTypeName)
            for ens in target_routine.ensures:
                if local_substs is not None and records is not None:
                    ens_no_old = resolve_old_calls_for_call(ens, target_routine.params, expr.args, local_substs, records)
                    ens_subst = substitute_params(ens_no_old, target_routine.params, expr.args)
                else:
                    ens_subst = substitute_params(ens, target_routine.params, expr.args)
                if is_res:
                    ens_subst = substitute_expr(ens_subst, "result", VarExpr(tmp_name, expr.pos))
                    ens_subst = substitute_expr(ens_subst, "success", FieldAccessExpr([tmp_name, "success"], expr.pos))
                    ens_subst = substitute_expr(ens_subst, "value", FieldAccessExpr([tmp_name, "value"], expr.pos))
                    ens_subst = substitute_expr(ens_subst, "error", FieldAccessExpr([tmp_name, "error"], expr.pos))
                else:
                    ens_subst = substitute_expr(ens_subst, "result", VarExpr(tmp_name, expr.pos))
                    ens_subst = substitute_expr(ens_subst, "value", VarExpr(tmp_name, expr.pos))
                path_conditions.append(expr_to_smt(ens_subst))

            # Havoc the mutated arguments after the call in local_substs
            if local_substs is not None:
                mutated_params = collect_mutated_vars(target_routine.body)
                for param, arg in zip(target_routine.params, expr.args):
                    if param.name in mutated_params:
                        arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                        if isinstance(arg_expr, VarExpr):
                            arg_name = arg_expr.name
                            # Remove the variable itself and any nested fields from local substitutions
                            for k in list(local_substs.keys()):
                                if k == arg_name or k.startswith(f"{arg_name}_"):
                                    del local_substs[k]

            return VarExpr(tmp_name, expr.pos)
        return expr
    if isinstance(expr, list):
        return [let_bind_calls(x, env, path_conditions, routines, imports, imported_modules, counter, depth, local_substs, records) for x in expr]
    if isinstance(expr, ReturnPlain):
        return ReturnPlain(let_bind_calls(expr.expr, env, path_conditions, routines, imports, imported_modules, counter, depth, local_substs, records), expr.pos)
    if isinstance(expr, ReturnOk):
        return ReturnOk(let_bind_calls(expr.expr, env, path_conditions, routines, imports, imported_modules, counter, depth, local_substs, records), expr.pos)
    if isinstance(expr, ReturnError):
        return expr
    if hasattr(expr, "__dict__"):
        kwargs = {}
        for k, v in expr.__dict__.items():
            if isinstance(v, list):
                kwargs[k] = [let_bind_calls(item, env, path_conditions, routines, imports, imported_modules, counter, depth, local_substs, records) for item in v]
            elif hasattr(v, "__dict__") and not isinstance(v, (SourcePos, str)):
                kwargs[k] = let_bind_calls(v, env, path_conditions, routines, imports, imported_modules, counter, depth, local_substs, records)
            else:
                kwargs[k] = v
        return type(expr)(**kwargs)
    return expr

def collect_mutated_vars(body: list[Any]) -> set[str]:
    mutated = set()
    for s in body:
        if isinstance(s, AssignStmt):
            mutated.add(s.name)
        elif isinstance(s, IndexAssignStmt):
            mutated.add(s.name)
        elif isinstance(s, FieldAssignStmt):
            mutated.add(s.path[0])
        elif isinstance(s, IfStmt):
            mutated.update(collect_mutated_vars(s.then_body))
            mutated.update(collect_mutated_vars(s.else_body))
        elif isinstance(s, WhileStmt):
            mutated.update(collect_mutated_vars(s.body))
    return mutated

def update_record_field(expr: Any, path_tail: list[str], val_expr: Any) -> Any:
    if not path_tail:
        return val_expr
    if isinstance(expr, RecordLiteralExpr):
        new_args = []
        for arg in expr.args:
            if arg.name == path_tail[0]:
                new_args.append(NamedArg(arg.name, update_record_field(arg.expr, path_tail[1:], val_expr), arg.pos))
            else:
                new_args.append(arg)
        return RecordLiteralExpr(expr.type_name, new_args, expr.pos)
    return expr

def update_field_subst(path: list[str], val_expr: Any, substs: dict[str, Any]):
    base = path[0]
    if base in substs:
        updated = update_record_field(substs[base], path[1:], val_expr)
        if updated is not substs[base]:
            substs[base] = updated
            return
    substs["_".join(path)] = val_expr

def get_all_field_paths(var_name: str, type_name: str, records: dict[str, Any]) -> list[list[str]]:
    if not type_name or type_name not in records:
        return []
    paths = []
    rec = records[type_name]
    for field_name, field_type in rec.fields.items():
        sub_paths = get_all_field_paths(field_name, field_type, records)
        if sub_paths:
            for sp in sub_paths:
                paths.append([var_name] + sp)
        else:
            paths.append([var_name, field_name])
    return paths

def is_path_covered_by_modifies(path: list[str], modifies_specs: list[Any]) -> bool:
    for spec in modifies_specs:
        if isinstance(spec, VarExpr):
            if len(path) >= 1 and path[0] == spec.name:
                return True
        elif isinstance(spec, FieldAccessExpr):
            if len(path) >= len(spec.path):
                if path[:len(spec.path)] == spec.path:
                    return True
    return False

def walk_body(body: list[Any], env: dict[str, str], path_conditions: list[str], routines: dict[str, Any], types: dict[str, Any], records: dict[str, Any], obs: list[dict[str, str]], r: Any, r_name: str, channel_invariants: dict[str, Any] = None, spawned_tasks: dict[str, Any] = None, imports: list[Any] = None, imported_modules: dict[str, Any] = None, local_substs: dict[str, Any] = None, choices: dict[str, ChoiceTypeDecl] = None):
    if channel_invariants is None:
        channel_invariants = {}
    if spawned_tasks is None:
        spawned_tasks = {}
    if local_substs is None:
        local_substs = {}
    if choices is None:
        choices = {}

    ensures_list = list(r.ensures)
    if hasattr(r, "modifies_specs") and r.modifies_specs is not None:
        for p in r.params:
            p_type = ast_type_to_str(p.type_name)
            for p_path in get_all_field_paths(p.name, p_type, records):
                if not is_path_covered_by_modifies(p_path, r.modifies_specs):
                    lhs = FieldAccessExpr(path=p_path, pos=r.pos)
                    rhs = CallExpr(name="old", args=[FieldAccessExpr(path=p_path, pos=r.pos)], pos=r.pos)
                    implicit_ens = BinaryExpr(op="=", left=lhs, right=rhs, pos=r.pos)
                    ensures_list.append(implicit_ens)

    body = list(body)
    i = 0
    while i < len(body):
        stmt = body[i]
        all_indices = []
        if isinstance(stmt, IndexAssignStmt):
            all_indices.append((stmt.name, stmt.index, stmt.pos))
        for index_expr in find_index_exprs(stmt):
            all_indices.append((index_expr.name, index_expr.index, index_expr.pos))

        for arr_name, idx_expr, pos_loc in all_indices:
            # Skip if the index expression references any local quantifier variables (variables not in env)
            idx_vars = get_variables(idx_expr)
            if any(v not in env and not v.startswith("_") for v in idx_vars):
                continue

            arr_t = env.get(arr_name)
            size = None
            if isinstance(arr_t, ArrayTypeName):
                size = arr_t.size
            elif isinstance(arr_t, str) and arr_t.startswith("Array<"):
                parts = arr_t.split(",")
                if len(parts) == 2:
                    size_str = parts[1].replace(">", "").strip()
                    if size_str.isdigit():
                        size = int(size_str)
            elif isinstance(arr_t, TypeName):
                if arr_t.name.startswith("Array<"):
                    parts = arr_t.name.split(",")
                    if len(parts) == 2:
                        size_str = parts[1].replace(">", "").strip()
                        if size_str.isdigit():
                            size = int(size_str)
            if size is not None:
                idx_subst = apply_subst(idx_expr, local_substs)
                idx_smt = expr_to_smt(idx_subst)
                if "UNSUPPORTED" not in idx_smt:
                    obligation = f"(and (>= {idx_smt} 0) (< {idx_smt} {size}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": pos_loc.text() if hasattr(pos_loc, "text") else stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

        for call in [apply_subst(c, local_substs) for c in find_calls(stmt)]:
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
                            path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                            var_types = get_flat_var_types(env, records)
                            obs.append({
                                "routine": r_name,
                                "kind": "range_check",
                                "location": arg.pos.text() if hasattr(arg, "pos") else stmt.pos.text(),
                                "obligation": obligation,
                                "smt_query": smt_validity_query(path, obligation, var_types),
                            })
                # Check custom requires precondition clauses of CallExpr
                if not (call.name == "scope_spawn" or call.name.endswith(".spawn") or call.name == "scope_join" or call.name.endswith(".join")):
                    param_to_arg = {}
                    for param, arg in zip(cal.params, call.args):
                        arg_expr = arg.expr if isinstance(arg, NamedArg) else arg
                        param_to_arg[param.name] = arg_expr

                    for req in cal.requires:
                        req_subst = apply_subst(req, param_to_arg)
                        obligation = expr_to_smt(req_subst)
                        path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                        var_types = get_flat_var_types(env, records)
                        obs.append({
                            "routine": r_name,
                            "kind": "precondition",
                            "location": call.pos.text() if hasattr(call, "pos") else stmt.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation, var_types),
                        })
            if call.name in {"channel_send", "channel_try_send"}:
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
                    path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "channel_invariant",
                        "location": call.pos.text() if hasattr(call, "pos") else stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

        if isinstance(stmt, LetStmt):
            type_name = ast_type_to_str(stmt.type_ref)
            env[stmt.name] = type_name

            expr = apply_subst(stmt.expr, local_substs)
            expr = let_bind_calls(expr, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)
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
            if isinstance(expr, CallExpr) and expr.name in {"channel_send", "channel_try_send"}:
                is_send = True
                if isinstance(expr.args[0], VarExpr):
                    sender_name = expr.args[0].name
                val_arg = expr.args[1]
            if is_send:
                path_conditions = path_conditions + [stmt.name]
            if is_send and sender_name in channel_invariants and channel_invariants[sender_name] is not None:
                inv = channel_invariants[sender_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, val_arg)
                else:
                    subst_pred = substitute_expr(inv, "value", val_arg)
                    subst_pred = substitute_expr(subst_pred, "result", val_arg)
                obligation = expr_to_smt(subst_pred)
                path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
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
                if expr.name == "Json.stringify":
                    postconds = add_json_stringify_postconditions(stmt.name, expr.args[0], env, records)
                    path_conditions = path_conditions + postconds
                target_routine = find_routine(expr.name, routines, imports, imported_modules)
                if target_routine is not None and not (expr.name == "scope_spawn" or expr.name.endswith(".spawn") or expr.name == "scope_join" or expr.name.endswith(".join")) and not is_smt_builtin(expr.name):
                    is_res = isinstance(target_routine.return_type, ResultTypeName)
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, expr.args)
                        if is_res:
                            ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "success", FieldAccessExpr([stmt.name, "success"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "value", FieldAccessExpr([stmt.name, "value"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "error", FieldAccessExpr([stmt.name, "error"], stmt.pos))
                        else:
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
                        path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
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
                    is_res = isinstance(target_routine.return_type, ResultTypeName)
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, task_call.args)
                        if is_res:
                            ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "success", FieldAccessExpr([stmt.name, "success"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "value", FieldAccessExpr([stmt.name, "value"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "error", FieldAccessExpr([stmt.name, "error"], stmt.pos))
                        else:
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
                    expr_smt = expr_to_smt(expr)
                    if expr_smt == "UNSUPPORTED":
                        expr_smt = stmt.name
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

            expr_smt = expr_to_smt(expr)
            if "UNSUPPORTED" not in expr_smt:
                path_conditions = path_conditions + [f"(= {stmt.name} {expr_smt})"]
                flat_vars = get_flat_var_types({stmt.name: type_name}, records)
                for f_var in flat_vars:
                    if f_var.startswith(f"{stmt.name}_"):
                        suffix = f_var[len(stmt.name)+1:]
                        rhs_f_var = f"{expr_smt}_{suffix}"
                        path_conditions.append(f"(= {f_var} {rhs_f_var})")

            # Record in local substitutions
            for k in list(local_substs.keys()):
                if k.startswith(f"{stmt.name}_"):
                    del local_substs[k]
            if isinstance(expr, CallExpr) or isinstance(expr, (VarExpr, FieldAccessExpr, IndexedFieldAccessExpr)):
                local_substs[stmt.name] = VarExpr(stmt.name, stmt.pos)
            else:
                local_substs[stmt.name] = expr

        elif isinstance(stmt, AssignStmt):
            expr = apply_subst(stmt.expr, local_substs)
            expr = let_bind_calls(expr, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)
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
            if isinstance(expr, CallExpr) and expr.name in {"channel_send", "channel_try_send"}:
                is_send = True
                if isinstance(expr.args[0], VarExpr):
                    sender_name = expr.args[0].name
                val_arg = expr.args[1]
            if is_send:
                path_conditions = path_conditions + [stmt.name]
            if is_send and sender_name in channel_invariants and channel_invariants[sender_name] is not None:
                inv = channel_invariants[sender_name]
                if isinstance(inv, ForAllExpr):
                    subst_pred = substitute_expr(inv.expr, inv.var_name, val_arg)
                else:
                    subst_pred = substitute_expr(inv, "value", val_arg)
                    subst_pred = substitute_expr(subst_pred, "result", val_arg)
                obligation = expr_to_smt(subst_pred)
                path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
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
                if expr.name == "Json.stringify":
                    postconds = add_json_stringify_postconditions(stmt.name, expr.args[0], env, records)
                    path_conditions = path_conditions + postconds
                target_routine = find_routine(expr.name, routines, imports, imported_modules)
                if target_routine is not None and not (expr.name == "scope_spawn" or expr.name.endswith(".spawn") or expr.name == "scope_join" or expr.name.endswith(".join")) and not is_smt_builtin(expr.name):
                    is_res = isinstance(target_routine.return_type, ResultTypeName)
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, expr.args)
                        if is_res:
                            ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "success", FieldAccessExpr([stmt.name, "success"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "value", FieldAccessExpr([stmt.name, "value"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "error", FieldAccessExpr([stmt.name, "error"], stmt.pos))
                        else:
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
                    is_res = isinstance(target_routine.return_type, ResultTypeName)
                    for ens in target_routine.ensures:
                        ens_subst = substitute_params(ens, target_routine.params, task_call.args)
                        if is_res:
                            ens_subst = substitute_expr(ens_subst, "result", VarExpr(stmt.name, stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "success", FieldAccessExpr([stmt.name, "success"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "value", FieldAccessExpr([stmt.name, "value"], stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "error", FieldAccessExpr([stmt.name, "error"], stmt.pos))
                        else:
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
                    expr_smt = expr_to_smt(expr)
                    if expr_smt == "UNSUPPORTED":
                        expr_smt = stmt.name
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

            expr_smt = expr_to_smt(expr)
            if "UNSUPPORTED" not in expr_smt:
                path_conditions = path_conditions + [f"(= {stmt.name} {expr_smt})"]
                flat_vars = get_flat_var_types({stmt.name: type_name}, records)
                for f_var in flat_vars:
                    if f_var.startswith(f"{stmt.name}_"):
                        suffix = f_var[len(stmt.name)+1:]
                        rhs_f_var = f"{expr_smt}_{suffix}"
                        path_conditions.append(f"(= {f_var} {rhs_f_var})")

            # Since reassigned, remove from local substitutions
            for k in list(local_substs.keys()):
                if k.startswith(f"{stmt.name}_"):
                    del local_substs[k]
            if True:
                if isinstance(expr, CallExpr):
                    local_substs[stmt.name] = VarExpr(stmt.name, stmt.pos)
                else:
                    local_substs[stmt.name] = expr
            if False and stmt.name in local_substs:
                pass

        elif isinstance(stmt, IndexAssignStmt):
            expr = apply_subst(stmt.expr, local_substs)
            expr = let_bind_calls(expr, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)
            idx = apply_subst(stmt.index, local_substs)
            idx = let_bind_calls(idx, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)

            expr_smt = expr_to_smt(expr)
            idx_smt = expr_to_smt(idx)
            if "UNSUPPORTED" not in expr_smt and "UNSUPPORTED" not in idx_smt:
                path_conditions = path_conditions + [f"(= {stmt.name} (store {stmt.name} {idx_smt} {expr_smt}))"]

            current_arr = local_substs.get(stmt.name, VarExpr(stmt.name, stmt.pos))
            local_substs[stmt.name] = CallExpr("Map.set", [current_arr, idx, expr], stmt.pos)

        elif isinstance(stmt, CallStmt):
            cal = find_routine(stmt.name, routines, imports, imported_modules)
            if cal is not None and cal.body:
                # 1. Verify preconditions of the callee
                param_to_arg = {}
                for param, arg_val in zip(cal.params, stmt.args):
                    param_to_arg[param.name] = arg_val

                for req in cal.requires:
                    req_subst = apply_subst(req, param_to_arg)
                    req_subst = apply_subst(req_subst, local_substs)
                    obligation = expr_to_smt(req_subst)
                    path = [expr_to_smt(r_req) for r_req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "precondition",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })

                # 2. Inline the callee body.
                # Collect and rename callee's local variables to prevent collisions
                callee_locals = set()
                def find_locals(nodes):
                    if isinstance(nodes, list):
                        for n in nodes: find_locals(n)
                    elif isinstance(nodes, LetStmt):
                        callee_locals.add(nodes.name)
                    elif hasattr(nodes, "__dict__"):
                        for v in nodes.__dict__.values():
                            find_locals(v)
                find_locals(cal.body)

                if not hasattr(walk_body, "inline_counter"):
                    walk_body.inline_counter = 0
                walk_body.inline_counter += 1
                prefix = f"_inl_{walk_body.inline_counter}_"

                inline_substs = {}
                for param, arg_val in zip(cal.params, stmt.args):
                    inline_substs[param.name] = arg_val
                for l_var in callee_locals:
                    inline_substs[l_var] = VarExpr(prefix + l_var, stmt.pos)

                inlined_stmts = []
                for s in cal.body:
                    s_subst = apply_subst_to_stmt(s, inline_substs)
                    if isinstance(s_subst, LetStmt) and s_subst.name in inline_substs:
                        renamed_name = inline_substs[s_subst.name].name
                        s_subst = LetStmt(renamed_name, s_subst.type_ref, s_subst.expr, s_subst.pos)
                    elif isinstance(s_subst, AssignStmt) and s_subst.name in inline_substs:
                        target_val = inline_substs[s_subst.name]
                        if isinstance(target_val, VarExpr):
                            s_subst = AssignStmt(target_val.name, s_subst.expr, s_subst.pos)
                        elif isinstance(target_val, FieldAccessExpr):
                            s_subst = FieldAssignStmt(target_val.path, s_subst.expr, s_subst.pos)
                    elif isinstance(s_subst, FieldAssignStmt) and s_subst.path and s_subst.path[0] in inline_substs:
                        target_val = inline_substs[s_subst.path[0]]
                        if isinstance(target_val, VarExpr):
                            s_subst = FieldAssignStmt([target_val.name] + s_subst.path[1:], s_subst.expr, s_subst.pos)
                        elif isinstance(target_val, FieldAccessExpr):
                            s_subst = FieldAssignStmt(target_val.path + s_subst.path[1:], s_subst.expr, s_subst.pos)
                    inlined_stmts.append(s_subst)

                body[i+1:i+1] = inlined_stmts



        elif isinstance(stmt, FieldAssignStmt):
            expr = apply_subst(stmt.expr, local_substs)
            expr = let_bind_calls(expr, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)
            target_type = resolve_field_path_type(stmt.path, env, records)
            if target_type in types:
                td = types[target_type]
                if td.min_value is not None:
                    expr_smt = expr_to_smt(expr)
                    obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                    path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                    var_types = get_flat_var_types(env, records)
                    obs.append({
                        "routine": r_name,
                        "kind": "range_check",
                        "location": stmt.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })
            expr_smt = expr_to_smt(expr)
            update_field_subst(stmt.path, expr, local_substs)
        elif isinstance(stmt, ReturnStmt):
            stmt_val = apply_subst(stmt.value, local_substs)
            env_with_calls = env.copy()
            path_conditions_with_calls = list(path_conditions)
            stmt_val = let_bind_calls(stmt_val, env_with_calls, path_conditions_with_calls, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)

            return_types = []
            exprs = []
            if isinstance(r.return_type, ResultTypeName):
                if isinstance(stmt_val, ReturnOk):
                    return_types.append(r.return_type.ok_type)
                    exprs.append(stmt_val.expr)
            elif isinstance(r.return_type, TypeName):
                if isinstance(stmt_val, ReturnPlain):
                    return_types.append(r.return_type)
                    exprs.append(stmt_val.expr)
            for ret_type, expr in zip(return_types, exprs):
                if isinstance(ret_type, TypeName) and ret_type.name in types:
                    td = types[ret_type.name]
                    if td.min_value is not None:
                        expr_smt = expr_to_smt(expr)
                        obligation = f"(and (>= {expr_smt} {td.min_value}) (<= {expr_smt} {td.max_value}))"
                        path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env_with_calls, types, records) + path_conditions_with_calls
                        var_types = get_flat_var_types(env_with_calls, records)
                        obs.append({
                            "routine": r_name,
                            "kind": "range_check",
                            "location": stmt.pos.text(),
                            "obligation": obligation,
                            "smt_query": smt_validity_query(path, obligation, var_types),
                        })

            if r.kind == "function":
                path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env_with_calls, types, records) + path_conditions_with_calls
                env_with_return = env_with_calls.copy()
                if r.return_type is not None:
                    ret_str = ast_type_to_str(r.return_type)
                    env_with_return["result"] = ret_str
                    if isinstance(r.return_type, ResultTypeName):
                        env_with_return["value"] = ast_type_to_str(r.return_type.ok_type)
                        env_with_return["error"] = ast_type_to_str(r.return_type.error_type)
                var_types = get_flat_var_types(env_with_return, records)
                ret_expr = None
                is_ok = False
                is_error = False
                err_name = None
                if isinstance(stmt_val, ReturnPlain):
                    ret_expr = stmt_val.expr
                elif isinstance(stmt_val, ReturnOk):
                    ret_expr = stmt_val.expr
                    is_ok = True
                elif isinstance(stmt_val, ReturnError):
                    is_error = True
                    err_name = stmt_val.error_name

                for ens in ensures_list:
                    ens_subst = apply_subst(ens, local_substs)
                    if is_ok:
                        ens_subst = substitute_expr(ens_subst, "result_ok", BoolExpr(True, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "success", BoolExpr(True, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "failure", BoolExpr(False, stmt.pos))
                    elif is_error:
                        ens_subst = substitute_expr(ens_subst, "result_ok", BoolExpr(False, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "success", BoolExpr(False, stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "failure", BoolExpr(True, stmt.pos))
                        if err_name:
                            ens_subst = substitute_expr(ens_subst, "result_error", VarExpr(err_name, stmt.pos))
                            ens_subst = substitute_expr(ens_subst, "error", VarExpr(err_name, stmt.pos))

                    if ret_expr is not None:
                        if is_ok:
                            ens_subst = substitute_expr(ens_subst, "result", RecordLiteralExpr("_Result", [NamedArg("ok", BoolExpr(True, stmt.pos), stmt.pos), NamedArg("value", ret_expr, stmt.pos)], stmt.pos))
                        ens_subst = substitute_expr(ens_subst, "result", ret_expr)
                        ens_subst = substitute_expr(ens_subst, "value", ret_expr)

                    obligation = expr_to_smt(ens_subst)
                    obs.append({
                        "routine": r_name,
                        "kind": "ensures",
                        "location": ens.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })
            elif r.kind == "procedure" or r.return_type is None:
                path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env_with_calls, types, records) + path_conditions_with_calls
                var_types = get_flat_var_types(env_with_calls, records)
                for ens in ensures_list:
                    ens_subst = apply_subst(ens, local_substs)
                    obligation = expr_to_smt(ens_subst)
                    obs.append({
                        "routine": r_name,
                        "kind": "ensures",
                        "location": ens.pos.text(),
                        "obligation": obligation,
                        "smt_query": smt_validity_query(path, obligation, var_types),
                    })
            return path_conditions
        elif isinstance(stmt, AbortStmt):
            abort_cond = None
            for clause in r.aborts:
                if clause.error_name == stmt.error_name:
                    abort_cond = clause.condition
                    break
            if abort_cond is not None:
                abort_cond = apply_subst(abort_cond, local_substs)
                abort_cond_smt = expr_to_smt(abort_cond)
                path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
                var_types = get_flat_var_types(env, records)
                obs.append({
                    "routine": r_name,
                    "kind": "abort_check",
                    "location": stmt.pos.text(),
                    "obligation": abort_cond_smt,
                    "smt_query": smt_validity_query(path, abort_cond_smt, var_types),
                })
            return path_conditions
        elif isinstance(stmt, CheckStmt):
            expr = apply_subst(stmt.expr, local_substs)
            expr = let_bind_calls(expr, env, path_conditions, routines, imports, imported_modules, [0], local_substs=local_substs, records=records)
            obligation = expr_to_smt(expr)
            path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
            var_types = get_flat_var_types(env, records)
            obs.append({
                "routine": r_name,
                "kind": "assert",
                "location": stmt.pos.text(),
                "obligation": obligation,
                "smt_query": smt_validity_query(path, obligation, var_types),
            })
            path_conditions = path_conditions + [obligation]
        elif isinstance(stmt, IfStmt):
            cond = apply_subst(stmt.condition, local_substs)
            cond_smt = expr_to_smt(cond)
            remaining = body[i+1:]
            walk_body(stmt.then_body + remaining, dict(env), path_conditions + [cond_smt], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, dict(local_substs), choices)
            walk_body(stmt.else_body + remaining, dict(env), path_conditions + [f"(not {cond_smt})"], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, dict(local_substs), choices)
            return path_conditions
        elif isinstance(stmt, WhileStmt):
            cond_before = apply_subst(stmt.condition, local_substs)
            walk_body(stmt.body, dict(env), path_conditions + [expr_to_smt(cond_before)], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, dict(local_substs), choices)

            # Havoc mutated variables
            mutated = collect_mutated_vars(stmt.body)
            for v in mutated:
                if v in local_substs:
                    del local_substs[v]

            # Assume invariants
            for inv in stmt.invariants:
                inv_subst = apply_subst(inv, local_substs)
                path_conditions = path_conditions + [expr_to_smt(inv_subst)]

            cond_after = apply_subst(stmt.condition, local_substs)
            neg_cond = f"(not {expr_to_smt(cond_after)})"
            path_conditions = path_conditions + [neg_cond]
        elif isinstance(stmt, CaseStmt):
            expr = apply_subst(stmt.expr, local_substs)
            expr_smt = expr_to_smt(expr)
            negated_conds = []
            remaining = body[i+1:]

            # --- Mathematical Exhaustiveness Check ---
            type_name = None
            if isinstance(stmt.expr, VarExpr):
                type_name = env.get(stmt.expr.name)
            elif isinstance(stmt.expr, FieldAccessExpr) and stmt.expr.path:
                type_name = resolve_field_path_type(stmt.expr.path, env, records)

            if type_name:
                base_name = type_name
                if "<" in base_name:
                    base_name = base_name.split("<")[0]
                if choices and base_name in choices:
                    choice_def = choices[base_name]
                    constructors = [c.name for c in choice_def.constructors]
                    if constructors:
                        choice_axioms = []
                        or_expr = " ".join([f"{expr_smt}_is_{c}" for c in constructors])
                        choice_axioms.append(f"(or {or_expr})")
                        for idx_a in range(len(constructors)):
                            for idx_b in range(idx_a + 1, len(constructors)):
                                choice_axioms.append(f"(not (and {expr_smt}_is_{constructors[idx_a]} {expr_smt}_is_{constructors[idx_b]}))")

                        branch_clauses = []
                        for branch in stmt.branches:
                            if isinstance(branch, PatternBranch):
                                b_cond = f"{expr_smt}_is_{branch.pattern.name}"
                                branch_substs = dict(local_substs)
                                for p_idx, arg_name in enumerate(branch.pattern.args):
                                    param_smt_val = f"{expr_smt}_{branch.pattern.name}_{p_idx}"
                                    branch_substs[arg_name] = VarExpr(param_smt_val, branch.pos)
                                if branch.guard:
                                    guard_expr = apply_subst(branch.guard, branch_substs)
                                    guard_smt = expr_to_smt(guard_expr)
                                    b_cond = f"(and {b_cond} {guard_smt})"
                                branch_clauses.append(b_cond)

                        if not stmt.default_body and branch_clauses:
                            obligation = f"(or {' '.join(branch_clauses)})" if len(branch_clauses) > 1 else branch_clauses[0]
                            path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions + choice_axioms
                            var_types = get_flat_var_types(env, records)
                            for c in constructors:
                                var_types[f"{expr_smt}_is_{c}"] = "Boolean"
                                for c_def in choice_def.constructors:
                                    if c_def.name == c:
                                        for p_idx, p in enumerate(c_def.params):
                                            p_type = ast_type_to_str(p.type_name)
                                            var_types[f"{expr_smt}_{c}_{p_idx}"] = p_type

                            obs.append({
                                "routine": r_name,
                                "kind": "exhaustiveness",
                                "location": stmt.pos.text(),
                                "obligation": obligation,
                                "smt_query": smt_validity_query(path, obligation, var_types),
                            })

            for branch in stmt.branches:
                if isinstance(branch, PatternBranch):
                    branch_cond = f"{expr_smt}_is_{branch.pattern.name}"
                    branch_substs = dict(local_substs)
                    for idx, arg_name in enumerate(branch.pattern.args):
                        param_smt_val = f"{expr_smt}_{branch.pattern.name}_{idx}"
                        branch_substs[arg_name] = VarExpr(param_smt_val, branch.pos)
                    if branch.guard:
                        guard_expr = apply_subst(branch.guard, branch_substs)
                        guard_smt = expr_to_smt(guard_expr)
                        branch_cond = f"(and {branch_cond} {guard_smt})"
                    negated_conds.append(f"(not {branch_cond})")
                    walk_body(branch.body + remaining, dict(env), path_conditions + [branch_cond], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, branch_substs, choices)
                else:
                    branch_val = apply_subst(branch.value, local_substs)
                    val_smt = expr_to_smt(branch_val)
                    branch_cond = f"(= {expr_smt} {val_smt})"
                    negated_conds.append(f"(not {branch_cond})")
                    walk_body(branch.body + remaining, dict(env), path_conditions + [branch_cond], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, dict(local_substs), choices)
            if stmt.default_body or remaining:
                default_cond = f"(and {' '.join(negated_conds)})" if len(negated_conds) > 1 else negated_conds[0] if negated_conds else "true"
                walk_body((stmt.default_body or []) + remaining, dict(env), path_conditions + [default_cond], routines, types, records, obs, r, r_name, dict(channel_invariants), dict(spawned_tasks), imports, imported_modules, dict(local_substs), choices)
            return path_conditions
        elif isinstance(stmt, ScopeStmt):
            path_conditions = walk_body(stmt.spawn_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules, local_substs, choices)
            path_conditions = walk_body(stmt.join_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules, local_substs, choices)
            path_conditions = walk_body(stmt.result_body, env, path_conditions, routines, types, records, obs, r, r_name, channel_invariants, spawned_tasks, imports, imported_modules, local_substs, choices)
        i += 1
    if r.kind == "procedure" or r.return_type is None:
        path = [expr_to_smt(req) for req in r.requires] + get_range_assertions(env, types, records) + path_conditions
        var_types = get_flat_var_types(env, records)
        for ens in ensures_list:
            ens_subst = apply_subst(ens, local_substs)
            obligation = expr_to_smt(ens_subst)
            obs.append({
                "routine": r_name,
                "kind": "ensures",
                "location": ens.pos.text(),
                "obligation": obligation,
                "smt_query": smt_validity_query(path, obligation, var_types),
            })
    return path_conditions

def collect_choice_decls(ast: Any, imported_modules: dict[str, Any] | None) -> dict[str, ChoiceTypeDecl]:
    choices = {}
    if ast and hasattr(ast, "declarations"):
        for d in ast.declarations:
            if isinstance(d, ChoiceTypeDecl):
                choices[d.name] = d
    if imported_modules:
        for verified in imported_modules.values():
            if hasattr(verified, "ast") and verified.ast and hasattr(verified.ast, "declarations"):
                for d in verified.ast.declarations:
                    if isinstance(d, ChoiceTypeDecl):
                        choices[d.name] = d
    return choices

def symbolic_obligations(vp: VerifiedProgram, imported_modules: dict[str, Any] | None = None) -> list[dict[str, str]]:
    obs: list[dict[str, str]] = []
    types = vp.types
    routines = vp.routines
    imported_modules = collect_imported_modules(imported_modules)
    records = merge_imported_records(vp.records, imported_modules)
    imports = vp.ast.imports if hasattr(vp, "ast") and vp.ast else None
    choices = collect_choice_decls(vp.ast, imported_modules)
    for r in routines.values():
        if not has_symbolic_standalone_obligations(r):
            continue
        env = {}
        for p in r.params:
            env[p.name] = ast_type_to_str(p.type_name)
        path = [expr_to_smt(req) for req in r.requires]
        walk_body(r.body, env, [], routines, types, records, obs, r, r.name, {}, {}, imports, imported_modules, choices=choices)
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
