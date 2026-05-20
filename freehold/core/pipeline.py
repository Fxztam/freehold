from __future__ import annotations

from pathlib import Path
from pprint import pprint
from typing import Any

from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program
from freehold.core.interpreter import Interpreter
from freehold.core.module_resolver import ModuleResolver

def read_source(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Freehold file not found: {p}")
    return p.read_text(encoding="utf-8")

def parse_file(path: str | Path) -> Any:
    return parse_source(read_source(path))

def verify_file(path: str | Path) -> Any:
    return ModuleResolver().verify_entry(path)

def run_file(path: str | Path) -> Any:
    verified = verify_file(path)
    return Interpreter(verified).run_main()

def print_ast(path: str | Path) -> None:
    pprint(parse_file(path))

def verify_source(source: str) -> Any:
    return verify_program(parse_source(source))

def run_source(source: str) -> Any:
    return Interpreter(verify_source(source)).run_main()
