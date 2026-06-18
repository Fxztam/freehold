# Coverage Notes

Source section: AdaCore SPARK User's Guide 7.9.2 Loop Examples.

The documentation groups loop examples into these patterns:

- Need for a loop invariant
- Initialization loops
- Mapping loops
- Validation loops
- Counting loops
- Search loops
- Maximize loops
- Update loops

This package models each pattern as a SPARK procedure and as one or more Freehold verification tests.

## Deliberate simplifications

- SPARK vector/list examples are represented by array-equivalent procedures.
- Ownership, borrowing, `At_End`, and structural loop variants are not translated into Freehold because those concepts are not yet core Freehold constructs.
- Freehold comments preserve the proof intent: prefix property, frame condition, early-exit search/validation, counter bound, maximum witness, and range update frame.

## Suggested future Freehold additions

- Container abstraction tests once Freehold has library-level vectors/lists.
- Borrow/aliasing tests once Freehold has ownership or frame-condition semantics.
- Ghost model / old-state snapshot tests for list-style update proofs.
