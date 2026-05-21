from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_GO_ROOT = Path("artifacts/go-ast")
DEFAULT_DHPARSER_ROOT = Path("artifacts/dhparser-ast")
DEFAULT_OUT_ROOT = Path("artifacts/compare-ast-shape")


TOKEN_NODES = {":Text", ":RegExp"}
WRAPPER_NODES = {
    "expr",
    "logic_or",
    "logic_and",
    "equality",
    "comparison",
    "sum",
    "product",
    "unary",
    "postfix_expr",
    "primary",
    "return_type",
    "type_ref",
    "base_type",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare normalized Go and DHParser AST shape artifacts")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go AST artifact root")
    parser.add_argument("--dhparser", default=str(DEFAULT_DHPARSER_ROOT), help="DHParser AST artifact root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    go_root = Path(args.go)
    dhparser_root = Path(args.dhparser)
    out_root = Path(args.out)

    go_results = load_results(go_root)
    dhparser_results = load_results(dhparser_root)

    comparable_keys = sorted(
        key for key, go_result in go_results.items()
        if go_result.get("parse_ok") and dhparser_results.get(key, {}).get("parse_ok")
    )

    matches: list[str] = []
    mismatches: list[dict[str, Any]] = []

    for key in comparable_keys:
        go_shape = normalize_go_module(go_results[key]["ast"])
        dhparser_shape = normalize_dhparser_module(dhparser_results[key]["ast"])

        if go_shape == dhparser_shape:
            matches.append(key)
        else:
            mismatches.append({
                "case": key,
                "go_shape": go_shape,
                "dhparser_shape": dhparser_shape,
            })

    summary = {
        "total_parse_status_cases": len(set(go_results) | set(dhparser_results)),
        "comparable_parse_ok_cases": len(comparable_keys),
        "matching_shape": len(matches),
        "mismatching_shape": len(mismatches),
        "matches": matches,
        "mismatches": mismatches,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_summary.json", summary)
    write_json(out_root / "_all.json", [
        {"case": key, "status": "mismatch" if any(item["case"] == key for item in mismatches) else "match"}
        for key in comparable_keys
    ])
    write_text_report(out_root / "_mismatches.txt", summary)

    print_summary(summary)
    return 1 if mismatches else 0


def load_results(root: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in root.glob("*/*/*.json"):
        with path.open("r", encoding="utf-8") as handle:
            results[path.relative_to(root).as_posix()] = json.load(handle)
    return results


def normalize_go_module(module: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "Module",
        "name": module.get("name", ""),
        "declarations": [normalize_go_decl(decl) for decl in module.get("declarations") or []],
        "end_name": module.get("end_name", ""),
    }


def normalize_go_decl(decl: dict[str, Any]) -> dict[str, Any]:
    kind = decl.get("kind")
    if kind == "ImportDecl":
        return {"kind": kind, "module": decl.get("module", ""), "exposing": decl.get("exposing") or []}
    if kind == "TypeDecl":
        item: dict[str, Any] = {"kind": kind, "name": decl.get("name", ""), "base": decl.get("base", "")}
        if decl.get("range"):
            item["range"] = decl["range"]
        if decl.get("fields"):
            item["fields"] = [normalize_go_param(param) for param in decl.get("fields") or []]
        return item
    if kind == "ErrorDecl":
        return {"kind": kind, "name": decl.get("name", "")}
    if kind in {"FunctionDecl", "ProcedureDecl"}:
        item = {
            "kind": kind,
            "name": decl.get("name", ""),
            "params": [normalize_go_param(param) for param in decl.get("params") or []],
            "requires": [normalize_go_expr(expr) for expr in decl.get("requires") or []],
            "ensures": [normalize_go_expr(expr) for expr in decl.get("ensures") or []],
            "body": [normalize_go_stmt(stmt) for stmt in decl.get("body") or []],
            "end_name": decl.get("end_name", ""),
        }
        if kind == "FunctionDecl":
            item["return_type"] = compact_type(decl.get("return_type", ""))
        return item
    return {"kind": kind or "UnknownDecl"}


def normalize_go_param(param: dict[str, Any]) -> dict[str, str]:
    return {"name": param.get("name", ""), "type": compact_type(param.get("type", ""))}


def normalize_go_stmt(stmt: dict[str, Any]) -> dict[str, Any]:
    kind = stmt.get("kind")
    if kind == "LetStmt":
        return {"kind": kind, "name": stmt.get("name", ""), "type": compact_type(stmt.get("type", "")), "value": normalize_go_expr(stmt.get("value"))}
    if kind == "ReturnStmt":
        return {"kind": kind, "value": normalize_go_expr(stmt.get("value"))}
    if kind == "CheckStmt":
        return {"kind": kind, "condition": normalize_go_expr(stmt.get("condition"))}
    if kind == "AssignmentStmt":
        return {"kind": kind, "target": normalize_go_expr(stmt.get("target")), "value": normalize_go_expr(stmt.get("value"))}
    if kind == "CallStmt":
        return {"kind": kind, "call": normalize_go_expr(stmt.get("call"))}
    if kind == "IfStmt":
        return {
            "kind": kind,
            "condition": normalize_go_expr(stmt.get("condition")),
            "then_body": [normalize_go_stmt(child) for child in stmt.get("then_body") or []],
            "else_body": [normalize_go_stmt(child) for child in stmt.get("else_body") or []],
        }
    if kind == "WhileStmt":
        item = {
            "kind": kind,
            "condition": normalize_go_expr(stmt.get("condition")),
            "invariants": [normalize_go_expr(expr) for expr in stmt.get("invariants") or []],
            "body": [normalize_go_stmt(child) for child in stmt.get("body") or []],
        }
        if stmt.get("variant") is not None:
            item["variant"] = normalize_go_expr(stmt.get("variant"))
        return item
    if kind == "CaseStmt":
        return {
            "kind": kind,
            "value": normalize_go_expr(stmt.get("value")),
            "when": [
                {"value": normalize_go_expr(branch.get("value")), "body": [normalize_go_stmt(child) for child in branch.get("body") or []]}
                for branch in stmt.get("when") or []
            ],
            "default": [normalize_go_stmt(child) for child in stmt.get("default") or []],
        }
    return {"kind": kind or "UnknownStmt"}


def normalize_go_expr(expr: Any) -> str:
    if not isinstance(expr, dict):
        return ""
    return canonical_expr_text(go_expr_text(expr))


def go_expr_text(expr: dict[str, Any], parent_prec: int = 0, side: str = "") -> str:
    kind = expr.get("kind")
    prec = go_expr_prec(expr)
    if kind == "IdentifierExpr":
        return expr.get("name", "")
    if kind == "NumberExpr":
        return expr.get("value", "")
    if kind == "StringExpr":
        return json.dumps(expr.get("value", ""))
    if kind == "BinaryExpr":
        op = expr.get("op", "")
        text = go_expr_text(expr.get("left", {}), prec, "left") + op + go_expr_text(expr.get("right", {}), prec, "right")
        if prec < parent_prec or (side == "right" and prec == parent_prec and op in {"-", "/", "=", "<", "<=", ">", ">="}):
            return "(" + text + ")"
        return text
    if kind == "UnaryExpr":
        text = expr.get("op", "") + go_expr_text(expr.get("value", {}), prec)
        return "(" + text + ")" if prec < parent_prec else text
    if kind == "FieldAccessExpr":
        return go_expr_text(expr.get("object", {}), prec) + "." + expr.get("field", "")
    if kind == "IndexExpr":
        return go_expr_text(expr.get("array", {}), prec) + "[" + go_expr_text(expr.get("index", {})) + "]"
    if kind == "ArrayLiteralExpr":
        return "[" + ",".join(go_expr_text(item) for item in expr.get("elements") or []) + "]"
    if kind == "CallExpr":
        return go_expr_text(expr.get("callee", {}), prec) + "(" + ",".join(go_expr_text(item) for item in expr.get("arguments") or []) + ")"
    if kind == "RecordLiteralExpr":
        fields = ",".join(field.get("name", "") + ":" + go_expr_text(field.get("value", {})) for field in expr.get("fields") or [])
        return expr.get("type", "") + "{" + fields + "}"
    if kind == "OkExpr":
        return "ok" + go_expr_text(expr.get("value", {}))
    if kind == "ErrorExpr":
        return "error" + expr.get("name", "")
    return kind or ""


def go_expr_prec(expr: dict[str, Any]) -> int:
    kind = expr.get("kind")
    if kind == "BinaryExpr":
        op = expr.get("op", "")
        if op == "or":
            return 1
        if op == "and":
            return 2
        if op in {"=", "<>", "<", "<=", ">", ">="}:
            return 3
        if op in {"+", "-"}:
            return 4
        if op in {"*", "/"}:
            return 5
        return 3
    if kind == "UnaryExpr":
        return 6
    if kind in {"FieldAccessExpr", "IndexExpr", "CallExpr"}:
        return 7
    return 8


def normalize_dhparser_module(root: dict[str, Any]) -> dict[str, Any]:
    module_decl = first_child(root, "module_decl")
    module_end = first_child(root, "module_end")
    declarations = []
    for child in children(root):
        if node_name(child) == "import_decl":
            declarations.append(child)
        elif node_name(child) == "declaration":
            declarations.append(first_named(child))

    return {
        "kind": "Module",
        "name": qualified_name_text(first_child(module_decl, "qualified_name")),
        "declarations": [normalize_dhparser_decl(decl) for decl in declarations if decl],
        "end_name": qualified_name_text(first_child(module_end, "qualified_name")),
    }


def normalize_dhparser_decl(node: dict[str, Any]) -> dict[str, Any]:
    name = node_name(node)
    if name == "import_decl":
        qnames = children(node, "qualified_name")
        exposing = first_child(node, "exposing_clause")
        return {
            "kind": "ImportDecl",
            "module": qualified_name_text(qnames[0]) if qnames else "",
            "exposing": [ident_text(item) for item in descendants(exposing, "IDENT")] if exposing else [],
        }
    if name == "type_decl":
        item: dict[str, Any] = {"kind": "TypeDecl", "name": nth_ident(node, 0), "base": type_text(first_child(node, "base_type"))}
        range_node = first_child(node, "range_decl")
        if range_node:
            nums = [text_of(child) for child in children(range_node) if node_name(child) in {"NUMBER_LITERAL", "INTEGER_LITERAL", "DOUBLE_LITERAL"}]
            if len(nums) >= 2:
                item["range"] = {"min": nums[0], "max": nums[1]}
        return item
    if name == "record_type_decl":
        return {
            "kind": "TypeDecl",
            "name": nth_ident(node, 0),
            "base": "record",
            "fields": [normalize_dhparser_param(field) for field in children(node, "record_field")],
        }
    if name == "error_decl":
        return {"kind": "ErrorDecl", "name": nth_ident(node, 0)}
    if name in {"function_decl", "procedure_decl"}:
        kind = "FunctionDecl" if name == "function_decl" else "ProcedureDecl"
        item = {
            "kind": kind,
            "name": nth_ident(node, 0),
            "params": [normalize_dhparser_param(param) for param in children(first_child(node, "param_list"), "param")],
            "requires": [canonical_expr_text(text_of(first_child(req, "expr"))) for req in children(first_child(node, "contract_block"), "requires_clause")],
            "ensures": [canonical_expr_text(text_of(first_child(req, "expr"))) for req in children(first_child(node, "contract_block"), "ensures_clause")],
            "body": [normalize_dhparser_stmt(stmt) for stmt in children(node, "stmt")],
            "end_name": nth_ident(node, -1),
        }
        if kind == "FunctionDecl":
            item["return_type"] = type_text(first_child(node, "return_type"))
        return item
    return {"kind": name}


def normalize_dhparser_param(node: dict[str, Any] | None) -> dict[str, str]:
    if not node:
        return {"name": "", "type": ""}
    return {"name": nth_ident(node, 0), "type": compact_type(type_text(first_child(node, "type_ref")))}


def normalize_dhparser_stmt(stmt: dict[str, Any]) -> dict[str, Any]:
    node = first_named(stmt) or stmt
    name = node_name(node)
    if name == "let_stmt":
        return {"kind": "LetStmt", "name": nth_ident(node, 0), "type": compact_type(type_text(first_child(node, "return_type"))), "value": expr_text(first_child(node, "expr"))}
    if name == "return_stmt":
        return {"kind": "ReturnStmt", "value": canonical_expr_text(text_of(first_child(node, "return_value")))}
    if name == "check_stmt":
        return {"kind": "CheckStmt", "condition": expr_text(first_child(node, "expr"))}
    if name in {"assign_stmt", "field_assign_stmt"}:
        parts = split_assignment(node)
        return {"kind": "AssignmentStmt", "target": canonical_expr_text(parts[0]), "value": canonical_expr_text(parts[1])}
    if name == "call_stmt":
        return {"kind": "CallStmt", "call": canonical_expr_text(text_of(node).removeprefix("call"))}
    if name == "if_stmt":
        return {
            "kind": "IfStmt",
            "condition": expr_text(first_child(node, "expr")),
            "then_body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "then_block"), "stmt")],
            "else_body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "else_block"), "stmt")],
        }
    if name == "while_stmt":
        item = {
            "kind": "WhileStmt",
            "condition": expr_text(first_child(node, "expr")),
            "invariants": [expr_text(first_child(inv, "expr")) for inv in children(node, "invariant_clause")],
            "body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "loop_block"), "stmt")],
        }
        variant = first_child(node, "variant_clause")
        if variant:
            item["variant"] = expr_text(first_child(variant, "expr"))
        return item
    if name == "case_stmt":
        return {
            "kind": "CaseStmt",
            "value": expr_text(first_child(node, "expr")),
            "when": [
                {"value": expr_text(first_child(branch, "expr")), "body": [normalize_dhparser_stmt(child) for child in children(first_child(branch, "case_block"), "stmt")]}
                for branch in children(node, "case_branch")
            ],
            "default": [normalize_dhparser_stmt(child) for child in children(first_child(first_child(node, "default_branch"), "case_block"), "stmt")],
        }
    return {"kind": name}


def split_assignment(node: dict[str, Any]) -> tuple[str, str]:
    text = canonical_expr_text(text_of(node))
    if ":=" in text:
        left, right = text.split(":=", 1)
        return left, right
    return text, ""


def expr_text(node: dict[str, Any] | None) -> str:
    return canonical_expr_text(text_of(node))


def type_text(node: dict[str, Any] | None) -> str:
    return compact_type(text_of(node))


def compact_type(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def canonical_expr_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def node_name(node: dict[str, Any] | None) -> str:
    return node.get("name", "") if isinstance(node, dict) else ""


def children(node: dict[str, Any] | None, name: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    items = [child for child in node.get("children") or [] if isinstance(child, dict)]
    return [child for child in items if name is None or node_name(child) == name]


def first_child(node: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    items = children(node, name)
    return items[0] if items else None


def first_named(node: dict[str, Any] | None) -> dict[str, Any] | None:
    for child in children(node):
        if not node_name(child).startswith(":"):
            return child
    return None


def descendants(node: dict[str, Any] | None, name: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for child in children(node):
        if node_name(child) == name:
            found.append(child)
        found.extend(descendants(child, name))
    return found


def text_of(node: dict[str, Any] | None) -> str:
    if not isinstance(node, dict):
        return ""
    if "text" in node:
        return str(node["text"])
    return "".join(text_of(child) for child in children(node))


def ident_text(node: dict[str, Any] | None) -> str:
    return text_of(node)


def nth_ident(node: dict[str, Any] | None, index: int) -> str:
    idents = descendants(node, "IDENT")
    if not idents:
        return ""
    return ident_text(idents[index])


def qualified_name_text(node: dict[str, Any] | None) -> str:
    return ".".join(ident_text(item) for item in descendants(node, "IDENT"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Comparable parse-ok cases: {summary['comparable_parse_ok_cases']}",
        f"Matching shape:            {summary['matching_shape']}",
        f"Mismatching shape:         {summary['mismatching_shape']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for item in summary["mismatches"]:
            lines.append(item["case"])
            lines.append("  Go:       " + json.dumps(item["go_shape"], sort_keys=True))
            lines.append("  DHParser: " + json.dumps(item["dhparser_shape"], sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare AST shape")
    print("-----------------")
    print("Comparable parse-ok cases:", summary["comparable_parse_ok_cases"])
    print("Matching shape:           ", summary["matching_shape"])
    print("Mismatching shape:        ", summary["mismatching_shape"])


if __name__ == "__main__":
    raise SystemExit(main())