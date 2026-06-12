from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.go_codegen import generate_go_project, generate_go_project_build_files, generate_go_project_extra_files


DEFAULT_MANIFEST = Path("artifacts/fhir-samples/compiler_v1_stage2/manifest.json")
DEFAULT_OUT = Path("artifacts/compare-ir/compiler_v1_stage2/report/go-project-contracts")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Stage-2 Go project codegen structure contracts")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Stage-2 manifest JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report output directory")
    args = parser.parse_args()

    manifest_path = resolve_repo_path(Path(args.manifest))
    out_root = resolve_repo_path(Path(args.out))
    manifest = load_manifest(manifest_path)
    contracts = manifest.get("go_project_contracts", [])
    if not isinstance(contracts, list):
        raise ValueError("manifest go_project_contracts must be a list")
    expected_count = (manifest.get("policy") or {}).get("go_project_contracts")
    if expected_count is not None and expected_count != len(contracts):
        raise ValueError(f"manifest policy violation: expected {expected_count} Go project contracts, found {len(contracts)}")

    rows = [verify_contract(contract) for contract in contracts]
    failures = [row for row in rows if row["status"] != "match"]
    summary = {
        "total_contracts": len(rows),
        "matching_contracts": len(rows) - len(failures),
        "failing_contracts": len(failures),
        "failures": failures,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_failures.txt").write_text(render_failures(summary), encoding="utf-8")
    print_summary(summary)
    return 1 if failures else 0


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    return manifest


def project_entry_module_name(files: list[Any], entry_file: Path) -> str | None:
    entry_path = entry_file.resolve()
    for file in files:
        source_path = Path(file.source_file)
        if not source_path.is_absolute():
            source_path = (Path.cwd() / source_path).resolve()
        if source_path.resolve() == entry_path:
            return file.module_name
    return files[0].module_name if files else None


def verify_contract(contract: dict[str, Any]) -> dict[str, Any]:
    name = contract.get("name", "<unnamed>")
    source_file = contract.get("source_file")
    failures: list[str] = []
    if not source_file:
        failures.append("missing source_file")
        return contract_row(name, source_file or "", {}, failures)

    source_path = REPO_ROOT / source_file
    try:
        files = generate_go_project(source_path)
        entry_module_name = project_entry_module_name(files, source_path)
        build_files = generate_go_project_build_files(files, entry_module_name=entry_module_name)
        extra_files = generate_go_project_extra_files(files)
    except Exception as exc:
        failures.append(f"generation failed: {type(exc).__name__}: {exc}")
        return contract_row(name, source_file, {}, failures)

    project = {
        "module_path": "freehold.local",
        "total_files": len(files),
        "total_build_files": len(build_files),
        "total_extra_files": len(extra_files),
        "supported": all(file.result.supported for file in files),
        "files": {file.output_path: file for file in files},
        "build_files": {file.output_path: file for file in build_files},
        "extra_files": {file.output_path: file for file in extra_files},
    }
    check_project_values(contract, project, failures)
    check_codegen_files(contract.get("files", []), project["files"], "files", failures)
    check_text_files(contract.get("build_files", []), project["build_files"], "build_files", failures)
    check_text_files(contract.get("extra_files", []), project["extra_files"], "extra_files", failures)

    return contract_row(
        name,
        source_file,
        {
            "total_files": project["total_files"],
            "total_build_files": project["total_build_files"],
            "total_extra_files": project["total_extra_files"],
            "supported": project["supported"],
            "file_paths": sorted(project["files"]),
            "build_file_paths": sorted(project["build_files"]),
            "extra_file_paths": sorted(project["extra_files"]),
        },
        failures,
    )


def check_project_values(contract: dict[str, Any], project: dict[str, Any], failures: list[str]) -> None:
    expected = contract.get("expected", {})
    for key in ("module_path", "total_files", "total_build_files", "total_extra_files", "supported"):
        if key in expected and project[key] != expected[key]:
            failures.append(f"expected {key}={expected[key]!r}, found {project[key]!r}")


def check_codegen_files(expected_items: list[dict[str, Any]], actual: dict[str, Any], label: str, failures: list[str]) -> None:
    for expected in expected_items:
        path = expected.get("output_path")
        if not path:
            failures.append(f"{label}: expected item without output_path")
            continue
        file = actual.get(path)
        if file is None:
            failures.append(f"{label}: missing {path}")
            continue
        if "module" in expected and file.module_name != expected["module"]:
            failures.append(f"{label}: {path} expected module {expected['module']!r}, found {file.module_name!r}")
        if "supported" in expected and file.result.supported != expected["supported"]:
            failures.append(f"{label}: {path} expected supported {expected['supported']!r}, found {file.result.supported!r}")
        check_snippets(label, path, file.result.go_source, expected.get("must_contain", []), failures)


def check_text_files(expected_items: list[dict[str, Any]], actual: dict[str, Any], label: str, failures: list[str]) -> None:
    for expected in expected_items:
        path = expected.get("output_path")
        if not path:
            failures.append(f"{label}: expected item without output_path")
            continue
        file = actual.get(path)
        if file is None:
            failures.append(f"{label}: missing {path}")
            continue
        if "kind" in expected and file.kind != expected["kind"]:
            failures.append(f"{label}: {path} expected kind {expected['kind']!r}, found {file.kind!r}")
        check_snippets(label, path, file.content, expected.get("must_contain", []), failures)


def check_snippets(label: str, path: str, content: str, snippets: list[str], failures: list[str]) -> None:
    for snippet in snippets:
        if snippet not in content:
            failures.append(f"{label}: {path} missing snippet {snippet!r}")


def contract_row(name: str, source_file: str, observed: dict[str, Any], failures: list[str]) -> dict[str, Any]:
    status = "match" if not failures else "mismatch"
    print(("OK   " if status == "match" else "FAIL ") + name)
    return {
        "name": name,
        "source_file": source_file,
        "status": status,
        "observed": observed,
        "failures": failures,
    }


def render_failures(summary: dict[str, Any]) -> str:
    lines = [
        f"Total contracts:   {summary['total_contracts']}",
        f"Matching contracts:{summary['matching_contracts']:4d}",
        f"Failing contracts: {summary['failing_contracts']:4d}",
    ]
    if summary["failures"]:
        lines.extend(["", "Failures", "--------"])
        for row in summary["failures"]:
            lines.append(row["name"])
            for failure in row["failures"]:
                lines.append(f"  - {failure}")
    return "\n".join(lines) + "\n"


def print_summary(summary: dict[str, Any]) -> None:
    print("Stage-2 Go project contracts")
    print("----------------------------")
    print("Total contracts:   ", summary["total_contracts"])
    print("Matching contracts:", summary["matching_contracts"])
    print("Failing contracts: ", summary["failing_contracts"])


if __name__ == "__main__":
    raise SystemExit(main())
