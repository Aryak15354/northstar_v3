#!/usr/bin/env python3
"""Refresh canonical runtime accounting artifacts for the live system."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pnl.runtime_accounting_sync import refresh_runtime_accounting


def main() -> int:
    report = refresh_runtime_accounting()
    print(json.dumps(report.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
