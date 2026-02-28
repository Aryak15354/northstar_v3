#!/usr/bin/env python3
"""Audit ledger underlying attribution quality."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = PROJECT_ROOT / "data/options/trade_ledger.parquet"
REPORT_PATH = PROJECT_ROOT / "data/options/live/underlying_attribution_audit.json"
GENERIC_UNDERLYING_TOKENS = {"NSE", "NSE_EQ", "NSE_FO", "NSE_INDEX", "NFO", "BSE", "BSE_EQ", "BSE_FO", "UNKNOWN"}


def run_audit(limit_examples: int = 25) -> dict:
    report = {
        "timestamp": datetime.now().isoformat(),
        "ledger_path": str(LEDGER_PATH),
        "exists": LEDGER_PATH.exists(),
        "total_rows": 0,
        "generic_underlying_rows": 0,
        "generic_underlying_ratio": 0.0,
        "by_underlying": {},
        "examples": [],
    }
    if not LEDGER_PATH.exists():
        return report

    df = pd.read_parquet(LEDGER_PATH)
    if df.empty:
        return report

    underlying_series = df.get("underlying", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
    report["total_rows"] = int(len(df))
    counts = underlying_series.value_counts(dropna=False)
    report["by_underlying"] = {str(k): int(v) for k, v in counts.items()}

    mask_generic = underlying_series.isin(GENERIC_UNDERLYING_TOKENS)
    generic_df = df.loc[mask_generic]
    report["generic_underlying_rows"] = int(len(generic_df))
    report["generic_underlying_ratio"] = (
        float(len(generic_df)) / float(len(df)) if len(df) > 0 else 0.0
    )
    if not generic_df.empty:
        cols = [c for c in ["trade_id", "timestamp", "action", "underlying", "strategy_type"] if c in generic_df.columns]
        report["examples"] = generic_df[cols].head(max(1, int(limit_examples))).to_dict("records")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit underlying attribution quality in trade ledger")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if generic underlying rows are present")
    parser.add_argument("--max-examples", type=int, default=25)
    args = parser.parse_args()

    report = run_audit(limit_examples=max(1, int(args.max_examples)))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))

    if args.strict and int(report.get("generic_underlying_rows", 0)) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
