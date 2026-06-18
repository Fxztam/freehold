#!/usr/bin/env python3
"""
Generic Freehold POS/NEG runner skeleton.

Usage:
  python run_expected.py --cmd "freehold verify"
  python run_expected.py --cmd "python -m freehold verify"

Assumption:
  The verifier returns exit code 0 for VERIFY_OK and non-zero for VERIFY_FAIL.
"""

from __future__ import annotations

import argparse
import pathlib
import shlex
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TEST_ROOT = ROOT / "tests" / "proof_equivalence" / "gnatprove_paired"


def expected_ok(path: pathlib.Path) -> bool:
    return path.name.startswith("pos_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", required=True, help="Freehold verifier command, e.g. 'freehold verify'")
    parser.add_argument("--include-pending", action="store_true", help="Also run *.pending.fh future tests")
    args = parser.parse_args()

    cmd_prefix = shlex.split(args.cmd)
    test_files = sorted(TEST_ROOT.rglob("*.fh"))
    if not args.include_pending:
        test_files = [p for p in test_files if not p.name.endswith(".pending.fh")]

    total = 0
    ok = 0

    for file in test_files:
        total += 1
        want_ok = expected_ok(file)
        proc = subprocess.run(cmd_prefix + [str(file)], text=True, capture_output=True)
        got_ok = proc.returncode == 0
        passed = got_ok == want_ok
        ok += int(passed)

        status = "PASS" if passed else "FAIL"
        expected = "VERIFY_OK" if want_ok else "VERIFY_FAIL"
        actual = "VERIFY_OK" if got_ok else "VERIFY_FAIL"
        rel = file.relative_to(ROOT)

        print(f"{status:4} {rel} expected={expected} actual={actual}")
        if not passed:
            if proc.stdout:
                print("--- stdout ---")
                print(proc.stdout)
            if proc.stderr:
                print("--- stderr ---")
                print(proc.stderr)

    print()
    print(f"Summary: {ok}/{total} matched expected result")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
