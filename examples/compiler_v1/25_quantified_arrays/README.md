# Example 25: Quantified Array Conditions (Frame Conditions)

This directory demonstrates Freehold's support for universal (`for all`) and existential (`for some`) quantifiers over arrays, which matches SPARK Ada/GNATprove formal verification features.

## Files

1. **`App/Main.fh` (Positive Case)**:
   - Contains `sum_positive` which has a contract `requires for all I in 0..2 => arr[I] >= 0` ensuring that all array elements are non-negative.
   - The postcondition `ensures result >= 0` is successfully proved by Z3 because the universal quantifier is instantiated for all index values.
   - The `main` procedure uses a literal array `[5, 10, 15]`, checks quantified properties runtime-wise, calls the function, and verifies the result.
   - **Verification**: Passes successfully.

2. **`Main_Negative.fh` (Negative Case)**:
   - Contains `sum_negative_fail` which uses `requires for some I in 0..2 => arr[I] >= 0` (existential quantifier).
   - This contract only guarantees that *at least one* element is non-negative. Since other elements could be negative, the solver cannot prove that the sum `result` is `>= 0`.
   - **Verification**: Fails with a verification error (Z3 cannot prove the ensures clause).

## Running the Verification

To verify the positive case:
```cmd
python -m freehold verify examples/compiler_v1/25_quantified_arrays/App/Main.fh
```

To verify the negative case (expected to fail):
```cmd
python -m freehold verify examples/compiler_v1/25_quantified_arrays/Main_Negative.fh
```
