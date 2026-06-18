# Freehold Specification — Condensed Summary

**Status:** Aggregated digest of all individual Freehold specifications in `Compiler-Tests/Specification/`
**Audience:** Freehold authors, verifier/back-end implementers, conformance-test writers
**Date:** 2026-06-18

This document condenses the Freehold specification files into one reference (all `SPECIFICATION-*.md` files except `SPECIFICATION-ANALYSE-STATUS.md`).
Each section summarizes one source specification; consult the named file for the complete normative text and examples.

---

## Index of Source Specifications

| # | Area | Source File |
|---|------|-------------|
| 1 | Program basics, modules, imports | `SPECIFICATION-FH-BASICS.md` |
| 2 | Statements (`let`, `call`, `=`, `:=`) | `SPECIFICATION-FH-STATEMENTS.md` |
| 3 | Functions, procedures, contracts | `SPECIFICATION-FUNCTION-PROCEDURE-VERIFY.md` |
| 4 | Error handling (`Result`, `abort`) | `SPECIFICATION-ERROR-HANDLING.md` |
| 5 | Loop invariants and variants | `SPECIFICATION-LOOP-INVARIANT.md` |
| 6 | Arrays | `SPECIFICATION-ARRAYS.md` |
| 7 | Maps | `SPECIFICATION-MAP.md` |
| 8 | Sets (ghost / specification-only) | `SPECIFICATION-SETS.md` |
| 9 | Choice ADTs and pattern matching | `SPECIFICATION-CHOICE-MAPPING.md` |
| 10 | Record JSON | `SPECIFICATION-RECORD-JSON.md` |
| 11 | Concurrency and parallelism | `SPECIFICATION-CONCURRENT-PARALLEL.md` |
| 12 | Formal verification (completed features) | `SPECIFICATION-VERIFICATION.md` |
| 13 | Compiler front-end | `SPECIFICATION-COMIPLER-FRONTEND.md` |
| 14 | Go back-end strategy | `SPECIFICATION-GO-BACKEND.md` |
| 15 | Standard library | `SPECIFICATION-STD.md` |
| 16 | gRPC IDL and bindings | `SPECIFICATION-GRPC.md` |
| 17 | HTTP / REST | `SPECIFICATION-HTTP-REST.md` |
| 18 | WebSockets | `SPECIFICATION-WEBSOCKETS.md` |
| 19 | Server-Sent Events (SSE) | `SPECIFICATION-SSE.md` |
| 20 | Crypto | `SPECIFICATION-CRYPTO.md` |
| 21 | KeyPass / KeePassXC bridge | `SPECIFICATION-KEYPASS.md` |
| 22 | Oracle database | `SPECIFICATION-ORACLE.md` |
| 23 | Process: Python → compile → build → Go → test | `SPECIFICATION-PROCESS-PYTHON-COMPILE-BUILD-GO-TEST.md` |
| 24 | Process: compile, build, test (IR) | `SPECIFICATION-PROCESS-COMPILE-BUILD-TEST-IR.md` |
| 25 | Process: native compile, build, Go, EXE test | `SPECIFICATION-PROCESS-COMPILE-BUILD-GO-TEST.md` |

---

## Part A — Core Language

### 1. Program Basics, Modules, Imports

- A source file is exactly one module: `module Name ... end Name`. The closing name must match exactly.
- Top-level order: `module_decl`, then `import_decl*`, then `declaration*`, then `module_end`.
- Qualified names form a namespace tree mapped to the file tree (`Banking.Types` → `Banking/Types.fh`).
- Recommended declaration order: ranged `type` aliases → `record` → `choice` → `error` → `service` → functions → procedures/tasks → `main`.
- Imports: plain (`import Std.IO`) or selective (`import M exposing A, B`). Prefer qualified access when names collide.
- Import safety rules: no self-imports, no duplicate imports, no duplicate/non-existent exposed symbols, no cyclic imports. Shared types go in a low-level module.

### 2. Statements (`let`, `call`, `=`, `:=`)

- `let name: Type = expr` introduces an initialized, immutable local binding (type-checked against the declared type).
- `:=` is the assignment/mutation operator (writes to variables, fields, array elements); `=` is equality in expressions/contracts.
- `call Proc(args)` invokes a procedure (no value). Function results are bound with `let`.
- `let` supports record literals, array literals, and binding the results of calls (including `Result` destructuring patterns).
- Plain `name = value` assignment (Pascal-style) is rejected; mutation must use `:=`.

### 3. Functions, Procedures, and Verification Contracts

- Routine kinds: pure `function` (returns a value), `procedure` (no return), plus async `task`.
- Contract block sits between the signature and `is`, in order: `requires` → `ensures` → `modifies` (→ `aborts`).
- `requires`: preconditions proven at every call site by the SMT solver.
- `ensures`: postconditions; may use `result` and `old(...)`. They flow into caller path conditions after the call.
- `modifies`: explicit mutation frame; any write to a parameter/field/array element/global must be declared (field frames like `c.val`, or whole-value frames).
- Plain functions must guarantee a return on every path and cannot return error branches.
- `Result<T,E>` functions use `return ok expr` / `return error ErrorName`; postconditions may constrain `success`/`value`/`error`.
- Verification failure patterns: missing precondition, missing `modifies`, wrong result-return form, wrong error type, postcondition not matching body.

### 4. Error Handling

- Two mechanisms: `Result<T,E>` for expected/typed failure as a return value, and `abort`/`aborts` for exceptional control-flow exit.
- Errors are declared at module level: `error NotFound`. Names should be stable domain names.
- Use `Result<T,E>` when failure is normal program logic; use `abort ErrorName` (declared via `aborts ErrorName`) when no normal return value is produced on that path.

### 5. Loop Invariants and Variants

- `while cond invariant <expr>+ variant <expr>? do ... end while`.
- A loop must have at least one `invariant`; the `variant` is optional grammatically but is the safe style for proving termination.
- Invariants must hold before and after each iteration; the variant must strictly decrease (and stay bounded) to prove termination.

---

## Part B — Data Types

### 6. Arrays

- Fixed-size typed arrays `Array<T, N>`; literals are length- and element-type-checked.
- Static index bounds are checked at compile time; runtime indices produce `range_check` proof obligations.
- Supports element update (`:=`), `modifies` frames for array mutation, quantifiers (`for all` / `for some`) for contracts, and nesting in records/JSON.
- Assigning arrays of differing size or element type is rejected. Returning arrays and arrays inside `Result` are supported.

### 7. Maps

- Associative `Map<K, V>` types with literal syntax, membership/lookup, and pure update operations.
- The verifier models finiteness and termination for map-driven reasoning (see Verification §3).

### 8. Sets (Ghost / Specification-Only)

- Sets are zero-runtime-footprint "ghost" constructs usable only in specifications (contracts/invariants), not in executable values.
- Forbidden as local variables, routine parameters, routine returns, record fields, and choice constructor payloads.
- Provide membership, pure add/remove, and size, mapped to SMT for proofs. Complement arrays/maps for verification only.

### 9. Choice ADTs and Pattern Matching

- `choice` declares tagged-union (algebraic) data types; pattern matching deconstructs them.
- Semantic rules: duplicate-branch control, guard validity, and mathematical exhaustiveness (all constructors/bounds covered).
- Mapped to SMT for verification and translated to WhyML (data types, generics/type parameters, guard translation).

### 10. Record JSON

- Records define schemas; `@json` maps fields to external JSON names; field-name matching is exact.
- `Json.stringify` serializes typed records; `Json.parse<Record>` returns a typed record or `SchemaError`.
- Supports nested records, arrays in JSON, range subtypes, null handling, and both literal (compile-time) and runtime validation.

---

## Part C — Concurrency & Verification

### 11. Concurrency and Parallelism (Dual-Core Model)

- Default (`spawn` without `parallel`): cooperative logical concurrency on exactly one physical core — deterministic, race-free.
- `parallel name (limit = N) do ... end parallel`: opt-in physical multi-core via Go M:N work-stealing scheduler; named-block parity enforced.
- Two async styles: functional `async`/`await` (typed `JoinHandle<T>`) and message-passing `task` (CSP via typed channels, `JoinHandle<Void>`).
- `spawn` targets: `async function`, `async procedure`, or `task`; attributes `priority`, `pool`, `name`.
- Safety rules: no shared mutable state across parallel spawns (arrays/records/paths); channels are the preferred parallel data path; nested-boundary rules.
- Z3 rules: async `ensures` flow into path conditions after `await`; channel `with invariant` asserted on send/receive; spawn-site `requires` proven.
- Static "No-Blocking" guarantee: unbounded blocking channel ops are forbidden in limited pools to prevent starvation/deadlock.
- Parallel rendezvous `await all [t1, t2]` joins a handle group into a monomorphic `Array<T, N>`; each task's `ensures` maps to its result slot.

### 12. Formal Verification (Completed Features)

1. Transitive context propagation across nested blocks.
2. Tagged-union (choice) exhaustiveness analysis.
3. Map finiteness and termination reasoning.
4. Concurrency verification (spawns and channel invariants).
5. Specification-only ghost sets.

---

## Part D — Compiler & Build Pipeline

### 13. Compiler Front-end

- Three front-end lanes: Python/Lark reference, Go front-end, and self-hosting FH-Native-V1 bootstrap.
- Clear separation of lexer, parser, AST boundary, parse diagnostics, module resolution, and exposed-symbol checks.
- Semantic verification and control-flow are handed off after parsing; determinism rules govern module traversal.
- Conformance gates and a front-end→back-end boundary keep parser concerns separate from semantics. Python is the reference implementation.

### 14. Go Back-end Strategy

- Phase 1 (active): high-performance Go back-end validation; Phase 2: native FFI/library ecosystem; Phase 3 (deferred): Freehold-IR + LLVM.
- Hybrid execution of `check` statements; ghost sets are zero-footprint (specification-only, no emitted code).

### 15. Standard Library

- `Std` modules imported explicitly. Includes `Math`, `Big` (BigInteger/BigFloat) with runtime mappings, and `Std.IO` (logging, `logf` templates).
- Standard/runtime modules sit outside the verification boundary (operational effects) and have a defined back-end boundary.

---

## Part E — Networking, Services & Integrations

### 16. gRPC IDL and Bindings

- Records become protobuf messages with explicit, unique proto field IDs; `service` declares unary and streaming RPCs.
- Defined protobuf type mapping, nested-message closure, package naming, proto generation, Go gRPC bindings, and error/status mapping.
- Diagnostics cover missing/duplicate/invalid field IDs, unknown RPC type, unsupported field type, duplicate RPC name; schema-evolution rules apply.

### 17. HTTP / REST

- Layered: `Std.Connect.Common` (shared transport types) → `Std.Connect.Http` (client/server/middleware/streaming/SSE) → `Std.Connect.Rest` (resource helpers).
- Typed JSON via `Json.stringify` / `Json.parse<T>`; fallible boundaries are explicit through `Result<T, ConnectError>` and `Result<T, SchemaError>`.
- `RequestScope` per-request lifetime; structured concurrency via `Scope` / `JoinHandle<T>`.

### 18. WebSockets

- Connection/server API with connection scope and message scope; text send/receive, backpressure, frame policy, close status.
- Typed JSON messages, broadcast envelopes, registry/room broadcast, keepalive, error messages, and static+runtime JSON validation.
- Maps to a native Go runtime.

### 19. Server-Sent Events (SSE)

- One-way server→client streaming; event creation, server response, native HTTP mapping, and client open.
- Channels + backpressure, an event-count contract, JSON payloads, and an error model; related to HTTP streaming and WebSockets.

### 20. Crypto

- `Std.Crypto` FFI over a Go shim: SHA-256/512 digests and HMAC (deterministic `String -> String`), secure random bytes, AES-256-GCM (AAD must match), and a KeePassXC bridge.
- Fallible operations return `Result<T, CryptoError>`; secret storage and master-key management stay outside Freehold source.

### 21. KeyPass / KeePassXC Bridge

- Conservative, read-only credential bridge exposed through `Std.Crypto`, backed by `keepassxc-cli` and (on Windows) Credential Manager.
- Lets programs use credentials, wallet locations, API tokens, and DB secrets without committing them to source. Returns `Result<T, CryptoError>`.

### 22. Oracle Database

- `Std`-style FFI module: connection URLs with credentials, wallet/tnsnames connection, DSN options, and credential sources (KeePassXC, env vars).
- Operations: ping, scalar query, SQL execute, SQL files, row queries as text tables, typed fixed projections; type-conversion and secret-handling rules; structured error handling.

---

## Part F — Process, Build & Test Gates

### 23. Process — Python Compile/Build/Go/EXE Test

- Source-of-truth files, high-level pipeline, Python CLI Go-project generation, generated layout/main wrapper/build scripts.
- Go dependency resolution, "go test before go build", native EXE build, runtime EXE validation and runtime-log Go test.
- Compiler-example and Stage-3 gates, confidence levels, acceptance checklist, and failure modes.

### 24. Process — Compile/Build/Test (IR)

- Process principles and layered commands: environment setup, single-file run/verify, AST/IR inspection, codegen, native build.
- Gates: language-module tests, regression runner, parser conformance, diagnostics, IR/artifact compare, Go front-end/build, Stage-3 compiler-core, bootstrap, and CI.
- Baseline-update policy, failure handling, and recommended gate selection.

### 25. Process — Native Compile/Build/Go/EXE Test

- The non-Python native lane: native CLI contract, front-end and Go back-end responsibilities, generated runtime project and `go.mod` contract.
- Executable wrapper, native builder Go commands, runtime EXE and golden contracts, native/compiler-core release gates.
- Native file/system APIs, Go runtime surface, sidecar runtime services, failure classes, acceptance matrix, and the "non-Python" rule.

---

## Cross-Cutting Principles

- **Verification first:** every fallible boundary is explicit (`Result`), every mutation is framed (`modifies`), and contracts (`requires`/`ensures`/`invariant`/`variant`) are SMT/Z3-checked.
- **Determinism:** module traversal, codegen, and artifacts are deterministic to support reproducible compare gates.
- **Reference parity:** the Python reference compiler defines correct behavior; Go and FH-Native lanes must match it before they can replace it.
- **Explicit effects:** standard-library and integration surfaces (IO, HTTP, WebSockets, SSE, Crypto, Oracle) sit outside the proof core but expose typed, checked boundaries.
- **Secrets stay out of source:** Crypto/KeyPass/Oracle credential flows read secrets externally (KeePassXC, keyring, env vars).
