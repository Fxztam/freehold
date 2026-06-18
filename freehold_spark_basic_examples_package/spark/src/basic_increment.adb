package body Basic_Increment with SPARK_Mode is

   -- Without a contract, GNATprove checks absence of run-time errors.
   -- X + 1 may overflow when X = Integer'Last, so this unit is a NEG demo.
   procedure Increment (X : in out Integer) is
   begin
      X := X + 1;
   end Increment;

   -- Adding a precondition removes the implementation overflow vulnerability,
   -- but it pushes the obligation to every caller.
   procedure Increment_Guarded (X : in out Integer) is
   begin
      X := X + 1;
   end Increment_Guarded;

   -- The full contract also gives the caller post-state knowledge.
   -- That makes repeated calls provable because GNATprove knows X was incremented.
   procedure Increment_Full (X : in out Integer) is
   begin
      X := X + 1;
   end Increment_Full;

   -- The second Increment_Guarded call is not provable from the guarded contract alone:
   -- after the first call, no postcondition tells the prover what X became.
   -- The two Increment_Full calls are provable because the postcondition exposes the result.
   procedure Increment_Calls is
      X : Integer;
   begin
      X := 0;
      Increment (X);
      Increment (X);

      X := 0;
      Increment_Guarded (X);
      Increment_Guarded (X);

      X := 0;
      Increment_Full (X);
      Increment_Full (X);
   end Increment_Calls;

   -- Local, contextually analyzed helper: the body can be inlined into the caller context.
   -- GNATprove can prove the two increments and the final assertion here.
   procedure Increment_Local is
      procedure Local_Increment (X : in out Integer) is
      begin
         X := X + 1;
      end Local_Increment;
      X : Integer;
   begin
      X := 0;
      Local_Increment (X);
      Local_Increment (X);
      pragma Assert (X = 2);
   end Increment_Local;

end Basic_Increment;
