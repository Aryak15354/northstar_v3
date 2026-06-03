"""Adaptive strategic objective reweighting for Phase 10."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass(frozen=True)
class ObjectiveWeights:
    lambda_return: float
    lambda_variance: float
    lambda_fragility: float
    lambda_drawdown: float
    strategic_multiplier: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "lambda_return": float(self.lambda_return),
            "lambda_variance": float(self.lambda_variance),
            "lambda_fragility": float(self.lambda_fragility),
            "lambda_drawdown": float(self.lambda_drawdown),
            "strategic_multiplier": float(self.strategic_multiplier),
        }


class ObjectiveReweighter:
    """Maps stability/regime/capital scale into dynamic utility weights."""

    def reweight(
        self,
        *,
        system_stability_index: float,
        regime_entropy: float,
        capital_scale: float,
    ) -> ObjectiveWeights:
        stability = float(np.clip(system_stability_index, 0.0, 1.0))
        entropy = float(np.clip(regime_entropy, 0.0, 1.5))
        scale = float(np.clip(capital_scale, 0.0, 1.0))

        instability = 1.0 - stability
        risk_mode = float(np.clip((0.55 * instability) + (0.30 * entropy) + (0.15 * scale), 0.0, 1.0))

        lam_return = float(np.clip(1.15 - (0.60 * risk_mode), 0.45, 1.30))
        lam_var = float(np.clip(0.85 + (1.20 * risk_mode), 0.70, 2.40))
        lam_frag = float(np.clip(0.80 + (1.10 * risk_mode), 0.70, 2.20))
        lam_dd = float(np.clip(0.75 + (1.05 * risk_mode), 0.65, 2.10))

        strategic = float(np.clip(lam_return / max(1e-6, 0.55 * lam_var + 0.45 * lam_frag), 0.60, 1.25))
        return ObjectiveWeights(
            lambda_return=lam_return,
            lambda_variance=lam_var,
            lambda_fragility=lam_frag,
            lambda_drawdown=lam_dd,
            strategic_multiplier=strategic,
        )
