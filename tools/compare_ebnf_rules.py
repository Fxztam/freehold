from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_GENERATED = Path("freehold/grammar/freehold.generated.ebnf")
DEFAULT_DHPARSER = Path("freehold/grammar/freehold.dhparser.ebnf")
DEFAULT_OUT = Path(".tmp/ebnf-rule-compare/report.json")

EXPECTED_GENERATED_ONLY = {
    "BACKSLASH",
    "BLOCK_COMMENT",
    "BLOCK_COMMENT_CHARACTER",
    "DIGIT",
    "DIGITS",
    "DOUBLE_QUOTE",
    "ESCAPE_SEQUENCE",
    "LETTER",
    "LINE_COMMENT",
    "LINE_COMMENT_CHARACTER",
    "NEWLINE",
    "PRINTABLE_SYMBOL",
    "SIGNED_DOUBLE_LITERAL",
    "SIGNED_INTEGER_LITERAL",
    "SPACE",
    "STRING_CHARACTER",
    "TAB",
    "TYPE_ARG_START",
}

EXPECTED_DHPARSER_ONLY = {
    "EOF",
    "FIELD_PATH",
    "member_name",
    "postfix",
    "postfix_expr",
    "primary",
}

EXPECTED_DIFFERENT_RULES = {
    "array_type",
    "atom",
    "call_arg",
    "comparison",
    "DOUBLE_LITERAL",
    "equality",
    "expr",
    "field_assign_stmt",
    "field_path",
    "FIELD_PATH",
    "function_decl",
    "IDENT",
    "INTEGER_LITERAL",
    "let_stmt",
    "logic_and",
    "logic_or",
    "module_decl",
    "module_end",
    "NUMBER_LITERAL",
    "primary",
    "procedure_decl",
    "product",
    "qualified_name",
    "record_type_decl",
    "result_type",
    "rpc_decl",
    "service_decl",
    "scope_join_block",
    "scope_result_block",
    "scope_spawn_block",
    "start",
    "stmt",
    "STRING_LITERAL",
    "sum",
    "type_arg_list",
    "type_param_list",
    "type_ref",
    "unary",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare generated Freehold EBNF with DHParser EBNF rules")
    parser.add_argument("--generated", default=str(DEFAULT_GENERATED), help="generated ISO EBNF file")
    parser.add_argument("--dhparser", default=str(DEFAULT_DHPARSER), help="DHParser EBNF file")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="write JSON report to this path")
    parser.add_argument("--strict", action="store_true", help="return non-zero for unexpected rule-set deltas")
    args = parser.parse_args()

    generated_path = Path(args.generated)
    dhparser_path = Path(args.dhparser)
    issues: list[str] = []

    generated_rules = load_rules(generated_path, issues)
    dhparser_rules = load_rules(dhparser_path, issues)

    generated_names = set(generated_rules)
    dhparser_names = set(dhparser_rules)
    generated_only = sorted(generated_names - dhparser_names)
    dhparser_only = sorted(dhparser_names - generated_names)
    common = sorted(generated_names & dhparser_names)

    body_differences = [
        name
        for name in common
        if normalize_rule_body(generated_rules[name]) != normalize_rule_body(dhparser_rules[name])
    ]

    unexpected_generated_only = sorted(set(generated_only) - EXPECTED_GENERATED_ONLY)
    unexpected_dhparser_only = sorted(set(dhparser_only) - EXPECTED_DHPARSER_ONLY)
    unexpected_body_differences = sorted(set(body_differences) - EXPECTED_DIFFERENT_RULES)

    report = {
        "generated": {
            "file": display_path(generated_path),
            "rule_count": len(generated_rules),
        },
        "dhparser": {
            "file": display_path(dhparser_path),
            "rule_count": len(dhparser_rules),
        },
        "rule_sets": {
            "common_count": len(common),
            "generated_only": generated_only,
            "dhparser_only": dhparser_only,
            "unexpected_generated_only": unexpected_generated_only,
            "unexpected_dhparser_only": unexpected_dhparser_only,
        },
        "rule_bodies": {
            "different_count": len(body_differences),
            "different_rules": body_differences,
            "unexpected_different_rules": unexpected_body_differences,
        },
        "known_intentional_deltas": {
            "generated_only": sorted(EXPECTED_GENERATED_ONLY),
            "dhparser_only": sorted(EXPECTED_DHPARSER_ONLY),
            "different_rules": sorted(EXPECTED_DIFFERENT_RULES),
        },
        "issues": issues,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("Compare EBNF rules")
    print("------------------")
    print("Generated:", display_path(generated_path))
    print("DHParser: ", display_path(dhparser_path))
    print("Generated rule count:", len(generated_rules))
    print("DHParser rule count: ", len(dhparser_rules))
    print("Common rules:        ", len(common))
    print("Generated-only rules:", len(generated_only))
    print("DHParser-only rules: ", len(dhparser_only))
    print("Different rule bodies:", len(body_differences))
    print("Unexpected generated-only:", len(unexpected_generated_only))
    print("Unexpected DHParser-only: ", len(unexpected_dhparser_only))
    print("Unexpected body diffs:    ", len(unexpected_body_differences))
    print("Report:", display_path(out_path))

    if issues:
        for issue in issues:
            print("Issue:", issue)
        return 1
    if args.strict and (unexpected_generated_only or unexpected_dhparser_only or unexpected_body_differences):
        return 1
    return 0


def load_rules(path: Path, issues: list[str]) -> dict[str, str]:
    if not path.exists():
        issues.append(f"missing file: {display_path(path)}")
        return {}
    text = path.read_text(encoding="utf-8")
    rules: dict[str, str] = {}
    for name, body in extract_rules(text).items():
        if name in rules:
            issues.append(f"duplicate rule in {display_path(path)}: {name}")
        rules[name] = body
    return rules


def extract_rules(text: str) -> dict[str, str]:
    rules: dict[str, str] = {}
    current_name: str | None = None
    current_body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("(*") or line.startswith("*)") or line.startswith("@"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if match:
            if current_name is not None:
                rules[current_name] = normalize_rule_end(" ".join(current_body))
            current_name = match.group(1)
            current_body = [match.group(2)]
            continue
        if current_name is not None:
            current_body.append(line)

    if current_name is not None:
        rules[current_name] = normalize_rule_end(" ".join(current_body))
    return rules


def normalize_rule_end(body: str) -> str:
    return body.strip().removesuffix(";").strip()


def normalize_rule_body(body: str) -> str:
    body = normalize_rule_end(body)
    body = body.replace("~", "")
    body = re.sub(r"\s+", " ", body)
    return body.strip()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())