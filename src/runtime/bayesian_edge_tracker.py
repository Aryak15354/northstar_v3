"""Bayesian posterior tracking for live edge confidence."""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Any, Dict, Iterable, List

import numpy as np


@dataclass(frozen=True)
class BayesianEdgeState:
    prior_mean: float
    prior_variance: float
    posterior_mean: float
    posterior_variance: float
    positive_probability: float
    updates: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prior_mean": float(self.prior_mean),
            "prior_variance": float(self.prior_variance),
            "posterior_mean": float(self.posterior_mean),
            "posterior_variance": float(self.posterior_variance),
            "positive_probability": float(self.positive_probability),
            "updates": int(self.updates),
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any] | None, *, fallback_mean: float = 0.0, fallback_variance: float = 1.0) -> "BayesianEdgeState":
        p = dict(payload or {})
        prior_mean = float(p.get("prior_mean", fallback_mean) or fallback_mean)
        prior_variance = float(p.get("prior_variance", fallback_variance) or fallback_variance)
        posterior_mean = float(p.get("posterior_mean", prior_mean) or prior_mean)
        posterior_variance = float(p.get("posterior_variance", prior_variance) or prior_variance)
        positive_probability = float(p.get("positive_probability", 0.5) or 0.5)
        updates = int(p.get("updates", 0) or 0)
        return BayesianEdgeState(
            prior_mean=prior_mean,
            prior_variance=prior_variance,
            posterior_mean=posterior_mean,
            posterior_variance=posterior_variance,
            positive_probability=positive_probability,
            updates=updates,
        )


class BayesianEdgeTracker:
    """Normal-Normal conjugate tracker for latent edge mean."""

    def __init__(
        self,
        *,
        min_variance: float = 1e-6,
        observation_variance_floor: float = 1e-6,
    ):
        self.min_variance = float(max(1e-12, min_variance))
        self.observation_variance_floor = float(max(1e-12, observation_variance_floor))

    @staticmethod
    def _phi(z: float) -> float:
        return float(0.5 * (1.0 + erf(float(z) / sqrt(2.0))))

    def initial_state(self, *, prior_mean: float, prior_variance: float) -> BayesianEdgeState:
        pvar = float(max(self.min_variance, prior_variance))
        z = float(prior_mean / max(sqrt(pvar), 1e-12))
        return BayesianEdgeState(
            prior_mean=float(prior_mean),
            prior_variance=pvar,
            posterior_mean=float(prior_mean),
            posterior_variance=pvar,
            positive_probability=self._phi(z),
            updates=0,
        )

    def update(
        self,
        *,
        state: BayesianEdgeState,
        observations: Iterable[float],
        observation_variance: float | None = None,
    ) -> BayesianEdgeState:
        obs = np.asarray(list(observations) if observations is not None else [], dtype=float)
        obs = obs[np.isfinite(obs)]
        if obs.size == 0:
            return state

        sample_mean = float(np.mean(obs))
        if observation_variance is None:
            sample_var = float(np.var(obs, ddof=1)) if obs.size > 1 else self.observation_variance_floor
            obs_var = float(max(self.observation_variance_floor, sample_var / max(float(obs.size), 1.0)))
        else:
            obs_var = float(max(self.observation_variance_floor, observation_variance))

        prior_mean = float(state.posterior_mean)
        prior_var = float(max(self.min_variance, state.posterior_variance))

        prior_precision = 1.0 / max(prior_var, self.min_variance)
        obs_precision = 1.0 / max(obs_var, self.observation_variance_floor)

        post_var = 1.0 / max(prior_precision + obs_precision, 1e-12)
        post_mean = post_var * ((prior_precision * prior_mean) + (obs_precision * sample_mean))

        z = float(post_mean / max(sqrt(max(post_var, self.min_variance)), 1e-12))
        return BayesianEdgeState(
            prior_mean=float(state.prior_mean),
            prior_variance=float(max(self.min_variance, state.prior_variance)),
            posterior_mean=float(post_mean),
            posterior_variance=float(max(self.min_variance, post_var)),
            positive_probability=self._phi(z),
            updates=int(state.updates) + 1,
        )
