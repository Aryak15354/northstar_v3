"""Advanced capital intelligence models for allocator sizing decisions."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


@dataclass(frozen=True)
class StrategyDiagnosticsPoint:
    strategy_id: str
    trade_count: int
    avg_err: float
    avg_cer: float
    avg_sdr: float
    starvation_ratio: float
    rebalance_efficiency: float
    stability_score: float
    edge_decay: float
    regime_sensitivity: float
    certification_survival_ratio: float


@dataclass(frozen=True)
class DiagnosticsContext:
    loaded_at_utc: str
    strategy_points: Dict[str, StrategyDiagnosticsPoint]
    strategy_return_series: Dict[str, List[float]]
    covariance_matrix: Dict[str, Dict[str, float]]
    policy_recommendations: Dict[str, Any]


@dataclass(frozen=True)
class RegimeStateEstimate:
    latent_risk_level: float
    posterior_variance: float
    multiplier: float
    observation: float


class DiagnosticsContextLoader:
    """Small cached reader for ADE diagnostics used by runtime allocator."""

    def __init__(self, diagnostics_db_path: str, refresh_seconds: int = 60):
        self.diagnostics_db_path = str(diagnostics_db_path)
        self.refresh_seconds = max(5, int(refresh_seconds))
        self._cached: DiagnosticsContext | None = None
        self._cached_at: datetime | None = None

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
    def _safe_json(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        try:
            payload = json.loads(str(raw or "{}"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _build_covariance(self, conn: sqlite3.Connection, strategy_ids: List[str]) -> Dict[str, Dict[str, float]]:
        if not strategy_ids:
            return {}
        try:
            rows = conn.execute(
                """
                SELECT strategy_id, close_event_id, realized_pnl
                FROM trade_diagnostics
                ORDER BY close_event_id ASC
                """
            ).fetchall()
        except Exception:
            rows = []
        series: Dict[str, List[float]] = {sid: [] for sid in strategy_ids}
        for row in rows:
            sid = str(row["strategy_id"] or "")
            if sid not in series:
                continue
            series[sid].append(self._safe_float(row["realized_pnl"], 0.0))

        cov: Dict[str, Dict[str, float]] = {}
        for i, s1 in enumerate(strategy_ids):
            cov[s1] = {}
            arr1 = np.asarray(series.get(s1, []), dtype=float)
            var1 = float(np.var(arr1, ddof=1)) if len(arr1) >= 2 else 0.0
            for j, s2 in enumerate(strategy_ids):
                arr2 = np.asarray(series.get(s2, []), dtype=float)
                var2 = float(np.var(arr2, ddof=1)) if len(arr2) >= 2 else 0.0
                if i == j:
                    cov[s1][s2] = float(max(1e-8, var1))
                    continue
                m = int(min(len(arr1), len(arr2), 64))
                if m < 4:
                    corr = 0.25
                else:
                    tail1 = arr1[-m:]
                    tail2 = arr2[-m:]
                    sd1 = float(np.std(tail1, ddof=1))
                    sd2 = float(np.std(tail2, ddof=1))
                    if sd1 <= 1e-10 or sd2 <= 1e-10:
                        corr = 0.25
                    else:
                        corr = float(np.corrcoef(tail1, tail2)[0, 1])
                        if not np.isfinite(corr):
                            corr = 0.25
                    corr = float(np.clip(corr, -0.95, 0.95))
                cov[s1][s2] = float(corr * np.sqrt(max(var1, 1e-8) * max(var2, 1e-8)))
        return cov

    def _build_strategy_return_series(self, conn: sqlite3.Connection) -> Dict[str, List[float]]:
        try:
            rows = conn.execute(
                """
                SELECT strategy_id, close_event_id, realized_pnl, capital_reserved
                FROM trade_diagnostics
                ORDER BY close_event_id ASC
                """
            ).fetchall()
        except Exception:
            rows = []
        if not rows:
            return {}

        pnl_by_strategy: Dict[str, List[float]] = {}
        abs_pnl: List[float] = []
        for row in rows:
            sid = str(row["strategy_id"] or "")
            if not sid:
                continue
            pnl = self._safe_float(row["realized_pnl"], 0.0)
            cap = self._safe_float(row["capital_reserved"], 0.0)
            if cap > 1e-9:
                ret = pnl / cap
            else:
                ret = pnl
            pnl_by_strategy.setdefault(sid, []).append(float(ret))
            abs_pnl.append(abs(float(ret)))

        if not pnl_by_strategy:
            return {}

        # If values are large absolute PnL points (not returns), normalize to stable return-like scale.
        median_abs = float(np.median(np.asarray(abs_pnl, dtype=float))) if abs_pnl else 0.0
        scale = 1.0
        if median_abs > 1.0:
            scale = float(max(1.0, median_abs * 50.0))

        out: Dict[str, List[float]] = {}
        for sid, series in pnl_by_strategy.items():
            arr = np.asarray(series, dtype=float)
            if scale > 1.0:
                arr = arr / scale
            out[sid] = arr.tolist()
        return out

    def load(self) -> DiagnosticsContext:
        now = datetime.now(timezone.utc)
        if self._cached is not None and self._cached_at is not None:
            if (now - self._cached_at) < timedelta(seconds=self.refresh_seconds):
                return self._cached

        db_path = Path(self.diagnostics_db_path)
        if not db_path.exists():
            ctx = DiagnosticsContext(
                loaded_at_utc=now.isoformat(),
                strategy_points={},
                strategy_return_series={},
                covariance_matrix={},
                policy_recommendations={},
            )
            self._cached = ctx
            self._cached_at = now
            return ctx

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            try:
                strat_rows = conn.execute(
                    """
                    SELECT
                        strategy_id, trade_count, avg_err, avg_cer, avg_sdr, starvation_ratio,
                        rebalance_efficiency, stability_score, edge_decay, regime_sensitivity,
                        certification_survival_ratio
                    FROM strategy_diagnostics
                    """
                ).fetchall()
            except Exception:
                strat_rows = []

            strategy_points: Dict[str, StrategyDiagnosticsPoint] = {}
            for row in strat_rows:
                sid = str(row["strategy_id"] or "")
                if not sid:
                    continue
                strategy_points[sid] = StrategyDiagnosticsPoint(
                    strategy_id=sid,
                    trade_count=int(row["trade_count"] or 0),
                    avg_err=self._safe_float(row["avg_err"], 0.0),
                    avg_cer=self._safe_float(row["avg_cer"], 0.0),
                    avg_sdr=self._safe_float(row["avg_sdr"], 0.0),
                    starvation_ratio=self._safe_float(row["starvation_ratio"], 0.0),
                    rebalance_efficiency=self._safe_float(row["rebalance_efficiency"], 0.0),
                    stability_score=self._safe_float(row["stability_score"], 0.0),
                    edge_decay=self._safe_float(row["edge_decay"], 0.0),
                    regime_sensitivity=self._safe_float(row["regime_sensitivity"], 0.0),
                    certification_survival_ratio=self._safe_float(row["certification_survival_ratio"], 0.0),
                )

            policy = {}
            try:
                row = conn.execute(
                    """
                    SELECT recommendation_json
                    FROM policy_recommendations
                    ORDER BY recommendation_ts DESC
                    LIMIT 1
                    """
                ).fetchone()
                if row is not None:
                    policy = self._safe_json(row["recommendation_json"])
            except Exception:
                policy = {}

            strategy_ids = sorted(strategy_points.keys())
            cov = self._build_covariance(conn, strategy_ids)
            returns = self._build_strategy_return_series(conn)
            ctx = DiagnosticsContext(
                loaded_at_utc=now.isoformat(),
                strategy_points=strategy_points,
                strategy_return_series=returns,
                covariance_matrix=cov,
                policy_recommendations=policy,
            )
            self._cached = ctx
            self._cached_at = now
            return ctx
        finally:
            conn.close()


class BayesianShrinkageModel:
    @staticmethod
    def posterior_edge(
        *,
        expected_edge: float,
        strategy_stat: StrategyDiagnosticsPoint | None,
        prior_strength: float = 20.0,
    ) -> Dict[str, float]:
        prior_strength = max(1e-6, float(prior_strength))
        if strategy_stat is None:
            return {
                "posterior_edge": float(expected_edge),
                "observed_edge": float(expected_edge),
                "sample_n": 0.0,
                "shrinkage_weight": 0.0,
            }
        n = float(max(0, int(strategy_stat.trade_count)))
        observed_edge = float(strategy_stat.avg_err * abs(expected_edge))
        if expected_edge < 0:
            observed_edge *= -1.0
        posterior = ((n * observed_edge) + (prior_strength * float(expected_edge))) / (n + prior_strength)
        return {
            "posterior_edge": float(posterior),
            "observed_edge": float(observed_edge),
            "sample_n": n,
            "shrinkage_weight": float(prior_strength / (n + prior_strength)),
        }


class KellyRegularizedSizer:
    @staticmethod
    def size_fraction(
        *,
        posterior_edge: float,
        variance: float,
        alpha: float = 0.25,
        min_fraction: float = 0.05,
        max_fraction: float = 1.0,
        confidence_scale: float = 1.0,
    ) -> Dict[str, float]:
        variance = float(max(1e-6, variance))
        alpha = float(max(0.0, alpha))
        confidence_scale = float(np.clip(confidence_scale, 0.1, 2.0))
        f_star = float(posterior_edge / variance)
        f = float(alpha * f_star * confidence_scale)
        f = float(np.clip(f, min_fraction, max_fraction))
        return {
            "kelly_fraction_raw": f_star,
            "kelly_fraction_regularized": f,
            "variance_used": variance,
        }


class KalmanRegimeTuner:
    """Single-step deterministic Kalman update from current snapshot inputs."""

    def __init__(self, process_var: float = 0.015, observation_var: float = 0.05, min_multiplier: float = 0.70):
        self.process_var = float(max(1e-6, process_var))
        self.observation_var = float(max(1e-6, observation_var))
        self.min_multiplier = float(np.clip(min_multiplier, 0.10, 1.0))

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def update(self, portfolio_snapshot: Dict[str, Any], risk_snapshot: Dict[str, Any] | None) -> RegimeStateEstimate:
        rs = dict(risk_snapshot or {})
        regime_ctx = dict(portfolio_snapshot.get("regime_context", {}) or {})
        prior = self._safe_float(regime_ctx.get("latent_risk_level", 0.50), 0.50)
        prior = float(np.clip(prior, 0.0, 1.0))
        prior_var = self._safe_float(regime_ctx.get("latent_risk_var", 0.10), 0.10)
        prior_var = float(np.clip(prior_var, 1e-5, 1.0))

        vol_obs = self._safe_float(rs.get("vol_percentile", rs.get("vol_multiplier", 1.0) - 1.0), 0.5)
        vol_obs = float(np.clip(vol_obs, 0.0, 1.0))
        corr_obs = self._safe_float(rs.get("correlation", 0.5), 0.5)
        corr_obs = float(np.clip(corr_obs, 0.0, 1.0))
        drawdown_obs = self._safe_float(rs.get("drawdown_ratio", portfolio_snapshot.get("drawdown_ratio", 0.0)), 0.0)
        drawdown_obs = float(np.clip(drawdown_obs, 0.0, 1.0))
        obs = float(np.clip((0.50 * vol_obs) + (0.30 * corr_obs) + (0.20 * drawdown_obs), 0.0, 1.0))

        p_pred = prior_var + self.process_var
        k_gain = p_pred / (p_pred + self.observation_var)
        post = prior + (k_gain * (obs - prior))
        post_var = (1.0 - k_gain) * p_pred
        post = float(np.clip(post, 0.0, 1.0))
        post_var = float(np.clip(post_var, 1e-5, 1.0))

        # Higher latent risk -> smaller multiplier.
        multiplier = float(np.clip(1.0 - (post * (1.0 - self.min_multiplier)), self.min_multiplier, 1.0))
        return RegimeStateEstimate(
            latent_risk_level=post,
            posterior_variance=post_var,
            multiplier=multiplier,
            observation=obs,
        )


class ConvexAllocationSolver:
    """Projected-gradient convex optimizer over strategy weights."""

    def __init__(self, risk_aversion: float = 2.0, concentration_penalty: float = 0.05, lr: float = 0.15, iters: int = 120):
        self.risk_aversion = float(max(1e-6, risk_aversion))
        self.concentration_penalty = float(max(0.0, concentration_penalty))
        self.lr = float(max(1e-4, lr))
        self.iters = max(10, int(iters))

    @staticmethod
    def _project_simplex_with_caps(x: np.ndarray, caps: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        caps = np.asarray(caps, dtype=float)
        caps = np.clip(caps, 1e-6, 1.0)
        x = np.clip(x, 0.0, caps)
        total = float(np.sum(x))
        if total <= 1e-12:
            x = np.minimum(caps, 1.0 / len(caps))
            total = float(np.sum(x))
        if total <= 1e-12:
            return np.ones_like(x) / float(len(x))
        x = x / total
        # Ensure upper bounds after normalization using iterative redistribution.
        for _ in range(8):
            over = x > caps
            if not np.any(over):
                break
            excess = float(np.sum(x[over] - caps[over]))
            x[over] = caps[over]
            under = ~over
            room = caps[under] - x[under]
            room_sum = float(np.sum(np.maximum(room, 0.0)))
            if room_sum <= 1e-12:
                break
            x[under] += excess * np.maximum(room, 0.0) / room_sum
            x = np.clip(x, 0.0, caps)
            s = float(np.sum(x))
            if s > 1e-12:
                x = x / s
        return x

    def solve(
        self,
        strategy_ids: List[str],
        expected_edges: Dict[str, float],
        covariance: Dict[str, Dict[str, float]],
        caps: Dict[str, float],
        current_weights: Dict[str, float] | None = None,
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}
        if len(strategy_ids) == 1:
            return {strategy_ids[0]: 1.0}

        n = len(strategy_ids)
        mu = np.asarray([float(expected_edges.get(s, 0.0)) for s in strategy_ids], dtype=float)
        if float(np.max(np.abs(mu))) <= 1e-10:
            mu = np.ones(n, dtype=float) * 1e-6

        sigma = np.zeros((n, n), dtype=float)
        for i, si in enumerate(strategy_ids):
            for j, sj in enumerate(strategy_ids):
                sigma[i, j] = float(covariance.get(si, {}).get(sj, 0.0))
        # Numerical stabilization.
        sigma = 0.5 * (sigma + sigma.T)
        diag = np.diag(np.maximum(np.diag(sigma), 1e-6))
        sigma = sigma + (1e-6 * np.eye(n)) + (0.01 * diag)

        ub = np.asarray([float(caps.get(s, 1.0)) for s in strategy_ids], dtype=float)
        ub = np.clip(ub, 1.0 / n, 1.0)

        if current_weights:
            x = np.asarray([float(current_weights.get(s, 0.0)) for s in strategy_ids], dtype=float)
            if float(np.sum(x)) <= 1e-12:
                x = np.ones(n, dtype=float) / n
            else:
                x = np.maximum(x, 0.0)
                x = x / float(np.sum(x))
        else:
            x = np.ones(n, dtype=float) / n
        x = self._project_simplex_with_caps(x, ub)
        uniform = np.ones(n, dtype=float) / n

        for _ in range(self.iters):
            grad = (-mu) + (2.0 * self.risk_aversion * (sigma @ x)) + (2.0 * self.concentration_penalty * (x - uniform))
            x = x - (self.lr * grad)
            x = self._project_simplex_with_caps(x, ub)

        return {sid: float(x[i]) for i, sid in enumerate(strategy_ids)}


class MonteCarloPortfolioStabilitySimulator:
    def __init__(
        self,
        n_paths: int = 400,
        horizon_days: int = 20,
        drawdown_breach: float = 0.12,
        penalty_scale: float = 0.60,
        min_multiplier: float = 0.70,
    ):
        self.n_paths = max(64, int(n_paths))
        self.horizon_days = max(5, int(horizon_days))
        self.drawdown_breach = float(max(0.01, drawdown_breach))
        self.penalty_scale = float(np.clip(penalty_scale, 0.0, 1.0))
        self.min_multiplier = float(np.clip(min_multiplier, 0.10, 1.0))

    @staticmethod
    def _stable_seed(seed_key: str) -> int:
        digest = sha256(seed_key.encode("utf-8")).hexdigest()[:16]
        return int(digest, 16) % (2**31 - 1)

    def evaluate(
        self,
        *,
        strategy_ids: List[str],
        weights: Dict[str, float],
        expected_edges: Dict[str, float],
        covariance: Dict[str, Dict[str, float]],
        seed_key: str,
    ) -> Dict[str, float]:
        if len(strategy_ids) <= 1:
            return {
                "breach_probability": 0.0,
                "stability_multiplier": 1.0,
                "expected_drawdown": 0.0,
            }

        n = len(strategy_ids)
        w = np.asarray([float(weights.get(s, 0.0)) for s in strategy_ids], dtype=float)
        if float(np.sum(w)) <= 1e-12:
            w = np.ones(n, dtype=float) / n
        else:
            w = np.maximum(w, 0.0)
            w = w / float(np.sum(w))

        mu = np.asarray([float(expected_edges.get(s, 0.0)) for s in strategy_ids], dtype=float)
        mu = mu / max(1.0, float(self.horizon_days))
        sigma = np.zeros((n, n), dtype=float)
        for i, si in enumerate(strategy_ids):
            for j, sj in enumerate(strategy_ids):
                sigma[i, j] = float(covariance.get(si, {}).get(sj, 0.0))
        sigma = 0.5 * (sigma + sigma.T)
        sigma = sigma + (1e-6 * np.eye(n))

        rng = np.random.default_rng(self._stable_seed(seed_key))
        max_drawdowns: List[float] = []
        for _ in range(self.n_paths):
            try:
                rets = rng.multivariate_normal(mu, sigma, size=self.horizon_days)
            except Exception:
                return {
                    "breach_probability": 0.0,
                    "stability_multiplier": 1.0,
                    "expected_drawdown": 0.0,
                }
            pnl_path = np.dot(rets, w)
            equity = np.cumprod(1.0 + pnl_path)
            peaks = np.maximum.accumulate(equity)
            dd = 1.0 - (equity / np.maximum(peaks, 1e-9))
            max_drawdowns.append(float(np.max(dd)))

        dd_arr = np.asarray(max_drawdowns, dtype=float)
        breach_prob = float(np.mean(dd_arr > self.drawdown_breach))
        expected_dd = float(np.mean(dd_arr))
        multiplier = 1.0 - (self.penalty_scale * breach_prob)
        multiplier = float(np.clip(multiplier, self.min_multiplier, 1.0))
        return {
            "breach_probability": breach_prob,
            "stability_multiplier": multiplier,
            "expected_drawdown": expected_dd,
        }
