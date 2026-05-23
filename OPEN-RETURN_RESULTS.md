# Open Return Results

This document captures the open design surface for Freehold `Result<T, E>` return behavior.

## Current Status

`Result<T, E>` already exists as a regular value-level result type.

It is not an abort mechanism.

```fh
error NotFound

function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

```fh
error NotFound

function load() returns Result<Integer, NotFound>
is
    return error NotFound
end load
```

Both are normal function returns.

## Current Syntax

Current result type shape:

```fh
Result<OkTypeName, ErrorTypeName>
```

Both type arguments are currently simple names.

Important current limitation:

```text
The current grammar does not yet allow structured type expressions inside Result<..., ...>.
```

Accepted:

```fh
Result<Integer, NotFound>
Result<Boolean, PermissionDenied>
Result<String, ValidationError>
Result<Account, NotFound>
Result<Money, Overdraft>
```

Not currently accepted:

```fh
Result<Array<Integer, 3>, NotFound>
Result<Result<Integer, NotFound>, OtherError>
Result<Integer, Array<Error, 3>>
```

This is a grammar/type-expression limitation, not a conceptual rejection of arrays as successful Result values.

## Current Return Rules

For a `Result<T, E>` function:

```fh
return ok expr
return error ErrorName
```

are valid return forms.

Plain return is invalid:

```fh
return 1
```

For a plain non-Result function, `return ok ...` and `return error ...` are invalid.

## Current Type Checks

The verifier checks:

```text
Result ok expression must match the ok type.
Returned error must be declared.
Returned error must match the Result error type.
Result functions must return ok or error.
Plain functions must return a plain expression.
Result values can be assigned only to compatible Result types.
```

Example invalid return:

```fh
error NotFound
error PermissionDenied

function load() returns Result<Integer, NotFound>
is
    return error PermissionDenied
end load
```

Expected diagnostic direction:

```text
FOUND => PermissionDenied
EXPECTED => NotFound
```

## Result Is Not Abort

`return error E` is still a normal function return.

It differs from abort:

```text
return error E
    Returns a value of type Result<T, E>.
    Caller receives a value.

abort E
    Leaves normal control flow.
    Caller receives no normal result unless it handles or propagates the abort.
```

The abort design is tracked separately in:

```text
OPEN-ABORT_HANDLING.md
```

## Result Contracts

Result-returning functions can use special result contract expressions in `ensures`.

Current examples:

```fh
function load() returns Result<Integer, NotFound>
ensures value >= 0
ensures error = NotFound or success
is
    return ok 1
end load
```

Current special expressions:

```text
success  Boolean
failure  Boolean
value    OkTypeName
error    ErrorTypeName
```

Open issue:

```text
value.field is not yet parseable when value is a record.
```

The positive matrix tracks this as a known gap.

## Open Design Questions

### Structured Result Payloads

Should Freehold allow structured ok payloads such as arrays?

```fh
Result<Array<Integer, 3>, NotFound>
```

Yes. This is conceptually desirable, but it requires widening the grammar from:

```text
Result<type_ref, type_ref>
```

to a nested value-type expression grammar.

Fixed v1 direction:

```text
Allow Array<T, N> as a future Result ok type once value-type expressions are supported.
Keep Result error type as a declared error name.
Forbid nested Result in v1.
```

### Result Ok Type Expression

The successful side of `Result<T, E>` should eventually accept the same value types that ordinary variables, parameters, and return values can use.

Recommended direction:

```text
Result ok type should be a full value type expression.
Result error type should remain a declared error name in v1.
```

Future valid examples:

```fh
Result<Array<Integer, 3>, NotFound>
Result<Array<String, 10>, ValidationError>
Result<Person, NotFound>
Result<AccountBalance, Overdraft>
```

This enables functions to return successful arrays and records without losing the explicit error channel:

```fh
error NotFound

function load_scores() returns Result<Array<Integer, 3>, NotFound>
is
    return ok scores
end load_scores
```

The `ok` expression must match the complete ok type:

```text
FOUND => Array<Boolean, 3>
EXPECTED => Array<Integer, 3>
```

### Result Error Type Constraint

The error side should stay narrow at first.

Recommended v1 rule:

```text
The E in Result<T, E> must name a declared error.
It must not be an Array, record, String, Integer, or nested Result.
```

Rejected examples:

```fh
Result<Integer, Array<Error, 3>>
Result<Integer, String>
Result<Integer, Result<String, ParseError>>
```

Reason:

```text
Result errors are part of the declared failure vocabulary.
They should remain comparable with return error ErrorName and contract expressions using error.
```

Payload-bearing errors can be considered later, but they should be designed explicitly rather than smuggled through the `E` type slot.

### Nested Result Values

Nested Result values are technically possible but are forbidden in v1:

```fh
Result<Result<Integer, NotFound>, OtherError>
```

This means that the successful side of an outer `Result` is another `Result`:

```text
Outer Result:
    ok    => inner Result<Integer, NotFound>
    error => OtherError

Inner Result:
    ok    => Integer
    error => NotFound
```

Such a function has three observable states:

```text
outer error OtherError
outer ok + inner error NotFound
outer ok + inner ok Integer
```

Example:

```fh
error NotFound
error NetworkError

function load_value() returns Result<Result<Integer, NotFound>, NetworkError>
is
    ...
end load_value
```

The main problem is contract readability. For a simple `Result<Integer, NotFound>`, the contract atoms are clear:

```text
success => an Integer value exists
failure => a NotFound error exists
value   => Integer
error   => NotFound
```

For `Result<Result<Integer, NotFound>, NetworkError>`, `success` only means that the outer result is ok. The `value` is then not an `Integer`; it is another `Result<Integer, NotFound>`.

That makes contracts awkward:

```fh
ensures success implies value >= 0
```

is no longer valid, because `value` is not the final integer value.

It would require a nested contract shape such as:

```fh
ensures success implies value.success
ensures success and value.success implies value.value >= 0
```

This is too complex for v1 and weakens the intended clarity of `success`, `failure`, `value`, and `error`.

Fixed v1 rule:

```text
Do not allow Result as the ok type of another Result.
```

The reason for this rule is semantic clarity:

```text
success, failure, value, and error must always refer to exactly one Result layer.
```

Reason:

```text
Nested Result makes success/failure interpretation harder.
It creates two independent failure layers.
It complicates contract expressions such as success, failure, value, and error.
```

If a function can fail for multiple reasons, prefer future explicit error sets or error families instead of nested Result.

Potential future alternatives:

```fh
Result<Integer, NotFound | NetworkError>
```

or:

```fh
error LoadError is
    NotFound
    NetworkError
end LoadError

function load_value() returns Result<Integer, LoadError>
is
    ...
end load_value
```

These alternatives keep one Result layer:

```text
ok Integer
error NotFound or NetworkError
```

instead of:

```text
ok (ok Integer or error NotFound)
error NetworkError
```

### Result Value Field Access

For record ok values, contracts should eventually allow field access from `value`:

```fh
record Person
is
    name: String
    age: Integer
end Person

error NotFound

function load_person() returns Result<Person, NotFound>
ensures success implies value.age >= 0
is
    return ok person
end load_person
```

Current gap:

```text
value.field is not yet parseable because value is a special result-contract atom, not a normal field-access root.
```

Recommended direction:

```text
Allow value.field when the Result ok type is a record.
Reject value.field when the Result ok type is not a record.
Type-check value.field against the record field type.
```

### Multiple Error Types

Current `Result<T, E>` has a single error type name.

Potential future forms:

```fh
Result<Account, NotFound | PermissionDenied>
Result<Account, ErrorSet>
```

This is open. The current language can model multiple error outcomes with declared error families later, but this should not be rushed.

### Unwrapping And Propagation

Current callers receive `Result` as a value. There is no built-in `try`, `?`, or pattern match syntax.

Open future designs:

```fh
let account: Account = try load(id)
let account: Account = load(id)?
case outcome is
    when success => ...
    when failure => ...
end case
```

Any such feature must remain explicit and should not be confused with abort propagation.

## Diagnostics

Current semantic diagnostics already cover result issues through legacy `VF-ER*` names and are normalized by the semantic diagnostics gate.

Suggested stable range:

```text
FH-RES-4100..4199  Result return diagnostics
```

Suggested diagnostics:

```text
FH-RES-4101 unknown result error type
FH-RES-4102 unknown returned error
FH-RES-4103 wrong result error return
FH-RES-4104 Result function must return ok or error
FH-RES-4105 plain function cannot return ok or error
FH-RES-4106 Result ok type mismatch
FH-RES-4107 nested Result payload not supported
FH-RES-4108 Result value field access not supported
FH-RES-4109 Result ok type expression not supported
FH-RES-4110 Result error type must be declared error
FH-RES-4111 Result value field does not exist
FH-RES-4112 Result value field access requires record ok type
```

## Positive Matrix Targets

Already covered:

```text
result_ok_return
result_error_return
result_let_from_function
result_assignment_from_function
result_value_ensures
result_status_ensures
```

Open matrix targets:

```text
function_returning_result_record
function_returning_result_array once Result ok type expressions are supported
function_returning_result_array_ok_type_mismatch
function_returning_result_nested_result_rejected
function_returning_result_error_array_rejected
contract_uses_result_value_field once value.field is supported
contract_uses_result_value_field_unknown_field
contract_uses_result_value_field_on_scalar_rejected
qualified_result_call_assignment
result_return_inside_case_branches
```

## Summary Rules

```text
Result<T, E> is value-level success/failure.
return ok expr returns a success value.
return error E returns a failure value.
return error E is not abort E.
Current Result type arguments are simple names.
Result ok type should later allow full value type expressions such as Array<T, N> and records.
Result error type should remain a declared error name in v1.
Nested Result payloads are forbidden in v1 so that success, failure, value, and error remain unambiguous.
value.field contracts should be added for record ok values.
```
