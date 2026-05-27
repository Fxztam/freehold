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

### EBNF rule comparison tool

- Added `tools/compare_ebnf_rules.py` to compare `freehold.generated.ebnf` against `freehold.dhparser.ebnf` on rule-set and normalized rule-body level.
- The tool writes a JSON report under `.tmp/ebnf-rule-compare/` and supports `--strict` for unexpected deltas.
- Current intentional deltas are allowlisted:
  - generated-only ISO/token helper rules such as `DIGIT`, `LETTER`, `TYPE_ARG_START`, string/comment character helpers;
  - DHParser-only parser helpers `EOF`, `FIELD_PATH`, `member_name`, `postfix`, `postfix_expr`, `primary`;
  - known body differences for DHParser postfix handling, regex tokens, whitespace markers, expression associativity spelling, and type argument spelling.
- Validation:
  - `python .\tools\compare_ebnf_rules.py --strict --out .tmp\ebnf-rule-compare\strict-report.json` passed with 97 generated rules, 85 DHParser rules, 79 common rules, 0 unexpected generated-only, 0 unexpected DHParser-only, 0 unexpected body diffs.

### Compare-IR coverage matrix

- Added `COMPARE-IR-COVERAGE-MATRIX.md` as a compact feature/sample/IR-node coverage map for compiler V1 Compare-IR.
- Matrix covers Stage 1 samples `01` through `15` and Stage 2 samples `16` through `18`.
- Feature rows include Records, Arrays, Result success/error, Abort contracts, Requires/ensures, Imports/exposed symbols, Qualified calls, Runtime calls, Control-flow if/while/case, Mutation/field assignment, Error constants, cross-module type composition, and name conflicts.
- Added a gap section for Generics, Async/Scope runtime, gRPC bindings, and broader abort handling.

### Compare-IR Stage 2 enrichment sample selection

- Marked Stage-2 demos 16, 17 and 18 as deliberate enrichment samples in `artifacts/fhir-samples/compiler_v1_stage2/manifest.json`.
- Added explicit selection reasons:
  - `16_abort_propagation_runtime_log`: aborting call propagation and `Main() error` surface.
  - `17_record_mutation_runtime_log`: assignment and field assignment surface.
  - `18_result_error_branch_runtime_log`: Result error branch and imported error constant surface.
- Updated `OPEN-COMPARE-IR-STAGE2.md` and `COMPARE-IR-COVERAGE-MATRIX.md` so Stage 2 is documented as intentional enrichment, not blind demo growth.

### Compare-IR readable mismatch diffs

- Enhanced `tools/compare_ir_hashes.py` so hash mismatches include the first differing JSON path.
- The mismatch report now records compact Python/Go values, the first differing JSON path, and up to 5 path-based differences per mismatch by default.
- Difference reason codes include `value_mismatch`, `type_mismatch`, `missing_in_python`, `missing_in_go`, `list_length_mismatch`, parse errors, and byte-only JSON hash differences.
- Added sorted mismatch output in `_mismatches.json`, richer `_mismatches.txt`, and optional console output via `--compact-mismatches`.
- Validation passed:
  - `python -m py_compile tools\compare_ir_hashes.py`
  - `cmd /c compare-ir-compiler-v1-stage2.cmd`
  - Temporary mismatch smoke test reported first difference `$.root.items[1].value` with Python value `2` and Go value `3`, plus a compact path-diff list including `$.root.status`.

### Compare-IR Stage 2 semantic field priority

- Added `--comparison semantic` to `tools/compare_ir_hashes.py`.
- Stage 2 now compares a compiler-contract projection instead of treating every AST-adjacent JSON detail as equally important.
- The semantic projection prioritizes import closure, routine signatures, contracts and bindings, abort effects, result payload/error shape, control-flow skeleton, and mutation targets.
- Updated `compare-ir-compiler-v1-stage2.cmd` to run semantic comparison and the full JSON hash comparison in parallel.
- Documented the policy in `OPEN-COMPARE-IR-STAGE2.md`, `COMPARE-IR-COVERAGE-MATRIX.md`, and the Stage-2 manifest.
- Validation passed:
  - `python -m py_compile tools\compare_ir_hashes.py`
  - `cmd /c compare-ir-compiler-v1-stage2.cmd` with semantic comparison and parallel full JSON hash comparison; both reported 3 matching, 0 mismatching, 0 skipped.
  - `cmd /c compare-ir-compiler-v1.cmd`
  - Semantic smoke test ignored source-span-only differences and reported a routine signature mismatch at `$.module.declarations[0].return_type.name`.

### Go/Python Compare-IR mismatch status

- Re-ran `cmd /c compare-ir-compiler-v1-stage2.cmd` after restoring the parallel full hash check.
- Stage 2 now reports 0 mismatches in both comparison modes:
  - semantic compiler-contract projection: 3 matching, 0 mismatching, 0 skipped.
  - full JSON hash: 3 matching, 0 mismatching, 0 skipped.
- Re-ran `cmd /c compare-ir-compiler-v1.cmd` for Stage 1 regression coverage.
- Stage 1 remains green across generated parity and both frozen baseline checks: 18 total, 15 matching, 0 mismatching, 3 skipped.
- No additional Go/Python IR changes were required because the current comparer and frontend outputs already converge to 0 mismatches.

### Language modules 02 test branch

- Added a second language-module test branch at `tests/language_modules_02`.
- Added initial `01_core` smoke module with `valid/minimal_module_02.fh` and a manifest-owned valid verification case.
- Added branch-local docs and metadata:
  - `tests/language_modules_02/README.md`
  - `tests/language_modules_02/positive_feature_matrix.json`
  - `tests/language_modules_02/expected_semantic_diagnostics.json`
- Extended `python -m freehold test-language` with `--root` so the stable `tests/language_modules` tree and the new `tests/language_modules_02` tree can run through the same runner.
- Extended `tools/test_steps.py` with `--language-root` for targeted test-step runs against the second branch.
- Added wrappers:
  - `tests/language_modules_02/01_core/test.cmd`
  - `tests/language_modules_02/01_core/test.ps1`
  - `compare-semantic-diagnostics-02.cmd`
  - `dhparser-parse-tests-language-modules-02.cmd`
- Validation passed:
  - `python -m py_compile freehold\tests\language_runner.py freehold\cli\main.py tools\test_steps.py`
  - `python -m freehold test-language --root tests\language_modules_02`
  - `python -m freehold test-language --module 01_core`
  - `cmd /c compare-semantic-diagnostics-02.cmd`
  - `cmd /c tests\language_modules_02\01_core\test.cmd`
  - `cmd /c dhparser-parse-tests-language-modules-02.cmd`
  - `python tools\test_steps.py 01_core --language-root tests\language_modules_02 --quick --no-demos`

### Language modules 02 package import

- Copied the package README to the repository root as `README.md`.
- Extracted `files-V2.zip` and the nested `freehold-tests-split.zip` package into a temporary import area.
- Imported the package into `tests/language_modules_02` using the requested numbered module layout:
  - `00_support`
  - `01_lex` through `17_stdlib_args`
- Split `_pos.fh` files into `valid/*_pos.fh` cases with `expected_ast` targets.
- Split `_neg.fh` files into one invalid case per embedded module, using `invalid_syntax` for `[FAIL SYN]` and `invalid_semantics` for the other annotated fail types.
- Generated expected artifacts with `python -m freehold test-language --root tests\language_modules_02 --update --json-summary .tmp\language_modules_02_summary.json`.
- Re-ran only this branch without update: `python -m freehold test-language --root tests\language_modules_02 --json-summary .tmp\language_modules_02_summary_no_update.json`.
- Current imported status:
  - 94 total cases.
  - 79 passing cases.
  - 15 failing positive package cases.
  - 3 expected AST files generated.
  - 76 expected error files generated.
- Package-count note: root `README.md` lists 75 negative cases, but the package source contains 76 `[FAIL ...]` modules; `14_control_flow` has 8 negative modules while the README table lists 7.

### Language modules 02 positive multi-module split

- Split `_pos` multi-module files for:
  - `tests/language_modules_02/02_module/valid/mod_pos.fh`
  - `tests/language_modules_02/03_imports/valid/imp_pos.fh`
- Replaced each aggregate positive case with one `valid/*.fh` case per embedded module and separate `expected_ast/*.ast.json` targets.
- Updated manifests for `02_module` and `03_imports`.
- Validation passed for `02_module`: 5/5.
- Validation for `03_imports` improved to 6/7; the remaining positive failure is `Test.Imp.Pos.Exposed`, which still needs project/support import resolution for `Point`.
- Re-ran only `tests/language_modules_02`: 84/98 passing, 14 failing.
- Expected artifacts now include 8 AST files and 76 error files.

### Language modules 02 Test.Support project resolution

- Solved the remaining `03_imports` support-resolution failure by adding resolver-backed valid cases.
- Extended `valid` language-runner cases so they can optionally use `root` and `entry` while still comparing an `expected_ast` for the resolved entry module.
- Added a branch-local project fixture for `03_imports`:
  - `tests/language_modules_02/03_imports/fixtures/valid/support_imports/Test/Support.fh`
  - `tests/language_modules_02/03_imports/fixtures/valid/support_imports/Test/Imp/Pos/Simple.fh`
  - `tests/language_modules_02/03_imports/fixtures/valid/support_imports/Test/Imp/Pos/Exposed.fh`
  - `tests/language_modules_02/03_imports/fixtures/valid/support_imports/Test/Imp/Pos/Multi.fh`
- Updated `03_imports` manifest to run the three positive import cases through project resolution.
- Adjusted branch-local `Test.Support` to use `amount` instead of the reserved keyword `value`.
- Validation passed:
  - `python -m py_compile freehold\tests\language_runner.py`
  - `python -m freehold test-language --root tests\language_modules_02 --module 00_support --update --json-summary .tmp\language_modules_02_00_support_update.json`
  - `python -m freehold test-language --root tests\language_modules_02 --module 03_imports --update --json-summary .tmp\language_modules_02_03_imports_project_update.json`
  - `python -m freehold test-language --root tests\language_modules_02 --json-summary .tmp\language_modules_02_summary_after_support_resolution.json`
- New status: 86/98 passing, 12 failing; `00_support` is 1/1 and `03_imports` is 7/7.
- Expected artifacts now include 10 AST files and 76 error files.

### General function ensures `value` binding

- Extended the language so `value` is available as a general function-ensures return binding:
  - for non-Result functions, `value` is an alias for the returned value;
  - for `Result<T,E>` functions, `value` remains the successful payload `T`;
  - `success`, `failure`, and `error` remain Result-only contract bindings;
  - `value` remains unavailable in `requires` and function bodies.
- Updated the Python verifier for scalar, field, and index access forms:
  - `ensures value = ...`
  - `ensures value.field = ...`
  - `ensures value[index] = ...`
- Updated Python FH-IR/FHIR metadata, Go frontend semantic contract env, Go Compare-IR contract binding metadata, and Python Go codegen ensures bindings.
- Added focused coverage in `tests/language_modules/13_contract_blocks`:
  - `valid/non_result_value_ensures.fh`
  - `invalid_semantics/requires_cannot_use_value.fh`
  - matching expected AST, Go, and semantic error artifacts.
- Updated compiler V1 Compare-IR baselines intentionally because `contract_bindings.value` is now available for non-Result functions.
- Validation passed:
  - `python -m py_compile freehold\core\verifier.py freehold\core\fhir.py freehold\core\go_codegen.py`
  - `python -m freehold test-language --module 13_contract_blocks --update --json-summary .tmp\language_13_contract_value_summary.json` -> 39/39
  - `python -m freehold test-language --json-summary .tmp\language_modules_summary_after_value_binding.json` -> 466/466
  - `cmd /c "cd /d D:\works\Work-VeraFlow\freehold\go-frontend && gofmt -w internal\semantic\analyzer.go internal\semantic\compare_ir.go && go test ./..."`
  - `cmd /c compare-ir-compiler-v1-update.cmd`
  - `cmd /c compare-ir-compiler-v1.cmd` -> Stage 1 green: 18 total, 15 matching, 0 mismatching, 3 skipped across generated parity and both frozen baselines.
- Package branch impact:
  - `05_generics` no longer fails on `ensures value...`.
  - The positive generics case now reaches the next independent issue: `plain function must return expression` at `return ok [...]` for a plain Array return.
  - Overall `tests/language_modules_02` remains 86/98, with the failure reason in `05_generics` advanced to the next compatibility point.

### Language modules 02 shared support project fixture

- Added a shared resolver-backed project fixture for branch-02 package positives that import `Test.Support`:
  - `tests/language_modules_02/fixtures/support_project/Test/Support.fh`
  - `tests/language_modules_02/fixtures/support_project/Test/Requires/Pos.fh`
  - `tests/language_modules_02/fixtures/support_project/Test/Ensures/Pos.fh`
  - `tests/language_modules_02/fixtures/support_project/Test/Aborts/Pos.fh`
  - `tests/language_modules_02/fixtures/support_project/Test/Control/Pos.fh`
- Switched positive cases in `09_requires`, `10_ensures`, `11_aborts`, and `14_control_flow` from isolated single-file validation to `root`/`entry` project validation.
- Validation results:
  - `09_requires`: 5/5
  - `11_aborts`: 5/5
  - `14_control_flow`: 9/9
  - `10_ensures`: advanced past `Test.Support` resolution and now fails on the independent `return ok [...]` vs plain Array-return question.
- Full branch status after this batch:
  - `python -m freehold test-language --root tests\language_modules_02 --json-summary .tmp\language_modules_02_summary_after_support_project_batch.json`
  - 89/98 passing, 9 failing.
  - Expected artifacts: 13 AST files and 76 error files.

### Language modules 02 package `ok` normalization

- Chose package normalization instead of extending `ok` as a general success wrapper:
  - `ok` remains Result-return syntax.
  - Plain Array returns now use `[a, b]` / `[a, b, c]` directly.
  - Array `let` initialization now uses a plain Array literal.
- Updated branch-02 positive package cases and shared fixtures:
  - `05_generics`: plain Array returns no longer use `ok`, and generic parameter `value` was renamed to `amount`.
  - `10_ensures`: plain Array returns no longer use `ok`.
  - `13_let_mutation`: Array `let` no longer uses `ok`; Result `let` now initializes from a Result-returning helper instead of `ok` as an expression.
- Added `Test/LetMut/Pos.fh` to the shared support project fixture and switched `13_let_mutation` to resolver-backed `root`/`entry` validation.
- Validation:
  - `python -m freehold test-language --root tests\language_modules_02`
  - New branch status: 92/98 passing, 6 failing.
  - Fully green after this batch: `05_generics`, `10_ensures`, `13_let_mutation`.

### Language modules 02 remaining 6 failure analysis

- Re-ran the branch-02 suite:
  - `python -m freehold test-language --root tests\language_modules_02 --json-summary .tmp\language_modules_02_remaining6_summary.json`
  - Status remains 92/98 passing, 6 failing.
- `07_procedures`: package uses trailing comma in zero-argument `Std.IO.logf` calls, e.g. `logf("Hello from procedure", )`. Current grammar requires `arg_list: call_arg ("," call_arg)*`, so this is a package normalization candidate.
- `17_stdlib_args`: same trailing-comma issue for `logf("Programm gestartet", )`; package normalization should be batched with `07_procedures`.
- `08_service_rpc`: package uses primitive RPC request types such as `rpc GetPoint(id: Integer): Point`. Current gRPC V1 policy requires declared record message types for unary request/response types, so this is a policy decision: either keep strict gRPC message records and adapt package, or intentionally extend service semantics.
- `12_result`: module name `Test.Result.Pos` uses reserved keyword `Result` as a module segment. This is a name-policy decision; simplest package adaptation is to rename the positive module path/entry to avoid `Result`.
- `15_scope_async`: grammar supports `async function` but not `async procedure`; the positive package also uses scope/spawn/join constructs. This is a larger language surface decision, not a tiny fixture cleanup.
- `16_expressions`: parameter declarations use `Array<Integer, 3>`, but grammar currently has `param: NAME ":" type_ref` and only `return_type`/`let` accept `array_type`. This is a coherent language-extension candidate because arrays already work in returns and lets.
- Recommended next order:
  - Batch 1: normalize trailing comma calls in `07_procedures` and `17_stdlib_args`.
  - Batch 2: decide/implement `Array<T,N>` in parameter type positions for `16_expressions`.
  - Batch 3: decide gRPC request/response policy for primitive request shorthands in `08_service_rpc`.
  - Batch 4: decide whether reserved keywords remain forbidden in module segments (`12_result`).
  - Batch 5: treat `async procedure`/scope runtime as a separate language feature slice (`15_scope_async`).

### Language modules 02 selected 4-fix batch

- Normalized trailing-comma `Std.IO.logf` package calls:
  - `07_procedures`: `Std.IO.logf("Hello from procedure", )` and `Std.IO.logf("done", )` now omit the trailing comma.
  - `17_stdlib_args`: `Std.IO.logf("Programm gestartet", )` now omits the trailing comma.
- Kept Result as a reserved name and renamed the positive Result package module from `Test.Result.Pos` to `Test.Results.Pos`.
- Added shared support-project fixture entries for the remaining support-dependent positives:
  - `Test/Procedures/Pos.fh`
  - `Test/Results/Pos.fh`
  - `Test/Expressions/Pos.fh`
  - `Test/Stdlib/Pos.fh`
- Switched `07_procedures`, `12_result`, `16_expressions`, and `17_stdlib_args` positive manifest cases to resolver-backed `root`/`entry` validation.
- Extended the Python grammar/parser/verifier path so `Array<T,N>` is accepted and type-checked in parameter positions while preserving the existing `Param.type_name` AST surface.
- Normalized newly exposed package-positive assumptions to current language semantics:
  - Result/status keywords remain contract-only; positive body locals now use plain booleans.
  - aborting calls must be propagated with `aborts`.
  - `Json.stringify` remains record-only; the stdlib positive now stringifies a `Point` record.
- Regenerated affected branch-02 AST goldens and `freehold.generated.ebnf`.
- Validation:
  - `python -m py_compile freehold\core\ast.py freehold\core\parser_legacy.py freehold\core\verifier.py freehold\core\interpreter.py` passed.
  - Targeted modules passed: `07_procedures` 4/4, `12_result` 5/5, `16_expressions` 7/7, `17_stdlib_args` 7/7.
  - Full branch-02 suite: `python -m freehold test-language --root tests\language_modules_02` -> 96/98.
  - Stable suite: `python -m freehold test-language` -> 466/466.
- Remaining branch-02 failures are now only:
  - `08_service_rpc`: primitive RPC request type shorthand versus strict record-message gRPC policy.
  - `15_scope_async`: `async procedure` grammar/language surface.

### Language modules 02 RPC package normalization

- Kept the existing gRPC V1 policy strict: unary RPC request and response types must be declared record-message types with `proto` field ids.
- Normalized `08_service_rpc` positive package coverage from primitive request shorthands and `Result<...>` responses to explicit message records:
  - request records: `PointRequest`, `PrefixRequest`, `ValueRequest`, `CreatePointRequest`;
  - response records: `PointMessage`, `LabeledMessage`, `CountLabelsResponse`, `SafePointResponse`.
- Avoided reserved field names in gRPC response messages (`success_flag`, `error_text` instead of `ok`, `error`).
- Added the resolver-backed fixture entry:
  - `tests/language_modules_02/fixtures/support_project/Test/Service/Pos.fh`
- Switched `08_service_rpc` positive manifest case to shared support-project `root`/`entry` validation.
- Regenerated the `08_service_rpc` expected AST golden.
- Validation:
  - `python -m freehold test-language --root tests\language_modules_02 --module 08_service_rpc` -> 5/5.
  - `python -m freehold test-language --root tests\language_modules_02` -> 97/98.
  - `python -m freehold test-language` -> 466/466.
- Intermediate remaining branch-02 failure before the later async/scope slice:
  - `15_scope_async`: unsupported `async procedure` grammar/language surface at that point.

### Rules/diagnostics/control-flow follow-up after RPC normalization

- Checked whether the RPC normalization and Array-parameter grammar extension require follow-up in `spec/freehold.rules`, `spec/freehold.diag`, or `spec/analyzer.cflow`.
- Result: no functional rules/diagnostics/control-flow spec changes are needed for the RPC package fix.
  - gRPC V1 strict record-message policy is already covered by `FH-GRPC-4403`, `FH-GRPC-4404`, and `FH-GRPC-4406`.
  - The positive RPC package was adapted to that policy instead of changing semantics.
  - `analyzer.cflow` is unaffected because RPC message record declarations do not change routine/control-flow behavior.
- Array parameters are covered by the executable grammar change and existing type/argument diagnostics; no new diagnostic code is needed.
- Validation:
  - `verify-spec-diagnostics.cmd` -> Failures: 0.
  - `compare-semantic-diagnostics.cmd` -> 99/99 matching semantic diagnostics.
  - `verify-grammar-consistency.cmd` -> Mismatches: 0.

### Async/scope remaining slice sizing

- Inspected the remaining `15_scope_async` branch-02 positive case against the existing stable `23_concurrency` implementation.
- Existing stable support already covers `async function`, `await`, `ScopeStmt`, `JoinHandle<T>`, `scope.spawn<T>`, `scope.join<T>`, scope lifetime diagnostics, AST export, verifier semantics, and cflow spec notes.
- The branch-02 positive file is not just missing parser support for `async procedure`; it also uses older shorthand/style forms:
  - `async procedure ...` while grammar currently only permits `async function ...`;
  - old trailing-comma `Std.IO.logf("...", )` calls;
  - `scope(n, 42)` / `scope(n)` as Integer-returning expression shorthands, while current stable semantics uses `scope()` returning `Scope`;
  - `.spawn` / `.join` as value-like member access, while current stable semantics uses typed calls such as `request_scope.spawn<T>(awaitable)` and `await request_scope.join<T>(handle)`.
- Size estimate:
  - Small parser-only patch if we only accept `async procedure` syntax and keep semantics otherwise unchanged.
  - Medium, low-risk package-normalization slice if `15_scope_async` is adapted to the already-stable `23_concurrency` surface and goldens are regenerated.
  - Large language-design slice only if the old shorthand forms (`scope(args)` as Integer and `.spawn`/`.join` field-like access) should become official semantics.

### Language modules 02 async/scope medium slice

- Chose the medium solution for the remaining async problem: keep the existing stable `23_concurrency` semantics and normalize the branch-02 package to that surface.
- Added `async procedure` syntax support in the executable grammar and inline grammar.
- Updated the parser so both async functions and async procedures set `RoutineDecl.is_async`.
- Normalized `15_scope_async` positive coverage:
  - removed old trailing-comma `Std.IO.logf("...", )` calls;
  - replaced old `scope(args)` integer shorthand with `scope()` returning `Scope`;
  - replaced `.spawn` / `.join` value-like member access with typed `Scope` calls such as `worker.spawn<Integer>(...)` and `await worker.join<Integer>(...)`;
  - avoided the reserved local name `value` by using `joined_value`.
- Kept the old shorthand forms out of the language for now; no new runtime/control-flow model was introduced.
- Broadened the await-context diagnostic wording from async function to async routine while preserving the existing `VF-ASY001` / `FH-CON-3101` compatibility path.
- Regenerated:
  - `freehold/grammar/freehold.generated.ebnf`;
  - `tests/language_modules_02/15_scope_async/expected_ast/scope_pos.ast.json`.
- Validation:
  - `python -m freehold test-language --root tests\language_modules_02 --module 15_scope_async` -> 4/4.
  - `python -m freehold test-language --root tests\language_modules_02` -> 98/98.
  - `python -m freehold test-language --module 23_concurrency` -> 20/20.
  - `python -m freehold test-language` -> 466/466.
  - `verify-spec-diagnostics.cmd` -> Failures: 0.
  - `compare-semantic-diagnostics.cmd` -> 99/99 matching semantic diagnostics.
  - `verify-grammar-consistency.cmd` -> Mismatches: 0.
- Branch-02 imported package suite is now fully green.

## Unsupported compiler-v1 demo check after RPC/Async work

- Checked `examples/compiler_v1/unsupported/async_scope_runtime/App/Main.fh` and `examples/compiler_v1/unsupported/grpc_binding/App/Main.fh` after the branch-02 RPC and async/scope fixes.
- `verify-compiler-examples.cmd` still passes and still expects both demos to report `FH-GOCODEGEN-0001` in the general Go codegen path.
- `async_scope_runtime` now verifies successfully in the frontend/verifier, but `go-codegen-project` exits with `1`; `.tmp/probe_async_scope.json` has `supported: false` with `FH-GOCODEGEN-0001` diagnostics: `async routines are not supported by Go codegen V1`.
- `grpc_binding` now verifies successfully in the frontend/verifier, but general `go-codegen-project` exits with `1`; `.tmp/probe_grpc_binding.json` has `supported: false` with `FH-GOCODEGEN-0001`: `declaration not supported by Go codegen V1`.
- Dedicated gRPC generation is working: `python -m freehold grpc-go-bindings examples\compiler_v1\unsupported\grpc_binding\App\Main.fh --output .tmp\probe_grpc_binding_exit.go` exits with `0` and generates the Go binding wrapper.

## Go-codegen support for async_scope_runtime and grpc_binding demos

- Solved both previously unsupported compiler-v1 demos in the general `go-codegen-project` path.
- `async_scope_runtime`:
  - Go codegen now accepts async routines and lowers them synchronously for V1.
  - `await` is transparent in the generated Go expression path.
  - `Scope` lowers to `FreeholdScope`; `JoinHandle<T>` lowers to `FreeholdJoinHandle[T]`; `scope` blocks and `scope.spawn<T>`/`scope.join<T>` lower to structured sequential Go code.
- `grpc_binding`:
  - `ServiceDecl` is no longer a general Go-codegen unsupported declaration.
  - Project codegen emits extra gRPC Go files for service modules: a minimal `pb` stub package plus the existing unary server binding wrapper.
  - gRPC projects add `google.golang.org/grpc v1.64.0` to `go.mod` and run `go mod tidy` in generated `build.cmd` before `go test ./...`.
- Promoted the two demos in `tools/verify_compiler_examples.py`:
  - `19_async_scope_runtime` is now a supported compiler example.
  - `20_grpc_binding` is now a supported compiler example.
- Kept `old_concurrent_grpc_channel_demo` unsupported because channels remain outside Go-codegen V1; Channel/Sender/Receiver now report structured `FH-GOCODEGEN-0001` diagnostics instead of aborting before project JSON is written.
- Updated `tests/language_modules/go_codegen_feature_matrix.json`: `23_concurrency` is now supported for async/await/scope/JoinHandle lowering, with channels and scheduler-backed async runtime still deferred.
- Validation:
  - Direct `go-codegen-project` probe for `async_scope_runtime` -> exit 0; generated Go project build -> exit 0.
  - Direct `go-codegen-project` probe for `grpc_binding` -> exit 0; generated Go project build -> exit 0.
  - `verify-compiler-examples.cmd` -> passed.
  - `python -m freehold test-language --module 23_concurrency` -> 20/20.
  - `python -m freehold test-language --module 24_grpc_idl` -> 10/10.
  - `verify-go-feature-matrix.cmd` -> Mismatches: 0.
  - `python -m freehold test-language --root tests\language_modules_02` -> 98/98.
  - `python -m freehold test-language` -> 466/466.

## Go-codegen channel runtime wrapper slice

- Added Go-codegen support for existing frontend channel syntax and semantics.
- `Channel<T>`, `Sender<T>`, and `Receiver<T>` now lower to small Go wrapper types over native `chan T`:
  - `FreeholdChannel[T]` owns `chan T`;
  - `FreeholdSender[T]` and `FreeholdReceiver[T]` expose send/receive endpoints.
- Added lowering for channel runtime calls:
  - `channel<T>(capacity)` -> `make(chan T, int(capacity))` inside `FreeholdChannel[T]`;
  - `channel_sender<T>(channel)` -> `FreeholdSender[T]`;
  - `channel_receiver<T>(channel)` -> `FreeholdReceiver[T]`;
  - `channel_send<T>(sender, value)` -> blocking Go send returning `true`;
  - `channel_receive<T>(receiver)` -> blocking Go receive.
- Promoted `examples/concurrent_grpc_channel_demo.fh` to supported compiler example `21_concurrent_grpc_channel_demo`; it now verifies, codegens, emits gRPC project extras, and builds.
- Updated `tests/language_modules/go_codegen_feature_matrix.json`: `23_concurrency` now lists channel endpoints and awaitable send/receive as supported Go-codegen cases; scheduler-backed async runtime remains deferred.
- Validation:
  - Direct `go-codegen` probe for `channel_endpoints.fh` -> exit 0.
  - Direct `go-codegen` probe for `await_channel_send_receive.fh` -> exit 0.
  - Direct `go-codegen-project` probe for `examples/concurrent_grpc_channel_demo.fh` -> exit 0; generated Go project build -> exit 0.
  - `verify-compiler-examples.cmd` -> passed; includes `21_concurrent_grpc_channel_demo`.
  - `python -m freehold test-language --module 23_concurrency` -> 20/20.
  - `verify-go-feature-matrix.cmd` -> Mismatches: 0.
  - `python -m freehold test-language` -> 466/466.
  - `python -m freehold test-language --root tests\language_modules_02` -> 98/98.

## Full test pass after compiler-v1 19/20/21 promotion

- Ran the broad Freehold verification set after promoting the solved demos to numbered compiler-v1 examples.
- Results:
  - `fhtest.cmd` -> exit 0; CLI smoke, core language module, full regression suite, hello run, and demo verifies all passed.
  - `verify-compiler-examples.cmd` -> exit 0; compiler example smoke passed.
  - `compare-ir-compiler-v1.cmd` -> exit 0; 15 matching, 0 mismatching, 3 skipped.
  - `compare-ir-compiler-v1-stage2.cmd` -> exit 0; 3 generated, 0 skipped, Python/Go export failures 0.
  - `verify-go-feature-matrix.cmd` -> exit 0; Mismatches: 0.
  - `verify-spec-diagnostics.cmd` -> exit 0; Failures: 0.
  - `compare-semantic-diagnostics.cmd` -> exit 0; 99 matching, 0 mismatching.
  - `verify-grammar-consistency.cmd` -> exit 0; Mismatches: 0.
  - `python -m freehold test-language` -> exit 0; 466/466.
  - `python -m freehold test-language --root tests\language_modules_02` -> exit 0; 98/98.

## Stage-2 Compare-IR status review

- Reviewed `compare-ir-compiler-v1-stage2.cmd`, `artifacts/fhir-samples/compiler_v1_stage2/manifest.json`, and the three active Stage-2 samples.
- Current Stage-2 mode is baseline-free check-only: it generates Python IR and Go IR into a temporary directory, then compares them directly using both semantic compiler-contract projection and full JSON hash.
- Active samples:
  - `16_abort_propagation_runtime_log` for abort propagation and Main error surface.
  - `17_record_mutation_runtime_log` for assignment and field assignment surface.
  - `18_result_error_branch_runtime_log` for Result error branch and imported error constant surface.
- There is currently no `artifacts/compare-ir/compiler_v1_stage2` frozen baseline directory; that matches the Stage-2 command design.
- Semantic projection currently covers module/import shape, declarations, routine signatures, `is_async`, contracts/bindings, statement skeletons, mutation targets, result/abort/control-flow values, and strips source-location noise. Unknown declaration kinds currently collapse to `{kind, name}`.
- Validation:
  - `compare-ir-compiler-v1-stage2.cmd` -> exit 0.
  - Semantic comparison -> 3 matching, 0 mismatching, 0 skipped.
  - Full JSON comparison -> 3 matching, 0 mismatching, 0 skipped.

## Promoted solved compiler-v1 demos to 19/20/21

- Moved the solved compiler-v1 demos out of `unsupported` and into numbered compiler examples:
  - `examples/compiler_v1/19_async_scope_runtime/App/Main.fh`.
  - `examples/compiler_v1/20_grpc_binding/App/Main.fh`.
  - `examples/compiler_v1/21_concurrent_grpc_channel_demo/App/Main.fh`.
- Updated `tools/verify_compiler_examples.py` so 19/20/21 are supported compiler examples at their new paths.
- `examples/compiler_v1/unsupported` now keeps only the still unsupported generic-function demo.
- Updated `artifacts/fhir-samples/compiler_v1/manifest.json` so skipped IR entries for 19/20 point at the new numbered paths while the frozen Stage-1 IR baseline scope stays unchanged.
- Validation:
  - Direct verify for 19/20/21 at the new paths -> exit 0 for each.
  - `verify-compiler-examples.cmd` -> passed; includes 19/20/21 as supported and only `unsupported_generic_function` as unsupported.
  - `compare-ir-compiler-v1.cmd` -> exit 0; generated/frozen parity still 15 matching, 0 mismatching, 3 skipped.
  - `verify-go-feature-matrix.cmd` -> Mismatches: 0.
  - `python -m freehold test-language` -> 466/466.
  - `python -m freehold test-language --root tests\language_modules_02` -> 98/98.

## Stage-2 Go project contract gate

- Added a Stage-2 contract gate for Go project codegen structure, focused on the newly solved compiler-v1 surfaces.
- New tool: `tools/verify_stage2_go_project_contracts.py`.
  - Reads `go_project_contracts` from `artifacts/fhir-samples/compiler_v1_stage2/manifest.json`.
  - Generates Go projects in memory using the normal project codegen path.
  - Verifies project shape without adding large Go source baselines: module path, supported flag, file/build/extra-file counts, expected output paths, build-file kinds, extra-file kinds, and required snippets in generated source/content.
  - Writes check reports under the requested report root (`_all.json`, `_summary.json`, `_failures.txt`).
- Wired the contract gate into:
  - `compare-ir-compiler-v1-stage2.cmd` after semantic/full IR parity.
  - `compare-ir-compiler-v1-stage2-update.cmd` so baseline-update runs also include the contract report.
- Added three manifest contracts:
  - `19_async_scope_runtime_project`: verifies async/scope/JoinHandle lowering and no gRPC extras.
  - `20_grpc_binding_project`: verifies gRPC pb stub, binding wrapper, `google.golang.org/grpc` dependency, and `go mod tidy` build command.
  - `21_concurrent_grpc_channel_demo_project`: verifies combined gRPC extras, Scope/JoinHandle lowering, Channel/Sender/Receiver wrappers, channel send/receive helpers, and endpoint construction.
- Validation:
  - `python -m py_compile tools\verify_stage2_go_project_contracts.py` -> exit 0.
  - `python tools\verify_stage2_go_project_contracts.py --manifest .\artifacts\fhir-samples\compiler_v1_stage2\manifest.json --out .tmp\stage2-go-project-contracts` -> 3/3 matching, exit 0.
  - `compare-ir-compiler-v1-stage2.cmd` -> exit 0; semantic 3/3, full JSON 3/3, Go project contracts 3/3.
  - `verify-compiler-examples.cmd` -> exit 0.
  - `verify-go-feature-matrix.cmd` -> Mismatches: 0.

## Stage-2 IR promotion for compiler-v1 19/20/21

- Checked whether the solved compiler-v1 examples 19/20/21 can become active Stage-2 Compare-IR samples.
- Initial probe:
  - Python Compare-IR exported all three samples.
  - Go Compare-IR exported `20_grpc_binding` immediately.
  - Go Compare-IR initially rejected `19_async_scope_runtime` and `21_concurrent_grpc_channel_demo` because the project qualified-call pass treated `request_scope.spawn` / `quote_scope.spawn` as unknown module-qualified routines.
- Fixed the Go frontend Compare-IR path:
  - `go-frontend/internal/semantic/project.go` now skips Scope runtime method calls (`*.spawn`, `*.join`) in the project-level qualified-call module diagnostic pass.
  - `go-frontend/internal/semantic/compare_ir.go` now exports generic type refs as `GenericTypeName` with `args`/`text`, record field `proto_id`, and RPC request/response `type_repr` fields so Python and Go IR stay full-JSON aligned for async/channel/gRPC surfaces.
- Promoted these active Stage-2 IR samples in `artifacts/fhir-samples/compiler_v1_stage2/manifest.json`:
  - `19_async_scope_runtime` for async routine surface plus Scope spawn/join and JoinHandle type refs.
  - `20_grpc_binding` for gRPC service declaration, proto field ids, and RPC request/response type refs.
  - `21_concurrent_grpc_channel_demo` for combined gRPC IDL, async Scope/JoinHandle, and Channel/Sender/Receiver generic type refs.
- Stage-2 IR policy now has 6 active samples and 0 skipped samples.
- Validation:
  - `go test ./...` under `go-frontend` -> exit 0.
  - Temporary 19/20/21 Python-vs-Go IR probe -> semantic 3/3, full JSON 3/3.
  - `compare-ir-compiler-v1-stage2.cmd` -> exit 0; generated 6, skipped 0, semantic 6/6, full JSON 6/6, Go project contracts 3/3.
  - `compare-ir-compiler-v1.cmd` -> exit 0; Stage-1 remains 15 matching, 0 mismatching, 3 skipped.
  - `verify-go-semantic-projects.cmd` -> Mismatches: 0.
  - `verify-go-project-semantic-diagnostics.cmd` -> Mismatches: 0.
  - `verify-parser-conformance.cmd` was also tried before the FH-IR baseline update; it failed at its existing `Compare FH-IR` baseline step with 18 FH-IR mismatches, outside the Stage-2 Compare-IR path.

## FH-IR baseline update after parser-conformance failure

- Investigated the remaining `verify-parser-conformance.cmd` failure at step `[18/22] Compare FH-IR`.
- Root cause:
  - `16_abort_propagation_runtime_log` through `21_concurrent_grpc_channel_demo` were now supported compiler examples, but had no committed FH-IR baselines in `artifacts/fhir` or `artifacts/fhir-v1`.
  - Existing baseline diffs were consistent with the current exporter typing contract `value` bindings correctly instead of leaving them unavailable/Void.
- Updated module-v0 FH-IR baselines in `artifacts/fhir`:
  - Added new baselines for compiler-v1 16/17/18/19/20/21.
  - Refreshed existing baselines whose contract `value` binding surface changed.
- Updated project-v1 FH-IR baselines in `artifacts/fhir-v1`:
  - Added new baselines for compiler-v1 16/17/18/19/20/21.
  - Refreshed existing baselines affected by the same contract binding/export surface.
- Validation:
  - `cmd /c compare-fhir.cmd` -> exit 0; module-v0 32/32 matching, 0 mismatching.
  - `cmd /c compare-fhir-v1.cmd` -> exit 0; project-v1 32/32 matching, 0 mismatching.
  - `cmd /c verify-parser-conformance.cmd` now passes both FH-IR steps: module-v0 32/32, determinism 6/6, language modules 10/10, project-v1 32/32.
  - The full parser-conformance run now reaches `[21/22] Verify additive test line` and stops there because the baseline update intentionally modifies existing protected artifact files in the working tree. This is expected until the baseline diff is reviewed/committed.
- Cleanup:
  - Removed two unrelated Go-codegen artifacts generated by the full conformance run: `artifacts/go-codegen/13_contract_blocks/valid/non_result_value_ensures.go` and `.json`.
