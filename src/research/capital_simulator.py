"""Capital allocation simulation and risk-of-ruin diagnostics."""

from __future__ import annotations

from typing import Dict

import numpy as np


class CapitalSimulator:
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        max_abs_period_return: float = 0.25,
        max_abs_weight: float = 0.35,
    ):
        self.initial_capital = float(initial_capital)
        self.max_abs_period_return = float(max(0.01, min(1.0, max_abs_period_return)))
        self.max_abs_weight = float(max(0.05, min(0.75, max_abs_weight)))

    def simulate(
        self,
        strategy_returns: np.ndarray,
        allocation_rule: str = "fractional_kelly",
        fraction: float = 0.25,
    ) -> Dict[str, float]:
        r = np.asarray(strategy_returns, dtype=float).reshape(-1)
        r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
        r = np.clip(r, -self.max_abs_period_return, self.max_abs_period_return)
        if len(r) == 0:
            return {
                "final_capital": self.initial_capital,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "risk_of_ruin": 0.0,
                "turnover_proxy": 0.0,
            }

        capital = self.initial_capital
        curve = []
        weights = []

        mu = float(np.mean(r))
        var = float(np.var(r))
        kelly = mu / (var + 1e-12)
        base_w = (
            float(np.clip(kelly * fraction, -self.max_abs_weight, self.max_abs_weight))
            if allocation_rule == "fractional_kelly"
            else float(np.clip(fraction, -self.max_abs_weight, self.max_abs_weight))
        )

        for x in r:
            w = float(np.clip(base_w, -self.max_abs_weight, self.max_abs_weight))
            capital *= float(1.0 + w * x)
            curve.append(capital)
            weights.append(w)

        curve = np.asarray(curve, dtype=float)
        peaks = np.maximum.accumulate(curve)
        dd = curve / np.maximum(peaks, 1e-12) - 1.0
        max_dd = float(abs(np.min(dd)))

        # Crude risk-of-ruin proxy from path endpoint distribution assumption.
        ruin_threshold = 0.70 * self.initial_capital
        risk_of_ruin = float(np.mean(curve <= ruin_threshold))
        turnover = float(np.mean(np.abs(np.diff(np.asarray(weights, dtype=float))))) if len(weights) > 1 else 0.0

        return {
            "final_capital": float(curve[-1]),
            "total_return": float(curve[-1] / self.initial_capital - 1.0),
            "max_drawdown": max_dd,
            "risk_of_ruin": risk_of_ruin,
            "turnover_proxy": turnover,
            "avg_weight": float(np.mean(weights)),
            "clipped_return_limit": float(self.max_abs_period_return),
            "max_abs_weight": float(self.max_abs_weight),
        }
