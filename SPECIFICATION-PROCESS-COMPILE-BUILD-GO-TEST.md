# Freehold Specification: Native Compile, Build, Go, and EXE Test Process

**Status:** Native-process specification for using the Freehold-native compiler and builder CLI to produce Go-backed runtime executables

**Scope:** FH-Native compiler frontend, native builder command, Go backend emission, Go runtime project build, native EXE generation, EXE execution, and runtime behavior validation

**Non-normative:** Python may still exist as a developer harness or legacy validation tool elsewhere in the repository. It is not part of the process specified here.

---

## 1. Purpose

This document specifies the process the Freehold-native compiler and builder must provide after bootstrapping.

The intended production path is:

```text
Freehold source
  -> FH-Native compiler frontend
  -> FH-Native resolver and verifier
  -> FH-Native Go backend
  -> generated Go runtime project
  -> native builder invokes Go toolchain
  -> runtime EXE
  -> EXE process execution
  -> behavior check
```

The important point is ownership. The compiler and builder entrypoint is the native Freehold binary, not a Python orchestration command.

The canonical native CLI artifact is:

```text
bin/stage3_compiler_core_v1.exe
```

The canonical build command shape is:

```powershell
.\bin\stage3_compiler_core_v1.exe --build-exe <entry.fh> <output_dir> <executable_name>
```

A successful native process produces an executable that can be launched directly by the host operating system.

---

## 2. Process Boundary

This specification describes the native compiler and builder path only.

Normative components:

```text
bootstrap/compiler_core_v1/App/Main.fh
bootstrap/compiler_core_v1/Compiler/Core/Lexer.fh
bootstrap/compiler_core_v1/Compiler/Core/Parser.fh
bootstrap/compiler_core_v1/Compiler/Core/Resolve.fh
bootstrap/compiler_core_v1/Compiler/Core/Verifier.fh
bootstrap/compiler_core_v1/Compiler/Core/Codegen.fh
bootstrap/compiler_core_v1/Compiler/Core/Names.fh
bootstrap/compiler_core_v1/File.fh
bootstrap/compiler_core_v1/System.fh
bin/stage3_compiler_core_v1.exe
```

Host toolchain dependency:

```text
go
```

The Go toolchain is allowed because the requested backend target is Go. The native Freehold compiler owns the frontend and builder orchestration; Go owns final package compilation and executable linking.

Out of process for this document:

- Python CLI commands.
- Python code generation as the primary path.
- Python verifier ownership as the primary path.
- Python-generated project contracts as the product process.
- Parser conformance harnesses except as external confidence gates.

---

## 3. Native CLI Contract

The native compiler binary must expose a builder command:

```text
--build-exe <entry.fh> <output_dir> [executable_name]
```

The equivalent non-dashed command is also accepted by the current native entrypoint:

```text
build-exe <entry.fh> <output_dir> [executable_name]
```

Required behavior:

1. Read the entry Freehold source file.
2. Determine the entry module name.
3. Discover the dependency graph.
4. Generate or complete the Go runtime project in the output directory.
5. Write `go.mod`.
6. Emit package files and executable wrapper when the entry has `Main`.
7. Invoke Go dependency resolution.
8. Invoke Go build.
9. Produce the runtime executable.
10. Report non-zero failures through the native process exit path or diagnostic output.

Current native implementation evidence is in `bootstrap/compiler_core_v1/App/Main.fh`, where the CLI recognizes:

```text
--build-exe
build-exe
```

and logs:

```text
compiler_core_v1 running native build-exe for: <entry>
compiler_core_v1 scanned entry module: <module>
compiler_core_v1 found <n> dependencies
compiler_core_v1 executing: go -C <dir> mod tidy
compiler_core_v1 executing: go -C <dir> build -trimpath -o <exe> ./cmd/<exe>
```

---

## 4. Native Frontend Responsibilities

The FH-Native compiler frontend is responsible for language understanding.

It must own:

- lexical analysis,
- parsing,
- AST construction,
- module-name extraction,
- import and dependency scanning,
- name resolution,
- type checking,
- verification where supported by the native compiler core,
- diagnostics,
- lowering into the backend representation.

The native frontend source lives under:

```text
bootstrap/compiler_core_v1/Compiler/Core
```

Key modules:

```text
Lexer.fh
Parser.fh
ParseResult.fh
Ast.fh
Resolve.fh
Flow.fh
Verifier.fh
Diagnostics.fh
Transform.fh
Lowering.fh
Ir.fh
```

The native CLI must not delegate these responsibilities to a Python command in the process defined here.

---

## 5. Native Go Backend Responsibilities

The FH-Native Go backend is responsible for producing Go source and build structure from the resolved Freehold program.

The native backend source is:

```text
bootstrap/compiler_core_v1/Compiler/Core/Codegen.fh
```

It owns Go-facing transformations such as:

- module name to package name conversion,
- Freehold type to Go type conversion,
- Go module header emission,
- record struct emission,
- expression emission,
- statement emission,
- runtime helper emission where implemented,
- stable generated Go text.

Examples of required mappings:

```text
Integer -> int64
String  -> string
Boolean -> bool
Double  -> float64
```

The backend must produce Go code compatible with the generated project layout and the Go toolchain.

---

## 6. Generated Runtime Project

The native compiler and builder produce or complete a Go runtime project under the requested output directory.

Expected project shape for an executable entry:

```text
<output_dir>/
  go.mod
  cmd/<exe_name>/main.go
  <generated package directories>/...
  <exe_name>.exe              # current native builder output on Windows after normalization
```

A builder implementation may also choose the classic generated-project shape:

```text
<output_dir>/
  go.mod
  build.cmd
  build.sh
  cmd/<exe_name>/main.go
  bin/<exe_name>.exe
  <generated package directories>/...
```

Both are acceptable only if the executable path is explicit and the verifier knows where to find it.

The current native Stage-3 builder command uses this Go build shape:

```powershell
go -C <output_dir> build -trimpath -o <exe_name> ./cmd/<exe_name>
```

On Windows, the verifier may normalize the raw output name to:

```text
<exe_name>.exe
```

---

## 7. `go.mod` Contract

The native builder must write a Go module file before invoking the Go toolchain.

Current minimal module content:

```text
module freehold.local

go 1.22
```

The builder must extend this content when generated code requires external runtime modules.

Examples:

- gRPC services require `google.golang.org/grpc`.
- FFI modules may require `require` and `replace` entries.
- Generated runtime glue may require local import paths.

The native builder must run dependency resolution after writing `go.mod`:

```powershell
go -C <output_dir> mod tidy
```

Failure of `go mod tidy` is a native build failure.

---

## 8. Executable Wrapper Contract

Executable programs require a Go `main` wrapper:

```text
cmd/<exe_name>/main.go
```

The wrapper must call the generated Freehold entry routine.

Required synchronous shape:

```go
package main

import (
    app_main "freehold.local/app/main"
)

func main() {
    app_main.Main()
}
```

If the generated `Main` takes a context, the wrapper must pass `context.Background()`.

If the generated `Main` returns `error`, the wrapper must convert non-nil errors into visible process failure, for example by panicking or exiting non-zero.

If generated runtime registration is required, the wrapper must include side-effect imports, especially for generated gRPC binding or runtime glue packages.

---

## 9. Native Builder Go Commands

The native builder invokes the host Go toolchain through `System.run_command`.

Required command sequence:

```powershell
go -C <output_dir> mod tidy
go -C <output_dir> build -trimpath -o <exe_name> ./cmd/<exe_name>
```

The current native implementation logs both commands and their exit codes.

The builder must treat non-zero exit codes as failures.

A future hardened builder should also run package tests before build when generated tests exist:

```powershell
go -C <output_dir> test ./...
```

For this native process specification, `go test ./...` is a required confidence step whenever generated tests or copied backend fixtures are part of the runtime project. It may be implemented either directly in the native builder or as a native builder subcommand.

---

## 10. Runtime EXE Contract

The output of the native builder is not the Go project. The output is the runtime executable.

On Windows, accepted runtime executable names are:

```text
<output_dir>/<exe_name>.exe
<output_dir>/bin/<exe_name>.exe
```

The native process must make the final executable path discoverable by log output or manifest output.

The runtime executable must satisfy:

- file exists,
- process starts,
- process exits with code 0 for positive examples,
- stdout is stable after CRLF/LF normalization,
- expected stdout matches the declared runtime golden when present.

An executable that exists but cannot be run is not accepted.

---

## 11. Runtime Golden Contract

Runtime goldens are behavioral specifications for generated executables.

A runtime golden check compares:

```text
actual stdout from generated EXE
```

against:

```text
expected stdout file
```

with normalized line endings.

Accepted comparison rule:

```text
normalize(actual_stdout) == normalize(expected_stdout)
```

Failure classes:

- missing executable,
- executable exits non-zero,
- stdout mismatch,
- expected log missing,
- backend sidecar missing,
- unstable output ordering.

The native process should eventually own this check directly. Until that is implemented inside the native CLI, an external harness may execute the native EXE for validation, but the compilation and build process itself remains native.

---

## 12. Native Example Gate

The native example gate validates the compiler and builder as a product.

Canonical command:

```powershell
.\verify-stage3-compiler-examples.cmd
```

The important product behavior inside that gate is the native command:

```powershell
.\bin\stage3_compiler_core_v1.exe --build-exe <entry.fh> <project_out> <exe_name>
```

The native compiler must perform the build, not the Python CLI.

The gate is accepted only if generated executables behave correctly.

Expected success marker:

```text
[OK] Stage 3 compiler example and fuzzy verification passed.
```

This script may still serve as an outer harness, but the specified compiler/builder responsibility belongs to `stage3_compiler_core_v1.exe`.

---

## 13. Compiler Core Release Gate

Before using the native compiler as the build frontend, the Stage-3 compiler core must be current.

Canonical gate:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

This gate proves that the native compiler-core release artifact is aligned with its contracts and can be placed under:

```text
bin/
```

The key release artifact is:

```text
bin/stage3_compiler_core_v1.exe
```

A native EXE build based on a stale or missing Stage-3 compiler binary is not valid.

---

## 14. Native Build Workflow

Minimal native build workflow:

```powershell
.\verify-stage3-compiler-core-v1.cmd
.\bin\stage3_compiler_core_v1.exe --build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh .\.tmp\native_minimal fh_01_minimal_app
.\.tmp\native_minimal\fh_01_minimal_app.exe
```

If the native builder emits to `bin/`, use:

```powershell
.\.tmp\native_minimal\bin\fh_01_minimal_app.exe
```

Expected native build log shape:

```text
compiler_core_v1 running native build-exe for: <entry>
compiler_core_v1 scanned entry module: App.Main
compiler_core_v1 found <n> dependencies
compiler_core_v1 wrote go.mod to <output_dir>/go.mod
compiler_core_v1 executing: go -C <output_dir> mod tidy
compiler_core_v1 go mod tidy exited with: 0
compiler_core_v1 executing: go -C <output_dir> build -trimpath -o <exe> ./cmd/<exe>
compiler_core_v1 go build exited with: 0
```

---

## 15. Native CLI Usage Errors

The native CLI must report usage when required arguments are missing.

Current usage text:

```text
compiler_core_v1 build-exe usage: --build-exe <entry.fh> <output_dir> [executable_name]
```

Required missing-input failures:

- no command,
- missing entry file,
- missing output directory,
- invalid output directory,
- missing executable name when an executable build is required,
- unreadable entry file,
- malformed module declaration,
- missing `Main` for executable target.

Diagnostics should identify the failing phase.

---

## 16. Native Dependency Scan

The native builder scans the entry module and dependency graph before build.

Current native log shape:

```text
compiler_core_v1 scanned entry module: <module>
compiler_core_v1 found <n> dependencies
  dependency: <module>
```

The scan is responsible for discovering imports that must become generated Go packages.

Acceptance criteria:

- entry module name is not hard-coded when the source declares a module,
- import graph is stable,
- duplicate dependencies are not emitted twice,
- missing dependencies produce diagnostics,
- generated package paths match module names.

---

## 17. Native File And System APIs

The native compiler relies on Freehold runtime APIs for host integration.

Required APIs:

```text
System.args
System.run_command
File.read_to_string
File.write_string
Std.IO.log
Std.IO.logf
```

These APIs are part of the native process boundary. They allow the Freehold compiler binary to:

- read entry sources,
- write generated project files,
- create `go.mod`,
- invoke Go commands,
- emit progress logs,
- report failures.

A native build process that requires Python file helpers is outside this specification.

---

## 18. Go Runtime Surface

Generated runtime executables may use Go-backed runtime modules.

The native backend must preserve supported runtime behavior for:

- integer and floating arithmetic,
- strings and templates,
- records and JSON tags,
- result and abort propagation,
- arrays,
- runtime logging,
- async/context-aware entrypoints where supported,
- gRPC/websocket/HTTP support where included by the generated project,
- FFI support where declared and mapped.

Runtime support may be generated directly, imported as Go packages, or emitted as glue files, but the native compiler must produce a buildable Go project.

---

## 19. Sidecar Runtime Services

Some generated EXE tests require a companion Go service.

Examples include:

```text
29_websocket_go_backend_demo
35_http_client_go_backend_demo
```

The native EXE itself is still the artifact under test. Sidecar services are test environment dependencies.

A native runtime test for these examples must:

1. Build or locate the sidecar service.
2. Start the sidecar process.
3. Wait for readiness.
4. Run the generated Freehold EXE.
5. Compare output.
6. Stop the sidecar process.

Future native test support may own this orchestration directly. Until then, the sidecar harness is external, but the Freehold program build remains native.

---

## 20. Failure Classes

The native process must distinguish these failures:

**Frontend failure:** Lexer, parser, resolver, verifier, or dependency scan rejects the source.

**Codegen failure:** Native Go backend cannot emit required package or wrapper code.

**Project write failure:** Output directory, `go.mod`, package files, or wrapper files cannot be written.

**Dependency failure:** `go -C <dir> mod tidy` exits non-zero.

**Package test failure:** `go -C <dir> test ./...` exits non-zero when test step is enabled.

**Build failure:** `go -C <dir> build -trimpath ...` exits non-zero.

**Missing EXE:** Build appears to complete but no executable exists at the declared path.

**Runtime failure:** Generated EXE exits non-zero.

**Golden mismatch:** Generated EXE stdout differs from expected behavior.

**Stale compiler failure:** `bin/stage3_compiler_core_v1.exe` is missing or not produced by a green Stage-3 compiler-core gate.

---

## 21. Acceptance Matrix

| Layer | Native Owner | Acceptance |
| --- | --- | --- |
| CLI entry | `App/Main.fh` | `--build-exe` accepts entry, output, executable name |
| Frontend | `Lexer.fh`, `Parser.fh`, `Resolve.fh`, `Verifier.fh` | source and dependencies are valid |
| Backend | `Codegen.fh`, `Names.fh` | Go package files and wrapper are generated |
| File output | `File.fh` | project files are written under output directory |
| System build | `System.fh` | Go commands are invoked and exit 0 |
| Dependency resolution | Go toolchain | `go mod tidy` succeeds |
| Package confidence | Go toolchain | `go test ./...` succeeds when enabled |
| Link/build | Go toolchain | `go build -trimpath` succeeds |
| Runtime artifact | native builder | EXE exists at declared path |
| Runtime behavior | generated EXE | process exit and stdout match expectations |

---

## 22. Non-Python Rule

For this specification, the following are not accepted as the primary process:

```powershell
python -m freehold verify <entry>
python -m freehold go-codegen-project <entry>
python -m freehold build-exe <entry>
```

Those commands may remain useful for development comparison, bootstrap history, or outer harness checks. They are not the process specified here.

The specified primary process starts with:

```powershell
.\bin\stage3_compiler_core_v1.exe --build-exe <entry.fh> <output_dir> <executable_name>
```

and ends with a generated runtime EXE.

---

## 23. Hardening Roadmap

The native process should continue hardening toward full standalone ownership.

Required hardening items:

- native build command exits non-zero when `go mod tidy` fails,
- native build command exits non-zero when `go build` fails,
- native command writes all generated package files itself,
- native command writes executable wrapper itself,
- native command supports `go test ./...` before build,
- native command writes a small build manifest with executable path and statuses,
- native command can run generated EXE and compare stdout to a golden file,
- native diagnostics include phase-specific error codes,
- native builder handles Windows `.exe` naming directly,
- native builder handles gRPC and FFI dependencies in `go.mod`.

These items keep the target clear: the native Freehold compiler and builder should be sufficient to produce and validate Go-backed runtime executables.

---

## 24. Practical Checklist

A native compile-build-go-test run is accepted when:

- `bin/stage3_compiler_core_v1.exe` exists from a green compiler-core gate.
- The native CLI accepts `--build-exe`.
- The native frontend scans the entry module.
- Dependencies are discovered and logged.
- `go.mod` is written by the native process.
- Generated Go package files are present.
- `cmd/<exe_name>/main.go` is present for executable entries.
- `go -C <output_dir> mod tidy` exits 0.
- `go -C <output_dir> build -trimpath ...` exits 0.
- The runtime EXE exists.
- The runtime EXE starts and exits successfully.
- stdout matches the expected golden when a golden is declared.

---

## 25. Summary

The process specified here is the native Freehold compiler and builder path.

The normative frontend is FH-Native. The backend target is Go. The final artifact is a runtime EXE. The proof is not that a Python command can generate Go, but that the native compiler binary can drive the build of Go-backed Freehold programs and produce executables that run correctly.

Canonical process:

```text
stage3_compiler_core_v1.exe --build-exe
  -> FH-Native frontend
  -> FH-Native Go backend
  -> Go toolchain build
  -> runtime EXE
  -> runtime behavior check
```

That is the acceptance standard for `SPECIFICATION-PROCESS-COMPILE-BUILD-GO-TEST.md`.
