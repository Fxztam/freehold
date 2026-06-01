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

---

## 4. Field-Level Dependency Tracking (Record-Field Tracking)
Port the qualified record field mapping in information flow analysis and callee argument mutation tracking.

### Go Frontend Tasks:
- Update `analyzer.go`'s depends spec parser to handle dotted paths (e.g., `p1.x` as target and `p2.y` as source).
- Adjust `collectMutatedVars` in `analyzer.go` to correctly split and extract the root variable name (e.g., `p1.x` -> `p1`) from depends targets of the callee when analyzing `CallStmt` mutations.

### FH-Native Compiler Core Tasks:
- Support field path resolution in depends targets within `Parser.fh` and `Ast.fh`.
- Update `collect_mutated_vars` in `Verifier.fh` to split depends targets on `.` and map them to their root variables for argument mutation tracking.

---

## 5. Universal WhyML Solver Code Generator
Port the WhyML translation layer to export Freehold AST modules to Why3 Intermediate Language syntax.

### Go Frontend Tasks:
- Add a new WhyML code generation module under `go-frontend/internal/whyml/`.
- Support keyword casing, reference cells (`ref`/`!`), record field updates (`<-`), loop invariants/variants, and OCaml-style exception-based early returns.
- Integrate the `whyml` command into the Go-based CLI frontend.

### FH-Native Compiler Core Tasks:
- Implement a `WhyMLCodeGen.fh` compiler module.
- Support translating AST constructs to WhyML code strings, tracking reference variables, and handling exception return blocks.

---

## 6. Quantified Array Conditions (Frame Conditions)
Port support for universal (`for all`) and existential (`for some`) quantifier syntax, bounds type checking, and SMT-LIB v2 generation.

### Go Frontend Tasks:
- Support parsing `for all` / `for some` expressions in Lark/inline grammar and map to `ForAllExpr` / `ExistsExpr` AST nodes.
- Update `analyzer.go` to type-check quantifiers (checking that bounds are Integers and body is Boolean).
- Update Go codegen in Go frontend to generate closed loops in anonymous functions for runtime contract verification.
- Update WhyML translation in Go frontend to generate WhyML logic quantifiers.
- Map array literals to SMT-LIB `store` operations and handle typed declarations for array variables (e.g. `(Array Int Int)`) in SMT queries.

### FH-Native Compiler Core Tasks:
- Add `ForAllExpr` and `ExistsExpr` AST dataclasses and parser logic in `Ast.fh` and `Parser.fh`.
- Add bounds check typing and quantifier SMT mapping in `Verifier.fh`.
- Expand array literal SMT-mapping to nested `store`/`as const` expressions and support type-resolved array constants/variables declarations.

---

## 7. Concurrency Verification & Contract Execution
Port support for channel invariants, task spawn preconditions, ReturnStmt ensures verification, and sequential ScopeStmt path-condition threading.

### Go Frontend Tasks:
- Update the parser to accept optional `with invariant <expr>` on `channel` calls and map it to `CallExpr.Invariant`.
- Update `analyzer.go` to type-check channel invariants (asserting they evaluate to `Boolean`).
- Ensure the Go code generator ignores the invariant for compilation (preserving standard channel creation).
- Update the symbolic execution engine to verify channel invariants on `channel_send` (obligation check) and assume invariants on `channel_receive` (propagated to path conditions).
- Propagate channel invariants correctly across channel endpoints (`channel_sender` and `channel_receiver`).
- Verify task preconditions at `spawn` calls (ensuring passed arguments satisfy routine contracts).
- Verify routine `ensures` clauses at each `ReturnStmt` by substituting `result`/`value` with the returned expression (supporting record literal field lookup, variable names, and field paths).
- Update `ScopeStmt` symbolic execution to thread the returned path conditions from `spawn_body`, `join_body`, and `result_body` sequentially.

### FH-Native Compiler Core Tasks:
- Add `invariant` field support on `CallExprNode` in `Ast.fh` and `Parser.fh`.
- Update `Verifier.fh` to type-check the `invariant` of channel creation calls and verify they resolve to `Boolean`.
- Integrate symbolic verification obligations for channel send/receive invariants and routine spawn preconditions.
- Support ReturnStmt ensures checking with expression substitution and sequential ScopeStmt path-condition threading.

---

## 8. Transitive Contract Propagation & Nested Context Resolution
Port recursive import and module context propagation down through nested control-flow structures (such as `If`, `While`, `Case`, and `Scope` statements) in the symbolic verification engine.

### Go Frontend Tasks:
- *Note*: Go frontend does not currently run the SMT solver; verify that transitive routine definitions are correctly fetched from import descriptors during semantic checks in `analyzer.go`.

### FH-Native Compiler Core Tasks:
- Ensure that `walk_body` in `Verifier.fh` recursively passes down `imports` and `imported_modules` contexts to all nested block handlers.
- Verify that `find_routine` helper correctly resolves qualified name routes across transitive cross-module imports.




