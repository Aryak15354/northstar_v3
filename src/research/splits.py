"""Leakage-safe time splits for walk-forward training."""

from __future__ import annotations

from typing import Dict, Iterator

import numpy as np
import pandas as pd


def eligible_trading_dates(
    frame: pd.DataFrame,
    *,
    date_col: str = "date",
    ticker_col: str = "ticker",
    min_tickers_per_date: int = 1,
) -> np.ndarray:
    """Return sorted eligible dates with sufficient cross-sectional coverage."""
    if frame.empty or date_col not in frame.columns:
        return np.asarray([], dtype="datetime64[ns]")

    d = pd.to_datetime(frame[date_col], errors="coerce")
    valid_rows = d.notna().to_numpy()
    if not valid_rows.any():
        return np.asarray([], dtype="datetime64[ns]")

    min_tickers = max(1, int(min_tickers_per_date))
    if ticker_col in frame.columns:
        work = pd.DataFrame(
            {
                "date": d[valid_rows].to_numpy(),
                "ticker": frame.loc[valid_rows, ticker_col].astype(str).to_numpy(),
            }
        )
        counts = work.groupby("date", sort=True)["ticker"].nunique()
        eligible = counts[counts >= min_tickers].index
        return np.asarray(sorted(pd.Index(eligible)), dtype="datetime64[ns]")

    # Without ticker column, degrade gracefully to date-only coverage.
    return np.asarray(sorted(pd.Index(d[valid_rows].unique())), dtype="datetime64[ns]")


def rolling_time_splits(
    frame: pd.DataFrame,
    date_col: str = "date",
    train_periods: int = 756,
    valid_periods: int = 126,
    test_periods: int = 126,
    step_periods: int = 63,
    ticker_col: str = "ticker",
    min_tickers_per_date: int = 1,
) -> Iterator[Dict[str, np.ndarray]]:
    """Yield rolling train/valid/test masks based on unique sorted dates.

    Period units are trading days (unique dates in the panel), not calendar days.
    """
    if frame.empty or date_col not in frame.columns:
        return

    d = pd.to_datetime(frame[date_col], errors="coerce")
    if not d.notna().to_numpy().any():
        return

    unique_dates = eligible_trading_dates(
        frame,
        date_col=date_col,
        ticker_col=ticker_col,
        min_tickers_per_date=min_tickers_per_date,
    )
    min_required = train_periods + valid_periods + test_periods
    if len(unique_dates) < min_required:
        return

    start = 0
    while start + min_required <= len(unique_dates):
        train_end = start + train_periods
        valid_end = train_end + valid_periods
        test_end = valid_end + test_periods

        train_dates = set(unique_dates[start:train_end])
        valid_dates = set(unique_dates[train_end:valid_end])
        test_dates = set(unique_dates[valid_end:test_end])

        row_dates = d.to_numpy()
        train_mask = np.array([x in train_dates for x in row_dates], dtype=bool)
        valid_mask = np.array([x in valid_dates for x in row_dates], dtype=bool)
        test_mask = np.array([x in test_dates for x in row_dates], dtype=bool)

        if train_mask.any() and test_mask.any():
            yield {
                "train_mask": train_mask,
                "valid_mask": valid_mask,
                "test_mask": test_mask,
                "train_start": str(unique_dates[start]),
                "train_end": str(unique_dates[train_end - 1]),
                "test_start": str(unique_dates[valid_end]),
                "test_end": str(unique_dates[test_end - 1]),
            }

        start += max(1, step_periods)


def regime_slice_mask(frame: pd.DataFrame, regime_col: str, regime_value: str) -> np.ndarray:
    if regime_col not in frame.columns:
        return np.zeros(len(frame), dtype=bool)
    return frame[regime_col].astype(str).str.lower().eq(str(regime_value).lower()).to_numpy()
