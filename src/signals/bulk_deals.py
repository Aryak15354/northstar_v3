"""Bulk deal feature engineering."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from src.core.panel_math import coalesce_rowwise, normalize_ticker as _normalize_ticker  # noqa: F401


BUYER_CATEGORIES = {
    "FII": ["FII", "FPI", "FOREIGN", "OVERSEAS", "OFFSHORE"],
    "DII": ["MUTUAL FUND", "MF", "INSURANCE", "PENSION", "BANK", "TRUST", "AMC", "ASSET MGMT"],
    "PROMOTER": ["PROMOTER", "PROMOTERS", "PROMOTER GROUP"],
    "INSTITUTIONAL": ["CAPITAL", "INVEST", "FUND", "VENTURE", "PARTNERS", "HOLDINGS"],
    "RETAIL": ["RETAIL", "INDIVIDUAL", "HUF"],
}

BUYER_LOOKUP_PATH = Path("data/processed/alternative/bulk_deals_buyer_lookup.csv")
FUZZY_THRESHOLD = 0.85


def _find_col(columns: Iterable[str], aliases: Iterable[str]) -> str | None:
    norm = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): str(c) for c in columns}
    for a in aliases:
        key = re.sub(r"[^a-z0-9]+", "", str(a).lower())
        if key in norm:
            return norm[key]
    return None


def _series_from_frame(frame: pd.DataFrame, column: str | None, default: object = np.nan) -> pd.Series:
    if column and column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def _normalize_name(value: object) -> str:
    s = str(value or "").strip().upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def _levenshtein_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    dist = _levenshtein_distance(a, b)
    denom = max(len(a), len(b), 1)
    return 1.0 - float(dist) / float(denom)


def _load_buyer_lookup() -> dict[str, str]:
    if not BUYER_LOOKUP_PATH.exists():
        return {}
    try:
        df = pd.read_csv(BUYER_LOOKUP_PATH)
    except Exception:
        return {}
    if df.empty or "pattern" not in df.columns or "category" not in df.columns:
        return {}
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        pat = _normalize_name(row.get("pattern"))
        cat = str(row.get("category") or "").strip().upper()
        if pat and cat:
            out[pat] = cat
    return out


def _classify_buyer(name: str, lookup: dict[str, str]) -> str:
    norm = _normalize_name(name)
    if not norm:
        return "UNKNOWN"
    for pat, cat in lookup.items():
        if pat in norm or norm == pat:
            return cat

    best_cat = "UNKNOWN"
    best_score = 0.0
    for cat, patterns in BUYER_CATEGORIES.items():
        for pat in patterns:
            p = _normalize_name(pat)
            if not p:
                continue
            score = _levenshtein_ratio(norm, p)
            if score > best_score:
                best_score = score
                best_cat = cat
    if best_score >= FUZZY_THRESHOLD:
        return best_cat
    return "UNKNOWN"


def _empty_output(prices_df: pd.DataFrame) -> pd.DataFrame:
    if prices_df is None or prices_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "ticker",
                "availability_date",
                "bulk_buy_volume_5d",
                "bulk_sell_volume_5d",
                "bulk_net_volume_5d",
                "bulk_buy_volume_21d",
                "bulk_sell_volume_21d",
                "bulk_net_volume_21d",
                "bulk_buy_count_5d",
                "bulk_deal_flag",
                "bulk_deal_value_pct_mcap",
                "institutional_buy_flag",
                "bulk_net_pressure_5d",
                "bulk_net_pressure_21d",
                "bulk_net_pressure_float_21d",
                "bulk_net_fii_21d",
                "bulk_net_dii_21d",
                "bulk_net_promoter_21d",
                "bulk_net_institutional_21d",
                "bulk_net_retail_21d",
                "bulk_net_unknown_21d",
            ]
        )
    out = prices_df[["date", "ticker"]].copy()
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in [
        "bulk_buy_volume_5d",
        "bulk_sell_volume_5d",
        "bulk_net_volume_5d",
        "bulk_buy_volume_21d",
        "bulk_sell_volume_21d",
        "bulk_net_volume_21d",
        "bulk_buy_count_5d",
        "bulk_deal_flag",
        "bulk_deal_value_pct_mcap",
        "institutional_buy_flag",
        "bulk_net_pressure_5d",
        "bulk_net_pressure_21d",
        "bulk_net_pressure_float_21d",
        "bulk_net_fii_21d",
        "bulk_net_dii_21d",
        "bulk_net_promoter_21d",
        "bulk_net_institutional_21d",
        "bulk_net_retail_21d",
        "bulk_net_unknown_21d",
    ]:
        out[c] = np.nan
    return out


def compute_bulk_deal_features(df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build PIT-safe bulk deal features aligned to the price panel.

    PIT rule:
    - A deal published at end-of-day on D is available from D+1 business day.
      Therefore availability_date = deal_date + 1 BDay.
    """
    if prices_df is None or prices_df.empty:
        return _empty_output(pd.DataFrame())

    prices = prices_df.copy()
    prices["date"] = pd.to_datetime(_series_from_frame(prices, "date"), errors="coerce")
    prices["ticker"] = _series_from_frame(prices, "ticker", "").map(_normalize_ticker)
    prices = prices.dropna(subset=["date", "ticker"])
    prices = prices.sort_values(["ticker", "date"], kind="mergesort")
    if prices.empty:
        return _empty_output(pd.DataFrame())

    if df is None or df.empty:
        return _empty_output(prices)

    deals = df.copy()
    deals_col_date = _find_col(deals.columns, ["date", "deal_date", "trade_date"])
    deals_col_ticker = _find_col(deals.columns, ["nse_ticker", "ticker"])
    if deals_col_ticker is None:
        deals_col_ticker = _find_col(deals.columns, ["symbol", "security"])
    col_type = _find_col(deals.columns, ["deal_type", "side", "action"])
    col_qty = _find_col(deals.columns, ["quantity", "qty", "deal_qty"])
    col_price = _find_col(deals.columns, ["price", "deal_price"])
    col_client = _find_col(deals.columns, ["client_name", "client", "buyer_name"])

    if deals_col_date is None or deals_col_ticker is None:
        return _empty_output(prices)

    deals["date"] = pd.to_datetime(deals[deals_col_date], errors="coerce")
    deals["ticker"] = deals[deals_col_ticker].map(_normalize_ticker)
    deals = deals.dropna(subset=["date", "ticker"])
    if deals.empty:
        return _empty_output(prices)

    deals["deal_type"] = deals[col_type].astype(str).str.upper().str.strip() if col_type else ""
    deals["quantity"] = pd.to_numeric(deals[col_qty], errors="coerce") if col_qty else np.nan
    deals["price"] = pd.to_numeric(deals[col_price], errors="coerce") if col_price else np.nan
    deals["value"] = deals["quantity"] * deals["price"]

    # PIT safety: bulk deal on D appears from D+1 business day.
    deals["availability_date"] = pd.to_datetime(deals["date"], errors="coerce") + BDay(1)

    # Survivorship filter: drop deals after delisting date.
    delist_path = Path("data/universe/delisting_database.parquet")
    if delist_path.exists():
        try:
            delist = pd.read_parquet(delist_path)
        except Exception:
            delist = pd.DataFrame()
        if not delist.empty and "symbol" in delist.columns:
            delist = delist.copy()
            delist["ticker"] = delist["symbol"].map(_normalize_ticker)
            delist["delisting_date"] = pd.to_datetime(delist.get("delisting_date"), errors="coerce")
            delist = delist.dropna(subset=["ticker", "delisting_date"])[["ticker", "delisting_date"]]
            if not delist.empty:
                deals = deals.merge(delist, on="ticker", how="left")
                deals = deals.loc[
                    ~(
                        deals["delisting_date"].notna()
                        & (pd.to_datetime(deals["date"], errors="coerce") > deals["delisting_date"])
                    )
                ].copy()
                deals = deals.drop(columns=["delisting_date"], errors="ignore")

    lookup = _load_buyer_lookup()
    names = deals[col_client].astype(str) if col_client else pd.Series("", index=deals.index)
    # Classify each DISTINCT buyer name once, not once per deal row. Buyer names
    # repeat massively across deals, and _classify_buyer runs pure-Python fuzzy
    # (Levenshtein) matching — computing it per-row made it 83% of the whole
    # feature build (5.7M Levenshtein calls, ~4h for 578 tickers). Deduping to
    # unique names is behaviour-identical (the function is a pure map of name ->
    # category) but collapses the call count ~100x.
    name_to_cat = {nm: _classify_buyer(nm, lookup) for nm in names.unique()}
    deals["buyer_category"] = names.map(name_to_cat)

    categories = ["FII", "DII", "PROMOTER", "INSTITUTIONAL", "RETAIL", "UNKNOWN"]
    for cat in categories:
        deals[f"buy_{cat}"] = np.where(
            (deals["deal_type"].eq("BUY") & deals["buyer_category"].eq(cat)),
            deals["quantity"],
            0.0,
        )
        deals[f"sell_{cat}"] = np.where(
            (deals["deal_type"].eq("SELL") & deals["buyer_category"].eq(cat)),
            deals["quantity"],
            0.0,
        )

    daily = deals.groupby(["ticker", "availability_date"], as_index=False).agg(
        buy_qty=("quantity", lambda x: pd.to_numeric(x, errors="coerce")[deals.loc[x.index, "deal_type"].eq("BUY")].sum()),
        sell_qty=("quantity", lambda x: pd.to_numeric(x, errors="coerce")[deals.loc[x.index, "deal_type"].eq("SELL")].sum()),
        buy_count=("deal_type", lambda x: float((x == "BUY").sum())),
        any_deal=("deal_type", lambda x: float(len(x) > 0)),
        deal_value=("value", "sum"),
        **{f"buy_{cat}": (f"buy_{cat}", "sum") for cat in categories},
        **{f"sell_{cat}": (f"sell_{cat}", "sum") for cat in categories},
    )

    inst_cats = {"FII", "DII", "INSTITUTIONAL", "PROMOTER"}
    daily["institutional_buy_flag"] = daily[[f"buy_{cat}" for cat in inst_cats]].sum(axis=1).gt(0.0).astype(float)

    base_cols = [
        c
        for c in [
            "date",
            "ticker",
            "close",
            "volume",
            "market_cap",
            "shares_outstanding",
            "screener_free_float_pct",
            "free_float_pct",
        ]
        if c in prices.columns
    ]
    base = prices[base_cols].copy() if base_cols else prices[["date", "ticker"]].copy()
    base["market_cap"] = pd.to_numeric(_series_from_frame(base, "market_cap"), errors="coerce")
    # N10: per-row fallback to close*shares where market_cap is missing.
    if {"close", "shares_outstanding"}.issubset(set(base.columns)):
        base["market_cap"] = coalesce_rowwise(
            base["market_cap"],
            pd.to_numeric(base["close"], errors="coerce") * pd.to_numeric(base["shares_outstanding"], errors="coerce"),
        )
    base["volume"] = pd.to_numeric(_series_from_frame(base, "volume"), errors="coerce")
    base["shares_outstanding"] = pd.to_numeric(_series_from_frame(base, "shares_outstanding"), errors="coerce")
    free_float_pct = pd.to_numeric(_series_from_frame(base, "free_float_pct"), errors="coerce")
    # N10: per-row fallback to the screener free-float column.
    free_float_pct = coalesce_rowwise(
        free_float_pct,
        pd.to_numeric(_series_from_frame(base, "screener_free_float_pct"), errors="coerce"),
    )
    base["free_float_pct"] = free_float_pct
    base["free_float_shares"] = base["shares_outstanding"] * (base["free_float_pct"] / 100.0)

    out_frames: list[pd.DataFrame] = []
    for ticker, grp in base.groupby("ticker", sort=False):
        d = daily[daily["ticker"] == ticker].copy()
        g = grp.sort_values("date", kind="mergesort").copy()
        if d.empty:
            for c in ["buy_qty", "sell_qty", "buy_count", "any_deal", "deal_value", "institutional_buy_flag"]:
                g[c] = 0.0
            for cat in ["FII", "DII", "PROMOTER", "INSTITUTIONAL", "RETAIL", "UNKNOWN"]:
                g[f"buy_{cat}"] = 0.0
                g[f"sell_{cat}"] = 0.0
        else:
            m = g.merge(
                d.drop(columns=["ticker"], errors="ignore"),
                left_on="date",
                right_on="availability_date",
                how="left",
            )
            for c in ["buy_qty", "sell_qty", "buy_count", "any_deal", "deal_value", "institutional_buy_flag"]:
                m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0.0)
            for cat in ["FII", "DII", "PROMOTER", "INSTITUTIONAL", "RETAIL", "UNKNOWN"]:
                for side in ["buy", "sell"]:
                    col = f"{side}_{cat}"
                    if col in m.columns:
                        m[col] = pd.to_numeric(m[col], errors="coerce").fillna(0.0)
                    else:
                        m[col] = 0.0
            g = m

        g = g.sort_values("date", kind="mergesort")
        g["bulk_buy_volume_5d"] = g["buy_qty"].rolling(5, min_periods=1).sum()
        g["bulk_sell_volume_5d"] = g["sell_qty"].rolling(5, min_periods=1).sum()
        g["bulk_net_volume_5d"] = g["bulk_buy_volume_5d"] - g["bulk_sell_volume_5d"]
        g["bulk_buy_volume_21d"] = g["buy_qty"].rolling(21, min_periods=5).sum()
        g["bulk_sell_volume_21d"] = g["sell_qty"].rolling(21, min_periods=5).sum()
        g["bulk_net_volume_21d"] = g["bulk_buy_volume_21d"] - g["bulk_sell_volume_21d"]
        g["bulk_buy_count_5d"] = g["buy_count"].rolling(5, min_periods=1).sum()
        g["bulk_deal_flag"] = g["any_deal"].rolling(5, min_periods=1).max().astype(float)
        g["institutional_buy_flag"] = g["institutional_buy_flag"].rolling(5, min_periods=1).max().astype(float)
        g["bulk_deal_value_5d"] = g["deal_value"].rolling(5, min_periods=1).sum()
        g["bulk_deal_value_pct_mcap"] = (
            100.0
            * pd.to_numeric(g["bulk_deal_value_5d"], errors="coerce")
            / pd.to_numeric(g["market_cap"], errors="coerce").replace(0.0, np.nan)
        )
        adv_21d = pd.to_numeric(g["volume"], errors="coerce").rolling(21, min_periods=10).mean()
        g["bulk_net_pressure_5d"] = g["bulk_net_volume_5d"] / adv_21d.replace(0.0, np.nan)
        g["bulk_net_pressure_21d"] = g["bulk_net_volume_21d"] / adv_21d.replace(0.0, np.nan)

        free_float = pd.to_numeric(g["free_float_shares"], errors="coerce")
        g["bulk_net_pressure_float_21d"] = g["bulk_net_volume_21d"] / free_float.replace(0.0, np.nan)

        for cat in ["FII", "DII", "PROMOTER", "INSTITUTIONAL", "RETAIL", "UNKNOWN"]:
            buy_col = f"buy_{cat}"
            sell_col = f"sell_{cat}"
            net = (g[buy_col] - g[sell_col]).rolling(21, min_periods=5).sum()
            g[f"bulk_net_{cat.lower()}_21d"] = net / free_float.replace(0.0, np.nan)
        out_frames.append(g)

    out = pd.concat(out_frames, ignore_index=True) if out_frames else _empty_output(prices)
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce")
    keep = [
        "date",
        "ticker",
        "availability_date",
        "bulk_buy_volume_5d",
        "bulk_sell_volume_5d",
        "bulk_net_volume_5d",
        "bulk_buy_volume_21d",
        "bulk_sell_volume_21d",
        "bulk_net_volume_21d",
        "bulk_buy_count_5d",
        "bulk_deal_flag",
        "bulk_deal_value_pct_mcap",
        "institutional_buy_flag",
        "bulk_net_pressure_5d",
        "bulk_net_pressure_21d",
        "bulk_net_pressure_float_21d",
        "bulk_net_fii_21d",
        "bulk_net_dii_21d",
        "bulk_net_promoter_21d",
        "bulk_net_institutional_21d",
        "bulk_net_retail_21d",
        "bulk_net_unknown_21d",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = np.nan
    return out[keep].sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
