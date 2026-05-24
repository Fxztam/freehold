from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.go_codegen import generate_go_file, generate_go_project, generate_go_project_build_files, generate_go_source


DEFAULT_ROOT = Path("tests/language_modules")
DEFAULT_OUT = Path("artifacts/go-codegen")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and compare Go codegen artifacts for Freehold language modules")
    parser.add_argument("root", nargs="?", default=str(DEFAULT_ROOT), help="language_modules root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="artifact output directory")
    args = parser.parse_args()

    root = Path(args.root)
    out_root = Path(args.out)
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for module_dir in sorted(path for path in root.iterdir() if path.is_dir() and looks_like_numbered_module(path.name)):
        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for case in manifest.get("cases", []):
            if case.get("kind") == "valid_go_project_codegen":
                row = run_project_case(module_dir, case, out_root)
                rows.append(row)
                if row["status"] != "match":
                    mismatches.append(row)
                continue
            if case.get("kind") != "valid_go_codegen":
                continue
            row = run_case(module_dir, case, out_root)
            rows.append(row)
            if row["status"] != "match":
                mismatches.append(row)

    summary = {
        "total_cases": len(rows),
        "matching_go": len(rows) - len(mismatches),
        "mismatching_go": len(mismatches),
        "mismatches": mismatches,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_all.json", rows)
    write_json(out_root / "_summary.json", summary)
    write_text_report(out_root / "_mismatches.txt", summary)
    print_summary(summary)
    return 1 if mismatches else 0


def run_case(module_dir: Path, case: dict[str, Any], out_root: Path) -> dict[str, Any]:
    source_path = case_source_path(module_dir, case)
    expected_path = module_dir / case["expected_go"]
    artifact_path = artifact_file_path(out_root, module_dir, case, source_path, ".go")
    json_path = artifact_file_path(out_root, module_dir, case, source_path, ".json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if "root" in case:
            result = generate_go_file(source_path)
        else:
            source = source_path.read_text(encoding="utf-8")
            result = generate_go_source(source)
        actual = result.go_source
        error = None
    except Exception as exc:
        actual = ""
        error = {"type": type(exc).__name__, "message": str(exc)}
        result = None
    expected = expected_path.read_text(encoding="utf-8") if expected_path.exists() else ""
    artifact_path.write_text(actual, encoding="utf-8")
    status = "match" if error is None and normalize(actual) == normalize(expected) else "mismatch"
    row = {
        "case": f"{module_dir.name}/{source_path.parent.name}/{source_path.name}",
        "name": case.get("name", source_path.stem),
        "status": status,
        "source_file": display_path(source_path),
        "artifact_file": display_path(artifact_path),
        "json_file": display_path(json_path),
        "expected_go": display_path(expected_path),
        "supported": bool(result.supported) if result is not None else False,
        "diagnostics": result.diagnostics if result is not None else [],
        "package_path": result.package_path if result is not None else "",
        "imports": result.imports if result is not None else [],
        "error": error,
    }
    write_json(json_path, row | {"go_source": actual})
    print("OK   " if status == "match" else "FAIL ", row["case"])
    print("WRITE", artifact_path)
    print("JSON ", json_path)
    return row


def run_project_case(module_dir: Path, case: dict[str, Any], out_root: Path) -> dict[str, Any]:
    entry_path = module_dir / case["root"] / case["entry"]
    expected_root = module_dir / case["expected_go_dir"]
    artifact_root = out_root / module_dir.name / Path(case["root"]).name / "project"
    json_path = artifact_root / "_project.json"
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    try:
        files = generate_go_project(entry_path)
        build_files = generate_go_project_build_files(files)
        actual = {file.output_path: file.result.go_source for file in files}
        actual.update({file.output_path: file.content for file in build_files})
        error = None
    except Exception as exc:
        files = []
        build_files = []
        actual = {}
        error = {"type": type(exc).__name__, "message": str(exc)}
    expected = {
        path.relative_to(expected_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(path for path in expected_root.rglob("*") if path.is_file())
    } if expected_root.exists() else {}
    for output_path, source in actual.items():
        artifact_path = artifact_root / output_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(source, encoding="utf-8")
    status = "match" if error is None and normalize_project(actual) == normalize_project(expected) else "mismatch"
    row = {
        "case": f"{module_dir.name}/{case['root']}/{case['entry']}",
        "name": case.get("name", entry_path.stem),
        "status": status,
        "source_file": display_path(entry_path),
        "artifact_dir": display_path(artifact_root),
        "json_file": display_path(json_path),
        "expected_go_dir": display_path(expected_root),
        "supported": all(file.result.supported for file in files) if files else False,
        "files": [
            {
                "module": file.module_name,
                "source_file": file.source_file,
                "output_path": file.output_path,
                "supported": file.result.supported,
                "diagnostics": file.result.diagnostics,
            }
            for file in files
        ],
        "build_files": [file.to_json() for file in build_files],
        "error": error,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(json_path, row)
    print("OK   " if status == "match" else "FAIL ", row["case"])
    print("WRITE", artifact_root)
    print("JSON ", json_path)
    return row


def normalize_project(files: dict[str, str]) -> dict[str, str]:
    return {path: normalize(source) for path, source in files.items()}


def case_source_path(module_dir: Path, case: dict[str, Any]) -> Path:
    if "root" in case:
        return module_dir / case["root"] / case["entry"]
    return module_dir / case["file"]


def artifact_file_path(out_root: Path, module_dir: Path, case: dict[str, Any], source_path: Path, suffix: str) -> Path:
    if "root" in case:
        root = module_dir / case["root"]
        relative_entry = source_path.relative_to(root).with_suffix(suffix)
        return out_root / module_dir.name / Path(case["root"]).name / relative_entry
    return out_root / module_dir.name / source_path.parent.name / f"{source_path.stem}{suffix}"


def normalize(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Total cases:    {summary['total_cases']}",
        f"Matching Go:    {summary['matching_go']}",
        f"Mismatching Go: {summary['mismatching_go']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            actual = mismatch.get("artifact_file") or mismatch.get("artifact_dir") or "<no artifact>"
            expected = mismatch.get("expected_go") or mismatch.get("expected_go_dir") or "<no expected>"
            lines.append(f"{mismatch['case']} => {actual} != {expected}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Generate Go codegen artifacts")
    print("-----------------------------")
    print("Total cases:   ", summary["total_cases"])
    print("Matching Go:   ", summary["matching_go"])
    print("Mismatching Go:", summary["mismatching_go"])


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def looks_like_numbered_module(name: str) -> bool:
    return len(name) >= 3 and name[:2].isdigit() and name[2] == "_"


if __name__ == "__main__":
    raise SystemExit(main())
