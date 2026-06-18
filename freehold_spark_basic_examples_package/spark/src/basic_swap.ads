package Basic_Swap with SPARK_Mode is
   procedure Swap_Bad (X, Y : in out Integer);
   procedure Swap_Bad_Post (X, Y : in out Integer)
     with Post => X = Y'Old and then Y = X'Old;
   procedure Swap (X, Y : in out Integer)
     with Depends => (X => Y, Y => X),
          Post    => X = Y'Old and Y = X'Old;
   procedure Swap_Warn (X, Y : in out Integer);
end Basic_Swap;
