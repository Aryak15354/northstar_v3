"""Phase 10 architecture hyperparameter optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping

import numpy as np

from .architecture_policy_store import ArchitecturePolicyStore
from .scenario_planner import ScenarioPlanner
from .strategic_regime_engine import StrategicRegimeEngine, StrategicRegimeSnapshot


@dataclass(frozen=True)
class ArchitectureUpdateDecision:
    updated: bool
    theta: Dict[str, float]
    objective_value: float
    objective_prev: float
    gradient_norm: float
    hessian_min_eig: float
    cadence_ready: bool
    last_update_date: str
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updated": bool(self.updated),
            "theta": {str(k): float(v) for k, v in dict(self.theta or {}).items()},
            "objective_value": float(self.objective_value),
            "objective_prev": float(self.objective_prev),
            "gradient_norm": float(self.gradient_norm),
            "hessian_min_eig": float(self.hessian_min_eig),
            "cadence_ready": bool(self.cadence_ready),
            "last_update_date": str(self.last_update_date),
            "diagnostics": dict(self.diagnostics or {}),
        }


class ArchitectureOptimizer:
    """Slow-timescale optimizer over architectural hyperparameters."""

    PARAM_ORDER = (
        "convex_risk_aversion",
        "phase8_redundancy_penalty_eta",
        "phase8_diversity_reward_delta",
        "phase4_cluster_cap",
        "phase4_leverage_limit",
        "kelly_alpha",
        "phase5_allocation_inertia",
        "phase10_exploration_rate",
        "phase10_mortality_sensitivity",
    )

    REGIMES = ("growth", "stability", "innovation")
    REGIME_WEIGHTS = {
        "growth": {
            "log_growth": 1.00,
            "cvar": 0.28,
            "fragility": 0.18,
            "eigen": 0.15,
            "survival": 0.16,
            "regret": 0.14,
            "innovation": 0.10,
            "mortality": 0.05,
            "target": 0.06,
        },
        "stability": {
            "log_growth": 0.70,
            "cvar": 0.45,
            "fragility": 0.35,
            "eigen": 0.30,
            "survival": 0.24,
            "regret": 0.32,
            "innovation": 0.03,
            "mortality": 0.14,
            "target": 0.11,
        },
        "innovation": {
            "log_growth": 0.86,
            "cvar": 0.30,
            "fragility": 0.20,
            "eigen": 0.16,
            "survival": 0.12,
            "regret": 0.18,
            "innovation": 0.22,
            "mortality": 0.07,
            "target": 0.05,
        },
    }

    REGIME_THETA_TARGETS = {
        "growth": {
            "convex_risk_aversion": 1.80,
            "phase8_redundancy_penalty_eta": 0.12,
            "phase8_diversity_reward_delta": 0.16,
            "phase4_cluster_cap": 0.68,
            "phase4_leverage_limit": 1.20,
            "kelly_alpha": 0.45,
            "phase5_allocation_inertia": 0.30,
            "phase10_exploration_rate": 0.28,
            "phase10_mortality_sensitivity": 1.00,
        },
        "stability": {
            "convex_risk_aversion": 3.40,
            "phase8_redundancy_penalty_eta": 0.26,
            "phase8_diversity_reward_delta": 0.06,
            "phase4_cluster_cap": 0.45,
            "phase4_leverage_limit": 0.85,
            "kelly_alpha": 0.20,
            "phase5_allocation_inertia": 0.75,
            "phase10_exploration_rate": 0.12,
            "phase10_mortality_sensitivity": 1.70,
        },
        "innovation": {
            "convex_risk_aversion": 2.20,
            "phase8_redundancy_penalty_eta": 0.10,
            "phase8_diversity_reward_delta": 0.14,
            "phase4_cluster_cap": 0.60,
            "phase4_leverage_limit": 1.00,
            "kelly_alpha": 0.33,
            "phase5_allocation_inertia": 0.45,
            "phase10_exploration_rate": 0.35,
            "phase10_mortality_sensitivity": 1.10,
        },
    }

    THETA_TARGET_WEIGHTS = {
        "convex_risk_aversion": 0.35,
        "phase8_redundancy_penalty_eta": 1.00,
        "phase8_diversity_reward_delta": 1.00,
        "phase4_cluster_cap": 0.75,
        "phase4_leverage_limit": 0.85,
        "kelly_alpha": 0.90,
        "phase5_allocation_inertia": 0.70,
        "phase10_exploration_rate": 0.60,
        "phase10_mortality_sensitivity": 0.50,
    }

    def __init__(
        self,
        *,
        bounds: Mapping[str, tuple[float, float]] | None = None,
        policy_store: ArchitecturePolicyStore | None = None,
        scenario_planner: ScenarioPlanner | None = None,
        strategic_regime_engine: StrategicRegimeEngine | None = None,
        inertia: float = 0.85,
        max_step_fraction: float = 0.20,
        hessian_regularization: float = 1e-4,
        cadence_days: int = 30,
        min_history_points: int = 20,
    ):
        self.bounds = dict(bounds or {})
        self.policy_store = policy_store or ArchitecturePolicyStore()
        self.scenario_planner = scenario_planner or ScenarioPlanner()
        self.strategic_regime_engine = strategic_regime_engine or StrategicRegimeEngine()
        self.inertia = float(np.clip(inertia, 0.0, 0.99))
        self.max_step_fraction = float(np.clip(max_step_fraction, 0.01, 0.50))
        self.hessian_regularization = float(max(1e-8, hessian_regularization))
        self.cadence_days = int(max(1, cadence_days))
        self.min_history_points = int(max(1, min_history_points))

        self._theta, self._last_update_date = self._load_initial_policy()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            x = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(x):
            return float(default)
        return float(x)

    def _default_theta(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for name in self.PARAM_ORDER:
            lo, hi = self.bounds.get(name, (0.0, 1.0))
            out[name] = float(0.5 * (float(lo) + float(hi)))
        return out

    def _load_initial_policy(self) -> tuple[Dict[str, float], str]:
        payload = self.policy_store.load()
        theta_raw = dict(payload.get("theta", {}) or {})
        if not theta_raw:
            return self._default_theta(), str(payload.get("last_update_date", "") or "")
        out = self._default_theta()
        for k in self.PARAM_ORDER:
            if k in theta_raw:
                out[k] = self._safe_float(theta_raw.get(k), out[k])
        out = self._clip_theta(out)
        return out, str(payload.get("last_update_date", "") or "")

    def current_theta(self) -> Dict[str, float]:
        return dict(self._theta)

    def _clip_theta(self, theta: Mapping[str, float]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k in self.PARAM_ORDER:
            lo, hi = self.bounds.get(k, (0.0, 1.0))
            x = self._safe_float(dict(theta).get(k, 0.5 * (lo + hi)), 0.5 * (lo + hi))
            out[k] = float(np.clip(x, float(lo), float(hi)))
        return out

    def _as_vector(self, theta: Mapping[str, float]) -> np.ndarray:
        return np.asarray([self._safe_float(dict(theta).get(k, 0.0), 0.0) for k in self.PARAM_ORDER], dtype=float)

    def _from_vector(self, vec: Iterable[float]) -> Dict[str, float]:
        arr = np.asarray(list(vec), dtype=float)
        out = {name: float(arr[i]) for i, name in enumerate(self.PARAM_ORDER)}
        return self._clip_theta(out)

    def _step_sizes(self) -> np.ndarray:
        vals = []
        for k in self.PARAM_ORDER:
            lo, hi = self.bounds.get(k, (0.0, 1.0))
            vals.append(max(1e-5, 0.05 * float(hi - lo)))
        return np.asarray(vals, dtype=float)

    def _cadence_ready(self, now: datetime) -> bool:
        if not self._last_update_date:
            return True
        try:
            prev = datetime.fromisoformat(self._last_update_date.replace("Z", "+00:00"))
        except Exception:
            return True
        dt = (now - prev).total_seconds() / 86400.0
        return bool(dt >= float(self.cadence_days))

    def _uniform_regime_probs(self) -> Dict[str, float]:
        p = 1.0 / float(len(self.REGIMES))
        return {r: p for r in self.REGIMES}

    def _normalize_regime_probs(self, regime_probs: Mapping[str, float] | None) -> Dict[str, float]:
        if not regime_probs:
            return self._uniform_regime_probs()
        out = {r: max(0.0, self._safe_float(dict(regime_probs).get(r), 0.0)) for r in self.REGIMES}
        total = float(sum(out.values()))
        if total <= 1e-12:
            return self._uniform_regime_probs()
        return {r: float(v / total) for r, v in out.items()}

    def _objective_components(self, theta: Mapping[str, float], context: Mapping[str, float]) -> Dict[str, float]:
        t = dict(theta)
        c = dict(context)

        mu = self._safe_float(c.get("expected_return", 0.0), 0.0)
        vol = max(1e-8, self._safe_float(c.get("volatility", 0.0), 0.0))
        cvar = abs(self._safe_float(c.get("cvar_95", 0.0), 0.0))
        frag = max(0.0, self._safe_float(c.get("structural_fragility_index", 0.0), 0.0))
        eig = max(0.0, self._safe_float(c.get("eigen_spike", 1.0), 1.0) - 1.0)
        survival = float(np.clip(self._safe_float(c.get("survival_probability", 1.0), 1.0), 0.0, 1.0))
        system_regret = float(np.clip(self._safe_float(c.get("system_regret", 0.0), 0.0), 0.0, 1.0))
        research_gap = float(np.clip(self._safe_float(c.get("research_gap", 0.0), 0.0), 0.0, 1.0))
        capital_scale = float(np.clip(self._safe_float(c.get("capital_scale", 0.0), 0.0), 0.0, 1.5))

        lev = self._safe_float(t.get("phase4_leverage_limit", 1.0), 1.0)
        kelly = self._safe_float(t.get("kelly_alpha", 0.25), 0.25)
        kelly_adj = kelly / 0.25
        eta = self._safe_float(t.get("phase8_redundancy_penalty_eta", 0.1), 0.1)
        delta = self._safe_float(t.get("phase8_diversity_reward_delta", 0.08), 0.08)
        risk_aversion = self._safe_float(t.get("convex_risk_aversion", 2.0), 2.0)
        explore = self._safe_float(t.get("phase10_exploration_rate", 0.20), 0.20)
        mortality = self._safe_float(t.get("phase10_mortality_sensitivity", 1.0), 1.0)

        risk_half = max(1e-6, risk_aversion / 2.0)
        sqrt_term = float(np.sqrt(risk_half))
        vol_scale = 0.8 + (0.2 * sqrt_term)
        mu_eff = mu * lev * kelly_adj
        vol_eff = vol * lev * vol_scale
        growth_raw = mu_eff - (0.5 * (vol_eff**2))
        growth_floor = -0.95
        growth_eff = max(growth_floor, growth_raw)
        log_growth = float(np.log1p(growth_eff))
        dlog_dgrowth = 0.0 if growth_raw <= growth_floor else float(1.0 / max(1e-8, 1.0 + growth_eff))

        frag_barrier_inner = 1.0 + eta - delta
        frag_barrier = max(0.1, frag_barrier_inner)
        frag_barrier_grad = 1.0 if frag_barrier_inner > 0.1 else 0.0

        mortality_pressure = float(capital_scale * max(0.0, system_regret - 0.20))

        return {
            "mu": float(mu),
            "vol": float(vol),
            "cvar": float(cvar),
            "frag": float(frag),
            "eig": float(eig),
            "survival": float(survival),
            "system_regret": float(system_regret),
            "research_gap": float(research_gap),
            "capital_scale": float(capital_scale),
            "lev": float(lev),
            "kelly": float(kelly),
            "kelly_adj": float(kelly_adj),
            "eta": float(eta),
            "delta": float(delta),
            "risk_aversion": float(risk_aversion),
            "explore": float(explore),
            "mortality": float(mortality),
            "vol_scale": float(vol_scale),
            "mu_eff": float(mu_eff),
            "vol_eff": float(vol_eff),
            "log_growth": float(log_growth),
            "dlog_dgrowth": float(dlog_dgrowth),
            "frag_barrier": float(frag_barrier),
            "frag_barrier_grad": float(frag_barrier_grad),
            "sqrt_term": float(sqrt_term),
            "mortality_pressure": float(mortality_pressure),
        }

    def _regime_objective_and_gradient(
        self,
        theta: Mapping[str, float],
        context: Mapping[str, float],
        regime: str,
    ) -> tuple[float, np.ndarray]:
        comp = self._objective_components(theta, context)
        w = dict(self.REGIME_WEIGHTS.get(regime, self.REGIME_WEIGHTS["growth"]))
        targets = dict(self.REGIME_THETA_TARGETS.get(regime, self.REGIME_THETA_TARGETS["growth"]))
        target_w = dict(self.THETA_TARGET_WEIGHTS)

        risk_half = max(1e-6, comp["risk_aversion"] / 2.0)
        d_sqrt_drisk = 0.25 / np.sqrt(risk_half) if risk_half > 1e-6 else 0.0
        d_vol_scale_drisk = 0.2 * d_sqrt_drisk

        d_mueff_d_lev = comp["mu"] * comp["kelly_adj"]
        d_mueff_d_kelly = comp["mu"] * comp["lev"] * (1.0 / 0.25)
        d_voleff_d_lev = comp["vol"] * comp["vol_scale"]
        d_voleff_d_risk = comp["vol"] * comp["lev"] * d_vol_scale_drisk

        d_growth_d_lev = d_mueff_d_lev - (comp["vol_eff"] * d_voleff_d_lev)
        d_growth_d_kelly = d_mueff_d_kelly
        d_growth_d_risk = -(comp["vol_eff"] * d_voleff_d_risk)

        d_log_d_lev = comp["dlog_dgrowth"] * d_growth_d_lev
        d_log_d_kelly = comp["dlog_dgrowth"] * d_growth_d_kelly
        d_log_d_risk = comp["dlog_dgrowth"] * d_growth_d_risk

        target_penalty = 0.0
        target_grad = np.zeros(len(self.PARAM_ORDER), dtype=float)
        for i, name in enumerate(self.PARAM_ORDER):
            t_val = self._safe_float(dict(theta).get(name), 0.0)
            t_tar = self._safe_float(targets.get(name), t_val)
            wj = float(max(0.0, target_w.get(name, 0.0)))
            diff = t_val - t_tar
            target_penalty += wj * (diff**2)
            target_grad[i] = 2.0 * wj * diff

        objective = (
            (w["log_growth"] * comp["log_growth"])
            - (w["cvar"] * comp["cvar"] * comp["lev"])
            - (w["fragility"] * comp["frag"] * comp["frag_barrier"])
            - (w["eigen"] * comp["eig"] * comp["lev"])
            + (w["survival"] * comp["survival"])
            - (w["regret"] * comp["system_regret"])
            + (w["innovation"] * comp["explore"] * comp["research_gap"])
            - (w["mortality"] * comp["mortality"] * comp["mortality_pressure"])
            - (w["target"] * target_penalty)
        )

        grad = np.zeros(len(self.PARAM_ORDER), dtype=float)
        idx = {name: i for i, name in enumerate(self.PARAM_ORDER)}

        grad[idx["convex_risk_aversion"]] += w["log_growth"] * d_log_d_risk
        grad[idx["phase8_redundancy_penalty_eta"]] += -(w["fragility"] * comp["frag"] * comp["frag_barrier_grad"])
        grad[idx["phase8_diversity_reward_delta"]] += +(w["fragility"] * comp["frag"] * comp["frag_barrier_grad"])
        grad[idx["phase4_leverage_limit"]] += (w["log_growth"] * d_log_d_lev) - (w["cvar"] * comp["cvar"]) - (
            w["eigen"] * comp["eig"]
        )
        grad[idx["kelly_alpha"]] += w["log_growth"] * d_log_d_kelly
        grad[idx["phase10_exploration_rate"]] += w["innovation"] * comp["research_gap"]
        grad[idx["phase10_mortality_sensitivity"]] += -(w["mortality"] * comp["mortality_pressure"])

        grad -= (w["target"] * target_grad)
        return float(objective), grad

    def _blended_objective(
        self,
        theta: Mapping[str, float],
        context: Mapping[str, float],
        regime_probs: Mapping[str, float] | None = None,
    ) -> float:
        probs = self._normalize_regime_probs(regime_probs)
        obj = 0.0
        for r in self.REGIMES:
            o, _ = self._regime_objective_and_gradient(theta, context, r)
            obj += probs[r] * o
        return float(obj)

    def _blended_objective_gradient_closed_form(
        self,
        theta: Mapping[str, float],
        context: Mapping[str, float],
        regime_probs: Mapping[str, float] | None = None,
    ) -> np.ndarray:
        probs = self._normalize_regime_probs(regime_probs)
        grad = np.zeros(len(self.PARAM_ORDER), dtype=float)
        for r in self.REGIMES:
            _, g_r = self._regime_objective_and_gradient(theta, context, r)
            grad += probs[r] * g_r
        return grad

    def _objective(self, theta: Mapping[str, float], context: Mapping[str, float]) -> float:
        return self._blended_objective(theta, context, self._uniform_regime_probs())

    def _scenario_objective(
        self,
        theta: Mapping[str, float],
        context: Mapping[str, float],
        regime_probs: Mapping[str, float] | None = None,
    ) -> float:
        probs = self._normalize_regime_probs(regime_probs)
        scenario = self.scenario_planner.evaluate(
            objective_fn=lambda th, ctx: self._blended_objective(th, ctx, probs),
            theta=theta,
            context=context,
        )
        return float(scenario.expected_utility)

    def _estimate_gradient_fd(
        self,
        theta: Dict[str, float],
        context: Mapping[str, float],
        regime_probs: Mapping[str, float],
    ) -> np.ndarray:
        x = self._as_vector(theta)
        h = self._step_sizes()
        g = np.zeros_like(x)
        for i in range(len(x)):
            xp = x.copy()
            xm = x.copy()
            xp[i] += h[i]
            xm[i] -= h[i]
            fp = self._scenario_objective(self._from_vector(xp), context, regime_probs)
            fm = self._scenario_objective(self._from_vector(xm), context, regime_probs)
            g[i] = (fp - fm) / (2.0 * h[i])
        return g

    def _estimate_hessian(
        self,
        theta: Dict[str, float],
        context: Mapping[str, float],
        regime_probs: Mapping[str, float],
    ) -> np.ndarray:
        x = self._as_vector(theta)
        h = self._step_sizes()
        k = len(x)
        H = np.zeros((k, k), dtype=float)
        f0 = self._scenario_objective(theta, context, regime_probs)
        for i in range(k):
            xp = x.copy()
            xm = x.copy()
            xp[i] += h[i]
            xm[i] -= h[i]
            fp = self._scenario_objective(self._from_vector(xp), context, regime_probs)
            fm = self._scenario_objective(self._from_vector(xm), context, regime_probs)
            H[i, i] = (fp - (2.0 * f0) + fm) / max(1e-12, h[i] ** 2)

        for i in range(k):
            for j in range(i + 1, k):
                xpp = x.copy()
                xpp[i] += h[i]
                xpp[j] += h[j]
                xpm = x.copy()
                xpm[i] += h[i]
                xpm[j] -= h[j]
                xmp = x.copy()
                xmp[i] -= h[i]
                xmp[j] += h[j]
                xmm = x.copy()
                xmm[i] -= h[i]
                xmm[j] -= h[j]
                fpp = self._scenario_objective(self._from_vector(xpp), context, regime_probs)
                fpm = self._scenario_objective(self._from_vector(xpm), context, regime_probs)
                fmp = self._scenario_objective(self._from_vector(xmp), context, regime_probs)
                fmm = self._scenario_objective(self._from_vector(xmm), context, regime_probs)
                v = (fpp - fpm - fmp + fmm) / max(1e-12, 4.0 * h[i] * h[j])
                H[i, j] = v
                H[j, i] = v

        H = 0.5 * (H + H.T)
        eigvals, eigvecs = np.linalg.eigh(H)
        eigvals = np.maximum(eigvals, -self.hessian_regularization)
        H_reg = eigvecs @ np.diag(eigvals) @ eigvecs.T
        return H_reg

    def _solve_step(self, g: np.ndarray, H: np.ndarray) -> np.ndarray:
        # Max objective: quadratic local model => minimize 1/2 d^T(-H)d - g^T d.
        Q = -H
        Q = 0.5 * (Q + Q.T)
        eigvals, eigvecs = np.linalg.eigh(Q)
        eigvals = np.maximum(eigvals, self.hessian_regularization)
        Qpsd = eigvecs @ np.diag(eigvals) @ eigvecs.T
        try:
            d = np.linalg.solve(Qpsd, g)
        except np.linalg.LinAlgError:
            d = np.linalg.pinv(Qpsd) @ g
        return np.asarray(d, dtype=float)

    def _strategic_state_from_context(self, context: Mapping[str, float]) -> Dict[str, float]:
        c = dict(context or {})
        system_regret = float(np.clip(self._safe_float(c.get("system_regret", 0.0), 0.0), 0.0, 1.0))
        stability = float(
            np.clip(
                self._safe_float(c.get("system_stability_index", 1.0 - system_regret), 1.0 - system_regret),
                0.0,
                1.0,
            )
        )
        frag = float(np.clip(self._safe_float(c.get("structural_fragility_index", 0.0), 0.0), 0.0, 1.0))
        eig = float(max(1.0, self._safe_float(c.get("eigen_spike", 1.0), 1.0)))
        research_gap = float(np.clip(self._safe_float(c.get("research_gap", 0.0), 0.0), 0.0, 1.0))
        cap_scale = float(np.clip(self._safe_float(c.get("capital_scale", 0.0), 0.0), 0.0, 1.5))
        return {
            "system_regret": system_regret,
            "stability_index": stability,
            "structural_fragility": frag,
            "eigen_spike": eig,
            "research_gap": research_gap,
            "capital_scale": cap_scale,
        }

    def run_cycle(
        self,
        *,
        context: Mapping[str, float],
        now_utc: str | None = None,
        history_points: int = 0,
    ) -> ArchitectureUpdateDecision:
        now = self._now() if not now_utc else datetime.fromisoformat(str(now_utc).replace("Z", "+00:00"))
        cadence_ready = self._cadence_ready(now)
        theta_prev = dict(self._theta)

        regime_snapshot: StrategicRegimeSnapshot = self.strategic_regime_engine.infer(
            state=self._strategic_state_from_context(context),
            update_state=True,
        )
        regime_probs = self._normalize_regime_probs(regime_snapshot.probabilities)
        obj_prev = self._scenario_objective(theta_prev, context, regime_probs)

        if (not cadence_ready) or (int(history_points) < self.min_history_points):
            return ArchitectureUpdateDecision(
                updated=False,
                theta=theta_prev,
                objective_value=float(obj_prev),
                objective_prev=float(obj_prev),
                gradient_norm=0.0,
                hessian_min_eig=0.0,
                cadence_ready=bool(cadence_ready),
                last_update_date=str(self._last_update_date),
                diagnostics={
                    "history_points": int(history_points),
                    "min_history_points": int(self.min_history_points),
                    "strategic_regime": regime_snapshot.to_dict(),
                    "regime_probs": dict(regime_probs),
                },
            )

        g_closed = self._blended_objective_gradient_closed_form(theta_prev, context, regime_probs)
        g_fd = self._estimate_gradient_fd(theta_prev, context, regime_probs)

        n_closed = float(np.linalg.norm(g_closed))
        n_fd = float(np.linalg.norm(g_fd))
        if n_closed > 1e-10 and n_fd > 1e-10:
            alignment = float(np.clip(np.dot(g_closed, g_fd) / (n_closed * n_fd), -1.0, 1.0))
        else:
            alignment = 0.0
        blend = 0.75 if n_closed > 1e-10 else 0.0
        g = (blend * g_closed) + ((1.0 - blend) * g_fd)

        H = self._estimate_hessian(theta_prev, context, regime_probs)
        d = self._solve_step(g, H)

        eigvals = np.linalg.eigvalsh(0.5 * (H + H.T))
        hmin = float(np.min(eigvals)) if eigvals.size > 0 else 0.0
        lipschitz_L = float(np.max(np.abs(eigvals))) if eigvals.size > 0 else 0.0
        eta_bound = float(2.0 / max(lipschitz_L, 1e-8))
        eta_applied = float(np.clip(min(1.0, 0.90 * eta_bound), 0.05, 1.0))
        d = eta_applied * d

        predicted_gain = float(np.dot(g, d) + (0.5 * np.dot(d, H @ d)))
        if (not np.isfinite(predicted_gain)) or (predicted_gain < 0.0):
            step_scale = float(np.mean(self._step_sizes()))
            g_norm = float(np.linalg.norm(g))
            if g_norm > 1e-10:
                d = eta_applied * step_scale * (g / g_norm)
                predicted_gain = float(np.dot(g, d) + (0.5 * np.dot(d, H @ d)))
            else:
                d = np.zeros_like(d)
                predicted_gain = 0.0

        # Enforce per-parameter step caps.
        x_prev = self._as_vector(theta_prev)
        x_prop = x_prev + d
        for i, name in enumerate(self.PARAM_ORDER):
            lo, hi = self.bounds.get(name, (0.0, 1.0))
            max_step = self.max_step_fraction * float(hi - lo)
            x_prop[i] = np.clip(x_prop[i], x_prev[i] - max_step, x_prev[i] + max_step)

        theta_prop = self._from_vector(x_prop)
        theta_new = {
            k: float((self.inertia * theta_prev[k]) + ((1.0 - self.inertia) * theta_prop[k]))
            for k in self.PARAM_ORDER
        }
        theta_new = self._clip_theta(theta_new)

        obj_new = self._scenario_objective(theta_new, context, regime_probs)
        accept = bool(np.isfinite(obj_new) and (obj_new >= (obj_prev - 1e-4)))
        theta_final = theta_new if accept else theta_prev
        obj_final = obj_new if accept else obj_prev

        diagnostics = {
            "accepted": bool(accept),
            "objective_new": float(obj_new),
            "history_points": int(history_points),
            "gradient_closed_norm": float(n_closed),
            "gradient_fd_norm": float(n_fd),
            "gradient_alignment": float(alignment),
            "predicted_gain": float(predicted_gain),
            "lipschitz_constant": float(lipschitz_L),
            "eta_bound": float(eta_bound),
            "eta_applied": float(eta_applied),
            "regime_probs": dict(regime_probs),
            "strategic_regime": regime_snapshot.to_dict(),
            "convergence_condition": bool(eta_applied <= eta_bound + 1e-8),
        }

        if accept:
            payload = {
                "last_update_date": now.astimezone(timezone.utc).isoformat(),
                "theta": dict(theta_final),
                "diagnostics": {
                    "objective_prev": float(obj_prev),
                    "objective_new": float(obj_new),
                    "accepted": True,
                    "gradient_norm": float(np.linalg.norm(g)),
                    "hessian_min_eig": float(hmin),
                    "gradient_closed_norm": float(n_closed),
                    "gradient_fd_norm": float(n_fd),
                    "gradient_alignment": float(alignment),
                    "predicted_gain": float(predicted_gain),
                    "lipschitz_constant": float(lipschitz_L),
                    "eta_bound": float(eta_bound),
                    "eta_applied": float(eta_applied),
                    "regime_probs": dict(regime_probs),
                    "strategic_regime": regime_snapshot.to_dict(),
                },
            }
            saved = self.policy_store.save(payload)
            self._theta = dict(saved.get("theta", theta_final) or theta_final)
            self._last_update_date = str(saved.get("last_update_date", payload["last_update_date"]))
        else:
            self._theta = dict(theta_final)

        return ArchitectureUpdateDecision(
            updated=bool(accept),
            theta=dict(theta_final),
            objective_value=float(obj_final),
            objective_prev=float(obj_prev),
            gradient_norm=float(np.linalg.norm(g)),
            hessian_min_eig=float(hmin),
            cadence_ready=True,
            last_update_date=str(self._last_update_date),
            diagnostics=diagnostics,
        )
