from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_MANIFEST = Path("artifacts/source-map/compiler_v1/manifest.json")
DEFAULT_PYTHON_ROOT = Path("artifacts/source-map/compiler_v1/python")
DEFAULT_GO_ROOT = Path("artifacts/source-map/compiler_v1/go")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fh-source-map-v0 JSON outputs for Python and Go roots")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="sample manifest JSON")
    parser.add_argument("--python-root", default=str(DEFAULT_PYTHON_ROOT), help="root for Python source-map JSON files")
    parser.add_argument("--go-root", default=str(DEFAULT_GO_ROOT), help="root for Go source-map JSON files")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    manifest_path = resolve_path(repo_root, Path(args.manifest))
    python_root = resolve_path(repo_root, Path(args.python_root))
    go_root = resolve_path(repo_root, Path(args.go_root))

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
        output_rel = Path(sample.get("source_map_file", sample["python_ir_file"]))
        python_out = python_root / output_rel
        go_out = go_root / output_rel
        python_out.parent.mkdir(parents=True, exist_ok=True)
        go_out.parent.mkdir(parents=True, exist_ok=True)

        python_ok = run_python_export(repo_root, source_path, python_out)
        go_ok = run_go_export(repo_root, source_path, go_out)
        if not python_ok:
            failed_python += 1
        if not go_ok:
            failed_go += 1
        generated += 1

    print("Generate source-map samples")
    print("---------------------------")
    print("Manifest: ", manifest_path)
    print("Generated:", generated)
    print("Skipped:  ", skipped)
    print("Python export failures:", failed_python)
    print("Go export failures:    ", failed_go)
    print("Python root:", python_root)
    print("Go root:    ", go_root)
    return 1 if failed_python or failed_go else 0


def resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest must contain a samples list")
    return manifest


def run_python_export(repo_root: Path, source_file: Path, out_file: Path) -> bool:
    command = [sys.executable, "-m", "freehold", "source-map", str(source_file), "--output", str(out_file)]
    result = subprocess.run(command, cwd=repo_root)
    if result.returncode != 0:
        print(f"[WARN] Python source-map export failed: {source_file}")
        return False
    return True


def run_go_export(repo_root: Path, source_file: Path, out_file: Path) -> bool:
    command = ["go", "run", "./cmd/go-source-map", "--out", str(out_file), str(source_file)]
    result = subprocess.run(command, cwd=repo_root / "go-frontend")
    if result.returncode != 0:
        print(f"[WARN] Go source-map export failed: {source_file}")
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
