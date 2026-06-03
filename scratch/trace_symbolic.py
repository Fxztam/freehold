import sys
import os
from pathlib import Path

os.environ["FREEHOLD_PROVER"] = "none"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.module_resolver import ModuleResolver
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.verifier import verify_program
import freehold.core.symbolic as sym

resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
resolved_modules = resolver.resolve_entry(REPO_ROOT / "bootstrap/compiler_core_v1/Compiler/Core/Loader.fh")

# Build imported modules dict
imported_modules = {}
for name, resolved in resolved_modules.items():
    if name != "Compiler.Core.Loader":
        imported_modules[name] = verify_program(resolved.ast, imported_modules=dict(imported_modules), prover="none")

vp = verify_program(resolved_modules["Compiler.Core.Loader"].ast, imported_modules=imported_modules, prover="none")

# Instrument walk_body to trace execution
original_walk_body = sym.walk_body

def traced_walk_body(body, env, path_conditions, routines, types, records, obs, r, r_name, *args, **kwargs):
    print(f"  walk_body called for routine {r_name} with {len(body)} statements. Path conditions: {len(path_conditions)}", flush=True)
    
    # We will wrap walk_body but print statements as they are processed
    # To do that, we can intercept the loop inside walk_body, or just let it run.
    # But since it hangs, let's print statement types and loop index!
    body = list(body)
    i = 0
    while i < len(body):
        stmt = body[i]
        stmt_class = stmt.__class__.__name__
        print(f"    [{r_name}] Processing stmt {i}/{len(body)}: {stmt_class} (line {stmt.pos.line if hasattr(stmt, 'pos') and stmt.pos else '?'})", flush=True)
        
        # Call original walk_body but for just one statement at a time to trace nested calls!
        # Wait, walk_body processes the list in a loop and handles IfStmt/WhileStmt/CaseStmt by recursively calling walk_body with the rest of the body.
        # So we can just print and call the original on the single-statement block.
        # But wait, original walk_body modifies and slices body.
        # Let's just print a message at the beginning of walk_body and let it run, but print nested entries!
        break # we'll implement a custom walk_body trace
    
    # Let's just run the original walk_body but print when it enters and exits
    res = original_walk_body(body, env, path_conditions, routines, types, records, obs, r, r_name, *args, **kwargs)
    print(f"  walk_body finished for routine {r_name}", flush=True)
    return res

sym.walk_body = traced_walk_body

print("Running symbolic_obligations...", flush=True)
obs = sym.symbolic_obligations(vp, imported_modules=imported_modules)
print(f"Done! Extracted {len(obs)} obligations.", flush=True)
