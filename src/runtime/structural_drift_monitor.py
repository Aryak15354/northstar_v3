"""Regime-aware structural drift monitor for live alpha."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Any, Dict, Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class StructuralDriftResult:
    live_sharpe: float
    residual_sharpe: float
    expected_sharpe: float
    drift: float
    drift_z: float
    regime_entropy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "live_sharpe": float(self.live_sharpe),
            "residual_sharpe": float(self.residual_sharpe),
            "expected_sharpe": float(self.expected_sharpe),
            "drift": float(self.drift),
            "drift_z": float(self.drift_z),
            "regime_entropy": float(self.regime_entropy),
        }


class StructuralDriftMonitor:
    def __init__(self, *, min_sigma: float = 0.10):
        self.min_sigma = float(max(1e-6, min_sigma))

    @staticmethod
    def _safe_probs(payload: Mapping[str, float] | None) -> Dict[str, float]:
        probs = {str(k): float(max(0.0, v)) for k, v in dict(payload or {}).items()}
        total = float(sum(probs.values()))
        if total <= 1e-12:
            return {"state_1": 1.0}
        return {k: float(v / total) for k, v in probs.items()}

    @staticmethod
    def _sharpe(values: Iterable[float]) -> float:
        arr = np.asarray(list(values) if values is not None else [], dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size <= 1:
            return 0.0
        mu = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=1))
        return float(mu / (sigma + 1e-8))

    @staticmethod
    def _entropy(probs: Mapping[str, float]) -> float:
        vals = [float(v) for v in dict(probs or {}).values() if float(v) > 1e-12]
        if not vals:
            return 0.0
        h = -sum(v * log(v) for v in vals)
        hmax = log(max(2, len(vals)))
        if hmax <= 0.0:
            return 0.0
        return float(h / hmax)

    def _residual_returns(
        self,
        *,
        strategy_returns: np.ndarray,
        portfolio_returns: np.ndarray | None,
    ) -> np.ndarray:
        if portfolio_returns is None or portfolio_returns.size != strategy_returns.size or strategy_returns.size <= 3:
            return strategy_returns

        x = np.asarray(portfolio_returns, dtype=float)
        y = np.asarray(strategy_returns, dtype=float)
        x_mean = float(np.mean(x))
        y_mean = float(np.mean(y))
        x_var = float(np.var(x, ddof=1))
        if x_var <= 1e-12:
            return y
        cov = float(np.cov(y, x, ddof=1)[0, 1])
        beta = cov / max(x_var, 1e-12)
        alpha = y_mean - (beta * x_mean)
        residual = y - (alpha + (beta * x))
        return residual

    def compute(
        self,
        *,
        strategy_returns: Iterable[float],
        regime_probabilities: Mapping[str, float] | None,
        regime_sharpe_profile: Mapping[str, float] | None,
        regime_sigma: float | None = None,
        portfolio_returns: Iterable[float] | None = None,
    ) -> StructuralDriftResult:
        sr = np.asarray(list(strategy_returns) if strategy_returns is not None else [], dtype=float)
        sr = sr[np.isfinite(sr)]
        pr = None
        if portfolio_returns is not None:
            pr_arr = np.asarray(list(portfolio_returns), dtype=float)
            pr_arr = pr_arr[np.isfinite(pr_arr)]
            if pr_arr.size == sr.size and sr.size > 0:
                pr = pr_arr

        live_sharpe = self._sharpe(sr)
        residual = self._residual_returns(strategy_returns=sr, portfolio_returns=pr)
        residual_sharpe = self._sharpe(residual)

        probs = self._safe_probs(regime_probabilities)
        profile = {str(k): float(v) for k, v in dict(regime_sharpe_profile or {}).items()}
        expected = 0.0
        for rk, p in probs.items():
            expected += float(p) * float(profile.get(rk, 0.0))

        sigma = float(max(self.min_sigma, (regime_sigma if regime_sigma is not None else np.std(list(profile.values()) or [0.0]))))
        drift = float(residual_sharpe - expected)
        drift_z = float(drift / sigma)

        return StructuralDriftResult(
            live_sharpe=float(live_sharpe),
            residual_sharpe=float(residual_sharpe),
            expected_sharpe=float(expected),
            drift=float(drift),
            drift_z=float(drift_z),
            regime_entropy=self._entropy(probs),
        )
