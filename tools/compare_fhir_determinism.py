from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.fhir import export_fhir_json
from freehold.core.module_resolver import ModuleResolver
from tools.verify_compiler_examples import SUPPORTED_EXAMPLES


DEFAULT_OUT_ROOT = Path("artifacts/compare-fhir-determinism")
DEFAULT_CASE_LIMIT = 6
DECLARATION_KIND_ORDER = {
    "TypeDecl": 0,
    "RecordTypeDecl": 1,
    "ErrorDecl": 2,
    "ServiceDecl": 3,
    "RoutineDecl": 4,
}
FORBIDDEN_KEYWORDS = (
    "__dict__",
    "__class__",
    "freehold.core.",
    "<class '",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic FH-IR v0 export profile")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    parser.add_argument("--limit", type=int, default=DEFAULT_CASE_LIMIT, help="number of supported compiler examples to check")
    parser.add_argument("--all", action="store_true", help="check all supported compiler examples")
    args = parser.parse_args()

    out_root = Path(args.out)
    case_limit = len(SUPPORTED_EXAMPLES) if args.all else max(args.limit, 1)
    selected_examples = SUPPORTED_EXAMPLES[:case_limit]

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for example in selected_examples:
        row = run_case(example.name, Path(example.entry))
        rows.append(row)
        if row["status"] != "match":
            mismatches.append(row)

    summary = {
        "total_cases": len(rows),
        "matching_cases": len(rows) - len(mismatches),
        "mismatching_cases": len(mismatches),
        "mismatches": mismatches,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.txt").write_text(render_report(summary), encoding="utf-8")
    print_summary(summary)
    return 1 if mismatches else 0


def run_case(name: str, entry_path: Path) -> dict[str, Any]:
    source_path = (REPO_ROOT / entry_path).resolve()
    error: dict[str, str] | None = None
    violations: list[str] = []

    try:
        first = export_fhir_json(ModuleResolver().verify_entry(source_path))
        second = export_fhir_json(ModuleResolver().verify_entry(source_path))
        deterministic_text = first == second
        if not deterministic_text:
            violations.append("non-deterministic serialization across repeated export")

        document = json.loads(first)
        violations.extend(validate_document(document))
    except Exception as exc:
        deterministic_text = False
        document = None
        error = {"type": type(exc).__name__, "message": str(exc)}
        violations.append("export failed")

    status = "match" if error is None and not violations else "mismatch"
    row = {
        "case": name,
        "status": status,
        "source_file": display_path(source_path),
        "deterministic_text": deterministic_text,
        "violations": violations,
        "error": error,
        "schema": document.get("schema") if isinstance(document, dict) else "",
        "module": document.get("module", {}).get("name", "") if isinstance(document, dict) else "",
    }
    print("OK   " if status == "match" else "FAIL ", name)
    return row


def validate_document(document: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    violations.extend(find_forbidden_keys(document))
    violations.extend(find_forbidden_string_markers(document))

    module = document.get("module", {})
    imports = module.get("imports", [])
    if imports != sorted(imports, key=lambda item: (item.get("module", ""), tuple(item.get("exposing", [])))):
        violations.append("module.imports order is not stable")

    declarations = module.get("declarations", [])
    if declarations != sorted(declarations, key=lambda item: (DECLARATION_KIND_ORDER.get(item.get("kind", ""), 99), item.get("name", ""))):
        violations.append("module.declarations order is not stable")

    analysis = document.get("analysis", {})
    violations.extend(validate_name_order(analysis.get("types", []), "analysis.types"))
    violations.extend(validate_name_order(analysis.get("records", []), "analysis.records"))
    if analysis.get("errors", []) != sorted(analysis.get("errors", [])):
        violations.append("analysis.errors order is not stable")
    violations.extend(validate_name_order(analysis.get("routines", []), "analysis.routines"))
    violations.extend(validate_name_order(analysis.get("services", []), "analysis.services"))

    for record in analysis.get("records", []):
        fields = record.get("fields", [])
        if fields != sorted(fields, key=lambda item: item.get("name", "")):
            violations.append(f"record fields order is not stable: {record.get('name', '<unknown>')}")
        proto_fields = record.get("proto_fields", [])
        if proto_fields != sorted(proto_fields, key=lambda item: item.get("name", "")):
            violations.append(f"record proto_fields order is not stable: {record.get('name', '<unknown>')}")

    for service in analysis.get("services", []):
        rpcs = service.get("rpcs", [])
        if rpcs != sorted(rpcs, key=lambda item: item.get("name", "")):
            violations.append(f"service RPC order is not stable: {service.get('name', '<unknown>')}")

    return violations


def validate_name_order(items: list[dict[str, Any]], label: str) -> list[str]:
    if items == sorted(items, key=lambda item: item.get("name", "")):
        return []
    return [f"{label} order is not stable"]


def find_forbidden_keys(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}" if path else key
            lower_key = key.lower()
            if lower_key in {"pos", "position", "line", "column", "offset"}:
                violations.append(f"source-position key present: {key_path}")
            violations.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return violations


def find_forbidden_string_markers(value: Any, path: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, str):
        lowered = value.lower()
        for marker in FORBIDDEN_KEYWORDS:
            if marker.lower() in lowered:
                violations.append(f"python-specific marker found at {path or '<root>'}: {marker}")
                break
    elif isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            violations.extend(find_forbidden_string_markers(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(find_forbidden_string_markers(child, f"{path}[{index}]"))
    return violations


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"Total cases:      {summary['total_cases']}",
        f"Matching cases:   {summary['matching_cases']}",
        f"Mismatching cases: {summary['mismatching_cases']}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            lines.append(f"{mismatch['case']} => {', '.join(mismatch['violations']) or 'error'}")
    return "\n".join(lines) + "\n"


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare FH-IR determinism")
    print("--------------------------")
    print("Total cases:      ", summary["total_cases"])
    print("Matching cases:   ", summary["matching_cases"])
    print("Mismatching cases:", summary["mismatching_cases"])


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
