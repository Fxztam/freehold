from __future__ import annotations

from freehold.core.ast import TypeCheckError


def validate_comments(source: str) -> None:
    line = 1
    column = 1
    index = 0
    length = len(source)
    in_string = False
    block_start: tuple[int, int] | None = None

    while index < length:
        char = source[index]
        next_char = source[index + 1] if index + 1 < length else ""

        if char == "\n":
            line += 1
            column = 1
            index += 1
            continue

        if in_string:
            if char == "\\":
                step = 2 if index + 1 < length else 1
                index += step
                column += step
                continue
            if char == '"':
                in_string = False
            index += 1
            column += 1
            continue

        if block_start is not None:
            if char == "/" and next_char == "*":
                raise TypeCheckError(f"line {line}:{column}: nested block comments are not allowed")
            if char == "*" and next_char == "/":
                block_start = None
                index += 2
                column += 2
                continue
            index += 1
            column += 1
            continue

        if char == '"':
            in_string = True
            index += 1
            column += 1
            continue

        if char == "-" and next_char == "-":
            index += 2
            column += 2
            while index < length and source[index] != "\n":
                index += 1
                column += 1
            continue

        if char == "/" and next_char == "*":
            block_start = (line, column)
            index += 2
            column += 2
            continue

        index += 1
        column += 1

    if block_start is not None:
        start_line, start_column = block_start
        raise TypeCheckError(f"line {start_line}:{start_column}: unterminated block comment")