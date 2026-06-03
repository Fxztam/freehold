import sys
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.module_resolver import ModuleResolver
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.symbolic import symbolic_obligations, solve_smt_query
from freehold.core.verifier import verify_program

# Disable prover during initial resolver run to load AST cleanly
os.environ["FREEHOLD_PROVER"] = "none"

source_path = REPO_ROOT / "bootstrap/compiler_core_v1/Compiler/Core/Loader.fh"
resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
resolved_modules = resolver.resolve_entry(source_path)

# Enable prover for manual trace
os.environ["FREEHOLD_PROVER"] = "z3"

print("Extracting symbolic obligations...", flush=True)

# Build imported modules dict using verified programs
imported_modules = {}
for name, resolved in resolved_modules.items():
    if name != "Compiler.Core.Loader":
        # Ensure it has a verified program
        imported_modules[name] = verify_program(resolved.ast, imported_modules=dict(imported_modules), prover="none")

vp = verify_program(resolved_modules["Compiler.Core.Loader"].ast, imported_modules=imported_modules, prover="none")
obs = symbolic_obligations(vp, imported_modules=imported_modules)
print(f"Total obligations: {len(obs)}", flush=True)

for i, ob in enumerate(obs):
    print(f"Obligation {i+1}/{len(obs)}: Kind={ob['kind']}, Location={ob['location']}", flush=True)
    t0 = time.time()
    res = solve_smt_query(ob["smt_query"], prover="z3", timeout=2)
    t1 = time.time()
    print(f"  Result: {res} (Time: {t1-t0:.4f}s)", flush=True)
    if t1 - t0 > 1.5:
        print(f"  Slow query: {ob['smt_query'][:200]}...", flush=True)
