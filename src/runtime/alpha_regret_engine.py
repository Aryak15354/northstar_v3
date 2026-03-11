"""Composite regret scoring with persistence filtering."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any, Dict


@dataclass(frozen=True)
class RegretState:
    smoothed_regret: float
    persistence_counter: int
    observations: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "smoothed_regret": float(self.smoothed_regret),
            "persistence_counter": int(self.persistence_counter),
            "observations": int(self.observations),
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any] | None) -> "RegretState":
        p = dict(payload or {})
        return RegretState(
            smoothed_regret=float(p.get("smoothed_regret", 0.0) or 0.0),
            persistence_counter=int(p.get("persistence_counter", 0) or 0),
            observations=int(p.get("observations", 0) or 0),
        )


@dataclass(frozen=True)
class RegretComputation:
    sharpe_z: float
    drawdown_z: float
    recovery_z: float
    drift_z: float
    posterior_drop_z: float
    decay_z: float
    regret_score: float
    smoothed_regret: float
    persistence_counter: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sharpe_z": float(self.sharpe_z),
            "drawdown_z": float(self.drawdown_z),
            "recovery_z": float(self.recovery_z),
            "drift_z": float(self.drift_z),
            "posterior_drop_z": float(self.posterior_drop_z),
            "decay_z": float(self.decay_z),
            "regret_score": float(self.regret_score),
            "smoothed_regret": float(self.smoothed_regret),
            "persistence_counter": int(self.persistence_counter),
        }


class AlphaRegretEngine:
    """Computes bounded regret and persistence for mortality transitions."""

    def __init__(
        self,
        *,
        w_sharpe: float = 1.0,
        w_drawdown: float = 1.0,
        w_recovery: float = 0.7,
        w_drift: float = 0.8,
        w_posterior: float = 0.9,
        w_decay: float = 0.7,
        smoothing_alpha: float = 0.80,
        persistence_threshold: float = 0.60,
    ):
        self.weights = {
            "sharpe": float(max(0.0, w_sharpe)),
            "drawdown": float(max(0.0, w_drawdown)),
            "recovery": float(max(0.0, w_recovery)),
            "drift": float(max(0.0, w_drift)),
            "posterior": float(max(0.0, w_posterior)),
            "decay": float(max(0.0, w_decay)),
        }
        self.weight_sum = float(max(1e-8, sum(self.weights.values())))
        self.smoothing_alpha = float(min(max(0.0, smoothing_alpha), 0.98))
        self.persistence_threshold = float(min(max(0.0, persistence_threshold), 1.0))

    @staticmethod
    def _sigmoid(x: float) -> float:
        z = float(max(-40.0, min(40.0, x)))
        return float(1.0 / (1.0 + exp(-z)))

    @staticmethod
    def _z(x: float, mu: float, sigma: float) -> float:
        return float((x - mu) / max(1e-8, sigma))

    def compute(
        self,
        *,
        live_sharpe: float,
        mc_sharpe_mean: float,
        mc_sharpe_std: float,
        live_drawdown: float,
        mc_drawdown_mean: float,
        mc_drawdown_std: float,
        recovery_inflation: float,
        recovery_sigma: float,
        drift_z: float,
        posterior_drop_z: float,
        lambda_norm: float,
        prev_state: RegretState | None,
    ) -> tuple[RegretComputation, RegretState]:
        sharpe_z = self._z(float(live_sharpe), float(mc_sharpe_mean), float(max(1e-6, mc_sharpe_std)))
        drawdown_z = self._z(float(live_drawdown), float(mc_drawdown_mean), float(max(1e-6, mc_drawdown_std)))
        recovery_z = self._z(float(recovery_inflation), 1.0, float(max(1e-6, recovery_sigma)))
        decay_z = float(lambda_norm - 1.0)

        regret = (
            self.weights["sharpe"] * self._sigmoid(-sharpe_z)
            + self.weights["drawdown"] * self._sigmoid(drawdown_z)
            + self.weights["recovery"] * self._sigmoid(recovery_z)
            + self.weights["drift"] * self._sigmoid(-float(drift_z))
            + self.weights["posterior"] * self._sigmoid(-float(posterior_drop_z))
            + self.weights["decay"] * self._sigmoid(decay_z)
        ) / self.weight_sum

        previous = prev_state or RegretState(smoothed_regret=0.0, persistence_counter=0, observations=0)
        smoothed = float((self.smoothing_alpha * previous.smoothed_regret) + ((1.0 - self.smoothing_alpha) * regret))
        if regret >= self.persistence_threshold:
            persistence = int(previous.persistence_counter) + 1
        else:
            persistence = max(0, int(previous.persistence_counter) - 1)

        state = RegretState(
            smoothed_regret=float(smoothed),
            persistence_counter=int(persistence),
            observations=int(previous.observations) + 1,
        )
        result = RegretComputation(
            sharpe_z=float(sharpe_z),
            drawdown_z=float(drawdown_z),
            recovery_z=float(recovery_z),
            drift_z=float(drift_z),
            posterior_drop_z=float(posterior_drop_z),
            decay_z=float(decay_z),
            regret_score=float(regret),
            smoothed_regret=float(smoothed),
            persistence_counter=int(persistence),
        )
        return result, state
