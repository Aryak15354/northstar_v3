from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if not np.isfinite(out):
            return default
        return out
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


def sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0))))


def infer_market_cap(row: pd.Series) -> float:
    # Preferred direct fields.
    for col in ("market_cap", "marketCap", "mcap", "marketcap"):
        market_cap = f(row.get(col), np.nan)
        if np.isfinite(market_cap) and market_cap > 0:
            return market_cap

    # Price x shares aliases.
    price = np.nan
    for p_col in ("Close", "close", "current_price", "close_price", "ltp", "price"):
        px = f(row.get(p_col), np.nan)
        if np.isfinite(px) and px > 0:
            price = px
            break
    shares = np.nan
    for s_col in (
        "shares_outstanding",
        "sharesOutstanding",
        "weighted_average_shares",
        "weighted_average_shares_ttm",
        "shares",
    ):
        sh = f(row.get(s_col), np.nan)
        if np.isfinite(sh) and sh > 0:
            shares = sh
            break
    if np.isfinite(price) and np.isfinite(shares):
        return float(price * shares)

    # EV bridge fallback: Equity = EV - Debt + Cash.
    enterprise_value = f(row.get("enterprise_value"), np.nan)
    if not (np.isfinite(enterprise_value) and enterprise_value > 0):
        enterprise_value = f(row.get("ev"), np.nan)
    debt = max(0.0, f(row.get("total_debt"), 0.0))
    cash = max(0.0, f(row.get("cash_and_equivalents"), 0.0))
    equity_from_ev = enterprise_value - debt + cash
    if np.isfinite(equity_from_ev) and equity_from_ev > 0:
        return float(equity_from_ev)

    return np.nan


def confidence_from_spread(
    spread_ratio: float,
    base: float = 0.70,
    floor: float = 0.20,
    cap: float = 0.95,
) -> float:
    """
    Convert valuation scenario spread into confidence.
    Larger spread -> lower confidence.
    """
    score = base - 1.2 * max(0.0, spread_ratio)
    return clamp(score, floor, cap)


def variance_from_bounds(low: float, high: float, scale: float = 1.96) -> float:
    if not (np.isfinite(low) and np.isfinite(high)):
        return 1.0
    if high < low:
        low, high = high, low
    sigma = (high - low) / (2.0 * max(scale, 1e-6))
    return float(max(1e-8, sigma * sigma))
