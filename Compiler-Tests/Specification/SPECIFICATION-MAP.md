# Freehold Specification: Map
**Status:** Baseline generic map type, string-keyed lookup, functional updates, and verifier rules  
**Audience:** Freehold authors, verifier implementers, conformance-test writers, and backend authors

This document explains Freehold `Map<T>`. A map is a finite key/value collection with `String` keys and values of one declared type `T`.

The core model is:

```text
Map<T>                    map from String keys to T values
Map<T> { "key": value }   typed map literal
m["key"]                  lookup returning Result<T, SchemaError>
Map.keys(m)               bounded key array
Map.size(m)               number of entries
Map.set(m, key, value)    returns a new map with key set
Map.remove(m, key)        returns a new map with key removed
```

Maps are ordinary typed values. `Map.set` and `Map.remove` do not mutate the original map in place; they return a new map value.

---

## 1. Map Type

A map type is written with one type argument:

```freehold
Map<Integer>
Map<String>
Map<Employee>
```

The key type is always `String`. The type argument is the value type.

```freehold
type Employee is record
    age: Integer
    role: String
end record

let scores: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
let employees: Map<Employee> = Map<Employee> {
    "Alice": Employee { age: 30, role: "Engineer" }
}
```

---

## 2. Map Literal Syntax

A map literal is typed explicitly:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
```

The grammar shape is:

```ebnf
map_literal ::= type_ref '{' map_entries? '}'
map_entries ::= map_entry (',' map_entry)*
map_entry   ::= ESCAPED_STRING ':' expr
```

Keys in literals are string literals:

```freehold
Map<Integer> { "Alice": 95 }
```

The values must be assignable to the map value type. This is invalid:

```freehold
let m: Map<String> = Map<Integer> { "Alice": 95 }
```

The declared variable type is `Map<String>`, but the literal is `Map<Integer>`.

---

## 3. Value Type Checking

Each map entry is checked against the value type.

```freehold
type Percent is Integer range 0..100

let ok: Map<Percent> = Map<Percent> { "Alice": 95 }
```

Out-of-range values are rejected:

```freehold
type Percent is Integer range 0..100

let bad: Map<Percent> = Map<Percent> { "Alice": 105 }
```

The value `105` is not assignable to `Percent`.

---

## 4. Lookup With `m[key]`

Map lookup uses index syntax:

```freehold
let r: Result<Integer, SchemaError> = m["Alice"]
```

A map lookup does not return the value directly. It returns a `Result<T, SchemaError>`:

```text
m[key] : Result<T, SchemaError>
```

Successful lookup:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
let r: Result<Integer, SchemaError> = m["Alice"]
check r.ok = true
check r.value = 95
```

Missing key:

```freehold
let r2: Result<Integer, SchemaError> = m["Charlie"]
check r2.ok = false
```

Use `.ok` before reading `.value`.

---

## 5. Key Type Rule

Map keys are always strings. The index expression must have type `String`.

Valid:

```freehold
let key: String = "Alice"
let r: Result<Integer, SchemaError> = m[key]
```

Invalid:

```freehold
let r: Result<Integer, SchemaError> = m[123]
```

The verifier rejects this because the map index is `Integer`, not `String`.

---

## 6. `Map.size`

`Map.size` returns the number of entries:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
let size: Integer = Map.size(m)
check size = 2
```

The argument must be a map:

```freehold
Map.size(m) : Integer
```

Use `Map.size` as the iteration bound when walking keys.

---

## 7. `Map.keys`

`Map.keys` returns the keys as an array:

```freehold
let keys: Array<String, 16> = Map.keys(m)
```

Current baseline behavior:

```text
Map.keys(m) : Array<String, 16>
```

The returned array is bounded to 16 entries. Runtime behavior pads unused slots with empty strings. Use `Map.size(m)` as the loop bound so the padding is ignored.

```freehold
let keys: Array<String, 16> = Map.keys(m)
let size: Integer = Map.size(m)
let i: Integer = 0
while i < size
invariant i >= 0
variant size - i
do
    let key: String = keys[i]
    let r: Result<Integer, SchemaError> = m[key]
    if r.ok = true then
        ...
    end if
    i := i + 1
end while
```

Do not iterate over all 16 positions unless empty padding is meaningful for the algorithm.

---

## 8. Iterating and Summing Values

A common pattern is to iterate over `Map.keys`, look each key up, and use the value only when lookup succeeds:

```freehold
function add(m: Map<Integer>) returns Integer
is
    let sum: Integer = 0
    let keys: Array<String, 16> = Map.keys(m)
    let size: Integer = Map.size(m)
    let i: Integer = 0
    while i < size
    invariant i >= 0
    variant size - i
    do
        let key: String = keys[i]
        let r: Result<Integer, SchemaError> = m[key]
        if r.ok = true then
            sum := sum + r.value
        end if
        i := i + 1
    end while
    return sum
end add
```

The lookup still returns a `Result` even though the key came from `Map.keys`. This keeps lookup behavior uniform and explicit.

---

## 9. `Map.set`

`Map.set` returns a new map with one key assigned:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
let m2: Map<Integer> = Map.set(m, "Charlie", 70)
check Map.size(m2) = 3
```

Type shape:

```text
Map.set(m: Map<T>, key: String, value: T) : Map<T>
```

The value must match the map's value type:

```freehold
let employees: Map<Employee> = Map<Employee> {
    "Alice": Employee { age: 30, role: "Engineer" }
}
let employees2: Map<Employee> = Map.set(employees, "Bob", Employee { age: 35, role: "Manager" })
```

Setting an existing key is an update:

```freehold
let bob_lookup: Result<Employee, SchemaError> = employees2["Bob"]
check bob_lookup.ok = true
let bob_data: Employee = bob_lookup.value
let bob_updated: Employee = Employee { age: bob_data.age + 1, role: "Senior Manager" }
let employees3: Map<Employee> = Map.set(employees2, "Bob", bob_updated)
```

---

## 10. `Map.remove`

`Map.remove` returns a new map without one key:

```freehold
let m3: Map<Integer> = Map.remove(m2, "Alice")
check Map.size(m3) = 2
let removed: Result<Integer, SchemaError> = m3["Alice"]
check removed.ok = false
```

Type shape:

```text
Map.remove(m: Map<T>, key: String) : Map<T>
```

Removing a key does not mutate the original map value. It returns a new map value.

---

## 11. Functional Update and Reassignment

`Map.set` and `Map.remove` are functional operations. They produce a new map.

```freehold
let demo_start: Map<Integer> = Map<Integer> { "X": 10 }
let demo_add: Map<Integer> = Map.set(demo_start, "Y", 20)
let demo_remove: Map<Integer> = Map.remove(demo_add, "Y")
```

If you want to keep using the same local variable, reassign it with `:=`:

```freehold
let mut_map: Map<Integer> = Map<Integer> { "Initial": 100 }
mut_map := Map.set(mut_map, "First", 10)
mut_map := Map.set(mut_map, "Second", 20)
mut_map := Map.set(mut_map, "Third", 30)
check Map.size(mut_map) = 4
```

The mutation here is local-variable reassignment. The map operation itself still returns a new value.

---

## 12. Map With Record Values

Maps can store records:

```freehold
type Employee is record
    age: Integer
    role: String
end record

let emp_map: Map<Employee> = Map<Employee> {
    "Alice": Employee { age: 30, role: "Engineer" }
}
```

Insert another record:

```freehold
let emp_map_2: Map<Employee> = Map.set(emp_map, "Bob", Employee { age: 35, role: "Manager" })
check Map.size(emp_map_2) = 2
```

Lookup and use fields after checking `.ok`:

```freehold
let bob_lookup: Result<Employee, SchemaError> = emp_map_2["Bob"]
check bob_lookup.ok = true
check bob_lookup.value.age = 35
check bob_lookup.value.role = "Manager"
```

Update a record by constructing a replacement value and setting it back into the map:

```freehold
let bob_data: Employee = bob_lookup.value
let bob_updated: Employee = Employee { age: bob_data.age + 1, role: "Senior Manager" }
let emp_map_3: Map<Employee> = Map.set(emp_map_2, "Bob", bob_updated)
```

---

## 13. Result Discipline

Because lookup returns a `Result`, map code should follow the same discipline as other result-returning operations.

Safe:

```freehold
let r: Result<Integer, SchemaError> = m["Alice"]
if r.ok = true then
    let value: Integer = r.value
end if
```

Risky idea:

```freehold
let value: Integer = m["Alice"].value
```

Even when a key is expected to exist, keep the `.ok` check close to the use. Missing keys are data errors, not crashes.

---

## 14. Common Failure Patterns

### 14.1 Literal Type Mismatch

Invalid:

```freehold
let m: Map<String> = Map<Integer> { "Alice": 95 }
```

The literal is `Map<Integer>`, not `Map<String>`.

### 14.2 Wrong Index Type

Invalid:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95 }
let r: Result<Integer, SchemaError> = m[123]
```

Map indexes must be `String`.

### 14.3 Value Outside Range

Invalid:

```freehold
type Percent is Integer range 0..100
let m: Map<Percent> = Map<Percent> { "Alice": 105 }
```

The map value must satisfy the declared value type.

### 14.4 Treating Lookup as Direct Value

Invalid idea:

```freehold
let score: Integer = m["Alice"]
```

Lookup returns `Result<Integer, SchemaError>`, not `Integer`.

### 14.5 Forgetting to Store `Map.set` Result

This does not change `m` for later use:

```freehold
let m: Map<Integer> = Map<Integer> { "Alice": 95 }
let ignored: Map<Integer> = Map.set(m, "Bob", 80)
check Map.size(m) = 1
```

Use the returned value:

```freehold
let m2: Map<Integer> = Map.set(m, "Bob", 80)
check Map.size(m2) = 2
```

Or reassign:

```freehold
m := Map.set(m, "Bob", 80)
```

---

## 15. Practical Checklist

Before committing map code, check:

- The map value type is explicit: `Map<T>`.
- Literal keys are string literals.
- Runtime lookup keys are `String` expressions.
- Every map literal value is assignable to `T`.
- Lookups are typed as `Result<T, SchemaError>`.
- `.value` is only used after `.ok` is known.
- `Map.size(m)` is used as the loop bound for `Map.keys(m)`.
- `Map.set` and `Map.remove` results are assigned to a new variable or reassigned with `:=`.
- Record values are updated by constructing a replacement record and storing it with `Map.set`.
- Range-constrained value types are respected in literals and updates.

A good Freehold map program treats missing keys as explicit result failures and keeps updates value-oriented.
