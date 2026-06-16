from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from freehold.core.ast import (
    AbortClause,
    AbortStmt,
    ArrayLiteralExpr,
    AssignStmt,
    AwaitExpr,
    BinaryExpr,
    BoolExpr,
    CallExpr,
    CallStmt,
    CaseBranch,
    CaseStmt,
    CheckStmt,
    DoubleExpr,
    ErrorDecl,
    ExistsExpr,
    FieldAccessExpr,
    FieldAssignStmt,
    ForAllExpr,
    GlobalSpec,
    IfStmt,
    ImportDecl,
    IndexExpr,
    IndexedFieldAccessExpr,
    LetStmt,
    MapEntry,
    MapLiteralExpr,
    NamedArg,
    NumberExpr,
    Param,
    PatternBranch,
    PatternExpr,
    Program,
    RecordField,
    RecordLiteralExpr,
    RecordTypeDecl,
    ReturnError,
    ReturnOk,
    ReturnPlain,
    ReturnStmt,
    RoutineDecl,
    ScopeStmt,
    ServiceDecl,
    SourcePos,
    StringExpr,
    TypeDecl,
    UnaryExpr,
    VarExpr,
    WhileStmt,
    type_to_string,
)
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.module_resolver import ModuleResolver, ResolvedModule

SOURCE_MAP_SCHEMA = "fh-source-map-v0"
FREEHOLD_LANGUAGE_VERSION = "freehold-v1"


def export_source_map_json(entry_file: str | Path) -> str:
    resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
    resolver.resolve_entry(entry_file)
    if resolver.entry is None:
        raise RuntimeError("module resolver did not produce an entry module")
    return json.dumps(export_resolved_source_map(resolver.entry.name, resolver.resolved), indent=2, ensure_ascii=False) + "\n"


def export_resolved_source_map(entry_module_name: str, resolved_modules: dict[str, ResolvedModule]) -> dict[str, Any]:
    modules = [export_module_source_map(resolved_modules[name]) for name in sorted(resolved_modules)]
    return {
        "schema": SOURCE_MAP_SCHEMA,
        "language_version": FREEHOLD_LANGUAGE_VERSION,
        "purpose": "source reconstruction sidecar for FH-IR",
        "entry_module": entry_module_name,
        "module_order": [module["name"] for module in modules],
        "modules": modules,
    }


def export_module_source_map(resolved: ResolvedModule) -> dict[str, Any]:
    source = resolved.path.read_text(encoding="utf-8")
    lines = source.splitlines()
    return {
        "name": resolved.name,
        "source_file": str(resolved.path),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "line_count": len(lines),
        "source_lines": lines,
        "ast": export_node(resolved.ast, resolved.name, "module", None, "module", 0, lines),
    }


def export_node(
    node: Any,
    module_name: str,
    path: str,
    parent_id: str | None,
    role: str,
    index: int,
    lines: list[str],
) -> dict[str, Any]:
    node_id = f"{module_name}:{path}"
    item: dict[str, Any] = {
        "id": node_id,
        "parent_id": parent_id,
        "role": role,
        "index": index,
        "kind": type(node).__name__,
        "span": export_span(getattr(node, "pos", None), lines),
    }
    item.update(node_summary(node))
    children = list(iter_children(node))
    if children:
        item["children"] = [
            export_node(child, module_name, f"{path}/{child_role}[{child_index}]", node_id, child_role, child_index, lines)
            for child_role, child_index, child in children
        ]
    else:
        item["children"] = []
    return item


def export_span(pos: SourcePos | None, lines: list[str]) -> dict[str, Any]:
    if pos is None or pos.line is None:
        return {"line": None, "column": None, "line_text": ""}
    line_text = lines[pos.line - 1] if 0 < pos.line <= len(lines) else ""
    return {"line": pos.line, "column": pos.column, "line_text": line_text}


def node_summary(node: Any) -> dict[str, Any]:
    if isinstance(node, Program):
        return {"name": node.module_name}
    if isinstance(node, ImportDecl):
        return {"module": node.module_name, "exposing": list(node.exposing)}
    if isinstance(node, TypeDecl):
        return {"name": node.name, "base": node.base, "min_value": node.min_value, "max_value": node.max_value}
    if isinstance(node, RecordTypeDecl):
        return {"name": node.name, "type_params": list(node.type_params or [])}
    if isinstance(node, RecordField):
        item = {"name": node.name, "type": node.type_name}
        if node.proto_id is not None:
            item["proto_id"] = node.proto_id
        if node.json_name is not None:
            item["json_name"] = node.json_name
        return item
    if isinstance(node, ErrorDecl):
        return {"name": node.name}
    if isinstance(node, ServiceDecl):
        return {"name": node.name}
    if isinstance(node, RoutineDecl):
        return {
            "name": node.name,
            "routine_kind": node.kind,
            "is_async": node.is_async,
            "type_params": list(node.type_params or []),
            "return_type": type_to_string(node.return_type),
        }
    if isinstance(node, Param):
        return {"name": node.name, "type": node.type_name}
    if isinstance(node, GlobalSpec):
        return {"name": node.name, "mode": node.mode}
    if isinstance(node, AbortClause):
        return {"error": node.error_name}
    if isinstance(node, LetStmt):
        return {"name": node.name, "type": type_to_string(node.type_ref)}
    if isinstance(node, AssignStmt):
        return {"name": node.name}
    if isinstance(node, FieldAssignStmt):
        return {"path": list(node.path)}
    if isinstance(node, AbortStmt):
        return {"error": node.error_name}
    if isinstance(node, CallStmt):
        return {"name": node.name, "type_args": list(node.type_args or [])}
    if isinstance(node, ScopeStmt):
        return {"name": node.name}
    if isinstance(node, ReturnError):
        return {"error": node.error_name}
    if isinstance(node, StringExpr):
        return {"value": node.value}
    if isinstance(node, NumberExpr):
        return {"value": node.value}
    if isinstance(node, DoubleExpr):
        return {"value": node.value}
    if isinstance(node, BoolExpr):
        return {"value": node.value}
    if isinstance(node, VarExpr):
        return {"name": node.name}
    if isinstance(node, FieldAccessExpr):
        return {"path": list(node.path)}
    if isinstance(node, CallExpr):
        return {"name": node.name, "type_args": list(node.type_args or [])}
    if isinstance(node, NamedArg):
        return {"name": node.name}
    if isinstance(node, RecordLiteralExpr):
        return {"type": node.type_name}
    if isinstance(node, MapLiteralExpr):
        return {"type": node.type_name}
    if isinstance(node, MapEntry):
        return {"key": node.key}
    if isinstance(node, IndexExpr):
        return {"name": node.name}
    if isinstance(node, IndexedFieldAccessExpr):
        return {"name": node.name, "fields": list(node.fields)}
    if isinstance(node, UnaryExpr):
        return {"op": node.op}
    if isinstance(node, BinaryExpr):
        return {"op": node.op}
    if isinstance(node, ForAllExpr):
        return {"var_name": node.var_name}
    if isinstance(node, ExistsExpr):
        return {"var_name": node.var_name}
    return {}


def iter_children(node: Any) -> list[tuple[str, int, Any]]:
    children: list[tuple[str, int, Any]] = []

    def add(role: str, values: list[Any] | tuple[Any, ...] | None) -> None:
        if not values:
            return
        for child_index, child in enumerate(values):
            if child is not None:
                children.append((role, child_index, child))

    def one(role: str, value: Any | None) -> None:
        if value is not None:
            children.append((role, 0, value))

    if isinstance(node, Program):
        add("imports", node.imports or [])
        add("declarations", node.declarations)
    elif isinstance(node, RecordTypeDecl):
        add("fields", node.fields)
    elif isinstance(node, ServiceDecl):
        add("rpcs", node.rpcs)
    elif isinstance(node, RoutineDecl):
        add("params", node.params)
        add("globals", node.global_specs or [])
        add("requires", node.requires)
        add("aborts", node.aborts)
        add("ensures", node.ensures)
        add("body", node.body)
    elif isinstance(node, AbortClause):
        one("condition", node.condition)
    elif isinstance(node, LetStmt):
        one("value", node.expr)
    elif isinstance(node, AssignStmt):
        one("value", node.expr)
    elif isinstance(node, FieldAssignStmt):
        one("value", node.expr)
    elif isinstance(node, ReturnStmt):
        one("value", node.value)
    elif isinstance(node, ReturnPlain):
        one("value", node.expr)
    elif isinstance(node, ReturnOk):
        one("value", node.expr)
    elif isinstance(node, CheckStmt):
        one("condition", node.expr)
    elif isinstance(node, CallStmt):
        add("args", node.args)
    elif isinstance(node, IfStmt):
        one("condition", node.condition)
        add("then_body", node.then_body)
        add("else_body", node.else_body)
    elif isinstance(node, WhileStmt):
        one("condition", node.condition)
        add("invariants", node.invariants)
        one("variant", node.variant)
        add("body", node.body)
    elif isinstance(node, CaseStmt):
        one("value", node.expr)
        add("branches", node.branches)
        add("default_body", node.default_body)
    elif isinstance(node, CaseBranch):
        one("value", node.value)
        add("body", node.body)
    elif isinstance(node, PatternBranch):
        one("guard", node.guard)
        add("body", node.body)
    elif isinstance(node, ScopeStmt):
        add("spawn_body", node.spawn_body)
        add("join_body", node.join_body)
        add("result_body", node.result_body)
    elif isinstance(node, CallExpr):
        add("args", node.args)
        one("invariant", node.invariant)
    elif isinstance(node, AwaitExpr):
        one("value", node.expr)
    elif isinstance(node, NamedArg):
        one("value", node.expr)
    elif isinstance(node, RecordLiteralExpr):
        add("args", node.args)
    elif isinstance(node, MapLiteralExpr):
        add("entries", node.entries)
    elif isinstance(node, MapEntry):
        one("expr", node.expr)
    elif isinstance(node, ArrayLiteralExpr):
        add("items", node.items)
    elif isinstance(node, IndexExpr):
        one("index", node.index)
    elif isinstance(node, IndexedFieldAccessExpr):
        one("index", node.index)
    elif isinstance(node, UnaryExpr):
        one("value", node.expr)
    elif isinstance(node, BinaryExpr):
        one("left", node.left)
        one("right", node.right)
    elif isinstance(node, ForAllExpr):
        one("lower", node.lower)
        one("upper", node.upper)
        one("expr", node.expr)
    elif isinstance(node, ExistsExpr):
        one("lower", node.lower)
        one("upper", node.upper)
        one("expr", node.expr)
    return children
