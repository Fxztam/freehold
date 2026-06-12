from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from freehold.core.diagnostics import diagnose_exception
from freehold.core.compare_ir import export_compare_ir_json
from freehold.core.fhir import export_fhir_json, export_fhir_project_json
from freehold.core.go_codegen import generate_go_file, generate_go_project, generate_go_project_build_files, generate_go_project_extra_files, project_result_json, result_json
from freehold.core.grpc_codegen import generate_proto_file
from freehold.core.grpc_go_codegen import generate_grpc_go_bindings_file
from freehold.core.module_resolver import ModuleResolver
from freehold.core.pipeline import verify_file, run_file, print_ast
from freehold.core.go_codegen import GO_RUNTIME_MODULE_EXPORTS
from freehold.core.source_map import export_source_map_json

DIAGNOSTIC_ERROR_NAMES = {"UnexpectedToken", "UnexpectedCharacters", "UnexpectedEOF", "TypeCheckError"}

def cmd_run(args):
    run_file(args.file)
    print(f"[OK] run succeeded: {args.file}")
    return 0

def cmd_verify(args):
    verified = verify_file(args.file, prover=args.prover, timeout=args.timeout)
    count = len(getattr(verified, "proof_obligations", []) or [])
    print(f"[OK] verification succeeded: {args.file}")
    print(f"[INFO] proof obligations: {count}")
    return 0

def cmd_ast(args):
    print_ast(args.file)
    return 0

def cmd_fhir(args):
    resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
    resolver.resolve_entry(args.file)
    if resolver.entry is None or resolver.entry.verified is None:
        raise RuntimeError("module resolver did not produce an entry module")

    if args.module_only:
        fhir_json = export_fhir_json(resolver.entry.verified)
    else:
        fhir_json = export_fhir_project_json(resolver.entry.name, resolver.resolved, GO_RUNTIME_MODULE_EXPORTS)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(fhir_json, encoding="utf-8")
        print(f"[OK] FH-IR JSON written: {out}")
    else:
        print(fhir_json, end="")
    return 0


def cmd_compare_ir(args):
    resolver = ModuleResolver(runtime_modules=GO_RUNTIME_MODULE_EXPORTS)
    verified = resolver.verify_entry(args.file)
    compare_ir_json = export_compare_ir_json(verified, profile=args.profile)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(compare_ir_json, encoding="utf-8", newline="\n")
        print(f"[OK] Compare-IR JSON written: {out}")
    else:
        print(compare_ir_json, end="")
    return 0

def cmd_source_map(args):
    source_map_json = export_source_map_json(args.file)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(source_map_json, encoding="utf-8", newline="\n")
        print(f"[OK] Source-map JSON written: {out}")
    else:
        print(source_map_json, end="")
    return 0

def cmd_grpc_proto(args):
    proto = generate_proto_file(args.file)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(proto, encoding="utf-8")
        print(f"[OK] gRPC proto generated: {out}")
    else:
        print(proto, end="")
    return 0

def cmd_grpc_go_bindings(args):
    source = generate_grpc_go_bindings_file(args.file)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(source, encoding="utf-8")
        print(f"[OK] gRPC Go bindings generated: {out}")
    else:
        print(source, end="")
    return 0

def cmd_go_codegen(args):
    result = generate_go_file(args.file)
    status = "generated"
    if args.verify:
        expected = Path(args.verify).read_text(encoding="utf-8")
        status = "match" if normalize_text(result.go_source) == normalize_text(expected) else "mismatch"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.go_source, encoding="utf-8")
        print(f"[OK] Go code generated: {out}")
    else:
        print(result.go_source, end="")
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(result_json(
            result,
            source_file=args.file,
            artifact_file=args.output or "",
            expected_file=args.verify or "",
            status=status,
        ), encoding="utf-8")
        print(f"[OK] Go codegen JSON written: {json_path}")
    if args.verify:
        print(f"[OK] Go codegen verify {status}: {args.verify}" if status == "match" else f"[FAIL] Go codegen verify mismatch: {args.verify}")
        return 0 if status == "match" else 1
    return 0

def cmd_go_codegen_project(args):
    files = generate_go_project(args.file)
    extra_files = generate_go_project_extra_files(files)
    entry_module_name = project_entry_module_name(files, args.file)
    executable_name = args.executable_name or Path(args.file).stem
    emit_executable = args.emit_executable and project_has_entry_main(files, entry_module_name)
    out_root = Path(args.output_dir)
    build_files = generate_go_project_build_files(
        files,
        executable_name=executable_name if emit_executable else None,
        entry_module_name=entry_module_name,
        output_dir=out_root,
    )
    for file in files:
        out_path = out_root / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.result.go_source, encoding="utf-8")
        print(f"[OK] Go project file generated: {out_path}")
    for file in build_files:
        out_path = out_root / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.content, encoding="utf-8")
        print(f"[OK] Go project build file generated: {out_path}")
    for file in extra_files:
        out_path = out_root / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.content, encoding="utf-8")
        print(f"[OK] Go project extra file generated: {out_path}")
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(project_result_json(files, build_files, extra_files), encoding="utf-8")
        print(f"[OK] Go project JSON written: {json_path}")
    if args.emit_executable and not emit_executable:
        print("[INFO] Go executable not emitted: entry module has no Main() routine")
    return 0 if all(file.result.supported for file in files) else 1

def cmd_whyml(args):
    from freehold.core.pipeline import parse_source
    from freehold.core.whyml_codegen import generate_whyml
    source = Path(args.file).read_text(encoding="utf-8")
    program = parse_source(source)
    result = generate_whyml(program)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")
        print(f"[OK] WhyML generated: {out}")
    else:
        print(result, end="")
    return 0

def cmd_build_exe(args):
    entry_file = Path(args.file)
    if not entry_file.exists():
        print(f"[ERROR] Entry file {args.file} does not exist.", file=sys.stderr)
        return 1

    exe_name = args.executable_name or entry_file.stem
    out_dir = Path(args.output_dir or "bin").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Generating Go project files in target directory: {out_dir}...")
    files = generate_go_project(str(entry_file))
    entry_module_name = project_entry_module_name(files, str(entry_file))
    
    if not project_has_entry_main(files, entry_module_name):
        print(f"[ERROR] Entry module {entry_module_name} has no Main() routine.", file=sys.stderr)
        return 1

    for file in files:
        out_path = out_dir / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.result.go_source, encoding="utf-8")

    extra_files = generate_go_project_extra_files(files)
    for file in extra_files:
        out_path = out_dir / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.content, encoding="utf-8")

    build_files = generate_go_project_build_files(
        files,
        executable_name=exe_name,
        entry_module_name=entry_module_name,
        output_dir=out_dir,
    )
    for file in build_files:
        out_path = out_dir / file.output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(file.content, encoding="utf-8")

    print("[INFO] Resolving Go dependencies (go mod tidy)...")
    res_tidy = subprocess.run(["go", "mod", "tidy"], cwd=out_dir, capture_output=True, text=True)
    if res_tidy.returncode != 0:
        print(f"[ERROR] go mod tidy failed:\n{res_tidy.stderr}", file=sys.stderr)
        return res_tidy.returncode

    print("[INFO] Compiling native binary...")
    bin_name = f"{exe_name}.exe" if sys.platform == "win32" else exe_name
    cmd_build = ["go", "build", "-trimpath", "-o", bin_name, f"./cmd/{exe_name}"]
    res_build = subprocess.run(cmd_build, cwd=out_dir, capture_output=True, text=True)
    if res_build.returncode != 0:
        print(f"[ERROR] go build failed:\n{res_build.stderr}", file=sys.stderr)
        return res_build.returncode

    dest_bin = out_dir / bin_name
    print(f"[OK] Successfully built native executable: {dest_bin}")
    return 0

def project_entry_module_name(files, entry_file: str):
    entry_path = Path(entry_file)
    if not entry_path.is_absolute():
        entry_path = Path.cwd() / entry_path
    entry_path = entry_path.resolve()
    for file in files:
        source_path = Path(file.source_file)
        if not source_path.is_absolute():
            source_path = Path.cwd() / source_path
        if source_path.resolve() == entry_path:
            return file.module_name
    return files[0].module_name if files else None

def project_has_entry_main(files, entry_module_name: str | None) -> bool:
    entry = next((file for file in files if file.module_name == entry_module_name), None)
    if entry is None:
        return False
    return re.search(r"(?m)^func Main\((?:ctx context\.Context)?\)(?: error)? \{", entry.result.go_source) is not None

def normalize_text(text: str) -> str:
    return text.strip().replace("\r\n", "\n")

def cmd_test(args):
    cmd = [sys.executable, "run_modular_tests.py"]
    if args.log: cmd += ["--log", args.log]
    if args.json_summary: cmd += ["--json-summary", args.json_summary]
    if args.no_console: cmd.append("--no-console")
    return subprocess.run(cmd, cwd=Path.cwd(), text=True).returncode

def cmd_ebnf(args):
    script = Path("tools/lark_to_ebnf.py")
    if not script.exists():
        print("[ERROR] tools/lark_to_ebnf.py not found. Run from project root.", file=sys.stderr)
        return 2
    subprocess.run([sys.executable, str(script)], check=True)
    print("[OK] EBNF generated: freehold/grammar/freehold.generated.ebnf")
    if args.dialects:
        dialect_script = next((path for path in [Path("iso2dialect.py"), Path("../iso2dialect.py"), Path("../../iso2dialect.py")] if path.exists()), None)
        if dialect_script is None:
            print("[ERROR] iso2dialect.py not found. Expected it in the project root or a parent folder.", file=sys.stderr)
            return 2
        source = "freehold/grammar/freehold.generated.ebnf"
        outputs = {
            "forge": "freehold/grammar/freehold.generated.forge.ebnf",
            "rr": "freehold/grammar/freehold.generated.rr.ebnf",
            "vscode": "freehold/grammar/freehold.generated.vscode.ebnf",
            "pyebnf": "freehold/grammar/freehold.generated.pyebnf.ebnf",
            "parseebnf": "freehold/grammar/freehold.generated.parseebnf.ebnf",
        }
        for dialect, output in outputs.items():
            subprocess.run([sys.executable, str(dialect_script), source, "--dialect", dialect, "-o", output], check=True)
            print(f"[OK] {dialect} EBNF generated: {output}")
        ebnff = Path("tools/ebnff.exe")
        if ebnff.exists():
            subprocess.run([
                str(ebnff),
                "--out",
                "freehold/grammar/freehold.generated.forge.ir.json",
                "freehold/grammar/freehold.generated.forge.ebnf",
            ], check=True)
            print("[OK] Forge IR generated: freehold/grammar/freehold.generated.forge.ir.json")
    return 0


def cmd_test_language(args):
    from freehold.tests.language_runner import main as language_main
    argv = []
    if getattr(args, "module", None):
        argv += ["--module", args.module]
    if getattr(args, "root", None):
        argv += ["--root", args.root]
    if getattr(args, "update", False):
        argv.append("--update")
    if getattr(args, "json_summary", None):
        argv += ["--json-summary", args.json_summary]
    return language_main(argv)

def print_diagnostic(args, exc: Exception) -> bool:
    if type(exc).__name__ not in DIAGNOSTIC_ERROR_NAMES or not hasattr(args, "file"):
        return False
    try:
        source = Path(args.file).read_text(encoding="utf-8")
    except OSError:
        return False
    print(diagnose_exception(source, exc).format(), file=sys.stderr)
    return True

def build_parser():
    parser = argparse.ArgumentParser(prog="freehold", description="Freehold command line toolchain")
    parser.add_argument("--version", action="store_true", help="Show CLI version/status and exit")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("run", help="Parse, verify, and run a .fh module"); p.add_argument("file"); p.set_defaults(func=cmd_run)
    p = sub.add_parser("verify", help="Parse and verify a .fh module")
    p.add_argument("file")
    p.add_argument("--prover", default=None, help="SMT solvers to use, comma-separated (e.g. 'z3', 'cvc5', or 'z3,cvc5')")
    p.add_argument("--timeout", type=int, default=None, help="Solver timeout in seconds")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("ast", help="Print parsed AST"); p.add_argument("file"); p.set_defaults(func=cmd_ast)
    p = sub.add_parser("ir", aliases=["fhir"], help="Export canonical FH-IR JSON (project-wide v1 by default)")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.add_argument("--module-only", action="store_true", help="Export single-module FH-IR v0 instead of project-wide v1")
    p.set_defaults(func=cmd_fhir)
    p = sub.add_parser("compare-ir", help="Export reduced compare IR JSON from a verified Freehold module")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.add_argument("--profile", choices=["v0", "v1"], default="v1", help="compare-ir export profile (default: v1)")
    p.set_defaults(func=cmd_compare_ir)
    p = sub.add_parser("source-map", help="Export source reconstruction sidecar JSON for FH-IR")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.set_defaults(func=cmd_source_map)
    p = sub.add_parser("grpc-proto", help="Generate a proto3 file from Freehold gRPC IDL")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.set_defaults(func=cmd_grpc_proto)
    p = sub.add_parser("grpc-go-bindings", help="Generate Go gRPC unary server bindings from Freehold gRPC IDL")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.set_defaults(func=cmd_grpc_go_bindings)
    p = sub.add_parser("go-codegen", help="Generate Go code from a Freehold module")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.add_argument("--json", default=None, help="Write a JSON mirror of the codegen result")
    p.add_argument("--verify", default=None, help="Compare generated Go source with an expected .go file")
    p.set_defaults(func=cmd_go_codegen)
    p = sub.add_parser("go-codegen-project", help="Generate Go files for a resolved Freehold module graph")
    p.add_argument("file")
    p.add_argument("--output-dir", "-o", required=True)
    p.add_argument("--json", default=None, help="Write a JSON mirror of the project codegen result")
    p.add_argument("--emit-executable", action="store_true", help="Emit a cmd/<name>/main.go wrapper and build a native Go executable")
    p.add_argument("--executable-name", default=None, help="Executable base name when --emit-executable is used")
    p.set_defaults(func=cmd_go_codegen_project)
    p = sub.add_parser("build-exe", help="Compile a Freehold module graph into a native executable")
    p.add_argument("file")
    p.add_argument("--output-dir", "-o", default="bin", help="Output directory for the compiled binary")
    p.add_argument("--executable-name", default=None, help="Executable base name")
    p.set_defaults(func=cmd_build_exe)
    p = sub.add_parser("whyml", help="Generate WhyML code from a Freehold module")
    p.add_argument("file")
    p.add_argument("--output", "-o", default=None)
    p.set_defaults(func=cmd_whyml)
    p = sub.add_parser("test", help="Run regression tests"); p.add_argument("--log", default=None); p.add_argument("--json-summary", default=None); p.add_argument("--no-console", action="store_true"); p.set_defaults(func=cmd_test)
    p = sub.add_parser("ebnf", help="Regenerate generated EBNF")
    p.add_argument("--dialects", action="store_true", help="Also generate Forge, RR/W3C, VS Code plugin, pyebnf, and parse-ebnf EBNF files")
    p.set_defaults(func=cmd_ebnf)
    p_lang = sub.add_parser("test-language", help="Run modular language conformance tests")
    p_lang.add_argument("--module", default=None)
    p_lang.add_argument("--root", default=None, help="language modules root, default tests/language_modules")
    p_lang.add_argument("--update", action="store_true")
    p_lang.add_argument("--json-summary", default=None)
    p_lang.set_defaults(func=cmd_test_language)

    return parser

def main(argv=None):
    parser = build_parser(); args = parser.parse_args(argv)
    if args.version:
        print("Freehold CLI: toolchain frontend")
        print("Commands: run, verify, test, ebnf, ast, ir/fhir, compare-ir, source-map, grpc-proto, grpc-go-bindings, go-codegen, go-codegen-project, build-exe, whyml")
        print("FH-IR schemas: fh-ir-v1 (project-wide default), fh-ir-v0 (--module-only)")
        return 0
    if not args.command:
        parser.print_help(); return 0
    try:
        return args.func(args)
    except Exception as exc:
        if print_diagnostic(args, exc):
            return 1
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
