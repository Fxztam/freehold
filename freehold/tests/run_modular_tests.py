from __future__ import annotations
import argparse, json
from collections import Counter
from freehold.core.log import configure_logger, logf
from freehold.core.parser import parse_source
from freehold.core.verifier import verify_program
from freehold.core.interpreter import Interpreter
from freehold.core.ast import SourcePos
from freehold.runtime import big as std_big
from freehold.tests.regression_cases import REGRESSION_TESTS
from freehold.tests.v11a_assignment_tests import V11A_ASSIGNMENT_TESTS
from freehold.tests.v11b_import_tests import V11B_IMPORT_TESTS
from freehold.tests.v11c_qualified_end_tests import V11C_QUALIFIED_END_TESTS
from freehold.tests.v11d_case_tests import V11D_CASE_TESTS
from freehold.tests.v11e_comment_tests import V11E_COMMENT_TESTS
from freehold.tests.v11f_string_tests import V11F_STRING_TESTS
from freehold.tests.v11h_std_io_tests import V11H_STD_IO_TESTS
from freehold.core.cfg import build_cfgs, cfg_summary
from freehold.core.symbolic import symbolic_obligations

ALL_STATIC_TESTS = REGRESSION_TESTS + V11A_ASSIGNMENT_TESTS + V11B_IMPORT_TESTS + V11C_QUALIFIED_END_TESTS + V11D_CASE_TESTS + V11E_COMMENT_TESTS + V11F_STRING_TESTS + V11H_STD_IO_TESTS

def run_source(src: str) -> None:
    ast = parse_source(src)
    verified = verify_program(ast)
    Interpreter(verified).run_main()

def run_cfg_if_smoke() -> None:
    src = """
module CFGIfSmoke
function f(x: Integer) returns Integer
ensures result >= 0
is
 if x < 0 then
  return -x
 else
  return x
 end if
end f
procedure main()
is
 let y: Integer = f(-3)
 check y = 3
end main
end CFGIfSmoke
"""
    ast = parse_source(src)
    s = cfg_summary(build_cfgs(ast)["f"])
    if s["blocks"] < 3 or s["edges"] < 2:
        raise AssertionError(f"CFG if too small: {s}")

def run_cfg_loop_smoke() -> None:
    src = """
module CFGLoopSmoke
procedure main()
is
 let i: Integer = 0
 while i < 2
  invariant i >= 0
  variant 2 - i
 do
  i := i + 1
 end while
 check i = 2
end main
end CFGLoopSmoke
"""
    ast = parse_source(src)
    s = cfg_summary(build_cfgs(ast)["main"])
    if s["blocks"] < 3 or s["edges"] < 2:
        raise AssertionError(f"CFG loop too small: {s}")

def run_symbolic_basic_smoke() -> None:
    src = """
module SMTSmoke
function add(a: Integer, b: Integer) returns Integer
ensures result = a + b
is
 return a + b
end add
procedure main()
is
 let x: Integer = add(1, 2)
 check x = 3
end main
end SMTSmoke
"""
    ast = parse_source(src)
    verified = verify_program(ast)
    obs = symbolic_obligations(verified)
    if not obs:
        raise AssertionError("no symbolic obligations generated")
    q = obs[0]["smt_query"]
    for token in ["set-logic", "assert", "check-sat"]:
        if token not in q:
            raise AssertionError(f"SMT query missing {token}")

def run_symbolic_record_smoke() -> None:
    src = """
module SMTRecordSmoke
type Customer is record
 id: Integer
end record
function make_customer() returns Customer
ensures result.id = 1
is
 return Customer { id: 1 }
end make_customer
procedure main()
is
 let c: Customer = make_customer()
 check c.id = 1
end main
end SMTRecordSmoke
"""
    ast = parse_source(src)
    verified = verify_program(ast)
    obs = symbolic_obligations(verified)
    if not obs:
        raise AssertionError("no record symbolic obligation generated")
    if "result_id" not in obs[0]["obligation"]:
        raise AssertionError(f"record SMT obligation not field-based: {obs[0]['obligation']}")

def run_determinism_smoke() -> None:
    src = """
module DeterminismSmoke
type Customer is record
 id: Integer
end record
procedure main()
is
 let c: Customer = Customer { id: 1 }
 c.id := 2
 check c.id = 2
end main
end DeterminismSmoke
"""
    for _ in range(5):
        run_source(src)

def run_recovery_smoke() -> None:
    bad = """
module Bad
procedure main()
is
 let x: Integer = 1
 check x = 2
end main
end Bad
"""
    good = """
module Good
procedure main()
is
 let x: Integer = 1
 check x = 1
end main
end Good
"""
    failed = False
    try:
        run_source(bad)
    except Exception:
        failed = True
    if not failed:
        raise AssertionError("bad program unexpectedly passed")
    run_source(good)

def run_runtime_vs_verifier_positive() -> None:
    src = """
module RuntimeVerifierPositive
function f(x: Integer) returns Integer
ensures result = x + 1
is
 return x + 1
end f
procedure main()
is
 let y: Integer = f(4)
 check y = 5
end main
end RuntimeVerifierPositive
"""
    ast = parse_source(src)
    verified = verify_program(ast)
    Interpreter(verified).run_main()

def run_runtime_vs_verifier_negative() -> None:
    src = """
module RuntimeVerifierNegative
function f(x: Integer) returns Integer
ensures result = x + 1
is
 return x
end f
procedure main()
is
 let y: Integer = f(4)
end main
end RuntimeVerifierNegative
"""
    ast = parse_source(src)
    verified = verify_program(ast)
    failed = False
    try:
        Interpreter(verified).run_main()
    except Exception:
        failed = True
    if not failed:
        raise AssertionError("runtime should have rejected violated ensures")

def run_bigfloat_precision_smoke() -> None:
    one = std_big.float_from_string("1", 256)
    seven = std_big.float_from_string("7", 256)
    quotient = std_big.div_float(one, seven, SourcePos())
    text = std_big.format_float(quotient, 60)
    expected = "0.142857142857142857142857142857142857142857142857142857142857"
    if text != expected:
        raise AssertionError(f"BigFloat precision regression: {text}")

def property_addition_cases() -> list[tuple[str, str]]:
    cases = []
    for a, b in [(0,0), (1,2), (5,7), (10,-3), (-4,9), (100,23), (-8,-9), (42,58), (999,1), (17,25)]:
        expected = a + b
        mod = f"PropAdd{abs(a)}_{abs(b)}"
        src = f"""
module {mod}
function add(a: Integer, b: Integer) returns Integer
ensures result = a + b
is
 return a + b
end add
procedure main()
is
 let x: Integer = add({a}, {b})
 check x = {expected}
end main
end {mod}
"""
        cases.append((f"property addition {a}+{b}", src))
    return cases

def property_record_update_cases() -> list[tuple[str, str]]:
    cases = []
    for start, end in [(1,2), (0,5), (10,10), (99,100), (-3,4)]:
        mod = f"PropRecordUpdate{abs(start)}_{abs(end)}"
        src = f"""
module {mod}
type Box is record
 amount: Integer
end record
procedure main()
is
 let b: Box = Box {{ amount: {start} }}
 b.amount := {end}
 check b.amount = {end}
end main
end {mod}
"""
        cases.append((f"property record update {start}->{end}", src))
    return cases

def meta_tests():
    items = [
        ("cfg_smt", "cfg if smoke", run_cfg_if_smoke),
        ("cfg_smt", "cfg loop smoke", run_cfg_loop_smoke),
        ("cfg_smt", "symbolic/smt basic smoke", run_symbolic_basic_smoke),
        ("cfg_smt", "symbolic/smt record smoke", run_symbolic_record_smoke),
        ("determinism", "repeat same program five times", run_determinism_smoke),
        ("recovery", "bad program followed by good program", run_recovery_smoke),
        ("runtime_vs_verifier", "positive consistency", run_runtime_vs_verifier_positive),
        ("runtime_vs_verifier", "negative ensures consistency", run_runtime_vs_verifier_negative),
        ("big", "BigFloat precision context", run_bigfloat_precision_smoke),
    ]
    for name, src in property_addition_cases():
        items.append(("property", name, lambda s=src: run_source(s)))
    for name, src in property_record_update_cases():
        items.append(("property", name, lambda s=src: run_source(s)))
    return items

def main() -> None:
    p = argparse.ArgumentParser(description="Freehold v11c regression suite")
    p.add_argument("--log", default=None)
    p.add_argument("--json-summary", default=None)
    p.add_argument("--no-console", action="store_true")
    args = p.parse_args()
    configure_logger(args.log, console=not args.no_console)

    passed = 0
    total = 0
    category = Counter()
    category_passed = Counter()
    failures = []

    for cat, name, src, should_pass in ALL_STATIC_TESTS:
        total += 1
        category[cat] += 1
        try:
            run_source(src)
            outcome = True
            msg = "PASS"
        except Exception as exc:
            outcome = False
            msg = f"FAIL as expected: {type(exc).__name__}: {exc}"
        ok = outcome == should_pass
        passed += int(ok)
        category_passed[cat] += int(ok)
        if not ok:
            failures.append({"category": cat, "name": name, "message": msg})
        logf(f"[{'OK' if ok else 'UNEXPECTED'}] {cat} :: {name}: {msg}")

    for cat, name, fn in meta_tests():
        total += 1
        category[cat] += 1
        try:
            fn()
            ok = True
            msg = "PASS"
        except Exception as exc:
            ok = False
            msg = f"{type(exc).__name__}: {exc}"
        passed += int(ok)
        category_passed[cat] += int(ok)
        if not ok:
            failures.append({"category": cat, "name": name, "message": msg})
        logf(f"[{'OK' if ok else 'UNEXPECTED'}] {cat} :: {name}: {msg}")

    from freehold.core.registry import default_registry
    reg = default_registry()
    logf("")
    logf("Feature registry:")
    for fname in reg.enabled_names():
        c = reg.contributions[fname]
        logf(f"  {fname}: AST={len(c.ast_nodes)} verifier_hooks={len(c.verifier_hooks)} interpreter_hooks={len(c.interpreter_hooks)}")

    logf("")
    logf("Category summary:")
    for cat in sorted(category):
        logf(f"  {cat}: {category_passed[cat]}/{category[cat]}")
    logf("")
    logf(f"{passed}/{total} tests matched expectation")

    summary = {
        "passed": passed,
        "enabled_features": reg.enabled_names(),
        "total": total,
        "categories": {cat: {"passed": category_passed[cat], "total": category[cat]} for cat in sorted(category)},
        "failures": failures,
    }
    if args.json_summary:
        with open(args.json_summary, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    if failures:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
