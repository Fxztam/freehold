# Freehold Control Flow Analyzer

This document captures the planned Control Flow Analyzer work after the current Parser, AST, Diagnostics, Rules, and Spec layers have been hardened.

## Status

Open. This is the next larger language-analysis complex after the diagnostic layer.

The current completed foundation is:

```text
Parser / AST
Diagnostics / Rules / Spec
```

That foundation makes syntax stable, ASTs comparable across parser frontends, and semantic errors addressable through stable diagnostic codes. The Control Flow Analyzer builds on that foundation by reasoning about routine paths rather than isolated statements.

## Scope

The analyzer should understand how control moves through a routine:

```text
return ends the normal path
abort ends an abnormal path
if/else splits paths
while creates loop paths
requires defines the routine input space
aborts when defines allowed abort paths
ensures applies only to normal return paths
```

The first goal is not a full proof engine. The first goal is a stable internal summary that later checks can consume.

## Initial Routine Summary

The first implementation should produce a small per-routine summary:

```text
RoutineFlowSummary
    normal_return_possible
    guaranteed_exit
    declared_aborts
    emitted_aborts
    called_routines
    propagated_aborts
```

This summary is enough to support Abort V2 call propagation without immediately implementing full path-condition proof.

## Relationship To Abort Handling

Abort Handling V1 is complete and deliberately stops before cross-routine control-flow reasoning. The Control Flow Analyzer is the proper home for the follow-up abort slices.

Recommended order:

1. Abort V2: Call Propagation

If routine `A` calls routine `B`, and `B` declares `aborts NotFound`, then `A` must either declare `aborts NotFound` as well or, in a later language version, handle `NotFound` explicitly.

This gives the largest semantic gain after diagnostics because aborts become visible across routine boundaries.

2. Abort V3: Main Rules

`main` must not silently lose open aborts. Depending on whether handler syntax exists by then, `main` should either reject open aborts or allow only explicitly declared top-level program aborts.

3. Abort V4: Reachability And Simple Path Checks

The analyzer should reject obviously unreachable statements and simple inconsistent control-flow shapes. Initial examples:

```text
abort after guaranteed return
return after unconditional abort
abort condition plainly incompatible with requires
```

4. Abort V5: Path Coverage And Proof Obligations

This is the heaviest slice. It should check whether each `aborts X when condition` is covered by actual abort paths and whether every `abort X` site is compatible with the declared abort condition.

This step should wait until call propagation is stable, because proof obligations build on the routine-level abort surface.

## Planned Diagnostics

The analyzer should eventually drive the later abort diagnostics already reserved in the abort design:

```text
FH-ABT-3004 declared abort is never used
FH-ABT-3005 caller does not handle or propagate abort
FH-ABT-3006 abort condition not covered by abort contract
FH-ABT-3007 unreachable abort condition
FH-ABT-3008 requires/abort responsibility overlap
FH-ABT-3009 aborts clause is not allowed on main requires space
```

The first Control Flow Analyzer slice should likely target `FH-ABT-3005` only. The remaining diagnostics require richer path conditions or main-specific policy decisions.

## Non-Goals For The First Slice

The first slice should not attempt a full symbolic prover.

It should avoid these until the routine summaries and call propagation are stable:

```text
full Boolean satisfiability
loop invariant proof
complete path coverage
condition implication proof beyond simple structural cases
handler syntax
```

## Summary

Diagnostics close the language surface. The Control Flow Analyzer starts the next layer: path-aware routine reasoning.

The practical first step is a small routine-summary analyzer, followed by Abort V2 call propagation.