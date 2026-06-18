# Freehold Specification: Loop Invariants and Variants
**Status:** Baseline loop verification model  
**Audience:** Freehold authors, verifier implementers, conformance-test writers, and proof-oriented example authors

This document explains how to write and reason about Freehold `while` loops. It focuses on loop invariants, loop variants, and the practical snippets needed to prove counters, array updates, searches, and range transformations.

---

## 1. Loop Syntax

Freehold `while` statements have this shape:

```ebnf
while_stmt ::= 'while' expr invariant_clause+ variant_clause? 'do' loop_block 'end' 'while'
invariant_clause ::= 'invariant' expr
variant_clause   ::= 'variant' expr
```

In source form:

```freehold
while condition
    invariant condition_that_holds_before_and_after_each_iteration
    variant expression_that_decreases
do
    statements
end while
```

A loop must have at least one `invariant`. A `variant` is optional in the grammar, but should be treated as the normal safe style for loops that are expected to terminate.

---

## 2. What an Invariant Means

An invariant is a fact that must be true:

1. before the first loop iteration,
2. before each iteration body,
3. after each iteration body,
4. when the loop exits, combined with the negated loop condition.

The verifier uses invariants to bridge the gap between individual loop steps and the final postcondition.

Example:

```freehold
function increment_loop_good(x: Integer, n: Integer) returns Integer
requires n >= 0
requires x <= 2147483647 - n
ensures result = x + n
is
    let i: Integer = 0
    let y: Integer = x

    while i < n
        invariant i >= 0
        invariant i <= n
        invariant y = x + i
        variant n - i
    do
        y := y + 1
        i := i + 1
    end while

    return y
end increment_loop_good
```

At exit, the verifier knows:

```text
not (i < n)
i <= n
y = x + i
```

Together these imply `i = n`, therefore `y = x + n`, which proves the postcondition.

---

## 3. What a Variant Means

A variant is an integer-like measure that decreases each iteration. It is used to prove progress and termination.

For an increasing counter from `0` to `n`, use:

```freehold
variant n - i
```

For an increasing counter from `0` to a fixed length `10`, use:

```freehold
variant 10 - i
```

For an inclusive range update from `first` to `last`, use:

```freehold
variant last - i + 1
```

The variant should be non-negative while the loop condition holds and should get smaller after the body executes.

---

## 4. Minimal Counter Loop Snippet

Use this pattern when a loop increments a counter until a bound:

```freehold
let i: Integer = 0

while i < n
    invariant i >= 0
    invariant i <= n
    variant n - i
do
    i := i + 1
end while
```

The two range invariants are not decorative. They tell the verifier that `i` stays inside the expected interval. Without them, later array bounds, arithmetic bounds, and postconditions often become unprovable.

---

## 5. Counter With Accumulated Value

When a loop maintains a derived value, add a relation invariant between the counter and the value:

```freehold
let i: Integer = 0
let y: Integer = x

while i < n
    invariant i >= 0
    invariant i <= n
    invariant y = x + i
    variant n - i
do
    y := y + 1
    i := i + 1
end while

return y
```

The key invariant is:

```freehold
invariant y = x + i
```

It captures the loop's meaning. The counter invariants capture the loop's safety.

---

## 6. Array Fill Snippet

When filling an array prefix, the invariant should describe the part already processed.

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

Important pieces:

- `i >= 0` and `i <= 32` keep the counter in range.
- `for all j in 0..i-1 => a[j] = v` says the processed prefix is filled.
- `variant 32 - i` decreases as `i` increases.
- `modifies a` is required because the loop mutates array elements.

At loop exit, `i = 32`, so the processed prefix `0..i-1` is exactly `0..31`.

---

## 7. Array Map/Transform Snippet

When transforming an array into a new array, describe both the processed and unprocessed regions.

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

This pattern is useful whenever the output starts as a copy of the input:

```text
processed prefix:   b[k] = transformed a[k]
unprocessed suffix: b[k] = original a[k]
```

The precondition prevents overflow in `b[i] + 1`.

---

## 8. Counting Snippet

When counting elements satisfying a condition, maintain bounds on the counter and a logical relation to the scanned prefix.

```freehold
function count_arr_zero(a: Array<Integer, 10>) returns Integer
ensures result >= 0
ensures result <= 10
ensures (result = 0) = (for all j in 0..9 => a[j] != 0)
is
    let i: Integer = 0
    let counter: Integer = 0

    while i < 10
        invariant i >= 0
        invariant i <= 10
        invariant counter >= 0
        invariant counter <= i
        invariant (counter = 0) = (for all k in 0..i-1 => a[k] != 0)
        variant 10 - i
    do
        if a[i] = 0 then
            counter := counter + 1
        end if
        i := i + 1
    end while

    return counter
end count_arr_zero
```

The invariant `counter <= i` connects the count to the number of inspected elements. The quantified invariant explains what `counter = 0` means for the scanned prefix.

---

## 9. Search With Early Return Snippet

When searching for a value and returning early, the invariant describes what has not been found yet in the scanned prefix.

```freehold
type SearchResult is record
    found: Boolean
    pos: Integer
end record

function search_arr_zero(a: Array<Integer, 10>) returns SearchResult
ensures result.found = (for some j in 0..9 => a[j] = 0)
ensures not result.found or a[result.pos] = 0
ensures result.found or result.pos = 0
is
    let i: Integer = 0

    while i < 10
        invariant i >= 0
        invariant i <= 10
        invariant for all k in 0..i-1 => a[k] != 0
        variant 10 - i
    do
        if a[i] = 0 then
            return SearchResult { found: true, pos: i }
        end if
        i := i + 1
    end while

    return SearchResult { found: false, pos: 0 }
end search_arr_zero
```

The important invariant is:

```freehold
invariant for all k in 0..i-1 => a[k] != 0
```

It says: if the loop has reached `i`, no earlier index contained the target.

---

## 10. Range Update Snippet

For an inclusive update range, initialize the loop index to `first`, keep it between `first` and `last + 1`, and describe the updated range prefix.

```freehold
function update_range_arr_zero(a: Array<Integer, 10>, first: Integer, last: Integer) returns Array<Integer, 10>
requires first >= 0
requires first <= 9
requires last >= 0
requires last <= 9
requires first <= last
ensures for all j in 0..9 => (not (j >= first and j <= last) or result[j] = 0) and ((j >= first and j <= last) or result[j] = a[j])
is
    let i: Integer = first
    let b: Array<Integer, 10> = a

    while i <= last
        invariant i >= first
        invariant i <= last + 1
        invariant for all k in 0..9 => (not (k >= first and k < i) or b[k] = 0) and ((k >= first and k < i) or b[k] = a[k])
        variant last - i + 1
    do
        b[i] := 0
        i := i + 1
    end while

    return b
end update_range_arr_zero
```

This is the general range-update pattern:

```text
already updated: first <= k < i
not yet updated: outside that range
loop exits with: i = last + 1
```

---

## 11. How to Derive an Invariant

Use this five-step method:

1. Identify the loop index and its legal range.
2. Write lower and upper bound invariants for the index.
3. Identify what portion of the data has already been processed.
4. Write a quantified invariant for the processed portion.
5. Add a variant that decreases as the processed portion grows.

For a prefix loop over `0..9`, this usually starts as:

```freehold
while i < 10
    invariant i >= 0
    invariant i <= 10
    invariant for all k in 0..i-1 => processed_property(k)
    variant 10 - i
do
    ...
end while
```

For an inclusive custom range `first..last`, start as:

```freehold
while i <= last
    invariant i >= first
    invariant i <= last + 1
    invariant for all k in first..i-1 => processed_property(k)
    variant last - i + 1
do
    ...
end while
```

---

## 12. Common Mistakes

### 12.1 Only Stating the Bounds

This is often too weak:

```freehold
while i < n
    invariant i >= 0
    invariant i <= n
    variant n - i
do
    y := y + 1
    i := i + 1
end while
```

It proves `i` is safe, but not what `y` means. Add the relation:

```freehold
invariant y = x + i
```

### 12.2 Forgetting the Unprocessed Region

When an output array starts as a copy of an input array, proving only the processed prefix may be insufficient. Add an invariant for the suffix that is not changed yet:

```freehold
invariant for all k in i..9 => b[k] = a[k]
```

### 12.3 Wrong Exit Bound

For loops using `while i <= last`, the exit index is usually `last + 1`, not `last`.

Use:

```freehold
invariant i <= last + 1
variant last - i + 1
```

### 12.4 Missing Mutation Frame

If the loop mutates a parameter array or record field, the enclosing routine needs a `modifies` clause:

```freehold
function fill(a: Array<Integer, 32>, v: Integer) returns Boolean
modifies a
...
is
    ...
end fill
```

### 12.5 Missing Arithmetic Preconditions

If the loop increments values, add preconditions that prevent overflow:

```freehold
requires for all j in 0..9 => a[j] < 2147483647
```

Then the body can safely prove:

```freehold
b[i] := b[i] + 1
```

---

## 13. Practical Checklist

Before committing a loop, check:

- The loop has at least one `invariant`.
- Counter loops include lower and upper bound invariants.
- The invariant describes the processed portion of the data.
- Array loops use quantifiers for prefixes, suffixes, or ranges.
- The postcondition follows from invariants plus loop exit condition.
- The `variant` decreases on every iteration.
- Array index expressions are protected by bounds invariants.
- Mutating loops have an enclosing `modifies` clause when they update parameters or globals.
- Arithmetic in the loop body has enough `requires` protection to avoid overflow.

A good invariant is not a comment. It is the contract between one loop iteration and the next.
