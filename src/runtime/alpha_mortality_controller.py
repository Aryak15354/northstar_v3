"""Phase 6 alpha mortality and regret intelligence controller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import exp, sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np

from .alpha_decay_estimator import AlphaDecayEstimator, AlphaDecayResult
from .alpha_regret_engine import AlphaRegretEngine, RegretComputation, RegretState
from .bayesian_edge_tracker import BayesianEdgeState, BayesianEdgeTracker
from .path_deformation_monitor import PathDeformationMonitor, PathDeformationResult
from .structural_drift_monitor import StructuralDriftMonitor, StructuralDriftResult


class MortalityState(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADING = "DEGRADING"
    SHADOW = "SHADOW"
    FROZEN = "FROZEN"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class AlphaMortalityProfile:
    strategy_id: str
    prior_mean: float
    prior_variance: float
    mc_sharpe_mean: float
    mc_sharpe_std: float
    mc_drawdown_mean: float
    mc_drawdown_std: float
    recovery_days_median: float
    recovery_sigma: float
    regime_sharpe_profile: Dict[str, float]
    regime_sigma: float
    baseline_vol_cluster_acf1: float
    baseline_skew: float
    baseline_convexity: float
    baseline_decay_lambda: float
    capacity_limit_estimate: float
    freeze_drawdown_limit: float
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": str(self.strategy_id),
            "prior_mean": float(self.prior_mean),
            "prior_variance": float(self.prior_variance),
            "mc_sharpe_mean": float(self.mc_sharpe_mean),
            "mc_sharpe_std": float(self.mc_sharpe_std),
            "mc_drawdown_mean": float(self.mc_drawdown_mean),
            "mc_drawdown_std": float(self.mc_drawdown_std),
            "recovery_days_median": float(self.recovery_days_median),
            "recovery_sigma": float(self.recovery_sigma),
            "regime_sharpe_profile": dict(self.regime_sharpe_profile or {}),
            "regime_sigma": float(self.regime_sigma),
            "baseline_vol_cluster_acf1": float(self.baseline_vol_cluster_acf1),
            "baseline_skew": float(self.baseline_skew),
            "baseline_convexity": float(self.baseline_convexity),
            "baseline_decay_lambda": float(self.baseline_decay_lambda),
            "capacity_limit_estimate": float(self.capacity_limit_estimate),
            "freeze_drawdown_limit": float(self.freeze_drawdown_limit),
            "updated_at": str(self.updated_at),
        }

    @staticmethod
    def from_dict(payload: Mapping[str, Any] | None, *, strategy_id: str) -> "AlphaMortalityProfile":
        p = dict(payload or {})
        return AlphaMortalityProfile(
            strategy_id=str(strategy_id),
            prior_mean=float(p.get("prior_mean", 0.0) or 0.0),
            prior_variance=float(max(1e-6, p.get("prior_variance", 0.10) or 0.10)),
            mc_sharpe_mean=float(p.get("mc_sharpe_mean", 0.0) or 0.0),
            mc_sharpe_std=float(max(1e-6, p.get("mc_sharpe_std", 0.25) or 0.25)),
            mc_drawdown_mean=float(max(0.0, p.get("mc_drawdown_mean", 0.10) or 0.10)),
            mc_drawdown_std=float(max(1e-6, p.get("mc_drawdown_std", 0.05) or 0.05)),
            recovery_days_median=float(max(1.0, p.get("recovery_days_median", 20.0) or 20.0)),
            recovery_sigma=float(max(1e-6, p.get("recovery_sigma", 0.25) or 0.25)),
            regime_sharpe_profile={str(k): float(v) for k, v in dict(p.get("regime_sharpe_profile", {}) or {}).items()},
            regime_sigma=float(max(1e-6, p.get("regime_sigma", 0.20) or 0.20)),
            baseline_vol_cluster_acf1=float(p.get("baseline_vol_cluster_acf1", 0.0) or 0.0),
            baseline_skew=float(p.get("baseline_skew", 0.0) or 0.0),
            baseline_convexity=float(p.get("baseline_convexity", 0.0) or 0.0),
            baseline_decay_lambda=float(max(1e-6, p.get("baseline_decay_lambda", 0.01) or 0.01)),
            capacity_limit_estimate=float(max(0.0, p.get("capacity_limit_estimate", 0.0) or 0.0)),
            freeze_drawdown_limit=float(max(0.0, p.get("freeze_drawdown_limit", 0.35) or 0.35)),
            updated_at=str(p.get("updated_at", datetime.now(timezone.utc).isoformat()) or datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class AlphaMortalityDecision:
    strategy_id: str
    state: str
    previous_state: str
    capital_multiplier: float
    regret_score: float
    smoothed_regret: float
    persistence_counter: int
    posterior_probability: float
    decay_lambda: float
    drift_z: float
    recovery_inflation: float
    live_drawdown: float
    freeze: bool
    freeze_reason: str
    shadow_mode: bool
    action: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": str(self.strategy_id),
            "state": str(self.state),
            "previous_state": str(self.previous_state),
            "capital_multiplier": float(self.capital_multiplier),
            "regret_score": float(self.regret_score),
            "smoothed_regret": float(self.smoothed_regret),
            "persistence_counter": int(self.persistence_counter),
            "posterior_probability": float(self.posterior_probability),
            "decay_lambda": float(self.decay_lambda),
            "drift_z": float(self.drift_z),
            "recovery_inflation": float(self.recovery_inflation),
            "live_drawdown": float(self.live_drawdown),
            "freeze": bool(self.freeze),
            "freeze_reason": str(self.freeze_reason),
            "shadow_mode": bool(self.shadow_mode),
            "action": str(self.action),
            "details": dict(self.details or {}),
        }


class AlphaMortalityController:
    """State machine controller for live alpha mortality management."""

    def __init__(
        self,
        *,
        regret_engine: AlphaRegretEngine | None = None,
        edge_tracker: BayesianEdgeTracker | None = None,
        drift_monitor: StructuralDriftMonitor | None = None,
        path_monitor: PathDeformationMonitor | None = None,
        decay_estimator: AlphaDecayEstimator | None = None,
        smoothing_gamma: float = 1.5,
        min_multiplier: float = 0.05,
        max_multiplier: float = 1.00,
        degrade_threshold: float = 0.30,
        shadow_threshold: float = 0.60,
        freeze_threshold: float = 0.80,
        persistence_degrade: int = 2,
        persistence_shadow: int = 3,
        persistence_freeze: int = 4,
        min_dwell_updates: int = 3,
        entropy_gate: float = 0.90,
        posterior_shadow_threshold: float = 0.65,
        posterior_freeze_threshold: float = 0.50,
        edge_window: int = 64,
    ):
        self.regret_engine = regret_engine or AlphaRegretEngine()
        self.edge_tracker = edge_tracker or BayesianEdgeTracker()
        self.drift_monitor = drift_monitor or StructuralDriftMonitor()
        self.path_monitor = path_monitor or PathDeformationMonitor()
        self.decay_estimator = decay_estimator or AlphaDecayEstimator()

        self.smoothing_gamma = float(max(1e-6, smoothing_gamma))
        self.min_multiplier = float(min(max(0.0, min_multiplier), 1.0))
        self.max_multiplier = float(min(max(self.min_multiplier, max_multiplier), 2.0))
        self.degrade_threshold = float(min(max(0.0, degrade_threshold), 1.0))
        self.shadow_threshold = float(min(max(self.degrade_threshold, shadow_threshold), 1.0))
        self.freeze_threshold = float(min(max(self.shadow_threshold, freeze_threshold), 1.0))

        self.persistence_degrade = int(max(1, persistence_degrade))
        self.persistence_shadow = int(max(self.persistence_degrade, persistence_shadow))
        self.persistence_freeze = int(max(self.persistence_shadow, persistence_freeze))
        self.min_dwell_updates = int(max(1, min_dwell_updates))
        self.entropy_gate = float(min(max(0.0, entropy_gate), 1.0))
        self.posterior_shadow_threshold = float(min(max(0.01, posterior_shadow_threshold), 0.99))
        self.posterior_freeze_threshold = float(min(max(0.01, posterior_freeze_threshold), self.posterior_shadow_threshold))
        self.edge_window = int(max(12, edge_window))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _series_max_drawdown(values: np.ndarray) -> float:
        if values.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + values)
        peaks = np.maximum.accumulate(eq)
        dd = (eq / np.maximum(peaks, 1e-12)) - 1.0
        return float(abs(np.min(dd)))

    @staticmethod
    def _load_state(payload: Mapping[str, Any] | None) -> Dict[str, Any]:
        p = dict(payload or {})
        state = str(p.get("state", MortalityState.ACTIVE.value) or MortalityState.ACTIVE.value)
        if state not in {s.value for s in MortalityState}:
            state = MortalityState.ACTIVE.value
        return {
            "state": state,
            "state_updates": int(p.get("state_updates", 0) or 0),
            "last_transition_update": int(p.get("last_transition_update", 0) or 0),
            "edge_state": dict(p.get("edge_state", {}) or {}),
            "regret_state": dict(p.get("regret_state", {}) or {}),
            "edge_history": [float(x) for x in list(p.get("edge_history", []) or [])],
            "last_decision": dict(p.get("last_decision", {}) or {}),
            "updated_at": str(p.get("updated_at", "") or ""),
        }

    @staticmethod
    def _state_to_dict(state: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(state or {})
        out["edge_history"] = [float(x) for x in list(out.get("edge_history", []) or [])]
        out["edge_state"] = dict(out.get("edge_state", {}) or {})
        out["regret_state"] = dict(out.get("regret_state", {}) or {})
        out["last_decision"] = dict(out.get("last_decision", {}) or {})
        out["updated_at"] = str(out.get("updated_at", AlphaMortalityController._now_iso()) or AlphaMortalityController._now_iso())
        return out

    def _multiplier(self, regret: float, *, state: str) -> float:
        if state in {MortalityState.FROZEN.value, MortalityState.RETIRED.value}:
            return 0.0
        raw = float(exp(-self.smoothing_gamma * max(0.0, regret)))
        raw = float(max(self.min_multiplier, min(self.max_multiplier, raw)))
        if state == MortalityState.SHADOW.value:
            return float(min(raw, 0.10))
        if state == MortalityState.DEGRADING.value:
            return float(min(raw, 0.60))
        return float(raw)

    def _next_state(
        self,
        *,
        prev_state: str,
        smoothed_regret: float,
        persistence: int,
        posterior_prob: float,
        entropy: float,
        live_drawdown: float,
        freeze_drawdown_limit: float,
        current_notional: float,
        capacity_limit: float,
        updates: int,
        last_transition_update: int,
    ) -> Tuple[str, str]:
        state = str(prev_state)
        reason = "hold"

        dwell_ok = bool((updates - last_transition_update) >= self.min_dwell_updates)
        entropy_high = bool(entropy >= self.entropy_gate)

        if capacity_limit > 0.0 and current_notional > (1.05 * capacity_limit):
            return MortalityState.FROZEN.value, "phase6.capacity_breach"
        if freeze_drawdown_limit > 0.0 and live_drawdown > freeze_drawdown_limit:
            return MortalityState.FROZEN.value, "phase6.drawdown_tail_breach"

        if (smoothed_regret >= self.freeze_threshold) and (persistence >= self.persistence_freeze) and (not entropy_high):
            return MortalityState.FROZEN.value, "phase6.critical_regret"
        if (posterior_prob < self.posterior_freeze_threshold) and (persistence >= self.persistence_freeze) and (not entropy_high):
            return MortalityState.FROZEN.value, "phase6.posterior_collapse"

        if state == MortalityState.FROZEN.value:
            return state, "phase6.frozen_hold"
        if state == MortalityState.RETIRED.value:
            return state, "phase6.retired_hold"

        if (smoothed_regret >= self.shadow_threshold and persistence >= self.persistence_shadow and dwell_ok and not entropy_high) or (
            posterior_prob < self.posterior_shadow_threshold and persistence >= self.persistence_shadow and dwell_ok
        ):
            return MortalityState.SHADOW.value, "phase6.shadow_demotion"

        if smoothed_regret >= self.degrade_threshold and persistence >= self.persistence_degrade and dwell_ok:
            return MortalityState.DEGRADING.value, "phase6.soft_degrade"

        if state in {MortalityState.DEGRADING.value, MortalityState.SHADOW.value}:
            if smoothed_regret < self.degrade_threshold and persistence == 0 and dwell_ok:
                return MortalityState.ACTIVE.value, "phase6.reactivate"

        return state, reason

    def update_strategy(
        self,
        *,
        strategy_id: str,
        profile: AlphaMortalityProfile,
        strategy_returns: Iterable[float],
        regime_probabilities: Mapping[str, float] | None,
        strategy_state_payload: Mapping[str, Any] | None,
        current_notional: float,
        portfolio_returns: Iterable[float] | None = None,
        market_returns: Iterable[float] | None = None,
    ) -> Tuple[AlphaMortalityDecision, Dict[str, Any]]:
        state = self._load_state(strategy_state_payload)

        sr = np.asarray(list(strategy_returns) if strategy_returns is not None else [], dtype=float)
        sr = sr[np.isfinite(sr)]
        if sr.size == 0:
            decision = AlphaMortalityDecision(
                strategy_id=strategy_id,
                state=str(state["state"]),
                previous_state=str(state["state"]),
                capital_multiplier=1.0,
                regret_score=0.0,
                smoothed_regret=float(RegretState.from_dict(state.get("regret_state", {})).smoothed_regret),
                persistence_counter=int(RegretState.from_dict(state.get("regret_state", {})).persistence_counter),
                posterior_probability=float(BayesianEdgeState.from_dict(state.get("edge_state", {})).positive_probability),
                decay_lambda=float(profile.baseline_decay_lambda),
                drift_z=0.0,
                recovery_inflation=1.0,
                live_drawdown=0.0,
                freeze=False,
                freeze_reason="",
                shadow_mode=bool(str(state["state"]) == MortalityState.SHADOW.value),
                action="hold",
                details={"reason": "no_returns"},
            )
            state["last_decision"] = decision.to_dict()
            state["updated_at"] = self._now_iso()
            return decision, self._state_to_dict(state)

        pr = None
        if portfolio_returns is not None:
            tmp = np.asarray(list(portfolio_returns), dtype=float)
            tmp = tmp[np.isfinite(tmp)]
            if tmp.size == sr.size:
                pr = tmp

        edge_state = BayesianEdgeState.from_dict(
            state.get("edge_state", {}),
            fallback_mean=float(profile.prior_mean),
            fallback_variance=float(profile.prior_variance),
        )
        if edge_state.updates == 0 and edge_state.posterior_variance <= 0.0:
            edge_state = self.edge_tracker.initial_state(
                prior_mean=float(profile.prior_mean),
                prior_variance=float(profile.prior_variance),
            )

        recent = sr[-min(self.edge_window, sr.size):]
        edge_state = self.edge_tracker.update(state=edge_state, observations=recent)

        edge_history = [float(x) for x in list(state.get("edge_history", []) or [])]
        edge_history.append(float(edge_state.posterior_mean))
        if len(edge_history) > int(self.edge_window * 4):
            edge_history = edge_history[-int(self.edge_window * 4):]

        drift: StructuralDriftResult = self.drift_monitor.compute(
            strategy_returns=sr,
            regime_probabilities=regime_probabilities,
            regime_sharpe_profile=profile.regime_sharpe_profile,
            regime_sigma=profile.regime_sigma,
            portfolio_returns=pr,
        )

        path: PathDeformationResult = self.path_monitor.compute(
            strategy_returns=sr,
            baseline_recovery_days=profile.recovery_days_median,
            baseline_vol_cluster_acf1=profile.baseline_vol_cluster_acf1,
            baseline_skew=profile.baseline_skew,
            baseline_convexity=profile.baseline_convexity,
            market_returns=market_returns,
        )

        decay: AlphaDecayResult = self.decay_estimator.estimate(
            edge_history=edge_history,
            baseline_lambda=profile.baseline_decay_lambda,
        )

        prior_sigma = float(max(1e-8, sqrt(max(profile.prior_variance, 1e-8))))
        posterior_drop_z = float((edge_state.posterior_mean - profile.prior_mean) / prior_sigma)

        regret_prev = RegretState.from_dict(state.get("regret_state", {}))
        live_dd = self._series_max_drawdown(sr)
        regret: RegretComputation
        regret, regret_state = self.regret_engine.compute(
            live_sharpe=float(drift.residual_sharpe),
            mc_sharpe_mean=float(profile.mc_sharpe_mean),
            mc_sharpe_std=float(profile.mc_sharpe_std),
            live_drawdown=float(live_dd),
            mc_drawdown_mean=float(profile.mc_drawdown_mean),
            mc_drawdown_std=float(profile.mc_drawdown_std),
            recovery_inflation=float(path.recovery_inflation),
            recovery_sigma=float(profile.recovery_sigma),
            drift_z=float(drift.drift_z),
            posterior_drop_z=float(posterior_drop_z),
            lambda_norm=float(decay.lambda_norm),
            prev_state=regret_prev,
        )

        prev_state = str(state["state"])
        updates = int(state.get("state_updates", 0) or 0) + 1
        last_transition_update = int(state.get("last_transition_update", 0) or 0)
        next_state, transition_reason = self._next_state(
            prev_state=prev_state,
            smoothed_regret=float(regret.smoothed_regret),
            persistence=int(regret.persistence_counter),
            posterior_prob=float(edge_state.positive_probability),
            entropy=float(drift.regime_entropy),
            live_drawdown=float(live_dd),
            freeze_drawdown_limit=float(profile.freeze_drawdown_limit),
            current_notional=float(max(0.0, current_notional)),
            capacity_limit=float(max(0.0, profile.capacity_limit_estimate)),
            updates=int(updates),
            last_transition_update=int(last_transition_update),
        )
        if next_state != prev_state:
            last_transition_update = int(updates)

        multiplier = self._multiplier(float(regret.smoothed_regret), state=next_state)
        freeze = bool(next_state == MortalityState.FROZEN.value)
        shadow_mode = bool(next_state == MortalityState.SHADOW.value)
        action = "hold"
        if freeze:
            action = "freeze"
        elif shadow_mode:
            action = "shadow"
        elif next_state == MortalityState.DEGRADING.value:
            action = "scale_down"
        elif (prev_state in {MortalityState.DEGRADING.value, MortalityState.SHADOW.value}) and (next_state == MortalityState.ACTIVE.value):
            action = "reactivate"

        details = {
            "regret": regret.to_dict(),
            "drift": drift.to_dict(),
            "path": path.to_dict(),
            "decay": decay.to_dict(),
            "transition_reason": str(transition_reason),
        }

        decision = AlphaMortalityDecision(
            strategy_id=str(strategy_id),
            state=str(next_state),
            previous_state=str(prev_state),
            capital_multiplier=float(multiplier),
            regret_score=float(regret.regret_score),
            smoothed_regret=float(regret.smoothed_regret),
            persistence_counter=int(regret.persistence_counter),
            posterior_probability=float(edge_state.positive_probability),
            decay_lambda=float(decay.decay_lambda),
            drift_z=float(drift.drift_z),
            recovery_inflation=float(path.recovery_inflation),
            live_drawdown=float(live_dd),
            freeze=bool(freeze),
            freeze_reason=str(transition_reason if freeze else ""),
            shadow_mode=bool(shadow_mode),
            action=str(action),
            details=details,
        )

        state.update(
            {
                "state": str(next_state),
                "state_updates": int(updates),
                "last_transition_update": int(last_transition_update),
                "edge_state": edge_state.to_dict(),
                "regret_state": regret_state.to_dict(),
                "edge_history": edge_history,
                "last_decision": decision.to_dict(),
                "updated_at": self._now_iso(),
            }
        )
        return decision, self._state_to_dict(state)

    def run_cycle(
        self,
        *,
        profiles: Mapping[str, Mapping[str, Any]],
        strategy_state: Mapping[str, Mapping[str, Any]] | None,
        strategy_returns_map: Mapping[str, Iterable[float]],
        regime_probabilities: Mapping[str, float] | None,
        current_notional_map: Mapping[str, float] | None,
        portfolio_returns: Iterable[float] | None = None,
        market_returns: Iterable[float] | None = None,
    ) -> Tuple[Dict[str, AlphaMortalityDecision], Dict[str, Dict[str, Any]]]:
        decisions: Dict[str, AlphaMortalityDecision] = {}
        next_state: Dict[str, Dict[str, Any]] = {}

        for sid, raw_profile in dict(profiles or {}).items():
            strategy_id = str(sid)
            profile = AlphaMortalityProfile.from_dict(raw_profile, strategy_id=strategy_id)
            returns = list(dict(strategy_returns_map or {}).get(strategy_id, []) or [])
            prior = dict(strategy_state or {}).get(strategy_id, {})
            current_notional = float(dict(current_notional_map or {}).get(strategy_id, 0.0) or 0.0)
            decision, updated = self.update_strategy(
                strategy_id=strategy_id,
                profile=profile,
                strategy_returns=returns,
                regime_probabilities=regime_probabilities,
                strategy_state_payload=prior,
                current_notional=current_notional,
                portfolio_returns=portfolio_returns,
                market_returns=market_returns,
            )
            decisions[strategy_id] = decision
            next_state[strategy_id] = dict(updated)

        return decisions, next_state
