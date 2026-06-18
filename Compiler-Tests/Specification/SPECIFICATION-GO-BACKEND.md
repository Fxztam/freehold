# Freehold Compiler: Go-Backend Strategy & Library Interface Specification
**Format Reference:** Google Open Knowledge Format (OKF) & Architectural Design Blueprint  

This specification defines the architectural roadmap, implementation constraints, and runtime integration of the native Go-CodeGen backend and standard library structures in the Freehold compiler ecosystem.

---

## 1. Architectural Strategy & Phased Roadmaps

The modernization and validation of Freehold's execution layers follow a hiearchical, proof-secured rollout strategy. By leveraging Go as the primary compilation target during pre-bootstrap and bootstrapping, we decouple frontend verification issues from hardware-level optimization hurdles.

### 1.1 Phase 1: High-Performance Go-Backend Validation (Active Target)
* **Goal:** Hardening compiler frontend semantics (lexing, parsing, verifier context, Z3 proof bindings) using a high-level, memory-safe compiled language.
* **Benefits:** 
  - Complete memory safety guarantees with Go's GC.
  - Lightning-fast compiler roundtrips for full E2E testing suites.
  - Native concurrency mapping via Go routines and channels.
* **Mitigation of Risks:** Eliminates low-level register-allocation and hardware-trap bugs, isolating any compilation discrepancies directly to the parsing or logical verifier modules.

### 1.2 Phase 2: Native FFI & Library Ecosystem
* All default runtime standard libraries, networking utilities (HTTP/2, gRPC-Protobuf, WebSockets), and operating system bindings are implemented and exported via Go's native packages.
* Performance-critical components are mapped directly to corresponding Go package structures to exploit multicore hardware.

### 1.3 Phase 3: Transition to Freehold-IR & LLVM (Deferred Target)
* **Strategy:** After the compiler achieves complete bootstrap validation with the Go backend, native code generation will extend towards a formalized Intermediate Representation (IR) and an LLVM optimization pipeline.
* **Release Optimization:** Statically proven tautologies will be optimized out entirely in production targets.

---

## 2. Compilation Translation Rules & Runtime Safety

This section outlines how compiler assertions and specification artifacts are mapped into executable files.

### 2.1 Hybrid Execution of `check` Statements
The `check` keyword represents a dual-guarantee verification instrument:
1. **Compile-Time (Z3):** Translated to an SMT-LIB v2 proof obligation. If Z3 finds any satisfiable counter-example state where the expression evaluates to false, compilation aborts with a static `VerificationError`.
2. **Runtime (Go Compilation):** Safely compiled into an efficient inline panic block. In [freehold/core/go_codegen.py](freehold/core/go_codegen.py) the instruction translates directly to:
   ```go
   if !(cond) {
       panic("freehold check failed")
   }
   ```

### 2.2 LLVM Direct-Compilation Alignment (Future Port)
When translating Freehold's verifications to bare-metal LLVM IR without Go-runtime dependencies, the `check` validation translates to:
* **Hardware Traps:** Incorporates direct CPU-level traps (`@llvm.trap` issuing `ud2` on x86) avoiding third-party runtime footprints.
* **Static Pruning (`unreachable`):** For certified production releases, verified assertions are declared as `unreachable` blocks. The LLVM Optimizer (`opt`) prunes the conditional branches entirely, producing branches-free assembler routines with absolute zero performance overhead.

---

## 3. Specification-Only Zero-Footprint Structures (Ghost Sets)

Abstract mathematical collection verifications are strictly delineated from executing memory layers.

### 3.1 Ghost Sets Contract Isolation
Mengen (`Set<T>`) are restricted solely to static, contract-based verification inside preconditions (`requires`), postconditions (`ensures`), and `while` loop invariants. 

### 3.2 Verification Restrictions & Type Conformance
During verifications in [freehold/core/verifier.py](freehold/core/verifier.py), the type-system strictly enforces:
* **No Variable Allocations:** Standard declarations such as `let s: Set<Integer>` are rejected.
* **No Functional Footprint:** Routine parameter bounds and return types must not contain set configurations.
* **No Struct States:** Fields in records or choice sum constructors must not declare sets.

This guarantees that all set literals (`{x1, x2, ..., xn}`) and element operations (`Set.contains`, `Set.add`, `Set.remove`, `Set.size`) are completely verified as pure functions via Z3's array theory at compile-time, with exactly zero execution footprint in the final binaries.
