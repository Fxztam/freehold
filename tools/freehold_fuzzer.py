#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Freehold Grammar-based Fuzzer
=============================

Modi:
  - parser_pos  : generiert syntaktisch gültige Programme aus der EBNF
  - parser_neg  : generiert syntaktisch ungültige Programme per Mutation
  - typing_pos  : generiert syntaktisch + typmäßig gültige Programme
  - typing_neg  : generiert syntaktisch gültige, aber typmäßig ungültige Programme

Eingabe:
  - DHParser-artige EBNF wie in DHParser.ebnf.txt

Ausgabe:
  - .fh.txt Dateien in einem Zielordner
  - manifest.jsonl mit Metadaten pro Datei

Designentscheidungen:
  - Die EBNF wird für die konkrete Freehold-Grammatik geparst.
  - Regex-Terminale werden nicht allgemein random aus Regex generiert, sondern
    für die in der EBNF vorhandenen Terminals gezielt unterstützt:
      IDENT, FIELD_PATH, STRING_LITERAL, INTEGER_LITERAL, DOUBLE_LITERAL, BASE_TYPE.
  - Für Typchecker-Tests kommt eine semantische Overlay-Schicht hinzu, da Typregeln
    nicht in der EBNF kodiert sind.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


# ============================================================
# AST für EBNF
# ============================================================

@dataclass
class Node:
    pass

@dataclass
class Ref(Node):
    name: str

@dataclass
class Lit(Node):
    value: str

@dataclass
class Regex(Node):
    pattern: str

@dataclass
class Seq(Node):
    parts: List[Node]

@dataclass
class Alt(Node):
    options: List[Node]

@dataclass
class Opt(Node):
    node: Node

@dataclass
class Rep(Node):
    node: Node

@dataclass
class Group(Node):
    node: Node


# ============================================================
# Tokenizer für RHS von EBNF-Regeln
# ============================================================

TOKEN_STRING = "STRING"
TOKEN_REGEX = "REGEX"
TOKEN_IDENT = "IDENT"
TOKEN_SYMBOL = "SYMBOL"


def tokenize_rhs(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        if ch == '"':
            j = i + 1
            escaped = False
            buf = ['"']
            while j < n:
                c = text[j]
                buf.append(c)
                if escaped:
                    escaped = False
                elif c == '\\':
                    escaped = True
                elif c == '"':
                    break
                j += 1
            if j >= n or buf[-1] != '"':
                raise ValueError(f"Unclosed string in RHS: {text}")
            tokens.append((TOKEN_STRING, "".join(buf)))
            i = j + 1
            continue

        if ch == '/':
            j = i + 1
            escaped = False
            buf = ['/']
            while j < n:
                c = text[j]
                buf.append(c)
                if escaped:
                    escaped = False
                elif c == '\\':
                    escaped = True
                elif c == '/':
                    break
                j += 1
            if j >= n or buf[-1] != '/':
                raise ValueError(f"Unclosed regex in RHS: {text}")
            tokens.append((TOKEN_REGEX, "".join(buf)))
            i = j + 1
            continue

        if ch in "=|{}[](),~":
            tokens.append((TOKEN_SYMBOL, ch))
            i += 1
            continue

        if re.match(r"[A-Za-z_@]", ch):
            j = i + 1
            while j < n and re.match(r"[A-Za-z0-9_\.@-]", text[j]):
                j += 1
            tokens.append((TOKEN_IDENT, text[i:j]))
            i = j
            continue

        tokens.append((TOKEN_SYMBOL, ch))
        i += 1

    return tokens


# ============================================================
# Parser für EBNF-RHS
# ============================================================

class RHSParser:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Optional[Tuple[str, str]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def pop(self) -> Tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected EOF in RHS parser")
        self.pos += 1
        return tok

    def accept(self, kind: str, value: Optional[str] = None) -> Optional[Tuple[str, str]]:
        tok = self.peek()
        if tok is None:
            return None
        if tok[0] != kind:
            return None
        if value is not None and tok[1] != value:
            return None
        self.pos += 1
        return tok

    def expect(self, kind: str, value: Optional[str] = None) -> Tuple[str, str]:
        tok = self.accept(kind, value)
        if tok is None:
            raise ValueError(f"Expected {kind} {value} at pos {self.pos}, got {self.peek()}")
        return tok

    def parse(self) -> Node:
        node = self.parse_alt()
        if self.peek() is not None:
            raise ValueError(f"Unexpected token after RHS parse: {self.peek()}")
        return node

    def parse_alt(self) -> Node:
        options = [self.parse_seq()]
        while self.accept(TOKEN_SYMBOL, "|"):
            options.append(self.parse_seq())
        if len(options) == 1:
            return options[0]
        return Alt(options)

    def parse_seq(self) -> Node:
        parts: List[Node] = []
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok == (TOKEN_SYMBOL, "|") or tok == (TOKEN_SYMBOL, "]") or tok == (TOKEN_SYMBOL, "}") or tok == (TOKEN_SYMBOL, ")"):
                break
            parts.append(self.parse_item())
        if len(parts) == 1:
            return parts[0]
        return Seq(parts)

    def parse_item(self) -> Node:
        if self.accept(TOKEN_SYMBOL, "~"):
            return self.parse_item()

        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected EOF in parse_item")

        if tok == (TOKEN_SYMBOL, "["):
            self.pop()
            node = self.parse_alt()
            self.expect(TOKEN_SYMBOL, "]")
            return Opt(node)

        if tok == (TOKEN_SYMBOL, "{"):
            self.pop()
            node = self.parse_alt()
            self.expect(TOKEN_SYMBOL, "}")
            return Rep(node)

        if tok == (TOKEN_SYMBOL, "("):
            self.pop()
            node = self.parse_alt()
            self.expect(TOKEN_SYMBOL, ")")
            return Group(node)

        kind, value = self.pop()

        if kind == TOKEN_STRING:
            return Lit(value[1:-1])

        if kind == TOKEN_REGEX:
            return Regex(value[1:-1])

        if kind == TOKEN_IDENT:
            return Ref(value)

        if kind == TOKEN_SYMBOL:
            return Lit(value)

        raise ValueError(f"Unknown token kind: {kind}")


# ============================================================
# EBNF laden
# ============================================================

def parse_ebnf_rules(text: str) -> Dict[str, Node]:
    rules: Dict[str, Node] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("@"):
            continue
        if "=" not in line:
            continue

        head, rhs = line.split("=", 1)
        name = head.strip()

        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue

        tokens = tokenize_rhs(rhs.strip())
        node = RHSParser(tokens).parse()
        rules[name] = node

    return rules


# ============================================================
# Generator aus Grammar
# ============================================================

@dataclass
class GenConfig:
    max_depth: int = 6
    max_repeat: int = 3
    max_seq_items_soft: int = 50


class GrammarGenerator:
    def __init__(self, rules: Dict[str, Node], seed: int = 1, config: Optional[GenConfig] = None):
        self.rules = rules
        self.rand = random.Random(seed)
        self.config = config or GenConfig()
        self.ident_counter = 0

    def generate_program(self, start_rule: str = "start") -> str:
        raw = self.gen_rule(start_rule, depth=0)
        return self.pretty(raw)

    def gen_rule(self, name: str, depth: int = 0) -> str:
        if name in self.rules:
            special = self.gen_special_rule(name, depth)
            if special is not None:
                return special
            return self.gen_node(self.rules[name], depth)
        return self.gen_special_ref(name, depth)

    def gen_special_rule(self, name: str, depth: int) -> Optional[str]:
        if name == "IDENT":
            return self.gen_ident()
        if name == "qualified_name":
            parts = [self.gen_ident(cap=True)]
            for _ in range(self.rand.randint(0, 2)):
                parts.append(self.gen_ident(cap=True))
            return ".".join(parts)
        if name == "FIELD_PATH":
            head = self.gen_ident()
            tail_n = self.rand.randint(1, 3)
            tail = [self.gen_ident() for _ in range(tail_n)]
            return ".".join([head] + tail)
        if name == "INTEGER_LITERAL":
            return str(self.rand.randint(-5, 25))
        if name == "DOUBLE_LITERAL":
            whole = self.rand.randint(-5, 10)
            frac = self.rand.randint(0, 999)
            return f"{whole}.{frac}"
        if name == "NUMBER_LITERAL":
            if self.rand.random() < 0.7:
                return self.gen_rule("INTEGER_LITERAL", depth + 1)
            return self.gen_rule("DOUBLE_LITERAL", depth + 1)
        if name == "STRING_LITERAL":
            return self.gen_string_literal()
        if name == "BASE_TYPE":
            return self.rand.choice(["Integer", "Boolean", "Double", "String", "BigInteger", "BigFloat"])
        if name == "EOF":
            return ""
        return None

    def gen_special_ref(self, name: str, depth: int) -> str:
        if name == "IDENT":
            return self.gen_ident()
        return name

    def gen_ident(self, cap: bool = False) -> str:
        self.ident_counter += 1
        base = self.rand.choice([
            "alpha", "beta", "gamma", "delta", "item", "box", "node",
            "proc", "func", "count", "scope", "audit", "stock", "value"
        ])
        s = f"{base}_{self.ident_counter}"
        if cap:
            s = s[0].upper() + s[1:]
        return s

    def gen_string_literal(self) -> str:
        options = [
            "hello", "world", "SKU-001", "north", "south",
            "trace-01", "demo", "ok", "x", "value"
        ]
        return json.dumps(self.rand.choice(options))

    def gen_node(self, node: Node, depth: int) -> str:
        if depth > self.config.max_depth:
            return self.gen_at_depth_limit(node, depth)

        if isinstance(node, Lit):
            return node.value

        if isinstance(node, Regex):
            return self.gen_from_regex(node.pattern)

        if isinstance(node, Ref):
            return self.gen_rule(node.name, depth + 1)

        if isinstance(node, Seq):
            parts = [self.gen_node(p, depth + 1) for p in node.parts]
            return self.join_parts(parts)

        if isinstance(node, Alt):
            option = self.choose_alt(node.options, depth)
            return self.gen_node(option, depth + 1)

        if isinstance(node, Opt):
            if self.rand.random() < 0.55:
                return self.gen_node(node.node, depth + 1)
            return ""

        if isinstance(node, Rep):
            k = self.choose_rep_count(depth)
            parts = [self.gen_node(node.node, depth + 1) for _ in range(k)]
            return self.join_parts(parts)

        if isinstance(node, Group):
            return self.gen_node(node.node, depth + 1)

        raise TypeError(f"Unsupported node: {type(node)}")

    def gen_at_depth_limit(self, node: Node, depth: int) -> str:
        if isinstance(node, Lit):
            return node.value
        if isinstance(node, Regex):
            return self.gen_from_regex(node.pattern)
        if isinstance(node, Ref):
            if node.name in ("IDENT", "qualified_name", "STRING_LITERAL", "INTEGER_LITERAL",
                             "DOUBLE_LITERAL", "NUMBER_LITERAL", "FIELD_PATH", "BASE_TYPE"):
                return self.gen_rule(node.name, depth + 1)
            if node.name in ("stmt", "declaration"):
                return ""
            if node.name in self.rules:
                return self.gen_at_depth_limit(self.rules[node.name], depth + 1)
            return ""
        if isinstance(node, Seq):
            return self.join_parts([self.gen_at_depth_limit(p, depth + 1) for p in node.parts])
        if isinstance(node, Alt):
            best = min(node.options, key=self.estimate_cost)
            return self.gen_at_depth_limit(best, depth + 1)
        if isinstance(node, Opt):
            return ""
        if isinstance(node, Rep):
            return ""
        if isinstance(node, Group):
            return self.gen_at_depth_limit(node.node, depth + 1)
        return ""

    def estimate_cost(self, node: Node) -> int:
        if isinstance(node, (Lit, Regex, Ref)):
            return 1
        if isinstance(node, Seq):
            return sum(self.estimate_cost(p) for p in node.parts)
        if isinstance(node, Alt):
            return min(self.estimate_cost(o) for o in node.options)
        if isinstance(node, (Opt, Rep, Group)):
            return self.estimate_cost(node.node)
        return 1

    def choose_alt(self, options: List[Node], depth: int) -> Node:
        if depth > self.config.max_depth - 2:
            return min(options, key=self.estimate_cost)
        return self.rand.choice(options)

    def choose_rep_count(self, depth: int) -> int:
        if depth > self.config.max_depth - 2:
            return 0
        return self.rand.choices(
            population=[0, 1, 2, 3],
            weights=[35, 35, 20, 10], k=1
        )[0]

    def gen_from_regex(self, pattern: str) -> str:
        p = pattern
        if "[0-9]" in p and "." not in p:
            return str(self.rand.randint(-10, 50))
        if "\\." in p or "." in p:
            whole = self.rand.randint(-10, 20)
            frac = self.rand.randint(0, 999)
            return f"{whole}.{frac}"
        if '"' in p:
            return self.gen_string_literal()
        if "A-Za-z" in p and "(?:\\." in p:
            head = self.gen_ident()
            tail = [self.gen_ident() for _ in range(self.rand.randint(1, 3))]
            return ".".join([head] + tail)
        if "A-Za-z" in p:
            return self.gen_ident()
        return "x"

    def join_parts(self, parts: List[str]) -> str:
        parts = [p for p in parts if p is not None and p != ""]
        if not parts:
            return ""
        return " ".join(parts)

    def pretty(self, text: str) -> str:
        s = text
        replacements = [
            (" ( ", "("), (" ) ", ")"),
            (" [ ", "["), (" ] ", "]"),
            (" { ", "{"), (" } ", "}"),
            (" ,", ","), (" . ", "."), (" .", "."),
            (" < ", "<"), (" > ", ">"),
            (" : ", ": "),
            (" => ", " => "),
            (" .. ", ".."),
        ]
        for a, b in replacements:
            s = s.replace(a, b)

        s = re.sub(r"\s+\)", ")", s)
        s = re.sub(r"\(\s+", "(", s)
        s = re.sub(r"\s+\]", "]", s)
        s = re.sub(r"\[\s+", "[", s)
        s = re.sub(r"\s+\}", " }", s)
        s = re.sub(r"\{\s+", "{ ", s)
        s = re.sub(r"\s+,", ",", s)
        s = re.sub(r"\s+\.", ".", s)
        s = re.sub(r"\.\s+", ".", s)
        s = re.sub(r"\s+:", ": ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()

        keywords_newline_before = [
            "module", "import", "type", "error", "service", "function", "procedure",
            "requires", "aborts", "ensures", "is", "let", "return", "abort", "if",
            "then", "else", "while", "invariant", "variant", "do", "case", "when",
            "default", "scope", "spawn", "join", "result", "call", "check", "end"
        ]

        for kw in keywords_newline_before:
            s = re.sub(rf"\b{kw}\b", f"\n{kw}", s)

        s = re.sub(r"^\s+", "", s)
        s = re.sub(r"\n{3,}", "\n\n", s)

        lines = [ln.rstrip() for ln in s.splitlines() if ln.strip()]
        out_lines: List[str] = []
        indent = 0
        for raw in lines:
            stripped = raw.strip()
            if stripped in ("end record", "end if", "end while", "end case", "end scope"):
                indent = max(0, indent - 1)
            if re.match(r"^end\b", stripped):
                indent = max(0, indent - 1)
            if stripped in ("else", "when", "default"):
                indent = max(0, indent - 1)

            out_lines.append(("    " * indent) + stripped)

            if stripped.endswith("record") and stripped.startswith("type "):
                indent += 1
            elif re.match(r"^(module|service|function|procedure)\b", stripped):
                indent += 1
            elif stripped.startswith("if "):
                indent += 1
            elif stripped.startswith("while "):
                indent += 1
            elif stripped.startswith("case "):
                indent += 1
            elif stripped.startswith("scope "):
                indent += 1
            elif stripped in ("spawn", "join", "result"):
                indent += 1
            elif stripped in ("else", "when", "default"):
                indent += 1

        final = "\n".join(out_lines).strip() + "\n"
        return final


# ============================================================
# Parser-Negativ-Mutationen
# ============================================================

PARSER_NEG_MUTATIONS = [
    "drop_end_record",
    "drop_default_branch",
    "drop_invariant",
    "drop_returns_clause",
    "break_rpc_syntax",
    "drop_join_block",
]

def mutate_parser_negative(src: str, rng: random.Random) -> Tuple[str, str]:
    muts = PARSER_NEG_MUTATIONS[:]
    rng.shuffle(muts)

    for mut in muts:
        out = apply_parser_mutation(src, mut)
        if out != src:
            return out, mut

    if len(src) > 20:
        idx = rng.randint(0, len(src) - 6)
        return src[:idx] + src[idx+5:], "delete_chunk"
    return src + "\n@", "append_garbage"


def apply_parser_mutation(src: str, mutation: str) -> str:
    if mutation == "drop_end_record":
        return src.replace("end record", "", 1)

    if mutation == "drop_default_branch":
        m = re.search(r"case\b.*?default\s*=>.*?end\s+case", src, flags=re.S)
        if m:
            chunk = m.group(0)
            chunk2 = re.sub(r"default\s*=>.*?(?=end\s+case)", "", chunk, flags=re.S)
            return src.replace(chunk, chunk2, 1)
        return src

    if mutation == "drop_invariant":
        return re.sub(r"\n\s*invariant\b.*", "", src, count=1)

    if mutation == "drop_returns_clause":
        return re.sub(r"\s+returns\s+[A-Za-z_][A-Za-z0-9_<>, ]*", "", src, count=1)

    if mutation == "break_rpc_syntax":
        return re.sub(r"rpc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^)]+)\)",
                      r"rpc \1(\3)", src, count=1)

    if mutation == "drop_join_block":
        m = re.search(r"\n\s*join\b.*?\n\s*result\b", src, flags=re.S)
        if m:
            chunk = m.group(0)
            return src.replace(chunk, "\nresult", 1)
        return src

    return src


# ============================================================
# Typing-Overlay: gültige/ungültige Programme
# ============================================================

PRIMITIVES = ["Integer", "Boolean", "String"]

@dataclass
class RecordDef:
    name: str
    fields: List[Tuple[str, str]]

@dataclass
class FuncDef:
    name: str
    params: List[Tuple[str, str]]
    ret: str

class TypeAwareGenerator:
    def __init__(self, seed: int = 1):
        self.rand = random.Random(seed)
        self.id_counter = 0

    def ident(self, prefix: str = "x", cap: bool = False) -> str:
        self.id_counter += 1
        s = f"{prefix}_{self.id_counter}"
        if cap:
            s = s[0].upper() + s[1:]
        return s

    def literal_for(self, typ: str) -> str:
        if typ == "Integer":
            return str(self.rand.randint(0, 20))
        if typ == "Boolean":
            return self.rand.choice(["true", "false"])
        if typ == "String":
            return json.dumps(self.rand.choice(["hello", "SKU-001", "north", "trace-01"]))
        return self.default_value_for(typ)

    def default_value_for(self, typ: str) -> str:
        if typ in PRIMITIVES:
            return self.literal_for(typ)
        return f"{typ} {{ }}"

    def gen_record(self) -> RecordDef:
        name = self.ident("Record", cap=True)
        fields = [
            (self.ident("id"), "Integer"),
            (self.ident("flag"), "Boolean"),
            (self.ident("label"), "String"),
        ]
        fields = fields[: self.rand.randint(2, 3)]
        return RecordDef(name=name, fields=fields)

    def gen_record_ctor(self, rec: RecordDef) -> str:
        args = []
        for field, typ in rec.fields:
            args.append(f"{field}: {self.literal_for(typ)}")
        return f"{rec.name} {{ " + ", ".join(args) + " }"

    def gen_function(self, rec: RecordDef) -> FuncDef:
        name = self.ident("make")
        return FuncDef(
            name=name,
            params=[("n", "Integer"), ("txt", "String")],
            ret=rec.name
        )

    def render_valid_module(self) -> str:
        module_name = f"fuzz.typing_ok_{self.rand.randint(1, 9999)}"
        rec = self.gen_record()
        f = self.gen_function(rec)

        lines = []
        lines.append(f"module {module_name}")
        lines.append("")
        lines.append(f"type {rec.name} is record")
        for field, typ in rec.fields:
            lines.append(f"    {field}: {typ}")
        lines.append("end record")
        lines.append("")

        lines.append(f"function {f.name}(n: Integer, txt: String) returns {rec.name}")
        lines.append(f"ensures result.{rec.fields[0][0]} = result.{rec.fields[0][0]}")
        lines.append("is")
        ctor_pairs = []
        for field, typ in rec.fields:
            if typ == "Integer":
                ctor_pairs.append(f"{field}: n")
            elif typ == "String":
                ctor_pairs.append(f"{field}: txt")
            elif typ == "Boolean":
                ctor_pairs.append(f"{field}: true")
        lines.append(f"    return {rec.name} {{ " + ", ".join(ctor_pairs) + " }")
        lines.append(f"end {f.name}")
        lines.append("")

        lines.append("procedure main()")
        lines.append("is")
        lines.append(f"    let item: {rec.name} = {f.name}(3, \"hello\")")
        field0, typ0 = rec.fields[0]
        lines.append(f"    check item.{field0} = item.{field0}")
        lines.append("end main")
        lines.append("")
        lines.append(f"end {module_name}")
        lines.append("")
        return "\n".join(lines)

    def mutate_to_typing_negative(self, src: str) -> Tuple[str, str]:
        muts = [
            "assign_string_to_integer",
            "return_wrong_type",
            "unknown_field",
            "wrong_arg_type",
            "field_assignment_type_mismatch",
            "await_non_async"
        ]
        self.rand.shuffle(muts)

        for mut in muts:
            out = self.apply_typing_mutation(src, mut)
            if out != src:
                return out, mut

        return src.replace("Integer", "String", 1), "fallback_type_swap"

    def apply_typing_mutation(self, src: str, mutation: str) -> str:
        if mutation == "assign_string_to_integer":
            m = re.search(r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*Integer\s*=\s*([^\n]+)", src)
            if m:
                full = m.group(0)
                repl = re.sub(r"=\s*[^\n]+", '= "oops"', full)
                return src.replace(full, repl, 1)
            return src.replace("check ", 'let broken: Integer = "oops"\n    check ', 1)

        if mutation == "return_wrong_type":
            m = re.search(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\([^)]*\)\s+returns\s+Integer.*?\bis\b(.*?)\nend\s+\1", src, flags=re.S)
            if m:
                block = m.group(0)
                block2 = re.sub(r"\breturn\b[^\n]+", 'return "nope"', block, count=1)
                return src.replace(block, block2, 1)
            return re.sub(r"\breturn\b[^\n]+", 'return "nope"', src, count=1)

        if mutation == "unknown_field":
            m = re.search(r"check\s+([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", src)
            if m:
                full = m.group(0)
                repl = re.sub(r"\.[A-Za-z_][A-Za-z0-9_]*", ".unknown_field", full, count=1)
                return src.replace(full, repl, 1)
            return src

        if mutation == "wrong_arg_type":
            return re.sub(r"\((\s*)\d+(\s*),", r'("bad",', src, count=1)

        if mutation == "field_assignment_type_mismatch":
            if ":=" in src:
                return re.sub(r":=\s*[^\n]+", ':= "bad"', src, count=1)
            insert = "\n    item." + re.findall(r"let\s+item\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", src)[0] if re.findall(r"let\s+item\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", src) else "\n"
            m_field = re.search(r"type\s+[A-Za-z_][A-Za-z0-9_]*\s+is\s+record\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*Integer", src, flags=re.S)
            if m_field:
                fld = m_field.group(1)
                return src.replace("end main", f"    item.{fld} := \"bad\"\nend main", 1)
            return src

        if mutation == "await_non_async":
            m = re.search(r"(function\s+[A-Za-z_][A-Za-z0-9_]*\([^)]*\)\s+returns\s+[A-Za-z_][A-Za-z0-9_<> ,]*\s*.*?\bis\b\s*\n)", src, flags=re.S)
            if m:
                start = m.group(1)
                return src.replace(start, start + "    let broken: Integer = await 7\n", 1)
            return src

        return src


# ============================================================
# Orchestrierung
# ============================================================

def build_parser_positive(grammar_text: str, seed: int) -> str:
    rules = parse_ebnf_rules(grammar_text)
    gen = GrammarGenerator(rules, seed=seed, config=GenConfig(max_depth=6, max_repeat=3))
    return gen.generate_program("start")


def build_parser_negative(grammar_text: str, seed: int) -> Tuple[str, str]:
    pos = build_parser_positive(grammar_text, seed)
    rng = random.Random(seed * 31337 + 7)
    neg, mut = mutate_parser_negative(pos, rng)
    return neg, mut


def build_typing_positive(seed: int) -> str:
    gen = TypeAwareGenerator(seed)
    return gen.render_valid_module()


def build_typing_negative(seed: int) -> Tuple[str, str]:
    gen = TypeAwareGenerator(seed)
    pos = gen.render_valid_module()
    neg, mut = gen.mutate_to_typing_negative(pos)
    return neg, mut


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_case(out_dir: Path, name: str, content: str) -> Path:
    path = out_dir / name
    path.write_text(content, encoding="utf-8")
    return path


def append_manifest(manifest: Path, obj: dict) -> None:
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def generate_suite(
    suite: str,
    count: int,
    out_dir: Path,
    seed: int,
    grammar_text: Optional[str],
) -> None:
    ensure_dir(out_dir)
    manifest = out_dir / "manifest.jsonl"
    if manifest.exists():
        manifest.unlink()

    for i in range(count):
        case_seed = seed + i * 101
        if suite == "parser_pos":
            if grammar_text is None:
                raise ValueError("parser_pos benötigt --ebnf")
            content = build_parser_positive(grammar_text, case_seed)
            mutation = None
        elif suite == "parser_neg":
            if grammar_text is None:
                raise ValueError("parser_neg benötigt --ebnf")
            content, mutation = build_parser_negative(grammar_text, case_seed)
        elif suite == "typing_pos":
            content = build_typing_positive(case_seed)
            mutation = None
        elif suite == "typing_neg":
            content, mutation = build_typing_negative(case_seed)
        else:
            raise ValueError(f"Unbekannte Suite: {suite}")

        file_name = f"{suite}_{i+1:04d}.fh.txt"
        path = write_case(out_dir, file_name, content)

        append_manifest(manifest, {
            "file": str(path.name),
            "suite": suite,
            "seed": case_seed,
            "mutation": mutation,
        })


# ============================================================
# CLI
# ============================================================

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Freehold grammar-based fuzzer")
    ap.add_argument("--suite", required=True, choices=["parser_pos", "parser_neg", "typing_pos", "typing_neg"])
    ap.add_argument("--ebnf", type=Path, help="Pfad zur EBNF-Datei (für parser_pos/parser_neg erforderlich)")
    ap.add_argument("--count", type=int, default=20, help="Anzahl Fälle")
    ap.add_argument("--seed", type=int, default=12345, help="Start-Seed")
    ap.add_argument("--out-dir", type=Path, required=True, help="Zielordner für generierte Fälle")
    args = ap.parse_args(argv)

    grammar_text = None
    if args.ebnf is not None:
        grammar_text = args.ebnf.read_text(encoding="utf-8")

    generate_suite(
        suite=args.suite,
        count=args.count,
        out_dir=args.out_dir,
        seed=args.seed,
        grammar_text=grammar_text,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
