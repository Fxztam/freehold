# Freehold CLI Toolchain

This adds a small command-line frontend without changing the Freehold language syntax.

## Commands

```bash
python -m freehold run examples/hello_cli.vf
python -m freehold verify examples/hello_cli.vf
python -m freehold ast examples/hello_cli.vf
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
fhrun .\tests\language_modules\01_core\valid\minimal_module.vf
fhverify .\tests\language_modules\01_core\valid\minimal_module.vf
fhfast .\tests\language_modules\01_core\valid\minimal_module.vf
fhtest 01_core
```

From the project root, use:

```powershell
.\fhenv.ps1
fhrun .\tests\language_modules\01_core\valid\minimal_module.vf
fhtest 01_core
```

After `fhenv.ps1`, the same short commands also work from subfolders, for example inside `tests\language_modules\01_core\valid`:

```powershell
fhrun .\minimal_module.vf
fhverify .\minimal_module.vf
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
freehold.cmd run examples/hello_cli.vf
```

PowerShell:

```powershell
.\freehold.ps1 run examples/hello_cli.vf
```
