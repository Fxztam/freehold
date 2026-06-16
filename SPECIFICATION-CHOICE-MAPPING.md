# Specification: Choice Algebraic Data Types & Pattern Matching Mapping

This document specifies the design, AST representation, semantic validation, SMT verifier mapping, and WhyML code generation structure for Freehold V2 **Algebraic Sum Types (`choice`) and Pattern Matching (`case` destructuring) with guards**.

---

## 1. Syntax & Lark Grammar Sync

Choice types are declared with a vertical bar delimiter:

```lark
choice_type_decl: "choice" NAME type_param_list? "=" "|"? constructor_decl ("|" constructor_decl)* "end" NAME
constructor_decl: NAME ("(" param ("," param)* ")")?
```

Pattern branches within case statements are prefix-marked with vertical bars `|` to eliminate LALR(1) shift-reduce hazards:

```lark
pattern_branch: "|" pattern_expr ("when" expr)? "=>" case_block
pattern_expr: NAME ("(" NAME ("," NAME)* ")")?
```

---

## 2. AST Definitions

Mapped under [freehold/core/ast.py](freehold/core/ast.py):

* **`ChoiceTypeDecl` (dataclass)**:
  Represents sum-type definitions with polymorphic `type_params`.
* **`ChoiceConstructor` (dataclass)**:
  Represents choice constructor nodes, containing parameter bindings.
* **`PatternExpr` (dataclass)**:
  Destructuring expression mapping a constructor name and bound arguments.
* **`PatternBranch` (dataclass)**:
  Each de-structured state branch containing local SMT environments, a guard-expression, and block statement bodies.

---

## 3. Semantic Verification Rules

Registered under [freehold/core/verifier.py](freehold/core/verifier.py):

### Duplicate Branch Controls:
* Standard tracking sets (`matched_fully`) trace constructors matched **without guards** (fully covered).
* A duplicate branch error triggers *only* if a constructor is matched *after* it has already been matched by an unguarded block.
* Duplicate pattern branches trigger:
  `duplicate pattern match branch for constructor <constructor_name>`

### Guard Validity Constraints:
* Match guards must evaluate to a scalar `Boolean` type. Non-boolean guards dynamically trigger:
  `pattern match guard must be Boolean, got <type>`

### Mathematical Exhaustiveness:
* Choice case blocks must be exhaustive.
* The set of all `matched_fully` constructor names is compared against the total defined choice constructor list. If exhaustiveness is not satisfied (and no literal `default` or fallback exists), the checker issues:
  `pattern matching is not exhaustive, missing: <missing_constructors>`

### Primitives Bounds:
* Pattern matching is strictly limited to choice types. Non-choice targets trigger:
  `pattern matching is only supported on choice types, got <type>`

---

## 4. Symbolic Verifier (SMT Solver Mapping)

Configured under [freehold/core/symbolic.py](freehold/core/symbolic.py):

* **Variable Havoc & Sub-Environments**:
  For each de-structured sum-type state, variables bound by constructors (e.g., `v` in `Some(v)`) are mapped to local SMT variables indexed by the expression and arg index (e.g., `expr_Some_0`).
* **Conditional Assertions**:
  SMT checks compile boolean checks checking constructor active states (`_is_Some`) inline with path preconditions:
  ```smt2
  (and expr_is_Some guard_smt_expression)
  ```
  Unmatched states negate branches in a chained default fall-through tree.

---

## 5. WhyML Verification Mapping

Generated under [freehold/core/whyml_codegen.py](freehold/core/whyml_codegen.py):

### Data Types Translation:
Choices map natively to WhyML variants:
```whyml
type trafficLight =
  | Red
  | Yellow
  | Green
```

### Type Parameters & Generics:
Polymorphic arguments (e.g. `Option<T>`) map to WhyML lower-case apostrophe tick-types, with generic references wrapped in why3 parentheses:
```whyml
type option 't =
  | Some 't
  | None
```

### Pattern Matching & Guard Translation:
Nested guard-checks are woven into WhyML pattern branches via clear conditional sub-blocks, ensuring flawless compatibility with Why3's default pattern-matching requirements:
```whyml
match opt with
  | Some v ->
    if (v > 5) then
      val := v
    else
      ()
  | Some v ->
    val := 100
  | None ->
    val := 0
end
```
