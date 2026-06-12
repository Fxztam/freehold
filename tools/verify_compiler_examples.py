from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freehold.core.go_codegen import go_executable_name


GO_BACKEND_EXAMPLES = {
    "29_websocket_go_backend_demo": ("websocket_go_backend.go", 8102),
    "35_http_client_go_backend_demo": ("http_go_backend.go", 8104),
}


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
    SupportedExample("25_quantified_arrays", "examples/compiler_v1/25_quantified_arrays/App/Main.fh"),

    SupportedExample("23_generic_type_inference_and_constraints", "examples/compiler_v1/23_generic_type_inference_and_constraints/App/Main.fh"),
    SupportedExample("26_generic_function", "examples/compiler_v1/26_generic_function/App/Main.fh"),
    SupportedExample("27_websocket_demo", "examples/compiler_v1/27_websocket_demo/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_demo.expected.log"),
    SupportedExample("28_websocket_multi_client_demo", "examples/compiler_v1/28_websocket_multi_client_demo/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_multi_client_demo.expected.log"),
    SupportedExample("29_websocket_go_backend_demo", "examples/compiler_v1/29_websocket_go_backend_demo/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_go_backend_demo.expected.log"),
    SupportedExample("30_websocket_json_broadcast_demo", "examples/compiler_v1/30_websocket_json_broadcast_demo/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_json_broadcast_demo.expected.log"),
    SupportedExample("32_websocket_json_broadcast_schema_neg", "examples/compiler_v1/32_websocket_json_broadcast_schema_neg/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_json_broadcast_schema_neg.expected.log"),
    SupportedExample("33_websocket_room_broadcast_demo", "examples/compiler_v1/33_websocket_room_broadcast_demo/App/Main.fh", "examples/expected_logs/compiler_v1_websocket_room_broadcast_demo.expected.log"),
    SupportedExample("34_http_rest_contract_demo", "examples/compiler_v1/34_http_rest_contract_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_rest_contract_demo.expected.log"),
    SupportedExample("35_http_client_go_backend_demo", "examples/compiler_v1/35_http_client_go_backend_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_client_go_backend_demo.expected.log"),
    SupportedExample("36_http_server_demo", "examples/compiler_v1/36_http_server_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_server_demo.expected.log"),
    SupportedExample("37_http_middleware_demo", "examples/compiler_v1/37_http_middleware_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_middleware_demo.expected.log"),
    SupportedExample("38_http_streaming_demo", "examples/compiler_v1/38_http_streaming_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_streaming_demo.expected.log"),
    SupportedExample("39_http_sse_demo", "examples/compiler_v1/39_http_sse_demo/App/Main.fh", "examples/expected_logs/compiler_v1_http_sse_demo.expected.log"),
    SupportedExample("40_grpc_unary_roundtrip_demo", "examples/compiler_v1/40_grpc_unary_roundtrip_demo/App/Main.fh", "examples/expected_logs/compiler_v1_grpc_unary_roundtrip_demo.expected.log"),
    SupportedExample("41_grpc_server_stream_demo", "examples/compiler_v1/41_grpc_server_stream_demo/App/Main.fh", "examples/expected_logs/compiler_v1_grpc_server_stream_demo.expected.log"),

    SupportedExample("42_go_ffi_demo", "examples/compiler_v1/42_go_ffi_demo/App/Main.fh", "examples/expected_logs/compiler_v1_go_ffi_demo.expected.log"),

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


UNSUPPORTED_EXAMPLES: list[UnsupportedExample] = []


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
        "--emit-executable",
        "--executable-name",
        example.name,
    ], ROOT).returncode != 0:
        print(f"[FAIL] Go project codegen failed: {example.name}")
        return True

    # Copy any extra Go files (like tests) from the example folder to project_out
    example_root = entry.parent
    if entry.parent.name == "App":
        example_root = entry.parent.parent
    for go_file in example_root.glob("*.go"):
        shutil.copy(go_file, project_out)

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


def collect_executable_blank_imports(data: dict, project_out: Path) -> list[str]:
    """Collect blank (side-effect) import paths from the generated executable wrapper.

    The executable wrapper (package main) blank-imports glue packages whose init()
    registers runtime dispatchers/registrars (e.g. gRPC). The in-process runtime-log
    test must perform the same blank imports so those init() functions run.
    """
    blank_imports: list[str] = []
    for f in [*data.get("files", []), *data.get("build_files", []), *data.get("extra_files", [])]:
        content = f.get("content")
        if content is None:
            content = (project_out / f["output_path"]).read_text(encoding="utf-8")
        if "package main" not in content or "func main()" not in content:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('_ "') and stripped.endswith('"'):
                path = stripped[3:-1]
                if path not in blank_imports:
                    blank_imports.append(path)
    return blank_imports


def run_runtime_log_check(example: SupportedExample, project_out: Path, json_path: Path) -> bool:
    assert example.expected_log is not None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    entry_file = next(
        (
            f
            for f in data["files"]
            if "func Main(" in (project_out / f["output_path"]).read_text(encoding="utf-8")
        ),
        data["files"][0],
    )
    go_file = project_out / entry_file["output_path"]
    package_dir = go_file.parent
    package_name = entry_file["result"]["package"]
    log_name = f"{Path(example.entry).stem}.log"
    log_path = package_dir / log_name
    expected_path = ROOT / example.expected_log
    test_path = package_dir / "freehold_runtime_log_test.go"
    main_content = go_file.read_text(encoding="utf-8")
    is_async = "func Main(ctx context.Context)" in main_content
    blank_imports = collect_executable_blank_imports(data, project_out)
    test_path.write_text(
        runtime_log_test_source(package_name, log_name, is_async, blank_imports),
        encoding="utf-8",
    )

    if run_with_optional_go_backend(example, project_out, ["go", "test", "./...", "-run", "TestFreeholdMainRuntimeLog", "-count=1"]).returncode != 0:
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
    exe_path = project_out / "bin" / f"{go_executable_name(example.name)}.exe"
    if not exe_path.exists():
        print(f"[FAIL] generated executable missing: {exe_path.relative_to(ROOT)}")
        return True
    result = run_with_optional_go_backend(example, project_out, [str(exe_path)], capture=True)
    if result.returncode != 0:
        print(f"[FAIL] generated executable failed: {example.name}")
        print(result.stdout)
        return True
    actual = normalize_log(result.stdout)
    expected = normalize_log(expected_path.read_text(encoding="utf-8"))
    if actual != expected:
        actual_path = project_out / f"{go_executable_name(example.name)}.exe.log"
        actual_path.write_text(result.stdout, encoding="utf-8")
        print(f"[FAIL] executable runtime log mismatch: {example.name}")
        print(f"[INFO] expected: {example.expected_log}")
        print(f"[INFO] actual: {actual_path.relative_to(ROOT)}")
        return True
    print(f"[OK] executable runtime log matches: {Path(example.expected_log or '').name}")
    return False


def runtime_log_test_source(package_name: str, log_name: str, is_async: bool = False, blank_imports: list[str] | None = None) -> str:
    ctx_import = '\n\t"context"' if is_async else ''
    main_call = 'Main(context.Background())' if is_async else 'Main()'
    blank_lines = ''.join(f'\n\t_ "{path}"' for path in (blank_imports or []))
    return f'''package {package_name}

import (
    "bytes"
    "os"
    "testing"{ctx_import}{blank_lines}
)

func TestFreeholdMainRuntimeLog(t *testing.T) {{
    oldStdout := os.Stdout
    reader, writer, err := os.Pipe()
    if err != nil {{
        t.Fatal(err)
    }}
    os.Stdout = writer
    {main_call}
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


def run_with_optional_go_backend(example: SupportedExample, project_out: Path, command: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    if example.name not in GO_BACKEND_EXAMPLES:
        if capture:
            return subprocess.run(command, cwd=project_out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return run(command, project_out)

    process = start_go_backend(example, project_out)
    try:
        if capture:
            return subprocess.run(command, cwd=project_out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return run(command, project_out)
    finally:
        stop_go_backend(process)


def start_go_backend(example: SupportedExample, project_out: Path) -> subprocess.Popen[str]:
    source_name, port = GO_BACKEND_EXAMPLES[example.name]
    source_path = project_out / source_name
    exe_path = project_out / "bin" / go_backend_executable_name(example.name)
    exe_path.parent.mkdir(parents=True, exist_ok=True)
    if run(["go", "build", "-trimpath", "-o", str(exe_path), source_name], project_out).returncode != 0:
        raise RuntimeError(f"failed to build Go backend for {example.name}: {source_path}")
    process = subprocess.Popen([str(exe_path)], cwd=project_out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    wait_for_port(port)
    return process


def stop_go_backend(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_for_port(port: int) -> None:
    deadline = time.monotonic() + 10
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"Go backend did not open port {port}: {last_error}")


def go_backend_executable_name(example_name: str) -> str:
    base = f"{go_executable_name(example_name)}_backend"
    if sys.platform == "win32":
        return f"{base}.exe"
    return base


def run(command: list[str], cwd: Path, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    if quiet:
        return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return subprocess.run(command, cwd=cwd, text=True)


if __name__ == "__main__":
    raise SystemExit(main())
