"""Path-shape drift diagnostics for live alpha behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

import numpy as np


@dataclass(frozen=True)
class PathDeformationResult:
    recovery_days: float
    recovery_inflation: float
    volatility_cluster_acf1: float
    volatility_cluster_drift: float
    skewness: float
    skew_drift: float
    convexity: float
    convexity_drift: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_days": float(self.recovery_days),
            "recovery_inflation": float(self.recovery_inflation),
            "volatility_cluster_acf1": float(self.volatility_cluster_acf1),
            "volatility_cluster_drift": float(self.volatility_cluster_drift),
            "skewness": float(self.skewness),
            "skew_drift": float(self.skew_drift),
            "convexity": float(self.convexity),
            "convexity_drift": float(self.convexity_drift),
        }


class PathDeformationMonitor:
    def __init__(self, *, eps: float = 1e-8):
        self.eps = float(max(1e-12, eps))

    @staticmethod
    def _underwater_run(values: np.ndarray) -> int:
        eq = np.cumprod(1.0 + values)
        peaks = np.maximum.accumulate(eq)
        underwater = eq < peaks
        run = 0
        longest = 0
        for flag in underwater.tolist():
            if flag:
                run += 1
                if run > longest:
                    longest = run
            else:
                run = 0
        return int(longest)

    @staticmethod
    def _acf1(values: np.ndarray) -> float:
        if values.size < 3:
            return 0.0
        x = np.asarray(values[:-1], dtype=float)
        y = np.asarray(values[1:], dtype=float)
        x = x - float(np.mean(x))
        y = y - float(np.mean(y))
        denom = float(np.sqrt(np.sum(x * x) * np.sum(y * y)))
        if denom <= 1e-12:
            return 0.0
        return float(np.sum(x * y) / denom)

    @staticmethod
    def _skew(values: np.ndarray) -> float:
        if values.size < 3:
            return 0.0
        mu = float(np.mean(values))
        centered = values - mu
        sigma = float(np.std(values, ddof=1))
        if sigma <= 1e-12:
            return 0.0
        return float(np.mean((centered / sigma) ** 3))

    @staticmethod
    def _convexity(strategy_returns: np.ndarray, market_returns: np.ndarray | None) -> float:
        if market_returns is None or market_returns.size != strategy_returns.size or strategy_returns.size < 5:
            return 0.0
        x = np.asarray(market_returns, dtype=float)
        y = np.asarray(strategy_returns, dtype=float)
        x2 = x * x
        mat = np.column_stack([np.ones_like(x), x, x2])
        try:
            beta, *_ = np.linalg.lstsq(mat, y, rcond=None)
            return float(beta[2])
        except Exception:
            return 0.0

    def compute(
        self,
        *,
        strategy_returns: Iterable[float],
        baseline_recovery_days: float,
        baseline_vol_cluster_acf1: float,
        baseline_skew: float,
        baseline_convexity: float,
        market_returns: Iterable[float] | None = None,
    ) -> PathDeformationResult:
        sr = np.asarray(list(strategy_returns) if strategy_returns is not None else [], dtype=float)
        sr = sr[np.isfinite(sr)]
        mr = None
        if market_returns is not None:
            tmp = np.asarray(list(market_returns), dtype=float)
            tmp = tmp[np.isfinite(tmp)]
            if tmp.size == sr.size and sr.size > 0:
                mr = tmp

        if sr.size == 0:
            return PathDeformationResult(
                recovery_days=0.0,
                recovery_inflation=1.0,
                volatility_cluster_acf1=0.0,
                volatility_cluster_drift=0.0,
                skewness=0.0,
                skew_drift=0.0,
                convexity=0.0,
                convexity_drift=0.0,
            )

        recovery_days = float(self._underwater_run(sr))
        baseline_rec = float(max(1.0, baseline_recovery_days))
        recovery_inflation = float(recovery_days / baseline_rec)

        acf1 = float(self._acf1(np.abs(sr)))
        vol_cluster_drift = float(acf1 - float(baseline_vol_cluster_acf1))

        skew = float(self._skew(sr))
        skew_drift = float(skew - float(baseline_skew))

        convexity = float(self._convexity(sr, mr))
        convexity_drift = float(convexity - float(baseline_convexity))

        return PathDeformationResult(
            recovery_days=recovery_days,
            recovery_inflation=recovery_inflation,
            volatility_cluster_acf1=acf1,
            volatility_cluster_drift=vol_cluster_drift,
            skewness=skew,
            skew_drift=skew_drift,
            convexity=convexity,
            convexity_drift=convexity_drift,
        )
