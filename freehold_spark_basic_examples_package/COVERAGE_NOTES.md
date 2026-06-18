# Coverage Notes

Covered from SPARK User's Guide 7.9.1 Basic Examples:

1. Increment
   - missing precondition -> overflow vulnerability
   - guarded increment -> caller must prove precondition
   - full increment with postcondition -> caller can chain calls
   - contextual/local helper idea represented as an inline/freehold local proof sketch

2. Swap
   - bad implementation without contract only yields a flow warning in SPARK
   - bad implementation with postcondition fails functionally
   - correct temp-based swap verifies
   - uninitialized temporary read is a hard diagnostic
   - bitwise modular swap is included as pending because Freehold may not yet have modular Unsigned_32/xor semantics

3. Addition
   - naive precondition `x + y in Integer` is itself overflow-prone
   - safe machine-integer precondition avoids overflow in the guard
   - Big_Integer variant is included as pending unless Freehold has an unbounded integer type
   - saturating addition is represented with explicit case-style ensures clauses

Pending / language-dependent:

- Flow dependency aspects equivalent to SPARK `Depends`.
- Modular arithmetic and bitwise xor.
- Big integer library support.
- Native `old(x)` / `x'Old` syntax may need adaptation to Freehold's current AST.
