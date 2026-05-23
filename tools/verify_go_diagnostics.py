from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EXPECTED = Path("tests/language_modules/expected_diagnostics.json")
DEFAULT_GO_ROOT = Path("artifacts/go-ast")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify stable Go parser diagnostics")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED), help="expected diagnostics JSON")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go AST artifact root")
    args = parser.parse_args()

    expected = load_json(Path(args.expected))["cases"]
    go_root = Path(args.go)
    failures: list[str] = []

    for case, want in sorted(expected.items()):
        path = go_root / case
        if not path.exists():
            failures.append(f"{case}: missing Go artifact")
            continue

        result = load_json(path)
        if result.get("parse_ok"):
            failures.append(f"{case}: expected parse failure, got parse_ok=true")
            continue

        wanted_diagnostics = want.get("diagnostics")
        if isinstance(wanted_diagnostics, list):
            actual_diagnostics = result.get("diagnostics")
            if not isinstance(actual_diagnostics, list):
                failures.append(f"{case}: missing diagnostics array")
                continue
            if len(actual_diagnostics) != len(wanted_diagnostics):
                failures.append(f"{case}: diagnostics count expected {len(wanted_diagnostics)}, got {len(actual_diagnostics)}")
                continue
            for index, wanted in enumerate(wanted_diagnostics):
                actual = actual_diagnostics[index]
                if not isinstance(actual, dict):
                    failures.append(f"{case}: diagnostics[{index}] is not an object")
                    continue
                check_diagnostic(failures, f"{case}: diagnostics[{index}]", actual, wanted)
            check_first_diagnostic_alias(failures, case, result.get("diagnostic"), actual_diagnostics)
            continue

        diagnostic = result.get("diagnostic")
        if not isinstance(diagnostic, dict):
            failures.append(f"{case}: missing structured diagnostic")
            continue

        check_diagnostic(failures, case, diagnostic, want)

    if failures:
        print("Verify Go diagnostics")
        print("---------------------")
        for failure in failures:
            print(failure)
        return 1

    print("Verify Go diagnostics")
    print("---------------------")
    print(f"Expected diagnostics: {len(expected)}")
    print("Mismatches:           0")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_field(failures: list[str], case: str, diagnostic: dict[str, Any], expected: dict[str, Any], field: str) -> None:
    if diagnostic.get(field) != expected.get(field):
        failures.append(f"{case}: {field} expected {expected.get(field)!r}, got {diagnostic.get(field)!r}")


def check_diagnostic(failures: list[str], case: str, diagnostic: dict[str, Any], expected: dict[str, Any]) -> None:
    check_field(failures, case, diagnostic, expected, "code")
    check_field(failures, case, diagnostic, expected, "name")
    check_field(failures, case, diagnostic, expected, "expected")
    check_field(failures, case, diagnostic, expected, "found")
    check_field(failures, case, diagnostic, expected, "hint")
    check_location(failures, case, diagnostic.get("location"), expected.get("location"))


def check_first_diagnostic_alias(failures: list[str], case: str, diagnostic: Any, diagnostics: list[Any]) -> None:
    if not diagnostics:
        return
    if not isinstance(diagnostic, dict):
        failures.append(f"{case}: missing first diagnostic alias")
        return
    first = diagnostics[0]
    if not isinstance(first, dict):
        return
    for field in ("code", "name", "location"):
        if diagnostic.get(field) != first.get(field):
            failures.append(f"{case}: diagnostic alias field {field} does not match diagnostics[0]")


def check_location(failures: list[str], case: str, actual: Any, expected: Any) -> None:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        failures.append(f"{case}: location expected {expected!r}, got {actual!r}")
        return

    actual_line_column = {"line": actual.get("line"), "column": actual.get("column")}
    if actual_line_column != expected:
        failures.append(f"{case}: location expected {expected!r}, got {actual_line_column!r}")


if __name__ == "__main__":
    raise SystemExit(main())