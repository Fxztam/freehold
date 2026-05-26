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
    ImportDecl,
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
FREEHOLD_LANGUAGE_VERSION = "freehold-v1"


def export_verified_program(verified: VerifiedProgram) -> dict[str, Any]:
    return {
        "schema": FH_IR_SCHEMA,
        "language_version": FREEHOLD_LANGUAGE_VERSION,
        "module": export_program(verified.ast),
        "analysis": {
            "types": [export_type_def(verified.types[name]) for name in sorted(verified.types)],
            "records": [export_record_def(verified.records[name]) for name in sorted(verified.records)],
            "errors": sorted(verified.errors),
            "routines": [export_routine_decl(verified.routines[name]) for name in sorted(verified.routines)],
            "services": [export_service_decl(verified.services[name]) for name in sorted(verified.services)],
            "proof_obligations": [dict(item) for item in verified.proof_obligations],
            "flow_summaries": [export_flow_summary(verified.flow_summaries[name]) for name in sorted(verified.flow_summaries)],
        },
    }


def export_program(program: Program) -> dict[str, Any]:
    return {
        "name": program.module_name,
        "imports": [export_import_decl(import_decl) for import_decl in sorted_imports(program.imports or [])],
        "declarations": [export_declaration(declaration) for declaration in sorted_declarations(program.declarations)],
    }


def export_fhir_json(verified: VerifiedProgram) -> str:
    return json.dumps(export_verified_program(verified), indent=2, ensure_ascii=False) + "\n"


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
    item: dict[str, Any] = {"name": type_def.name, "base": type_def.base}
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
        "name": record_def.name,
        "fields": [{"name": field_name, "type": record_def.fields[field_name]} for field_name in sorted(record_def.fields)],
        "proto_fields": [{"name": field_name, "id": proto_fields[field_name]} for field_name in sorted(proto_fields)],
    }


def sorted_record_fields(fields: list[Any]) -> list[Any]:
    return sorted(fields, key=lambda item: getattr(item, "name", ""))


def export_record_field(field: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"name": field.name, "type": field.type_name}
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
        "response_type": rpc.response_type,
    }


def export_routine_decl(routine: RoutineDecl) -> dict[str, Any]:
    return {
        "kind": "RoutineDecl",
        "routine_kind": routine.kind,
        "name": routine.name,
        "type_params": sorted(routine.type_params or []),
        "is_async": routine.is_async,
        "params": [export_param(param) for param in routine.params],
        "return_type": export_type_ref(routine.return_type),
        "requires": [export_expr(expr) for expr in routine.requires],
        "aborts": [export_abort_clause(clause) for clause in routine.aborts],
        "ensures": [export_expr(expr) for expr in routine.ensures],
        "body": [export_stmt(stmt) for stmt in routine.body],
    }


def export_param(param: Param) -> dict[str, Any]:
    return {"name": param.name, "type": param.type_name}


def export_abort_clause(clause: AbortClause) -> dict[str, Any]:
    item: dict[str, Any] = {"error": clause.error_name}
    if clause.condition is not None:
        item["condition"] = export_expr(clause.condition)
    return item


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
        return {"kind": "ReturnError", "error": value.error_name}
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
    if isinstance(expr, UnaryExpr):
        return {"kind": "UnaryExpr", "op": expr.op, "value": export_expr(expr.expr)}
    if isinstance(expr, BinaryExpr):
        return {"kind": "BinaryExpr", "op": expr.op, "left": export_expr(expr.left), "right": export_expr(expr.right)}
    if expr is None:
        return {"kind": "NullExpr"}
    raise TypeError(f"unsupported expression for FH-IR export: {type(expr).__name__}")


def export_type_ref(type_ref: TypeRef | None) -> dict[str, Any]:
    if type_ref is None:
        return {"kind": "Void"}
    if isinstance(type_ref, TypeName):
        return {"kind": "TypeName", "name": type_ref.name}
    if isinstance(type_ref, ResultTypeName):
        return {"kind": "ResultTypeName", "ok_type": export_type_ref(type_ref.ok_type), "error_type": type_ref.error_type}
    if isinstance(type_ref, ArrayTypeName):
        return {"kind": "ArrayTypeName", "element_type": type_ref.element_type, "size": type_ref.size}
    if isinstance(type_ref, ArrayLiteralType):
        return {"kind": "ArrayLiteralType", "element_type": type_ref.element_type, "size": type_ref.size}
    if isinstance(type_ref, AwaitableType):
        return {"kind": "AwaitableType", "inner_type": export_type_ref(type_ref.inner_type)}
    raise TypeError(f"unsupported type reference for FH-IR export: {type(type_ref).__name__}")


def export_type_ref_name(name: str) -> str:
    return name


def export_flow_summary(summary: RoutineFlowSummary) -> dict[str, Any]:
    return {
        "routine_name": summary.routine_name,
        "routine_kind": summary.routine_kind,
        "normal_return_possible": summary.normal_return_possible,
        "guaranteed_exit": summary.guaranteed_exit,
        "declared_aborts": sorted(summary.declared_aborts),
        "emitted_aborts": sorted(summary.emitted_aborts),
        "called_routines": sorted(summary.called_routines),
        "propagated_aborts": sorted(summary.propagated_aborts),
    }


def export_proof_obligation(item: dict[str, Any]) -> dict[str, Any]:
    return dict(item)
