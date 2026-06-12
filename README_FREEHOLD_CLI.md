# Freehold CLI Toolchain

This adds a small command-line frontend without changing the Freehold language syntax.

## Structured parser diagnostics

The Go parser emits structured diagnostics for all parse errors.

- **Catalog:** `go-frontend/internal/diagnostic/catalog.go`
- **Examples:** `artifacts/go-ast/*/*.json`

Every new error class gets a stable code and catalog entry.

## Commands

```bash
python -m freehold run examples/hello_cli.fh
python -m freehold verify examples/hello_cli.fh
python -m freehold ast examples/hello_cli.fh
python -m freehold test --log cli_test.log --json-summary cli_summary.json
python -m freehold ebnf
```

Step-by-step source directory test command:

```powershell
.\test.ps1
.\test.ps1 --quick
.\test.ps1 01_core
```

Or from `cmd.exe`:

```cmd
test.cmd
test.cmd --quick
test.cmd 01_core
```

The step runner executes the CLI smoke test, the core language module tests, the full regression suite, and the example demos. Use `--quick` for the shorter loop while working on diagnostics.
Pass a language module name such as `01_core` to run only that module.

Short developer commands:

```powershell
.\fhenv.ps1
fhrun .\tests\language_modules\01_core\valid\minimal_module.fh
fhverify .\tests\language_modules\01_core\valid\minimal_module.fh
fhfast .\tests\language_modules\01_core\valid\minimal_module.fh
fhtest 01_core
```

From the project root, use:

```powershell
.\fhenv.ps1
fhrun .\tests\language_modules\01_core\valid\minimal_module.fh
fhtest 01_core
```

After `fhenv.ps1`, the same short commands also work from subfolders, for example inside `tests\language_modules\01_core\valid`:

```powershell
fhrun .\minimal_module.fh
fhverify .\minimal_module.fh
```

The core language module can also be tested directly from its folders:

```powershell
cd tests\language_modules\01_core
.\test.ps1

cd invalid_syntax
.\test.ps1
```

Optional Windows wrappers:

```cmd
freehold.cmd run examples/hello_cli.fh
```

PowerShell:

```powershell
.\freehold.ps1 run examples/hello_cli.fh
```

## Parser artifact paths

Run the full parser conformance chain with one command:

```powershell
.\verify-parser-conformance.cmd
```

The verify command regenerates Go AST artifacts, checks expected Go diagnostics, verifies the semantic-rule diagnostic spec, checks expected semantic/type diagnostics, regenerates DHParser AST artifacts, runs all parser comparison gates, and finishes with `go test ./...`.

Expected Go parser diagnostics are stored in:

```text
tests/language_modules/expected_diagnostics.json
```

Expected semantic/type diagnostics are stored in:

```text
tests/language_modules/expected_semantic_diagnostics.json
```

The semantic diagnostic spec is stored in:

```text
spec/freehold.diag
spec/freehold.rules
```

Verify the spec diagnostic coverage with:

```powershell
.\verify-spec-diagnostics.cmd
```

```text
artifacts/verify-spec-diagnostics
```

This gate checks that every `emit FH-*` in `spec/freehold.rules` exists in `spec/freehold.diag`, every expected syntax/semantic diagnostic code exists in `spec/freehold.diag`, and every `CODE_MAP` entry from the semantic diagnostic normalizer has a matching spec diagnostic.

Current spec diagnostic baseline:

```text
Diagnostic specs:        87
Rule emits:              87
Expected syntax codes:   19
Expected semantic codes: 60
CODE_MAP entries:        64
Failures:                0
```

The Go parser frontend writes parse results and reports to:

```powershell
cd go-frontend
.\go-parse-tests-language-modules.cmd
```

```text
artifacts/go-ast
```

The DHParser path writes the matching corpus layout to:

```powershell
.\dhparser-parse-tests-language-modules.cmd
```

```text
artifacts/dhparser-ast
```

Both artifact roots contain `_summary.json`, `_errors.txt`, and one JSON file per parsed `.fh` source.

Compare Go and DHParser parse status artifacts with:

```powershell
.\compare-parser-status.cmd
```

```text
artifacts/compare-parse-status
```

The first comparator stage checks `parse_ok` parity and records mismatch reports. AST-shape comparison comes after the parse-status baseline is aligned.

Compare parse error diagnostics for the cases that both parsers reject with:

```powershell
.\compare-parse-errors.cmd
```

```text
artifacts/compare-parse-errors
```

This diagnostic report keeps failure locations visible without making the parser conformance gates depend on identical third-party error wording. Go parser artifacts now include a structured `diagnostic` object with code, message, location, expected tokens, found token, and hint, plus `diagnostics[]` for recovery cases that produce more than one parser diagnostic. The singular `diagnostic` field remains a compatibility alias for the first entry.

The report also assigns provisional Freehold diagnostic codes. Current ranges are reserved as:

```text
FH-SYN-0001..0999  syntax and parsing diagnostics
FH-SEM-1000..1999  semantic diagnostics
FH-TYP-2000..2999  type diagnostics
FH-CON-3000..3999  contract diagnostics
FH-TPL-4000..4099  string template diagnostics
FH-JSON-4200..4299 JSON diagnostics
FH-BLD-9000..9999  bootstrap/tooling diagnostics
```

Current parse-error diagnostic baseline:

```text
Shared failures:               43
Matching failure locations:    40
Mismatching failure locations: 3
Status mismatches:             0
```

Compare semantic/type diagnostics with:

```powershell
.\compare-semantic-diagnostics.cmd
```

```text
artifacts/compare-semantic-diagnostics
```

Current semantic/type diagnostic baseline:

```text
Expected semantic diagnostics:    69
Matching semantic diagnostics:    69
Mismatching semantic diagnostics: 0
```

Positive feature-matrix coverage is tracked in:

```text
tests/language_modules/positive_feature_matrix.json
```

The current matrix includes valid interaction cases for while invariants plus variants, case branches with record values, record-field contracts, qualified calls in contracts, comma-separated `requires`/`ensures`, declared abort paths, abort call propagation, explicit top-level main aborts, positional and named string templates, string templates inside `Std.IO.logf`, string templates inside record literals, Big number calls inside expressions, `Json.stringify` on record values, typed `Json.parse<Record>(text)` Result flows, `@json("externalName")` record-field mapping, compile-time JSON literal schema diagnostics, `Result<Array<...>, E>` ok payloads, and `value.field` contracts over record ok payloads.

Compare normalized AST shape for the files that both parsers accept with:

```powershell
.\compare-ast-shape.cmd
```

```text
artifacts/compare-ast-shape
```

This second stage compares a normalized outline of modules, declarations, statement trees, and canonical expression text. It is intentionally separate from raw JSON equality because DHParser artifacts are CST-shaped while Go artifacts are already semantic AST-shaped.

Current normalized AST-shape baseline:

```text
Comparable parse-ok cases: 238
Matching shape:            238
Mismatching shape:         0
```

Compare normalized semantic ASTs for the files that both parsers accept with:

```powershell
.\compare-ast-semantic.cmd
```

## FH-IR profile (V1)

Export project-wide FH-IR directly from CLI with:

```powershell
python -m freehold ir .\examples\compiler_v1\01_minimal_app\App\Main.fh
```

This emits FH-IR schema `fh-ir-v1` and serializes the full resolved import graph.

V1 includes:

```text
- complete project module set (not only entry module)
- canonical module order
- per-module canonical imports/declarations/analysis
- explicit import graph edges with exposing and qualified_exposing
- explicit runtime module entries for imported runtime modules
```

V1 now also includes explicit schema version metadata and fixed root node names:

```text
- schema_profile: fh-ir
- schema_version: { major, minor, patch }
- fixed node names (for example: FhirDocumentV1, ProjectGraph, ModuleEntry, ImportEdge)
```

Type and verifier representation in FH-IR is normalized for stable downstream checks:

```text
- type_repr payloads on record fields, routine params, and RPC request/response types
- explicit Result/Array/Awaitable type nodes in type_repr
- verifier report mirrored under analysis.verifier
- proof obligations and flow summaries emitted with fixed node names
```

Contract metadata is exported explicitly for verification-aware tooling:

```text
- routine.contract_bindings with explicit binding entries
- explicit Result value/error bindings (value, error)
- context availability matrix for requires/ensures/aborts
```

FH-IR now keeps source syntax and semantic enrichment clearly separated:

```text
- source_ast section for canonical declaration/statement tree
- semantic_ir section for verifier/enriched analysis data
- compatibility aliases remain (module/analysis) for existing consumers
```

Legacy single-module export remains available with:

```powershell
python -m freehold ir .\examples\compiler_v1\01_minimal_app\App\Main.fh --module-only
```

This emits schema `fh-ir-v0`.

Compare canonical FH-IR baselines with:

```powershell
.\compare-fhir.cmd
```

Compare canonical FH-IR V1 baselines with:

```powershell
.\compare-fhir-v1.cmd
```

Targeted V1 baseline update:

```powershell
.\compare-fhir-v1-update.cmd
```

```text
artifacts/compare-fhir
```

Run the additive determinism check in a small scope with:

```powershell
.\compare-fhir-determinism.cmd
```

```text
artifacts/compare-fhir-determinism
```

The determinism check validates FH-IR canonical export constraints:

```text
- stable ordering for modules/imports/declarations/record fields
- stable ordering in analysis lists (types, records, errors, routines, services)
- no source-position payloads in the comparison profile
- no Python runtime/object-name leakage in serialized output
- deterministic repeated export text for the same input
```

Determinism artifacts now include a normalized manifest for bootstrap comparisons:

```text
artifacts/compare-fhir-determinism/_manifest.json
```

The manifest contains stable per-case schema metadata, normalized diagnostics, and sorted violation lists.

The parser conformance verify chain includes this check as a narrow additive gate. It is intentionally small-scope by default to keep baseline runtime low while still catching ordering drift.

The parser conformance verify chain now includes the FH-IR V1 compare gate by default. Use the escape flag when needed:

```powershell
.\verify-parser-conformance.cmd --disable-fhir-v1-gate
```

Run the FH-IR language-module stability gate (stable profile) with:

```powershell
.\compare-fhir-language-modules.cmd
```

```text
artifacts/compare-fhir-language-modules
```

The language-module gate starts with stable domains and expands stepwise:

```text
- records
- results
- arrays
- contracts
- imports
```

Language-module artifacts also include a normalized comparison manifest:

```text
artifacts/compare-fhir-language-modules/_manifest.json
```

For broader coverage, run the expanded profile directly:

```powershell
python .\tools\compare_fhir_language_modules.py --profile expanded
```

### FH-IR V1 limits (intentional)

FH-IR v1 is a canonical project export profile, not a full lowering IR. The following are intentionally out of scope in v1:

```text
- backend-specific lowering stages and optimization passes
- executable runtime representation details
- cross-target ABI/packing commitments
- V1/V2 lowering metadata and phase annotations
```

These omissions are expected and should not be interpreted as regressions when later V2/V3 lowering layers are introduced.

```text
artifacts/compare-ast-semantic
```

This third stage normalizes expressions into typed nodes such as `BinaryExpr`, `CallExpr`, `IndexExpr`, `StringExpr`, `OkExpr`, and `ErrorExpr` before comparing the complete accepted program ASTs.

Current normalized semantic AST baseline:

```text
Comparable parse-ok cases:    238
Matching semantic AST:        238
Mismatching semantic AST:     0
```
