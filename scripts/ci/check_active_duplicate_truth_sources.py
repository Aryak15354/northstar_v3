#!/usr/bin/env python3
"""Reject legacy data-path truth sources in active runtime files.

Historical processed/market datasets may remain on disk and may be consumed by
canonical builders. Active runtime code should read through canonical contracts
or dedicated accessors instead of hard-coded legacy parquet paths.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACTIVE_FILES = (
    "scripts/ns.py",
    "scripts/run_complete_v3_system.py",
    "scripts/northstar_v3_unified.py",
    "scripts/system_status_report.py",
    "scripts/eod_rebalance_with_pnl.py",
    "scripts/force_market_update.py",
    "src/ingestion/market_loader.py",
    "src/data/price_access.py",
    "src/dashboard/v3_data_hub.py",
    "src/backtesting/backtest_engine.py",
    "src/live/daily_shadow_trader.py",
    "src/orchestrator/master_orchestrator.py",
)

LEGACY_TRUTH_PATHS = (
    "data/processed/prices.parquet",
    "data/market/daily_prices.parquet",
    "data/market/financials.parquet",
    "data/processed/fundamentals.parquet",
    "data/processed/macro_factors.parquet",
    "data/macro/comprehensive_rbi_data.parquet",
    "data/processed/news/news_dataset.parquet",
    "data/processed/sentiment/ticker_sentiment_daily.parquet",
    "data/processed/sentiment/market_sentiment_daily.parquet",
    "data/processed/alternative/bulk_deals_nse_all.parquet",
    "data/processed/alternative/bulk_deals_all.parquet",
    "data/processed/alternative/announcements_all.parquet",
    "data/processed/alternative/announcements_all.csv",
)


def main() -> int:
    findings: list[dict[str, object]] = []
    for rel in ACTIVE_FILES:
        path = ROOT / rel
        if not path.exists():
            findings.append({"file": rel, "path": "missing_active_file"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for legacy_path in LEGACY_TRUTH_PATHS:
            if legacy_path in text:
                findings.append({"file": rel, "legacy_path": legacy_path})

    print(json.dumps({"check": "active_duplicate_truth_sources", "count": len(findings), "findings": findings[:200]}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
