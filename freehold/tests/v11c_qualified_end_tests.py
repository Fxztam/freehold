from __future__ import annotations

V11C_QUALIFIED_END_TESTS = [
    ("v11c", "qualified module and procedure end OK", """
module EndDemo
procedure main()
is
    check true
end main
end EndDemo
""", True),

    ("v11c", "if end if OK", """
module EndIfDemo
procedure main()
is
    let x: Integer = 1
    if x = 1 then
        check true
    else
        check false
    end if
end main
end EndIfDemo
""", True),

    ("v11c", "while end while OK", """
module EndWhileDemo
procedure main()
is
    let i: Integer = 0
    while i < 2
        invariant i >= 0
        invariant i <= 2
        variant 2 - i
    do
        i := i + 1
    end while
    check i = 2
end main
end EndWhileDemo
""", True),

    ("v11c", "record end record OK", """
module EndRecordDemo
type Box is record
    amount: Integer
end record
procedure main()
is
    let b: Box = Box { amount: 1 }
    check b.amount = 1
end main
end EndRecordDemo
""", True),

    ("v11c", "naked procedure end fails", """
module NakedEndFails
procedure main()
is
    check true
end
end NakedEndFails
""", False),

    ("v11c", "wrong procedure end name fails", """
module WrongProcedureEndFails
procedure main()
is
    check true
end other
end WrongProcedureEndFails
""", False),

    ("v11c", "wrong module end name fails", """
module WrongModuleEndFails
procedure main()
is
    check true
end main
end OtherModule
""", False),

    ("v11c", "naked if end fails", """
module NakedIfEndFails
procedure main()
is
    if true then
        check true
    end
end main
end NakedIfEndFails
""", False),
]
