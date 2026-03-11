"""Phase 4/8/9 portfolio convex allocation with manifold intelligence controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class ConvexAllocationResult:
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    objective_value: float
    leverage: float
    max_pair_correlation: float
    cluster_exposure: Dict[str, float]
    constraints_ok: bool
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": {str(k): float(v) for k, v in dict(self.weights or {}).items()},
            "expected_return": float(self.expected_return),
            "volatility": float(self.volatility),
            "objective_value": float(self.objective_value),
            "leverage": float(self.leverage),
            "max_pair_correlation": float(self.max_pair_correlation),
            "cluster_exposure": {str(k): float(v) for k, v in dict(self.cluster_exposure or {}).items()},
            "constraints_ok": bool(self.constraints_ok),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class MultiHorizonAllocationResult:
    aggregated_weights: Dict[str, float]
    horizon_weights: Dict[str, Dict[str, float]]
    expected_return: float
    volatility: float
    objective_value: float
    leverage: float
    constraints_ok: bool
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aggregated_weights": {str(k): float(v) for k, v in dict(self.aggregated_weights or {}).items()},
            "horizon_weights": {
                str(h): {str(k): float(v) for k, v in dict(w or {}).items()}
                for h, w in dict(self.horizon_weights or {}).items()
            },
            "expected_return": float(self.expected_return),
            "volatility": float(self.volatility),
            "objective_value": float(self.objective_value),
            "leverage": float(self.leverage),
            "constraints_ok": bool(self.constraints_ok),
            "metadata": dict(self.metadata or {}),
        }


class ConvexPortfolioAllocator:
    """Projected-gradient optimizer with crisis-correlation and manifold penalties."""

    def __init__(
        self,
        *,
        risk_aversion: float = 2.0,
        return_weight: float = 1.0,
        concentration_penalty: float = 0.05,
        cluster_penalty: float = 3.0,
        turnover_penalty: float = 0.20,
        lr: float = 0.12,
        iters: int = 180,
        crisis_corr_spike: float = 0.35,
    ):
        self.risk_aversion = float(max(1e-8, risk_aversion))
        self.return_weight = float(max(1e-8, return_weight))
        self.concentration_penalty = float(max(0.0, concentration_penalty))
        self.cluster_penalty = float(max(0.0, cluster_penalty))
        self.turnover_penalty = float(max(0.0, turnover_penalty))
        self.lr = float(max(1e-4, lr))
        self.iters = int(max(20, iters))
        self.crisis_corr_spike = float(np.clip(crisis_corr_spike, 0.0, 0.95))

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
        diag = np.maximum(np.diag(sigma), 1e-8)
        sigma[np.diag_indices(n)] = diag
        sigma = sigma + (1e-8 * np.eye(n))
        return sigma

    @staticmethod
    def _build_matrix(
        ids: List[str],
        mapping: Mapping[str, Mapping[str, float]] | None,
    ) -> np.ndarray:
        n = len(ids)
        if not mapping:
            return np.zeros((n, n), dtype=float)
        out = np.zeros((n, n), dtype=float)
        for i, si in enumerate(ids):
            row = dict(mapping.get(si, {}) or {})
            for j, sj in enumerate(ids):
                out[i, j] = float(row.get(sj, 0.0) or 0.0)
        out = 0.5 * (out + out.T)
        out[np.diag_indices(n)] = 0.0
        return out

    @staticmethod
    def _psd_project(mat: np.ndarray) -> np.ndarray:
        m = 0.5 * (np.asarray(mat, dtype=float) + np.asarray(mat, dtype=float).T)
        eigvals, eigvecs = np.linalg.eigh(m)
        eigvals = np.maximum(eigvals, 0.0)
        return (eigvecs @ np.diag(eigvals) @ eigvecs.T).astype(float)

    def _crisis_covariance(self, sigma: np.ndarray) -> np.ndarray:
        n = int(sigma.shape[0])
        std = np.sqrt(np.maximum(np.diag(sigma), 1e-10))
        denom = np.outer(std, std)
        corr = sigma / np.maximum(denom, 1e-12)
        corr = np.clip(corr, -0.99, 0.99)
        np.fill_diagonal(corr, 1.0)
        sign = np.sign(corr)
        corr_abs = np.abs(corr)
        corr_shocked = corr_abs + (self.crisis_corr_spike * (1.0 - corr_abs))
        corr_shocked = sign * np.clip(corr_shocked, 0.0, 0.999)
        np.fill_diagonal(corr_shocked, 1.0)
        shocked = corr_shocked * denom
        shocked = 0.5 * (shocked + shocked.T)
        eigvals, eigvecs = np.linalg.eigh(shocked)
        eigvals = np.maximum(eigvals, 1e-8)
        return (eigvecs @ np.diag(eigvals) @ eigvecs.T).astype(float)

    @staticmethod
    def _project_with_caps_and_leverage(x: np.ndarray, caps: np.ndarray, leverage_limit: float) -> np.ndarray:
        x = np.clip(np.asarray(x, dtype=float), 0.0, np.asarray(caps, dtype=float))
        lev = float(np.sum(np.abs(x)))
        if lev > float(leverage_limit) > 0.0:
            x = x * (float(leverage_limit) / max(lev, 1e-12))
        return np.clip(x, 0.0, caps)

    @staticmethod
    def _enforce_cluster_caps(
        x: np.ndarray,
        cluster_indices: Dict[str, np.ndarray],
        cluster_cap: float,
        leverage_limit: float,
    ) -> np.ndarray:
        out = np.asarray(x, dtype=float).copy()
        cap = float(max(1e-8, cluster_cap))
        for _ in range(4):
            adjusted = False
            for idx in cluster_indices.values():
                expo = float(np.sum(out[idx]))
                if expo > cap:
                    out[idx] = out[idx] * (cap / max(expo, 1e-12))
                    adjusted = True
            lev = float(np.sum(np.abs(out)))
            if lev > float(leverage_limit) > 0.0:
                out = out * (float(leverage_limit) / max(lev, 1e-12))
                adjusted = True
            if not adjusted:
                break
        return np.maximum(out, 0.0)

    @staticmethod
    def _max_pair_correlation(sigma: np.ndarray) -> float:
        std = np.sqrt(np.maximum(np.diag(sigma), 1e-10))
        corr = sigma / np.maximum(np.outer(std, std), 1e-12)
        corr = np.clip(corr, -0.999, 0.999)
        mask = ~np.eye(len(std), dtype=bool)
        if not np.any(mask):
            return 0.0
        return float(np.max(np.abs(corr[mask])))

    @staticmethod
    def _cluster_exposure(strategy_ids: List[str], weights: np.ndarray, cluster_map: Dict[str, str]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for i, sid in enumerate(strategy_ids):
            cluster = str(cluster_map.get(sid, sid))
            out[cluster] = out.get(cluster, 0.0) + float(weights[i])
        return out

    @staticmethod
    def _turnover(new_w: np.ndarray, prev_w: np.ndarray) -> float:
        if new_w.size != prev_w.size:
            return float(np.sum(np.abs(new_w)))
        return float(np.sum(np.abs(new_w - prev_w)))

    @staticmethod
    def _distance_diversity_score(weights: np.ndarray, dist: np.ndarray) -> float:
        if weights.size == 0 or dist.size == 0:
            return 0.0
        w = np.asarray(weights, dtype=float)
        total = float(np.sum(w))
        if total <= 1e-12:
            return 0.0
        w = w / total
        return float(w @ dist @ w)

    def optimize(
        self,
        *,
        strategy_ids: List[str],
        expected_edges: Dict[str, float],
        covariance: Mapping[str, Mapping[str, float]],
        capacity_caps: Dict[str, float],
        cluster_map: Dict[str, str] | None = None,
        current_weights: Dict[str, float] | None = None,
        leverage_limit: float = 1.0,
        cluster_cap: float = 0.55,
        correlation_threshold: float = 0.85,
        max_turnover: float | None = None,
        factor_exposures: Dict[str, Dict[str, float]] | None = None,
        factor_limits: Dict[str, float] | None = None,
        manifold_redundancy: Dict[str, float] | None = None,
        manifold_distance: Mapping[str, Mapping[str, float]] | None = None,
        manifold_penalty_eta: float = 0.0,
        manifold_diversity_delta: float = 0.0,
    ) -> ConvexAllocationResult:
        if not strategy_ids:
            return ConvexAllocationResult(
                weights={},
                expected_return=0.0,
                volatility=0.0,
                objective_value=0.0,
                leverage=0.0,
                max_pair_correlation=0.0,
                cluster_exposure={},
                constraints_ok=True,
                metadata={"reason": "empty_strategy_universe"},
            )
        if len(strategy_ids) == 1:
            sid = str(strategy_ids[0])
            cap = float(np.clip(self._safe_float(capacity_caps.get(sid, 1.0), 1.0), 0.0, leverage_limit))
            w = {sid: cap}
            return ConvexAllocationResult(
                weights=w,
                expected_return=float(self._safe_float(expected_edges.get(sid, 0.0), 0.0) * cap),
                volatility=0.0,
                objective_value=0.0,
                leverage=float(abs(cap)),
                max_pair_correlation=0.0,
                cluster_exposure={str((cluster_map or {}).get(sid, sid)): float(cap)},
                constraints_ok=True,
                metadata={"single_strategy": True},
            )

        ids = [str(s) for s in strategy_ids]
        n = len(ids)
        cluster_map = dict(cluster_map or {})
        caps = np.asarray(
            [self._safe_float(capacity_caps.get(s, 1.0), 1.0 / n) for s in ids],
            dtype=float,
        )
        caps = np.clip(caps, 0.0, float(max(leverage_limit, 1e-6)))
        if float(np.sum(caps)) <= 1e-10:
            caps = np.ones(n, dtype=float) * (float(leverage_limit) / n)

        mu = np.asarray([self._safe_float(expected_edges.get(s, 0.0), 0.0) for s in ids], dtype=float)
        if float(np.max(np.abs(mu))) <= 1e-10:
            mu = np.ones(n, dtype=float) * 1e-6

        sigma_base = self._build_covariance(ids, covariance)
        sigma_crisis = self._crisis_covariance(sigma_base)
        sigma = (0.70 * sigma_base) + (0.30 * sigma_crisis)
        sigma = 0.5 * (sigma + sigma.T)

        dmat = self._build_matrix(ids, manifold_distance)
        dmat_psd = self._psd_project(dmat) if np.any(dmat) else dmat

        delta_req = float(max(0.0, manifold_diversity_delta))
        delta_eff = 0.0
        if np.any(dmat_psd) and delta_req > 0.0:
            eig_sigma = np.linalg.eigvalsh(sigma)
            eig_d = np.linalg.eigvalsh(dmat_psd)
            lam_min_sigma = float(max(1e-8, np.min(eig_sigma)))
            lam_max_d = float(max(1e-8, np.max(eig_d)))
            delta_bound = float(0.95 * lam_min_sigma / lam_max_d)
            delta_eff = float(min(delta_req, max(0.0, delta_bound)))
        sigma_eff = sigma - (delta_eff * dmat_psd)
        sigma_eff = self._psd_project(sigma_eff)
        sigma_eff[np.diag_indices(n)] = np.maximum(np.diag(sigma_eff), 1e-8)

        eta = float(max(0.0, manifold_penalty_eta))
        redundancy_vec = np.asarray(
            [self._safe_float(dict(manifold_redundancy or {}).get(sid, 0.0), 0.0) for sid in ids],
            dtype=float,
        )

        if current_weights:
            x0 = np.asarray([self._safe_float(current_weights.get(s, 0.0), 0.0) for s in ids], dtype=float)
        else:
            x0 = np.asarray([min(caps[i], float(leverage_limit) / n) for i in range(n)], dtype=float)
        x = self._project_with_caps_and_leverage(x0, caps, leverage_limit)
        prev_x = np.asarray(x, dtype=float)

        cluster_indices: Dict[str, np.ndarray] = {}
        for idx, sid in enumerate(ids):
            cluster = str(cluster_map.get(sid, sid))
            cluster_indices.setdefault(cluster, []).append(idx)
        cluster_indices = {k: np.asarray(v, dtype=int) for k, v in cluster_indices.items()}
        x = self._enforce_cluster_caps(x, cluster_indices, float(cluster_cap), float(leverage_limit))

        for _ in range(self.iters):
            grad = (2.0 * self.risk_aversion * (sigma_eff @ x)) - (self.return_weight * mu)
            if eta > 0.0:
                grad = grad + (eta * redundancy_vec)
            if self.concentration_penalty > 0.0:
                grad = grad + (2.0 * self.concentration_penalty * x)
            if self.turnover_penalty > 0.0:
                grad = grad + (2.0 * self.turnover_penalty * (x - prev_x))
            if self.cluster_penalty > 0.0:
                for idx in cluster_indices.values():
                    expo = float(np.sum(x[idx]))
                    excess = expo - float(cluster_cap)
                    if excess > 0.0:
                        grad[idx] = grad[idx] + (2.0 * self.cluster_penalty * excess)
            if factor_exposures and factor_limits:
                for fac, lim in dict(factor_limits or {}).items():
                    limit = float(max(1e-8, lim))
                    loads = np.asarray(
                        [self._safe_float(dict(factor_exposures.get(sid, {}) or {}).get(str(fac), 0.0), 0.0) for sid in ids],
                        dtype=float,
                    )
                    exp = float(np.dot(x, loads))
                    excess = abs(exp) - limit
                    if excess > 0.0:
                        grad = grad + (2.0 * self.cluster_penalty * excess * np.sign(exp) * loads)
            x = self._project_with_caps_and_leverage(x - (self.lr * grad), caps, leverage_limit)
            x = self._enforce_cluster_caps(x, cluster_indices, float(cluster_cap), float(leverage_limit))
            if max_turnover is not None:
                max_to = float(max(0.0, max_turnover))
                to = self._turnover(x, prev_x)
                if to > max_to > 0.0:
                    alpha = float(max_to / max(to, 1e-12))
                    x = prev_x + (alpha * (x - prev_x))
                    x = self._project_with_caps_and_leverage(x, caps, leverage_limit)
                    x = self._enforce_cluster_caps(x, cluster_indices, float(cluster_cap), float(leverage_limit))

        expected_return = float(np.dot(x, mu))
        variance = float(x @ sigma_eff @ x)
        volatility = float(np.sqrt(max(1e-12, variance)))
        redundancy_penalty = float(eta * np.dot(redundancy_vec, x)) if eta > 0.0 else 0.0
        diversity_reward = float(delta_eff * (x @ dmat_psd @ x)) if delta_eff > 0.0 else 0.0
        objective_value = float((self.risk_aversion * variance) - (self.return_weight * expected_return) + redundancy_penalty - diversity_reward)
        leverage = float(np.sum(np.abs(x)))
        max_pair_corr = self._max_pair_correlation(sigma_crisis)
        cluster_exposure = self._cluster_exposure(ids, x, cluster_map)

        caps_ok = bool(np.all(x <= (caps + 1e-6)))
        leverage_ok = bool(leverage <= (float(leverage_limit) + 1e-6))
        cluster_ok = bool(all(v <= (float(cluster_cap) + 1e-6) for v in cluster_exposure.values()))
        corr_ok = bool(max_pair_corr <= float(correlation_threshold))
        turnover = self._turnover(x, prev_x)

        eig_base = np.linalg.eigvalsh(sigma_base)
        eig_crisis = np.linalg.eigvalsh(sigma_crisis)
        eig_base = np.maximum(np.asarray(eig_base, dtype=float), 1e-12)
        eig_crisis = np.maximum(np.asarray(eig_crisis, dtype=float), 1e-12)
        eig_ratio_base = float(np.max(eig_base) / max(np.sum(eig_base), 1e-12))
        eig_ratio_crisis = float(np.max(eig_crisis) / max(np.sum(eig_crisis), 1e-12))
        eig_spike = float(eig_ratio_crisis / max(eig_ratio_base, 1e-12))

        constraints_ok = bool(caps_ok and leverage_ok and cluster_ok and corr_ok)
        diversity_score = self._distance_diversity_score(x, dmat)

        return ConvexAllocationResult(
            weights={sid: float(x[i]) for i, sid in enumerate(ids)},
            expected_return=expected_return,
            volatility=volatility,
            objective_value=objective_value,
            leverage=leverage,
            max_pair_correlation=max_pair_corr,
            cluster_exposure=cluster_exposure,
            constraints_ok=constraints_ok,
            metadata={
                "caps_ok": caps_ok,
                "leverage_ok": leverage_ok,
                "cluster_ok": cluster_ok,
                "corr_ok": corr_ok,
                "turnover": float(turnover),
                "cluster_cap": float(cluster_cap),
                "leverage_limit": float(leverage_limit),
                "correlation_threshold": float(correlation_threshold),
                "eigen_ratio_base": eig_ratio_base,
                "eigen_ratio_crisis": eig_ratio_crisis,
                "eigen_spike": eig_spike,
                "manifold_penalty_eta": float(eta),
                "manifold_diversity_delta_requested": float(delta_req),
                "manifold_diversity_delta_effective": float(delta_eff),
                "redundancy_penalty": float(redundancy_penalty),
                "diversity_reward": float(diversity_reward),
                "manifold_diversity_score": float(diversity_score),
            },
        )

    def optimize_multi_horizon(
        self,
        *,
        strategy_ids: List[str],
        horizons: List[str],
        expected_edges_by_horizon: Mapping[str, Mapping[str, float]],
        covariance: Mapping[str, Mapping[str, float]],
        capacity_caps: Mapping[str, float],
        cluster_map: Mapping[str, str] | None = None,
        leverage_limit: float = 1.0,
        cluster_cap: float = 0.55,
        cross_horizon_corr: float = 0.35,
        horizon_mix: Mapping[str, float] | None = None,
        manifold_redundancy: Mapping[str, float] | None = None,
        manifold_distance: Mapping[str, Mapping[str, float]] | None = None,
        manifold_penalty_eta: float = 0.0,
        manifold_diversity_delta: float = 0.0,
    ) -> MultiHorizonAllocationResult:
        ids = [str(s) for s in list(strategy_ids or [])]
        hs = [str(h) for h in list(horizons or [])]
        if not ids or not hs:
            return MultiHorizonAllocationResult(
                aggregated_weights={},
                horizon_weights={},
                expected_return=0.0,
                volatility=0.0,
                objective_value=0.0,
                leverage=0.0,
                constraints_ok=True,
                metadata={"reason": "empty_multi_horizon_universe"},
            )

        n_s = len(ids)
        n_h = len(hs)
        n = n_s * n_h
        base_sigma = self._build_covariance(ids, covariance)

        # Build block covariance matrix Sigma_multi.
        sigma = np.zeros((n, n), dtype=float)
        for h1 in range(n_h):
            for h2 in range(n_h):
                d = abs(h1 - h2)
                rho_h = float(np.clip(cross_horizon_corr ** d if d > 0 else 1.0, 0.0, 1.0))
                block = rho_h * base_sigma
                i0 = h1 * n_s
                j0 = h2 * n_s
                sigma[i0 : i0 + n_s, j0 : j0 + n_s] = block
        sigma = 0.5 * (sigma + sigma.T)
        sigma[np.diag_indices(n)] = np.maximum(np.diag(sigma), 1e-8)

        # Build expected return vector.
        mu = np.zeros(n, dtype=float)
        for h_idx, h in enumerate(hs):
            edges = dict(expected_edges_by_horizon.get(h, {}) or {})
            for i, sid in enumerate(ids):
                mu[(h_idx * n_s) + i] = float(edges.get(sid, 0.0) or 0.0)
        if float(np.max(np.abs(mu))) <= 1e-10:
            mu += 1e-6

        mix_raw = {str(h): float(dict(horizon_mix or {}).get(h, 1.0 / n_h)) for h in hs}
        mix_total = float(sum(max(0.0, v) for v in mix_raw.values()))
        if mix_total <= 1e-12:
            mix_raw = {h: 1.0 / n_h for h in hs}
            mix_total = 1.0
        mix = {h: float(max(0.0, v) / mix_total) for h, v in mix_raw.items()}

        caps = np.zeros(n, dtype=float)
        for h_idx, h in enumerate(hs):
            h_cap_share = float(mix.get(h, 0.0))
            for i, sid in enumerate(ids):
                base_cap = float(max(0.0, capacity_caps.get(sid, 0.0)))
                caps[(h_idx * n_s) + i] = float(base_cap * h_cap_share)
        if float(np.sum(caps)) <= 1e-10:
            caps[:] = float(leverage_limit) / n

        # Map strategy-level manifold matrices into multi-horizon space.
        d_base = self._build_matrix(ids, manifold_distance)
        d_base = self._psd_project(d_base) if np.any(d_base) else d_base
        d_multi = np.zeros((n, n), dtype=float)
        for h1 in range(n_h):
            for h2 in range(n_h):
                d = abs(h1 - h2)
                rho_h = float(np.clip(cross_horizon_corr ** d if d > 0 else 1.0, 0.0, 1.0))
                block = rho_h * d_base
                i0 = h1 * n_s
                j0 = h2 * n_s
                d_multi[i0 : i0 + n_s, j0 : j0 + n_s] = block
        d_multi = self._psd_project(0.5 * (d_multi + d_multi.T)) if np.any(d_multi) else d_multi

        red_s = np.asarray([float(dict(manifold_redundancy or {}).get(sid, 0.0) or 0.0) for sid in ids], dtype=float)
        red = np.tile(red_s, n_h)

        delta_req = float(max(0.0, manifold_diversity_delta))
        delta_eff = 0.0
        if np.any(d_multi) and delta_req > 0.0:
            eig_sigma = np.linalg.eigvalsh(sigma)
            eig_d = np.linalg.eigvalsh(d_multi)
            lam_min_sigma = float(max(1e-8, np.min(eig_sigma)))
            lam_max_d = float(max(1e-8, np.max(eig_d)))
            delta_eff = float(min(delta_req, 0.95 * lam_min_sigma / lam_max_d))
        sigma_eff = self._psd_project(sigma - (delta_eff * d_multi))
        sigma_eff[np.diag_indices(n)] = np.maximum(np.diag(sigma_eff), 1e-8)

        cluster_map = dict(cluster_map or {})
        cluster_indices: Dict[str, List[int]] = {}
        for h_idx, _h in enumerate(hs):
            for i, sid in enumerate(ids):
                idx = (h_idx * n_s) + i
                cluster = str(cluster_map.get(sid, sid))
                cluster_indices.setdefault(cluster, []).append(idx)
        cluster_indices = {k: np.asarray(v, dtype=int) for k, v in cluster_indices.items()}

        x = np.asarray([min(float(leverage_limit) / n, caps[i]) for i in range(n)], dtype=float)
        x = self._project_with_caps_and_leverage(x, caps, leverage_limit)
        x = self._enforce_cluster_caps(x, cluster_indices, float(cluster_cap), float(leverage_limit))
        prev_x = np.asarray(x, dtype=float)
        eta = float(max(0.0, manifold_penalty_eta))

        for _ in range(self.iters):
            grad = (2.0 * self.risk_aversion * (sigma_eff @ x)) - (self.return_weight * mu)
            if eta > 0.0:
                grad = grad + (eta * red)
            if self.concentration_penalty > 0.0:
                grad = grad + (2.0 * self.concentration_penalty * x)
            if self.turnover_penalty > 0.0:
                grad = grad + (2.0 * self.turnover_penalty * (x - prev_x))
            x = self._project_with_caps_and_leverage(x - (self.lr * grad), caps, leverage_limit)
            x = self._enforce_cluster_caps(x, cluster_indices, float(cluster_cap), float(leverage_limit))

        # Aggregate back to strategy and per-horizon maps.
        h_weights: Dict[str, Dict[str, float]] = {}
        agg = {sid: 0.0 for sid in ids}
        for h_idx, h in enumerate(hs):
            row: Dict[str, float] = {}
            for i, sid in enumerate(ids):
                w = float(x[(h_idx * n_s) + i])
                row[sid] = w
                agg[sid] = agg.get(sid, 0.0) + w
            h_weights[h] = row

        expected_return = float(np.dot(x, mu))
        variance = float(x @ sigma_eff @ x)
        volatility = float(np.sqrt(max(1e-12, variance)))
        redundancy_penalty = float(eta * np.dot(red, x)) if eta > 0.0 else 0.0
        diversity_reward = float(delta_eff * (x @ d_multi @ x)) if delta_eff > 0.0 else 0.0
        objective = float((self.risk_aversion * variance) - (self.return_weight * expected_return) + redundancy_penalty - diversity_reward)
        leverage = float(np.sum(np.abs(x)))

        # caps and cluster checks on vectorized variable.
        caps_ok = bool(np.all(x <= (caps + 1e-6)))
        leverage_ok = bool(leverage <= (float(leverage_limit) + 1e-6))
        cluster_ok = True
        cluster_expo: Dict[str, float] = {}
        for c, idx in cluster_indices.items():
            expo = float(np.sum(x[idx]))
            cluster_expo[c] = expo
            if expo > float(cluster_cap) + 1e-6:
                cluster_ok = False

        return MultiHorizonAllocationResult(
            aggregated_weights={sid: float(v) for sid, v in agg.items()},
            horizon_weights={str(h): {str(k): float(v) for k, v in row.items()} for h, row in h_weights.items()},
            expected_return=expected_return,
            volatility=volatility,
            objective_value=objective,
            leverage=leverage,
            constraints_ok=bool(caps_ok and leverage_ok and cluster_ok),
            metadata={
                "multi_horizon": True,
                "horizons": list(hs),
                "n_variables": int(n),
                "caps_ok": bool(caps_ok),
                "leverage_ok": bool(leverage_ok),
                "cluster_ok": bool(cluster_ok),
                "cluster_exposure": {str(k): float(v) for k, v in cluster_expo.items()},
                "horizon_mix": {str(k): float(v) for k, v in mix.items()},
                "manifold_penalty_eta": float(eta),
                "manifold_diversity_delta_requested": float(delta_req),
                "manifold_diversity_delta_effective": float(delta_eff),
                "redundancy_penalty": float(redundancy_penalty),
                "diversity_reward": float(diversity_reward),
            },
        )
