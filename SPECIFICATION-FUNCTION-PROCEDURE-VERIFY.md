# Freehold Specification: Functions, Procedures, and Verification Contracts
**Status:** Baseline routine model, contracts, framing, and result returns  
**Audience:** Freehold authors, verifier implementers, test authors, and code generators

This document explains how Freehold routines are structured and verified. It focuses on the distinction between `function` and `procedure`, and on the core verification clauses `requires`, `ensures`, and `modifies`. For functions, the difference between plain returns and error-aware `Result<T,E>` returns is decisive.

---

## 1. Routine Kinds

Freehold has two primary routine forms for ordinary code:

```ebnf
function_decl  ::= async_marker? 'function' NAME type_params? '(' params? ')' 'returns' return_type contract_block? 'is' stmt* 'end' NAME
procedure_decl ::= async_marker? 'procedure' NAME type_params? '(' params? ')' contract_block? 'is' stmt* 'end' NAME
```

The practical rule is:

```text
function  computes and returns a value
procedure performs an operation and is invoked with call
```

Functions are expression-producing routines:

```freehold
let x: Integer = add(1, 2)
check add(1, 2) = 3
```

Procedures are statement routines:

```freehold
call Std.IO.log("ready")
call update_account(acc, 50)
```

---

## 2. Contract Block Order

Routine contracts appear after the signature and before `is`.

The grammar order is:

```ebnf
contract_block ::= global_clause*
                 depends_clause*
                 modifies_clause*
                 requires_clause*
                 aborts_clause*
                 ensures_clause*
```

For the common subset covered here, write contracts in this order:

```freehold
procedure p(...)
modifies target
requires precondition
ensures postcondition
is
    ...
end p
```

Multiple clauses are allowed:

```freehold
function bounded_increment(x: Integer) returns Integer
requires x < 2147483647
ensures result = x + 1
is
    return x + 1
end bounded_increment
```

---

## 3. `requires`: Preconditions

### 3.1 Meaning

`requires` defines what must be true before the routine body may execute.

```freehold
function bounded_increment(x: Integer) returns Integer
requires x < 2147483647
ensures result = x + 1
is
    return x + 1
end bounded_increment
```

The routine may rely on the precondition inside its body. Callers must prove that the precondition holds at every call site.

### 3.2 Callsite Verification

This is valid:

```freehold
procedure main()
is
    let x: Integer = bounded_increment(41)
    check x = 42
end main
```

This is rejected because the caller cannot satisfy the precondition:

```freehold
procedure main()
is
    let x: Integer = bounded_increment(2147483647)
end main
```

### 3.3 Common Uses

Use `requires` for:

- range limits,
- non-zero divisors,
- valid array indices,
- non-negative amounts,
- domain preconditions such as `balance >= amount`,
- type parameter constraints such as `T is Comparable`.

The safe style is one logical idea per `requires` clause.

---

## 4. `ensures`: Postconditions

### 4.1 Meaning

`ensures` defines what must be true after the routine completes normally.

For a function, postconditions usually describe `result`:

```freehold
function add(a: Integer, b: Integer) returns Integer
ensures result = a + b
is
    return a + b
end add
```

For a procedure or mutating function, postconditions can describe updated parameters or preserved fields:

```freehold
type Account is record
    balance: Integer
    limit: Integer
end record

procedure deposit(acc: Account, amount: Integer)
modifies acc.balance
requires amount >= 0
ensures acc.balance = old(acc.balance) + amount
ensures acc.limit = old(acc.limit)
is
    acc.balance := acc.balance + amount
end deposit
```

### 4.2 `result`

In a non-`Result` function, `result` names the returned value in `ensures`:

```freehold
function identity(x: Integer) returns Integer
ensures result = x
is
    return x
end identity
```

`result` is only available in function postconditions where a return value exists.

### 4.3 `old(...)`

`old(expr)` refers to the value of `expr` at routine entry.

Use it to describe how mutation changed state:

```freehold
ensures acc.balance = old(acc.balance) + amount
ensures acc.limit = old(acc.limit)
```

The first postcondition says what changed. The second says what did not change.

---

## 5. `modifies`: Mutation Frame

### 5.1 Meaning

`modifies` declares which externally visible targets the routine is allowed to write.

```freehold
type Cell is record
    val: Integer
end record

procedure add_one(c: Cell)
modifies c.val
is
    c.val := c.val + 1
end add_one
```

Without the matching `modifies` clause, modern Freehold framing rejects the body if it mutates a parameter, field, array element, or global target.

### 5.2 Field Frames

Use field paths for precise record updates:

```freehold
type Account is record
    balance: Integer
    limit: Integer
end record

procedure deposit(acc: Account, amount: Integer)
modifies acc.balance
requires amount >= 0
is
    acc.balance := acc.balance + amount
end deposit
```

This allows `acc.balance` to change but does not authorize writes to `acc.limit`.

### 5.3 Whole-Value Frames

Use the root name for whole-value mutation, especially arrays:

```freehold
procedure set_first(a: Array<Integer, 3>, v: Integer)
modifies a
is
    a[0] := v
end set_first
```

### 5.4 Why Frames Matter

`modifies` has three jobs:

- it documents side effects,
- it lets the verifier reject accidental writes,
- it helps callers reason about what remains unchanged.

The safe habit is: whenever a routine uses `:=` on a parameter path or global state, add the matching `modifies` clause.

---

## 6. Functions Without Error Return

### 6.1 Plain Return Type

A normal function returns a plain type:

```freehold
function add(a: Integer, b: Integer) returns Integer
ensures result = a + b
is
    return a + b
end add
```

The return statement must return an expression assignable to the declared return type.

### 6.2 Guaranteed Return

Every function must have a guaranteed return on all paths:

```freehold
function abs_value(x: Integer) returns Integer
ensures result >= 0
is
    if x < 0 then
        return -x
    else
        return x
    end if
end abs_value
```

If a function can fall through without returning, verification rejects it.

### 6.3 Plain Functions Cannot Return Error Branches

This is invalid for a plain `Integer` function:

```freehold
function load() returns Integer
is
    return error NotFound
end load
```

Use `Result<T,E>` when failure is part of the function contract.

---

## 7. Functions With Error Return: `Result<T,E>`

### 7.1 Result Type

When a function can fail, declare a `Result` return type:

```freehold
error NotFound

function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

The first type argument is the success payload type. The second is the error type.

```text
Result<SuccessType, ErrorType>
```

### 7.2 Successful Return: `return ok expr`

Use `return ok expr` to produce the success payload:

```freehold
error NotFound

function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

The expression after `ok` must match the success payload type. For `Result<Integer, NotFound>`, `return ok 1` is valid and `return ok "one"` is not.

### 7.3 Error Return: `return error ErrorName`

Use `return error ErrorName` to return a declared error:

```freehold
error NotFound

function load_missing() returns Result<Integer, NotFound>
is
    return error NotFound
end load_missing
```

The error name must match the `Result` error type. Returning the wrong error is rejected.

### 7.4 Result Functions Must Use Result Returns

For a `Result<T,E>` function, return with `ok` or `error`:

```freehold
function load() returns Result<Integer, NotFound>
is
    return ok 1
end load
```

Do not return the raw payload directly:

```freehold
function load() returns Result<Integer, NotFound>
is
    return 1 -- invalid for Result<T,E>
end load
```

### 7.5 Result Postconditions

Result-returning functions may use status-oriented contract names in `ensures`:

```freehold
error NotFound

function load(found: Boolean) returns Result<Integer, NotFound>
requires found = true
ensures success or failure
is
    return ok 1
end load
```

Common result contract names include:

- `success`: whether the result is an `ok` value,
- `failure`: whether the result is an error,
- `value`: the success payload value,
- `error`: the error value.

Use `value` when the function is expected to succeed under its preconditions:

```freehold
function load_one() returns Result<Integer, NotFound>
ensures success
ensures value = 1
is
    return ok 1
end load_one
```

---

## 8. Procedures

### 8.1 No Return Value

Procedures do not have `returns Type` and do not return a value:

```freehold
procedure log_ready()
is
    call Std.IO.log("ready")
end log_ready
```

A procedure may finish by reaching its `end` declaration. It may also use control flow, checks, calls, aborts, loops, and mutation.

### 8.2 Procedures and Contracts

Procedures can have the same verification contracts for inputs, mutations, and post-state:

```freehold
type Counter is record
    value: Integer
end record

procedure increment(c: Counter)
modifies c.value
requires c.value < 2147483647
ensures c.value = old(c.value) + 1
is
    c.value := c.value + 1
end increment
```

Because procedures do not produce `result`, procedure postconditions describe parameters, globals, or other externally visible state.

### 8.3 Calling Procedures

Procedures are invoked with `call`:

```freehold
procedure main()
is
    let c: Counter = Counter { value: 0 }
    call increment(c)
    check c.value = 1
end main
```

Callers must satisfy `requires`, and they may rely on `ensures` after the call.

---

## 9. Callsite Reasoning

At a call site, the verifier checks three things:

1. The argument count and argument types match the callee.
2. The caller can prove every callee `requires` clause.
3. The caller respects the callee's mutation frame and aliasing rules.

Example:

```freehold
function bounded_increment(x: Integer) returns Integer
requires x < 2147483647
ensures result = x + 1
is
    return x + 1
end bounded_increment

procedure main()
is
    let x: Integer = bounded_increment(41)
    check x = 42
end main
```

The call is safe because `41 < 2147483647` is provable at the call site.

---

## 10. Choosing Function or Procedure

Use a plain function when:

- the primary purpose is computing a value,
- failure is not part of the normal result path,
- callers should use the routine inside expressions.

Use a `Result<T,E>` function when:

- the routine computes a value but can fail in a typed, expected way,
- the caller must inspect success/failure,
- errors are data, not process aborts.

Use a procedure when:

- the primary purpose is an effect,
- the routine mutates existing state,
- the routine performs I/O,
- the caller should invoke it with `call`.

| Need | Routine Form | Return Form |
| :--- | :--- | :--- |
| Compute `a + b` | `function` | `return a + b` |
| Parse data that may fail | `function ... returns Result<T,E>` | `return ok value` or `return error E` |
| Log a message | `procedure` | no returned value |
| Update account balance | `procedure` or framed function | mutation plus `modifies` |
| Start a task-like side effect | `task` or `procedure` | synchronized separately |

---

## 11. Verification Failure Patterns

### 11.1 Missing Precondition

If an arithmetic operation can overflow, the routine should usually state the needed bound:

```freehold
function bad_increment(x: Integer) returns Integer
ensures result = x + 1
is
    return x + 1
end bad_increment
```

Safer:

```freehold
function good_increment(x: Integer) returns Integer
requires x < 2147483647
ensures result = x + 1
is
    return x + 1
end good_increment
```

### 11.2 Missing `modifies`

Invalid under modern framing:

```freehold
procedure deposit(acc: Account, amount: Integer)
is
    acc.balance := acc.balance + amount
end deposit
```

Valid:

```freehold
procedure deposit(acc: Account, amount: Integer)
modifies acc.balance
is
    acc.balance := acc.balance + amount
end deposit
```

### 11.3 Wrong Result Return Form

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

### 11.4 Wrong Error Type

Invalid:

```freehold
error NotFound
error PermissionDenied

function load() returns Result<Integer, NotFound>
is
    return error PermissionDenied
end load
```

The declared error type is `NotFound`, so only `return error NotFound` is valid.

### 11.5 Postcondition Does Not Match Body

This body does not implement the stated swap contract:

```freehold
procedure swap_bad(x: Cell, y: Cell)
modifies x.val, y.val
ensures x.val = old(y.val)
ensures y.val = old(x.val)
is
    x.val := y.val
    y.val := x.val
end swap_bad
```

After the first assignment, `x.val` has changed, so the second assignment no longer uses the old value of `x.val`. Use a temporary local:

```freehold
procedure swap(x: Cell, y: Cell)
modifies x.val, y.val
ensures x.val = old(y.val)
ensures y.val = old(x.val)
is
    let tmp: Integer = x.val
    x.val := y.val
    y.val := tmp
end swap
```

---

## 12. Practical Checklist

Before committing routine code, check:

- Each function has a guaranteed return on every path.
- Plain functions return a plain expression of the declared type.
- `Result<T,E>` functions return either `ok` payloads or declared errors.
- Preconditions needed for arithmetic, indexing, division, or domain validity are written as `requires`.
- Every parameter/global mutation is covered by `modifies`.
- Postconditions describe either `result` or the changed/preserved state.
- Calls satisfy callee preconditions.
- Procedures are invoked with `call`; functions are used as expressions.
- `old(...)` is used when an `ensures` clause compares post-state to entry-state.

The result is a routine whose inputs, effects, outputs, and failure paths are visible before reading the body.
