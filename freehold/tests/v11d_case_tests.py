from __future__ import annotations

V11D_CASE_TESTS = [
    ("v11d", "case integer first branch OK", """
module CaseIntegerFirst
procedure main()
is
    let x: Integer = 1
    let y: Integer = 0
    case x is
        when 1 =>
            y := 10
        when 2 =>
            y := 20
        default =>
            y := 99
    end case
    check y = 10
end main
end CaseIntegerFirst
""", True),
    ("v11d", "case integer default OK", """
module CaseIntegerDefault
procedure main()
is
    let x: Integer = 3
    let y: Integer = 0
    case x is
        when 1 =>
            y := 10
        when 2 =>
            y := 20
        default =>
            y := 99
    end case
    check y = 99
end main
end CaseIntegerDefault
""", True),
    ("v11d", "case boolean OK", """
module CaseBoolean
procedure main()
is
    let b: Boolean = false
    let x: Integer = 0
    case b is
        when true =>
            x := 1
        default =>
            x := 2
    end case
    check x = 2
end main
end CaseBoolean
""", True),
    ("v11d", "case branch type mismatch fails", """
module CaseTypeMismatchFails
procedure main()
is
    let x: Integer = 1
    case x is
        when true =>
            check false
        default =>
            check true
    end case
end main
end CaseTypeMismatchFails
""", False),
    ("v11d", "case missing default fails", """
module CaseMissingDefaultFails
procedure main()
is
    let x: Integer = 1
    case x is
        when 1 =>
            check true
    end case
end main
end CaseMissingDefaultFails
""", False),
    ("v11d", "case duplicate branch fails", """
module CaseDuplicateBranchFails
procedure main()
is
    let x: Integer = 1
    case x is
        when 1 =>
            check true
        when 1 =>
            check false
        default =>
            check true
    end case
end main
end CaseDuplicateBranchFails
""", False),
    ("v11d", "case nested if OK", """
module CaseNestedIf
procedure main()
is
    let x: Integer = 2
    let y: Integer = 0
    case x is
        when 1 =>
            y := 1
        when 2 =>
            if x = 2 then
                y := 22
            else
                y := 99
            end if
        default =>
            y := 0
    end case
    check y = 22
end main
end CaseNestedIf
""", True),
]
