import sys
import os
from pathlib import Path

os.environ["FREEHOLD_PROVER"] = "none"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("Importing...", flush=True)
from freehold.core.module_resolver import ModuleResolver
from freehold.core.go_codegen import GoGenerator, GO_RUNTIME_MODULE_EXPORTS
print("Imported successfully.", flush=True)

source_path = REPO_ROOT / "bootstrap/compiler_core_v1/Compiler/Core/Loader.fh"
print("Creating ModuleResolver...", flush=True)
resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
print("Resolving entry...", flush=True)
resolved_modules = resolver.resolve_entry(source_path)
print(f"Resolved {len(resolved_modules)} modules: {list(resolved_modules.keys())}", flush=True)

for name in sorted(resolved_modules):
    print(f"Generating for module {name}...", flush=True)
    resolved = resolved_modules[name]
    gen = GoGenerator(resolved.ast, resolved_modules)
    result = gen.generate()
    print(f"Module {name} generated successfully. Supported: {result.supported}", flush=True)
