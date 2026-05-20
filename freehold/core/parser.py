from __future__ import annotations
from pathlib import Path
from lark import Lark
from freehold.core.comment_rules import validate_comments
from freehold.core.parser_legacy import AstBuilder

GRAMMAR_PATH = Path(__file__).resolve().parents[1] / "grammar" / "freehold.lark"

def load_grammar() -> str:
    return GRAMMAR_PATH.read_text(encoding="utf-8")

_parser = None

def get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = Lark(load_grammar(), parser="lalr", start="start", propagate_positions=True)
    return _parser

def parse_source(source: str):
    validate_comments(source)
    return AstBuilder().program(get_parser().parse(source))
