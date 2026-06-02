"""Portfolio Runtime Service (PRS): single mutation authority for portfolio state."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np

from .capital_allocator import CapitalAllocatorPolicy
from .alpha_mortality_controller import AlphaMortalityController, AlphaMortalityProfile, MortalityState
from .certification_gate import CertificationGate, CertificationGateConfig
from .conditional_parameter_engine import ConditionalParameterEngine
from .contracts import (
    BudgetDecision,
    CapitalDecision,
    DecisionMode,
    ExecutionEvent,
    ExecutionEventType,
    ExecutionResult,
    LiquidityDecision,
    PortfolioStateSnapshot,
    ProposalOrigin,
    ProposalReceipt,
    RuntimeState,
    StressScenarioResult,
    TradeProposal,
)
from .fsm import ExecutionFSM
from .regime_state_engine import BayesianRegimeStateEngine
from .research_evolution_engine import ResearchEvolutionEngine
from .liquidity_gate import LiquidityGate
from .materializer import RuntimeMaterializer
from .greeks_adapter import RuntimeGreeksAdapter
from .rebalance_trigger import RebalanceTriggerEngine
from .risk_budget import RiskBudgetManager
from .shock_engine import OptionsShockEngine
from .state import PortfolioState, compute_state_hash
from .storage import RuntimeEventStore
from .truth_drift_monitor import TruthDriftMonitor


class PortfolioRuntimeService:
    """Canonical operating layer for proposal -> decision -> execution -> state."""

    _REGIME_STATE_CONTROL_KEY = "adaptive.regime_engine_state"
    _PARAM_STATE_CONTROL_KEY = "adaptive.parameter_engine_state"
    _EVOLUTION_META_CONTROL_KEY = "adaptive.research_evolution_meta"
    _PHASE3_LIVE_CONTROL_KEY = "adaptive.phase3_live_envelopes"
    _PHASE6_PROFILE_CONTROL_KEY = "adaptive.phase6_mortality_profiles"
    _PHASE6_STATE_CONTROL_KEY = "adaptive.phase6_mortality_state"
    _PHASE6_DECISIONS_CONTROL_KEY = "adaptive.phase6_mortality_decisions"

    def __init__(
        self,
        *,
        db_path: str = "data/runtime/portfolio_runtime.db",
        materialized_output_dir: str = "data/processed/runtime",
        starting_cash: float = 1_000_000.0,
        cert_ttl_days: int = 30,
        post_fill_breach_freeze_threshold: int = 3,
        enable_research_evolution: bool = True,
        enable_phase6_mortality: bool = True,
    ):
        self.store = RuntimeEventStore(db_path, writer_name="portfolio_runtime_service")
        self.fsm = ExecutionFSM()
        self.capital_allocator = CapitalAllocatorPolicy()
        self.risk_budget_manager = RiskBudgetManager()
        self.liquidity_gate = LiquidityGate()
        self.cert_gate = CertificationGate(self.store, config=CertificationGateConfig(ttl_days=cert_ttl_days))
        self.rebalance_engine = RebalanceTriggerEngine()
        self.shock_engine = OptionsShockEngine()
        self.materializer = RuntimeMaterializer(materialized_output_dir)
        self.truth_drift_monitor = TruthDriftMonitor()
        self.greeks_adapter = RuntimeGreeksAdapter()
        self.strict_mode = str(os.getenv("NORTHSTAR_STRICT_MODE", "0")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        freeze_state = self.store.get_runtime_freeze_state()
        runtime_state = str(self.store.get_runtime_state() or "ACTIVE").upper()
        if runtime_state not in {RuntimeState.ACTIVE.value, RuntimeState.FROZEN.value}:
            runtime_state = RuntimeState.ACTIVE.value
        self.runtime_state = RuntimeState(runtime_state)
        self.global_freeze = bool(freeze_state.get("is_frozen", False)) or (
            self.runtime_state == RuntimeState.FROZEN
        )
        self.freeze_reason = str(freeze_state.get("reason", "") or "")
        self._post_fill_breach_count = 0
        self._post_fill_breach_freeze_threshold = max(1, int(post_fill_breach_freeze_threshold))
        self._enable_research_evolution = bool(enable_research_evolution)
        self._enable_phase6_mortality = bool(enable_phase6_mortality)
        self._phase3_live_envelopes: Dict[str, Dict[str, Any]] = {}
        self._phase6_profiles: Dict[str, Dict[str, Any]] = {}
        self._phase6_state_by_strategy: Dict[str, Dict[str, Any]] = {}
        self._phase6_latest_decisions: Dict[str, Dict[str, Any]] = {}
        self.mortality_controller: Optional[AlphaMortalityController] = (
            AlphaMortalityController() if self._enable_phase6_mortality else None
        )

        self._starting_cash = float(starting_cash)
        self.state = self._load_state_or_initialize()
        self.regime_engine: Optional[BayesianRegimeStateEngine] = None
        self.parameter_engine: Optional[ConditionalParameterEngine] = None
        self.research_evolution: Optional[ResearchEvolutionEngine] = None
        self._ade_engine: Optional[Any] = None
        self._last_evolution_cycle_date_by_scope: Dict[str, str] = {}
        self._latest_evolution_cycle: Dict[str, Any] = {}
        self._init_adaptive_layers()
        self._restore_phase3_live_state()
        self._restore_phase6_mortality_state()
        self._rehydrate_fsm()
        self._materialize_all()

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return float(default)

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return float(max(lo, min(hi, v)))

    def _init_adaptive_layers(self) -> None:
        if not self._enable_research_evolution:
            return
        self.regime_engine = BayesianRegimeStateEngine(
            n_states=3,
            confidence_threshold=0.80,
            min_persistence_days=5,
        )
        self.parameter_engine = ConditionalParameterEngine(
            base_parameters={
                "size_multiplier": 1.0,
                "slippage_buffer_bps": 0.0,
                "aggressiveness_multiplier": 1.0,
            },
            n_states=3,
            max_step_norm=0.10,
            min_regime_confidence=0.80,
            min_regime_persistence_days=5,
            require_structural_break=True,
            parameter_bounds={
                "size_multiplier": (0.50, 1.50),
                "slippage_buffer_bps": (0.0, 25.0),
                "aggressiveness_multiplier": (0.50, 1.50),
            },
        )
        self.parameter_engine.set_surface("size_multiplier", [0.08, 0.00, -0.12])
        self.parameter_engine.set_surface("slippage_buffer_bps", [0.0, 4.0, 10.0])
        self.parameter_engine.set_surface("aggressiveness_multiplier", [0.10, 0.00, -0.12])

        try:
            from src.diagnostics.alpha_diagnostics_engine import AlphaDiagnosticsEngine, DiagnosticsPaths

            self._ade_engine = AlphaDiagnosticsEngine(
                DiagnosticsPaths(runtime_db=str(self.store.db_path))
            )
        except Exception:
            self._ade_engine = None
        phase7_engine = None
        try:
            from src.research.meta import (
                AlphaExperienceMemory,
                MetaPolicyStore,
                ResearchEvolutionEngineV2,
            )

            meta_dir = Path(str(self.store.db_path)).parent.parent / "research"
            memory = AlphaExperienceMemory(db_path=str(meta_dir / "alpha_experience_memory.db"))
            policy_store = MetaPolicyStore(policy_path=str(meta_dir / "meta_policy.json"))
            phase7_engine = ResearchEvolutionEngineV2(
                memory=memory,
                policy_store=policy_store,
            )
        except Exception:
            phase7_engine = None
        self.research_evolution = ResearchEvolutionEngine(
            regime_engine=self.regime_engine,
            parameter_engine=self.parameter_engine,
            ade_engine=self._ade_engine,
            phase7_engine=phase7_engine,
            lock_drawdown_threshold=0.12,
            degrade_err_threshold=0.60,
            degrade_decay_threshold=-0.02,
        )
        self._restore_adaptive_state()

    def _restore_adaptive_state(self) -> None:
        if self.regime_engine is not None:
            payload = self.store.get_runtime_control_json(self._REGIME_STATE_CONTROL_KEY, {})
            if payload:
                self.regime_engine.load_state_dict(payload)
        if self.parameter_engine is not None:
            payload = self.store.get_runtime_control_json(self._PARAM_STATE_CONTROL_KEY, {})
            if payload:
                self.parameter_engine.load_state_dict(payload)
        meta = self.store.get_runtime_control_json(self._EVOLUTION_META_CONTROL_KEY, {})
        by_scope = dict(meta.get("last_cycle_date_by_scope", {}) or {})
        self._last_evolution_cycle_date_by_scope = {str(k): str(v) for k, v in by_scope.items()}
        latest = dict(meta.get("latest_cycle", {}) or {})
        self._latest_evolution_cycle = latest if isinstance(latest, dict) else {}

    def _persist_adaptive_state(self) -> None:
        if self.regime_engine is not None:
            self.store.set_runtime_control_json(
                self._REGIME_STATE_CONTROL_KEY,
                self.regime_engine.to_state_dict(),
            )
        if self.parameter_engine is not None:
            self.store.set_runtime_control_json(
                self._PARAM_STATE_CONTROL_KEY,
                self.parameter_engine.to_state_dict(),
            )
        self.store.set_runtime_control_json(
            self._EVOLUTION_META_CONTROL_KEY,
            {
                "last_cycle_date_by_scope": dict(self._last_evolution_cycle_date_by_scope),
                "latest_cycle": dict(self._latest_evolution_cycle),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _restore_phase3_live_state(self) -> None:
        payload = self.store.get_runtime_control_json(self._PHASE3_LIVE_CONTROL_KEY, {})
        if not isinstance(payload, dict):
            self._phase3_live_envelopes = {}
            return
        cleaned: Dict[str, Dict[str, Any]] = {}
        for sid, raw in payload.items():
            if not isinstance(raw, dict):
                continue
            cleaned[str(sid)] = dict(raw)
        self._phase3_live_envelopes = cleaned

    def _persist_phase3_live_state(self) -> None:
        self.store.set_runtime_control_json(
            self._PHASE3_LIVE_CONTROL_KEY,
            dict(self._phase3_live_envelopes),
        )

    def _restore_phase6_mortality_state(self) -> None:
        if not self._enable_phase6_mortality:
            self._phase6_profiles = {}
            self._phase6_state_by_strategy = {}
            self._phase6_latest_decisions = {}
            return
        raw_profiles = self.store.get_runtime_control_json(self._PHASE6_PROFILE_CONTROL_KEY, {})
        raw_state = self.store.get_runtime_control_json(self._PHASE6_STATE_CONTROL_KEY, {})
        raw_decisions = self.store.get_runtime_control_json(self._PHASE6_DECISIONS_CONTROL_KEY, {})
        profiles: Dict[str, Dict[str, Any]] = {}
        for sid, payload in dict(raw_profiles or {}).items():
            try:
                profile = AlphaMortalityProfile.from_dict(payload, strategy_id=str(sid))
                profiles[str(sid)] = profile.to_dict()
            except Exception:
                continue
        state = {str(k): dict(v) for k, v in dict(raw_state or {}).items() if isinstance(v, dict)}
        decisions = {str(k): dict(v) for k, v in dict(raw_decisions or {}).items() if isinstance(v, dict)}
        self._phase6_profiles = profiles
        self._phase6_state_by_strategy = state
        self._phase6_latest_decisions = decisions

    def _persist_phase6_mortality_state(self) -> None:
        self.store.set_runtime_control_json(self._PHASE6_PROFILE_CONTROL_KEY, dict(self._phase6_profiles))
        self.store.set_runtime_control_json(self._PHASE6_STATE_CONTROL_KEY, dict(self._phase6_state_by_strategy))
        self.store.set_runtime_control_json(self._PHASE6_DECISIONS_CONTROL_KEY, dict(self._phase6_latest_decisions))

    def _extract_phase6_profile(self, strategy_id: str, cap: CapitalDecision) -> Dict[str, Any]:
        sid = str(strategy_id or "")
        if not sid:
            return {}
        advanced = dict(cap.sizing_rationale.get("advanced_models", {}) or {})
        phase3 = dict(advanced.get("phase3", {}) or {})
        deterministic = dict(phase3.get("deterministic", {}) or {})
        phase4 = dict(advanced.get("phase4", {}) or {})
        regime_rows = list(phase4.get("regime_allocations", []) or [])

        prior_mean = float(self._safe_float(advanced.get("bayesian_posterior_edge", 0.0), 0.0))
        prior_var = float(max(1e-6, self._safe_float(advanced.get("kelly_variance_used", 0.05), 0.05)))
        expected_sharpe = float(prior_mean / max(prior_var ** 0.5, 1e-6))
        mc_sharpe_std = float(max(0.10, 0.35 * abs(expected_sharpe) + 0.10))

        regime_profile: Dict[str, float] = {}
        for row in regime_rows:
            if not isinstance(row, dict):
                continue
            regime = str(row.get("regime", "") or "")
            if not regime:
                continue
            ret = float(self._safe_float(row.get("expected_return", 0.0), 0.0))
            vol = float(max(1e-6, self._safe_float(row.get("volatility", 0.20), 0.20)))
            regime_profile[regime] = float(ret / vol)
        if not regime_profile:
            regime_profile = {"state_1": float(expected_sharpe)}
        regime_sigma = float(np.std(list(regime_profile.values()) or [0.0]))
        regime_sigma = float(max(0.10, regime_sigma))

        expected_dd = float(max(0.0, self._safe_float(advanced.get("monte_carlo_expected_drawdown", 0.10), 0.10)))
        dd_std = float(max(0.03, expected_dd * 0.50))
        recovery_p95 = float(max(1.0, self._safe_float(advanced.get("monte_carlo_recovery_days_p95", 30.0), 30.0)))
        recovery_med = float(max(1.0, 0.50 * recovery_p95))
        recovery_sigma = float(max(0.20, 0.25 * (recovery_p95 / max(recovery_med, 1.0))))

        decay_slope = float(self._safe_float(deterministic.get("rolling_decay_slope", 0.0), 0.0))
        baseline_decay_lambda = float(max(1e-4, abs(min(0.0, decay_slope))))
        capacity_limit = float(max(0.0, self._safe_float(deterministic.get("capacity_limit_estimate", 0.0), 0.0)))
        stress_dd = float(max(0.0, self._safe_float(deterministic.get("stress_max_dd", 0.0), 0.0)))
        freeze_dd_limit = float(1.10 * stress_dd) if stress_dd > 0.0 else 0.35

        profile = AlphaMortalityProfile(
            strategy_id=sid,
            prior_mean=prior_mean,
            prior_variance=prior_var,
            mc_sharpe_mean=expected_sharpe,
            mc_sharpe_std=mc_sharpe_std,
            mc_drawdown_mean=expected_dd,
            mc_drawdown_std=dd_std,
            recovery_days_median=recovery_med,
            recovery_sigma=recovery_sigma,
            regime_sharpe_profile=regime_profile,
            regime_sigma=regime_sigma,
            baseline_vol_cluster_acf1=0.0,
            baseline_skew=0.0,
            baseline_convexity=0.0,
            baseline_decay_lambda=baseline_decay_lambda,
            capacity_limit_estimate=capacity_limit,
            freeze_drawdown_limit=freeze_dd_limit,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        return profile.to_dict()

    def _register_phase6_profile(self, strategy_id: str, cap: CapitalDecision) -> Dict[str, Any]:
        if not self._enable_phase6_mortality:
            return {}
        sid = str(strategy_id or "")
        if not sid:
            return {}
        profile = self._extract_phase6_profile(sid, cap)
        if not profile:
            return {}
        self._phase6_profiles[sid] = dict(profile)
        self._persist_phase6_mortality_state()
        return profile

    @staticmethod
    def _phase6_reason_code(reason: str) -> str:
        mapping = {
            "phase6.capacity_breach": "risk.phase6_capacity_breach",
            "phase6.drawdown_tail_breach": "risk.phase6_drawdown_tail_breach",
            "phase6.critical_regret": "risk.phase6_critical_regret",
            "phase6.posterior_collapse": "risk.phase6_posterior_collapse",
        }
        return str(mapping.get(str(reason or ""), "risk.phase6_critical_regret"))

    def _current_regime_probabilities(self) -> Dict[str, float]:
        latest = dict(self._latest_evolution_cycle or {})
        regime_state = dict(latest.get("regime_state", {}) or {})
        probs = dict(regime_state.get("state_probabilities", {}) or {})
        if probs:
            total = float(sum(max(0.0, self._safe_float(v, 0.0)) for v in probs.values()))
            if total > 1e-12:
                return {str(k): float(max(0.0, self._safe_float(v, 0.0)) / total) for k, v in probs.items()}
        return {"state_1": 1.0}

    def _portfolio_proxy_returns(self, max_points: int = 256) -> List[float]:
        series: List[List[float]] = []
        for sid in list(self._phase6_profiles.keys()):
            vals = self._strategy_realized_returns(sid, max_points=max_points)
            if vals:
                series.append(list(vals))
        if not series:
            return []
        m = min(len(x) for x in series)
        if m <= 0:
            return []
        aligned = np.asarray([x[-m:] for x in series], dtype=float)
        return np.mean(aligned, axis=0).tolist()

    def _run_phase6_mortality_monitor(self) -> None:
        if self._is_runtime_frozen():
            return
        if (not self._enable_phase6_mortality) or (self.mortality_controller is None):
            return
        if not self._phase6_profiles:
            return

        strategy_returns_map = {
            sid: self._strategy_realized_returns(sid, max_points=256)
            for sid in list(self._phase6_profiles.keys())
        }
        current_notional_map = {
            sid: self._current_strategy_notional(sid)
            for sid in list(self._phase6_profiles.keys())
        }
        portfolio_returns = self._portfolio_proxy_returns(max_points=256)
        decisions, next_state = self.mortality_controller.run_cycle(
            profiles=self._phase6_profiles,
            strategy_state=self._phase6_state_by_strategy,
            strategy_returns_map=strategy_returns_map,
            regime_probabilities=self._current_regime_probabilities(),
            current_notional_map=current_notional_map,
            portfolio_returns=portfolio_returns,
            market_returns=None,
        )
        self._phase6_state_by_strategy = {str(k): dict(v) for k, v in dict(next_state or {}).items()}
        self._phase6_latest_decisions = {str(k): d.to_dict() for k, d in dict(decisions or {}).items()}
        self._persist_phase6_mortality_state()

        for sid, decision in decisions.items():
            if not bool(decision.freeze):
                continue
            reason_code = self._phase6_reason_code(str(decision.freeze_reason))
            self.set_global_freeze(True, reason=reason_code, updated_by=f"phase6_mortality:{sid}")
            break

    @staticmethod
    def _series_sharpe(values: List[float]) -> float:
        if len(values) <= 1:
            return 0.0
        mean_v = sum(values) / float(len(values))
        var = sum((x - mean_v) ** 2 for x in values) / float(max(1, len(values) - 1))
        std = var ** 0.5
        return float(mean_v / (std + 1e-8))

    @staticmethod
    def _series_max_drawdown(values: List[float]) -> float:
        if not values:
            return 0.0
        eq = 1.0
        peak = 1.0
        worst = 0.0
        for r in values:
            eq *= (1.0 + float(r))
            if eq > peak:
                peak = eq
            dd = (eq / (peak + 1e-12)) - 1.0
            if dd < worst:
                worst = dd
        return float(worst)

    def _extract_phase3_envelope(self, cap: CapitalDecision) -> Dict[str, Any]:
        advanced = dict(cap.sizing_rationale.get("advanced_models", {}) or {})
        phase3 = dict(advanced.get("phase3", {}) or {})
        deterministic = dict(phase3.get("deterministic", {}) or {})
        monte_carlo = dict(phase3.get("monte_carlo", {}) or {})
        return {
            "phase3_status": str(phase3.get("phase3_status", "provisional_pass") or "provisional_pass"),
            "mc_sharpe_p05": float(self._safe_float(monte_carlo.get("sharpe_p05", 0.0), 0.0)),
            "stress_max_dd": float(self._safe_float(deterministic.get("stress_max_dd", 0.0), 0.0)),
            "capacity_limit_estimate": float(
                self._safe_float(deterministic.get("capacity_limit_estimate", 0.0), 0.0)
            ),
            "min_history": int(max(5, self._safe_float(advanced.get("phase3_min_history", 20), 20))),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _register_phase3_envelope(self, strategy_id: str, cap: CapitalDecision) -> Dict[str, Any]:
        sid = str(strategy_id or "")
        if not sid:
            return {}
        envelope = self._extract_phase3_envelope(cap)
        if not envelope:
            return {}
        self._phase3_live_envelopes[sid] = envelope
        self._persist_phase3_live_state()
        return envelope

    def _current_strategy_notional(self, strategy_id: str) -> float:
        sid = str(strategy_id or "")
        if not sid:
            return 0.0
        snap = self._snapshot_dict()
        holdings = dict(snap.get("holdings", {}) or {})
        total = 0.0
        for payload in holdings.values():
            if str(dict(payload or {}).get("strategy_id", "") or "") != sid:
                continue
            total += abs(self._safe_float(dict(payload or {}).get("notional", 0.0), 0.0))
        return float(total)

    def _strategy_realized_returns(self, strategy_id: str, max_points: int = 256) -> List[float]:
        sid = str(strategy_id or "")
        if not sid:
            return []
        rows = self.store.list_events(since_event_id=0)
        out: List[float] = []
        for row in rows:
            if str(row.get("strategy_id", "") or "") != sid:
                continue
            if str(row.get("event_type", "") or "") not in {"ORDER_PARTIAL", "ORDER_FILLED", "POSITION_ADJUSTED"}:
                continue
            payload = self._payload_from_row(row)
            realized = self._safe_float(payload.get("realized_pnl", 0.0), 0.0)
            approved = self._safe_float(payload.get("approved_budget_notional", 0.0), 0.0)
            if approved <= 1e-9:
                fill_price = self._safe_float(payload.get("fill_price", payload.get("price", 0.0)), 0.0)
                fill_qty = self._safe_float(payload.get("filled_qty", payload.get("quantity", 0.0)), 0.0)
                approved = abs(fill_price * fill_qty)
            if approved > 1e-9:
                out.append(float(realized / approved))
            else:
                out.append(float(realized))
        if len(out) > int(max_points):
            out = out[-int(max_points):]
        return out

    def _evaluate_phase3_live_envelope(
        self,
        strategy_id: str,
        envelope: Dict[str, Any],
        *,
        current_notional: float,
    ) -> str:
        phase3_status = str(envelope.get("phase3_status", "provisional_pass") or "provisional_pass")
        if phase3_status in {"disabled", "provisional_pass"}:
            return ""
        cap_limit = self._safe_float(envelope.get("capacity_limit_estimate", 0.0), 0.0)
        if cap_limit > 0.0 and current_notional > (cap_limit * 1.001):
            return "risk.phase3_capacity_breach"

        history = self._strategy_realized_returns(strategy_id, max_points=256)
        min_history = max(5, int(self._safe_float(envelope.get("min_history", 20), 20)))
        if len(history) < min_history:
            return ""

        live_sharpe = self._series_sharpe(history)
        sharpe_floor = self._safe_float(envelope.get("mc_sharpe_p05", 0.0), 0.0)
        if live_sharpe < sharpe_floor:
            return "risk.phase3_live_sharpe_breach"

        stress_dd = self._safe_float(envelope.get("stress_max_dd", 0.0), 0.0)
        if stress_dd > 0.0:
            live_dd = abs(self._series_max_drawdown(history))
            if live_dd > (1.1 * stress_dd):
                return "risk.phase3_live_drawdown_breach"

        return ""

    def _run_phase3_live_monitor(self) -> None:
        if self._is_runtime_frozen():
            return
        if not self._phase3_live_envelopes:
            return
        for sid, envelope in list(self._phase3_live_envelopes.items()):
            reason = self._evaluate_phase3_live_envelope(
                sid,
                dict(envelope or {}),
                current_notional=self._current_strategy_notional(sid),
            )
            if not reason:
                continue
            self.set_global_freeze(True, reason=reason, updated_by="phase3_monitor")
            break

    @staticmethod
    def _proposal_with_requested_notional(proposal: TradeProposal, requested_notional: float) -> TradeProposal:
        return TradeProposal(
            proposal_id=proposal.proposal_id,
            origin=proposal.origin,
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            alpha_type=proposal.alpha_type,
            expected_edge=float(proposal.expected_edge),
            risk_score=float(proposal.risk_score),
            regime_context=dict(proposal.regime_context or {}),
            instrument_plan=dict(proposal.instrument_plan or {}),
            requested_notional=float(requested_notional),
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            decision_mode=proposal.decision_mode,
            trigger_reason_code=proposal.trigger_reason_code,
            risk_override_flag=bool(proposal.risk_override_flag),
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            created_at=proposal.created_at,
        )

    def _maybe_run_research_evolution(
        self,
        proposal: TradeProposal,
        *,
        risk_snapshot: Optional[Dict[str, Any]],
        market_snapshot: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if self.research_evolution is None:
            return dict(self._latest_evolution_cycle or {})
        scope = str(proposal.runtime_scope or "live")
        today_key = datetime.now(timezone.utc).date().isoformat()
        last_key = str(self._last_evolution_cycle_date_by_scope.get(scope, "") or "")
        if last_key == today_key:
            return dict(self._latest_evolution_cycle or {})
        try:
            cycle = self.research_evolution.run_cycle(
                proposal=proposal,
                portfolio_snapshot=self._snapshot_dict(),
                risk_snapshot=risk_snapshot,
                market_snapshot=market_snapshot,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
            )
            payload = cycle.to_dict()
            self._latest_evolution_cycle = payload
            self._last_evolution_cycle_date_by_scope[scope] = today_key
            self._persist_adaptive_state()
            return payload
        except Exception as exc:
            return {
                "error": f"research_evolution_failed:{exc}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

    def _adaptive_gate_adjustments(
        self,
        proposal: TradeProposal,
        *,
        close_only: bool,
        market_liquidity_snapshot: Optional[Dict[str, Any]],
    ) -> tuple[TradeProposal, Dict[str, Any]]:
        base = {
            "size_multiplier": 1.0,
            "slippage_buffer_bps": 0.0,
            "aggressiveness_multiplier": 1.0,
            "phase6_mortality_multiplier": 1.0,
            "phase6_mortality_state": MortalityState.ACTIVE.value,
            "applied": False,
        }
        if close_only or self.parameter_engine is None:
            return proposal, {"liquidity_snapshot": dict(market_liquidity_snapshot or {}), **base}

        params = dict(self.parameter_engine.current_parameters or {})
        size_multiplier = self._clamp(self._safe_float(params.get("size_multiplier", 1.0), 1.0), 0.50, 1.50)
        slip_buffer = max(0.0, self._safe_float(params.get("slippage_buffer_bps", 0.0), 0.0))
        aggressiveness = self._clamp(
            self._safe_float(params.get("aggressiveness_multiplier", 1.0), 1.0),
            0.50,
            1.50,
        )
        mortality_payload = dict(self._phase6_latest_decisions.get(str(proposal.strategy_id or ""), {}) or {})
        mortality_multiplier = self._clamp(
            self._safe_float(mortality_payload.get("capital_multiplier", 1.0), 1.0),
            0.0,
            1.25,
        )
        mortality_state = str(mortality_payload.get("state", MortalityState.ACTIVE.value) or MortalityState.ACTIVE.value)
        size_multiplier = self._clamp(size_multiplier * mortality_multiplier, 0.0, 1.50)

        adjusted_notional = max(0.0, float(proposal.requested_notional) * size_multiplier)
        proposal_for_gates = self._proposal_with_requested_notional(proposal, adjusted_notional)

        liq = dict(market_liquidity_snapshot or {})
        spread = max(0.0, self._safe_float(liq.get("spread_bps", 0.0), 0.0))
        est_slip = max(0.0, self._safe_float(liq.get("estimated_slippage_bps", spread), spread))
        aggressiveness_penalty = max(0.0, (1.0 / aggressiveness) - 1.0) * spread
        liq["spread_bps"] = float(spread + slip_buffer + aggressiveness_penalty)
        liq["estimated_slippage_bps"] = float(est_slip + slip_buffer)

        return proposal_for_gates, {
            "liquidity_snapshot": liq,
            "size_multiplier": size_multiplier,
            "slippage_buffer_bps": slip_buffer,
            "aggressiveness_multiplier": aggressiveness,
            "phase6_mortality_multiplier": float(mortality_multiplier),
            "phase6_mortality_state": str(mortality_state),
            "applied": True,
        }

    def _load_state_or_initialize(self) -> PortfolioState:
        latest = self.store.latest_snapshot()
        if latest and latest.get("state_json"):
            try:
                payload = json.loads(str(latest["state_json"]))
                return PortfolioState.from_snapshot(payload)
            except Exception:
                pass
        return PortfolioState.initialize(self._starting_cash)

    def _rehydrate_fsm(self) -> None:
        for row in self.store.list_events(since_event_id=0):
            pid = str(row.get("proposal_id", "") or "")
            etype = str(row.get("event_type", "") or "")
            if pid and etype:
                self.fsm.force_set(pid, etype)

    @staticmethod
    def _payload_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(str(row.get("payload_json", "{}") or "{}"))
        except Exception:
            return {}

    @staticmethod
    def _proposal_from_payload(payload: Dict[str, Any]) -> TradeProposal:
        return TradeProposal(
            proposal_id=str(payload.get("proposal_id", "") or ""),
            origin=ProposalOrigin(str(payload.get("origin", "manual") or "manual")),
            strategy_id=str(payload.get("strategy_id", "") or ""),
            signal_id=str(payload.get("signal_id", "") or ""),
            alpha_type=str(payload.get("alpha_type", "") or ""),
            expected_edge=float(payload.get("expected_edge", 0.0) or 0.0),
            risk_score=float(payload.get("risk_score", 0.0) or 0.0),
            regime_context=dict(payload.get("regime_context", {}) or {}),
            instrument_plan=dict(payload.get("instrument_plan", {}) or {}),
            requested_notional=float(payload.get("requested_notional", 0.0) or 0.0),
            certification_snapshot_hash=str(payload.get("certification_snapshot_hash", "") or ""),
            decision_mode=DecisionMode(str(payload.get("decision_mode", "auto") or "auto")),
            trigger_reason_code=str(payload.get("trigger_reason_code", "proposal.runtime.default") or "proposal.runtime.default"),
            risk_override_flag=bool(payload.get("risk_override_flag", False)),
            operator_id=str(payload.get("operator_id", "") or ""),
            runtime_scope=str(payload.get("runtime_scope", "live") or "live"),
        )

    def _to_event_obj(self, row: Dict[str, Any]) -> ExecutionEvent:
        return ExecutionEvent(
            event_type=ExecutionEventType(str(row.get("event_type"))),
            proposal_id=str(row.get("proposal_id", "") or ""),
            sequence_no=int(row.get("sequence_no", 0) or 0),
            timestamp_utc=datetime.fromisoformat(str(row.get("timestamp_utc"))),
            trigger_reason_code=str(row.get("trigger_reason_code", "") or ""),
            strategy_id=str(row.get("strategy_id", "") or ""),
            signal_id=str(row.get("signal_id", "") or ""),
            certification_snapshot_hash=str(row.get("certification_snapshot_hash", "") or ""),
            risk_override_flag=bool(int(row.get("risk_override_flag", 0) or 0)),
            decision_mode=DecisionMode(str(row.get("decision_mode", "auto") or "auto")),
            origin=ProposalOrigin(str(row.get("origin", "manual") or "manual")),
            allocator_decision_id=str(row.get("allocator_decision_id", "") or ""),
            budget_decision_id=str(row.get("budget_decision_id", "") or ""),
            liquidity_decision_id=str(row.get("liquidity_decision_id", "") or ""),
            operator_id=str(row.get("operator_id", "") or ""),
            runtime_scope=str(row.get("runtime_scope", "live") or "live"),
            payload=self._payload_from_row(row),
            parent_event_id=row.get("parent_event_id"),
        )

    def _append_event(self, event: ExecutionEvent, update_fsm: bool = True) -> int:
        if update_fsm:
            self.fsm.transition(event.proposal_id, event.event_type)
        event_id = self.store.append_event(event)
        self.state.apply(event, event_id)
        return event_id

    def _snapshot_dict(self) -> Dict[str, Any]:
        return self.state.to_snapshot().to_dict()

    def _persist_snapshot(self, source_event_id: int) -> PortfolioStateSnapshot:
        snap = self.state.to_snapshot()
        payload = snap.to_dict()
        payload["source_event_id"] = int(source_event_id)
        self.store.append_snapshot(source_event_id, payload, snap.state_hash)
        return snap

    def _materialize_all(self) -> None:
        snapshot = self.state.to_snapshot().to_dict()
        self.materializer.materialize_snapshot(snapshot)
        events = self.store.list_events(since_event_id=0)
        self.materializer.materialize_events(events)

    def register_certification_snapshot(self, snapshot: Any) -> str:
        self.store.insert_certification_snapshot(snapshot)
        return str(snapshot.snapshot_hash)

    def submit_proposal(self, proposal: TradeProposal) -> ProposalReceipt:
        self.store.upsert_proposal(proposal.proposal_id, proposal.to_dict(), status="submitted")

        event = ExecutionEvent(
            event_type=ExecutionEventType.INTENT_SUBMITTED,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code=proposal.trigger_reason_code,
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id="na",
            budget_decision_id="na",
            liquidity_decision_id="na",
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={"proposal": proposal.to_dict()},
        )
        event_id = self._append_event(event)
        return ProposalReceipt(proposal_id=proposal.proposal_id, submitted_event_id=event_id, status="submitted")

    def set_global_freeze(self, is_frozen: bool, reason: str, updated_by: str = "prs") -> None:
        self.global_freeze = bool(is_frozen)
        self.freeze_reason = str(reason or "")
        self.runtime_state = RuntimeState.FROZEN if is_frozen else RuntimeState.ACTIVE
        self.store.set_runtime_state(self.runtime_state.value, updated_by=updated_by)
        self.store.set_runtime_freeze_state(
            is_frozen=bool(is_frozen),
            reason=self.freeze_reason,
            updated_by=updated_by,
        )

    def _reject(
        self,
        proposal: TradeProposal,
        reason_code: str,
        *,
        capital_decision_id: str = "na",
        budget_decision_id: str = "na",
        liquidity_decision_id: str = "na",
    ) -> ExecutionResult:
        event = ExecutionEvent(
            event_type=ExecutionEventType.INTENT_REJECTED,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code=reason_code,
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id=capital_decision_id,
            budget_decision_id=budget_decision_id,
            liquidity_decision_id=liquidity_decision_id,
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={"denial_reason": reason_code},
        )
        eid = self._append_event(event)
        self.store.update_proposal_status(proposal.proposal_id, status="rejected", denial_reason=reason_code)
        self._materialize_all()
        return ExecutionResult(
            proposal_id=proposal.proposal_id,
            approved=False,
            status="rejected",
            denial_reason=reason_code,
            event_ids=[eid],
            capital_decision_id=capital_decision_id,
            budget_decision_id=budget_decision_id,
            liquidity_decision_id=liquidity_decision_id,
        )

    def _is_runtime_frozen(self) -> bool:
        return bool(self.global_freeze) or (self.runtime_state == RuntimeState.FROZEN)

    def _resolve_instrument_plan(
        self,
        proposal: TradeProposal,
        *,
        market_snapshot: Optional[Dict[str, Any]],
        risk_snapshot: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        enriched = self.greeks_adapter.enrich(
            proposal.instrument_plan,
            market_snapshot=market_snapshot,
            risk_snapshot=risk_snapshot,
            as_of=datetime.now(timezone.utc),
        )
        if self.strict_mode and (not enriched.has_required_greeks):
            is_option = str(proposal.instrument_plan.get("instrument_type", "equity") or "equity").strip().lower() in {
                "option",
                "options",
            }
            close_only = bool(proposal.instrument_plan.get("close_only", False))
            if is_option and (not close_only):
                raise ValueError("risk.options_missing_greeks")
        return dict(enriched.instrument_plan or proposal.instrument_plan)

    def _post_fill_budget_recheck(
        self,
        *,
        proposal: TradeProposal,
        cap: CapitalDecision,
        budget: BudgetDecision,
        liq: LiquidityDecision,
        fill_payload: Dict[str, Any],
        risk_snapshot: Optional[Dict[str, Any]],
        stress_results: List[StressScenarioResult],
    ) -> Optional[int]:
        if not bool(getattr(budget, "post_fill_guard_required", True)):
            return None
        fill_price = float(fill_payload.get("fill_price", 0.0) or 0.0)
        fill_qty = float(fill_payload.get("filled_qty", 0.0) or 0.0)
        actual_fill_notional = abs(fill_price * fill_qty)
        approved_budget_notional = float(budget.approved_notional or 0.0)

        post_risk_snapshot = dict(risk_snapshot or {})
        if stress_results:
            worst_pnl = min(float(s.pnl_impact) for s in stress_results)
            nav = max(1e-9, float(self._snapshot_dict().get("net_liquidation_value", 0.0) or 0.0))
            inferred_worst_loss_ratio = abs(min(0.0, worst_pnl)) / nav
            post_risk_snapshot["worst_case_loss_ratio"] = max(
                float(post_risk_snapshot.get("worst_case_loss_ratio", 0.0) or 0.0),
                float(inferred_worst_loss_ratio),
            )

        post_cap = CapitalDecision(
            decision_id=f"cap_post_{proposal.proposal_id}",
            is_approved=True,
            approved_notional=actual_fill_notional,
            reserve_pool=cap.reserve_pool,
            reserve_impact=cap.reserve_impact,
            sizing_rationale={
                "check": "post_fill",
                "actual_fill_notional": float(actual_fill_notional),
                "approved_budget_notional": float(approved_budget_notional),
            },
        )
        post_budget = self.risk_budget_manager.check(
            post_cap,
            proposal,
            portfolio_snapshot=self._snapshot_dict(),
            risk_snapshot=post_risk_snapshot,
        )

        drift_ratio = (
            (actual_fill_notional / approved_budget_notional)
            if approved_budget_notional > 0.0
            else 0.0
        )
        breach = (not post_budget.is_approved) or (
            approved_budget_notional > 0.0 and actual_fill_notional > (approved_budget_notional * 1.02)
        )
        if not breach:
            self._post_fill_breach_count = 0
            return None

        self._post_fill_breach_count += 1
        breach_event = ExecutionEvent(
            event_type=ExecutionEventType.RECONCILIATION_APPLIED,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code="risk.post_fill_budget_breach",
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id=cap.decision_id,
            budget_decision_id=post_budget.decision_id,
            liquidity_decision_id=liq.decision_id,
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={
                "cash_adjustment": 0.0,
                "realized_pnl_adjustment": 0.0,
                "post_fill_budget_breach": True,
                "approved_budget_notional": approved_budget_notional,
                "actual_fill_notional": actual_fill_notional,
                "drift_ratio": drift_ratio,
                "post_budget_denial_reason": str(post_budget.denial_reason or ""),
                "breach_count": int(self._post_fill_breach_count),
            },
        )
        breach_eid = self._append_event(breach_event)
        self._persist_snapshot(source_event_id=breach_eid)

        if self._post_fill_breach_count >= self._post_fill_breach_freeze_threshold:
            self.set_global_freeze(
                True,
                reason="risk.post_fill_budget_breach",
                updated_by="risk_budget_manager",
            )
        return breach_eid

    def _post_event_budget_recheck(
        self,
        event: ExecutionEvent,
        *,
        risk_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        if event.event_type not in {
            ExecutionEventType.ORDER_PARTIAL,
            ExecutionEventType.ORDER_FILLED,
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.POSITION_ADJUSTED,
        }:
            return None
        if str(event.trigger_reason_code or "") == "risk.post_fill_budget_breach":
            return None

        payload = dict(event.payload or {})
        fill_price = float(payload.get("fill_price", payload.get("price", 0.0)) or 0.0)
        fill_qty = float(payload.get("filled_qty", payload.get("quantity", 0.0)) or 0.0)
        actual_fill_notional = float(abs(payload.get("fill_notional", fill_price * fill_qty) or 0.0))
        if actual_fill_notional <= 0.0:
            return None

        approved_budget_notional = float(payload.get("approved_budget_notional", 0.0) or 0.0)
        if approved_budget_notional <= 0.0:
            latest_approval = self.store.latest_intent_approval(event.proposal_id)
            if latest_approval:
                approved_budget_notional = float(
                    dict(latest_approval.get("payload", {}) or {}).get("approved_notional", 0.0) or 0.0
                )
        if approved_budget_notional <= 0.0:
            return None

        proposal_payload = self.store.get_proposal(event.proposal_id)
        if not proposal_payload:
            return None
        proposal = self._proposal_from_payload(proposal_payload)

        post_cap = CapitalDecision(
            decision_id=f"cap_post_{proposal.proposal_id}",
            is_approved=True,
            approved_notional=actual_fill_notional,
            reserve_pool="post_event",
            reserve_impact={},
            sizing_rationale={
                "check": "post_event",
                "event_type": event.event_type.value,
                "actual_fill_notional": actual_fill_notional,
                "approved_budget_notional": approved_budget_notional,
            },
        )
        post_budget = self.risk_budget_manager.check(
            post_cap,
            proposal,
            portfolio_snapshot=self._snapshot_dict(),
            risk_snapshot=dict(risk_snapshot or {}),
        )

        drift_ratio = actual_fill_notional / approved_budget_notional if approved_budget_notional > 0.0 else 0.0
        breach = (not post_budget.is_approved) or (actual_fill_notional > (approved_budget_notional * 1.02))
        if not breach:
            self._post_fill_breach_count = 0
            return None

        self._post_fill_breach_count += 1
        breach_event = ExecutionEvent(
            event_type=ExecutionEventType.RECONCILIATION_APPLIED,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code="risk.post_fill_budget_breach",
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id=str(event.allocator_decision_id or "na"),
            budget_decision_id=post_budget.decision_id,
            liquidity_decision_id=str(event.liquidity_decision_id or "na"),
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={
                "cash_adjustment": 0.0,
                "realized_pnl_adjustment": 0.0,
                "post_fill_budget_breach": True,
                "approved_budget_notional": approved_budget_notional,
                "actual_fill_notional": actual_fill_notional,
                "drift_ratio": drift_ratio,
                "post_budget_denial_reason": str(post_budget.denial_reason or ""),
                "breach_count": int(self._post_fill_breach_count),
            },
        )
        breach_eid = self._append_event(breach_event)
        self._persist_snapshot(source_event_id=breach_eid)
        if self._post_fill_breach_count >= self._post_fill_breach_freeze_threshold:
            self.set_global_freeze(
                True,
                reason="risk.post_fill_budget_breach",
                updated_by="risk_budget_manager",
            )
        return breach_eid

    def ingest_execution_event(
        self,
        event: ExecutionEvent,
        *,
        risk_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        update_fsm = event.event_type != ExecutionEventType.MARK_TO_MARKET
        event_id = self._append_event(event, update_fsm=update_fsm)
        breach_eid = self._post_event_budget_recheck(event, risk_snapshot=risk_snapshot)
        if event.event_type in {
            ExecutionEventType.ORDER_PARTIAL,
            ExecutionEventType.ORDER_FILLED,
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.POSITION_ADJUSTED,
            ExecutionEventType.CORPORATE_ACTION_APPLIED,
            ExecutionEventType.MARK_TO_MARKET,
        }:
            self._persist_snapshot(source_event_id=int(event_id))
        self._run_phase3_live_monitor()
        self._run_phase6_mortality_monitor()
        self._materialize_all()
        event_ids = [int(event_id)]
        if breach_eid is not None:
            event_ids.append(int(breach_eid))
        return {
            "event_ids": event_ids,
            "runtime_state": self.runtime_state.value,
            "global_freeze": bool(self.global_freeze),
        }

    def mark_to_market(
        self,
        price_map: Dict[str, Any],
        *,
        timestamp_utc: Optional[datetime] = None,
        source: str = "market_data",
        runtime_scope: str = "live",
    ) -> Dict[str, Any]:
        event = ExecutionEvent(
            event_type=ExecutionEventType.MARK_TO_MARKET,
            proposal_id=f"mtm::{runtime_scope}",
            sequence_no=0,
            timestamp_utc=timestamp_utc or datetime.now(timezone.utc),
            trigger_reason_code="portfolio.mark_to_market",
            strategy_id="runtime_state",
            signal_id=f"mark_to_market::{source}",
            certification_snapshot_hash="na",
            risk_override_flag=False,
            decision_mode=DecisionMode.AUTO,
            origin=ProposalOrigin.ALPHA_OS,
            allocator_decision_id="na",
            budget_decision_id="na",
            liquidity_decision_id="na",
            operator_id="runtime",
            runtime_scope=str(runtime_scope or "live"),
            payload={"price_map": dict(price_map or {}), "source": str(source or "market_data")},
        )
        return self.ingest_execution_event(event, risk_snapshot=None)

    def process_proposal(
        self,
        proposal: TradeProposal,
        *,
        budget_snapshot: Optional[Dict[str, Any]] = None,
        risk_snapshot: Optional[Dict[str, Any]] = None,
        market_snapshot: Optional[Dict[str, Any]] = None,
        market_liquidity_snapshot: Optional[Dict[str, Any]] = None,
        certification_context: Optional[Dict[str, Any]] = None,
        auto_fill: bool = True,
    ) -> ExecutionResult:
        result_event_ids: List[int] = []
        self.submit_proposal(proposal)
        evolution_payload = self._maybe_run_research_evolution(
            proposal,
            risk_snapshot=risk_snapshot,
            market_snapshot=market_snapshot,
        )
        self._run_phase6_mortality_monitor()
        try:
            effective_plan = self._resolve_instrument_plan(
                proposal,
                market_snapshot=market_snapshot,
                risk_snapshot=risk_snapshot,
            )
        except ValueError as exc:
            return self._reject(proposal, str(exc))

        close_only = bool(effective_plan.get("close_only", False))
        proposal_for_gates, adaptive_meta = self._adaptive_gate_adjustments(
            proposal,
            close_only=close_only,
            market_liquidity_snapshot=market_liquidity_snapshot,
        )
        liquidity_snapshot_for_gate = dict(adaptive_meta.get("liquidity_snapshot", market_liquidity_snapshot or {}))
        phase6_state = str(adaptive_meta.get("phase6_mortality_state", MortalityState.ACTIVE.value) or MortalityState.ACTIVE.value)

        if self._is_runtime_frozen() and (not close_only):
            return self._reject(proposal, "risk.runtime_frozen_close_only")
        if (not close_only) and phase6_state == MortalityState.SHADOW.value:
            return self._reject(proposal, "risk.phase6_shadow_mode")
        if (not close_only) and phase6_state == MortalityState.FROZEN.value:
            return self._reject(proposal, "risk.phase6_alpha_frozen")
        if (not close_only) and phase6_state == MortalityState.RETIRED.value:
            return self._reject(proposal, "risk.phase6_retired")
        if not close_only:
            cert = self.cert_gate.validate(proposal_for_gates, current_context=certification_context)
            if not cert.is_valid:
                return self._reject(proposal, cert.reason)

            cap = self.capital_allocator.evaluate(
                proposal_for_gates,
                portfolio_snapshot=self._snapshot_dict(),
                budget_snapshot=budget_snapshot,
                risk_snapshot=risk_snapshot,
            )
            if not cap.is_approved:
                return self._reject(proposal, cap.denial_reason, capital_decision_id=cap.decision_id)
            envelope = self._register_phase3_envelope(proposal_for_gates.strategy_id, cap)
            self._register_phase6_profile(proposal_for_gates.strategy_id, cap)
            self._run_phase6_mortality_monitor()
            phase3_breach_reason = self._evaluate_phase3_live_envelope(
                proposal_for_gates.strategy_id,
                envelope,
                current_notional=float(cap.approved_notional),
            ) if envelope else ""
            if phase3_breach_reason:
                self.set_global_freeze(True, reason=phase3_breach_reason, updated_by="phase3_monitor")
                return self._reject(
                    proposal,
                    phase3_breach_reason,
                    capital_decision_id=cap.decision_id,
                )

            budget = self.risk_budget_manager.check(
                cap,
                proposal_for_gates,
                portfolio_snapshot=self._snapshot_dict(),
                risk_snapshot=risk_snapshot,
            )
            if not budget.is_approved:
                return self._reject(
                    proposal,
                    budget.denial_reason,
                    capital_decision_id=cap.decision_id,
                    budget_decision_id=budget.decision_id,
                )

            liq = self.liquidity_gate.check(
                {
                    "notional": budget.approved_notional,
                    "quantity": float(effective_plan.get("quantity", 0.0) or 0.0),
                },
                liquidity_snapshot_for_gate,
            )
            if not liq.is_approved:
                return self._reject(
                    proposal,
                    liq.denial_reason,
                    capital_decision_id=cap.decision_id,
                    budget_decision_id=budget.decision_id,
                    liquidity_decision_id=liq.decision_id,
                )
        else:
            cap = CapitalDecision("close_override", True, float(proposal.requested_notional), "close", {})
            budget = BudgetDecision("close_override", True, float(proposal.requested_notional), "")
            liq = LiquidityDecision("close_override", True, "")

        intent_approved = ExecutionEvent(
            event_type=ExecutionEventType.INTENT_APPROVED,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code=proposal.trigger_reason_code,
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id=cap.decision_id,
            budget_decision_id=budget.decision_id,
            liquidity_decision_id=liq.decision_id,
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={
                "approved_notional": float(budget.approved_notional),
                "reserve_impact": dict(cap.reserve_impact or {}),
                "sizing_rationale": dict(cap.sizing_rationale or {}),
                "cap_observations": dict(budget.cap_observations or {}),
                "liquidity_observations": dict(liq.observations or {}),
                "adaptive_overrides": dict(adaptive_meta or {}),
                "evolution_cycle": dict(evolution_payload or {}),
            },
        )
        result_event_ids.append(self._append_event(intent_approved))

        order_sent = ExecutionEvent(
            event_type=ExecutionEventType.ORDER_SENT,
            proposal_id=proposal.proposal_id,
            sequence_no=0,
            timestamp_utc=datetime.now(timezone.utc),
            trigger_reason_code=proposal.trigger_reason_code,
            strategy_id=proposal.strategy_id,
            signal_id=proposal.signal_id,
            certification_snapshot_hash=proposal.certification_snapshot_hash,
            risk_override_flag=bool(proposal.risk_override_flag),
            decision_mode=proposal.decision_mode,
            origin=proposal.origin,
            allocator_decision_id=cap.decision_id,
            budget_decision_id=budget.decision_id,
            liquidity_decision_id=liq.decision_id,
            operator_id=str(proposal.operator_id or ""),
            runtime_scope=str(proposal.runtime_scope or "live"),
            payload={
                "order": effective_plan,
                "notional": float(budget.approved_notional),
                "adaptive_overrides": dict(adaptive_meta or {}),
            },
        )
        result_event_ids.append(self._append_event(order_sent))

        stress_results: List[StressScenarioResult] = []

        if auto_fill:
            price = float(effective_plan.get("price", 0.0) or 0.0)
            qty = float(effective_plan.get("quantity", 0.0) or 0.0)
            if qty <= 0.0 and price > 0:
                qty = max(1.0, float(budget.approved_notional) / price)
            if price > 0.0 and qty > 0.0:
                max_qty_for_budget = float(budget.approved_notional) / price if budget.approved_notional > 0 else 0.0
                if max_qty_for_budget > 0.0:
                    qty = min(qty, max_qty_for_budget)
            filled_qty = float(effective_plan.get("filled_qty", qty) or qty)
            if price > 0.0 and budget.approved_notional > 0.0:
                max_fill_qty = float(budget.approved_notional) / price
                filled_qty = min(filled_qty, max_fill_qty)

            event_type = ExecutionEventType.ORDER_FILLED
            if 0.0 < filled_qty < qty:
                event_type = ExecutionEventType.ORDER_PARTIAL

            fill_payload = {
                "symbol": str(effective_plan.get("symbol", "") or ""),
                "side": str(effective_plan.get("side", "buy") or "buy"),
                "filled_qty": float(filled_qty),
                "fill_price": float(price if price > 0 else effective_plan.get("mark_price", 0.0) or 0.0),
                "sector": str(effective_plan.get("sector", "") or "").lower(),
                "strategy_id": proposal.strategy_id,
                "origin": proposal.origin.value,
                "position_key": str(effective_plan.get("position_key", "") or proposal.proposal_id),
                "lifecycle_action": str(effective_plan.get("lifecycle_action", "open") or "open"),
                "regime_context": proposal.regime_context,
                "hedging_state": dict(effective_plan.get("hedging_state", {}) or {}),
                "instrument_type": str(effective_plan.get("instrument_type", "equity") or "equity"),
                "greek_delta_per_unit": float(effective_plan.get("greek_delta_per_unit", 0.0) or 0.0),
                "greek_gamma_per_unit": float(effective_plan.get("greek_gamma_per_unit", 0.0) or 0.0),
                "greek_vega_per_unit": float(effective_plan.get("greek_vega_per_unit", 0.0) or 0.0),
                "greek_theta_per_unit": float(effective_plan.get("greek_theta_per_unit", 0.0) or 0.0),
                "greek_rho_per_unit": float(effective_plan.get("greek_rho_per_unit", 0.0) or 0.0),
                "realized_pnl": float(effective_plan.get("realized_pnl", 0.0) or 0.0),
                "max_adverse_excursion": float(effective_plan.get("max_adverse_excursion", 0.0) or 0.0),
                "max_favorable_excursion": float(effective_plan.get("max_favorable_excursion", 0.0) or 0.0),
                "approved_budget_notional": float(budget.approved_notional),
                "adaptive_size_multiplier": float(adaptive_meta.get("size_multiplier", 1.0) or 1.0),
            }
            fill_event = ExecutionEvent(
                event_type=event_type,
                proposal_id=proposal.proposal_id,
                sequence_no=0,
                timestamp_utc=datetime.now(timezone.utc),
                trigger_reason_code=proposal.trigger_reason_code,
                strategy_id=proposal.strategy_id,
                signal_id=proposal.signal_id,
                certification_snapshot_hash=proposal.certification_snapshot_hash,
                risk_override_flag=bool(proposal.risk_override_flag),
                decision_mode=proposal.decision_mode,
                origin=proposal.origin,
                allocator_decision_id=cap.decision_id,
                budget_decision_id=budget.decision_id,
                liquidity_decision_id=liq.decision_id,
                operator_id=str(proposal.operator_id or ""),
                runtime_scope=str(proposal.runtime_scope or "live"),
                payload=fill_payload,
            )
            fill_eid = self._append_event(fill_event)
            result_event_ids.append(fill_eid)
            snap = self._persist_snapshot(source_event_id=fill_eid)

            stress_results = self.shock_engine.compute_stress_matrix(snap.to_dict(), risk_snapshot or {})
            self.store.append_stress_matrix(fill_eid, [asdict(s) for s in stress_results])

            breach_eid = self._post_fill_budget_recheck(
                proposal=proposal_for_gates,
                cap=cap,
                budget=budget,
                liq=liq,
                fill_payload=fill_payload,
                risk_snapshot=risk_snapshot,
                stress_results=stress_results,
            )
            if breach_eid is not None:
                result_event_ids.append(int(breach_eid))

        self.store.update_proposal_status(proposal.proposal_id, status="executed", denial_reason="")

        rebalance_triggers = self.rebalance_engine.evaluate(
            self._snapshot_dict(),
            market_snapshot or {},
            risk_snapshot or {},
        )
        self._materialize_all()

        return ExecutionResult(
            proposal_id=proposal.proposal_id,
            approved=True,
            status="executed",
            denial_reason="",
            event_ids=result_event_ids,
            capital_decision_id=cap.decision_id,
            budget_decision_id=budget.decision_id,
            liquidity_decision_id=liq.decision_id,
            stress_matrix=stress_results,
            rebalance_triggers=rebalance_triggers,
        )

    def get_portfolio_state(self) -> PortfolioStateSnapshot:
        return self.state.to_snapshot()

    def replay(self, from_event_id: int = 0, to_event_id: Optional[int] = None) -> Dict[str, Any]:
        latest = self.store.latest_snapshot()
        latest_hash = ""
        latest_cash = None
        compare_event_id = to_event_id
        if latest is not None:
            try:
                latest_payload = json.loads(str(latest.get("state_json", "{}") or "{}"))
                latest_hash = compute_state_hash(latest_payload)
                latest_cash = float(latest_payload.get("cash", 0.0) or 0.0)
                if compare_event_id is None:
                    compare_event_id = int(latest.get("event_id", 0) or 0) or None
            except Exception:
                latest_hash = ""
                latest_cash = None

        events = self.store.list_events(since_event_id=from_event_id, to_event_id=compare_event_id)

        inferred_starting_cash = float(self._starting_cash)
        if int(from_event_id or 0) <= 0 and latest_cash is not None and events:
            zero_base_state = PortfolioState.initialize(0.0)
            for row in events:
                event_id = int(row.get("event_id", 0) or 0)
                ev = self._to_event_obj(row)
                zero_base_state.apply(ev, event_id)
            inferred_starting_cash = float(latest_cash - zero_base_state.cash)

        replay_state = PortfolioState.initialize(inferred_starting_cash)

        applied = 0
        for row in events:
            event_id = int(row.get("event_id", 0) or 0)
            ev = self._to_event_obj(row)
            replay_state.apply(ev, event_id)
            applied += 1

        replay_snapshot = replay_state.to_snapshot().to_dict()

        return {
            "applied_events": int(applied),
            "replayed_to_event_id": int(compare_event_id or 0),
            "inferred_starting_cash": float(inferred_starting_cash),
            "replay_state_hash": replay_snapshot.get("state_hash", ""),
            "latest_snapshot_hash": latest_hash,
            "deterministic_match": bool(replay_snapshot.get("state_hash", "") == latest_hash) if latest_hash else True,
        }

    def run_truth_drift_check(
        self,
        *,
        shadow_state: Optional[Dict[str, Any]],
        extra_derived_paths: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        derived_paths = [
            str(self.materializer.state_json_path),
            str(self.materializer.state_parquet_path),
            str(self.materializer.events_parquet_path),
        ]
        if extra_derived_paths:
            derived_paths.extend([str(p) for p in extra_derived_paths])

        incident = self.truth_drift_monitor.check(
            live_state=self.get_portfolio_state().to_dict(),
            shadow_state=shadow_state,
            derived_view_paths=derived_paths,
        )
        replay_result = self.replay(from_event_id=0, to_event_id=None)
        replay_mismatch = not bool(replay_result.get("deterministic_match", True))

        if incident is None and replay_mismatch:
            live = self.get_portfolio_state().to_dict()
            incident = {
                "incident_id": f"replay_drift_{uuid4().hex[:16]}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "live_state_hash": str(live.get("state_hash", "")),
                "shadow_state_hash": "",
                "derived_view_hash": "",
                "breach_count": 1,
                "escalated_freeze": True,
                "details": {
                    "replay_mismatch": True,
                    "replay_state_hash": replay_result.get("replay_state_hash", ""),
                    "latest_snapshot_hash": replay_result.get("latest_snapshot_hash", ""),
                    "applied_events": replay_result.get("applied_events", 0),
                },
            }
            self.store.append_truth_drift_incident(dict(incident))
            self.set_global_freeze(True, reason="runtime.truth_drift.replay_mismatch", updated_by="truth_drift_monitor")
            return dict(incident)

        if incident is None:
            return None
        payload = incident.to_dict()
        payload.setdefault("details", {})
        payload["details"]["replay_result"] = replay_result
        self.store.append_truth_drift_incident(payload)
        if bool(payload.get("escalated_freeze", False)):
            self.set_global_freeze(
                True,
                reason="runtime.truth_drift.escalated",
                updated_by="truth_drift_monitor",
            )
        return payload

    def weekly_open_fill_count(self, start_ts_utc_iso: str) -> int:
        return self.store.count_open_fills_since(start_ts_utc_iso)

    def latest_events(self) -> List[Dict[str, Any]]:
        return self.store.list_events(since_event_id=0)

    def close(self) -> None:
        if self._enable_research_evolution:
            try:
                self._persist_adaptive_state()
            except Exception:
                pass
        if self._enable_phase6_mortality:
            try:
                self._persist_phase6_mortality_state()
            except Exception:
                pass
        if self._ade_engine is not None:
            try:
                self._ade_engine.close()
            except Exception:
                pass
        if self.research_evolution is not None:
            try:
                phase7_engine = getattr(self.research_evolution, "phase7_engine", None)
                memory = getattr(phase7_engine, "memory", None)
                if memory is not None and hasattr(memory, "close"):
                    memory.close()
            except Exception:
                pass
        self.store.close()
