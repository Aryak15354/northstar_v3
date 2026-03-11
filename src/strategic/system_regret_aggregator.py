"""Phase 10 system-level regret aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

import numpy as np


@dataclass(frozen=True)
class SystemRegretSnapshot:
    alpha_regret: float
    portfolio_regret: float
    research_regret: float
    system_regret: float
    system_stability_index: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "alpha_regret": float(self.alpha_regret),
            "portfolio_regret": float(self.portfolio_regret),
            "research_regret": float(self.research_regret),
            "system_regret": float(self.system_regret),
            "system_stability_index": float(self.system_stability_index),
        }


class SystemRegretAggregator:
    """Aggregates alpha, portfolio, and research regret into a stability index."""

    def __init__(
        self,
        *,
        alpha_weight: float = 0.50,
        portfolio_weight: float = 0.35,
        research_weight: float = 0.15,
    ):
        total = float(max(1e-8, alpha_weight + portfolio_weight + research_weight))
        self.alpha_weight = float(alpha_weight / total)
        self.portfolio_weight = float(portfolio_weight / total)
        self.research_weight = float(research_weight / total)

    @staticmethod
    def _safe(v: Any, default: float = 0.0) -> float:
        try:
            x = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(x):
            return float(default)
        return float(x)

    def compute(
        self,
        *,
        alpha_regrets: Mapping[str, float] | None,
        portfolio_metrics: Mapping[str, Any] | None,
        research_metrics: Mapping[str, Any] | None,
    ) -> SystemRegretSnapshot:
        alpha_regrets = dict(alpha_regrets or {})
        portfolio_metrics = dict(portfolio_metrics or {})
        research_metrics = dict(research_metrics or {})

        if alpha_regrets:
            a_vals = np.asarray([max(0.0, self._safe(v, 0.0)) for v in alpha_regrets.values()], dtype=float)
            alpha_regret = float(np.clip(np.mean(a_vals), 0.0, 1.0))
        else:
            alpha_regret = 0.0

        p_dd = float(np.clip(self._safe(portfolio_metrics.get("p_maxdd_breach", 0.0), 0.0), 0.0, 1.0))
        eig_spike = float(max(0.0, self._safe(portfolio_metrics.get("eigen_spike", 0.0), 0.0)))
        eig_pen = float(np.clip((eig_spike - 1.0) / 2.0, 0.0, 1.0))
        fragility = float(np.clip(self._safe(portfolio_metrics.get("structural_fragility_index", 0.0), 0.0) / 5.0, 0.0, 1.0))
        portfolio_regret = float(np.clip((0.45 * p_dd) + (0.35 * eig_pen) + (0.20 * fragility), 0.0, 1.0))

        dur_collapse = float(np.clip(self._safe(research_metrics.get("durability_collapse", 0.0), 0.0), 0.0, 1.0))
        compute_mis = float(np.clip(self._safe(research_metrics.get("compute_misallocation", 0.0), 0.0), 0.0, 1.0))
        exploration_gap = float(np.clip(self._safe(research_metrics.get("exploration_gap", 0.0), 0.0), 0.0, 1.0))
        research_regret = float(np.clip((0.50 * dur_collapse) + (0.35 * compute_mis) + (0.15 * exploration_gap), 0.0, 1.0))

        system_regret = float(
            np.clip(
                (self.alpha_weight * alpha_regret)
                + (self.portfolio_weight * portfolio_regret)
                + (self.research_weight * research_regret),
                0.0,
                1.0,
            )
        )
        stability = float(np.clip(np.exp(-2.0 * system_regret), 0.0, 1.0))

        return SystemRegretSnapshot(
            alpha_regret=alpha_regret,
            portfolio_regret=portfolio_regret,
            research_regret=research_regret,
            system_regret=system_regret,
            system_stability_index=stability,
        )
