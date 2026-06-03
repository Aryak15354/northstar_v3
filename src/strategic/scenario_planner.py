"""Long-horizon strategic scenario planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

import numpy as np


@dataclass(frozen=True)
class ScenarioPlan:
    expected_utility: float
    scenarios: Dict[str, Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_utility": float(self.expected_utility),
            "scenarios": {
                str(k): {str(sk): float(sv) for sk, sv in dict(v or {}).items()}
                for k, v in dict(self.scenarios or {}).items()
            },
        }


class ScenarioPlanner:
    """Evaluates strategic policy under coarse long-horizon stress scenarios."""

    def evaluate(
        self,
        *,
        objective_fn,
        theta: Mapping[str, float],
        context: Mapping[str, float],
    ) -> ScenarioPlan:
        base = dict(context or {})
        scenarios = {
            "baseline": {"p": 0.45, "ret": 1.00, "vol": 1.00, "cvar": 1.00, "frag": 1.00, "eig": 1.00},
            "vol_expansion": {"p": 0.15, "ret": 0.85, "vol": 1.35, "cvar": 1.30, "frag": 1.20, "eig": 1.15},
            "corr_spike": {"p": 0.15, "ret": 0.90, "vol": 1.25, "cvar": 1.25, "frag": 1.35, "eig": 1.45},
            "liquidity_collapse": {"p": 0.15, "ret": 0.80, "vol": 1.30, "cvar": 1.50, "frag": 1.40, "eig": 1.20},
            "crowding_shock": {"p": 0.10, "ret": 0.75, "vol": 1.20, "cvar": 1.40, "frag": 1.55, "eig": 1.30},
        }

        detail: Dict[str, Dict[str, float]] = {}
        expected = 0.0
        for name, s in scenarios.items():
            ctx = dict(base)
            ctx["expected_return"] = float(base.get("expected_return", 0.0) * s["ret"])
            ctx["volatility"] = float(base.get("volatility", 0.0) * s["vol"])
            ctx["cvar_95"] = float(base.get("cvar_95", 0.0) * s["cvar"])
            ctx["structural_fragility_index"] = float(base.get("structural_fragility_index", 0.0) * s["frag"])
            ctx["eigen_spike"] = float(base.get("eigen_spike", 0.0) * s["eig"])
            u = float(objective_fn(theta, ctx))
            p = float(np.clip(s["p"], 0.0, 1.0))
            expected += p * u
            detail[name] = {
                "probability": p,
                "utility": u,
                "expected_contribution": p * u,
            }

        return ScenarioPlan(expected_utility=float(expected), scenarios=detail)
