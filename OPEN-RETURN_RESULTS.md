# Open Return Results

This document captures the V1 design status and remaining post-V1 design surface for Freehold `Result<T, E>` return behavior.

## V1 Closure Status

Status: V1 accepted and conformance-checked on 2026-05-23.

V1 is now closed around this scope:

```text
Result<T, E> is a value-level success/failure return type.
return ok expr and return error ErrorName are the only Result return forms.
The ok side supports simple value type names and Array<T, N> payloads.
The error side is a declared error name.
Nested Result ok payloads are forbidden.
Result contract atoms success, failure, value, and error refer to one Result layer.
```

The accepted V1 test/conformance package includes:

```text
result_ok_return
result_error_return
result_let_from_function
result_assignment_from_function
result_value_ensures
result_status_ensures
function_returning_result_array
nested_result_payload_not_supported
```

Latest validated gate baseline:

```text
11_errors_results module:       14/14
Semantic diagnostics:           62/62
Spec diagnostics:               87/87 emits, 60 semantic codes, 64 CODE_MAP entries
Parser conformance corpus:      270 total, 227 OK, 43 expected FAIL
Parser status parity:           270/270
AST shape parity:               227/227
Semantic AST parity:            227/227
```

Post-V1 remains intentionally open for richer result ergonomics such as multiple error types and explicit unwrapping/propagation syntax. `value.field` for record ok payloads is part of the V1 surface.

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
Result<OkTypeName, ErrorName>
```

The error side is currently a declared error name. The ok side accepts a simple value type name or an Array payload.

Accepted:

```fh
Result<Integer, NotFound>
Result<Boolean, PermissionDenied>
Result<String, ValidationError>
Result<Account, NotFound>
Result<Money, Overdraft>
Result<Array<Integer, 3>, NotFound>
```

Not currently accepted:

```fh
Result<Result<Integer, NotFound>, OtherError>
Result<Integer, Array<Error, 3>>
```

Nested Result payloads are forbidden in V1, and the error side remains a declared error name.

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

V1 field access:

```text
value.field is parseable and type-checked when value is a record ok payload.
```

The positive matrix tracks this with Result value-field contract coverage.

## V1 Scope And Post-V1 Questions

### Structured Result Payloads

Freehold V1 allows structured Array ok payloads:

```fh
Result<Array<Integer, 3>, NotFound>
```

This was accepted by widening the grammar from:

```text
Result<type_ref, type_ref>
```

to a nested value-type expression grammar.

Fixed v1 direction:

```text
Allow Array<T, N> as a Result ok type.
Keep Result error type as a declared error name.
Forbid nested Result in v1.
```

### Result Ok Type Expression

The successful side of `Result<T, E>` now accepts simple value type names and `Array<T, N>` payloads.

V1 rule:

```text
Result ok type may be a simple value type name or Array<T, N>.
Result error type should remain a declared error name in v1.
```

V1 valid examples:

```fh
Result<Array<Integer, 3>, NotFound>
Result<Array<String, 10>, ValidationError>
Result<Person, NotFound>
Result<AccountBalance, Overdraft>
```

Post-V1 may generalize this further so the ok side accepts the same complete value type expression surface as ordinary variables, parameters, and return values.

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

The error side stays narrow in V1.

V1 rule:

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

For record ok values, contracts allow field access from `value`:

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

V1 decision:

```text
Allow value.field when the Result ok type is a record.
Reject value.field when the Result ok type is not a record.
Type-check value.field against the record field type.
For imported record ok payloads, use the same transitive imported record type context as ordinary imported record field access.
```

### Multiple Error Types

Current `Result<T, E>` has a single error type name.

Potential future forms:

```fh
Result<Account, NotFound | PermissionDenied>
Result<Account, ErrorSet>
```

This remains post-V1. The current language can model multiple error outcomes with declared error families later, but this should not be rushed.

### Unwrapping And Propagation

Current callers receive `Result` as a value. There is no built-in `try`, `?`, or pattern match syntax.

Post-V1 design candidates:

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
FH-RES-4109 Result ok type expression not supported
FH-RES-4110 Result error type must be declared error
FH-RES-4111 Result value field does not exist
FH-RES-4112 Result value field access requires record ok type
```

## Coverage Matrix Status

Covered in V1 or current conformance gates:

```text
result_ok_return
result_error_return
result_let_from_function
result_assignment_from_function
result_value_ensures
result_value_field_ensures
result_status_ensures
function_returning_result_array
nested_result_payload_not_supported
```

Post-V1 matrix targets:

```text
function_returning_result_record
contract_uses_result_value_field_unknown_field
contract_uses_result_value_field_on_scalar_rejected
qualified_result_call_assignment
result_return_inside_case_branches
```

Additional V1 hardening candidates can still be added as diagnostics-focused negatives, but they do not change the accepted V1 surface.

## Summary Rules

```text
Result<T, E> is value-level success/failure.
return ok expr returns a success value.
return error E returns a failure value.
return error E is not abort E.
Result ok type supports simple value type names and Array<T, N> payloads.
Result ok type supports record field access through value.field contracts.
Result error type should remain a declared error name in v1.
Nested Result payloads are forbidden in v1 so that success, failure, value, and error remain unambiguous.
value.field contracts are allowed for record ok values.
```
