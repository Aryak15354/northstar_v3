#!/usr/bin/env python3
"""Parse every active Python file that belongs to the public source tree."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


ACTIVE_ROOTS = ("arya", "scripts", "src", "tests")
SKIP_PARTS = {
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "archive",
    "backups",
    "catboost_info",
    "data",
    "dist",
    "docs/archive",
    "logs",
    "legacy",
    "reports",
    "snapshots",
    "tmp",
    "venv",
}


def _git_lines(args: list[str]) -> list[str]:
    try:
        output = subprocess.check_output(args, text=True)
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _is_active(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_PARTS:
        return False
    rel = path.as_posix()
    return any(rel == root or rel.startswith(f"{root}/") for root in ACTIVE_ROOTS)


def candidate_files() -> list[Path]:
    tracked = _git_lines(["git", "ls-files", "*.py"])
    untracked = _git_lines(["git", "ls-files", "--others", "--exclude-standard", "*.py"])
    paths = {Path(rel) for rel in tracked + untracked}
    return sorted(path for path in paths if path.exists() and _is_active(path))


def main() -> int:
    failures: list[str] = []
    checked = 0
    for path in candidate_files():
        checked += 1
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError as exc:
            failures.append(f"{path}:{exc.lineno}: {exc.msg}")

    if failures:
        print("Python syntax failures in active source files:")
        print("\n".join(failures[:200]))
        if len(failures) > 200:
            print(f"... and {len(failures) - 200} more")
        return 1

    print(f"Parsed {checked} active Python files successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
