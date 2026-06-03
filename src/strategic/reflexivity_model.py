"""Capital-scale reflexivity model for decay-aware sizing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass(frozen=True)
class ReflexivityDecision:
    decay_lambda: float
    reflexivity_multiplier: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "decay_lambda": float(self.decay_lambda),
            "reflexivity_multiplier": float(self.reflexivity_multiplier),
        }


class ReflexivityModel:
    """Models lambda_decay(C) = lambda0 + alpha * C^beta."""

    def __init__(self, *, lambda0: float = 0.02, alpha: float = 0.10, beta: float = 1.30):
        self.lambda0 = float(max(0.0, lambda0))
        self.alpha = float(max(0.0, alpha))
        self.beta = float(max(1.0, beta))

    def evaluate(
        self,
        *,
        capital_scale: float,
        base_decay: float,
        mortality_sensitivity: float = 1.0,
    ) -> ReflexivityDecision:
        c = float(np.clip(capital_scale, 0.0, 2.0))
        decay_lambda = float(max(0.0, base_decay) + self.lambda0 + (self.alpha * (c**self.beta)))
        sens = float(np.clip(mortality_sensitivity, 0.25, 3.0))
        multiplier = float(np.clip(np.exp(-sens * decay_lambda), 0.55, 1.0))
        return ReflexivityDecision(decay_lambda=decay_lambda, reflexivity_multiplier=multiplier)
