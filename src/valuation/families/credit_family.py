from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import clamp, f, infer_market_cap, sigmoid, variance_from_bounds


class CreditFamilyEngine:
    """
    Credit-implied equity family using structural-style proxies:
    - default_probability
    - credit_stress_score
    - credit_implied_equity_value
    """

    def run(self, core_df: pd.DataFrame) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for _, row in core_df.iterrows():
            ticker = row.get("ticker")
            market_cap = infer_market_cap(row)
            debt_equity = clamp(f(row.get("debt_equity"), 1.0), 0.0, 12.0)
            op_income = f(row.get("operating_income_ttm"), np.nan)
            interest = abs(f(row.get("interest_expense_ttm"), np.nan))
            if np.isfinite(op_income) and np.isfinite(interest) and interest > 0:
                coverage = clamp(op_income / interest, -5.0, 20.0)
            else:
                coverage = np.nan

            # Structural-style PD proxy: leverage up, coverage down => higher PD.
            cov_term = 0.0 if not np.isfinite(coverage) else -0.55 * coverage
            lev_term = 0.45 * debt_equity
            quality_term = -0.02 * f(row.get("earnings_quality_score_v2"), 50.0)
            logit = -2.20 + lev_term + cov_term + quality_term
            pd_default = clamp(sigmoid(logit), 0.001, 0.95)
            credit_stress = pd_default * 100.0

            credit_value = np.nan
            gap = np.nan
            variance = 1.0
            confidence = 0.25
            if np.isfinite(market_cap) and market_cap > 0:
                credit_value = market_cap * (1.0 - 0.65 * pd_default)
                gap = clamp((credit_value - market_cap) / market_cap, -2.0, 2.0)
                low = market_cap * (1.0 - 0.80 * pd_default)
                high = market_cap * (1.0 - 0.45 * pd_default)
                variance = variance_from_bounds(low, high)
                coverage_quality = 0.35 if not np.isfinite(coverage) else clamp((coverage + 2.0) / 8.0, 0.2, 0.95)
                confidence = clamp(0.35 + 0.45 * coverage_quality, 0.20, 0.90)

            rows.append(
                {
                    "ticker": ticker,
                    "credit_value": credit_value,
                    "credit_gap": gap,
                    "credit_variance": variance,
                    "credit_confidence": confidence,
                    "default_probability": pd_default,
                    "credit_stress_score": credit_stress,
                    "interest_coverage_proxy": coverage,
                }
            )
        return pd.DataFrame(rows)

