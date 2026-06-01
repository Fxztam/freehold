# Freehold Requires and Ensures

This document captures the proposed notation rule for `requires` and `ensures` clauses.

## Status

Accepted and implemented as V1 on 2026-05-23.

Validation baseline:

```text
13_contract_blocks module:      16/16
Semantic diagnostics:           63/63
Spec diagnostics:               87/87 emits, 60 semantic codes, 64 CODE_MAP entries
Parser status parity:           272/272
AST shape parity:               229/229
Semantic AST parity:            229/229
freehold.rules:                 no new diagnostic emit; existing ContractClause rules apply per normalized comma item
```

## Core Rule

In `requires` and `ensures`, comma-separated conditions are AND conditions at the contract-clause level.

```text
Comma in requires/ensures means AND between independent contract conditions.
```

For example:

```fh
requires a > 0, b > 0, c > 0
```

is semantically equivalent to:

```fh
requires a > 0
requires b > 0
requires c > 0
```

and logically equivalent to:

```text
(a > 0) and (b > 0) and (c > 0)
```

The same rule applies to `ensures`:

```fh
ensures result.id = kind, result.active = true
```

is semantically equivalent to:

```fh
ensures result.id = kind
ensures result.active = true
```

and logically equivalent to:

```text
(result.id = kind) and (result.active = true)
```

## Intended Syntax

The intended grammar shape is:

```ebnf
requires_clause: "requires" expr_list
ensures_clause: "ensures" expr_list
expr_list: expr ("," expr)*
```

The AST and verifier can continue to store contracts as lists of expressions:

```text
requires: list[Expr]
ensures: list[Expr]
```

The comma notation is only syntactic sugar for adding multiple contract expressions in one source line.

## And/Or Inside a Condition

Comma separates independent contract conditions. Logical `and` and `or` remain available inside a single condition.

```fh
requires kind >= 0 and kind <= 100, user.active = true
```

means:

```text
(kind >= 0 and kind <= 100)
and
(user.active = true)
```

It is normalized as two contract expressions:

```fh
requires kind >= 0 and kind <= 100
requires user.active = true
```

This preserves the distinction between:

```fh
requires a and b, c
```

and:

```fh
requires a and (b or c)
```

## Diagnostics

Diagnostics should point to the specific comma-separated contract item that fails.

Example:

```fh
requires kind >= 0, missing > 0
```

If `missing` is not in scope, the diagnostic should point to the second condition, not to the entire `requires` line.

Conceptually:

```text
FOUND => missing
EXPECTED => variable in scope
LOCATION => second requires item
```

This requires preserving source positions for each expression in `expr_list`.

## Relationship to Aborts

This comma notation applies to `requires` and `ensures` only.

It does not apply to `aborts`.

Abort clauses remain one abort contract per clause:

```fh
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
```

This is intentional. Each abort clause is a distinct localized contract point with its own error, optional condition, source position, diagnostic behavior, and later proof obligation.

Do not write:

```fh
aborts NotFound01 when kind = 1, NotFound02 when kind = 2
```

## Example

Compact notation:

```fh
function read(kind: Integer) returns Account
requires kind >= 0, kind <= 100
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
ensures result.id = kind, result.active = true
is
    ...
end read
```

Normalized contract model:

```fh
function read(kind: Integer) returns Account
requires kind >= 0
requires kind <= 100
aborts NotFound01 when kind = 1
aborts NotFound02 when kind = 2
ensures result.id = kind
ensures result.active = true
is
    ...
end read
```

Logical meaning:

```text
requires:
    kind >= 0
    and kind <= 100

normal ensures:
    result.id = kind
    and result.active = true
```

## Summary Rules

```text
requires A, B, C
    means requires A and requires B and requires C

ensures A, B, C
    means ensures A and ensures B and ensures C

and/or
    stay inside an individual condition

aborts
    remains one abort contract per clause
```

=== CLOSED ===
