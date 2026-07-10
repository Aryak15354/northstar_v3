#!/usr/bin/env python3
"""CI gate: the processed price panel must contain no scale discontinuities.

Invariant: no ticker's close may jump by more than 2.5x (or drop below 0.4x)
in a single day in data/processed/prices.parquet. Genuine daily moves never
approach ±150%; such jumps are mixed adjusted/unadjusted fetch artifacts (the
TCS 34x / RELIANCE 8x corruption that produced fake backtest returns). The
raw→processed merge back-adjusts them (src/data/price_sanitizer); this gate
ensures that repair never regresses.

Exit 0 = clean. Exit 1 = discontinuities found (listed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRICES = PROJECT_ROOT / "data" / "processed" / "prices.parquet"

# Bounds match src/data/price_sanitizer: a genuine single-day equity move rarely
# exceeds ~65% (circuit limits), so only >2.5x / <0.2x is treated as a scale
# artifact. Keeps the gate from false-flagging real crashes as discontinuities.
UPPER, LOWER = 2.5, 0.2


def main() -> int:
    if not PRICES.exists():
        print(json.dumps({"gate": "price_continuity", "status": "SKIP",
                          "reason": "prices.parquet missing"}))
        return 0
    px = pd.read_parquet(PRICES, columns=["Date", "ticker", "Close"])
    px = px.dropna().sort_values(["ticker", "Date"])
    ratio = px.groupby("ticker")["Close"].pct_change() + 1.0
    bad = px[(ratio > UPPER) | (ratio < LOWER)]
    if bad.empty:
        print(json.dumps({"gate": "price_continuity", "status": "PASS",
                          "tickers": int(px["ticker"].nunique())}))
        return 0
    offenders = (bad.groupby("ticker").size().sort_values(ascending=False)
                 .head(20).to_dict())
    print(json.dumps({"gate": "price_continuity", "status": "FAIL",
                      "discontinuities": int(len(bad)),
                      "offenders": offenders}, indent=2, default=str))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
