"""Research evolution orchestrator: regime state + diagnostics + conditional params."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd

from .conditional_parameter_engine import ConditionalParameterEngine, ParameterUpdateResult
from .regime_state_engine import BayesianRegimeStateEngine, RegimeStateOutput


@dataclass(frozen=True)
class EvolutionCycleResult:
    timestamp_utc: str
    regime_state: Dict[str, Any]
    parameter_update: Dict[str, Any]
    diagnostics_summary: Dict[str, Any]
    performance_degraded: bool
    crisis_lock: bool
    advisory_actions: Dict[str, Any]
    phase7_policy: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchEvolutionEngine:
    """
    Bounded research-evolution loop.

    - Updates probabilistic regime state.
    - Reads ADE diagnostics (or injected diagnostics).
    - Gates parameter adaptation conservatively.
    - Emits advisory outputs only in this phase.
    """

    def __init__(
        self,
        *,
        regime_engine: BayesianRegimeStateEngine,
        parameter_engine: ConditionalParameterEngine,
        ade_engine: Optional[Any] = None,
        phase7_engine: Optional[Any] = None,
        lock_drawdown_threshold: float = 0.12,
        degrade_err_threshold: float = 0.60,
        degrade_decay_threshold: float = -0.02,
    ):
        self.regime_engine = regime_engine
        self.parameter_engine = parameter_engine
        self.ade_engine = ade_engine
        self.phase7_engine = phase7_engine
        self.lock_drawdown_threshold = float(max(0.01, lock_drawdown_threshold))
        self.degrade_err_threshold = float(degrade_err_threshold)
        self.degrade_decay_threshold = float(degrade_decay_threshold)

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if out != out:
            return float(default)
        return float(out)

    def _load_strategy_diagnostics(self) -> pd.DataFrame:
        if self.ade_engine is None:
            return pd.DataFrame()
        try:
            return self.ade_engine.compute_strategy_diagnostics()
        except Exception:
            return pd.DataFrame()

    def _performance_degraded(self, strategy_df: pd.DataFrame) -> tuple[bool, Dict[str, Any]]:
        if strategy_df is None or strategy_df.empty:
            return False, {"reason": "no_strategy_diagnostics"}
        avg_err = self._safe_float(pd.to_numeric(strategy_df.get("avg_err", pd.Series(dtype=float)), errors="coerce").mean(), 0.0)
        avg_decay = self._safe_float(pd.to_numeric(strategy_df.get("edge_decay", pd.Series(dtype=float)), errors="coerce").mean(), 0.0)
        avg_stability = self._safe_float(pd.to_numeric(strategy_df.get("stability_score", pd.Series(dtype=float)), errors="coerce").mean(), 0.0)
        degraded = bool((avg_err < self.degrade_err_threshold) or (avg_decay < self.degrade_decay_threshold))
        return degraded, {
            "avg_err": avg_err,
            "avg_edge_decay": avg_decay,
            "avg_stability": avg_stability,
        }

    def _build_phase7_experiments(
        self,
        *,
        strategy_df: pd.DataFrame,
        regime_state: RegimeStateOutput,
    ) -> list[Dict[str, Any]]:
        if strategy_df is None or strategy_df.empty:
            return []
        regime_features = {
            "regime": str(regime_state.dominant_state),
            "confidence": float(regime_state.confidence),
            "persistence_days": int(regime_state.persistence_days),
            "entropy": float(regime_state.entropy),
        }
        regime_features.update({f"state_{k}": float(v) for k, v in dict(regime_state.state_probabilities or {}).items()})
        params = dict(getattr(self.parameter_engine, "current_parameters", {}) or {})
        out: list[Dict[str, Any]] = []
        for row in strategy_df.to_dict(orient="records"):
            r = dict(row or {})
            sid = str(r.get("strategy_id", "unknown") or "unknown")
            wf_sharpe = self._safe_float(r.get("sharpe", 0.0), 0.0)
            survival = self._safe_float(r.get("certification_survival_ratio", 0.0), 0.0)
            fragility = self._safe_float(r.get("regime_sensitivity", 0.0), 0.0)
            longevity = 1.0 - min(1.0, abs(self._safe_float(r.get("edge_decay", 0.0), 0.0)))
            durability = (0.35 * min(1.0, max(0.0, wf_sharpe / 2.0))) + (0.35 * max(0.0, min(1.0, survival))) + (0.30 * max(0.0, min(1.0, longevity)))
            durability = durability / (1.0 + max(0.0, fragility))
            out.append(
                {
                    "experiment_id": f"runtime::{sid}::{regime_state.timestamp_utc}",
                    "family": sid.split(":")[0],
                    "parameter_vector": params,
                    "regime_features": regime_features,
                    "metrics": {
                        "wf_sharpe": wf_sharpe,
                        "mc_survival": survival,
                        "phase6_longevity": longevity,
                        "surface_fragility": fragility,
                        "avg_err": self._safe_float(r.get("avg_err", 0.0), 0.0),
                    },
                    "durability_score": float(max(0.0, min(1.0, durability))),
                    "timestamp_utc": str(regime_state.timestamp_utc),
                }
            )
        return out

    def run_cycle(
        self,
        *,
        proposal: Optional[Any] = None,
        portfolio_snapshot: Optional[Dict[str, Any]] = None,
        risk_snapshot: Optional[Dict[str, Any]] = None,
        market_snapshot: Optional[Dict[str, Any]] = None,
        strategy_diagnostics: Optional[pd.DataFrame] = None,
        timestamp_utc: Optional[str] = None,
    ) -> EvolutionCycleResult:
        ps = dict(portfolio_snapshot or {})
        rs = dict(risk_snapshot or {})

        obs = self.regime_engine.build_observation(
            proposal=proposal,
            portfolio_snapshot=ps,
            risk_snapshot=rs,
            market_snapshot=market_snapshot,
        )
        regime_state: RegimeStateOutput = self.regime_engine.update(
            obs,
            timestamp_utc=timestamp_utc or datetime.now(timezone.utc).isoformat(),
        )

        strategy_df = strategy_diagnostics if strategy_diagnostics is not None else self._load_strategy_diagnostics()
        degraded, diag_summary = self._performance_degraded(strategy_df)

        drawdown_ratio = self._safe_float(rs.get("drawdown_ratio", ps.get("drawdown_ratio", 0.0)), 0.0)
        shock_flag = bool(rs.get("shock_detected", False))
        crisis_lock = bool((drawdown_ratio >= self.lock_drawdown_threshold) or shock_flag)

        p_update: ParameterUpdateResult = self.parameter_engine.update(
            regime_state=regime_state.to_dict(),
            performance_degraded=degraded,
            crisis_lock=crisis_lock,
        )

        phase7_policy: Dict[str, Any] = {}
        if self.phase7_engine is not None:
            try:
                experiments = self._build_phase7_experiments(
                    strategy_df=strategy_df,
                    regime_state=regime_state,
                )
                safe_bounds = {"runtime": dict(getattr(self.parameter_engine, "parameter_bounds", {}) or {})}
                phase7_policy = dict(
                    self.phase7_engine.run_cycle(
                        experiments=experiments,
                        safe_parameter_bounds=safe_bounds,
                    )
                    or {}
                )
            except Exception as exc:
                phase7_policy = {
                    "status": "error",
                    "error": f"phase7_cycle_failed:{exc}",
                }

        advisory = {
            "action": "hold",
            "reason": p_update.reason,
            "parameter_mutation": bool(p_update.mutated),
        }
        if p_update.mutated:
            advisory["action"] = "apply_shadow_only"
            advisory["reason"] = "parameter_surface_update_ready"
        if crisis_lock:
            advisory["action"] = "freeze_parameter_mutation"
            advisory["reason"] = "crisis_lock"

        return EvolutionCycleResult(
            timestamp_utc=timestamp_utc or datetime.now(timezone.utc).isoformat(),
            regime_state=regime_state.to_dict(),
            parameter_update=p_update.to_dict(),
            diagnostics_summary=diag_summary,
            performance_degraded=bool(degraded),
            crisis_lock=bool(crisis_lock),
            advisory_actions=advisory,
            phase7_policy=phase7_policy,
        )
