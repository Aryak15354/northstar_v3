#!/usr/bin/env python3
"""Build crisis replay parquet from India regime windows using DuckDB pushdown."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.query_engine import DuckDBQueryEngine
from src.research.regime_map import RegimeWindow, get_regime, list_regimes


def _pick_first(columns: List[str], options: List[str]) -> str:
    avail = {str(c) for c in columns}
    for name in options:
        if name in avail:
            return name
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build crisis replay dataset")
    parser.add_argument("--prices-path", default="data/processed/prices.parquet")
    parser.add_argument("--output-path", default="data/stress/crisis_replay_prices.parquet")
    parser.add_argument("--metadata-path", default="data/stress/crisis_replay_metadata.json")
    parser.add_argument("--regimes", default="")
    parser.add_argument("--categories", default="crisis,stress,event")
    parser.add_argument("--duckdb-memory-mb", type=int, default=768)
    args = parser.parse_args()

    prices_path = Path(args.prices_path)
    if not prices_path.is_absolute():
        prices_path = (PROJECT_ROOT / prices_path).resolve()
    if not prices_path.exists():
        raise FileNotFoundError(f"prices_artifact_missing:{prices_path}")

    output_path = Path(args.output_path)
    if not output_path.is_absolute():
        output_path = (PROJECT_ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_path = Path(args.metadata_path)
    if not metadata_path.is_absolute():
        metadata_path = (PROJECT_ROOT / metadata_path).resolve()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    regime_items: List[RegimeWindow] = []
    if str(args.regimes).strip():
        for name in [x.strip().lower() for x in str(args.regimes).split(",") if x.strip()]:
            r = get_regime(name)
            if r is not None:
                regime_items.append(r)
    else:
        cats = {x.strip().lower() for x in str(args.categories).split(",") if x.strip()}
        for cat in cats:
            regime_items.extend(list_regimes(category=cat))
        dedup = {}
        for r in regime_items:
            dedup[r.name] = r
        regime_items = list(dedup.values())

    if not regime_items:
        raise ValueError("no_regimes_selected")

    query = DuckDBQueryEngine(memory_limit_mb=max(256, int(args.duckdb_memory_mb)), threads=1)
    cols = query.columns(prices_path)
    date_col = _pick_first(cols, ["Date", "date", "timestamp"])
    ticker_col = _pick_first(cols, ["ticker", "symbol"])
    close_col = _pick_first(cols, ["Close", "close"])
    volume_col = _pick_first(cols, ["Volume", "volume"])
    keep = [c for c in [date_col, ticker_col, close_col, volume_col] if c]
    if not keep:
        raise ValueError("prices_schema_missing_required_fields")

    frames: List[pd.DataFrame] = []
    for regime in regime_items:
        chunk = query.read_parquet(
            prices_path,
            columns=keep,
            date_col=date_col if date_col else None,
            start_date=regime.start_date,
            end_date=regime.end_date,
        )
        if chunk.empty:
            continue
        if date_col and "date" not in chunk.columns:
            chunk["date"] = pd.to_datetime(chunk[date_col], errors="coerce")
        if ticker_col and ticker_col != "ticker":
            chunk["ticker"] = chunk[ticker_col].astype(str)
        if close_col and close_col != "close":
            chunk["close"] = pd.to_numeric(chunk[close_col], errors="coerce")
        if volume_col and volume_col != "volume":
            chunk["volume"] = pd.to_numeric(chunk[volume_col], errors="coerce")
        chunk["regime_name"] = regime.name
        chunk["regime_category"] = regime.category
        chunk["regime_start"] = regime.start_date
        chunk["regime_end"] = regime.end_date
        frames.append(chunk)

    if not frames:
        raise RuntimeError("crisis_replay_empty")

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values(["date", "ticker"]).reset_index(drop=True)
    out.to_parquet(output_path, index=False)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prices_path": str(prices_path),
        "output_path": str(output_path),
        "rows": int(len(out)),
        "tickers": int(out["ticker"].astype(str).nunique()) if "ticker" in out.columns else 0,
        "date_start": str(out["date"].min()),
        "date_end": str(out["date"].max()),
        "regimes": [r.name for r in regime_items],
    }
    metadata_path.write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
