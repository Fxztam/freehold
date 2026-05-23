from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from DHParser.dsl import compileEBNF, compile_python_object
from DHParser.error import has_errors


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAMMAR = REPO_ROOT / "freehold" / "grammar" / "freehold.dhparser.ebnf"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DHParser AST JSON for Freehold language-module tests")
    parser.add_argument("root", nargs="?", default="tests/language_modules", help="language_modules root")
    parser.add_argument("--grammar", default=str(DEFAULT_GRAMMAR), help="DHParser EBNF grammar")
    parser.add_argument("--out", default="artifacts/dhparser-ast", help="artifact output directory")
    parser.add_argument("--stop-after-first", action="store_true", help="stop after the first parsed test case")
    args = parser.parse_args()

    root = Path(args.root)
    out_root = Path(args.out)
    grammar_path = Path(args.grammar)

    parser_factory = load_parser(grammar_path)
    dhparser = parser_factory()

    total = 0
    ok_count = 0
    fail_count = 0
    failures: list[dict[str, str]] = []

    for module_path in sorted(path for path in root.iterdir() if path.is_dir() and looks_like_numbered_module(path.name)):
        module_name = module_path.name
        for case_kind in ("valid", "invalid_syntax", "invalid_semantics"):
            case_path = module_path / case_kind
            if not case_path.is_dir():
                continue

            out_dir = out_root / module_name / case_kind
            out_dir.mkdir(parents=True, exist_ok=True)

            for source_file in sorted(case_path.glob("*.fh")):
                total += 1
                result = parse_file(dhparser, source_file, module_name, case_kind)
                write_json(out_dir / f"{source_file.stem}.json", result)

                if result["parse_ok"]:
                    ok_count += 1
                    print("OK   ", module_name, case_kind, source_file.name)
                else:
                    fail_count += 1
                    failure = {
                        "source_file": result["source_file"],
                        "module_name": module_name,
                        "case_kind": case_kind,
                        "file_name": source_file.name,
                        "error": result["error"],
                    }
                    failures.append(failure)
                    print("FAIL ", module_name, case_kind, source_file.name, "=>", result["error"])

                print("WRITE", out_dir / f"{source_file.stem}.json")

                if args.stop_after_first:
                    print()
                    print("--stop-after-first: stopped after first parsing attempt.")
                    write_run_reports(out_root, total, ok_count, fail_count, failures)
                    print_summary(total, ok_count, fail_count)
                    return 0

    write_run_reports(out_root, total, ok_count, fail_count, failures)
    print_summary(total, ok_count, fail_count)
    return 0


def load_parser(grammar_path: Path):
    grammar = grammar_path.read_text(encoding="utf-8")
    python_source = compileEBNF(grammar, branding="Freehold")
    return compile_python_object(python_source, "FreeholdGrammar")


def parse_file(dhparser: Any, source_file: Path, module_name: str, case_kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_file": display_path(source_file),
        "module_name": module_name,
        "case_kind": case_kind,
        "parse_ok": False,
    }

    try:
        source = source_file.read_text(encoding="utf-8")
        result["source_snippet"] = source
        tree = dhparser(source)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    errors = [str(error) for error in tree.errors]
    if has_errors(tree.errors):
        result["error"] = errors[0] if errors else "DHParser reported an unknown parse error"
        result["errors"] = errors
        return result

    result["parse_ok"] = True
    result["ast"] = node_to_json(tree)
    return result


def node_to_json(node: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"name": node.name}

    pos = getattr(node, "pos", None)
    if isinstance(pos, int) and pos >= 0:
        item["pos"] = pos

    children = [child for child in getattr(node, "children", ()) if child.name != ":Whitespace"]
    if children:
        item["children"] = [node_to_json(child) for child in children]
    else:
        item["text"] = node.content

    return item


def write_run_reports(out_root: Path, total: int, ok_count: int, fail_count: int, failures: list[dict[str, str]]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    write_json(
        out_root / "_summary.json",
        {
            "total": total,
            "ok": ok_count,
            "fail": fail_count,
            "failures": failures,
        },
    )

    lines = [
        f"Total: {total}",
        f"OK:    {ok_count}",
        f"FAIL:  {fail_count}",
    ]
    if failures:
        lines.extend(["", "Failures", "--------"])
        for failure in failures:
            lines.append(
                f"{failure['module_name']} {failure['case_kind']} {failure['file_name']} => {failure['error']}"
            )

    (out_root / "_errors.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def print_summary(total: int, ok_count: int, fail_count: int) -> None:
    print()
    print("Summary")
    print("-------")
    print("Total:", total)
    print("OK:   ", ok_count)
    print("FAIL: ", fail_count)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def looks_like_numbered_module(name: str) -> bool:
    return len(name) >= 3 and name[:2].isdigit() and name[2] == "_"


if __name__ == "__main__":
    raise SystemExit(main())