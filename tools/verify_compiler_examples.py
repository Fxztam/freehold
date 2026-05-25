from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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
    UnsupportedExample("unsupported_grpc_binding", "examples/compiler_v1/unsupported/grpc_binding/App/Main.fh", "FH-GOCODEGEN-0001"),
    UnsupportedExample("unsupported_async_scope_runtime", "examples/compiler_v1/unsupported/async_scope_runtime/App/Main.fh", "FH-GOCODEGEN-0001"),
    UnsupportedExample("old_concurrent_grpc_channel_demo", "examples/concurrent_grpc_channel_demo.fh", "FH-GOCODEGEN-0001"),
]


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / ".tmp" / "compiler_examples"


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    failed = False
    for example in SUPPORTED_EXAMPLES:
        failed = run_supported(example) or failed
    for example in UNSUPPORTED_EXAMPLES:
        failed = run_unsupported(example) or failed

    if failed:
        print("\n[FAIL] Compiler example smoke failed.")
        return 1
    print("\n[OK] Compiler example smoke passed.")
    return 0


def run_supported(example: SupportedExample) -> bool:
    print(f"\n[EXAMPLE] {example.name}")
    project_out = OUT_ROOT / example.name
    entry = ROOT / example.entry

    if run([sys.executable, "-m", "freehold", "verify", str(entry)], ROOT).returncode != 0:
        print(f"[FAIL] verification failed: {example.name}")
        return True

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
    ], ROOT).returncode != 0:
        print(f"[FAIL] Go project codegen failed: {example.name}")
        return True

    if run(["cmd", "/c", "build.cmd"], project_out).returncode != 0:
        print(f"[FAIL] generated Go build failed: {example.name}")
        return True

    if example.expected_log is not None and run_runtime_log_check(example, project_out, json_path):
        return True

    print(f"[OK] {example.name}")
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


if __name__ == "__main__":
    raise SystemExit(main())
