from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("artifacts/fhir-samples/manifest.json")
DEFAULT_PYTHON_ROOT = Path("artifacts/compare-ir/python")
DEFAULT_GO_ROOT = Path("artifacts/compare-ir/go")
DEFAULT_OUT_ROOT = Path("artifacts/compare-ir/report")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare SHA-256 hashes for Python IR and Go IR sample outputs")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="sample manifest JSON")
    parser.add_argument("--python-root", default=str(DEFAULT_PYTHON_ROOT), help="root containing Python IR sample JSON files")
    parser.add_argument("--go-root", default=str(DEFAULT_GO_ROOT), help="root containing Go IR sample JSON files")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    python_root = Path(args.python_root)
    go_root = Path(args.go_root)
    out_root = Path(args.out)

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    skipped = 0

    for sample in manifest["samples"]:
        row = compare_sample(sample, python_root, go_root)
        rows.append(row)
        if row["status"] == "skipped":
            skipped += 1
            continue
        if row["status"] != "match":
            mismatches.append(row)

    summary = {
        "total_samples": len(rows),
        "matching_samples": sum(1 for row in rows if row["status"] == "match"),
        "mismatching_samples": len(mismatches),
        "skipped_samples": skipped,
        "mismatches": mismatches,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.txt").write_text(render_report(summary), encoding="utf-8")
    print_report(summary)
    return 1 if mismatches else 0


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest must contain a samples list")
    return manifest


def compare_sample(sample: dict[str, Any], python_root: Path, go_root: Path) -> dict[str, Any]:
    if sample.get("skip"):
        return {
            "name": sample["name"],
            "source_file": sample["source_file"],
            "python_ir_file": sample.get("python_ir_file", ""),
            "go_ir_file": sample.get("go_ir_file", ""),
            "python_ir_sha256": None,
            "go_ir_sha256": None,
            "status": "skipped",
            "reason": sample.get("skip_reason", "skipped"),
        }

    python_path = python_root / sample["python_ir_file"]
    go_path = go_root / sample.get("go_ir_file", sample["python_ir_file"])

    python_sha256 = file_sha256(python_path) if python_path.exists() else None
    go_sha256 = file_sha256(go_path) if go_path.exists() else None

    status = "match" if python_sha256 is not None and go_sha256 is not None and python_sha256 == go_sha256 else "mismatch"
    return {
        "name": sample["name"],
        "source_file": sample["source_file"],
        "python_ir_file": sample["python_ir_file"],
        "go_ir_file": sample.get("go_ir_file", sample["python_ir_file"]),
        "python_ir_sha256": python_sha256,
        "go_ir_sha256": go_sha256,
        "status": status,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"Total samples:      {summary['total_samples']}",
        f"Matching samples:   {summary['matching_samples']}",
        f"Mismatching samples: {summary['mismatching_samples']}",
        f"Skipped samples:    {summary['skipped_samples']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            lines.append(f"{mismatch['name']} => {mismatch['python_ir_file']} vs {mismatch['go_ir_file']}")
    return "\n".join(lines) + "\n"


def print_report(summary: dict[str, Any]) -> None:
    print("Compare IR sample hashes")
    print("------------------------")
    print("Total samples:     ", summary["total_samples"])
    print("Matching samples:  ", summary["matching_samples"])
    print("Mismatching samples:", summary["mismatching_samples"])
    print("Skipped samples:   ", summary["skipped_samples"])


if __name__ == "__main__":
    raise SystemExit(main())