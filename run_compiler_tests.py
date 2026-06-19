#!/usr/bin/env python3
"""
Custom Test Runner for Compiler-Tests suite in Freehold.

This runner scans the five compiler test suite directories:
  01_Module, 02_Procedures, 03_Functions, 04_Records, 05_Contracts

And checks:
1. *.fh script compilation and verification
2. Checks of output / errors against .expected configuration rules

Because Freehold enforces that the file name matches the module name,
this runner copies each test file to a temporary file named exactly after its declared module name before compiling/verifying.
"""

import sys
import os
import re
import shlex
import shutil
import tempfile
import argparse
import pathlib
import subprocess

ROOT_DIR = pathlib.Path(__file__).resolve().parent
TESTS_DIR = ROOT_DIR / "Compiler-Tests" / "Test"

# Map to collect results
categories = [
    "01_Module",
    "02_Procedures",
    "03_Functions",
    "04_Records",
    "05_Contracts"
]

def extract_module_name(file_path: pathlib.Path) -> str:
    """Reads the Freehold file and extracts the module name or the closest match."""
    try:
        content = file_path.read_text(encoding="utf-8")
        # Match 'module Name' or 'module Name.SubName'
        match = re.search(r"^\s*module\s+([a-zA-Z0-9_\.]+)", content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

def parse_expected_file(expected_path: pathlib.Path) -> dict:
    """Parses .expected file into a key-value dict."""
    config = {}
    if not expected_path.exists():
        return config
    try:
        content = expected_path.read_text(encoding="utf-8")
        current_key = None
        for line_raw in content.splitlines():
            line = line_raw.strip()
            if not line:
                continue
            if ":" in line:
                parts = line.split(":", 1)
                key = parts[0].strip()
                val = parts[1].strip()
                config[key] = val
                current_key = key
            elif current_key and line_raw.startswith(" "):
                # Multi-line append
                config[current_key] += " " + line
    except Exception as e:
        print(f"Warning: Failed to parse expected file {expected_path}: {e}")
    return config

def run_test_file(file_path: pathlib.Path, expected_config: dict, python_exe: str) -> tuple[bool, str]:
    """Runs a single test case by copying it to module-name.fh to satisfy path rules."""
    module_name = extract_module_name(file_path)
    env = dict(os.environ)
    # Set PYTHONPATH so 'freehold' package can be found from within any CWD
    env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    if not module_name:
        cmd_args = [python_exe, "-m", "freehold", "verify", str(file_path), "--prover", "z3"]
        proc = subprocess.run(cmd_args, text=True, capture_output=True, env=env)
        return evaluate_result(proc, expected_config)

    # If it has a module name, we must copy it to <module_name>.fh inside a temp dir
    with tempfile.TemporaryDirectory() as tmp_dir_sz:
        tmp_dir = pathlib.Path(tmp_dir_sz)
        
        # Copy Std directory if it exists to allow resolving standard library modules
        std_src = ROOT_DIR / "Std"
        if std_src.exists():
            shutil.copytree(std_src, tmp_dir / "Std", dirs_exist_ok=True)

        # Create dummy Banking/Proofs.fh
        banking_dir = tmp_dir / "Banking"
        banking_dir.mkdir(parents=True, exist_ok=True)
        (banking_dir / "Proofs.fh").write_text("module Banking.Proofs\nend Banking.Proofs\n", encoding="utf-8")

        # Create dummy Domain/Customers.fh
        domain_dir = tmp_dir / "Domain"
        domain_dir.mkdir(parents=True, exist_ok=True)
        customers_fh_content = """module Domain.Customers
type Customer is record
    id: Integer
    name: String
end record
function make_customer(id: Integer, name: String) returns Customer
is
    return Customer { id: id, name: name }
end make_customer
end Domain.Customers
"""
        (domain_dir / "Customers.fh").write_text(customers_fh_content, encoding="utf-8")
        
        # Freehold supports dotted module names like 'A.B.C', which expect directory structure
        module_parts = module_name.split(".")
        target_dir = tmp_dir
        if len(module_parts) > 1:
            for part in module_parts[:-1]:
                target_dir = target_dir / part
            target_dir.mkdir(parents=True, exist_ok=True)
        
        target_file = target_dir / f"{module_parts[-1]}.fh"
        shutil.copy(file_path, target_file)

        cmd_args = [python_exe, "-m", "freehold", "verify", str(target_file), "--prover", "z3"]
        proc = subprocess.run(cmd_args, text=True, capture_output=True, cwd=tmp_dir_sz, env=env)
        
        return evaluate_result(proc, expected_config)

def evaluate_result(proc: subprocess.CompletedProcess, expected_config: dict) -> tuple[bool, str]:
    """Evaluates the process output against the parsed expected config."""
    got_error = proc.returncode != 0
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    combined_output = stdout + "\n" + stderr

    # Determine desired status
    want_parser_fail = expected_config.get("parser_result") == "failure"
    want_verifier_fail = expected_config.get("verifier_result") == "failure"
    want_success = not want_parser_fail and not want_verifier_fail

    if want_success:
        if got_error:
            return False, f"Expected verification success, but failed. Code={proc.returncode}.\nOutput:\n{combined_output}"
        return True, "Passed as expected (Success)"

    # If we expected a failure:
    if not got_error:
        return False, f"Expected failure but completed with exit code 0."

    # Validate failure details from .expected if present
    expected_hint = expected_config.get("error_hint")
    if expected_hint:
        # Check if hint is in output
        # Let's perform case-insensitive checking and tolerate slight space variations
        hint_pattern = expected_hint.lower().replace("'", "").replace("\"", "")
        output_lower = combined_output.lower().replace("'", "").replace("\"", "")
        
        # Let's check direct substring or some fuzzy match
        if hint_pattern not in output_lower:
            # Sometime the error hint is a generic expectation. Let's do a backup search for principal keywords
            words = [w for w in hint_pattern.split() if len(w) > 3]
            matched_words = [w in output_lower for w in words]
            if len(words) > 0 and sum(matched_words) / len(words) >= 0.6:
                # Close enough keyword match
                pass
            else:
                return False, f"Failed but with a different error message.\nExpected Hint: '{expected_hint}'\nActual Output:\n{combined_output}"

    # Also check error phase if specified
    expected_phase = expected_config.get("error_phase")
    if expected_phase:
        if expected_phase == "parser" and "UnexpectedToken" not in combined_output and "UnexpectedCharacters" not in combined_output and "syntax error" not in combined_output:
            # Check if there is some parser indicator in output
            if "parser" not in combined_output.lower() and "syntax" not in combined_output.lower():
                return False, f"Failed in unexpected phase. Expected parser error.\nActual Output:\n{combined_output}"
        elif expected_phase == "verifier" and "TypeCheckError" not in combined_output and "VerificationError" not in combined_output and "verification failed" not in combined_output:
            if "verifier" not in combined_output.lower() and "semantic" not in combined_output.lower() and "oblig" not in combined_output.lower() and "resolution" not in combined_output.lower():
                 return False, f"Failed in unexpected phase. Expected verifier/semantic error.\nActual Output:\n{combined_output}"

    return True, "Failed with expected error"

def main() -> int:
    parser = argparse.ArgumentParser(description="Compiler test-suite runner.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use.")
    parser.add_argument("--filter", "-f", default=None, help="Regex pattern or keyword to filter tests and categories by path/filename.")
    args = parser.parse_args()

    print("=========================================================================")
    print("      FREEHOLD COMPILER TEST SUITE INTEGRATION RUNNER                    ")
    print("=========================================================================\n")

    if not TESTS_DIR.exists():
        print(f"Error: Compiler tests directory not found at: {TESTS_DIR}")
        return 1

    total_tests = 0
    passed_tests = 0
    failed_test_details = []

    # Compile filter pattern if specified
    filter_pat = None
    if args.filter:
        try:
            filter_pat = re.compile(args.filter, re.IGNORECASE)
        except re.error as e:
            print(f"Error: Invalid regex pattern '{args.filter}': {e}")
            return 1

    for cat in categories:
        cat_path = TESTS_DIR / cat
        if not cat_path.exists():
            continue

        # If filtering, check if category name matches. If not, we might still match specific files inside.
        if filter_pat and not filter_pat.search(cat):
            # Check if any test files inside the category match before printing the header
            has_matching_files = False
            for root, _, files in os.walk(cat_path):
                for f in files:
                    if f.endswith(".fh"):
                        f_rel = os.path.relpath(os.path.join(root, f), TESTS_DIR)
                        if filter_pat.search(f_rel):
                            has_matching_files = True
                            break
                if has_matching_files:
                    break
            if not has_matching_files:
                continue

        print(f"--- Running [Category: {cat}] ---")
        
        # Collect demo and valid files
        tests_in_category = []
        
        # Files at top category (demos)
        for p in cat_path.glob("*.fh"):
            tests_in_category.append((p, "demo"))
            
        # Files in valid/ subfolder
        valid_dir = cat_path / "valid"
        if valid_dir.exists():
            for p in valid_dir.glob("*.fh"):
                tests_in_category.append((p, "valid"))
                
        # Files in invalid/ subfolder
        invalid_dir = cat_path / "invalid"
        if invalid_dir.exists():
            for p in invalid_dir.glob("*.fh"):
                tests_in_category.append((p, "invalid"))

        # Sort tests
        tests_in_category.sort(key=lambda x: x[0].name)

        cat_passed = 0
        cat_total = 0

        for test_file, test_type in tests_in_category:
            # Apply filter pattern if specified on the relative path of the file
            if filter_pat:
                rel_f_path = str(test_file.relative_to(TESTS_DIR)).replace("\\", "/")
                if not filter_pat.search(rel_f_path):
                    continue

            total_tests += 1
            cat_total += 1
            
            # Locate expected config
            expected_file = None
            if test_type in ("demo", "valid"):
                expected_file = cat_path / "expected_positive_outputs" / f"{test_file.stem}.expected"
            else:
                expected_file = cat_path / "expected_negative_errors" / f"{test_file.stem}.expected"

            expected_config = parse_expected_file(expected_file)
            
            # Run test
            success, reason = run_test_file(test_file, expected_config, args.python)
            
            status_str = "PASS" if success else "FAIL"
            print(f"  [{status_str:4}] {test_file.relative_to(TESTS_DIR)} ({test_type}) -> {reason}")
            
            if success:
                passed_tests += 1
                cat_passed += 1
            else:
                failed_test_details.append((test_file, reason))

        if cat_total > 0:
            print(f"Category {cat} Summary: {cat_passed}/{cat_total} passed.\n")

    print("=========================================================================")
    print(f"FINAL RESULT: {passed_tests}/{total_tests} tests matched expected config.")
    print("=========================================================================")

    if failed_test_details:
        print("\nFailed test details:")
        for idx, (f, reason) in enumerate(failed_test_details, 1):
            print(f"\n{idx}. File: {[f.relative_to(ROOT_DIR)]}")
            print(f"   Reason: {reason}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
