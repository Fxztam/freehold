import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("Importing modules...")
from freehold.core.module_resolver import ModuleResolver
from freehold.core.go_codegen import GoGenerator, GO_RUNTIME_MODULE_EXPORTS

# Monkeypatch ModuleResolver to print resolution and verification steps
original_resolve_imports = ModuleResolver._resolve_imports
def new_resolve_imports(self, program, stack):
    print(f"  Resolving imports for module: {program.module_name}")
    return original_resolve_imports(self, program, stack)

original_verify_module = ModuleResolver._verify_module
def new_verify_module(self, module_name):
    print(f"  Verifying module: {module_name} ...")
    t0 = time.time()
    res = original_verify_module(self, module_name)
    print(f"  Verified module: {module_name} in {time.time() - t0:.2f}s")
    return res

ModuleResolver._resolve_imports = new_resolve_imports
ModuleResolver._verify_module = new_verify_module

print("Resolving entry Main.fh...")
resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
start = time.time()
resolved_modules = resolver.resolve_entry(REPO_ROOT / "bootstrap/compiler_core_v1/App/Main.fh")
print(f"Resolved modules in {time.time() - start:.2f}s. Modules: {list(resolved_modules.keys())}")

for name in sorted(resolved_modules):
    print(f"Generating Go for {name}...")
    resolved = resolved_modules[name]
    t0 = time.time()
    result = GoGenerator(resolved.ast, resolved_modules).generate()
    print(f"Generated {name} in {time.time() - t0:.2f}s (supported={result.supported})")

print("Done diagnostic run successfully!")
