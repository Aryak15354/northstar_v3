#!/usr/bin/env python3
"""Refresh forex and commodities raw history files from yfinance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.cross_asset_data import (  # noqa: E402
    discover_symbols,
    update_symbol_history,
    write_cross_asset_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update cross-asset raw datasets.")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=PROJECT_ROOT / "data/raw",
        help="Root containing the forex and commodities directories.",
    )
    parser.add_argument(
        "--asset-class",
        action="append",
        choices=["commodities", "forex", "indices", "rates"],
        dest="asset_classes",
        help="Limit refresh to a specific asset class. Repeatable.",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Specific symbol(s) to refresh. Defaults to every CSV already present in the chosen asset-class directories.",
    )
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument(
        "--panel-path",
        type=Path,
        default=PROJECT_ROOT / "data/canonical/macro/cross_asset_prices_daily.parquet",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT / "data/raw/shared/market_data/cross_asset_manifest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_root = args.raw_root.expanduser().resolve()
    asset_classes = args.asset_classes or ["commodities", "forex", "indices", "rates"]
    discovered = discover_symbols(raw_root, asset_classes)
    explicit_symbols = {str(sym).strip() for sym in args.symbol if str(sym).strip()}

    updates = []
    for asset_class in asset_classes:
        symbols = discovered.get(asset_class, [])
        if explicit_symbols:
            symbols = [sym for sym in symbols if sym in explicit_symbols]
        for symbol in symbols:
            path = raw_root / asset_class / f"{symbol}.csv"
            result = update_symbol_history(
                symbol=symbol,
                path=path,
                start_date=args.start_date,
                end_date=args.end_date,
                timeout_seconds=args.timeout_seconds,
            )
            result["asset_class"] = asset_class
            updates.append(result)
            print(
                f"[cross-asset] {asset_class}/{symbol} rows={result['rows']} "
                f"date_max={result['date_max']} downloaded_rows={result['downloaded_rows']}"
            )

    manifest = write_cross_asset_outputs(
        raw_root=raw_root,
        panel_path=args.panel_path.expanduser().resolve(),
        manifest_path=args.manifest_path.expanduser().resolve(),
    )
    manifest["updates"] = updates
    args.manifest_path.expanduser().resolve().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    latest_panel = pd.read_parquet(args.panel_path.expanduser().resolve(), columns=["date", "symbol", "asset_class"])
    print(
        f"[cross-asset] panel rows={len(latest_panel)} "
        f"symbols={latest_panel['symbol'].astype(str).nunique()} "
        f"date_max={pd.to_datetime(latest_panel['date'], errors='coerce').max()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
