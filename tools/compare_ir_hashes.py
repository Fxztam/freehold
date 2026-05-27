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
MISSING = object()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare SHA-256 hashes for Python IR and Go IR sample outputs")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="sample manifest JSON")
    parser.add_argument("--python-root", default=str(DEFAULT_PYTHON_ROOT), help="root containing Python IR sample JSON files")
    parser.add_argument("--go-root", default=str(DEFAULT_GO_ROOT), help="root containing Go IR sample JSON files")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    parser.add_argument(
        "--comparison",
        choices=("full", "semantic"),
        default="full",
        help="compare full JSON bytes or a compiler-contract semantic projection",
    )
    parser.add_argument(
        "--compact-mismatches",
        action="store_true",
        help="print sorted compact mismatch details to stdout",
    )
    parser.add_argument(
        "--max-differences",
        type=int,
        default=5,
        help="maximum path-based JSON differences to include per mismatch",
    )
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    python_root = Path(args.python_root)
    go_root = Path(args.go_root)
    out_root = Path(args.out)

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    skipped = 0

    for sample in manifest["samples"]:
        row = compare_sample(sample, python_root, go_root, args.comparison, max(1, args.max_differences))
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
        "comparison": args.comparison,
        "mismatches": mismatches,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.json").write_text(json.dumps(sorted_mismatches(mismatches), indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.txt").write_text(render_report(summary), encoding="utf-8")
    print_report(summary)
    if args.compact_mismatches and mismatches:
        print_compact_mismatches(mismatches)
    return 1 if mismatches else 0


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)
    if manifest.get("schema") != "fhir-samples-v1":
        raise ValueError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    if not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest must contain a samples list")
    validate_manifest_policy(manifest)
    return manifest


def validate_manifest_policy(manifest: dict[str, Any]) -> None:
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


def compare_sample(
    sample: dict[str, Any],
    python_root: Path,
    go_root: Path,
    comparison: str,
    max_differences: int,
) -> dict[str, Any]:
    if sample.get("skip"):
        return {
            "name": sample["name"],
            "source_file": sample["source_file"],
            "python_ir_file": sample.get("python_ir_file", ""),
            "go_ir_file": sample.get("go_ir_file", ""),
            "python_ir_sha256": None,
            "go_ir_sha256": None,
            "comparison": comparison,
            "status": "skipped",
            "reason": sample.get("skip_reason", "skipped"),
        }

    python_path = python_root / sample["python_ir_file"]
    go_path = go_root / sample.get("go_ir_file", sample["python_ir_file"])

    python_sha256 = file_sha256(python_path) if python_path.exists() else None
    go_sha256 = file_sha256(go_path) if go_path.exists() else None

    python_compare_sha256 = python_sha256
    go_compare_sha256 = go_sha256
    first_difference: dict[str, Any] | None = None
    if comparison == "semantic":
        semantic_report = semantic_compare_report(python_path, go_path, max_differences)
        python_compare_sha256 = semantic_report["python_semantic_sha256"]
        go_compare_sha256 = semantic_report["go_semantic_sha256"]
        first_difference = semantic_report.get("first_difference")

    status = (
        "match"
        if python_compare_sha256 is not None and go_compare_sha256 is not None and python_compare_sha256 == go_compare_sha256
        else "mismatch"
    )
    row = {
        "name": sample["name"],
        "source_file": sample["source_file"],
        "python_ir_file": sample["python_ir_file"],
        "go_ir_file": sample.get("go_ir_file", sample["python_ir_file"]),
        "python_ir_sha256": python_sha256,
        "go_ir_sha256": go_sha256,
        "comparison": comparison,
        "python_compare_sha256": python_compare_sha256,
        "go_compare_sha256": go_compare_sha256,
        "status": status,
    }
    if status == "mismatch":
        row["first_difference"] = first_difference or first_difference_report(python_path, go_path, max_differences)
    return row


def semantic_compare_report(python_path: Path, go_path: Path, max_differences: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "python_semantic_sha256": None,
        "go_semantic_sha256": None,
        "first_difference": None,
    }
    if not python_path.exists() or not go_path.exists():
        report["first_difference"] = first_difference_report(python_path, go_path, max_differences)
        return report
    try:
        python_projection = semantic_projection(load_json(python_path))
    except Exception as exc:
        report["first_difference"] = {
            "path": "$",
            "reason": "python_semantic_projection_error",
            "python_value": f"{type(exc).__name__}: {exc}",
            "go_value": display_json_value(str(go_path)),
        }
        return report
    try:
        go_projection = semantic_projection(load_json(go_path))
    except Exception as exc:
        report["python_semantic_sha256"] = json_sha256(python_projection)
        report["first_difference"] = {
            "path": "$",
            "reason": "go_semantic_projection_error",
            "python_value": display_json_value(str(python_path)),
            "go_value": f"{type(exc).__name__}: {exc}",
        }
        return report

    report["python_semantic_sha256"] = json_sha256(python_projection)
    report["go_semantic_sha256"] = json_sha256(go_projection)
    if report["python_semantic_sha256"] != report["go_semantic_sha256"]:
        differences = json_differences(python_projection, go_projection, max_differences)
        if differences:
            first_difference = differences[0].copy()
            first_difference["differences"] = differences
            report["first_difference"] = first_difference
    return report


def semantic_projection(ir: dict[str, Any]) -> dict[str, Any]:
    module = ir.get("module", {})
    analysis = ir.get("analysis", {})
    return {
        "schema": ir.get("schema"),
        "language_version": ir.get("language_version"),
        "module": {
            "name": module.get("name"),
            "imports": sorted((semantic_import(item) for item in module.get("imports", [])), key=sort_key),
            "declarations": [semantic_declaration(item) for item in module.get("declarations", [])],
        },
        "analysis": semantic_analysis(analysis),
    }


def semantic_import(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"module": item, "exposing": []}
    return {
        "kind": item.get("kind"),
        "module": item.get("module"),
        "exposing": sorted(item.get("exposing", [])),
    }


def semantic_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "types": sorted((semantic_type_def(item) for item in analysis.get("types", [])), key=sort_key),
        "records": sorted((semantic_record_def(item) for item in analysis.get("records", [])), key=sort_key),
        "errors": sorted((semantic_error_def(item) for item in analysis.get("errors", [])), key=sort_key),
        "routines": sorted((semantic_routine_signature(item) for item in analysis.get("routines", [])), key=sort_key),
    }


def semantic_declaration(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    kind = item.get("kind")
    if kind == "RoutineDecl":
        return {
            "kind": kind,
            "routine_kind": item.get("routine_kind"),
            "name": item.get("name"),
            "type_params": item.get("type_params", []),
            "is_async": item.get("is_async", False),
            "params": [semantic_param(param) for param in item.get("params", [])],
            "return_type": semantic_value(item.get("return_type")),
            "contracts": semantic_contracts(item),
            "contract_bindings": semantic_value(item.get("contract_bindings")),
            "body": [semantic_statement(stmt) for stmt in item.get("body", [])],
        }
    if kind == "RecordTypeDecl":
        return semantic_record_def(item)
    if kind == "ErrorDecl":
        return semantic_error_def(item)
    if kind in {"TypeDecl", "TypeDef"}:
        return semantic_type_def(item)
    return {"kind": kind, "name": item.get("name")}


def semantic_type_def(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    return {
        "kind": item.get("kind"),
        "name": item.get("name"),
        "base": item.get("base"),
        "base_type": semantic_value(item.get("base_type")),
    }


def semantic_record_def(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    return {
        "kind": item.get("kind"),
        "name": item.get("name"),
        "fields": [
            {
                "name": field.get("name") if isinstance(field, dict) else field,
                "type": field.get("type") if isinstance(field, dict) else None,
                "type_repr": semantic_value(field.get("type_repr")) if isinstance(field, dict) else None,
            }
            for field in item.get("fields", [])
        ],
    }


def semantic_error_def(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    return {
        "kind": item.get("kind"),
        "name": item.get("name"),
    }


def semantic_routine_signature(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    return {
        "kind": item.get("kind"),
        "routine_kind": item.get("routine_kind"),
        "name": item.get("name"),
        "type_params": item.get("type_params", []),
        "is_async": item.get("is_async", False),
        "params": [semantic_param(param) for param in item.get("params", [])],
        "return_type": semantic_value(item.get("return_type")),
        "contracts": semantic_contracts(item),
        "contract_bindings": semantic_value(item.get("contract_bindings")),
    }


def semantic_param(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": item}
    return {
        "name": item.get("name"),
        "type": item.get("type"),
        "type_repr": semantic_value(item.get("type_repr")),
    }


def semantic_contracts(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"requires": [], "ensures": [], "aborts": []}
    contracts = item.get("contracts") or {}
    return {
        "requires": [semantic_value(clause) for clause in contracts.get("requires", item.get("requires", []))],
        "ensures": [semantic_value(clause) for clause in contracts.get("ensures", item.get("ensures", []))],
        "aborts": [semantic_value(clause) for clause in contracts.get("aborts", item.get("aborts", []))],
    }


def semantic_statement(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"kind": item}
    kind = item.get("kind")
    result: dict[str, Any] = {"kind": kind}
    if kind == "LetStmt":
        result.update({"name": item.get("name"), "type": semantic_value(item.get("type")), "value": semantic_value(item.get("value"))})
    elif kind == "AssignStmt":
        result.update({"target": item.get("target") or item.get("name"), "value": semantic_value(item.get("value"))})
    elif kind == "FieldAssignStmt":
        result.update({"path": item.get("path"), "value": semantic_value(item.get("value"))})
    elif kind in {"CallStmt", "ReturnPlain", "ReturnOk", "ReturnErr", "CheckStmt", "AbortStmt"}:
        result.update(semantic_value(item))
    elif kind == "IfStmt":
        result.update(
            {
                "condition": semantic_value(item.get("condition")),
                "then_body": [semantic_statement(stmt) for stmt in item.get("then_body", [])],
                "else_body": [semantic_statement(stmt) for stmt in item.get("else_body", [])],
            }
        )
    elif kind == "WhileStmt":
        result.update(
            {
                "condition": semantic_value(item.get("condition")),
                "invariants": [semantic_value(clause) for clause in item.get("invariants", [])],
                "variant": semantic_value(item.get("variant")),
                "body": [semantic_statement(stmt) for stmt in item.get("body", [])],
            }
        )
    elif kind == "CaseStmt":
        result.update(
            {
                "subject": semantic_value(item.get("subject")),
                "branches": [semantic_case_branch(branch) for branch in item.get("branches", [])],
                "default_body": [semantic_statement(stmt) for stmt in item.get("default_body", [])],
            }
        )
    else:
        result.update(semantic_value(item))
    return result


def semantic_case_branch(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"pattern": semantic_value(item), "body": []}
    return {
        "pattern": semantic_value(item.get("pattern")),
        "body": [semantic_statement(stmt) for stmt in item.get("body", [])],
    }


def semantic_value(value: Any) -> Any:
    if isinstance(value, list):
        return [semantic_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key in sorted(value):
        if key in {"span", "range", "location", "source_span", "source_range"}:
            continue
        kept[key] = semantic_value(value[key])
    return kept


def sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def first_difference_report(python_path: Path, go_path: Path, max_differences: int) -> dict[str, Any]:
    if not python_path.exists() or not go_path.exists():
        return {
            "path": "$",
            "reason": "missing_file",
            "python_value": display_json_value(str(python_path) if python_path.exists() else MISSING),
            "go_value": display_json_value(str(go_path) if go_path.exists() else MISSING),
        }
    try:
        python_json = load_json(python_path)
    except Exception as exc:
        return {
            "path": "$",
            "reason": "python_json_parse_error",
            "python_value": f"{type(exc).__name__}: {exc}",
            "go_value": display_json_value(str(go_path)),
        }
    try:
        go_json = load_json(go_path)
    except Exception as exc:
        return {
            "path": "$",
            "reason": "go_json_parse_error",
            "python_value": display_json_value(str(python_path)),
            "go_value": f"{type(exc).__name__}: {exc}",
        }

    differences = json_differences(python_json, go_json, max_differences)
    if not differences:
        return {
            "path": "$",
            "reason": "json_equal_hash_diff",
            "python_value": display_json_value("JSON values are equal; byte representation differs"),
            "go_value": display_json_value("JSON values are equal; byte representation differs"),
            "differences": [],
        }
    report = differences[0].copy()
    report["differences"] = differences
    return report


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def json_differences(python_value: Any, go_value: Any, max_differences: int) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    collect_json_differences(python_value, go_value, "$", differences, max_differences)
    return differences


def collect_json_differences(
    python_value: Any,
    go_value: Any,
    path: str,
    differences: list[dict[str, Any]],
    max_differences: int,
) -> None:
    if len(differences) >= max_differences:
        return
    difference = first_json_difference(python_value, go_value, path)
    if difference is None:
        return
    if type(python_value) is not type(go_value) or not isinstance(python_value, (dict, list)):
        differences.append(difference)
        return
    if isinstance(python_value, dict):
        keys = sorted(set(python_value) | set(go_value))
        for key in keys:
            next_path = f"{path}.{escape_json_path_key(key)}"
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
            python_item = python_value[index] if index < len(python_value) else MISSING
            go_item = go_value[index] if index < len(go_value) else MISSING
            differences.append(json_difference(f"{path}[{index}]", "list_length_mismatch", python_item, go_item))


def first_json_difference(python_value: Any, go_value: Any, path: str) -> dict[str, Any] | None:
    if type(python_value) is not type(go_value):
        return json_difference(path, "type_mismatch", python_value, go_value)
    if isinstance(python_value, dict):
        keys = sorted(set(python_value) | set(go_value))
        for key in keys:
            next_path = f"{path}.{escape_json_path_key(key)}"
            if key not in python_value:
                return json_difference(next_path, "missing_in_python", MISSING, go_value[key])
            if key not in go_value:
                return json_difference(next_path, "missing_in_go", python_value[key], MISSING)
            difference = first_json_difference(python_value[key], go_value[key], next_path)
            if difference is not None:
                return difference
        return None
    if isinstance(python_value, list):
        for index, (python_item, go_item) in enumerate(zip(python_value, go_value)):
            difference = first_json_difference(python_item, go_item, f"{path}[{index}]")
            if difference is not None:
                return difference
        if len(python_value) != len(go_value):
            index = min(len(python_value), len(go_value))
            python_item = python_value[index] if index < len(python_value) else MISSING
            go_item = go_value[index] if index < len(go_value) else MISSING
            return json_difference(f"{path}[{index}]", "list_length_mismatch", python_item, go_item)
        return None
    if python_value != go_value:
        return json_difference(path, "value_mismatch", python_value, go_value)
    return None


def json_difference(path: str, reason: str, python_value: Any, go_value: Any) -> dict[str, Any]:
    return {
        "path": path,
        "reason": reason,
        "python_value": display_json_value(python_value),
        "go_value": display_json_value(go_value),
    }


def escape_json_path_key(key: str) -> str:
    if re_identifier_key(key):
        return key
    return json.dumps(key, ensure_ascii=False)


def re_identifier_key(key: str) -> bool:
    return bool(key) and (key[0].isalpha() or key[0] == "_") and all(char.isalnum() or char == "_" for char in key)


def display_json_value(value: Any, max_length: int = 180) -> str:
    if value is MISSING:
        return "<missing>"
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) > max_length:
        return rendered[: max_length - 3] + "..."
    return rendered


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
        f"Comparison mode:    {summary.get('comparison', 'full')}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in sorted_mismatches(summary["mismatches"]):
            lines.append(f"{mismatch['name']} => {mismatch['python_ir_file']} vs {mismatch['go_ir_file']}")
            first_difference = mismatch.get("first_difference") or {}
            if first_difference:
                lines.append(f"  first difference: {first_difference.get('path', '$')} ({first_difference.get('reason', 'unknown')})")
                lines.append(f"  python: {first_difference.get('python_value', '')}")
                lines.append(f"  go:     {first_difference.get('go_value', '')}")
                differences = first_difference.get("differences") or []
                if len(differences) > 1:
                    lines.append("  path diffs:")
                    for difference in differences:
                        lines.append(
                            f"    {difference.get('path', '$')} ({difference.get('reason', 'unknown')}): "
                            f"python={difference.get('python_value', '')} go={difference.get('go_value', '')}"
                        )
    return "\n".join(lines) + "\n"


def sorted_mismatches(mismatches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(mismatches, key=lambda mismatch: (mismatch.get("name", ""), mismatch.get("python_ir_file", "")))


def print_report(summary: dict[str, Any]) -> None:
    print("Compare IR sample hashes")
    print("------------------------")
    print("Total samples:     ", summary["total_samples"])
    print("Matching samples:  ", summary["matching_samples"])
    print("Mismatching samples:", summary["mismatching_samples"])
    print("Skipped samples:   ", summary["skipped_samples"])
    print("Comparison mode:   ", summary.get("comparison", "full"))


def print_compact_mismatches(mismatches: list[dict[str, Any]]) -> None:
    print()
    print("Compact mismatches")
    print("------------------")
    for mismatch in sorted_mismatches(mismatches):
        first_difference = mismatch.get("first_difference") or {}
        print(
            f"{mismatch['name']}: {first_difference.get('path', '$')} "
            f"({first_difference.get('reason', 'unknown')}) "
            f"python={first_difference.get('python_value', '')} go={first_difference.get('go_value', '')}"
        )


if __name__ == "__main__":
    raise SystemExit(main())