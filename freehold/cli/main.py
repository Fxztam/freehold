from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from freehold.core.diagnostics import diagnose_exception
from freehold.core.pipeline import verify_file, run_file, print_ast

DIAGNOSTIC_ERROR_NAMES = {"UnexpectedToken", "UnexpectedCharacters", "UnexpectedEOF", "TypeCheckError"}

def cmd_run(args):
    run_file(args.file)
    print(f"[OK] run succeeded: {args.file}")
    return 0

def cmd_verify(args):
    verified = verify_file(args.file)
    count = len(getattr(verified, "proof_obligations", []) or [])
    print(f"[OK] verification succeeded: {args.file}")
    print(f"[INFO] proof obligations: {count}")
    return 0

def cmd_ast(args):
    print_ast(args.file)
    return 0

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
    p = sub.add_parser("verify", help="Parse and verify a .fh module"); p.add_argument("file"); p.set_defaults(func=cmd_verify)
    p = sub.add_parser("ast", help="Print parsed AST"); p.add_argument("file"); p.set_defaults(func=cmd_ast)
    p = sub.add_parser("test", help="Run regression tests"); p.add_argument("--log", default=None); p.add_argument("--json-summary", default=None); p.add_argument("--no-console", action="store_true"); p.set_defaults(func=cmd_test)
    p = sub.add_parser("ebnf", help="Regenerate generated EBNF")
    p.add_argument("--dialects", action="store_true", help="Also generate Forge, RR/W3C, VS Code plugin, pyebnf, and parse-ebnf EBNF files")
    p.set_defaults(func=cmd_ebnf)
    p_lang = sub.add_parser("test-language", help="Run modular language conformance tests")
    p_lang.add_argument("--module", default=None)
    p_lang.add_argument("--update", action="store_true")
    p_lang.add_argument("--json-summary", default=None)
    p_lang.set_defaults(func=cmd_test_language)

    return parser

def main(argv=None):
    parser = build_parser(); args = parser.parse_args(argv)
    if args.version:
        print("Freehold CLI: toolchain frontend")
        print("Commands: run, verify, test, ebnf, ast")
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
