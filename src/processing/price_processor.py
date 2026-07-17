import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.price_sanitizer import sanitize_ticker_frame

RAW_PRICE_DIR = "data/raw/prices_daily"
OUTPUT_FILE = "data/processed/prices.parquet"


def drop_non_session_rows(prices: pd.DataFrame,
                          min_session_frac: float = 0.30,
                          date_col: str | None = None,
                          ticker_col: str | None = None) -> tuple[pd.DataFrame, int]:
    """Remove rows stamped on dates that were not real NSE sessions.

    A handful of corrupted mega-cap feeds (HDFCBANK, ICICIBANK, INFY, RELIANCE,
    TCS) fabricate rows on weekends and every NSE holiday — e.g. exactly those 5
    tickers appear on 2023-01-26 (Republic Day) and 2024-12-25 (Christmas). Those
    forward-filled rows manufacture the false year-boundary scale seams and the
    5-ticker phantom weeks that poisoned the alpha export.

    Rule (calendar-free so it adapts as the universe grows): a real session has
    hundreds of tickers reporting; a fabricated holiday date has only the corrupt
    few. Keep weekdays whose ticker count is at least `min_session_frac` of the
    trailing-median session count. Weekends are always dropped.

    Column names are auto-detected (Title-case processed panel or lower-case
    canonical panel) unless given explicitly."""
    df = prices.copy()
    dcol = date_col or ("Date" if "Date" in df.columns else "date")
    tcol = ticker_col or ("ticker" if "ticker" in df.columns else "Ticker")
    df[dcol] = pd.to_datetime(df[dcol])
    weekday = df[dcol].dt.dayofweek < 5
    per_date = df[weekday].groupby(dcol)[tcol].nunique().sort_index()
    if per_date.empty:
        return df[weekday].reset_index(drop=True), int((~weekday).sum())
    trailing_median = per_date.rolling(30, min_periods=5).median().bfill()
    valid_dates = set(per_date.index[per_date >= min_session_frac * trailing_median])
    keep = weekday & df[dcol].isin(valid_dates)
    return df[keep].reset_index(drop=True), int((~keep).sum())


def trim_frozen_runs(prices: pd.DataFrame, min_run: int = 10,
                     delisted_before: str = "2024-06-01",
                     date_col: str | None = None,
                     ticker_col: str | None = None) -> tuple[pd.DataFrame, int]:
    """Drop forward-filled frozen rows where a name was not actually trading.

    A delisted / suspended stock keeps getting its last price forward-filled, so
    the panel shows a constant series it never traded (SBIHOMEFIN: flat at ₹15.35
    for 2013-2020; SALORAINTL: a frozen pre-delisting tail). Those rows are not
    real sessions for that name and must not enter the cross-section — a constant
    series has a meaningless rank and, once NaN→0 imputed downstream, masquerades
    as 'perfectly average'.

    Two regimes, by whether the ticker is still live (last observation on/after
    `delisted_before`):
      * DELISTED name (last obs before the cutoff): every frozen session
        (|return| < 0.1%) is dropped — a dying micro-cap's terminal illiquidity
        is interspersed, not one long run, so the run rule alone misses it.
      * ACTIVE name: only maximal runs of >= `min_run` frozen sessions are
        dropped, so a genuinely quiet week in a liquid name is never touched
        (the sanitized mega-caps move daily and are unaffected)."""
    dcol = date_col or ("Date" if "Date" in prices.columns else "date")
    tcol = ticker_col or ("ticker" if "ticker" in prices.columns else "Ticker")
    ccol = "Close" if "Close" in prices.columns else "close"
    cutoff = pd.Timestamp(delisted_before)
    df = prices.sort_values([tcol, dcol]).reset_index(drop=True)
    dates = pd.to_datetime(df[dcol])
    drop_mask = pd.Series(False, index=df.index)
    for _, idx in df.groupby(tcol).groups.items():
        idx = list(idx)
        c = pd.to_numeric(df.loc[idx, ccol], errors="coerce").to_numpy()
        if len(c) < min_run + 1 or np.nanmedian(c) < 5.0:
            continue
        frozen = np.abs(np.diff(c) / c[:-1]) < 0.001   # len-1; frozen[i] = row i+1 vs i
        delisted = dates.iloc[idx].max() < cutoff
        if delisted:
            for k in np.nonzero(frozen)[0]:
                drop_mask.iloc[idx[k + 1]] = True
        else:
            run = 0
            for j in range(len(frozen)):
                if frozen[j]:
                    run += 1
                else:
                    if run >= min_run:
                        for k in range(j - run + 1, j + 1):
                            drop_mask.iloc[idx[k]] = True
                    run = 0
            if run >= min_run:  # trailing run to the series end
                for k in range(len(frozen) - run + 1, len(frozen) + 1):
                    drop_mask.iloc[idx[k]] = True
    return df[~drop_mask].reset_index(drop=True), int(drop_mask.sum())


def main():
    all_data = []
    fixed_tickers = []

    files = [f for f in os.listdir(RAW_PRICE_DIR) if f.endswith(".csv")]

    print(f"📦 Processing {len(files)} price files")

    for file in files:
        try:
            ticker = file.replace(".csv", "")
            path = os.path.join(RAW_PRICE_DIR, file)

            df = pd.read_csv(path)
            if df.empty:
                continue

            df["Date"] = pd.to_datetime(df["Date"])
            # Repair mixed adjusted/unadjusted scale discontinuities at the
            # source so every downstream consumer (scores, momentum, backtests,
            # NAV marks) sees a continuous series. See src/data/price_sanitizer.
            df, n_fixed = sanitize_ticker_frame(df)
            if n_fixed:
                fixed_tickers.append((ticker, n_fixed))
            df["ticker"] = ticker

            all_data.append(df)

        except Exception as e:
            print(f"❌ {file}: {e}")

    prices = pd.concat(all_data)
    prices = prices.sort_values(["ticker", "Date"])

    prices, n_dropped = drop_non_session_rows(prices)

    prices.to_parquet(OUTPUT_FILE, index=False)

    if fixed_tickers:
        print(f"🩹 back-adjusted scale discontinuities in {len(fixed_tickers)} tickers: "
              + ", ".join(f"{t}({n})" for t, n in fixed_tickers[:10]))
    if n_dropped:
        print(f"🗓  dropped {n_dropped} fabricated non-session rows "
              "(weekends / NSE holidays present only in corrupted mega-cap feeds)")
    print(f"✅ Prices saved: {len(prices)} rows (last date {prices['Date'].max().date()})")


if __name__ == "__main__":
    main()
