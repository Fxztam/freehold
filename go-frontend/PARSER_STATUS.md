# Freehold Go Parser Status

Date: 2026-05-21

## Structured parser diagnostics

The Go parser emits structured diagnostics for all parse errors.

- **Catalog:** `internal/diagnostic/catalog.go`
- **Examples:** `../../artifacts/go-ast/*/*.json`

Every new error class gets a stable code and catalog entry.

## Current Harness Baseline

Full parser conformance verify from the repository root:

```powershell
.\verify-parser-conformance.cmd
```

This command runs the complete chain: Go-AST regeneration, expected Go diagnostic verification, semantic-rule diagnostic spec verification, semantic/type diagnostic comparison, DHParser-AST regeneration, parse-status comparison, parse-error diagnostic comparison, AST-shape comparison, semantic AST comparison, and `go test ./...`.

Command:

```powershell
cd go-frontend
.\go-parse-tests-language-modules.cmd
```

The wrapper writes repository-local artifacts to:

```text
artifacts/go-ast/<module>/<case>/<source>.json
```

Latest artifact generation produced 279 JSON files across the 21 numbered language-module directories currently present in `tests/language_modules` (`01` through `21`).

Baseline:

```text
Total: 279
OK:    236
FAIL:  43
```

The parser now rejects reserved keywords in name positions. This intentionally moves the keyword-as-name cases from semantic acceptance back to syntax rejection, matching the DHParser direction.

## Important DHParser Comparison Note

DHParser rejects keyword-as-name cases syntactically. The Go parser has been tightened to the same policy: `parseName()` accepts only `Ident` tokens, and the lexer reserves `true`, `false`, `success`, `failure`, and `value` in addition to the statement/type keywords.

Relevant implementation area:

- `internal/parser/parser.go`: `parseName()` and keyword atom handling in `parseAtom()`
- `internal/lexer/lexer.go`: keyword classification
- `internal/token/token.go`: reserved keyword tokens

The DHParser artifact path now starts at:

```powershell
.\dhparser-parse-tests-language-modules.cmd
```

It writes:

```text
artifacts/dhparser-ast/<module>/<case>/<source>.json
artifacts/dhparser-ast/_summary.json
artifacts/dhparser-ast/_errors.txt
```

Initial DHParser bootstrap baseline:

```text
Total: 279
OK:    236
FAIL:  43
```

The DHParser EBNF now uses a postfix expression rule and orders identifier matching before reserved expression literals such as `value`. This prevents identifiers like `values` from being consumed as the literal prefix `value`.

The first comparison stage is parse-status parity:

```powershell
.\compare-parser-status.cmd
```

It writes:

```text
artifacts/compare-parse-status/_summary.json
artifacts/compare-parse-status/_all.json
artifacts/compare-parse-status/_mismatches.txt
```

Current parse-status comparison:

```text
Total cases:        279
Matching status:    279
Mismatching status: 0
Missing Go:         0
Missing DHParser:   0
Go:                 OK 236 / FAIL 43
DHParser:           OK 236 / FAIL 43
```

The parse error diagnostic comparison is:

```powershell
.\compare-parse-errors.cmd
```

It compares the 43 shared failures and records whether Go and DHParser report the same source location. The diagnostic comparison is intentionally reported separately from parse-status parity, because DHParser error wording exposes grammar internals. Go parser artifacts now include a structured `diagnostic` object with code, message, location, expected tokens, found token, and hint.

The diagnostic report now carries provisional Freehold diagnostic codes. Syntax/parser diagnostics use `FH-SYN-0001..0999`; semantic, type, abort, contract, and bootstrap/tooling diagnostics use `FH-SEM-1000..1999`, `FH-TYP-2000..2999`, `FH-ABT-3000..3999`, `FH-CON-3000..3999`, and `FH-BLD-9000..9999`.

Current parse-error diagnostic comparison:

```text
Shared failures:               43
Matching failure locations:    40
Mismatching failure locations: 3
Status mismatches:             0
```

The three current location differences are expected diagnostic boundary cases: empty input without a DHParser source location, a one-column token-boundary difference for `:=`, and a number-literal boundary difference for invalid decimal syntax.

The semantic/type diagnostic comparison is:

```powershell
.\compare-semantic-diagnostics.cmd
```

It verifies expected semantic and type diagnostics from `tests/language_modules/expected_semantic_diagnostics.json` against the Python verifier's structured diagnostics. The report writes:

```text
artifacts/compare-semantic-diagnostics/_summary.json
artifacts/compare-semantic-diagnostics/_all.json
artifacts/compare-semantic-diagnostics/_mismatches.txt
```

The semantic/type diagnostic manifest reserves stable Freehold codes in the `FH-SEM-1000..1999` and `FH-TYP-2000..2999` ranges while retaining the previous Python diagnostic code as `legacy_code` for traceability.

Current semantic/type diagnostic comparison:

```text
Expected semantic diagnostics:    68
Matching semantic diagnostics:    68
Mismatching semantic diagnostics: 0
```

The semantic-rule diagnostic spec verification is:

```powershell
.\verify-spec-diagnostics.cmd
```

It verifies that `spec/freehold.rules`, `spec/freehold.diag`, the expected syntax/semantic diagnostic manifests, and the semantic diagnostic normalizer's `CODE_MAP` stay aligned.

Current spec diagnostic verification:

```text
Diagnostic specs:        91
Rule emits:              91
Expected syntax codes:   19
Expected semantic codes: 64
CODE_MAP entries:        68
Failures:                0
```

Positive feature-matrix coverage is tracked in:

```text
tests/language_modules/positive_feature_matrix.json
```

The first matrix wave adds valid interaction cases for multiple while invariants with a variant, case branches returning record values, record-field contracts, qualified calls inside contracts, comma-separated `requires`/`ensures`, declared abort paths, abort call propagation, positional and named string templates, string templates inside `Std.IO.logf`, string templates inside record literals, Big number calls inside expressions, `Json.stringify` on record values, and `Result<Array<...>, E>` ok payloads. `value.field` in Result ensures remains recorded as a known grammar gap rather than a green positive case.

The first AST-shape comparison stage is:

```powershell
.\compare-ast-shape.cmd
```

It compares the 236 files that both parsers accept after normalizing DHParser CST nodes and Go AST nodes into module/declaration/statement/expression outlines.

Current AST-shape comparison:

```text
Comparable parse-ok cases: 236
Matching shape:            236
Mismatching shape:         0
```

The semantic AST comparison stage is:

```powershell
.\compare-ast-semantic.cmd
```

It compares the same 236 accepted files after normalizing expressions into typed semantic nodes rather than canonical expression text.

Current semantic AST comparison:

```text
Comparable parse-ok cases:    236
Matching semantic AST:        236
Mismatching semantic AST:     0
```

## Current Failure Set

The expected parser failures at this checkpoint are:

```text
01_core invalid_syntax empty_file.fh
01_core invalid_syntax missing_module_end.fh
01_core invalid_syntax missing_module_name.fh
01_core invalid_syntax unknown_top_level_token.fh
01_core invalid_semantics keyword_module_name.fh
02_import invalid_syntax bad_import_then_valid_procedure.fh
02_import invalid_syntax missing_exposing_list.fh
02_import invalid_syntax missing_import_name.fh
02_import invalid_semantics keyword_exposing_symbol.fh
02_import invalid_semantics keyword_import_module_name.fh
04_types invalid_semantics keyword_local_name.fh
04_types invalid_semantics keyword_parameter_name.fh
04_types invalid_semantics keyword_record_field_name.fh
04_types invalid_semantics keyword_type_name.fh
04_types invalid_semantics unknown_let_type.fh
04_types invalid_semantics unknown_parameter_type.fh
05_records invalid_semantics keyword_record_field.fh
05_records invalid_semantics keyword_record_name.fh
08_routines invalid_semantics keyword_function_name.fh
08_routines invalid_semantics keyword_parameter_name.fh
08_routines invalid_semantics keyword_procedure_name.fh
08_routines invalid_syntax error_after_valid_declaration.fh
09_statements invalid_syntax bad_statement_then_following_statement.fh
09_statements invalid_syntax let_uses_assignment_operator.fh
09_statements invalid_syntax multiple_errors_in_one_file.fh
11_errors_results invalid_semantics keyword_error_name.fh
12_type_conflicts invalid_semantics parameter_alias_mismatch.fh
13_contract_blocks invalid_syntax ensures_before_requires.fh
14_comments_whitespace invalid_syntax nested_block_comment.fh
14_comments_whitespace invalid_syntax unterminated_block_comment.fh
16_control_flow_edges invalid_syntax case_without_default.fh
16_control_flow_edges invalid_syntax error_inside_nested_block.fh
16_control_flow_edges invalid_syntax while_without_invariant.fh
```

## Recovery and Multi-Diagnostics

The recovery-oriented syntax cases are now part of the normal conformance corpus:

```text
02_import invalid_syntax bad_import_then_valid_procedure.fh
08_routines invalid_syntax error_after_valid_declaration.fh
09_statements invalid_syntax bad_statement_then_following_statement.fh
09_statements invalid_syntax multiple_errors_in_one_file.fh
16_control_flow_edges invalid_syntax error_inside_nested_block.fh
```

Go parser artifacts now include `diagnostics[]` while keeping the singular `diagnostic` field as a compatibility alias for the first diagnostic. The parser collects diagnostics internally and recovers at declaration boundaries (`import`, `type`, `error`, `function`, `procedure`) and statement boundaries (`let`, `return`, `check`, `call`, identifier-led statements, `if`, `while`, `case`) while respecting block sentinels (`else`, `when`, `default`, `end`). Top-level recovery only treats `end <module-name>` as the module boundary, so failed routine bodies do not accidentally terminate module parsing at `end <routine-name>`.

`tests/language_modules/expected_diagnostics.json` still checks first diagnostics for the existing negative corpus and can also check complete `diagnostics[]` sequences. Checked multi-diagnostic contracts currently cover declaration recovery, statement-list recovery, repeated statement recovery, and nested-block recovery:

```text
08_routines invalid_syntax error_after_valid_declaration.fh
09_statements invalid_syntax bad_statement_then_following_statement.fh
09_statements invalid_syntax multiple_errors_in_one_file.fh
16_control_flow_edges invalid_syntax error_inside_nested_block.fh
```

## Modules Covered

Modules 01 through 19 have been exercised by the Go parser harness. The remaining Go failures are expected syntax rejections or keyword-as-name rejections at this checkpoint.
