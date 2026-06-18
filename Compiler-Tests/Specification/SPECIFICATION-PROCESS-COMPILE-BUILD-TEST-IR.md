# Freehold Specification: Process, Compile, Build, and Test
**Status:** Baseline process specification for Freehold CLI execution, verification, code generation, native builds, conformance gates, and bootstrap validation  
**Audience:** Freehold contributors, compiler maintainers, CI owners, release engineers, verifier authors, and test writers

This document specifies the current Freehold development and validation process.

The process is layered. A small local change should normally run a narrow command first. A parser, semantic, codegen, or bootstrap change must then run the matching comparison gates before baselines are updated or the change is considered complete.

```text
edit source or tests
  -> quick CLI smoke
  -> targeted language module or verifier check
  -> parser/semantic/codegen compare gate when relevant
  -> generated artifact or baseline check when relevant
  -> Stage-3/bootstrap gate when compiler-core behavior changes
  -> CI gate before merge/release
```

The goal is deterministic confidence: Freehold accepts the same valid programs, rejects the same invalid programs, emits the same normalized artifacts, and builds the same compiler/runtime outputs across supported lanes.

---

## 1. Process Principles

Freehold process rules:

- Use the narrowest useful command while editing.
- Run the gate that owns the changed layer before declaring the change done.
- Keep parser, semantic, IR, codegen, and bootstrap baselines separate.
- Treat generated artifacts as checked outputs, not casual scratch files.
- Do not update baselines unless the semantic change is intentional.
- Keep baseline updates out of CI unless explicitly allowed.
- Prefer deterministic compare artifacts over visual/manual inspection.
- Run Stage-3 gates for compiler-core and bootstrap-sensitive changes.
- Run example/compiler build gates for backend or runtime mapping changes.
- Report skipped gates when the change is documentation-only or otherwise outside executable behavior.

---

## 2. Command Layers

Freehold has three command layers:

```text
short developer wrappers
Python CLI commands
repository gate scripts
```

Short developer wrappers:

```powershell
fhrun <file.fh>
fhverify <file.fh>
fhfast <file.fh>
fhtest [module]
```

Python CLI form:

```powershell
python -m freehold run <file.fh>
python -m freehold verify <file.fh>
python -m freehold ast <file.fh>
python -m freehold ir <file.fh>
python -m freehold go-codegen <file.fh>
python -m freehold build-exe <file.fh>
python -m freehold test-language --module <module>
```

Repository gate scripts:

```powershell
verify-parser-conformance.cmd
verify-compiler-examples.cmd
verify-stage3-compiler-core-v1.cmd
verify-stage3-compiler-examples.cmd
compare-fhir-v1.cmd
compare-ir.cmd
```

---

## 3. Environment Setup

The wrapper scripts set `PYTHONPATH` to the repository root before invoking Python.

PowerShell helper:

```powershell
.\fhenv.ps1
```

After environment setup, short commands can be used from subdirectories:

```powershell
fhrun .\minimal_module.fh
fhverify .\minimal_module.fh
fhtest 01_core
```

Direct project-root form remains valid:

```powershell
.\freehold.ps1 run .\examples\hello_cli.fh
.\freehold.ps1 verify .\examples\hello_cli.fh
```

The `freehold.ps1` wrapper delegates to:

```powershell
python -m freehold @args
```

---

## 4. Single-File Run And Verify

Use `run` when you want parser, verifier, and interpreter execution:

```powershell
python -m freehold run .\examples\hello_cli.fh
```

Equivalent short wrapper:

```powershell
fhrun .\examples\hello_cli.fh
```

Use `verify` when you want parser and semantic/proof verification without executing the program:

```powershell
python -m freehold verify .\examples\hello_cli.fh
```

Equivalent short wrapper:

```powershell
fhverify .\examples\hello_cli.fh
```

`verify` supports solver options:

```powershell
python -m freehold verify .\examples\hello_cli.fh --prover z3 --timeout 10
```

`fhfast` prints the parsed AST quickly through the `ast` command:

```powershell
fhfast .\tests\language_modules\01_core\valid\minimal_module.fh
```

This is useful while debugging grammar and AST builder behavior.

---

## 5. AST And IR Inspection

Print the parsed AST:

```powershell
python -m freehold ast <file.fh>
```

Export canonical FH-IR project JSON:

```powershell
python -m freehold ir <file.fh>
```

Write FH-IR to a file:

```powershell
python -m freehold ir <file.fh> --output .\artifacts\scratch\project.fhir.json
```

Export legacy single-module FH-IR v0:

```powershell
python -m freehold ir <file.fh> --module-only
```

Export reduced Compare-IR:

```powershell
python -m freehold compare-ir <file.fh> --profile v1 --output .\artifacts\scratch\compare-ir.json
```

Use AST/IR inspection to understand a change. Use compare gates to validate it.

---

## 6. Code Generation

Generate Go code for one module:

```powershell
python -m freehold go-codegen <file.fh> --output .\artifacts\scratch\main.go
```

Generate a Go project for a resolved module graph:

```powershell
python -m freehold go-codegen-project <entry.fh> --output-dir .\artifacts\scratch\project
```

Generate project code with an executable wrapper:

```powershell
python -m freehold go-codegen-project <entry.fh> --output-dir .\artifacts\scratch\project --emit-executable --executable-name app
```

`go-codegen` can also verify generated Go source against an expected file:

```powershell
python -m freehold go-codegen <file.fh> --verify .\expected\main.go
```

If the generated source differs, the command reports a mismatch. A mismatch is not automatically a bug, but it requires intentional baseline review.

---

## 7. Native Build

Build a Freehold module graph into a native executable:

```powershell
python -m freehold build-exe <entry.fh>
```

Optional output directory and executable name:

```powershell
python -m freehold build-exe <entry.fh> --output-dir .\bin --executable-name my_app
```

The build process:

```text
check entry file exists
resolve and verify module graph
generate Go project files
check entry module has Main()
generate runtime/helper/build files
run go mod tidy
run go build -trimpath
write native executable
```

On Windows the binary name receives `.exe`. On other platforms the executable name has no `.exe` suffix.

The build requires a working Go toolchain.

---

## 8. Language Module Tests

Run the default language-module conformance tests:

```powershell
python -m freehold test-language
```

Run a specific module:

```powershell
python -m freehold test-language --module 01_core
```

Run a specific root:

```powershell
python -m freehold test-language --root .\tests\language_modules_v2_3
```

Repository wrapper for v2_3:

```powershell
.\verify-language-modules-v2_3.cmd
```

Short wrapper:

```powershell
fhtest 01_core
```

The language-module runner treats valid and invalid fixtures differently:

```text
valid fixtures              must parse and verify successfully
invalid_syntax fixtures     must fail during parsing
invalid_semantics fixtures  must fail during semantic/type verification
expected_errors             document expected diagnostics
expected_ast                documents AST shapes where applicable
```

Use this gate after grammar, AST, verifier, diagnostic, or feature-surface changes.

---

## 9. Regression Test Runner

The general test runner is:

```powershell
python -m freehold test
```

Wrapper form:

```powershell
.\test.ps1
```

Quick mode:

```powershell
.\test.ps1 --quick
```

Run one module through the step runner:

```powershell
.\test.ps1 01_core
```

`fhtest.ps1` delegates to:

```powershell
python tools/test_steps.py @args
```

Use this runner for local regression sweeps that are broader than a single language module but lighter than the full parser/bootstrap gate set.

---

## 10. Parser Conformance Gate

The parser conformance gate is:

```powershell
.\verify-parser-conformance.cmd
```

It is the main frontend parity gate.

It regenerates and checks:

```text
Go AST artifacts
Go parser diagnostics
grammar consistency
Go semantic diagnostics
Go semantic projects
Go project semantic diagnostics
spec diagnostics
Python semantic diagnostics
protobuf/gRPC artifacts
Go codegen artifacts
Go feature matrix
DHParser parser code
DHParser AST artifacts
parse-status parity
parse-error diagnostics
AST shape parity
semantic AST parity
FH-IR comparison
FH-IR determinism
FH-IR language module profile
FH-IR V1 comparison
go-frontend Go tests
```

The script reports this as a 22-step chain with an optional `20b/22` FH-IR V1 gate.

Run this gate after:

- grammar changes
- parser changes
- AST normalization changes
- diagnostic catalog/spec changes
- semantic diagnostic changes
- Go frontend changes
- FH-IR export changes
- feature-matrix changes

---

## 11. Parser Conformance Modes

Default mode checks without writing permanent baselines. Temporary output roots are used for Go/Python artifacts where possible.

Supported flags include:

```text
--update-go-baseline
--update-python-baseline
--enable-fhir-v1-gate
--disable-fhir-v1-gate
--force
```

Baseline updates are guarded. In CI, baseline update flags are blocked unless:

```text
FREEHOLD_ALLOW_BASELINE_UPDATE=1
```

Use update modes only when the new output is the intended language/compiler behavior.

---

## 12. Diagnostic Gates

Verify diagnostic spec consistency:

```powershell
.\verify-spec-diagnostics.cmd
```

Compare semantic/type diagnostics:

```powershell
.\compare-semantic-diagnostics.cmd
```

Go-native semantic diagnostic gates:

```powershell
.\verify-go-semantic-diagnostics.cmd
.\verify-go-semantic-projects.cmd
.\verify-go-project-semantic-diagnostics.cmd
```

Use these gates when changing:

- `spec/freehold.diag`
- `spec/freehold.rules`
- `spec/analyzer.cflow`
- diagnostic normalizers
- verifier diagnostics
- Go diagnostic catalog
- Go semantic project loader
- expected diagnostic manifests

Diagnostic wording may vary across implementations, but code, category, normalized behavior, and source position must remain controlled by the gates.

---

## 13. IR And Artifact Compare Gates

Compare reduced IR samples:

```powershell
.\compare-ir.cmd
```

Compiler V1 Compare-IR gates:

```powershell
.\compare-ir-compiler-v1.cmd
.\compare-ir-compiler-v1-stage2.cmd
```

Compare canonical FH-IR:

```powershell
.\compare-fhir.cmd
```

Compare project-wide FH-IR V1:

```powershell
.\compare-fhir-v1.cmd
```

Targeted FH-IR V1 baseline update:

```powershell
.\compare-fhir-v1-update.cmd
```

Determinism check:

```powershell
.\compare-fhir-determinism.cmd
```

Language-module FH-IR profile:

```powershell
.\compare-fhir-language-modules.cmd
```

Use these gates after changes to AST enrichment, module graph resolution, verifier analysis export, source-map-sensitive structure, IR serialization, canonical ordering, or compiler sample coverage.

---

## 14. Go Frontend And Go Build Gates

Run Go frontend tests directly:

```powershell
cd go-frontend
 go test ./...
```

The parser conformance gate runs this as its final Go frontend step.

Generate Go parser artifacts manually:

```powershell
cd go-frontend
.\go-parse-tests-language-modules.cmd
```

Generate Go codegen artifacts:

```powershell
.\generate-go-codegen-artifacts.cmd
```

Verify compiler examples:

```powershell
.\verify-compiler-examples.cmd
```

`verify-compiler-examples.cmd` runs `tools\verify_compiler_examples.py` and validates Go project code generation and executable behavior for supported compiler examples.

Use these gates for Go parser, Go semantic, Go codegen, runtime module mapping, generated Go project layout, and executable build behavior.

---

## 15. Stage-3 Compiler-Core Gate

The Stage-3 compiler-core gate is:

```powershell
.\verify-stage3-compiler-core-v1.cmd
```

It runs:

```text
tools/verify_stage3_compiler_core_contracts.py
  --manifest artifacts/stage3/compiler_core_v1/manifest.json
  --out artifacts/stage3/compiler_core_v1/report
```

The script selects `.venv\Scripts\python.exe` when available, otherwise `python`.

If `FREEHOLD_PROVER` is not set, it defaults to:

```text
none
```

Use this gate when changing:

- `bootstrap/compiler_core_v1` compiler-core source
- Stage-3 manifests
- compiler-core generated Go expectations
- compiler-core contracts
- bootstrap-sensitive codegen
- canonical compiler-core outputs

A passing gate means the compiler-core contracts and generated project/report match the Stage-3 manifest expectations.

---

## 16. Stage-3 Compiler Examples Gate

The Stage-3 example gate is:

```powershell
.\verify-stage3-compiler-examples.cmd
```

It runs:

```text
tools/verify_stage3_compiler_on_examples.py
```

Use this gate when changing compiler-core behavior that affects example parsing, lowering, VM/interpreter behavior, runtime assertions, compiler examples, or Stage-3 example artifacts.

---

## 17. Bootstrap Gate

The bootstrap trust anchor is deterministic canonical FH-IR, not a native binary by itself.

Conceptual chain:

```text
Stage 0 compiler compiles Freehold compiler sources
  -> compiler.stage1.fhirb

Stage 1 compiler/runner compiles the same compiler sources again
  -> compiler.stage2.fhirb

Bootstrap gate
  -> sha256(compiler.stage1.fhirb) == sha256(compiler.stage2.fhirb)
```

Native binaries, LLVM IR, or generated Go code may also be produced, but the primary bootstrap comparison is the deterministic compiler-state artifact.

Bootstrap-sensitive output must avoid:

- nondeterministic map/hash iteration
- host-specific paths in comparison artifacts
- timestamps
- unstable symbol ordering
- unstable module ordering
- nondeterministic standard-library/runtime builtin tables

---

## 18. CI Process

The CI process runs major gates automatically.

Documented CI gates include:

```text
verify-parser-conformance.cmd
verify-compiler-examples.cmd
verify-stage3-compiler-core-v1.cmd
```

CI setup includes Python dependencies and Go.

Baseline update protection:

```text
CI baseline updates are blocked by default.
FREEHOLD_ALLOW_BASELINE_UPDATE=1 is required for planned baseline maintenance.
```

This prevents accidental drift in generated parser, diagnostic, IR, or codegen artifacts.

---

## 19. Suggested Gate Selection

Use this as the normal local decision table:

```text
Documentation only
  -> no executable tests required; verify Markdown integrity

Single program behavior
  -> fhrun / fhverify

Verifier or semantic rule
  -> targeted test-language module
  -> compare-semantic-diagnostics if diagnostics changed
  -> verify-parser-conformance if normalized artifacts changed

Parser or grammar
  -> fhfast / ast inspection
  -> verify-parser-conformance

Go frontend parser/semantic
  -> go-frontend go test ./...
  -> verify-go-* gates
  -> verify-parser-conformance

Runtime standard module or Go codegen
  -> targeted language module
  -> generate-go-codegen-artifacts.cmd
  -> verify-compiler-examples.cmd

FH-IR/export/canonical ordering
  -> compare-fhir-v1.cmd
  -> compare-fhir-determinism.cmd
  -> verify-parser-conformance when frontend artifacts are affected

Bootstrap compiler-core
  -> verify-stage3-compiler-core-v1.cmd
  -> verify-stage3-compiler-examples.cmd when examples/runtime behavior are affected

Release or broad merge confidence
  -> verify-parser-conformance.cmd
  -> verify-compiler-examples.cmd
  -> verify-stage3-compiler-core-v1.cmd
```

---

## 20. Baseline Update Policy

Baseline updates are allowed only when the new behavior is intentional.

Examples of legitimate baseline updates:

- a grammar change intentionally changes AST shape
- a diagnostic code becomes more precise
- a semantic rule intentionally rejects a previously accepted invalid program
- FH-IR V1 gains a new canonical field
- Go codegen intentionally changes generated output

Examples of illegitimate baseline updates:

- accepting nondeterministic output because it happened locally
- hiding a parser mismatch without understanding it
- updating diagnostics after an accidental wording/category regression
- committing generated artifacts from a failed or partial gate
- updating CI baselines without explicit approval

Baseline update commands should be run from the repository root and reviewed as generated-output changes.

---

## 21. Failure Handling

When a gate fails:

1. Identify the owning layer: syntax, AST, semantic, diagnostic, IR, Go codegen, build, Stage-3, or bootstrap.
2. Read the generated report under `artifacts/...` or the temp path printed by the gate.
3. Fix the root cause before updating baselines.
4. Re-run the narrow failing gate.
5. Re-run the broader gate if the fix changes shared behavior.

Do not treat all mismatches as baseline churn. Many mismatches are real regressions in determinism, semantic normalization, or backend handoff.

---

## 22. Common Workflows

### 22.1 Quick Feature Edit

```powershell
fhfast .\tests\language_modules\01_core\valid\minimal_module.fh
fhverify .\tests\language_modules\01_core\valid\minimal_module.fh
fhtest 01_core
```

### 22.2 Semantic Diagnostic Edit

```powershell
python -m freehold test-language --module <module>
.\compare-semantic-diagnostics.cmd
.\verify-spec-diagnostics.cmd
```

### 22.3 Parser/AST Edit

```powershell
.\verify-parser-conformance.cmd
```

### 22.4 Go Codegen Edit

```powershell
.\generate-go-codegen-artifacts.cmd
.\verify-compiler-examples.cmd
```

### 22.5 Compiler-Core Edit

```powershell
.\verify-stage3-compiler-core-v1.cmd
.\verify-stage3-compiler-examples.cmd
```

### 22.6 Native Application Build

```powershell
python -m freehold build-exe .\examples\compiler_v1\01_minimal_app\App\Main.fh --output-dir .\bin --executable-name minimal_app
```

---

## 23. Practical Checklist

Before closing a code task, check:

- The touched layer has an appropriate gate.
- The narrow gate passes first.
- Generated artifacts were updated only intentionally.
- Diagnostic changes are reflected in specs/manifests/normalizers.
- Parser changes preserve parse-status and AST parity.
- Semantic changes preserve expected diagnostics or update them deliberately.
- Codegen changes preserve supported example builds.
- IR changes preserve canonical ordering and determinism.
- Stage-3 changes pass compiler-core contracts.
- Bootstrap-sensitive changes preserve deterministic compiler artifacts.
- Any skipped tests are explained clearly.

A good Freehold process keeps edit feedback fast while reserving full confidence for the gates that actually own parser parity, semantic correctness, deterministic IR, executable builds, and self-hosting compiler stability.
