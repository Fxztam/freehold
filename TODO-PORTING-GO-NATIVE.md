# TODO: Porting Python Verifier Upgrades to Go & FH-Native

This document tracks the recently implemented GNATprove-alignment verifier upgrades in the Python reference compiler (`freehold/core/verifier.py`) that need to be ported to both the Go Frontend and the self-hosted Freehold-Native-V1 compiler core.

---

## 1. Transitive Information Flow Analysis (Taint-Tracking)
Port the inter-procedural dependency tracking engine to enforce information flow contracts across module boundaries.

### Go Frontend Tasks:
- Update `go-frontend/internal/semantic/analyzer.go` to support `depends` contracts.
- Implement AST checks to ensure all mutated variables in routine bodies map correctly to declared dependency targets.
- Propagate transitive parameter dependencies across nested call expressions/statements.

### FH-Native Compiler Core Tasks:
- Add `DependsSpec` support to `bootstrap/compiler_core_v1/Compiler/Core/Ast.fh` and `Parser.fh`.
- Implement dependency checking and body mutation parity checks in `bootstrap/compiler_core_v1/Compiler/Core/Verifier.fh`.

---

## 2. Transitive Globals Propagation
Ensure that global variables and services accessed transitively down the call stack are declared by callers with compatible access modes.

### Go Frontend Tasks:
- Trace routine calls and collect transitively accessed global resources/services.
- Validate that the caller's `global` block specifies all transitively accessed globals with compatible modes (`Input`, `Output`, `In_Out`).

### FH-Native Compiler Core Tasks:
- Extend `Verifier.fh` with global resource call-stack propagation checking.

---

## 3. Static Anti-Aliasing Verification
Enforce strict rules during procedure calls to prevent overlapping mutable memory references.

### Go Frontend Tasks:
- Implement `get_root_var` helper to resolve record field accesses (`x.field`) and array indexing (`arr[idx]`) back to their base variable names.
- Update the call statement validator in `analyzer.go` to reject calls violating:
  1. **Parameter-Parameter Aliasing**: Two arguments resolving to the same root variable passed to mutable parameters (where at least one is mutable).
  2. **Parameter-Global Aliasing**: A mutable parameter argument resolving to a global variable/service that is also read or written by the callee.
  3. **Argument-Global Aliasing**: An argument resolving to a global variable/service that is mutated (`Output` or `In_Out`) by the callee.

### FH-Native Compiler Core Tasks:
- Add `get_root_var` base variable resolution to `Verifier.fh`.
- Integrate parameter-parameter, parameter-global, and argument-global checks into Call statement validation in `Verifier.fh`.
