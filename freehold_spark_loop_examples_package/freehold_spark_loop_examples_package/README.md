# SPARK Loop Examples -> Freehold Verification Tests

This package contains two artifacts:

1. `spark/`: a compact SPARK/Ada package with loop examples and English comments.
2. `freehold/`: Freehold transformations of the same proof patterns.

The examples are derived from AdaCore SPARK User's Guide section 7.9.2, "Loop Examples".
The comments paraphrase the documentation and are intentionally written as test guidance.

## Covered loop-equivalence classes

| Class | SPARK procedure | Freehold test |
|---|---|---|
| Need for loop invariant | `Increment_Loop_Bad`, `Increment_Loop_Good` | `01_increment_loop_*` |
| Initialization loop | `Init_Arr_Zero` | `02_init_arr_zero.fh` |
| Index-dependent initialization | `Init_Arr_Index` | `03_init_arr_index.fh` |
| Mapping loop | `Map_Arr_Incr` | `04_map_arr_incr.fh` |
| Validation with early exit | `Validate_Arr_Zero` | `05_validate_arr_zero.fh` |
| Full validation | `Validate_Full_Arr_Zero` | `06_validate_full_arr_zero.fh` |
| Counting loop | `Count_Arr_Zero` | `07_count_arr_zero.fh` |
| Search with early exit | `Search_Arr_Zero` | `08_search_arr_zero.fh` |
| Maximize loop | `Search_Arr_Max` | `09_search_arr_max.fh` |
| Conditional update | `Update_Arr_Zero` | `10_update_arr_zero.fh` |
| Range update | `Update_Range_Arr_Zero` | `11_update_range_arr_zero.fh` |

## Notes

The AdaCore page also shows container/vector/list variants. Freehold currently has no direct equivalent for SPARK formal containers, access types, borrowing, or ownership-aware list traversal. Therefore this package keeps the verification essence of all loop patterns in array-oriented Freehold tests.

## How to run SPARK side

```bash
cd spark
gnatprove -P loop_examples.gpr --level=2
```

`Increment_Loop_Bad` is intentionally included as the negative example for missing loop invariant. Depending on your GNATprove invocation, verify it separately if you want the project-wide run to stay green.

## How to use the Freehold side

Use `freehold/expected/loop_examples.expected.txt` as the initial expected-result manifest for your Freehold runner.

