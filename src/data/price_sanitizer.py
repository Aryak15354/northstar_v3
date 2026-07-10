"""Price-scale sanitizer — back-adjusts corrupted scale discontinuities.

A handful of tickers in the raw yfinance CSVs carry mixed adjusted/unadjusted
history (e.g. TCS.NS: ₹116 on 2024-12-31 → ₹3,974 on 2025-01-01, a 34×
overnight "jump" on a market holiday). This is the classic artifact of
fetching some slices with auto_adjust=True and others without. Left alone it
corrupts every consumer: momentum signals, backtests, NAV marks (it produced
a fake +128% strategy return before this fix).

The repair is the standard split-adjustment operation: detect any single-day
close ratio outside [0.4, 2.5] and multiply ALL earlier rows by that factor,
so the series is continuous at the most-recent (trusted) scale. Genuine daily
moves never approach ±150%; genuine splits/bonuses in adjusted data don't
appear as jumps at all. Applied at the raw→processed merge so every consumer
downstream sees clean data; the paper-fund engine keeps its own pass as a
safety net.

Used by: src/processing/price_processor.py, src/portfolio/paper_portfolio_engine.py
CI gate: scripts/ci/check_price_continuity.py enforces the invariant.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("data.price_sanitizer")

# Single-day close-ratio bounds beyond which we treat a move as a SCALE ERROR
# (mixed adjusted/unadjusted history) and back-adjust prior rows.
#
# The root cause of scale errors — appending fetch slices on different
# dividend/split adjustment bases — is now prevented at the source
# (src/ingestion/price_fetcher.py re-downloads the full window on one basis), so
# this is a legacy safety net. Its dominant remaining risk is CORRUPTING a
# genuinely-crashed stock: rescaling all prior history by the jump factor would
# destroy the true pre-crash prices. NSE circuit limits cap most single-day
# equity moves near ±20%, and even circuit-free crashes rarely exceed ~65%, so
# the DOWNSIDE bound is set to 0.2 (an >80% single-day fall is almost certainly a
# data/scale artifact, not real trading), protecting genuine crashes. Every
# rescale is logged loudly for review.
UPPER_RATIO = 2.5
LOWER_RATIO = 0.2

_PRICE_COLS = ("Open", "High", "Low", "Close")


def sanitize_ticker_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Back-adjust one ticker's Date-sorted OHLC frame in place.

    Returns (frame, n_discontinuities_fixed). Volume is left untouched — the
    corruption is a price-scale artifact, share counts are unaffected.
    """
    if df.empty or "Close" not in df.columns or len(df) < 3:
        return df, 0
    work = df.sort_values("Date").reset_index(drop=True)
    close = pd.to_numeric(work["Close"], errors="coerce")
    ratio = close / close.shift(1)
    jumps = ratio[(ratio > UPPER_RATIO) | (ratio < LOWER_RATIO)].dropna()
    if jumps.empty:
        return work, 0
    ticker = str(work["ticker"].iloc[0]) if "ticker" in work.columns else "?"
    for idx, f in jumps.items():
        dt = work["Date"].iloc[idx] if "Date" in work.columns else idx
        logger.warning(
            "price scale discontinuity back-adjusted: ticker=%s date=%s ratio=%.3f "
            "(rescaling %d prior rows by %.4f) — REVIEW if this was a genuine move",
            ticker, dt, float(f), idx, float(f),
        )
    factor = pd.Series(1.0, index=work.index)
    for idx, f in jumps.items():
        factor.iloc[:idx] *= float(f)
    for col in _PRICE_COLS:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce") * factor
    return work, len(jumps)


def sanitize_close_panel(close: pd.DataFrame) -> pd.DataFrame:
    """Back-adjust a Date×ticker close-price pivot (paper-engine safety net)."""
    adjusted = close.copy()
    for col in adjusted.columns:
        s = adjusted[col].dropna()
        if len(s) < 3:
            continue
        r = s / s.shift(1)
        jumps = r[(r > UPPER_RATIO) | (r < LOWER_RATIO)].dropna()
        if jumps.empty:
            continue
        factor = pd.Series(1.0, index=adjusted.index)
        for dt, f in jumps.items():
            factor.loc[adjusted.index < dt] *= float(f)
        adjusted[col] = adjusted[col] * factor
    return adjusted
