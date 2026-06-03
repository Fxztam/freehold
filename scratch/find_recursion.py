import sys
import os
from pathlib import Path

os.environ["FREEHOLD_PROVER"] = "none"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.module_resolver import ModuleResolver
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.ast import CallStmt, CallExpr

resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
resolved_modules = resolver.resolve_entry(REPO_ROOT / "bootstrap/compiler_core_v1/Compiler/Core/Loader.fh")

loader_ast = resolved_modules["Compiler.Core.Loader"].ast
routines = {decl.name: decl for decl in loader_ast.declarations if hasattr(decl, "body")}

print("Routines in Loader.fh:")
for r_name, r in routines.items():
    calls = []
    def find_calls(nodes):
        if isinstance(nodes, list):
            for n in nodes: find_calls(n)
        elif isinstance(nodes, (CallStmt, CallExpr)):
            calls.append(nodes.name)
            for arg in nodes.args: find_calls(arg)
        elif hasattr(nodes, "__dict__"):
            for v in nodes.__dict__.values():
                find_calls(v)
    find_calls(r.body)
    print(f"  {r_name} calls: {list(set(calls))}")
