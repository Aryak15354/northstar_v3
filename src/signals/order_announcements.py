"""Corporate announcement feature engineering."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


_ORDER_VALUE_PATTERNS = [
    re.compile(r"(?:rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:crore|cr)\b", re.IGNORECASE),
    re.compile(r"(?:rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:lakh|lac)\b", re.IGNORECASE),
]


CATEGORY_ALIASES = {
    "ORDER WIN": "order_win",
    "CAPACITY EXPANSION": "capacity_expansion",
    "ACQUISITION": "acquisition",
    "MERGER": "merger",
    "INSIDER TRADING": "insider_trading",
}


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _parse_order_value_crore(text: object) -> float:
    s = str(text or "")
    if not s:
        return np.nan
    for pat in _ORDER_VALUE_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        try:
            v = float(str(m.group(1)).replace(",", ""))
        except Exception:
            continue
        if "lakh" in pat.pattern or "lac" in pat.pattern:
            return v / 100.0
        return v
    return np.nan


def _resolve_revenue_frame(fundamentals_df: pd.DataFrame | None) -> pd.DataFrame:
    if fundamentals_df is None or fundamentals_df.empty:
        return pd.DataFrame(columns=["ticker", "availability_date", "annual_revenue"])
    f = fundamentals_df.copy()
    tk_col = "ticker" if "ticker" in f.columns else ("nse_ticker" if "nse_ticker" in f.columns else None)
    dt_col = "availability_date" if "availability_date" in f.columns else ("date" if "date" in f.columns else None)
    rev_col = "revenue" if "revenue" in f.columns else None
    if tk_col is None or dt_col is None or rev_col is None:
        return pd.DataFrame(columns=["ticker", "availability_date", "annual_revenue"])
    out = f[[tk_col, dt_col, rev_col]].copy()
    out.columns = ["ticker", "availability_date", "annual_revenue"]
    out["ticker"] = out["ticker"].map(_normalize_ticker)
    out["availability_date"] = pd.to_datetime(out["availability_date"], errors="coerce")
    out["annual_revenue"] = pd.to_numeric(out["annual_revenue"], errors="coerce")
    out = out.dropna(subset=["ticker", "availability_date"]).sort_values(["ticker", "availability_date"], kind="mergesort")
    return out


def compute_announcement_features(
    df: pd.DataFrame,
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Build PIT-safe event-window features from BSE announcements.

    PIT rule:
    - Corporate announcements on D are available from D+1 business day.
    """
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "availability_date",
                "order_win_count_90d",
                "order_win_flag_30d",
                "capex_announced_flag",
                "insider_buy_flag_30d",
                "insider_sell_flag_30d",
                "acquisition_flag_180d",
                "order_to_revenue_ratio",
            ]
        )

    px = prices_df[["date", "ticker"]].copy()
    px["date"] = pd.to_datetime(px["date"], errors="coerce")
    px["ticker"] = px["ticker"].map(_normalize_ticker)
    px = px.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"], kind="mergesort")

    if df is None or df.empty:
        out = px.copy()
        out["availability_date"] = out["date"]
        for c in [
            "order_win_count_90d",
            "order_win_flag_30d",
            "capex_announced_flag",
            "insider_buy_flag_30d",
            "insider_sell_flag_30d",
            "acquisition_flag_180d",
            "order_to_revenue_ratio",
        ]:
            out[c] = np.nan
        return out

    ev = df.copy()
    tk_col = "nse_ticker" if "nse_ticker" in ev.columns else ("ticker" if "ticker" in ev.columns else None)
    dt_col = "date" if "date" in ev.columns else ("announcement_date" if "announcement_date" in ev.columns else None)
    cat_col = "category" if "category" in ev.columns else None
    head_col = "headline" if "headline" in ev.columns else None
    text_col = "announcement_text" if "announcement_text" in ev.columns else None

    if tk_col is None or dt_col is None or cat_col is None:
        out = px.copy()
        out["availability_date"] = out["date"]
        for c in [
            "order_win_count_90d",
            "order_win_flag_30d",
            "capex_announced_flag",
            "insider_buy_flag_30d",
            "insider_sell_flag_30d",
            "acquisition_flag_180d",
            "order_to_revenue_ratio",
        ]:
            out[c] = np.nan
        return out

    ev["ticker"] = ev[tk_col].map(_normalize_ticker)
    ev["date"] = pd.to_datetime(ev[dt_col], errors="coerce")
    ev["category"] = ev[cat_col].astype(str).str.upper().str.strip()
    ev["cat_norm"] = ev["category"].map(lambda x: CATEGORY_ALIASES.get(x, x.lower().replace(" ", "_")))

    text = ev[head_col].astype(str).fillna("") if head_col else pd.Series("", index=ev.index)
    if text_col:
        text = text + " " + ev[text_col].astype(str).fillna("")
    ev["full_text"] = text

    ev = ev.dropna(subset=["ticker", "date"]).copy()
    # PIT safety for announcement events.
    ev["availability_date"] = ev["date"] + BDay(1)

    ev["order_win_event"] = ev["cat_norm"].eq("order_win").astype(float)
    ev["capex_event"] = ev["cat_norm"].eq("capacity_expansion").astype(float)
    ev["acquisition_event"] = ev["cat_norm"].isin(["acquisition", "merger"]).astype(float)
    ev["insider_event"] = ev["cat_norm"].eq("insider_trading").astype(float)
    ev["insider_buy_event"] = (
        ev["insider_event"].eq(1.0) & ev["full_text"].str.contains(r"\bbuy|purchase|acquire\b", regex=True, case=False)
    ).astype(float)
    ev["insider_sell_event"] = (
        ev["insider_event"].eq(1.0) & ev["full_text"].str.contains(r"\bsell|sale|disposed\b", regex=True, case=False)
    ).astype(float)
    ev["order_value_crore"] = ev["full_text"].map(_parse_order_value_crore)

    daily = (
        ev.groupby(["ticker", "availability_date"], as_index=False)
        .agg(
            order_win_count=("order_win_event", "sum"),
            order_win_flag=("order_win_event", "max"),
            capex_flag=("capex_event", "max"),
            insider_buy_flag=("insider_buy_event", "max"),
            insider_sell_flag=("insider_sell_event", "max"),
            acquisition_flag=("acquisition_event", "max"),
            order_value_crore=("order_value_crore", "sum"),
        )
    )

    rev = _resolve_revenue_frame(fundamentals_df)

    out_frames: list[pd.DataFrame] = []
    for tk, grp in px.groupby("ticker", sort=False):
        base = grp.sort_values("date", kind="mergesort").copy()
        d = daily[daily["ticker"] == tk].copy()
        merged = base.merge(
            d.drop(columns=["ticker"], errors="ignore"),
            left_on="date",
            right_on="availability_date",
            how="left",
        )
        for c in [
            "order_win_count",
            "order_win_flag",
            "capex_flag",
            "insider_buy_flag",
            "insider_sell_flag",
            "acquisition_flag",
            "order_value_crore",
        ]:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0)

        merged["order_win_count_90d"] = merged["order_win_count"].rolling(90, min_periods=1).sum()
        merged["order_win_flag_30d"] = merged["order_win_flag"].rolling(30, min_periods=1).max().astype(float)
        merged["capex_announced_flag"] = merged["capex_flag"].rolling(180, min_periods=1).max().astype(float)
        merged["insider_buy_flag_30d"] = merged["insider_buy_flag"].rolling(30, min_periods=1).max().astype(float)
        merged["insider_sell_flag_30d"] = merged["insider_sell_flag"].rolling(30, min_periods=1).max().astype(float)
        merged["acquisition_flag_180d"] = merged["acquisition_flag"].rolling(180, min_periods=1).max().astype(float)
        merged["order_value_90d"] = merged["order_value_crore"].rolling(90, min_periods=1).sum()

        rt = rev[rev["ticker"] == tk].copy()
        if rt.empty:
            merged["annual_revenue"] = np.nan
        else:
            merged = pd.merge_asof(
                merged.sort_values("date", kind="mergesort"),
                rt[["availability_date", "annual_revenue"]].sort_values("availability_date", kind="mergesort"),
                left_on="date",
                right_on="availability_date",
                direction="backward",
                allow_exact_matches=True,
                suffixes=("", "_rev"),
            )

        merged["order_to_revenue_ratio"] = pd.to_numeric(merged["order_value_90d"], errors="coerce") / pd.to_numeric(
            merged.get("annual_revenue", np.nan), errors="coerce"
        ).replace(0.0, np.nan)
        out_frames.append(merged)

    out = pd.concat(out_frames, ignore_index=True) if out_frames else px.copy()
    out["availability_date"] = out["date"]
    keep = [
        "date",
        "ticker",
        "availability_date",
        "order_win_count_90d",
        "order_win_flag_30d",
        "capex_announced_flag",
        "insider_buy_flag_30d",
        "insider_sell_flag_30d",
        "acquisition_flag_180d",
        "order_to_revenue_ratio",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = np.nan
    return out[keep].sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
