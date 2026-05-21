from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from freehold.core.ast import ErrorDecl, Program, RecordTypeDecl, RoutineDecl, TypeCheckError, TypeDecl
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program


@dataclass(frozen=True)
class ResolvedModule:
    name: str
    path: Path
    ast: Program
    verified: Any


class ModuleResolver:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else None
        self.resolved: dict[str, ResolvedModule] = {}
        self.entry: ResolvedModule | None = None

    def module_path(self, module_name: str) -> Path:
        if self.root is None:
            raise TypeCheckError("module resolver root is not set")
        return self.root.joinpath(*module_name.split(".")).with_suffix(".fh")

    def resolve_entry(self, entry_file: str | Path) -> dict[str, ResolvedModule]:
        entry_path = Path(entry_file)
        if not entry_path.is_absolute() and self.root is not None:
            entry_path = self.root / entry_path
        entry_path = entry_path.resolve()
        source = entry_path.read_text(encoding="utf-8")
        program = parse_source(source)
        verified = verify_program(program)
        if self.root is None:
            self.root = infer_module_root(entry_path, program.module_name)
        expected_path = self.module_path(program.module_name).resolve()
        if entry_path != expected_path:
            raise TypeCheckError(
                f"{program.pos.text()}: module file path mismatch: expected {expected_path}, got {entry_path}"
            )
        self.entry = ResolvedModule(program.module_name, entry_path, program, verified)
        self.resolved[program.module_name] = self.entry
        self._resolve_imports(program, stack=[program.module_name])
        return dict(self.resolved)

    def verify_entry(self, entry_file: str | Path) -> Any:
        self.resolve_entry(entry_file)
        if self.entry is None:
            raise TypeCheckError("module resolver did not produce an entry module")
        return self.entry.verified

    def _resolve_imports(self, program: Program, stack: list[str]) -> None:
        for import_decl in program.imports or []:
            module_name = import_decl.module_name
            if module_name in stack:
                cycle = " -> ".join(stack + [module_name])
                raise TypeCheckError(f"{import_decl.pos.text()}: cyclic import: {cycle}")
            if module_name not in self.resolved:
                path = self.module_path(module_name)
                if not path.exists():
                    raise TypeCheckError(f"{import_decl.pos.text()}: imported module not found: {module_name}")
                imported_source = path.read_text(encoding="utf-8")
                try:
                    imported_program = parse_source(imported_source)
                except Exception as exc:
                    if type(exc).__name__ in {"UnexpectedToken", "UnexpectedCharacters", "UnexpectedEOF"}:
                        raise TypeCheckError(f"{import_decl.pos.text()}: imported module has syntax error: {module_name}") from exc
                    raise
                imported_verified = verify_program(imported_program)
                if imported_program.module_name != module_name:
                    raise TypeCheckError(
                        f"{import_decl.pos.text()}: imported module name mismatch: expected {module_name}, got {imported_program.module_name}"
                    )
                self.resolved[module_name] = ResolvedModule(module_name, path, imported_program, imported_verified)
                self._resolve_imports(imported_program, stack + [module_name])
            self._check_exposing(import_decl, self.resolved[module_name].ast)

    def _check_exposing(self, import_decl, imported_program: Program) -> None:
        if not import_decl.exposing:
            return
        symbols = exported_symbols(imported_program)
        for symbol_name in import_decl.exposing:
            if symbol_name not in symbols:
                raise TypeCheckError(
                    f"{import_decl.pos.text()}: exposed symbol not found: {symbol_name} in import {import_decl.module_name}"
                )


def exported_symbols(program: Program) -> set[str]:
    symbols: set[str] = set()
    for declaration in program.declarations:
        if isinstance(declaration, (TypeDecl, RecordTypeDecl, ErrorDecl, RoutineDecl)):
            symbols.add(declaration.name)
    return symbols


def infer_module_root(entry_path: Path, module_name: str) -> Path:
    parts = module_name.split(".")
    if len(entry_path.parents) < len(parts):
        raise TypeCheckError(f"module path is too short for module name: {module_name}")
    return entry_path.parents[len(parts) - 1]