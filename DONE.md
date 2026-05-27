# DONE

## 2026-05-26

### Python IR V1 Baseline Lane + Optional Gate

- V1 baseline lane was built via dry run:
  - `python .\tools\compare_fhir.py --mode project-v1 --expected .\artifacts\fhir-v1 --update --dry-run`
- Targeted baseline update was executed and reviewed:
  - `python .\tools\compare_fhir.py --mode project-v1 --expected .\artifacts\fhir-v1 --update`
  - Result: 26/26 cases matching.
- Optional V1 conformance gate was integrated into verify flow:
  - `verify-parser-conformance.cmd --enable-fhir-v1-gate`
- Conformance run with optional V1 gate passed.
- Baseline lane artifacts are present under `artifacts/fhir-v1`.
- Process guidance was updated in `TODO-CONFORMANCE-BASELINE-TESTS.md`.

### Commit

- Single clean commit created for the three requested blocks:
  - Commit: `17927a1`
  - Message: `feat(conformance): add FH-IR v1 baseline lane and optional gate`
  - Scope:
    - `verify-parser-conformance.cmd`
    - `TODO-CONFORMANCE-BASELINE-TESTS.md`
    - `artifacts/fhir-v1/*`

### Next IR Step: V1 ergonomics wrappers

- Added dedicated V1 compare wrappers:
  - `compare-fhir-v1.cmd`
  - `compare-fhir-v1-update.cmd`
- Updated usage docs in:
  - `README_FREEHOLD_CLI.md`
  - `TODO-CONFORMANCE-BASELINE-TESTS.md`
- Validation run:
  - `cmd /c compare-fhir-v1.cmd`
  - Result: `Mismatching FH-IR: 0` (26/26 matching)

### Next IR Step: V1 gate default-on

- Switched V1 gate policy in verify flow from optional to default enabled.
- Added escape flag to disable V1 gate when needed:
  - `--disable-fhir-v1-gate`
- Kept `--enable-fhir-v1-gate` as compatibility flag.
- Updated files:
  - `verify-parser-conformance.cmd`
  - `TODO-CONFORMANCE-BASELINE-TESTS.md`
  - `README_FREEHOLD_CLI.md`
- Validation run:
  - `cmd /c verify-parser-conformance.cmd --disable-fhir-v1-gate`
  - Result: parser conformance verify passed.

### Final closeout: all pending commits completed

- User-requested closeout performed: all remaining pending workspace deltas were committed.
- Included:
  - remaining conformance artifact deltas
  - pending Python FH-IR source delta
  - pending Go parser/semantic source deltas
  - V1 wrapper scripts (`compare-fhir-v1.cmd`, `compare-fhir-v1-update.cmd`)

### Go-Compiler-Path kickoff baseline

- IR-V1 handover baseline revalidated:
  - `cmd /c verify-parser-conformance.cmd`
  - Result: parser conformance verify passed.
- Go project-aware semantic gates revalidated:
  - `cmd /c verify-go-semantic-projects.cmd` -> expected 18, mismatches 0
  - `cmd /c verify-go-project-semantic-diagnostics.cmd` -> expected 13, mismatches 0
- Umschwenkstatus: Go compiler path can start from green baseline.

### Go slice: cross-module type composition hardening

- Added new negative project-aware semantic fixture:
  - `tests/language_modules/03_import_resolution/fixtures/invalid/import_array_record_return_unknown_field/*`
- New coverage target:
  - direct `Array<imported Record, N>` return contract path via `result[index].field` over imported nested record types.
- Added expected diagnostic golden in:
  - `tests/language_modules/expected_go_project_semantic_diagnostics.json`
  - expected code: `FH-SEM-1105` (`unknown_record_field`)
- Validation:
  - `cmd /c verify-go-project-semantic-diagnostics.cmd` -> expected 14, mismatches 0
  - `cmd /c verify-go-semantic-projects.cmd` -> expected 18, mismatches 0

### Go slice: positive array return counterpart

- Added new positive project-aware semantic fixture:
  - `tests/language_modules/03_import_resolution/fixtures/valid/import_array_record_return/*`
- New coverage target:
  - direct `Array<imported Record, N>` return with nested `result[index].field` contract access over imported types.
- Added expected project semantic case in:
  - `tests/language_modules/expected_go_semantic_projects.json`
- Validation:
  - `cmd /c verify-go-semantic-projects.cmd` -> expected 19, mismatches 0
  - `cmd /c verify-go-project-semantic-diagnostics.cmd` -> expected 14, mismatches 0

### Compare-IR V1 enrichment (forward-driven)

- Upgraded compare-ir profile to V1 on both exporters.
  - Python compare-ir default profile is now `v1` (`fh-compare-ir-v1`), with optional `--profile v0` fallback.
  - Go compare-ir now supports `--profile v0|v1` and defaults to `v1`.
- Go exporter now emits enriched V1 fields (module node, contracts, contract_bindings, typed params/fields, type base_type metadata).
- compare-ir sample generator now requests V1 profile explicitly for Python and Go export paths.
- Validation:
  - `cmd /c compare-ir-compiler-v1.cmd` generates all compiler_v1 Python+Go IR files successfully.
  - Generated files use `schema: fh-compare-ir-v1` on both sides.

### Compare-IR V1 parity closeout

- Closed the Go Compare-IR V1 parity slice against Python's enriched V1 output.
- Key Go exporter fixes:
  - Preserve empty arrays instead of `null` for V1 lists.
  - Preserve record literal source argument order.
  - Emit source and analysis record field type metadata.
  - Emit abort contract `kind` and `error_ref` metadata.
  - Wrap V1 `contracts.requires` / `contracts.ensures` as `ContractClause` entries while keeping top-level clauses raw.
  - Disable Go JSON HTML escaping and preserve decimal literal spelling for byte-stable hashes.
  - Limit analysis routines to the entry module and include imported type/record/error closure for cross-module type composition.
  - Export `result`, `value`, and `error` identifiers as normal `VarExpr` nodes; V1 binding semantics remain in `contract_bindings`.
- Validation:
  - `cmd /c "cd /d go-frontend && gofmt -w internal\semantic\compare_ir.go && go test ./..."` passed.
  - `cmd /c compare-ir-compiler-v1.cmd` passed with hash parity:
    - total samples: 18
    - matching samples: 15
    - mismatching samples: 0
    - skipped samples: 3

### Go codegen language-module validity fix

- Investigated invalid generated Go programs under `tests/language_modules/**/expected_go`.
- Root cause: Freehold allows unused `let` bindings, but generated Go must mark otherwise-unused locals as used.
- Updated Python Go codegen to emit `_ = <local>` for unused `let` bindings.
- Updated affected expected Go goldens:
  - `tests/language_modules/06_arrays/expected_go/array_literal.go`
  - `tests/language_modules/06_arrays/expected_go/empty_array_literal.go`
  - `tests/language_modules/11_errors_results/expected_go/result_let_from_function.go`
  - `tests/language_modules/11_errors_results/expected_go/result_array_ok_payload.go`
- Validation:
  - `python .\tools\generate_go_codegen_artifacts.py` -> total cases 94, matching Go 94, mismatching Go 0.
  - `cmd /c generate-go-codegen-artifacts.cmd` -> all cases OK in additive mode.
  - `cmd /c "cd /d go-frontend && go test ./..."` passed.
  - Standalone compile scan of 84 `expected_go` files found 0 non-import failures.

### Compiler V1 verification demo: abort propagation runtime log

- Added positive compiler V1 demo `16_abort_propagation_runtime_log` for aborting cross-module calls in a runtime-log path.
- Extended Go codegen so aborting `let` call bindings propagate `err`, aborting procedures return `nil` on normal fallthrough, and generated executables support `Main() error`.
- Registered the demo in `tools/verify_compiler_examples.py` and documented it in `TEST-NEXT.md`.
- Validation:
  - `cmd /c verify-compiler-examples.cmd` passed.
  - Demo 16 passed frontend verification, Go project codegen, package build, package runtime-log check, and executable runtime-log check.

### Compiler V1 verification demo map + gap demos

- Mapped the current compiler V1 smoke set in `TEST-NEXT.md` and corrected the positive-example list for demos 13 through 18.
- Added focused positive demo `17_record_mutation_runtime_log`:
  - covers record field mutation (`record.field := ...`) in the runtime path;
  - covers String runtime usage inside a field assignment;
  - validates both package runtime-log and executable runtime-log output.
- Added focused positive demo `18_result_error_branch_runtime_log`:
  - covers the normal `Result` error branch without abort propagation;
  - covers direct comparison against an imported error constant;
  - validates package and executable runtime-log output.
- Extended Go codegen expression rendering so imported error constants are emitted with their imported Go package alias.
- Validation:
  - `python -m freehold verify .\examples\compiler_v1\17_record_mutation_runtime_log\App\Main.fh` passed.
  - `python -m freehold verify .\examples\compiler_v1\18_result_error_branch_runtime_log\App\Main.fh` passed.
  - `cmd /c verify-compiler-examples.cmd` passed.

### Compare-IR Stage 1 manifest hardening

- Hardened `artifacts/fhir-samples/compiler_v1/manifest.json` with an explicit Stage-1 policy:
  - active samples: 15
  - skipped samples: `unsupported_async_scope_runtime`, `unsupported_generic_function`, `unsupported_grpc_binding`
  - sample growth is opt-in only, so new runtime demos such as 16/17/18 are not pulled into Stage 1 implicitly.
- Added manifest policy validation to both Compare-IR tools:
  - `tools/generate_compare_ir_samples.py`
  - `tools/compare_ir_hashes.py`
- Validation:
  - `cmd /c compare-ir-compiler-v1.cmd` passed with 18 total, 15 matching, 0 mismatching, 3 skipped.

### Compare-IR Stage 1 non-mutating gate

- Changed `compare-ir-compiler-v1.cmd` to check-only mode:
  - generated Python/Go IR goes to `%TEMP%`, not `artifacts/`;
  - generated Python IR is compared against generated Go IR;
  - generated Python IR is compared against the frozen Python baseline;
  - generated Go IR is compared against the frozen Go baseline.
- Added explicit baseline writer `compare-ir-compiler-v1-update.cmd` for intentional Stage-1 baseline updates.
- Documented the check/update split in `TEST-NEXT.md`.
- Validation:
  - `cmd /c compare-ir-compiler-v1.cmd` passed in check-only mode with all three comparisons green: 18 total, 15 matching, 0 mismatching, 3 skipped.

### Compare-IR Stage 1 acceptance run

- Ran the non-mutating Stage-1 gate:
  - `cmd /c compare-ir-compiler-v1.cmd`
- Stable sample counts across all three checks:
  - generated Python IR vs generated Go IR: 18 total, 15 matching, 0 mismatching, 3 skipped
  - frozen Python baseline vs generated Python IR: 18 total, 15 matching, 0 mismatching, 3 skipped
  - frozen Go baseline vs generated Go IR: 18 total, 15 matching, 0 mismatching, 3 skipped
- The 3 skipped samples are deliberate Stage-1 skips, fixed by manifest policy and marked `unsupported by IR export`:
  - `unsupported_async_scope_runtime`
  - `unsupported_generic_function`
  - `unsupported_grpc_binding`
- Result: Stage 1 remains stable as a watcher; no baseline update command was used.

### Compare-IR Stage 2 planning decision

- Decided not to fold the 3 deliberate Stage-1 skips back into Stage 1.
- Added `OPEN-COMPARE-IR-STAGE2.md` as the follow-up plan for:
  - `unsupported_generic_function`
  - `unsupported_async_scope_runtime`
  - `unsupported_grpc_binding`
- Stage-2 rule: use a separate manifest/gate, keep non-mutating check default, and require an explicit update command for any Stage-2 baselines.
- Updated `TEST-NEXT.md` with the Stage-1/Stage-2 split.

### IR Stage 2 sample expansion

- Confirmed Stage 1 before expansion:
  - `cmd /c compare-ir-compiler-v1.cmd` passed with 18 total, 15 matching, 0 mismatching, 3 skipped across all Stage-1 checks.
- Reviewed the generic Compare-IR sample generator/comparator and kept Stage 2 separated by manifest/command rather than changing Stage 1.
- Added Stage-2 Compare-IR sample manifest for demos 16, 17 and 18:
  - `artifacts/fhir-samples/compiler_v1_stage2/manifest.json`
  - active samples: 3
  - skipped samples: 0
- Added Stage-2 commands:
  - `compare-ir-compiler-v1-stage2.cmd` for non-mutating check-only generated Python/Go parity
  - `compare-ir-compiler-v1-stage2-update.cmd` for explicit Stage-2 baseline writes
- Closed two Go frontend gaps found by the new samples:
  - parser accepts `error` as a field member after `.`, matching Result `.error` usage;
  - semantic analyzer tracks error symbols separately and accepts imported error constants in expressions.
- Validation:
  - `cmd /c compare-ir-compiler-v1-stage2.cmd` passed: 3 total, 3 matching, 0 mismatching, 0 skipped.
  - `cmd /c compare-ir-compiler-v1.cmd` still passed: 18 total, 15 matching, 0 mismatching, 3 skipped across all Stage-1 checks.
  - `cmd /c "cd /d D:\works\Work-VeraFlow\freehold\go-frontend && go test ./..."` passed.
