from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ARTIFACT_ROOT = "artifacts/"
DEFAULT_FH_ROOT = "tests/language_modules/"
IGNORED_ARTIFACT_REPORT_PREFIXES = (
    "artifacts/compare-",
    "artifacts/verify-spec-diagnostics/",
)
IGNORED_ARTIFACT_REPORT_FILES = {
    "artifacts/dhparser-ast/_errors.txt",
    "artifacts/dhparser-ast/_summary.json",
    "artifacts/go-ast/_errors.txt",
    "artifacts/go-ast/_summary.json",
}


@dataclass(frozen=True)
class StatusEntry:
    status: str
    path: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that frozen test lines are only extended, not rewritten."
    )
    parser.add_argument(
        "--artifact-root",
        default=DEFAULT_ARTIFACT_ROOT,
        help="protected artifact root; existing files may not be modified/deleted/renamed",
    )
    parser.add_argument(
        "--fh-root",
        default=DEFAULT_FH_ROOT,
        help="protected .fh test root; existing .fh cases may not be modified/deleted/renamed",
    )
    args = parser.parse_args()

    entries = git_status_entries()
    violations = [entry for entry in entries if is_violation(entry, args.artifact_root, args.fh_root)]
    additions = [entry for entry in entries if is_allowed_addition(entry, args.artifact_root, args.fh_root)]

    print("Verify additive test line")
    print("-------------------------")
    print(f"Allowed additions: {len(additions)}")
    print(f"Frozen-line violations: {len(violations)}")

    if additions:
        print("\nAdditions")
        print("---------")
        for entry in additions:
            print(f"{entry.status} {entry.path}")

    if violations:
        print("\nViolations")
        print("----------")
        for entry in violations:
            print(f"{entry.status} {entry.path}")
        print(
            "\nExisting artifacts and existing .fh language cases are frozen verification baselines. "
            "Add new cases/artifacts instead of modifying or deleting old ones.",
            file=sys.stderr,
        )
        return 1

    return 0


def git_status_entries() -> list[StatusEntry]:
    refresh = subprocess.run(
        ["git", "update-index", "--refresh"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if refresh.returncode not in (0, 1):
        print(refresh.stderr, file=sys.stderr, end="")
        raise SystemExit(refresh.returncode)
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    return [parse_status_line(line) for line in result.stdout.splitlines() if line]


def parse_status_line(line: str) -> StatusEntry:
    status = line[:2]
    raw_path = line[3:]
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]
    return StatusEntry(status=status, path=normalize_path(raw_path))


def is_violation(entry: StatusEntry, artifact_root: str, fh_root: str) -> bool:
    if is_ignored_artifact_report(entry.path):
        return False
    if not is_protected_path(entry.path, artifact_root, fh_root):
        return False
    if is_added(entry.status):
        return False
    return status_touches_existing_file(entry.status)


def is_allowed_addition(entry: StatusEntry, artifact_root: str, fh_root: str) -> bool:
    if is_ignored_artifact_report(entry.path):
        return False
    return is_protected_path(entry.path, artifact_root, fh_root) and is_added(entry.status)


def is_protected_path(path: str, artifact_root: str, fh_root: str) -> bool:
    artifact_root = normalize_root(artifact_root)
    fh_root = normalize_root(fh_root)
    return path.startswith(artifact_root) or (path.startswith(fh_root) and path.endswith(".fh"))


def is_ignored_artifact_report(path: str) -> bool:
    return path in IGNORED_ARTIFACT_REPORT_FILES or any(path.startswith(prefix) for prefix in IGNORED_ARTIFACT_REPORT_PREFIXES)


def is_added(status: str) -> bool:
    return status == "??" or status[0] == "A"


def status_touches_existing_file(status: str) -> bool:
    return any(code in status for code in "MDRCTU")


def normalize_root(path: str) -> str:
    normalized = normalize_path(path)
    return normalized if normalized.endswith("/") else normalized + "/"


def normalize_path(path: str) -> str:
    return Path(path.strip('"')).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())