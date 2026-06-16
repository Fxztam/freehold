from __future__ import annotations

V11J_MAP_TESTS = [
    ("v11j", "map literal and size OK", """
module MapLiteralAndSize
procedure main()
is
    let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
    let s: Integer = Map.size(m)
    check s = 2
end main
end MapLiteralAndSize
""", True),

    ("v11j", "map indexing success OK", """
module MapIndexingSuccess
procedure main()
is
    let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
    let r: Result<Integer, SchemaError> = m["Alice"]
    check r.ok = true
    check r.value = 95
end main
end MapIndexingSuccess
""", True),

    ("v11j", "map indexing failure OK", """
module MapIndexingFailure
procedure main()
is
    let m: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
    let r: Result<Integer, SchemaError> = m["Charlie"]
    check r.ok = false
end main
end MapIndexingFailure
""", True),

    ("v11j", "map keys OK", """
module MapKeys
procedure main()
is
    let m: Map<Integer> = Map<Integer> { "Alice": 95 }
    let keys: Array<String, 16> = Map.keys(m)
    check keys[0] = "Alice"
end main
end MapKeys
""", True),

    ("v11j", "map set and update OK", """
module MapSetAndUpdate
procedure main()
is
    let m1: Map<Integer> = Map<Integer> { "Alice": 95 }
    let m2: Map<Integer> = Map.set(m1, "Bob", 80)
    let m3: Map<Integer> = Map.set(m2, "Alice", 99)

    let s1: Integer = Map.size(m1)
    let s2: Integer = Map.size(m2)
    let s3: Integer = Map.size(m3)

    check s1 = 1
    check s2 = 2
    check s3 = 2

    let r_alice: Result<Integer, SchemaError> = m3["Alice"]
    let r_bob: Result<Integer, SchemaError> = m3["Bob"]

    check r_alice.ok = true
    check r_alice.value = 99
    check r_bob.ok = true
    check r_bob.value = 80
end main
end MapSetAndUpdate
""", True),

    ("v11j", "map remove OK", """
module MapRemove
procedure main()
is
    let m1: Map<Integer> = Map<Integer> { "Alice": 95, "Bob": 80 }
    let m2: Map<Integer> = Map.remove(m1, "Alice")
    
    let s1: Integer = Map.size(m1)
    let s2: Integer = Map.size(m2)

    check s1 = 2
    check s2 = 1

    let r_alice: Result<Integer, SchemaError> = m2["Alice"]
    let r_bob: Result<Integer, SchemaError> = m2["Bob"]

    check r_alice.ok = false
    check r_bob.ok = true
    check r_bob.value = 80
end main
end MapRemove
""", True),

    ("v11j", "map type mismatch fail", """
module MapTypeMismatchFail
procedure main()
is
    let m: Map<String> = Map<Integer> { "Alice": 95 }
end main
end MapTypeMismatchFail
""", False),

    ("v11j", "map index type mismatch fail", """
module MapIndexTypeMismatchFail
procedure main()
is
    let m: Map<Integer> = Map<Integer> { "Alice": 95 }
    let r: Result<Integer, SchemaError> = m[123]
end main
end MapIndexTypeMismatchFail
""", False),

    ("v11j", "map value range bound check fail", """
module MapValueRangeBoundCheckFail
type Percent is Integer range 0..100
procedure main()
is
    let m: Map<Percent> = Map<Percent> { "Alice": 105 }
end main
end MapValueRangeBoundCheckFail
""", False),

    ("v11j", "map record values OK", """
module MapRecordValues
type Student is record
    score: Integer
end record
procedure main()
is
    let s: Student = Student { score: 95 }
    let m: Map<Student> = Map<Student> { "Alice": s }
    let r: Result<Student, SchemaError> = m["Alice"]
    check r.ok = true
    check r.value.score = 95
end main
end MapRecordValues
""", True),
]
