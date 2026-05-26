from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_EXPECTED = Path("tests/language_modules/expected_go_semantic_projects.json")
DEFAULT_OUT_ROOT = Path(".tmp/go-semantic-project")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Go-native semantic project loader")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED), help="expected Go semantic project JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="temporary output root")
    args = parser.parse_args()

    expected = load_json(Path(args.expected))["cases"]
    out_root = Path(args.out)
    failures: list[str] = []

    for case, want in sorted(expected.items()):
        out_file = out_root / f"{safe_case_name(case)}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "go",
            "run",
            ".\\cmd\\go-semantic-project",
            "--out",
            str(Path("..").joinpath(out_file)),
            str(Path("..").joinpath(want["entry"])),
        ]
        completed = subprocess.run(command, cwd=Path("go-frontend"), text=True, capture_output=True)
        want_semantic_ok = expected_semantic_ok(want)
        if completed.returncode != 0 and want_semantic_ok:
            failures.append(f"{case}: go-semantic-project failed: {completed.stdout}{completed.stderr}")
            continue
        if not out_file.exists():
            failures.append(f"{case}: missing output {out_file}")
            continue

        result = load_json(out_file)
        check_project(failures, case, result, want)

    print("Verify Go semantic projects")
    print("---------------------------")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print(f"Expected semantic projects: {len(expected)}")
    print("Mismatches:                 0")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_case_name(case: str) -> str:
    return case.replace("/", "__").replace("\\", "__")


def check_project(failures: list[str], case: str, result: dict[str, Any], expected: dict[str, Any]) -> None:
    for field in ("entry_module", "modules", "semantic_ok"):
        if result.get(field) != expected.get(field):
            failures.append(f"{case}: {field} expected {expected.get(field)!r}, got {result.get(field)!r}")
    expected_diagnostics = expected.get("semantic_diagnostics")
    if expected_diagnostics is not None:
        check_diagnostics(failures, case, result.get("semantic_diagnostics"), expected_diagnostics)
    expected_parse_ok = expected.get("parse_ok", True)
    if result.get("parse_ok") != expected_parse_ok:
        failures.append(f"{case}: parse_ok expected {expected_parse_ok!r}, got {result.get('parse_ok')!r}")
    expected_semantic_run = expected.get("semantic_run", True)
    if result.get("semantic_run") != expected_semantic_run:
        failures.append(f"{case}: semantic_run expected {expected_semantic_run!r}, got {result.get('semantic_run')!r}")


def expected_semantic_ok(expected: dict[str, Any]) -> bool:
    return expected.get("semantic_ok", True) is True


def check_diagnostics(
    failures: list[str],
    case: str,
    result_diagnostics: Any,
    expected_diagnostics: list[dict[str, Any]],
) -> None:
    if not isinstance(result_diagnostics, list):
        failures.append(f"{case}: semantic_diagnostics expected list, got {result_diagnostics!r}")
        return
    if len(result_diagnostics) != len(expected_diagnostics):
        failures.append(
            f"{case}: semantic_diagnostics length expected {len(expected_diagnostics)}, got {len(result_diagnostics)}"
        )
        return
    for index, (got, want) in enumerate(zip(result_diagnostics, expected_diagnostics)):
        for field, expected_value in want.items():
            if got.get(field) != expected_value:
                failures.append(
                    f"{case}: semantic_diagnostics[{index}].{field} expected {expected_value!r}, got {got.get(field)!r}"
                )


if __name__ == "__main__":
    raise SystemExit(main())
