from __future__ import annotations

V11F_STRING_TESTS = [
    ("v11f", "string literal OK", """
module StringLiteral
procedure main()
is
    let s: String = "hello"
    check s = "hello"
end main
end StringLiteral
""", True),

    ("v11f", "string concat OK", """
module StringConcat
procedure main()
is
    let a: String = "hello"
    let b: String = " world"
    let c: String = String.concat(a, b)
    check c = "hello world"
end main
end StringConcat
""", True),

    ("v11f", "string substr OK", """
module StringSubstr
procedure main()
is
    let s: String = "abcdef"
    let part: String = String.substr(s, 2, 3)
    check part = "cde"
end main
end StringSubstr
""", True),

    ("v11f", "string replace OK", """
module StringReplace
procedure main()
is
    let s: String = "a-b-c"
    let r: String = String.replace(s, "-", "_")
    check r = "a_b_c"
end main
end StringReplace
""", True),

    ("v11f", "string instr found OK", """
module StringInstrFound
procedure main()
is
    let s: String = "abcdef"
    let i: Integer = String.instr(s, "cd")
    check i = 2
end main
end StringInstrFound
""", True),

    ("v11f", "string instr not found OK", """
module StringInstrNotFound
procedure main()
is
    let s: String = "abcdef"
    let i: Integer = String.instr(s, "xy")
    check i = -1
end main
end StringInstrNotFound
""", True),

    ("v11f", "string type mismatch fail", """
module StringTypeMismatchFail
procedure main()
is
    let s: String = 1
end main
end StringTypeMismatchFail
""", False),

    ("v11f", "string concat type fail", """
module StringConcatTypeFail
procedure main()
is
    let s: String = "a"
    let x: String = String.concat(s, 1)
end main
end StringConcatTypeFail
""", False),

    ("v11f", "string substr bounds fail", """
module StringSubstrBoundsFail
procedure main()
is
    let s: String = "abc"
    let x: String = String.substr(s, 2, 5)
end main
end StringSubstrBoundsFail
""", False),

    ("v11f", "string arithmetic fail", """
module StringArithmeticFail
procedure main()
is
    let s: String = "a" + "b"
end main
end StringArithmeticFail
""", False),

    ("v11f", "string in case OK", """
module StringCase
procedure main()
is
    let s: String = "green"
    let x: Integer = 0
    case s is
        when "red" =>
            x := 1
        when "green" =>
            x := 2
        default =>
            x := 99
    end case
    check x = 2
end main
end StringCase
""", True),
]
