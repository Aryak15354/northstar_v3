#!/usr/bin/env python3
"""Compatibility wrapper for launching the canonical Streamlit dashboard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CANONICAL_LAUNCHER = PROJECT_ROOT / "launch_dashboard.sh"


def main() -> int:
    if not CANONICAL_LAUNCHER.exists():
        print(f"ERROR: Missing launcher: {CANONICAL_LAUNCHER}")
        return 1

    cmd = ["bash", str(CANONICAL_LAUNCHER), *sys.argv[1:]]
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
