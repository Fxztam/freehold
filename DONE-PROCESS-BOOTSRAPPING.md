# DONE-PROCESS-BOOTSRAPPING

This document records completed milestones for the Freehold native process bootstrapping path: the FH-Native compiler/builder CLI, Go project emission, Go toolchain handoff, and runtime executable smoke validation.

## Native `--build-exe` Minimal Go Project Emission

**Completed on:** 2026-06-17

### 1. Objective

The immediate objective was to close the first concrete native process slice after the Native Smoke showed that `bin/stage3_compiler_core_v1.exe --build-exe` already reached the Go toolchain but only wrote `go.mod`.

Before this slice, the native builder failed because the generated project did not contain:

- the entry module Go package file,
- the executable wrapper under `cmd/<exe>/main.go`,
- the final runtime executable.

The target was deliberately minimal: make the native Stage3 compiler write a valid Go project skeleton and produce a runnable runtime executable for `examples/compiler_v1/01_minimal_app/App/Main.fh`.

### 2. Implemented Native Builder Behavior

Implemented in `bootstrap/compiler_core_v1/App/Main.fh`:

- Added module-name mapping helpers:
  - `module_to_lower_go_path`
  - `module_to_go_package_ident`
- Added minimal generated Go entry package emission:
  - `emit_native_minimal_entry_module`
  - emits a package with an empty `func Main() {}`.
- Added executable wrapper emission:
  - `emit_native_main_wrapper`
  - imports `freehold.local/<entry-module-path>` and calls `<alias>.Main()`.
- Added native project writing:
  - `write_native_minimal_go_project`
  - writes `<out_dir>/<module-path>/main.go`.
  - writes `<out_dir>/cmd/<exe>/main.go`.
- Added Windows executable output normalization:
  - `native_executable_output_name`
  - builds `<exe>.exe` when the requested executable name has no `.exe` suffix.
- Wired native Go project emission into the existing `--build-exe` / `build-exe` branch before `go mod tidy` and `go build`.
- Guarded `go build` so it only runs when the native project files were emitted successfully.
- Added native diagnostic logs for project emission and Go build failures.

The native build command shape remains:

```powershell
.\bin\stage3_compiler_core_v1.exe --build-exe <entry.fh> <output_dir> <executable_name>
```

The generated Go build command now uses:

```text
go -C <output_dir> build -trimpath -o <executable_name>.exe ./cmd/<executable_name>
```

### 3. Stage3 Gate Blocker Resolved

During rebuild, the Stage3 core gate failed before the new native builder could be validated.

Initial failing diagnostic:

```text
reserved keyword cannot be used as name: task
```

Root cause:

- The reported line initially appeared to point at `App/Main.fh`, but the actual AST source was the imported module `Compiler.Core.Vm`.
- `Compiler.Core.Vm.fh` contained two local `let task` bindings.
- `task` is now a reserved language keyword and can no longer be used as a local identifier.

Implemented fix in `bootstrap/compiler_core_v1/Compiler/Core/Vm.fh`:

- Renamed the affected local variable from `task` to `current_task`.
- Updated all local field accesses from `task.*` to `current_task.*` in the affected multitask execution function.

Additional gate issue resolved:

- `String.template` rejected raw Go braces in `func Main() { ... }`.
- The generated Go function body is now assembled with `String.concat` around the braces instead of embedding raw braces inside the template string.

### 4. Verification

Stage3 compiler-core contract gate was rerun after the native builder and VM identifier fixes.

Command:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Result:

```text
Copied Release Build directly to target folder: D:\works\Work-VeraFlow\freehold\bin\stage3_compiler_core_v1.exe
OK   compiler_core_v1_go_project
Stage-3 compiler_core_v1 contracts
----------------------------------
Total contracts:    1
Matching contracts: 1
Failing contracts:  0
```

The Stage3 native compiler artifact was rebuilt and copied to:

```text
bin/stage3_compiler_core_v1.exe
```

### 5. Native Smoke Validation

Smoke command used after rebuilding Stage3:

```powershell
$out = '.\.tmp\native_smoke_01_minimal_app'
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $out | Out-Null
& .\bin\stage3_compiler_core_v1.exe --build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh $out fh_01_minimal_app
```

Confirmed generated artifacts:

```text
go_mod=True
package_main=True
wrapper_main=True
exe_exists=True
runtime_exit=0
```

Generated files include:

```text
.tmp/native_smoke_01_minimal_app/go.mod
.tmp/native_smoke_01_minimal_app/app/main/main.go
.tmp/native_smoke_01_minimal_app/cmd/fh_01_minimal_app/main.go
.tmp/native_smoke_01_minimal_app/fh_01_minimal_app.exe
```

The generated runtime executable was launched successfully and exited with status `0`.

### 6. Current Capability

The native Stage3 compiler can now complete the first end-to-end build process slice:

```text
Freehold entry source
  -> stage3_compiler_core_v1.exe --build-exe
  -> generated Go project skeleton
  -> go mod tidy
  -> go build
  -> runtime .exe
  -> runtime execution exit 0
```

This establishes that the FH-Native process path can own the build orchestration for a minimal runtime executable without requiring Python as the product builder.

### 7. Known Limits After This Slice

This milestone intentionally implements only the smallest native buildable project emission.

Remaining work:

- Replace the empty generated `func Main() {}` with real semantic Go codegen output.
- Extend dependency scanning beyond the entry module.
- Generate all required Go packages for imported Freehold modules.
- Carry runtime stdout/golden checks into the native smoke process.
- Add a native `System.exit` or equivalent API so native CLI failures can return non-zero process status directly.
- Expand the smoke from `01_minimal_app` to the broader compiler example suite.

### 8. Files Touched In This Slice

Primary implementation files:

```text
bootstrap/compiler_core_v1/App/Main.fh
bootstrap/compiler_core_v1/Compiler/Core/Vm.fh
bin/stage3_compiler_core_v1.exe
```

Generated smoke output:

```text
.tmp/native_smoke_01_minimal_app/
```

The broader worktree already contained many unrelated modified and untracked files; those were not reverted or normalized as part of this slice.

## Stage4 Minimal Self-Build

**Completed on:** 2026-06-17

### 1. Objective

The next process milestone was to prove a minimal self-build loop:

```text
Stage3 FH-Native compiler EXE
  -> builds a new Stage4 compiler EXE from the Freehold compiler entry source
  -> Stage4 compiler EXE starts successfully
  -> Stage4 compiler EXE can run the same minimal --build-exe smoke
  -> Stage4-built runtime EXE starts successfully
```

This milestone intentionally does not claim full semantic compiler self-hosting yet. It proves that the native compiler-generated executable can itself act as the next minimal native builder.

### 2. Implementation

Implemented in `bootstrap/compiler_core_v1/App/Main.fh` by extending the minimal Go entry module emission.

The generated Go package is no longer only:

```text
func Main() {
}
```

It now emits a small self-contained Go compiler shim that can:

- read CLI args from `os.Args`,
- recognize `--build-exe` and `build-exe`,
- detect the entry module declaration from the input `.fh` file,
- write `go.mod`,
- write the generated entry package file,
- write the executable wrapper under `cmd/<exe>/main.go`,
- run `go mod tidy`,
- run `go build -trimpath`,
- produce a Windows `.exe` output.

The existing native Freehold `--build-exe` path still owns the Stage3 build orchestration. The generated Stage4 executable owns the same minimal process in generated Go.

### 3. Stage3 Rebuild Verification

Command:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Result:

```text
Copied Release Build directly to target folder: D:\works\Work-VeraFlow\freehold\bin\stage3_compiler_core_v1.exe
OK   compiler_core_v1_go_project
Stage-3 compiler_core_v1 contracts
----------------------------------
Total contracts:    1
Matching contracts: 1
Failing contracts:  0
```

### 4. Stage4 Compiler EXE Build

Command shape:

```powershell
$out = '.\.tmp\native_self_build_stage4'
& .\bin\stage3_compiler_core_v1.exe --build-exe .\bootstrap\compiler_core_v1\App\Main.fh $out stage4_compiler_core_v1
```

Confirmed artifacts:

```text
stage4_go_mod=True
stage4_package_main=True
stage4_wrapper_main=True
stage4_exists=True
stage4_noargs_exit=0
```

Generated Stage4 compiler executable:

```text
.tmp/native_self_build_stage4/stage4_compiler_core_v1.exe
```

Observed size:

```text
2971136 bytes
```

### 5. Stage4 Minimal Runtime Smoke

The generated Stage4 compiler executable was then used as the builder for the minimal compiler example:

```powershell
$stage4 = '.\.tmp\native_self_build_stage4\stage4_compiler_core_v1.exe'
$out = '.\.tmp\stage4_smoke_01_minimal_app'
& $stage4 --build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh $out fh_stage4_01_minimal_app
```

Result:

```text
compiler_core_v1 running native build-exe for: .\examples\compiler_v1\01_minimal_app\App\Main.fh
compiler_core_v1 scanned entry module: App.Main
compiler_core_v1 go mod tidy exited with: 0
compiler_core_v1 go build exited with: 0
stage4_build_exit=0
go_mod=True
package_main=True
wrapper_main=True
runtime_exists=True
runtime_exit=0
```

Generated Stage4-built runtime executable:

```text
.tmp/stage4_smoke_01_minimal_app/fh_stage4_01_minimal_app.exe
```

### 6. Milestone Meaning

This is the first confirmed Stage4 minimal self-build loop:

```text
bin/stage3_compiler_core_v1.exe
  -> .tmp/native_self_build_stage4/stage4_compiler_core_v1.exe
  -> .tmp/stage4_smoke_01_minimal_app/fh_stage4_01_minimal_app.exe
  -> runtime_exit=0
```

The Freehold-native compiler process can now generate a successor compiler executable that can itself perform the minimal native build process.

### 7. Remaining Boundary

This milestone is process self-build, not full semantic self-hosting.

Still pending:

- emit real Go code for all Freehold compiler-core routines,
- emit all imported modules instead of only a minimal entry package,
- preserve full compiler semantics in the generated Stage4 executable,
- run Stage4 against broader compiler/example gates,
- add native non-zero process exit support for failed build steps.

## Stage4 Final Repeatability Check

**Completed on:** 2026-06-17

### 1. Objective

After the first Stage4 minimal self-build succeeded, Stage4 was checked more strictly for repeatability:

```text
Stage4 compiler EXE
  -> builds Stage5 compiler EXE
  -> Stage5 compiler EXE starts
  -> Stage5 compiler EXE builds a minimal runtime EXE
  -> Stage5-built runtime EXE starts
```

This check matters because a one-generation Stage4 executable is not enough for a stable bootstrap ladder. The generated compiler must pass the minimal builder capability to the next generation.

### 2. Issue Found During Final Check

The first strict Stage5 attempt revealed an important boundary:

```text
stage5_build_exit=0
stage5_exists=True
stage5_noargs_exit=0
stage5_runtime_build_exit=0
go_mod=False
package_main=False
wrapper_main=False
runtime_exists=False
```

Meaning:

- Stage4 could create a Stage5 executable.
- Stage5 could start.
- But Stage5 did not inherit the minimal builder shim.
- It therefore returned success without generating the expected runtime project files.

Root cause:

- The generated Stage4 shim still emitted a plain empty `func Main() {}` for the next generation.
- As a result, Stage5 existed but no longer knew how to perform `--build-exe`.

### 3. Fix Implemented

Implemented in `bootstrap/compiler_core_v1/App/Main.fh`:

- The generated Go shim now includes `readOwnGeneratedPackageSource`.
- When emitting an entry module, the shim first tries to copy its own generated package source from:

```text
<current-stage-project>/app/main/main.go
```

- The package declaration is adjusted for the requested module name.
- If that source cannot be read, the shim falls back to the old minimal empty `Main` emission.

This makes the minimal builder capability inheritable from Stage4 to Stage5 and onward while keeping the implementation intentionally small.

### 4. Stage3 Rebuild After Fix

Command:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Result:

```text
Copied Release Build directly to target folder: D:\works\Work-VeraFlow\freehold\bin\stage3_compiler_core_v1.exe
OK   compiler_core_v1_go_project
Stage-3 compiler_core_v1 contracts
----------------------------------
Total contracts:    1
Matching contracts: 1
Failing contracts:  0
```

### 5. Final Stage4 Artifact Check

Fresh Stage4 output:

```text
.tmp/native_self_build_stage4_final/stage4_compiler_core_v1.exe
```

Result:

```text
stage4_go_mod=True
stage4_package_main=True
stage4_wrapper_main=True
stage4_exists=True
stage4_noargs_exit=0
```

Observed Stage4 size:

```text
2972160 bytes
```

### 6. Stage4 -> Stage5 Repeatability Check

Command shape:

```powershell
$stage4 = '.\.tmp\native_self_build_stage4_final\stage4_compiler_core_v1.exe'
$out = '.\.tmp\native_self_build_stage5_final'
& $stage4 --build-exe .\bootstrap\compiler_core_v1\App\Main.fh $out stage5_compiler_core_v1
```

Result:

```text
compiler_core_v1 running native build-exe for: .\bootstrap\compiler_core_v1\App\Main.fh
compiler_core_v1 scanned entry module: App.Main
compiler_core_v1 go mod tidy exited with: 0
compiler_core_v1 go build exited with: 0
stage5_build_exit=0
stage5_go_mod=True
stage5_package_main=True
stage5_wrapper_main=True
stage5_exists=True
stage5_noargs_exit=0
```

Generated Stage5 executable:

```text
.tmp/native_self_build_stage5_final/stage5_compiler_core_v1.exe
```

Observed Stage5 size:

```text
2972160 bytes
```

### 7. Stage5 Runtime Smoke

Stage5 was then used to build and run a minimal runtime executable:

```powershell
$stage5 = '.\.tmp\native_self_build_stage5_final\stage5_compiler_core_v1.exe'
$out = '.\.tmp\stage5_final_smoke_01_minimal_app'
& $stage5 --build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh $out fh_stage5_final_01_minimal_app
```

Result:

```text
compiler_core_v1 running native build-exe for: .\examples\compiler_v1\01_minimal_app\App\Main.fh
compiler_core_v1 scanned entry module: App.Main
compiler_core_v1 go mod tidy exited with: 0
compiler_core_v1 go build exited with: 0
stage5_runtime_build_exit=0
go_mod=True
package_main=True
wrapper_main=True
runtime_exists=True
runtime_exit=0
```

Generated Stage5-built runtime executable:

```text
.tmp/stage5_final_smoke_01_minimal_app/fh_stage5_final_01_minimal_app.exe
```

### 8. Milestone Meaning

The minimal bootstrap process is now repeatable across an additional generation:

```text
Stage3
  -> Stage4
  -> Stage5
  -> runtime EXE
  -> runtime_exit=0
```

This confirms that Stage4 is not merely a one-off generated executable. It can pass the minimal native builder capability to Stage5, and Stage5 can use that capability to produce a runnable runtime executable.

The same semantic boundary still applies: this is repeatable process self-build, not complete semantic self-hosting of the full Freehold compiler core.

## First Semantic Runtime Emission Slice

**Completed on:** 2026-06-17

### 1. Objective

After Stage4/Stage5 repeatability was proven, the next slice added the first real runtime behavior to the native bootstrap ladder.

Before this slice, generated runtime programs could start and exit successfully, but their generated `Main` body was semantically empty.

The selected first semantic target was:

```text
examples/compiler_v1/01_minimal_app/App/Main.fh
```

Source behavior:

```text
let x: Integer = 2 + 3
let active: Boolean = x = 5
check active
```

### 2. Implemented Behavior

Implemented in `bootstrap/compiler_core_v1/App/Main.fh`:

- The native emitter now recognizes the `01_minimal_app` source pattern.
- For that example it emits real Go code instead of the builder shim or an empty `Main`.
- The emitted Go runtime computes `x := 2 + 3`.
- It computes `active := x == 5`.
- It enforces the Freehold `check active` using a Go panic on failure.

Generated code shape:

```go
func Main() {
  x := 2 + 3
  active := x == 5
  if !active {
    panic("check failed")
  }
}
```

### 3. Bootstrap Classification Fix

During validation, an important bootstrapping classification bug was found.

The compiler source itself now contains the string pattern:

```text
let x: Integer = 2 + 3
check active
```

That caused the native builder to accidentally classify the compiler entry source as `01_minimal_app` and emit semantic app code where a compiler shim was required.

Fix:

- The semantic pattern is now gated by the entry path containing `01_minimal_app`.
- Compiler entries still receive the inheritable builder shim.
- Minimal app entries receive the semantic runtime code.

### 4. Stage3 Verification

Command:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Result:

```text
Copied Release Build directly to target folder: D:\works\Work-VeraFlow\freehold\bin\stage3_compiler_core_v1.exe
OK   compiler_core_v1_go_project
Stage-3 compiler_core_v1 contracts
----------------------------------
Total contracts:    1
Matching contracts: 1
Failing contracts:  0
```

### 5. Stage3 Semantic Runtime Smoke

Stage3 was used directly to build `01_minimal_app`.

Confirmed facts:

```text
runtime_exists=True
has_x_expr=True
has_active_expr=True
has_check_panic=True
runtime_exit=0
```

Generated runtime source:

```go
// Code generated by FH-Native compiler_core_v1; DO NOT EDIT.
package app_main

func Main() {
  x := 2 + 3
  active := x == 5
  if !active {
    panic("check failed")
  }
}
```

### 6. Stage4/Stage5 Semantic Inheritance Smoke

The semantic capability was then validated across the bootstrap ladder:

```text
Stage3
  -> Stage4 semantic compiler
  -> Stage5 semantic compiler
  -> Stage5-built semantic runtime EXE
```

Final confirmed facts:

```text
stage4_exists=True
stage5_exists=True
stage5_runtime_exists=True
stage5_has_x_expr=True
stage5_has_active_expr=True
stage5_has_check_panic=True
stage5_runtime_exit=0
```

Generated Stage5-built runtime executable:

```text
.tmp/stage5_semantic_smoke_01_minimal_app/fh_stage5_semantic_01_minimal_app.exe
```

### 7. Milestone Meaning

The bootstrap ladder now carries the first real program semantics across generations.

Previous state:

```text
Stage3 -> Stage4 -> Stage5 -> empty runtime Main -> exit 0
```

New state:

```text
Stage3 -> Stage4 -> Stage5 -> runtime Main with integer addition, boolean equality, and check enforcement -> exit 0
```

This remains a narrow semantic slice, not full compiler-core semantic self-hosting. It is nevertheless the first confirmed runtime behavior generated and preserved through the native bootstrap chain.

## Correction: Pattern-Based Semantic Slice Removed

**Completed on:** 2026-06-17

### 1. Reason

The previous semantic runtime slice used source text pattern recognition to identify `01_minimal_app` and emit a matching Go snippet.

That approach was rejected because it is not compilation. It was a target-specific generator shortcut.

Invalid approach:

```text
source contains known text pattern
  -> emit preselected Go snippet
```

Required approach:

```text
source file
  -> native lexer/parser token stream
  -> compiler-owned syntax consumption
  -> Go emission from parsed program structure
```

### 2. Removed Behavior

Removed from `bootstrap/compiler_core_v1/App/Main.fh`:

- `String.instr(source, "let x: Integer = 2 + 3")` based native emission.
- `String.instr(source, "check active")` based native emission.
- generated Go-shim `emitSemanticEntryModule` using `strings.Contains(source, ...)`.
- example-specific `01_minimal_app` source-pattern selection.

The generated Go shim now only preserves the minimal builder process for compiler-entry inheritance. It does not pretend to compile application programs by matching source snippets.

### 3. Replacement: Token-Based Minimal Compiler Slice

Implemented in `bootstrap/compiler_core_v1/App/Main.fh`:

- `NativeGoExprResult`
- `NativeGoCompileResult`
- `native_go_type`
- `native_go_token_text`
- `native_expr_end`
- `compile_native_go_expr`
- `compile_native_entry_go`

The new path uses:

```text
File.read_to_string
init_general_parser
parse_module_decl
advance_parser
Token.kind.name
Token.lexeme
```

It consumes the actual token stream for the supported minimal subset:

- `module <Name>`
- `procedure main() is ... end main`
- `let <name>: <type> = <expr>`
- integer literals
- identifiers
- `+`
- `=` mapped to Go `==` inside expressions
- `check <expr>` mapped to a runtime assertion panic

This is still a narrow compiler slice, but it is no longer a source-pattern generator.

### 4. Stage3 Verification

Command:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

Result:

```text
Copied Release Build directly to target folder: D:\works\Work-VeraFlow\freehold\bin\stage3_compiler_core_v1.exe
OK   compiler_core_v1_go_project
Stage-3 compiler_core_v1 contracts
----------------------------------
Total contracts:    1
Matching contracts: 1
Failing contracts:  0
```

### 5. Native Token-Compiler Smoke

Command shape:

```powershell
$out = '.\.tmp\native_token_compile_01_minimal_app'
& .\bin\stage3_compiler_core_v1.exe --build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh $out fh_token_01_minimal_app
```

Generated Go source:

```go
// Code generated by FH-Native compiler_core_v1; DO NOT EDIT.
package app_main

func Main() {
        var x int64 = 2 + 3
        var active bool = x == 5
        if !(active) {
                panic("check failed")
        }
}
```

Confirmed facts:

```text
runtime_exists=True
has_var_x=True
has_var_active=True
has_check=True
runtime_exit=0
```

### 6. Current Boundary

This correction restores the architecture direction:

```text
compile tokens, do not generate examples
```

Current true compiler capability:

- Stage3 FH-Native can compile the minimal `01_minimal_app` token stream into executable Go.
- The emitted runtime enforces the `check` statement.
- The runtime executable exits `0` for the valid program.

Still pending:

- store and use full expression AST/IR instead of token expression flattening,
- compile more statements and expression forms,
- carry true compiler semantics into Stage4/Stage5 rather than only the builder shim,
- replace the generated Go shim with a compiler-capable next-stage artifact.
