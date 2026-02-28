#!/usr/bin/env python3
"""Run liquidity risk assessment."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script (python scripts/...).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk.liquidity_kill_switch import LiquidityRiskAssessor


def main() -> None:
    assessor = LiquidityRiskAssessor()
    assessor.run()


if __name__ == "__main__":
    main()
