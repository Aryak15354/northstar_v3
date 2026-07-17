"""
Famous benchmark strategies — the yardsticks V3's alpha gets measured against.

While the alpha engine is still NIL and real edge is being hunted on Kaggle,
these canonical, literature-standard strategies act as honest benchmarks. Each
builds a `[ticker, Industry, weight]` target from the cross-sectional valuation
snapshot; the SAME PaperPortfolioEngine (₹100cr, full costs/taxes/caps/ADV)
then runs each one, so comparisons are apples-to-apples.

Strategies:
  * buffett          — wonderful businesses at fair prices: quality + moat +
                       margin-of-safety, penalised for leverage.
  * magic_formula    — Greenblatt: earnings yield (EBIT/EV) + return on capital.
  * piotroski        — financial-strength score (proxy from available fields).
  * graham_defensive — classic deep value: cheap on P/E & P/B with real earnings
                       and low debt.

All are long-only, top-N, score-weighted; the engine enforces position/sector
caps so no single pick can dominate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VALUATION = PROJECT_ROOT / "data" / "processed" / "valuation.parquet"


def _load() -> pd.DataFrame:
    df = pd.read_parquet(_VALUATION)
    if "ticker" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["sector"] = df.get("Industry", pd.Series(["Unknown"] * len(df))).fillna("Unknown")
    return df


def _z(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mu, sd = s.mean(), s.std(ddof=0)
    if not sd or sd < 1e-9:
        return pd.Series(0.0, index=series.index)
    return ((s - mu) / sd).clip(-4, 4).fillna(0.0)


def _rank_ascending(series: pd.Series) -> pd.Series:
    """Rank where LOW raw value = best (rank 1)."""
    return pd.to_numeric(series, errors="coerce").rank(method="min", na_option="bottom")


def _finalize(df: pd.DataFrame, score: pd.Series, top_n: int) -> pd.DataFrame:
    """Take top-N by score, weight ∝ score (shifted positive), sum to 1."""
    work = df.assign(_score=score).dropna(subset=["_score"])
    work = work[work["_score"] > -np.inf].sort_values("_score", ascending=False).head(top_n)
    if work.empty:
        return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    w = work["_score"] - work["_score"].min() + 1e-6
    weight = w / w.sum()
    return pd.DataFrame({
        "ticker": work["ticker"].values,
        "Industry": work["sector"].values,
        "weight": weight.values,
    })


# --------------------------------------------------------------------------- #
# strategy constructors
# --------------------------------------------------------------------------- #
def buffett(top_n: int = 30) -> pd.DataFrame:
    df = _load()
    if df.empty:
        return df
    quality = (_z(df.get("buffett_quality_score", df.get("roe")))
               + _z(df.get("moat_score_v2", 0))
               + _z(df.get("roe", 0)))
    value = _z(df.get("margin_of_safety_pct", df.get("owner_earnings_yield_v2", 0)))
    leverage_penalty = _z(df.get("debt_equity", 0))
    # gate to real earnings
    score = 0.5 * quality + 0.4 * value - 0.3 * leverage_penalty
    score = score.where(pd.to_numeric(df.get("net_income", 1), errors="coerce").fillna(0) > 0, -np.inf)
    return _finalize(df, score, top_n)


def magic_formula(top_n: int = 30) -> pd.DataFrame:
    df = _load()
    if df.empty:
        return df
    # earnings yield ≈ EBIT/EV, proxied by 1/ev_ebitda (higher = cheaper)
    ev_ebitda = pd.to_numeric(df.get("ev_ebitda"), errors="coerce")
    earnings_yield = 1.0 / ev_ebitda.where(ev_ebitda > 0)
    roc = pd.to_numeric(df.get("adjusted_roic_v2", df.get("roe")), errors="coerce")
    # Greenblatt: sum of the two ranks (best combined = highest), so rank each descending
    ey_rank = earnings_yield.rank(method="min", ascending=False)
    roc_rank = roc.rank(method="min", ascending=False)
    combined = ey_rank + roc_rank                    # lower is better
    score = -combined                                 # flip so higher = better
    score = score.where(pd.to_numeric(df.get("net_income", 1), errors="coerce").fillna(0) > 0, -np.inf)
    return _finalize(df, score, top_n)


def piotroski(top_n: int = 30) -> pd.DataFrame:
    """Financial-strength proxy from available fields (a full 9-point F-score
    needs YoY panel deltas; here we score the strength signals we have)."""
    df = _load()
    if df.empty:
        return df
    ni = pd.to_numeric(df.get("net_income"), errors="coerce")
    fcf_yield = pd.to_numeric(df.get("fcf_yield"), errors="coerce")
    roe = pd.to_numeric(df.get("roe"), errors="coerce")
    de = pd.to_numeric(df.get("debt_equity"), errors="coerce")
    eq = pd.to_numeric(df.get("earnings_quality_score_v2"), errors="coerce")
    points = (
        (ni > 0).astype(float)
        + (fcf_yield > 0).astype(float)
        + (roe > 0.12).astype(float)
        + (de < 0.6).astype(float)
        + (eq > eq.median()).astype(float)
        + (fcf_yield > roe / 100.0).astype(float)   # cash-backed earnings
    )
    score = points + 0.001 * _z(roe)                 # tie-break by quality
    score = score.where(ni.fillna(0) > 0, -np.inf)
    return _finalize(df, score, top_n)


def graham_defensive(top_n: int = 30) -> pd.DataFrame:
    df = _load()
    if df.empty:
        return df
    pe = pd.to_numeric(df.get("pe"), errors="coerce")
    pb = pd.to_numeric(df.get("pb"), errors="coerce")
    ni = pd.to_numeric(df.get("net_income"), errors="coerce")
    de = pd.to_numeric(df.get("debt_equity"), errors="coerce")
    # classic Graham: positive earnings, low P/E, low P/B, moderate leverage,
    # and the P/E×P/B "Graham number" screen (< 22.5 is the textbook threshold)
    graham_number = pe * pb
    cheap = -_z(pe) - _z(pb) - 0.3 * _z(de)
    score = cheap.where(
        (ni.fillna(-1) > 0) & (pe > 0) & (pb > 0) & (graham_number < 40),
        -np.inf,
    )
    return _finalize(df, score, top_n)


STRATEGIES: dict[str, Callable[[int], pd.DataFrame]] = {
    "buffett": buffett,
    "magic_formula": magic_formula,
    "piotroski": piotroski,
    "graham_defensive": graham_defensive,
}
