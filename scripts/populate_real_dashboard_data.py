#!/usr/bin/env python3
"""Compatibility wrapper to populate dashboard data through the canonical V3 runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_complete_v3_system.py"),
        "--data-only",
        "--proof-level",
        "none",
    ]
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
