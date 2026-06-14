# TODO: FH-Native-V1 Final Bootstrapping Phase Checklist
**Format Reference:** Google Open Knowledge Format (OKF) & Implementation Blueprint  
**Status:** High Priority Roadmap (The Final Step to Permanent Self-Hosting)  
**Target Domain:** Language Design, Compiler Engineering & GNATprove/SPARK Ada Parity  

---

## 1. Executive Summary & V1 Bootstrapping Gate Status

All functional core milestones of the **Stage-1 Self-Hosting Bootstrapping** cycles have been successfully completed. 
The transpiled Go-native Stage-3 compiler binary (`bin/stage3_compiler_core_v1.exe`) successfully compiles its own source code, producing byte-identical intermediate representations (`stage2.fhirb` == `stage1.fhirb` by matching SHA-256 hashes).

However, before the Python-based reference compiler can be permanently decommissioned and Freehold becomes a 100% autarkic, self-hosted native compiler, several verifier-level upgrades must be natively ported, and CLI build drivers hardened.

This specification sheets exactly what stands between our current state and the **Final Freehold-Native-V1 Release Gate**.

---

## 2. Topic 1: Porting Verifier Upgrades (GNATprove/SPARK Ada Parity)

The high-safety verification upgrades recently established inside the Python reference model (`freehold/core/verifier.py`) must be fully ported to the native self-hosted compiler core under `bootstrap/compiler_core_v1/Compiler/Core/Verifier.fh`.

### 2.1 Transitive Information Flow Analysis (Taint-Tracking)
* **Goal:** Implement inter-procedural dependency tracking inside `Verifier.fh` to enforce information-flow integrity across module boundaries.
* **Task:** Add full parsing, validation, and semantic analysis of `depends` contract statements.

### 2.2 Transitive Globals-Resource Propagation
* **Goal:** Track global variables and service resources transitively down the functional call stack.
* **Task:** Extend `Verifier.fh` to validate that a caller's `global` aspect declares all transitively accessed globals with compatible usage modes (`Input`, `Output`, `In_Out`).

### 2.3 Static Memory Anti-Aliasing (Aliasing Protection)
* **Goal:** Prevent overlapping mutable memory references at compile-time to guarantee execution safety.
* **Task:** Add the root variable resolution helper (`get_root_var`) and validate procedure arguments at call-sites to reject:
  1. **Parameter-Parameter Aliasing:** Passing two overlapping locations to mutable parameters.
  2. **Parameter-Global / Argument-Global Aliasing:** Overlapping arguments with active callee global access specs.

### 2.4 Field-Level Dependency Mapping
* **Goal:** Track info-flow and mutations down to qualified record attributes (e.g. `p1.x` -> `p1`).
* **Task:** Extend AST fields evaluation in `Verifier.fh` and `Parser.fh` to cleanly extract and split nested qualified field path contexts.

### 2.5 Universal WhyML Code-Generation
* **Goal:** Modernize Why3 integration to export validated Freehold modules directly to WhyML intermediate syntax.
* **Task:** Implement `WhyMLCodeGen.fh` inside the compiler-core supporting value cells (`ref`/`!`), records mutations, and early returns.

### 2.6 Quantified Array Conditions
* **Goal:** Enable universal (`for all`) and existential (`for some`) loop-free logical assertions in contracts.
* **Task:** Implement `ForAllExpr` and `ExistsExpr` parsing and type checking inside the native parser mitsamt SMT-LIB v2 generation.

### 2.7 Concurrent Memory Safety & Channel Invariants
* **Goal:** Support proving thread-safety and race-free state transitions inside parallel flows.
* **Task:** Parse and verify `with invariant` conditions on `channel` types and validate `spawn` calling preconditions.

---

## 3. Topic 2: CLI comfort & Cross-Platform Hardening

To establish maximum ergonomics (Developer Experience - DX) and deployment portability:

### 3.1 Integrated CLI Binary Builder (`freehold build-exe`)
* **Goal:** Introduce a straightforward, developer-friendly CLI command to compile Freehold codebases directly into single, standalone OS-native binaries.
* **Task:** Abstract the underlying Go workspace scaffolding, compilation, and transpiling steps under:
  ```bash
  freehold build-exe App/Main.fh --output bin/my-program
  ```

### 3.2 Cross-Platform Script Hardening
* **Goal:** Ensure the compiler bootstraps and verifiably executes across other target infrastructures (Linux, macOS).
* **Task:** Port all active Windows-based `.cmd` verification scripts into standardized Bash (`.sh`) runners.
