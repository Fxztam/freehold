from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from freehold.core.diagnostics import diagnose_exception
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program


DEFAULT_EXPECTED = Path("tests/language_modules/expected_semantic_diagnostics.json")
DEFAULT_LANGUAGE_ROOT = Path("tests/language_modules")
DEFAULT_OUT_ROOT = Path("artifacts/compare-semantic-diagnostics")


CODE_MAP = {
    "VF-I001": ("FH-SEM-1001", 1001, "module_self_import", "semantic"),
    "VF-I002": ("FH-SEM-1002", 1002, "duplicate_import", "semantic"),
    "VF-I003": ("FH-SEM-1003", 1003, "duplicate_exposing_symbol", "semantic"),
    "VF-N002": ("FH-SEM-1004", 1004, "reserved_keyword_name", "semantic"),
    "VF-T001": ("FH-TYP-2001", 2001, "duplicate_type_declaration", "type"),
    "VF-T002": ("FH-TYP-2002", 2002, "builtin_type_redefinition", "type"),
    "VF-T003": ("FH-TYP-2003", 2003, "unknown_type_reference", "type"),
    "VF-T004": ("FH-TYP-2004", 2004, "invalid_range_bounds", "type"),
    "VF-T005": ("FH-TYP-2005", 2005, "range_requires_numeric_base", "type"),
    "VF-T006": ("FH-TYP-2006", 2006, "integer_range_requires_integer_bounds", "type"),
    "VF-R001": ("FH-SEM-1101", 1101, "duplicate_record_field", "semantic"),
    "VF-R003": ("FH-SEM-1102", 1102, "duplicate_record_literal_field", "semantic"),
    "VF-R004": ("FH-SEM-1103", 1103, "unknown_record_literal_field", "semantic"),
    "VF-R005": ("FH-SEM-1104", 1104, "missing_record_literal_field", "semantic"),
    "VF-R006": ("FH-TYP-2101", 2101, "field_access_requires_record", "type"),
    "VF-R007": ("FH-SEM-1105", 1105, "unknown_record_field", "semantic"),
    "VF-A001": ("FH-TYP-2111", 2111, "array_literal_requires_scalar", "type"),
    "VF-A002": ("FH-TYP-2112", 2112, "array_literal_mixed_element_types", "type"),
    "VF-A003": ("FH-TYP-2113", 2113, "array_length_mismatch", "type"),
    "VF-A004": ("FH-TYP-2114", 2114, "array_element_type_mismatch", "type"),
    "VF-A006": ("FH-TYP-2115", 2115, "index_access_requires_array", "type"),
    "VF-A007": ("FH-TYP-2116", 2116, "array_index_requires_integer", "type"),
    "VF-A008": ("FH-SEM-1111", 1111, "array_index_out_of_bounds", "semantic"),
    "VF-U002": ("FH-SEM-1201", 1201, "duplicate_parameter_name", "semantic"),
    "VF-U003": ("FH-SEM-1202", 1202, "function_missing_guaranteed_return", "semantic"),
    "VF-U004": ("FH-SEM-1203", 1203, "procedure_return_value", "semantic"),
    "VF-U005": ("FH-SEM-1204", 1204, "unknown_routine", "semantic"),
    "VF-U007": ("FH-SEM-1205", 1205, "routine_argument_count_mismatch", "semantic"),
    "VF-U008": ("FH-TYP-2201", 2201, "routine_argument_type_mismatch", "type"),
    "VF-U009": ("FH-TYP-2202", 2202, "function_return_type_mismatch", "type"),
    "VF-ST001": ("FH-SEM-1301", 1301, "unknown_assignment_target", "semantic"),
    "VF-ST002": ("FH-TYP-2301", 2301, "assignment_type_mismatch", "type"),
    "VF-ST003": ("FH-TYP-2007", 2007, "statement_requires_boolean", "type"),
    "VF-ST004": ("FH-TYP-2302", 2302, "while_variant_requires_integer", "type"),
    "VF-ST005": ("FH-TYP-2303", 2303, "case_branch_type_mismatch", "type"),
    "VF-ST006": ("FH-SEM-1302", 1302, "duplicate_case_branch_value", "semantic"),
    "VF-E001": ("FH-SEM-1401", 1401, "unknown_variable", "semantic"),
    "VF-E002": ("FH-TYP-2401", 2401, "comparison_type_mismatch", "type"),
    "VF-E003": ("FH-TYP-2402", 2402, "boolean_operator_operand_mismatch", "type"),
    "VF-E004": ("FH-TYP-2403", 2403, "ordering_comparison_operand_mismatch", "type"),
    "VF-E005": ("FH-TYP-2404", 2404, "arithmetic_operand_mismatch", "type"),
    "VF-E006": ("FH-TYP-2405", 2405, "unary_not_requires_boolean", "type"),
    "VF-E007": ("FH-TYP-2406", 2406, "unary_negative_requires_numeric", "type"),
    "VF-ER001": ("FH-SEM-1501", 1501, "unknown_result_error_type", "semantic"),
    "VF-ER002": ("FH-SEM-1502", 1502, "unknown_returned_error", "semantic"),
    "VF-ER003": ("FH-SEM-1503", 1503, "wrong_result_error_return", "semantic"),
    "VF-ER004": ("FH-SEM-1504", 1504, "result_function_requires_ok_or_error_return", "semantic"),
    "VF-ER005": ("FH-SEM-1505", 1505, "plain_function_rejects_ok_or_error_return", "semantic"),
    "VF-ER006": ("FH-TYP-2501", 2501, "result_ok_type_mismatch", "type"),
    "VF-ER007": ("FH-RES-4107", 4107, "nested_result_payload_not_supported", "result"),
    "VF-CT001": ("FH-TYP-2601", 2601, "contract_clause_requires_boolean", "type"),
    "VF-CT002": ("FH-SEM-1601", 1601, "result_contract_expression_outside_result_ensures", "semantic"),
    "VF-ABT001": ("FH-ABT-3001", 3001, "unknown_abort_error", "abort"),
    "VF-ABT002": ("FH-ABT-3002", 3002, "abort_not_declared_by_routine", "abort"),
    "VF-ABT003": ("FH-ABT-3003", 3003, "duplicate_abort_declaration", "abort"),
    "VF-ABT005": ("FH-ABT-3005", 3005, "caller_does_not_handle_or_propagate_abort", "abort"),
    "VF-ABT009": ("FH-ABT-3009", 3009, "main_requires_clause_not_allowed", "abort"),
    "VF-TPL001": ("FH-TPL-4001", 4001, "template_placeholder_count_mismatch", "template"),
    "VF-TPL002": ("FH-TPL-4002", 4002, "template_old_placeholder_rejected", "template"),
    "VF-TPL003": ("FH-TPL-4003", 4003, "template_invalid_named_placeholder", "template"),
    "VF-TPL004": ("FH-TPL-4004", 4004, "template_invalid_brace", "template"),
    "VF-TPL005": ("FH-TPL-4005", 4005, "template_value_type_mismatch", "template"),
    "VF-TPL006": ("FH-TPL-4006", 4006, "template_duplicate_binding", "template"),
    "VF-TPL007": ("FH-TPL-4007", 4007, "template_missing_binding", "template"),
    "VF-TPL008": ("FH-TPL-4008", 4008, "template_unused_binding", "template"),
    "VF-TPL009": ("FH-TPL-4009", 4009, "template_mixed_modes", "template"),
    "VF-J001": ("FH-JSON-4201", 4201, "json_stringify_argument_count", "json"),
    "VF-J002": ("FH-JSON-4202", 4202, "json_stringify_requires_record", "json"),
    "VF-J003": ("FH-JSON-4203", 4203, "json_stringify_unsupported_type", "json"),
    "VF-GEN002": ("FH-GEN-5002", 5002, "duplicate_type_parameter", "generic"),
    "VF-GEN010": ("FH-GEN-5010", 5010, "missing_type_argument", "generic"),
    "VF-GEN011": ("FH-GEN-5011", 5011, "too_many_type_arguments", "generic"),
    "VF-GEN012": ("FH-GEN-5012", 5012, "non_generic_type_used_with_type_arguments", "generic"),
    "VF-GEN030": ("FH-GEN-5030", 5030, "missing_routine_type_argument", "generic"),
    "VF-GEN031": ("FH-GEN-5031", 5031, "wrong_routine_type_argument_count", "generic"),
    "VF-GEN032": ("FH-GEN-5032", 5032, "non_generic_routine_used_with_type_arguments", "generic"),
    "VF-ASY001": ("FH-CON-3101", 3101, "await_outside_async_function", "concurrency"),
    "VF-ASY002": ("FH-CON-3102", 3102, "await_requires_awaitable_expression", "concurrency"),
    "VF-CH001": ("FH-CON-3111", 3111, "channel_argument_count_mismatch", "concurrency"),
    "VF-CH002": ("FH-CON-3112", 3112, "channel_argument_type_mismatch", "concurrency"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare expected Freehold semantic/type diagnostics")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED), help="expected semantic diagnostics JSON")
    parser.add_argument("--root", default=str(DEFAULT_LANGUAGE_ROOT), help="language_modules source root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    expected_path = Path(args.expected)
    language_root = Path(args.root)
    out_root = Path(args.out)

    expected = load_json(expected_path)["cases"]
    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []

    for case, want in sorted(expected.items()):
        path = language_root / case.replace(".json", ".fh")
        if not path.exists():
            mismatches.append(f"{case}: missing source file {path}")
            rows.append({"case": case, "status": "missing_source"})
            continue

        actual = run_semantic_diagnostic(path)
        if actual is None:
            mismatches.append(f"{case}: expected semantic failure, got verification success")
            rows.append({"case": case, "status": "unexpected_success"})
            continue

        case_mismatches = compare_diagnostic(case, actual, want)
        mismatches.extend(case_mismatches)
        rows.append({
            "case": case,
            "status": "mismatch" if case_mismatches else "match",
            "actual": actual,
            "expected": want,
        })

    summary = {
        "expected_semantic_diagnostics": len(expected),
        "matching_semantic_diagnostics": sum(1 for row in rows if row.get("status") == "match"),
        "mismatching_semantic_diagnostics": len(mismatches),
        "mismatches": mismatches,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_summary.json", summary)
    write_json(out_root / "_all.json", rows)
    write_text_report(out_root / "_mismatches.txt", summary)
    print_summary(summary)
    return 1 if mismatches else 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_semantic_diagnostic(path: Path) -> dict[str, Any] | None:
    source = path.read_text(encoding="utf-8")
    try:
        verify_program(parse_source(source))
    except Exception as exc:
        return normalize_diagnostic(diagnose_exception(source, exc))
    return None


def normalize_diagnostic(diagnostic: Any) -> dict[str, Any]:
    raw = asdict(diagnostic)
    legacy_code = raw["code"]
    code, number, name, category = CODE_MAP.get(
        legacy_code,
        ("FH-SEM-1999", 1999, "unclassified_semantic_diagnostic", "semantic"),
    )
    return {
        "severity": "error",
        "phase": raw.get("phase") or "semantic",
        "category": category,
        "code": code,
        "number": number,
        "name": name,
        "message": raw["message"],
        "location": {"line": raw["line"], "column": raw["column"]},
        "expected": raw["expected"],
        "found": raw["found"],
        "hint": raw["hint"],
        "legacy_code": legacy_code,
    }


def compare_diagnostic(case: str, actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for field in ("code", "name", "phase", "category", "legacy_code", "message", "expected", "found"):
        if actual.get(field) != expected.get(field):
            mismatches.append(f"{case}: {field} expected {expected.get(field)!r}, got {actual.get(field)!r}")

    actual_location = actual.get("location")
    expected_location = expected.get("location")
    if actual_location != expected_location:
        mismatches.append(f"{case}: location expected {expected_location!r}, got {actual_location!r}")
    return mismatches


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Expected semantic diagnostics:     {summary['expected_semantic_diagnostics']}",
        f"Matching semantic diagnostics:     {summary['matching_semantic_diagnostics']}",
        f"Mismatching semantic diagnostics:  {summary['mismatching_semantic_diagnostics']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        lines.extend(summary["mismatches"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare semantic diagnostics")
    print("----------------------------")
    print("Expected semantic diagnostics:   ", summary["expected_semantic_diagnostics"])
    print("Matching semantic diagnostics:   ", summary["matching_semantic_diagnostics"])
    print("Mismatching semantic diagnostics:", summary["mismatching_semantic_diagnostics"])


if __name__ == "__main__":
    raise SystemExit(main())