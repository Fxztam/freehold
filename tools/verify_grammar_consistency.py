from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_OUT = Path(".tmp/grammar-consistency/report.json")
GRAMMAR_DIR = Path("freehold/grammar")
TOKEN_FILE = Path("go-frontend/internal/token/token.go")

GRAMMAR_FILES = [
    GRAMMAR_DIR / "freehold.ebnf",
    GRAMMAR_DIR / "freehold.lark",
    GRAMMAR_DIR / "freehold.generated.ebnf",
    GRAMMAR_DIR / "freehold.dhparser.ebnf",
    GRAMMAR_DIR / "freehold.generated.parseebnf.ebnf",
    GRAMMAR_DIR / "freehold.generated.pyebnf.ebnf",
    GRAMMAR_DIR / "freehold.generated.rr.ebnf",
    GRAMMAR_DIR / "freehold.generated.vscode.ebnf",
]

REQUIRED_LARK_RULES = [
    "start",
    "module_decl",
    "module_end",
    "qualified_name",
    "import_decl",
    "exposing_clause",
    "declaration",
    "record_type_decl",
    "type_decl",
    "error_decl",
    "service_decl",
    "function_decl",
    "procedure_decl",
    "type_ref",
    "return_type",
    "result_type",
    "array_type",
    "stmt",
    "let_stmt",
    "assign_stmt",
    "field_assign_stmt",
    "return_stmt",
    "abort_stmt",
    "if_stmt",
    "while_stmt",
    "case_stmt",
    "scope_stmt",
    "check_stmt",
    "call_stmt",
    "expr",
    "field_path",
    "array_literal",
]

REQUIRED_LARK_TERMINALS = [
    "BASE_TYPE",
    "INT_NUMBER",
    "SIGNED_FLOAT",
    "SIGNED_NUMBER",
    "TYPE_ARG_START",
    "COMMENT",
    "BLOCK_COMMENT",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Freehold grammar consistency")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="write JSON report to this path")
    args = parser.parse_args()

    issues: list[dict[str, Any]] = []
    report: dict[str, Any] = {"files": {}, "checks": {}}

    texts = load_grammar_files(issues, report)
    lark_text = texts.get(str(GRAMMAR_DIR / "freehold.lark"), "")
    ebnf_text = texts.get(str(GRAMMAR_DIR / "freehold.ebnf"), "")

    if lark_text:
        lark_rules = extract_lark_rules(lark_text)
        lark_terminals = extract_lark_terminals(lark_text)
        report["checks"]["lark_rules"] = {"count": len(lark_rules), "required": REQUIRED_LARK_RULES}
        report["checks"]["lark_terminals"] = {"count": len(lark_terminals), "required": REQUIRED_LARK_TERMINALS}
        add_duplicate_issues(issues, "freehold.lark", "rule", lark_rules)
        add_missing_issues(issues, "freehold.lark", "required_rule", REQUIRED_LARK_RULES, lark_rules)
        add_missing_issues(issues, "freehold.lark", "required_terminal", REQUIRED_LARK_TERMINALS, lark_terminals)
        check_go_keyword_literals(issues, report, lark_text)

    if ebnf_text:
        ebnf_rules = extract_ebnf_rules(ebnf_text)
        report["checks"]["human_ebnf_rules"] = {"count": len(ebnf_rules)}
        add_duplicate_issues(issues, "freehold.ebnf", "rule", ebnf_rules)

    for path, text in texts.items():
        if path.endswith(".ebnf") and path != str(GRAMMAR_DIR / "freehold.ebnf"):
            add_duplicate_issues(issues, path, "rule", extract_ebnf_rules(text))

    report["issues"] = issues
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Verify grammar consistency")
    print("--------------------------")
    if issues:
        for issue in issues:
            print(f"{issue['file']}: {issue['kind']}: {issue['name']}")
        return 1
    print(f"Grammar files:            {len(GRAMMAR_FILES)}")
    print(f"Lark rules:               {len(extract_lark_rules(lark_text)) if lark_text else 0}")
    print(f"Go keywords covered:      {len(report.get('checks', {}).get('go_keywords', {}).get('covered', []))}")
    print("Mismatches:               0")
    return 0


def load_grammar_files(issues: list[dict[str, Any]], report: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in GRAMMAR_FILES:
        key = str(path)
        if not path.exists():
            issues.append({"file": key, "kind": "missing_file", "name": key})
            report["files"][key] = {"exists": False, "bytes": 0}
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            issues.append({"file": key, "kind": "empty_file", "name": key})
        report["files"][key] = {"exists": True, "bytes": len(text.encode("utf-8"))}
        texts[key] = text
    return texts


def extract_lark_rules(text: str) -> list[str]:
    return re.findall(r"(?m)^\??!?([a-z][A-Za-z0-9_]*)\s*:", text)


def extract_lark_terminals(text: str) -> list[str]:
    return re.findall(r"(?m)^([A-Z][A-Z0-9_]*)\s*:", text)


def extract_ebnf_rules(text: str) -> list[str]:
    return re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|::=)", text)


def add_duplicate_issues(issues: list[dict[str, Any]], file_name: str, kind: str, names: list[str]) -> None:
    for name, count in sorted(Counter(names).items()):
        if count > 1:
            issues.append({"file": file_name, "kind": f"duplicate_{kind}", "name": name, "count": count})


def add_missing_issues(
    issues: list[dict[str, Any]],
    file_name: str,
    kind: str,
    required: list[str],
    available: list[str],
) -> None:
    available_set = set(available)
    for name in required:
        if name not in available_set:
            issues.append({"file": file_name, "kind": kind, "name": name})


def check_go_keyword_literals(issues: list[dict[str, Any]], report: dict[str, Any], lark_text: str) -> None:
    keywords = sorted(extract_go_keywords())
    lark_literals = set(re.findall(r'"([A-Za-z][A-Za-z0-9_.]*)"', lark_text))
    missing = [keyword for keyword in keywords if keyword not in lark_literals]
    report["checks"]["go_keywords"] = {
        "count": len(keywords),
        "covered": [keyword for keyword in keywords if keyword in lark_literals],
        "missing": missing,
    }
    for keyword in missing:
        issues.append({"file": "freehold.lark", "kind": "missing_go_keyword_literal", "name": keyword})


def extract_go_keywords() -> set[str]:
    if not TOKEN_FILE.exists():
        return set()
    text = TOKEN_FILE.read_text(encoding="utf-8")
    values = re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\s+Kind\s*=\s*"([^"]+)"', text)
    return {value for value in values if re.fullmatch(r"[a-z]+", value)}


if __name__ == "__main__":
    raise SystemExit(main())