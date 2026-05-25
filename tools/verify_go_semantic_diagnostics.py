from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_EXPECTED = Path("tests/language_modules/expected_go_semantic_diagnostics.json")
DEFAULT_GO_ROOT = Path("artifacts/go-semantic")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify narrow Go-native semantic diagnostics")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED), help="expected Go semantic diagnostics JSON")
    parser.add_argument("--go", default=str(DEFAULT_GO_ROOT), help="Go semantic artifact root")
    args = parser.parse_args()

    expected = load_json(Path(args.expected))["cases"]
    go_root = Path(args.go)
    failures: list[str] = []

    for case, want in sorted(expected.items()):
        path = go_root / case
        if not path.exists():
            failures.append(f"{case}: missing Go semantic artifact")
            continue

        result = load_json(path)
        if not result.get("parse_ok"):
            failures.append(f"{case}: expected parse_ok=true, got parse failure: {result.get('error', '')}")
            continue
        if not result.get("semantic_run"):
            failures.append(f"{case}: semantic_run is false or missing")
            continue
        if result.get("semantic_ok"):
            failures.append(f"{case}: expected semantic failure, got semantic_ok=true")
            continue

        diagnostics = result.get("semantic_diagnostics")
        if not isinstance(diagnostics, list) or len(diagnostics) != 1:
            failures.append(f"{case}: expected one semantic diagnostic, got {diagnostics!r}")
            continue

        diagnostic = diagnostics[0]
        if not isinstance(diagnostic, dict):
            failures.append(f"{case}: semantic diagnostic is not an object")
            continue

        check_diagnostic(failures, case, diagnostic, want)
        alias = result.get("diagnostic")
        if not isinstance(alias, dict):
            failures.append(f"{case}: missing diagnostic alias for first semantic diagnostic")
        else:
            for field in ("code", "name", "location"):
                if alias.get(field) != diagnostic.get(field):
                    failures.append(f"{case}: diagnostic alias field {field} does not match semantic_diagnostics[0]")

    if failures:
        print("Verify Go semantic diagnostics")
        print("------------------------------")
        for failure in failures:
            print(failure)
        return 1

    print("Verify Go semantic diagnostics")
    print("------------------------------")
    print(f"Expected semantic diagnostics: {len(expected)}")
    print("Mismatches:                    0")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_diagnostic(failures: list[str], case: str, diagnostic: dict[str, Any], expected: dict[str, Any]) -> None:
    for field in ("code", "name", "expected", "found"):
        if diagnostic.get(field) != expected.get(field):
            failures.append(f"{case}: {field} expected {expected.get(field)!r}, got {diagnostic.get(field)!r}")
    check_location(failures, case, diagnostic.get("location"), expected.get("location"))


def check_location(failures: list[str], case: str, actual: Any, expected: Any) -> None:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        failures.append(f"{case}: location expected {expected!r}, got {actual!r}")
        return

    actual_line_column = {"line": actual.get("line"), "column": actual.get("column")}
    if actual_line_column != expected:
        failures.append(f"{case}: location expected {expected!r}, got {actual_line_column!r}")


if __name__ == "__main__":
    raise SystemExit(main())
