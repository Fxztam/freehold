with Loop_Examples; use Loop_Examples;
with Loop_Types; use Loop_Types;

procedure Main with SPARK_Mode is
   A : Arr_T (1 .. 10) := (others => 1);
   B : Arr_T (1 .. 10);
   X : Integer := 10;
   C : Natural;
   P : Opt_Index_T;
   S : Boolean;
   M : Component_T;
   MP : Index_T;
begin
   Increment_Loop_Good (X, 5);
   Init_Arr_Zero (B);
   Init_Arr_Index (B);
   Map_Arr_Incr (A);
   Validate_Arr_Zero (B, S);
   Validate_Full_Arr_Zero (B, S);
   Count_Arr_Zero (B, C);
   Search_Arr_Zero (B, P, S);
   Search_Arr_Max (A, MP, M);
   Update_Arr_Zero (A, 2);
   Update_Range_Arr_Zero (A, 2, 5);
end Main;
