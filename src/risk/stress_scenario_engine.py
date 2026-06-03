"""
Historical crisis stress scenarios and gap-risk estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping

import numpy as np


@dataclass
class StressScenario:
    name: str
    spot_move_sigma: float
    iv_shock: float
    vol_of_vol_shock: float


DEFAULT_SCENARIOS = [
    StressScenario("2008_crisis", -3.5, 0.60, 0.80),
    StressScenario("2018_volmageddon", -2.2, 0.45, 0.70),
    StressScenario("2020_covid", -4.0, 0.90, 1.10),
    StressScenario("2022_inflation", -2.8, 0.40, 0.55),
]


class StressScenarioEngine:
    def __init__(self, scenarios: List[StressScenario] | None = None) -> None:
        self.scenarios = scenarios or DEFAULT_SCENARIOS

    def evaluate(
        self,
        *,
        delta: float,
        gamma: float,
        vega: float,
        theta: float,
        portfolio_value: float,
        spot_sigma: float,
    ) -> Dict[str, object]:
        results: List[Dict[str, float | str]] = []
        for scenario in self.scenarios:
            move = scenario.spot_move_sigma * spot_sigma
            pnl_delta = delta * move
            pnl_gamma = 0.5 * gamma * (move ** 2)
            pnl_vega = vega * scenario.iv_shock
            pnl_theta = theta * 1.0
            total = float(pnl_delta + pnl_gamma + pnl_vega + pnl_theta)
            results.append(
                {
                    "scenario": scenario.name,
                    "spot_move_sigma": float(scenario.spot_move_sigma),
                    "pnl": total,
                    "pnl_pct": float(total / max(1e-8, portfolio_value)),
                }
            )

        pnl_values = np.asarray([float(row["pnl"]) for row in results], dtype=float)
        tail_loss = float(np.quantile(pnl_values, 0.10)) if pnl_values.size else 0.0
        gap_loss = float(min(0.0, tail_loss))
        gap_risk_score = float(np.clip(abs(gap_loss) / max(1.0, portfolio_value), 0.0, 2.0))
        return {
            "scenarios": results,
            "tail_loss_p10": tail_loss,
            "gap_risk_score": gap_risk_score,
        }
