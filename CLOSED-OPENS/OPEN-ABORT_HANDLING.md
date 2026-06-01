# Freehold Abort Handling

This document captures the proposed Freehold abort model. It separates regular `Result<T, E>` values from controlled abnormal control flow and defines how `requires`, `aborts`, `ensures`, and `main` interact.

## V1 Completion

Accepted and implemented as V1 on 2026-05-23.

Implemented scope:

```text
aborts ErrorName
aborts ErrorName when condition
abort ErrorName
```

V1 verifies declared errors, duplicate abort declarations, abort statements declared by the enclosing routine, and Boolean abort conditions. V2 adds same-error-name call propagation. V3 adds main-specific requires rejection while keeping explicit top-level main aborts valid. V4a rejects statements after syntactically guaranteed exits such as `abort`, `return`, and exhaustive aborting branches. V4b adds simple syntactic path implication for conditional abort contracts using routine `requires` clauses and `if`/`else` guards. Handler syntax, broader call-condition implication, and full proof obligations remain future slices.

Current validation baseline after V4b:

```text
21_abort_handling module:       17/17
Language module gate:           461/461
Semantic diagnostics:           99/99
Spec diagnostics:               114 specs, 115 emits, 85 semantic codes, 91 CODE_MAP entries
Parser status parity:           322/322
AST shape parity:               277/277
Semantic AST parity:            277/277
```

V1 is intentionally a clean, green anchor. Parser/AST support, basic verifier rules, stable diagnostics, positive and negative language tests, Go/DHParser artifacts, comparison artifacts, rules, and diagnostic specs are complete for this slice.

The heavier proof-oriented control-flow work is explicitly not part of V1. It should be implemented as follow-up slices, so parser/AST/diagnostic hardening stays separate from deeper path reasoning.

## Post-V1 Roadmap

Recommended order after committing Abort V1:

1. Abort V2: Call Propagation

Implemented on 2026-05-23 for same-error-name propagation without condition implication.

If routine `A` calls routine `B`, and `B` declares `aborts NotFound`, then `A` must either declare `aborts NotFound` as well or, in a later language version, handle `NotFound` explicitly.

This is the most useful next step because it makes aborts semantically visible across routine boundaries while remaining clearly testable.

2. Abort V3: Main Rules

Implemented on 2026-05-23 for rejecting normal `requires` clauses on `main`. Explicit top-level `aborts` clauses on `main` remain valid.

`main` must not silently lose open aborts. Depending on whether handler syntax exists by then, `main` should either reject open aborts or allow only explicitly declared top-level program aborts.

3. Abort V4: Reachability And Simple Path Checks

V4a implemented on 2026-05-25 for statements after guaranteed exits in the same block. Covered shapes include a direct `abort` followed by another statement and an exhaustive `if/else` whose branches both abort before a later statement.

V4b implemented on 2026-05-25 for simple syntactic condition implication at abort sites. The verifier carries routine `requires` expressions and surrounding `if`/`else` guards as active path conditions. An `abort X` covered by `aborts X when condition` must occur under a syntactically matching condition; otherwise `FH-ABT-3006` rejects the site.

Reject obviously unreachable abort statements and simple inconsistent control-flow shapes. Initial examples include `abort` after a guaranteed `return`, `return` after an unconditional `abort`, and abort conditions that are plainly incompatible with routine preconditions.

Remaining V4 work: broader call-condition implication and contract/path consistency beyond direct syntactic matches.

4. Abort V5: Path Coverage And Proof Obligations

This is the heaviest slice. It should check whether each `aborts X when condition` is covered by actual abort paths and whether every `abort X` site is compatible with the declared abort condition.

The first abort-site compatibility slice is now covered by V4b for direct syntactic path matches. V5 remains responsible for full path coverage and proof obligations.

This step should wait until call propagation is stable, because path coverage and proof obligations build on the routine-level abort surface.

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

Completed in V1:

1. Parse `aborts ErrorName`, `aborts ErrorName when expr`, and `abort ErrorName`.
2. Verify declared errors and declared aborts.
3. Reject duplicate abort declarations.
4. Reject abort statements that are not declared by the enclosing routine.
5. Check abort conditions as Boolean contract expressions.
6. Emit abort clauses and abort statements in AST artifacts.
7. Add stable `FH-ABT-3001..3003` diagnostics, rules, specs, CODE_MAP entries, and expected diagnostic cases.

Planned after V1:

1. Add caller propagation checks. Completed in V2 for same-error-name propagation.
2. Add `main`-specific abort rules. Completed in V3 for rejecting normal `requires` clauses on `main`.
3. Add reachability and simple path-condition checks.
4. Add abort path coverage and proof obligations.
5. Consider condition implication for propagated aborts.
6. Consider `return` without value for early normal procedure exit.
7. Consider `Program.Args` and optional explicit abort handling syntax.

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

=== CLOSED ===
