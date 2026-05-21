from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_GO_ROOT = Path("artifacts/go-ast")
DEFAULT_DHPARSER_ROOT = Path("artifacts/dhparser-ast")
DEFAULT_OUT_ROOT = Path("artifacts/compare-parse-errors")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Go and DHParser parse error diagnostics")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go AST artifact root")
    parser.add_argument("--dhparser", default=str(DEFAULT_DHPARSER_ROOT), help="DHParser AST artifact root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    go_results = load_results(Path(args.go))
    dhparser_results = load_results(Path(args.dhparser))
    all_keys = sorted(set(go_results) | set(dhparser_results))

    rows: list[dict[str, Any]] = []
    missing_go: list[str] = []
    missing_dhparser: list[str] = []
    status_mismatches: list[dict[str, Any]] = []
    location_matches = 0
    location_mismatches: list[dict[str, Any]] = []
    shared_failures = 0

    for key in all_keys:
        go_result = go_results.get(key)
        dhparser_result = dhparser_results.get(key)
        if go_result is None:
            missing_go.append(key)
            continue
        if dhparser_result is None:
            missing_dhparser.append(key)
            continue

        go_ok = bool(go_result.get("parse_ok"))
        dhparser_ok = bool(dhparser_result.get("parse_ok"))
        if go_ok != dhparser_ok:
            status_mismatches.append({"case": key, "go_parse_ok": go_ok, "dhparser_parse_ok": dhparser_ok})
            continue
        if go_ok:
            continue

        shared_failures += 1
        go_diag = diagnostic_from_go(go_result)
        dhparser_diag = diagnostic_from_dhparser(dhparser_result.get("error", ""))
        row = {
            "case": key,
            "freehold": go_diag.get("freehold") or classify_failure(key, go_diag["message"], dhparser_diag["message"]),
            "go": go_diag,
            "dhparser": dhparser_diag,
            "same_location": same_location(go_diag.get("location"), dhparser_diag.get("location")),
        }
        rows.append(row)
        if row["same_location"]:
            location_matches += 1
        else:
            location_mismatches.append(row)

    summary = {
        "total_cases": len(all_keys),
        "shared_failures": shared_failures,
        "matching_failure_locations": location_matches,
        "mismatching_failure_locations": len(location_mismatches),
        "status_mismatches": len(status_mismatches),
        "missing_go": len(missing_go),
        "missing_dhparser": len(missing_dhparser),
        "code_counts": code_counts(rows),
        "location_mismatches": location_mismatches,
        "status_mismatch_cases": status_mismatches,
        "missing_go_cases": missing_go,
        "missing_dhparser_cases": missing_dhparser,
    }

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_summary.json", summary)
    write_json(out_root / "_all.json", rows)
    write_text_report(out_root / "_diagnostics.txt", summary)
    print_summary(summary)
    return 1 if status_mismatches or missing_go or missing_dhparser else 0


def load_results(root: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in root.glob("*/*/*.json"):
        with path.open("r", encoding="utf-8") as handle:
            results[path.relative_to(root).as_posix()] = json.load(handle)
    return results


def diagnostic_from_go(result: dict[str, Any]) -> dict[str, Any]:
    error = result.get("error", "")
    diagnostic = result.get("diagnostic") if isinstance(result.get("diagnostic"), dict) else None
    if diagnostic:
        return {
            "location": diagnostic.get("location"),
            "message": single_line(error),
            "freehold": diagnostic,
        }

    match = re.search(r"line (\d+) col (\d+)", error) or re.search(r"Location: line (\d+), column (\d+)", error)
    location = {"line": int(match.group(1)), "column": int(match.group(2))} if match else None
    return {"location": location, "message": single_line(error)}


def diagnostic_from_dhparser(error: str) -> dict[str, Any]:
    match = re.search(r"^(\d+):(\d+):", error)
    location = {"line": int(match.group(1)), "column": int(match.group(2))} if match else None
    return {"location": location, "message": single_line(error)}


def classify_failure(case: str, go_error: str, dhparser_error: str) -> dict[str, Any]:
    text = f"{case} {go_error} {dhparser_error}"
    lowered = text.lower()

    if "empty_file" in case or "empty document" in lowered:
        return syntax_code("FH-SYN-0003", 3, "missing_module_declaration", "Expected a module declaration.")
    if "expected ident" in lowered or "parser ident" in lowered:
        return syntax_code("FH-SYN-0002", 2, "expected_identifier", "Expected an identifier.")
    if "expected module" in lowered or "parser module_decl" in lowered:
        return syntax_code("FH-SYN-0003", 3, "missing_module_declaration", "Expected a module declaration.")
    if "unterminated_block_comment" in case:
        return syntax_code("FH-SYN-0010", 10, "unterminated_block_comment", "Unterminated block comment.")
    if "expected end" in lowered:
        return syntax_code("FH-SYN-0004", 4, "missing_end", "Expected an end marker.")
    if "expected :," in lowered or "let_uses_assignment_operator" in case:
        return syntax_code("FH-SYN-0005", 5, "expected_type_annotation_colon", "Expected ':' for a type annotation.")
    if "ensures_before_requires" in case or "expected is" in lowered:
        return syntax_code("FH-SYN-0006", 6, "invalid_contract_order", "Expected requires clauses before ensures clauses.")
    if "expected declaration" in lowered:
        return syntax_code("FH-SYN-0007", 7, "expected_declaration", "Expected a declaration.")
    if "expected default" in lowered:
        return syntax_code("FH-SYN-0008", 8, "missing_case_default", "Expected a default case branch.")
    if "expected invariant" in lowered:
        return syntax_code("FH-SYN-0009", 9, "missing_while_invariant", "Expected a while invariant.")
    return syntax_code("FH-SYN-9999", 9999, "parse_error", "Parse error.")


def syntax_code(code: str, number: int, name: str, message: str) -> dict[str, Any]:
    return {
        "severity": "error",
        "phase": "parse",
        "category": "syntax",
        "code": code,
        "number": number,
        "name": name,
        "message": message,
    }


def code_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        code = row["freehold"]["code"]
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def single_line(text: str) -> str:
    return " ".join((text or "").split())


def same_location(left: dict[str, int] | None, right: dict[str, int] | None) -> bool:
    if not left or not right:
        return left == right
    return left.get("line") == right.get("line") and left.get("column") == right.get("column")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Total cases:                    {summary['total_cases']}",
        f"Shared failures:                {summary['shared_failures']}",
        f"Matching failure locations:     {summary['matching_failure_locations']}",
        f"Mismatching failure locations:  {summary['mismatching_failure_locations']}",
        f"Status mismatches:              {summary['status_mismatches']}",
        f"Missing Go:                     {summary['missing_go']}",
        f"Missing DHParser:               {summary['missing_dhparser']}",
    ]

    if summary["code_counts"]:
        lines.extend(["", "Freehold Diagnostic Codes", "-------------------------"])
        for code, count in summary["code_counts"].items():
            lines.append(f"{code}: {count}")

    if summary["location_mismatches"]:
        lines.extend(["", "Location Mismatches", "-------------------"])
        for item in summary["location_mismatches"]:
            lines.append(item["case"])
            lines.append(f"  Freehold: {item['freehold']['code']} {item['freehold']['name']} - {item['freehold']['message']}")
            lines.append(f"  Go:       {format_location(item['go']['location'])} {item['go']['message']}")
            lines.append(f"  DHParser: {format_location(item['dhparser']['location'])} {item['dhparser']['message']}")

    if summary["status_mismatch_cases"]:
        lines.extend(["", "Status Mismatches", "-----------------"])
        for item in summary["status_mismatch_cases"]:
            lines.append(f"{item['case']} => Go={item['go_parse_ok']} DHParser={item['dhparser_parse_ok']}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_location(location: dict[str, int] | None) -> str:
    if not location:
        return "line ?:?"
    return f"line {location['line']}:{location['column']}"


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare parse errors")
    print("--------------------")
    print("Shared failures:              ", summary["shared_failures"])
    print("Matching failure locations:   ", summary["matching_failure_locations"])
    print("Mismatching failure locations:", summary["mismatching_failure_locations"])
    print("Status mismatches:            ", summary["status_mismatches"])


if __name__ == "__main__":
    raise SystemExit(main())