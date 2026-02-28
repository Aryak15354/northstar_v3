"""Capital allocation simulation and risk-of-ruin diagnostics."""

from __future__ import annotations

from typing import Dict

import numpy as np


class CapitalSimulator:
    def __init__(self, initial_capital: float = 1_000_000.0):
        self.initial_capital = float(initial_capital)

    def simulate(
        self,
        strategy_returns: np.ndarray,
        allocation_rule: str = "fractional_kelly",
        fraction: float = 0.25,
    ) -> Dict[str, float]:
        r = np.asarray(strategy_returns, dtype=float).reshape(-1)
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
        base_w = float(np.clip(kelly * fraction, -0.50, 0.50)) if allocation_rule == "fractional_kelly" else float(fraction)

        for x in r:
            w = float(np.clip(base_w, -0.50, 0.50))
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
        }
