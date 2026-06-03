"""Phase 3 Monte Carlo survival qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import numpy as np


@dataclass(frozen=True)
class MonteCarloStabilityResult:
    p_sharpe_negative: float
    p_dd_gt_40: float
    sharpe_p05: float
    median_terminal_return: float
    status: str
    n_simulations: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p_sharpe_negative": float(self.p_sharpe_negative),
            "p_dd_gt_40": float(self.p_dd_gt_40),
            "sharpe_p05": float(self.sharpe_p05),
            "median_terminal_return": float(self.median_terminal_return),
            "status": str(self.status),
            "n_simulations": int(self.n_simulations),
        }


class MonteCarloStabilitySimulator:
    """Blend IID, block, regime, and shock simulations for survival estimates."""

    def __init__(
        self,
        n_sim: int = 1000,
        *,
        block_size: int = 5,
        max_p_sharpe_negative: float = 0.30,
        max_p_dd_gt_40: float = 0.25,
        min_sharpe_p05: float = 0.30,
        random_seed: int = 42,
    ):
        self.n_sim = max(100, int(n_sim))
        self.block_size = max(2, int(block_size))
        self.max_p_sharpe_negative = float(max_p_sharpe_negative)
        self.max_p_dd_gt_40 = float(max_p_dd_gt_40)
        self.min_sharpe_p05 = float(min_sharpe_p05)
        self.random_seed = int(random_seed)

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

    def _iid_bootstrap(self, r: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        idx = rng.integers(0, len(r), size=len(r))
        return r[idx]

    def _block_bootstrap(self, r: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n = len(r)
        out: List[float] = []
        while len(out) < n:
            start = int(rng.integers(0, max(1, n - self.block_size + 1)))
            out.extend(r[start:start + self.block_size].tolist())
        return np.asarray(out[:n], dtype=float)

    def _regime_sim(self, r: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n = len(r)
        if n < 10:
            return self._iid_bootstrap(r, rng)
        vol = np.abs(r - np.mean(r))
        thr = float(np.median(vol))
        state = (vol > thr).astype(int)
        low = r[state == 0]
        high = r[state == 1]
        if low.size < 2 or high.size < 2:
            return self._iid_bootstrap(r, rng)

        # Empirical 2-state transition matrix.
        trans = np.ones((2, 2), dtype=float) * 1e-3
        for i in range(n - 1):
            trans[state[i], state[i + 1]] += 1.0
        trans = trans / np.maximum(trans.sum(axis=1, keepdims=True), 1e-12)

        path = np.zeros(n, dtype=float)
        s = int(state[-1])
        low_mu, low_sd = float(np.mean(low)), float(np.std(low))
        high_mu, high_sd = float(np.mean(high)), float(np.std(high))
        low_sd = max(1e-6, low_sd)
        high_sd = max(1e-6, high_sd)
        for i in range(n):
            if s == 0:
                path[i] = float(rng.normal(low_mu, low_sd))
            else:
                path[i] = float(rng.normal(high_mu, high_sd))
            s = int(0 if rng.random() < trans[s, 0] else 1)
        return path

    def _inject_shock(self, path: np.ndarray, r: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n = len(path)
        if n < 8:
            return path
        block = max(3, min(self.block_size, n // 2))
        # Worst historical block replay.
        worst_sum = None
        worst_slice = r[:block]
        for i in range(0, len(r) - block + 1):
            s = float(np.sum(r[i:i + block]))
            if (worst_sum is None) or (s < worst_sum):
                worst_sum = s
                worst_slice = r[i:i + block]
        start = int(rng.integers(0, n - block + 1))
        out = path.copy()
        out[start:start + block] = worst_slice
        return out

    def run_simulations(self, returns: Iterable[float]) -> np.ndarray:
        r = self._to_array(returns)
        if r.size <= 2:
            return np.zeros((0, 0), dtype=float)
        rng = np.random.default_rng(self.random_seed)
        sims = np.zeros((self.n_sim, len(r)), dtype=float)
        for i in range(self.n_sim):
            mode = i % 4
            if mode == 0:
                path = self._iid_bootstrap(r, rng)
            elif mode == 1:
                path = self._block_bootstrap(r, rng)
            elif mode == 2:
                path = self._regime_sim(r, rng)
            else:
                path = self._inject_shock(self._block_bootstrap(r, rng), r, rng)
            sims[i, :] = path
        return sims

    def compute_survival_metrics(self, simulations: np.ndarray) -> Dict[str, float]:
        if simulations.size == 0:
            return {
                "p_sharpe_negative": 1.0,
                "p_dd_gt_40": 1.0,
                "sharpe_p05": -1.0,
                "median_terminal_return": -1.0,
            }

        sharpes = np.asarray([self._sharpe(simulations[i, :]) for i in range(simulations.shape[0])], dtype=float)
        maxdds = np.asarray([self._max_drawdown(simulations[i, :]) for i in range(simulations.shape[0])], dtype=float)
        terminal = np.asarray([np.prod(1.0 + simulations[i, :]) - 1.0 for i in range(simulations.shape[0])], dtype=float)
        return {
            "p_sharpe_negative": float(np.mean(sharpes < 0.0)),
            "p_dd_gt_40": float(np.mean(maxdds < -0.40)),
            "sharpe_p05": float(np.percentile(sharpes, 5)),
            "median_terminal_return": float(np.median(terminal)),
        }

    def qualify(self, returns: Iterable[float]) -> MonteCarloStabilityResult:
        simulations = self.run_simulations(returns)
        metrics = self.compute_survival_metrics(simulations)
        status = "stable"
        if metrics["p_sharpe_negative"] > self.max_p_sharpe_negative:
            status = "reject"
        if metrics["p_dd_gt_40"] > self.max_p_dd_gt_40:
            status = "reject"
        if metrics["sharpe_p05"] < self.min_sharpe_p05:
            status = "reject"
        return MonteCarloStabilityResult(
            p_sharpe_negative=float(metrics["p_sharpe_negative"]),
            p_dd_gt_40=float(metrics["p_dd_gt_40"]),
            sharpe_p05=float(metrics["sharpe_p05"]),
            median_terminal_return=float(metrics["median_terminal_return"]),
            status=status,
            n_simulations=int(simulations.shape[0]),
        )
