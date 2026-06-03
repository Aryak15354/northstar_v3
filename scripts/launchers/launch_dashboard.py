#!/usr/bin/env python3
"""
🎯 NORTHSTAR V3 DASHBOARD LAUNCHER (COMPAT WRAPPER)

This script exists for backward compatibility with older docs that referenced
`python scripts/launchers/launch_dashboard.py`.

It delegates to the repo-root `launch_dashboard.py`, which is now the single
Python compatibility wrapper around the canonical `launch_dashboard.sh`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    launcher = repo_root / "launch_dashboard.py"
    if not launcher.exists():
        print(f"❌ Missing launcher: {launcher}")
        return 1

    cmd = [sys.executable, str(launcher), *sys.argv[1:]]
    return subprocess.call(cmd, cwd=str(repo_root))


if __name__ == "__main__":
    raise SystemExit(main())
