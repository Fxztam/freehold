package Basic_Addition with SPARK_Mode is
   function Addition_Naive_Pre (X, Y : Integer) return Integer
     with Pre  => X + Y in Integer,
          Post => Addition_Naive_Pre'Result = X + Y;

   function Addition_Safe_Pre (X, Y : Integer) return Integer
     with Pre  => (X >= 0 and then Y <= Integer'Last - X) or else
                  (X < 0 and then Y >= Integer'First - X),
          Post => Addition_Safe_Pre'Result = X + Y;

   function Addition_Saturating (X, Y : Integer) return Integer
     with Contract_Cases =>
       ((X + Y in Integer)    => Addition_Saturating'Result = X + Y,
        X + Y < Integer'First => Addition_Saturating'Result = Integer'First,
        X + Y > Integer'Last  => Addition_Saturating'Result = Integer'Last);
end Basic_Addition;
