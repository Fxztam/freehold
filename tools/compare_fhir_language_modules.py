from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lark.exceptions import UnexpectedInput

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.ast import TypeCheckError
from freehold.core.fhir import export_fhir_json, export_fhir_project_json
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.module_resolver import ModuleResolver
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program

DEFAULT_OUT_ROOT = Path("artifacts/compare-fhir-language-modules")
FORBIDDEN_KEYWORDS = (
    "__dict__",
    "__class__",
    "freehold.core.",
    "<class '",
)
DECLARATION_KIND_ORDER = {
    "TypeDecl": 0,
    "RecordTypeDecl": 1,
    "ErrorDecl": 2,
    "ServiceDecl": 3,
    "RoutineDecl": 4,
}


@dataclass(frozen=True)
class GateCase:
    name: str
    entry: str
    mode: str
    domain: str


STABLE_CASES = [
    GateCase(
        "records_record_declaration",
        "tests/language_modules/05_records/valid/record_declaration.fh",
        "module",
        "records",
    ),
    GateCase(
        "arrays_array_literal",
        "tests/language_modules/06_arrays/valid/array_literal.fh",
        "module",
        "arrays",
    ),
    GateCase(
        "arrays_array_return",
        "tests/language_modules/06_arrays/valid/array_return.fh",
        "module",
        "arrays",
    ),
    GateCase(
        "results_result_array_ok_payload",
        "tests/language_modules/11_errors_results/valid/result_array_ok_payload.fh",
        "module",
        "results",
    ),
    GateCase(
        "contracts_comma_requires_ensures",
        "tests/language_modules/13_contract_blocks/valid/comma_requires_ensures.fh",
        "module",
        "contracts",
    ),
    GateCase(
        "contracts_result_value_field",
        "tests/language_modules/13_contract_blocks/valid/contract_uses_result_value_field.fh",
        "module",
        "contracts",
    ),
    GateCase(
        "imports_plain_import_project",
        "tests/language_modules/02_import/fixtures/valid/plain_import_project/App/Main.fh",
        "project",
        "imports",
    ),
    GateCase(
        "imports_record_type_project",
        "tests/language_modules/03_import_resolution/fixtures/valid/import_record_type/App/Main.fh",
        "project",
        "imports",
    ),
    GateCase(
        "imports_result_error_project",
        "tests/language_modules/03_import_resolution/fixtures/valid/import_result_error/App/Main.fh",
        "project",
        "imports",
    ),
    GateCase(
        "imports_result_array_record_project",
        "tests/language_modules/03_import_resolution/fixtures/valid/import_result_array_record/App/Main.fh",
        "project",
        "imports",
    ),
]

EXPANDED_EXTRA_CASES = [
    GateCase(
        "records_nested_field_access",
        "tests/language_modules/05_records/valid/nested_record_field_access.fh",
        "module",
        "records",
    ),
    GateCase(
        "results_result_value_field_access",
        "tests/language_modules/11_errors_results/valid/result_value_field_access.fh",
        "module",
        "results",
    ),
    GateCase(
        "contracts_qualified_call_inside_contract",
        "tests/language_modules/13_contract_blocks/valid/qualified_call_inside_contract.fh",
        "module",
        "contracts",
    ),
    GateCase(
        "imports_nested_record_field_project",
        "tests/language_modules/03_import_resolution/fixtures/valid/import_nested_record_field_access/App/Main.fh",
        "project",
        "imports",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FH-IR stability for language modules")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    parser.add_argument(
        "--profile",
        choices=("stable", "expanded"),
        default="stable",
        help="coverage profile: stable core domains or expanded set",
    )
    args = parser.parse_args()

    selected_cases = list(STABLE_CASES)
    if args.profile == "expanded":
        selected_cases.extend(EXPANDED_EXTRA_CASES)

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for case in selected_cases:
        row = run_case(case)
        rows.append(row)
        if row["status"] != "match":
            mismatches.append(row)

    summary = {
        "artifact": "compare-fhir-language-modules",
        "profile": args.profile,
        "total_cases": len(rows),
        "matching_cases": len(rows) - len(mismatches),
        "mismatching_cases": len(mismatches),
        "domains": sorted({case.domain for case in selected_cases}),
        "mismatches": mismatches,
    }
    manifest = build_manifest(rows, summary)

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_all.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_root / "_mismatches.txt").write_text(render_report(summary), encoding="utf-8")
    print_summary(summary)
    return 1 if mismatches else 0


def run_case(case: GateCase) -> dict[str, Any]:
    source_path = (REPO_ROOT / case.entry).resolve()
    error: dict[str, str] | None = None
    violations: list[str] = []

    try:
        first = export_case(case, source_path)
        second = export_case(case, source_path)
        deterministic_text = first == second
        if not deterministic_text:
            violations.append("non-deterministic serialization across repeated export")

        document = json.loads(first)
        violations.extend(validate_common_document(document))
        if case.mode == "project":
            violations.extend(validate_project_document(document))
        else:
            violations.extend(validate_module_document(document))
    except (TypeCheckError, UnexpectedInput, ValueError) as exc:
        deterministic_text = False
        document = None
        error = build_error("parse_or_resolver", exc, source_path)
        violations.append("export failed")
    except (OSError, UnicodeError) as exc:
        deterministic_text = False
        document = None
        error = build_error("io", exc, source_path)
        violations.append("export failed")
    except json.JSONDecodeError as exc:
        deterministic_text = False
        document = None
        error = build_error("json_decode", exc, source_path)
        violations.append("export failed")
    except Exception as exc:
        raise RuntimeError(f"unexpected failure while running language-module case: {display_path(source_path)}") from exc

    status = "match" if error is None and not violations else "mismatch"
    row = {
        "case": case.name,
        "domain": case.domain,
        "mode": case.mode,
        "status": status,
        "source_file": display_path(source_path),
        "deterministic_text": deterministic_text,
        "violations": violations,
        "error": error,
        "diagnostic": normalize_diagnostic_error(error),
        "schema": document.get("schema") if isinstance(document, dict) else "",
        "schema_version": document.get("schema_version") if isinstance(document, dict) else {},
    }
    print("OK   " if status == "match" else "FAIL ", case.name)
    return row


def export_case(case: GateCase, source_path: Path) -> str:
    if case.mode == "module":
        source = source_path.read_text(encoding="utf-8")
        verified = verify_program(parse_source(source))
        return export_fhir_json(verified)

    resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
    resolver.resolve_entry(source_path)
    if resolver.entry is None:
        raise RuntimeError("module resolver did not produce an entry module")
    return export_fhir_project_json(resolver.entry.name, resolver.resolved, GO_RUNTIME_MODULE_EXPORTS)


def validate_common_document(document: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    violations.extend(find_forbidden_keys(document))
    violations.extend(find_forbidden_string_markers(document))

    if document.get("schema_profile") != "fh-ir":
        violations.append("schema_profile is not fh-ir")

    schema_version = document.get("schema_version", {})
    if not isinstance(schema_version, dict) or any(key not in schema_version for key in ("major", "minor", "patch")):
        violations.append("schema_version is missing major/minor/patch")

    schema = document.get("schema")
    if schema == "fh-ir-v0":
        analysis = document.get("analysis", {})
        violations.extend(validate_analysis(analysis, scope_label="analysis"))
        verifier = analysis.get("verifier", {})
        if verifier.get("node") != "VerifierReport":
            violations.append("analysis.verifier.node is not VerifierReport")

    return violations


def validate_project_document(document: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    if document.get("node") != "FhirDocumentV1":
        violations.append("document node is not FhirDocumentV1")
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

        source_ast = module.get("source_ast", {})
        if source_ast.get("node") != "SourceAst":
            violations.append(f"module.source_ast.node mismatch: {module.get('name', '<unknown>')}")
        if source_ast.get("module") != module.get("module"):
            violations.append(f"module.source_ast.module alias mismatch: {module.get('name', '<unknown>')}")

        semantic_ir = module.get("semantic_ir", {})
        if semantic_ir.get("node") != "SemanticIr":
            violations.append(f"module.semantic_ir.node mismatch: {module.get('name', '<unknown>')}")
        if semantic_ir.get("analysis") != module.get("analysis"):
            violations.append(f"module.semantic_ir.analysis alias mismatch: {module.get('name', '<unknown>')}")

        module_block = module.get("module", {})
        if module_block.get("node") != "Module":
            violations.append(f"module.node mismatch: {module.get('name', '<unknown>')}")
        violations.extend(validate_module_shape(module_block, f"module[{module.get('name', '<unknown>')}].module"))
        violations.extend(validate_analysis(module.get("analysis", {}), f"module[{module.get('name', '<unknown>')}].analysis"))

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


def validate_module_document(document: dict[str, Any]) -> list[str]:
    violations: list[str] = []

    if document.get("node") != "FhirDocumentV0":
        violations.append("document node is not FhirDocumentV0")
    if document.get("schema") != "fh-ir-v0":
        violations.append("schema is not fh-ir-v0")

    source_ast = document.get("source_ast", {})
    if source_ast.get("node") != "SourceAst":
        violations.append("source_ast.node is not SourceAst")
    if source_ast.get("module") != document.get("module"):
        violations.append("source_ast.module alias mismatch")

    semantic_ir = document.get("semantic_ir", {})
    if semantic_ir.get("node") != "SemanticIr":
        violations.append("semantic_ir.node is not SemanticIr")
    if semantic_ir.get("analysis") != document.get("analysis"):
        violations.append("semantic_ir.analysis alias mismatch")

    violations.extend(validate_module_shape(document.get("module", {}), "module"))
    return violations


def validate_module_shape(module_block: dict[str, Any], scope_label: str) -> list[str]:
    violations: list[str] = []

    imports = module_block.get("imports", [])
    if imports != sorted(imports, key=lambda item: (item.get("module", ""), tuple(item.get("exposing", [])))):
        violations.append(f"{scope_label}.imports order is not stable")

    declarations = module_block.get("declarations", [])
    if declarations != sorted(declarations, key=lambda item: (DECLARATION_KIND_ORDER.get(item.get("kind", ""), 99), item.get("name", ""))):
        violations.append(f"{scope_label}.declarations order is not stable")

    for declaration in declarations:
        if declaration.get("kind") == "RoutineDecl":
            contracts = declaration.get("contracts", {})
            for clause in contracts.get("requires", []):
                if clause.get("kind") != "ContractClause" or clause.get("role") != "requires":
                    violations.append(f"{scope_label}.contracts requires clause is malformed")
            for clause in contracts.get("ensures", []):
                if clause.get("kind") != "ContractClause" or clause.get("role") != "ensures":
                    violations.append(f"{scope_label}.contracts ensures clause is malformed")
            for clause in contracts.get("aborts", []):
                if clause.get("kind") != "AbortContractClause":
                    violations.append(f"{scope_label}.contracts abort clause is malformed")

            contract_bindings = declaration.get("contract_bindings", {})
            if contract_bindings.get("kind") != "ContractBindings":
                violations.append(f"{scope_label}.contract_bindings is missing")
            bindings = contract_bindings.get("bindings", [])
            if [item.get("name") for item in bindings] != ["result", "success", "failure", "value", "error"]:
                violations.append(f"{scope_label}.contract_bindings order is malformed")
            for binding in bindings:
                if binding.get("kind") != "ContractBinding":
                    violations.append(f"{scope_label}.contract binding kind mismatch")
                if "available" not in binding:
                    violations.append(f"{scope_label}.contract binding availability missing")
            if contract_bindings.get("result_value_binding", {}).get("name") != "value":
                violations.append(f"{scope_label}.result_value_binding malformed")
            if contract_bindings.get("result_error_binding", {}).get("name") != "error":
                violations.append(f"{scope_label}.result_error_binding malformed")

    return violations


def validate_analysis(analysis: dict[str, Any], scope_label: str) -> list[str]:
    violations: list[str] = []
    if analysis.get("node") != "AnalysisReport":
        violations.append(f"{scope_label}.node is not AnalysisReport")

    violations.extend(validate_name_order(analysis.get("types", []), f"{scope_label}.types"))
    violations.extend(validate_name_order(analysis.get("records", []), f"{scope_label}.records"))
    violations.extend(validate_name_order(analysis.get("routines", []), f"{scope_label}.routines"))
    violations.extend(validate_name_order(analysis.get("services", []), f"{scope_label}.services"))

    if analysis.get("errors", []) != sorted(analysis.get("errors", [])):
        violations.append(f"{scope_label}.errors order is not stable")

    for type_def in analysis.get("types", []):
        if type_def.get("kind") != "TypeDef":
            violations.append(f"{scope_label}.type kind mismatch: {type_def.get('name', '<unknown>')}")

    for record in analysis.get("records", []):
        if record.get("kind") != "RecordDef":
            violations.append(f"{scope_label}.record kind mismatch: {record.get('name', '<unknown>')}")
        fields = record.get("fields", [])
        if fields != sorted(fields, key=lambda item: item.get("name", "")):
            violations.append(f"{scope_label}.record fields order is not stable: {record.get('name', '<unknown>')}")
        for field in fields:
            if field.get("kind") != "RecordFieldDef":
                violations.append(f"{scope_label}.record field kind mismatch: {record.get('name', '<unknown>')}.{field.get('name', '<unknown>')}")
            if "type_repr" not in field:
                violations.append(f"{scope_label}.record field type_repr missing: {record.get('name', '<unknown>')}.{field.get('name', '<unknown>')}")

    for routine in analysis.get("routines", []):
        return_type = routine.get("return_type", {})
        if not isinstance(return_type, dict) or "kind" not in return_type:
            violations.append(f"{scope_label}.routine return_type missing kind: {routine.get('name', '<unknown>')}")
        contract_bindings = routine.get("contract_bindings", {})
        if contract_bindings.get("kind") != "ContractBindings":
            violations.append(f"{scope_label}.routine contract_bindings missing: {routine.get('name', '<unknown>')}")

    for proof in analysis.get("proof_obligations", []):
        if proof.get("kind") != "ProofObligation":
            violations.append(f"{scope_label}.proof obligation kind mismatch")

    for flow in analysis.get("flow_summaries", []):
        if flow.get("kind") != "RoutineFlowSummary":
            violations.append(f"{scope_label}.flow summary kind mismatch: {flow.get('routine_name', '<unknown>')}")

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


def build_manifest(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    manifest_cases = []
    for row in sorted(rows, key=lambda item: item.get("case", "")):
        manifest_cases.append(
            {
                "case": row.get("case", ""),
                "domain": row.get("domain", ""),
                "mode": row.get("mode", ""),
                "status": row.get("status", ""),
                "schema": row.get("schema", ""),
                "schema_version": row.get("schema_version", {}),
                "diagnostic": row.get("diagnostic"),
                "violations": sorted(row.get("violations", [])),
            }
        )
    return {
        "artifact": summary.get("artifact", "compare-fhir-language-modules"),
        "profile": summary.get("profile", "stable"),
        "domains": summary.get("domains", []),
        "total_cases": summary.get("total_cases", 0),
        "matching_cases": summary.get("matching_cases", 0),
        "mismatching_cases": summary.get("mismatching_cases", 0),
        "cases": manifest_cases,
    }


def normalize_diagnostic_error(error: dict[str, Any] | None) -> dict[str, Any] | None:
    if error is None:
        return None
    raw_message = str(error.get("message", "")).strip()
    normalized_message = normalize_message_text(raw_message)
    location = None
    match = re.search(r"line\s+(\d+):(\d+)", raw_message)
    if match:
        location = {"line": int(match.group(1)), "column": int(match.group(2))}
    return {
        "type": error.get("type", ""),
        "category": error.get("category", ""),
        "message": normalized_message,
        "location": location,
        "context": error.get("context", ""),
    }


def normalize_message_text(message: str) -> str:
    normalized = message.replace("\\", "/")
    repo_root = REPO_ROOT.as_posix()
    normalized = normalized.replace(repo_root, "<repo>")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def build_error(category: str, exc: Exception, context_path: Path) -> dict[str, Any]:
    return {
        "category": category,
        "type": type(exc).__name__,
        "message": str(exc),
        "context": display_path(context_path),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"Profile:          {summary['profile']}",
        f"Total cases:      {summary['total_cases']}",
        f"Matching cases:   {summary['matching_cases']}",
        f"Mismatching cases: {summary['mismatching_cases']}",
        f"Domains:          {', '.join(summary['domains'])}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            lines.append(f"{mismatch['case']} => {', '.join(mismatch['violations']) or 'error'}")
    return "\n".join(lines) + "\n"


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare FH-IR language module stability")
    print("--------------------------------------")
    print("Profile:          ", summary["profile"])
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
