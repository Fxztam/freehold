from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freehold.core.ast import (
    ArrayLiteralExpr,
    ArrayTypeName,
    AwaitExpr,
    AbortStmt,
    AssignStmt,
    BinaryExpr,
    BoolExpr,
    CallStmt,
    CaseStmt,
    CallExpr,
    CheckStmt,
    DoubleExpr,
    ErrorDecl,
    FieldAccessExpr,
    FieldAssignStmt,
    IfStmt,
    ExistsExpr,
    ForAllExpr,
    IsExpr,
    ImportDecl,
    IndexedFieldAccessExpr,
    IndexExpr,
    LetStmt,
    NamedArg,
    NumberExpr,
    Param,
    Program,
    RecordLiteralExpr,
    RecordTypeDecl,
    ReturnPlain,
    ReturnOk,
    ReturnError,
    ReturnStmt,
    RoutineDecl,
    ServiceDecl,
    SpecialResultExpr,
    ScopeStmt,
    ParallelStmt,
    SpawnExpr,
    ResultTypeName,
    StringExpr,
    TypeDecl,
    TypeName,
    UnaryExpr,
    VarExpr,
    WhileStmt,
    type_to_string,
    RecordField,
    CaseBranch,
    ArrayLiteralType,
    AwaitableType,
    AbortClause,
    ChoiceTypeDecl,
    ChoiceConstructor,
    PatternBranch,
    PatternExpr,
)
from freehold.core.module_resolver import ModuleResolver, ResolvedModule
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program


class GoCodegenError(Exception):
    pass


GO_RUNTIME_MODULE_EXPORTS: dict[str, set[str]] = {
    "Math": {"sin", "cos", "tan", "sqrt", "pow", "abs", "min", "max", "floor", "ceil"},
    "Std.IO": {"log", "logf", "log_int", "log_bool", "log_double"},
    "Big": {
        "int", "integer", "fromInteger", "float", "floatFromInteger",
        "addInt", "subInt", "mulInt", "divInt", "negInt", "absInt", "signInt",
        "addFloat", "subFloat", "mulFloat", "divFloat", "sqrt", "absFloat", "signFloat",
        "toString", "format",
    },
}

GO_PROJECT_MODULE_PATH = "freehold.local"

WEBSOCKET_RUNTIME_MODULES = {"WebSocket", "Std.Connect.WebSocket"}
HTTP_RUNTIME_MODULES = {"Std.Connect.Http"}
GRPC_RUNTIME_MODULES = {"Std.Connect.Grpc"}

FFI_GO_MODULE_MAPPINGS = {
    "freehold.local/cryptoshim": {
        "requires": [
            ("freehold.local/cryptoshim", "v0.0.0"),
        ],
        "replaces": [
            ("freehold.local/cryptoshim", Path("vendor-go/crypto-shim")),
        ],
    },
    "freehold.local/fileshim": {
        "requires": [
            ("freehold.local/fileshim", "v0.0.0"),
        ],
        "replaces": [
            ("freehold.local/fileshim", Path("vendor-go/file-shim")),
        ],
    },
    "freehold.local/oracleshim": {
        "requires": [
            ("freehold.local/oracleshim", "v0.0.0"),
            ("github.com/sijms/go-ora/v2", "v2.9.0"),
        ],
        "replaces": [
            ("freehold.local/oracleshim", Path("vendor-go/oracle-shim")),
            ("github.com/sijms/go-ora/v2", Path("vendor-go/go-ora")),
        ],
    },
}


def is_websocket_runtime_module(module_name: str) -> bool:
    return module_name in WEBSOCKET_RUNTIME_MODULES


def is_http_runtime_module(module_name: str) -> bool:
    return module_name in HTTP_RUNTIME_MODULES


def is_grpc_runtime_module(module_name: str) -> bool:
    return module_name in GRPC_RUNTIME_MODULES


@dataclass(frozen=True)
class GoCodegenResult:
    module_name: str
    package_name: str
    package_path: str
    go_source: str
    supported: bool
    diagnostics: list[dict[str, str]]
    imports: list[dict[str, Any]]

    def to_json(self, source_file: str | None = None, artifact_file: str | None = None, expected_file: str | None = None, status: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "module": self.module_name,
            "package": self.package_name,
            "package_path": self.package_path,
            "supported": self.supported,
            "diagnostics": self.diagnostics,
            "imports": self.imports,
            "go_source": self.go_source,
        }
        if source_file is not None:
            data["source_file"] = source_file
        if artifact_file is not None:
            data["artifact_file"] = artifact_file
        if expected_file is not None:
            data["expected_file"] = expected_file
        if status is not None:
            data["status"] = status
        return data


@dataclass(frozen=True)
class GoProjectFile:
    module_name: str
    source_file: str
    output_path: str
    result: GoCodegenResult
    result_program: Program

    def to_json(self) -> dict[str, Any]:
        return {
            "module": self.module_name,
            "source_file": self.source_file,
            "output_path": self.output_path,
            "result": self.result.to_json(),
        }


@dataclass(frozen=True)
class GoProjectBuildFile:
    output_path: str
    content: str
    kind: str

    def to_json(self) -> dict[str, str]:
        return {
            "output_path": self.output_path,
            "kind": self.kind,
            "content": self.content,
        }


@dataclass(frozen=True)
class GoProjectExtraFile:
    output_path: str
    content: str
    kind: str

    def to_json(self) -> dict[str, str]:
        return {
            "output_path": self.output_path,
            "kind": self.kind,
            "content": self.content,
        }


def generate_go_source(source: str) -> GoCodegenResult:
    program = parse_source(source)
    verify_program(program)
    generator = GoGenerator(program)
    return generator.generate()


def generate_go_file(path: str | Path) -> GoCodegenResult:
    source_path = Path(path)
    source = source_path.read_text(encoding="utf-8")
    program = parse_source(source)
    if program.imports and any(import_decl.module_name not in GO_RUNTIME_MODULE_EXPORTS for import_decl in program.imports):
        resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
        resolved_modules = resolver.resolve_entry(source_path)
        if resolver.entry is None:
            raise GoCodegenError("module resolver did not produce an entry module")
        generator = GoGenerator(resolver.entry.ast, resolved_modules)
        return generator.generate()
    verify_program(program)
    generator = GoGenerator(program)
    return generator.generate()


def generate_go_project(entry_file: str | Path) -> list[GoProjectFile]:
    resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
    resolved_modules = resolver.resolve_entry(entry_file)
    files: list[GoProjectFile] = []
    for module_name in sorted(resolved_modules):
        if module_name in GO_RUNTIME_MODULE_EXPORTS:
            continue
        resolved = resolved_modules[module_name]
        result = GoGenerator(resolved.ast, resolved_modules).generate()
        files.append(
            GoProjectFile(
                module_name=module_name,
                source_file=display_path(resolved.path),
                output_path=go_module_output_path(module_name).as_posix(),
                result=result,
                result_program=resolved.ast,
            )
        )
    return files


def generate_go_project_extra_files(files: list[GoProjectFile]) -> list[GoProjectExtraFile]:
    from freehold.core.grpc_go_codegen import generate_grpc_go_bindings, generate_grpc_runtime_glue

    has_grpc_runtime = any(is_grpc_runtime_module(file.module_name) for file in files)
    extras: list[GoProjectExtraFile] = []
    for file in files:
        if not any(isinstance(declaration, ServiceDecl) for declaration in file.result_program.declarations):
            continue
        extras.append(
            GoProjectExtraFile(
                output_path=go_grpc_pb_stub_output_path(file.module_name).as_posix(),
                kind="grpc_go_pb_stub",
                content=generate_grpc_pb_stub(file.result_program),
            )
        )
        extras.append(
            GoProjectExtraFile(
                output_path=go_grpc_binding_output_path(file.module_name).as_posix(),
                kind="grpc_go_bindings",
                content=generate_grpc_go_bindings(file.result_program),
            )
        )
        if has_grpc_runtime:
            extras.append(
                GoProjectExtraFile(
                    output_path=go_grpc_runtime_glue_output_path(file.module_name).as_posix(),
                    kind="grpc_go_runtime_glue",
                    content=generate_grpc_runtime_glue(file.result_program),
                )
            )
    return extras


def generate_go_project_build_files(files: list[GoProjectFile], executable_name: str | None = None, entry_module_name: str | None = None, output_dir: str | Path | None = None) -> list[GoProjectBuildFile]:
    grpc_required = any(any(isinstance(declaration, ServiceDecl) for declaration in file.result_program.declarations) for file in files)
    go_mod = f"module {GO_PROJECT_MODULE_PATH}\n\ngo 1.22\n"
    requirements: dict[str, str] = {}
    replacements: dict[str, str] = {}
    if grpc_required:
        requirements["google.golang.org/grpc"] = "v1.64.0"
    for ffi_import_path in project_ffi_import_paths(files):
        mapping = FFI_GO_MODULE_MAPPINGS.get(ffi_import_path)
        if mapping is None:
            continue
        for module_path, version in mapping["requires"]:
            requirements.setdefault(module_path, version)
        for module_path, repo_relative_path in mapping["replaces"]:
            replacements.setdefault(module_path, go_mod_replace_path(repo_relative_path, output_dir))
    if requirements:
        go_mod += "\nrequire (\n"
        for module_path, version in sorted(requirements.items()):
            go_mod += f"\t{module_path} {version}\n"
        go_mod += ")\n"
    if replacements:
        for module_path, local_path in sorted(replacements.items()):
            go_mod += f"\nreplace {module_path} => {local_path}\n"
    build_files = [
        GoProjectBuildFile(
            output_path="go.mod",
            kind="go_mod",
            content=go_mod,
        ),
    ]
    if executable_name is not None:
        if not files:
            raise GoCodegenError("cannot generate executable wrapper without project files")
        entry = next((file for file in files if file.module_name == entry_module_name), files[0])
        exe_name = go_executable_name(executable_name)
        import_alias = go_package_name(entry.module_name)
        has_ctx = "ctx context.Context" in entry.result.go_source
        arg_str = "context.Background()" if has_ctx else ""
        main_call = f"\t{import_alias}.Main({arg_str})\n"
        if re.search(r"(?m)^func Main\((?:ctx context\.Context)?\) error \{", entry.result.go_source):
            main_call = (
                f"\tif err := {import_alias}.Main({arg_str}); err != nil {{\n"
                "\t\tpanic(err)\n"
                "\t}\n"
            )
        imports = [f'\t{import_alias} "{go_import_path(entry.module_name)}"\n']
        if has_ctx:
            imports.insert(0, '\t"context"\n')
        # Blank-import generated gRPC binding/glue packages so their init() hooks
        # register the per-service runtime registrars and client dispatchers.
        if any(is_grpc_runtime_module(file.module_name) for file in files):
            for file in files:
                if any(isinstance(declaration, ServiceDecl) for declaration in file.result_program.declarations):
                    binding_import = f"{GO_PROJECT_MODULE_PATH}/grpc/{go_package_path(file.module_name)}"
                    imports.append(f'\t_ "{binding_import}"\n')
        imports_str = "".join(imports)
        build_files.append(
            GoProjectBuildFile(
                output_path=f"cmd/{exe_name}/main.go",
                kind="go_main",
                content=(
                    "package main\n\n"
                    "import (\n"
                    f"{imports_str}"
                    ")\n\n"
                    "func main() {\n"
                    f"{main_call}"
                    "}\n"
                ),
            )
        )
        build_files.append(
            GoProjectBuildFile(
                output_path="build.cmd",
                kind="build_cmd",
                content=(
                    "@echo off\n"
                    "setlocal\n"
                    "go mod tidy\n"
                    "if errorlevel 1 exit /b %errorlevel%\n"
                    "go test ./...\n"
                    "if errorlevel 1 exit /b %errorlevel%\n"
                    f"go build -trimpath -o bin\\{exe_name}.exe .\\cmd\\{exe_name}\n"
                ),
            )
        )
        build_files.append(
            GoProjectBuildFile(
                output_path="build.sh",
                kind="build_sh",
                content=(
                    "#!/bin/bash\n"
                    "set -e\n"
                    "go mod tidy\n"
                    "go test ./...\n"
                    f"go build -trimpath -o bin/{exe_name} ./cmd/{exe_name}\n"
                ),
            )
        )
        return build_files
    build_files.append(
        GoProjectBuildFile(
            output_path="build.cmd",
            kind="build_cmd",
            content="@echo off\nsetlocal\ngo mod tidy\nif errorlevel 1 exit /b %errorlevel%\ngo test ./...\n",
        ),
    )
    build_files.append(
        GoProjectBuildFile(
            output_path="build.sh",
            kind="build_sh",
            content="#!/bin/bash\nset -e\ngo mod tidy\ngo test ./...\n",
        ),
    )
    return build_files


def project_ffi_import_paths(files: list[GoProjectFile]) -> set[str]:
    imports: set[str] = set()
    for file in files:
        for declaration in file.result_program.declarations:
            if isinstance(declaration, RoutineDecl) and declaration.ffi_binding is not None:
                imports.add(declaration.ffi_binding.import_path)
    return imports


def go_mod_replace_path(repo_relative_path: Path, output_dir: str | Path | None) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    target = (repo_root / repo_relative_path).resolve()
    if output_dir is None:
        return target.as_posix()
    out_root = Path(output_dir).resolve()
    return Path(os.path.relpath(target, out_root)).as_posix()


def result_json(result: GoCodegenResult, **metadata: str) -> str:
    return json.dumps(result.to_json(**metadata), indent=2) + "\n"


def project_result_json(files: list[GoProjectFile], build_files: list[GoProjectBuildFile] | None = None, extra_files: list[GoProjectExtraFile] | None = None) -> str:
    build_files = build_files or []
    extra_files = extra_files or []
    return json.dumps(
        {
            "module_path": GO_PROJECT_MODULE_PATH,
            "total_files": len(files),
            "total_build_files": len(build_files),
            "total_extra_files": len(extra_files),
            "supported": all(file.result.supported for file in files),
            "files": [file.to_json() for file in files],
            "build_files": [file.to_json() for file in build_files],
            "extra_files": [file.to_json() for file in extra_files],
        },
        indent=2,
    ) + "\n"


def extract_generic_record_instances(type_ref: Any) -> list[tuple[str, list[str]]]:
    if type_ref is None:
        return []
    if isinstance(type_ref, str):
        gen = parse_generic(type_ref)
        if gen is not None:
            base, args = gen
            res = [(base, args)]
            for arg in args:
                res.extend(extract_generic_record_instances(arg))
            return res
        return []
    if isinstance(type_ref, TypeName):
        return extract_generic_record_instances(type_ref.name)
    if isinstance(type_ref, ArrayTypeName):
        return extract_generic_record_instances(type_ref.element_type)
    if isinstance(type_ref, ResultTypeName):
        res = []
        res.extend(extract_generic_record_instances(type_ref.ok_type))
        res.extend(extract_generic_record_instances(type_ref.error_type))
        return res
    return []


class GoGenerator:
    def __init__(self, program: Program, resolved_modules: dict[str, ResolvedModule] | None = None):
        self.program = program
        self.resolved_modules = resolved_modules or {}
        self.diagnostics: list[dict[str, str]] = []
        self.imports = program.imports or []
        self.local_routines = {declaration.name for declaration in program.declarations if isinstance(declaration, RoutineDecl)}
        self.local_types = {declaration.name for declaration in program.declarations if isinstance(declaration, (TypeDecl, RecordTypeDecl, ErrorDecl))}
        self.local_errors = {declaration.name for declaration in program.declarations if isinstance(declaration, ErrorDecl)}
        self.routines_by_name = {declaration.name: declaration for declaration in program.declarations if isinstance(declaration, RoutineDecl)}
        self.generic_records_by_name = {declaration.name: declaration for declaration in program.declarations if isinstance(declaration, RecordTypeDecl) and declaration.type_params}
        self.imports_by_module = {import_decl.module_name: import_decl for import_decl in self.imports}
        self.exposed_symbols = self.build_exposed_symbols(self.imports)
        self.exposed_type_modules = self.build_exposed_type_modules(self.imports)
        self.exposed_error_modules = self.build_exposed_error_modules(self.imports)
        self.used_import_modules: set[str] = set()
        self.used_runtime_modules: set[str] = set()
        self.std_imports: set[str] = set()
        self.result_types: dict[str, ResultTypeName] = {}
        self.needs_json_helper = False
        self.needs_json_parse_helper = False
        self.needs_big_helpers = False
        self.needs_template_helper = False
        self.needs_async_helpers = False
        self.current_return_type: Any = None
        self.current_aborts: list[Any] = []
        self.current_routine_decl: RoutineDecl | None = None
        self.current_local_types: dict[str, Any] = {}
        self.inferred_int_locals: set[str] = set()
        self.contract_bindings: dict[str, str] = {}
        self.current_routine_read_names = set()
        self.active_scopes: list[str] = []

        self.choices: dict[str, ChoiceTypeDecl] = {}
        for decl in program.declarations:
            if isinstance(decl, ChoiceTypeDecl):
                self.choices[decl.name] = decl
        for module_name, resolved in self.resolved_modules.items():
            if resolved.ast:
                for decl in resolved.ast.declarations:
                    if isinstance(decl, ChoiceTypeDecl):
                        self.choices[decl.name] = decl
                        self.choices[f"{module_name}.{decl.name}"] = decl

        self.constructor_to_choice: dict[str, tuple[str, ChoiceTypeDecl, ChoiceConstructor]] = {}
        for choice_name, choice_decl in list(self.choices.items()):
            for constr in choice_decl.constructors:
                self.constructor_to_choice[constr.name] = (choice_name, choice_decl, constr)
                if "." in choice_name:
                    mod_prefix = choice_name.split(".")[0]
                    self.constructor_to_choice[f"{mod_prefix}.{constr.name}"] = (choice_name, choice_decl, constr)

    def current_context_expr(self) -> str:
        if self.active_scopes:
            return f"{self.active_scopes[-1]}.ctx"
        return "ctx"

    def parent_context_expr(self) -> str:
        if len(self.active_scopes) > 1:
            return f"{self.active_scopes[-2]}.ctx"
        return "ctx"

    def parse_type_ref_simple(self, type_name: str) -> TypeRef:
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            if base == "Array" and len(args) == 2 and args[1].isdigit():
                return ArrayTypeName(args[0], int(args[1]))
            if base == "Result" and len(args) == 2:
                return ResultTypeName(self.parse_type_ref_simple(args[0]), args[1])
        return TypeName(type_name)

    def substitute_type_simple(self, type_name: str, substitutions: dict[str, str]) -> str:
        if type_name in substitutions:
            return substitutions[type_name]
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            new_args = [self.substitute_type_simple(arg, substitutions) for arg in args]
            return f"{base}<{', '.join(new_args)}>"
        return type_name

    def substitute_type_ref_simple(self, type_ref: Any, substitutions: dict[str, str]) -> Any:
        if type_ref is None:
            return None
        if isinstance(type_ref, TypeName):
            return TypeName(self.substitute_type_simple(type_ref.name, substitutions))
        if isinstance(type_ref, ArrayTypeName):
            return ArrayTypeName(self.substitute_type_simple(type_ref.element_type, substitutions), type_ref.size)
        if isinstance(type_ref, ResultTypeName):
            return ResultTypeName(
                self.substitute_type_ref_simple(type_ref.ok_type, substitutions),
                self.substitute_type_simple(type_ref.error_type, substitutions)
            )
        return type_ref

    def match_types_simple(self, formal: TypeRef, actual: TypeRef, type_params: set[str], inferred: dict[str, set[str]]) -> None:
        if isinstance(formal, TypeName):
            if formal.name in type_params:
                inferred[formal.name].add(type_to_string(actual))
                return
            generic_formal = parse_generic(formal.name)
            if generic_formal is not None:
                if not isinstance(actual, TypeName):
                    return
                generic_actual = parse_generic(actual.name)
                if generic_actual is not None:
                    base_formal, args_formal = generic_formal
                    base_actual, args_actual = generic_actual
                    if base_formal == base_actual and len(args_formal) == len(args_actual):
                        for f_arg, a_arg in zip(args_formal, args_actual):
                            self.match_types_simple(self.parse_type_ref_simple(f_arg), self.parse_type_ref_simple(a_arg), type_params, inferred)
        elif isinstance(formal, ArrayTypeName):
            if isinstance(actual, (ArrayTypeName, ArrayLiteralType)):
                self.match_types_simple(self.parse_type_ref_simple(formal.element_type), self.parse_type_ref_simple(actual.element_type), type_params, inferred)
        elif isinstance(formal, ResultTypeName):
            if isinstance(actual, ResultTypeName):
                self.match_types_simple(formal.ok_type, actual.ok_type, type_params, inferred)
                if formal.error_type in type_params:
                    inferred[formal.error_type].add(actual.error_type)

    def go_declared_base_simple(self, t: TypeRef) -> str:
        if isinstance(t, TypeName):
            return t.name
        if isinstance(t, ArrayTypeName) or isinstance(t, ArrayLiteralType):
            return "Array"
        if isinstance(t, ResultTypeName):
            return "Result"
        return "Unknown"

    def infer_expr_type(self, expr: Any) -> TypeRef:
        if isinstance(expr, StringExpr):
            return TypeName("String")
        if isinstance(expr, NumberExpr):
            return TypeName("Integer")
        if isinstance(expr, DoubleExpr):
            return TypeName("Double")
        if isinstance(expr, BoolExpr):
            return TypeName("Boolean")
        if isinstance(expr, VarExpr):
            if expr.name == "result" and self.current_return_type is not None:
                return self.current_return_type
            if expr.name in self.current_local_types:
                return self.current_local_types[expr.name]
            for param in (self.current_routine_decl.params if self.current_routine_decl else []):
                if param.name == expr.name:
                    return self.parse_type_ref_simple(param.type_name)
            return TypeName("Integer")
        if isinstance(expr, FieldAccessExpr):
            head, *tail = expr.path
            curr_type = self.infer_expr_type(VarExpr(head, expr.pos))
            for part in tail:
                if isinstance(curr_type, TypeName):
                    rec = self.find_record_decl(curr_type.name)
                    if rec is not None:
                        for field in rec.fields:
                            if field.name == part:
                                curr_type = self.parse_type_ref_simple(field.type_name)
                                break
            return curr_type
        if isinstance(expr, IndexedFieldAccessExpr):
            head_type = self.infer_expr_type(VarExpr(expr.name, expr.pos))
            if isinstance(head_type, ArrayTypeName):
                curr_type = self.parse_type_ref_simple(head_type.element_type)
            elif isinstance(head_type, ResultTypeName):
                curr_type = head_type.ok_type
            else:
                curr_type = head_type
            for part in expr.fields:
                if isinstance(curr_type, TypeName):
                    rec = self.find_record_decl(curr_type.name)
                    if rec is not None:
                        for field in rec.fields:
                            if field.name == part:
                                curr_type = self.parse_type_ref_simple(field.type_name)
                                break
            return curr_type
        if isinstance(expr, IndexExpr):
            head_type = self.infer_expr_type(VarExpr(expr.name, expr.pos))
            if isinstance(head_type, ArrayTypeName):
                return self.parse_type_ref_simple(head_type.element_type)
            return head_type
        if isinstance(expr, CallExpr):
            rot = self.called_routine(expr.name)
            if rot is not None:
                if rot.return_type is not None:
                    type_args = self.infer_type_args(rot, expr)
                    substitutions = dict(zip(rot.type_params or [], type_args))
                    return self.substitute_type_ref_simple(rot.return_type, substitutions)
            return TypeName("Integer")
        if isinstance(expr, RecordLiteralExpr):
            return TypeName(expr.type_name)
        if isinstance(expr, ArrayLiteralExpr):
            if expr.items:
                elem_type = self.infer_expr_type(expr.items[0])
                return ArrayTypeName(type_to_string(elem_type), len(expr.items))
            return ArrayTypeName("Integer", 0)
        if isinstance(expr, AwaitExpr):
            awaited = self.infer_expr_type(expr.expr)
            if isinstance(awaited, AwaitableType):
                return awaited.inner_type
            gen = parse_generic(type_to_string(awaited))
            if gen is not None and gen[0] == "JoinHandle":
                return self.parse_type_ref_simple(gen[1][0])
            return awaited
        if isinstance(expr, UnaryExpr):
            return self.infer_expr_type(expr.expr)
        if isinstance(expr, BinaryExpr):
            if expr.op in ("=", "!=", "<", "<=", ">", ">=", "and", "or"):
                return TypeName("Boolean")
            left = self.infer_expr_type(expr.left)
            right = self.infer_expr_type(expr.right)
            if type_to_string(left) == "Double" or type_to_string(right) == "Double":
                return TypeName("Double")
            return TypeName("Integer")
        return TypeName("Integer")

    def infer_type_args(self, routine: RoutineDecl, call_node: Any) -> list[str]:
        if call_node.type_args:
            return call_node.type_args
        params = routine.type_params or []
        inferred = {p: set() for p in params}
        for arg, p in zip(call_node.args, routine.params):
            actual_type = self.infer_expr_type(arg)
            formal_type_ref = self.parse_type_ref_simple(p.type_name)
            self.match_types_simple(formal_type_ref, actual_type, set(params), inferred)
        resolved = []
        for p in params:
            types_set = inferred[p]
            if not types_set:
                resolved.append("Integer")
            elif len(types_set) == 1:
                resolved.append(list(types_set)[0])
            else:
                bases = {self.go_declared_base_simple(self.parse_type_ref_simple(t)) for t in types_set}
                if len(bases) == 1:
                    resolved.append(list(bases)[0])
                else:
                    resolved.append(sorted(list(types_set))[0])
        return resolved

    def go_specialized_name(self, name: str, args: list[str]) -> str:
        parts = name.split(".")
        normalized_parts = [go_exported_name(p) for p in parts]
        base_name = "".join(normalized_parts)
        
        def format_arg(arg: str) -> str:
            cleaned = arg.replace("<", "_").replace(">", "").replace(",", "_").replace(" ", "")
            parts = cleaned.split(".")
            return "".join(go_exported_name(p) for p in parts)
            
        args_str = "_".join(format_arg(a) for a in args)
        return f"{base_name}_{args_str}"

    def qualify_type_name(self, type_name: str | None, context_module: str) -> str:
        if type_name is None:
            return ""
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            qualified_base = self.qualify_type_name(base, context_module)
            qualified_args = [self.qualify_type_name(arg, context_module) for arg in args]
            return f"{qualified_base}<{', '.join(qualified_args)}>"

        builtins = {"Integer", "Boolean", "Double", "String", "BigInteger", "BigFloat", "Scope", "JoinHandle", "Channel", "Sender", "Receiver", "Result", "Array"}
        if type_name in builtins:
            return type_name

        if "." in type_name:
            return type_name

        if context_module == self.program.module_name:
            for decl in self.program.declarations:
                if isinstance(decl, (TypeDecl, RecordTypeDecl, ErrorDecl)) and decl.name == type_name:
                    return f"{self.program.module_name}.{type_name}"
            exposed = self.exposed_type_modules.get(type_name)
            if exposed is not None:
                return f"{exposed}.{type_name}"
        else:
            resolved = self.resolved_modules.get(context_module)
            if resolved is not None:
                for decl in resolved.ast.declarations:
                    if isinstance(decl, (TypeDecl, RecordTypeDecl, ErrorDecl)) and decl.name == type_name:
                        return f"{context_module}.{type_name}"
                temp_exposed = self.build_exposed_type_modules(resolved.ast.imports or [])
                exposed = temp_exposed.get(type_name)
                if exposed is not None:
                    return f"{exposed}.{type_name}"

        return type_name

    def qualify_type_ref(self, type_ref: TypeRef | None, context_module: str) -> TypeRef | None:
        if type_ref is None:
            return None
        if isinstance(type_ref, TypeName):
            return TypeName(self.qualify_type_name(type_ref.name, context_module))
        if isinstance(type_ref, ArrayTypeName):
            return ArrayTypeName(self.qualify_type_name(type_ref.element_type, context_module), type_ref.size)
        if isinstance(type_ref, ResultTypeName):
            return ResultTypeName(
                self.qualify_type_ref(type_ref.ok_type, context_module),
                self.qualify_type_name(type_ref.error_type, context_module)
            )
        return type_ref

    def qualify_routine_name(self, name: str, context_module: str) -> str:
        builtins = {"channel", "channel_sender", "channel_receiver", "channel_send", "channel_try_send", "channel_receive"}
        if name in builtins or name.endswith(".spawn") or name.endswith(".join") or name == "scope_spawn" or name == "scope_join":
            return name

        if "." in name:
            return name

        if context_module == self.program.module_name:
            for decl in self.program.declarations:
                if isinstance(decl, RoutineDecl) and decl.name == name:
                    return f"{self.program.module_name}.{name}"
            exposed = self.exposed_symbols.get(name)
            if exposed is not None:
                return f"{exposed}.{name}"
        else:
            resolved = self.resolved_modules.get(context_module)
            if resolved is not None:
                for decl in resolved.ast.declarations:
                    if isinstance(decl, RoutineDecl) and decl.name == name:
                        return f"{context_module}.{name}"
                temp_exposed = self.build_exposed_symbols(resolved.ast.imports or [])
                exposed = temp_exposed.get(name)
                if exposed is not None:
                    return f"{exposed}.{name}"

        return name

    def specialize_record(self, name: str, args: list[str]) -> RecordTypeDecl:
        decl = self.find_record_decl(name)
        if decl is None:
            raise ValueError(f"Generic record {name} not found")
        substitutions = dict(zip(decl.type_params or [], args))
        
        context_module = self.program.module_name
        if "." in name:
            context_module = ".".join(name.split(".")[:-1])
        elif name in self.exposed_symbols:
            exposed = self.exposed_symbols[name]
            if exposed is not None:
                context_module = exposed
                
        specialized_fields = []
        for field in decl.fields:
            new_type_name = self.substitute_type_simple(field.type_name, substitutions)
            new_type_name = self.qualify_type_name(new_type_name, context_module)
            specialized_fields.append(RecordField(field.name, new_type_name, field.pos, field.proto_id, field.json_name))
            
        specialized_name = self.go_specialized_name(name, args)
        return RecordTypeDecl(specialized_name, specialized_fields, decl.pos, None)

    def specialize_choice(self, name: str, args: list[str]) -> ChoiceTypeDecl:
        decl = self.choices.get(name)
        if decl is None:
            raise ValueError(f"Generic choice {name} not found")
        substitutions = dict(zip(decl.type_params or [], args))
        
        context_module = self.program.module_name
        if "." in name:
            context_module = ".".join(name.split(".")[:-1])
        elif name in self.exposed_symbols:
            exposed = self.exposed_symbols[name]
            if exposed is not None:
                context_module = exposed
                
        specialized_constructors = []
        for constr in decl.constructors:
            specialized_params = []
            for param in constr.params:
                new_type_name = self.substitute_type_simple(param.type_name, substitutions)
                new_type_name = self.qualify_type_name(new_type_name, context_module)
                specialized_params.append(Param(param.name, new_type_name, param.pos))
            specialized_constructors.append(ChoiceConstructor(constr.name, specialized_params, constr.pos))
            
        specialized_name = self.go_specialized_name(name, args)
        return ChoiceTypeDecl(specialized_name, specialized_constructors, decl.pos, None)

    def specialize_routine(self, name: str, args: list[str]) -> RoutineDecl:
        routine = self.called_routine(name)
        if routine is None:
            raise ValueError(f"Generic routine {name} not found")
        substitutions = dict(zip(routine.type_params or [], args))

        context_module = self.program.module_name
        if "." in name:
            context_module = ".".join(name.split(".")[:-1])
        elif name in self.exposed_symbols:
            exposed = self.exposed_symbols[name]
            if exposed is not None:
                context_module = exposed

        def sub_type_ref(t):
            res = self.substitute_type_ref_simple(t, substitutions)
            if isinstance(res, TypeName):
                return TypeName(self.qualify_type_name(res.name, context_module))
            if isinstance(res, ArrayTypeName):
                return ArrayTypeName(self.qualify_type_name(res.element_type, context_module), res.size)
            if isinstance(res, ResultTypeName):
                return ResultTypeName(sub_type_ref(res.ok_type), self.qualify_type_name(res.error_type, context_module))
            return res

        def sub_type_str(s: str) -> str:
            res = self.substitute_type_simple(s, substitutions)
            return self.qualify_type_name(res, context_module)

        def sub_expr(expr):
            if expr is None:
                return None
            if isinstance(expr, VarExpr):
                return expr
            if isinstance(expr, NumberExpr):
                return expr
            if isinstance(expr, DoubleExpr):
                return expr
            if isinstance(expr, BoolExpr):
                return expr
            if isinstance(expr, StringExpr):
                return expr
            if isinstance(expr, SpecialResultExpr):
                return expr
            if isinstance(expr, FieldAccessExpr):
                return expr
            if isinstance(expr, IndexExpr):
                return IndexExpr(expr.name, sub_expr(expr.index), expr.pos)
            if isinstance(expr, IndexedFieldAccessExpr):
                return IndexedFieldAccessExpr(expr.name, sub_expr(expr.index), expr.fields, expr.pos)
            if isinstance(expr, UnaryExpr):
                return UnaryExpr(expr.op, sub_expr(expr.expr), expr.pos)
            if isinstance(expr, BinaryExpr):
                return BinaryExpr(expr.op, sub_expr(expr.left), sub_expr(expr.right), expr.pos)
            if isinstance(expr, CallExpr):
                new_type_args = [sub_type_str(ta) for ta in expr.type_args] if expr.type_args is not None else None
                qualified_call_name = self.qualify_routine_name(expr.name, context_module)
                return CallExpr(qualified_call_name, [sub_expr(a) for a in expr.args], expr.pos, new_type_args)
            if isinstance(expr, AwaitExpr):
                return AwaitExpr(sub_expr(expr.expr), expr.pos)
            if isinstance(expr, NamedArg):
                return NamedArg(expr.name, sub_expr(expr.expr), expr.pos)
            if isinstance(expr, RecordLiteralExpr):
                return RecordLiteralExpr(sub_type_str(expr.type_name), [sub_expr(a) for a in expr.args], expr.pos)
            if isinstance(expr, ArrayLiteralExpr):
                return ArrayLiteralExpr([sub_expr(item) for item in expr.items], expr.pos)
            if isinstance(expr, ForAllExpr):
                return ForAllExpr(expr.var_name, sub_expr(expr.lower), sub_expr(expr.upper), sub_expr(expr.expr), expr.pos)
            if isinstance(expr, ExistsExpr):
                return ExistsExpr(expr.var_name, sub_expr(expr.lower), sub_expr(expr.upper), sub_expr(expr.expr), expr.pos)
            return expr

        def sub_stmt(stmt):
            if isinstance(stmt, LetStmt):
                return LetStmt(stmt.name, sub_type_ref(stmt.type_ref), sub_expr(stmt.expr), stmt.pos)
            if isinstance(stmt, AssignStmt):
                return AssignStmt(stmt.name, sub_expr(stmt.expr), stmt.pos)
            if isinstance(stmt, FieldAssignStmt):
                return FieldAssignStmt(stmt.path, sub_expr(stmt.expr), stmt.pos)
            if isinstance(stmt, ReturnStmt):
                new_val = stmt.value
                if isinstance(new_val, ReturnPlain):
                    new_val = ReturnPlain(sub_expr(new_val.expr), new_val.pos)
                elif isinstance(new_val, ReturnOk):
                    new_val = ReturnOk(sub_expr(new_val.expr), new_val.pos)
                return ReturnStmt(new_val, stmt.pos)
            if isinstance(stmt, CheckStmt):
                return CheckStmt(sub_expr(stmt.expr), stmt.pos)
            if isinstance(stmt, CallStmt):
                new_type_args = [sub_type_str(ta) for ta in stmt.type_args] if stmt.type_args is not None else None
                qualified_call_name = self.qualify_routine_name(stmt.name, context_module)
                return CallStmt(qualified_call_name, [sub_expr(a) for a in stmt.args], stmt.pos, new_type_args)
            if isinstance(stmt, IfStmt):
                return IfStmt(sub_expr(stmt.condition), [sub_stmt(s) for s in stmt.then_body], [sub_stmt(s) for s in stmt.else_body], stmt.pos)
            if isinstance(stmt, WhileStmt):
                return WhileStmt(sub_expr(stmt.condition), [sub_expr(i) for i in stmt.invariants], sub_expr(stmt.variant), [sub_stmt(s) for s in stmt.body], stmt.pos)
            if isinstance(stmt, CaseStmt):
                new_branches = []
                for b in stmt.branches:
                    new_branches.append(CaseBranch(sub_expr(b.value), [sub_stmt(s) for s in b.body], b.pos))
                return CaseStmt(sub_expr(stmt.expr), new_branches, [sub_stmt(s) for s in stmt.default_body], stmt.pos)
            if isinstance(stmt, ScopeStmt):
                return ScopeStmt(stmt.name, [sub_stmt(s) for s in stmt.spawn_body], [sub_stmt(s) for s in stmt.join_body], [sub_stmt(s) for s in stmt.result_body], stmt.pos)
            return stmt

        specialized_name = self.go_specialized_name(name, args)
        specialized_params = [Param(p.name, sub_type_str(p.type_name), p.pos) for p in routine.params]
        specialized_return_type = sub_type_ref(routine.return_type)
        specialized_requires = [sub_expr(req) for req in routine.requires or []]
        specialized_ensures = [sub_expr(ens) for ens in routine.ensures or []]
        specialized_aborts = []
        for ab in routine.aborts or []:
            specialized_aborts.append(AbortClause(ab.error_name, sub_expr(ab.condition), ab.pos))
        specialized_body = [sub_stmt(s) for s in routine.body]

        return RoutineDecl(
            kind=routine.kind,
            name=specialized_name,
            params=specialized_params,
            return_type=specialized_return_type,
            requires=specialized_requires,
            aborts=specialized_aborts,
            ensures=specialized_ensures,
            body=specialized_body,
            pos=routine.pos,
            type_params=None,
            is_async=routine.is_async,
            global_specs=routine.global_specs,
            depends_specs=routine.depends_specs
        )

    def monomorphize(self) -> None:
        self.specialized_records: dict[tuple[str, tuple[str, ...]], RecordTypeDecl] = {}
        self.specialized_routines: dict[tuple[str, tuple[str, ...]], RoutineDecl] = {}
        self.specialized_choices: dict[tuple[str, tuple[str, ...]], ChoiceTypeDecl] = {}
        
        self.pending_scans: list[tuple[str, Any]] = []
        
        for decl in self.program.declarations:
            if isinstance(decl, RecordTypeDecl) and not decl.type_params:
                self.pending_scans.append((self.program.module_name, decl))
            elif isinstance(decl, ChoiceTypeDecl) and not decl.type_params:
                self.pending_scans.append((self.program.module_name, decl))
            elif isinstance(decl, RoutineDecl) and not decl.type_params:
                self.pending_scans.append((self.program.module_name, decl))
                
        for module_name, resolved in self.resolved_modules.items():
            if resolved.ast.module_name != self.program.module_name:
                for decl in resolved.ast.declarations:
                    if isinstance(decl, RecordTypeDecl) and not decl.type_params:
                        self.pending_scans.append((module_name, decl))
                    elif isinstance(decl, ChoiceTypeDecl) and not decl.type_params:
                        self.pending_scans.append((module_name, decl))
                    elif isinstance(decl, RoutineDecl) and not decl.type_params:
                        self.pending_scans.append((module_name, decl))
                        
        scanned_decls = set()
        
        while self.pending_scans:
            context_module, decl = self.pending_scans.pop(0)
            
            decl_key = (context_module, decl.name, type(decl))
            if decl_key in scanned_decls:
                continue
            scanned_decls.add(decl_key)
            
            self.current_routine_decl = decl if isinstance(decl, RoutineDecl) else None
            self.current_local_types = {}
            if isinstance(decl, RoutineDecl):
                self.current_return_type = decl.return_type
                def build_local_types(stmt):
                    if isinstance(stmt, LetStmt):
                        self.current_local_types[stmt.name] = stmt.type_ref
                    elif isinstance(stmt, IfStmt):
                        for s in stmt.then_body + stmt.else_body:
                            build_local_types(s)
                    elif isinstance(stmt, WhileStmt):
                        for s in stmt.body:
                            build_local_types(s)
                    elif isinstance(stmt, CaseStmt):
                        for b in stmt.branches:
                            for s in b.body:
                                build_local_types(s)
                        for s in stmt.default_body:
                            build_local_types(s)
                    elif isinstance(stmt, ScopeStmt):
                        for s in stmt.spawn_body + stmt.join_body + stmt.result_body:
                            build_local_types(s)
                for s in decl.body:
                    build_local_types(s)
            else:
                self.current_return_type = None
                
            self.scan_declaration(context_module, decl)
            
        self.specialized_records_to_emit = []
        for key, spec_rec in sorted(self.specialized_records.items()):
            self.local_types.add(spec_rec.name)
            self.specialized_records_to_emit.append(spec_rec)

        self.specialized_choices_to_emit = []
        for key, spec_choice in sorted(self.specialized_choices.items()):
            self.local_types.add(spec_choice.name)
            self.specialized_choices_to_emit.append(spec_choice)
            
        self.specialized_routines_to_emit = []
        for key, spec_rot in sorted(self.specialized_routines.items()):
            self.local_routines.add(spec_rot.name)
            self.routines_by_name[spec_rot.name] = spec_rot
            self.specialized_routines_to_emit.append(spec_rot)

    def scan_declaration(self, context_module: str, decl: Any) -> None:
        def resolve_type_str(s: str) -> str:
            return self.qualify_type_name(s, context_module)

        def resolve_type_ref(t: TypeRef | None) -> TypeRef | None:
            return self.qualify_type_ref(t, context_module)
            
        def process_type_ref(t: TypeRef | str | None):
            if isinstance(t, str):
                resolved = resolve_type_str(t)
            else:
                resolved = resolve_type_ref(t)
            instances = extract_generic_record_instances(resolved)
            for base, args in instances:
                rec_decl = self.find_record_decl(base)
                if rec_decl is not None and rec_decl.type_params:
                    if any("<" in arg or arg == "T" for arg in args):
                        continue
                    key = (base, tuple(args))
                    if key not in self.specialized_records:
                        spec_rec = self.specialize_record(base, list(args))
                        self.specialized_records[key] = spec_rec
                        rec_ctx = self.program.module_name
                        if "." in base:
                            rec_ctx = ".".join(base.split(".")[:-1])
                        elif base in self.exposed_type_modules:
                            exposed = self.exposed_type_modules[base]
                            if exposed is not None:
                                rec_ctx = exposed
                        elif base in self.exposed_symbols:
                            exposed = self.exposed_symbols[base]
                            if exposed is not None:
                                rec_ctx = exposed
                        self.pending_scans.append((rec_ctx, spec_rec))
                else:
                    choice_decl = self.choices.get(base)
                    if choice_decl is not None and choice_decl.type_params:
                        if any("<" in arg or arg == "T" for arg in args):
                            continue
                        key = (base, tuple(args))
                        if key not in self.specialized_choices:
                            spec_choice = self.specialize_choice(base, list(args))
                            self.specialized_choices[key] = spec_choice
                            for constr in spec_choice.constructors:
                                self.constructor_to_choice[constr.name] = (spec_choice.name, spec_choice, constr)
                            choice_ctx = self.program.module_name
                            if "." in base:
                                choice_ctx = ".".join(base.split(".")[:-1])
                            elif base in self.exposed_type_modules:
                                exposed = self.exposed_type_modules[base]
                                if exposed is not None:
                                    choice_ctx = exposed
                            elif base in self.exposed_symbols:
                                exposed = self.exposed_symbols[base]
                                if exposed is not None:
                                    choice_ctx = exposed
                            self.pending_scans.append((choice_ctx, spec_choice))

        def process_call(name: str, node: Any):
            qualified_name = self.qualify_routine_name(name, context_module)
            routine = self.called_routine(qualified_name)
            if routine is not None and routine.type_params:
                type_args = []
                if node.type_args:
                    type_args = [resolve_type_str(ta) for ta in node.type_args]
                else:
                    inferred = self.infer_type_args(routine, node)
                    type_args = [resolve_type_str(ta) for ta in inferred]
                
                if any("<" in arg or arg == "T" for arg in type_args):
                    return
                    
                key = (qualified_name, tuple(type_args))
                if key not in self.specialized_routines:
                    spec_rot = self.specialize_routine(qualified_name, type_args)
                    self.specialized_routines[key] = spec_rot
                    rot_ctx = self.program.module_name
                    if "." in qualified_name:
                        rot_ctx = ".".join(qualified_name.split(".")[:-1])
                    elif qualified_name in self.exposed_symbols:
                        exposed = self.exposed_symbols[qualified_name]
                        if exposed is not None:
                            rot_ctx = exposed
                    self.pending_scans.append((rot_ctx, spec_rot))

        if isinstance(decl, RecordTypeDecl):
            for field in decl.fields:
                process_type_ref(field.type_name)
        elif isinstance(decl, ChoiceTypeDecl):
            for constr in decl.constructors:
                for param in constr.params:
                    process_type_ref(param.type_name)
        elif isinstance(decl, RoutineDecl):
            for param in decl.params:
                process_type_ref(param.type_name)
            process_type_ref(decl.return_type)
            
            def visit_stmt(stmt):
                if stmt is None:
                    return
                if isinstance(stmt, LetStmt):
                    process_type_ref(stmt.type_ref)
                    visit_expr(stmt.expr)
                elif isinstance(stmt, AssignStmt):
                    visit_expr(stmt.expr)
                elif isinstance(stmt, FieldAssignStmt):
                    visit_expr(stmt.expr)
                elif isinstance(stmt, ReturnStmt):
                    if isinstance(stmt.value, (ReturnPlain, ReturnOk)):
                        visit_expr(stmt.value.expr)
                elif isinstance(stmt, CheckStmt):
                    visit_expr(stmt.expr)
                elif isinstance(stmt, IfStmt):
                    visit_expr(stmt.condition)
                    for s in stmt.then_body + stmt.else_body:
                        visit_stmt(s)
                elif isinstance(stmt, WhileStmt):
                    visit_expr(stmt.condition)
                    for inv in stmt.invariants:
                        visit_expr(inv)
                    if stmt.variant is not None:
                        visit_expr(stmt.variant)
                    for s in stmt.body:
                        visit_stmt(s)
                elif isinstance(stmt, CaseStmt):
                    visit_expr(stmt.expr)
                    for branch in stmt.branches:
                        if hasattr(branch, "pattern") and branch.pattern is not None:
                            if hasattr(branch, "guard") and branch.guard is not None:
                                visit_expr(branch.guard)
                        elif hasattr(branch, "value"):
                            visit_expr(branch.value)
                        for s in branch.body:
                            visit_stmt(s)
                    for s in stmt.default_body:
                        visit_stmt(s)
                elif isinstance(stmt, ScopeStmt):
                    for s in stmt.spawn_body + stmt.join_body + stmt.result_body:
                        visit_stmt(s)
                elif isinstance(stmt, CallStmt):
                    for a in stmt.args:
                        visit_expr(a)
                    process_call(stmt.name, stmt)

            def visit_expr(expr):
                if expr is None:
                    return
                if isinstance(expr, UnaryExpr):
                    visit_expr(expr.expr)
                elif isinstance(expr, BinaryExpr):
                    visit_expr(expr.left)
                    visit_expr(expr.right)
                elif isinstance(expr, CallExpr):
                    for a in expr.args:
                        visit_expr(a)
                    process_call(expr.name, expr)
                elif isinstance(expr, AwaitExpr):
                    visit_expr(expr.expr)
                elif isinstance(expr, NamedArg):
                    visit_expr(expr.expr)
                elif isinstance(expr, RecordLiteralExpr):
                    process_type_ref(expr.type_name)
                    for a in expr.args:
                        visit_expr(a.expr)
                elif isinstance(expr, ArrayLiteralExpr):
                    for item in expr.items:
                        visit_expr(item)
                elif isinstance(expr, IndexExpr):
                    visit_expr(expr.index)
                elif isinstance(expr, IndexedFieldAccessExpr):
                    visit_expr(expr.index)
                elif isinstance(expr, IsExpr):
                    visit_expr(expr.left)
                elif isinstance(expr, ForAllExpr):
                    visit_type_and_exprs = [expr.lower, expr.upper, expr.expr]
                    for sub in visit_type_and_exprs:
                        visit_expr(sub)
                elif isinstance(expr, ExistsExpr):
                    visit_type_and_exprs = [expr.lower, expr.upper, expr.expr]
                    for sub in visit_type_and_exprs:
                        visit_expr(sub)

            for s in decl.body:
                visit_stmt(s)

    def find_record_decl(self, name: str) -> RecordTypeDecl | None:
        current_prefix = f"{self.program.module_name}."
        local_name = name[len(current_prefix):] if name.startswith(current_prefix) else name
        if "." not in local_name:
            for decl in self.program.declarations:
                if isinstance(decl, RecordTypeDecl) and decl.name == local_name:
                    return decl
        if "." in name:
            for module_name, resolved in sorted(self.resolved_modules.items(), key=lambda item: len(item[0]), reverse=True):
                prefix = f"{module_name}."
                if not name.startswith(prefix):
                    continue
                record_name = name[len(prefix):]
                if resolved.verified is not None:
                    for decl in resolved.ast.declarations:
                        if isinstance(decl, RecordTypeDecl) and decl.name == record_name:
                            return decl
            return None
        exposed_module = self.exposed_symbols.get(name)
        if exposed_module is not None:
            resolved = self.resolved_modules.get(exposed_module)
            if resolved is not None:
                for decl in resolved.ast.declarations:
                    if isinstance(decl, RecordTypeDecl) and decl.name == name:
                        return decl
        return None

    def go_resolved_name(self, name: str) -> str:
        current_prefix = f"{self.program.module_name}."
        if name.startswith(current_prefix):
            return go_exported_name(name[len(current_prefix):])
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if name.startswith(prefix):
                symbol_name = name[len(prefix):]
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}"
        imported = self.imported_type_module(name)
        if imported is not None:
            self.used_import_modules.add(imported)
            return f"{go_import_alias(imported)}.{go_exported_name(name)}"
        return go_exported_name(name)

    def generate(self) -> GoCodegenResult:
        package_name = go_package_name(self.program.module_name)

        self.monomorphize()

        body_lines: list[str] = []
        if program_uses_big_types(self.program):
            self.std_imports.add("math/big")
        for declaration in self.program.declarations:
            if isinstance(declaration, TypeDecl):
                body_lines.extend(self.type_decl(declaration))
            elif isinstance(declaration, RecordTypeDecl):
                if declaration.type_params:
                    continue
                body_lines.extend(self.record_decl(declaration))
            elif isinstance(declaration, ChoiceTypeDecl):
                if declaration.type_params:
                    continue
                body_lines.extend(self.choice_decl(declaration))
            elif isinstance(declaration, RoutineDecl):
                if declaration.type_params:
                    continue
                body_lines.extend(self.routine_decl(declaration))
            elif isinstance(declaration, ErrorDecl):
                body_lines.extend(self.error_decl(declaration))
            elif isinstance(declaration, ServiceDecl):
                body_lines.extend(self.service_decl(declaration))
            else:
                self.unsupported(declaration, "declaration not supported by Go codegen V1")

        # Emit specialized declarations
        for spec_rec in self.specialized_records_to_emit:
            body_lines.extend(self.record_decl(spec_rec))
        for spec_choice in self.specialized_choices_to_emit:
            body_lines.extend(self.choice_decl(spec_choice))
        for spec_rot in self.specialized_routines_to_emit:
            body_lines.extend(self.routine_decl(spec_rot))

        helper_lines = self.helper_decls()
        result_type_lines = self.result_type_decls()
        import_block_lines = self.import_block()

        lines = [
            "// Code generated by Freehold Go codegen V1; DO NOT EDIT.",
            f"package {package_name}",
            "",
        ]
        lines.extend(import_block_lines)
        lines.extend(result_type_lines)
        lines.extend(helper_lines)
        lines.extend(body_lines)
        go_source = format_go_source("\n".join(lines).rstrip() + "\n")
        return GoCodegenResult(
            module_name=self.program.module_name,
            package_name=package_name,
            package_path=go_package_path(self.program.module_name),
            go_source=go_source,
            supported=not self.diagnostics,
            diagnostics=self.diagnostics,
            imports=self.import_metadata(),
        )

    def build_exposed_symbols(self, imports: list[ImportDecl]) -> dict[str, str | None]:
        symbols: dict[str, str | None] = {}
        for import_decl in imports:
            for symbol in import_decl.exposing:
                if symbol in symbols and symbols[symbol] != import_decl.module_name:
                    symbols[symbol] = None
                else:
                    symbols[symbol] = import_decl.module_name
        return symbols

    def build_exposed_type_modules(self, imports: list[ImportDecl]) -> dict[str, str | None]:
        symbols: dict[str, str | None] = {}
        for import_decl in imports:
            resolved = self.resolved_modules.get(import_decl.module_name)
            if resolved is None:
                continue
            exported_types = {
                declaration.name
                for declaration in resolved.ast.declarations
                if isinstance(declaration, (TypeDecl, RecordTypeDecl, ErrorDecl))
            }
            for symbol in import_decl.exposing:
                if symbol not in exported_types:
                    continue
                if symbol in symbols and symbols[symbol] != import_decl.module_name:
                    symbols[symbol] = None
                else:
                    symbols[symbol] = import_decl.module_name
        return symbols

    def build_exposed_error_modules(self, imports: list[ImportDecl]) -> dict[str, str | None]:
        symbols: dict[str, str | None] = {}
        for import_decl in imports:
            resolved = self.resolved_modules.get(import_decl.module_name)
            if resolved is None:
                continue
            exported_errors = {
                declaration.name
                for declaration in resolved.ast.declarations
                if isinstance(declaration, ErrorDecl)
            }
            for symbol in import_decl.exposing:
                if symbol not in exported_errors:
                    continue
                if symbol in symbols and symbols[symbol] != import_decl.module_name:
                    symbols[symbol] = None
                else:
                    symbols[symbol] = import_decl.module_name
        return symbols

    def import_block(self) -> list[str]:
        used_imports = [import_decl for import_decl in self.imports if import_decl.module_name in self.used_import_modules]
        if self.needs_async_helpers:
            self.std_imports.add("sync")
            self.std_imports.add("context")
            self.std_imports.add("runtime")
        
        # Prepare imports
        go_std_imports = set(self.std_imports)
        go_user_imports = []
        for import_decl in used_imports:
            runtime_path = runtime_module_import_path(import_decl.module_name)
            if runtime_path is not None:
                go_std_imports.add(runtime_path)
            else:
                go_user_imports.append((go_import_alias(import_decl.module_name), go_import_path(import_decl.module_name)))

        if not go_user_imports and not go_std_imports:
            return []
        lines = ["import ("]
        for import_path in sorted(go_std_imports):
            lines.append(f"\t{json.dumps(import_path)}")
        for alias, path in go_user_imports:
            lines.append(f"\t{alias} \"{path}\"")
        lines.extend([")", ""])
        return lines

    def import_metadata(self) -> list[dict[str, Any]]:
        metadata = []
        for import_decl in self.imports:
            runtime_path = runtime_module_import_path(import_decl.module_name)
            metadata.append({
                "module": import_decl.module_name,
                "alias": go_import_alias(import_decl.module_name),
                "path": runtime_path or go_import_path(import_decl.module_name),
                "runtime": import_decl.module_name in GO_RUNTIME_MODULE_EXPORTS,
                "used": import_decl.module_name in self.used_import_modules
                or import_decl.module_name in self.used_runtime_modules,
            })
        return metadata

    def type_decl(self, declaration: TypeDecl) -> list[str]:
        return [f"type {go_exported_name(declaration.name)} {self.go_type_string(declaration.base)}", ""]

    def choice_decl(self, declaration: ChoiceTypeDecl) -> list[str]:
        lines = []
        interface_name = go_exported_name(declaration.name)
        lines.append(f"type {interface_name} interface {{")
        lines.append(f"\tis_{interface_name}()")
        lines.append("}")
        lines.append("")

        for constr in declaration.constructors:
            struct_name = f"{interface_name}_{go_exported_name(constr.name)}_struct"
            lines.append(f"type {struct_name} struct {{")
            for param in constr.params:
                go_type = self.go_type_string(param.type_name)
                lines.append(f"\t{go_exported_name(param.name)} {go_type}")
            lines.append("}")
            lines.append(f"func ({struct_name}) is_{interface_name}() {{}}")
            lines.append("")

            ctor_name = f"{interface_name}_{go_exported_name(constr.name)}_ctor"
            ctor_params = []
            for param in constr.params:
                go_type = self.go_type_string(param.type_name)
                ctor_params.append(f"{go_local_name(param.name)} {go_type}")
            ctor_params_str = ", ".join(ctor_params)

            lines.append(f"func {ctor_name}({ctor_params_str}) {interface_name} {{")
            fields_inst = []
            for param in constr.params:
                fields_inst.append(f"{go_exported_name(param.name)}: {go_local_name(param.name)}")
            fields_inst_str = ", ".join(fields_inst)
            lines.append(f"\treturn {struct_name}{{{fields_inst_str}}}")
            lines.append("}")
            lines.append("")
        return lines

    def find_type_decl(self, name: str) -> TypeDecl | None:
        for declaration in self.program.declarations:
            if isinstance(declaration, TypeDecl) and declaration.name == name:
                return declaration
        return None

    def error_decl(self, declaration: ErrorDecl) -> list[str]:
        return [f"const {go_exported_name(declaration.name)} = {json.dumps(declaration.name)}", ""]

    def result_type_decls(self) -> list[str]:
        lines: list[str] = []
        for result_type in self.result_types.values():
            if self.imported_result_type_module(result_type) is not None:
                continue
            lines.append(f"type {self.go_result_type_name(result_type)} struct {{")
            lines.append("\tOk bool")
            lines.append(f"\tValue {self.go_type_ref(result_type.ok_type)}")
            lines.append("\tError string")
            lines.extend(["}", ""])
        return lines

    def helper_decls(self) -> list[str]:
        lines: list[str] = []
        if self.needs_async_helpers:
            self.std_imports.add("context")
            self.std_imports.add("runtime")
            lines.extend([
                "type freeholdTask struct {",
                "\tfn       func()",
                "\tpriority int",
                "}",
                "",
                "type freeholdWorker struct {",
                "\tid         int",
                "\tmu         sync.Mutex",
                "\tq          []freeholdTask",
                "\tsch        *freeholdScheduler",
                "\tlastVictim int",
                "}",
                "",
                "type freeholdScheduler struct {",
                "\tmu          sync.Mutex",
                "\tworkers     []*freeholdWorker",
                "\tworkerCount int",
                "\tcond        *sync.Cond",
                "\tshutdown    bool",
                "\tnextWorker  int",
                "}",
                "",
                "var globalScheduler *freeholdScheduler",
                "var schedulerOnce sync.Once",
                "",
                "func getScheduler() *freeholdScheduler {",
                "\tschedulerOnce.Do(func() {",
                "\t\tglobalScheduler = newScheduler(runtime.NumCPU())",
                "\t})",
                "\treturn globalScheduler",
                "}",
                "",
                "func newScheduler(workerCount int) *freeholdScheduler {",
                "\ts := &freeholdScheduler{",
                "\t\tworkerCount: workerCount,",
                "\t}",
                "\ts.cond = sync.NewCond(&s.mu)",
                "\ts.workers = make([]*freeholdWorker, workerCount)",
                "\tfor i := 0; i < workerCount; i++ {",
                "\t\ts.workers[i] = &freeholdWorker{",
                "\t\t\tid:         i,",
                "\t\t\tsch:        s,",
                "\t\t\tlastVictim: i,",
                "\t\t}",
                "\t}",
                "\tfor i := 0; i < workerCount; i++ {",
                "\t\tgo s.workers[i].run()",
                "\t}",
                "\treturn s",
                "}",
                "",
                "func (s *freeholdScheduler) Schedule(fn func(), priority int) {",
                "\ttask := freeholdTask{fn: fn, priority: priority}",
                "\ts.mu.Lock()",
                "\tnext := s.nextWorker",
                "\ts.nextWorker = (s.nextWorker + 1) % s.workerCount",
                "\ts.mu.Unlock()",
                "",
                "\tw := s.workers[next]",
                "\tw.mu.Lock()",
                "\tinsertIndex := len(w.q)",
                "\tfor i, t := range w.q {",
                "\t\tif task.priority > t.priority {",
                "\t\t\tinsertIndex = i",
                "\t\t\tbreak",
                "\t\t}",
                "\t}",
                "\tw.q = append(w.q, freeholdTask{})",
                "\tcopy(w.q[insertIndex+1:], w.q[insertIndex:])",
                "\tw.q[insertIndex] = task",
                "\tw.mu.Unlock()",
                "",
                "\ts.cond.Broadcast()",
                "}",
                "",
                "func (w *freeholdWorker) run() {",
                "\ts := w.sch",
                "\tfor {",
                "\t\tvar task freeholdTask",
                "\t\tfound := false",
                "",
                "\t\tw.mu.Lock()",
                "\t\tif len(w.q) > 0 {",
                "\t\t\ttask = w.q[0]",
                "\t\t\tw.q = w.q[1:]",
                "\t\t\tfound = true",
                "\t\t}",
                "\t\tw.mu.Unlock()",
                "",
                "\t\tif !found {",
                "\t\t\ttask, found = w.steal()",
                "\t\t}",
                "",
                "\t\tif !found {",
                "\t\t\ts.mu.Lock()",
                "\t\t\tfor !s.shutdown {",
                "\t\t\t\tw.mu.Lock()",
                "\t\t\t\tif len(w.q) > 0 {",
                "\t\t\t\t\ttask = w.q[0]",
                "\t\t\t\t\tw.q = w.q[1:]",
                "\t\t\t\t\tfound = true",
                "\t\t\t\t}",
                "\t\t\t\tw.mu.Unlock()",
                "\t\t\t\tif found {",
                "\t\t\t\t\tbreak",
                "\t\t\t\t}",
                "",
                "\t\t\t\ttask, found = w.steal()",
                "\t\t\t\tif found {",
                "\t\t\t\t\tbreak",
                "\t\t\t\t}",
                "",
                "\t\t\t\ts.cond.Wait()",
                "\t\t\t}",
                "\t\t\ts.mu.Unlock()",
                "\t\t}",
                "",
                "\t\tif s.shutdown {",
                "\t\t\treturn",
                "\t\t}",
                "",
                "\t\tif found {",
                "\t\t\ttask.fn()",
                "\t\t}",
                "\t}",
                "}",
                "",
                "func (w *freeholdWorker) steal() (freeholdTask, bool) {",
                "\ts := w.sch",
                "\tnumWorkers := len(s.workers)",
                "\tif numWorkers <= 1 {",
                "\t\treturn freeholdTask{}, false",
                "\t}",
                "\tw.lastVictim = (w.lastVictim + 1) % numWorkers",
                "\tif w.lastVictim == w.id {",
                "\t\tw.lastVictim = (w.lastVictim + 1) % numWorkers",
                "\t}",
                "\tvictim := s.workers[w.lastVictim]",
                "",
                "\tvictim.mu.Lock()",
                "\tdefer victim.mu.Unlock()",
                "\tif len(victim.q) > 0 {",
                "\t\ttask := victim.q[len(victim.q)-1]",
                "\t\tvictim.q = victim.q[:len(victim.q)-1]",
                "\t\treturn task, true",
                "\t}",
                "\treturn freeholdTask{}, false",
                "}",
                "",
                "type Void struct{}",
                "",
                "type FreeholdScope struct {",
                "\twg       sync.WaitGroup",
                "\tctx      context.Context",
                "\tcancel   context.CancelFunc",
                "\tpriority int",
                "\tsem      chan struct{}",
                "}",
                "",
                "type FreeholdJoinHandle[T any] struct {",
                "\tch chan T",
                "}",
                "",
                "func freeholdSpawn[T any](wg *sync.WaitGroup, priority int, sem chan struct{}, f func() T) FreeholdJoinHandle[T] {",
                "\twg.Add(1)",
                "\tch := make(chan T, 1)",
                "\ttaskFn := func() {",
                "\t\tdefer wg.Done()",
                "\t\tif sem != nil {",
                "\t\t\tsem <- struct{}{}",
                "\t\t\tdefer func() { <-sem }()",
                "\t\t}",
                "\t\tch <- f()",
                "\t}",
                "\tgetScheduler().Schedule(taskFn, priority)",
                "\treturn FreeholdJoinHandle[T]{ch: ch}",
                "}",
                "",
                "func freeholdJoin[T any](ctx context.Context, handle FreeholdJoinHandle[T]) T {",
                "\tselect {",
                "\tcase val := <-handle.ch:",
                "\t\treturn val",
                "\tcase <-ctx.Done():",
                "\t\tvar zero T",
                "\t\treturn zero",
                "\t}",
                "}",
                "",
                "func freeholdChannelSend[T any](sender chan<- T, value T) (ok bool) {",
                "\tdefer func() {",
                "\t\tif r := recover(); r != nil {",
                "\t\t\tok = false",
                "\t\t}",
                "\t}()",
                "\tsender <- value",
                "\treturn true",
                "}",
                "",
                "func freeholdChannelTrySend[T any](sender chan<- T, value T) (ok bool) {",
                "\tdefer func() {",
                "\t\tif r := recover(); r != nil {",
                "\t\t\tok = false",
                "\t\t}",
                "\t}()",
                "\tselect {",
                "\tcase sender <- value:",
                "\t\treturn true",
                "\tdefault:",
                "\t\treturn false",
                "\t}",
                "}",
                "",
                "func freeholdChannelReceive[T any](ctx context.Context, receiver <-chan T) T {",
                "\tselect {",
                "\tcase val := <-receiver:",
                "\t\treturn val",
                "\tcase <-ctx.Done():",
                "\t\tvar zero T",
                "\t\treturn zero",
                "\t}",
                "}",
                "",
            ])
        if self.needs_json_helper:
            lines.extend([
                "func freeholdJSONString(value interface{}) string {",
                "\tdata, err := json.Marshal(value)",
                "\tif err != nil {",
                "\t\tpanic(err)",
                "\t}",
                "\treturn string(data)",
                "}",
                "",
            ])
        if self.needs_json_parse_helper:
            self.std_imports.add("reflect")
            self.std_imports.add("strconv")
            lines.extend([
                "type freeholdJSONFieldSpec struct {",
                "\ttyp reflect.Type",
                "\tmin string",
                "\tmax string",
                "}",
                "",
                "func freeholdRejectDuplicateJSONKeys(raw json.RawMessage, path string) error {",
                "\tdecoder := json.NewDecoder(strings.NewReader(string(raw)))",
                "\tdecoder.UseNumber()",
                "\tif err := freeholdRejectDuplicateJSONKeysValue(decoder, path); err != nil {",
                "\t\treturn err",
                "\t}",
                "\tif _, err := decoder.Token(); err != io.EOF {",
                "\t\tif err == nil {",
                "\t\t\terr = fmt.Errorf(\"unexpected trailing JSON value\")",
                "\t\t}",
                "\t\treturn err",
                "\t}",
                "\treturn nil",
                "}",
                "",
                "func freeholdRejectDuplicateJSONKeysValue(decoder *json.Decoder, path string) error {",
                "\ttoken, err := decoder.Token()",
                "\tif err != nil {",
                "\t\treturn err",
                "\t}",
                "\tdelim, ok := token.(json.Delim)",
                "\tif !ok {",
                "\t\treturn nil",
                "\t}",
                "\tswitch delim {",
                "\tcase '{':",
                "\t\tseen := map[string]bool{}",
                "\t\tfor decoder.More() {",
                "\t\t\tkeyToken, err := decoder.Token()",
                "\t\t\tif err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t\tkey, ok := keyToken.(string)",
                "\t\t\tif !ok {",
                "\t\t\t\treturn fmt.Errorf(\"%s: expected object key\", path)",
                "\t\t\t}",
                "\t\t\tif seen[key] {",
                "\t\t\t\treturn fmt.Errorf(\"%s: duplicate object key %s\", path, key)",
                "\t\t\t}",
                "\t\t\tseen[key] = true",
                "\t\t\tif err := freeholdRejectDuplicateJSONKeysValue(decoder, path+\".\"+key); err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t}",
                "\t\tendToken, err := decoder.Token()",
                "\t\tif err != nil {",
                "\t\t\treturn err",
                "\t\t}",
                "\t\tif end, ok := endToken.(json.Delim); !ok || end != '}' {",
                "\t\t\treturn fmt.Errorf(\"%s: expected object end\", path)",
                "\t\t}",
                "\tcase '[':",
                "\t\tfor decoder.More() {",
                "\t\t\tif err := freeholdRejectDuplicateJSONKeysValue(decoder, path+\"[]\"); err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t}",
                "\t\tendToken, err := decoder.Token()",
                "\t\tif err != nil {",
                "\t\t\treturn err",
                "\t\t}",
                "\t\tif end, ok := endToken.(json.Delim); !ok || end != ']' {",
                "\t\t\treturn fmt.Errorf(\"%s: expected array end\", path)",
                "\t\t}",
                "\tdefault:",
                "\t\treturn fmt.Errorf(\"%s: unexpected JSON delimiter\", path)",
                "\t}",
                "\treturn nil",
                "}",
                "",
                "func freeholdValidateJSONValue(raw json.RawMessage, target reflect.Type, path string) error {",
                "\treturn freeholdValidateJSONValueWithRange(raw, target, path, \"\", \"\")",
                "}",
                "",
                "func freeholdValidateJSONValueWithRange(raw json.RawMessage, target reflect.Type, path string, minValue string, maxValue string) error {",
                "\tif strings.TrimSpace(string(raw)) == \"null\" {",
                "\t\treturn fmt.Errorf(\"%s: null not allowed\", path)",
                "\t}",
                "\tswitch target.Kind() {",
                "\tcase reflect.Struct:",
                "\t\tvar object map[string]json.RawMessage",
                "\t\tif err := json.Unmarshal(raw, &object); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected object\", path)",
                "\t\t}",
                "\t\tfields := map[string]freeholdJSONFieldSpec{}",
                "\t\tfor index := 0; index < target.NumField(); index++ {",
                "\t\t\tfield := target.Field(index)",
                "\t\t\tname := field.Tag.Get(\"json\")",
                "\t\t\tif name == \"\" {",
                "\t\t\t\tname = field.Name",
                "\t\t\t}",
                "\t\t\tfields[name] = freeholdJSONFieldSpec{typ: field.Type, min: field.Tag.Get(\"fh_min\"), max: field.Tag.Get(\"fh_max\")}",
                "\t\t}",
                "\t\tfor name := range object {",
                "\t\t\tif _, ok := fields[name]; !ok {",
                "\t\t\t\treturn fmt.Errorf(\"%s: unknown field %s\", path, name)",
                "\t\t\t}",
                "\t\t}",
                "\t\tfor name, fieldSpec := range fields {",
                "\t\t\tfieldRaw, ok := object[name]",
                "\t\t\tif !ok {",
                "\t\t\t\treturn fmt.Errorf(\"%s: missing required field %s\", path, name)",
                "\t\t\t}",
                "\t\t\tif err := freeholdValidateJSONValueWithRange(fieldRaw, fieldSpec.typ, path+\".\"+name, fieldSpec.min, fieldSpec.max); err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t}",
                "\t\treturn nil",
                "\tcase reflect.Array:",
                "\t\tvar items []json.RawMessage",
                "\t\tif err := json.Unmarshal(raw, &items); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected array\", path)",
                "\t\t}",
                "\t\tif len(items) != target.Len() {",
                "\t\t\treturn fmt.Errorf(\"%s: expected array length %d, got %d\", path, target.Len(), len(items))",
                "\t\t}",
                "\t\tfor _, item := range items {",
                "\t\t\tif err := freeholdValidateJSONValueWithRange(item, target.Elem(), path+\"[]\", minValue, maxValue); err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t}",
                "\t\treturn nil",
                "\tcase reflect.String:",
                "\t\tvar value string",
                "\t\tif err := json.Unmarshal(raw, &value); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected String\", path)",
                "\t\t}",
                "\t\treturn nil",
                "\tcase reflect.Bool:",
                "\t\tvar value bool",
                "\t\tif err := json.Unmarshal(raw, &value); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected Boolean\", path)",
                "\t\t}",
                "\t\treturn nil",
                "\tcase reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:",
                "\t\tvar value json.Number",
                "\t\tif err := json.Unmarshal(raw, &value); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected Integer\", path)",
                "\t\t}",
                "\t\tif _, err := value.Int64(); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected Integer\", path)",
                "\t\t}",
                "\t\tif minValue != \"\" {",
                "\t\t\tparsed, _ := value.Int64()",
                "\t\t\tminInt, err := strconv.ParseInt(minValue, 10, 64)",
                "\t\t\tif err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t\tmaxInt, err := strconv.ParseInt(maxValue, 10, 64)",
                "\t\t\tif err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t\tif parsed < minInt || parsed > maxInt {",
                "\t\t\t\treturn fmt.Errorf(\"%s: value %d out of range (%s..%s)\", path, parsed, minValue, maxValue)",
                "\t\t\t}",
                "\t\t}",
                "\t\treturn nil",
                "\tcase reflect.Float32, reflect.Float64:",
                "\t\tvar value float64",
                "\t\tif err := json.Unmarshal(raw, &value); err != nil {",
                "\t\t\treturn fmt.Errorf(\"%s: expected Double\", path)",
                "\t\t}",
                "\t\tif minValue != \"\" {",
                "\t\t\tminFloat, err := strconv.ParseFloat(minValue, 64)",
                "\t\t\tif err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t\tmaxFloat, err := strconv.ParseFloat(maxValue, 64)",
                "\t\t\tif err != nil {",
                "\t\t\t\treturn err",
                "\t\t\t}",
                "\t\t\tif value < minFloat || value > maxFloat {",
                "\t\t\t\treturn fmt.Errorf(\"%s: value %v out of range (%s..%s)\", path, value, minValue, maxValue)",
                "\t\t\t}",
                "\t\t}",
                "\t\treturn nil",
                "\tdefault:",
                "\t\treturn fmt.Errorf(\"%s: unsupported JSON target type %s\", path, target.String())",
                "\t}",
                "}",
                "",
            ])
        if self.needs_big_helpers:
            lines.extend([
                "func freeholdBigInt(text string) *big.Int {",
                "\tvalue, ok := new(big.Int).SetString(text, 10)",
                "\tif !ok {",
                "\t\tpanic(\"invalid BigInteger literal\")",
                "\t}",
                "\treturn value",
                "}",
                "",
                "func freeholdBigFloat(text string, precision int64) *big.Float {",
                "\tvalue, ok := new(big.Float).SetPrec(uint(precision)).SetString(text)",
                "\tif !ok {",
                "\t\tpanic(\"invalid BigFloat literal\")",
                "\t}",
                "\treturn value",
                "}",
                "",
                "func freeholdBigFloatFromInteger(value *big.Int, precision int64) *big.Float {",
                "\treturn new(big.Float).SetPrec(uint(precision)).SetInt(value)",
                "}",
                "",
                "func freeholdBigFloatAbs(value *big.Float) *big.Float {",
                "\tresult := new(big.Float).SetPrec(value.Prec()).Set(value)",
                "\tif result.Sign() < 0 {",
                "\t\tresult.Neg(result)",
                "\t}",
                "\treturn result",
                "}",
                "",
            ])
        if self.needs_template_helper:
            lines.extend([
                "func freeholdStringTemplateWriteText(builder *strings.Builder, text string) {",
                "\tif strings.Contains(text, \"{}\") {",
                "\t\tpanic(\"template placeholder must use ${} instead of {}\")",
                "\t}",
                "\tif strings.ContainsAny(text, \"{}\") {",
                "\t\tpanic(\"invalid template brace\")",
                "\t}",
                "\tbuilder.WriteString(text)",
                "}",
                "",
                "func freeholdStringTemplateIdent(name string) bool {",
                "\tif name == \"\" {",
                "\t\treturn false",
                "\t}",
                "\tfor index := 0; index < len(name); index++ {",
                "\t\tchar := name[index]",
                "\t\tletter := (char >= 'A' && char <= 'Z') || (char >= 'a' && char <= 'z') || char == '_'",
                "\t\tdigit := char >= '0' && char <= '9'",
                "\t\tif index == 0 {",
                "\t\t\tif !letter {",
                "\t\t\t\treturn false",
                "\t\t\t}",
                "\t\t\tcontinue",
                "\t\t}",
                "\t\tif !letter && !digit {",
                "\t\t\treturn false",
                "\t\t}",
                "\t}",
                "\treturn true",
                "}",
                "",
                "func freeholdStringTemplate(template string, positional []any, named map[string]any) string {",
                "\tvar builder strings.Builder",
                "\tposition := 0",
                "\tusedNamed := map[string]bool{}",
                "\tsawPositional := false",
                "\tsawNamed := false",
                "\tfor index := 0; index < len(template); {",
                "\t\tstart := strings.Index(template[index:], \"${\")",
                "\t\tif start < 0 {",
                "\t\t\tfreeholdStringTemplateWriteText(&builder, template[index:])",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tstart += index",
                "\t\tfreeholdStringTemplateWriteText(&builder, template[index:start])",
                "\t\tend := strings.Index(template[start+2:], \"}\")",
                "\t\tif end < 0 {",
                "\t\t\tpanic(\"invalid string template brace\")",
                "\t\t}",
                "\t\tend += start + 2",
                "\t\tplaceholder := strings.TrimSpace(template[start+2 : end])",
                "\t\tif placeholder == \"\" {",
                "\t\t\tif sawNamed {",
                "\t\t\t\tpanic(\"cannot mix positional and named template placeholders\")",
                "\t\t\t}",
                "\t\t\tsawPositional = true",
                "\t\t\tif position >= len(positional) {",
                "\t\t\t\tpanic(\"string template placeholder count mismatch\")",
                "\t\t\t}",
                "\t\t\tbuilder.WriteString(fmt.Sprint(positional[position]))",
                "\t\t\tposition++",
                "\t\t} else {",
                "\t\t\tif sawPositional {",
                "\t\t\t\tpanic(\"cannot mix positional and named template placeholders\")",
                "\t\t\t}",
                "\t\t\tif !freeholdStringTemplateIdent(placeholder) {",
                "\t\t\t\tpanic(\"invalid named template placeholder: ${\" + placeholder + \"}\")",
                "\t\t\t}",
                "\t\t\tsawNamed = true",
                "\t\t\tvalue, ok := named[placeholder]",
                "\t\t\tif !ok {",
                "\t\t\t\tpanic(\"missing string template binding: \" + placeholder)",
                "\t\t\t}",
                "\t\t\tusedNamed[placeholder] = true",
                "\t\t\tbuilder.WriteString(fmt.Sprint(value))",
                "\t\t}",
                "\t\tindex = end + 1",
                "\t}",
                "\tif position != len(positional) {",
                "\t\tpanic(\"string template placeholder count mismatch\")",
                "\t}",
                "\tfor name := range named {",
                "\t\tif !usedNamed[name] {",
                "\t\t\tpanic(\"unused string template binding: \" + name)",
                "\t\t}",
                "\t}",
                "\treturn builder.String()",
                "}",
                "",
            ])
        if is_websocket_runtime_module(self.program.module_name):
            lines.extend(self.websocket_helpers())
        if is_http_runtime_module(self.program.module_name):
            lines.extend(self.http_helpers())
        if is_grpc_runtime_module(self.program.module_name):
            lines.extend(self.grpc_helpers())
        return lines

    def http_helpers(self) -> list[str]:
        self.std_imports.update({"context", "fmt", "net", "sync", "time"})
        return [
            "type httpRuntimeConn struct {",
            "\tid   string",
            "\tconn net.Conn",
            "}",
            "",
            "var (",
            "\thttpListeners     = make(map[string]net.Listener)",
            "\thttpListenersMu   sync.Mutex",
            "\thttpServerCounter int64",
            "\thttpConns         = make(map[string]*httpRuntimeConn)",
            "\thttpConnsMu       sync.Mutex",
            "\thttpConnCounter   int64",
            ")",
            "",
            "func registerHTTPListener(l net.Listener) string {",
            "\thttpListenersMu.Lock()",
            "\tdefer httpListenersMu.Unlock()",
            "\thttpServerCounter++",
            "\tid := fmt.Sprintf(\"http-server-%d\", httpServerCounter)",
            "\thttpListeners[id] = l",
            "\treturn id",
            "}",
            "",
            "func getHTTPListener(id string) net.Listener {",
            "\thttpListenersMu.Lock()",
            "\tdefer httpListenersMu.Unlock()",
            "\treturn httpListeners[id]",
            "}",
            "",
            "func closeHTTPListener(id string) {",
            "\thttpListenersMu.Lock()",
            "\tl := httpListeners[id]",
            "\tdelete(httpListeners, id)",
            "\thttpListenersMu.Unlock()",
            "\tif l != nil {",
            "\t\t_ = l.Close()",
            "\t}",
            "}",
            "",
            "func registerHTTPConn(conn net.Conn) *httpRuntimeConn {",
            "\thttpConnsMu.Lock()",
            "\tdefer httpConnsMu.Unlock()",
            "\thttpConnCounter++",
            "\tid := fmt.Sprintf(\"http-conn-%d\", httpConnCounter)",
            "\truntimeConn := &httpRuntimeConn{id: id, conn: conn}",
            "\thttpConns[id] = runtimeConn",
            "\treturn runtimeConn",
            "}",
            "",
            "func getHTTPConn(id string) *httpRuntimeConn {",
            "\thttpConnsMu.Lock()",
            "\tdefer httpConnsMu.Unlock()",
            "\treturn httpConns[id]",
            "}",
            "",
            "func removeHTTPConn(id string) {",
            "\thttpConnsMu.Lock()",
            "\tdelete(httpConns, id)",
            "\thttpConnsMu.Unlock()",
            "}",
            "",
            "func httpAcceptWithContext(ctx context.Context, l net.Listener) (net.Conn, error) {",
            "\tfor {",
            "\t\tselect {",
            "\t\tcase <-ctx.Done():",
            "\t\t\treturn nil, ctx.Err()",
            "\t\tdefault:",
            "\t\t}",
            "\t\tif deadlineListener, ok := l.(interface{ SetDeadline(time.Time) error }); ok {",
            "\t\t\t_ = deadlineListener.SetDeadline(time.Now().Add(200 * time.Millisecond))",
            "\t\t}",
            "\t\tconn, err := l.Accept()",
            "\t\tif err == nil {",
            "\t\t\treturn conn, nil",
            "\t\t}",
            "\t\tif netErr, ok := err.(net.Error); ok && netErr.Timeout() {",
            "\t\t\tcontinue",
            "\t\t}",
            "\t\treturn nil, err",
            "\t}",
            "}",
        ]

    def grpc_helpers(self) -> list[str]:
        self.std_imports.update({"context", "net", "strconv", "sync", "google.golang.org/grpc"})
        return [
            "type GrpcUnaryCall struct {",
            "\tMethod  string",
            "\tPayload string",
            "\tReply   chan string",
            "}",
            "",
            "type GrpcStreamCall struct {",
            "\tMethod  string",
            "\tPayload string",
            "\tOut     chan string",
            "\tDone    chan struct{}",
            "}",
            "",
            "type grpcServerEntry struct {",
            "\tserver   *grpc.Server",
            "\tlistener net.Listener",
            "}",
            "",
            "var (",
            "\tGrpcUnaryQueue        = make(chan *GrpcUnaryCall, 64)",
            "\tGrpcStreamQueue       = make(chan *GrpcStreamCall, 64)",
            "\tgrpcRegistrarsMu      sync.Mutex",
            "\tgrpcServiceRegistrars []func(*grpc.Server)",
            "\tgrpcDispatchersMu     sync.Mutex",
            "\tgrpcClientDispatchers = make(map[string]func(context.Context, grpc.ClientConnInterface, string) (string, error))",
            "\tgrpcStreamDispatchers = make(map[string]func(context.Context, grpc.ClientConnInterface, string) ([]string, error))",
            "\tgrpcServersMu         sync.Mutex",
            "\tgrpcServers           = make(map[string]*grpcServerEntry)",
            "\tgrpcServerCounter     int64",
            "\tgrpcCallsMu           sync.Mutex",
            "\tgrpcUnaryCalls        = make(map[string]*GrpcUnaryCall)",
            "\tgrpcStreamCalls       = make(map[string]*GrpcStreamCall)",
            "\tgrpcCallCounter       int64",
            ")",
            "",
            "func RegisterServiceRegistrar(register func(*grpc.Server)) {",
            "\tgrpcRegistrarsMu.Lock()",
            "\tdefer grpcRegistrarsMu.Unlock()",
            "\tgrpcServiceRegistrars = append(grpcServiceRegistrars, register)",
            "}",
            "",
            "func RegisterClientDispatcher(method string, dispatch func(context.Context, grpc.ClientConnInterface, string) (string, error)) {",
            "\tgrpcDispatchersMu.Lock()",
            "\tdefer grpcDispatchersMu.Unlock()",
            "\tgrpcClientDispatchers[method] = dispatch",
            "}",
            "",
            "func RegisterStreamDispatcher(method string, dispatch func(context.Context, grpc.ClientConnInterface, string) ([]string, error)) {",
            "\tgrpcDispatchersMu.Lock()",
            "\tdefer grpcDispatchersMu.Unlock()",
            "\tgrpcStreamDispatchers[method] = dispatch",
            "}",
            "",
            "func EnqueueUnaryCall(call *GrpcUnaryCall) {",
            "\tGrpcUnaryQueue <- call",
            "}",
            "",
            "func EnqueueStreamCall(call *GrpcStreamCall) {",
            "\tGrpcStreamQueue <- call",
            "}",
            "",
            "func grpcLookupClientDispatcher(method string) func(context.Context, grpc.ClientConnInterface, string) (string, error) {",
            "\tgrpcDispatchersMu.Lock()",
            "\tdefer grpcDispatchersMu.Unlock()",
            "\treturn grpcClientDispatchers[method]",
            "}",
            "",
            "func grpcLookupStreamDispatcher(method string) func(context.Context, grpc.ClientConnInterface, string) ([]string, error) {",
            "\tgrpcDispatchersMu.Lock()",
            "\tdefer grpcDispatchersMu.Unlock()",
            "\treturn grpcStreamDispatchers[method]",
            "}",
            "",
            "func registerGrpcServer(server *grpc.Server, listener net.Listener) string {",
            "\tgrpcServersMu.Lock()",
            "\tdefer grpcServersMu.Unlock()",
            "\tgrpcServerCounter++",
            "\tid := \"grpc-server-\" + strconv.FormatInt(grpcServerCounter, 10)",
            "\tgrpcServers[id] = &grpcServerEntry{server: server, listener: listener}",
            "\treturn id",
            "}",
            "",
            "func takeGrpcServer(id string) *grpcServerEntry {",
            "\tgrpcServersMu.Lock()",
            "\tdefer grpcServersMu.Unlock()",
            "\tentry := grpcServers[id]",
            "\tdelete(grpcServers, id)",
            "\treturn entry",
            "}",
            "",
            "func registerUnaryCall(call *GrpcUnaryCall) string {",
            "\tgrpcCallsMu.Lock()",
            "\tdefer grpcCallsMu.Unlock()",
            "\tgrpcCallCounter++",
            "\tid := \"grpc-call-\" + strconv.FormatInt(grpcCallCounter, 10)",
            "\tgrpcUnaryCalls[id] = call",
            "\treturn id",
            "}",
            "",
            "func takeUnaryCall(id string) *GrpcUnaryCall {",
            "\tgrpcCallsMu.Lock()",
            "\tdefer grpcCallsMu.Unlock()",
            "\tcall := grpcUnaryCalls[id]",
            "\tdelete(grpcUnaryCalls, id)",
            "\treturn call",
            "}",
            "",
            "func registerStreamCall(call *GrpcStreamCall) string {",
            "\tgrpcCallsMu.Lock()",
            "\tdefer grpcCallsMu.Unlock()",
            "\tgrpcCallCounter++",
            "\tid := \"grpc-stream-\" + strconv.FormatInt(grpcCallCounter, 10)",
            "\tgrpcStreamCalls[id] = call",
            "\treturn id",
            "}",
            "",
            "func takeStreamCall(id string) *GrpcStreamCall {",
            "\tgrpcCallsMu.Lock()",
            "\tdefer grpcCallsMu.Unlock()",
            "\tcall := grpcStreamCalls[id]",
            "\tdelete(grpcStreamCalls, id)",
            "\treturn call",
            "}",
        ]

    def websocket_helpers(self) -> list[str]:
        self.std_imports.update({"bufio", "context", "crypto/rand", "crypto/sha1", "crypto/tls", "encoding/base64", "errors", "fmt", "io", "net", "net/http", "net/url", "strings", "sync", "time"})
        conn_res = ResultTypeName(TypeName("Connection"), "WebSocketError")
        server_res = ResultTypeName(TypeName("Server"), "WebSocketError")
        self.result_types.setdefault(type_to_string(conn_res), conn_res)
        self.result_types.setdefault(type_to_string(server_res), server_res)
        return [
            "const wsMaxPayloadBytes int64 = 16 * 1024 * 1024",
            "",
            "type wsFrame struct {",
            "\tOpcode byte",
            "\tPayload []byte",
            "\tMasked bool",
            "}",
            "",
            "type wsRuntimeConn struct {",
            "\tid string",
            "\tconn net.Conn",
            "\tin chan string",
            "\tout chan string",
            "\twriteMu sync.Mutex",
            "\tcloseOnce sync.Once",
            "\tsendMasked bool",
            "}",
            "",
            "var (",
            "\tlisteners      = make(map[string]net.Listener)",
            "\tlistenersMu    sync.Mutex",
            "\tserverCounter  int64",
            "\tconnections    = make(map[string]*wsRuntimeConn)",
            "\tconnectionsMu  sync.Mutex",
            "\tconnectionNext int64",
            ")",
            "",
            "func registerListener(l net.Listener) string {",
            "\tlistenersMu.Lock()",
            "\tdefer listenersMu.Unlock()",
            "\tserverCounter++",
            "\tid := fmt.Sprintf(\"server-%d\", serverCounter)",
            "\tlisteners[id] = l",
            "\treturn id",
            "}",
            "",
            "func getListener(id string) net.Listener {",
            "\tlistenersMu.Lock()",
            "\tdefer listenersMu.Unlock()",
            "\treturn listeners[id]",
            "}",
            "",
            "func closeServerByID(id string) {",
            "\tlistenersMu.Lock()",
            "\tl := listeners[id]",
            "\tdelete(listeners, id)",
            "\tlistenersMu.Unlock()",
            "\tif l != nil {",
            "\t\t_ = l.Close()",
            "\t}",
            "}",
            "",
            "func registerConnection(conn net.Conn, in chan string, out chan string) *wsRuntimeConn {",
            "\tconnectionsMu.Lock()",
            "\tdefer connectionsMu.Unlock()",
            "\tconnectionNext++",
            "\tid := fmt.Sprintf(\"conn-%d\", connectionNext)",
            "\truntimeConn := &wsRuntimeConn{id: id, conn: conn, in: in, out: out}",
            "\tconnections[id] = runtimeConn",
            "\treturn runtimeConn",
            "}",
            "",
            "func getConnection(id string) *wsRuntimeConn {",
            "\tconnectionsMu.Lock()",
            "\tdefer connectionsMu.Unlock()",
            "\treturn connections[id]",
            "}",
            "",
            "func removeConnection(id string) {",
            "\tconnectionsMu.Lock()",
            "\tdelete(connections, id)",
            "\tconnectionsMu.Unlock()",
            "}",
            "",
            "func (c *wsRuntimeConn) closeOutgoing() {",
            "\tc.closeOnce.Do(func() {",
            "\t\tdefer func() { _ = recover() }()",
            "\t\tclose(c.out)",
            "\t})",
            "}",
            "",
            "func (c *wsRuntimeConn) closeNetwork() {",
            "\t\t_ = c.conn.Close()",
            "\t\tremoveConnection(c.id)",
            "}",
            "",
            "func randomBytes(length int) ([]byte, error) {",
            "\tb := make([]byte, length)",
            "\tif _, err := io.ReadFull(rand.Reader, b); err != nil {",
            "\t\treturn nil, err",
            "\t}",
            "\treturn b, nil",
            "}",
            "",
            "func makeWSKey() (string, error) {",
            "\tb, err := randomBytes(16)",
            "\tif err != nil {",
            "\t\treturn \"\", err",
            "\t}",
            "\treturn base64.StdEncoding.EncodeToString(b), nil",
            "}",
            "",
            "func wsAcceptKey(key string) string {",
            "\th := sha1.New()",
            "\t_, _ = h.Write([]byte(key + \"258EAFA5-E914-47DA-95CA-C5AB0DC85B11\"))",
            "\treturn base64.StdEncoding.EncodeToString(h.Sum(nil))",
            "}",
            "",
            "func readFrame(r io.Reader) (wsFrame, error) {",
            "\theader := make([]byte, 2)",
            "\tif _, err := io.ReadFull(r, header); err != nil {",
            "\t\treturn wsFrame{}, err",
            "\t}",
            "\tif header[0]&0x80 == 0 {",
            "\t\treturn wsFrame{}, errors.New(\"fragmented websocket frames are not supported\")",
            "\t}",
            "\topcode := header[0] & 0x0F",
            "\tmasked := (header[1] & 0x80) != 0",
            "\tpayloadLen := int64(header[1] & 0x7F)",
            "\tif payloadLen == 126 {",
            "\t\tlenBytes := make([]byte, 2)",
            "\t\tif _, err := io.ReadFull(r, lenBytes); err != nil {",
            "\t\t\treturn wsFrame{}, err",
            "\t\t}",
            "\t\tpayloadLen = int64(lenBytes[0])<<8 | int64(lenBytes[1])",
            "\t} else if payloadLen == 127 {",
            "\t\tlenBytes := make([]byte, 8)",
            "\t\tif _, err := io.ReadFull(r, lenBytes); err != nil {",
            "\t\t\treturn wsFrame{}, err",
            "\t\t}",
            "\t\tpayloadLen = 0",
            "\t\tfor i := 0; i < 8; i++ {",
            "\t\t\tpayloadLen = (payloadLen << 8) | int64(lenBytes[i])",
            "\t\t}",
            "\t}",
            "\tif payloadLen < 0 || payloadLen > wsMaxPayloadBytes {",
            "\t\treturn wsFrame{}, errors.New(\"websocket payload too large\")",
            "\t}",
            "\tif opcode >= 8 && payloadLen > 125 {",
            "\t\treturn wsFrame{}, errors.New(\"websocket control frame too large\")",
            "\t}",
            "\tmaskKey := make([]byte, 4)",
            "\tif masked {",
            "\t\tif _, err := io.ReadFull(r, maskKey); err != nil {",
            "\t\t\treturn wsFrame{}, err",
            "\t\t}",
            "\t}",
            "\tpayload := make([]byte, payloadLen)",
            "\tif _, err := io.ReadFull(r, payload); err != nil {",
            "\t\treturn wsFrame{}, err",
            "\t}",
            "\tif masked {",
            "\t\tfor i := int64(0); i < payloadLen; i++ {",
            "\t\t\tpayload[i] ^= maskKey[i%4]",
            "\t\t}",
            "\t}",
            "\treturn wsFrame{Opcode: opcode, Payload: payload, Masked: masked}, nil",
            "}",
            "",
            "func writeFrame(w io.Writer, opcode byte, payload []byte, mask bool) error {",
            "\tvar header []byte",
            "\tfirstByte := byte(0x80) | opcode",
            "\theader = append(header, firstByte)",
            "\tlength := len(payload)",
            "\tvar lenByte byte",
            "\tif mask {",
            "\t\tlenByte = 0x80",
            "\t}",
            "\tif length < 126 {",
            "\t\tlenByte |= byte(length)",
            "\t\theader = append(header, lenByte)",
            "\t} else if length <= 65535 {",
            "\t\tlenByte |= 126",
            "\t\theader = append(header, lenByte, byte(length>>8), byte(length))",
            "\t} else {",
            "\t\tlenByte |= 127",
            "\t\theader = append(header, lenByte)",
            "\t\tfor i := 7; i >= 0; i-- {",
            "\t\t\theader = append(header, byte(length>>(i*8)))",
            "\t\t}",
            "\t}",
            "\tif mask {",
            "\t\tmaskKey, err := randomBytes(4)",
            "\t\tif err != nil {",
            "\t\t\treturn err",
            "\t\t}",
            "\t\theader = append(header, maskKey...)",
            "\t\tmaskedPayload := make([]byte, length)",
            "\t\tfor i := 0; i < length; i++ {",
            "\t\t\tmaskedPayload[i] = payload[i] ^ maskKey[i%4]",
            "\t\t}",
            "\t\tpayload = maskedPayload",
            "\t}",
            "\tif _, err := w.Write(header); err != nil {",
            "\t\treturn err",
            "\t}",
            "\tif _, err := w.Write(payload); err != nil {",
            "\t\treturn err",
            "\t}",
            "\treturn nil",
            "}",
            "",
            "func wsReadLoop(runtimeConn *wsRuntimeConn, expectMasked bool) {",
            "\tdefer func() {",
            "\t\tdefer func() { _ = recover() }()",
            "\t\tclose(runtimeConn.in)",
            "\t\truntimeConn.closeOutgoing()",
            "\t\truntimeConn.closeNetwork()",
            "\t}()",
            "readLoop:",
            "\tfor {",
            "\t\tframe, err := readFrame(runtimeConn.conn)",
            "\t\tif err != nil {",
            "\t\t\tbreak",
            "\t\t}",
            "\t\tif frame.Masked != expectMasked {",
            "\t\t\tbreak readLoop",
            "\t\t}",
            "\t\tswitch frame.Opcode {",
            "\t\tcase 1:",
            "\t\t\truntimeConn.in <- string(frame.Payload)",
            "\t\tcase 8:",
            "\t\t\tbreak readLoop",
            "\t\tcase 9:",
            "\t\t\truntimeConn.writeMu.Lock()",
            "\t\t\t_ = writeFrame(runtimeConn.conn, 10, frame.Payload, runtimeConn.sendMasked)",
            "\t\t\truntimeConn.writeMu.Unlock()",
            "\t\tcase 10:",
            "\t\tdefault:",
            "\t\t\tbreak readLoop",
            "\t\t}",
            "\t}",
            "}",
            "",
            "func wsWriteLoop(runtimeConn *wsRuntimeConn, mask bool) {",
            "\tfor msg := range runtimeConn.out {",
            "\t\truntimeConn.writeMu.Lock()",
            "\t\terr := writeFrame(runtimeConn.conn, 1, []byte(msg), mask)",
            "\t\truntimeConn.writeMu.Unlock()",
            "\t\tif err != nil {",
            "\t\t\tbreak",
            "\t\t}",
            "\t}",
            "\truntimeConn.writeMu.Lock()",
            "\t_ = writeFrame(runtimeConn.conn, 8, nil, mask)",
            "\truntimeConn.writeMu.Unlock()",
            "\truntimeConn.closeNetwork()",
            "}",
            "",
            "func startWSConnection(conn net.Conn, id string, expectMasked bool, sendMasked bool) Connection {",
            "\tinChan := make(chan string, 64)",
            "\toutChan := make(chan string, 64)",
            "\truntimeConn := registerConnection(conn, inChan, outChan)",
            "\truntimeConn.sendMasked = sendMasked",
            "\tif id != \"\" {",
            "\t\toldID := runtimeConn.id",
            "\t\truntimeConn.id = id",
            "\t\tconnectionsMu.Lock()",
            "\t\tdelete(connections, oldID)",
            "\t\tconnections[id] = runtimeConn",
            "\t\tconnectionsMu.Unlock()",
            "\t}",
            "\tgo wsReadLoop(runtimeConn, expectMasked)",
            "\tgo wsWriteLoop(runtimeConn, sendMasked)",
            "\treturn Connection{Id: runtimeConn.id, Incoming: inChan, Outgoing: outChan}",
            "}",
            "",
            "func acceptWithContext(ctx context.Context, l net.Listener) (net.Conn, error) {",
            "\tfor {",
            "\t\tselect {",
            "\t\tcase <-ctx.Done():",
            "\t\t\treturn nil, ctx.Err()",
            "\t\tdefault:",
            "\t\t}",
            "\t\tif deadlineListener, ok := l.(interface{ SetDeadline(time.Time) error }); ok {",
            "\t\t\t_ = deadlineListener.SetDeadline(time.Now().Add(200 * time.Millisecond))",
            "\t\t}",
            "\t\tconn, err := l.Accept()",
            "\t\tif err == nil {",
            "\t\t\treturn conn, nil",
            "\t\t}",
            "\t\tif netErr, ok := err.(net.Error); ok && netErr.Timeout() {",
            "\t\t\tcontinue",
            "\t\t}",
            "\t\treturn nil, err",
            "\t}",
            "}",
        ]

    def record_decl(self, declaration: RecordTypeDecl) -> list[str]:
        if declaration.type_params:
            # Skip un-specialized generic records as they are monomorphized
            return []
        lines = [f"type {go_exported_name(declaration.name)} struct {{"]
        for field in declaration.fields:
            json_name = field.json_name or field.name
            tag_parts = [f"json:\"{json_name}\""]
            type_decl = self.find_type_decl(field.type_name)
            if type_decl is not None and type_decl.min_value is not None:
                tag_parts.append(f"fh_min:\"{type_decl.min_value}\"")
                tag_parts.append(f"fh_max:\"{type_decl.max_value}\"")
            lines.append(f"\t{go_exported_name(field.name)} {self.go_type_string(field.type_name)} `{' '.join(tag_parts)}`")
        lines.extend(["}", ""])
        return lines

    def service_decl(self, declaration: ServiceDecl) -> list[str]:
        return [f"// Service {go_exported_name(declaration.name)} is emitted through the generated gRPC binding file.", ""]

    def routine_decl(self, routine: RoutineDecl) -> list[str]:
        if routine.type_params:
            # Skip un-specialized generic routines; they are monomorphized
            return []
        if routine.ffi_binding is not None:
            return self.ffi_routine_decl(routine)
        if is_websocket_runtime_module(self.program.module_name):
            if routine.name == "connect":
                return [
                    "func Connect(ctx context.Context, urlStr string) ResultConnectionWebSocketError {",
                    "\tu, err := url.Parse(urlStr)",
                    "\tif err != nil {",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tif u.Scheme != \"ws\" && u.Scheme != \"wss\" {",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"unsupported websocket scheme: \" + u.Scheme}",
                    "\t}",
                    "\thost := u.Host",
                    "\tif !strings.Contains(host, \":\") {",
                    "\t\tif u.Scheme == \"wss\" {",
                    "\t\t\thost = host + \":443\"",
                    "\t\t} else {",
                    "\t\t\thost = host + \":80\"",
                    "\t\t}",
                    "\t}",
                    "\tvar conn net.Conn",
                    "\tif u.Scheme == \"wss\" {",
                    "\t\tdialer := tls.Dialer{NetDialer: &net.Dialer{}}",
                    "\t\tconn, err = dialer.DialContext(ctx, \"tcp\", host)",
                    "\t} else {",
                    "\t\tdialer := net.Dialer{}",
                    "\t\tconn, err = dialer.DialContext(ctx, \"tcp\", host)",
                    "\t}",
                    "\tif err != nil {",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tkey, err := makeWSKey()",
                    "\tif err != nil {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tpath := u.Path",
                    "\tif path == \"\" {",
                    "\t\tpath = \"/\"",
                    "\t}",
                    "\tif u.RawQuery != \"\" {",
                    "\t\tpath += \"?\" + u.RawQuery",
                    "\t}",
                    "\treq := \"GET \" + path + \" HTTP/1.1\\r\\n\" +",
                    "\t\t\"Host: \" + u.Host + \"\\r\\n\" +",
                    "\t\t\"Upgrade: websocket\\r\\n\" +",
                    "\t\t\"Connection: Upgrade\\r\\n\" +",
                    "\t\t\"Sec-WebSocket-Key: \" + key + \"\\r\\n\" +",
                    "\t\t\"Sec-WebSocket-Version: 13\\r\\n\\r\\n\"",
                    "\t_, err = conn.Write([]byte(req))",
                    "\tif err != nil {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tresp, err := http.ReadResponse(bufio.NewReader(conn), nil)",
                    "\tif err != nil {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tif resp.StatusCode != 101 {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"unexpected status: \" + resp.Status}",
                    "\t}",
                    "\tif !strings.EqualFold(resp.Header.Get(\"Upgrade\"), \"websocket\") || !strings.Contains(strings.ToLower(resp.Header.Get(\"Connection\")), \"upgrade\") {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"invalid websocket upgrade response\"}",
                    "\t}",
                    "\tif resp.Header.Get(\"Sec-WebSocket-Accept\") != wsAcceptKey(key) {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"invalid Sec-WebSocket-Accept\"}",
                    "\t}",
                    "\treturn ResultConnectionWebSocketError{",
                    "\t\tOk:    true,",
                    "\t\tValue: startWSConnection(conn, \"\", false, true),",
                    "\t}",
                    "}",
                    ""
                ]
            elif routine.name == "listen":
                return [
                    "func Listen(addr string) ResultServerWebSocketError {",
                    "\tl, err := net.Listen(\"tcp\", addr)",
                    "\tif err != nil {",
                    "\t\treturn ResultServerWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tid := registerListener(l)",
                    "\treturn ResultServerWebSocketError{",
                    "\t\tOk: true,",
                    "\t\tValue: Server{Id: id},",
                    "\t}",
                    "}",
                    ""
                ]
            elif routine.name == "accept":
                return [
                    "func Accept(ctx context.Context, server Server) ResultConnectionWebSocketError {",
                    "\tl := getListener(server.Id)",
                    "\tif l == nil {",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"server listener not found\"}",
                    "\t}",
                    "\tconn, err := acceptWithContext(ctx, l)",
                    "\tif err != nil {",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tr := bufio.NewReader(conn)",
                    "\treq, err := http.ReadRequest(r)",
                    "\tif err != nil {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\tif req.Method != http.MethodGet || !strings.EqualFold(req.Header.Get(\"Upgrade\"), \"websocket\") || !strings.Contains(strings.ToLower(req.Header.Get(\"Connection\")), \"upgrade\") {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"invalid websocket upgrade request\"}",
                    "\t}",
                    "\tif req.Header.Get(\"Sec-WebSocket-Version\") != \"13\" {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"unsupported websocket version\"}",
                    "\t}",
                    "\tkey := req.Header.Get(\"Sec-WebSocket-Key\")",
                    "\tif key == \"\" {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: \"missing Sec-WebSocket-Key\"}",
                    "\t}",
                    "\tacceptKey := wsAcceptKey(key)",
                    "\tresp := \"HTTP/1.1 101 Switching Protocols\\r\\n\" +",
                    "\t\t\"Upgrade: websocket\\r\\n\" +",
                    "\t\t\"Connection: Upgrade\\r\\n\" +",
                    "\t\t\"Sec-WebSocket-Accept: \" + acceptKey + \"\\r\\n\\r\\n\"",
                    "\t_, err = conn.Write([]byte(resp))",
                    "\tif err != nil {",
                    "\t\tconn.Close()",
                    "\t\treturn ResultConnectionWebSocketError{Ok: false, Error: err.Error()}",
                    "\t}",
                    "\treturn ResultConnectionWebSocketError{",
                    "\t\tOk:    true,",
                    "\t\tValue: startWSConnection(conn, \"\", true, false),",
                    "\t}",
                    "}",
                    ""
                ]
            elif routine.name == "close":
                return [
                    "func Close(conn Connection) {",
                    "\tif runtimeConn := getConnection(conn.Id); runtimeConn != nil {",
                    "\t\truntimeConn.closeOutgoing()",
                    "\t\treturn",
                    "\t}",
                    "\tdefer func() { _ = recover() }()",
                    "\tclose(conn.Outgoing)",
                    "}",
                    ""
                ]
            elif routine.name == "close_server":
                return [
                    "func CloseServer(server Server) {",
                    "\tcloseServerByID(server.Id)",
                    "}",
                    ""
                ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "send":
            self.std_imports.update({"context", "io", "net/http", "net/url", "strconv", "strings", "time"})
            self.used_import_modules.add("Std.Connect.Common")
            common_alias = go_import_alias("Std.Connect.Common")
            res_type = ResultTypeName(TypeName("Response"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func Send(ctx context.Context, client Client, request Request) ResultResponseConnectError {",
                "\tscheme := client.Endpoint.Scheme",
                "\tif scheme == \"\" {",
                "\t\tscheme = \"http\"",
                "\t}",
                "\thost := client.Endpoint.Host",
                "\tif host == \"\" {",
                "\t\treturn ResultResponseConnectError{Ok: false, Error: \"missing http endpoint host\"}",
                "\t}",
                "\tif client.Endpoint.Port > 0 {",
                "\t\thost = host + \":\" + strconv.FormatInt(client.Endpoint.Port, 10)",
                "\t}",
                "\tbasePath := client.Endpoint.PathPrefix",
                "\tif basePath == \"\" {",
                "\t\tbasePath = \"/\"",
                "\t}",
                "\trequestPath := request.Path",
                "\tif requestPath == \"\" {",
                "\t\trequestPath = \"/\"",
                "\t}",
                "\tfullPath := strings.TrimRight(basePath, \"/\") + \"/\" + strings.TrimLeft(requestPath, \"/\")",
                "\tif fullPath == \"\" {",
                "\t\tfullPath = \"/\"",
                "\t}",
                "\tu := url.URL{Scheme: scheme, Host: host, Path: fullPath}",
                "\tif request.Query != \"\" {",
                "\t\tu.RawQuery = request.Query",
                "\t}",
                "\tmethod := request.Method",
                "\tif method == \"\" {",
                "\t\tmethod = http.MethodGet",
                "\t}",
                "\treq, err := http.NewRequestWithContext(ctx, method, u.String(), strings.NewReader(request.Body.Text))",
                "\tif err != nil {",
                "\t\treturn ResultResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tif request.Headers.Accept != \"\" {",
                "\t\treq.Header.Set(\"Accept\", request.Headers.Accept)",
                "\t}",
                "\tif request.Headers.ContentType != \"\" {",
                "\t\treq.Header.Set(\"Content-Type\", request.Headers.ContentType)",
                "\t}",
                "\tif request.Headers.Authorization != \"\" {",
                "\t\treq.Header.Set(\"Authorization\", request.Headers.Authorization)",
                "\t}",
                "\tif request.Headers.RequestId != \"\" {",
                "\t\treq.Header.Set(\"X-Request-Id\", request.Headers.RequestId)",
                "\t}",
                "\thttpClient := &http.Client{Timeout: 30 * time.Second}",
                "\tresp, err := httpClient.Do(req)",
                "\tif err != nil {",
                "\t\treturn ResultResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tdefer resp.Body.Close()",
                "\tbodyBytes, err := io.ReadAll(resp.Body)",
                "\tif err != nil {",
                "\t\treturn ResultResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                f"\tresponseHeaders := {common_alias}.Headers{{",
                "\t\tAccept: resp.Header.Get(\"Accept\"),",
                "\t\tContentType: resp.Header.Get(\"Content-Type\"),",
                "\t\tAuthorization: resp.Header.Get(\"Authorization\"),",
                "\t\tRequestId: resp.Header.Get(\"X-Request-Id\"),",
                "\t}",
                "\treturn ResultResponseConnectError{",
                "\t\tOk: true,",
                "\t\tValue: Response{",
                "\t\t\tStatusCode: int64(resp.StatusCode),",
                "\t\t\tHeaders: responseHeaders,",
                f"\t\t\tBody: {common_alias}.Body{{Text: string(bodyBytes), ContentType: resp.Header.Get(\"Content-Type\")}},",
                "\t\t},",
                "\t}",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "serve":
            self.std_imports.update({"net", "strconv"})
            self.used_import_modules.add("Std.Connect.Common")
            common_alias = go_import_alias("Std.Connect.Common")
            res_type = ResultTypeName(TypeName("ServerHandle"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                f"func Serve(endpoint {common_alias}.Endpoint) ResultServerHandleConnectError {{",
                "\thost := endpoint.Host",
                "\tif host == \"\" {",
                "\t\thost = \"127.0.0.1\"",
                "\t}",
                "\taddr := host",
                "\tif endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(endpoint.Port, 10)",
                "\t}",
                "\tl, err := net.Listen(\"tcp\", addr)",
                "\tif err != nil {",
                "\t\treturn ResultServerHandleConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tid := registerHTTPListener(l)",
                "\treturn ResultServerHandleConnectError{Ok: true, Value: ServerHandle{Id: id}}",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "accept_request":
            self.std_imports.update({"bufio", "context", "io", "net/http"})
            self.used_import_modules.add("Std.Connect.Common")
            common_alias = go_import_alias("Std.Connect.Common")
            res_type = ResultTypeName(TypeName("RequestContext"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func AcceptRequest(ctx context.Context, server ServerHandle) ResultRequestContextConnectError {",
                "\tl := getHTTPListener(server.Id)",
                "\tif l == nil {",
                "\t\treturn ResultRequestContextConnectError{Ok: false, Error: \"server listener not found\"}",
                "\t}",
                "\tconn, err := httpAcceptWithContext(ctx, l)",
                "\tif err != nil {",
                "\t\treturn ResultRequestContextConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\treader := bufio.NewReader(conn)",
                "\treq, err := http.ReadRequest(reader)",
                "\tif err != nil {",
                "\t\t_ = conn.Close()",
                "\t\treturn ResultRequestContextConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tvar bodyText string",
                "\tif req.Body != nil {",
                "\t\tbodyBytes, readErr := io.ReadAll(req.Body)",
                "\t\tif readErr != nil {",
                "\t\t\t_ = conn.Close()",
                "\t\t\treturn ResultRequestContextConnectError{Ok: false, Error: readErr.Error()}",
                "\t\t}",
                "\t\tbodyText = string(bodyBytes)",
                "\t}",
                "\truntimeConn := registerHTTPConn(conn)",
                f"\trequestHeaders := {common_alias}.Headers{{",
                "\t\tAccept: req.Header.Get(\"Accept\"),",
                "\t\tContentType: req.Header.Get(\"Content-Type\"),",
                "\t\tAuthorization: req.Header.Get(\"Authorization\"),",
                "\t\tRequestId: req.Header.Get(\"X-Request-Id\"),",
                "\t}",
                "\trequestValue := Request{",
                "\t\tMethod: req.Method,",
                "\t\tPath: req.URL.Path,",
                "\t\tQuery: req.URL.RawQuery,",
                "\t\tHeaders: requestHeaders,",
                f"\t\tBody: {common_alias}.Body{{Text: bodyText, ContentType: req.Header.Get(\"Content-Type\")}},",
                "\t}",
                "\treturn ResultRequestContextConnectError{Ok: true, Value: RequestContext{Id: runtimeConn.id, Request: requestValue}}",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "respond":
            self.std_imports.update({"context", "net/http", "strconv", "strings"})
            return [
                "func Respond(ctx context.Context, requestContext RequestContext, response Response) bool {",
                "\truntimeConn := getHTTPConn(requestContext.Id)",
                "\tif runtimeConn == nil {",
                "\t\treturn false",
                "\t}",
                "\tdefer func() {",
                "\t\t_ = runtimeConn.conn.Close()",
                "\t\tremoveHTTPConn(runtimeConn.id)",
                "\t}()",
                "\tstatus := response.StatusCode",
                "\tif status == 0 {",
                "\t\tstatus = 200",
                "\t}",
                "\tstatusText := http.StatusText(int(status))",
                "\tif statusText == \"\" {",
                "\t\tstatusText = \"OK\"",
                "\t}",
                "\tbody := response.Body.Text",
                "\tvar builder strings.Builder",
                "\tbuilder.WriteString(\"HTTP/1.1 \" + strconv.FormatInt(status, 10) + \" \" + statusText + \"\\r\\n\")",
                "\tcontentType := response.Body.ContentType",
                "\tif contentType == \"\" {",
                "\t\tcontentType = response.Headers.ContentType",
                "\t}",
                "\tif contentType != \"\" {",
                "\t\tbuilder.WriteString(\"Content-Type: \" + contentType + \"\\r\\n\")",
                "\t}",
                "\tif response.Headers.RequestId != \"\" {",
                "\t\tbuilder.WriteString(\"X-Request-Id: \" + response.Headers.RequestId + \"\\r\\n\")",
                "\t}",
                "\tbuilder.WriteString(\"Content-Length: \" + strconv.Itoa(len(body)) + \"\\r\\n\")",
                "\tbuilder.WriteString(\"Connection: close\\r\\n\\r\\n\")",
                "\tbuilder.WriteString(body)",
                "\t_, err := runtimeConn.conn.Write([]byte(builder.String()))",
                "\treturn err == nil",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "stop_server":
            return [
                "func StopServer(server ServerHandle) {",
                "\tcloseHTTPListener(server.Id)",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "respond_stream":
            self.std_imports.update({"context", "net/http", "strconv", "strings"})
            return [
                "func RespondStream(ctx context.Context, requestContext RequestContext, statusCode int64, contentType string, chunkCount int64, chunks <-chan string) bool {",
                "\truntimeConn := getHTTPConn(requestContext.Id)",
                "\tif runtimeConn == nil {",
                "\t\treturn false",
                "\t}",
                "\tdefer func() {",
                "\t\t_ = runtimeConn.conn.Close()",
                "\t\tremoveHTTPConn(runtimeConn.id)",
                "\t}()",
                "\tstatus := statusCode",
                "\tif status == 0 {",
                "\t\tstatus = 200",
                "\t}",
                "\tstatusText := http.StatusText(int(status))",
                "\tif statusText == \"\" {",
                "\t\tstatusText = \"OK\"",
                "\t}",
                "\tvar head strings.Builder",
                "\thead.WriteString(\"HTTP/1.1 \" + strconv.FormatInt(status, 10) + \" \" + statusText + \"\\r\\n\")",
                "\tif contentType != \"\" {",
                "\t\thead.WriteString(\"Content-Type: \" + contentType + \"\\r\\n\")",
                "\t}",
                "\thead.WriteString(\"X-Chunk-Count: \" + strconv.FormatInt(chunkCount, 10) + \"\\r\\n\")",
                "\thead.WriteString(\"Transfer-Encoding: chunked\\r\\n\")",
                "\thead.WriteString(\"Connection: close\\r\\n\\r\\n\")",
                "\tif _, err := runtimeConn.conn.Write([]byte(head.String())); err != nil {",
                "\t\treturn false",
                "\t}",
                "\tfor i := int64(0); i < chunkCount; i++ {",
                "\t\tvar chunk string",
                "\t\tselect {",
                "\t\tcase <-ctx.Done():",
                "\t\t\treturn false",
                "\t\tcase chunk = <-chunks:",
                "\t\t}",
                "\t\tframe := strconv.FormatInt(int64(len(chunk)), 16) + \"\\r\\n\" + chunk + \"\\r\\n\"",
                "\t\tif _, err := runtimeConn.conn.Write([]byte(frame)); err != nil {",
                "\t\t\treturn false",
                "\t\t}",
                "\t}",
                "\tif _, err := runtimeConn.conn.Write([]byte(\"0\\r\\n\\r\\n\")); err != nil {",
                "\t\treturn false",
                "\t}",
                "\treturn true",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "open_stream":
            self.std_imports.update({"bufio", "context", "io", "net", "strconv", "strings"})
            res_type = ResultTypeName(TypeName("StreamResponse"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func OpenStream(ctx context.Context, client Client, request Request) ResultStreamResponseConnectError {",
                "\thost := client.Endpoint.Host",
                "\tif host == \"\" {",
                "\t\treturn ResultStreamResponseConnectError{Ok: false, Error: \"missing http endpoint host\"}",
                "\t}",
                "\taddr := host",
                "\tif client.Endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(client.Endpoint.Port, 10)",
                "\t}",
                "\tbasePath := client.Endpoint.PathPrefix",
                "\tif basePath == \"\" {",
                "\t\tbasePath = \"/\"",
                "\t}",
                "\trequestPath := request.Path",
                "\tif requestPath == \"\" {",
                "\t\trequestPath = \"/\"",
                "\t}",
                "\tfullPath := strings.TrimRight(basePath, \"/\") + \"/\" + strings.TrimLeft(requestPath, \"/\")",
                "\tif fullPath == \"\" {",
                "\t\tfullPath = \"/\"",
                "\t}",
                "\tif request.Query != \"\" {",
                "\t\tfullPath = fullPath + \"?\" + request.Query",
                "\t}",
                "\tmethod := request.Method",
                "\tif method == \"\" {",
                "\t\tmethod = \"GET\"",
                "\t}",
                "\tdialer := net.Dialer{}",
                "\tconn, err := dialer.DialContext(ctx, \"tcp\", addr)",
                "\tif err != nil {",
                "\t\treturn ResultStreamResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tvar reqBuilder strings.Builder",
                "\treqBuilder.WriteString(method + \" \" + fullPath + \" HTTP/1.1\\r\\n\")",
                "\treqBuilder.WriteString(\"Host: \" + host + \"\\r\\n\")",
                "\tif request.Headers.Accept != \"\" {",
                "\t\treqBuilder.WriteString(\"Accept: \" + request.Headers.Accept + \"\\r\\n\")",
                "\t}",
                "\tif request.Headers.Authorization != \"\" {",
                "\t\treqBuilder.WriteString(\"Authorization: \" + request.Headers.Authorization + \"\\r\\n\")",
                "\t}",
                "\treqBuilder.WriteString(\"Connection: close\\r\\n\\r\\n\")",
                "\tif _, err := conn.Write([]byte(reqBuilder.String())); err != nil {",
                "\t\tconn.Close()",
                "\t\treturn ResultStreamResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\treader := bufio.NewReader(conn)",
                "\tstatusLine, err := reader.ReadString('\\n')",
                "\tif err != nil {",
                "\t\tconn.Close()",
                "\t\treturn ResultStreamResponseConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tstatusLine = strings.TrimRight(statusLine, \"\\r\\n\")",
                "\tstatusCode := int64(0)",
                "\tparts := strings.SplitN(statusLine, \" \", 3)",
                "\tif len(parts) >= 2 {",
                "\t\tif code, convErr := strconv.ParseInt(parts[1], 10, 64); convErr == nil {",
                "\t\t\tstatusCode = code",
                "\t\t}",
                "\t}",
                "\tchunkCount := int64(0)",
                "\tfor {",
                "\t\tline, readErr := reader.ReadString('\\n')",
                "\t\tif readErr != nil {",
                "\t\t\tconn.Close()",
                "\t\t\treturn ResultStreamResponseConnectError{Ok: false, Error: readErr.Error()}",
                "\t\t}",
                "\t\tline = strings.TrimRight(line, \"\\r\\n\")",
                "\t\tif line == \"\" {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tif strings.HasPrefix(strings.ToLower(line), \"x-chunk-count:\") {",
                "\t\t\tvalue := strings.TrimSpace(line[len(\"x-chunk-count:\"):])",
                "\t\t\tif parsed, convErr := strconv.ParseInt(value, 10, 64); convErr == nil {",
                "\t\t\t\tchunkCount = parsed",
                "\t\t\t}",
                "\t\t}",
                "\t}",
                "\tchunks := make(chan string, chunkCount+1)",
                "\tfor {",
                "\t\tsizeLine, readErr := reader.ReadString('\\n')",
                "\t\tif readErr != nil {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tsizeLine = strings.TrimRight(sizeLine, \"\\r\\n\")",
                "\t\tif sizeLine == \"\" {",
                "\t\t\tcontinue",
                "\t\t}",
                "\t\tsize, convErr := strconv.ParseInt(sizeLine, 16, 64)",
                "\t\tif convErr != nil {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tif size == 0 {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tbuf := make([]byte, size)",
                "\t\tif _, readErr := io.ReadFull(reader, buf); readErr != nil {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\t_, _ = reader.Discard(2)",
                "\t\tchunks <- string(buf)",
                "\t}",
                "\tconn.Close()",
                "\tclose(chunks)",
                "\treturn ResultStreamResponseConnectError{",
                "\t\tOk: true,",
                "\t\tValue: StreamResponse{",
                "\t\t\tStatusCode: statusCode,",
                "\t\t\tChunkCount: chunkCount,",
                "\t\t\tChunks: chunks,",
                "\t\t},",
                "\t}",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "respond_sse":
            self.std_imports.update({"context", "strconv", "strings"})
            return [
                "func RespondSse(ctx context.Context, requestContext RequestContext, eventCount int64, events <-chan SseEvent) bool {",
                "\truntimeConn := getHTTPConn(requestContext.Id)",
                "\tif runtimeConn == nil {",
                "\t\treturn false",
                "\t}",
                "\tdefer func() {",
                "\t\t_ = runtimeConn.conn.Close()",
                "\t\tremoveHTTPConn(runtimeConn.id)",
                "\t}()",
                "\tvar head strings.Builder",
                "\thead.WriteString(\"HTTP/1.1 200 OK\\r\\n\")",
                "\thead.WriteString(\"Content-Type: text/event-stream\\r\\n\")",
                "\thead.WriteString(\"Cache-Control: no-cache\\r\\n\")",
                "\thead.WriteString(\"X-Event-Count: \" + strconv.FormatInt(eventCount, 10) + \"\\r\\n\")",
                "\thead.WriteString(\"Connection: close\\r\\n\\r\\n\")",
                "\tif _, err := runtimeConn.conn.Write([]byte(head.String())); err != nil {",
                "\t\treturn false",
                "\t}",
                "\tfor i := int64(0); i < eventCount; i++ {",
                "\t\tvar event SseEvent",
                "\t\tselect {",
                "\t\tcase <-ctx.Done():",
                "\t\t\treturn false",
                "\t\tcase event = <-events:",
                "\t\t}",
                "\t\tvar frame strings.Builder",
                "\t\tif event.EventType != \"\" {",
                "\t\t\tframe.WriteString(\"event: \" + event.EventType + \"\\n\")",
                "\t\t}",
                "\t\tframe.WriteString(\"data: \" + event.Data + \"\\n\\n\")",
                "\t\tif _, err := runtimeConn.conn.Write([]byte(frame.String())); err != nil {",
                "\t\t\treturn false",
                "\t\t}",
                "\t}",
                "\treturn true",
                "}",
                "",
            ]
        if is_http_runtime_module(self.program.module_name) and routine.name == "open_sse":
            self.std_imports.update({"bufio", "context", "net", "strconv", "strings"})
            res_type = ResultTypeName(TypeName("SseStream"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func OpenSse(ctx context.Context, client Client, request Request) ResultSseStreamConnectError {",
                "\thost := client.Endpoint.Host",
                "\tif host == \"\" {",
                "\t\treturn ResultSseStreamConnectError{Ok: false, Error: \"missing http endpoint host\"}",
                "\t}",
                "\taddr := host",
                "\tif client.Endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(client.Endpoint.Port, 10)",
                "\t}",
                "\tbasePath := client.Endpoint.PathPrefix",
                "\tif basePath == \"\" {",
                "\t\tbasePath = \"/\"",
                "\t}",
                "\trequestPath := request.Path",
                "\tif requestPath == \"\" {",
                "\t\trequestPath = \"/\"",
                "\t}",
                "\tfullPath := strings.TrimRight(basePath, \"/\") + \"/\" + strings.TrimLeft(requestPath, \"/\")",
                "\tif fullPath == \"\" {",
                "\t\tfullPath = \"/\"",
                "\t}",
                "\tif request.Query != \"\" {",
                "\t\tfullPath = fullPath + \"?\" + request.Query",
                "\t}",
                "\tmethod := request.Method",
                "\tif method == \"\" {",
                "\t\tmethod = \"GET\"",
                "\t}",
                "\tdialer := net.Dialer{}",
                "\tconn, err := dialer.DialContext(ctx, \"tcp\", addr)",
                "\tif err != nil {",
                "\t\treturn ResultSseStreamConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tvar reqBuilder strings.Builder",
                "\treqBuilder.WriteString(method + \" \" + fullPath + \" HTTP/1.1\\r\\n\")",
                "\treqBuilder.WriteString(\"Host: \" + host + \"\\r\\n\")",
                "\treqBuilder.WriteString(\"Accept: text/event-stream\\r\\n\")",
                "\tif request.Headers.Authorization != \"\" {",
                "\t\treqBuilder.WriteString(\"Authorization: \" + request.Headers.Authorization + \"\\r\\n\")",
                "\t}",
                "\treqBuilder.WriteString(\"Connection: close\\r\\n\\r\\n\")",
                "\tif _, err := conn.Write([]byte(reqBuilder.String())); err != nil {",
                "\t\tconn.Close()",
                "\t\treturn ResultSseStreamConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\treader := bufio.NewReader(conn)",
                "\tstatusLine, err := reader.ReadString('\\n')",
                "\tif err != nil {",
                "\t\tconn.Close()",
                "\t\treturn ResultSseStreamConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tstatusLine = strings.TrimRight(statusLine, \"\\r\\n\")",
                "\tstatusCode := int64(0)",
                "\tparts := strings.SplitN(statusLine, \" \", 3)",
                "\tif len(parts) >= 2 {",
                "\t\tif code, convErr := strconv.ParseInt(parts[1], 10, 64); convErr == nil {",
                "\t\t\tstatusCode = code",
                "\t\t}",
                "\t}",
                "\teventCount := int64(0)",
                "\tfor {",
                "\t\tline, readErr := reader.ReadString('\\n')",
                "\t\tif readErr != nil {",
                "\t\t\tconn.Close()",
                "\t\t\treturn ResultSseStreamConnectError{Ok: false, Error: readErr.Error()}",
                "\t\t}",
                "\t\tline = strings.TrimRight(line, \"\\r\\n\")",
                "\t\tif line == \"\" {",
                "\t\t\tbreak",
                "\t\t}",
                "\t\tif strings.HasPrefix(strings.ToLower(line), \"x-event-count:\") {",
                "\t\t\tvalue := strings.TrimSpace(line[len(\"x-event-count:\"):])",
                "\t\t\tif parsed, convErr := strconv.ParseInt(value, 10, 64); convErr == nil {",
                "\t\t\t\teventCount = parsed",
                "\t\t\t}",
                "\t\t}",
                "\t}",
                "\tevents := make(chan SseEvent, eventCount+1)",
                "\tcurrentType := \"\"",
                "\tcurrentData := \"\"",
                "\thaveData := false",
                "\tfor {",
                "\t\tline, readErr := reader.ReadString('\\n')",
                "\t\ttrimmed := strings.TrimRight(line, \"\\r\\n\")",
                "\t\tif trimmed == \"\" {",
                "\t\t\tif haveData {",
                "\t\t\t\tevents <- SseEvent{EventType: currentType, Data: currentData}",
                "\t\t\t\tcurrentType = \"\"",
                "\t\t\t\tcurrentData = \"\"",
                "\t\t\t\thaveData = false",
                "\t\t\t}",
                "\t\t\tif readErr != nil {",
                "\t\t\t\tbreak",
                "\t\t\t}",
                "\t\t\tcontinue",
                "\t\t}",
                "\t\tif strings.HasPrefix(trimmed, \"event:\") {",
                "\t\t\tcurrentType = strings.TrimSpace(trimmed[len(\"event:\"):])",
                "\t\t} else if strings.HasPrefix(trimmed, \"data:\") {",
                "\t\t\tcurrentData = strings.TrimSpace(trimmed[len(\"data:\"):])",
                "\t\t\thaveData = true",
                "\t\t}",
                "\t\tif readErr != nil {",
                "\t\t\tif haveData {",
                "\t\t\t\tevents <- SseEvent{EventType: currentType, Data: currentData}",
                "\t\t\t}",
                "\t\t\tbreak",
                "\t\t}",
                "\t}",
                "\tconn.Close()",
                "\tclose(events)",
                "\treturn ResultSseStreamConnectError{",
                "\t\tOk: true,",
                "\t\tValue: SseStream{",
                "\t\t\tStatusCode: statusCode,",
                "\t\t\tEventCount: eventCount,",
                "\t\t\tEvents: events,",
                "\t\t},",
                "\t}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "serve":
            self.std_imports.update({"net", "strconv", "google.golang.org/grpc"})
            self.used_import_modules.add("Std.Connect.Common")
            common_alias = go_import_alias("Std.Connect.Common")
            res_type = ResultTypeName(TypeName("ServerHandle"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                f"func Serve(endpoint {common_alias}.Endpoint) ResultServerHandleConnectError {{",
                "\thost := endpoint.Host",
                "\tif host == \"\" {",
                "\t\thost = \"127.0.0.1\"",
                "\t}",
                "\taddr := host",
                "\tif endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(endpoint.Port, 10)",
                "\t}",
                "\tlistener, err := net.Listen(\"tcp\", addr)",
                "\tif err != nil {",
                "\t\treturn ResultServerHandleConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tserver := grpc.NewServer()",
                "\tgrpcRegistrarsMu.Lock()",
                "\tfor _, register := range grpcServiceRegistrars {",
                "\t\tregister(server)",
                "\t}",
                "\tgrpcRegistrarsMu.Unlock()",
                "\tid := registerGrpcServer(server, listener)",
                "\tgo func() {",
                "\t\t_ = server.Serve(listener)",
                "\t}()",
                "\treturn ResultServerHandleConnectError{Ok: true, Value: ServerHandle{Id: id}}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "accept_call":
            self.std_imports.add("context")
            res_type = ResultTypeName(TypeName("Call"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func AcceptCall(ctx context.Context, server ServerHandle) ResultCallConnectError {",
                "\tselect {",
                "\tcase <-ctx.Done():",
                "\t\treturn ResultCallConnectError{Ok: false, Error: ctx.Err().Error()}",
                "\tcase call := <-GrpcUnaryQueue:",
                "\t\tid := registerUnaryCall(call)",
                "\t\treturn ResultCallConnectError{Ok: true, Value: Call{Id: id, Method: call.Method, Payload: call.Payload}}",
                "\t}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "respond":
            self.std_imports.add("context")
            return [
                "func Respond(ctx context.Context, pending Call, payload string) bool {",
                "\tcall := takeUnaryCall(pending.Id)",
                "\tif call == nil {",
                "\t\treturn false",
                "\t}",
                "\tselect {",
                "\tcase call.Reply <- payload:",
                "\t\treturn true",
                "\tcase <-ctx.Done():",
                "\t\treturn false",
                "\t}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "unary":
            self.std_imports.update({"context", "strconv", "google.golang.org/grpc", "google.golang.org/grpc/credentials/insecure"})
            res_type = ResultTypeName(TypeName("UnaryReply"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func Unary(ctx context.Context, client Client, method string, payload string) ResultUnaryReplyConnectError {",
                "\thost := client.Endpoint.Host",
                "\tif host == \"\" {",
                "\t\thost = \"127.0.0.1\"",
                "\t}",
                "\taddr := host",
                "\tif client.Endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(client.Endpoint.Port, 10)",
                "\t}",
                "\tconn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))",
                "\tif err != nil {",
                "\t\treturn ResultUnaryReplyConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tdefer conn.Close()",
                "\tdispatch := grpcLookupClientDispatcher(method)",
                "\tif dispatch == nil {",
                "\t\treturn ResultUnaryReplyConnectError{Ok: false, Error: \"no client dispatcher for method \" + method}",
                "\t}",
                "\tresponse, err := dispatch(ctx, conn, payload)",
                "\tif err != nil {",
                "\t\treturn ResultUnaryReplyConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\treturn ResultUnaryReplyConnectError{Ok: true, Value: UnaryReply{Payload: response}}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "stop_server":
            return [
                "func StopServer(server ServerHandle) {",
                "\tentry := takeGrpcServer(server.Id)",
                "\tif entry != nil {",
                "\t\tentry.server.Stop()",
                "\t}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "accept_stream":
            self.std_imports.add("context")
            res_type = ResultTypeName(TypeName("Call"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func AcceptStream(ctx context.Context, server ServerHandle) ResultCallConnectError {",
                "\tselect {",
                "\tcase <-ctx.Done():",
                "\t\treturn ResultCallConnectError{Ok: false, Error: ctx.Err().Error()}",
                "\tcase call := <-GrpcStreamQueue:",
                "\t\tid := registerStreamCall(call)",
                "\t\treturn ResultCallConnectError{Ok: true, Value: Call{Id: id, Method: call.Method, Payload: call.Payload}}",
                "\t}",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "respond_stream":
            self.std_imports.add("context")
            return [
                "func RespondStream(ctx context.Context, pending Call, count int64, messages <-chan string) bool {",
                "\tcall := takeStreamCall(pending.Id)",
                "\tif call == nil {",
                "\t\treturn false",
                "\t}",
                "\tfor i := int64(0); i < count; i++ {",
                "\t\tvar message string",
                "\t\tselect {",
                "\t\tcase <-ctx.Done():",
                "\t\t\tclose(call.Out)",
                "\t\t\treturn false",
                "\t\tcase message = <-messages:",
                "\t\t}",
                "\t\tselect {",
                "\t\tcase call.Out <- message:",
                "\t\tcase <-call.Done:",
                "\t\t\treturn false",
                "\t\tcase <-ctx.Done():",
                "\t\t\tclose(call.Out)",
                "\t\t\treturn false",
                "\t\t}",
                "\t}",
                "\tclose(call.Out)",
                "\treturn true",
                "}",
                "",
            ]
        if is_grpc_runtime_module(self.program.module_name) and routine.name == "open_stream":
            self.std_imports.update({"context", "strconv", "google.golang.org/grpc", "google.golang.org/grpc/credentials/insecure"})
            res_type = ResultTypeName(TypeName("StreamHandle"), "ConnectError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return [
                "func OpenStream(ctx context.Context, client Client, method string, payload string) ResultStreamHandleConnectError {",
                "\thost := client.Endpoint.Host",
                "\tif host == \"\" {",
                "\t\thost = \"127.0.0.1\"",
                "\t}",
                "\taddr := host",
                "\tif client.Endpoint.Port > 0 {",
                "\t\taddr = host + \":\" + strconv.FormatInt(client.Endpoint.Port, 10)",
                "\t}",
                "\tconn, err := grpc.NewClient(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))",
                "\tif err != nil {",
                "\t\treturn ResultStreamHandleConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tdefer conn.Close()",
                "\tdispatch := grpcLookupStreamDispatcher(method)",
                "\tif dispatch == nil {",
                "\t\treturn ResultStreamHandleConnectError{Ok: false, Error: \"no stream dispatcher for method \" + method}",
                "\t}",
                "\tmessages, err := dispatch(ctx, conn, payload)",
                "\tif err != nil {",
                "\t\treturn ResultStreamHandleConnectError{Ok: false, Error: err.Error()}",
                "\t}",
                "\tbuffer := make(chan string, len(messages)+1)",
                "\tfor _, message := range messages {",
                "\t\tbuffer <- message",
                "\t}",
                "\tclose(buffer)",
                "\treturn ResultStreamHandleConnectError{Ok: true, Value: StreamHandle{StatusCode: 200, MessageCount: int64(len(messages)), Messages: buffer}}",
                "}",
                "",
            ]
        params_list = []
        if routine.is_async:
            self.std_imports.add("context")
            params_list.append("ctx context.Context")
        params_list.extend(self.param(param) for param in routine.params)
        params = ", ".join(params_list)
        result_type = self.routine_result_type(routine)
        lines = [f"func {go_exported_name(routine.name)}({params}){result_type} {{"]
        if routine.is_async:
            self.needs_async_helpers = True
            lines.extend([
                "\tfreeholdDefaultScope := FreeholdScope{}",
                "\tfreeholdDefaultScope.ctx, freeholdDefaultScope.cancel = context.WithCancel(ctx)",
                "\tfreeholdDefaultScope.priority = 3",
                "\tfreeholdDefaultScope.sem = nil",
                "\tdefer freeholdDefaultScope.cancel()",
                "\t_ = freeholdDefaultScope",
            ])
            self.active_scopes.append("freeholdDefaultScope")
        previous_return_type = self.current_return_type
        previous_aborts = self.current_aborts
        previous_routine_decl = self.current_routine_decl
        previous_local_types = self.current_local_types
        previous_inferred_int_locals = self.inferred_int_locals
        previous_contract_bindings = self.contract_bindings
        previous_routine_read_names = self.current_routine_read_names
        self.current_return_type = routine.return_type
        self.current_aborts = routine.aborts or []
        self.current_routine_decl = routine
        self.current_local_types = {param.name: param.type_name for param in routine.params}
        self.inferred_int_locals = set()
        self.contract_bindings = {}
        self.current_routine_read_names = self.routine_read_names(routine)
        lines.extend(f"\t{line}" for line in self.contract_checks(routine.requires, "requires"))
        for stmt in routine.body:
            lines.extend(f"\t{line}" for line in self.statement(stmt))
        if routine.return_type is None and routine.aborts:
            lines.append("\treturn nil")
        self.current_return_type = previous_return_type
        self.current_aborts = previous_aborts
        self.current_routine_decl = previous_routine_decl
        self.current_local_types = previous_local_types
        self.inferred_int_locals = previous_inferred_int_locals
        self.contract_bindings = previous_contract_bindings
        self.current_routine_read_names = previous_routine_read_names
        if routine.is_async:
            self.active_scopes.pop()
        lines.extend(["}", ""])
        return lines

    def ffi_routine_decl(self, routine: RoutineDecl) -> list[str]:
        binding = routine.ffi_binding
        package_alias = binding.import_path.rsplit("/", 1)[-1]
        self.std_imports.add(binding.import_path)
        params = ", ".join(self.param(param) for param in routine.params)
        arg_names = ", ".join(go_local_name(param.name) for param in routine.params)
        call_expr = f"{package_alias}.{binding.symbol}({arg_names})"
        name = go_exported_name(routine.name)
        if isinstance(routine.return_type, ResultTypeName):
            result_go_type = self.go_type_ref(routine.return_type)
            success_lines = self.ffi_result_success_lines(result_go_type, routine.return_type.ok_type)
            return [
                f"func {name}({params}) {result_go_type} {{",
                f"\tffiResult, ffiErr := {call_expr}",
                "\tif ffiErr != nil {",
                f"\t\treturn {result_go_type}{{Ok: false, Error: ffiErr.Error()}}",
                "\t}",
                *success_lines,
                "}",
                "",
            ]
        if routine.return_type is None:
            return [
                f"func {name}({params}) {{",
                f"\t{call_expr}",
                "}",
                "",
            ]
        result_go_type = self.go_type_ref(routine.return_type)
        return [
            f"func {name}({params}) {result_go_type} {{",
            f"\treturn {call_expr}",
            "}",
            "",
        ]

    def ffi_result_success_lines(self, result_go_type: str, ok_type: Any) -> list[str]:
        if isinstance(ok_type, ArrayTypeName) and self.find_record_decl(ok_type.element_type) is not None:
            array_go_type = self.go_type_ref(ok_type)
            element_go_type = self.go_type_string(ok_type.element_type)
            return [
                f"\tffiValue := {array_go_type}{{}}",
                "\tfor ffiIndex := range ffiValue {",
                f"\t\tffiValue[ffiIndex] = {element_go_type}(ffiResult[ffiIndex])",
                "\t}",
                f"\treturn {result_go_type}{{Ok: true, Value: ffiValue}}",
            ]
        record_type_name = ok_type.name if isinstance(ok_type, TypeName) else ok_type
        if isinstance(record_type_name, str) and self.find_record_decl(record_type_name) is not None:
            return [f"\treturn {result_go_type}{{Ok: true, Value: {self.go_type_ref(ok_type)}(ffiResult)}}"]
        return [f"\treturn {result_go_type}{{Ok: true, Value: ffiResult}}"]

    def routine_result_type(self, routine: RoutineDecl) -> str:
        has_aborts = bool(routine.aborts)
        if routine.return_type is None:
            return " error" if has_aborts else ""
        result_type = self.go_type_ref(routine.return_type)
        return f" ({result_type}, error)" if has_aborts else f" {result_type}"

    def param(self, param: Param) -> str:
        return f"{go_local_name(param.name)} {self.go_type_string(param.type_name)}"

    def statement(self, stmt: Any) -> list[str]:
        if isinstance(stmt, LetStmt):
            already_declared = stmt.name in self.current_local_types
            self.current_local_types[stmt.name] = stmt.type_ref
            is_inferred_int = self.go_declared_base(stmt.type_ref) == "Integer" and self.integer_expr_kind(stmt.expr) in {"inferred_int", "untyped"}
            if is_inferred_int:
                self.inferred_int_locals.add(stmt.name)
            if isinstance(stmt.expr, CallExpr):
                call_routine = self.called_routine(stmt.expr.name)
                if call_routine is not None and call_routine.aborts:
                    return self.let_aborting_call(stmt, already_declared, call_routine)
            if already_declared:
                target_type = None if is_inferred_int else stmt.type_ref
                lines = [f"{go_local_name(stmt.name)} = {self.expr_with_type(stmt.expr, target_type)}"]
            else:
                if is_inferred_int:
                    lines = [f"{go_local_name(stmt.name)} := {self.expr_with_type(stmt.expr, None)}"]
                else:
                    lines = [f"var {go_local_name(stmt.name)} {self.go_decl_type_ref(stmt.type_ref, stmt.expr)} = {self.expr_with_type(stmt.expr, stmt.type_ref)}"]
            if stmt.name not in self.current_routine_read_names:
                lines.append(f"_ = {go_local_name(stmt.name)}")
            return lines
        if isinstance(stmt, AssignStmt):
            target_type = None if stmt.name in self.inferred_int_locals else self.current_local_types.get(stmt.name)
            return [f"{go_local_name(stmt.name)} = {self.expr_with_type(stmt.expr, target_type)}"]
        if isinstance(stmt, FieldAssignStmt):
            head, *tail = stmt.path
            target = ".".join([go_local_name(head)] + [go_exported_name(part) for part in tail])
            return [f"{target} = {self.expr(stmt.expr)}"]
        if isinstance(stmt, ReturnStmt):
            wait_lines = []
            for scope_name in reversed(self.active_scopes):
                wait_lines.append(f"{scope_name}.wg.Wait()")

            ret_lines: list[str] = []
            if isinstance(stmt.value, ReturnPlain):
                if isinstance(stmt.value.expr, CallExpr):
                    call_routine = self.called_routine(stmt.value.expr.name)
                    if call_routine is not None and call_routine.aborts:
                        ret_lines = self.return_aborting_call(stmt.value.expr, call_routine)
                if not ret_lines:
                    rendered = self.expr_with_type(stmt.value.expr, self.current_return_type)
                    if self.current_ensures():
                        result_name = self.fresh_local_name("result")
                        lines = [f"var {result_name} {self.go_type_ref(self.current_return_type)} = {rendered}"]
                        lines.extend(self.ensure_checks_for_value(result_name))
                        if self.current_aborts:
                            lines.append(f"return {result_name}, nil")
                        else:
                            lines.append(f"return {result_name}")
                        ret_lines = lines
                    elif self.current_aborts:
                        ret_lines = [f"return {rendered}, nil"]
                    else:
                        ret_lines = [f"return {rendered}"]
            elif isinstance(stmt.value, ReturnOk):
                if not isinstance(self.current_return_type, ResultTypeName):
                    self.unsupported(stmt, "return ok requires a Result return type")
                    ret_lines = ["// unsupported result return"]
                else:
                    result_expr = f"{self.go_result_type_name(self.current_return_type)}{{Ok: true, Value: {self.expr_with_type(stmt.value.expr, self.current_return_type.ok_type)}}}"
                    if self.current_ensures():
                        result_name = self.fresh_local_name("result")
                        lines = [f"{result_name} := {result_expr}"]
                        lines.extend(self.ensure_checks_for_result(result_name))
                        lines.append(f"return {result_name}, nil" if self.current_aborts else f"return {result_name}")
                        ret_lines = lines
                    elif self.current_aborts:
                        ret_lines = [f"return {result_expr}, nil"]
                    else:
                        ret_lines = [f"return {result_expr}"]
            elif isinstance(stmt.value, ReturnError):
                if not isinstance(self.current_return_type, ResultTypeName):
                    self.unsupported(stmt, "return error requires a Result return type")
                    ret_lines = ["// unsupported result return"]
                else:
                    result_expr = f"{self.go_result_type_name(self.current_return_type)}{{Ok: false, Error: {self.go_error_name(stmt.value.error_name)}}}"
                    if self.current_ensures():
                        result_name = self.fresh_local_name("result")
                        lines = [f"{result_name} := {result_expr}"]
                        lines.extend(self.ensure_checks_for_result(result_name))
                        lines.append(f"return {result_name}, nil" if self.current_aborts else f"return {result_name}")
                        ret_lines = lines
                    elif self.current_aborts:
                        ret_lines = [f"return {result_expr}, nil"]
                    else:
                        ret_lines = [f"return {result_expr}"]
            else:
                self.unsupported(stmt, "return form is not supported by Go codegen V1")
                ret_lines = ["// unsupported return"]
            return wait_lines + ret_lines
        if isinstance(stmt, AbortStmt):
            return self.abort_return(stmt.error_name)
        if isinstance(stmt, CheckStmt):
            return [f"if !({self.expr(stmt.expr)}) {{ panic(\"freehold check failed\") }}"]
        if isinstance(stmt, CallStmt):
            builtin_stmt = self.runtime_call_statement(stmt)
            if builtin_stmt is not None:
                return builtin_stmt
            call_routine = self.called_routine(stmt.name)
            if call_routine is not None and call_routine.aborts:
                return self.call_aborting_routine(stmt.name, stmt.args, call_routine)
            args = self.render_call_args(stmt.args, call_routine)
            return [f"{self.callable_name(stmt.name, stmt)}({args})"]
        if isinstance(stmt, IfStmt):
            lines = [f"if {self.expr(stmt.condition)} {{"]
            lines.extend(indent_lines(self.statement_block(stmt.then_body)))
            if stmt.else_body:
                lines.append("} else {")
                lines.extend(indent_lines(self.statement_block(stmt.else_body)))
            lines.append("}")
            return lines
        if isinstance(stmt, WhileStmt):
            lines = [f"for {self.expr(stmt.condition)} {{"]
            lines.extend(indent_lines(self.statement_block(stmt.body)))
            lines.append("}")
            return lines
        if isinstance(stmt, CaseStmt):
            is_pattern_match = len(stmt.branches) > 0 and isinstance(stmt.branches[0], PatternBranch)
            if is_pattern_match:
                case_t = self.infer_expr_type(stmt.expr)
                if isinstance(case_t, str):
                    case_t_str = case_t
                elif isinstance(case_t, TypeName):
                    case_t_str = case_t.name
                else:
                    case_t_str = ""
                base_name = case_t_str
                if "<" in base_name:
                    base_name = base_name.split("<")[0]
                choice_ref_name = self.go_type_ref(case_t)
                choice_decl = self.choices.get(base_name) or self.choices.get(choice_ref_name)
                
                lines = []
                expr_var = self.fresh_local_name("match_expr")
                self.current_local_types[expr_var] = case_t
                lines.append(f"{expr_var} := {self.expr(stmt.expr)}")
                
                for branch_idx, br in enumerate(stmt.branches):
                    constructor = next((c for c in choice_decl.constructors if c.name == br.pattern.name), None)
                    struct_type = f"{choice_ref_name}_{go_exported_name(br.pattern.name)}_struct"
                    
                    if_op = "if" if branch_idx == 0 else "} else if"
                    v_var = "_" if len(br.pattern.args) == 0 else self.fresh_local_name("v")
                    
                    # Bindings to inject
                    bindings = []
                    previous_local_types = dict(self.current_local_types)
                    for idx, arg_name in enumerate(br.pattern.args):
                        param_name = constructor.params[idx].name
                        param_type = constructor.params[idx].type_name
                        # Substitute type if specialized choice
                        if choice_decl.type_params and "<" in case_t_str:
                            m = re.match(r"^(\w+)<(.*)>$", case_t_str)
                            if m:
                                raw_args = [x.strip() for x in m.group(2).split(",")]
                                substitutions = dict(zip(choice_decl.type_params, raw_args))
                                param_type = self.substitute_type_simple(param_type, substitutions)
                        
                        self.current_local_types[arg_name] = self.parse_type_ref_simple(param_type)
                        exported_param_name = go_exported_name(param_name)
                        bindings.append(f"{go_local_name(arg_name)} := {v_var}.{exported_param_name}")
                        bindings.append(f"_ = {go_local_name(arg_name)}")
                    
                    if br.guard is not None:
                        # Guard evaluation in binding context
                        guard_block_lines = []
                        for b_line in bindings:
                            guard_block_lines.append(b_line)
                        guard_block_lines.append(f"return {self.expr(br.guard)}")
                        guard_block_inner = "; ".join(guard_block_lines)
                        cond = f"{v_var}, ok := {expr_var}.({struct_type}); ok && func() bool {{ {guard_block_inner} }}()"
                    else:
                        cond = f"{v_var}, ok := {expr_var}.({struct_type}); ok"
                    
                    lines.append(f"{if_op} {cond} {{")
                    body_lines = list(bindings)
                    body_lines.extend(self.statement_block(br.body))
                    lines.extend(indent_lines(body_lines))
                    self.current_local_types = previous_local_types
                
                if stmt.default_body:
                    lines.append("} else {")
                    lines.extend(indent_lines(self.statement_block(stmt.default_body)))
                lines.append("}")
                return lines
            else:
                lines = [f"switch {self.expr(stmt.expr)} {{"]
                for branch in stmt.branches:
                    lines.append(f"case {self.expr(branch.value)}:")
                    lines.extend(indent_lines(self.statement_block(branch.body)))
                if stmt.default_body:
                    lines.append("default:")
                    lines.extend(indent_lines(self.statement_block(stmt.default_body)))
                lines.append("}")
                return lines
        if isinstance(stmt, ScopeStmt):
            self.needs_async_helpers = True
            self.std_imports.add("sync")
            self.std_imports.add("context")
            scope_name = go_local_name(stmt.name)
            parent_ctx = self.current_context_expr()
            self.active_scopes.append(scope_name)
            lines = ["{"]
            lines.append(f"\t{scope_name} := FreeholdScope{{}}")
            lines.append(f"\t{scope_name}.ctx, {scope_name}.cancel = context.WithCancel({parent_ctx})")
            lines.append(f"\t{scope_name}.priority = 3")
            lines.append(f"\t{scope_name}.sem = nil")
            lines.append(f"\tdefer {scope_name}.cancel()")
            lines.append(f"\t_ = {scope_name}")
            lines.extend(indent_lines(self.statement_block(stmt.spawn_body)))
            lines.extend(indent_lines(self.statement_block(stmt.join_body)))
            lines.extend(indent_lines(self.statement_block(stmt.result_body)))
            has_return = any(isinstance(s, ReturnStmt) for s in stmt.spawn_body + stmt.join_body + stmt.result_body)
            if not has_return:
                lines.append(f"\t{scope_name}.wg.Wait()")
            lines.append("}")
            self.active_scopes.pop()
            return lines
        if isinstance(stmt, ParallelStmt):
            self.needs_async_helpers = True
            self.std_imports.add("sync")
            self.std_imports.add("context")
            scope_name = go_local_name(stmt.block_name or "parallel_block")
            parent_ctx = self.current_context_expr()
            self.active_scopes.append(scope_name)
            lines = ["{"]
            lines.append(f"\t{scope_name} := FreeholdScope{{}}")
            lines.append(f"\t{scope_name}.ctx, {scope_name}.cancel = context.WithCancel({parent_ctx})")
            lines.append(f"\t{scope_name}.priority = 3")
            if stmt.limit is not None:
                lines.append(f"\t{scope_name}.sem = make(chan struct{{}}, int({self.expr(stmt.limit)}))")
            else:
                lines.append(f"\t{scope_name}.sem = nil")
            lines.append(f"\tdefer {scope_name}.cancel()")
            lines.append(f"\t_ = {scope_name}")
            lines.extend(indent_lines(self.statement_block(stmt.body)))
            has_return = any(isinstance(s, ReturnStmt) for s in stmt.body)
            if not has_return:
                lines.append(f"\t{scope_name}.wg.Wait()")
            lines.append("}")
            self.active_scopes.pop()
            return lines
        self.unsupported(stmt, "statement not supported by Go codegen V1")
        return ["// unsupported statement"]

    def statement_block(self, statements: list[Any]) -> list[str]:
        previous_local_types = dict(self.current_local_types)
        lines: list[str] = []
        for statement in statements:
            lines.extend(self.statement(statement))
        self.current_local_types = previous_local_types
        return lines or ["// empty"]

    def routine_read_names(self, routine: RoutineDecl) -> set[str]:
        names: set[str] = set()
        for expr in routine.requires or []:
            names.update(self.expr_read_names(expr))
        for expr in routine.ensures or []:
            names.update(self.expr_read_names(expr))
        for abort in routine.aborts or []:
            if abort.condition is not None:
                names.update(self.expr_read_names(abort.condition))
        for stmt in routine.body:
            names.update(self.statement_read_names(stmt))
        return names

    def statement_read_names(self, stmt: Any) -> set[str]:
        names: set[str] = set()
        if isinstance(stmt, LetStmt):
            names.update(self.expr_read_names(stmt.expr))
        elif isinstance(stmt, AssignStmt):
            names.update(self.expr_read_names(stmt.expr))
        elif isinstance(stmt, FieldAssignStmt):
            if stmt.path:
                names.add(stmt.path[0])
            names.update(self.expr_read_names(stmt.expr))
        elif isinstance(stmt, ReturnStmt):
            names.update(self.return_read_names(stmt.value))
        elif isinstance(stmt, CheckStmt):
            names.update(self.expr_read_names(stmt.expr))
        elif isinstance(stmt, CallStmt):
            for arg in stmt.args:
                names.update(self.expr_read_names(arg))
        elif isinstance(stmt, IfStmt):
            names.update(self.expr_read_names(stmt.condition))
            for nested in stmt.then_body + stmt.else_body:
                names.update(self.statement_read_names(nested))
        elif isinstance(stmt, WhileStmt):
            names.update(self.expr_read_names(stmt.condition))
            for invariant in stmt.invariants:
                names.update(self.expr_read_names(invariant))
            if stmt.variant is not None:
                names.update(self.expr_read_names(stmt.variant))
            for nested in stmt.body:
                names.update(self.statement_read_names(nested))
        elif isinstance(stmt, CaseStmt):
            names.update(self.expr_read_names(stmt.expr))
            for branch in stmt.branches:
                if hasattr(branch, "pattern") and branch.pattern is not None:
                    # In PatternBranch, names from guards or patterns can be processed
                    if branch.guard is not None:
                        names.update(self.expr_read_names(branch.guard))
                elif hasattr(branch, "value"):
                    names.update(self.expr_read_names(branch.value))
                for nested in branch.body:
                    names.update(self.statement_read_names(nested))
            for nested in stmt.default_body:
                names.update(self.statement_read_names(nested))
        elif isinstance(stmt, ScopeStmt):
            for nested in stmt.spawn_body + stmt.join_body + stmt.result_body:
                names.update(self.statement_read_names(nested))
        return names

    def return_read_names(self, value: Any) -> set[str]:
        if isinstance(value, ReturnPlain):
            return self.expr_read_names(value.expr)
        if isinstance(value, ReturnOk):
            return self.expr_read_names(value.expr)
        return set()

    def expr_read_names(self, expr: Any) -> set[str]:
        names: set[str] = set()
        if isinstance(expr, VarExpr):
            names.add(expr.name)
        elif isinstance(expr, SpecialResultExpr):
            names.add(expr.name)
        elif isinstance(expr, FieldAccessExpr):
            if expr.path:
                names.add(expr.path[0])
        elif isinstance(expr, IndexedFieldAccessExpr):
            names.add(expr.name)
            names.update(self.expr_read_names(expr.index))
        elif isinstance(expr, IndexExpr):
            names.add(expr.name)
            names.update(self.expr_read_names(expr.index))
        elif isinstance(expr, UnaryExpr):
            names.update(self.expr_read_names(expr.expr))
        elif isinstance(expr, BinaryExpr):
            names.update(self.expr_read_names(expr.left))
            names.update(self.expr_read_names(expr.right))
        elif isinstance(expr, CallExpr):
            for arg in expr.args:
                names.update(self.expr_read_names(arg))
        elif isinstance(expr, AwaitExpr):
            names.update(self.expr_read_names(expr.expr))
        elif isinstance(expr, NamedArg):
            names.update(self.expr_read_names(expr.expr))
        elif isinstance(expr, RecordLiteralExpr):
            for arg in expr.args:
                names.update(self.expr_read_names(arg))
        elif isinstance(expr, ArrayLiteralExpr):
            for item in expr.items:
                names.update(self.expr_read_names(item))
        return names

    def abort_return(self, error_name: str) -> list[str]:
        self.std_imports.add("errors")
        wait_lines = []
        for scope_name in reversed(self.active_scopes):
            wait_lines.append(f"{scope_name}.wg.Wait()")
        if self.current_return_type is None:
            return wait_lines + [f"return errors.New({self.go_error_name(error_name)})"]
        return wait_lines + [f"return {self.go_zero_value(self.current_return_type)}, errors.New({self.go_error_name(error_name)})"]

    def call_aborting_routine(self, name: str, args: list[Any], routine: RoutineDecl) -> list[str]:
        args_text = self.render_call_args(args, routine)
        call_text = f"{self.callable_name(name, routine)}({args_text})"
        if routine.return_type is None:
            lines = [f"if err := {call_text}; err != nil {{"]
        else:
            lines = [f"_, err := {call_text}", "if err != nil {"]
        lines.extend(indent_lines(self.propagate_abort_return()))
        lines.append("}")
        return lines

    def return_aborting_call(self, call: CallExpr, routine: RoutineDecl) -> list[str]:
        if routine.return_type is None:
            self.unsupported(call, "aborting procedure call cannot be returned as a value")
            return ["// unsupported aborting procedure return"]
        args_text = self.render_call_args(call.args, routine)
        call_text = f"{self.callable_name(call.name, call)}({args_text})"
        lines = [f"value, err := {call_text}", "if err != nil {"]
        lines.extend(indent_lines(self.propagate_abort_return()))
        lines.append("}")
        if self.current_ensures():
            lines.extend(self.ensure_checks_for_value("value"))
        lines.append("return value, nil" if self.current_aborts else "return value")
        return lines

    def let_aborting_call(self, stmt: LetStmt, already_declared: bool, routine: RoutineDecl) -> list[str]:
        args_text = self.render_call_args(stmt.expr.args, routine)
        call_text = f"{self.callable_name(stmt.expr.name, stmt.expr)}({args_text})"
        name = go_local_name(stmt.name)
        if already_declared:
            temp_name = self.fresh_local_name(stmt.name)
            lines = [f"{temp_name}, err := {call_text}"]
        else:
            temp_name = name
            lines = [f"{name}, err := {call_text}"]
        lines.append("if err != nil {")
        lines.extend(indent_lines(self.propagate_abort_return()))
        lines.append("}")
        if already_declared:
            lines.append(f"{name} = {temp_name}")
        if stmt.name not in self.current_routine_read_names:
            lines.append(f"_ = {name}")
        return lines

    def propagate_abort_return(self) -> list[str]:
        if not self.current_aborts:
            self.unsupported(self.program, "aborting call requires the enclosing routine to declare abort propagation")
            return ["// unsupported abort propagation"]
        wait_lines = []
        for scope_name in reversed(self.active_scopes):
            wait_lines.append(f"{scope_name}.wg.Wait()")
        if self.current_return_type is None:
            return wait_lines + ["return err"]
        return wait_lines + [f"return {self.go_zero_value(self.current_return_type)}, err"]

    def local_called_routine(self, name: str) -> RoutineDecl | None:
        current_prefix = f"{self.program.module_name}."
        local_name = name[len(current_prefix):] if name.startswith(current_prefix) else name
        if "." in local_name:
            return None
        return self.routines_by_name.get(local_name)

    def called_routine(self, name: str) -> RoutineDecl | None:
        local = self.local_called_routine(name)
        if local is not None:
            return local
        return self.imported_called_routine(name)

    def imported_called_routine(self, name: str) -> RoutineDecl | None:
        if "." in name:
            for module_name, resolved in sorted(self.resolved_modules.items(), key=lambda item: len(item[0]), reverse=True):
                prefix = f"{module_name}."
                if not name.startswith(prefix):
                    continue
                routine_name = name[len(prefix):]
                if "." in routine_name or resolved.verified is None:
                    return None
                return resolved.verified.routines.get(routine_name)
            return None
        exposed_module = self.exposed_symbols.get(name)
        if exposed_module is None:
            return None
        resolved = self.resolved_modules.get(exposed_module)
        if resolved is None or resolved.verified is None:
            return None
        return resolved.verified.routines.get(name)

    def expr(self, expr: Any) -> str:
        return self.expr_at(expr, 0)

    def expr_with_type(self, expr: Any, type_ref: Any) -> str:
        if isinstance(expr, ArrayLiteralExpr):
            go_t = None
            if isinstance(type_ref, ArrayTypeName):
                go_t = f"[{type_ref.size}]{self.go_type_string(type_ref.element_type)}"
            elif isinstance(type_ref, str):
                go_t = self.go_type_string(type_ref)
                if not go_t.startswith("["):
                    go_t = None
            if go_t is not None:
                values = ", ".join(self.expr(item) for item in expr.items)
                return f"{go_t}{{{values}}}"
        if isinstance(expr, CallExpr):
            rendered = self.runtime_call_expr(expr, type_ref)
            if rendered is not None:
                return rendered
        rendered_expr = self.expr_at(expr, 0, expected_type=type_ref)
        if self.integer_expr_kind(expr) == "inferred_int" and self.go_declared_base(type_ref) == "Integer":
            return f"int64({rendered_expr})"
        return rendered_expr

    def record_field_type(self, record_name: str, field_name: str) -> Any | None:
        short_rec = record_name.split(".")[-1]
        for decl in self.program.declarations:
            if isinstance(decl, RecordTypeDecl):
                decl_short = decl.name.split(".")[-1]
                if decl.name == record_name or decl_short == short_rec:
                    for field in decl.fields:
                        if field.name == field_name:
                            return field.type_name
        for module_name, resolved in self.resolved_modules.items():
            if resolved.verified is not None:
                short_name = record_name.split(".")[-1]
                for rec_name, rec in resolved.verified.records.items():
                    if rec_name == record_name or rec_name == short_name:
                        if field_name in rec.fields:
                            return rec.fields[field_name]
        return None

    def go_type_ref(self, type_ref: Any) -> str:
        if isinstance(type_ref, ResultTypeName):
            self.result_types.setdefault(type_to_string(type_ref), type_ref)
        return self.go_type_ref_text(type_ref)

    def go_decl_type_ref(self, type_ref: Any, initializer: Any) -> str:
        if isinstance(type_ref, ResultTypeName):
            imported_module = self.imported_result_initializer_module(type_ref, initializer)
            if imported_module is not None:
                self.used_import_modules.add(imported_module)
                return f"{go_import_alias(imported_module)}.{go_result_type_name(type_ref)}"
        return self.go_type_ref(type_ref)

    def go_type_ref_text(self, type_ref: Any) -> str:
        if isinstance(type_ref, str):
            return self.go_type_string(type_ref)
        if isinstance(type_ref, TypeName):
            return self.go_type_string(type_ref.name)
        if isinstance(type_ref, ArrayTypeName):
            return f"[{type_ref.size}]{self.go_type_string(type_ref.element_type)}"
        if isinstance(type_ref, ResultTypeName):
            return self.go_result_type_name(type_ref)
        raise GoCodegenError(f"unsupported Go type reference: {type_to_string(type_ref)}")

    def go_type_string(self, type_name: str) -> str:
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            if base == "Array" and len(args) == 2 and args[1].isdigit():
                return f"[{args[1]}]{self.go_type_string(args[0])}"
            if base == "Result" and len(args) == 2:
                return self.go_result_type_name(ResultTypeName(TypeName(args[0]), args[1]))
            if base == "JoinHandle" and len(args) == 1:
                self.needs_async_helpers = True
                return f"FreeholdJoinHandle[{self.go_type_string(args[0])}]"
            if base == "Channel" and len(args) == 1:
                self.needs_async_helpers = True
                return f"chan {self.go_type_string(args[0])}"
            if base == "Sender" and len(args) == 1:
                self.needs_async_helpers = True
                return f"chan<- {self.go_type_string(args[0])}"
            if base == "Receiver" and len(args) == 1:
                self.needs_async_helpers = True
                return f"<-chan {self.go_type_string(args[0])}"
            qualified_base = self.qualify_type_name(base, self.program.module_name)
            qualified_args = [self.qualify_type_name(arg, self.program.module_name) for arg in args]
            specialized = self.go_specialized_name(qualified_base, qualified_args)
            return go_exported_name(specialized)
        
        current_prefix = f"{self.program.module_name}."
        if type_name.startswith(current_prefix):
            return go_exported_name(type_name[len(current_prefix):])
            
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if type_name.startswith(prefix):
                symbol_name = type_name[len(prefix):]
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}"
                
        imported = self.imported_type_module(type_name)
        if imported is not None:
            self.used_import_modules.add(imported)
            return f"{go_import_alias(imported)}.{go_exported_name(type_name)}"
        if type_name == "Scope":
            self.needs_async_helpers = True
            return "FreeholdScope"
        return go_type_string(type_name)

    def go_zero_value(self, type_ref: Any) -> str:
        if isinstance(type_ref, str):
            return self.go_zero_value_for_type_name(type_ref)
        if isinstance(type_ref, TypeName):
            return self.go_zero_value_for_type_name(type_ref.name)
        if isinstance(type_ref, ArrayTypeName):
            return f"[{type_ref.size}]{self.go_type_string(type_ref.element_type)}{{}}"
        if isinstance(type_ref, ResultTypeName):
            return f"{self.go_result_type_name(type_ref)}{{}}"
        return "nil"

    def go_zero_value_for_type_name(self, type_name: str) -> str:
        current_prefix = f"{self.program.module_name}."
        if type_name.startswith(current_prefix):
            return f"{go_exported_name(type_name[len(current_prefix):])}{{}}"
            
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if type_name.startswith(prefix):
                symbol_name = type_name[len(prefix):]
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}{{}}"
                
        imported = self.imported_type_module(type_name)
        if imported is not None:
            self.used_import_modules.add(imported)
            return f"{go_import_alias(imported)}.{go_exported_name(type_name)}{{}}"
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            if base == "Array" and len(args) == 2 and args[1].isdigit():
                return f"[{args[1]}]{self.go_type_string(args[0])}{{}}"
            if base == "Result" and len(args) == 2:
                return f"{self.go_result_type_name(ResultTypeName(TypeName(args[0]), args[1]))}{{}}"
            return f"{self.go_type_string(type_name)}{{}}"
        return go_zero_value_for_type_name(type_name)

    def go_error_name(self, error_name: str) -> str:
        current_prefix = f"{self.program.module_name}."
        if error_name.startswith(current_prefix):
            return go_exported_name(error_name[len(current_prefix):])
            
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if error_name.startswith(prefix):
                symbol_name = error_name[len(prefix):]
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}"
                
        imported = self.imported_type_module(error_name)
        if imported is not None:
            self.used_import_modules.add(imported)
            return f"{go_import_alias(imported)}.{go_exported_name(error_name)}"
        return go_exported_name(error_name)

    def go_result_type_name(self, type_ref: ResultTypeName) -> str:
        imported = self.imported_result_type_module(type_ref)
        result_name = go_result_type_name(type_ref)
        if imported is None:
            return result_name
        self.used_import_modules.add(imported)
        return f"{go_import_alias(imported)}.{result_name}"

    def imported_result_type_module(self, type_ref: ResultTypeName) -> str | None:
        error_module = self.imported_type_module(type_ref.error_type)
        if error_module is None:
            return None
        if self.type_ref_has_local_type(type_ref.ok_type):
            return None
        return error_module

    def imported_result_initializer_module(self, type_ref: ResultTypeName, initializer: Any) -> str | None:
        expr = initializer.expr if isinstance(initializer, AwaitExpr) else initializer
        if not isinstance(expr, CallExpr):
            return None
        routine = self.called_routine(expr.name)
        if routine is None or not isinstance(routine.return_type, ResultTypeName):
            return None
        if go_result_type_name(routine.return_type) != go_result_type_name(type_ref):
            return None
        return self.imported_call_module(expr.name)

    def imported_call_module(self, name: str) -> str | None:
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            if name.startswith(f"{module_name}."):
                return module_name
        exposed_module = self.exposed_symbols.get(name)
        if exposed_module is not None and name not in self.local_routines:
            return exposed_module
        return None

    def type_ref_has_local_type(self, type_ref: Any) -> bool:
        if isinstance(type_ref, TypeName):
            return type_ref.name in self.local_types
        if isinstance(type_ref, ArrayTypeName):
            return type_ref.element_type in self.local_types
        return False

    def imported_type_module(self, type_name: str) -> str | None:
        if type_name in self.local_types:
            return None
        return self.exposed_type_modules.get(type_name)

    def expr_at(self, expr: Any, parent_precedence: int, side: str = "", expected_type: Any = None) -> str:
        if isinstance(expr, NumberExpr):
            return str(expr.value)
        if isinstance(expr, DoubleExpr):
            return repr(expr.value)
        if isinstance(expr, BoolExpr):
            return "true" if expr.value else "false"
        if isinstance(expr, StringExpr):
            return json.dumps(expr.value)
        if isinstance(expr, VarExpr):
            if expr.name in self.contract_bindings:
                return self.contract_bindings[expr.name]
            if expr.name in self.local_errors or expr.name in self.exposed_error_modules:
                return self.go_error_name(expr.name)
            if expr.name in self.constructor_to_choice:
                choice_name, choice_decl, constr = self.constructor_to_choice[expr.name]
                if choice_decl.type_params:
                    if expected_type is not None:
                        try:
                            resolved_choice_name = self.go_type_ref(expected_type)
                            return f"{resolved_choice_name}_{go_exported_name(constr.name)}_ctor()"
                        except Exception:
                            pass
                    return f"{go_exported_name(choice_decl.name)}_{go_exported_name(constr.name)}_ctor[any]()"
                else:
                    return f"{go_exported_name(choice_decl.name)}_{go_exported_name(constr.name)}_ctor()"
            return go_local_name(expr.name)
        if isinstance(expr, SpecialResultExpr):
            if expr.name in self.contract_bindings:
                return self.contract_bindings[expr.name]
            self.unsupported(expr, f"contract token is not available in this Go codegen context: {expr.name}")
            return "false"
        if isinstance(expr, FieldAccessExpr):
            head, *tail = expr.path
            if head in self.contract_bindings:
                return ".".join([self.contract_bindings[head]] + [go_exported_name(part) for part in tail])
            return ".".join([go_local_name(head)] + [go_exported_name(part) for part in tail])
        if isinstance(expr, IndexExpr):
            base = self.contract_bindings.get(expr.name, go_local_name(expr.name))
            return f"{base}[{self.expr(expr.index)}]"
        if isinstance(expr, IndexedFieldAccessExpr):
            base = self.contract_bindings.get(expr.name, go_local_name(expr.name))
            indexed = f"{base}[{self.expr(expr.index)}]"
            return ".".join([indexed] + [go_exported_name(field) for field in expr.fields])
        if isinstance(expr, ForAllExpr):
            var_name = go_local_name(expr.var_name)
            lower = self.expr(expr.lower)
            upper = self.expr(expr.upper)
            previous_local_types = dict(self.current_local_types)
            self.current_local_types[expr.var_name] = TypeName("Integer")
            body = self.expr(expr.expr)
            self.current_local_types = previous_local_types
            return f"func() bool {{ for {var_name} := int64({lower}); {var_name} <= int64({upper}); {var_name}++ {{ if !({body}) {{ return false }} }}; return true }}()"
        if isinstance(expr, ExistsExpr):
            var_name = go_local_name(expr.var_name)
            lower = self.expr(expr.lower)
            upper = self.expr(expr.upper)
            previous_local_types = dict(self.current_local_types)
            self.current_local_types[expr.var_name] = TypeName("Integer")
            body = self.expr(expr.expr)
            self.current_local_types = previous_local_types
            return f"func() bool {{ for {var_name} := int64({lower}); {var_name} <= int64({upper}); {var_name}++ {{ if {body} {{ return true }} }}; return false }}()"
        if isinstance(expr, AwaitExpr):
            return self.await_expr(expr)
        if isinstance(expr, SpawnExpr):
            self.needs_async_helpers = True
            self.std_imports.add("sync")
            if not isinstance(expr.target, CallExpr):
                self.unsupported(expr, "spawn target must be a call expression")
                return "nil"
            routine = self.called_routine(expr.target.name)
            if routine is None:
                self.unsupported(expr, f"unknown spawn target routine: {expr.target.name}")
                return "nil"

            if routine.return_type is None:
                value_type = "Void"
            else:
                value_type = self.go_type_string(type_to_string(routine.return_type))

            if not self.active_scopes:
                self.unsupported(expr, "spawn expression requires an active scope")
                return "nil"
            scope_expr = self.active_scopes[-1]

            priority_expr_str = "3"
            if "priority" in expr.attributes:
                priority_expr_str = f"int({self.expr(expr.attributes['priority'])})"

            args_text = self.render_call_args(expr.target.args, routine)
            call_rendered = f"{self.callable_name(expr.target.name, expr.target)}({args_text})"

            if routine.return_type is None:
                return f"freeholdSpawn[{value_type}](&{scope_expr}.wg, {priority_expr_str}, {scope_expr}.sem, func() {value_type} {{ {call_rendered}; return {value_type}{{}} }})"
            else:
                return f"freeholdSpawn[{value_type}](&{scope_expr}.wg, {priority_expr_str}, {scope_expr}.sem, func() {value_type} {{ return {call_rendered} }})"
        if isinstance(expr, UnaryExpr):
            precedence = unary_precedence(expr.op)
            rendered = f"{go_operator(expr.op)}{self.expr_at(expr.expr, precedence)}"
            return parenthesize_if_needed(rendered, precedence, parent_precedence, side, expr.op)
        if isinstance(expr, BinaryExpr):
            precedence = go_precedence(expr.op)
            if expr.op in {"=", "!=", "<", "<=", ">", ">="}:
                left_type = type_to_string(self.infer_expr_type(expr.left))
                right_type = type_to_string(self.infer_expr_type(expr.right))
                if left_type in {"BigInteger", "BigFloat"} or right_type in {"BigInteger", "BigFloat"}:
                    go_op = "==" if expr.op == "=" else expr.op
                    rendered = f"{self.expr(expr.left)}.Cmp({self.expr(expr.right)}) {go_op} 0"
                else:
                    rendered = f"{self.expr_for_integer_comparison(expr.left, expr.right, precedence, 'left')} {go_operator(expr.op)} {self.expr_for_integer_comparison(expr.right, expr.left, precedence, 'right')}"
            else:
                rendered = f"{self.expr_at(expr.left, precedence, 'left')} {go_operator(expr.op)} {self.expr_at(expr.right, precedence, 'right')}"
            return parenthesize_if_needed(rendered, precedence, parent_precedence, side, expr.op)
        if isinstance(expr, RecordLiteralExpr):
            args = ", ".join(f"{go_exported_name(arg.name)}: {self.expr_with_type(arg.expr, self.record_field_type(expr.type_name, arg.name))}" for arg in expr.args)
            return f"{self.go_type_string(expr.type_name)}{{{args}}}"
        if isinstance(expr, ArrayLiteralExpr):
            values = ", ".join(self.expr(item) for item in expr.items)
            return f"[]any{{{values}}}"
        if isinstance(expr, CallExpr):
            if expr.name in self.constructor_to_choice:
                choice_name, choice_decl, constr = self.constructor_to_choice[expr.name]
                resolved_choice_name = None
                if choice_decl.type_params:
                    if expected_type is not None:
                        try:
                            resolved_choice_name = self.go_type_ref(expected_type)
                        except Exception:
                            pass
                    if resolved_choice_name is None:
                        type_args = []
                        for param, arg in zip(constr.params, expr.args):
                            if param.type_name in choice_decl.type_params:
                                arg_type = self.infer_expr_type(arg)
                                type_args.append(type_to_string(arg_type))
                            else:
                                type_args.append(param.type_name)
                        if type_args:
                            try:
                                resolved_choice_name = self.go_type_ref(TypeName(f"{choice_decl.name}<{', '.join(type_args)}>"))
                            except Exception:
                                pass
                if resolved_choice_name is None:
                    resolved_choice_name = go_exported_name(choice_decl.name)
                
                ctor_name = f"{resolved_choice_name}_{go_exported_name(constr.name)}_ctor"
                rendered_args = []
                for index, arg in enumerate(expr.args):
                    if index < len(constr.params) and constr.params[index].type_name == "Integer":
                        rendered_args.append(self.expr_as_int64(arg))
                    else:
                        rendered_args.append(self.expr(arg))
                args_str = ", ".join(rendered_args)
                return f"{ctor_name}({args_str})"

            runtime_call = self.runtime_call_expr(expr, None)
            if runtime_call is not None:
                return runtime_call
            call_routine = self.called_routine(expr.name)
            if call_routine is not None and call_routine.aborts:
                self.unsupported(expr, "aborting calls in expressions are not supported by Go codegen V1")
            args = self.render_call_args(expr.args, call_routine)
            return f"{self.callable_name(expr.name, expr)}({args})"
        if isinstance(expr, IsExpr):
            return "true"
        self.unsupported(expr, "expression not supported by Go codegen V1")
        return "nil"

    def await_expr(self, expr: AwaitExpr) -> str:
        if isinstance(expr.expr, VarExpr):
            handle_type = self.current_local_types.get(expr.expr.name)
            if self.is_join_handle_type(handle_type):
                inner = self.join_handle_inner_type_string(handle_type)
                value_type = self.go_type_string(inner) if inner else "any"
                ctx_expr = self.current_context_expr()
                return f"freeholdJoin[{value_type}]({ctx_expr}, {go_local_name(expr.expr.name)})"
        return self.expr(expr.expr)

    def callable_name(self, name: str, node: Any) -> str:
        routine = self.called_routine(name)
        if routine is not None and routine.type_params:
            qualified_name = self.qualify_routine_name(name, self.program.module_name)
            if node.type_args:
                type_args = [self.qualify_type_name(ta, self.program.module_name) for ta in node.type_args]
            else:
                inferred = self.infer_type_args(routine, node)
                type_args = [self.qualify_type_name(ta, self.program.module_name) for ta in inferred]
            specialized = self.go_specialized_name(qualified_name, type_args)
            
            # Check if this specialized routine belongs to an imported module.
            # If so, prefix the specialized name with that module's Go import alias.
            resolved_module_name = self.program.module_name
            if "." in qualified_name:
                resolved_module_name = ".".join(qualified_name.split(".")[:-1])
            elif qualified_name in self.exposed_symbols:
                exposed = self.exposed_symbols[qualified_name]
                if exposed is not None:
                    resolved_module_name = exposed

            if resolved_module_name != self.program.module_name:
                self.used_import_modules.add(resolved_module_name)
                return f"{go_import_alias(resolved_module_name)}.{go_exported_name(specialized)}"
            return go_exported_name(specialized)

        resolved_name = name
        current_prefix = f"{self.program.module_name}."
        if resolved_name.startswith(current_prefix):
            return go_exported_name(resolved_name[len(current_prefix):])
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if resolved_name.startswith(prefix):
                symbol_name = resolved_name[len(prefix):]
                if "." in symbol_name:
                    self.unsupported(node, f"nested imported routine names are not supported by Go codegen V1: {resolved_name}")
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}"
        if "." in resolved_name:
            parts = resolved_name.split(".")
            if len(parts) == 2 and parts[0] in self.imports_by_module:
                self.used_import_modules.add(parts[0])
                return f"{go_import_alias(parts[0])}.{go_exported_name(parts[1])}"
            self.unsupported(node, f"qualified call target is not imported by this module: {resolved_name}")
            return go_qualified_name(resolved_name)
        exposed_module = self.exposed_symbols.get(name)
        if exposed_module is None and name in self.exposed_symbols:
            self.unsupported(node, f"ambiguous exposed symbol in imported modules: {name}")
            return go_exported_name(resolved_name)
        if exposed_module is not None and resolved_name not in self.local_routines:
            self.used_import_modules.add(exposed_module)
            return f"{go_import_alias(exposed_module)}.{go_exported_name(resolved_name)}"
        return go_exported_name(resolved_name)

    def runtime_call_statement(self, stmt: CallStmt) -> list[str] | None:
        resolved_name = stmt.name
        exposed_module = self.exposed_symbols.get(stmt.name)
        if exposed_module is not None and stmt.name not in self.local_routines:
            resolved_name = f"{exposed_module}.{stmt.name}"

        if resolved_name == "Std.IO.log":
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            return [f"fmt.Println({self.expr(stmt.args[0])})"]
        if resolved_name == "Std.IO.logf":
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            if len(stmt.args) == 1:
                return [f"fmt.Println({self.expr(stmt.args[0])})"]
            return [f"fmt.Println({self.render_string_template_call(stmt.args)})"]
        if resolved_name in {"Std.IO.log_int", "Std.IO.log_bool", "Std.IO.log_double"}:
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            return [f"fmt.Println({self.expr(stmt.args[0])})"]
        if resolved_name.endswith(".cancel"):
            scope_var = go_local_name(resolved_name.split(".")[0])
            return [f"{scope_var}.cancel()"]
        if resolved_name.endswith(".timeout"):
            scope_var = go_local_name(resolved_name.split(".")[0])
            self.std_imports.add("time")
            self.std_imports.add("context")
            return [f"{scope_var}.ctx, {scope_var}.cancel = context.WithTimeout({scope_var}.ctx, time.Duration({self.expr(stmt.args[0])})*time.Millisecond)"]
        if resolved_name.endswith(".priority"):
            scope_var = go_local_name(resolved_name.split(".")[0])
            return [f"{scope_var}.priority = int({self.expr(stmt.args[0])})"]
        if resolved_name.endswith(".limit"):
            scope_var = go_local_name(resolved_name.split(".")[0])
            return [f"{scope_var}.sem = make(chan struct{{}}, {self.expr(stmt.args[0])})"]
        return None

    def runtime_call_expr(self, expr: CallExpr, expected_type: Any) -> str | None:
        resolved_name = expr.name
        exposed_module = self.exposed_symbols.get(expr.name)
        if exposed_module is not None and expr.name not in self.local_routines:
            resolved_name = f"{exposed_module}.{expr.name}"

        routine = self.called_routine(expr.name)
        if routine is not None and routine.ffi_binding is not None:
            return None

        if resolved_name == "System.args":
            self.std_imports.add("os")
            res_type = ArrayTypeName("String", 10)
            # Ensure the wrapper for ArrayString10 is processed or we just use [10]string
            return "func() [10]string { var res [10]string; for i := 0; i < 10 && i < len(os.Args)-1; i++ { res[i] = os.Args[i+1] }; return res }()"

        if resolved_name == "System.run_command":
            self.std_imports.add("os/exec")
            self.std_imports.add("runtime")
            return f"func() int64 {{ cmdStr := {self.expr(expr.args[0])}; var cmd *exec.Cmd; if runtime.GOOS == \"windows\" {{ cmd = exec.Command(\"cmd\", \"/c\", cmdStr) }} else {{ cmd = exec.Command(\"sh\", \"-c\", cmdStr) }}; err := cmd.Run(); if err != nil {{ if exitError, ok := err.(*exec.ExitError); ok {{ return int64(exitError.ExitCode()) }}; return -1 }}; return 0 }}()"

        if resolved_name == "System.get_env":
            self.std_imports.add("os")
            return f"os.Getenv({self.expr(expr.args[0])})"

        if resolved_name == "File.read_to_string":
            self.std_imports.add("os")
            self.used_import_modules.add("File")
            result_type = f"{go_import_alias('File')}.ResultStringString"
            return f"func() {result_type} {{ content, err := os.ReadFile({self.expr(expr.args[0])}); if err != nil {{ return {result_type}{{Ok: false, Error: err.Error()}} }}; return {result_type}{{Ok: true, Value: string(content)}} }}()"

        if resolved_name == "File.write_string":
            self.std_imports.add("os")
            self.std_imports.add("path/filepath")
            self.used_import_modules.add("File")
            result_type = f"{go_import_alias('File')}.ResultBooleanString"
            return f"func() {result_type} {{ dir := filepath.Dir({self.expr(expr.args[0])}); if err := os.MkdirAll(dir, 0755); err != nil {{ return {result_type}{{Ok: false, Error: err.Error()}} }}; err := os.WriteFile({self.expr(expr.args[0])}, []byte({self.expr(expr.args[1])}), 0644); if err != nil {{ return {result_type}{{Ok: false, Error: err.Error()}} }}; return {result_type}{{Ok: true, Value: true}} }}()"

        async_call = self.async_runtime_call_expr(expr)
        if async_call is not None:
            return async_call
        if expr.name == "Json.stringify":
            self.std_imports.add("encoding/json")
            self.needs_json_helper = True
            return f"freeholdJSONString({self.expr(expr.args[0])})"
        if expr.name == "Json.parse":
            self.std_imports.add("encoding/json")
            self.std_imports.add("fmt")
            self.std_imports.add("io")
            self.std_imports.add("strings")
            self.needs_json_parse_helper = True
            target_type = expr.type_args[0]
            res_type = ResultTypeName(TypeName(target_type), "SchemaError")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            result_name = self.go_result_type_name(res_type)
            value_type = self.go_type_string(target_type)
            source = self.expr(expr.args[0])
            return f"func() {result_name} {{ var value {value_type}; raw := []byte({source}); if err := freeholdRejectDuplicateJSONKeys(json.RawMessage(raw), \"value\"); err != nil {{ return {result_name}{{Ok: false, Error: err.Error()}} }}; if err := freeholdValidateJSONValue(json.RawMessage(raw), reflect.TypeOf(value), \"value\"); err != nil {{ return {result_name}{{Ok: false, Error: err.Error()}} }}; decoder := json.NewDecoder(strings.NewReader(string(raw))); decoder.DisallowUnknownFields(); if err := decoder.Decode(&value); err != nil {{ return {result_name}{{Ok: false, Error: err.Error()}} }}; var extra interface{{}}; if err := decoder.Decode(&extra); err != io.EOF {{ if err == nil {{ err = fmt.Errorf(\"unexpected trailing JSON value\") }}; return {result_name}{{Ok: false, Error: err.Error()}} }}; return {result_name}{{Ok: true, Value: value}} }}()"
        string_call = self.string_runtime_call_expr(expr)
        if string_call is not None:
            return string_call
        if expr.name == "String.template":
            self.std_imports.add("fmt")
            return self.render_string_template_call(expr.args)
        big_call = self.big_runtime_call_expr(expr)
        if big_call is not None:
            return big_call
        if not expr.name.startswith("Math."):
            return None
        self.used_runtime_modules.add("Math")
        self.std_imports.add("math")
        args = [self.expr(arg) for arg in expr.args]
        if expr.name in {"Math.sin", "Math.cos", "Math.tan", "Math.sqrt"}:
            go_name = {"Math.sin": "Sin", "Math.cos": "Cos", "Math.tan": "Tan", "Math.sqrt": "Sqrt"}[expr.name]
            return f"math.{go_name}(float64({args[0]}))"
        if expr.name == "Math.pow":
            return f"math.Pow(float64({args[0]}), float64({args[1]}))"
        if expr.name == "Math.floor":
            return f"int64(math.Floor(float64({args[0]})))"
        if expr.name == "Math.ceil":
            return f"int64(math.Ceil(float64({args[0]})))"
        if expr.name == "Math.abs":
            rendered = f"math.Abs(float64({args[0]}))"
            return f"int64({rendered})" if go_expected_base(expected_type) == "Integer" else rendered
        if expr.name in {"Math.min", "Math.max"}:
            go_name = "Min" if expr.name == "Math.min" else "Max"
            rendered = f"math.{go_name}(float64({args[0]}), float64({args[1]}))"
            return f"int64({rendered})" if go_expected_base(expected_type) == "Integer" else rendered
        return None

    def async_runtime_call_expr(self, expr: CallExpr) -> str | None:
        if expr.name == "scope" and not expr.args:
            self.needs_async_helpers = True
            return "FreeholdScope{}"
        if expr.name == "channel":
            return self.render_channel_call(expr)
        if expr.name == "channel_sender":
            return self.render_channel_endpoint_call(expr, "FreeholdSender")
        if expr.name == "channel_receiver":
            return self.render_channel_endpoint_call(expr, "FreeholdReceiver")
        if expr.name == "channel_send":
            return self.render_channel_send_call(expr)
        if expr.name == "channel_try_send":
            return self.render_channel_try_send_call(expr)
        if expr.name == "channel_receive":
            return self.render_channel_receive_call(expr)
        if expr.name == "scope_spawn":
            return self.render_spawn_call(expr, task_arg_index=1)
        if expr.name == "scope_join":
            return self.render_join_call(expr, handle_arg_index=1)
        if expr.name.endswith(".spawn"):
            return self.render_spawn_call(expr, task_arg_index=0)
        if expr.name.endswith(".join"):
            return self.render_join_call(expr, handle_arg_index=0)
        if expr.name.endswith(".cancel"):
            scope_var = go_local_name(expr.name.split(".")[0])
            return f"func() {{ {scope_var}.cancel() }}()"
        if expr.name.endswith(".timeout"):
            scope_var = go_local_name(expr.name.split(".")[0])
            self.std_imports.add("time")
            self.std_imports.add("context")
            return f"func() {{ {scope_var}.ctx, {scope_var}.cancel = context.WithTimeout({scope_var}.ctx, time.Duration({self.expr(expr.args[0])})*time.Millisecond) }}()"
        if expr.name.endswith(".is_cancelled"):
            scope_var = go_local_name(expr.name.split(".")[0])
            return f"({scope_var}.ctx.Err() != nil)"
        if expr.name.endswith(".priority"):
            scope_var = go_local_name(expr.name.split(".")[0])
            return f"func() {{ {scope_var}.priority = int({self.expr(expr.args[0])}) }}()"
        if expr.name.endswith(".limit"):
            scope_var = go_local_name(expr.name.split(".")[0])
            return f"func() {{ {scope_var}.sem = make(chan struct{{}}, {self.expr(expr.args[0])}) }}()"
        return None

    def render_channel_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel requires one type argument and one capacity argument")
            return "nil"
        value_type = self.go_type_string(expr.type_args[0])
        return f"make(chan {value_type}, int({self.expr(expr.args[0])}))"

    def render_channel_endpoint_call(self, expr: CallExpr, endpoint_type: str) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel endpoint requires one type argument and one Channel argument")
            return "nil"
        return self.expr(expr.args[0])

    def render_channel_send_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 2:
            self.unsupported(expr, "channel_send requires one type argument, a Sender, and a value")
            return "false"
        value_type = self.go_type_string(expr.type_args[0])
        return f"freeholdChannelSend[{value_type}]({self.expr(expr.args[0])}, {self.expr_with_type(expr.args[1], expr.type_args[0])})"

    def render_channel_try_send_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 2:
            self.unsupported(expr, "channel_try_send requires one type argument, a Sender, and a value")
            return "false"
        value_type = self.go_type_string(expr.type_args[0])
        return f"freeholdChannelTrySend[{value_type}]({self.expr(expr.args[0])}, {self.expr_with_type(expr.args[1], expr.type_args[0])})"

    def render_channel_receive_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel_receive requires one type argument and a Receiver")
            return "nil"
        value_type = self.go_type_string(expr.type_args[0])
        return f"freeholdChannelReceive[{value_type}]({self.current_context_expr()}, {self.expr(expr.args[0])})"

    def render_spawn_call(self, expr: CallExpr, task_arg_index: int) -> str:
        self.needs_async_helpers = True
        self.std_imports.add("sync")
        if not expr.type_args or len(expr.type_args) != 1 or task_arg_index >= len(expr.args):
            self.unsupported(expr, "scope spawn requires one type argument and an awaitable value")
            return "FreeholdJoinHandle[any]{}"
        value_type = self.go_type_string(expr.type_args[0])
        if expr.name == "scope_spawn":
            scope_expr = self.expr(expr.args[0])
        else:
            scope_expr = go_local_name(expr.name.split(".")[0])
        return f"freeholdSpawn[{value_type}](&{scope_expr}.wg, {scope_expr}.priority, {scope_expr}.sem, func() {value_type} {{ return {self.expr(expr.args[task_arg_index])} }})"

    def render_join_call(self, expr: CallExpr, handle_arg_index: int) -> str:
        self.needs_async_helpers = True
        if handle_arg_index >= len(expr.args):
            self.unsupported(expr, "scope join requires a JoinHandle argument")
            return "nil"
        if not expr.type_args or len(expr.type_args) != 1:
            return f"<-{self.expr(expr.args[handle_arg_index])}.ch"
        value_type = self.go_type_string(expr.type_args[0])
        if expr.name == "scope_join":
            scope_expr = self.expr(expr.args[0])
        else:
            scope_expr = go_local_name(expr.name.split(".")[0])
        return f"freeholdJoin[{value_type}]({scope_expr}.ctx, {self.expr(expr.args[handle_arg_index])})"

    def is_join_handle_type(self, type_ref: Any) -> bool:
        if isinstance(type_ref, TypeName):
            return self.is_join_handle_type(type_ref.name)
        if isinstance(type_ref, str):
            generic = parse_generic(type_ref)
            return generic is not None and generic[0] == "JoinHandle" and len(generic[1]) == 1
        return False

    def join_handle_inner_type_string(self, type_ref: Any) -> str | None:
        if isinstance(type_ref, TypeName):
            return self.join_handle_inner_type_string(type_ref.name)
        if isinstance(type_ref, str):
            generic = parse_generic(type_ref)
            if generic is not None and generic[0] == "JoinHandle" and len(generic[1]) == 1:
                return generic[1][0]
        return None

    def big_runtime_call_expr(self, expr: CallExpr) -> str | None:
        if not expr.name.startswith("Big."):
            return None
        self.used_runtime_modules.add("Big")
        self.std_imports.add("math/big")
        self.needs_big_helpers = True
        args = [self.expr(arg) for arg in expr.args]
        if expr.name in {"Big.int", "Big.integer"}:
            return f"freeholdBigInt({args[0]})"
        if expr.name == "Big.fromInteger":
            return f"big.NewInt({self.expr_as_int64(expr.args[0])})"
        if expr.name == "Big.float":
            return f"freeholdBigFloat({args[0]}, {self.expr_as_int64(expr.args[1])})"
        if expr.name == "Big.floatFromInteger":
            return f"freeholdBigFloatFromInteger({args[0]}, {self.expr_as_int64(expr.args[1])})"
        int_ops = {
            "Big.addInt": "Add",
            "Big.subInt": "Sub",
            "Big.mulInt": "Mul",
            "Big.divInt": "Quo",
        }
        if expr.name in int_ops:
            return f"new(big.Int).{int_ops[expr.name]}({args[0]}, {args[1]})"
        if expr.name == "Big.negInt":
            return f"new(big.Int).Neg({args[0]})"
        if expr.name == "Big.absInt":
            return f"new(big.Int).Abs({args[0]})"
        if expr.name == "Big.signInt":
            return f"int64({args[0]}.Sign())"
        float_ops = {
            "Big.addFloat": "Add",
            "Big.subFloat": "Sub",
            "Big.mulFloat": "Mul",
            "Big.divFloat": "Quo",
        }
        if expr.name in float_ops:
            return f"new(big.Float).SetPrec({args[0]}.Prec()).{float_ops[expr.name]}({args[0]}, {args[1]})"
        if expr.name == "Big.sqrt":
            return f"new(big.Float).SetPrec({args[0]}.Prec()).Sqrt({args[0]})"
        if expr.name == "Big.absFloat":
            return f"freeholdBigFloatAbs({args[0]})"
        if expr.name == "Big.signFloat":
            return f"int64({args[0]}.Sign())"
        if expr.name == "Big.toString":
            return f"{args[0]}.String()"
        if expr.name == "Big.format":
            return f"{args[0]}.Text('f', int({args[1]}))"
        return None

    def string_runtime_call_expr(self, expr: CallExpr) -> str | None:
        if expr.name == "String.concat":
            return f"{self.expr_at(expr.args[0], go_precedence('+'), 'left')} + {self.expr_at(expr.args[1], go_precedence('+'), 'right')}"
        if expr.name == "String.substr":
            text = self.expr(expr.args[0])
            start = self.expr(expr.args[1])
            length = self.expr(expr.args[2])
            return f"{text}[int({start}):int({start}+{length})]"
        if expr.name == "String.replace":
            self.std_imports.add("strings")
            args = [self.expr(arg) for arg in expr.args]
            return f"strings.ReplaceAll({args[0]}, {args[1]}, {args[2]})"
        if expr.name == "String.instr":
            self.std_imports.add("strings")
            args = [self.expr(arg) for arg in expr.args]
            return f"int64(strings.Index({args[0]}, {args[1]}))"
        if expr.name == "String.length":
            return f"int64(len({self.expr(expr.args[0])}))"
        if expr.name == "String.error_text":
            return self.expr(expr.args[0])
        return None

    def render_call_args(self, args: list[Any], routine: RoutineDecl | None) -> str:
        rendered: list[str] = []
        if routine is not None and getattr(routine, "is_async", False):
            self.std_imports.add("context")
            rendered.append(self.current_context_expr())
        if routine is None:
            rendered.extend(self.expr(arg) for arg in args)
        else:
            for index, arg in enumerate(args):
                if index < len(routine.params) and routine.params[index].type_name == "Integer":
                    rendered.append(self.expr_as_int64(arg))
                else:
                    rendered.append(self.expr(arg))
        return ", ".join(rendered)

    def expr_as_int64(self, expr: Any) -> str:
        rendered = self.expr(expr)
        return f"int64({rendered})" if self.integer_expr_kind(expr) == "inferred_int" else rendered

    def expr_for_integer_comparison(self, expr: Any, other: Any, parent_precedence: int = 0, side: str = "") -> str:
        if self.integer_expr_kind(expr) == "inferred_int":
            other_kind = self.integer_expr_kind(other)
            if other_kind not in {"inferred_int", "untyped"}:
                return f"int64({self.expr_at(expr, parent_precedence, side)})"
        return self.expr_at(expr, parent_precedence, side)

    def integer_expr_kind(self, expr: Any) -> str | None:
        if isinstance(expr, NumberExpr):
            return "untyped"
        if isinstance(expr, UnaryExpr) and expr.op in {"-", "+"}:
            return self.integer_expr_kind(expr.expr)
        if isinstance(expr, VarExpr):
            if expr.name in self.inferred_int_locals:
                return "inferred_int"
            if self.go_declared_base(self.current_local_types.get(expr.name)) == "Integer":
                return "int64"
            return None
        if isinstance(expr, BinaryExpr) and expr.op in {"+", "-", "*", "/"}:
            left = self.integer_expr_kind(expr.left)
            right = self.integer_expr_kind(expr.right)
            if "int64" in {left, right}:
                return "int64"
            if "inferred_int" in {left, right}:
                return "inferred_int"
            if left == "untyped" and right == "untyped":
                return "untyped"
        if isinstance(expr, CallExpr):
            routine = self.called_routine(expr.name)
            if routine is not None and self.go_declared_base(routine.return_type) == "Integer":
                return "int64"
            if expr.name in {"Math.floor", "Math.ceil", "String.instr", "Big.signInt", "Big.signFloat"}:
                return "int64"
        return None

    def go_declared_base(self, type_ref: Any) -> str | None:
        if isinstance(type_ref, TypeName):
            return type_ref.name
        if isinstance(type_ref, str):
            return type_ref
        return None

    def render_string_template_call(self, args: list[Any]) -> str:
        if not args:
            self.unsupported(self.program, "String.template requires a template argument")
            return "\"\""
        template_arg = args[0]
        if not isinstance(template_arg, StringExpr):
            if len(args) == 1:
                return self.expr(template_arg)
            self.needs_template_helper = True
            self.std_imports.add("strings")
            return self.render_dynamic_string_template_call(args)
        format_text, ordered_args = go_template_format(template_arg.value, args[1:])
        if not ordered_args:
            return json.dumps(format_text)
        return f"fmt.Sprintf({json.dumps(format_text)}, {', '.join(self.expr(arg) for arg in ordered_args)})"

    def render_dynamic_string_template_call(self, args: list[Any]) -> str:
        positional: list[Any] = []
        named: dict[str, Any] = {}
        for arg in args[1:]:
            if isinstance(arg, NamedArg):
                named[arg.name] = arg.expr
            else:
                positional.append(arg)
        positional_expr = "[]any{" + ", ".join(self.expr(arg) for arg in positional) + "}"
        if named:
            named_expr = "map[string]any{" + ", ".join(f"{json.dumps(name)}: {self.expr(expr)}" for name, expr in sorted(named.items())) + "}"
        else:
            named_expr = "nil"
        return f"freeholdStringTemplate({self.expr(args[0])}, {positional_expr}, {named_expr})"

    def contract_checks(self, contracts: list[Any], label: str) -> list[str]:
        lines: list[str] = []
        for contract in contracts:
            lines.extend(self.contract_check(contract, label))
        return lines

    def contract_check(self, contract: Any, label: str) -> list[str]:
        return [f"if !({self.expr(contract)}) {{ panic(\"freehold {label} contract failed\") }}"]

    def current_ensures(self) -> list[Any]:
        return self.current_routine_decl.ensures if self.current_routine_decl is not None else []

    def ensure_checks_for_value(self, result_expr: str) -> list[str]:
        previous = self.contract_bindings
        self.contract_bindings = {**previous, "result": result_expr, "value": result_expr}
        lines = self.contract_checks(self.current_ensures(), "ensures")
        self.contract_bindings = previous
        return lines

    def ensure_checks_for_result(self, result_expr: str) -> list[str]:
        previous = self.contract_bindings
        self.contract_bindings = {
            **previous,
            "result": result_expr,
            "success": f"{result_expr}.Ok",
            "failure": f"!{result_expr}.Ok",
            "value": f"{result_expr}.Value",
            "error": f"{result_expr}.Error",
        }
        lines = self.contract_checks(self.current_ensures(), "ensures")
        self.contract_bindings = previous
        return lines

    def fresh_local_name(self, base: str) -> str:
        candidate = f"freehold{go_exported_name(base)}"
        local_names = {go_local_name(name) for name in self.current_local_types}
        if candidate not in local_names:
            return candidate
        index = 2
        while f"{candidate}{index}" in local_names:
            index += 1
        return f"{candidate}{index}"

    def unsupported(self, node: Any, message: str) -> None:
        pos = getattr(node, "pos", None)
        location = pos.text() if pos is not None else "line ?:?"
        diagnostic = {
            "code": "FH-GOCODEGEN-0001",
            "message": message,
            "location": location,
        }
        if diagnostic not in self.diagnostics:
            self.diagnostics.append(diagnostic)


def go_type_ref(type_ref: Any) -> str:
    if isinstance(type_ref, str):
        return go_type_string(type_ref)
    if isinstance(type_ref, TypeName):
        return go_type_string(type_ref.name)
    if isinstance(type_ref, ArrayTypeName):
        return f"[{type_ref.size}]{go_type_string(type_ref.element_type)}"
    if isinstance(type_ref, ResultTypeName):
        return go_result_type_name(type_ref)
    raise GoCodegenError(f"unsupported Go type reference: {type_to_string(type_ref)}")


def go_type_string(type_name: str) -> str:
    generic = parse_generic(type_name)
    if generic is not None:
        base, args = generic
        if base == "Array" and len(args) == 2 and args[1].isdigit():
            return f"[{args[1]}]{go_type_string(args[0])}"
        if base == "Result" and len(args) == 2:
            return go_result_type_name(ResultTypeName(TypeName(args[0]), args[1]))
        if base == "JoinHandle" and len(args) == 1:
            return f"FreeholdJoinHandle[{go_type_string(args[0])}]"
        if base == "Channel" and len(args) == 1:
            return f"chan {go_type_string(args[0])}"
        if base == "Sender" and len(args) == 1:
            return f"chan<- {go_type_string(args[0])}"
        if base == "Receiver" and len(args) == 1:
            return f"<-chan {go_type_string(args[0])}"
        
        parts = base.split(".")
        normalized_parts = [go_exported_name(p) for p in parts]
        base_name = "".join(normalized_parts)
        
        def format_arg(arg: str) -> str:
            cleaned = arg.replace("<", "_").replace(">", "").replace(",", "_").replace(" ", "")
            parts = cleaned.split(".")
            return "".join(go_exported_name(p) for p in parts)
            
        args_str = "_".join(format_arg(a) for a in args)
        return go_exported_name(f"{base_name}_{args_str}")
    if type_name == "Scope":
        return "FreeholdScope"
    mapping = {
        "Integer": "int64",
        "Boolean": "bool",
        "Double": "float64",
        "String": "string",
        "BigInteger": "*big.Int",
        "BigFloat": "*big.Float",
    }
    return mapping.get(type_name, go_exported_name(type_name))


def go_result_type_name(type_ref: ResultTypeName) -> str:
    return f"Result{go_type_name_fragment(type_ref.ok_type)}{go_exported_name(type_ref.error_type)}"


def go_zero_value(type_ref: Any) -> str:
    if isinstance(type_ref, str):
        return go_zero_value_for_type_name(type_ref)
    if isinstance(type_ref, TypeName):
        return go_zero_value_for_type_name(type_ref.name)
    if isinstance(type_ref, ArrayTypeName):
        return f"[{type_ref.size}]{go_type_string(type_ref.element_type)}{{}}"
    if isinstance(type_ref, ResultTypeName):
        return f"{go_result_type_name(type_ref)}{{}}"
    return "nil"


def go_zero_value_for_type_name(type_name: str) -> str:
    mapping = {
        "Integer": "0",
        "Boolean": "false",
        "Double": "0.0",
        "String": "\"\"",
        "BigInteger": "nil",
        "BigFloat": "nil",
    }
    if type_name in mapping:
        return mapping[type_name]
    generic = parse_generic(type_name)
    if generic is not None:
        base, args = generic
        if base == "Array" and len(args) == 2 and args[1].isdigit():
            return f"[{args[1]}]{go_type_string(args[0])}{{}}"
        if base == "Result" and len(args) == 2:
            return f"{go_result_type_name(ResultTypeName(TypeName(args[0]), args[1]))}{{}}"
    return f"{go_exported_name(type_name)}{{}}"


def go_type_name_fragment(type_ref: Any) -> str:
    if isinstance(type_ref, TypeName):
        return go_exported_name(type_ref.name)
    if isinstance(type_ref, ArrayTypeName):
        return f"Array{go_exported_name(type_ref.element_type)}{type_ref.size}"
    if isinstance(type_ref, ResultTypeName):
        return go_result_type_name(type_ref)
    return go_exported_name(type_to_string(type_ref))


def program_uses_big_types(program: Program) -> bool:
    for declaration in program.declarations:
        if isinstance(declaration, TypeDecl) and type_name_uses_big(declaration.base):
            return True
        if isinstance(declaration, RecordTypeDecl):
            if any(type_name_uses_big(field.type_name) for field in declaration.fields):
                return True
        if isinstance(declaration, RoutineDecl):
            if any(type_name_uses_big(param.type_name) for param in declaration.params):
                return True
            if type_ref_uses_big(declaration.return_type):
                return True
    return False


def type_ref_uses_big(type_ref: Any) -> bool:
    if type_ref is None:
        return False
    if isinstance(type_ref, TypeName):
        return type_name_uses_big(type_ref.name)
    if isinstance(type_ref, ArrayTypeName):
        return type_name_uses_big(type_ref.element_type)
    if isinstance(type_ref, ResultTypeName):
        return type_ref_uses_big(type_ref.ok_type) or type_name_uses_big(type_ref.error_type)
    return False


def type_name_uses_big(type_name: str) -> bool:
    if type_name in {"BigInteger", "BigFloat"}:
        return True
    generic = parse_generic(type_name)
    if generic is None:
        return False
    _, args = generic
    return any(type_name_uses_big(arg) for arg in args)


def generate_grpc_pb_stub(program: Program) -> str:
    from freehold.core.grpc_codegen import proto_package_name
    record_decls = [declaration for declaration in program.declarations if isinstance(declaration, RecordTypeDecl)]
    service_decls = [declaration for declaration in program.declarations if isinstance(declaration, ServiceDecl)]
    package_name = f"{go_package_name(program.module_name)}pb"
    proto_pkg = proto_package_name(program.module_name)
    lines: list[str] = [
        "// Code generated by Freehold Go codegen V1 gRPC project stubs; DO NOT EDIT.",
        f"package {package_name}",
        "",
    ]
    if service_decls:
        lines.extend([
            "import (",
            "\t\"context\"",
            "\t\"encoding/json\"",
            "",
            "\t\"google.golang.org/grpc\"",
            "\t\"google.golang.org/grpc/codes\"",
            "\t\"google.golang.org/grpc/status\"",
            "\t\"google.golang.org/grpc/encoding\"",
            ")",
            "",
        ])
    from freehold.core.grpc_codegen import array_element_type
    for record in record_decls:
        lines.append(f"type {go_exported_name(record.name)} struct {{")
        for field in record.fields:
            tag_parts = []
            if field.proto_id is not None:
                type_name = field.type_name
                element = array_element_type(type_name)
                is_repeated = element is not None
                base_type = element if is_repeated else type_name
                if base_type in ("Integer", "Boolean"):
                    wire = "varint"
                elif base_type == "Double":
                    wire = "fixed64"
                else:
                    wire = "bytes"
                rep_opt = "rep" if is_repeated else "opt"
                tag_parts.append(f'protobuf:"{wire},{field.proto_id},{rep_opt},name={field.name},proto3"')
            tag_parts.append(f'json:"{field.json_name or field.name}"')
            lines.append(f"\t{go_exported_name(field.name)} {go_type_string(field.type_name)} `{' '.join(tag_parts)}`")
        lines.extend(["}", ""])

        # Methods to satisfy legacy proto.Message
        lines.extend([
            f"func (*{go_exported_name(record.name)}) Reset()         {{}}",
            f"func (*{go_exported_name(record.name)}) String() string {{ return \"\" }}",
            f"func (*{go_exported_name(record.name)}) ProtoMessage()  {{}}",
            "",
        ])
    for service in service_decls:
        service_name = go_exported_name(service.name)

        def is_server_stream(rpc) -> bool:
            return not getattr(rpc, "request_stream", False) and getattr(rpc, "response_stream", False)

        stream_rpcs = [rpc for rpc in service.rpcs if is_server_stream(rpc)]

        lines.append(f"type {service_name}Server interface {{")
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
            if is_server_stream(rpc):
                lines.append(f"\t{method_name}(*{req_type}, {service_name}_{method_name}Server) error")
            else:
                lines.append(f"\t{method_name}(context.Context, *{req_type}) (*{resp_type}, error)")
        lines.extend(["}", ""])
        lines.extend([
            f"type Unimplemented{service_name}Server struct{{}}",
            "",
        ])
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
            if is_server_stream(rpc):
                lines.extend([
                    f"func (Unimplemented{service_name}Server) {method_name}(*{req_type}, {service_name}_{method_name}Server) error {{",
                    f"\treturn status.Error(codes.Unimplemented, \"method {method_name} not implemented\")",
                    "}",
                    "",
                ])
            else:
                lines.extend([
                    f"func (Unimplemented{service_name}Server) {method_name}(context.Context, *{req_type}) (*{resp_type}, error) {{",
                    f"\treturn nil, status.Error(codes.Unimplemented, \"method {method_name} not implemented\")",
                    "}",
                    "",
                ])

        # Server stream interfaces and concrete types
        for rpc in stream_rpcs:
            method_name = go_exported_name(rpc.name)
            resp_type = go_exported_name(rpc.response_type)
            stream_server_struct = go_package_name(service.name) + method_name + "Server"
            lines.extend([
                f"type {service_name}_{method_name}Server interface {{",
                f"\tSend(*{resp_type}) error",
                "\tgrpc.ServerStream",
                "}",
                "",
                f"type {stream_server_struct} struct {{",
                "\tgrpc.ServerStream",
                "}",
                "",
                f"func (x *{stream_server_struct}) Send(m *{resp_type}) error {{",
                "\treturn x.ServerStream.SendMsg(m)",
                "}",
                "",
            ])

        # Client interface
        lines.extend([
            f"type {service_name}Client interface {{",
        ])
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
            if is_server_stream(rpc):
                lines.append(f"\t{method_name}(ctx context.Context, in *{req_type}, opts ...grpc.CallOption) ({service_name}_{method_name}Client, error)")
            else:
                lines.append(f"\t{method_name}(ctx context.Context, in *{req_type}, opts ...grpc.CallOption) (*{resp_type}, error)")
        lines.extend([
            "}",
            "",
            f"type {go_package_name(service.name)}Client struct {{",
            "\tcc grpc.ClientConnInterface",
            "}",
            "",
            f"func New{service_name}Client(cc grpc.ClientConnInterface) {service_name}Client {{",
            f"\treturn &{go_package_name(service.name)}Client{{cc}}",
            "}",
            "",
        ])
        # Client stream interfaces and concrete types
        for rpc in stream_rpcs:
            method_name = go_exported_name(rpc.name)
            resp_type = go_exported_name(rpc.response_type)
            stream_client_struct = go_package_name(service.name) + method_name + "Client"
            lines.extend([
                f"type {service_name}_{method_name}Client interface {{",
                f"\tRecv() (*{resp_type}, error)",
                "\tgrpc.ClientStream",
                "}",
                "",
                f"type {stream_client_struct} struct {{",
                "\tgrpc.ClientStream",
                "}",
                "",
                f"func (x *{stream_client_struct}) Recv() (*{resp_type}, error) {{",
                f"\tm := new({resp_type})",
                "\tif err := x.ClientStream.RecvMsg(m); err != nil {",
                "\t\treturn nil, err",
                "\t}",
                "\treturn m, nil",
                "}",
                "",
            ])
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
            if is_server_stream(rpc):
                stream_idx = stream_rpcs.index(rpc)
                stream_client_struct = go_package_name(service.name) + method_name + "Client"
                lines.extend([
                    f"func (c *{go_package_name(service.name)}Client) {method_name}(ctx context.Context, in *{req_type}, opts ...grpc.CallOption) ({service_name}_{method_name}Client, error) {{",
                    f"\topts = append(opts, grpc.CallContentSubtype(\"json\"))",
                    f"\tstream, err := c.cc.NewStream(ctx, &{service_name}_ServiceDesc.Streams[{stream_idx}], \"/{proto_pkg}.{service_name}/{method_name}\", opts...)",
                    "\tif err != nil {",
                    "\t\treturn nil, err",
                    "\t}",
                    f"\tx := &{stream_client_struct}{{stream}}",
                    "\tif err := x.ClientStream.SendMsg(in); err != nil {",
                    "\t\treturn nil, err",
                    "\t}",
                    "\tif err := x.ClientStream.CloseSend(); err != nil {",
                    "\t\treturn nil, err",
                    "\t}",
                    "\treturn x, nil",
                    "}",
                    "",
                ])
            else:
                lines.extend([
                    f"func (c *{go_package_name(service.name)}Client) {method_name}(ctx context.Context, in *{req_type}, opts ...grpc.CallOption) (*{resp_type}, error) {{",
                    f"\tout := new({resp_type})",
                    f"\topts = append(opts, grpc.CallContentSubtype(\"json\"))",
                    f"\terr := c.cc.Invoke(ctx, \"/{proto_pkg}.{service_name}/{method_name}\", in, out, opts...)",
                    "\tif err != nil {",
                    "\t\treturn nil, err",
                    "\t}",
                    "\treturn out, nil",
                    "}",
                    "",
                ])

        # Server Handlers and ServiceDesc
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
            if is_server_stream(rpc):
                stream_server_struct = go_package_name(service.name) + method_name + "Server"
                lines.extend([
                    f"func _{service_name}_{method_name}_Handler(srv interface{{}}, stream grpc.ServerStream) error {{",
                    f"\tm := new({req_type})",
                    "\tif err := stream.RecvMsg(m); err != nil {",
                    "\t\treturn err",
                    "\t}",
                    f"\treturn srv.({service_name}Server).{method_name}(m, &{stream_server_struct}{{stream}})",
                    "}",
                    "",
                ])
            else:
                lines.extend([
                    f"func _{service_name}_{method_name}_Handler(srv interface{{}}, ctx context.Context, dec func(interface{{}}) error, interceptor grpc.UnaryServerInterceptor) (interface{{}}, error) {{",
                    f"\tin := new({req_type})",
                    "\tif err := dec(in); err != nil {",
                    "\t\treturn nil, err",
                    "\t}",
                    "\tif interceptor == nil {",
                    f"\t\treturn srv.({service_name}Server).{method_name}(ctx, in)",
                    "\t}",
                    "\tinfo := &grpc.UnaryServerInfo{",
                    "\t\tServer: srv,",
                    f"\t\tFullMethod: \"/{proto_pkg}.{service_name}/{method_name}\",",
                    "\t}",
                    "\thandler := func(ctx context.Context, req interface{}) (interface{}, error) {",
                    f"\t\treturn srv.({service_name}Server).{method_name}(ctx, req.(*{req_type}))",
                    "\t}",
                    "\treturn interceptor(ctx, in, info, handler)",
                    "}",
                    "",
                ])

        lines.extend([
            f"func Register{service_name}Server(registrar grpc.ServiceRegistrar, server {service_name}Server) {{",
            f"\tregistrar.RegisterService(&{service_name}_ServiceDesc, server)",
            "}",
            "",
            f"var {service_name}_ServiceDesc = grpc.ServiceDesc{{",
            f"\tServiceName: \"{proto_pkg}.{service_name}\",",
            f"\tHandlerType: (*{service_name}Server)(nil),",
            "\tMethods: []grpc.MethodDesc{",
        ])
        for rpc in service.rpcs:
            if is_server_stream(rpc):
                continue
            method_name = go_exported_name(rpc.name)
            lines.extend([
                "\t\t{",
                f"\t\t\tMethodName: \"{method_name}\",",
                f"\t\t\tHandler: _{service_name}_{method_name}_Handler,",
                "\t\t},",
            ])
        lines.append("\t},")
        if stream_rpcs:
            lines.append("\tStreams: []grpc.StreamDesc{")
            for rpc in stream_rpcs:
                method_name = go_exported_name(rpc.name)
                lines.extend([
                    "\t\t{",
                    f"\t\t\tStreamName: \"{method_name}\",",
                    f"\t\t\tHandler: _{service_name}_{method_name}_Handler,",
                    "\t\t\tServerStreams: true,",
                    "\t\t},",
                ])
            lines.append("\t},")
        else:
            lines.append("\tStreams: []grpc.StreamDesc{},")
        lines.extend([
            "\tMetadata: \"\",",
            "}",
            "",
        ])
    if service_decls:
        lines.extend([
            "type jsonCodec struct{}",
            "",
            "func (jsonCodec) Marshal(v interface{}) ([]byte, error) {",
            "\treturn json.Marshal(v)",
            "}",
            "",
            "func (jsonCodec) Unmarshal(data []byte, v interface{}) error {",
            "\treturn json.Unmarshal(data, v)",
            "}",
            "",
            "func (jsonCodec) Name() string {",
            "\treturn \"json\"",
            "}",
            "",
            "func init() {",
            "\tif encoding.GetCodec(\"json\") == nil {",
            "\t\tencoding.RegisterCodec(jsonCodec{})",
            "\t}",
            "}",
            "",
        ])
    return format_go_source("\n".join(lines).rstrip() + "\n")


def go_package_name(module_name: str) -> str:
    package = re.sub(r"[^A-Za-z0-9_]", "_", module_name).lower()
    if not package or package[0].isdigit():
        return f"fh_{package}"
    return package


def go_package_path(module_name: str) -> str:
    return "/".join(go_package_path_part(part) for part in module_name.split("."))


def go_module_output_path(module_name: str) -> Path:
    parts = module_name.split(".")
    return Path(go_package_path(module_name)) / f"{go_package_path_part(parts[-1])}.go"


def go_grpc_binding_output_path(module_name: str) -> Path:
    parts = module_name.split(".")
    return Path("grpc") / go_package_path(module_name) / f"{go_package_path_part(parts[-1])}_grpc.go"


def go_grpc_pb_stub_output_path(module_name: str) -> Path:
    return Path("grpc") / f"{go_package_path(module_name)}pb" / f"{go_package_path_part(module_name.split('.')[-1])}pb.go"


def go_grpc_runtime_glue_output_path(module_name: str) -> Path:
    parts = module_name.split(".")
    return Path("grpc") / go_package_path(module_name) / f"{go_package_path_part(parts[-1])}_runtime.go"


def go_import_path(module_name: str) -> str:
    return f"{GO_PROJECT_MODULE_PATH}/{go_package_path(module_name)}"


def runtime_module_import_path(module_name: str) -> str | None:
    return {"Math": "math", "Std.IO": "fmt", "Big": "math/big"}.get(module_name)


def go_import_alias(module_name: str) -> str:
    return go_package_name(module_name)


def go_package_path_part(name: str) -> str:
    part = re.sub(r"[^A-Za-z0-9_]", "_", name).lower()
    if not part or part[0].isdigit():
        return f"fh_{part}"
    return part


def go_executable_name(name: str) -> str:
    return go_package_path_part(name)


def go_expected_base(type_ref: Any) -> str | None:
    if isinstance(type_ref, TypeName):
        return type_ref.name
    if isinstance(type_ref, str):
        return type_ref
    return None


def go_template_format(template: str, args: list[Any]) -> tuple[str, list[Any]]:
    positional: list[Any] = []
    named: dict[str, Any] = {}
    for arg in args:
        if isinstance(arg, NamedArg):
            named[arg.name] = arg.expr
        else:
            positional.append(arg)
    ordered: list[Any] = []
    positional_index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal positional_index
        placeholder = match.group(1).strip()
        if placeholder:
            if placeholder in named:
                ordered.append(named[placeholder])
            return "%v"
        if positional_index < len(positional):
            ordered.append(positional[positional_index])
            positional_index += 1
        return "%v"

    return re.sub(r"\$\{([^}]*)\}", replace, template), ordered


def go_exported_name(name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    if not parts:
        return "X"
    return "".join(part[:1].upper() + part[1:] for part in parts)


def go_local_name(name: str) -> str:
    exported = go_exported_name(name)
    local = exported[:1].lower() + exported[1:]
    if local in {
        "break", "default", "func", "interface", "select",
        "case", "defer", "go", "map", "struct",
        "chan", "else", "goto", "package", "switch",
        "const", "fallthrough", "if", "range", "type",
        "continue", "for", "import", "return", "var"
    }:
        return local + "_"
    return local


def go_qualified_name(name: str) -> str:
    return ".".join(go_exported_name(part) for part in name.split("."))


def go_operator(op: str) -> str:
    return {"=": "==", "and": "&&", "or": "||", "not": "!"}.get(op, op)


def go_precedence(op: str) -> int:
    return {
        "or": 1,
        "and": 2,
        "=": 3,
        "!=": 3,
        "<": 3,
        "<=": 3,
        ">": 3,
        ">=": 3,
        "+": 4,
        "-": 4,
        "*": 5,
        "/": 5,
        "not": 6,
    }.get(op, 7)


def unary_precedence(op: str) -> int:
    return 6 if op in {"not", "-"} else go_precedence(op)


def parenthesize_if_needed(rendered: str, precedence: int, parent_precedence: int, side: str, op: str) -> str:
    if precedence < parent_precedence:
        return f"({rendered})"
    if side == "right" and precedence == parent_precedence and op in {"-", "/", "=", "!=", "<", "<=", ">", ">="}:
        return f"({rendered})"
    return rendered


def indent_lines(lines: list[str]) -> list[str]:
    return [f"\t{line}" for line in lines]


def parse_generic(type_name: str) -> tuple[str, list[str]] | None:
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)<(.+)>", type_name.strip())
    if not match:
        return None
    return match.group(1), split_type_args(match.group(2))


def format_go_source(source: str) -> str:
    try:
        completed = subprocess.run(
            ["gofmt"],
            input=source,
            text=True,
            capture_output=True,
            check=True,
        )
        return completed.stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return source


def split_type_args(text: str) -> list[str]:
    args: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(text[start:index].strip())
            start = index + 1
    args.append(text[start:].strip())
    return args


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()
