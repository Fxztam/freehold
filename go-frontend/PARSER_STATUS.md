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
OK:    226
FAIL:  12
```

The remaining 12 failures are currently all `invalid_syntax` cases that the parser is expected to reject.

## Important DHParser Comparison Note

The current Go parser accepts keywords in name positions syntactically, so cases such as `module module`, `type module is Integer`, `let module: Integer = 0`, and `procedure return()` produce AST JSON and are left for semantic checking.

This is provisional.

Before treating this behavior as final, compare the Go AST results with the DHParser AST/error results for the same keyword-as-name tests. If DHParser reports these cases as parse errors instead of semantic errors, revert or tighten the Go parser's keyword-as-name handling so the parsers agree.

Relevant implementation area:

- `internal/parser/parser.go`: `parseName()` and `isKeywordName()`

## Current Failure Set

The expected parser failures at this checkpoint are:

```text
01_core invalid_syntax empty_file.fh
01_core invalid_syntax missing_module_end.fh
01_core invalid_syntax missing_module_name.fh
01_core invalid_syntax unknown_top_level_token.fh
02_import invalid_syntax missing_exposing_list.fh
02_import invalid_syntax missing_import_name.fh
09_statements invalid_syntax let_uses_assignment_operator.fh
13_contract_blocks invalid_syntax ensures_before_requires.fh
14_comments_whitespace invalid_syntax nested_block_comment.fh
14_comments_whitespace invalid_syntax unterminated_block_comment.fh
16_control_flow_edges invalid_syntax case_without_default.fh
16_control_flow_edges invalid_syntax while_without_invariant.fh
```

## Modules Covered

Modules 01 through 19 have been exercised by the Go parser harness. Modules 13 through 19 valid and invalid_semantics cases parse successfully at this checkpoint.