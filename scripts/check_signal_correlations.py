#!/usr/bin/env python3
"""Check pairwise Spearman correlations across canonical base-factor z-scores."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors import FactorRegistry
from src.ingestion import IngestionRegistry


def parse_args():
    parser = argparse.ArgumentParser(description="Check factor correlation budget")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--config", type=str, default="config/factors_config.yaml")
    parser.add_argument("--limit", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with open(args.config, "r") as f:
        cfg = yaml.safe_load(f) or {}

    as_of_date = datetime.strptime(args.date, "%Y-%m-%d")
    registry = IngestionRegistry(cfg)
    factor_registry = FactorRegistry(registry, cfg)
    tickers = registry.market.get_universe_as_of(as_of_date)[: max(10, int(args.limit))]
    scores = factor_registry.compute_all(as_of_date, tickers, use_cache=True)
    zcols = [c for c in scores.columns if c.endswith("_zscore")]
    corr = scores[zcols].corr(method="spearman")

    warnings = 0
    failures = 0
    print("SIGNAL CORRELATION CHECK")
    print("=" * 60)
    for i, left in enumerate(zcols):
        for right in zcols[i + 1 :]:
            val = float(corr.loc[left, right]) if pd.notna(corr.loc[left, right]) else float("nan")
            if pd.isna(val):
                continue
            abs_val = abs(val)
            if abs_val > 0.80:
                failures += 1
                status = "FAIL"
            elif abs_val > 0.60:
                warnings += 1
                status = "WARN"
            else:
                status = "OK"
            print(f"{status:4} {left} vs {right}: rho={val:.3f}")
    print("=" * 60)
    print(f"Warnings: {warnings}  Failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
