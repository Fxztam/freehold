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
Expected semantic diagnostics:    68
Matching semantic diagnostics:    68
Mismatching semantic diagnostics: 0
```

Positive feature-matrix coverage is tracked in:

```text
tests/language_modules/positive_feature_matrix.json
```

The current matrix includes valid interaction cases for while invariants plus variants, case branches with record values, record-field contracts, qualified calls in contracts, comma-separated `requires`/`ensures`, declared abort paths, abort call propagation, positional and named string templates, string templates inside `Std.IO.logf`, string templates inside record literals, Big number calls inside expressions, `Json.stringify` on record values, and `Result<Array<...>, E>` ok payloads. `value.field` in Result ensures remains an explicit known gap until field access from the special `value` contract expression is supported.

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
Comparable parse-ok cases: 236
Matching shape:            236
Mismatching shape:         0
```

Compare normalized semantic ASTs for the files that both parsers accept with:

```powershell
.\compare-ast-semantic.cmd
```

```text
artifacts/compare-ast-semantic
```

This third stage normalizes expressions into typed nodes such as `BinaryExpr`, `CallExpr`, `IndexExpr`, `StringExpr`, `OkExpr`, and `ErrorExpr` before comparing the complete accepted program ASTs.

Current normalized semantic AST baseline:

```text
Comparable parse-ok cases:    236
Matching semantic AST:        236
Mismatching semantic AST:     0
```
