# Freehold Specification: Arrays
**Status:** Baseline fixed-size array type, literals, indexing, mutation, quantifiers, and verification rules  
**Audience:** Freehold authors, verifier implementers, conformance-test writers, and backend authors

This document explains Freehold arrays. Arrays are fixed-size, typed collections with integer indexes.

The core model is:

```text
Array<T, N>       fixed-size array of N elements of type T
[1, 2, 3]         array literal
xs[0]             zero-based index access
xs[i] := value    element update
for all i in A..B => expr
for some i in A..B => expr
```

Arrays are ordinary values. Their element type and length are part of the type.

---

## 1. Array Type

An array type is written with an element type and a fixed size:

```freehold
Array<Integer, 3>
Array<String, 2>
Array<Employee, 10>
```

The grammar shape is:

```ebnf
array_type ::= NAME '<' type_ref ',' INT_NUMBER '>'
```

The first argument is the element type. The second argument is the fixed length.

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
```

The type `Array<Integer, 3>` is not the same as `Array<Integer, 2>` and not the same as `Array<Boolean, 3>`.

---

## 2. Array Literal

An array literal is written with square brackets:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
```

The literal length must match the declared array length.

Valid:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
```

Invalid:

```freehold
let values: Array<Integer, 3> = [1, 2]
```

The declared type expects 3 elements, but the literal has 2.

---

## 3. Empty Arrays

Empty arrays are allowed when the declared length is zero:

```freehold
let values: Array<Integer, 0> = []
```

An empty literal must be given a target array type by the surrounding declaration, assignment, or return context.

---

## 4. Element Type Checking

Every literal element must be assignable to the array element type.

Valid:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
```

Invalid:

```freehold
let values: Array<Integer, 3> = [1, true, 3]
```

The second element is `Boolean`, not `Integer`.

Element type is exact under the verifier's assignment rules. This is invalid:

```freehold
let values: Array<Double, 3> = [1, 2, 3]
```

The literal elements are integer values, while the target element type is `Double`.

---

## 5. Index Access

Array index access uses square brackets:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
check values[1] = 2
```

Indexes are zero-based. For `Array<T, 3>`, valid indexes are:

```text
0, 1, 2
```

Static out-of-bounds indexes are rejected:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
check values[3] = 0
```

The index `3` is outside `0..2`.

---

## 6. Index Type Rule

Array indexes must be integer expressions.

Valid:

```freehold
let i: Integer = 1
let value: Integer = values[i]
```

Invalid:

```freehold
check values[true] = 1
```

The verifier rejects this because the index is `Boolean`, not `Integer`.

Indexing also requires the target to be an array:

```freehold
let amount: Integer = 1
check amount[0] = 1
```

This is rejected because `amount` is an `Integer`, not an array.

---

## 7. Returning Arrays

Functions can return arrays:

```freehold
function values() returns Array<Integer, 3>
is
    return [1, 2, 3]
end values
```

The returned literal must match the declared return type.

```freehold
procedure main()
is
    let xs: Array<Integer, 3> = values()
    check xs[0] = 1
end main
```

A size mismatch is rejected:

```freehold
function values() returns Array<Integer, 3>
is
    return [1, 2, 3]
end values

procedure main()
is
    let xs: Array<Integer, 2> = values()
end main
```

An element type mismatch is also rejected:

```freehold
let flags: Array<Boolean, 3> = values()
```

---

## 8. Arrays in `Result`

Arrays can be success payloads in `Result<T,E>` functions:

```freehold
error NotFound

function collect() returns Result<Array<Integer, 3>, NotFound>
is
    return ok [1, 2, 3]
end collect
```

Postconditions can describe result array elements with `value[index]`:

```freehold
function ok_array(a: Integer, b: Integer) returns Result<Array<Integer, 2>, NotFound>
ensures success, value[0] = a, value[1] = b
is
    return ok [a, b]
end ok_array
```

For non-`Result` functions, use `result[index]` in postconditions:

```freehold
function make_pair(a: Integer, b: Integer) returns Array<Integer, 2>
ensures result[0] = a
ensures result[1] = b
is
    return [a, b]
end make_pair
```

---

## 9. Element Update

Array elements can be updated with `:=`:

```freehold
function map_arr_incr(a: Array<Integer, 10>) returns Array<Integer, 10>
requires for all j in 0..9 => a[j] < 2147483647
ensures for all j in 0..9 => result[j] = a[j] + 1
is
    let i: Integer = 0
    let b: Array<Integer, 10> = a

    while i < 10
        invariant i >= 0
        invariant i <= 10
        invariant for all k in 0..i-1 => b[k] = a[k] + 1
        invariant for all k in i..9 => b[k] = a[k]
        variant 10 - i
    do
        b[i] := b[i] + 1
        i := i + 1
    end while

    return b
end map_arr_incr
```

The update target must be an array, the index must be `Integer`, and the assigned value must match the element type.

---

## 10. Array Mutation and `modifies`

When a routine mutates an array parameter, declare the mutation frame:

```freehold
procedure set_first(a: Array<Integer, 3>, v: Integer)
modifies a
is
    a[0] := v
end set_first
```

Without `modifies a`, a parameter mutation is rejected by modern framing rules.

For local arrays, a common value-oriented pattern is to copy the input into a local, mutate the local, and return it:

```freehold
let b: Array<Integer, 10> = a
b[i] := b[i] + 1
return b
```

---

## 11. Quantifiers Over Arrays

Array properties are often stated with quantifiers:

```freehold
function verify_quantifiers(arr: Array<Integer, 3>) returns Boolean
is
    let all_positive: Boolean = for all I in 0..2 => arr[I] >= 0
    let some_zero: Boolean = for some I in 0..2 => arr[I] = 0
    return all_positive and some_zero
end verify_quantifiers
```

Use quantifiers in contracts to describe whole-array behavior:

```freehold
function fill(a: Array<Integer, 32>, v: Integer) returns Boolean
modifies a
ensures for all k in 0..31 => a[k] = v
is
    let i: Integer = 0
    while i <= 31
        invariant i >= 0
        invariant i <= 32
        invariant for all j in 0..i-1 => a[j] = v
        variant 32 - i
    do
        a[i] := v
        i := i + 1
    end while
    return true
end fill
```

The quantifier range should match valid array indexes.

---

## 12. Loop Pattern for Arrays

For an array of length `N`, the basic prefix loop is:

```freehold
let i: Integer = 0
while i < N
    invariant i >= 0
    invariant i <= N
    invariant for all k in 0..i-1 => processed_property(k)
    variant N - i
do
    ... use a[i] ...
    i := i + 1
end while
```

For `Array<T, 10>`:

```freehold
while i < 10
    invariant i >= 0
    invariant i <= 10
    variant 10 - i
do
    let value: T = a[i]
    i := i + 1
end while
```

The upper bound invariant `i <= N` is what lets the verifier reason about exit. The loop condition `i < N` is what makes `a[i]` safe inside the body.

---

## 13. Arrays in Records and JSON

Arrays can appear as record fields:

```freehold
type BroadcastEnvelope is record
    event: String
    recipients: Array<String, 2>
end record
```

When such records are used with `Json.parse<Record>` or `Json.stringify`, array length is part of the schema. A JSON array for `Array<String, 2>` must contain exactly two items.

Arrays can also appear in gRPC/protobuf IDL records, where they map to `repeated` fields in proto generation when the element type is supported.

---

## 14. Nested Arrays

The current baseline syntax and verifier focus on arrays whose element type is a normal type or record type. Nested array literals such as this are rejected in current conformance tests:

```freehold
let values: Array<Integer, 2> = [[1], [2]]
```

Model multidimensional data with records or explicit fixed-size fields until nested-array support has clear language rules.

---

## 15. Common Failure Patterns

### 15.1 Length Mismatch

Invalid:

```freehold
let values: Array<Integer, 3> = [1, 2]
```

The literal has length 2, but the type requires length 3.

### 15.2 Element Type Mismatch

Invalid:

```freehold
let values: Array<Integer, 3> = [1, true, 3]
```

All elements must be assignable to the declared element type.

### 15.3 Index Type Mismatch

Invalid:

```freehold
check values[true] = 1
```

Array indexes must be `Integer`.

### 15.4 Static Index Out of Bounds

Invalid:

```freehold
let values: Array<Integer, 3> = [1, 2, 3]
check values[3] = 0
```

For length 3, valid indexes are `0`, `1`, and `2`.

### 15.5 Indexing a Scalar

Invalid:

```freehold
let amount: Integer = 1
check amount[0] = 1
```

Only arrays and map values support index syntax. For arrays, the target must be an `Array<T, N>`.

### 15.6 Assigning Arrays of Different Size

Invalid:

```freehold
function values() returns Array<Integer, 3>
is
    return [1, 2, 3]
end values

let xs: Array<Integer, 2> = values()
```

Array size is part of the type.

### 15.7 Assigning Arrays of Different Element Type

Invalid:

```freehold
let flags: Array<Boolean, 3> = values()
```

Array element type is part of the type.

---

## 16. Practical Checklist

Before committing array code, check:

- The type is written as `Array<T, N>` with a fixed size.
- Array literals contain exactly `N` elements.
- Every element is assignable to `T`.
- Indexes are `Integer` expressions.
- Static indexes are in `0..N-1`.
- Loops over arrays use invariants that keep the index in range.
- Quantifier ranges match valid index ranges.
- Functions returning arrays return the exact element type and size.
- `Result<Array<T,N>, E>` functions use `return ok [ ... ]`.
- Mutating array parameters declare `modifies a`.
- JSON records with array fields use the exact expected array length.

A good Freehold array program makes length, element type, and index safety visible in the type and in the loop invariants.
