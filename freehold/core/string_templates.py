from __future__ import annotations

import re
from typing import Any

POSITIONAL_PLACEHOLDER = re.compile(r"\$\{\s*\}")
ANY_TEMPLATE_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")


def template_value_to_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def validate_template(template: str, value_count: int) -> int:
    consumed: list[tuple[int, int]] = []
    positional_count = 0
    for match in ANY_TEMPLATE_PLACEHOLDER.finditer(template):
        consumed.append(match.span())
        content = match.group(1)
        if content.strip():
            raise ValueError(f"named templates are TODO: ${{{content}}}")
        positional_count += 1

    consumed_indexes = {
        index
        for start, end in consumed
        for index in range(start, end)
    }
    index = 0
    while index < len(template):
        if index in consumed_indexes:
            index += 1
            continue
        if template.startswith("{}", index) and index + 1 not in consumed_indexes:
            raise ValueError("template placeholder must use ${} instead of {}")
        char = template[index]
        if char in "{}":
            raise ValueError(f"invalid template brace: {char}")
        index += 1

    if positional_count != value_count:
        raise ValueError(f"placeholder count mismatch: expected {positional_count}, got {value_count}")
    return positional_count


def render_template(template: str, values: list[Any]) -> str:
    validate_template(template, len(values))
    rendered = template
    for value in values:
        rendered = POSITIONAL_PLACEHOLDER.sub(template_value_to_string(value), rendered, count=1)
    return rendered