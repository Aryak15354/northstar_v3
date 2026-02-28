from __future__ import annotations

from math import erf, exp, log, sqrt
from typing import Any

import numpy as np
import pandas as pd

from .common import clamp, f, infer_market_cap, variance_from_bounds


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


class RealOptionsFamilyEngine:
    """
    Real-options overlay using a Black-Scholes style optionality proxy.
    Adjusted value = base intrinsic anchor + option premium.
    """

    def __init__(self, risk_free_rate: float = 0.07, horizon_years: float = 2.0) -> None:
        self.risk_free_rate = float(risk_free_rate)
        self.horizon_years = float(max(0.5, horizon_years))

    def _option_premium(self, s: float, k: float, sigma: float, t: float, r: float) -> float:
        if s <= 0 or k <= 0 or sigma <= 0 or t <= 0:
            return 0.0
        d1 = (log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
        d2 = d1 - sigma * sqrt(t)
        call = s * _norm_cdf(d1) - k * exp(-r * t) * _norm_cdf(d2)
        return max(0.0, call)

    def run(self, core_df: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for _, row in core_df.iterrows():
            ticker = row.get("ticker")
            market_cap = infer_market_cap(row)
            base_intrinsic = f(row.get("intrinsic_value_estimate"), np.nan)
            if not np.isfinite(base_intrinsic) and np.isfinite(market_cap):
                base_intrinsic = market_cap
            growth = clamp(f(row.get("revenue_growth"), 0.02), -0.10, 0.30)
            quality = clamp(f(row.get("buffett_quality_score"), 50.0) / 100.0, 0.0, 1.0)
            # Volatility proxy: higher with lower earnings stability and high growth.
            earnings_stability = clamp(f(row.get("earnings_stability_raw"), 0.5), 0.0, 1.0)
            sigma = clamp(0.20 + 0.35 * max(0.0, growth) + 0.25 * (1.0 - earnings_stability), 0.10, 0.90)
            s = max(base_intrinsic, 1.0)
            k = s * (1.0 + clamp(0.10 - 0.08 * quality, 0.02, 0.20))
            premium = self._option_premium(s=s, k=k, sigma=sigma, t=self.horizon_years, r=self.risk_free_rate)
            premium = clamp(premium, 0.0, 0.40 * s)
            adjusted_value = s + premium

            gap = np.nan
            if np.isfinite(market_cap) and market_cap > 0:
                gap = clamp((adjusted_value - market_cap) / market_cap, -2.0, 2.0)
            low = adjusted_value * 0.87
            high = adjusted_value * 1.13
            variance = variance_from_bounds(low, high)
            confidence = clamp(0.30 + 0.55 * quality, 0.20, 0.90)
            rows.append(
                {
                    "ticker": ticker,
                    "real_option_value": adjusted_value,
                    "real_option_gap": gap,
                    "real_option_variance": variance,
                    "real_option_confidence": confidence,
                    "real_option_premium": premium,
                }
            )
        return pd.DataFrame(rows)

