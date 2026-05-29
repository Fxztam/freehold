from __future__ import annotations

import json
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
    ResultTypeName,
    StringExpr,
    TypeDecl,
    TypeName,
    UnaryExpr,
    VarExpr,
    WhileStmt,
    type_to_string,
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
    from freehold.core.grpc_go_codegen import generate_grpc_go_bindings

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
    return extras


def generate_go_project_build_files(files: list[GoProjectFile], executable_name: str | None = None, entry_module_name: str | None = None) -> list[GoProjectBuildFile]:
    grpc_required = any(any(isinstance(declaration, ServiceDecl) for declaration in file.result_program.declarations) for file in files)
    go_mod = f"module {GO_PROJECT_MODULE_PATH}\n\ngo 1.22\n"
    if grpc_required:
        go_mod += "\nrequire google.golang.org/grpc v1.64.0\n"
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
        main_call = f"\t{import_alias}.Main()\n"
        if re.search(r"(?m)^func Main\(\) error \{", entry.result.go_source):
            main_call = (
                f"\tif err := {import_alias}.Main(); err != nil {{\n"
                "\t\tpanic(err)\n"
                "\t}\n"
            )
        build_files.append(
            GoProjectBuildFile(
                output_path=f"cmd/{exe_name}/main.go",
                kind="go_main",
                content=(
                    "package main\n\n"
                    "import (\n"
                    f"\t{import_alias} \"{go_import_path(entry.module_name)}\"\n"
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
        self.imports_by_module = {import_decl.module_name: import_decl for import_decl in self.imports}
        self.exposed_symbols = self.build_exposed_symbols(self.imports)
        self.exposed_type_modules = self.build_exposed_type_modules(self.imports)
        self.exposed_error_modules = self.build_exposed_error_modules(self.imports)
        self.used_import_modules: set[str] = set()
        self.used_runtime_modules: set[str] = set()
        self.std_imports: set[str] = set()
        self.result_types: dict[str, ResultTypeName] = {}
        self.needs_json_helper = False
        self.needs_big_helpers = False
        self.needs_template_helper = False
        self.needs_async_helpers = False
        self.current_return_type: Any = None
        self.current_aborts: list[Any] = []
        self.current_routine_decl: RoutineDecl | None = None
        self.current_local_types: dict[str, Any] = {}
        self.inferred_int_locals: set[str] = set()
        self.contract_bindings: dict[str, str] = {}
        self.current_routine_read_names: set[str] = set()

    def generate(self) -> GoCodegenResult:
        package_name = go_package_name(self.program.module_name)
        body_lines: list[str] = []
        if program_uses_big_types(self.program):
            self.std_imports.add("math/big")
        for declaration in self.program.declarations:
            if isinstance(declaration, TypeDecl):
                body_lines.extend(self.type_decl(declaration))
            elif isinstance(declaration, RecordTypeDecl):
                body_lines.extend(self.record_decl(declaration))
            elif isinstance(declaration, RoutineDecl):
                body_lines.extend(self.routine_decl(declaration))
            elif isinstance(declaration, ErrorDecl):
                body_lines.extend(self.error_decl(declaration))
            elif isinstance(declaration, ServiceDecl):
                body_lines.extend(self.service_decl(declaration))
            else:
                self.unsupported(declaration, "declaration not supported by Go codegen V1")
        lines = [
            "// Code generated by Freehold Go codegen V1; DO NOT EDIT.",
            f"package {package_name}",
            "",
        ]
        lines.extend(self.import_block())
        lines.extend(self.result_type_decls())
        lines.extend(self.helper_decls())
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
        if not used_imports and not self.std_imports:
            return []
        lines = ["import ("]
        for import_path in sorted(self.std_imports):
            lines.append(f"\t{json.dumps(import_path)}")
        for import_decl in used_imports:
            lines.append(f"\t{go_import_alias(import_decl.module_name)} \"{go_import_path(import_decl.module_name)}\"")
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
            lines.extend([
                "type FreeholdScope struct{}",
                "",
                "type FreeholdJoinHandle[T any] struct {",
                "\tvalue T",
                "}",
                "",
                "type FreeholdChannel[T any] struct {",
                "\tch chan T",
                "}",
                "",
                "type FreeholdSender[T any] struct {",
                "\tch chan T",
                "}",
                "",
                "type FreeholdReceiver[T any] struct {",
                "\tch chan T",
                "}",
                "",
                "func freeholdChannelSend[T any](sender FreeholdSender[T], value T) bool {",
                "\tsender.ch <- value",
                "\treturn true",
                "}",
                "",
                "func freeholdChannelReceive[T any](receiver FreeholdReceiver[T]) T {",
                "\treturn <-receiver.ch",
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
        return lines

    def record_decl(self, declaration: RecordTypeDecl) -> list[str]:
        if declaration.type_params:
            self.unsupported(declaration, "generic records are not supported by Go codegen V1")
            return []
        lines = [f"type {go_exported_name(declaration.name)} struct {{"]
        for field in declaration.fields:
            lines.append(f"\t{go_exported_name(field.name)} {self.go_type_string(field.type_name)} `json:\"{field.name}\"`")
        lines.extend(["}", ""])
        return lines

    def service_decl(self, declaration: ServiceDecl) -> list[str]:
        return [f"// Service {go_exported_name(declaration.name)} is emitted through the generated gRPC binding file.", ""]

    def routine_decl(self, routine: RoutineDecl) -> list[str]:
        if routine.type_params:
            self.unsupported(routine, "generic routines are not supported by Go codegen V1")
            return []
        params = ", ".join(self.param(param) for param in routine.params)
        result_type = self.routine_result_type(routine)
        lines = [f"func {go_exported_name(routine.name)}({params}){result_type} {{"]
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
        lines.extend(["}", ""])
        return lines

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
            operator = "=" if already_declared else ":="
            target_type = None if is_inferred_int else stmt.type_ref
            lines = [f"{go_local_name(stmt.name)} {operator} {self.expr_with_type(stmt.expr, target_type)}"]
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
            if isinstance(stmt.value, ReturnPlain):
                if isinstance(stmt.value.expr, CallExpr):
                    call_routine = self.called_routine(stmt.value.expr.name)
                    if call_routine is not None and call_routine.aborts:
                        return self.return_aborting_call(stmt.value.expr, call_routine)
                rendered = self.expr_with_type(stmt.value.expr, self.current_return_type)
                if self.current_ensures():
                    result_name = self.fresh_local_name("result")
                    lines = [f"var {result_name} {self.go_type_ref(self.current_return_type)} = {rendered}"]
                    lines.extend(self.ensure_checks_for_value(result_name))
                    if self.current_aborts:
                        lines.append(f"return {result_name}, nil")
                    else:
                        lines.append(f"return {result_name}")
                    return lines
                if self.current_aborts:
                    return [f"return {rendered}, nil"]
                return [f"return {rendered}"]
            if isinstance(stmt.value, ReturnOk):
                if not isinstance(self.current_return_type, ResultTypeName):
                    self.unsupported(stmt, "return ok requires a Result return type")
                    return ["// unsupported result return"]
                result_expr = f"{self.go_result_type_name(self.current_return_type)}{{Ok: true, Value: {self.expr_with_type(stmt.value.expr, self.current_return_type.ok_type)}}}"
                if self.current_ensures():
                    result_name = self.fresh_local_name("result")
                    lines = [f"{result_name} := {result_expr}"]
                    lines.extend(self.ensure_checks_for_result(result_name))
                    lines.append(f"return {result_name}, nil" if self.current_aborts else f"return {result_name}")
                    return lines
                if self.current_aborts:
                    return [f"return {result_expr}, nil"]
                return [f"return {result_expr}"]
            if isinstance(stmt.value, ReturnError):
                if not isinstance(self.current_return_type, ResultTypeName):
                    self.unsupported(stmt, "return error requires a Result return type")
                    return ["// unsupported result return"]
                result_expr = f"{self.go_result_type_name(self.current_return_type)}{{Ok: false, Error: {self.go_error_name(stmt.value.error_name)}}}"
                if self.current_ensures():
                    result_name = self.fresh_local_name("result")
                    lines = [f"{result_name} := {result_expr}"]
                    lines.extend(self.ensure_checks_for_result(result_name))
                    lines.append(f"return {result_name}, nil" if self.current_aborts else f"return {result_name}")
                    return lines
                if self.current_aborts:
                    return [f"return {result_expr}, nil"]
                return [f"return {result_expr}"]
            self.unsupported(stmt, "return form is not supported by Go codegen V1")
            return ["// unsupported return"]
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
            scope_name = go_local_name(stmt.name)
            lines = ["{"]
            lines.append(f"\t{scope_name} := FreeholdScope{{}}")
            lines.append(f"\t_ = {scope_name}")
            lines.extend(indent_lines(self.statement_block(stmt.spawn_body)))
            lines.extend(indent_lines(self.statement_block(stmt.join_body)))
            lines.extend(indent_lines(self.statement_block(stmt.result_body)))
            lines.append("}")
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
        if self.current_return_type is None:
            return [f"return errors.New({self.go_error_name(error_name)})"]
        return [f"return {self.go_zero_value(self.current_return_type)}, errors.New({self.go_error_name(error_name)})"]

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
        if self.current_return_type is None:
            return ["return err"]
        return [f"return {self.go_zero_value(self.current_return_type)}, err"]

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
        if isinstance(expr, ArrayLiteralExpr) and isinstance(type_ref, ArrayTypeName):
            values = ", ".join(self.expr(item) for item in expr.items)
            return f"[{type_ref.size}]{self.go_type_string(type_ref.element_type)}{{{values}}}"
        if isinstance(expr, CallExpr):
            rendered = self.runtime_call_expr(expr, type_ref)
            if rendered is not None:
                return rendered
        rendered_expr = self.expr(expr)
        if self.integer_expr_kind(expr) == "inferred_int" and self.go_declared_base(type_ref) == "Integer":
            return f"int64({rendered_expr})"
        return rendered_expr

    def record_field_type(self, record_name: str, field_name: str) -> Any | None:
        for decl in self.program.declarations:
            if isinstance(decl, RecordTypeDecl) and decl.name == record_name:
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

    def go_type_ref_text(self, type_ref: Any) -> str:
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
                return f"FreeholdChannel[{self.go_type_string(args[0])}]"
            if base == "Sender" and len(args) == 1:
                self.needs_async_helpers = True
                return f"FreeholdSender[{self.go_type_string(args[0])}]"
            if base == "Receiver" and len(args) == 1:
                self.needs_async_helpers = True
                return f"FreeholdReceiver[{self.go_type_string(args[0])}]"
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
        imported = self.imported_type_module(type_name)
        if imported is not None:
            self.used_import_modules.add(imported)
            return f"{go_import_alias(imported)}.{go_exported_name(type_name)}{{}}"
        generic = parse_generic(type_name)
        if generic is not None:
            base, args = generic
            if base == "Array" and len(args) == 2 and args[1].isdigit():
                return f"[{args[1]}]{self.go_type_string(args[0])}{{}}"
        return go_zero_value_for_type_name(type_name)

    def go_error_name(self, error_name: str) -> str:
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

    def expr_at(self, expr: Any, parent_precedence: int, side: str = "") -> str:
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
        if isinstance(expr, AwaitExpr):
            return self.await_expr(expr)
        if isinstance(expr, UnaryExpr):
            precedence = unary_precedence(expr.op)
            rendered = f"{go_operator(expr.op)}{self.expr_at(expr.expr, precedence)}"
            return parenthesize_if_needed(rendered, precedence, parent_precedence, side, expr.op)
        if isinstance(expr, BinaryExpr):
            precedence = go_precedence(expr.op)
            if expr.op in {"=", "!=", "<", "<=", ">", ">="}:
                rendered = f"{self.expr_for_integer_comparison(expr.left, expr.right)} {go_operator(expr.op)} {self.expr_for_integer_comparison(expr.right, expr.left)}"
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
            runtime_call = self.runtime_call_expr(expr, None)
            if runtime_call is not None:
                return runtime_call
            if expr.type_args:
                self.unsupported(expr, "generic calls are not supported by Go codegen V1")
            call_routine = self.called_routine(expr.name)
            if call_routine is not None and call_routine.aborts:
                self.unsupported(expr, "aborting calls in expressions are not supported by Go codegen V1")
            args = self.render_call_args(expr.args, call_routine)
            return f"{self.callable_name(expr.name, expr)}({args})"
        self.unsupported(expr, "expression not supported by Go codegen V1")
        return "nil"

    def await_expr(self, expr: AwaitExpr) -> str:
        if isinstance(expr.expr, VarExpr) and self.is_join_handle_type(self.current_local_types.get(expr.expr.name)):
            return f"{go_local_name(expr.expr.name)}.value"
        return self.expr(expr.expr)

    def callable_name(self, name: str, node: Any) -> str:
        current_prefix = f"{self.program.module_name}."
        if name.startswith(current_prefix):
            return go_exported_name(name[len(current_prefix):])
        for module_name in sorted(self.imports_by_module, key=len, reverse=True):
            prefix = f"{module_name}."
            if name.startswith(prefix):
                symbol_name = name[len(prefix):]
                if "." in symbol_name:
                    self.unsupported(node, f"nested imported routine names are not supported by Go codegen V1: {name}")
                self.used_import_modules.add(module_name)
                return f"{go_import_alias(module_name)}.{go_exported_name(symbol_name)}"
        if "." in name:
            self.unsupported(node, f"qualified call target is not imported by this module: {name}")
            return go_qualified_name(name)
        exposed_module = self.exposed_symbols.get(name)
        if exposed_module is None and name in self.exposed_symbols:
            self.unsupported(node, f"ambiguous exposed symbol in imported modules: {name}")
            return go_exported_name(name)
        if exposed_module is not None and name not in self.local_routines:
            self.used_import_modules.add(exposed_module)
            return f"{go_import_alias(exposed_module)}.{go_exported_name(name)}"
        return go_exported_name(name)

    def runtime_call_statement(self, stmt: CallStmt) -> list[str] | None:
        if stmt.name == "Std.IO.log":
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            return [f"fmt.Println({self.expr(stmt.args[0])})"]
        if stmt.name == "Std.IO.logf":
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            if len(stmt.args) == 1:
                return [f"fmt.Println({self.expr(stmt.args[0])})"]
            return [f"fmt.Println({self.render_string_template_call(stmt.args)})"]
        if stmt.name in {"Std.IO.log_int", "Std.IO.log_bool", "Std.IO.log_double"}:
            self.used_runtime_modules.add("Std.IO")
            self.std_imports.add("fmt")
            return [f"fmt.Println({self.expr(stmt.args[0])})"]
        return None

    def runtime_call_expr(self, expr: CallExpr, expected_type: Any) -> str | None:
        resolved_name = expr.name
        exposed_module = self.exposed_symbols.get(expr.name)
        if exposed_module is not None and expr.name not in self.local_routines:
            resolved_name = f"{exposed_module}.{expr.name}"

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
            res_type = ResultTypeName(TypeName("String"), "String")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return f"func() ResultStringString {{ content, err := os.ReadFile({self.expr(expr.args[0])}); if err != nil {{ return ResultStringString{{Ok: false, Error: err.Error()}} }}; return ResultStringString{{Ok: true, Value: string(content)}} }}()"

        if resolved_name == "File.write_string":
            self.std_imports.add("os")
            self.std_imports.add("path/filepath")
            res_type = ResultTypeName(TypeName("Boolean"), "String")
            self.result_types.setdefault(type_to_string(res_type), res_type)
            return f"func() ResultBooleanString {{ dir := filepath.Dir({self.expr(expr.args[0])}); if err := os.MkdirAll(dir, 0755); err != nil {{ return ResultBooleanString{{Ok: false, Error: err.Error()}} }}; err := os.WriteFile({self.expr(expr.args[0])}, []byte({self.expr(expr.args[1])}), 0644); if err != nil {{ return ResultBooleanString{{Ok: false, Error: err.Error()}} }}; return ResultBooleanString{{Ok: true, Value: true}} }}()"

        async_call = self.async_runtime_call_expr(expr)
        if async_call is not None:
            return async_call
        if expr.name == "Json.stringify":
            self.std_imports.add("encoding/json")
            self.needs_json_helper = True
            return f"freeholdJSONString({self.expr(expr.args[0])})"
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
        return None

    def render_channel_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel requires one type argument and one capacity argument")
            return "FreeholdChannel[any]{}"
        value_type = self.go_type_string(expr.type_args[0])
        return f"FreeholdChannel[{value_type}]{{ch: make(chan {value_type}, int({self.expr(expr.args[0])}))}}"

    def render_channel_endpoint_call(self, expr: CallExpr, endpoint_type: str) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel endpoint requires one type argument and one Channel argument")
            return f"{endpoint_type}[any]{{}}"
        value_type = self.go_type_string(expr.type_args[0])
        return f"{endpoint_type}[{value_type}]{{ch: {self.expr(expr.args[0])}.ch}}"

    def render_channel_send_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 2:
            self.unsupported(expr, "channel_send requires one type argument, a Sender, and a value")
            return "false"
        value_type = self.go_type_string(expr.type_args[0])
        return f"freeholdChannelSend[{value_type}]({self.expr(expr.args[0])}, {self.expr(expr.args[1])})"

    def render_channel_receive_call(self, expr: CallExpr) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or len(expr.args) != 1:
            self.unsupported(expr, "channel_receive requires one type argument and a Receiver")
            return "nil"
        value_type = self.go_type_string(expr.type_args[0])
        return f"freeholdChannelReceive[{value_type}]({self.expr(expr.args[0])})"

    def render_spawn_call(self, expr: CallExpr, task_arg_index: int) -> str:
        self.needs_async_helpers = True
        if not expr.type_args or len(expr.type_args) != 1 or task_arg_index >= len(expr.args):
            self.unsupported(expr, "scope spawn requires one type argument and an awaitable value")
            return "FreeholdJoinHandle[any]{}"
        value_type = self.go_type_string(expr.type_args[0])
        return f"FreeholdJoinHandle[{value_type}]{{value: {self.expr(expr.args[task_arg_index])}}}"

    def render_join_call(self, expr: CallExpr, handle_arg_index: int) -> str:
        self.needs_async_helpers = True
        if handle_arg_index >= len(expr.args):
            self.unsupported(expr, "scope join requires a JoinHandle argument")
            return "nil"
        return f"{self.expr(expr.args[handle_arg_index])}.value"

    def is_join_handle_type(self, type_ref: Any) -> bool:
        if isinstance(type_ref, TypeName):
            return self.is_join_handle_type(type_ref.name)
        if isinstance(type_ref, str):
            generic = parse_generic(type_ref)
            return generic is not None and generic[0] == "JoinHandle" and len(generic[1]) == 1
        return False

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
        return None

    def render_call_args(self, args: list[Any], routine: RoutineDecl | None) -> str:
        if routine is None:
            return ", ".join(self.expr(arg) for arg in args)
        rendered: list[str] = []
        for index, arg in enumerate(args):
            if index < len(routine.params) and routine.params[index].type_name == "Integer":
                rendered.append(self.expr_as_int64(arg))
            else:
                rendered.append(self.expr(arg))
        return ", ".join(rendered)

    def expr_as_int64(self, expr: Any) -> str:
        rendered = self.expr(expr)
        return f"int64({rendered})" if self.integer_expr_kind(expr) == "inferred_int" else rendered

    def expr_for_integer_comparison(self, expr: Any, other: Any) -> str:
        if self.integer_expr_kind(expr) == "inferred_int":
            other_kind = self.integer_expr_kind(other)
            if other_kind not in {"inferred_int", "untyped"}:
                return f"int64({self.expr(expr)})"
        return self.expr(expr)

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
            return f"FreeholdChannel[{go_type_string(args[0])}]"
        if base == "Sender" and len(args) == 1:
            return f"FreeholdSender[{go_type_string(args[0])}]"
        if base == "Receiver" and len(args) == 1:
            return f"FreeholdReceiver[{go_type_string(args[0])}]"
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
            tag_parts.append(f'json:"{field.name}"')
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
        lines.append(f"type {service_name}Server interface {{")
        for rpc in service.rpcs:
            lines.append(f"\t{go_exported_name(rpc.name)}(context.Context, *{go_exported_name(rpc.request_type)}) (*{go_exported_name(rpc.response_type)}, error)")
        lines.extend(["}", ""])
        lines.extend([
            f"type Unimplemented{service_name}Server struct{{}}",
            "",
        ])
        for rpc in service.rpcs:
            lines.extend([
                f"func (Unimplemented{service_name}Server) {go_exported_name(rpc.name)}(context.Context, *{go_exported_name(rpc.request_type)}) (*{go_exported_name(rpc.response_type)}, error) {{",
                f"\treturn nil, status.Error(codes.Unimplemented, \"method {go_exported_name(rpc.name)} not implemented\")",
                "}",
                "",
            ])

        # Client interface
        lines.extend([
            f"type {service_name}Client interface {{",
        ])
        for rpc in service.rpcs:
            lines.append(f"\t{go_exported_name(rpc.name)}(ctx context.Context, in *{go_exported_name(rpc.request_type)}, opts ...grpc.CallOption) (*{go_exported_name(rpc.response_type)}, error)")
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
        for rpc in service.rpcs:
            method_name = go_exported_name(rpc.name)
            req_type = go_exported_name(rpc.request_type)
            resp_type = go_exported_name(rpc.response_type)
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
            method_name = go_exported_name(rpc.name)
            lines.extend([
                "\t\t{",
                f"\t\t\tMethodName: \"{method_name}\",",
                f"\t\t\tHandler: _{service_name}_{method_name}_Handler,",
                "\t\t},",
            ])
        lines.extend([
            "\t},",
            "\tStreams: []grpc.StreamDesc{},",
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
    return exported[:1].lower() + exported[1:]


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
