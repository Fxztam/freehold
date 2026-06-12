from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("artifacts/source-map/compiler_v1/manifest.json")
DEFAULT_PYTHON_ROOT = Path("artifacts/source-map/compiler_v1/python")
DEFAULT_GO_ROOT = Path("artifacts/source-map/compiler_v1/go")
DEFAULT_OUT_ROOT = Path("artifacts/source-map/compiler_v1/report")
MISSING = object()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Python and Go fh-source-map-v0 contract projections")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="sample manifest JSON")
    parser.add_argument("--python-root", default=str(DEFAULT_PYTHON_ROOT), help="root containing Python source-map JSON files")
    parser.add_argument("--go-root", default=str(DEFAULT_GO_ROOT), help="root containing Go source-map JSON files")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    parser.add_argument("--max-differences", type=int, default=5, help="maximum JSON differences to include per mismatch")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    manifest = load_manifest(resolve_path(repo_root, Path(args.manifest)))
    python_root = resolve_path(repo_root, Path(args.python_root))
    go_root = resolve_path(repo_root, Path(args.go_root))
    out_root = resolve_path(repo_root, Path(args.out))

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    skipped = 0
    for sample in manifest["samples"]:
        row = compare_sample(sample, python_root, go_root, max(1, args.max_differences))
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
        "comparison": "source-map-contract",
        "mismatches": mismatches,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.json").write_text(json.dumps(sorted_mismatches(mismatches), indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.txt").write_text(render_report(summary), encoding="utf-8")
    print_report(summary)
    return 1 if mismatches else 0


def resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest must contain a samples list")
    return manifest


def compare_sample(sample: dict[str, Any], python_root: Path, go_root: Path, max_differences: int) -> dict[str, Any]:
    output_rel = Path(sample.get("source_map_file", sample.get("python_ir_file", sample["name"] + ".json")))
    if sample.get("skip"):
        return {
            "name": sample["name"],
            "source_file": sample["source_file"],
            "source_map_file": str(output_rel),
            "status": "skipped",
            "reason": sample.get("skip_reason", "skipped"),
        }

    python_path = python_root / output_rel
    go_path = go_root / output_rel
    row: dict[str, Any] = {
        "name": sample["name"],
        "source_file": sample["source_file"],
        "source_map_file": str(output_rel),
        "python_source_map_sha256": file_sha256(python_path) if python_path.exists() else None,
        "go_source_map_sha256": file_sha256(go_path) if go_path.exists() else None,
        "comparison": "source-map-contract",
    }
    if not python_path.exists() or not go_path.exists():
        row["status"] = "mismatch"
        row["first_difference"] = missing_file_difference(python_path, go_path)
        return row

    try:
        python_projection = source_map_projection(load_json(python_path))
        go_projection = source_map_projection(load_json(go_path))
    except Exception as exc:
        row["status"] = "mismatch"
        row["first_difference"] = {"path": "$", "reason": "projection_error", "python_value": type(exc).__name__, "go_value": str(exc)}
        return row

    row["python_contract_sha256"] = json_sha256(python_projection)
    row["go_contract_sha256"] = json_sha256(go_projection)
    row["status"] = "match" if row["python_contract_sha256"] == row["go_contract_sha256"] else "mismatch"
    if row["status"] != "match":
        differences = json_differences(python_projection, go_projection, max_differences)
        row["first_difference"] = differences[0].copy() if differences else {"path": "$", "reason": "unknown_mismatch"}
        if differences:
            row["first_difference"]["differences"] = differences
    return row


def source_map_projection(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": doc.get("schema"),
        "language_version": doc.get("language_version"),
        "purpose": doc.get("purpose"),
        "entry_module": doc.get("entry_module"),
        "module_order": list_value(doc.get("module_order")),
        "modules": [module_projection(module) for module in list_value(doc.get("modules"))],
    }


def module_projection(module: dict[str, Any]) -> dict[str, Any]:
    ast_root = module.get("ast", {})
    return {
        "name": module.get("name"),
        "source_sha256": module.get("source_sha256"),
        "line_count": module.get("line_count"),
        "source_lines": list_value(module.get("source_lines")),
        "ast": top_level_shape(ast_root),
    }


def top_level_shape(node: dict[str, Any]) -> dict[str, Any]:
    declarations = [child for child in list_value(node.get("children")) if source_child_is_top_level(child)]
    return {
        "kind": node.get("kind"),
        "name": node.get("name"),
        "declarations": [top_level_declaration_shape(child) for child in declarations],
    }


def source_child_is_top_level(child: dict[str, Any]) -> bool:
    return child.get("kind") in {"ImportDecl", "TypeDecl", "RecordTypeDecl", "ErrorDecl", "ServiceDecl", "RoutineDecl"}


def top_level_declaration_shape(node: dict[str, Any]) -> dict[str, Any]:
    kind = node.get("kind")
    shape: dict[str, Any] = {
        "kind": kind,
        "name": node.get("name") or node.get("module"),
        "line": (node.get("span") or {}).get("line"),
    }
    if kind == "ImportDecl":
        shape["module"] = node.get("module")
        shape["exposing"] = sorted(list_value(node.get("exposing")))
    if kind == "RoutineDecl":
        shape["routine_kind"] = node.get("routine_kind")
        shape["is_async"] = node.get("is_async", False)
        shape["params"] = [param_shape(child) for child in list_value(node.get("children")) if child.get("kind") == "Param"]
    if kind == "RecordTypeDecl":
        shape["fields"] = [param_shape(child) for child in list_value(node.get("children")) if child.get("kind") in {"Param", "RecordField"}]
    if kind == "TypeDecl":
        shape["base"] = node.get("base")
        shape["min_value"] = node.get("min_value")
        shape["max_value"] = node.get("max_value")
    return shape


def param_shape(node: dict[str, Any]) -> dict[str, Any]:
    return {"name": node.get("name")}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def missing_file_difference(python_path: Path, go_path: Path) -> dict[str, Any]:
    return {
        "path": "$",
        "reason": "missing_file",
        "python_value": str(python_path) if python_path.exists() else "<missing>",
        "go_value": str(go_path) if go_path.exists() else "<missing>",
    }


def json_differences(python_value: Any, go_value: Any, max_differences: int) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    collect_json_differences(python_value, go_value, "$", differences, max_differences)
    return differences


def collect_json_differences(python_value: Any, go_value: Any, path: str, differences: list[dict[str, Any]], max_differences: int) -> None:
    if len(differences) >= max_differences:
        return
    if type(python_value) is not type(go_value):
        differences.append(json_difference(path, "type_mismatch", python_value, go_value))
        return
    if isinstance(python_value, dict):
        keys = sorted(set(python_value) | set(go_value))
        for key in keys:
            next_path = f"{path}.{key}"
            if key not in python_value:
                differences.append(json_difference(next_path, "missing_in_python", MISSING, go_value[key]))
            elif key not in go_value:
                differences.append(json_difference(next_path, "missing_in_go", python_value[key], MISSING))
            else:
                collect_json_differences(python_value[key], go_value[key], next_path, differences, max_differences)
            if len(differences) >= max_differences:
                return
        return
    if isinstance(python_value, list):
        for index, (python_item, go_item) in enumerate(zip(python_value, go_value)):
            collect_json_differences(python_item, go_item, f"{path}[{index}]", differences, max_differences)
            if len(differences) >= max_differences:
                return
        if len(python_value) != len(go_value):
            index = min(len(python_value), len(go_value))
            differences.append(json_difference(f"{path}[{index}]", "list_length_mismatch", len(python_value), len(go_value)))
        return
    if python_value != go_value:
        differences.append(json_difference(path, "value_mismatch", python_value, go_value))


def json_difference(path: str, reason: str, python_value: Any, go_value: Any) -> dict[str, Any]:
    return {"path": path, "reason": reason, "python_value": display_json_value(python_value), "go_value": display_json_value(go_value)}


def display_json_value(value: Any) -> Any:
    if value is MISSING:
        return "<missing>"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def sorted_mismatches(mismatches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(mismatches, key=lambda row: row.get("name", ""))


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "Source-map parity report",
        "------------------------",
        f"Comparison:          {summary['comparison']}",
        f"Total samples:       {summary['total_samples']}",
        f"Matching samples:    {summary['matching_samples']}",
        f"Mismatching samples: {summary['mismatching_samples']}",
        f"Skipped samples:     {summary['skipped_samples']}",
        "",
    ]
    if summary["mismatches"]:
        lines.append("Mismatches:")
        for row in sorted_mismatches(summary["mismatches"]):
            lines.append(f"- {row['name']}: {row.get('first_difference', {}).get('path', '$')} ({row.get('first_difference', {}).get('reason', 'mismatch')})")
    else:
        lines.append("All source-map contract projections match.")
    return "\n".join(lines) + "\n"


def print_report(summary: dict[str, Any]) -> None:
    print("Source-map parity report")
    print("------------------------")
    print("Comparison:         ", summary["comparison"])
    print("Total samples:      ", summary["total_samples"])
    print("Matching samples:   ", summary["matching_samples"])
    print("Mismatching samples:", summary["mismatching_samples"])
    print("Skipped samples:    ", summary["skipped_samples"])
    if summary["mismatches"]:
        print("Mismatches:")
        for row in sorted_mismatches(summary["mismatches"]):
            first = row.get("first_difference", {})
            print(f"- {row['name']}: {first.get('path', '$')} ({first.get('reason', 'mismatch')})")


if __name__ == "__main__":
    raise SystemExit(main())
