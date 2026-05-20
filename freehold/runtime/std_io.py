from __future__ import annotations

from freehold.core.string_templates import render_template

def log(value) -> None:
    print(value)

def logf(template: str, *values) -> None:
    print(render_template(template, list(values)))
