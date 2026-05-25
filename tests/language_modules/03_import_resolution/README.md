# 03_import_resolution

Multi-file import resolution tests live here.

This section starts after local import declaration diagnostics in `02_import`.
It is active in `test-language` and uses the real `ModuleResolver`.

Modules in one import graph must live under one common module root. The root is
derived from the entry module path and its declared module name:

```text
fixtures/valid/import_existing_module/App/Main.fh
module App.Main

root = fixtures/valid/import_existing_module
import Banking.Proofs -> fixtures/valid/import_existing_module/Banking/Proofs.fh
```

That means sibling top-level module folders, such as `App/` and `Banking/`, must
sit next to each other under the same root.

Planned diagnostics:

```text
VF-M001 imported module not found
VF-M002 imported file module name mismatch
VF-M003 imported module has syntax error
VF-M004 exposed symbol not found
VF-M005 cyclic import
VF-I006 ambiguous exposed symbol
```

Planned resolver responsibilities:

```text
Import name -> file path
Parse imported module
Verify imported module file envelope
Compare declared module name with expected import name
Check exposing symbols
Detect import cycles
Reject ambiguous symbols exposed from multiple imports
```

Fixture layout:

```text
fixtures/
  valid/import_existing_module/
  valid/import_transitive_name_conflicts/
  invalid/imported_module_not_found/
  invalid/imported_module_not_sibling/
  invalid/imported_module_name_mismatch/
  invalid/imported_module_syntax_error/
  invalid/exposed_symbol_not_found/
  invalid/cyclic_import/
  invalid/ambiguous_exposed_routine/
  invalid/ambiguous_exposed_record/
  invalid/ambiguous_exposed_error/
```

Run this module with:

```powershell
fhtest 03_import_resolution
```
