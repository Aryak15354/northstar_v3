#!/usr/bin/env python3
"""Reject generated, archived, and local-runtime files from Git tracking."""

from __future__ import annotations

import subprocess


FORBIDDEN_PREFIXES = (
    "analysis_results/",
    "archive/",
    "backups/",
    "catboost_info/",
    "data/",
    "dist/kaggle/",
    "logs/",
    "reports/",
    "snapshots/",
    "tmp/",
)

FORBIDDEN_EXACT = {
    ".DS_Store",
    "nohup.out",
}

FORBIDDEN_SUFFIXES = (
    ".pid",
    ".pyc",
)

ALLOWLIST = {
    "src/data/__init__.py",
    "src/data/loaders.py",
    "src/data/query_engine.py",
}


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files"], text=True)
    return [line.strip() for line in output.splitlines() if line.strip()]


def is_deadweight(path: str) -> bool:
    if path in ALLOWLIST:
        return False
    if path in FORBIDDEN_EXACT:
        return True
    if path.endswith(FORBIDDEN_SUFFIXES):
        return True
    return path.startswith(FORBIDDEN_PREFIXES)


def main() -> int:
    findings = [path for path in tracked_files() if is_deadweight(path)]
    if findings:
        print("Generated/archive/runtime files are tracked:")
        print("\n".join(findings[:200]))
        if len(findings) > 200:
            print(f"... and {len(findings) - 200} more")
        return 1

    print("No generated/archive/runtime deadweight is tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
