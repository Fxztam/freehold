from freehold.core.module_resolver import ModuleResolver
import freehold.core.symbolic as sym

original_solve = sym.solve_smt_query

def custom_solve(smt_query, prover=None, timeout=None):
    res = original_solve(smt_query, prover, timeout)
    print(f"--- SOLVE QUERY (Result: {res}) ---")
    print(smt_query)
    print()
    return res

sym.solve_smt_query = custom_solve

mr = ModuleResolver()
try:
    mr.resolve_entry("examples/GaussLegendrePi.fh")
except Exception as e:
    import traceback
    traceback.print_exc()
