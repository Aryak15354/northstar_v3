"""
Regime drift monitor for frozen HMM health surveillance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RegimeDriftConfig:
    history_limit: int = 600
    baseline_window: int = 80
    rolling_window: int = 30
    entropy_increase_threshold: float = 0.25
    transition_kl_threshold: float = 0.35
    emission_distance_threshold: float = 4.0
    min_points_for_alerts: int = 50


class RegimeDriftMonitor:
    def __init__(
        self,
        config: Optional[RegimeDriftConfig] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.config = config or RegimeDriftConfig()
        self.state_path = state_path
        self.log_likelihood: List[float] = []
        self.entropy: List[float] = []
        self.emission_distance: List[float] = []
        self.dominant_states: List[int] = []
        self.baseline: Dict[str, float] = {}
        self.last_payload: Dict[str, Any] = {}
        self._load_state()

    def update(
        self,
        *,
        feature_vector: Sequence[float],
        regime_probs: Mapping[str, float],
        model: Any = None,
        dominant_regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        x = np.asarray(feature_vector, dtype=float)
        probs_arr = np.asarray([float(v) for v in regime_probs.values()], dtype=float)
        probs_arr = np.clip(probs_arr, 1e-12, None)
        probs_arr = probs_arr / probs_arr.sum() if probs_arr.sum() > 0 else probs_arr

        entropy = float(-np.sum(probs_arr * np.log(probs_arr + 1e-12)))
        self.entropy.append(entropy)

        ll = float("nan")
        emission_distance = float("nan")
        state_idx = 0

        states = list(regime_probs.keys())
        if dominant_regime and dominant_regime in states:
            state_idx = states.index(dominant_regime)
        elif probs_arr.size > 0:
            state_idx = int(np.argmax(probs_arr))
        self.dominant_states.append(state_idx)

        if model is not None:
            try:
                ll = self._weighted_log_likelihood(x, probs_arr, model)
                emission_distance = self._closest_emission_distance(x, model)
            except Exception:
                ll = float("nan")
                emission_distance = float("nan")
        self.log_likelihood.append(ll)
        self.emission_distance.append(emission_distance)

        self._trim()
        if not self.baseline and len(self.entropy) >= int(self.config.baseline_window):
            self.baseline = self._compute_baseline()

        observed_transition = self._observed_transition_matrix(max_states=len(states))
        transition_kl = self._transition_kl(observed_transition, model)
        payload = self._build_payload(
            ll=ll,
            entropy=entropy,
            emission_distance=emission_distance,
            transition_kl=transition_kl,
        )
        self.last_payload = payload
        self._save_state()
        return payload

    def _compute_baseline(self) -> Dict[str, float]:
        b = max(1, int(self.config.baseline_window))
        ll_vec = np.asarray(self.log_likelihood[:b], dtype=float)
        ll_vec = ll_vec[np.isfinite(ll_vec)]
        ent_vec = np.asarray(self.entropy[:b], dtype=float)
        em_vec = np.asarray(self.emission_distance[:b], dtype=float)
        em_vec = em_vec[np.isfinite(em_vec)]
        return {
            "ll_mean": float(np.mean(ll_vec)) if ll_vec.size else 0.0,
            "ll_std": float(np.std(ll_vec)) if ll_vec.size else 1.0,
            "entropy_mean": float(np.mean(ent_vec)) if ent_vec.size else 0.0,
            "emission_mean": float(np.mean(em_vec)) if em_vec.size else 0.0,
        }

    def _build_payload(
        self,
        *,
        ll: float,
        entropy: float,
        emission_distance: float,
        transition_kl: float,
    ) -> Dict[str, Any]:
        w = max(1, int(self.config.rolling_window))
        ll_recent = np.asarray(self.log_likelihood[-w:], dtype=float)
        ll_recent = ll_recent[np.isfinite(ll_recent)]
        ll_roll = float(np.mean(ll_recent)) if ll_recent.size else float("nan")
        ent_roll = float(np.mean(np.asarray(self.entropy[-w:], dtype=float)))
        em_recent = np.asarray(self.emission_distance[-w:], dtype=float)
        em_recent = em_recent[np.isfinite(em_recent)]
        em_roll = float(np.mean(em_recent)) if em_recent.size else float("nan")

        flags = {
            "log_likelihood_decay": False,
            "entropy_rise": False,
            "transition_instability": False,
            "emission_shift": False,
        }
        if self.baseline and len(self.entropy) >= int(self.config.min_points_for_alerts):
            ll_std = max(1e-8, float(self.baseline.get("ll_std", 1.0)))
            ll_cut = float(self.baseline.get("ll_mean", 0.0)) - 2.0 * ll_std
            if np.isfinite(ll_roll):
                flags["log_likelihood_decay"] = bool(ll_roll < ll_cut)
            flags["entropy_rise"] = bool(
                ent_roll > float(self.baseline.get("entropy_mean", 0.0)) * (1.0 + float(self.config.entropy_increase_threshold))
            )
            flags["transition_instability"] = bool(transition_kl > float(self.config.transition_kl_threshold))
            if np.isfinite(em_roll):
                flags["emission_shift"] = bool(em_roll > float(self.config.emission_distance_threshold))

        n_flags = int(sum(1 for v in flags.values() if v))
        drift_detected = bool(n_flags >= 1)
        severity = "normal"
        if n_flags >= 3:
            severity = "high"
        elif n_flags == 2:
            severity = "elevated"
        elif n_flags == 1:
            severity = "watch"

        payload = {
            "timestamp": _utc_iso(),
            "drift_detected": drift_detected,
            "severity": severity,
            "flags": flags,
            "metrics": {
                "log_likelihood_latest": float(ll) if np.isfinite(ll) else None,
                "log_likelihood_roll": float(ll_roll) if np.isfinite(ll_roll) else None,
                "entropy_latest": float(entropy),
                "entropy_roll": float(ent_roll),
                "transition_kl": float(transition_kl),
                "emission_distance_latest": float(emission_distance) if np.isfinite(emission_distance) else None,
                "emission_distance_roll": float(em_roll) if np.isfinite(em_roll) else None,
            },
            "recommended_actions": {
                "gross_reduction_fraction": 0.20 if drift_detected else 0.0,
                "risk_aversion_multiplier": 1.20 if drift_detected else 1.0,
                "retrain_eligibility_flag": bool(drift_detected),
            },
            "baseline": dict(self.baseline),
        }
        return payload

    @staticmethod
    def _weighted_log_likelihood(x: np.ndarray, probs: np.ndarray, model: Any) -> float:
        means = np.asarray(getattr(model, "emission_means"), dtype=float)
        covs = np.asarray(getattr(model, "emission_covs"), dtype=float)
        if means.ndim != 2 or covs.ndim != 3:
            return float("nan")
        terms = []
        for i in range(min(len(probs), means.shape[0])):
            lp = _gaussian_logpdf(x, means[i], covs[i])
            terms.append(np.log(max(1e-12, float(probs[i]))) + lp)
        if not terms:
            return float("nan")
        m = max(terms)
        return float(m + np.log(np.sum(np.exp(np.asarray(terms) - m))))

    @staticmethod
    def _closest_emission_distance(x: np.ndarray, model: Any) -> float:
        means = np.asarray(getattr(model, "emission_means"), dtype=float)
        covs = np.asarray(getattr(model, "emission_covs"), dtype=float)
        if means.ndim != 2 or covs.ndim != 3:
            return float("nan")
        dists = []
        for i in range(means.shape[0]):
            cov = covs[i] + np.eye(covs[i].shape[0]) * 1e-6
            try:
                inv = np.linalg.inv(cov)
                diff = x - means[i]
                d = float(np.sqrt(max(0.0, diff.T @ inv @ diff)))
                dists.append(d)
            except Exception:
                continue
        return float(min(dists)) if dists else float("nan")

    def _observed_transition_matrix(self, max_states: int) -> np.ndarray:
        n = max(1, int(max_states))
        mat = np.full((n, n), 1e-6, dtype=float)
        seq = self.dominant_states[-max(3, int(self.config.rolling_window) * 2) :]
        for a, b in zip(seq[:-1], seq[1:]):
            if 0 <= int(a) < n and 0 <= int(b) < n:
                mat[int(a), int(b)] += 1.0
        mat = mat / np.clip(mat.sum(axis=1, keepdims=True), 1e-12, None)
        return mat

    @staticmethod
    def _transition_kl(observed: np.ndarray, model: Any) -> float:
        try:
            trained = np.asarray(getattr(model, "transition_matrix"), dtype=float)
            n = min(observed.shape[0], trained.shape[0])
            if n <= 0:
                return 0.0
            p = np.clip(observed[:n, :n], 1e-12, None)
            q = np.clip(trained[:n, :n], 1e-12, None)
            p = p / p.sum(axis=1, keepdims=True)
            q = q / q.sum(axis=1, keepdims=True)
            kl = np.sum(p * (np.log(p) - np.log(q)), axis=1)
            return float(np.mean(kl))
        except Exception:
            return 0.0

    def _trim(self) -> None:
        limit = max(50, int(self.config.history_limit))
        self.log_likelihood = self.log_likelihood[-limit:]
        self.entropy = self.entropy[-limit:]
        self.emission_distance = self.emission_distance[-limit:]
        self.dominant_states = self.dominant_states[-limit:]

    def _load_state(self) -> None:
        if self.state_path is None or not Path(self.state_path).exists():
            return
        try:
            payload = json.loads(Path(self.state_path).read_text())
            self.log_likelihood = [float(v) for v in payload.get("log_likelihood", [])]
            self.entropy = [float(v) for v in payload.get("entropy", [])]
            self.emission_distance = [float(v) for v in payload.get("emission_distance", [])]
            self.dominant_states = [int(v) for v in payload.get("dominant_states", [])]
            self.baseline = dict(payload.get("baseline", {}))
            self.last_payload = dict(payload.get("last_payload", {}))
            self._trim()
        except Exception:
            return

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        try:
            path = Path(self.state_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": _utc_iso(),
                "log_likelihood": self.log_likelihood,
                "entropy": self.entropy,
                "emission_distance": self.emission_distance,
                "dominant_states": self.dominant_states,
                "baseline": self.baseline,
                "last_payload": self.last_payload,
            }
            path.write_text(json.dumps(payload, indent=2))
        except Exception:
            return


def _gaussian_logpdf(x: np.ndarray, mean: np.ndarray, cov: np.ndarray) -> float:
    cov_reg = np.asarray(cov, dtype=float) + np.eye(len(x), dtype=float) * 1e-6
    try:
        sign, logdet = np.linalg.slogdet(cov_reg)
        if sign <= 0:
            cov_reg = cov_reg + np.eye(len(x), dtype=float) * 1e-3
            sign, logdet = np.linalg.slogdet(cov_reg)
        inv = np.linalg.inv(cov_reg)
        diff = x - mean
        quad = float(diff.T @ inv @ diff)
        return float(-0.5 * (len(x) * np.log(2.0 * np.pi) + logdet + quad))
    except Exception:
        return -1e6
