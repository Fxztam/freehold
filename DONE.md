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
