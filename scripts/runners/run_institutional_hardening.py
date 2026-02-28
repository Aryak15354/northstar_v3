#!/usr/bin/env python3
"""
Run institutional hardening checks and persist governance artifacts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.validation.institutional_hardening import run_institutional_hardening


def main() -> int:
    result = run_institutional_hardening(PROJECT_ROOT)
    summary = result.to_summary()
    print("✅ Institutional hardening checks completed")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

