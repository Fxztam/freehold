from __future__ import annotations

V11K_SET_TESTS = [
    ("v11k", "set in contract requirements OK", """
module SetInContracts
procedure test_set_properties(x: Integer)
requires Set.contains(Set<Integer> { 1, 2, 3 }, x)
is
    check x = 1 or x = 2 or x = 3
end test_set_properties
end SetInContracts
""", True),

    ("v11k", "set operations add remove spec OK", """
module SetOperationsSpec
procedure check_add_remove(x: Integer)
requires not Set.contains(Set.remove(Set.add(Set<Integer> { 1, 2 }, 3), 3), x)
is
    check x != 1 and x != 2
end check_add_remove
end SetOperationsSpec
""", True),

    ("v11k", "set local variable declaration fails", """
module SetLocalVarFails
procedure main()
is
    let s: Set<Integer> = Set<Integer> { 1, 2 }
end main
end SetLocalVarFails
""", False),

    ("v11k", "set routine parameter fails", """
module SetParamFails
procedure process(s: Set<Integer>)
is
    skip
end process
end SetParamFails
""", False),

    ("v11k", "set routine return fails", """
module SetReturnFails
function get_set() returns Set<Integer>
is
    return Set<Integer> { 1, 2 }
end get_set
end SetReturnFails
""", False),

    ("v11k", "set record field fails", """
module SetRecordFieldFails
type MyRecord is record
    items: Set<Integer>
end record
end SetRecordFieldFails
""", False),

    ("v11k", "set choice constructor fails", """
module SetChoiceConstructorFails
type MyChoice is choice
    SomeConstructor(Set<Integer>)
end choice
end SetChoiceConstructorFails
""", False),
]
