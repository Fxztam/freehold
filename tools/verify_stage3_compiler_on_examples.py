from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freehold.core.go_codegen import go_executable_name
from tools.freehold_fuzzer import build_typing_positive, build_typing_negative


@dataclass(frozen=True)
class SupportedExample:
    name: str
    entry: str
    expected_log: str | None = None


@dataclass(frozen=True)
class UnsupportedExample:
    name: str
    entry: str
    expected_diagnostic: str


SUPPORTED_EXAMPLES = [
    SupportedExample("01_minimal_app", "examples/compiler_v1/01_minimal_app/App/Main.fh"),
    SupportedExample("02_records_functions", "examples/compiler_v1/02_records_functions/App/Main.fh"),
    SupportedExample("03_cross_module_calls", "examples/compiler_v1/03_cross_module_calls/App/Main.fh"),
    SupportedExample("04_result_abort", "examples/compiler_v1/04_result_abort/App/Main.fh"),
    SupportedExample("05_runtime_builtins", "examples/compiler_v1/05_runtime_builtins/App/Main.fh", "examples/expected_logs/compiler_v1_runtime_builtins.expected.log"),
    SupportedExample("06_integer_big_loop", "examples/compiler_v1/06_integer_big_loop/App/Main.fh"),
    SupportedExample("07_complex_contracts", "examples/compiler_v1/07_complex_contracts/App/Main.fh", "examples/expected_logs/compiler_v1_complex_contracts.expected.log"),
    SupportedExample("08_cross_module_type_composition", "examples/compiler_v1/08_cross_module_type_composition/App/Main.fh", "examples/expected_logs/compiler_v1_cross_module_type_composition.expected.log"),
    SupportedExample("09_result_record_type_composition", "examples/compiler_v1/09_result_record_type_composition/App/Main.fh", "examples/expected_logs/compiler_v1_result_record_type_composition.expected.log"),
    SupportedExample("10_result_record_contract_demo", "examples/compiler_v1/10_result_record_contract_demo/App/Main.fh", "examples/expected_logs/compiler_v1_result_record_contract_demo.expected.log"),
    SupportedExample("11_result_array_record_payload", "examples/compiler_v1/11_result_array_record_payload/App/Main.fh", "examples/expected_logs/compiler_v1_result_array_record_payload.expected.log"),
    SupportedExample("12_qualified_name_conflicts", "examples/compiler_v1/12_qualified_name_conflicts/App/Main.fh", "examples/expected_logs/compiler_v1_qualified_name_conflicts.expected.log"),
    SupportedExample("13_control_flow_runtime_log", "examples/compiler_v1/13_control_flow_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_control_flow_runtime_log.expected.log"),
    SupportedExample("14_big_loop_runtime_log", "examples/compiler_v1/14_big_loop_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_big_loop_runtime_log.expected.log"),
    SupportedExample("15_result_abort_array_runtime_builtins", "examples/compiler_v1/15_result_abort_array_runtime_builtins/App/Main.fh", "examples/expected_logs/compiler_v1_result_abort_array_runtime_builtins.expected.log"),
    SupportedExample("16_abort_propagation_runtime_log", "examples/compiler_v1/16_abort_propagation_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_abort_propagation_runtime_log.expected.log"),
    SupportedExample("17_mutation_record_runtime_log", "examples/compiler_v1/17_mutation_record_update_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_mutation_record_update_runtime_log.expected.log"),
    SupportedExample("17_record_mutation_runtime_log", "examples/compiler_v1/17_record_mutation_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_record_mutation_runtime_log.expected.log"),
    SupportedExample("18_result_error_branch_runtime_log", "examples/compiler_v1/18_result_error_branch_runtime_log/App/Main.fh", "examples/expected_logs/compiler_v1_result_error_branch_runtime_log.expected.log"),
    SupportedExample("19_async_scope_runtime", "examples/compiler_v1/19_async_scope_runtime/App/Main.fh"),
    SupportedExample("20_grpc_binding", "examples/compiler_v1/20_grpc_binding/App/Main.fh"),
    SupportedExample("21_concurrent_grpc_channel_demo", "examples/compiler_v1/21_concurrent_grpc_channel_demo/App/Main.fh"),
    SupportedExample("22_subtype_range", "examples/compiler_v1/22_subtype_range/App/Main.fh"),
    SupportedExample("24_flow_contracts", "examples/compiler_v1/24_flow_contracts/App/Main.fh"),
    SupportedExample("old_BigNumbers", "examples/BigNumbers.fh", "examples/expected_logs/BigNumbers.expected.log"),
    SupportedExample("old_ChudnovskyFeynmanPoint", "examples/ChudnovskyFeynmanPoint.fh", "examples/expected_logs/ChudnovskyFeynmanPoint.expected.log"),
    SupportedExample("old_ChudnovskyPi", "examples/ChudnovskyPi.fh", "examples/expected_logs/ChudnovskyPi.expected.log"),
    SupportedExample("old_epsilon_demo", "examples/epsilon_demo.fh", "examples/expected_logs/epsilon_demo.expected.log"),
    SupportedExample("old_GaussLegendrePi", "examples/GaussLegendrePi.fh", "examples/expected_logs/GaussLegendrePi.expected.log"),
    SupportedExample("old_hello_cli", "examples/hello_cli.fh", "examples/expected_logs/hello_cli.expected.log"),
    SupportedExample("old_JsonStringifySmoke", "examples/JsonStringifySmoke.fh", "examples/expected_logs/JsonStringifySmoke.expected.log"),
    SupportedExample("old_RecordTemplateSmoke", "examples/RecordTemplateSmoke.fh", "examples/expected_logs/RecordTemplateSmoke.expected.log"),
    SupportedExample("old_banking_records", "examples/banking_records.fh", "examples/expected_logs/banking_records.expected.log"),
    SupportedExample("old_retail_cli_demo_v11f", "examples/retail_cli_demo_v11f.fh", "examples/expected_logs/retail_cli_demo_v11f.expected.log"),
    SupportedExample("old_std_io_console_demo", "examples/std_io_console_demo.fh", "examples/expected_logs/std_io_console_demo.expected.log"),
]

UNSUPPORTED_EXAMPLES = [
    UnsupportedExample("unsupported_generic_function", "examples/compiler_v1/unsupported/generic_function/App/Main.fh", "FH-GOCODEGEN-0001"),
]

OUT_ROOT = ROOT / ".tmp" / "stage3_compiler_examples"


def safe_rmtree(path: Path) -> None:
    import time
    for _ in range(5):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except Exception:
            time.sleep(0.5)
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Verify Stage 3 native compiler on examples and fuzzy tests")
    parser.add_argument("--fuzz-only", action="store_true", help="Only run dynamic fuzzy tests")
    parser.add_argument("--fuzz-cycles", type=int, default=5, help="Number of fuzzing cycles to run (default: 5)")
    parser.add_argument("--seed", type=int, default=42000, help="Initial seed for the fuzzer (default: 42000)")
    args = parser.parse_args()

    safe_rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    failed = False
    if not args.fuzz_only:
        for example in SUPPORTED_EXAMPLES:
            failed = run_supported_with_stage3(example) or failed
        for example in UNSUPPORTED_EXAMPLES:
            failed = run_unsupported(example) or failed

    # Run dynamically generated fuzzy tests
    failed = run_fuzzy_tests(cycles=args.fuzz_cycles, initial_seed=args.seed) or failed

    if failed:
        print("\n[FAIL] Stage 3 compiler example and fuzzy verification failed.")
        return 1
    print("\n[OK] Stage 3 compiler example and fuzzy verification passed.")
    return 0


def run_supported_with_stage3(example: SupportedExample) -> bool:
    print(f"\n[STAGE3 EXAMPLE] {example.name}")
    project_out = OUT_ROOT / example.name
    entry = ROOT / example.entry

    # Step 1: Verify with python compiler frontend
    if run([sys.executable, "-m", "freehold", "verify", str(entry)], ROOT).returncode != 0:
        print(f"[FAIL] verification failed: {example.name}")
        return True

    # Step 2: Generate Go files to project_out (but DO NOT build exe with Python)
    json_path = project_out / "_project.json"
    if run([
        sys.executable,
        "-m",
        "freehold",
        "go-codegen-project",
        str(entry),
        "--output-dir",
        str(project_out),
        "--json",
        str(json_path),
        "--emit-executable",
        "--executable-name",
        example.name,
    ], ROOT).returncode != 0:
        print(f"[FAIL] Go project codegen failed: {example.name}")
        return True

    # Step 3: Run the native bootstrapped compiler binary to compile the project
    stage3_compiler = ROOT / "bin" / "stage3_compiler_core_v1.exe"
    if not stage3_compiler.exists():
        print(f"[FAIL] stage3_compiler_core_v1.exe not found at {stage3_compiler}")
        return True

    cmd_dir = project_out / "cmd"
    exe_arg = go_executable_name(example.name) if cmd_dir.exists() else ""

    print(f"[STAGE3] Building project with native stage3 compiler...")
    stage3_res = run([
        str(stage3_compiler),
        "--build-exe",
        str(entry),
        str(project_out),
        exe_arg,
    ], ROOT)

    if stage3_res.returncode != 0:
        print(f"[FAIL] Native stage3 compiler build failed for {example.name}")
        return True

    # Rename output binary on Windows if generated without .exe
    if sys.platform == "win32" and exe_arg != "":
        raw_exe = project_out / exe_arg
        win_exe = project_out / f"{exe_arg}.exe"
        if raw_exe.exists():
            if win_exe.exists():
                win_exe.unlink()
            raw_exe.rename(win_exe)

    # Step 4: Verify outputs and run log checks if expected_log is defined
    if example.expected_log is not None:
        if run_runtime_log_check(example, project_out, json_path):
            return True

    print(f"[OK] {example.name} verified successfully via stage3 compiler.")
    return False


def run_unsupported(example: UnsupportedExample) -> bool:
    print(f"\n[UNSUPPORTED] {example.name}")
    project_out = OUT_ROOT / example.name
    entry = ROOT / example.entry

    if run([sys.executable, "-m", "freehold", "verify", str(entry)], ROOT).returncode != 0:
        print(f"[FAIL] frontend verification failed before codegen: {example.name}")
        return True

    json_path = project_out / "_project.json"
    result = run([
        sys.executable,
        "-m",
        "freehold",
        "go-codegen-project",
        str(entry),
        "--output-dir",
        str(project_out),
        "--json",
        str(json_path),
    ], ROOT, quiet=True)
    if result.returncode == 0:
        print(f"[FAIL] unsupported example unexpectedly generated cleanly: {example.name}")
        return True
    if not json_path.exists() or example.expected_diagnostic not in json_path.read_text(encoding="utf-8"):
        print(f"[FAIL] expected diagnostic {example.expected_diagnostic} not found: {example.name}")
        return True
    print(f"[OK] {example.name} reported {example.expected_diagnostic}")
    return False


def run_runtime_log_check(example: SupportedExample, project_out: Path, json_path: Path) -> bool:
    assert example.expected_log is not None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    entry_file = data["files"][0]
    go_file = project_out / entry_file["output_path"]
    package_dir = go_file.parent
    package_name = entry_file["result"]["package"]
    log_name = f"{Path(example.entry).stem}.log"
    log_path = package_dir / log_name
    expected_path = ROOT / example.expected_log
    test_path = package_dir / "freehold_runtime_log_test.go"
    test_path.write_text(runtime_log_test_source(package_name, log_name), encoding="utf-8")

    if run(["go", "test", "./...", "-run", "TestFreeholdMainRuntimeLog", "-count=1"], project_out).returncode != 0:
        print(f"[FAIL] runtime log test failed: {example.name}")
        return True
    actual = normalize_log(log_path.read_text(encoding="utf-8") if log_path.exists() else "")
    expected = normalize_log(expected_path.read_text(encoding="utf-8"))
    if actual != expected:
        print(f"[FAIL] runtime log mismatch: {example.name}")
        print(f"[INFO] expected: {example.expected_log}")
        print(f"[INFO] actual: {log_path.relative_to(ROOT)}")
        return True
    print(f"[OK] runtime log matches: {Path(example.expected_log).name}")
    if run_executable_log_check(example, project_out, expected_path):
        return True
    return False


def run_executable_log_check(example: SupportedExample, project_out: Path, expected_path: Path) -> bool:
    exe_name = go_executable_name(example.name)
    if sys.platform == "win32":
        exe_path = project_out / f"{exe_name}.exe"
    else:
        exe_path = project_out / exe_name
    # Wait, the native stage3 compiler builds the executable in the project_out root directory or where?
    # Let's check: System.run_command("go build -trimpath -o ${exe} ./cmd/${exe}") in project_out.
    # Yes! So the executable is written directly to project_out / f"{exe_name}.exe" on Windows, or f"{exe_name}" on other platforms.
    if not exe_path.exists():
        # Fallback to bin/ if the go build command was customized.
        bin_exe = f"{exe_name}.exe" if sys.platform == "win32" else exe_name
        exe_path = project_out / "bin" / bin_exe
        if not exe_path.exists():
            print(f"[FAIL] generated executable missing: {exe_path.name} in {project_out}")
            return True
    
    result = subprocess.run([str(exe_path)], cwd=project_out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        print(f"[FAIL] generated executable failed: {example.name}")
        print(result.stdout)
        return True
    actual = normalize_log(result.stdout)
    expected = normalize_log(expected_path.read_text(encoding="utf-8"))
    if actual != expected:
        actual_path = project_out / f"{exe_name}.exe.log"
        actual_path.write_text(result.stdout, encoding="utf-8")
        print(f"[FAIL] executable runtime log mismatch: {example.name}")
        print(f"[INFO] expected: {example.expected_log}")
        print(f"[INFO] actual: {actual_path.relative_to(ROOT)}")
        return True
    print(f"[OK] executable runtime log matches: {Path(example.expected_log or '').name}")
    return False


def runtime_log_test_source(package_name: str, log_name: str) -> str:
    return f'''package {package_name}

import (
    "bytes"
    "os"
    "testing"
)

func TestFreeholdMainRuntimeLog(t *testing.T) {{
    oldStdout := os.Stdout
    reader, writer, err := os.Pipe()
    if err != nil {{
        t.Fatal(err)
    }}
    os.Stdout = writer
    Main()
    if err := writer.Close(); err != nil {{
        t.Fatal(err)
    }}
    os.Stdout = oldStdout
    var buffer bytes.Buffer
    if _, err := buffer.ReadFrom(reader); err != nil {{
        t.Fatal(err)
    }}
    if err := os.WriteFile({json.dumps(log_name)}, buffer.Bytes(), 0644); err != nil {{
        t.Fatal(err)
    }}
}}
'''


def normalize_log(text: str) -> str:
    return text.replace("\r\n", "\n")


def run(command: list[str], cwd: Path, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    if quiet:
        return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return subprocess.run(command, cwd=cwd, text=True)


def run_fuzzy_tests(cycles: int = 5, initial_seed: int = 42000) -> bool:
    print("\n=== RUNNING DYNAMIC FUZZY TESTS ===")
    failed = False

    # 1. Positive typing fuzz tests (typing_pos): must compile & build with stage3
    print(f"\n--- Running {cycles} Positive Fuzzing Tests (typing_pos) ---")
    for i in range(1, cycles + 1):
        seed = initial_seed + i * 111
        source = build_typing_positive(seed)
        
        match = re.search(r'module\s+([A-Za-z0-9_\.]+)', source)
        if not match:
            print(f"[FAIL] Could not extract module name from typing_pos fuzz source (seed {seed})")
            failed = True
            continue
        module_name = match.group(1)
        
        parts = module_name.split(".")
        fuzz_root = OUT_ROOT / f"fuzz_pos_{i}"
        fuzz_root.mkdir(parents=True, exist_ok=True)
        
        fuzz_dir = fuzz_root / "fuzz"
        fuzz_dir.mkdir(parents=True, exist_ok=True)
        
        entry_file = fuzz_dir / f"{parts[1]}.fh"
        entry_file.write_text(source, encoding="utf-8")
        
        example = SupportedExample(
            name=f"fuzz_pos_{i}",
            entry=str(entry_file.relative_to(ROOT)),
            expected_log=None
        )
        
        import time
        start_time = time.time()
        res = run_supported_with_stage3(example)
        elapsed = time.time() - start_time
        
        if res:
            failed = True
            print(f"[FAIL] Positive fuzz test {i} (seed {seed}) failed (took {elapsed:.2f}s).")
        else:
            print(f"[OK] Positive fuzz test {i} (seed {seed}) verified successfully (took {elapsed:.2f}s).")

    # 2. Negative typing fuzz tests (typing_neg): must be rejected by verifier
    print(f"\n--- Running {cycles} Negative Fuzzing Tests (typing_neg) ---")
    for i in range(1, cycles + 1):
        seed = initial_seed + 10000 + i * 111
        source, mutation = build_typing_negative(seed)
        
        match = re.search(r'module\s+([A-Za-z0-9_\.]+)', source)
        if not match:
            print(f"[FAIL] Could not extract module name from typing_neg fuzz source (seed {seed})")
            failed = True
            continue
        module_name = match.group(1)
        
        parts = module_name.split(".")
        fuzz_root = OUT_ROOT / f"fuzz_neg_{i}"
        fuzz_root.mkdir(parents=True, exist_ok=True)
        
        fuzz_dir = fuzz_root / "fuzz"
        fuzz_dir.mkdir(parents=True, exist_ok=True)
        
        entry_file = fuzz_dir / f"{parts[1]}.fh"
        entry_file.write_text(source, encoding="utf-8")
        
        print(f"[STAGE3 FUZZ NEG] fuzz_neg_{i} (mutation: {mutation})")
        
        # Verify must fail
        res = run([sys.executable, "-m", "freehold", "verify", str(entry_file)], ROOT, quiet=True)
        if res.returncode == 0:
            print(f"[FAIL] Negative fuzz test {i} (seed {seed}, mutation {mutation}) unexpectedly verified successfully.")
            failed = True
        else:
            print(f"[OK] Negative fuzz test {i} (seed {seed}, mutation {mutation}) correctly rejected.")

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
