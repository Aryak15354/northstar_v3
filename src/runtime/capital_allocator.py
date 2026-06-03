"""Capital allocator policy layer for proposal sizing authority separation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import numpy as np

from src.diagnostics import (
    MonteCarloStabilitySimulator,
    Phase3DeploymentQualifier,
    StructuralQualificationEngine,
)
from src.manifold import AlphaManifoldBuilder
from src.portfolio import ConvexPortfolioAllocator, PortfolioMonteCarloSimulator
from src.strategic import (
    ArchitectureOptimizer,
    ExplorationGovernor,
    ObjectiveReweighter,
    ReflexivityModel,
    SystemRegretAggregator,
)
from src.strategic.architecture_policy_store import ArchitecturePolicyStore

from .capital_intelligence import (
    BayesianShrinkageModel,
    DiagnosticsContextLoader,
    KellyRegularizedSizer,
)
from .adaptive_capital_engine import AdaptiveCapitalEngine
from .contracts import CapitalDecision, ProposalOrigin, TradeProposal
from .regime_state_engine import BayesianRegimeStateEngine


@dataclass(frozen=True)
class CapitalAllocatorConfig:
    equity_alpha_reserve_pct: float = 0.45
    options_alpha_reserve_pct: float = 0.25
    hedge_reserve_pct: float = 0.20
    discretionary_reserve_pct: float = 0.10
    min_trade_notional: float = 1.0
    diagnostics_db_path: str = "data/diagnostics/alpha_diagnostics.db"
    diagnostics_refresh_seconds: int = 60
    enable_advanced_models: bool = True
    apply_advisory_feedback: bool = False
    bayesian_prior_strength: float = 20.0
    kelly_alpha: float = 0.25
    kelly_min_fraction: float = 0.05
    kelly_max_fraction: float = 1.0
    min_size_factor: float = 0.25
    max_size_factor: float = 1.25
    convex_risk_aversion: float = 2.0
    convex_concentration_penalty: float = 0.05
    regime_confidence_threshold: float = 0.80
    regime_persistence_days: int = 5
    max_weekly_capital_shift_pct: float = 0.05
    drawdown_lock_threshold: float = 0.12
    regime_engine_states: int = 3
    phase3_enabled: bool = True
    phase3_enforce: bool = True
    phase3_min_history: int = 20
    phase3_n_sim: int = 800
    phase3_cost_ratio_min: float = 0.60
    phase3_capacity_ratio_min: float = 0.70
    phase3_marginal_sharpe_min_delta: float = 0.10
    phase3_decay_min_slope: float = -0.05
    phase3_max_stress_drawdown: float = 0.35
    phase3_mc_max_p_sharpe_negative: float = 0.30
    phase3_mc_max_p_dd_gt_40: float = 0.25
    phase3_mc_min_sharpe_p05: float = 0.30
    phase3_cost_impact_a: float = 0.0004
    phase3_cost_impact_b: float = 0.0001
    phase4_enabled: bool = True
    phase4_leverage_limit: float = 1.0
    phase4_cluster_cap: float = 0.55
    phase4_corr_threshold: float = 0.85
    phase4_correlation_spike: float = 0.35
    phase4_drawdown_breach: float = 0.15
    phase4_max_p_dd_breach: float = 0.30
    phase4_mc_paths: int = 600
    phase4_mc_horizon_days: int = 30
    phase4_max_turnover: float = 0.30
    phase4_eigen_risk_threshold: float = 0.75
    phase4_eigen_penalty_scale: float = 0.50
    phase5_enabled: bool = True
    phase5_regime_conditioned: bool = True
    phase5_allocation_inertia: float = 0.35
    phase5_entropy_freeze_threshold: float = 0.90
    phase5_kelly_estimation_penalty: float = 8.0
    phase5_factor_limit: float = 0.30
    phase8_enabled: bool = False
    phase8_redundancy_penalty_eta: float = 0.10
    phase8_diversity_reward_delta: float = 0.08
    phase8_cluster_cap: float = 0.55
    phase8_overcrowding_cluster_threshold: float = 0.65
    phase9_enabled: bool = False
    phase9_horizons: tuple[str, ...] = ("1d", "5d", "20d", "60d", "120d")
    phase9_cross_horizon_corr: float = 0.35
    phase9_short_horizon_risk_sensitivity: float = 0.35
    phase10_enabled: bool = False
    phase10_policy_path: str = "data/strategic/architecture_policy.json"
    phase10_cadence_days: int = 30
    phase10_inertia: float = 0.85
    phase10_max_step_fraction: float = 0.20
    phase10_hessian_regularization: float = 1e-4
    phase10_min_history_points: int = 20
    phase10_base_exploration: float = 0.20
    phase10_mortality_sensitivity: float = 1.0
    phase6_enabled: bool = True
    phase6_target_volatility: float = 0.12
    phase6_min_multiplier: float = 0.35
    phase6_max_multiplier: float = 1.25


class CapitalAllocatorPolicy:
    """Applies reserve-aware notional approvals before risk budget checks."""

    def __init__(self, config: CapitalAllocatorConfig | None = None):
        self.config = config or CapitalAllocatorConfig()
        self._diag_loader = DiagnosticsContextLoader(
            diagnostics_db_path=self.config.diagnostics_db_path,
            refresh_seconds=self.config.diagnostics_refresh_seconds,
        )
        self._bayes = BayesianShrinkageModel()
        self._kelly = KellyRegularizedSizer()
        self._regime_engine = BayesianRegimeStateEngine(
            n_states=self.config.regime_engine_states,
            confidence_threshold=self.config.regime_confidence_threshold,
            min_persistence_days=self.config.regime_persistence_days,
        )
        self._phase4_allocator = ConvexPortfolioAllocator(
            risk_aversion=self.config.convex_risk_aversion,
            return_weight=1.0,
            concentration_penalty=self.config.convex_concentration_penalty,
            crisis_corr_spike=self.config.phase4_correlation_spike,
        )
        self._phase4_mc = PortfolioMonteCarloSimulator(
            n_paths=self.config.phase4_mc_paths,
            horizon_days=self.config.phase4_mc_horizon_days,
            crisis_corr_spike=self.config.phase4_correlation_spike,
        )
        self._adaptive_capital = AdaptiveCapitalEngine(
            target_volatility=self.config.phase6_target_volatility,
            min_multiplier=self.config.phase6_min_multiplier,
            max_multiplier=self.config.phase6_max_multiplier,
        )
        self._phase8_builder = AlphaManifoldBuilder()
        self._phase10_regret = SystemRegretAggregator()
        self._phase10_reweighter = ObjectiveReweighter()
        self._phase10_exploration = ExplorationGovernor(
            base_exploration=float(self.config.phase10_base_exploration),
        )
        self._phase10_reflexivity = ReflexivityModel()
        phase10_bounds = {
            "convex_risk_aversion": (0.80, 5.00),
            "phase8_redundancy_penalty_eta": (0.00, 0.45),
            "phase8_diversity_reward_delta": (0.00, 0.25),
            "phase4_cluster_cap": (0.35, 0.80),
            "phase4_leverage_limit": (0.70, 1.40),
            "kelly_alpha": (0.05, 0.70),
            "phase5_allocation_inertia": (0.05, 0.95),
            "phase10_exploration_rate": (0.03, 0.45),
            "phase10_mortality_sensitivity": (0.25, 3.00),
        }
        self._phase10_store = ArchitecturePolicyStore(
            policy_path=str(self.config.phase10_policy_path),
        )
        self._phase10_optimizer = ArchitectureOptimizer(
            bounds=phase10_bounds,
            policy_store=self._phase10_store,
            inertia=float(self.config.phase10_inertia),
            max_step_fraction=float(self.config.phase10_max_step_fraction),
            hessian_regularization=float(self.config.phase10_hessian_regularization),
            cadence_days=int(self.config.phase10_cadence_days),
            min_history_points=int(self.config.phase10_min_history_points),
        )
        self._phase3 = Phase3DeploymentQualifier(
            deterministic_engine=StructuralQualificationEngine(
                min_cost_ratio=float(self.config.phase3_cost_ratio_min),
                min_capacity_ratio=float(self.config.phase3_capacity_ratio_min),
                min_marginal_sharpe_delta=float(self.config.phase3_marginal_sharpe_min_delta),
                min_decay_slope=float(self.config.phase3_decay_min_slope),
                max_stress_drawdown=float(self.config.phase3_max_stress_drawdown),
                cost_impact_a=float(self.config.phase3_cost_impact_a),
                cost_impact_b=float(self.config.phase3_cost_impact_b),
            ),
            monte_carlo_engine=MonteCarloStabilitySimulator(
                n_sim=int(self.config.phase3_n_sim),
                max_p_sharpe_negative=float(self.config.phase3_mc_max_p_sharpe_negative),
                max_p_dd_gt_40=float(self.config.phase3_mc_max_p_dd_gt_40),
                min_sharpe_p05=float(self.config.phase3_mc_min_sharpe_p05),
            ),
        )
        self._last_size_factor: Dict[str, float] = {}
        self._weekly_anchor: Dict[str, Dict[str, Any]] = {}
        self._last_phase4_weights_by_universe: Dict[str, Dict[str, float]] = {}
        self._last_phase6_multiplier_by_strategy: Dict[str, float] = {}

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
    def _clamp(x: float, lo: float, hi: float) -> float:
        return float(max(lo, min(hi, x)))

    def _apply_weekly_shift_cap(self, strategy_id: str, raw_factor: float) -> Dict[str, float]:
        sid = str(strategy_id or "")
        now = datetime.now(timezone.utc)
        week_key = now.strftime("%G-%V")
        prev_factor = float(self._last_size_factor.get(sid, 1.0))
        anchor = self._weekly_anchor.get(sid)
        if (anchor is None) or (str(anchor.get("week", "")) != week_key):
            self._weekly_anchor[sid] = {"week": week_key, "anchor_factor": prev_factor}
            anchor_factor = prev_factor
        else:
            anchor_factor = float(anchor.get("anchor_factor", prev_factor))

        max_shift = float(max(0.0, self.config.max_weekly_capital_shift_pct))
        lo = float(max(0.0, anchor_factor * (1.0 - max_shift)))
        hi = float(anchor_factor * (1.0 + max_shift))
        clipped = self._clamp(float(raw_factor), lo, hi)
        self._last_size_factor[sid] = clipped
        return {
            "factor": clipped,
            "weekly_anchor_factor": float(anchor_factor),
            "weekly_cap_low": lo,
            "weekly_cap_high": hi,
        }

    def _strategy_caps(
        self,
        *,
        strategy_ids: list[str],
        advisory: Dict[str, Any],
    ) -> Dict[str, float]:
        if not strategy_ids:
            return {}
        default_cap = max(1.0 / max(1, len(strategy_ids)), 0.35)
        caps = {sid: default_cap for sid in strategy_ids}
        if not self.config.apply_advisory_feedback:
            return caps
        cap_adj = dict(advisory.get("strategy_cap_adjustment", {}) or {})
        for sid in strategy_ids:
            delta = self._safe_float(cap_adj.get(sid, 0.0), 0.0)
            caps[sid] = self._clamp(default_cap + delta, 1.0 / len(strategy_ids), 1.0)
        return caps

    @staticmethod
    def _strategy_clusters(
        *,
        strategy_ids: list[str],
        advisory: Dict[str, Any],
    ) -> Dict[str, str]:
        cluster_map = dict(advisory.get("strategy_cluster_map", advisory.get("alpha_cluster_map", {})) or {})
        out: Dict[str, str] = {}
        for sid in strategy_ids:
            out[sid] = str(cluster_map.get(sid, sid))
        return out

    @staticmethod
    def _universe_key(strategy_ids: list[str]) -> str:
        if not strategy_ids:
            return "empty"
        return "|".join(sorted(str(x) for x in strategy_ids))

    @staticmethod
    def _normalize_weights(
        weights: Dict[str, float],
        caps: Dict[str, float],
        leverage_limit: float,
    ) -> Dict[str, float]:
        out = {str(k): float(max(0.0, v)) for k, v in dict(weights or {}).items()}
        if not out:
            return {}
        for sid in list(out.keys()):
            cap = float(max(0.0, caps.get(sid, 1.0)))
            out[sid] = float(min(out[sid], cap))
        lev = float(sum(abs(v) for v in out.values()))
        if lev > max(1e-12, float(leverage_limit)):
            scale = float(float(leverage_limit) / lev)
            for sid in list(out.keys()):
                out[sid] *= scale
        return out

    @staticmethod
    def _blend_weight_maps(
        weighted_maps: list[tuple[float, Dict[str, float]]],
    ) -> Dict[str, float]:
        out: Dict[str, float] = {}
        total = 0.0
        for prob, wmap in weighted_maps:
            p = float(max(0.0, prob))
            if p <= 0.0:
                continue
            total += p
            for sid, w in dict(wmap or {}).items():
                out[str(sid)] = out.get(str(sid), 0.0) + (p * float(w))
        if total <= 1e-12:
            return out
        inv = 1.0 / total
        for sid in list(out.keys()):
            out[sid] *= inv
        return out

    @staticmethod
    def _regime_risk_level(regime_name: str) -> float:
        key = str(regime_name or "").lower()
        if ("high" in key and "vol" in key) or ("crisis" in key) or ("stress" in key):
            return 1.0
        if ("mid" in key) or ("neutral" in key):
            return 0.5
        if ("low" in key and "vol" in key) or ("calm" in key) or ("bull" in key):
            return 0.2
        if key.startswith("state_"):
            try:
                idx = int(key.split("_")[-1])
                return float(np.clip(0.2 + (0.4 * idx), 0.0, 1.0))
            except Exception:
                return 0.5
        return 0.5

    @staticmethod
    def _extract_regime_probabilities(
        *,
        regime_state: Any,
        portfolio_snapshot: Dict[str, Any],
        risk_snapshot: Dict[str, Any] | None,
    ) -> Dict[str, float]:
        rs = dict(risk_snapshot or {})
        direct = dict(rs.get("regime_probabilities", {}) or {})
        if direct:
            total = float(sum(max(0.0, float(v)) for v in direct.values()))
            if total > 1e-12:
                return {str(k): float(max(0.0, float(v)) / total) for k, v in direct.items()}

        from_state = dict(getattr(regime_state, "state_probabilities", {}) or {})
        if from_state:
            total = float(sum(max(0.0, float(v)) for v in from_state.values()))
            if total > 1e-12:
                return {str(k): float(max(0.0, float(v)) / total) for k, v in from_state.items()}

        ctx = dict(portfolio_snapshot.get("regime_context", {}) or {})
        from_ctx = dict(ctx.get("state_probabilities", {}) or {})
        if from_ctx:
            total = float(sum(max(0.0, float(v)) for v in from_ctx.values()))
            if total > 1e-12:
                return {str(k): float(max(0.0, float(v)) / total) for k, v in from_ctx.items()}

        return {"state_1": 1.0}

    @staticmethod
    def _adjust_expected_edges_for_regime(
        expected_edges: Dict[str, float],
        risk_level: float,
    ) -> Dict[str, float]:
        # As risk rises, shrink optimistic expected edges and preserve sign.
        shrink = float(np.clip(1.0 - (0.35 * risk_level), 0.50, 1.0))
        out: Dict[str, float] = {}
        for sid, edge in dict(expected_edges or {}).items():
            out[str(sid)] = float(edge) * shrink
        return out

    @staticmethod
    def _adjust_covariance_for_regime(
        covariance: Dict[str, Dict[str, float]],
        risk_level: float,
    ) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        corr_boost = float(1.0 + (0.75 * max(0.0, risk_level)))
        var_boost = float(1.0 + (0.60 * max(0.0, risk_level)))
        keys = set(covariance.keys())
        for row in covariance.values():
            keys.update(row.keys())
        ids = sorted(str(x) for x in keys)
        for i in ids:
            out[i] = {}
            for j in ids:
                v = float(dict(covariance.get(i, {}) or {}).get(j, 0.0))
                if i == j:
                    out[i][j] = float(v * var_boost)
                else:
                    out[i][j] = float(v * corr_boost)
        return out

    @staticmethod
    def _parse_horizon_days(h: str) -> int:
        key = str(h or "").strip().lower()
        if not key:
            return 20
        digits = "".join(ch for ch in key if ch.isdigit())
        if not digits:
            return 20
        value = int(digits)
        if key.endswith("w"):
            return int(max(1, value * 5))
        if key.endswith("m"):
            return int(max(1, value * 21))
        return int(max(1, value))

    def _phase9_horizon_mix(self, horizons: list[str], risk_level: float) -> Dict[str, float]:
        if not horizons:
            return {}
        risk = float(np.clip(risk_level, 0.0, 1.0))
        short_sens = float(max(0.0, self.config.phase9_short_horizon_risk_sensitivity))
        raw: Dict[str, float] = {}
        for h in horizons:
            days = float(self._parse_horizon_days(h))
            shortness = float(np.clip(20.0 / max(20.0, days), 0.0, 1.0))
            damp = float(np.clip(1.0 - (short_sens * risk * shortness), 0.20, 1.0))
            raw[str(h)] = damp
        total = float(sum(raw.values()))
        if total <= 1e-12:
            return {str(h): 1.0 / max(1, len(horizons)) for h in horizons}
        return {str(k): float(v / total) for k, v in raw.items()}

    def _phase9_horizon_edges(
        self,
        *,
        strategy_ids: list[str],
        expected_edges: Dict[str, float],
        horizons: list[str],
        risk_level: float,
        strategy_points: Dict[str, Any],
    ) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        for h in horizons:
            days = float(self._parse_horizon_days(h))
            # Longer horizons get smoother edge retention under stress.
            longness = float(np.clip(np.log1p(days) / np.log1p(120.0), 0.0, 1.0))
            risk_shrink = float(np.clip(1.0 - (0.25 * risk_level * (1.0 - longness)), 0.55, 1.0))
            h_map: Dict[str, float] = {}
            for sid in strategy_ids:
                edge = float(expected_edges.get(sid, 0.0))
                pt = strategy_points.get(sid)
                decay = abs(self._safe_float(getattr(pt, "edge_decay", 0.0), 0.0)) if pt is not None else 0.0
                decay_term = float(np.clip(np.exp(-decay * np.sqrt(max(1.0, days / 20.0))), 0.30, 1.0))
                h_map[str(sid)] = float(edge * risk_shrink * decay_term)
            out[str(h)] = h_map
        return out

    def _phase10_theta(self) -> Dict[str, float]:
        if not bool(self.config.phase10_enabled):
            return {
                "convex_risk_aversion": float(self.config.convex_risk_aversion),
                "phase8_redundancy_penalty_eta": float(self.config.phase8_redundancy_penalty_eta),
                "phase8_diversity_reward_delta": float(self.config.phase8_diversity_reward_delta),
                "phase4_cluster_cap": float(self.config.phase4_cluster_cap),
                "phase4_leverage_limit": float(self.config.phase4_leverage_limit),
                "kelly_alpha": float(self.config.kelly_alpha),
                "phase5_allocation_inertia": float(self.config.phase5_allocation_inertia),
                "phase10_exploration_rate": float(self.config.phase10_base_exploration),
                "phase10_mortality_sensitivity": float(self.config.phase10_mortality_sensitivity),
            }
        theta = dict(self._phase10_optimizer.current_theta() or {})
        if not theta:
            return {
                "convex_risk_aversion": float(self.config.convex_risk_aversion),
                "phase8_redundancy_penalty_eta": float(self.config.phase8_redundancy_penalty_eta),
                "phase8_diversity_reward_delta": float(self.config.phase8_diversity_reward_delta),
                "phase4_cluster_cap": float(self.config.phase4_cluster_cap),
                "phase4_leverage_limit": float(self.config.phase4_leverage_limit),
                "kelly_alpha": float(self.config.kelly_alpha),
                "phase5_allocation_inertia": float(self.config.phase5_allocation_inertia),
                "phase10_exploration_rate": float(self.config.phase10_base_exploration),
                "phase10_mortality_sensitivity": float(self.config.phase10_mortality_sensitivity),
            }
        return theta

    def _advanced_size_factor(
        self,
        proposal: TradeProposal,
        *,
        portfolio_snapshot: Dict[str, Any],
        budget_snapshot: Dict[str, Any] | None,
        risk_snapshot: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not self.config.enable_advanced_models:
            return {
                "size_factor": 1.0,
                "enabled": False,
                "reason": "advanced_models_disabled",
                "phase3_status": "disabled",
            }

        ctx = self._diag_loader.load()
        strategy_points = dict(ctx.strategy_points or {})
        if not strategy_points:
            return {
                "size_factor": 1.0,
                "enabled": True,
                "mode": "fallback_no_diagnostics",
                "phase3_status": "provisional_pass",
            }
        strategy_point = strategy_points.get(proposal.strategy_id)
        strategy_returns = list(dict(ctx.strategy_return_series or {}).get(proposal.strategy_id, []) or [])
        if strategy_returns:
            max_hist = 512
            strategy_returns = [float(x) for x in strategy_returns[-max_hist:]]

        portfolio_proxy_returns: list[float] = []
        for sid, series in dict(ctx.strategy_return_series or {}).items():
            if sid == proposal.strategy_id:
                continue
            vals = [float(x) for x in list(series or [])]
            if vals:
                portfolio_proxy_returns.append(vals[-min(len(vals), 128):])
        if portfolio_proxy_returns:
            m = min(len(s) for s in portfolio_proxy_returns)
            if m > 0:
                arr = np.asarray([s[-m:] for s in portfolio_proxy_returns], dtype=float)
                portfolio_returns = np.mean(arr, axis=0).tolist()
            else:
                portfolio_returns = []
        else:
            portfolio_returns = []

        theta = self._phase10_theta()
        effective_risk_aversion = float(self._safe_float(theta.get("convex_risk_aversion", self.config.convex_risk_aversion), self.config.convex_risk_aversion))
        effective_eta = float(self._safe_float(theta.get("phase8_redundancy_penalty_eta", self.config.phase8_redundancy_penalty_eta), self.config.phase8_redundancy_penalty_eta))
        effective_delta = float(self._safe_float(theta.get("phase8_diversity_reward_delta", self.config.phase8_diversity_reward_delta), self.config.phase8_diversity_reward_delta))
        effective_cluster_cap_cfg = float(self._safe_float(theta.get("phase4_cluster_cap", self.config.phase4_cluster_cap), self.config.phase4_cluster_cap))
        effective_leverage_limit = float(self._safe_float(theta.get("phase4_leverage_limit", self.config.phase4_leverage_limit), self.config.phase4_leverage_limit))
        effective_kelly_alpha = float(self._safe_float(theta.get("kelly_alpha", self.config.kelly_alpha), self.config.kelly_alpha))
        effective_inertia = float(self._safe_float(theta.get("phase5_allocation_inertia", self.config.phase5_allocation_inertia), self.config.phase5_allocation_inertia))
        effective_mortality_sensitivity = float(self._safe_float(theta.get("phase10_mortality_sensitivity", self.config.phase10_mortality_sensitivity), self.config.phase10_mortality_sensitivity))

        bayes = self._bayes.posterior_edge(
            expected_edge=float(proposal.expected_edge),
            strategy_stat=strategy_point,
            prior_strength=float(self.config.bayesian_prior_strength),
        )

        confidence = 1.0
        if strategy_point is not None:
            stability = self._clamp(strategy_point.stability_score, 0.0, 1.0)
            regime_penalty = self._clamp(strategy_point.regime_sensitivity, 0.0, 2.0)
            decay_penalty = self._clamp(abs(strategy_point.edge_decay), 0.0, 1.0)
            confidence = self._clamp((0.60 + (0.50 * stability)) - (0.20 * regime_penalty) - (0.20 * decay_penalty), 0.25, 1.25)

        variance = 0.04
        if strategy_point is not None:
            variance = max(0.01, (abs(strategy_point.avg_sdr) + 0.10) ** 2)
        sample_n = float(max(0, int(getattr(strategy_point, "trade_count", 0) if strategy_point is not None else 0)))
        kelly_estimation_error = 0.0
        variance_for_kelly = float(variance)
        if bool(self.config.phase5_enabled):
            kelly_estimation_error = float(self.config.phase5_kelly_estimation_penalty) / max(np.sqrt(max(sample_n, 1.0)), 1.0)
            variance_for_kelly = float(max(1e-8, variance + (kelly_estimation_error ** 2)))

        kelly = self._kelly.size_fraction(
            posterior_edge=float(bayes["posterior_edge"]),
            variance=float(variance_for_kelly),
            alpha=float(effective_kelly_alpha),
            min_fraction=float(self.config.kelly_min_fraction),
            max_fraction=float(self.config.kelly_max_fraction),
            confidence_scale=float(confidence),
        )
        kelly_multiplier = self._clamp(float(kelly["kelly_fraction_regularized"]), 0.05, 1.5)

        regime_obs = self._regime_engine.build_observation(
            proposal=proposal,
            portfolio_snapshot=portfolio_snapshot,
            risk_snapshot=risk_snapshot,
            market_snapshot=None,
        )
        regime = self._regime_engine.update(regime_obs)
        regime_probs = self._extract_regime_probabilities(
            regime_state=regime,
            portfolio_snapshot=portfolio_snapshot,
            risk_snapshot=risk_snapshot,
        )
        regime_gate = bool(
            (regime.confidence >= float(self.config.regime_confidence_threshold))
            and (regime.persistence_days >= int(self.config.regime_persistence_days))
            and (regime.transition_confirmed or regime.structural_break)
        )
        drawdown_ratio = self._safe_float(
            dict(risk_snapshot or {}).get("drawdown_ratio", portfolio_snapshot.get("drawdown_ratio", 0.0)),
            0.0,
        )
        drawdown_lock = bool(drawdown_ratio >= float(self.config.drawdown_lock_threshold))
        if drawdown_lock:
            regime_multiplier = 1.0
            regime_gate = False
        else:
            regime_multiplier = self._clamp(float(regime.risk_multiplier), 0.70, 1.0) if regime_gate else 1.0

        strategy_ids = sorted(set(strategy_points.keys()) | {proposal.strategy_id})
        expected_edges = {sid: 0.0 for sid in strategy_ids}
        for sid in strategy_ids:
            sp = strategy_points.get(sid)
            if sp is None:
                expected_edges[sid] = float(proposal.expected_edge if sid == proposal.strategy_id else 0.01)
            else:
                expected_edges[sid] = float(sp.avg_err * max(0.0, sp.avg_cer))
        expected_edges[proposal.strategy_id] = float(bayes["posterior_edge"])

        advisory_payload = dict(ctx.policy_recommendations or {})
        current_weights = dict((budget_snapshot or {}).get("strategy_usage", {}) or {})
        caps = self._strategy_caps(
            strategy_ids=strategy_ids,
            advisory=advisory_payload,
        )
        clusters = self._strategy_clusters(
            strategy_ids=strategy_ids,
            advisory=advisory_payload,
        )
        universe_key = self._universe_key(strategy_ids)
        prev_universe_weights = dict(self._last_phase4_weights_by_universe.get(universe_key, {}) or {})
        factor_exposures = dict(advisory_payload.get("strategy_factor_exposures", {}) or {})
        factor_limits = dict(advisory_payload.get("factor_limits", {}) or {})
        if (not factor_limits) and factor_exposures:
            inferred_factors = set()
            for payload in factor_exposures.values():
                inferred_factors.update(dict(payload or {}).keys())
            factor_limits = {str(f): float(self.config.phase5_factor_limit) for f in inferred_factors}

        phase8_snapshot: Dict[str, Any] = {}
        manifold_redundancy: Dict[str, float] = {}
        manifold_distance: Dict[str, Dict[str, float]] = {}
        manifold_clusters: Dict[str, str] = {}
        manifold_cluster_cap = float(effective_cluster_cap_cfg)
        if bool(self.config.phase8_enabled):
            snap = self._phase8_builder.build(
                alpha_ids=strategy_ids,
                expected_edges=expected_edges,
                strategy_points=strategy_points,
                return_series_map=dict(ctx.strategy_return_series or {}),
                capacity_caps=caps,
                factor_exposures=factor_exposures,
                weights=(prev_universe_weights or current_weights),
            )
            phase8_snapshot = snap.to_dict()
            manifold_redundancy = dict(snap.redundancy_scores or {})
            manifold_distance = dict(snap.distance_matrix or {})
            manifold_clusters = dict(snap.cluster_map or {})
            if bool(snap.overcrowding_flag):
                manifold_cluster_cap = float(
                    min(
                        float(effective_cluster_cap_cfg),
                        float(self.config.phase8_cluster_cap),
                    )
                )
            else:
                manifold_cluster_cap = float(effective_cluster_cap_cfg)
        effective_clusters = dict(manifold_clusters or clusters)

        phase4_payload: Dict[str, Any] = {
            "status": "disabled",
            "allocation": {},
            "portfolio_monte_carlo": {},
            "regime_allocations": [],
            "manifold": phase8_snapshot,
            "phase9": {},
        }
        if bool(self.config.phase4_enabled):
            phase4_allocator = ConvexPortfolioAllocator(
                risk_aversion=effective_risk_aversion,
                return_weight=1.0,
                concentration_penalty=self.config.convex_concentration_penalty,
                crisis_corr_spike=self.config.phase4_correlation_spike,
            )

            def _run_allocation(
                *,
                expected_edges_local: Dict[str, float],
                covariance_local: Dict[str, Dict[str, float]],
                current_weights_local: Dict[str, float],
                risk_level_local: float,
            ) -> tuple[Dict[str, float], Dict[str, Any]]:
                if bool(self.config.phase9_enabled):
                    horizons = [str(h) for h in list(self.config.phase9_horizons or ()) if str(h).strip()]
                    if not horizons:
                        horizons = ["1d", "5d", "20d", "60d", "120d"]
                    horizon_mix = self._phase9_horizon_mix(horizons, risk_level_local)
                    horizon_edges = self._phase9_horizon_edges(
                        strategy_ids=strategy_ids,
                        expected_edges=expected_edges_local,
                        horizons=horizons,
                        risk_level=risk_level_local,
                        strategy_points=strategy_points,
                    )
                    phase9_alloc = phase4_allocator.optimize_multi_horizon(
                        strategy_ids=strategy_ids,
                        horizons=horizons,
                        expected_edges_by_horizon=horizon_edges,
                        covariance=covariance_local,
                        capacity_caps=caps,
                        cluster_map=effective_clusters,
                        leverage_limit=float(effective_leverage_limit),
                        cluster_cap=float(manifold_cluster_cap),
                        cross_horizon_corr=float(self.config.phase9_cross_horizon_corr),
                        horizon_mix=horizon_mix,
                        manifold_redundancy=manifold_redundancy,
                        manifold_distance=manifold_distance,
                        manifold_penalty_eta=float(effective_eta),
                        manifold_diversity_delta=float(effective_delta),
                    )
                    alloc_payload = phase9_alloc.to_dict()
                    alloc_payload["weights"] = dict(phase9_alloc.aggregated_weights or {})
                    alloc_payload["phase9_enabled"] = True
                    return dict(phase9_alloc.aggregated_weights or {}), alloc_payload

                alloc = phase4_allocator.optimize(
                    strategy_ids=strategy_ids,
                    expected_edges=expected_edges_local,
                    covariance=covariance_local,
                    capacity_caps=caps,
                    cluster_map=effective_clusters,
                    current_weights=current_weights_local,
                    leverage_limit=float(effective_leverage_limit),
                    cluster_cap=float(manifold_cluster_cap),
                    correlation_threshold=float(self.config.phase4_corr_threshold),
                    max_turnover=float(self.config.phase4_max_turnover),
                    factor_exposures=factor_exposures,
                    factor_limits=factor_limits,
                    manifold_redundancy=manifold_redundancy,
                    manifold_distance=manifold_distance,
                    manifold_penalty_eta=float(effective_eta),
                    manifold_diversity_delta=float(effective_delta),
                )
                alloc_payload = alloc.to_dict()
                alloc_payload["phase9_enabled"] = False
                return dict(alloc.weights or {}), alloc_payload

            if bool(self.config.phase5_enabled) and bool(self.config.phase5_regime_conditioned):
                regime_weight_maps: list[tuple[float, Dict[str, float]]] = []
                regime_rows: list[Dict[str, Any]] = []
                for reg_name, reg_prob in sorted(dict(regime_probs or {}).items()):
                    prob = float(max(0.0, reg_prob))
                    if prob <= 0.0:
                        continue
                    risk_level = self._regime_risk_level(reg_name)
                    w_r, row = _run_allocation(
                        expected_edges_local=self._adjust_expected_edges_for_regime(expected_edges, risk_level),
                        covariance_local=self._adjust_covariance_for_regime(dict(ctx.covariance_matrix or {}), risk_level),
                        current_weights_local=(prev_universe_weights or current_weights),
                        risk_level_local=float(risk_level),
                    )
                    regime_weight_maps.append((prob, dict(w_r)))
                    row["regime"] = str(reg_name)
                    row["probability"] = float(prob)
                    row["risk_level"] = float(risk_level)
                    regime_rows.append(row)
                blended = self._blend_weight_maps(regime_weight_maps)
                convex_weights = self._normalize_weights(
                    blended,
                    caps=caps,
                    leverage_limit=float(effective_leverage_limit),
                )
                phase4_payload["regime_allocations"] = regime_rows
                phase4_payload["regime_conditioned"] = True
                convex_weights, alloc_payload = _run_allocation(
                    expected_edges_local=expected_edges,
                    covariance_local=dict(ctx.covariance_matrix or {}),
                    current_weights_local=convex_weights,
                    risk_level_local=float(self._regime_risk_level(str(regime.dominant_state))),
                )
                phase4_payload["allocation"] = alloc_payload
            else:
                convex_weights, alloc_payload = _run_allocation(
                    expected_edges_local=expected_edges,
                    covariance_local=dict(ctx.covariance_matrix or {}),
                    current_weights_local=(prev_universe_weights or current_weights),
                    risk_level_local=float(self._regime_risk_level(str(regime.dominant_state))),
                )
                phase4_payload["allocation"] = alloc_payload
                phase4_payload["regime_conditioned"] = False
            phase4_payload["phase8_cluster_cap_effective"] = float(manifold_cluster_cap)
            phase4_payload["phase9_enabled"] = bool(self.config.phase9_enabled)
            phase4_payload["phase9"] = {
                "enabled": bool(self.config.phase9_enabled),
                "horizons": [str(h) for h in list(self.config.phase9_horizons or ())],
                "cross_horizon_corr": float(self.config.phase9_cross_horizon_corr),
            }

            inertia = float(np.clip(effective_inertia, 0.0, 0.95)) if bool(self.config.phase5_enabled) else 0.0
            entropy_high = bool(float(getattr(regime, "entropy", 0.0)) > float(self.config.phase5_entropy_freeze_threshold))
            if prev_universe_weights:
                alpha = float(max(0.05, 1.0 - inertia))
                if entropy_high or (not regime_gate):
                    alpha = float(min(alpha, 0.20))
                smoothed: Dict[str, float] = {}
                for sid in strategy_ids:
                    new_w = float(convex_weights.get(sid, 0.0))
                    old_w = float(prev_universe_weights.get(sid, 0.0))
                    smoothed[sid] = float((alpha * new_w) + ((1.0 - alpha) * old_w))
                convex_weights = self._normalize_weights(
                    smoothed,
                    caps=caps,
                    leverage_limit=float(effective_leverage_limit),
                )
                phase4_payload["inertia_alpha"] = float(alpha)
                phase4_payload["entropy_high"] = bool(entropy_high)

            self._last_phase4_weights_by_universe[universe_key] = dict(convex_weights)
            convex_share = float(convex_weights.get(proposal.strategy_id, 1.0 / max(1, len(strategy_ids))))

            eig_ratio = self._safe_float(
                dict(phase4_payload.get("allocation", {}) or {}).get("metadata", {}).get("eigen_ratio_crisis", 0.0),
                0.0,
            )
            eig_threshold = float(self.config.phase4_eigen_risk_threshold)
            if eig_ratio > eig_threshold:
                x = float((eig_ratio - eig_threshold) / max(1e-6, 1.0 - eig_threshold))
                eigen_multiplier = float(np.clip(1.0 - (self.config.phase4_eigen_penalty_scale * x), 0.50, 1.0))
            else:
                eigen_multiplier = 1.0
            phase4_payload["eigen_multiplier"] = float(eigen_multiplier)
            if eig_ratio > eig_threshold:
                phase4_payload["status"] = "stressed"
        else:
            if len(strategy_ids) <= 1:
                convex_share = 1.0
                convex_weights = {proposal.strategy_id: 1.0}
            else:
                convex_weights = {sid: float(1.0 / len(strategy_ids)) for sid in strategy_ids}
                convex_share = float(convex_weights.get(proposal.strategy_id, 1.0 / max(1, len(strategy_ids))))
            eigen_multiplier = 1.0

        uniform_share = 1.0 / max(1, len(strategy_ids))
        convex_multiplier = self._clamp(
            (convex_share / max(1e-6, uniform_share)) * float(eigen_multiplier),
            0.50,
            1.50,
        )

        if bool(self.config.phase4_enabled):
            phase4_mc = self._phase4_mc.evaluate(
                strategy_ids=strategy_ids,
                weights=convex_weights,
                expected_edges=expected_edges,
                return_series_map=dict(ctx.strategy_return_series or {}),
                covariance=dict(ctx.covariance_matrix or {}),
                drawdown_breach=float(self.config.phase4_drawdown_breach),
                max_p_dd_breach=float(self.config.phase4_max_p_dd_breach),
                seed_key=f"{proposal.proposal_id}:{proposal.strategy_id}:{proposal.signal_id}",
            )
            phase4_payload["portfolio_monte_carlo"] = phase4_mc.to_dict()
            phase4_payload["status"] = "stable" if str(phase4_mc.status) == "stable" else "stressed"
            mc = {
                "breach_probability": float(phase4_mc.p_maxdd_breach),
                "expected_drawdown": float(phase4_mc.expected_drawdown),
                "stability_multiplier": float(phase4_mc.stability_multiplier),
                "sharpe_negative_probability": float(phase4_mc.p_sharpe_negative),
                "cvar_95": float(phase4_mc.cvar_95),
                "recovery_days_p95": float(phase4_mc.recovery_days_p95),
                "drawdown_cluster_p95": float(phase4_mc.drawdown_cluster_p95),
                "time_under_water_mean": float(phase4_mc.time_under_water_mean),
            }
            mc_multiplier = self._clamp(float(phase4_mc.stability_multiplier), 0.60, 1.0)
        else:
            mc = {
                "breach_probability": 0.0,
                "expected_drawdown": 0.0,
                "stability_multiplier": 1.0,
                "sharpe_negative_probability": 0.0,
                "cvar_95": 0.0,
                "recovery_days_p95": 0.0,
                "drawdown_cluster_p95": 0.0,
                "time_under_water_mean": 0.0,
            }
            mc_multiplier = 1.0

        phase3_payload: Dict[str, Any] = {
            "phase3_status": "provisional_pass",
            "reason": "insufficient_history",
            "alpha_id": str(proposal.strategy_id),
        }
        phase3_multiplier = 1.0
        if bool(self.config.phase3_enabled):
            min_history = max(5, int(self.config.phase3_min_history))
            if len(strategy_returns) >= min_history:
                q = self._phase3.qualify_alpha(
                    alpha_id=str(proposal.strategy_id),
                    returns=strategy_returns,
                    portfolio_returns=portfolio_returns,
                )
                phase3_payload = q.to_dict()
                phase3_payload["phase3_status"] = str(q.phase3_status)
                cap_est = self._safe_float(
                    phase3_payload.get("deterministic", {}).get("capacity_limit_estimate", 0.0),
                    0.0,
                )
                if cap_est > 0.0 and proposal.requested_notional > 0.0:
                    phase3_multiplier = self._clamp(cap_est / float(proposal.requested_notional), 0.25, 1.0)
            else:
                phase3_payload = {
                    "phase3_status": "provisional_pass",
                    "reason": "insufficient_history",
                    "alpha_id": str(proposal.strategy_id),
                    "history_points": int(len(strategy_returns)),
                    "min_required_history": int(min_history),
                }

        phase6_payload: Dict[str, Any] = {
            "status": "disabled",
            "final_multiplier": 1.0,
        }
        phase6_multiplier = 1.0
        survival_prob = float(1.0 - self._safe_float(mc.get("breach_probability", 0.0), 0.0))
        live_sharpe = 0.0
        if bool(self.config.phase6_enabled):
            if len(strategy_returns) >= 5:
                live_arr = np.asarray(strategy_returns, dtype=float)
                live_sharpe = float(np.mean(live_arr) / (np.std(live_arr) + 1e-8))
                mc_sharpe_std = float(np.std(live_arr) / max(np.sqrt(float(len(live_arr))), 1.0))
            else:
                live_sharpe = 0.0
                mc_sharpe_std = 0.20
            expected_sharpe = float(bayes["posterior_edge"] / max(np.sqrt(variance_for_kelly), 1e-6))
            prior_phase6 = float(self._last_phase6_multiplier_by_strategy.get(proposal.strategy_id, 1.0))
            adaptive = self._adaptive_capital.scale(
                risk_snapshot=dict(risk_snapshot or {}),
                survival_probability=survival_prob,
                regime_multiplier=float(regime_multiplier),
                estimation_error=float(kelly_estimation_error),
                live_sharpe=float(live_sharpe),
                expected_sharpe=float(expected_sharpe),
                mc_sharpe_std=float(max(mc_sharpe_std, 1e-4)),
                prior_multiplier=prior_phase6,
                inertia=float(np.clip(effective_inertia, 0.0, 0.95)),
            )
            phase6_payload = adaptive.to_dict()
            phase6_multiplier = float(adaptive.final_multiplier)
            self._last_phase6_multiplier_by_strategy[str(proposal.strategy_id)] = float(phase6_multiplier)

        phase10_payload: Dict[str, Any] = {
            "status": "disabled",
            "theta": dict(theta),
            "multiplier": 1.0,
        }
        phase10_multiplier = 1.0
        if bool(self.config.phase10_enabled):
            alpha_regret_component = float(
                np.clip(
                    (max(0.0, -self._safe_float(dict(phase6_payload).get("drift_z_score", 0.0), 0.0)) / 3.0)
                    + (0.40 * max(0.0, 1.0 - survival_prob))
                    + (0.20 * max(0.0, -live_sharpe)),
                    0.0,
                    1.0,
                )
            )
            exploration_gap = float(
                np.clip(
                    max(0.0, 0.20 - self._safe_float(theta.get("phase10_exploration_rate", 0.2), 0.2)),
                    0.0,
                    1.0,
                )
            )
            system_regret = self._phase10_regret.compute(
                alpha_regrets={str(proposal.strategy_id): alpha_regret_component},
                portfolio_metrics={
                    "p_maxdd_breach": float(mc.get("breach_probability", 0.0)),
                    "eigen_spike": float(dict(phase4_payload.get("allocation", {}) or {}).get("metadata", {}).get("eigen_spike", 1.0)),
                    "structural_fragility_index": float(dict(phase8_snapshot or {}).get("structural_fragility_index", 0.0)),
                },
                research_metrics={
                    "durability_collapse": float(np.clip(max(0.0, 1.0 - self._safe_float(bayes.get("shrinkage_weight", 0.0), 0.0)), 0.0, 1.0)),
                    "compute_misallocation": float(1.0 if bool(dict(phase8_snapshot or {}).get("overcrowding_flag", False)) else 0.0),
                    "exploration_gap": float(exploration_gap),
                },
            )
            capital_scale = float(
                np.clip(
                    float(proposal.requested_notional) / max(1.0, float(portfolio_snapshot.get("net_liquidation_value", 0.0) or 0.0)),
                    0.0,
                    1.5,
                )
            )
            weights = self._phase10_reweighter.reweight(
                system_stability_index=float(system_regret.system_stability_index),
                regime_entropy=float(getattr(regime, "entropy", 0.0)),
                capital_scale=capital_scale,
            )
            reflex = self._phase10_reflexivity.evaluate(
                capital_scale=capital_scale,
                base_decay=abs(self._safe_float(getattr(strategy_point, "edge_decay", 0.0) if strategy_point is not None else 0.0, 0.0)),
                mortality_sensitivity=effective_mortality_sensitivity,
            )
            capital_growth_proxy = float(np.clip(self._safe_float(expected_edges.get(proposal.strategy_id, 0.0), 0.0), -0.5, 1.0))
            explore = self._phase10_exploration.decide(
                system_stability_index=float(system_regret.system_stability_index),
                capital_growth_rate=capital_growth_proxy,
            )
            arch = self._phase10_optimizer.run_cycle(
                context={
                    "expected_return": float(dict(phase4_payload.get("allocation", {}) or {}).get("expected_return", 0.0)),
                    "volatility": float(dict(phase4_payload.get("allocation", {}) or {}).get("volatility", 0.0)),
                    "cvar_95": float(mc.get("cvar_95", 0.0)),
                    "structural_fragility_index": float(dict(phase8_snapshot or {}).get("structural_fragility_index", 0.0)),
                    "eigen_spike": float(dict(phase4_payload.get("allocation", {}) or {}).get("metadata", {}).get("eigen_spike", 1.0)),
                    "survival_probability": float(survival_prob),
                    "system_regret": float(system_regret.system_regret),
                    "system_stability_index": float(system_regret.system_stability_index),
                    "research_gap": float(exploration_gap),
                    "capital_scale": float(capital_scale),
                },
                history_points=int(len(strategy_returns)),
            )
            phase10_multiplier = float(
                np.clip(
                    float(weights.strategic_multiplier) * float(reflex.reflexivity_multiplier),
                    0.55,
                    1.30,
                )
            )
            phase10_payload = {
                "status": "active",
                "theta": dict(arch.theta),
                "system_regret": system_regret.to_dict(),
                "objective_weights": weights.to_dict(),
                "reflexivity": reflex.to_dict(),
                "exploration_governor": explore.to_dict(),
                "architecture_update": arch.to_dict(),
                "multiplier": float(phase10_multiplier),
            }

        factor = (
            float(kelly_multiplier)
            * float(convex_multiplier)
            * float(regime_multiplier)
            * float(mc_multiplier)
            * float(phase3_multiplier)
            * float(phase6_multiplier)
            * float(phase10_multiplier)
        )
        weekly = self._apply_weekly_shift_cap(proposal.strategy_id, factor)
        factor = float(weekly["factor"])
        factor = self._clamp(factor, float(self.config.min_size_factor), float(self.config.max_size_factor))
        return {
            "size_factor": factor,
            "enabled": True,
            "bayesian_posterior_edge": float(bayes["posterior_edge"]),
            "bayesian_observed_edge": float(bayes["observed_edge"]),
            "bayesian_shrinkage_weight": float(bayes["shrinkage_weight"]),
            "kelly_fraction": float(kelly["kelly_fraction_regularized"]),
            "kelly_fraction_raw": float(kelly["kelly_fraction_raw"]),
            "kelly_variance_used": float(kelly["variance_used"]),
            "kelly_variance_base": float(variance),
            "kelly_estimation_error": float(kelly_estimation_error),
            "convex_target_share": float(convex_share),
            "convex_uniform_share": float(uniform_share),
            "convex_multiplier": float(convex_multiplier),
            "regime_multiplier": float(regime_multiplier),
            "regime_state": regime.to_dict(),
            "regime_probabilities": dict(regime_probs),
            "regime_gate": bool(regime_gate),
            "drawdown_lock": bool(drawdown_lock),
            "monte_carlo_breach_prob": float(mc["breach_probability"]),
            "monte_carlo_expected_drawdown": float(mc["expected_drawdown"]),
            "monte_carlo_multiplier": float(mc_multiplier),
            "monte_carlo_sharpe_negative_prob": float(mc.get("sharpe_negative_probability", 0.0)),
            "monte_carlo_cvar_95": float(mc.get("cvar_95", 0.0)),
            "monte_carlo_recovery_days_p95": float(mc.get("recovery_days_p95", 0.0)),
            "monte_carlo_drawdown_cluster_p95": float(mc.get("drawdown_cluster_p95", 0.0)),
            "monte_carlo_time_under_water_mean": float(mc.get("time_under_water_mean", 0.0)),
            "phase4": phase4_payload,
            "phase4_status": str(phase4_payload.get("status", "disabled")),
            "phase5": {
                "enabled": bool(self.config.phase5_enabled),
                "regime_conditioned": bool(self.config.phase5_regime_conditioned),
                "allocation_inertia": float(effective_inertia),
                "entropy_threshold": float(self.config.phase5_entropy_freeze_threshold),
            },
            "phase3": phase3_payload,
            "phase3_status": str(phase3_payload.get("phase3_status", "provisional_pass")),
            "phase3_multiplier": float(phase3_multiplier),
            "phase3_min_history": int(max(5, int(self.config.phase3_min_history))),
            "phase6_adaptive": phase6_payload,
            "phase6_multiplier": float(phase6_multiplier),
            "phase10": phase10_payload,
            "phase10_status": str(phase10_payload.get("status", "disabled")),
            "phase10_multiplier": float(phase10_multiplier),
            "phase10_theta": dict(theta),
            "weekly_shift_control": weekly,
            "strategy_universe_size": int(len(strategy_ids)),
        }

    def _pool_for_origin(self, origin: ProposalOrigin) -> str:
        if origin == ProposalOrigin.OPTIONS_HEDGE:
            return "hedge"
        if origin == ProposalOrigin.OPTIONS_ALPHA:
            return "options_alpha"
        if origin == ProposalOrigin.MANUAL:
            return "discretionary"
        return "equity_alpha"

    def _pool_target(self, pool: str, total_capital: float) -> float:
        total = float(max(0.0, total_capital))
        if pool == "hedge":
            return total * float(self.config.hedge_reserve_pct)
        if pool == "options_alpha":
            return total * float(self.config.options_alpha_reserve_pct)
        if pool == "discretionary":
            return total * float(self.config.discretionary_reserve_pct)
        return total * float(self.config.equity_alpha_reserve_pct)

    def evaluate(
        self,
        proposal: TradeProposal,
        portfolio_snapshot: Dict[str, Any],
        budget_snapshot: Dict[str, Any] | None = None,
        risk_snapshot: Dict[str, Any] | None = None,
    ) -> CapitalDecision:
        request = float(proposal.requested_notional or 0.0)
        decision_id = f"cap_{uuid4().hex[:16]}"
        if request <= 0.0:
            return CapitalDecision(
                decision_id=decision_id,
                is_approved=False,
                approved_notional=0.0,
                reserve_pool=self._pool_for_origin(proposal.origin),
                reserve_impact={},
                sizing_rationale={"requested_notional": request, "reason": "non_positive_request"},
                denial_reason="capital.request_non_positive",
            )

        total_capital = float(portfolio_snapshot.get("net_liquidation_value", 0.0) or 0.0)
        reserve_usage = dict((budget_snapshot or {}).get("reserve_usage", {}) or {})
        reserve_pool = self._pool_for_origin(proposal.origin)
        target = self._pool_target(reserve_pool, total_capital)
        used = float(reserve_usage.get(reserve_pool, 0.0) or 0.0)
        available = max(0.0, target - used)
        advanced = self._advanced_size_factor(
            proposal,
            portfolio_snapshot=portfolio_snapshot,
            budget_snapshot=budget_snapshot,
            risk_snapshot=risk_snapshot,
        )
        adjusted_request = request * float(advanced.get("size_factor", 1.0) or 1.0)
        adjusted_request = max(0.0, adjusted_request)

        phase3_status = str(advanced.get("phase3_status", "provisional_pass") or "provisional_pass")
        if bool(self.config.phase3_enabled) and bool(self.config.phase3_enforce) and str(phase3_status) == "reject":
            phase3_payload = dict(advanced.get("phase3", {}) or {})
            det_status = str(dict(phase3_payload.get("deterministic", {}) or {}).get("status", "") or "")
            mc_status = str(dict(phase3_payload.get("monte_carlo", {}) or {}).get("status", "") or "")
            if det_status != "deployable":
                denial = "capital.phase3_deterministic_fail"
            elif mc_status != "stable":
                denial = "capital.phase3_monte_carlo_fail"
            else:
                denial = "capital.phase3_reject"
            return CapitalDecision(
                decision_id=decision_id,
                is_approved=False,
                approved_notional=0.0,
                reserve_pool=reserve_pool,
                reserve_impact={
                    "target": target,
                    "used": used,
                    "available": available,
                    "requested": request,
                },
                sizing_rationale={
                    "reserve_pool": reserve_pool,
                    "reserve_target": target,
                    "reserve_used": used,
                    "reserve_available": available,
                    "requested_notional": request,
                    "advanced_models": advanced,
                },
                denial_reason=denial,
            )
        approved = min(adjusted_request, available)

        if approved < float(self.config.min_trade_notional):
            return CapitalDecision(
                decision_id=decision_id,
                is_approved=False,
                approved_notional=0.0,
                reserve_pool=reserve_pool,
                reserve_impact={
                    "target": target,
                    "used": used,
                    "available": available,
                    "requested": request,
                },
                sizing_rationale={
                    "reserve_pool": reserve_pool,
                    "reserve_target": target,
                    "reserve_used": used,
                    "reserve_available": available,
                    "min_trade_notional": float(self.config.min_trade_notional),
                    "requested_notional": request,
                    "adjusted_requested_notional": adjusted_request,
                    "advanced_models": advanced,
                },
                denial_reason="capital.reserve_unavailable",
            )

        return CapitalDecision(
            decision_id=decision_id,
            is_approved=True,
            approved_notional=float(approved),
            reserve_pool=reserve_pool,
            reserve_impact={
                "target": target,
                "used": used,
                "available_before": available,
                "available_after": max(0.0, available - approved),
                "requested": request,
                "requested_adjusted": adjusted_request,
                "approved": approved,
            },
            sizing_rationale={
                "reserve_pool": reserve_pool,
                "reserve_target": target,
                "reserve_used": used,
                "reserve_available_before": available,
                "requested_notional": request,
                "adjusted_requested_notional": adjusted_request,
                "approved_notional": approved,
                "advanced_models": advanced,
            },
        )
