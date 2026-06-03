from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.valuation.families.common import clamp, f, sigmoid


@dataclass
class PortfolioState:
    date: pd.Timestamp
    market_percentile: float
    sector_dispersion: float
    aggregate_gap_mean: float
    aggregate_gap_std: float
    bubble_probability: float
    valuation_regime: str


class PortfolioValuationStateEngine:
    """
    Portfolio-level valuation regime diagnostics.
    """

    @staticmethod
    def _classify_regime(market_percentile: float, gap_mean: float, bubble_probability: float) -> str:
        if bubble_probability >= 0.70:
            return "bubble_risk"
        if market_percentile >= 0.75 and gap_mean < 0:
            return "overvalued"
        if market_percentile <= 0.25 and gap_mean > 0:
            return "deep_value"
        return "balanced"

    def compute(
        self,
        posterior_df: pd.DataFrame,
        families_df: pd.DataFrame,
        macro_state_df: pd.DataFrame | None = None,
        industry_col: str = "Industry",
    ) -> pd.DataFrame:
        if posterior_df.empty:
            now = pd.Timestamp.utcnow()
            return pd.DataFrame(
                [
                    {
                        "date": now,
                        "market_percentile": np.nan,
                        "sector_dispersion": np.nan,
                        "aggregate_gap_mean": np.nan,
                        "aggregate_gap_std": np.nan,
                        "bubble_probability": np.nan,
                        "valuation_regime": "unknown",
                    }
                ]
            )

        merged = posterior_df.merge(
            families_df[["ticker", industry_col]].drop_duplicates(),
            on="ticker",
            how="left",
        )
        gaps = pd.to_numeric(merged.get("posterior_gap"), errors="coerce")
        gap_mean = float(gaps.mean()) if gaps.notna().any() else np.nan
        gap_std = float(gaps.std()) if gaps.notna().any() else np.nan

        if industry_col in merged.columns and gaps.notna().any():
            tmp = merged[[industry_col, "posterior_gap"]].copy()
            tmp["posterior_gap"] = pd.to_numeric(tmp["posterior_gap"], errors="coerce")
            sector_std = tmp.groupby(industry_col)["posterior_gap"].std().replace([np.inf, -np.inf], np.nan).dropna()
            sector_dispersion = float(sector_std.mean()) if not sector_std.empty else float(gap_std if np.isfinite(gap_std) else 0.0)
        else:
            sector_dispersion = float(gap_std if np.isfinite(gap_std) else np.nan)

        market_percentile = np.nan
        if macro_state_df is not None and not macro_state_df.empty:
            market_percentile = f(macro_state_df.iloc[-1].get("macro_valuation_percentile"), np.nan)
        if not np.isfinite(market_percentile):
            # fallback from valuation distribution if macro state missing
            market_percentile = clamp(float((gaps < 0).mean()) if gaps.notna().any() else 0.5, 0.01, 0.99)

        bubble_logit = 5.0 * (market_percentile - 0.70) + 3.5 * max(0.0, -f(gap_mean, 0.0))
        bubble_probability = clamp(sigmoid(bubble_logit), 0.01, 0.99)
        regime = self._classify_regime(market_percentile, f(gap_mean, 0.0), bubble_probability)

        date = pd.to_datetime(posterior_df.get("date"), errors="coerce").max()
        if pd.isna(date):
            date = pd.Timestamp.utcnow()
        state = PortfolioState(
            date=date,
            market_percentile=market_percentile,
            sector_dispersion=float(sector_dispersion) if np.isfinite(sector_dispersion) else np.nan,
            aggregate_gap_mean=float(gap_mean) if np.isfinite(gap_mean) else np.nan,
            aggregate_gap_std=float(gap_std) if np.isfinite(gap_std) else np.nan,
            bubble_probability=bubble_probability,
            valuation_regime=regime,
        )
        return pd.DataFrame(
            [
                {
                    "date": state.date,
                    "market_percentile": state.market_percentile,
                    "sector_dispersion": state.sector_dispersion,
                    "aggregate_gap_mean": state.aggregate_gap_mean,
                    "aggregate_gap_std": state.aggregate_gap_std,
                    "bubble_probability": state.bubble_probability,
                    "valuation_regime": state.valuation_regime,
                }
            ]
        )

