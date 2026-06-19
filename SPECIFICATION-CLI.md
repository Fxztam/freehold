# Freehold Specification: Command-Line Interface and Platform Portability

**Status:** Approved Specification  
**Audience:** Compiler Developers, Test Integrators, CI/CD Maintainers  
**Date:** 2026-06-19

This document outlines the command-line interface (CLI) architecture, environment validations, interactive safeguards, workspace isolation, cleanup execution policies, cross-platform conformance script structures, and a complete step-by-step TODO guide for building native executables.

---

## 1. Environment Safeguards & Pre-Flight Validations

Before generating Go source repositories or initiating build compilation subprocesses via advanced CLI actions, the driver must verify that the underlying execution platform satisfies the necessary toolchain dependencies:

- **Go Compiler Verification:** The CLI checks if `go` is on the system PATH using a safe lookup. It executes `go version` to log compiler characteristics and verify readiness. If missing, the build terminates with a clear, user-friendly error.
- **SMT Solver Verification:** The CLI checks if the Z3 Theorem Prover (`z3` or `z3.exe`) is available on the system PATH, or fallback searches for the native Python `z3-solver` API library package. It executes `z3 --version` or confirms active solver library availability before and during verification sequences.

---

## 2. Workspace Cleanups & Interruption Reversion

To prevent half-completed or failed builds from leaving stale fragments, intermediate outputs, or broken packaging dependencies in the workspace, the compiler implements a strict transactional cleanup engine:

- **Resource Tracking:** All generated Go files and folders created during project generation are tracked recursively.
- **Error and Abort Rewinds:** If of Go dependencies (`go mod tidy`) or compilation (`go build`) fail, or if the process is terminated via `KeyboardInterrupt` / SIGINT, the workspace execution automatically intercepts the exception:
  1. Unlinks and deletes each written file.
  2. Recursive-cleanup has been upgraded to a bottom-up automatic mechanism which cleanly unlinks all generated subfolders (e.g. `cmd`, `app`, `freehold_go_runtime`), leaving only the final product binary in the target directory upon successful packaging.
  3. Formally reports a clean workspace termination to standard error.

These controls reside in [freehold/freehold/cli/main.py](freehold/freehold/cli/main.py#L186).

---

## 3. Integration Runner Filtering Mechanics

To increase development velocity during local debugging, the main integration test-runner incorporates path-based filtering:

- Uses `--filter` / `-f` with any regex pattern or keyword.
- Compares the case-insensitive pattern against the file path relative to the test directory.
- Skips other files dynamically, ensuring immediate feedback loops without run-time overhead.

These controls reside in [freehold/run_compiler_tests.py](freehold/run_compiler_tests.py).

---

## 4. Platform Portability & Standardized Conformance Scripts

To support cross-platform Continuous Integration (CI) and local testing workflows under Windows, Linux, and macOS, the system provides standard shell counterparts matching the legacy command batch scripts:

- **Python Interpreter Auto-Detection:** The shell wrapper detects the active Python virtual environment (checking in order `freehold/.venv/bin/python`, `freehold/venv/bin/python`, standard `python3`, or standard `python`) to maintain isolation without user environment variables.
- **Temporary Folder Management:** Temporary directories are resolved natively using standard utilities (such as `mktemp`) across platforms, ensuring clean state separation.

---

## 5. Rich Color-Coded Context Diagnostics for Verification Failures

To ensure maximum developer readability, the CLI captures SMT solver (Z3/CVC5) contract violations and expands the default printed traceback block into a rich, colored terminal output:

- **Location Extraction:** Resolves the exact line and 1-based column of the violated contract.
- **Colored Source Blocks:** Integrates a context box showing 2 lines before and 1 line after the failure.
- **Exact Caret Pointing:** Generates an inline spacing pointer tracking spaces and tabs precisely, with a custom red caret under the exact column where the verification failed.
- **Color Codes (ANSI Escapes):** Uses high-visibility bold headings, muted grey context lines, red highlighted error targets, and cyan boundaries to provide clear warning output directly in the console.

These controls reside in [freehold/freehold/cli/main.py](freehold/freehold/cli/main.py#L396).

---

## 6. Step-by-Step TODO Guide: Compile a Freehold Module Graph Into a Native EXE

This section provides a rigorous checklist and step-by-step workflow to safely compile a contractual Freehold program into a standalone native binary (`.exe` on Windows, native binary on Linux/macOS) using the `build-exe` CLI action.

### Prerequisite Self-Check

Before execution, ensure the system state meets these prerequisites:

- [ ] **Go Toolchain:** Installed and queryable on PATH (Version `1.18` or greater recommended).
- [ ] **Z3 Theorem Prover:** Placed on system PATH (Version `4.8` or greater).
- [ ] **Python Interpreter:** Active virtual environment (`.venv` or `venv`) configured with lark parser dependencies.

---

### Step 1: Write a Valid Freehold Program with a `Main()` Entrance Point

A module graph is only compiler-targetable if the entry file declares a formal `Main()` procedure.

Create a source file, e.g. `App.fh`:

```freehold
module App

-- Simple FFI dependency
import Std.IO

procedure Main()
is
    call Std.IO.logf("Freehold program initialized successfully.\n", [])
end Main

end App
```

---

### Step 2: Validate Semantic and Verification Validity

Always verify the program contract statically before starting native compilation:

```bash
python -m freehold verify App.fh --prover z3
```

*Goal:* Consumes the contracts tree and confirms Z3 returns total safety proofs without raising verification errors.

---

### Step 3: Trigger the Native Binary Compilation

Execute the `build-exe` command. This initiates pre-flight checks, generates structural Go wrappers, runs `go mod tidy` in the target, is SMT-validated, and outputs the binary:

```bash
python -m freehold build-exe App.fh --output-dir ./bin --executable-name my_app
```

**Parameters Explained:**

- `file` (Positional): Path to your entry Freehold module.
- `--output-dir` / `-o` (Optional): Target directory for compiling output files (Default: `bin`).
- `--executable-name` (Optional): Custom name given to the executable target (Default: uses the source filename, e.g., `App` or `App.exe`).

---

### Step 4: Verification of Output and Cleanup Status

Upon successful compilation, verify that:

- [ ] Target directory `./bin` exists and contains the compiled executable (e.g. `./bin/my_app` or `./bin/my_app.exe`).
- [ ] No temporary, intermediate wrapper, or configuration `.go` files have leaked into the current workspace directory.
- [ ] Execution of the binary returns the expected output:

  ```bash
  ./bin/my_app
  ```

  *Expected Output:* `Freehold program initialized successfully.`

---

### Step 5: Handling Interrupts and Failures (Safe Rollback)

During the build action, if you encounter an error (for example, target module has no `Main()` routine, Go dependency resolution fails, or you hit `Ctrl+C`):

- [ ] Confirm that your output directory has been restored to its clean, pristine pre-build state.
- [ ] Review the error output printed in standard error for diagnostic line numbers and SMT context boxes to resolve root causes.
