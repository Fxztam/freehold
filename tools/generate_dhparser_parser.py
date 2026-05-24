from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from DHParser.dsl import compileEBNF


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAMMAR = Path("freehold/grammar/freehold.dhparser.ebnf")
DEFAULT_OUT = Path("artifacts/dhparser-parser")
DEFAULT_PARSER_NAME = "freehold_dhparser_parser.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DHParser Python parser code from Freehold DHParser EBNF")
    parser.add_argument("--grammar", default=str(DEFAULT_GRAMMAR), help="DHParser EBNF grammar")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument("--parser-name", default=DEFAULT_PARSER_NAME, help="generated parser file name")
    args = parser.parse_args()

    grammar_path = Path(args.grammar)
    out_root = Path(args.out)
    parser_path = out_root / args.parser_name
    summary_path = out_root / "_summary.json"

    grammar = grammar_path.read_text(encoding="utf-8")
    generated_source = compileEBNF(grammar, branding="Freehold")

    out_root.mkdir(parents=True, exist_ok=True)
    parser_path.write_text(generated_source, encoding="utf-8")
    summary = build_summary(grammar_path, parser_path, grammar, generated_source)
    write_json(summary_path, summary)

    print("Generate DHParser parser")
    print("------------------------")
    print("Grammar: ", display_path(grammar_path))
    print("Parser:  ", display_path(parser_path))
    print("Summary: ", display_path(summary_path))
    print("Bytes:   ", summary["generated_bytes"])
    return 0


def build_summary(grammar_path: Path, parser_path: Path, grammar: str, generated_source: str) -> dict[str, Any]:
    return {
        "grammar_file": display_path(grammar_path),
        "parser_file": display_path(parser_path),
        "grammar_sha256": sha256_text(grammar),
        "generated_sha256": sha256_text(generated_source),
        "grammar_bytes": len(grammar.encode("utf-8")),
        "generated_bytes": len(generated_source.encode("utf-8")),
        "contains_freehold_grammar": "FreeholdGrammar" in generated_source,
    }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())