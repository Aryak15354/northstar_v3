"""CEA power data helpers."""

from __future__ import annotations

import pandas as pd


def apply_power_pit_lag(df: pd.DataFrame) -> pd.DataFrame:
    """Apply CEA lag (date + 1 day)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["date"] = pd.to_datetime(out.get("date"), errors="coerce")
    out["availability_date"] = pd.to_datetime(out.get("availability_date"), errors="coerce")
    mask = out["availability_date"].isna()
    out.loc[mask, "availability_date"] = out.loc[mask, "date"] + pd.Timedelta(days=1)
    return out
