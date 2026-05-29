from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.go_codegen import generate_go_project, generate_go_project_build_files, generate_go_project_extra_files


DEFAULT_MANIFEST = Path("artifacts/stage3/compiler_core_v1/manifest.json")
DEFAULT_OUT = Path("artifacts/stage3/compiler_core_v1/report")
DEFAULT_BUILD_ROOT = Path(".tmp/stage3-compiler-core-v1")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Stage-3 compiler_core_v1 contracts")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Stage-3 compiler core manifest")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="report output directory")
    parser.add_argument("--build-root", default=str(DEFAULT_BUILD_ROOT), help="temporary generated Go project root")
    parser.add_argument("--keep-build", action="store_true", help="keep generated Go project for inspection")
    args = parser.parse_args()

    manifest_path = resolve_repo_path(Path(args.manifest))
    out_root = resolve_repo_path(Path(args.out))
    build_root = resolve_repo_path(Path(args.build_root))
    manifest = load_manifest(manifest_path)
    contracts = manifest.get("contracts", [])
    if not isinstance(contracts, list):
        raise ValueError("manifest contracts must be a list")
    expected_count = (manifest.get("policy") or {}).get("total_contracts")
    if expected_count is not None and expected_count != len(contracts):
        raise ValueError(f"manifest policy violation: expected {expected_count} contracts, found {len(contracts)}")

    rows = [verify_contract(contract, build_root) for contract in contracts]
    failures = [row for row in rows if row["status"] != "match"]
    summary = {
        "total_contracts": len(rows),
        "matching_contracts": len(rows) - len(failures),
        "failing_contracts": len(failures),
        "failures": failures,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_all.json", rows)
    write_json(out_root / "_summary.json", summary)
    (out_root / "_failures.txt").write_text(render_failures(summary), encoding="utf-8")
    print_summary(summary)
    if not args.keep_build and build_root.exists():
        shutil.rmtree(build_root)
    return 1 if failures else 0


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "stage3-compiler-core-contracts-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    return manifest


def verify_contract(contract: dict[str, Any], build_root: Path) -> dict[str, Any]:
    name = contract.get("name", "<unnamed>")
    source_file = contract.get("source_file")
    failures: list[str] = []
    if not source_file:
        failures.append("missing source_file")
        return contract_row(name, source_file or "", {}, failures)

    source_path = REPO_ROOT / source_file
    try:
        files = generate_go_project(source_path)
        build_files = generate_go_project_build_files(files, executable_name="stage3_compiler_core_v1", entry_module_name="App.Main")
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
    runtime_golden_result: dict[str, Any] | None = None
    check_project_values(contract, project, failures)
    check_codegen_files(contract.get("files", []), project["files"], "files", failures)
    check_text_files(contract.get("build_files", []), project["build_files"], "build_files", failures)
    check_text_files(contract.get("extra_files", []), project["extra_files"], "extra_files", failures)

    if not failures:
        write_project(build_root, files, build_files, extra_files)
        build_result = subprocess.run(["cmd", "/c", "build.cmd"], cwd=build_root, text=True)
        if build_result.returncode != 0:
            failures.append(f"generated Go project build failed with exit code {build_result.returncode}")
        else:
            runtime_golden_result = check_runtime_golden(contract, build_root, failures)

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
            "runtime_golden": runtime_golden_result,
        },
        failures,
    )


def check_runtime_golden(contract: dict[str, Any], build_root: Path, failures: list[str]) -> dict[str, Any] | None:
    runtime_golden = contract.get("runtime_golden")
    if runtime_golden is None:
        return None
    executable = runtime_golden.get("executable")
    expected_stdout_file = runtime_golden.get("expected_stdout_file")
    if not executable:
        failures.append("runtime_golden: missing executable")
        return {"status": "mismatch"}
    if not expected_stdout_file:
        failures.append("runtime_golden: missing expected_stdout_file")
        return {"status": "mismatch", "executable": executable}

    executable_path = build_root / executable
    expected_path = REPO_ROOT / expected_stdout_file
    if not executable_path.exists():
        failures.append(f"runtime_golden: missing executable {executable}")
        return {"status": "mismatch", "executable": executable, "expected_stdout_file": expected_stdout_file}
    if not expected_path.exists():
        failures.append(f"runtime_golden: missing expected stdout file {expected_stdout_file}")
        return {"status": "mismatch", "executable": executable, "expected_stdout_file": expected_stdout_file}

    result = subprocess.run([str(executable_path)], cwd=build_root, capture_output=True, text=True)
    actual_stdout = normalize_text(result.stdout)
    expected_stdout = normalize_text(expected_path.read_text(encoding="utf-8"))
    status = "match"
    if result.returncode != 0:
        failures.append(f"runtime_golden: executable failed with exit code {result.returncode}")
        status = "mismatch"
    if actual_stdout != expected_stdout:
        failures.append(f"runtime_golden: stdout mismatch for {expected_stdout_file}")
        status = "mismatch"
    return {
        "status": status,
        "executable": executable,
        "expected_stdout_file": expected_stdout_file,
        "actual_stdout_lines": len(actual_stdout.splitlines()),
        "expected_stdout_lines": len(expected_stdout.splitlines()),
    }


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"


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


def write_project(build_root: Path, files: list[Any], build_files: list[Any], extra_files: list[Any]) -> None:
    if build_root.exists():
        shutil.rmtree(build_root)
    for file in files:
        write_text(build_root / file.output_path, file.result.go_source)
    for file in build_files:
        write_text(build_root / file.output_path, file.content)
    for file in extra_files:
        write_text(build_root / file.output_path, file.content)
    
    # Copy fixtures to build_root so dynamic file reading works during verification
    fixtures_src = REPO_ROOT / "bootstrap/compiler_core_v1/fixtures"
    if fixtures_src.exists():
        shutil.copytree(fixtures_src, build_root / "bootstrap/compiler_core_v1/fixtures")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


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
    print("Stage-3 compiler_core_v1 contracts")
    print("----------------------------------")
    print("Total contracts:   ", summary["total_contracts"])
    print("Matching contracts:", summary["matching_contracts"])
    print("Failing contracts: ", summary["failing_contracts"])


if __name__ == "__main__":
    raise SystemExit(main())