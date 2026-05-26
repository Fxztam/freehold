from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def default_temp_out_root(name: str) -> Path:
    return Path(tempfile.gettempdir()) / f"freehold-{name}"


def canonical_json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalize_text(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, canonical_json_text(value))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def would_change_file(path: Path, content: str) -> bool:
    if not path.exists():
        return True
    return normalize_text(path.read_text(encoding="utf-8")) != normalize_text(content)
