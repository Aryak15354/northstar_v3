#!/usr/bin/env python3
"""Compute Screener-backed valuation scores for the active universe."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion import IngestionRegistry
from src.valuation.valuation_feature_block import ValuationFeatureBlock


def load_config() -> dict:
    config: dict = {}
    for path in [
        PROJECT_ROOT / "config" / "ingestion_config.yaml",
        PROJECT_ROOT / "config" / "factors_config.yaml",
        PROJECT_ROOT / "config" / "valuation_config.yaml",
    ]:
        if not path.exists():
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            config.update(payload)
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute valuation score cache for the current universe.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--max-tickers", type=int, default=0)
    parser.add_argument("--output-json", default="", help="Optional path for a summary JSON report.")
    return parser.parse_args()


def resolve_date(raw: str) -> pd.Timestamp:
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    value = pd.to_datetime(raw, errors="coerce")
    if pd.isna(value):
        raise ValueError(f"invalid --date: {raw}")
    return pd.Timestamp(value).normalize()


def load_price_lookup(registry: IngestionRegistry, tickers: list[str], as_of_date: pd.Timestamp) -> dict[str, float]:
    prices = registry.market.load(
        as_of_date=as_of_date.to_pydatetime(),
        tickers=tickers,
        start_date=(as_of_date - pd.Timedelta(days=15)).to_pydatetime(),
        fields=["close"],
    )
    if prices is None or prices.empty:
        return {}
    if isinstance(prices.index, pd.MultiIndex):
        frame = prices.reset_index()
        date_col = "Date" if "Date" in frame.columns else "date"
        ticker_col = "Ticker" if "Ticker" in frame.columns else "ticker"
        close_col = "close" if "close" in frame.columns else ("Close" if "Close" in frame.columns else None)
        if close_col is None:
            return {}
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.sort_values([ticker_col, date_col], kind="mergesort")
        latest = frame.dropna(subset=[ticker_col, close_col]).groupby(ticker_col, sort=False)[close_col].last()
        return {str(k): float(v) for k, v in latest.items() if pd.notna(v)}
    if "close" in prices.columns:
        latest = prices["close"].dropna()
        return {str(k): float(v) for k, v in latest.items()}
    return {}


def main() -> int:
    args = parse_args()
    as_of_date = resolve_date(args.date)
    config = load_config()
    registry = IngestionRegistry(config)
    valuation_block = ValuationFeatureBlock(config)

    tickers = [str(t) for t in registry.market.get_universe_as_of(as_of_date.to_pydatetime())]
    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: int(args.max_tickers)]
    prices = load_price_lookup(registry, tickers, as_of_date)
    scores = valuation_block.compute(
        as_of_date=as_of_date.to_pydatetime(),
        tickers=tickers,
        market_prices=prices,
        use_cache=False,
    )
    raw_cols = [c for c in valuation_block.FEATURE_NAMES if c in scores.columns]
    coverage = {c: float(pd.to_numeric(scores[c], errors="coerce").notna().mean()) for c in raw_cols}
    summary = {
        "as_of_date": str(as_of_date.date()),
        "tickers": len(tickers),
        "rows_written": int(len(scores)),
        "cache_path": str(valuation_block.CACHE_PATH),
        "feature_coverage": coverage,
        "computed_at": datetime.now().isoformat(),
    }
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
