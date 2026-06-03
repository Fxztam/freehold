from __future__ import annotations

import json
from typing import Any

from freehold.core.ast import (
    AbortClause,
    AbortStmt,
    ArrayLiteralExpr,
    ArrayLiteralType,
    ArrayTypeName,
    AssignStmt,
    AwaitExpr,
    AwaitableType,
    BinaryExpr,
    BoolExpr,
    CallExpr,
    CallStmt,
    CaseStmt,
    CheckStmt,
    DoubleExpr,
    ErrorDecl,
    FieldAccessExpr,
    FieldAssignStmt,
    IfStmt,
    ExistsExpr,
    ForAllExpr,
    ImportDecl,
    IsExpr,
    IndexExpr,
    IndexedFieldAccessExpr,
    LetStmt,
    NamedArg,
    NumberExpr,
    Param,
    Program,
    RecordLiteralExpr,
    RecordTypeDecl,
    ResultTypeName,
    ReturnError,
    ReturnOk,
    ReturnPlain,
    ReturnStmt,
    RoutineDecl,
    ScopeStmt,
    ServiceDecl,
    SpecialResultExpr,
    StringExpr,
    TypeDecl,
    TypeName,
    TypeRef,
    UnaryExpr,
    VarExpr,
    WhileStmt,
)
from freehold.core.control_flow import RoutineFlowSummary
from freehold.core.verifier import VerifiedProgram

FH_IR_SCHEMA = "fh-ir-v0"
FH_IR_SCHEMA_V1 = "fh-ir-v1"
FH_IR_PROFILE = "fh-ir"
FREEHOLD_LANGUAGE_VERSION = "freehold-v1"
FH_IR_SCHEMA_VERSION_V0 = {"major": 0, "minor": 1, "patch": 0}
FH_IR_SCHEMA_VERSION_V1 = {"major": 1, "minor": 0, "patch": 0}

NODE_DOCUMENT_V0 = "FhirDocumentV0"
NODE_DOCUMENT_V1 = "FhirDocumentV1"
NODE_PROJECT = "ProjectGraph"
NODE_MODULE = "Module"
NODE_MODULE_ENTRY = "ModuleEntry"
NODE_ANALYSIS = "AnalysisReport"
NODE_VERIFIER = "VerifierReport"
NODE_IMPORT_EDGE = "ImportEdge"
NODE_RUNTIME_MODULE = "RuntimeModule"
NODE_TYPE_DEF = "TypeDef"
NODE_RECORD_DEF = "RecordDef"
NODE_RECORD_FIELD_DEF = "RecordFieldDef"
NODE_ERROR_DEF = "ErrorDef"
NODE_PROOF_OBLIGATION = "ProofObligation"
NODE_FLOW_SUMMARY = "RoutineFlowSummary"
NODE_CONTRACT_CLAUSE = "ContractClause"
NODE_CONTRACT_BINDINGS = "ContractBindings"
NODE_CONTRACT_BINDING = "ContractBinding"
NODE_ABORT_CONTRACT_CLAUSE = "AbortContractClause"
NODE_ERROR_REF = "ErrorRef"
NODE_SOURCE_AST = "SourceAst"
NODE_SEMANTIC_IR = "SemanticIr"


def export_verified_program(verified: VerifiedProgram) -> dict[str, Any]:
    source_ast = {
        "node": NODE_SOURCE_AST,
        "module": export_program(verified.ast),
    }
    semantic_ir = {
        "node": NODE_SEMANTIC_IR,
        "analysis": export_analysis(verified),
    }
    return {
        "node": NODE_DOCUMENT_V0,
        "schema_profile": FH_IR_PROFILE,
        "schema": FH_IR_SCHEMA,
        "schema_version": dict(FH_IR_SCHEMA_VERSION_V0),
        "language_version": FREEHOLD_LANGUAGE_VERSION,
        "source_ast": source_ast,
        "semantic_ir": semantic_ir,
        "module": source_ast["module"],
        "analysis": semantic_ir["analysis"],
    }


def export_verified_project(
    entry_module_name: str,
    resolved_modules: dict[str, Any],
    runtime_modules: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    runtime_modules = runtime_modules or {}
    module_names = sorted(name for name in resolved_modules if getattr(resolved_modules[name], "verified", None) is not None)

    modules: list[dict[str, Any]] = []
    import_graph: list[dict[str, Any]] = []
    runtime_used: set[str] = set()

    for module_name in module_names:
        resolved = resolved_modules[module_name]
        verified = resolved.verified
        source_ast = {
            "node": NODE_SOURCE_AST,
            "module": export_program(verified.ast),
        }
        semantic_ir = {
            "node": NODE_SEMANTIC_IR,
            "analysis": export_analysis(verified),
        }
        modules.append(
            {
                "node": NODE_MODULE_ENTRY,
                "name": module_name,
                "source_ast": source_ast,
                "semantic_ir": semantic_ir,
                "module": source_ast["module"],
                "analysis": semantic_ir["analysis"],
            }
        )

        for import_decl in sorted_imports(verified.ast.imports or []):
            is_runtime = import_decl.module_name in runtime_modules
            if is_runtime:
                runtime_used.add(import_decl.module_name)
            exposing = sorted(import_decl.exposing)
            import_graph.append(
                {
                    "node": NODE_IMPORT_EDGE,
                    "from_module": module_name,
                    "to_module": import_decl.module_name,
                    "is_runtime": is_runtime,
                    "exposing": exposing,
                    "qualified_exposing": [f"{import_decl.module_name}.{symbol_name}" for symbol_name in exposing],
                }
            )

    runtime_entries = [
        {
            "node": NODE_RUNTIME_MODULE,
            "name": module_name,
            "exports": sorted(runtime_modules[module_name]),
        }
        for module_name in sorted(runtime_used)
    ]

    return {
        "node": NODE_DOCUMENT_V1,
        "schema_profile": FH_IR_PROFILE,
        "schema": FH_IR_SCHEMA_V1,
        "schema_version": dict(FH_IR_SCHEMA_VERSION_V1),
        "language_version": FREEHOLD_LANGUAGE_VERSION,
        "entry_module": entry_module_name,
        "project": {
            "node": NODE_PROJECT,
            "module_order": module_names,
            "modules": modules,
            "import_graph": import_graph,
            "runtime_modules": runtime_entries,
        },
    }


def export_program(program: Program) -> dict[str, Any]:
    return {
        "node": NODE_MODULE,
        "name": program.module_name,
        "imports": [export_import_decl(import_decl) for import_decl in sorted_imports(program.imports or [])],
        "declarations": [export_declaration(declaration) for declaration in sorted_declarations(program.declarations)],
    }


def export_fhir_json(verified: VerifiedProgram) -> str:
    return json.dumps(export_verified_program(verified), indent=2, ensure_ascii=False) + "\n"


def export_fhir_project_json(
    entry_module_name: str,
    resolved_modules: dict[str, Any],
    runtime_modules: dict[str, set[str]] | None = None,
) -> str:
    return json.dumps(
        export_verified_project(entry_module_name, resolved_modules, runtime_modules),
        indent=2,
        ensure_ascii=False,
    ) + "\n"


def export_analysis(verified: VerifiedProgram) -> dict[str, Any]:
    errors = sorted(verified.errors)
    proof_obligations = [export_proof_obligation(item) for item in sorted(verified.proof_obligations, key=canonical_json_key)]
    flow_summaries = [export_flow_summary(verified.flow_summaries[name]) for name in sorted(verified.flow_summaries)]
    return {
        "node": NODE_ANALYSIS,
        "types": [export_type_def(verified.types[name]) for name in sorted(verified.types)],
        "records": [export_record_def(verified.records[name]) for name in sorted(verified.records)],
        "errors": errors,
        "error_defs": [export_error_def(error_name) for error_name in errors],
        "routines": [export_routine_decl(verified.routines[name]) for name in sorted(verified.routines)],
        "services": [export_service_decl(verified.services[name]) for name in sorted(verified.services)],
        "proof_obligations": proof_obligations,
        "flow_summaries": flow_summaries,
        "verifier": {
            "node": NODE_VERIFIER,
            "proof_obligations": proof_obligations,
            "flow_summaries": flow_summaries,
        },
    }


def canonical_json_key(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def sorted_imports(imports: list[ImportDecl]) -> list[ImportDecl]:
    return sorted(imports, key=lambda item: (item.module_name, tuple(sorted(item.exposing))))


def sorted_declarations(declarations: list[Any]) -> list[Any]:
    return sorted(declarations, key=lambda item: (declaration_sort_key(item), declaration_name(item)))


def declaration_sort_key(declaration: Any) -> int:
    if isinstance(declaration, TypeDecl):
        return 0
    if isinstance(declaration, RecordTypeDecl):
        return 1
    if isinstance(declaration, ErrorDecl):
        return 2
    if isinstance(declaration, ServiceDecl):
        return 3
    if isinstance(declaration, RoutineDecl):
        return 4
    return 9


def declaration_name(declaration: Any) -> str:
    return getattr(declaration, "name", "")


def export_import_decl(import_decl: ImportDecl) -> dict[str, Any]:
    return {
        "kind": "ImportDecl",
        "module": import_decl.module_name,
        "exposing": sorted(import_decl.exposing),
    }


def export_declaration(declaration: Any) -> dict[str, Any]:
    if isinstance(declaration, TypeDecl):
        return export_type_decl(declaration)
    if isinstance(declaration, RecordTypeDecl):
        return export_record_type_decl(declaration)
    if isinstance(declaration, ErrorDecl):
        return {"kind": "ErrorDecl", "name": declaration.name}
    if isinstance(declaration, ServiceDecl):
        return export_service_decl(declaration)
    if isinstance(declaration, RoutineDecl):
        return export_routine_decl(declaration)
    raise TypeError(f"unsupported declaration for FH-IR export: {type(declaration).__name__}")


def export_type_decl(declaration: TypeDecl) -> dict[str, Any]:
    item: dict[str, Any] = {"kind": "TypeDecl", "name": declaration.name, "base": declaration.base}
    if declaration.min_value is not None:
        item["min_value"] = declaration.min_value
    if declaration.max_value is not None:
        item["max_value"] = declaration.max_value
    return item


def export_type_def(type_def: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"kind": NODE_TYPE_DEF, "name": type_def.name, "base": type_def.base, "base_type": export_type_name_ref(type_def.base)}
    if getattr(type_def, "min_value", None) is not None:
        item["min_value"] = type_def.min_value
    if getattr(type_def, "max_value", None) is not None:
        item["max_value"] = type_def.max_value
    return item


def export_record_type_decl(declaration: RecordTypeDecl) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": "RecordTypeDecl",
        "name": declaration.name,
        "fields": [export_record_field(field) for field in sorted_record_fields(declaration.fields)],
    }
    if declaration.type_params:
        item["type_params"] = sorted(declaration.type_params)
    return item


def export_record_def(record_def: Any) -> dict[str, Any]:
    proto_fields = getattr(record_def, "proto_fields", None) or {}
    return {
        "kind": NODE_RECORD_DEF,
        "name": record_def.name,
        "fields": [
            {
                "kind": NODE_RECORD_FIELD_DEF,
                "name": field_name,
                "type": record_def.fields[field_name],
                "type_repr": export_type_name_ref(record_def.fields[field_name]),
            }
            for field_name in sorted(record_def.fields)
        ],
        "proto_fields": [{"name": field_name, "id": proto_fields[field_name]} for field_name in sorted(proto_fields)],
    }


def sorted_record_fields(fields: list[Any]) -> list[Any]:
    return sorted(fields, key=lambda item: getattr(item, "name", ""))


def export_record_field(field: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"name": field.name, "type": field.type_name, "type_repr": export_type_name_ref(field.type_name)}
    if getattr(field, "proto_id", None) is not None:
        item["proto_id"] = field.proto_id
    return item


def export_service_decl(service: ServiceDecl) -> dict[str, Any]:
    return {"kind": "ServiceDecl", "name": service.name, "rpcs": [export_rpc_decl(rpc) for rpc in sorted(service.rpcs, key=lambda item: item.name)]}


def export_rpc_decl(rpc: Any) -> dict[str, Any]:
    return {
        "kind": "RpcDecl",
        "name": rpc.name,
        "request_name": rpc.request_name,
        "request_type": rpc.request_type,
        "request_type_repr": export_type_name_ref(rpc.request_type),
        "response_type": rpc.response_type,
        "response_type_repr": export_type_name_ref(rpc.response_type),
        "request_stream": getattr(rpc, "request_stream", False),
        "response_stream": getattr(rpc, "response_stream", False),
    }


def export_routine_decl(routine: RoutineDecl) -> dict[str, Any]:
    requires = [export_expr(expr) for expr in routine.requires]
    ensures = [export_expr(expr) for expr in routine.ensures]
    aborts = [export_abort_clause(clause) for clause in routine.aborts]
    contract_bindings = export_contract_bindings(routine.return_type)
    return {
        "kind": "RoutineDecl",
        "routine_kind": routine.kind,
        "name": routine.name,
        "type_params": sorted(routine.type_params or []),
        "is_async": routine.is_async,
        "params": [export_param(param) for param in routine.params],
        "return_type": export_type_ref(routine.return_type),
        "requires": requires,
        "aborts": aborts,
        "ensures": ensures,
        "contracts": {
            "requires": [export_contract_clause("requires", index, condition) for index, condition in enumerate(requires)],
            "ensures": [export_contract_clause("ensures", index, condition) for index, condition in enumerate(ensures)],
            "aborts": aborts,
        },
        "contract_bindings": contract_bindings,
        "body": [export_stmt(stmt) for stmt in routine.body],
    }


def export_param(param: Param) -> dict[str, Any]:
    return {"name": param.name, "type": param.type_name, "type_repr": export_type_name_ref(param.type_name)}


def export_contract_clause(role: str, index: int, condition: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": NODE_CONTRACT_CLAUSE,
        "role": role,
        "index": index,
        "condition": condition,
    }


def export_contract_bindings(return_type: TypeRef | None) -> dict[str, Any]:
    ok_type, error_type = extract_result_type_components(return_type)
    is_result = ok_type is not None and error_type is not None
    has_return = return_type is not None
    result_binding_type = export_type_ref(return_type)
    value_binding_type = export_type_ref(ok_type if ok_type is not None else return_type)
    error_binding_ref = export_error_ref(error_type) if error_type is not None else None

    return {
        "kind": NODE_CONTRACT_BINDINGS,
        "is_result_return": is_result,
        "contexts": {
            "requires": {
                "result": False,
                "success": False,
                "failure": False,
                "value": False,
                "error": False,
            },
            "ensures": {
                "result": True,
                "success": is_result,
                "failure": is_result,
                "value": has_return,
                "error": is_result,
            },
            "aborts": {
                "result": False,
                "success": False,
                "failure": False,
                "value": False,
                "error": False,
            },
        },
        "bindings": [
            {
                "kind": NODE_CONTRACT_BINDING,
                "name": "result",
                "available": True,
                "type": result_binding_type,
            },
            {
                "kind": NODE_CONTRACT_BINDING,
                "name": "success",
                "available": is_result,
                "type": {"kind": "TypeName", "name": "Boolean"},
            },
            {
                "kind": NODE_CONTRACT_BINDING,
                "name": "failure",
                "available": is_result,
                "type": {"kind": "TypeName", "name": "Boolean"},
            },
            {
                "kind": NODE_CONTRACT_BINDING,
                "name": "value",
                "available": has_return,
                "type": value_binding_type,
            },
            {
                "kind": NODE_CONTRACT_BINDING,
                "name": "error",
                "available": is_result,
                "type": export_type_name_ref(error_type) if error_type is not None else {"kind": "Void"},
                "error_ref": error_binding_ref,
            },
        ],
        "result_value_binding": {
            "name": "value",
            "available": has_return,
            "type": value_binding_type,
        },
        "result_error_binding": {
            "name": "error",
            "available": is_result,
            "type": export_type_name_ref(error_type) if error_type is not None else {"kind": "Void"},
            "error_ref": error_binding_ref,
        },
    }


def extract_result_type_components(return_type: TypeRef | None) -> tuple[TypeRef | None, str | None]:
    if isinstance(return_type, ResultTypeName):
        return return_type.ok_type, return_type.error_type
    return None, None


def export_abort_clause(clause: AbortClause) -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": NODE_ABORT_CONTRACT_CLAUSE,
        "error": clause.error_name,
        "error_ref": export_error_ref(clause.error_name),
    }
    if clause.condition is not None:
        item["condition"] = export_expr(clause.condition)
    return item


def export_error_ref(error_name: str) -> dict[str, Any]:
    return {"kind": NODE_ERROR_REF, "name": error_name}


def export_error_def(error_name: str) -> dict[str, Any]:
    return {"kind": NODE_ERROR_DEF, "name": error_name}


def export_stmt(stmt: Any) -> dict[str, Any]:
    if isinstance(stmt, LetStmt):
        return {"kind": "LetStmt", "name": stmt.name, "type": export_type_ref(stmt.type_ref), "value": export_expr(stmt.expr)}
    if isinstance(stmt, AssignStmt):
        return {"kind": "AssignStmt", "name": stmt.name, "value": export_expr(stmt.expr)}
    if isinstance(stmt, FieldAssignStmt):
        return {"kind": "FieldAssignStmt", "path": list(stmt.path), "value": export_expr(stmt.expr)}
    if isinstance(stmt, ReturnStmt):
        return {"kind": "ReturnStmt", "value": export_return_value(stmt.value)}
    if isinstance(stmt, AbortStmt):
        return {"kind": "AbortStmt", "error": stmt.error_name}
    if isinstance(stmt, CheckStmt):
        return {"kind": "CheckStmt", "condition": export_expr(stmt.expr)}
    if isinstance(stmt, CallStmt):
        return {"kind": "CallStmt", "name": stmt.name, "args": [export_call_arg(arg) for arg in stmt.args]}
    if isinstance(stmt, IfStmt):
        return {
            "kind": "IfStmt",
            "condition": export_expr(stmt.condition),
            "then_body": [export_stmt(child) for child in stmt.then_body],
            "else_body": [export_stmt(child) for child in stmt.else_body],
        }
    if isinstance(stmt, WhileStmt):
        item = {
            "kind": "WhileStmt",
            "condition": export_expr(stmt.condition),
            "invariants": [export_expr(expr) for expr in stmt.invariants],
            "body": [export_stmt(child) for child in stmt.body],
        }
        if stmt.variant is not None:
            item["variant"] = export_expr(stmt.variant)
        return item
    if isinstance(stmt, CaseStmt):
        return {
            "kind": "CaseStmt",
            "value": export_expr(stmt.expr),
            "branches": [{"value": export_expr(branch.value), "body": [export_stmt(child) for child in branch.body]} for branch in stmt.branches],
            "default_body": [export_stmt(child) for child in stmt.default_body],
        }
    if isinstance(stmt, ScopeStmt):
        return {
            "kind": "ScopeStmt",
            "name": stmt.name,
            "spawn_body": [export_stmt(child) for child in stmt.spawn_body],
            "join_body": [export_stmt(child) for child in stmt.join_body],
            "result_body": [export_stmt(child) for child in stmt.result_body],
        }
    raise TypeError(f"unsupported statement for FH-IR export: {type(stmt).__name__}")


def export_return_value(value: Any) -> dict[str, Any]:
    if isinstance(value, ReturnPlain):
        return {"kind": "ReturnPlain", "value": export_expr(value.expr)}
    if isinstance(value, ReturnOk):
        return {"kind": "ReturnOk", "value": export_expr(value.expr)}
    if isinstance(value, ReturnError):
        return {"kind": "ReturnError", "error": value.error_name, "error_ref": export_error_ref(value.error_name)}
    return {"kind": "ReturnValue", "value": export_expr(value)}


def export_call_arg(arg: Any) -> dict[str, Any]:
    if isinstance(arg, NamedArg):
        return {"kind": "NamedArg", "name": arg.name, "value": export_expr(arg.expr)}
    return {"kind": "PositionalArg", "value": export_expr(arg)}


def export_expr(expr: Any) -> dict[str, Any]:
    if isinstance(expr, StringExpr):
        return {"kind": "StringExpr", "value": expr.value}
    if isinstance(expr, NumberExpr):
        return {"kind": "NumberExpr", "value": expr.value}
    if isinstance(expr, DoubleExpr):
        return {"kind": "DoubleExpr", "value": expr.value}
    if isinstance(expr, BoolExpr):
        return {"kind": "BoolExpr", "value": expr.value}
    if isinstance(expr, SpecialResultExpr):
        return {"kind": "SpecialResultExpr", "name": expr.name}
    if isinstance(expr, VarExpr):
        return {"kind": "VarExpr", "name": expr.name}
    if isinstance(expr, FieldAccessExpr):
        return {"kind": "FieldAccessExpr", "path": list(expr.path)}
    if isinstance(expr, CallExpr):
        item: dict[str, Any] = {"kind": "CallExpr", "name": expr.name, "args": [export_call_arg(arg) for arg in expr.args]}
        if expr.type_args:
            item["type_args"] = [export_type_ref_name(type_arg) for type_arg in expr.type_args]
        return item
    if isinstance(expr, AwaitExpr):
        return {"kind": "AwaitExpr", "value": export_expr(expr.expr)}
    if isinstance(expr, RecordLiteralExpr):
        return {"kind": "RecordLiteralExpr", "type": expr.type_name, "args": [export_call_arg(arg) for arg in expr.args]}
    if isinstance(expr, ArrayLiteralExpr):
        return {"kind": "ArrayLiteralExpr", "items": [export_expr(item) for item in expr.items]}
    if isinstance(expr, IndexExpr):
        return {"kind": "IndexExpr", "name": expr.name, "index": export_expr(expr.index)}
    if isinstance(expr, IndexedFieldAccessExpr):
        return {"kind": "IndexedFieldAccessExpr", "name": expr.name, "index": export_expr(expr.index), "fields": list(expr.fields)}
    if isinstance(expr, ForAllExpr):
        return {
            "kind": "ForAllExpr",
            "var_name": expr.var_name,
            "lower": export_expr(expr.lower),
            "upper": export_expr(expr.upper),
            "expr": export_expr(expr.expr),
        }
    if isinstance(expr, ExistsExpr):
        return {
            "kind": "ExistsExpr",
            "var_name": expr.var_name,
            "lower": export_expr(expr.lower),
            "upper": export_expr(expr.upper),
            "expr": export_expr(expr.expr),
        }
    if isinstance(expr, UnaryExpr):
        return {"kind": "UnaryExpr", "op": expr.op, "value": export_expr(expr.expr)}
    if isinstance(expr, BinaryExpr):
        return {"kind": "BinaryExpr", "op": expr.op, "left": export_expr(expr.left), "right": export_expr(expr.right)}
    if isinstance(expr, IsExpr):
        return {"kind": "IsExpr", "left": export_expr(expr.left), "right": expr.right}
    if expr is None:
        return {"kind": "NullExpr"}
    raise TypeError(f"unsupported expression for FH-IR export: {type(expr).__name__}")


def export_type_ref(type_ref: TypeRef | None) -> dict[str, Any]:
    if type_ref is None:
        return {"kind": "Void"}
    if isinstance(type_ref, TypeName):
        return export_type_name_ref(type_ref.name)
    if isinstance(type_ref, ResultTypeName):
        return {
            "kind": "ResultTypeName",
            "ok_type": export_type_ref(type_ref.ok_type),
            "error_type": type_ref.error_type,
            "error_ref": export_error_ref(type_ref.error_type),
        }
    if isinstance(type_ref, ArrayTypeName):
        return {"kind": "ArrayTypeName", "element_type": type_ref.element_type, "element_type_repr": export_type_name_ref(type_ref.element_type), "size": type_ref.size}
    if isinstance(type_ref, ArrayLiteralType):
        return {
            "kind": "ArrayLiteralType",
            "element_type": type_ref.element_type,
            "element_type_repr": export_type_name_ref(type_ref.element_type),
            "size": type_ref.size,
        }
    if isinstance(type_ref, AwaitableType):
        return {"kind": "AwaitableType", "inner_type": export_type_ref(type_ref.inner_type)}
    raise TypeError(f"unsupported type reference for FH-IR export: {type(type_ref).__name__}")


def export_type_ref_name(name: str) -> str:
    return name


def export_type_name_ref(type_name: str) -> dict[str, Any]:
    base_name, generic_args = split_generic_type(type_name)
    if generic_args is None:
        return {"kind": "TypeName", "name": type_name}
    if base_name == "Array" and len(generic_args) == 2 and generic_args[1].strip().isdigit():
        return {
            "kind": "ArrayTypeName",
            "element_type": generic_args[0].strip(),
            "element_type_repr": export_type_name_ref(generic_args[0].strip()),
            "size": int(generic_args[1].strip()),
        }
    if base_name == "Result" and len(generic_args) == 2:
        error_name = generic_args[1].strip()
        return {
            "kind": "ResultTypeName",
            "ok_type": export_type_name_ref(generic_args[0].strip()),
            "error_type": error_name,
            "error_ref": export_error_ref(error_name),
        }
    if base_name == "Awaitable" and len(generic_args) == 1:
        return {
            "kind": "AwaitableType",
            "inner_type": export_type_name_ref(generic_args[0].strip()),
        }
    return {
        "kind": "GenericTypeName",
        "name": base_name,
        "args": [export_type_name_ref(arg.strip()) for arg in generic_args],
        "text": type_name,
    }


def split_generic_type(type_name: str) -> tuple[str, list[str] | None]:
    left = type_name.find("<")
    if left <= 0 or not type_name.endswith(">"):
        return type_name, None
    base = type_name[:left].strip()
    inner = type_name[left + 1 : -1]
    return base, split_top_level_csv(inner)


def split_top_level_csv(value: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(value):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def export_flow_summary(summary: RoutineFlowSummary) -> dict[str, Any]:
    return {
        "kind": NODE_FLOW_SUMMARY,
        "routine_name": summary.routine_name,
        "routine_kind": summary.routine_kind,
        "normal_return_possible": summary.normal_return_possible,
        "guaranteed_exit": summary.guaranteed_exit,
        "declared_aborts": sorted(summary.declared_aborts),
        "declared_abort_refs": [export_error_ref(name) for name in sorted(summary.declared_aborts)],
        "emitted_aborts": sorted(summary.emitted_aborts),
        "emitted_abort_refs": [export_error_ref(name) for name in sorted(summary.emitted_aborts)],
        "called_routines": sorted(summary.called_routines),
        "propagated_aborts": sorted(summary.propagated_aborts),
        "propagated_abort_refs": [export_error_ref(name) for name in sorted(summary.propagated_aborts)],
    }


def export_proof_obligation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": NODE_PROOF_OBLIGATION,
        "data": canonicalize(dict(item)),
    }
