package Loop_Types with SPARK_Mode is
   subtype Index_T is Positive range 1 .. 1000;
   subtype Opt_Index_T is Natural range 0 .. 1000;
   subtype Component_T is Natural;
   type Arr_T is array (Index_T range <>) of Component_T;
end Loop_Types;
