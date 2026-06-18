# Freehold Specification: Statements, `let`, `call`, `=` and `:=`
**Status:** Baseline statement semantics and v11a assignment model  
**Audience:** Freehold authors, test writers, frontend implementers, and code generators

This document explains the core Freehold statement forms for local bindings, procedure calls, and mutation. It focuses especially on the difference between `=` and `:=`, because that distinction is central to writing clear and verifiable Freehold programs.

---

## 1. Statement Overview

Inside routine bodies, Freehold statements are parsed as one of the supported statement forms:

```ebnf
stmt ::= let_stmt
       | field_assign_stmt
       | assign_stmt
       | return_stmt
       | abort_stmt
       | if_stmt
       | while_stmt
       | case_stmt
       | scope_stmt
       | check_stmt
       | call_stmt
       | parallel_stmt
```

This specification concentrates on:

```ebnf
let_stmt          ::= 'let' NAME ':' return_type '=' expr
assign_stmt       ::= NAME ':=' expr
field_assign_stmt ::= field_path ':=' expr
call_stmt         ::= 'call' qualified_name type_arg_list? '(' arg_list? ')'
```

The short rule is:

```text
let ... = ...   creates and initializes a new local variable
x := ...        mutates an existing variable
x.y := ...      mutates an existing record field
call f(...)     executes a procedure/task for its effects
x = y           compares values inside expressions and contracts
```

---

## 2. `let`: Local Binding and Initialization

### 2.1 Basic Form

`let` introduces a new local variable with an explicit type and an initializer expression:

```freehold
let x: Integer = 1
let name: String = "Ada"
let ok: Boolean = true
```

The `=` in a `let` statement is not mutation. It is initialization: the variable does not exist before the statement and is created with the expression value.

### 2.2 Type Checking

The initializer expression must be assignable to the declared type:

```freehold
let x: Integer = 1        -- valid
let b: Boolean = true     -- valid
let s: String = "hello"   -- valid
```

This is rejected:

```freehold
let x: Integer = false
```

because `false` has type `Boolean`, not `Integer`.

### 2.3 Record Initialization

Records are normally created with record literals:

```freehold
type Account is record
    id: Integer
    active: Boolean
end record

procedure main()
is
    let account: Account = Account { id: 1, active: true }
    check account.id = 1
end main
```

All required fields must be present, field names must be known, and field values must match their declared types.

### 2.4 Array Initialization

Arrays can be initialized with array literals when the length and element type match:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
let first: Integer = values[0]
```

Length mismatches and mixed element types are semantic errors.

### 2.5 Binding Results of Calls

Functions are expressions and can be used on the right side of `let`:

```freehold
function add(a: Integer, b: Integer) returns Integer
ensures result = a + b
is
    return a + b
end add

procedure main()
is
    let sum: Integer = add(1, 2)
    check sum = 3
end main
```

Async joins and channel operations can also initialize locals when their expression type matches:

```freehold
let item: Integer = await handle
let sent: Boolean = await channel_send<Integer>(sender, 42)
```

---

## 3. `call`: Effectful Routine Invocation

### 3.1 Basic Form

`call` executes a routine for its side effects:

```freehold
call Std.IO.log("hello")
call update_account(acc, 50)
```

The target name may be qualified:

```freehold
call Std.IO.log("starting")
call App.Services.refresh_cache()
```

### 3.2 `call` Requires Procedure or Task

A `call` statement is for routines that do not produce a direct expression result at the call site. In semantic terms, the target must be a `procedure` or a `task`.

Use `call` for this:

```freehold
procedure log_value(x: Integer)
is
    call Std.IO.log("value")
end log_value

procedure main()
is
    call log_value(42)
end main
```

Do not use `call` for a function result:

```freehold
function value() returns Integer
is
    return 42
end value

procedure main()
is
    call value() -- invalid: function call requires expression context
end main
```

Use `let` instead:

```freehold
let x: Integer = value()
```

### 3.3 Arguments

Arguments are checked against the callee's parameter list:

```freehold
procedure print_twice(left: String, right: String)
is
    call Std.IO.log(left)
    call Std.IO.log(right)
end print_twice

procedure main()
is
    call print_twice("Ada", "Lovelace")
end main
```

The verifier checks arity and type compatibility. Passing too few, too many, or wrongly typed arguments is rejected.

### 3.4 Qualified Calls and Imports

When a routine is imported through its module, qualified `call` keeps the effect source visible:

```freehold
import Std.IO

procedure main()
is
    call Std.IO.log("ready")
end main
```

When a procedure is explicitly exposed, it may be called unqualified:

```freehold
import App.Logging exposing log_ready

procedure main()
is
    call log_ready()
end main
```

For operational effects, qualified calls are often easier to audit.

---

## 4. `=`: Initialization, Equality, and Named Arguments

### 4.1 `=` in `let` Means Initialization

In this context, `=` creates a local binding:

```freehold
let x: Integer = 1
```

It is part of the `let` syntax. It does not update an existing variable.

### 4.2 `=` in Expressions Means Equality

Inside expressions, checks, conditions, requires, ensures, invariants, and case logic, `=` is equality comparison:

```freehold
check x = 1

if x = 1 then
    check true
else
    check false = false
end if

ensures result = a + b
```

Equality produces a `Boolean` expression.

### 4.3 `=` in Record Literals Binds Field Values by Name-Like Syntax

Record literals use field bindings with `:` rather than `=`:

```freehold
let account: Account = Account { id: 1, active: true }
```

The outer `=` belongs to `let`; the inner `id: 1` and `active: true` entries bind record fields.

### 4.4 `=` Is Not Assignment After Declaration

This is invalid in v11a and newer:

```freehold
procedure main()
is
    let x: Integer = 1
    x = x + 1
end main
```

Use `:=` for mutation:

```freehold
x := x + 1
```

---

## 5. `:=`: Mutation of Existing Storage

### 5.1 Variable Assignment

`:=` updates an existing local variable:

```freehold
procedure main()
is
    let x: Integer = 1
    x := x + 1
    check x = 2
end main
```

The target must already exist in scope.

This is rejected:

```freehold
procedure main()
is
    x := 1
end main
```

because `x` has not been declared.

### 5.2 Field Assignment

`:=` also updates record fields:

```freehold
type Address is record
    city_id: Integer
end record

type Customer is record
    id: Integer
    address: Address
end record

procedure main()
is
    let c: Customer = Customer { id: 1, address: Address { city_id: 42 } }
    c.address.city_id := 99
    check c.address.city_id = 99
end main
```

The field path must exist and the assigned expression must match the field type.

### 5.3 Array Element Assignment

Array elements are updated with index assignment:

```freehold
procedure set_first(a: Array<Integer, 3>)
modifies a
is
    a[0] := 99
end set_first
```

The verifier checks that the target is an array, the index is an `Integer`, and the assigned value matches the element type.

### 5.4 Mutation Requires Framing in Routines

If a routine mutates a parameter, field, array element, or global state, declare the mutation with `modifies`:

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

This makes side effects explicit and allows the verifier to reject accidental writes.

---

## 6. `=` Versus `:=` Decision Table

| Situation | Use | Example |
| :--- | :--- | :--- |
| Declare and initialize a local | `let ... = ...` | `let x: Integer = 1` |
| Compare two values | `=` | `check x = 1` |
| State a postcondition | `=` | `ensures result = x + 1` |
| Update an existing local | `:=` | `x := x + 1` |
| Update a record field | `:=` | `account.balance := 10` |
| Update an array element | `:=` | `items[0] := 42` |
| Execute an effectful procedure | `call` | `call Std.IO.log("done")` |
| Use a function result | expression/`let` | `let y: Integer = f()` |

Mental model:

```text
=  says what a value is, or asks whether two values are equal.
:= changes an existing storage location.
```

---

## 7. Common Mistakes

### 7.1 Using `=` for Mutation

Invalid:

```freehold
let x: Integer = 1
x = x + 1
```

Valid:

```freehold
let x: Integer = 1
x := x + 1
```

### 7.2 Using `call` for a Function

Invalid:

```freehold
function next(x: Integer) returns Integer
is
    return x + 1
end next

procedure main()
is
    call next(1)
end main
```

Valid:

```freehold
let value: Integer = next(1)
```

### 7.3 Forgetting `modifies`

Invalid under modern framing rules:

```freehold
type Account is record
    balance: Integer
end record

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

### 7.4 Assigning the Wrong Type

Invalid:

```freehold
let active: Boolean = true
active := 1
```

Valid:

```freehold
active := false
```

---

## 8. Safe Statement Style

Prefer statement bodies that read like a small proof:

```freehold
procedure transfer(from_acc: Account, to_acc: Account, amount: Integer)
modifies from_acc.balance, to_acc.balance
requires amount >= 0
requires from_acc.balance >= amount
is
    from_acc.balance := from_acc.balance - amount
    to_acc.balance := to_acc.balance + amount
    check from_acc.balance >= 0
end transfer
```

This style makes intent visible:

- `let` names intermediate values,
- `call` marks effectful operations,
- `:=` marks mutation,
- `=` remains available for equality in checks and contracts,
- `modifies` frames the allowed write targets.

---

## 9. Practical Checklist

Before committing statement-heavy code, check:

- New locals use `let name: Type = expr`.
- Existing locals or fields use `:=` for updates.
- `=` appears in initialization, equality checks, conditions, or contracts, not as post-declaration assignment.
- Function results are used as expressions, usually through `let`.
- Procedures and tasks are invoked with `call` when used as statements.
- Mutating routines declare `modifies` clauses.
- Record and array updates use valid paths and compatible value types.

The result is code that is easier to read, easier to verify, and much less ambiguous for parsers, humans, and code generators.