# Freehold CLI Toolchain

This adds a small command-line frontend without changing the Freehold language syntax.

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
Comparable parse-ok cases: 210
Matching shape:            210
Mismatching shape:         0
```
