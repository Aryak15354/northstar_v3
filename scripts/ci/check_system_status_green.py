#!/usr/bin/env python3
"""Fail CI when the operator status report is not fully green."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "scripts/system_status_report.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        return proc.returncode
    if "Overall: PASS" not in proc.stdout:
        return 1
    if "WARN=" not in proc.stdout or "FAIL=" not in proc.stdout:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
