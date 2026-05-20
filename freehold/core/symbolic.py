from __future__ import annotations
from typing import Any
from freehold.core.ast import *
from freehold.core.verifier import VerifiedProgram

def expr_to_smt(e: Any) -> str:
    if isinstance(e, NumberExpr): return str(e.value)
    if isinstance(e, DoubleExpr): return str(e.value)
    if isinstance(e, BoolExpr): return "true" if e.value else "false"
    if isinstance(e, VarExpr): return e.name
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
    lines = ["; Freehold SMT-LIB smoke query", "(set-logic ALL)"]
    for pc in path:
        lines.append(f"(assert {pc})")
    lines.append(f"(assert (not {obligation}))")
    lines.append("(check-sat)")
    lines.append("; unsat means proved")
    return "\n".join(lines)

def symbolic_obligations(vp: VerifiedProgram) -> list[dict[str, str]]:
    obs: list[dict[str, str]] = []
    for r in vp.routines.values():
        if r.kind != "function":
            continue
        path = [expr_to_smt(req) for req in r.requires]
        # Current smoke: returns + ensures only, enough for regression of SMT text generation.
        for ens in r.ensures:
            obligation = expr_to_smt(ens)
            obs.append({
                "routine": r.name,
                "kind": "ensures",
                "location": ens.pos.text(),
                "obligation": obligation,
                "smt_query": smt_validity_query(path, obligation),
            })
    return obs
