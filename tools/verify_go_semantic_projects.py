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
        if completed.returncode != 0:
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
    for field in ("entry_module", "modules", "semantic_ok", "semantic_diagnostics"):
        if result.get(field) != expected.get(field):
            failures.append(f"{case}: {field} expected {expected.get(field)!r}, got {result.get(field)!r}")
    if not result.get("parse_ok"):
        failures.append(f"{case}: parse_ok expected true, got {result.get('parse_ok')!r}")
    if not result.get("semantic_run"):
        failures.append(f"{case}: semantic_run expected true, got {result.get('semantic_run')!r}")


if __name__ == "__main__":
    raise SystemExit(main())
