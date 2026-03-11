"""Alpha Lab robustness perturbation checks."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np


class RobustnessTester:
    """Deterministic perturbation scoring for walk-forward aggregate metrics."""

    def __init__(self, perturb_scales: Iterable[float] | None = None):
        self.perturb_scales = list(perturb_scales or (0.8, 1.0, 1.2))

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def score(self, aggregate_metrics: Dict[str, Any]) -> Dict[str, float]:
        sharpe = self._safe_float(aggregate_metrics.get("avg_sharpe", 0.0))
        dd = self._safe_float(aggregate_metrics.get("avg_max_drawdown", 0.0))
        turnover = self._safe_float(aggregate_metrics.get("avg_turnover", 0.0))
        stressed_scores: List[float] = []

        for scale in self.perturb_scales:
            st_sharpe = sharpe * float(scale)
            st_dd = dd * float(2.0 - min(1.5, scale))
            st_turnover = turnover * float(1.5 if scale < 1.0 else scale)
            # deterministic utility proxy under shock
            utility = st_sharpe - (0.60 * st_dd) - (0.10 * st_turnover)
            stressed_scores.append(float(utility))

        mean_u = float(np.mean(stressed_scores)) if stressed_scores else 0.0
        std_u = float(np.std(stressed_scores)) if stressed_scores else 0.0
        if abs(mean_u) > 1e-9:
            robustness = 1.0 - (std_u / abs(mean_u))
        else:
            robustness = 0.0
        robustness = float(np.clip(robustness, 0.0, 1.0))

        return {
            "robustness_score": robustness,
            "mean_utility": mean_u,
            "std_utility": std_u,
        }

