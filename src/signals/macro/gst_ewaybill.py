"""GST e-way bill helpers."""

from __future__ import annotations

import pandas as pd


def apply_gst_pit_lag(df: pd.DataFrame) -> pd.DataFrame:
    """Apply conservative GST lag (month end + 30 days)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "year_month" in out.columns:
        out["date"] = pd.to_datetime(out["year_month"].astype(str) + "-01", errors="coerce")
        out["date"] = out["date"] + pd.offsets.MonthEnd(0)
    else:
        out["date"] = pd.to_datetime(out.get("date"), errors="coerce")
    out["availability_date"] = pd.to_datetime(out.get("availability_date"), errors="coerce")
    mask = out["availability_date"].isna()
    out.loc[mask, "availability_date"] = out.loc[mask, "date"] + pd.Timedelta(days=30)
    return out
