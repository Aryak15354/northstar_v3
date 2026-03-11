"""Conditional parameter surfaces with conservative drift controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass(frozen=True)
class ParameterUpdateResult:
    parameters: Dict[str, float]
    target_parameters: Dict[str, float]
    mutated: bool
    reason: str
    drift_norm: float
    applied_step_norm: float
    adaptation_enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConditionalParameterEngine:
    """
    Smoothly adapts parameter values as a function of regime probabilities.

    theta_t = theta_0 + W * regime_probs
    with bounded drift and confidence/structure gates.
    """

    def __init__(
        self,
        base_parameters: Dict[str, float],
        *,
        n_states: int,
        max_step_norm: float = 0.10,
        min_regime_confidence: float = 0.80,
        min_regime_persistence_days: int = 5,
        require_structural_break: bool = True,
        parameter_bounds: Optional[Dict[str, tuple[float, float]]] = None,
    ):
        self.base_parameters = {str(k): float(v) for k, v in dict(base_parameters or {}).items()}
        self.n_states = max(1, int(n_states))
        self.max_step_norm = float(max(1e-6, max_step_norm))
        self.min_regime_confidence = float(np.clip(min_regime_confidence, 0.1, 0.99))
        self.min_regime_persistence_days = max(1, int(min_regime_persistence_days))
        self.require_structural_break = bool(require_structural_break)
        self.parameter_bounds = dict(parameter_bounds or {})

        self.parameter_surfaces: Dict[str, np.ndarray] = {
            k: np.zeros(self.n_states, dtype=float)
            for k in self.base_parameters.keys()
        }
        self.current_parameters: Dict[str, float] = dict(self.base_parameters)
        self.locked: bool = False
        self.lock_reason: str = ""

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def set_surface(self, parameter_name: str, state_weights: np.ndarray) -> None:
        pname = str(parameter_name)
        weights = np.asarray(state_weights, dtype=float).reshape(-1)
        if len(weights) != self.n_states:
            raise ValueError(f"parameter_surface_shape_mismatch expected={self.n_states} got={len(weights)}")
        if pname not in self.parameter_surfaces:
            self.base_parameters[pname] = 0.0
            self.current_parameters[pname] = 0.0
        self.parameter_surfaces[pname] = weights

    def lock(self, reason: str) -> None:
        self.locked = True
        self.lock_reason = str(reason or "locked")

    def unlock(self) -> None:
        self.locked = False
        self.lock_reason = ""

    def to_state_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "n_states": int(self.n_states),
            "base_parameters": dict(self.base_parameters),
            "current_parameters": dict(self.current_parameters),
            "parameter_surfaces": {
                k: np.asarray(v, dtype=float).tolist()
                for k, v in self.parameter_surfaces.items()
            },
            "locked": bool(self.locked),
            "lock_reason": str(self.lock_reason or ""),
        }

    def load_state_dict(self, payload: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        try:
            if int(payload.get("n_states", self.n_states)) != self.n_states:
                return
            base = dict(payload.get("base_parameters", {}) or {})
            if base:
                for k, v in base.items():
                    self.base_parameters[str(k)] = float(v)
                    self.current_parameters.setdefault(str(k), float(v))
            surf = dict(payload.get("parameter_surfaces", {}) or {})
            for pname, weights in surf.items():
                w = np.asarray(weights, dtype=float).reshape(-1)
                if len(w) != self.n_states:
                    continue
                self.parameter_surfaces[str(pname)] = w
                if str(pname) not in self.base_parameters:
                    self.base_parameters[str(pname)] = 0.0
                if str(pname) not in self.current_parameters:
                    self.current_parameters[str(pname)] = float(self.base_parameters[str(pname)])
            cur = dict(payload.get("current_parameters", {}) or {})
            for k, v in cur.items():
                if str(k) not in self.current_parameters:
                    self.current_parameters[str(k)] = float(v)
                else:
                    self.current_parameters[str(k)] = float(v)
            self.locked = bool(payload.get("locked", self.locked))
            self.lock_reason = str(payload.get("lock_reason", self.lock_reason) or "")
        except Exception:
            # Ignore invalid persisted state and keep defaults.
            return

    def _target_from_regime(self, regime_probs: Dict[str, float]) -> Dict[str, float]:
        probs = np.zeros(self.n_states, dtype=float)
        for i in range(self.n_states):
            probs[i] = self._safe_float(regime_probs.get(f"state_{i}", 0.0), 0.0)
        s = float(np.sum(probs))
        if s <= 1e-12:
            probs = np.ones(self.n_states, dtype=float) / float(self.n_states)
        else:
            probs = probs / s

        target: Dict[str, float] = {}
        for pname, base in self.base_parameters.items():
            w = self.parameter_surfaces.get(pname)
            if w is None:
                w = np.zeros(self.n_states, dtype=float)
            value = float(base + float(np.dot(w, probs)))
            lo_hi = self.parameter_bounds.get(pname)
            if lo_hi is not None:
                lo = float(lo_hi[0])
                hi = float(lo_hi[1])
                value = float(np.clip(value, min(lo, hi), max(lo, hi)))
            target[pname] = value
        return target

    def update(
        self,
        *,
        regime_state: Dict[str, Any],
        performance_degraded: bool,
        crisis_lock: bool = False,
    ) -> ParameterUpdateResult:
        confidence = self._safe_float(regime_state.get("confidence", 0.0), 0.0)
        persistence = int(regime_state.get("persistence_days", 0) or 0)
        structural_break = bool(regime_state.get("structural_break", False))
        regime_probs = dict(regime_state.get("state_probabilities", {}) or {})

        target = self._target_from_regime(regime_probs)
        cur_vec = np.asarray([self.current_parameters[k] for k in sorted(target.keys())], dtype=float)
        tgt_vec = np.asarray([target[k] for k in sorted(target.keys())], dtype=float)
        raw_delta = tgt_vec - cur_vec
        drift_norm = float(np.linalg.norm(raw_delta, ord=2))

        if self.locked:
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason=f"engine_locked:{self.lock_reason}",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )
        if crisis_lock:
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason="crisis_lock",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )
        if confidence < self.min_regime_confidence:
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason="regime_confidence_below_threshold",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )
        if persistence < self.min_regime_persistence_days:
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason="regime_persistence_below_threshold",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )
        if self.require_structural_break and (not structural_break):
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason="no_structural_break",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )
        if not bool(performance_degraded):
            return ParameterUpdateResult(
                parameters=dict(self.current_parameters),
                target_parameters=target,
                mutated=False,
                reason="performance_not_degraded",
                drift_norm=drift_norm,
                applied_step_norm=0.0,
                adaptation_enabled=False,
            )

        delta = raw_delta.copy()
        delta_norm = float(np.linalg.norm(delta, ord=2))
        if delta_norm > self.max_step_norm and delta_norm > 1e-12:
            scale = float(self.max_step_norm / delta_norm)
            delta = delta * scale
        applied_step_norm = float(np.linalg.norm(delta, ord=2))
        new_vec = cur_vec + delta

        updated: Dict[str, float] = {}
        for i, pname in enumerate(sorted(target.keys())):
            val = float(new_vec[i])
            lo_hi = self.parameter_bounds.get(pname)
            if lo_hi is not None:
                lo = float(lo_hi[0])
                hi = float(lo_hi[1])
                val = float(np.clip(val, min(lo, hi), max(lo, hi)))
            updated[pname] = val
        self.current_parameters.update(updated)

        return ParameterUpdateResult(
            parameters=dict(self.current_parameters),
            target_parameters=target,
            mutated=True,
            reason="updated",
            drift_norm=drift_norm,
            applied_step_norm=applied_step_norm,
            adaptation_enabled=True,
        )
