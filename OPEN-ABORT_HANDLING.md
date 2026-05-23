# Freehold Abort Handling

This document captures the proposed Freehold abort model. It separates regular `Result<T, E>` values from controlled abnormal control flow and defines how `requires`, `aborts`, `ensures`, and `main` interact.

## Design Goal

Freehold should support controlled abort paths without turning them into hidden exceptions. An abort is a declared, typed, source-located control-flow exit that can be checked by diagnostics and later by proof obligations.

This keeps the model close to SPARK-style reasoning while making abort paths more explicit than general exception handling.

## Result Is Not Abort

`Result<T, E>` is a regular return value. It is not an abort.

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

Both branches are regular function returns. The caller receives a value of type `Result<Integer, NotFound>` and must handle it as data.

By contrast, `abort ErrorName` leaves the normal control-flow path.

## Core Syntax Proposal

```fh
error NotFound01
error NotFound02

type Account is record
    id: Integer
    active: Boolean
end record

function read(kind: Integer) returns Account
requires kind >= 0
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
ensures result.id = kind
ensures result.active = true
is
    if kind = 1 then
        abort NotFound01
    end if

    if kind = 2 then
        abort NotFound02
    end if

    return Account { id: kind, active: true }
end read
```

The intended meaning is:

```text
requires kind >= 0
    Defines the valid caller input space.

aborts NotFound01 when kind = 1
    Defines a controlled abort path inside the valid caller input space.

aborts NotFound02 when kind = 2
    Defines another controlled abort path inside the valid caller input space.

ensures result.id = kind
ensures result.active = true
    Apply only to normal return paths.
```

## Requires Defines the Valid Call Space

`requires` is a caller obligation for ordinary routines.

```fh
function read(kind: Integer) returns Account
requires kind >= 0
...
```

The caller must prove or otherwise guarantee `kind >= 0` before calling `read`.

An abort must not be used to handle invalid inputs. Invalid inputs belong in `requires`.

## Aborts Only Inside the Requires Space

Abort conditions must be reachable within the `requires` space.

The rule is:

```text
requires_condition AND abort_condition must be satisfiable
```

This is valid:

```fh
function read(kind: Integer) returns Account
requires kind >= 0
aborts NotFound01 when kind = 1
is
    if kind = 1 then
        abort NotFound01
    end if

    return Account { id: kind, active: true }
end read
```

Because:

```text
kind >= 0 AND kind = 1
```

is satisfiable.

This is invalid:

```fh
function read(kind: Integer) returns Account
requires kind != 1
aborts NotFound01 when kind = 1
is
    if kind = 1 then
        abort NotFound01
    end if

    return Account { id: kind, active: true }
end read
```

Because:

```text
kind != 1 AND kind = 1
```

is unsatisfiable. The abort path is outside the valid caller input space.

In that case diagnostics should reject the contract.

## Ensures Applies to Normal Return Only

`ensures` describes normal return behavior. It does not describe abort paths.

For this contract:

```fh
function read(kind: Integer) returns Account
requires kind >= 0
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
ensures result.id = kind
ensures result.active = true
is
    ...
end read
```

The checker can derive:

```text
normal_return_condition =
    kind >= 0
    and not (kind = 1)
    and not (kind = 2)
```

The postconditions are checked under that normal return condition:

```text
normal_return_condition => result.id = kind
normal_return_condition => result.active = true
```

The source code should not need to duplicate this with another explicit normal-case `requires` or `returns when` clause in the first implementation step.

## Abort Sites Are Source-Located

Every `abort ErrorName` statement should be represented in the AST as a source-located abort site.

An abort site is more than a control-flow jump. It is a localized, context-bound control point and contract point. The source text stays small:

```fh
if kind = 1 then
        abort NotFound01
end if
```

The verifier enriches that statement with its surrounding semantic context:

```text
module
routine kind
routine name
abort error
source position
active path condition
declared abort condition
matching aborts clause
coverage/proof status
```

Conceptually:

```json
{
  "kind": "abort_site",
    "module": "Accounts.Reader",
    "routine_kind": "function",
  "routine": "read",
  "error": "NotFound01",
  "location": { "line": 14, "column": 9 },
    "path_condition": "kind = 1",
    "declared_condition": "kind = 1",
    "covered_by": {
        "error": "NotFound01",
        "clause": "aborts NotFound01 when kind = 1",
        "location": { "line": 8, "column": 1 }
    },
    "coverage": "covered"
}
```

This makes aborts inspectable by tooling, diagnostics, and later proof reports.

The first implementation can collect path conditions syntactically from surrounding control flow. For example:

```fh
if kind >= 0 then
        if kind = 1 then
                abort NotFound01
        end if
end if
```

can produce:

```text
path_condition = kind >= 0 and kind = 1
```

For an `else` branch:

```fh
if kind = 1 then
        abort NotFound01
else
        abort NotFound02
end if
```

the abort sites can carry:

```text
NotFound01 path_condition = kind = 1
NotFound02 path_condition = not (kind = 1)
```

Later proof checking can use the contract point to generate:

```text
path_condition => declared_abort_condition
```

If a site is not covered by its declared abort condition, diagnostics can point to the exact abort location and show the mismatch:

```text
FH-ABT-3006: abort condition not covered by abort contract
FOUND => abort NotFound01 at line 14, column 9 under condition kind = 1
EXPECTED => aborts NotFound01 when kind = 2
```

## Multiple Abort Paths

A routine may declare multiple abort paths.

```fh
error NotFound01
error NotFound02

function read(kind: Integer) returns Account
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
is
    if kind = 1 then
        abort NotFound01
    end if

    if kind = 2 then
        abort NotFound02
    end if

    return Account { id: kind, active: true }
end read
```

Each abort declaration and abort site is checked independently.

## Main Has No Caller Pre-Space

`main` has no ordinary Freehold caller. Therefore `main` should not use `requires` as a normal caller obligation.

For ordinary routines:

```text
requires = caller obligation
```

For `main`, there is no caller inside the program. A `requires` clause on `main` would be an environment assumption, not a call-site proof obligation. To keep the language clean, the initial design should avoid normal `requires` on `main`.

The recommended `main` forms are:

```fh
procedure main()
is
    ...
end main
```

and later, if program arguments are supported:

```fh
procedure main(args: Program.Args)
is
    ...
end main
```

Controlled program aborts should be explicit:

```fh
error MissingArgument

procedure main(args: Program.Args)
aborts MissingArgument when Program.arg_count(args) = 0
is
    if Program.arg_count(args) = 0 then
        abort MissingArgument
    end if

    call run(args)
end main
```

The meaning is:

```text
Program starts with any environment-provided args.
If arg_count(args) = 0, main may abort with MissingArgument.
Otherwise, main continues normally.
```

If Freehold later needs explicit environment assumptions, prefer a separate keyword such as `assumes` instead of overloading `requires` on `main`.

```fh
procedure main(args: Program.Args)
assumes Program.arg_count(args) >= 1
is
    ...
end main
```

That keeps `requires` reserved for caller obligations.

## Early Normal Exit From Main

A normal early exit from `main` should be distinct from abort.

Proposed future syntax:

```fh
procedure main(args: Program.Args)
is
    if Program.arg_count(args) = 0 then
        return
    end if

    call run(args)
end main
```

This is not an abort. It is normal procedure completion.

The distinction is:

```text
return
    Normal early exit from a procedure.

abort ErrorName
    Controlled abnormal exit declared by an aborts clause.

return error ErrorName
    Regular Result<T, E> value from a Result-returning function.
```

## Caller Rule: Handle Or Propagate

Once routine calls are checked for abort behavior, every call to an aborting routine should either handle or propagate the abort.

If a callee aborts, the caller does not receive the expected normal result. The caller's normal expression or statement does not complete. Instead, the abort leaves the caller as well unless the caller handles it explicitly.

Before Freehold has explicit handling syntax, the only valid behavior is propagation through the caller's own `aborts` declarations.

This makes abort propagation a conscious part of every routine in the call chain.

Example callee:

```fh
error NotFound

function read(id: Integer) returns Account
aborts NotFound when id = 0
is
    if id = 0 then
        abort NotFound
    end if

    return Account { id: id, active: true }
end read
```

Invalid caller:

```fh
function load(id: Integer) returns Account
is
    return read(id)
end load
```

This must be rejected because `read(id)` may abort but `load` neither handles nor propagates that abort.

Diagnostic:

```text
FH-ABT-3005: caller does not handle or propagate abort
FOUND => call read(id) may abort NotFound
EXPECTED => load declares aborts NotFound or handles NotFound
```

Valid propagation:

```fh
function load(id: Integer) returns Account
aborts NotFound when id = 0
is
    return read(id)
end load
```

For a deeper call chain, each layer must keep the abort visible until a future handler consumes it:

```fh
function read(id: Integer) returns Account
aborts NotFound when id = 0
is
    ...
end read

function load(id: Integer) returns Account
aborts NotFound when id = 0
is
    return read(id)
end load

procedure service(id: Integer)
aborts NotFound when id = 0
is
    let account: Account = load(id)
end service

procedure main()
aborts NotFound
is
    call service(0)
end main
```

If any middle layer omits the abort declaration, verification fails at that layer. The error should not be delayed until `main`.

Longer term, condition compatibility should also be checked. It is not enough to propagate the same error name if the propagated condition does not cover the callee's abort condition.

Example:

```fh
function read(id: Integer) returns Account
aborts NotFound when id = 0
is
    ...
end read

function load(id: Integer) returns Account
aborts NotFound when id = 1
is
    return read(id)
end load
```

This declares `NotFound`, but under the wrong condition. A later checker should reject it because the caller's abort condition does not cover the callee's possible abort.

Conceptually:

```text
callee abort condition => caller propagated abort condition
```

For the invalid example:

```text
id = 0 => id = 1
```

is false.

Initial propagation-only rule:

```fh
function outer(kind: Integer) returns Account
aborts NotFound01 when kind = 1
is
    return read(kind)
end outer
```

This is valid only if every abort that `read(kind)` may produce is declared by `outer` under a compatible condition.

Later, Freehold may add explicit handling syntax. Until then, propagation through `aborts` clauses is enough to keep abort paths visible.

## Diagnostics

Abort diagnostics should be stable and structured.

Suggested code range:

```text
FH-ABT-3000..3999  abort and controlled abnormal control-flow diagnostics
```

Suggested initial diagnostics:

```text
FH-ABT-3001 unknown abort error
FH-ABT-3002 abort not declared by routine
FH-ABT-3003 duplicate abort declaration
FH-ABT-3004 declared abort is never used
FH-ABT-3005 caller does not handle or propagate abort
FH-ABT-3006 abort condition not covered by abort contract
FH-ABT-3007 unreachable abort condition
FH-ABT-3008 requires/abort responsibility overlap
FH-ABT-3009 aborts clause is not allowed on main requires space
```

Example: unknown abort error.

```fh
function read(kind: Integer) returns Account
aborts MissingError when kind = 1
is
    abort MissingError
end read
```

Diagnostic:

```text
FH-ABT-3001: unknown abort error
FOUND => MissingError
EXPECTED => declared error
```

Example: abort not declared by routine.

```fh
error NotFound01

function read(kind: Integer) returns Account
is
    abort NotFound01
end read
```

Diagnostic:

```text
FH-ABT-3002: abort not declared by routine
FOUND => abort NotFound01
EXPECTED => aborts NotFound01
```

Example: unreachable abort condition.

```fh
error NotFound01

function read(kind: Integer) returns Account
requires kind != 1
aborts NotFound01 when kind = 1
is
    if kind = 1 then
        abort NotFound01
    end if

    return Account { id: kind, active: true }
end read
```

Diagnostic:

```text
FH-ABT-3007: unreachable abort condition
FOUND => aborts NotFound01 when kind = 1
EXPECTED => condition compatible with requires
```

## Proof Obligations

The abort model should generate explicit obligations.

For:

```fh
function read(kind: Integer) returns Account
requires kind >= 0
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
ensures result.id = kind
ensures result.active = true
is
    if kind = 1 then
        abort NotFound01
    end if

    if kind = 2 then
        abort NotFound02
    end if

    return Account { id: kind, active: true }
end read
```

The checker should conceptually produce:

```text
requires AND abort_condition satisfiable:
    kind >= 0 AND kind = 1
    kind >= 0 AND kind = 2

abort sites covered:
    path_to_abort_NotFound01 => kind = 1
    path_to_abort_NotFound02 => kind = 2

normal return condition:
    kind >= 0 AND not (kind = 1) AND not (kind = 2)

normal postconditions:
    normal_return_condition => result.id = kind
    normal_return_condition => result.active = true
```

## Implementation Phases

Recommended first implementation phases:

1. Parse `aborts ErrorName` and `abort ErrorName` without `when`.
2. Verify declared errors and declared aborts.
3. Emit abort sites with source positions in artifacts.
4. Add stable `FH-ABT-*` diagnostics and expected diagnostics cases.
5. Add `aborts ErrorName when expr`.
6. Check `requires AND abort_condition` reachability for simple expressions.
7. Derive normal-return conditions for `ensures` checking.
8. Add caller propagation checks.
9. Consider `return` without value for early normal procedure exit.
10. Consider `Program.Args` and optional `main` abort handling.

## Summary Rules

```text
Result<T, E>
    Regular value-level success/failure result.

return error E
    Regular Result<T, E> return, not an abort.

abort E
    Controlled abnormal control-flow exit.

requires
    Defines valid call space for ordinary routines.

aborts E when condition
    Defines abort path inside the requires space.

ensures
    Applies only to normal return.

main
    Has no ordinary caller pre-space. Do not use normal requires as a call-site obligation.
```
