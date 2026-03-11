"""Exploration/exploitation governor for strategic layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass(frozen=True)
class ExplorationDecision:
    exploration_rate: float
    research_budget_multiplier: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "exploration_rate": float(self.exploration_rate),
            "research_budget_multiplier": float(self.research_budget_multiplier),
        }


class ExplorationGovernor:
    def __init__(self, *, base_exploration: float = 0.20, decay_alpha: float = 1.25):
        self.base_exploration = float(np.clip(base_exploration, 0.01, 0.60))
        self.decay_alpha = float(max(0.01, decay_alpha))

    def decide(
        self,
        *,
        system_stability_index: float,
        capital_growth_rate: float,
    ) -> ExplorationDecision:
        stability = float(np.clip(system_stability_index, 0.0, 1.0))
        instability = 1.0 - stability
        eps = float(self.base_exploration * np.exp(-self.decay_alpha * instability))
        eps = float(np.clip(eps, 0.03, 0.45))

        growth = float(np.clip(capital_growth_rate, -0.50, 1.00))
        budget_mult = float(np.clip(0.85 + (0.30 * growth) + (0.20 * stability), 0.60, 1.25))

        return ExplorationDecision(
            exploration_rate=eps,
            research_budget_multiplier=budget_mult,
        )
