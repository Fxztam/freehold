package body Basic_Swap with SPARK_Mode is

   -- This implementation is functionally wrong: X's initial value is lost.
   -- Without a functional contract, GNATprove cannot infer intended swap semantics.
   procedure Swap_Bad (X, Y : in out Integer) is
   begin
      X := Y;
      Y := X;
   end Swap_Bad;

   -- Adding the intended postcondition exposes the defect:
   -- after X := Y, assigning Y := X simply copies the old Y into both variables.
   procedure Swap_Bad_Post (X, Y : in out Integer) is
   begin
      X := Y;
      Y := X;
   end Swap_Bad_Post;

   -- Correct temp-based swap: the initial value of X is preserved before overwriting X.
   procedure Swap (X, Y : in out Integer) is
      Tmp : constant Integer := X;
   begin
      X := Y;
      Y := Tmp;
   end Swap;

   -- Wrong order: Tmp_Y is read before assignment. This should be a hard diagnostic.
   procedure Swap_Warn (X, Y : in out Integer) is
      Tmp_X : Integer;
      Tmp_Y : Integer;
   begin
      Tmp_X := X;
      X := Tmp_Y;
      Tmp_Y := Y;
      Y := Tmp_X;
   end Swap_Warn;

end Basic_Swap;
