from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import clamp, confidence_from_spread, f, infer_market_cap, variance_from_bounds


class ResidualIncomeFamilyEngine:
    """
    Residual-income family:
    - Clean-surplus residual income
    - Abnormal earnings growth proxy (financial-friendly fallback)
    """

    def __init__(self, risk_free_rate: float = 0.07, equity_risk_premium: float = 0.06) -> None:
        self.risk_free_rate = float(risk_free_rate)
        self.equity_risk_premium = float(equity_risk_premium)

    def _cost_of_equity(self, row: pd.Series) -> float:
        quality = clamp(f(row.get("buffett_quality_score"), 50.0) / 100.0, 0.0, 1.0)
        adjustment = (0.5 - quality) * 0.03
        return clamp(self.risk_free_rate + self.equity_risk_premium + adjustment, 0.08, 0.18)

    def _clean_surplus_value(self, row: pd.Series) -> tuple[float, float, float]:
        equity = f(row.get("equity"), np.nan)
        net_income = f(row.get("net_income_ttm"), np.nan)
        if not (np.isfinite(equity) and np.isfinite(net_income) and equity > 0):
            return np.nan, np.nan, np.nan

        r = self._cost_of_equity(row)
        roe = clamp(net_income / max(equity, 1e-6), -0.20, 0.40)
        growth = clamp(f(row.get("revenue_growth"), 0.02), -0.05, 0.15)
        years = 8
        bv = equity
        value = equity
        for t in range(1, years + 1):
            roe_t = roe * (1.0 - 0.05 * t)
            ri = (roe_t - r) * bv
            value += ri / ((1.0 + r) ** t)
            # Clean-surplus dynamics with conservative retention assumption.
            retention = clamp(0.65 - 0.2 * growth, 0.30, 0.85)
            bv = bv + net_income * retention

        terminal_ri = (roe * 0.6 - r) * bv
        if r > 0.01:
            terminal = terminal_ri / max(r - 0.01, 0.01)
            value += terminal / ((1.0 + r) ** years)

        low = value * 0.85
        high = value * 1.15
        return value, low, high

    def _abnormal_earnings_growth_value(self, row: pd.Series) -> tuple[float, float, float]:
        """
        Simplified abnormal earnings growth (AEG) proxy.
        Useful fallback for financials where FCF-based DCF can be unstable.
        """
        equity = f(row.get("equity"), np.nan)
        net_income = f(row.get("net_income_ttm"), np.nan)
        if not (np.isfinite(equity) and np.isfinite(net_income) and equity > 0):
            return np.nan, np.nan, np.nan

        r = self._cost_of_equity(row)
        eps_growth = clamp(f(row.get("revenue_growth"), 0.03), -0.03, 0.18)
        ni = net_income
        value = equity
        for t in range(1, 7):
            ni_next = ni * (1.0 + eps_growth * (1.0 - 0.1 * t))
            aeg = (ni_next - ni) - r * ni
            value += aeg / ((1.0 + r) ** t)
            ni = ni_next
        low = value * 0.82
        high = value * 1.18
        return value, low, high

    def run(self, core_df: pd.DataFrame) -> pd.DataFrame:
        out: list[dict[str, Any]] = []
        for _, row in core_df.iterrows():
            ticker = row.get("ticker")
            market_cap = infer_market_cap(row)
            residual_value, residual_low, residual_high = self._clean_surplus_value(row)
            aeg_value, aeg_low, aeg_high = self._abnormal_earnings_growth_value(row)

            # Blend RI and AEG with sector-sensitive emphasis.
            is_fin = bool(str(row.get("Industry", "")).lower().find("financial") >= 0 or bool(row.get("is_financial", False)))
            residual_valid = np.isfinite(residual_value)
            aeg_valid = np.isfinite(aeg_value)

            if residual_valid and aeg_valid:
                if is_fin:
                    value = residual_value * 0.35 + aeg_value * 0.65
                    low = residual_low * 0.35 + aeg_low * 0.65
                    high = residual_high * 0.35 + aeg_high * 0.65
                else:
                    value = (residual_value + aeg_value) / 2.0
                    low = (residual_low + aeg_low) / 2.0
                    high = (residual_high + aeg_high) / 2.0
            elif residual_valid:
                value, low, high = residual_value, residual_low, residual_high
            elif aeg_valid:
                value, low, high = aeg_value, aeg_low, aeg_high
            else:
                value, low, high = np.nan, np.nan, np.nan

            if not np.isfinite(value):
                out.append(
                    {
                        "ticker": ticker,
                        "residual_value": np.nan,
                        "residual_gap": np.nan,
                        "residual_variance": 1.0,
                        "residual_confidence": 0.20,
                    }
                )
                continue

            spread_ratio = (high - low) / max(abs(value), 1.0) if np.isfinite(low) and np.isfinite(high) else 1.0
            confidence = confidence_from_spread(spread_ratio, base=0.69)
            variance = variance_from_bounds(low, high)
            gap = np.nan
            if np.isfinite(market_cap) and market_cap > 0:
                gap = clamp((value - market_cap) / market_cap, -2.0, 2.0)
            out.append(
                {
                    "ticker": ticker,
                    "residual_value": value,
                    "residual_gap": gap,
                    "residual_variance": variance,
                    "residual_confidence": confidence,
                }
            )
        return pd.DataFrame(out)
