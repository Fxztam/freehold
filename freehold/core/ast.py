from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Union

@dataclass(frozen=True)
class SourcePos:
    line: int | None = None
    column: int | None = None
    def text(self) -> str:
        return "line ?:?" if self.line is None else f"line {self.line}:{self.column}"

@dataclass(frozen=True)
class TypeName:
    name: str

@dataclass(frozen=True)
class ResultTypeName:
    ok_type: Any
    error_type: str

@dataclass(frozen=True)
class ArrayTypeName:
    element_type: str
    size: int

@dataclass(frozen=True)
class ArrayLiteralType:
    element_type: str
    size: int

@dataclass(frozen=True)
class AwaitableType:
    inner_type: Any

TypeRef = Union[TypeName, ResultTypeName, ArrayTypeName, ArrayLiteralType]

@dataclass(frozen=True)
class TypeDef:
    name: str
    base: str
    min_value: int | float | None = None
    max_value: int | float | None = None

@dataclass(frozen=True)
class RecordField:
    name: str
    type_name: str
    pos: SourcePos
    proto_id: int | None = None

@dataclass(frozen=True)
class RecordDef:
    name: str
    fields: dict[str, str]
    proto_fields: dict[str, int] | None = None

@dataclass(frozen=True)
class RpcDecl:
    name: str
    request_name: str
    request_type: str
    response_type: str
    pos: SourcePos

@dataclass(frozen=True)
class ServiceDecl:
    name: str
    rpcs: list[RpcDecl]
    pos: SourcePos

@dataclass(frozen=True)
class RecordValue:
    type_name: str
    fields: dict[str, Any]

@dataclass(frozen=True)
class ResultValue:
    ok: bool
    value: Any | None = None
    error: str | None = None

@dataclass(frozen=True)
class BigIntegerValue:
    value: int

@dataclass(frozen=True)
class BigFloatValue:
    value: Decimal
    precision_bits: int

@dataclass(frozen=True)
class TypeDecl:
    name: str; base: str; min_value: int | float | None; max_value: int | float | None; pos: SourcePos

@dataclass(frozen=True)
class RecordTypeDecl:
    name: str; fields: list[RecordField]; pos: SourcePos; type_params: list[str] | None = None

@dataclass(frozen=True)
class ErrorDecl:
    name: str; pos: SourcePos

@dataclass(frozen=True)
class Param:
    name: str; type_name: str; pos: SourcePos

@dataclass(frozen=True)
class ImportDecl:
    module_name: str
    exposing: list[str]
    pos: SourcePos

@dataclass
class Program:
    module_name: str
    declarations: list[Any]
    pos: SourcePos
    imports: list[ImportDecl] | None = None

@dataclass
class RoutineDecl:
    kind: str; name: str; params: list[Param]; return_type: TypeRef | None
    requires: list[Any]; aborts: list[Any]; ensures: list[Any]; body: list[Any]; pos: SourcePos; type_params: list[str] | None = None; is_async: bool = False

@dataclass
class AbortClause:
    error_name: str; condition: Any | None; pos: SourcePos

@dataclass
class LetStmt:
    name: str; type_ref: TypeRef; expr: Any; pos: SourcePos

@dataclass
class AssignStmt:
    name: str; expr: Any; pos: SourcePos

@dataclass
class FieldAssignStmt:
    path: list[str]; expr: Any; pos: SourcePos

@dataclass
class ReturnStmt:
    value: Any; pos: SourcePos

@dataclass
class AbortStmt:
    error_name: str; pos: SourcePos

@dataclass
class ReturnPlain:
    expr: Any; pos: SourcePos

@dataclass
class ReturnOk:
    expr: Any; pos: SourcePos

@dataclass
class ReturnError:
    error_name: str; pos: SourcePos

@dataclass
class CheckStmt:
    expr: Any; pos: SourcePos

@dataclass
class CallStmt:
    name: str; args: list[Any]; pos: SourcePos

@dataclass
class IfStmt:
    condition: Any; then_body: list[Any]; else_body: list[Any]; pos: SourcePos

@dataclass
class WhileStmt:
    condition: Any; invariants: list[Any]; variant: Any | None; body: list[Any]; pos: SourcePos

@dataclass(frozen=True)
class NumberExpr:
    value: int; pos: SourcePos

@dataclass(frozen=True)
class DoubleExpr:
    value: float; pos: SourcePos

@dataclass(frozen=True)
class BoolExpr:
    value: bool; pos: SourcePos

@dataclass(frozen=True)
class SpecialResultExpr:
    name: str; pos: SourcePos

@dataclass(frozen=True)
class VarExpr:
    name: str; pos: SourcePos

@dataclass(frozen=True)
class FieldAccessExpr:
    path: list[str]; pos: SourcePos

@dataclass(frozen=True)
class CallExpr:
    name: str; args: list[Any]; pos: SourcePos; type_args: list[str] | None = None

@dataclass(frozen=True)
class AwaitExpr:
    expr: Any; pos: SourcePos

@dataclass(frozen=True)
class NamedArg:
    name: str; expr: Any; pos: SourcePos

@dataclass(frozen=True)
class RecordLiteralExpr:
    type_name: str; args: list[NamedArg]; pos: SourcePos

@dataclass(frozen=True)
class ArrayLiteralExpr:
    items: list[Any]; pos: SourcePos

@dataclass(frozen=True)
class IndexExpr:
    name: str; index: Any; pos: SourcePos

@dataclass(frozen=True)
class UnaryExpr:
    op: str; expr: Any; pos: SourcePos

@dataclass(frozen=True)
class BinaryExpr:
    op: str; left: Any; right: Any; pos: SourcePos

class FreeholdError(Exception): pass
class TypeCheckError(FreeholdError): pass
class VerificationError(FreeholdError): pass

class ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value

class AbortSignal(Exception):
    def __init__(self, error_name: str):
        self.error_name = error_name

def type_to_string(t: TypeRef | None) -> str:
    if t is None: return "Void"
    if isinstance(t, TypeName): return t.name
    if isinstance(t, ResultTypeName): return f"Result<{type_to_string(t.ok_type)},{t.error_type}>"
    if isinstance(t, ArrayTypeName): return f"Array<{t.element_type},{t.size}>"
    if isinstance(t, ArrayLiteralType): return f"ArrayLiteral<{t.element_type},{t.size}>"
    if isinstance(t, AwaitableType): return f"Awaitable<{type_to_string(t.inner_type)}>"
    return str(t)


@dataclass
class CaseBranch:
    value: Any
    body: list[Any]
    pos: SourcePos

@dataclass
class CaseStmt:
    expr: Any
    branches: list[CaseBranch]
    default_body: list[Any]
    pos: SourcePos


@dataclass
class ScopeStmt:
    name: str
    spawn_body: list[Any]
    join_body: list[Any]
    result_body: list[Any]
    pos: SourcePos


@dataclass(frozen=True)
class StringExpr:
    value: str
    pos: SourcePos
