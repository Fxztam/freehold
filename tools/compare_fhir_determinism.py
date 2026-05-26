from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.fhir import export_fhir_project_json
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
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
    parser = argparse.ArgumentParser(description="Validate deterministic FH-IR v1 project export profile")
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
        first_resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
        first_resolver.resolve_entry(source_path)
        if first_resolver.entry is None:
            raise RuntimeError("module resolver did not produce an entry module")
        first = export_fhir_project_json(first_resolver.entry.name, first_resolver.resolved, GO_RUNTIME_MODULE_EXPORTS)

        second_resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
        second_resolver.resolve_entry(source_path)
        if second_resolver.entry is None:
            raise RuntimeError("module resolver did not produce an entry module")
        second = export_fhir_project_json(second_resolver.entry.name, second_resolver.resolved, GO_RUNTIME_MODULE_EXPORTS)

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
        "entry_module": document.get("entry_module", "") if isinstance(document, dict) else "",
    }
    print("OK   " if status == "match" else "FAIL ", name)
    return row


def validate_document(document: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    violations.extend(find_forbidden_keys(document))
    violations.extend(find_forbidden_string_markers(document))

    if document.get("node") != "FhirDocumentV1":
        violations.append("document node is not FhirDocumentV1")
    if document.get("schema_profile") != "fh-ir":
        violations.append("schema_profile is not fh-ir")

    schema_version = document.get("schema_version", {})
    if not isinstance(schema_version, dict) or any(key not in schema_version for key in ("major", "minor", "patch")):
        violations.append("schema_version is missing major/minor/patch")

    if document.get("schema") != "fh-ir-v1":
        violations.append("schema is not fh-ir-v1")

    project = document.get("project", {})
    if project.get("node") != "ProjectGraph":
        violations.append("project.node is not ProjectGraph")

    module_order = project.get("module_order", [])
    if module_order != sorted(module_order):
        violations.append("project.module_order is not canonical")

    modules = project.get("modules", [])
    if [item.get("name", "") for item in modules] != module_order:
        violations.append("project.modules order does not match project.module_order")

    for module in modules:
        if module.get("node") != "ModuleEntry":
            violations.append(f"project.modules node mismatch: {module.get('name', '<unknown>')}")
        module_block = module.get("module", {})
        if module_block.get("node") != "Module":
            violations.append(f"module.node mismatch: {module.get('name', '<unknown>')}")
        imports = module_block.get("imports", [])
        if imports != sorted(imports, key=lambda item: (item.get("module", ""), tuple(item.get("exposing", [])))):
            violations.append(f"module.imports order is not stable: {module.get('name', '<unknown>')}")

        declarations = module_block.get("declarations", [])
        if declarations != sorted(declarations, key=lambda item: (DECLARATION_KIND_ORDER.get(item.get("kind", ""), 99), item.get("name", ""))):
            violations.append(f"module.declarations order is not stable: {module.get('name', '<unknown>')}")

        analysis = module.get("analysis", {})
        if analysis.get("node") != "AnalysisReport":
            violations.append(f"analysis.node mismatch: {module.get('name', '<unknown>')}")
        violations.extend(validate_name_order(analysis.get("types", []), f"analysis.types[{module.get('name', '<unknown>')}]"))
        violations.extend(validate_name_order(analysis.get("records", []), f"analysis.records[{module.get('name', '<unknown>')}]"))
        if analysis.get("errors", []) != sorted(analysis.get("errors", [])):
            violations.append(f"analysis.errors order is not stable: {module.get('name', '<unknown>')}")
        violations.extend(validate_name_order(analysis.get("routines", []), f"analysis.routines[{module.get('name', '<unknown>')}]"))
        violations.extend(validate_name_order(analysis.get("services", []), f"analysis.services[{module.get('name', '<unknown>')}]"))

        verifier = analysis.get("verifier", {})
        if verifier.get("node") != "VerifierReport":
            violations.append(f"analysis.verifier.node mismatch: {module.get('name', '<unknown>')}")

        for type_def in analysis.get("types", []):
            if type_def.get("kind") != "TypeDef":
                violations.append(f"type kind mismatch: {module.get('name', '<unknown>')}.{type_def.get('name', '<unknown>')}")
            if "base_type" not in type_def:
                violations.append(f"type base_type missing: {module.get('name', '<unknown>')}.{type_def.get('name', '<unknown>')}")

        for record in analysis.get("records", []):
            if record.get("kind") != "RecordDef":
                violations.append(f"record kind mismatch: {module.get('name', '<unknown>')}.{record.get('name', '<unknown>')}")
            fields = record.get("fields", [])
            if fields != sorted(fields, key=lambda item: item.get("name", "")):
                violations.append(f"record fields order is not stable: {record.get('name', '<unknown>')}")
            for field in fields:
                if field.get("kind") != "RecordFieldDef":
                    violations.append(f"record field kind mismatch: {record.get('name', '<unknown>')}.{field.get('name', '<unknown>')}")
                if "type_repr" not in field:
                    violations.append(f"record field type_repr missing: {record.get('name', '<unknown>')}.{field.get('name', '<unknown>')}")
            proto_fields = record.get("proto_fields", [])
            if proto_fields != sorted(proto_fields, key=lambda item: item.get("name", "")):
                violations.append(f"record proto_fields order is not stable: {record.get('name', '<unknown>')}")

        for routine in analysis.get("routines", []):
            contracts = routine.get("contracts", {})
            for clause in contracts.get("requires", []):
                if clause.get("kind") != "ContractClause" or clause.get("role") != "requires":
                    violations.append(f"routine requires contract malformed: {routine.get('name', '<unknown>')}")
            for clause in contracts.get("ensures", []):
                if clause.get("kind") != "ContractClause" or clause.get("role") != "ensures":
                    violations.append(f"routine ensures contract malformed: {routine.get('name', '<unknown>')}")
            for clause in contracts.get("aborts", []):
                if clause.get("kind") != "AbortContractClause":
                    violations.append(f"routine abort contract malformed: {routine.get('name', '<unknown>')}")

        for proof in analysis.get("proof_obligations", []):
            if proof.get("kind") != "ProofObligation":
                violations.append(f"proof obligation kind mismatch: {module.get('name', '<unknown>')}")

        for flow in analysis.get("flow_summaries", []):
            if flow.get("kind") != "RoutineFlowSummary":
                violations.append(f"flow summary kind mismatch: {module.get('name', '<unknown>')}.{flow.get('routine_name', '<unknown>')}")

        for service in analysis.get("services", []):
            rpcs = service.get("rpcs", [])
            if rpcs != sorted(rpcs, key=lambda item: item.get("name", "")):
                violations.append(f"service RPC order is not stable: {service.get('name', '<unknown>')}")
            for rpc in rpcs:
                if "request_type_repr" not in rpc or "response_type_repr" not in rpc:
                    violations.append(f"service RPC type_repr missing: {service.get('name', '<unknown>')}.{rpc.get('name', '<unknown>')}")

    import_graph = project.get("import_graph", [])
    if import_graph != sorted(import_graph, key=lambda item: (item.get("from_module", ""), item.get("to_module", ""), tuple(item.get("exposing", [])))):
        violations.append("project.import_graph order is not canonical")

    for edge in import_graph:
        if edge.get("node") != "ImportEdge":
            violations.append("import_graph edge node is not ImportEdge")
        exposing = edge.get("exposing", [])
        if exposing != sorted(exposing):
            violations.append(f"import_graph exposing order is not stable: {edge.get('from_module', '<unknown>')} -> {edge.get('to_module', '<unknown>')}")
        expected_qualified = [f"{edge.get('to_module', '')}.{symbol_name}" for symbol_name in exposing]
        if edge.get("qualified_exposing", []) != expected_qualified:
            violations.append(f"import_graph qualified_exposing mismatch: {edge.get('from_module', '<unknown>')} -> {edge.get('to_module', '<unknown>')}")

    runtime_modules = project.get("runtime_modules", [])
    if runtime_modules != sorted(runtime_modules, key=lambda item: item.get("name", "")):
        violations.append("project.runtime_modules order is not canonical")
    for runtime_entry in runtime_modules:
        if runtime_entry.get("node") != "RuntimeModule":
            violations.append("runtime module node is not RuntimeModule")
        exports = runtime_entry.get("exports", [])
        if exports != sorted(exports):
            violations.append(f"runtime module exports order is not stable: {runtime_entry.get('name', '<unknown>')}")

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
