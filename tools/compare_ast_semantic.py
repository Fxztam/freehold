from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_GO_ROOT = Path("artifacts/go-ast")
DEFAULT_DHPARSER_ROOT = Path("artifacts/dhparser-ast")
DEFAULT_OUT_ROOT = Path("artifacts/compare-ast-semantic")


BINARY_LEVELS = {
    "logic_or": "logic_and",
    "logic_and": "equality",
    "equality": "comparison",
    "comparison": "sum",
    "sum": "product",
    "product": "unary",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare normalized Go and DHParser semantic AST artifacts")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go AST artifact root")
    parser.add_argument("--dhparser", default=str(DEFAULT_DHPARSER_ROOT), help="DHParser AST artifact root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    go_results = load_results(Path(args.go))
    dhparser_results = load_results(Path(args.dhparser))

    comparable_keys = sorted(
        key for key, go_result in go_results.items()
        if go_result.get("parse_ok") and dhparser_results.get(key, {}).get("parse_ok")
    )

    matches: list[str] = []
    mismatches: list[dict[str, Any]] = []

    for key in comparable_keys:
        go_ast = normalize_go_module(go_results[key]["ast"])
        dhparser_ast = normalize_dhparser_module(dhparser_results[key]["ast"])
        if go_ast == dhparser_ast:
            matches.append(key)
        else:
            mismatches.append({"case": key, "go_ast": go_ast, "dhparser_ast": dhparser_ast})

    summary = {
        "total_parse_status_cases": len(set(go_results) | set(dhparser_results)),
        "comparable_parse_ok_cases": len(comparable_keys),
        "matching_semantic_ast": len(matches),
        "mismatching_semantic_ast": len(mismatches),
        "matches": matches,
        "mismatches": mismatches,
    }

    out_root = Path(args.out)
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
        item: dict[str, Any] = {"kind": kind, "name": decl.get("name", ""), "base": compact_type(decl.get("base", ""))}
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
            "aborts": [normalize_go_abort_clause(clause) for clause in decl.get("aborts") or []],
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


def normalize_go_abort_clause(clause: dict[str, Any]) -> dict[str, Any]:
    return {"error": clause.get("error", ""), "condition": normalize_go_expr(clause.get("condition")) if clause.get("condition") else None}


def normalize_go_stmt(stmt: dict[str, Any]) -> dict[str, Any]:
    kind = stmt.get("kind")
    if kind == "LetStmt":
        return {"kind": kind, "name": stmt.get("name", ""), "type": compact_type(stmt.get("type", "")), "value": normalize_go_expr(stmt.get("value"))}
    if kind == "ReturnStmt":
        return {"kind": kind, "value": normalize_go_expr(stmt.get("value"))}
    if kind == "AbortStmt":
        return {"kind": kind, "error": stmt.get("error", "")}
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


def normalize_go_expr(expr: Any) -> dict[str, Any]:
    if not isinstance(expr, dict):
        return {"kind": "MissingExpr"}
    kind = expr.get("kind")
    if kind == "IdentifierExpr":
        return {"kind": kind, "name": expr.get("name", "")}
    if kind == "NumberExpr":
        return normalize_number_expr(expr.get("value", ""))
    if kind == "StringExpr":
        return {"kind": kind, "value": expr.get("value", "")}
    if kind == "BinaryExpr":
        return {"kind": kind, "op": expr.get("op", ""), "left": normalize_go_expr(expr.get("left")), "right": normalize_go_expr(expr.get("right"))}
    if kind == "UnaryExpr":
        return {"kind": kind, "op": expr.get("op", ""), "value": normalize_go_expr(expr.get("value"))}
    if kind == "FieldAccessExpr":
        return {"kind": kind, "object": normalize_go_expr(expr.get("object")), "field": expr.get("field", "")}
    if kind == "IndexExpr":
        return {"kind": kind, "array": normalize_go_expr(expr.get("array")), "index": normalize_go_expr(expr.get("index"))}
    if kind == "ArrayLiteralExpr":
        return {"kind": kind, "elements": [normalize_go_expr(item) for item in expr.get("elements") or []]}
    if kind == "CallExpr":
        return {"kind": kind, "callee": normalize_go_expr(expr.get("callee")), "arguments": [normalize_go_expr(item) for item in expr.get("arguments") or []]}
    if kind == "NamedArgumentExpr":
        return {"kind": kind, "name": expr.get("name", ""), "value": normalize_go_expr(expr.get("value"))}
    if kind == "RecordLiteralExpr":
        return {
            "kind": kind,
            "type": expr.get("type", ""),
            "fields": [{"name": field.get("name", ""), "value": normalize_go_expr(field.get("value"))} for field in expr.get("fields") or []],
        }
    if kind == "OkExpr":
        return {"kind": kind, "value": normalize_go_expr(expr.get("value"))}
    if kind == "ErrorExpr":
        return {"kind": kind, "name": expr.get("name", "")}
    return {"kind": kind or "UnknownExpr"}


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
        return {"kind": "ImportDecl", "module": qualified_name_text(qnames[0]) if qnames else "", "exposing": [ident_text(item) for item in descendants(exposing, "IDENT")] if exposing else []}
    if name == "type_decl":
        item: dict[str, Any] = {"kind": "TypeDecl", "name": nth_ident(node, 0), "base": type_text(first_child(node, "base_type"))}
        range_node = first_child(node, "range_decl")
        if range_node:
            nums = [text_of(child) for child in children(range_node) if node_name(child) in {"NUMBER_LITERAL", "INTEGER_LITERAL", "DOUBLE_LITERAL"}]
            if len(nums) >= 2:
                item["range"] = {"min": nums[0], "max": nums[1]}
        return item
    if name == "record_type_decl":
        return {"kind": "TypeDecl", "name": nth_ident(node, 0), "base": "record", "fields": [normalize_dhparser_param(field) for field in children(node, "record_field")]}
    if name == "error_decl":
        return {"kind": "ErrorDecl", "name": nth_ident(node, 0)}
    if name in {"function_decl", "procedure_decl"}:
        kind = "FunctionDecl" if name == "function_decl" else "ProcedureDecl"
        item = {
            "kind": kind,
            "name": nth_ident(node, 0),
            "params": [normalize_dhparser_param(param) for param in children(first_child(node, "param_list"), "param")],
            "requires": [dh_expr(expr) for req in children(first_child(node, "contract_block"), "requires_clause") for expr in children(first_child(req, "expr_list"), "expr")],
            "aborts": [normalize_dhparser_abort_clause(clause) for clause in children(first_child(node, "contract_block"), "aborts_clause")],
            "ensures": [dh_expr(expr) for req in children(first_child(node, "contract_block"), "ensures_clause") for expr in children(first_child(req, "expr_list"), "expr")],
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
    return {"name": nth_ident(node, 0), "type": type_text(first_child(node, "type_ref"))}


def normalize_dhparser_abort_clause(node: dict[str, Any]) -> dict[str, Any]:
    condition = first_child(node, "expr")
    return {"error": nth_ident(node, 0), "condition": dh_expr(condition) if condition else None}


def normalize_dhparser_stmt(stmt: dict[str, Any]) -> dict[str, Any]:
    node = first_named(stmt) or stmt
    name = node_name(node)
    if name == "let_stmt":
        return {"kind": "LetStmt", "name": nth_ident(node, 0), "type": type_text(first_child(node, "return_type")), "value": dh_expr(first_child(node, "expr"))}
    if name == "return_stmt":
        return {"kind": "ReturnStmt", "value": dh_return_value(first_child(node, "return_value"))}
    if name == "abort_stmt":
        return {"kind": "AbortStmt", "error": nth_ident(node, 0)}
    if name == "check_stmt":
        return {"kind": "CheckStmt", "condition": dh_expr(first_child(node, "expr"))}
    if name == "assign_stmt":
        return {"kind": "AssignmentStmt", "target": ident_expr(nth_ident(node, 0)), "value": dh_expr(first_child(node, "expr"))}
    if name == "field_assign_stmt":
        return {"kind": "AssignmentStmt", "target": qualified_expr(text_of(first_child(node, "FIELD_PATH"))), "value": dh_expr(first_child(node, "expr"))}
    if name == "call_stmt":
        return {"kind": "CallStmt", "call": {"kind": "CallExpr", "callee": qualified_expr(qualified_name_text(first_child(node, "qualified_name"))), "arguments": dh_arg_list(first_child(node, "arg_list"))}}
    if name == "if_stmt":
        return {
            "kind": "IfStmt",
            "condition": dh_expr(first_child(node, "expr")),
            "then_body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "then_block"), "stmt")],
            "else_body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "else_block"), "stmt")],
        }
    if name == "while_stmt":
        item = {
            "kind": "WhileStmt",
            "condition": dh_expr(first_child(node, "expr")),
            "invariants": [dh_expr(first_child(inv, "expr")) for inv in children(node, "invariant_clause")],
            "body": [normalize_dhparser_stmt(child) for child in children(first_child(node, "loop_block"), "stmt")],
        }
        variant = first_child(node, "variant_clause")
        if variant:
            item["variant"] = dh_expr(first_child(variant, "expr"))
        return item
    if name == "case_stmt":
        return {
            "kind": "CaseStmt",
            "value": dh_expr(first_child(node, "expr")),
            "when": [
                {"value": dh_expr(first_child(branch, "expr")), "body": [normalize_dhparser_stmt(child) for child in children(first_child(branch, "case_block"), "stmt")]}
                for branch in children(node, "case_branch")
            ],
            "default": [normalize_dhparser_stmt(child) for child in children(first_child(first_child(node, "default_branch"), "case_block"), "stmt")],
        }
    return {"kind": name}


def dh_return_value(node: dict[str, Any] | None) -> dict[str, Any]:
    named = children(node)
    if not named:
        return {"kind": "MissingExpr"}
    first = named[0]
    if node_name(first) == ":Text" and text_of(first) == "ok":
        return {"kind": "OkExpr", "value": dh_expr(first_child(node, "expr"))}
    if node_name(first) == ":Text" and text_of(first) == "error":
        return {"kind": "ErrorExpr", "name": nth_ident(node, 0)}
    return dh_expr(first_child(node, "expr") or first_named(node))


def dh_expr(node: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {"kind": "MissingExpr"}
    name = node_name(node)
    if name == "expr":
        return dh_expr(first_child(node, "logic_or"))
    if name in BINARY_LEVELS:
        return dh_binary(node, BINARY_LEVELS[name])
    if name == "unary":
        named = children(node)
        if named and node_name(named[0]) == ":Text" and text_of(named[0]) in {"-", "not"}:
            return {"kind": "UnaryExpr", "op": text_of(named[0]), "value": dh_expr(next_non_token(named[1:]))}
        return dh_expr(first_named(node))
    if name == "postfix_expr":
        return dh_postfix(node)
    if name == "primary":
        return dh_primary(node)
    if name == "return_value":
        return dh_return_value(node)
    return dh_primary(node)


def dh_binary(node: dict[str, Any], operand_name: str) -> dict[str, Any]:
    items = children(node)
    operands = [item for item in items if node_name(item) == operand_name]
    operators = [text_of(item) for item in items if node_name(item) == ":Text" and text_of(item).strip()]
    if not operands:
        return {"kind": "MissingExpr"}
    expr = dh_expr(operands[0])
    for op, operand in zip(operators, operands[1:]):
        expr = {"kind": "BinaryExpr", "op": op, "left": expr, "right": dh_expr(operand)}
    return expr


def dh_postfix(node: dict[str, Any]) -> dict[str, Any]:
    expr = dh_expr(first_child(node, "primary"))
    for postfix in children(node, "postfix"):
        parts = children(postfix)
        marker = text_of(parts[0]) if parts else ""
        if marker == "(":
            expr = {"kind": "CallExpr", "callee": expr, "arguments": dh_arg_list(first_child(postfix, "arg_list"))}
        elif marker == "[":
            expr = {"kind": "IndexExpr", "array": expr, "index": dh_expr(first_child(postfix, "expr"))}
        elif marker == ".":
            expr = {"kind": "FieldAccessExpr", "object": expr, "field": nth_ident(postfix, 0)}
    return expr


def dh_primary(node: dict[str, Any]) -> dict[str, Any]:
    if node_name(node) != "primary":
        name = node_name(node)
        if name in {"INTEGER_LITERAL", "DOUBLE_LITERAL", "NUMBER_LITERAL"}:
            return normalize_number_expr(text_of(node))
        if name == "STRING_LITERAL":
            return {"kind": "StringExpr", "value": parse_string_literal(text_of(node))}
        if name == "IDENT":
            return ident_expr(ident_text(node))
        return {"kind": "UnknownExpr", "source": canonical_expr_text(text_of(node))}

    expr_child = first_child(node, "expr")
    if expr_child:
        return dh_expr(expr_child)
    array = first_child(node, "array_literal")
    if array:
        return {"kind": "ArrayLiteralExpr", "elements": dh_arg_list(first_child(array, "arg_list"))}
    named_args = first_child(node, "named_arg_list")
    ident = first_child(node, "IDENT")
    if named_args and ident:
        return {"kind": "RecordLiteralExpr", "type": ident_text(ident), "fields": dh_named_arg_list(named_args)}
    literal = first_literal_child(node)
    if literal:
        return dh_primary(literal)
    text = canonical_expr_text(text_of(node))
    if text in {"true", "false", "success", "failure", "value", "error"}:
        return ident_expr(text)
    return ident_expr(text)


def dh_arg_list(node: dict[str, Any] | None) -> list[dict[str, Any]]:
    args: list[dict[str, Any]] = []
    for child in children(node, "call_arg"):
        named = first_child(child, "named_arg")
        if named:
            args.append({"kind": "NamedArgumentExpr", "name": nth_ident(named, 0), "value": dh_expr(first_child(named, "expr"))})
            continue
        args.append(dh_expr(first_child(child, "expr")))
    if args:
        return args
    return [dh_expr(child) for child in children(node, "expr")]


def dh_named_arg_list(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"name": nth_ident(arg, 0), "value": dh_expr(first_child(arg, "expr"))} for arg in children(node, "named_arg")]


def normalize_number_expr(value: str) -> dict[str, Any]:
    if value.startswith("-") and len(value) > 1:
        return {"kind": "UnaryExpr", "op": "-", "value": {"kind": "NumberExpr", "value": value[1:]}}
    return {"kind": "NumberExpr", "value": value}


def parse_string_literal(value: str) -> str:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, str) else value
    except json.JSONDecodeError:
        return value[1:-1] if value.startswith('"') and value.endswith('"') else value


def qualified_expr(text: str) -> dict[str, Any]:
    parts = [part for part in text.split(".") if part]
    if not parts:
        return {"kind": "MissingExpr"}
    expr = ident_expr(parts[0])
    for field in parts[1:]:
        expr = {"kind": "FieldAccessExpr", "object": expr, "field": field}
    return expr


def ident_expr(name: str) -> dict[str, str]:
    return {"kind": "IdentifierExpr", "name": name}


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
    return next_non_token(children(node))


def next_non_token(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    for child in items:
        if not node_name(child).startswith(":"):
            return child
    return None


def first_literal_child(node: dict[str, Any]) -> dict[str, Any] | None:
    for child in children(node):
        if node_name(child) in {"INTEGER_LITERAL", "DOUBLE_LITERAL", "NUMBER_LITERAL", "STRING_LITERAL", "IDENT"}:
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
        f"Comparable parse-ok cases:    {summary['comparable_parse_ok_cases']}",
        f"Matching semantic AST:        {summary['matching_semantic_ast']}",
        f"Mismatching semantic AST:     {summary['mismatching_semantic_ast']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for item in summary["mismatches"]:
            lines.append(item["case"])
            lines.append("  Go:       " + json.dumps(item["go_ast"], sort_keys=True))
            lines.append("  DHParser: " + json.dumps(item["dhparser_ast"], sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare semantic AST")
    print("--------------------")
    print("Comparable parse-ok cases:   ", summary["comparable_parse_ok_cases"])
    print("Matching semantic AST:       ", summary["matching_semantic_ast"])
    print("Mismatching semantic AST:    ", summary["mismatching_semantic_ast"])


if __name__ == "__main__":
    raise SystemExit(main())