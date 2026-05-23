from __future__ import annotations

import re
from typing import Any

POSITIONAL_PLACEHOLDER = re.compile(r"\$\{\s*\}")
IDENT_PLACEHOLDER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ANY_TEMPLATE_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")


def template_value_to_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def validate_template(template: str, value_count: int, binding_names: list[str] | None = None) -> int:
    binding_names = binding_names or []
    consumed: list[tuple[int, int]] = []
    positional_count = 0
    named_placeholders: list[str] = []
    for match in ANY_TEMPLATE_PLACEHOLDER.finditer(template):
        consumed.append(match.span())
        content = match.group(1).strip()
        if content:
            if not IDENT_PLACEHOLDER.match(content):
                raise ValueError(f"invalid named template placeholder: ${{{match.group(1)}}}")
            named_placeholders.append(content)
            continue
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

    if positional_count and named_placeholders:
        raise ValueError("cannot mix positional and named template placeholders")

    if named_placeholders:
        seen_bindings: set[str] = set()
        duplicate_bindings = sorted({name for name in binding_names if name in seen_bindings or seen_bindings.add(name)})
        if duplicate_bindings:
            raise ValueError(f"duplicate template binding: {duplicate_bindings[0]}")
        placeholder_names = set(named_placeholders)
        binding_name_set = set(binding_names)
        missing = sorted(placeholder_names - binding_name_set)
        if missing:
            raise ValueError(f"missing template binding: {missing[0]}")
        extra = sorted(binding_name_set - placeholder_names)
        if extra:
            raise ValueError(f"unused template binding: {extra[0]}")
        return len(placeholder_names)

    if binding_names:
        raise ValueError(f"unused template binding: {binding_names[0]}")
    if positional_count != value_count:
        raise ValueError(f"placeholder count mismatch: expected {positional_count}, got {value_count}")
    return positional_count


def render_template(template: str, values: list[Any], bindings: dict[str, Any] | None = None) -> str:
    bindings = bindings or {}
    validate_template(template, len(values), list(bindings.keys()))
    if bindings:
        return ANY_TEMPLATE_PLACEHOLDER.sub(
            lambda match: template_value_to_string(bindings[match.group(1).strip()]),
            template,
        )
    rendered = template
    for value in values:
        rendered = POSITIONAL_PLACEHOLDER.sub(template_value_to_string(value), rendered, count=1)
    return rendered