"""Bulk deal feature engineering."""

from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


INSTITUTIONAL_KEYWORDS = (
    "MF",
    "MUTUAL FUND",
    "FII",
    "FPI",
    "INSURANCE",
    "PENSION",
    "FUND",
)


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _find_col(columns: Iterable[str], aliases: Iterable[str]) -> str | None:
    norm = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): str(c) for c in columns}
    for a in aliases:
        key = re.sub(r"[^a-z0-9]+", "", str(a).lower())
        if key in norm:
            return norm[key]
    return None


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
                "bulk_buy_count_5d",
                "bulk_deal_flag",
                "bulk_deal_value_pct_mcap",
                "institutional_buy_flag",
            ]
        )
    out = prices_df[["date", "ticker"]].copy()
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in [
        "bulk_buy_volume_5d",
        "bulk_sell_volume_5d",
        "bulk_net_volume_5d",
        "bulk_buy_count_5d",
        "bulk_deal_flag",
        "bulk_deal_value_pct_mcap",
        "institutional_buy_flag",
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
    prices["date"] = pd.to_datetime(prices.get("date"), errors="coerce")
    prices["ticker"] = prices.get("ticker", "").map(_normalize_ticker)
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

    names = deals[col_client].astype(str).str.upper().fillna("") if col_client else pd.Series("", index=deals.index)
    inst_pat = "|".join(re.escape(k) for k in INSTITUTIONAL_KEYWORDS)
    deals["institutional_buy"] = (
        deals["deal_type"].eq("BUY") & names.str.contains(inst_pat, regex=True, na=False)
    ).astype(float)

    daily = (
        deals.groupby(["ticker", "availability_date"], as_index=False)
        .agg(
            buy_qty=("quantity", lambda x: pd.to_numeric(x, errors="coerce")[deals.loc[x.index, "deal_type"].eq("BUY")].sum()),
            sell_qty=("quantity", lambda x: pd.to_numeric(x, errors="coerce")[deals.loc[x.index, "deal_type"].eq("SELL")].sum()),
            buy_count=("deal_type", lambda x: float((x == "BUY").sum())),
            any_deal=("deal_type", lambda x: float(len(x) > 0)),
            deal_value=("value", "sum"),
            institutional_buy_flag=("institutional_buy", "max"),
        )
    )

    base = prices[["date", "ticker"]].copy()
    if "market_cap" in prices.columns:
        base["market_cap"] = pd.to_numeric(prices["market_cap"], errors="coerce")
    elif {"close", "shares_outstanding"}.issubset(set(prices.columns)):
        base["market_cap"] = pd.to_numeric(prices["close"], errors="coerce") * pd.to_numeric(
            prices["shares_outstanding"], errors="coerce"
        )
    else:
        base["market_cap"] = np.nan

    out_frames: list[pd.DataFrame] = []
    for ticker, grp in base.groupby("ticker", sort=False):
        d = daily[daily["ticker"] == ticker].copy()
        g = grp.sort_values("date", kind="mergesort").copy()
        if d.empty:
            for c in ["buy_qty", "sell_qty", "buy_count", "any_deal", "deal_value", "institutional_buy_flag"]:
                g[c] = 0.0
        else:
            m = g.merge(
                d.drop(columns=["ticker"], errors="ignore"),
                left_on="date",
                right_on="availability_date",
                how="left",
            )
            for c in ["buy_qty", "sell_qty", "buy_count", "any_deal", "deal_value", "institutional_buy_flag"]:
                m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0.0)
            g = m

        g = g.sort_values("date", kind="mergesort")
        g["bulk_buy_volume_5d"] = g["buy_qty"].rolling(5, min_periods=1).sum()
        g["bulk_sell_volume_5d"] = g["sell_qty"].rolling(5, min_periods=1).sum()
        g["bulk_net_volume_5d"] = g["bulk_buy_volume_5d"] - g["bulk_sell_volume_5d"]
        g["bulk_buy_count_5d"] = g["buy_count"].rolling(5, min_periods=1).sum()
        g["bulk_deal_flag"] = g["any_deal"].rolling(5, min_periods=1).max().astype(float)
        g["institutional_buy_flag"] = g["institutional_buy_flag"].rolling(5, min_periods=1).max().astype(float)
        g["bulk_deal_value_5d"] = g["deal_value"].rolling(5, min_periods=1).sum()
        g["bulk_deal_value_pct_mcap"] = (
            100.0
            * pd.to_numeric(g["bulk_deal_value_5d"], errors="coerce")
            / pd.to_numeric(g["market_cap"], errors="coerce").replace(0.0, np.nan)
        )
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
        "bulk_buy_count_5d",
        "bulk_deal_flag",
        "bulk_deal_value_pct_mcap",
        "institutional_buy_flag",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = np.nan
    return out[keep].sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
