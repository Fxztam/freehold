# Language Modules 02

Second language-module test branch for opt-in growth of new conformance slices.

The original `tests/language_modules` tree remains the stable broad suite. This tree contains the imported pos/neg package split from the root `README.md` package description.

Current imported status:

```text
Total: 98
Passed: 92
Failed: 6
Expected AST files: 13
Expected error files: 76
```

Update note:

- `02_module` and `03_imports` positive package files were split into one valid case per embedded module.
- `02_module` is now fully green.
- `03_imports` now runs its positive import cases through a resolver-backed fixture with `Test.Support` and is fully green.
- `09_requires`, `10_ensures`, `11_aborts`, `13_let_mutation`, and `14_control_flow` now run their support-dependent positive cases through the shared resolver-backed fixture `fixtures/support_project` and are fully green.
- The branch-local `Test.Support` fixture uses `amount` instead of `value`, because `value` remains a reserved contract binding name and is not allowed as a record field or parameter name.
- General function `ensures value...` is now supported in the main language.
- Package positives were normalized so `ok` remains Result-return syntax only; plain Array returns and Array lets now use plain Array literals. This made `05_generics`, `10_ensures`, and `13_let_mutation` fully green.
- Remaining positive failures are now concentrated in: trailing comma calls (`07_procedures`, `17_stdlib_args`), primitive RPC request type (`08_service_rpc`), reserved module segment `Result` (`12_result`), unsupported `async procedure` (`15_scope_async`), and `Array<Integer, 3>` parameter type syntax (`16_expressions`).

The package README table lists 75 negative cases, but the imported source contains 76 `[FAIL ...]` modules. The additional case is in `14_control_flow`, where `test-14-control_neg.fh` contains 8 failure modules while the table lists 7.

Run all modules in this branch:

```text
python -m freehold test-language --root tests/language_modules_02
```

Run one module:

```text
python -m freehold test-language --root tests/language_modules_02 --module 01_lex
```