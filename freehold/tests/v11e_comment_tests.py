from __future__ import annotations

V11E_COMMENT_TESTS = [
    ("v11e", "line comment OK", """
module CommentLine
-- This is a normal line comment.
procedure main()
is
    let x: Integer = 1 -- Inline line comment
    check x = 1
end main
end CommentLine
""", True),

    ("v11e", "block comment OK", """
module CommentBlock
/*
This block comment must be ignored completely.
It may contain words like procedure, end, case, while.
*/
procedure main()
is
    let x: Integer = 1
    /*
       x := 99
       check false
    */
    check x = 1
end main
end CommentBlock
""", True),

    ("v11e", "ai doc comment OK no semantic effect", """
module CommentAiDoc
/**
@ai intent:
This procedure should remain deterministic.

@ai risk:
This comment must not change semantics.
*/
procedure main()
is
    let x: Integer = 1
    check x = 1
end main
end CommentAiDoc
""", True),

    ("v11e", "commented failing code is ignored", """
module CommentIgnoredCode
procedure main()
is
    let x: Integer = 1
    /*
    check false
    x := 999
    */
    check x = 1
end main
end CommentIgnoredCode
""", True),

    ("v11e", "comments inside case OK", """
module CommentCase
procedure main()
is
    let x: Integer = 2
    let y: Integer = 0
    case x is
        when 1 =>
            -- no hit
            y := 10
        when 2 =>
            /*
              selected branch
            */
            y := 20
        default =>
            y := 99
    end case
    check y = 20
end main
end CommentCase
""", True),

    ("v11e", "unterminated block comment fails", """
module UnterminatedBlockComment
/*
procedure main()
is
    check true
end main
end UnterminatedBlockComment
""", False),

    ("v11e", "comment cannot hide missing end", """
module CommentCannotHideMissingEnd
procedure main()
is
    check true
/* end main
end CommentCannotHideMissingEnd */
""", False),

    ("v11e", "comment cannot create executable semantics", """
module CommentCannotCreateSemantics
/* check false
   x := 999
*/
procedure main()
is
    check true
end main
end CommentCannotCreateSemantics
""", True),
]
