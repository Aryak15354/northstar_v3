"""Promoter pledge feature engineering."""

from __future__ import annotations

import numpy as np
import pandas as pd


QUARTER_LAG_DAYS = 45


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def compute_pledge_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build promoter pledge features from quarterly filing records.

    PIT rule:
    - Quarterly pledge filings are conservatively available at quarter_end + 45 days.
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "availability_date",
                "pledge_pct",
                "pledge_change_1q",
                "pledge_change_4q",
                "pledge_high_flag",
                "pledge_increasing_flag",
                "pledge_decreasing_flag",
            ]
        )

    out = df.copy()
    date_col = "date" if "date" in out.columns else ("quarter_end" if "quarter_end" in out.columns else None)
    ticker_col = "nse_ticker" if "nse_ticker" in out.columns else ("ticker" if "ticker" in out.columns else None)
    if date_col is None or ticker_col is None:
        return pd.DataFrame()

    out["date"] = pd.to_datetime(out[date_col], errors="coerce")
    out["ticker"] = out[ticker_col].map(_normalize_ticker)
    out["pledge_pct"] = pd.to_numeric(out.get("pledge_pct"), errors="coerce")
    if out["pledge_pct"].isna().all() and {"shares_pledged", "total_promoter_shares"}.issubset(set(out.columns)):
        pledged = pd.to_numeric(out.get("shares_pledged"), errors="coerce")
        total = pd.to_numeric(out.get("total_promoter_shares"), errors="coerce").replace(0.0, np.nan)
        out["pledge_pct"] = 100.0 * pledged / total

    out = out.dropna(subset=["date", "ticker"])
    if out.empty:
        return pd.DataFrame()

    # PIT safety for quarterly filings.
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce") + pd.Timedelta(days=QUARTER_LAG_DAYS)
    out = out.sort_values(["ticker", "availability_date"], kind="mergesort")

    out["pledge_change_1q"] = out.groupby("ticker", sort=False)["pledge_pct"].diff(1)
    out["pledge_change_4q"] = out.groupby("ticker", sort=False)["pledge_pct"].diff(4)
    out["pledge_change_1q"] = out["pledge_change_1q"].fillna(0.0)
    out["pledge_change_4q"] = out["pledge_change_4q"].fillna(0.0)
    out["pledge_high_flag"] = (pd.to_numeric(out["pledge_pct"], errors="coerce") > 30.0).astype(float)

    d = out.groupby("ticker", sort=False)["pledge_pct"].diff(1)
    out["pledge_increasing_flag"] = ((d > 0.0) & (d.groupby(out["ticker"], sort=False).shift(1) > 0.0)).astype(float)
    out["pledge_decreasing_flag"] = ((d < 0.0) & (d.groupby(out["ticker"], sort=False).shift(1) < 0.0)).astype(float)

    cols = [
        "ticker",
        "date",
        "availability_date",
        "pledge_pct",
        "pledge_change_1q",
        "pledge_change_4q",
        "pledge_high_flag",
        "pledge_increasing_flag",
        "pledge_decreasing_flag",
    ]
    return out[cols].reset_index(drop=True)
