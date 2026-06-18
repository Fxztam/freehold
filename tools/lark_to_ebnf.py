from __future__ import annotations
from pathlib import Path
import argparse
import html
import re

TERMINAL_MAP = {
    "NAME": "IDENT",
    "INT_NUMBER": "INTEGER_LITERAL",
    "SIGNED_FLOAT": "DOUBLE_LITERAL",
    "SIGNED_NUMBER": "NUMBER_LITERAL",
    "BASE_TYPE": "BASE_TYPE",
    "ESCAPED_STRING": "STRING_LITERAL",
    "WS": "WHITESPACE",
    "COMMENT": "LINE_COMMENT",
    "BLOCK_COMMENT": "BLOCK_COMMENT",
}

TOKEN_RE = re.compile(
    r"""
    (?P<regex>/(?:\\.|[^/])+/)
  | (?P<string>"(?:\\.|[^"])*")
  | (?P<alias>->\s*[A-Za-z_][A-Za-z0-9_]*)
  | (?P<name>[?]?[A-Za-z_][A-Za-z0-9_]*)
  | (?P<symbol>\.\.|=>|:=|!=|<=|>=|[()\[\]{}|*+?:,<>.=\-/])
    """,
    re.VERBOSE,
)

LEXICAL_RULES = {
    "DOUBLE_LITERAL": 'SIGNED_DOUBLE_LITERAL',
    "NUMBER_LITERAL": 'SIGNED_DOUBLE_LITERAL | SIGNED_INTEGER_LITERAL',
    "INTEGER_LITERAL": 'DIGITS',
    "LINE_COMMENT": '"-" "-" { LINE_COMMENT_CHARACTER }',
    "BLOCK_COMMENT": '"/" "*" { BLOCK_COMMENT_CHARACTER } "*" "/"',
    "IDENT": 'LETTER { LETTER | DIGIT | "_" }',
    "STRING_LITERAL": 'DOUBLE_QUOTE { STRING_CHARACTER | ESCAPE_SEQUENCE } DOUBLE_QUOTE',
}

SUPPORT_RULES = {
    "DIGIT": '"0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"',
    "DIGITS": 'DIGIT { DIGIT }',
    "SIGNED_INTEGER_LITERAL": '[ "-" ] DIGITS',
    "SIGNED_DOUBLE_LITERAL": '[ "-" ] DIGITS "." DIGITS',
    "LETTER": '"A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J" | "K" | "L" | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T" | "U" | "V" | "W" | "X" | "Y" | "Z" | "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j" | "k" | "l" | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t" | "u" | "v" | "w" | "x" | "y" | "z"',
    "DOUBLE_QUOTE": '"\\\""',
    "BACKSLASH": '"\\\\"',
    "SPACE": '" "',
    "TAB": '"\\t"',
    "NEWLINE": '"\\n"',
    "PRINTABLE_SYMBOL": '"!" | "#" | "$" | "%" | "&" | "(" | ")" | "*" | "+" | "," | "-" | "." | "/" | ":" | ";" | "<" | "=" | ">" | "?" | "@" | "[" | "]" | "^" | "_" | "`" | "{" | "|" | "}" | "~"',
    "LINE_COMMENT_CHARACTER": 'LETTER | DIGIT | PRINTABLE_SYMBOL | SPACE | TAB | DOUBLE_QUOTE | BACKSLASH',
    "BLOCK_COMMENT_CHARACTER": 'LINE_COMMENT_CHARACTER | NEWLINE',
    "STRING_CHARACTER": 'LETTER | DIGIT | PRINTABLE_SYMBOL | SPACE | TAB',
    "ESCAPE_SEQUENCE": 'BACKSLASH ( DOUBLE_QUOTE | BACKSLASH | "/" | "b" | "f" | "n" | "r" | "t" )',
}


class RhsParser:
    def __init__(self, rhs: str) -> None:
        self.tokens = tokenize_rhs(rhs)
        self.pos = 0

    def peek(self) -> str | None:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def pop(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("unexpected end of rule")
        if expected is not None and token != expected:
            raise ValueError(f"expected {expected!r}, got {token!r}")
        self.pos += 1
        return token

    def parse(self) -> str:
        expr = self.parse_alternatives(stop=set())
        if self.peek() is not None:
            raise ValueError(f"unexpected token {self.peek()!r}")
        return expr

    def parse_alternatives(self, stop: set[str]) -> str:
        choices = [self.parse_sequence(stop | {"|"})]
        while self.peek() == "|":
            self.pop("|")
            choices.append(self.parse_sequence(stop | {"|"}))
        return " | ".join(choice for choice in choices if choice)

    def parse_sequence(self, stop: set[str]) -> str:
        items: list[str] = []
        while True:
            token = self.peek()
            if token is None or token in stop:
                break
            if token == ",":
                self.pop(",")
                continue
            item = self.parse_postfix(stop)
            if item:
                items.append(item)
        return " ".join(items)

    def parse_postfix(self, stop: set[str]) -> str:
        item = self.parse_atom(stop)
        token = self.peek()
        if token == "?":
            self.pop("?")
            return f"[ {item} ]"
        if token == "*":
            self.pop("*")
            return f"{{ {item} }}"
        if token == "+":
            self.pop("+")
            return f"{item} {{ {item} }}"
        return item

    def parse_atom(self, stop: set[str]) -> str:
        token = self.peek()
        if token is None or token in stop:
            return ""
        if token == "(":
            self.pop("(")
            expr = self.parse_alternatives({")"})
            self.pop(")")
            return f"( {expr} )" if " | " in expr else expr
        token = self.pop()
        return convert_token(token)

def strip_lark_directives(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("%"):
            continue
        if s.startswith("//"):
            continue
        out.append(line.rstrip())
    return out

def normalize_rule_name(name: str) -> str:
    return name[1:] if name.startswith("?") else name

def split_rules(text: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    current_name = None
    current_rhs: list[str] = []

    for raw in strip_lark_directives(text.splitlines()):
        if not raw.strip():
            continue
        m = re.match(r"^\s*([?]?[A-Za-z_][A-Za-z0-9_\.]*)\s*:\s*(.*)$", raw)
        if m:
            if current_name is not None:
                rules.append((normalize_rule_name(current_name), " ".join(current_rhs).strip()))
            current_name = m.group(1)
            current_rhs = [m.group(2).strip()]
        elif current_name is not None:
            current_rhs.append(raw.strip())

    if current_name is not None:
        rules.append((normalize_rule_name(current_name), " ".join(current_rhs).strip()))
    return rules


def tokenize_rhs(rhs: str) -> list[str]:
    rhs = re.sub(r"\s*->\s*[A-Za-z_][A-Za-z0-9_]*", "", rhs)
    tokens: list[str] = []
    pos = 0
    while pos < len(rhs):
        if rhs[pos].isspace():
            pos += 1
            continue
        match = TOKEN_RE.match(rhs, pos)
        if match is None:
            raise ValueError(f"cannot tokenize RHS near {rhs[pos:pos + 24]!r}")
        if match.lastgroup != "alias":
            tokens.append(match.group(0))
        pos = match.end()
    return tokens


def convert_token(token: str) -> str:
    if token.startswith("?") and re.match(r"^[?][A-Za-z_]", token):
        token = token[1:]
    if token in TERMINAL_MAP:
        return TERMINAL_MAP[token]
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token):
        return token
    if token.startswith("/") and token.endswith("/"):
        return f"? regular expression {token} ?"
    return token


def convert_rhs(rhs: str) -> str:
    return RhsParser(rhs).parse()


def convert_rule_name(name: str) -> str:
    return TERMINAL_MAP.get(name, name)

def generate_ebnf(lark_text: str, source_name: str = "freehold.lark") -> str:
    rules = split_rules(lark_text)
    lines: list[str] = []
    lines.append("(*")
    lines.append("  Freehold generated ISO EBNF grammar.")
    lines.append(f"  Source: {source_name}")
    lines.append("")
    lines.append("  Generated from the executable Lark grammar.")
    lines.append("  This file is intended for review/documentation.")
    lines.append("  The parser source of truth remains freehold.lark.")
    lines.append("*)")
    lines.append("")

    for name, rhs in rules:
        rule_name = convert_rule_name(name)
        rule_rhs = LEXICAL_RULES.get(rule_name, convert_rhs(rhs))
        lines.append(f"{rule_name} = {rule_rhs} ;")
    lines.extend(synthetic_lexical_rules(lark_text, "\n".join(lines)))
    lines.append("")
    return normalize_entities("\n".join(lines))


def normalize_entities(text: str) -> str:
    text = html.unescape(text)
    return text.replace("=&gt;", "=>")


def synthetic_lexical_rules(lark_text: str, generated_text: str) -> list[str]:
    lines: list[str] = []
    defined = {convert_rule_name(name) for name, _ in split_rules(lark_text)}

    if "IDENT" in generated_text and "IDENT" not in defined:
        lines.append(f"IDENT = {LEXICAL_RULES['IDENT']} ;")
    if "STRING_LITERAL" in generated_text and "STRING_LITERAL" not in defined:
        lines.append(f"STRING_LITERAL = {LEXICAL_RULES['STRING_LITERAL']} ;")

    used_names = set(re.findall(r"\b[A-Z][A-Z0-9_]*\b", "\n".join(lines) + "\n" + generated_text))
    changed = True
    while changed:
        changed = False
        for name, rhs in SUPPORT_RULES.items():
            if name not in used_names:
                continue
            for dependency in re.findall(r"\b[A-Z][A-Z0-9_]*\b", rhs):
                if dependency not in used_names:
                    used_names.add(dependency)
                    changed = True

    for name, rhs in SUPPORT_RULES.items():
        if name in used_names and name not in defined:
            lines.append(f"{name} = {rhs} ;")
    return lines

def main() -> None:
    p = argparse.ArgumentParser(description="Generate Freehold EBNF from Lark grammar")
    p.add_argument("--input", default="freehold/grammar/freehold.lark")
    p.add_argument("--output", default="freehold/grammar/freehold.generated.ebnf")
    args = p.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    text = inp.read_text(encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generate_ebnf(text, str(inp)), encoding="utf-8")
    print(f"[OK] generated {out}")

if __name__ == "__main__":
    main()
