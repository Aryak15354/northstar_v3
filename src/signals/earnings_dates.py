"""Earnings announcement date utilities and features."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def get_availability_date(ticker: str, fiscal_year_end: object, earnings_dates_df: pd.DataFrame) -> pd.Timestamp:
    """
    For a ticker and fiscal year-end, return announcement_date + 1 day.

    Falls back to fiscal_year_end + 60 days if no match exists.
    """
    fy_end = pd.to_datetime(fiscal_year_end, errors="coerce")
    if pd.isna(fy_end):
        return pd.NaT
    fallback = fy_end + pd.Timedelta(days=60)
    if earnings_dates_df is None or earnings_dates_df.empty:
        return fallback

    df = earnings_dates_df.copy()
    tk = _normalize_ticker(ticker)
    tk_col = "nse_ticker" if "nse_ticker" in df.columns else ("ticker" if "ticker" in df.columns else None)
    ann_col = "announcement_date" if "announcement_date" in df.columns else ("date" if "date" in df.columns else None)
    if tk_col is None or ann_col is None:
        return fallback

    df["_ticker"] = df[tk_col].map(_normalize_ticker)
    df["_announcement"] = pd.to_datetime(df[ann_col], errors="coerce")
    df = df[df["_ticker"] == tk].dropna(subset=["_announcement"])
    if df.empty:
        return fallback

    if "fiscal_year_end" in df.columns:
        df["_fye"] = pd.to_datetime(df["fiscal_year_end"], errors="coerce")
        exact = df[df["_fye"] == fy_end]
        if not exact.empty:
            return pd.Timestamp(exact["_announcement"].min()) + pd.Timedelta(days=1)

    # Best-effort match: first announcement in [FYE, FYE+180d].
    win = df[(df["_announcement"] >= fy_end) & (df["_announcement"] <= fy_end + pd.Timedelta(days=180))]
    if not win.empty:
        return pd.Timestamp(win["_announcement"].min()) + pd.Timedelta(days=1)

    return fallback


def compute_earnings_features(df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build PIT-safe earnings cadence features.

    PIT rule:
    - Announcement on D is usable from D+1 business day.
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "availability_date",
                "days_since_earnings",
                "earnings_frequency_annual",
                "earnings_gap_days",
            ]
        )

    px = prices_df[["date", "ticker"]].copy()
    px["date"] = pd.to_datetime(px["date"], errors="coerce")
    px["ticker"] = px["ticker"].map(_normalize_ticker)
    px = px.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"], kind="mergesort")

    if df is None or df.empty:
        out = px.copy()
        out["availability_date"] = out["date"]
        out["days_since_earnings"] = np.nan
        out["earnings_frequency_annual"] = np.nan
        out["earnings_gap_days"] = np.nan
        return out

    e = df.copy()
    tk_col = "nse_ticker" if "nse_ticker" in e.columns else ("ticker" if "ticker" in e.columns else None)
    ann_col = "announcement_date" if "announcement_date" in e.columns else ("date" if "date" in e.columns else None)
    if tk_col is None or ann_col is None:
        out = px.copy()
        out["availability_date"] = out["date"]
        out["days_since_earnings"] = np.nan
        out["earnings_frequency_annual"] = np.nan
        out["earnings_gap_days"] = np.nan
        return out

    e["ticker"] = e[tk_col].map(_normalize_ticker)
    e["announcement_date"] = pd.to_datetime(e[ann_col], errors="coerce")
    e = e.dropna(subset=["ticker", "announcement_date"]).copy()
    if e.empty:
        out = px.copy()
        out["availability_date"] = out["date"]
        out["days_since_earnings"] = np.nan
        out["earnings_frequency_annual"] = np.nan
        out["earnings_gap_days"] = np.nan
        return out

    # PIT safety for earnings announcements.
    e["availability_date"] = e["announcement_date"] + BDay(1)

    if "fiscal_year_end" in e.columns:
        e["fiscal_year_end"] = pd.to_datetime(e["fiscal_year_end"], errors="coerce")
        e["earnings_gap_days"] = (e["announcement_date"] - e["fiscal_year_end"]).dt.days
    else:
        e["earnings_gap_days"] = np.nan
    e["earnings_frequency_annual"] = np.where(e["earnings_gap_days"].notna(), (e["earnings_gap_days"] <= 90).astype(float), np.nan)

    e = e.sort_values(["ticker", "availability_date"], kind="mergesort")

    out_frames: list[pd.DataFrame] = []
    for tk, grp in px.groupby("ticker", sort=False):
        ev = e[e["ticker"] == tk].copy()
        base = grp.sort_values("date", kind="mergesort").copy()
        if ev.empty:
            base["last_earnings_announcement"] = pd.NaT
            base["earnings_frequency_annual"] = np.nan
            base["earnings_gap_days"] = np.nan
        else:
            merged = pd.merge_asof(
                base,
                ev[["availability_date", "announcement_date", "earnings_frequency_annual", "earnings_gap_days"]].sort_values(
                    "availability_date", kind="mergesort"
                ),
                left_on="date",
                right_on="availability_date",
                direction="backward",
                allow_exact_matches=True,
            )
            merged = merged.rename(columns={"announcement_date": "last_earnings_announcement"})
            base = merged

        base["days_since_earnings"] = (
            pd.to_datetime(base["date"], errors="coerce") - pd.to_datetime(base["last_earnings_announcement"], errors="coerce")
        ).dt.days
        out_frames.append(base)

    out = pd.concat(out_frames, ignore_index=True) if out_frames else px.copy()
    out["availability_date"] = out["date"]
    keep = [
        "date",
        "ticker",
        "availability_date",
        "days_since_earnings",
        "earnings_frequency_annual",
        "earnings_gap_days",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = np.nan
    return out[keep].sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
