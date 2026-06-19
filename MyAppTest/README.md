# Freehold MyAppTestCase: Guide & Instructions (Steps 1 to 5)

This directory contains a complete, self-contained test case demonstrating how to compile a contractual Freehold program into a standalone native binary.

---

## Prerequisite Self-Check

Ensure your environment satisfies these prerequisites:

- [ ] **Go Compiler:** Installed and available on system PATH (`go version`).
- [ ] **Z3 Theorem Prover:** Placed on system PATH (`z3 --version`).
- [ ] **Python Environment:** The Freehold virtual environment is active or surrounding folders contains configured dependencies.

---

## Step 1: Examine the Freehold Source (`App.fh`)

The file [App.fh](App.fh) declares a formal entry loop inside a module:

```freehold
module App

import Std.IO

procedure Main()
is
    call Std.IO.log("Freehold program initialized successfully.\n")
end Main

end App
```

---

## Step 2: Validate Semantic and Verification Validity

Before compilation, you can prove correctness statically over Z3.

- **On Windows:**

  ```cmd
  build.cmd
  ```

- **On Linux/macOS:**

  ```bash
  chmod +x build.sh
  ./build.sh
  ```

This automates the execution of:

```bash
python -m freehold verify App.fh --prover z3
```

---

## Step 3: Native Executable Compilation

The build script invokes the automated `build-exe` command:

```bash
python -m freehold build-exe App.fh --output-dir ./bin --executable-name my_app
```

This triggers environment diagnostic checks, generates secure Go source proxies, runs dependency resolution in a temporary transaction, compiles the native executable, and isolates the target directory.

---

## Step 4: Verification of Output

Run the resulting standalone binary to verify output correctness:

- **On Windows:**

  ```cmd
  .\bin\my_app.exe
  ```

- **On Linux/macOS:**

  ```bash
  ./bin/my_app
  ```

*Expected Output:*
`Freehold program initialized successfully.`

---

## Step 5: Interruption and Transactional Rollback

To test rollback safeguards, try running the build command and stopping it (`Ctrl+C`) or adding a syntactic/verifier violation to [App.fh](App.fh). The compiler transactional engine will automatically wipe intermediate files, leaving a clean workspace with no loose `.go` boilerplate.
