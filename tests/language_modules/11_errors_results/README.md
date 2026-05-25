# 11_errors_results

Error declarations and Result return semantics are tested together because `error Name` declarations become the error side of `Result<T, E>`.

This section covers declared errors, `return ok`, `return error`, Result-typed local variables, Result `value.field` access, name conflicts, unknown error references, and Result return form mismatches.

Go codegen V1 policy:

```text
Result<T, E> values are emitted as Go structs with Ok, Value, and Error fields
covered Result.value.field expressions are emitted as Value.<Field> chains
```

Initial diagnostics:

```text
VF-N001 duplicate top-level declaration name
VF-N002 reserved keyword cannot be used as name
VF-ER001 unknown result error type
VF-ER002 unknown returned error
VF-ER003 wrong Result error return
VF-ER004 Result function must return ok or error
VF-ER005 plain function cannot return ok or error
VF-ER006 Result ok type mismatch
```
