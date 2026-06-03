"""
Volatility carry forecasting utilities.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np


class VolCarryForecaster:
    def forecast(
        self,
        *,
        implied_vol: float,
        expected_realized_vol: float,
        term_slope: float,
        skew_decay: float,
        seasonality_score: float = 0.0,
    ) -> Dict[str, float]:
        implied_var = float(implied_vol) ** 2
        realized_var = float(expected_realized_vol) ** 2
        raw_carry = implied_var - realized_var
        carry_score = raw_carry * (1.0 + 0.6 * term_slope) + 0.15 * skew_decay + 0.10 * seasonality_score
        conviction = float(np.clip(abs(carry_score) / max(1e-6, implied_var), 0.0, 1.0))
        return {
            "implied_variance": implied_var,
            "expected_realized_variance": realized_var,
            "raw_carry": raw_carry,
            "carry_score": float(carry_score),
            "conviction": conviction,
        }
