"""Risk classification engine — assigns each scored name a portfolio ROLE.

Rewritten 2026-07 to fix three defects found in the forensic audit:

1. SCALE BUG (critical): classify() compared `northstar_score` against 70/60,
   assuming a 0–100 scale. The live scorer emits a cross-sectional Z-SCORE
   (range ≈ [-3, +2]), so `> 70` was never true and virtually every name fell
   through to "Avoid" (output was 468 Avoid + 32 Speculative, zero
   Safe/Income/Directional). Classification is now percentile-based and thus
   scale-independent.

2. STALE INPUT: realized_vol / volatility_regime were read from
   data/processed/volatility_state.parquet, which had been frozen since
   2025-12-28. Volatility is now recomputed fresh from the price panel each run.

3. RUN-AT-IMPORT: the whole pipeline executed at module import time (module-level
   side effects). It is now wrapped in build_stock_roles()/main() behind a
   __main__ guard.

Output (unchanged schema): data/processed/stock_roles.parquet with columns
ticker, Industry, stock_role, northstar_score, realized_vol, volatility_regime.
Guarded by scripts/ci/check_live_artifact_invariants.py::stock_roles_nondegenerate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCORES = PROJECT_ROOT / "data/processed/scores.parquet"
PRICES = PROJECT_ROOT / "data/processed/prices.parquet"
OUT = PROJECT_ROOT / "data/processed/stock_roles.parquet"

# Trading days used to estimate trailing realized volatility.
_VOL_WINDOW = 63
_TRADING_DAYS = 252


def _realized_vol_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Trailing annualized realized volatility per ticker, from the price panel."""
    px = prices.copy()
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    px = px.dropna(subset=["Date", "ticker", "Close"]).sort_values(["ticker", "Date"])
    px["ret"] = px.groupby("ticker")["Close"].pct_change()

    def _vol(returns: pd.Series) -> float:
        tail = returns.dropna().tail(_VOL_WINDOW)
        if len(tail) < 10:
            return np.nan
        return float(tail.std(ddof=0) * np.sqrt(_TRADING_DAYS))

    vol = px.groupby("ticker")["ret"].apply(_vol).reset_index()
    vol.columns = ["ticker", "realized_vol"]
    return vol


def _avg_volume_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    px = prices.copy()
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    px = px.dropna(subset=["Date", "ticker"]).sort_values(["ticker", "Date"])
    liq = px.groupby("ticker").tail(30).groupby("ticker")["Volume"].mean().reset_index()
    liq.columns = ["ticker", "avg_volume"]
    return liq


def build_stock_roles() -> pd.DataFrame:
    scores = pd.read_parquet(SCORES)
    prices = pd.read_parquet(PRICES, columns=["Date", "ticker", "Close", "Volume"])

    vol = _realized_vol_from_prices(prices)
    liq = _avg_volume_from_prices(prices)

    df = scores.merge(vol, on="ticker", how="left").merge(liq, on="ticker", how="left")

    score_col = "northstar_score" if "northstar_score" in df.columns else "final_score"
    df["_score_pct"] = pd.to_numeric(df[score_col], errors="coerce").rank(pct=True)
    df["_vol_pct"] = pd.to_numeric(df["realized_vol"], errors="coerce").rank(pct=True)

    # Cross-sectional volatility regime (scale-independent, fresh each run).
    df["volatility_regime"] = np.where(
        df["_vol_pct"] >= 0.66, "High",
        np.where(df["_vol_pct"] <= 0.33, "Low", "Medium"),
    )

    def classify(row) -> str:
        sp = row["_score_pct"]
        if pd.isna(sp):
            return "Avoid"
        high_vol = row["volatility_regime"] == "High"
        if high_vol:
            # In a high-vol name, only the strongest scores are worth directional risk.
            return "Directional" if sp >= 0.70 else "Speculative"
        # Low/medium vol: the calmest high-quality names are core holdings.
        if sp >= 0.85:
            return "Income"
        if sp >= 0.50:
            return "Safe"
        return "Avoid"

    df["stock_role"] = df.apply(classify, axis=1)

    cols = ["ticker", "Industry", "stock_role", "northstar_score", "realized_vol", "volatility_regime"]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df[cols].copy()


def main() -> int:
    print("🛡 Building Risk Classification Engine...")
    out = build_stock_roles()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    dist = out["stock_role"].value_counts().to_dict()
    print(f"✅ Risk Classification built: {len(out)} stocks → {dist}")
    print(f"📁 Saved to {OUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
