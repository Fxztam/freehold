# Freehold Specification: Sets
**Status:** Baseline specification-only ghost sets for contracts, invariants, SMT solving, and zero-runtime verification  
**Audience:** Freehold authors, verifier implementers, prover/backend authors, and developers writing contracts

This document explains Freehold's current `Set<T>` model.

Sets are not ordinary runtime collections. They are specification-only ghost values used to express mathematical properties in contracts and loop invariants:

```text
Set<T>                         ghost set type
Set<T> { a, b, c }              set literal expression
Set.contains(set, value)        membership predicate
Set.add(set, value)             pure set expression with value present
Set.remove(set, value)          pure set expression with value absent
Set.size(set)                   cardinality expression
requires / ensures              allowed contract locations
invariant                       allowed loop location
SMT-LIB / Z3                    proof backend representation
zero runtime footprint          no executable allocation or codegen state
```

The design goal is strict: sets help the verifier reason about mathematical membership, addition, removal, and size, but they must not appear as executable program state.

---

## 1. Ghost Model

`Set<T>` is a ghost type.

That means:

- It exists for verification.
- It is accepted inside specification expressions.
- It is translated to SMT expressions for the prover.
- It must not become a local runtime variable.
- It must not be stored in records or choices.
- It must not cross routine boundaries as a parameter or return value.
- It must not require Go/native runtime representation.

This makes `Set<T>` different from `Array<T,N>` and `Map<T>`.

Arrays and maps are ordinary typed values. Sets are contract-only mathematical structures.

---

## 2. Allowed Locations

The intended locations for `Set<T>` expressions are:

```freehold
requires Set.contains(Set<Integer> { 1, 2, 3 }, x)
ensures Set.size(Set<Integer> { 10, 20 }) = 2
invariant Set.contains(Set.add(Set<Integer> { 1 }, i), i)
check Set.size(Set<Integer> { 100, 200 }) = 2
```

The core use cases are:

```text
preconditions       requires
postconditions      ensures
loop invariants     invariant
verification checks check
```

A set expression is therefore valid when it remains inside proof-oriented expression evaluation and does not need storage in the executable program.

---

## 3. Syntax

A set literal names its element type explicitly:

```freehold
Set<Integer> { 1, 2, 3 }
Set<String> { "admin", "operator" }
Set<Boolean> { true, false }
```

The generic type name is part of the literal:

```text
Set<T> { item1, item2, ... }
```

Each item must type-check against `T`.

Example:

```freehold
requires Set.contains(Set<Integer> { 1, 2, 3 }, x)
```

Here `x` must be an `Integer`, because the set is `Set<Integer>`.

---

## 4. Type Checking

The verifier enforces element compatibility for literals and operations.

For a literal:

```freehold
Set<Integer> { 1, 2, 3 }
```

all items must be assignable to `Integer`.

For membership:

```freehold
Set.contains(Set<Integer> { 1, 2, 3 }, x)
```

`x` must be assignable to `Integer`.

For add/remove:

```freehold
Set.add(Set<Integer> { 1, 2 }, 3)
Set.remove(Set<Integer> { 1, 2 }, 1)
```

the second argument must match the element type of the first argument.

---

## 5. Membership

Use `Set.contains` to express membership:

```freehold
procedure test_set_contains(x: Integer)
requires Set.contains(Set<Integer> { 1, 2, 3 }, x)
is
    check x = 1 or x = 2 or x = 3
end test_set_contains
```

Signature shape:

```text
Set.contains(set: Set<T>, value: T) : Boolean
```

`Set.contains` is a predicate. It does not search a runtime collection. It becomes an SMT boolean expression.

---

## 6. Pure Add And Remove

`Set.add` and `Set.remove` are pure expression operations.

They do not mutate an existing set. They produce a new mathematical set expression:

```freehold
Set.add(Set<Integer> { 1, 2 }, 3)
Set.remove(Set<Integer> { 1, 2, 3 }, 3)
```

Signature shapes:

```text
Set.add(set: Set<T>, value: T) : Set<T>
Set.remove(set: Set<T>, value: T) : Set<T>
```

Example:

```freehold
procedure test_set_add_remove(x: Integer)
requires not Set.contains(Set.remove(Set.add(Set<Integer> { 1, 2 }, 3), 3), x)
is
    check x != 1 and x != 2
end test_set_add_remove
```

This precondition says that `x` is not contained after adding `3` and then removing `3` from `{1, 2}`. The remaining set is effectively `{1, 2}`, so the body proves `x != 1 and x != 2`.

---

## 7. Size

Use `Set.size` to express cardinality:

```freehold
procedure test_set_size()
requires Set.size(Set<Integer> { 10, 20, 30, 40 }) = 4
is
    check Set.size(Set<Integer> { 100, 200 }) = 2
end test_set_size
```

Signature shape:

```text
Set.size(set: Set<T>) : Integer
```

For set literals, the SMT translation can emit the literal item count directly:

```text
Set.size(Set<Integer> { 100, 200 }) -> 2
```

For non-literal set expressions, size is represented through an uninterpreted size function in the prover model:

```text
Set_size(set)
```

The current model is useful for simple literal cardinalities and proof constraints. It is not a full executable collection cardinality API.

---

## 8. Comprehensive Contract Example

Sets can be composed inside contracts:

```freehold
procedure test_comprehensive(x: Integer)
requires Set.size(Set<Integer> { 5, 6, 7 }) = 3
requires Set.contains(Set.add(Set.remove(Set<Integer> { 5, 6 }, 5), x), x)
is
    check Set.contains(Set.add(Set<Integer> { 6 }, x), x)
end test_comprehensive
```

This demonstrates three ideas:

- literal set size can be checked directly
- `Set.remove` and `Set.add` build new pure set expressions
- containment remains a boolean proof expression

No set is stored in program memory.

---

## 9. SMT Mapping

The prover maps `Set<T>` to a functional boolean array:

```text
Set<T> -> (Array T Bool)
```

The element type maps to an SMT sort:

```text
Set<Integer> -> (Array Int Bool)
Set<Boolean> -> (Array Bool Bool)
Set<Double>  -> (Array Real Bool)
Set<String>  -> (Array String Bool)
```

A set literal starts as a constant false array:

```smt2
((as const (Array Int Bool)) false)
```

Each literal element is added with `store`:

```smt2
(store S x true)
```

Membership becomes `select`:

```smt2
(select S x)
```

Adding an element becomes:

```smt2
(store S x true)
```

Removing an element becomes:

```smt2
(store S x false)
```

This is why sets are excellent for membership-style proof obligations: they map directly to solver array theory.

---

## 10. Zero Runtime Footprint

The verifier rejects executable uses of `Set<T>` so the compiler never has to allocate, store, pass, or return sets at runtime.

Forbidden categories:

```text
local variables
routine parameters
routine return types
record fields
choice constructor payloads
```

This is not an implementation gap. It is the safety rule that makes sets ghost-only.

---

## 11. Forbidden: Local Variables

Invalid:

```freehold
procedure main()
is
    let s: Set<Integer> = Set<Integer> { 1, 2 }
end main
```

Reason:

```text
Set<T> is specification-only and cannot be declared as a local variable.
```

Use the set expression directly in a contract or check instead:

```freehold
check Set.contains(Set<Integer> { 1, 2 }, 1)
```

---

## 12. Forbidden: Routine Parameters

Invalid:

```freehold
procedure process(s: Set<Integer>)
is
    skip
end process
```

Reason:

```text
Set<T> is specification-only and cannot be used as a routine parameter.
```

Do not pass sets as data. If a routine needs a runtime collection, use a runtime type such as `Array<T,N>` or `Map<T>` where appropriate.

---

## 13. Forbidden: Routine Returns

Invalid:

```freehold
function get_set() returns Set<Integer>
is
    return Set<Integer> { 1, 2 }
end get_set
```

Reason:

```text
Set<T> is specification-only and cannot be used as a routine return type.
```

A function may return runtime values, not ghost set structures.

---

## 14. Forbidden: Record Fields

Invalid:

```freehold
type MyRecord is record
    items: Set<Integer>
end record
```

Reason:

```text
Set<T> is specification-only and cannot be a record field.
```

Records describe runtime data layout. Sets do not have a runtime layout in the current model.

---

## 15. Forbidden: Choice Constructor Payloads

Invalid:

```freehold
type MyChoice is choice
    SomeConstructor(Set<Integer>)
end choice
```

Reason:

```text
Set<T> is specification-only and cannot be used in a choice constructor.
```

Choice constructors carry runtime payloads. Ghost sets cannot be carried as payload data.

---

## 16. Relationship To Arrays And Maps

Use `Set<T>` when you need a mathematical proof expression:

```freehold
requires Set.contains(Set<Integer> { 1, 2, 3 }, x)
```

Use `Array<T,N>` when you need indexed runtime storage:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
```

Use `Map<T>` when you need string-keyed runtime lookup/update:

```freehold
let scores: Map<Integer> = Map<Integer> { "Ada": 100 }
let updated: Map<Integer> = Map.set(scores, "Grace", 95)
```

The distinction is simple:

```text
Set<T>       proof-only, no runtime storage
Array<T,N>   runtime sequence with fixed length
Map<T>       runtime associative value keyed by String
```

---

## 17. Relationship To Verification

Sets are part of the verification language.

They are useful for writing compact contracts such as:

```freehold
requires Set.contains(Set<Integer> { 200, 201, 204 }, status_code)
```

or loop invariants such as:

```freehold
invariant Set.contains(Set<Integer> { 0, 1, 2, 3 }, state)
```

They should not be used to model changing runtime membership across loop iterations. If the program needs changing runtime membership, use a runtime data structure and then write contracts about its observable properties.

---

## 18. Common Failure Patterns

### 18.1 Treating Sets As Runtime Collections

Invalid:

```freehold
let allowed: Set<Integer> = Set<Integer> { 1, 2, 3 }
```

Use direct contract expressions or a runtime collection type.

### 18.2 Passing Sets To Helpers

Invalid:

```freehold
procedure validate(allowed: Set<Integer>, value: Integer)
```

Keep the set expression inside the contract where it is needed.

### 18.3 Returning Sets From Builder Functions

Invalid:

```freehold
function allowed_statuses() returns Set<Integer>
```

Sets are not runtime values and cannot be returned.

### 18.4 Putting Sets In Records

Invalid:

```freehold
type Config is record
    allowed_statuses: Set<Integer>
end record
```

A record field is runtime state. Use a runtime structure or keep the allowed set in contracts.

### 18.5 Wrong Element Type

Invalid:

```freehold
requires Set.contains(Set<Integer> { 1, 2, 3 }, "2")
```

The searched value must match the set element type.

### 18.6 Expecting Full Cardinality Reasoning For Derived Sets

Literal size is direct:

```freehold
Set.size(Set<Integer> { 1, 2 }) = 2
```

Derived set size may require stronger solver axioms than the current baseline exposes. Prefer membership proofs when possible.

---

## 19. Practical Checklist

Before committing code that uses `Set<T>`, check:

- The set appears only in proof-oriented expressions: `requires`, `ensures`, `invariant`, or `check`.
- No local variable has type `Set<T>`.
- No routine parameter has type `Set<T>`.
- No routine return type is `Set<T>`.
- No record field or choice payload has type `Set<T>`.
- Every set literal explicitly names its element type.
- Every literal item matches the set element type.
- `Set.contains`, `Set.add`, and `Set.remove` use values of the same element type as the set.
- `Set.size` is used mainly for simple literal cardinality or explicit proof constraints.
- Runtime membership requirements use runtime structures such as arrays or maps.
- Contracts remain readable enough that the mathematical intent is clear.

A good Freehold set expression is short, local to the contract that needs it, and erased from runtime. It helps the verifier prove membership and finite-domain facts without changing the executable program at all.
