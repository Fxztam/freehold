from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from lark.exceptions import UnexpectedInput

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from freehold.core.ast import TypeCheckError
from freehold.core.fhir import export_fhir_json
from freehold.core.module_resolver import ModuleResolver
from tools.verify_compiler_examples import SUPPORTED_EXAMPLES


DEFAULT_EXPECTED_ROOT = Path("artifacts/fhir")
DEFAULT_OUT_ROOT = Path("artifacts/compare-fhir")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare canonical FH-IR export against committed baselines")
    parser.add_argument("--expected", default=str(DEFAULT_EXPECTED_ROOT), help="committed FH-IR baseline root")
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="comparison report output root")
    parser.add_argument("--update", action="store_true", help="write missing or changed FH-IR baselines")
    parser.add_argument("--force", action="store_true", help="allow baseline update even when expected root is dirty")
    parser.add_argument("--dry-run", action="store_true", help="report baseline changes without writing files")
    args = parser.parse_args()

    if args.dry_run and not args.update:
        print("--dry-run requires --update", file=sys.stderr)
        return 2

    expected_root = Path(args.expected)
    out_root = Path(args.out)

    if args.update and not ensure_update_allowed(expected_root, force=args.force):
        return 2

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    baseline_updates = 0

    for example in SUPPORTED_EXAMPLES:
        row = run_case(example.name, Path(example.entry), expected_root, update=args.update, dry_run=args.dry_run)
        rows.append(row)
        if row["status"] != "match":
            mismatches.append(row)
        if row.get("would_update_baseline"):
            baseline_updates += 1

    summary = {
        "total_cases": len(rows),
        "matching_fhir": len(rows) - len(mismatches),
        "mismatching_fhir": len(mismatches),
        "mismatches": mismatches,
        "baseline_updates": baseline_updates,
        "dry_run": bool(args.dry_run),
    }

    out_root.mkdir(parents=True, exist_ok=True)
    write_json(out_root / "_all.json", rows, additive=args.update)
    write_json(out_root / "_summary.json", summary, additive=args.update)
    write_text_report(out_root / "_mismatches.txt", summary, additive=args.update)
    print_summary(summary)
    return 1 if mismatches else 0


def run_case(name: str, entry_path: Path, expected_root: Path, *, update: bool, dry_run: bool) -> dict[str, Any]:
    source_path = (REPO_ROOT / entry_path).resolve()
    expected_path = expected_root / f"{name}.json"
    expected_path.parent.mkdir(parents=True, exist_ok=True)

    actual_text = ""
    actual: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    try:
        verified = ModuleResolver().verify_entry(source_path)
        actual_text = export_fhir_json(verified)
        actual = json.loads(actual_text)
    except (TypeCheckError, UnexpectedInput) as exc:
        error = build_error("parse_or_resolver", exc, source_path)
    except (OSError, UnicodeError) as exc:
        error = build_error("io", exc, source_path)
    except json.JSONDecodeError as exc:
        error = build_error("json_decode", exc, source_path)
    except Exception as exc:
        raise RuntimeError(f"unexpected failure while exporting FH-IR: {display_path(source_path)}") from exc

    baseline_changed = False
    if actual_text:
        if expected_path.exists():
            baseline_changed = normalize(expected_path.read_text(encoding="utf-8")) != normalize(actual_text)
        else:
            baseline_changed = True
    if update and actual_text and not dry_run:
        expected_path.write_text(actual_text, encoding="utf-8")

    expected = None
    if expected_path.exists():
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            if error is None:
                error = build_error("io", exc, expected_path)
        except json.JSONDecodeError as exc:
            if error is None:
                error = build_error("json_decode", exc, expected_path)
        except Exception as exc:
            raise RuntimeError(f"unexpected failure while loading baseline: {display_path(expected_path)}") from exc

    status = "match" if error is None and actual == expected else "mismatch"
    row = {
        "case": name,
        "status": status,
        "source_file": display_path(source_path),
        "expected_file": display_path(expected_path),
        "schema": actual.get("schema") if isinstance(actual, dict) else "",
        "module": actual.get("module", {}).get("name", "") if isinstance(actual, dict) else "",
        "analysis_routines": len(actual.get("analysis", {}).get("routines", [])) if isinstance(actual, dict) else 0,
        "error": error,
        "would_update_baseline": bool(update and dry_run and baseline_changed),
    }
    if row["would_update_baseline"]:
        print("DRY  ", name)
    else:
        print("OK   " if status == "match" else "FAIL ", name)
    print(display_path(expected_path))
    return row


def write_json(path: Path, value: Any, *, additive: bool = False) -> bool:
    return write_artifact(path, json.dumps(value, indent=2) + "\n", additive=additive)


def write_text_report(path: Path, summary: dict[str, Any], *, additive: bool = False) -> bool:
    lines = [
        f"Total cases:     {summary['total_cases']}",
        f"Matching FH-IR:  {summary['matching_fhir']}",
        f"Mismatching FH-IR: {summary['mismatching_fhir']}",
        f"Baseline updates: {summary.get('baseline_updates', 0)}",
        f"Dry run:         {summary.get('dry_run', False)}",
    ]
    if summary["mismatches"]:
        lines.extend(["", "Mismatches", "----------"])
        for mismatch in summary["mismatches"]:
            lines.append(f"{mismatch['case']} => {mismatch['expected_file']}")
    return write_artifact(path, "\n".join(lines) + "\n", additive=additive)


def write_artifact(path: Path, content: str, *, additive: bool) -> bool:
    if additive and path.exists():
        return normalize(path.read_text(encoding="utf-8")) != normalize(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return False


def normalize(text: str) -> str:
    return text.strip().replace("\r\n", "\n")


def print_summary(summary: dict[str, Any]) -> None:
    print("Compare FH-IR artifacts")
    print("-----------------------")
    print("Total cases:     ", summary["total_cases"])
    print("Matching FH-IR:  ", summary["matching_fhir"])
    print("Mismatching FH-IR:", summary["mismatching_fhir"])
    print("Baseline updates:", summary.get("baseline_updates", 0))
    print("Dry run:         ", summary.get("dry_run", False))


def ensure_update_allowed(expected_root: Path, *, force: bool) -> bool:
    if force:
        return True

    pathspec = expected_root.as_posix()
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", pathspec],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        return False
    if result.stdout.strip():
        print(
            f"Refusing to update baselines: target path is dirty ({pathspec}). "
            "Commit/stash changes first or rerun with --force.",
            file=sys.stderr,
        )
        return False
    return True


def build_error(category: str, exc: Exception, context_path: Path) -> dict[str, Any]:
    return {
        "category": category,
        "type": type(exc).__name__,
        "message": str(exc),
        "context": display_path(context_path),
    }


def display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())