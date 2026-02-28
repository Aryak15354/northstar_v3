#!/usr/bin/env python3
"""
📊 MARKET REGIME ENGINE (REAL DATA)

Builds a dense daily market-regime time series from processed price history.

Inputs:
  - data/processed/prices.parquet  (columns must include: Date, ticker, Close)

Output:
  - data/processed/market_regime.parquet
    Columns:
      Date, breadth, participation, volatility, correlation, risk_on_score, market_regime

Notes:
  - No synthetic data. Everything is derived from real price history.
  - Designed to be fast enough to run on each system refresh.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PRICES = Path("data/processed/prices.parquet")
OUT = Path("data/processed/market_regime.parquet")


def _infer_regime(risk_on: float, vol_daily: float, corr: float) -> str:
    """Classify regime into a small, interpretable set used across the dashboard."""
    if risk_on is None or np.isnan(risk_on):
        return "Neutral"

    # Convert daily volatility to a simple "panic score" comparable to legacy thresholds.
    panic = float(vol_daily) * 100.0 if vol_daily is not None and not np.isnan(vol_daily) else 0.0

    if risk_on >= 0.62 and panic <= 2.0:
        return "Bull"
    if panic >= 3.0:
        return "Panic"
    if risk_on >= 0.52 and corr >= 0.55:
        return "Fragile"
    if risk_on >= 0.52:
        return "Neutral"
    return "Bear"


def build_market_regime(
    prices: pd.DataFrame,
    *,
    ema_span: int = 200,
    participation_window: int = 60,
    corr_window: int = 30,
    min_coverage: int = 300,
) -> pd.DataFrame:
    df = prices.copy()

    # Normalize schema
    if "Date" not in df.columns or "ticker" not in df.columns or "Close" not in df.columns:
        raise ValueError("prices.parquet must contain columns: Date, ticker, Close")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "ticker", "Close"])
    df["ticker"] = df["ticker"].astype(str).str.strip()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])

    df = df.sort_values(["ticker", "Date"]).reset_index(drop=True)

    # 1) Breadth: fraction of names above their EMA(200)
    # Compute EMA per ticker (fast + avoids needing to read the huge technicals artifact).
    df["ema200"] = df.groupby("ticker", sort=False)["Close"].transform(
        lambda s: s.ewm(span=ema_span, adjust=False).mean()
    )
    df["above_ema200"] = df["Close"] > df["ema200"]
    breadth = df.groupby("Date")["above_ema200"].mean()

    # 2) Participation: fraction of names within ~3% of their rolling window highs
    df["roll_max"] = df.groupby("ticker", sort=False)["Close"].transform(
        lambda s: s.rolling(participation_window, min_periods=max(20, participation_window // 3)).max()
    )
    df["near_high"] = df["Close"] >= (df["roll_max"] * 0.97)
    participation = df.groupby("Date")["near_high"].mean()

    # 3) Volatility + Correlation: computed from return matrix (Date x ticker)
    df["ret"] = df.groupby("ticker", sort=False)["Close"].pct_change()
    ret_wide = df.pivot(index="Date", columns="ticker", values="ret").sort_index()

    # Coverage for quality gating
    coverage = ret_wide.notna().sum(axis=1)

    # Market return = equal-weight mean of available returns
    market_ret = ret_wide.mean(axis=1, skipna=True)

    dates = ret_wide.index.to_list()
    vol_series = pd.Series(index=ret_wide.index, dtype="float64")
    corr_series = pd.Series(index=ret_wide.index, dtype="float64")

    # Rolling window calculations (fast enough for ~5y x 500 names)
    for i in range(len(dates)):
        if i < corr_window:
            continue
        win = slice(i - corr_window + 1, i + 1)
        wret = ret_wide.iloc[win]
        wmkt = market_ret.iloc[win]

        # Volatility: daily std of market return in the window
        vol = float(pd.to_numeric(wmkt, errors="coerce").std())
        if np.isnan(vol):
            continue

        # Correlation: average corr of constituents vs market return
        try:
            c = wret.corrwith(wmkt)
            corr = float(pd.to_numeric(c, errors="coerce").mean())
        except Exception:
            corr = np.nan

        vol_series.iloc[i] = vol
        corr_series.iloc[i] = corr

    out = pd.DataFrame(
        {
            "breadth": breadth,
            "participation": participation,
            "volatility": vol_series,
            "correlation": corr_series,
            "coverage": coverage,
        }
    ).sort_index()

    # Filter low-coverage dates (avoid regimes computed from too few tickers)
    out = out[out["coverage"] >= min_coverage].copy()

    # Risk-on composite score
    out["risk_on_score"] = (0.4 * out["breadth"] + 0.6 * out["participation"]).clip(0, 1)

    # Regime label
    out["market_regime"] = [
        _infer_regime(float(r), float(v) if pd.notna(v) else np.nan, float(c) if pd.notna(c) else np.nan)
        for r, v, c in zip(out["risk_on_score"].values, out["volatility"].values, out["correlation"].values)
    ]

    out = out.reset_index().rename(columns={"index": "Date"})
    # Keep only the fields the dashboard expects (coverage is useful for debugging but not required).
    out = out[["Date", "breadth", "participation", "volatility", "correlation", "risk_on_score", "market_regime"]]
    return out


def main() -> int:
    print("📊 Building Market Regime Engine (real data)...")
    if not PRICES.exists():
        print(f"❌ Missing input: {PRICES}")
        return 1

    try:
        prices = pd.read_parquet(PRICES, columns=["Date", "ticker", "Close"])
    except Exception as e:
        print(f"❌ Could not read {PRICES}: {e}")
        return 1

    try:
        out = build_market_regime(prices)
    except Exception as e:
        print(f"❌ Market regime build failed: {e}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    try:
        dmin = pd.to_datetime(out["Date"], errors="coerce").min()
        dmax = pd.to_datetime(out["Date"], errors="coerce").max()
        print(f"✅ Saved {OUT} ({len(out)} rows, {dmin.date()} → {dmax.date()})")
    except Exception:
        print(f"✅ Saved {OUT} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

