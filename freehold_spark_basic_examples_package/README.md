# SPARK Basic Examples -> Freehold Proof-Equivalence Package

Source: AdaCore SPARK User's Guide, section 7.9.1 Basic Examples.

This package contains:

- `spark/src/*.ads|*.adb`: SPARK/Ada demo units with English explanatory comments derived from the guide.
- `freehold/**`: Freehold transformations as POS/NEG verification tests.
- `expected/manifest.json`: expected verification classification.
- `scripts/list_tests.py`: small helper to print the manifest.

The goal is not Ada syntax equivalence. The goal is proof-obligation equivalence:

- possible overflow must become a Freehold static verification failure;
- missing caller-side precondition knowledge must fail at call site;
- complete contracts must make subsequent calls provable;
- bad functional implementations must fail postconditions;
- uninitialized reads must be caught;
- safe arithmetic preconditions must be written without overflowing inside the precondition itself;
- saturating arithmetic should be expressed as disjoint/complete cases.

