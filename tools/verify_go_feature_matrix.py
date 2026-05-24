from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MATRIX = Path("tests/language_modules/go_codegen_feature_matrix.json")
DEFAULT_LANGUAGE_MODULES = Path("tests/language_modules")
VALID_STATUSES = {"supported", "rejected", "deferred"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Go codegen feature matrix coverage")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX), help="Go codegen feature matrix JSON")
    parser.add_argument("--language-modules", default=str(DEFAULT_LANGUAGE_MODULES), help="language modules root")
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    language_modules = Path(args.language_modules)
    matrix = load_json(matrix_path)
    manifests = load_manifests(language_modules)
    failures: list[str] = []

    entries = matrix.get("modules")
    if not isinstance(entries, list):
        failures.append("matrix.modules must be a list")
        entries = []

    by_module: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            failures.append(f"modules[{index}] must be an object")
            continue
        module = entry.get("module")
        if not isinstance(module, str) or not module:
            failures.append(f"modules[{index}].module must be a non-empty string")
            continue
        if module in by_module:
            failures.append(f"duplicate matrix module: {module}")
        by_module[module] = entry

    manifest_modules = set(manifests)
    matrix_modules = set(by_module)
    for module in sorted(manifest_modules - matrix_modules):
        failures.append(f"missing matrix entry for language module: {module}")
    for module in sorted(matrix_modules - manifest_modules):
        failures.append(f"matrix entry has no language module manifest: {module}")

    for module, entry in sorted(by_module.items()):
        manifest = manifests.get(module)
        if manifest is None:
            continue
        check_entry(failures, module, entry, manifest)

    summary = summarize(by_module)
    if failures:
        print("Verify Go feature matrix")
        print("------------------------")
        for failure in failures:
            print(failure)
        return 1

    print("Verify Go feature matrix")
    print("------------------------")
    print(f"Language modules: {len(manifests)}")
    print(f"Matrix entries:   {len(by_module)}")
    for status in sorted(VALID_STATUSES):
        print(f"{status.title():<9}: {summary.get(status, 0)}")
    print("Mismatches:       0")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_manifests(root: Path) -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for module_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest_path = module_dir / "manifest.json"
        if manifest_path.exists():
            manifests[module_dir.name] = load_json(manifest_path)
    return manifests


def check_entry(failures: list[str], module: str, entry: dict[str, Any], manifest: dict[str, Any]) -> None:
    title = entry.get("title")
    if title != manifest.get("title"):
        failures.append(f"{module}: title mismatch with manifest")

    status = entry.get("status")
    if status not in VALID_STATUSES:
        failures.append(f"{module}: invalid status {status!r}")

    summary = entry.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        failures.append(f"{module}: summary must be a non-empty string")

    case_names = {case.get("name") for case in manifest.get("cases", []) if isinstance(case, dict)}
    for field in ("supported_cases", "rejected_cases"):
        values = entry.get(field, [])
        if not isinstance(values, list):
            failures.append(f"{module}: {field} must be a list")
            continue
        for value in values:
            if value not in case_names:
                failures.append(f"{module}: {field} references unknown manifest case {value!r}")

    if status == "supported" and not entry.get("supported_cases"):
        failures.append(f"{module}: supported entries must list supported_cases")
    if status == "rejected" and not entry.get("rejected_reason") and not entry.get("rejected_cases"):
        failures.append(f"{module}: rejected entries need rejected_reason or rejected_cases")
    if status == "deferred" and not entry.get("deferred_items"):
        failures.append(f"{module}: deferred entries must list deferred_items")


def summarize(entries: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for entry in entries.values():
        status = entry.get("status")
        if isinstance(status, str):
            summary[status] = summary.get(status, 0) + 1
    return summary


if __name__ == "__main__":
    raise SystemExit(main())