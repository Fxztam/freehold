from __future__ import annotations

V11I_GENERICS_TESTS = [
    ("v11i_generics", "scalar generic function identity OK", """
module ScalarGenericIdentity
function identity<T>(x: T) returns T
is
    return x
end identity

procedure main()
is
    let val_int: Integer = identity<Integer>(42)
    let val_bool: Boolean = identity<Boolean>(true)
    let val_str: String = identity<String>("VeraFlow")
    check val_int = 42
    check val_bool = true
    check val_str = "VeraFlow"
end main
end ScalarGenericIdentity
""", True),

    ("v11i_generics", "record generic field mapping OK", """
module RecordGenericMapping
type Box<T> is record
    item: T
end record

function unpack<T>(b: Box<T>) returns T
is
    return b.item
end unpack

procedure main()
is
    let b_int: Box<Integer> = Box<Integer> { item: 100 }
    let b_str: Box<String> = Box<String> { item: "Vera" }
    
    let val_int: Integer = unpack<Integer>(b_int)
    let val_str: String = unpack<String>(b_str)
    
    check val_int = 100
    check val_str = "Vera"
end main
end RecordGenericMapping
""", True),

    ("v11i_generics", "array generic mapping OK", """
module ArrayGenericMapping

function first_elem<T>(arr: Array<T, 3>) returns T
is
    return arr[0]
end first_elem

procedure main()
is
    let arr_int: Array<Integer, 3> = [10, 20, 30]
    
    let first_int: Integer = first_elem<Integer>(arr_int)
    
    check first_int = 10
end main
end ArrayGenericMapping
""", True),

    ("v11i_generics", "generic nested routine calls OK", """
module NestedGenericRoutines
function outer<T>(x: T) returns T
is
    return inner<T>(x)
end outer

function inner<T>(y: T) returns T
is
    return y
end inner

procedure main()
is
    let res: Integer = outer<Integer>(999)
    check res = 999
end main
end NestedGenericRoutines
""", True),

    ("v11i_generics", "type variable keyword conflict test (VF-N002) OK", """
module TypeVariableConflict
-- VF-N002: testing naming of type parameters against keywords or reserved names
-- We use Type as our parameter name which may shadow type keywords but should parse and compile
function keyword_shadow<Type>(arg: Type) returns Type
is
    return arg
end keyword_shadow

procedure main()
is
    let res: Integer = keyword_shadow<Integer>(777)
    check res = 777
end main
end TypeVariableConflict
""", True),

    ("v11i_generics", "invalid generic call type mismatch fails", """
module GenericTypeMismatchFails
function check_item<T>(val: T, expected: T) returns Boolean
is
    return true
end check_item

procedure main()
is
    -- Should fail to type-check as arguments should match T
    let res: Boolean = check_item<Integer>(10, "string_mismatch")
end main
end GenericTypeMismatchFails
""", False),
]
