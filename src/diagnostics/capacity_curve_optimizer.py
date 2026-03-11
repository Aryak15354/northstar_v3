"""Phase 3 capacity curve optimization under convex impact costs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np


@dataclass(frozen=True)
class CapacityCurveResult:
    optimal_capital: float
    sharpe_at_optimal: float
    capacity_limit_estimate: float
    status: str
    sharpe_curve: Dict[float, float]
    drawdown_curve: Dict[float, float]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimal_capital": float(self.optimal_capital),
            "sharpe_at_optimal": float(self.sharpe_at_optimal),
            "capacity_limit_estimate": float(self.capacity_limit_estimate),
            "status": str(self.status),
            "sharpe_curve": {str(k): float(v) for k, v in dict(self.sharpe_curve).items()},
            "drawdown_curve": {str(k): float(v) for k, v in dict(self.drawdown_curve).items()},
            "metadata": dict(self.metadata or {}),
        }


class CapacityCurveOptimizer:
    """Compute capacity frontier and optimal capital under cost convexity."""

    def __init__(
        self,
        capital_grid: Sequence[float] | None = None,
    ):
        default_grid = (10_000_000.0, 25_000_000.0, 50_000_000.0, 100_000_000.0)
        self.capital_grid = np.asarray(list(capital_grid or default_grid), dtype=float)
        self.capital_grid = np.asarray([c for c in self.capital_grid if np.isfinite(c) and c > 0.0], dtype=float)
        if self.capital_grid.size == 0:
            self.capital_grid = np.asarray(list(default_grid), dtype=float)
        self.capital_grid = np.unique(np.sort(self.capital_grid))

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    @staticmethod
    def _to_array(values: Iterable[float]) -> np.ndarray:
        arr = np.asarray(list(values), dtype=float).reshape(-1)
        arr = arr[np.isfinite(arr)]
        return arr

    @staticmethod
    def _sharpe(returns: np.ndarray) -> float:
        if returns.size <= 1:
            return 0.0
        mu = float(np.mean(returns))
        sigma = float(np.std(returns))
        return float(mu / (sigma + 1e-8))

    @staticmethod
    def _max_drawdown(returns: np.ndarray) -> float:
        if returns.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + returns)
        peaks = np.maximum.accumulate(eq)
        dd = (eq / (peaks + 1e-12)) - 1.0
        return float(np.min(dd))

    def optimize(
        self,
        returns: Iterable[float],
        *,
        impact_a: float = 0.0004,
        impact_b: float = 0.0001,
        drawdown_limit: float = 0.35,
        min_sharpe: float = 0.5,
        sharpe_capacity_ratio: float = 0.70,
        base_capital: float | None = None,
    ) -> CapacityCurveResult:
        r = self._to_array(returns)
        if r.size <= 1:
            return CapacityCurveResult(
                optimal_capital=0.0,
                sharpe_at_optimal=0.0,
                capacity_limit_estimate=0.0,
                status="reject",
                sharpe_curve={},
                drawdown_curve={},
                metadata={"reason": "insufficient_returns"},
            )

        capital_grid = np.asarray(self.capital_grid, dtype=float)
        base = float(base_capital) if base_capital is not None else float(np.min(capital_grid))
        base = max(1.0, base)

        sharpe_curve: Dict[float, float] = {}
        drawdown_curve: Dict[float, float] = {}
        for cap in capital_grid:
            q = float(cap / base)
            # Net return with convex impact: mu*q - a*q - b*q^2 (periodic approximation)
            net = (r * q) - float(impact_a * q) - float(impact_b * (q ** 2))
            sharpe_curve[float(cap)] = self._sharpe(net)
            drawdown_curve[float(cap)] = abs(self._max_drawdown(net))

        caps = sorted(sharpe_curve.keys())
        sharpes = np.asarray([sharpe_curve[c] for c in caps], dtype=float)
        drawdowns = np.asarray([drawdown_curve[c] for c in caps], dtype=float)
        feasible_idx = np.where(drawdowns <= float(drawdown_limit))[0]

        if feasible_idx.size == 0:
            return CapacityCurveResult(
                optimal_capital=float(caps[0]),
                sharpe_at_optimal=float(sharpes[0]),
                capacity_limit_estimate=0.0,
                status="reject",
                sharpe_curve=sharpe_curve,
                drawdown_curve=drawdown_curve,
                metadata={"reason": "no_feasible_capital_under_drawdown_limit"},
            )

        best_idx_local = int(feasible_idx[np.argmax(sharpes[feasible_idx])])
        optimal_capital = float(caps[best_idx_local])
        sharpe_at_optimal = float(sharpes[best_idx_local])

        base_sharpe = float(sharpes[0]) if sharpes.size else 0.0
        min_allowed = float(sharpe_capacity_ratio) * base_sharpe
        viable_caps = [
            float(caps[i])
            for i in feasible_idx
            if float(sharpes[i]) >= min_allowed
        ]
        capacity_limit = float(max(viable_caps)) if viable_caps else 0.0

        status = "viable" if (sharpe_at_optimal >= float(min_sharpe) and capacity_limit > 0.0) else "reject"
        return CapacityCurveResult(
            optimal_capital=optimal_capital,
            sharpe_at_optimal=sharpe_at_optimal,
            capacity_limit_estimate=capacity_limit,
            status=status,
            sharpe_curve=sharpe_curve,
            drawdown_curve=drawdown_curve,
            metadata={
                "base_capital": float(base),
                "drawdown_limit": float(drawdown_limit),
                "min_sharpe": float(min_sharpe),
                "sharpe_capacity_ratio": float(sharpe_capacity_ratio),
            },
        )
