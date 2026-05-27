from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(number: int, title: str, command: list[str]) -> None:
    print("")
    print(f"=== Step {number}: {title} ===")
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Freehold tests step by step from the source directory")
    parser.add_argument("target", nargs="?", help="Optional language module name, for example 01_core")
    parser.add_argument("--language-root", default="tests/language_modules", help="language modules root")
    parser.add_argument("--quick", action="store_true", help="Run only CLI, core language tests, and the hello demo")
    parser.add_argument("--no-regression", action="store_true", help="Skip the full regression suite")
    parser.add_argument("--no-demos", action="store_true", help="Skip example demo verification")
    args = parser.parse_args(argv)

    py = sys.executable
    step = 1

    if args.target:
        language_root = PROJECT_ROOT / args.language_root
        module_dir = language_root / args.target
        if not module_dir.is_dir():
            print(f"Unknown test target: {args.target}", file=sys.stderr)
            print("Known language modules:", file=sys.stderr)
            modules_root = language_root
            for path in sorted(modules_root.iterdir()):
                if path.is_dir():
                    print(f"  {path.name}", file=sys.stderr)
            return 2
        run_step(step, f"Language module tests: {args.target}", [py, "-m", "freehold", "test-language", "--root", args.language_root, "--module", args.target])
        print("")
        print("All requested Freehold test steps passed.")
        return 0

    run_step(step, "CLI smoke test", [py, "-m", "freehold", "--version"])
    step += 1

    run_step(step, "Core language module tests", [py, "-m", "freehold", "test-language", "--root", args.language_root, "--module", "01_core"])
    step += 1

    if not args.quick and not args.no_regression:
        run_step(step, "Full regression suite", [py, "-m", "freehold", "test"])
        step += 1

    if not args.no_demos:
        run_step(step, "Demo verify: hello_cli", [py, "-m", "freehold", "verify", "examples/hello_cli.fh"])
        step += 1
        run_step(step, "Demo run: hello_cli", [py, "-m", "freehold", "run", "examples/hello_cli.fh"])
        step += 1

        if not args.quick:
            demo_files = [
                "examples/retail_cli_demo_v11f.fh",
                "examples/banking_records.fh",
                "examples/BigNumbers.fh",
                "examples/epsilon_demo.fh",
                "examples/GaussLegendrePi.fh",
                "examples/std_io_console_demo.fh",
                "examples/ChudnovskyPi.fh",
                "examples/ChudnovskyFeynmanPoint.fh",
            ]
            for demo_file in demo_files:
                run_step(step, f"Demo verify: {Path(demo_file).name}", [py, "-m", "freehold", "verify", demo_file])
                step += 1

    print("")
    print("All requested Freehold test steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())