package body Basic_Addition with SPARK_Mode is

   -- The precondition itself can overflow while evaluating X + Y.
   -- This is a subtle but important NEG proof obligation.
   function Addition_Naive_Pre (X, Y : Integer) return Integer is
   begin
      return X + Y;
   end Addition_Naive_Pre;

   -- This precondition avoids evaluating X + Y before proving it is safe.
   function Addition_Safe_Pre (X, Y : Integer) return Integer is
   begin
      return X + Y;
   end Addition_Safe_Pre;

   -- Saturating addition expands the accepted input range and returns a boundary value
   -- instead of overflowing. Contract cases should be disjoint and complete.
   function Addition_Saturating (X, Y : Integer) return Integer is
   begin
      if X < 0 and Y < 0 then
         if X < Integer'First - Y then
            return Integer'First;
         else
            return X + Y;
         end if;
      elsif X > 0 and Y > 0 then
         if X > Integer'Last - Y then
            return Integer'Last;
         else
            return X + Y;
         end if;
      else
         return X + Y;
      end if;
   end Addition_Saturating;

end Basic_Addition;
