#!/usr/bin/env python3
"""Run one fixed-export Northstar V3 experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.kaggle.plan_2026_05_18_production.experiments import RUNNERS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exp_id", choices=sorted(RUNNERS))
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--feature-policy", choices=["safe", "full"], default=None)
    args = parser.parse_args()
    if args.feature_policy is None:
        args.feature_policy = "safe" if args.exp_id in {"EXP-20", "EXP-21", "EXP-22", "EXP-23"} else "full"
    RUNNERS[args.exp_id](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
