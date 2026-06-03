#!/usr/bin/env python3
"""Reject machine-local absolute paths in public source/config files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg",
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "archive",
    "audit",
    "backups",
    "data",
    "docs/archive",
    "logs",
    "legacy",
    "northstar_ratio_campaign_fresh",
    "reports",
    "snapshots",
    "tmp",
    "venv",
}

ALLOWLIST_RE = re.compile(
    r"("
    r"docs/PRODUCTION_GRADE_HEALTH_AUDIT_2026-05-18\.md"
    r"|docs/PUBLIC_READINESS_AUDIT\.md"
    r"|docs/kaggle/"
    r"|docs/research/"
    r"|docs/system/"
    r"|scripts/kaggle/"
    r"|configs/plan_2026_04_05/catalog_v1\.yaml"
    r"|tests/intelligence_observer/test_results_\d+_\d+\.json"
    r")"
)

LOCAL_PATH_RE = re.compile(r"(/" + r"Users/[^'\"\s)]+|/" + r"Volumes/[^'\"\s)]+)")


def _git_lines(args: list[str]) -> list[str]:
    try:
        output = subprocess.check_output(args, text=True)
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _should_scan(path: Path) -> bool:
    rel = path.as_posix()
    if ALLOWLIST_RE.search(rel):
        return False
    if set(path.parts) & SKIP_PARTS:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {".gitignore", "README.md"}


def candidate_files() -> list[Path]:
    tracked = _git_lines(["git", "ls-files"])
    untracked = _git_lines(["git", "ls-files", "--others", "--exclude-standard"])
    paths = {Path(rel) for rel in tracked + untracked}
    return sorted(path for path in paths if path.exists() and _should_scan(path))


def main() -> int:
    findings: list[str] = []
    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if LOCAL_PATH_RE.search(line):
                findings.append(f"{path}:{line_no}: {line.strip()[:220]}")

    if findings:
        print("Machine-local absolute paths found:")
        print("\n".join(findings[:200]))
        if len(findings) > 200:
            print(f"... and {len(findings) - 200} more")
        return 1

    print("No machine-local absolute paths found in active public files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
