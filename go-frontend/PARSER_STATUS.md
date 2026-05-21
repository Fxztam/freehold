# Freehold Go Parser Status

Date: 2026-05-21

## Current Harness Baseline

Command:

```powershell
cd go-frontend
.\go-parse-tests-language-modules.cmd
```

The wrapper writes repository-local artifacts to:

```text
artifacts/go-ast/<module>/<case>/<source>.json
```

Latest artifact generation produced 238 JSON files across the 18 numbered language-module directories currently present in `tests/language_modules` (`01`, `02`, `04` through `19`; no `03_*` module exists in the current corpus).

Baseline:

```text
Total: 238
OK:    210
FAIL:  28
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
Total: 238
OK:    210
FAIL:  28
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
Total cases:        238
Matching status:    238
Mismatching status: 0
Missing Go:         0
Missing DHParser:   0
Go:                 OK 210 / FAIL 28
DHParser:           OK 210 / FAIL 28
```

The first AST-shape comparison stage is:

```powershell
.\compare-ast-shape.cmd
```

It compares the 210 files that both parsers accept after normalizing DHParser CST nodes and Go AST nodes into module/declaration/statement/expression outlines.

Current AST-shape comparison:

```text
Comparable parse-ok cases: 210
Matching shape:            210
Mismatching shape:         0
```

## Current Failure Set

The expected parser failures at this checkpoint are:

```text
01_core invalid_syntax empty_file.fh
01_core invalid_syntax missing_module_end.fh
01_core invalid_syntax missing_module_name.fh
01_core invalid_syntax unknown_top_level_token.fh
01_core invalid_semantics keyword_module_name.fh
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
09_statements invalid_syntax let_uses_assignment_operator.fh
11_errors_results invalid_semantics keyword_error_name.fh
12_type_conflicts invalid_semantics parameter_alias_mismatch.fh
13_contract_blocks invalid_syntax ensures_before_requires.fh
14_comments_whitespace invalid_syntax nested_block_comment.fh
14_comments_whitespace invalid_syntax unterminated_block_comment.fh
16_control_flow_edges invalid_syntax case_without_default.fh
16_control_flow_edges invalid_syntax while_without_invariant.fh
```

## Modules Covered

Modules 01 through 19 have been exercised by the Go parser harness. The remaining Go failures are expected syntax rejections or keyword-as-name rejections at this checkpoint.