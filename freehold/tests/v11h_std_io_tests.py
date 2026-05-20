from __future__ import annotations

V11H_STD_IO_TESTS = [
    ("v11h", "Std.IO.log string OK", """
module StdIoLogString
import Std.IO exposing log
procedure main()
is
    call Std.IO.log("Hello Freehold")
end main
end StdIoLogString
""", True),
    ("v11h", "Std.IO.log integer OK", """
module StdIoLogInteger
import Std.IO exposing log
procedure main()
is
    let x: Integer = 42
    call Std.IO.log(x)
end main
end StdIoLogInteger
""", True),
    ("v11h", "Std.IO.logf integer OK", """
module StdIoLogfInteger
import Std.IO exposing logf
procedure main()
is
    let x: Integer = 42
    call Std.IO.logf("value = ${}", x)
end main
end StdIoLogfInteger
""", True),
    ("v11h", "Std.IO.logf string OK", """
module StdIoLogfString
import Std.IO exposing logf
procedure main()
is
    let s: String = "Ada"
    call Std.IO.logf("name = ${}", s)
end main
end StdIoLogfString
""", True),
    ("v11h", "Std.IO.log record fails", """
module StdIoLogRecordFails
import Std.IO exposing log
type Box is record
    amount: Integer
end record
procedure main()
is
    let b: Box = Box { amount: 1 }
    call Std.IO.log(b)
end main
end StdIoLogRecordFails
""", False),
    ("v11h", "Std.IO.logf template must be string fails", """
module StdIoLogfTemplateFails
import Std.IO exposing logf
procedure main()
is
    let x: Integer = 42
    call Std.IO.logf(1, x)
end main
end StdIoLogfTemplateFails
""", False),
]
