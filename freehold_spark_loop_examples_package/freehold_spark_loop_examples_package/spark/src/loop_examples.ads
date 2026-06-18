with Loop_Types; use Loop_Types;

package Loop_Examples with SPARK_Mode is
   -- Derived from AdaCore SPARK User's Guide 7.9.2 Loop Examples.
   -- Comments paraphrase the documentation: each loop needs invariants that
   -- summarize the part of the data structure already traversed.

   procedure Increment_Loop_Bad (X : in out Integer; N : Natural) with
     Pre  => X <= Integer'Last - N,
     Post => X = X'Old + N;

   procedure Increment_Loop_Good (X : in out Integer; N : Natural) with
     Pre  => X <= Integer'Last - N,
     Post => X = X'Old + N;

   procedure Init_Arr_Zero (A : out Arr_T) with
     Post => (for all J in A'Range => A (J) = 0);

   procedure Init_Arr_Index (A : out Arr_T) with
     Post => (for all J in A'Range => A (J) = Component_T (J));

   procedure Map_Arr_Incr (A : in out Arr_T) with
     Pre  => (for all J in A'Range => A (J) /= Component_T'Last),
     Post => (for all J in A'Range => A (J) = A'Old (J) + 1);

   procedure Validate_Arr_Zero (A : Arr_T; Success : out Boolean) with
     Post => Success = (for all J in A'Range => A (J) = 0);

   procedure Validate_Full_Arr_Zero (A : Arr_T; Success : out Boolean) with
     Post => Success = (for all J in A'Range => A (J) = 0);

   procedure Count_Arr_Zero (A : Arr_T; Counter : out Natural) with
     Post => (Counter in 0 .. A'Length) and then
             ((Counter = 0) = (for all K in A'Range => A (K) /= 0));

   procedure Search_Arr_Zero
     (A : Arr_T; Pos : out Opt_Index_T; Success : out Boolean) with
     Post => Success = (for some J in A'Range => A (J) = 0) and then
             (if Success then A (Pos) = 0);

   procedure Search_Arr_Max
     (A : Arr_T; Pos : out Index_T; Max : out Component_T) with
     Pre  => A'Length > 0,
     Post => (for all J in A'Range => A (J) <= Max) and then
             (for some J in A'Range => A (J) = Max) and then
             A (Pos) = Max;

   procedure Update_Arr_Zero (A : in out Arr_T; Threshold : Component_T) with
     Post => (for all J in A'Range =>
                (if A'Old (J) <= Threshold then A (J) = 0 else A (J) = A'Old (J)));

   procedure Update_Range_Arr_Zero
     (A : in out Arr_T; First, Last : Index_T) with
     Pre  => First in A'Range and then Last in A'Range and then First <= Last,
     Post => (for all J in A'Range =>
                (if J in First .. Last then A (J) = 0 else A (J) = A'Old (J)));
end Loop_Examples;
