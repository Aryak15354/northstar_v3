from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .common import clamp, f, sigmoid


@dataclass
class MacroValuationState:
    date: pd.Timestamp
    macro_valuation_percentile: float
    macro_valuation_state: str
    macro_risk_adjustment_factor: float
    market_pe_median: float
    market_pb_median: float
    market_fcf_yield_median: float


class MacroValuationFamilyEngine:
    """
    Top-down market valuation overlay.
    This is a market/portfolio-level state projected onto each ticker.
    """

    def __init__(self, alpha: float = 0.80) -> None:
        self.alpha = float(alpha)

    def compute_state(self, core_df: pd.DataFrame) -> MacroValuationState:
        work = core_df.copy()
        market_pe = float(pd.to_numeric(work.get("pe"), errors="coerce").replace([np.inf, -np.inf], np.nan).median())
        market_pb = float(pd.to_numeric(work.get("pb"), errors="coerce").replace([np.inf, -np.inf], np.nan).median())
        market_fcf = float(pd.to_numeric(work.get("fcf_yield"), errors="coerce").replace([np.inf, -np.inf], np.nan).median())

        # Coarse macro valuation score proxy (higher means more expensive).
        pe_z = np.log(max(market_pe, 1.0) / 18.0)
        pb_z = np.log(max(market_pb, 0.5) / 2.5)
        fcf_z = -((market_fcf - 0.03) / 0.04)  # low FCF yield -> expensive
        score = 0.45 * pe_z + 0.35 * pb_z + 0.20 * fcf_z

        percentile = clamp(sigmoid(score), 0.01, 0.99)
        # Compression factor C = 1 - alpha (M - 0.5)
        compress = clamp(1.0 - self.alpha * (percentile - 0.5), 0.60, 1.40)

        if percentile >= 0.80:
            regime = "overvalued"
        elif percentile <= 0.20:
            regime = "undervalued"
        else:
            regime = "neutral"

        date = pd.to_datetime(work.get("date"), errors="coerce").max()
        if pd.isna(date):
            date = pd.Timestamp.utcnow()
        return MacroValuationState(
            date=date,
            macro_valuation_percentile=percentile,
            macro_valuation_state=regime,
            macro_risk_adjustment_factor=compress,
            market_pe_median=market_pe if np.isfinite(market_pe) else np.nan,
            market_pb_median=market_pb if np.isfinite(market_pb) else np.nan,
            market_fcf_yield_median=market_fcf if np.isfinite(market_fcf) else np.nan,
        )

    def annotate(self, core_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        state = self.compute_state(core_df)
        per_ticker = pd.DataFrame(
            {
                "ticker": core_df["ticker"].astype(str),
                "macro_percentile": state.macro_valuation_percentile,
                "macro_adjustment_factor": state.macro_risk_adjustment_factor,
                "macro_valuation_state": state.macro_valuation_state,
            }
        )
        state_df = pd.DataFrame(
            [
                {
                    "date": state.date,
                    "macro_valuation_percentile": state.macro_valuation_percentile,
                    "macro_valuation_state": state.macro_valuation_state,
                    "macro_risk_adjustment_factor": state.macro_risk_adjustment_factor,
                    "market_pe_median": state.market_pe_median,
                    "market_pb_median": state.market_pb_median,
                    "market_fcf_yield_median": state.market_fcf_yield_median,
                }
            ]
        )
        return per_ticker, state_df

