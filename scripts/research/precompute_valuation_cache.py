#!/usr/bin/env python3
"""Precompute the historical valuation cache locally, once.

Why: computing valuations inside every panel build killed three Kaggle runs
(2026-07-16/17) — ~116ms/ticker-date of DCF+moat+quality makes any in-build
recompute blow the 12h session cap. Valuation is point-in-time (no rolling
lookback), so it is DATA, not a build step: compute the weekly grid here, ship
`valuation_scores.parquet` + a provenance marker in the raw bundle, and the
Kaggle build becomes cache lookups (the block's 7-day prior-date fallback
serves every weekly-tail request from this grid).

Output:
  data/processed/valuation_scores.parquet          (date, ticker, val_* raw)
  data/processed/valuation_scores.provenance.json  (post_n1_fix marker)

Resume-safe: per-worker shard parquets checkpoint every N dates; rerunning
skips dates already in shards.
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--runtime-root", type=Path, default=Path(__file__).resolve().parents[2],
                 help="dir whose data/ + config/ the valuation engines read (cwd is set here)")
_ap.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2],
                 help="dir containing src/ (sys.path)")
_ap.add_argument("--out-dir", type=Path, default=None,
                 help="where cache+marker+shards are written (default <runtime-root>/data/processed)")
_ap.add_argument("--workers", type=int, default=6)
_ap.add_argument("--start", type=str, default="2017-10-01")
_A = _ap.parse_args()

RUNTIME_ROOT = _A.runtime_root.resolve()
os.chdir(RUNTIME_ROOT)
sys.path.insert(0, str(_A.code_root.resolve()))

import pandas as pd  # noqa: E402

PRICES = RUNTIME_ROOT / "data/canonical/prices/equity_prices_daily.parquet"
_OUTBASE = (_A.out_dir.resolve() if _A.out_dir else RUNTIME_ROOT / "data/processed")
OUT = _OUTBASE / "valuation_scores.parquet"
MARKER = _OUTBASE / "valuation_scores.provenance.json"
SHARD_DIR = _OUTBASE / "valuation_shards"
START = pd.Timestamp(_A.start)   # covers chunk-1's 420d warmup from 2019-01
WORKERS = _A.workers
CHECKPOINT_EVERY = 20


def weekly_anchor_dates() -> list[pd.Timestamp]:
    dates = pd.read_parquet(PRICES, columns=["date"])["date"].drop_duplicates().sort_values()
    dates = dates[dates >= START]
    grid = dates.groupby(dates.dt.to_period("W-FRI")).max()
    return [pd.Timestamp(d) for d in grid.tolist()]


def _worker(shard_id: int, dates: list[str]) -> str:
    import warnings
    warnings.filterwarnings("ignore")
    from src.valuation.valuation_feature_block import ValuationFeatureBlock

    shard_path = SHARD_DIR / f"shard_{shard_id:02d}.parquet"
    done: set[str] = set()
    frames: list[pd.DataFrame] = []
    if shard_path.exists():
        prev = pd.read_parquet(shard_path)
        frames.append(prev)
        done = set(pd.to_datetime(prev["date"]).dt.strftime("%Y-%m-%d"))

    prices = pd.read_parquet(PRICES, columns=["date", "ticker", "close"])
    blk = ValuationFeatureBlock({})
    feature_names = list(blk.FEATURE_NAMES)

    todo = [d for d in dates if d not in done]
    t0 = time.time()
    since_ckpt = 0
    for i, ds in enumerate(todo):
        d = pd.Timestamp(ds)
        day = prices[prices["date"] == d]
        tickers = sorted(day["ticker"].astype(str).unique().tolist())
        lookup = dict(zip(day["ticker"].astype(str), day["close"]))
        out = blk.compute(as_of_date=d.to_pydatetime(), tickers=tickers,
                          market_prices=lookup, use_cache=False)
        keep = [c for c in feature_names if c in out.columns]
        rows = out[keep].copy()
        rows["date"] = d.normalize()
        rows["ticker"] = rows.index.astype(str)
        frames.append(rows.reset_index(drop=True))
        since_ckpt += 1
        if since_ckpt >= CHECKPOINT_EVERY or i == len(todo) - 1:
            pd.concat(frames, ignore_index=True).to_parquet(shard_path, index=False)
            since_ckpt = 0
        rate = (i + 1) / max(time.time() - t0, 1e-9)
        eta_min = (len(todo) - i - 1) / max(rate, 1e-9) / 60
        print(f"[shard {shard_id}] {i+1}/{len(todo)} dates ({ds}, {len(tickers)} tk) "
              f"rate={rate*60:.1f} dates/min eta={eta_min:.0f}m", flush=True)
    return str(shard_path)


def main() -> None:
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    dates = weekly_anchor_dates()
    print(f"{len(dates)} weekly anchor dates: {dates[0].date()} -> {dates[-1].date()}", flush=True)

    # round-robin so every shard mixes cheap/expensive eras evenly
    shards: list[list[str]] = [[] for _ in range(WORKERS)]
    for i, d in enumerate(dates):
        shards[i % WORKERS].append(d.strftime("%Y-%m-%d"))

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_worker, i, s): i for i, s in enumerate(shards) if s}
        for f in as_completed(futs):
            print(f"[main] shard {futs[f]} finished: {f.result()}", flush=True)

    parts = [pd.read_parquet(p) for p in sorted(SHARD_DIR.glob("shard_*.parquet"))]
    cache = pd.concat(parts, ignore_index=True)
    cache["date"] = pd.to_datetime(cache["date"]).dt.normalize()
    cache["ticker"] = cache["ticker"].astype(str)
    cache = cache.drop_duplicates(subset=["date", "ticker"], keep="last").sort_values(["date", "ticker"])
    cache.to_parquet(OUT, index=False)

    val_cols = [c for c in cache.columns if c.startswith("val_")]
    per_ticker_var = cache.groupby("ticker")[val_cols[0]].nunique().median() if val_cols else 0
    marker = {
        "post_n1_fix": True,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "computed_by": "scripts/research/precompute_valuation_cache.py",
        "n_rows": int(len(cache)),
        "n_dates": int(cache["date"].nunique()),
        "n_tickers": int(cache["ticker"].nunique()),
        "date_min": str(cache["date"].min().date()),
        "date_max": str(cache["date"].max().date()),
        "median_unique_values_per_ticker_first_val_col": float(per_ticker_var),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(marker, indent=1))
    print(f"DONE in {(time.time()-t0)/60:.0f}m: {len(cache):,} rows, "
          f"{marker['n_dates']} dates, {marker['n_tickers']} tickers -> {OUT}", flush=True)
    print(json.dumps(marker, indent=1), flush=True)


if __name__ == "__main__":
    main()
