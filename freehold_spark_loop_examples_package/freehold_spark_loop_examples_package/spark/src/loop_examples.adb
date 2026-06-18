with Loop_Types; use Loop_Types;

package body Loop_Examples with SPARK_Mode is

   procedure Increment_Loop_Bad (X : in out Integer; N : Natural) is
   begin
      -- Need-for-invariant example: the contract is correct, but without an
      -- invariant the prover loses the relationship between X, X'Old and I.
      -- Expected GNATprove result: postcondition and overflow may be unproved.
      for I in 1 .. N loop
         X := X + 1;
      end loop;
   end Increment_Loop_Bad;

   procedure Increment_Loop_Good (X : in out Integer; N : Natural) is
   begin
      -- The invariant states the exact accumulated effect after I iterations.
      -- This is the essential proof bridge from loop body to postcondition.
      for I in 1 .. N loop
         X := X + 1;
         pragma Loop_Invariant (X = X'Loop_Entry + I);
      end loop;
   end Increment_Loop_Good;

   procedure Init_Arr_Zero (A : out Arr_T) is
   begin
      -- Initialization loop: every element visited so far has been initialized.
      for J in A'Range loop
         A (J) := 0;
         pragma Loop_Invariant (for all K in A'First .. J => A (K) = 0);
      end loop;
   end Init_Arr_Zero;

   procedure Init_Arr_Index (A : out Arr_T) is
   begin
      -- Initialization with index-dependent value: the prefix property records
      -- the value chosen for each already initialized cell.
      for J in A'Range loop
         A (J) := Component_T (J);
         pragma Loop_Invariant (for all K in A'First .. J => A (K) = Component_T (K));
      end loop;
   end Init_Arr_Index;

   procedure Map_Arr_Incr (A : in out Arr_T) is
   begin
      -- Mapping loop: updated prefix is related to the loop-entry array.
      -- GNATprove can often infer the complementary frame condition for the
      -- suffix, but the transformed Freehold test keeps that idea explicit.
      for J in A'Range loop
         A (J) := A (J) + 1;
         pragma Loop_Invariant (for all K in A'First .. J => A (K) = A'Loop_Entry (K) + 1);
      end loop;
   end Map_Arr_Incr;

   procedure Validate_Arr_Zero (A : Arr_T; Success : out Boolean) is
   begin
      -- Validation with early return: if no failure was found yet, the visited
      -- prefix satisfies the validation predicate.
      for J in A'Range loop
         if A (J) /= 0 then
            Success := False;
            return;
         end if;
         pragma Loop_Invariant (for all K in A'First .. J => A (K) = 0);
      end loop;
      Success := True;
   end Validate_Arr_Zero;

   procedure Validate_Full_Arr_Zero (A : Arr_T; Success : out Boolean) is
   begin
      -- Full validation keeps scanning even after a failing element. The flag
      -- is connected to the prefix property by the invariant.
      Success := True;
      for J in A'Range loop
         if A (J) /= 0 then
            Success := False;
         end if;
         pragma Loop_Invariant (Success = (for all K in A'First .. J => A (K) = 0));
      end loop;
   end Validate_Full_Arr_Zero;

   procedure Count_Arr_Zero (A : Arr_T; Counter : out Natural) is
   begin
      -- Counting loop: the counter is bounded by the number of visited cells;
      -- counter = 0 is equivalent to no zero in the visited prefix.
      Counter := 0;
      for J in A'Range loop
         if A (J) = 0 then
            Counter := Counter + 1;
         end if;
         pragma Loop_Invariant (Counter in 0 .. J - A'First + 1);
         pragma Loop_Invariant ((Counter = 0) = (for all K in A'First .. J => A (K) /= 0));
      end loop;
   end Count_Arr_Zero;

   procedure Search_Arr_Zero
     (A : Arr_T; Pos : out Opt_Index_T; Success : out Boolean) is
   begin
      -- Search with early exit: until a hit is found, the visited prefix is
      -- known not to contain the searched value.
      for J in A'Range loop
         if A (J) = 0 then
            Success := True;
            Pos := J;
            return;
         end if;
         pragma Loop_Invariant (for all K in A'First .. J => A (K) /= 0);
      end loop;
      Success := False;
      Pos := 0;
   end Search_Arr_Zero;

   procedure Search_Arr_Max
     (A : Arr_T; Pos : out Index_T; Max : out Component_T) is
   begin
      -- Maximize loop: Pos is valid, Max dominates the visited prefix, some
      -- visited element equals Max, and Pos names one such element.
      Max := 0;
      Pos := A'First;
      for J in A'Range loop
         if A (J) > Max then
            Max := A (J);
            Pos := J;
         end if;
         pragma Loop_Invariant (Pos in A'Range);
         pragma Loop_Invariant (for all K in A'First .. J => A (K) <= Max);
         pragma Loop_Invariant (for some K in A'First .. J => A (K) = Max);
         pragma Loop_Invariant (A (Pos) = Max);
      end loop;
   end Search_Arr_Max;

   procedure Update_Arr_Zero (A : in out Arr_T; Threshold : Component_T) is
   begin
      -- Conditional update loop: the prefix is already transformed, while the
      -- prover must preserve enough frame information for the unvisited suffix.
      for J in A'Range loop
         if A (J) <= Threshold then
            A (J) := 0;
         end if;
         pragma Loop_Invariant
           (for all K in A'First .. J =>
              (if A'Loop_Entry (K) <= Threshold then A (K) = 0 else A (K) = A'Loop_Entry (K)));
      end loop;
   end Update_Arr_Zero;

   procedure Update_Range_Arr_Zero
     (A : in out Arr_T; First, Last : Index_T) is
   begin
      -- Range update loop: the invariant describes the growing updated slice.
      for J in First .. Last loop
         A (J) := 0;
         pragma Loop_Invariant
           (for all K in A'Range =>
              (if K in First .. J then A (K) = 0 else A (K) = A'Loop_Entry (K)));
      end loop;
   end Update_Range_Arr_Zero;

end Loop_Examples;
