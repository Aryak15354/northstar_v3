"""Rolling decay estimator for alpha edge half-life."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Any, Dict, Iterable

import numpy as np


@dataclass(frozen=True)
class AlphaDecayResult:
    decay_lambda: float
    half_life_days: float
    lambda_norm: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decay_lambda": float(self.decay_lambda),
            "half_life_days": float(self.half_life_days),
            "lambda_norm": float(self.lambda_norm),
        }


class AlphaDecayEstimator:
    def __init__(self, *, eps: float = 1e-8, min_history: int = 12):
        self.eps = float(max(1e-12, eps))
        self.min_history = int(max(5, min_history))

    def estimate(
        self,
        *,
        edge_history: Iterable[float],
        baseline_lambda: float = 0.01,
    ) -> AlphaDecayResult:
        values = np.asarray(list(edge_history or []), dtype=float)
        values = values[np.isfinite(values)]
        if values.size < self.min_history:
            lam = float(max(0.0, baseline_lambda))
            half_life = float(log(2.0) / max(lam, self.eps)) if lam > 0.0 else float("inf")
            return AlphaDecayResult(decay_lambda=lam, half_life_days=half_life, lambda_norm=1.0)

        mags = np.abs(values)
        mags = np.maximum(mags, self.eps)
        y = np.log(mags)
        x = np.arange(len(y), dtype=float)
        try:
            slope, _intercept = np.polyfit(x, y, 1)
            lam = float(max(0.0, -slope))
        except Exception:
            lam = float(max(0.0, baseline_lambda))

        base = float(max(self.eps, baseline_lambda))
        lambda_norm = float(lam / base)
        if lam <= self.eps:
            half_life = float("inf")
        else:
            half_life = float(log(2.0) / lam)

        return AlphaDecayResult(
            decay_lambda=lam,
            half_life_days=half_life,
            lambda_norm=lambda_norm,
        )
