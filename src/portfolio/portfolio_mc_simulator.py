"""Phase 4 portfolio-level Monte Carlo with regime and correlation stress."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class PortfolioMonteCarloResult:
    p_sharpe_negative: float
    p_maxdd_breach: float
    expected_drawdown: float
    cvar_95: float
    recovery_days_p95: float
    drawdown_cluster_p95: float
    time_under_water_mean: float
    stability_multiplier: float
    status: str
    n_paths: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p_sharpe_negative": float(self.p_sharpe_negative),
            "p_maxdd_breach": float(self.p_maxdd_breach),
            "expected_drawdown": float(self.expected_drawdown),
            "cvar_95": float(self.cvar_95),
            "recovery_days_p95": float(self.recovery_days_p95),
            "drawdown_cluster_p95": float(self.drawdown_cluster_p95),
            "time_under_water_mean": float(self.time_under_water_mean),
            "stability_multiplier": float(self.stability_multiplier),
            "status": str(self.status),
            "n_paths": int(self.n_paths),
        }


class PortfolioMonteCarloSimulator:
    def __init__(
        self,
        *,
        n_paths: int = 600,
        horizon_days: int = 30,
        block_size: int = 5,
        crisis_corr_spike: float = 0.35,
        penalty_scale: float = 0.60,
        min_multiplier: float = 0.60,
    ):
        self.n_paths = int(max(100, n_paths))
        self.horizon_days = int(max(5, horizon_days))
        self.block_size = int(max(2, block_size))
        self.crisis_corr_spike = float(np.clip(crisis_corr_spike, 0.0, 0.95))
        self.penalty_scale = float(np.clip(penalty_scale, 0.0, 1.0))
        self.min_multiplier = float(np.clip(min_multiplier, 0.05, 1.0))

    @staticmethod
    def _seed(seed_key: str) -> int:
        digest = sha256(str(seed_key).encode("utf-8")).hexdigest()[:16]
        return int(digest, 16) % (2**31 - 1)

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
    def _sharpe(r: np.ndarray) -> float:
        if r.size <= 1:
            return 0.0
        mu = float(np.mean(r))
        sigma = float(np.std(r))
        return float(mu / (sigma + 1e-8))

    @staticmethod
    def _max_drawdown(r: np.ndarray) -> float:
        if r.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + r)
        peaks = np.maximum.accumulate(eq)
        dd = (eq / (peaks + 1e-12)) - 1.0
        return float(np.min(dd))

    @staticmethod
    def _recovery_days(r: np.ndarray) -> int:
        if r.size == 0:
            return 0
        eq = np.cumprod(1.0 + r)
        peaks = np.maximum.accumulate(eq)
        underwater = eq < peaks
        longest = 0
        run = 0
        for b in underwater.tolist():
            if b:
                run += 1
                if run > longest:
                    longest = run
            else:
                run = 0
        return int(longest)

    @staticmethod
    def _drawdown_cluster_severity(r: np.ndarray, dd_threshold: float = 0.08) -> float:
        if r.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + r)
        peaks = np.maximum.accumulate(eq)
        dd = 1.0 - (eq / np.maximum(peaks, 1e-12))
        mask = dd > float(dd_threshold)
        if not np.any(mask):
            return 0.0
        runs: List[float] = []
        current = 0
        area = 0.0
        for i, b in enumerate(mask.tolist()):
            if b:
                current += 1
                area += float(dd[i])
            else:
                if current > 0:
                    runs.append(float(area))
                    current = 0
                    area = 0.0
        if current > 0:
            runs.append(float(area))
        return float(max(runs) if runs else 0.0)

    @staticmethod
    def _time_under_water_ratio(r: np.ndarray) -> float:
        if r.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + r)
        peaks = np.maximum.accumulate(eq)
        underwater = eq < peaks
        return float(np.mean(underwater.astype(float)))

    @staticmethod
    def _build_covariance(
        strategy_ids: List[str],
        covariance: Mapping[str, Mapping[str, float]],
    ) -> np.ndarray:
        n = len(strategy_ids)
        sigma = np.zeros((n, n), dtype=float)
        for i, si in enumerate(strategy_ids):
            for j, sj in enumerate(strategy_ids):
                sigma[i, j] = float(covariance.get(si, {}).get(sj, 0.0))
        sigma = 0.5 * (sigma + sigma.T)
        sigma[np.diag_indices(n)] = np.maximum(np.diag(sigma), 1e-8)
        sigma = sigma + (1e-8 * np.eye(n))
        return sigma

    def _crisis_covariance(self, sigma: np.ndarray) -> np.ndarray:
        std = np.sqrt(np.maximum(np.diag(sigma), 1e-10))
        denom = np.maximum(np.outer(std, std), 1e-12)
        corr = np.clip(sigma / denom, -0.99, 0.99)
        np.fill_diagonal(corr, 1.0)
        sign = np.sign(corr)
        abs_corr = np.abs(corr)
        shocked = abs_corr + (self.crisis_corr_spike * (1.0 - abs_corr))
        shocked = np.clip(shocked, 0.0, 0.999)
        shocked = sign * shocked
        np.fill_diagonal(shocked, 1.0)
        cov = shocked * denom
        cov = 0.5 * (cov + cov.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.maximum(eigvals, 1e-8)
        return eigvecs @ np.diag(eigvals) @ eigvecs.T

    @staticmethod
    def _align_history(
        strategy_ids: List[str],
        return_series_map: Mapping[str, List[float]],
    ) -> np.ndarray:
        valid: List[np.ndarray] = []
        for sid in strategy_ids:
            arr = np.asarray(list(return_series_map.get(sid, []) or []), dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size > 0:
                valid.append(arr)
            else:
                valid.append(np.asarray([], dtype=float))
        lengths = [len(a) for a in valid if len(a) > 0]
        if not lengths:
            return np.zeros((0, len(strategy_ids)), dtype=float)
        m = int(min(lengths))
        if m <= 1:
            return np.zeros((0, len(strategy_ids)), dtype=float)
        mat = np.zeros((m, len(strategy_ids)), dtype=float)
        for i, arr in enumerate(valid):
            if len(arr) < m:
                mat[:, i] = 0.0
            else:
                mat[:, i] = arr[-m:]
        return mat

    def evaluate(
        self,
        *,
        strategy_ids: List[str],
        weights: Dict[str, float],
        expected_edges: Dict[str, float],
        return_series_map: Mapping[str, List[float]],
        covariance: Mapping[str, Mapping[str, float]],
        drawdown_breach: float = 0.15,
        max_p_dd_breach: float = 0.30,
        seed_key: str = "phase4_portfolio_mc",
    ) -> PortfolioMonteCarloResult:
        ids = [str(s) for s in list(strategy_ids or [])]
        if not ids:
            return PortfolioMonteCarloResult(
                p_sharpe_negative=1.0,
                p_maxdd_breach=1.0,
                expected_drawdown=1.0,
                cvar_95=-1.0,
                recovery_days_p95=float(self.horizon_days),
                drawdown_cluster_p95=1.0,
                time_under_water_mean=1.0,
                stability_multiplier=self.min_multiplier,
                status="reject",
                n_paths=0,
            )
        w = np.asarray([self._safe_float(weights.get(s, 0.0), 0.0) for s in ids], dtype=float)
        lev = float(np.sum(np.abs(w)))
        if lev > 0.0:
            w = w / lev
        else:
            w = np.ones(len(ids), dtype=float) / float(len(ids))

        hist = self._align_history(ids, return_series_map)
        base_cov = self._build_covariance(ids, covariance)
        crisis_cov = self._crisis_covariance(base_cov)
        mu = np.asarray([self._safe_float(expected_edges.get(s, 0.0), 0.0) for s in ids], dtype=float)
        mu = mu / float(max(5, self.horizon_days))

        rng = np.random.default_rng(self._seed(seed_key))
        path_sharpes: List[float] = []
        path_dd: List[float] = []
        terminal_ret: List[float] = []
        recovery_days: List[int] = []
        cluster_scores: List[float] = []
        time_under_water: List[float] = []

        for i in range(self.n_paths):
            mode = i % 4
            if (mode in {0, 3}) and (hist.shape[0] > (self.block_size + 2)):
                # Block bootstrap.
                rows: List[np.ndarray] = []
                while len(rows) < self.horizon_days:
                    start = int(rng.integers(0, hist.shape[0] - self.block_size))
                    rows.extend(hist[start:start + self.block_size, :])
                sim = np.asarray(rows[: self.horizon_days], dtype=float)
            elif mode == 1:
                # Base Gaussian.
                sim = rng.multivariate_normal(mu, base_cov, size=self.horizon_days)
            else:
                # Crisis covariance scenario.
                sim = rng.multivariate_normal(mu, crisis_cov, size=self.horizon_days)

            if mode == 3 and hist.shape[0] > (self.block_size + 2):
                # Inject historical worst portfolio block.
                port_hist = hist @ w
                worst_sum = None
                worst = port_hist[: self.block_size]
                for j in range(0, len(port_hist) - self.block_size + 1):
                    s = float(np.sum(port_hist[j : j + self.block_size]))
                    if (worst_sum is None) or (s < worst_sum):
                        worst_sum = s
                        worst = port_hist[j : j + self.block_size]
                start = int(rng.integers(0, self.horizon_days - self.block_size + 1))
                p = sim @ w
                p[start : start + self.block_size] = worst
                port = p
            else:
                port = sim @ w

            path_sharpes.append(self._sharpe(port))
            dd = abs(self._max_drawdown(port))
            path_dd.append(dd)
            terminal_ret.append(float(np.prod(1.0 + port) - 1.0))
            recovery_days.append(self._recovery_days(port))
            cluster_scores.append(self._drawdown_cluster_severity(port))
            time_under_water.append(self._time_under_water_ratio(port))

        sharpe_arr = np.asarray(path_sharpes, dtype=float)
        dd_arr = np.asarray(path_dd, dtype=float)
        term_arr = np.asarray(terminal_ret, dtype=float)
        rec_arr = np.asarray(recovery_days, dtype=float)

        p_sharpe_negative = float(np.mean(sharpe_arr < 0.0))
        p_dd_breach = float(np.mean(dd_arr > float(drawdown_breach)))
        expected_dd = float(np.mean(dd_arr))
        cvar_95 = float(np.mean(np.sort(term_arr)[: max(1, int(0.05 * len(term_arr)))]))
        recovery_p95 = float(np.percentile(rec_arr, 95))
        cluster_p95 = float(np.percentile(np.asarray(cluster_scores, dtype=float), 95))
        tuw_mean = float(np.mean(np.asarray(time_under_water, dtype=float)))
        multiplier = float(np.clip(1.0 - (self.penalty_scale * p_dd_breach), self.min_multiplier, 1.0))

        status = "stable"
        if p_dd_breach > float(max_p_dd_breach):
            status = "reject"
        if p_sharpe_negative > 0.40:
            status = "reject"
        if cvar_95 < -0.25:
            status = "reject"
        if cluster_p95 > 0.90:
            status = "reject"

        return PortfolioMonteCarloResult(
            p_sharpe_negative=p_sharpe_negative,
            p_maxdd_breach=p_dd_breach,
            expected_drawdown=expected_dd,
            cvar_95=cvar_95,
            recovery_days_p95=recovery_p95,
            drawdown_cluster_p95=cluster_p95,
            time_under_water_mean=tuw_mean,
            stability_multiplier=multiplier,
            status=status,
            n_paths=int(self.n_paths),
        )
