from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.grpc_codegen import generate_proto_source


DEFAULT_ROOT = Path("tests/language_modules")
DEFAULT_OUT = Path("artifacts/grpc-proto")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and compare gRPC proto artifacts for Freehold language modules")
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
            if case.get("kind") != "valid_grpc_proto":
                continue
            row = run_case(module_dir, case, out_root)
            rows.append(row)
            if row["status"] != "match":
                mismatches.append(row)

    summary = {
        "total_cases": len(rows),
        "matching_proto": len(rows) - len(mismatches),
        "mismatching_proto": len(mismatches),
        "mismatches": mismatches,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_all.json", rows)
    write_json(out_root / "_summary.json", summary)
    write_text_report(out_root / "_mismatches.txt", summary)
    print_summary(summary)
    return 1 if mismatches else 0


def run_case(module_dir: Path, case: dict[str, Any], out_root: Path) -> dict[str, Any]:
    source_path = module_dir / case["file"]
    expected_path = module_dir / case["expected_proto"]
    actual = generate_proto_source(source_path.read_text(encoding="utf-8"))
    expected = expected_path.read_text(encoding="utf-8") if expected_path.exists() else ""
    artifact_path = out_root / module_dir.name / source_path.parent.name / f"{source_path.stem}.proto"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(actual, encoding="utf-8")

    status = "match" if normalize(actual) == normalize(expected) else "mismatch"
    row = {
        "case": f"{module_dir.name}/{source_path.parent.name}/{source_path.name}",
        "name": case.get("name", source_path.stem),
        "status": status,
        "source_file": display_path(source_path),
        "artifact_file": display_path(artifact_path),
        "expected_proto": display_path(expected_path),
    }
    print("OK   " if status == "match" else "FAIL ", row["case"])
    print("WRITE", artifact_path)
    return row


def normalize(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"Total cases:       {summary['total_cases']}",
        f"Matching proto:    {summary['matching_proto']}",
        f"Mismatching proto: {summary['mismatching_proto']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            lines.append(f"{mismatch['case']} => {mismatch['artifact_file']} != {mismatch['expected_proto']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print("Generate gRPC proto artifacts")
    print("-----------------------------")
    print("Total cases:      ", summary["total_cases"])
    print("Matching proto:   ", summary["matching_proto"])
    print("Mismatching proto:", summary["mismatching_proto"])


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def looks_like_numbered_module(name: str) -> bool:
    return len(name) >= 3 and name[:2].isdigit() and name[2] == "_"


if __name__ == "__main__":
    raise SystemExit(main())
