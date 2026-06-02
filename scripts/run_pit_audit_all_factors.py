#!/usr/bin/env python3
"""Run PIT leakage audits for enabled scalar / primary factor surfaces."""

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
    parser = argparse.ArgumentParser(description="Run PIT leakage audits for enabled factors")
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2024-06-30")
    parser.add_argument("--config", type=str, default="config/factors_config.yaml")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def factor_lag_days(cfg: dict, factor_name: str) -> int:
    factor_cfg = (cfg.get("factors", {}).get(factor_name, {}) or {})
    for key in ('reporting_lag_days', 'announcement_safety_lag_days', 'safety_lag_days'):
        value = factor_cfg.get(key)
        if value is not None:
            return int(value)
    return 1


def build_forward_returns(registry: IngestionRegistry, tickers: list[str], start_date: datetime, end_date: datetime) -> pd.DataFrame:
    prices = registry.market.load(
        as_of_date=end_date,
        tickers=tickers,
        start_date=start_date,
        fields=["close"],
    )
    frame = prices.reset_index()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.sort_values(["Ticker", "Date"], kind="mergesort")
    frame["fwd_5d_return"] = frame.groupby("Ticker")["close"].shift(-5) / frame["close"] - 1.0
    return frame.set_index(["Date", "Ticker"])[["fwd_5d_return"]]


def main() -> int:
    args = parse_args()
    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")
    cfg = load_config(args.config)

    registry = IngestionRegistry(cfg)
    factor_registry = FactorRegistry(registry, cfg)
    tickers = registry.market.get_universe_as_of(end_date)[:50]
    test_dates = [d.to_pydatetime() for d in pd.date_range(start_date, end_date, freq="W-FRI")]
    forward_returns = build_forward_returns(registry, tickers, start_date, end_date)

    failures = 0
    print("PIT AUDIT RESULTS")
    print("=" * 60)
    for name, factor in factor_registry._factors.items():
        lag_days = factor_lag_days(cfg, name)
        report = factor.run_pit_leakage_test(tickers, test_dates, forward_returns, correct_lag_days=lag_days)
        leak = bool(report["leakage_detected"])
        failures += int(leak)
        print(
            f"{name}: lag_ic={report['lag_ic']:.4f} no_lag_ic={report['no_lag_ic']:.4f} "
            f"ratio={report['ratio']:.2f} leak={leak}"
        )
    print("=" * 60)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
