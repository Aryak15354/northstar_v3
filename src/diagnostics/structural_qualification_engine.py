"""Phase 3 deterministic structural robustness qualification engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

from .capacity_curve_optimizer import CapacityCurveOptimizer, CapacityCurveResult


@dataclass(frozen=True)
class DeterministicQualificationResult:
    cost_ok: bool
    capacity_ok: bool
    marginal_ok: bool
    decay_ok: bool
    stress_ok: bool
    status: str
    gross_sharpe: float
    net_sharpe: float
    cost_sensitivity: float
    capacity_limit_estimate: float
    marginal_sharpe: float
    rolling_decay_slope: float
    stress_max_dd: float
    stress_matrix: List[Dict[str, float]]
    capacity_curve: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_ok": bool(self.cost_ok),
            "capacity_ok": bool(self.capacity_ok),
            "marginal_ok": bool(self.marginal_ok),
            "decay_ok": bool(self.decay_ok),
            "stress_ok": bool(self.stress_ok),
            "status": str(self.status),
            "gross_sharpe": float(self.gross_sharpe),
            "net_sharpe": float(self.net_sharpe),
            "cost_sensitivity": float(self.cost_sensitivity),
            "capacity_limit_estimate": float(self.capacity_limit_estimate),
            "marginal_sharpe": float(self.marginal_sharpe),
            "rolling_decay_slope": float(self.rolling_decay_slope),
            "stress_max_dd": float(self.stress_max_dd),
            "stress_matrix": [dict(x) for x in list(self.stress_matrix or [])],
            "capacity_curve": dict(self.capacity_curve or {}),
        }


class StructuralQualificationEngine:
    """Rule-based Phase 3 gates: cost, capacity, marginal, decay, stress."""

    def __init__(
        self,
        *,
        min_cost_ratio: float = 0.60,
        min_capacity_ratio: float = 0.70,
        min_marginal_sharpe_delta: float = 0.10,
        min_decay_slope: float = -0.05,
        max_stress_drawdown: float = 0.35,
        cost_impact_a: float = 0.0004,
        cost_impact_b: float = 0.0001,
        cost_multipliers: Sequence[float] = (1.0, 1.5, 2.0),
        rolling_window: int = 252,
        capital_grid: Sequence[float] | None = None,
    ):
        self.min_cost_ratio = float(min_cost_ratio)
        self.min_capacity_ratio = float(min_capacity_ratio)
        self.min_marginal_sharpe_delta = float(min_marginal_sharpe_delta)
        self.min_decay_slope = float(min_decay_slope)
        self.max_stress_drawdown = float(max_stress_drawdown)
        self.cost_impact_a = float(cost_impact_a)
        self.cost_impact_b = float(cost_impact_b)
        self.cost_multipliers = [float(x) for x in list(cost_multipliers or (1.0, 1.5, 2.0)) if float(x) > 0.0]
        if not self.cost_multipliers:
            self.cost_multipliers = [1.0, 2.0]
        self.rolling_window = max(20, int(rolling_window))
        self.capacity_optimizer = CapacityCurveOptimizer(capital_grid=capital_grid)

    @staticmethod
    def _to_array(values: Iterable[float]) -> np.ndarray:
        arr = np.asarray(list(values), dtype=float).reshape(-1)
        arr = arr[np.isfinite(arr)]
        return arr

    @staticmethod
    def _sharpe(returns: np.ndarray) -> float:
        if returns.size <= 1:
            return 0.0
        return float(np.mean(returns) / (np.std(returns) + 1e-8))

    @staticmethod
    def _max_drawdown(returns: np.ndarray) -> float:
        if returns.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + returns)
        peaks = np.maximum.accumulate(eq)
        dd = (eq / (peaks + 1e-12)) - 1.0
        return float(np.min(dd))

    def _net_returns_with_cost(self, returns: np.ndarray, multiplier: float) -> np.ndarray:
        linear = float(multiplier * self.cost_impact_a)
        quad = float(multiplier * self.cost_impact_b)
        return returns - linear - (quad * np.abs(returns))

    def cost_convexity_test(self, returns: np.ndarray) -> Tuple[bool, float, float]:
        if returns.size <= 1:
            return False, 0.0, 0.0
        gross = self._sharpe(returns)
        net_scores = []
        for m in self.cost_multipliers:
            net_scores.append(self._sharpe(self._net_returns_with_cost(returns, m)))
        net_1x = float(net_scores[0]) if net_scores else gross
        net_2x = float(net_scores[-1]) if net_scores else gross
        if abs(net_1x) <= 1e-9:
            ratio = -1.0
        else:
            ratio = float(net_2x / net_1x)
        return bool(ratio >= self.min_cost_ratio), float(net_1x), float(ratio)

    def capacity_scaling_test(self, returns: np.ndarray) -> Tuple[bool, CapacityCurveResult]:
        result = self.capacity_optimizer.optimize(
            returns,
            impact_a=self.cost_impact_a,
            impact_b=self.cost_impact_b,
            sharpe_capacity_ratio=self.min_capacity_ratio,
            drawdown_limit=self.max_stress_drawdown,
        )
        return bool(result.status == "viable"), result

    def marginal_contribution_test(self, returns: np.ndarray, portfolio_returns: np.ndarray) -> Tuple[bool, float]:
        if returns.size <= 1 or portfolio_returns.size <= 1:
            return True, 0.0
        m = int(min(returns.size, portfolio_returns.size))
        alpha = returns[-m:]
        portfolio = portfolio_returns[-m:]
        base = self._sharpe(portfolio)
        combined = self._sharpe(portfolio + (0.25 * alpha))
        delta = float(combined - base)
        return bool(delta >= self.min_marginal_sharpe_delta), delta

    def decay_test(self, returns: np.ndarray) -> Tuple[bool, float]:
        if returns.size < (self.rolling_window + 10):
            return True, 0.0
        roll: List[float] = []
        for i in range(returns.size - self.rolling_window + 1):
            roll.append(self._sharpe(returns[i:i + self.rolling_window]))
        if len(roll) < 5:
            return True, 0.0
        slope = float(np.polyfit(np.arange(len(roll), dtype=float), np.asarray(roll, dtype=float), 1)[0])
        return bool(slope >= self.min_decay_slope), slope

    def stress_matrix_test(
        self,
        returns: np.ndarray,
        portfolio_returns: np.ndarray,
    ) -> Tuple[bool, float, List[Dict[str, float]]]:
        if returns.size <= 1:
            return False, 1.0, []

        mu = float(np.mean(returns))
        sigma = float(np.std(returns))
        sigma = max(1e-8, sigma)
        m = int(min(returns.size, portfolio_returns.size)) if portfolio_returns.size > 0 else 0
        if m > 1:
            p = portfolio_returns[-m:]
            a = returns[-m:]
            corr_mix = (0.6 * a) + (0.4 * p)
        else:
            corr_mix = returns.copy()

        block = max(3, min(20, returns.size // 4))
        worst_sum = None
        worst = returns[:block]
        for i in range(returns.size - block + 1):
            s = float(np.sum(returns[i:i + block]))
            if (worst_sum is None) or (s < worst_sum):
                worst_sum = s
                worst = returns[i:i + block]
        crisis = returns.copy()
        crisis[:block] = worst

        scenarios = {
            "vol_shock": mu + (2.0 * (returns - mu)),
            "correlation_spike": corr_mix,
            "liquidity_freeze": returns - (2.0 * self.cost_impact_a) - (3.0 * self.cost_impact_b * np.abs(returns)),
            "crisis_replay": crisis,
            "drift_shift": returns - (0.5 * sigma),
        }
        matrix: List[Dict[str, float]] = []
        worst_dd = 0.0
        for name, path in scenarios.items():
            dd = abs(self._max_drawdown(path))
            worst_dd = max(worst_dd, dd)
            matrix.append(
                {
                    "scenario": str(name),
                    "max_dd": float(dd),
                    "sharpe": float(self._sharpe(path)),
                }
            )
        return bool(worst_dd <= self.max_stress_drawdown), float(worst_dd), matrix

    def qualify(
        self,
        returns: Iterable[float],
        portfolio_returns: Iterable[float] | None = None,
    ) -> DeterministicQualificationResult:
        r = self._to_array(returns)
        p = self._to_array(portfolio_returns or [])
        if r.size <= 1:
            return DeterministicQualificationResult(
                cost_ok=False,
                capacity_ok=False,
                marginal_ok=False,
                decay_ok=False,
                stress_ok=False,
                status="reject",
                gross_sharpe=0.0,
                net_sharpe=0.0,
                cost_sensitivity=0.0,
                capacity_limit_estimate=0.0,
                marginal_sharpe=0.0,
                rolling_decay_slope=0.0,
                stress_max_dd=1.0,
                stress_matrix=[],
                capacity_curve={},
            )

        gross_sharpe = self._sharpe(r)
        cost_ok, net_sharpe, cost_ratio = self.cost_convexity_test(r)
        capacity_ok, cap = self.capacity_scaling_test(r)
        marginal_ok, marginal_delta = self.marginal_contribution_test(r, p)
        decay_ok, decay_slope = self.decay_test(r)
        stress_ok, stress_dd, matrix = self.stress_matrix_test(r, p)

        status = "deployable" if all([cost_ok, capacity_ok, marginal_ok, decay_ok, stress_ok]) else "reject"
        return DeterministicQualificationResult(
            cost_ok=bool(cost_ok),
            capacity_ok=bool(capacity_ok),
            marginal_ok=bool(marginal_ok),
            decay_ok=bool(decay_ok),
            stress_ok=bool(stress_ok),
            status=status,
            gross_sharpe=float(gross_sharpe),
            net_sharpe=float(net_sharpe),
            cost_sensitivity=float(cost_ratio),
            capacity_limit_estimate=float(cap.capacity_limit_estimate),
            marginal_sharpe=float(marginal_delta),
            rolling_decay_slope=float(decay_slope),
            stress_max_dd=float(stress_dd),
            stress_matrix=matrix,
            capacity_curve=cap.to_dict(),
        )
