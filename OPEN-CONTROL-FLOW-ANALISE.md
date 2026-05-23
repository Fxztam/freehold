# Freehold Control Flow Analyzer

This document captures the planned Control Flow Analyzer work after the current Parser, AST, Diagnostics, Rules, and Spec layers have been hardened.

## Status

Open. V0 is implemented as an internal routine-summary layer. Abort V3 main-specific requires rejection is implemented. Later path-aware diagnostics remain open.

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

This summary is enough to support later abort analysis without immediately implementing full path-condition proof.

## Control Flow Analyzer V0

V0 is implemented as an internal structure slice. Abort V2 call propagation has been implemented directly in the verifier as a small same-error-name rule; V0 provides the summary shape for later path-aware analysis.

The analyzer contract is also captured in a small meta-language spec:

```text
spec/analyzer.cflow
```

That file records the intended `RoutineFlowSummary`, direct flow facts, the Abort V2 same-error-name propagation rule, and explicit non-goals such as condition implication and handler syntax.

Proposed internal structure:

```text
RoutineFlowSummary
    routine_name
    routine_kind
    normal_return_possible
    guaranteed_exit
    declared_aborts
    emitted_aborts
    called_routines
    propagated_aborts
```

Field meanings:

```text
normal_return_possible
    True if at least one path can complete by normal return or normal procedure completion.

guaranteed_exit
    True if every analyzed path ends in return or abort.

declared_aborts
    Abort errors declared by the routine's aborts clauses.

emitted_aborts
    Abort errors emitted directly by abort statements inside the routine body.

called_routines
    Routine calls observed inside statements and expressions.

propagated_aborts
    Abort errors that the routine surface declares as available to callers.
    In V0 this can be equivalent to declared_aborts. Later slices can enrich it with call-chain data.
```

V0 inputs:

```text
Module AST
Routine declarations
Routine contract clauses
Routine body statements and expressions
Known routine symbol table from the verifier
```

V0 outputs:

```text
RoutineFlowSummary per function/procedure
No new diagnostics required for the first structure-only pass
Optional debug/artifact output only if useful for inspection
```

V0 should recognize these direct facts only:

```text
return statement contributes a normal exit
abort statement contributes an emitted abort and an abnormal exit
call statement contributes a called routine
call expression contributes a called routine
if/else combines branch summaries conservatively
sequential statements stop after a guaranteed exit for summary purposes
```

V0 should not yet prove Boolean path conditions, check caller propagation, or reject programs. That keeps the first analyzer slice small and reviewable.

The implementation shape is:

```text
freehold/core/control_flow.py
    RoutineFlowSummary
    ControlFlowAnalyzer
```

The verifier calls this analyzer after semantic verification and stores the result on `VerifiedProgram.flow_summaries`. V0 does not change language behavior or emit diagnostics.

## Relationship To Abort Handling

Abort Handling V1 is complete and deliberately stops before cross-routine control-flow reasoning. The Control Flow Analyzer is the proper home for the follow-up abort slices.

Recommended order:

1. Abort V2: Call Propagation

Implemented on 2026-05-23 for same-error-name propagation. Condition implication and handler syntax are not included.

If routine `A` calls routine `B`, and `B` declares `aborts NotFound`, then `A` must either declare `aborts NotFound` as well or, in a later language version, handle `NotFound` explicitly.

This gives the largest semantic gain after diagnostics because aborts become visible across routine boundaries.

2. Abort V3: Main Rules

Implemented on 2026-05-23 for rejecting normal `requires` clauses on `main`. Explicit top-level main abort declarations remain valid.

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

The first propagation diagnostic, `FH-ABT-3005`, and the first main diagnostic, `FH-ABT-3009`, are implemented by the verifier. The remaining diagnostics require richer path conditions or additional main-specific policy decisions.

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

The next practical Control Flow Analyzer step is the small routine-summary analyzer. Abort V2 call propagation is already in place as a verifier rule and can later be migrated behind the summary API if needed.