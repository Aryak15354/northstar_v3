#!/usr/bin/env python3
"""Run 3 EXP-15: Capital Goods sector model without coal proxy contamination."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kaggle.plan_2026_05_18_production.experiments import RUNNERS

EXP_ID = "EXP-15"
DESCRIPTION = "Capital Goods sector model with coal_4w_return excluded and metal/order-backlog signals tested."
RUN3_FIXES = [
    "removes coal_4w_return from the sector feature pool",
    "adds nifty_metal_4w_return if available in the dataset",
    "lets the IC screen validate steel/copper/order-backlog signals",
    "uses sector-appropriate row floor and Run 3 aggregate gates",
]


def _default_data_dir() -> str | None:
    path = Path("/kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-fixed")
    return str(path) if path.exists() else None


def _default_output_dir() -> str:
    path = Path("/kaggle/working/northstar_results_run3_exp15")
    return str(path) if Path("/kaggle/working").exists() else str(ROOT / "tmp" / "kaggle_results" / "run3_exp15")


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--data-dir", default=_default_data_dir())
    parser.add_argument("--output-dir", default=_default_output_dir())
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--feature-policy", choices=["safe", "full"], default="full")
    args = parser.parse_args()
    print(f"\nRunning {EXP_ID}: {DESCRIPTION}")
    for item in RUN3_FIXES:
        print(f"  - {item}")
    RUNNERS[EXP_ID](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
