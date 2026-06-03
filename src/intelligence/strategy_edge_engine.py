"""
Bayesian strategy edge estimation for AlphaOS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np


def _clip(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


@dataclass
class EdgeEngineConfig:
    prior_mean: float = 0.0
    prior_variance: float = 0.01
    ewma_lambda: float = 0.97
    min_observations: int = 20


class StrategyEdgeEngine:
    """
    Regime-aware Bayesian posterior edge estimator.
    """

    def __init__(self, config: Optional[EdgeEngineConfig] = None) -> None:
        self.config = config or EdgeEngineConfig()

    def estimate(
        self,
        returns_by_strategy: Mapping[str, Iterable[float]],
        regime_probs: Mapping[str, float],
        crowding_scores: Optional[Mapping[str, float]] = None,
        convexity_scores: Optional[Mapping[str, float]] = None,
        regime_sensitivity: Optional[Mapping[str, Mapping[str, float]]] = None,
    ) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        crowding_scores = crowding_scores or {}
        convexity_scores = convexity_scores or {}
        regime_sensitivity = regime_sensitivity or {}
        regime_weight_default = dict(regime_probs)

        for strategy, raw_returns in returns_by_strategy.items():
            vec = np.asarray(list(raw_returns), dtype=float)
            vec = vec[np.isfinite(vec)]
            if vec.size == 0:
                out[strategy] = self._empty_stats()
                continue

            ew = self._ewma_weights(vec.size)
            mean_hat = float(np.sum(vec * ew))
            var_hat = float(np.sum(ew * (vec - mean_hat) ** 2))
            var_hat = max(var_hat, 1e-8)

            # Normal-Normal posterior update.
            n_eff = float(np.sum(ew > (1.0 / max(1, len(ew)) * 0.1)))
            tau0 = float(self.config.prior_variance)
            sigma2 = float(var_hat)
            post_var = 1.0 / ((1.0 / tau0) + (n_eff / sigma2))
            post_mean = post_var * ((self.config.prior_mean / tau0) + (n_eff * mean_hat / sigma2))

            # Regime-weighted edge.
            sens = regime_sensitivity.get(strategy, {})
            rw = 0.0
            for regime, prob in regime_weight_default.items():
                rw += float(prob) * float(sens.get(regime, 1.0))
            post_mean *= float(rw)

            crowding = _clip(float(crowding_scores.get(strategy, 0.0)), 0.0, 1.0)
            convexity = max(0.0, float(convexity_scores.get(strategy, 0.0)))
            crowding_penalty = float(np.exp(-2.0 * crowding))
            convexity_penalty = 1.0 / (1.0 + convexity)
            adjusted_mean = float(post_mean * crowding_penalty * convexity_penalty)

            adjusted_sharpe = adjusted_mean / float(np.sqrt(sigma2 + post_var))
            credibility = _clip(adjusted_sharpe / 2.0 + 0.5, 0.0, 1.0)

            out[strategy] = {
                "posterior_mean": float(adjusted_mean),
                "posterior_variance": float(max(post_var, 1e-8)),
                "volatility": float(np.sqrt(sigma2)),
                "adjusted_sharpe": float(adjusted_sharpe),
                "credibility": float(credibility),
                "crowding_penalty": float(crowding_penalty),
                "convexity_penalty": float(convexity_penalty),
                "observations": int(vec.size),
            }

        return out

    def _ewma_weights(self, n: int) -> np.ndarray:
        lam = float(self.config.ewma_lambda)
        weights = np.array([lam ** (n - i - 1) for i in range(n)], dtype=float)
        weights = np.clip(weights, 1e-12, None)
        return weights / weights.sum()

    def _empty_stats(self) -> Dict[str, float]:
        return {
            "posterior_mean": float(self.config.prior_mean),
            "posterior_variance": float(self.config.prior_variance),
            "volatility": 1.0,
            "adjusted_sharpe": 0.0,
            "credibility": 0.0,
            "crowding_penalty": 1.0,
            "convexity_penalty": 1.0,
            "observations": 0,
        }
