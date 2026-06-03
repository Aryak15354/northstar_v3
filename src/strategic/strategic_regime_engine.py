"""Strategic regime classification for Phase 10 architecture blending."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

import numpy as np


@dataclass(frozen=True)
class StrategicRegimeSnapshot:
    dominant_regime: str
    probabilities: Dict[str, float]
    raw_probabilities: Dict[str, float]
    state_vector: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_regime": str(self.dominant_regime),
            "probabilities": {str(k): float(v) for k, v in dict(self.probabilities or {}).items()},
            "raw_probabilities": {str(k): float(v) for k, v in dict(self.raw_probabilities or {}).items()},
            "state_vector": {str(k): float(v) for k, v in dict(self.state_vector or {}).items()},
        }


class StrategicRegimeEngine:
    """
    Soft strategic regime classifier with exponential smoothing.

    Uses a state vector:
    [system_regret, stability_index, structural_fragility, eigen_spike_excess, research_gap, capital_scale]
    """

    REGIMES = ("growth", "stability", "innovation")
    STATE_ORDER = (
        "system_regret",
        "stability_index",
        "structural_fragility",
        "eigen_spike_excess",
        "research_gap",
        "capital_scale",
    )

    DEFAULT_BETA = {
        "growth": np.asarray([-1.50, 2.00, -1.50, -1.00, -0.50, 0.50], dtype=float),
        "stability": np.asarray([1.20, -1.50, 2.00, 1.80, -0.50, 0.30], dtype=float),
        "innovation": np.asarray([0.50, -0.50, 0.20, 0.20, 2.20, -0.30], dtype=float),
    }
    DEFAULT_BIAS = {"growth": 0.25, "stability": 0.10, "innovation": 0.05}

    def __init__(
        self,
        *,
        smoothing_alpha: float = 0.10,
        beta: Mapping[str, np.ndarray] | None = None,
        bias: Mapping[str, float] | None = None,
    ):
        self.smoothing_alpha = float(np.clip(smoothing_alpha, 0.01, 0.50))
        self.beta = {
            r: np.asarray((beta or {}).get(r, self.DEFAULT_BETA[r]), dtype=float)
            for r in self.REGIMES
        }
        self.bias = {
            r: float((bias or {}).get(r, self.DEFAULT_BIAS[r]))
            for r in self.REGIMES
        }
        self._smoothed = {r: 1.0 / float(len(self.REGIMES)) for r in self.REGIMES}

    @staticmethod
    def _safe(v: Any, default: float = 0.0) -> float:
        try:
            x = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(x):
            return float(default)
        return float(x)

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        x = np.asarray(logits, dtype=float)
        x = x - np.max(x)
        e = np.exp(x)
        return e / (np.sum(e) + 1e-12)

    def _state_vector(self, state: Mapping[str, Any] | None) -> Dict[str, float]:
        s = dict(state or {})
        system_regret = float(np.clip(self._safe(s.get("system_regret", 0.0), 0.0), 0.0, 1.0))
        stability_index = float(np.clip(self._safe(s.get("stability_index", 1.0 - system_regret), 1.0 - system_regret), 0.0, 1.0))
        fragility = float(np.clip(self._safe(s.get("structural_fragility", 0.0), 0.0), 0.0, 1.0))
        eig_spike = self._safe(s.get("eigen_spike", 1.0), 1.0)
        eig_excess = float(np.clip((eig_spike - 1.0) / 2.0, 0.0, 1.0))
        research_gap = float(np.clip(self._safe(s.get("research_gap", 0.0), 0.0), 0.0, 1.0))
        capital_scale = float(np.clip(self._safe(s.get("capital_scale", 0.0), 0.0), 0.0, 1.5))

        return {
            "system_regret": system_regret,
            "stability_index": stability_index,
            "structural_fragility": fragility,
            "eigen_spike_excess": eig_excess,
            "research_gap": research_gap,
            "capital_scale": capital_scale,
        }

    def infer(
        self,
        *,
        state: Mapping[str, Any] | None = None,
        update_state: bool = True,
    ) -> StrategicRegimeSnapshot:
        vec = self._state_vector(state)
        z = np.asarray([vec[name] for name in self.STATE_ORDER], dtype=float)

        logits = np.asarray(
            [(self.beta[r] @ z) + float(self.bias[r]) for r in self.REGIMES],
            dtype=float,
        )
        raw = self._softmax(logits)
        raw_map = {r: float(raw[i]) for i, r in enumerate(self.REGIMES)}

        if update_state:
            smoothed = {}
            for i, r in enumerate(self.REGIMES):
                prev = float(self._smoothed.get(r, 1.0 / float(len(self.REGIMES))))
                smoothed[r] = float((self.smoothing_alpha * raw[i]) + ((1.0 - self.smoothing_alpha) * prev))
            total = float(sum(smoothed.values()) + 1e-12)
            self._smoothed = {r: float(v / total) for r, v in smoothed.items()}

        probs = dict(self._smoothed)
        dominant = max(self.REGIMES, key=lambda r: probs.get(r, 0.0))
        return StrategicRegimeSnapshot(
            dominant_regime=str(dominant),
            probabilities=probs,
            raw_probabilities=raw_map,
            state_vector=vec,
        )

    def current_probabilities(self) -> Dict[str, float]:
        return dict(self._smoothed)
