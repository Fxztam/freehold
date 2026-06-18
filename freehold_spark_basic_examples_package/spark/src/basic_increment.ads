package Basic_Increment with SPARK_Mode is
   procedure Increment (X : in out Integer);
   procedure Increment_Guarded (X : in out Integer)
     with Pre => X < Integer'Last;
   procedure Increment_Full (X : in out Integer)
     with Global  => null,
          Depends => (X => X),
          Pre     => X < Integer'Last,
          Post    => X = X'Old + 1;
   procedure Increment_Calls;
   procedure Increment_Local;
end Basic_Increment;
