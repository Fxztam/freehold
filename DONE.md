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
