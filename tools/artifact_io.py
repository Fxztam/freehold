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


def build_manifest(
    rows: list[dict[str, Any]],
    *,
    artifact: str,
    profile: str,
    total_cases: int,
    matching_cases: int,
    mismatching_cases: int,
    case_fields: list[str],
    extra_top_level: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_cases: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: item.get("case", "")):
        manifest_case = {field: row.get(field) for field in case_fields}
        if isinstance(manifest_case.get("violations"), list):
            manifest_case["violations"] = sorted(manifest_case["violations"])
        manifest_cases.append(manifest_case)

    manifest: dict[str, Any] = {
        "artifact": artifact,
        "profile": profile,
        "total_cases": total_cases,
        "matching_cases": matching_cases,
        "mismatching_cases": mismatching_cases,
        "cases": manifest_cases,
    }
    if extra_top_level:
        manifest.update(extra_top_level)
    return manifest
