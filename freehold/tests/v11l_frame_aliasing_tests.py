from __future__ import annotations

V11L_FRAME_ALIASING_TESTS = [
    ("v11l", "pos frame update declared", """
module Pos_Frame_Update_Declared

type Account is record
    balance: Integer
    limit: Integer
end record

procedure deposit(acc: Account, amount: Integer)
modifies acc.balance
requires amount >= 0
requires acc.balance <= 1000000
ensures acc.balance = old(acc.balance) + amount
ensures acc.limit = old(acc.limit)
is
    acc.balance := acc.balance + amount
end deposit

end Pos_Frame_Update_Declared
""", True),

    ("v11l", "neg frame update undeclared field", """
module Neg_Frame_Update_Undeclared_Field

type Account is record
    balance: Integer
    limit: Integer
end record

procedure bad_deposit(acc: Account, amount: Integer)
modifies acc.balance
requires amount >= 0
requires acc.balance <= 1000000
ensures acc.balance = old(acc.balance) + amount
is
    acc.balance := acc.balance + amount
    acc.limit := acc.limit + 1
end bad_deposit

end Neg_Frame_Update_Undeclared_Field
""", False),

    ("v11l", "neg alias two mutable parameters", """
module Neg_Alias_Two_Mutable_Parameters

type Cell is record
    val: Integer
end record

procedure add_to_both(left: Cell, right: Cell)
modifies left.val, right.val
is
    left.val := left.val + 1
    right.val := right.val + 1
end add_to_both

procedure main()
is
    let c: Cell = Cell { val: 0 }
    call add_to_both(c, c)
end main

end Neg_Alias_Two_Mutable_Parameters
""", False),
]
