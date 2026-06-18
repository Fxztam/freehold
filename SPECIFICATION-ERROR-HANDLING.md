# Freehold Specification: Error Handling
**Status:** Baseline error, result, and abort model  
**Audience:** Freehold authors, verifier implementers, conformance-test writers, and backend authors

This document explains how Freehold represents and verifies errors. Freehold has two related but distinct mechanisms:

```text
Result<T,E>     expected failure as a typed return value
abort / aborts  exceptional control-flow exit declared in the contract
```

Use `Result<T,E>` when failure is part of normal program logic. Use `abort` when the routine does not produce a normal return value on that path.

---

## 1. Error Declarations

Errors are declared at module level:

```freehold
module ErrorDeclaration

error NotFound
error InvalidInput
error Overflow

procedure main()
is
    check true
end main

end ErrorDeclaration
```

An error declaration introduces a named error type/value that can be used in `Result<T,E>`, `return error ErrorName`, `aborts ErrorName`, and `abort ErrorName`.

Error names should be stable domain names:

```freehold
error NotFound
error PermissionDenied
error ValidationError
error ExecutionError
```

Avoid generic names such as `Error` when the caller must decide what to do next.

---

## 2. Result Types

A `Result` return type has two type arguments:

```freehold
Result<SuccessType, ErrorType>
```

Example:

```freehold
error NotFound

function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

The first type is the success payload. The second type is the error that can be returned with `return error`.

---

## 3. Successful Result Return

Use `return ok expr` to return a successful payload:

```freehold
error NotFound

function ok_integer(n: Integer) returns Result<Integer, NotFound>
requires n >= 0
ensures success, value = n
is
    return ok n
end ok_integer
```

The expression after `ok` must match the success payload type.

For arrays:

```freehold
error NotFound

function ok_array(a: Integer, b: Integer) returns Result<Array<Integer, 2>, NotFound>
requires a >= 0, b >= 0
ensures success, value[0] = a, value[1] = b
is
    return ok [a, b]
end ok_array
```

For records:

```freehold
type Customer is record
    id: Integer
end record

error NotFound

function load_customer() returns Result<Customer, NotFound>
ensures success
ensures value.id = 1
is
    return ok Customer { id: 1 }
end load_customer
```

---

## 4. Error Result Return

Use `return error ErrorName` to return the error branch of a `Result<T,E>` function:

```freehold
error NotFound

function load_missing() returns Result<Integer, NotFound>
is
    return error NotFound
end load_missing
```

The returned error must be declared and must match the error type in `Result<T,E>`.

A conditional result-returning function:

```freehold
error NotFound

function fail_on_zero(n: Integer) returns Result<Integer, NotFound>
requires n >= 0
ensures error = NotFound or success
is
    if n = 0 then
        return error NotFound
    end if
    return ok n
end fail_on_zero
```

The function returns normally in both cases. The difference is whether the normal return value is an `ok` branch or an `error` branch.

---

## 5. Result Values at Call Sites

A result-returning function can be assigned to a `Result<T,E>` variable:

```freehold
error NotFound

function load() returns Result<Integer, NotFound>
is
    return ok 1
end load

procedure main()
is
    let outcome: Result<Integer, NotFound> = load()
    check true
end main
```

A caller can inspect result payload fields when the result is known to be successful by contract or by control-flow reasoning:

```freehold
type Address is record
    city_id: Integer
end record

type Customer is record
    id: Integer
    address: Address
end record

error NotFound

function load() returns Result<Customer, NotFound>
ensures result.ok
ensures result.value.id = 1
ensures result.value.address.city_id = 42
is
    return ok Customer { id: 1, address: Address { city_id: 42 } }
end load

procedure main()
is
    let loaded: Result<Customer, NotFound> = load()
    check loaded.value.id = 1
    check loaded.value.address.city_id = 42
end main
```

---

## 6. Result Contract Names

Inside postconditions for `Result<T,E>` functions, Freehold supports result-oriented names and accessors.

Common short forms:

```freehold
ensures success
ensures failure
ensures value = 1
ensures error = NotFound or success
```

Field and index access:

```freehold
ensures value.id = 1
ensures value.address.city_id = 42
ensures value[0] = a
ensures result.value.id = 1
ensures result.ok
```

Use these forms to document the relation between preconditions and result state:

```freehold
error NotFound

function load_one(found: Boolean) returns Result<Integer, NotFound>
requires found = true
ensures success
ensures value = 1
is
    return ok 1
end load_one
```

`success`, `failure`, `value`, and `error` are postcondition concepts for the returned result. They should not be used in `requires`, because no result exists before the routine is called.

---

## 7. Plain Return Versus Result Return

A plain function returns a plain expression:

```freehold
function add(a: Integer, b: Integer) returns Integer
is
    return a + b
end add
```

A `Result<T,E>` function returns either `ok` or `error`:

```freehold
function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

This is invalid:

```freehold
function load() returns Result<Integer, NotFound>
is
    return 1
end load
```

The raw `Integer` payload is not the same as `Result<Integer, NotFound>`.

---

## 8. Abort Declarations in Contracts

`aborts` declares that a routine may exit through an abort path:

```freehold
error NotFound

function lookup(id: Integer) returns String
requires id >= 0
aborts NotFound
ensures String.instr(result, "item") >= 0
is
    if id = 0 then
        abort NotFound
    end if
    return "item-found"
end lookup
```

The grammar allows an optional condition:

```freehold
aborts ErrorName when condition
```

Example:

```freehold
error Overflow

function divide(a: Integer, b: Integer) returns Integer
requires a >= 0
aborts Overflow when b = 0
ensures result >= 0
is
    if b = 0 then
        abort Overflow
    end if
    return a
end divide
```

The condition documents when the abort is allowed. The body must be consistent with the declared abort behavior.

---

## 9. Abort Statements

Use `abort ErrorName` to leave the routine through an abort path:

```freehold
error InvalidInput

function strict_lookup(id: Integer) returns String
requires id > 0
aborts InvalidInput when id > 1000
ensures String.instr(result, "id") >= 0
is
    if id > 1000 then
        abort InvalidInput
    end if
    return "id-ok"
end strict_lookup
```

An `abort` is not a `return error`. It does not construct a `Result<T,E>` value. It leaves the routine through the declared abort channel.

---

## 10. Result Versus Abort

Use `Result<T,E>` for expected, recoverable outcomes:

```freehold
error NotFound

function find(id: Integer) returns Result<String, NotFound>
requires id >= 0
ensures success or error = NotFound
is
    if id = 0 then
        return error NotFound
    end if
    return ok "item"
end find
```

Use `abort` when the routine cannot produce its normal return value and the caller must reason through the abort contract:

```freehold
error NotFound

function lookup(id: Integer) returns String
requires id >= 0
aborts NotFound when id = 0
is
    if id = 0 then
        abort NotFound
    end if
    return "item"
end lookup
```

The practical distinction:

| Case | Mechanism | Caller Sees |
| :--- | :--- | :--- |
| Normal success | `return ok value` | `Result<T,E>` success branch |
| Expected failure | `return error E` | `Result<T,E>` error branch |
| Exceptional exit | `abort E` | abort path declared by `aborts` |
| Plain computation | `return value` | plain return value |

---

## 11. Combining Result and Abort

A routine may return a `Result<T,E>` and still declare aborts for a different class of failure:

```freehold
error NotFound

function find_or_fail(id: Integer) returns Result<String, NotFound>
requires id >= 0
aborts NotFound
ensures success, String.instr(value, "item") >= 0
is
    if id = 0 then
        abort NotFound
    end if
    return ok "item"
end find_or_fail
```

This should be used carefully. Prefer one failure channel when possible:

```text
Result<T,E> for ordinary domain failure
abort E     for control-flow failure that prevents a normal result
```

If both are used, document the meaning of each channel with `requires`, `aborts when`, and `ensures`.

---

## 12. Contract Order

Routine contracts appear before `is`. The full contract order is:

```freehold
global ...
depends ...
modifies ...
requires ...
aborts ...
ensures ...
is
    ...
end name
```

For error handling, the common pattern is:

```freehold
function f(x: Integer) returns Result<Integer, NotFound>
requires x >= 0
aborts NotFound when x = 0
ensures success or error = NotFound
is
    ...
end f
```

Keep `requires` before `aborts`, and `aborts` before `ensures`.

---

## 13. Common Failure Patterns

### 13.1 Returning a Plain Payload From Result

Invalid:

```freehold
function load() returns Result<Integer, NotFound>
is
    return 1
end load
```

Valid:

```freehold
function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

### 13.2 Wrong `ok` Payload Type

Invalid:

```freehold
function load() returns Result<Integer, NotFound>
is
    return ok true
end load
```

The success payload is `Integer`, so the `ok` expression must be an integer.

### 13.3 Wrong Error Type

Invalid:

```freehold
error NotFound
error PermissionDenied

function load() returns Result<Integer, NotFound>
is
    return error PermissionDenied
end load
```

The declared error type is `NotFound`, so the only valid error branch is:

```freehold
return error NotFound
```

### 13.4 Unknown Returned Error

Invalid:

```freehold
error NotFound

function load() returns Result<Integer, NotFound>
is
    return error MissingError
end load
```

`MissingError` must be declared before it can be returned.

### 13.5 Using Result Concepts Before a Result Exists

Invalid idea:

```freehold
function load() returns Result<Integer, NotFound>
requires success
is
    return ok 1
end load
```

`success`, `failure`, `value`, and `error` describe the result after the function returns. They belong in `ensures`, not in `requires`.

### 13.6 Aborting Without a Contract

Invalid idea:

```freehold
error NotFound

function lookup(id: Integer) returns String
is
    abort NotFound
end lookup
```

The routine body aborts, so the contract must declare the abort:

```freehold
function lookup(id: Integer) returns String
aborts NotFound
is
    abort NotFound
end lookup
```

---

## 14. Choosing the Right Error Channel

Choose `Result<T,E>` when:

- the caller should receive and inspect the error as data,
- failure is expected in ordinary program flow,
- the function can still return normally with an error branch,
- you want postconditions over `success`, `value`, and `error`.

Choose `abort` / `aborts` when:

- the routine cannot produce a normal return value on that path,
- the path is exceptional for the routine's contract,
- the caller must reason about abnormal control flow,
- you want to declare an allowed abort condition with `aborts E when condition`.

Use plain returns when:

- failure is not part of the routine's behavior,
- preconditions rule out invalid input,
- the caller should receive a direct value.

---

## 15. Practical Checklist

Before committing error-handling code, check:

- Every error name is declared once in the module or imported explicitly.
- Every `Result<T,E>` return uses `return ok expr` or `return error E`.
- The `ok` payload type matches `T`.
- The returned error matches `E`.
- Result postconditions use `success`, `failure`, `value`, `error`, or `result.value` only where a result exists.
- Plain functions do not use `return ok` or `return error`.
- Every `abort E` is covered by an `aborts E` contract clause.
- Conditional aborts use `aborts E when condition` when the condition is part of the specification.
- `requires` rules out invalid inputs when failure should not be observable.
- `Result` and `abort` are not mixed unless the two channels have distinct meanings.

A good Freehold error contract makes failure visible at the signature, not hidden in the body.
