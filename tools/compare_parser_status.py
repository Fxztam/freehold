from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_GO_ROOT = Path("artifacts/go-ast")
DEFAULT_DHPARSER_ROOT = Path("artifacts/dhparser-ast")
DEFAULT_OUT_ROOT = Path("artifacts/compare-parse-status")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Go and DHParser parse status artifacts")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go AST artifact root")
    parser.add_argument("--dhparser", default=str(DEFAULT_DHPARSER_ROOT), help="DHParser AST artifact root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    go_root = Path(args.go)
    dhparser_root = Path(args.dhparser)
    out_root = Path(args.out)

    go_results = load_results(go_root)
    dhparser_results = load_results(dhparser_root)

    all_keys = sorted(set(go_results) | set(dhparser_results))
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    missing_go: list[str] = []
    missing_dhparser: list[str] = []
    matching_status = 0

    for key in all_keys:
        go_result = go_results.get(key)
        dhparser_result = dhparser_results.get(key)

        if go_result is None:
            missing_go.append(key)
            rows.append({"case": key, "status": "missing_go", "dhparser_parse_ok": dhparser_result.get("parse_ok")})
            continue

        if dhparser_result is None:
            missing_dhparser.append(key)
            rows.append({"case": key, "status": "missing_dhparser", "go_parse_ok": go_result.get("parse_ok")})
            continue

        go_ok = bool(go_result.get("parse_ok"))
        dhparser_ok = bool(dhparser_result.get("parse_ok"))
        status = "match" if go_ok == dhparser_ok else "mismatch"

        row = {
            "case": key,
            "status": status,
            "go_parse_ok": go_ok,
            "dhparser_parse_ok": dhparser_ok,
            "go_error": go_result.get("error", ""),
            "dhparser_error": dhparser_result.get("error", ""),
        }
        rows.append(row)

        if status == "match":
            matching_status += 1
        else:
            mismatches.append(row)

    summary = {
        "total_cases": len(all_keys),
        "matching_status": matching_status,
        "mismatching_status": len(mismatches),
        "missing_go": len(missing_go),
        "missing_dhparser": len(missing_dhparser),
        "go_total": len(go_results),
        "dhparser_total": len(dhparser_results),
        "go_ok": count_ok(go_results),
        "go_fail": len(go_results) - count_ok(go_results),
        "dhparser_ok": count_ok(dhparser_results),
        "dhparser_fail": len(dhparser_results) - count_ok(dhparser_results),
        "mismatches": mismatches,
        "missing_go_cases": missing_go,
        "missing_dhparser_cases": missing_dhparser,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_summary.json", summary)
    write_json(out_root / "_all.json", rows)
    write_text_report(out_root / "_mismatches.txt", summary)

    print_summary(summary)
    return 1 if mismatches or missing_go or missing_dhparser else 0


def load_results(root: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in root.glob("*/*/*.json"):
        relative = path.relative_to(root).as_posix()
        with path.open("r", encoding="utf-8") as handle:
            results[relative] = json.load(handle)
    return results


def count_ok(results: dict[str, dict[str, Any]]) -> int:
    return sum(1 for result in results.values() if result.get("parse_ok"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Total cases:        {summary['total_cases']}",
        f"Matching status:    {summary['matching_status']}",
        f"Mismatching status: {summary['mismatching_status']}",
        f"Missing Go:         {summary['missing_go']}",
        f"Missing DHParser:   {summary['missing_dhparser']}",
        "",
        f"Go:       OK {summary['go_ok']} / FAIL {summary['go_fail']}",
        f"DHParser: OK {summary['dhparser_ok']} / FAIL {summary['dhparser_fail']}",
    ]

    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for item in summary["mismatches"]:
            lines.append(
                f"{item['case']} => Go={format_status(item['go_parse_ok'])}, "
                f"DHParser={format_status(item['dhparser_parse_ok'])}"
            )
            if item.get("go_error"):
                lines.append(f"  Go:       {single_line(item['go_error'])}")
            if item.get("dhparser_error"):
                lines.append(f"  DHParser: {single_line(item['dhparser_error'])}")

    if summary["missing_go_cases"]:
        lines.extend(["", "Missing Go Cases", "----------------"])
        lines.extend(summary["missing_go_cases"])

    if summary["missing_dhparser_cases"]:
        lines.extend(["", "Missing DHParser Cases", "----------------------"])
        lines.extend(summary["missing_dhparser_cases"])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare parse status")
    print("--------------------")
    print("Total cases:       ", summary["total_cases"])
    print("Matching status:   ", summary["matching_status"])
    print("Mismatching status:", summary["mismatching_status"])
    print("Missing Go:        ", summary["missing_go"])
    print("Missing DHParser:  ", summary["missing_dhparser"])
    print("Go:                ", f"OK {summary['go_ok']} / FAIL {summary['go_fail']}")
    print("DHParser:          ", f"OK {summary['dhparser_ok']} / FAIL {summary['dhparser_fail']}")


def format_status(parse_ok: bool) -> str:
    return "OK" if parse_ok else "FAIL"


def single_line(text: str) -> str:
    return " ".join(text.split())


if __name__ == "__main__":
    raise SystemExit(main())