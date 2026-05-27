from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_MANIFEST = Path("artifacts/fhir-samples/manifest.json")
DEFAULT_PYTHON_ROOT = Path("artifacts/compare-ir/python")
DEFAULT_GO_ROOT = Path("artifacts/compare-ir/go")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate compare IR JSON outputs for Python and Go roots")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="sample manifest JSON")
    parser.add_argument("--python-root", default=str(DEFAULT_PYTHON_ROOT), help="root for Python compare IR JSON files")
    parser.add_argument("--go-root", default=str(DEFAULT_GO_ROOT), help="root for Go compare IR JSON files")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    python_root = Path(args.python_root)
    if not python_root.is_absolute():
        python_root = (repo_root / python_root).resolve()

    go_root = Path(args.go_root)
    if not go_root.is_absolute():
        go_root = (repo_root / go_root).resolve()

    manifest = load_manifest(manifest_path)

    generated = 0
    failed_python = 0
    failed_go = 0
    skipped = 0

    for sample in manifest["samples"]:
        if sample.get("skip"):
            skipped += 1
            continue

        source_path = (repo_root / sample["source_file"]).resolve()
        python_rel = Path(sample["python_ir_file"])
        go_rel = Path(sample.get("go_ir_file", sample["python_ir_file"]))

        python_out = python_root / python_rel
        go_out = go_root / go_rel

        python_out.parent.mkdir(parents=True, exist_ok=True)
        go_out.parent.mkdir(parents=True, exist_ok=True)

        python_ok = run_python_export(repo_root, source_path, python_out)
        go_ok = run_go_export(repo_root, source_path, go_out)
        if not python_ok:
            failed_python += 1
        if not go_ok:
            failed_go += 1
        generated += 1

    print("Generate compare IR samples")
    print("---------------------------")
    print("Manifest: ", manifest_path)
    print("Generated:", generated)
    print("Skipped:  ", skipped)
    print("Python export failures:", failed_python)
    print("Go export failures:    ", failed_go)
    print("Python root:", python_root)
    print("Go root:    ", go_root)
    return 0


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest must contain a samples list")
    validate_manifest_policy(manifest)
    return manifest


def validate_manifest_policy(manifest: dict) -> None:
    policy = manifest.get("policy")
    if policy is None:
        return
    samples = manifest["samples"]
    active_names = [sample.get("name") for sample in samples if not sample.get("skip")]
    skipped_names = [sample.get("name") for sample in samples if sample.get("skip")]

    expected_active = policy.get("active_samples")
    if expected_active is not None and len(active_names) != expected_active:
        raise ValueError(
            f"manifest policy violation: expected {expected_active} active samples, found {len(active_names)}"
        )

    expected_skipped = policy.get("skipped_samples")
    if expected_skipped is not None and sorted(skipped_names) != sorted(expected_skipped):
        raise ValueError(
            "manifest policy violation: skipped samples must be exactly "
            f"{sorted(expected_skipped)!r}, found {sorted(skipped_names)!r}"
        )


def run_python_export(repo_root: Path, source_file: Path, out_file: Path) -> bool:
    command = [
        sys.executable,
        "-m",
        "freehold",
        "compare-ir",
        "--profile",
        "v1",
        str(source_file),
        "--output",
        str(out_file),
    ]
    result = subprocess.run(command, cwd=repo_root)
    if result.returncode != 0:
        print(f"[WARN] Python compare-ir export failed: {source_file}")
        return False
    return True


def run_go_export(repo_root: Path, source_file: Path, out_file: Path) -> bool:
    command = [
        "go",
        "run",
        "./cmd/go-compare-ir",
        "--profile",
        "v1",
        "--out",
        str(out_file),
        str(source_file),
    ]
    result = subprocess.run(command, cwd=repo_root / "go-frontend")
    if result.returncode != 0:
        print(f"[WARN] Go compare-ir export failed: {source_file}")
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
