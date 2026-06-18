# Freehold Specification: Compile, Build, Go, and EXE Test

**Status:** Current post-bootstrap specification for compiling Freehold sources through the Go backend, building native executables, and validating generated EXE behavior

**Scope:** Go project generation, generated build scripts, native executable creation, Go-frontend confidence gates, Stage-3 post-bootstrap builds, runtime log checks, and release artifact handling

**Out of scope:** General parser conformance, full IR baseline management, language design proposals, and non-executable library-only module policy except where it affects EXE emission

---

## 1. Purpose

This document specifies the current Freehold compile-build-test path for native executables after the bootstrapping milestone.

The important post-bootstrap question is no longer only whether Freehold source can be parsed, verified, and interpreted. The practical question is:

```text
Can a verified Freehold entry module be lowered into a generated Go project, built by Go, emitted as a native executable, and then checked by running the resulting EXE against expected runtime behavior?
```

The answer is yes for the supported compiler examples and Stage-3 compiler-core contracts that are covered by the repository gates.

The executable path has two closely related variants:

1. Python CLI driven Go project generation and Go build.
2. Native Stage-3 compiler driven build after bootstrapping.

Both variants must preserve the same observable contract: generated Go code must compile, Go tests must pass, a native executable must be produced when the entry module has `Main`, and runtime output must match the expected golden log where a golden exists.

---

## 2. Current Post-Bootstrap Baseline

The current baseline is the repository state after Freehold has reached Stage-3 compiler-core validation.

Relevant closed status:

- Stage-1 bootstrapping reached byte-identical self-translation for compiler-core IR.
- Stage-3 compiler core exists as a native executable at `bin/stage3_compiler_core_v1.exe` when the Stage-3 gate has built it.
- The generated Go project for the compiler core is contract-checked by `verify-stage3-compiler-core-v1.cmd`.
- Supported compiler examples are verified through generated Go projects and executable runtime checks.
- The Go frontend has its own unit and conformance surface under `go-frontend`.

Post-bootstrap EXE testing therefore treats the native Stage-3 compiler as a product artifact, not only as an intermediate compiler experiment.

---

## 3. Definitions

**Entry module** means the Freehold source file passed as the root of compilation, usually an `App/Main.fh` file in a multi-module example.

**Executable entry** means the resolved entry module contains a generated `Main` routine that can be wrapped by Go `package main`.

**Generated Go project** means the directory written by `go-codegen-project` or by the Stage-3 compiler build path. It contains generated package files, `go.mod`, generated build scripts, and optionally `cmd/<exe>/main.go`.

**Generated EXE** means the native executable created from the generated Go project.

**Runtime golden** means the expected stdout log stored under `examples/expected_logs` or a Stage-3 manifest output file.

**Stage-3 compiler** means `bin/stage3_compiler_core_v1.exe`, produced from the bootstrapped compiler-core pipeline.

---

## 4. Source Of Truth Files

The current executable pipeline is implemented and verified through these files:

```text
freehold/cli/main.py
freehold/core/go_codegen.py
tools/verify_compiler_examples.py
tools/verify_stage3_compiler_on_examples.py
tools/verify_stage3_compiler_core_contracts.py
verify-compiler-examples.cmd
verify-stage3-compiler-examples.cmd
verify-stage3-compiler-core-v1.cmd
TODO-FH-TO-GO-EXE.md
DONE-BOOTSTRAPPING.md
DONE-COMPILER.md
OPEN-STATUS.md
```

Go frontend confidence is anchored in:

```text
go-frontend/internal/lexer/lexer.go
go-frontend/internal/parser/parser.go
go-frontend/internal/ast/ast.go
go-frontend/internal/semantic/analyzer.go
go-frontend/internal/semantic/project.go
go-frontend/internal/semantic/control_flow.go
go-frontend/internal/semantic/compare_ir.go
go-frontend/cmd/go-parse-tests-language-modules/main.go
go-frontend/cmd/go-compare-ir/main.go
go-frontend/PARSER_STATUS.md
```

---

## 5. High-Level Pipeline

The intended executable pipeline is:

```text
Freehold source
  -> parser and semantic verifier
  -> resolved module graph
  -> generated Go package files
  -> generated go.mod and build scripts
  -> generated cmd/<exe>/main.go wrapper
  -> go mod tidy
  -> go test ./...
  -> go build -trimpath
  -> native executable
  -> runtime stdout/log comparison
```

For Stage-3 post-bootstrap validation, the build step is additionally checked by invoking the native compiler:

```text
Freehold source
  -> Python verifier and Go project generation for test setup
  -> native stage3_compiler_core_v1.exe --build-exe
  -> generated executable
  -> runtime stdout/log comparison
```

The Stage-3 path is the stronger post-bootstrap evidence because it proves that the bootstrapped compiler artifact can participate in real executable production.

---

## 6. Python CLI Go Project Generation

The main project command is:

```powershell
python -m freehold go-codegen-project <entry.fh> --output-dir <out-dir> --json <out-dir>\_project.json --emit-executable --executable-name <exe-name>
```

The command performs these steps:

1. Resolves the Freehold module graph from the entry file.
2. Generates Go source files for supported Freehold modules.
3. Generates extra Go files for required runtime glue, such as gRPC bindings.
4. Generates `go.mod`.
5. Generates `build.cmd` and `build.sh`.
6. Generates `cmd/<exe-name>/main.go` if the entry module has `Main`.
7. Writes `_project.json` when requested.

The command returns success only if all generated project files report `supported = true`.

---

## 7. Direct Native Build Command

The convenience command is:

```powershell
python -m freehold build-exe <entry.fh> --output-dir <out-dir> --executable-name <exe-name>
```

This command is stricter than plain project generation. It requires the entry module to contain `Main` and fails when no executable entry exists.

Its build sequence is:

```text
generate Go project files
write extra generated files
write build files
run go mod tidy
run go build -trimpath -o <exe>
```

On Windows, the produced binary name ends in `.exe`.

The command reports the final executable path as:

```text
[OK] Successfully built native executable: <path>
```

---

## 8. Generated Project Layout

For an executable entry module, the generated project normally contains:

```text
<out-dir>/
  go.mod
  build.cmd
  build.sh
  _project.json
  cmd/<exe-name>/main.go
  bin/<exe-name>.exe
  <generated package directories>/...
```

The package layout is derived from Freehold module names. For example:

```text
App.Main -> app/main/main.go
Domain.Rules -> domain/rules/rules.go
```

The generated module path is:

```text
freehold.local
```

Runtime modules such as `Math`, `Std.IO`, and `Big` are mapped to Go runtime imports instead of being emitted as ordinary Freehold module stubs.

---

## 9. Generated Main Wrapper

When the entry module has `Main`, the generator writes:

```text
cmd/<exe-name>/main.go
```

The wrapper imports the generated entry package and calls `Main`.

For synchronous programs the wrapper shape is:

```go
package main

import (
    app_main "freehold.local/app/main"
)

func main() {
    app_main.Main()
}
```

For async/context-aware generated programs, the wrapper imports `context` and calls:

```go
app_main.Main(context.Background())
```

If `Main` returns `error`, the wrapper panics on non-nil errors so failed execution is visible to the process exit path.

For gRPC projects, generated binding or glue packages may be blank-imported so their `init` hooks register runtime dispatchers.

---

## 10. Generated Build Scripts

For executable projects, `generate_go_project_build_files` writes a Windows build script equivalent to:

```cmd
@echo off
setlocal
go mod tidy
if errorlevel 1 exit /b %errorlevel%
go test ./...
if errorlevel 1 exit /b %errorlevel%
go build -trimpath -o bin\<exe-name>.exe .\cmd\<exe-name>
```

It also writes a POSIX shell variant equivalent to:

```bash
#!/bin/bash
set -e
go mod tidy
go test ./...
go build -trimpath -o bin/<exe-name> ./cmd/<exe-name>
```

For non-executable library projects, build scripts still run dependency resolution and `go test ./...`, but no `cmd/<exe>` wrapper and no EXE are produced.

---

## 11. Go Dependency Resolution

Generated projects must run:

```powershell
go mod tidy
```

This is required because generated projects may depend on:

- the Go standard library,
- `google.golang.org/grpc` for gRPC services,
- local replacement paths for supported Go FFI modules,
- generated runtime glue packages.

The generated `go.mod` starts with:

```text
module freehold.local

go 1.22
```

Additional `require` and `replace` directives are inserted only when needed.

---

## 12. Go Test Before Go Build

Generated build scripts must run:

```powershell
go test ./...
```

before building the executable.

This catches:

- Go syntax errors in generated package files,
- package import path mistakes,
- generated gRPC glue errors,
- FFI replacement mistakes,
- runtime-log test failures inserted by the example verifier,
- ordinary Go unit failures in copied example support files.

The native executable must not be considered valid if `go test ./...` fails.

---

## 13. Native EXE Build

The final generated build command on Windows is:

```powershell
go build -trimpath -o bin\<exe-name>.exe .\cmd\<exe-name>
```

The `-trimpath` flag is part of the reproducibility policy. It reduces host-specific paths in build output.

The expected Windows output path for the Python-generated build script is:

```text
<out-dir>/bin/<exe-name>.exe
```

The Stage-3 native compiler path may emit into the project root depending on the build command used by the native compiler. The Stage-3 verifier accepts the root path and has a fallback check for `bin/` when needed.

---

## 14. Runtime EXE Validation

An EXE is not fully validated by existence alone.

For examples with expected logs, the verifier must run the generated executable and compare stdout against the expected file.

The expected files live under:

```text
examples/expected_logs
```

The executable check performs:

```text
run generated executable
capture stdout
normalize CRLF/LF line endings
compare with expected log
fail on non-zero exit code
fail on stdout mismatch
write actual mismatch log for inspection
```

The check is implemented in the `run_executable_log_check` functions in the compiler example verifiers.

---

## 15. Runtime Log Go Test

For examples with expected logs, the verifier also injects a Go test into the generated entry package:

```text
freehold_runtime_log_test.go
```

That test captures stdout from calling generated `Main` directly and writes a local log file. The verifier compares that log with the expected golden.

This gives two layers of runtime evidence:

1. The generated Go package behavior is correct when called under `go test`.
2. The generated native executable behavior is correct when launched as a process.

Both layers must pass for an example with a golden log.

---

## 16. Compiler Example Gate

The standard Python-driven executable smoke gate is:

```powershell
.\verify-compiler-examples.cmd
```

It delegates to:

```powershell
python tools\verify_compiler_examples.py
```

For each supported example, the gate performs:

1. `python -m freehold verify <entry>`.
2. `python -m freehold go-codegen-project <entry> --emit-executable`.
3. Copy extra example Go files into the generated project if present.
4. Run generated `build.cmd`.
5. Run runtime log Go test when an expected log is declared.
6. Run generated EXE and compare stdout when an expected log is declared.

The success footer is:

```text
[OK] Compiler example smoke passed.
```

This gate validates the Python compiler frontend plus Go codegen/build pipeline.

---

## 17. Stage-3 Compiler Example Gate

The post-bootstrap executable gate is:

```powershell
.\verify-stage3-compiler-examples.cmd
```

It delegates to:

```powershell
python tools\verify_stage3_compiler_on_examples.py
```

For each supported example, the gate performs:

1. Verify the entry file with the Python compiler frontend.
2. Generate a Go project with `go-codegen-project` for the resolved example graph.
3. Require `bin/stage3_compiler_core_v1.exe` to exist.
4. Invoke the native Stage-3 compiler with `--build-exe`.
5. Normalize Windows executable naming when necessary.
6. Run runtime log Go test when an expected log is declared.
7. Run generated EXE and compare stdout when an expected log is declared.

The success footer is:

```text
[OK] Stage 3 compiler example and fuzzy verification passed.
```

This gate is stronger than `verify-compiler-examples.cmd` because it proves the bootstrapped native compiler can build real example executables.

---

## 18. Stage-3 Compiler-Core Contract Gate

The compiler-core contract gate is:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

It delegates to:

```powershell
python tools\verify_stage3_compiler_core_contracts.py --manifest .\artifacts\stage3\compiler_core_v1\manifest.json --out .\artifacts\stage3\compiler_core_v1\report
```

For each manifest contract, it checks:

- project metadata such as file counts,
- generated Go source snippets,
- generated build files,
- generated extra files,
- required repository files,
- generated Go project build success,
- optional runtime golden execution.

When a runtime golden declares an executable, the gate copies successful release builds into:

```text
bin/
```

This is the gate that keeps `bin/stage3_compiler_core_v1.exe` aligned with compiler-core contracts.

---

## 19. Go Frontend Confidence Gate

The Go frontend is not the same component as the Python Go-codegen backend, but it is part of the post-bootstrap confidence story.

The Go frontend owns Go-native parsing, AST construction, semantic analysis, source-map export, IR comparison support, and frontend command binaries.

The basic Go frontend command is:

```powershell
Push-Location .\go-frontend
go test ./...
Pop-Location
```

The parser conformance chain also ends with Go frontend tests after regenerating and comparing parser artifacts:

```powershell
.\verify-parser-conformance.cmd
```

For this specification, the Go frontend gate answers:

```text
Does the Go-native frontend still compile and pass its own tests while generated executables are being validated through the backend and Stage-3 gates?
```

It does not by itself prove that a generated EXE is correct. EXE correctness belongs to the compiler-example and Stage-3 executable gates.

---

## 20. Supported Example Surface

The supported compiler examples cover a broad executable surface, including:

- minimal app entry points,
- records and functions,
- cross-module calls,
- result and abort handling,
- runtime builtins,
- Big number loops,
- complex contracts,
- record and result type composition,
- array payloads,
- control-flow runtime logging,
- mutation and record updates,
- async scope runtime,
- gRPC and channel demos,
- subtype ranges,
- flow contracts,
- websocket demos,
- HTTP REST/client/server/middleware/streaming/SSE demos,
- gRPC unary and server-stream demos,
- Go FFI demos,
- legacy standalone demos such as Chudnovsky and Gauss-Legendre examples.

Only examples with declared expected logs receive stdout golden comparison. Examples without expected logs still receive verify, codegen, build, and success/failure status checks.

---

## 21. Go Backend Sidecar Examples

Some examples require a Go backend process while the generated Freehold executable is tested.

The current sidecar examples include:

```text
29_websocket_go_backend_demo
35_http_client_go_backend_demo
```

For these examples, the verifier:

1. Builds the sidecar Go backend.
2. Starts it as a subprocess.
3. Waits for the configured port.
4. Runs the Go test or generated EXE.
5. Stops the backend process.

The sidecar process is part of the executable validation environment. A generated EXE that depends on a backend must be tested with that backend running.

---

## 22. Library-Only Modules

Not every valid Freehold module should produce an executable.

If the entry module has no `Main` routine:

- `go-codegen-project` can still produce a Go project,
- `go.mod` can still be generated,
- `build.cmd` can still run `go mod tidy` and `go test ./...`,
- no `cmd/<exe>/main.go` is emitted,
- no native EXE is built.

When `--emit-executable` was requested but no entry `Main` exists, the CLI prints:

```text
[INFO] Go executable not emitted: entry module has no Main() routine
```

For `build-exe`, missing `Main` is a hard error because the command explicitly promises an executable.

---

## 23. Manual Smoke Workflow

A manual executable smoke can be run with:

```powershell
Remove-Item -Recurse -Force .\.tmp\manual_exe -ErrorAction SilentlyContinue
python -m freehold go-codegen-project .\examples\compiler_v1\15_result_abort_array_runtime_builtins\App\Main.fh --output-dir .\.tmp\manual_exe --json .\.tmp\manual_exe\_project.json --emit-executable --executable-name freehold_runtime_demo
Push-Location .\.tmp\manual_exe
.\build.cmd
.\bin\freehold_runtime_demo.exe
Pop-Location
```

Expected executable:

```text
.tmp/manual_exe/bin/freehold_runtime_demo.exe
```

Expected stdout:

```text
summary = SKU001@north
json has sku = 8
max score = 4
total = 16
third = SKU-003
```

This manual path is useful for debugging a single generated project, but the repository confidence gates should be used for regression coverage.

---

## 24. Post-Bootstrap Stage-3 Manual Workflow

A manual Stage-3 executable build requires the native compiler artifact first:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Then a Stage-3 example build can be checked through:

```powershell
.\verify-stage3-compiler-examples.cmd
```

The underlying Stage-3 example flow invokes the native compiler as:

```text
bin/stage3_compiler_core_v1.exe --build-exe <entry.fh> <project_out> <exe_name>
```

The resulting EXE must then pass the same runtime checks used for generated project validation.

---

## 25. Release Artifact Policy

Successful Stage-3 compiler-core contract builds may copy release executables into:

```text
bin/
```

The most important current artifact is:

```text
bin/stage3_compiler_core_v1.exe
```

A binary in `bin/` is meaningful only if it was produced by a green Stage-3 contract gate. Manual binaries in `.tmp/` are inspection artifacts and should not be treated as release state.

---

## 26. Failure Modes

The executable pipeline must fail on:

- frontend verification failure,
- unsupported codegen result,
- missing entry file,
- missing `Main` for `build-exe`,
- failed `go mod tidy`,
- failed `go test ./...`,
- failed `go build`,
- missing generated executable,
- generated executable non-zero exit,
- stdout mismatch against expected runtime golden,
- missing Stage-3 compiler artifact for Stage-3 example gate,
- sidecar backend build/start failure for examples that require it.

The generated EXE must not be accepted based only on file existence.

---

## 27. What Each Gate Proves

```text
Go frontend go test ./...
  proves Go-native frontend packages compile and their unit tests pass.

verify-compiler-examples.cmd
  proves Python frontend + Go codegen can generate, build, and run supported example executables.

verify-stage3-compiler-core-v1.cmd
  proves Stage-3 compiler-core generated project contracts, build files, runtime goldens, and release artifact generation.

verify-stage3-compiler-examples.cmd
  proves the native bootstrapped compiler can build supported examples into executables and those executables match runtime goldens where defined.

verify-parser-conformance.cmd
  proves parser/diagnostic/artifact parity and includes Go frontend tests, but it is not the main EXE runtime gate.
```

---

## 28. Recommended Confidence Levels

For a small Go codegen or wrapper edit:

```powershell
.\verify-compiler-examples.cmd
```

For an edit that might affect the bootstrapped compiler artifact:

```powershell
.\verify-stage3-compiler-core-v1.cmd
.\verify-stage3-compiler-examples.cmd
```

For an edit that affects Go frontend parser or semantic behavior:

```powershell
Push-Location .\go-frontend
go test ./...
Pop-Location
.\verify-parser-conformance.cmd
```

For a release-confidence pass involving generated native executables:

```powershell
.\verify-compiler-examples.cmd
.\verify-stage3-compiler-core-v1.cmd
.\verify-stage3-compiler-examples.cmd
```

---

## 29. Current Acceptance Checklist

A post-bootstrap generated EXE is accepted only when all applicable checks are true:

- The Freehold entry source verifies.
- Project codegen succeeds with all generated files marked supported.
- The generated project contains `go.mod`.
- The generated project contains `build.cmd` and `build.sh`.
- Executable entries contain `cmd/<exe>/main.go`.
- `go mod tidy` succeeds.
- `go test ./...` succeeds.
- `go build -trimpath` succeeds.
- The expected EXE path exists.
- Running the EXE returns exit code 0.
- Captured stdout matches the expected golden when one is declared.
- Stage-3 paths use `bin/stage3_compiler_core_v1.exe` and fail if it is missing.
- Release binaries copied into `bin/` come from a green Stage-3 contract gate.

---

## 30. Practical Summary

The current Freehold post-bootstrap build story is executable-first.

The Go backend must not merely print Go source. It must generate a complete Go project, run Go dependency resolution, pass Go tests, build a native executable, and run that executable against expected behavior.

The Stage-3 path raises the bar further: the native bootstrapped compiler must itself be able to build example executables, and those executables must satisfy the same runtime-golden checks.

This is the current acceptance standard for `SPECIFICATION-COMPILE-BUILD-GO-TEST`: generated Go projects are useful only when their resulting EXEs are buildable, runnable, and behaviorally checked.
