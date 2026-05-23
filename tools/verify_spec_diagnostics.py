from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.compare_semantic_diagnostics import CODE_MAP


DEFAULT_DIAG = Path("spec/freehold.diag")
DEFAULT_RULES = Path("spec/freehold.rules")
DEFAULT_EXPECTED_SYNTAX = Path("tests/language_modules/expected_diagnostics.json")
DEFAULT_EXPECTED_SEMANTIC = Path("tests/language_modules/expected_semantic_diagnostics.json")
DEFAULT_OUT_ROOT = Path("artifacts/verify-spec-diagnostics")


@dataclass(frozen=True)
class DiagnosticSpec:
    code: str
    name: str
    line: int
    fields: dict[str, str]


@dataclass(frozen=True)
class RuleEmit:
    code: str
    rule: str
    line: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Freehold spec diagnostic coverage")
    parser.add_argument("--diag", default=str(DEFAULT_DIAG), help="freehold.diag path")
    parser.add_argument("--rules", default=str(DEFAULT_RULES), help="freehold.rules path")
    parser.add_argument("--expected-syntax", default=str(DEFAULT_EXPECTED_SYNTAX), help="expected syntax diagnostics JSON")
    parser.add_argument("--expected-semantic", default=str(DEFAULT_EXPECTED_SEMANTIC), help="expected semantic diagnostics JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="report output root")
    args = parser.parse_args()

    diag_path = Path(args.diag)
    rules_path = Path(args.rules)
    expected_syntax_path = Path(args.expected_syntax)
    expected_semantic_path = Path(args.expected_semantic)
    out_root = Path(args.out)

    diagnostics = parse_diag(diag_path)
    rule_emits = parse_rule_emits(rules_path)
    expected_syntax_codes = load_expected_codes(expected_syntax_path)
    expected_semantic_codes = load_expected_codes(expected_semantic_path)
    code_map_rows = load_code_map_rows()

    failures: list[str] = []
    rows: list[dict[str, Any]] = []

    check_required_fields(failures, rows, diagnostics)
    check_rule_emit_coverage(failures, rows, diagnostics, rule_emits)
    check_expected_coverage(failures, rows, diagnostics, expected_syntax_path, expected_syntax_codes)
    check_expected_coverage(failures, rows, diagnostics, expected_semantic_path, expected_semantic_codes)
    check_code_map_coverage(failures, rows, diagnostics, code_map_rows)
    check_name_consistency(failures, rows, diagnostics, expected_syntax_path)
    check_name_consistency(failures, rows, diagnostics, expected_semantic_path)
    check_code_map_name_consistency(failures, rows, diagnostics, code_map_rows)

    summary = {
        "diagnostic_specs": len(diagnostics),
        "rule_emits": len(rule_emits),
        "expected_syntax_codes": len(expected_syntax_codes),
        "expected_semantic_codes": len(expected_semantic_codes),
        "code_map_entries": len(code_map_rows),
        "failures": failures,
        "failure_count": len(failures),
    }

    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_summary.json", summary)
    write_json(out_root / "_all.json", rows)
    write_text_report(out_root / "_failures.txt", summary)
    print_summary(summary)
    return 1 if failures else 0


def parse_diag(path: Path) -> dict[str, DiagnosticSpec]:
    diagnostics: dict[str, DiagnosticSpec] = {}
    current: tuple[str, str, int, dict[str, str]] | None = None

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = clean_line(raw_line)
        if not line:
            continue
        parts = line.split(maxsplit=2)
        if parts[0] == "diag":
            if current is not None:
                code, _, start_line, _ = current
                raise ValueError(f"{path}:{start_line}: diag {code} missing end")
            if len(parts) != 3:
                raise ValueError(f"{path}:{line_number}: invalid diag declaration")
            current = (parts[1], parts[2], line_number, {})
            continue
        if line == "end":
            if current is None:
                raise ValueError(f"{path}:{line_number}: unexpected end")
            code, name, start_line, fields = current
            if code in diagnostics:
                raise ValueError(f"{path}:{line_number}: duplicate diagnostic code {code}")
            diagnostics[code] = DiagnosticSpec(code=code, name=name, line=start_line, fields=fields)
            current = None
            continue
        if current is not None:
            key, value = split_field(line)
            current[3][key] = value

    if current is not None:
        code, _, start_line, _ = current
        raise ValueError(f"{path}:{start_line}: diag {code} missing end")
    return diagnostics


def parse_rule_emits(path: Path) -> list[RuleEmit]:
    emits: list[RuleEmit] = []
    current_rule = "<top-level>"
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = clean_line(raw_line)
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in {"rule", "completion"}:
            current_rule = parts[1]
            continue
        if len(parts) >= 2 and parts[0] == "emit":
            emits.append(RuleEmit(code=parts[1], rule=current_rule, line=line_number))
    return emits


def clean_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return ""
    return stripped


def split_field(line: str) -> tuple[str, str]:
    parts = line.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], unquote(parts[1].strip())


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def load_expected_codes(path: Path) -> dict[str, set[str]]:
    expected = load_json(path)["cases"]
    codes: dict[str, set[str]] = {}
    for case, diagnostic in expected.items():
        collect_expected_code(codes, case, diagnostic)
        for nested in diagnostic.get("diagnostics", []) or []:
            collect_expected_code(codes, case, nested)
    return codes


def collect_expected_code(codes: dict[str, set[str]], case: str, diagnostic: dict[str, Any]) -> None:
    code = diagnostic.get("code")
    if isinstance(code, str):
        codes.setdefault(code, set()).add(case)


def load_code_map_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for legacy_code, (code, number, name, category) in sorted(CODE_MAP.items()):
        rows.append({
            "legacy_code": legacy_code,
            "code": code,
            "number": number,
            "name": name,
            "category": category,
        })
    return rows


def check_required_fields(failures: list[str], rows: list[dict[str, Any]], diagnostics: dict[str, DiagnosticSpec]) -> None:
    required = {"severity", "phase", "category", "message", "expected"}
    for spec in diagnostics.values():
        missing = sorted(required - spec.fields.keys())
        status = "match" if not missing else "mismatch"
        rows.append({"check": "diag_required_fields", "code": spec.code, "status": status, "missing": missing})
        for field in missing:
            failures.append(f"{spec.code}: missing required field {field}")


def check_rule_emit_coverage(
    failures: list[str],
    rows: list[dict[str, Any]],
    diagnostics: dict[str, DiagnosticSpec],
    rule_emits: list[RuleEmit],
) -> None:
    for emit in rule_emits:
        status = "match" if emit.code in diagnostics else "mismatch"
        rows.append({"check": "rule_emit_coverage", "code": emit.code, "rule": emit.rule, "line": emit.line, "status": status})
        if emit.code not in diagnostics:
            failures.append(f"freehold.rules:{emit.line}: rule {emit.rule} emits {emit.code}, missing in freehold.diag")


def check_expected_coverage(
    failures: list[str],
    rows: list[dict[str, Any]],
    diagnostics: dict[str, DiagnosticSpec],
    path: Path,
    expected_codes: dict[str, set[str]],
) -> None:
    for code, cases in sorted(expected_codes.items()):
        status = "match" if code in diagnostics else "mismatch"
        rows.append({"check": "expected_diagnostic_coverage", "source": str(path), "code": code, "cases": sorted(cases), "status": status})
        if code not in diagnostics:
            failures.append(f"{path}: expected diagnostic {code} missing in freehold.diag")


def check_code_map_coverage(
    failures: list[str],
    rows: list[dict[str, Any]],
    diagnostics: dict[str, DiagnosticSpec],
    code_map_rows: list[dict[str, Any]],
) -> None:
    for row in code_map_rows:
        code = row["code"]
        status = "match" if code in diagnostics else "mismatch"
        rows.append({"check": "code_map_coverage", **row, "status": status})
        if code not in diagnostics:
            failures.append(f"CODE_MAP {row['legacy_code']} -> {code} missing in freehold.diag")


def check_name_consistency(failures: list[str], rows: list[dict[str, Any]], diagnostics: dict[str, DiagnosticSpec], path: Path) -> None:
    expected = load_json(path)["cases"]
    for case, diagnostic in expected.items():
        check_one_name(failures, rows, diagnostics, path, case, diagnostic)
        for index, nested in enumerate(diagnostic.get("diagnostics", []) or []):
            check_one_name(failures, rows, diagnostics, path, f"{case}: diagnostics[{index}]", nested)


def check_one_name(
    failures: list[str],
    rows: list[dict[str, Any]],
    diagnostics: dict[str, DiagnosticSpec],
    path: Path,
    case: str,
    diagnostic: dict[str, Any],
) -> None:
    code = diagnostic.get("code")
    name = diagnostic.get("name")
    if not isinstance(code, str) or not isinstance(name, str) or code not in diagnostics:
        return
    expected_name = diagnostics[code].name
    status = "match" if name == expected_name else "mismatch"
    rows.append({"check": "expected_name_consistency", "source": str(path), "case": case, "code": code, "name": name, "expected_name": expected_name, "status": status})
    if name != expected_name:
        failures.append(f"{path}:{case}: {code} name expected {expected_name!r}, got {name!r}")


def check_code_map_name_consistency(
    failures: list[str],
    rows: list[dict[str, Any]],
    diagnostics: dict[str, DiagnosticSpec],
    code_map_rows: list[dict[str, Any]],
) -> None:
    for row in code_map_rows:
        code = row["code"]
        if code not in diagnostics:
            continue
        expected_name = diagnostics[code].name
        name = row["name"]
        status = "match" if name == expected_name else "mismatch"
        rows.append({"check": "code_map_name_consistency", **row, "expected_name": expected_name, "status": status})
        if name != expected_name:
            failures.append(f"CODE_MAP {row['legacy_code']} -> {code}: name expected {expected_name!r}, got {name!r}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Diagnostic specs:        {summary['diagnostic_specs']}",
        f"Rule emits:              {summary['rule_emits']}",
        f"Expected syntax codes:   {summary['expected_syntax_codes']}",
        f"Expected semantic codes: {summary['expected_semantic_codes']}",
        f"CODE_MAP entries:        {summary['code_map_entries']}",
        f"Failures:                {summary['failure_count']}",
    ]
    if summary["failures"]:
        lines.extend(["", "Failures", "--------"])
        lines.extend(summary["failures"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Verify spec diagnostics")
    print("-----------------------")
    print("Diagnostic specs:       ", summary["diagnostic_specs"])
    print("Rule emits:             ", summary["rule_emits"])
    print("Expected syntax codes:  ", summary["expected_syntax_codes"])
    print("Expected semantic codes:", summary["expected_semantic_codes"])
    print("CODE_MAP entries:       ", summary["code_map_entries"])
    print("Failures:               ", summary["failure_count"])
    if summary["failures"]:
        print()
        for failure in summary["failures"]:
            print(failure)


if __name__ == "__main__":
    raise SystemExit(main())