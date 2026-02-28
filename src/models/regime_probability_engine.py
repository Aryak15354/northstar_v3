"""
Regime probability engine with strict runtime/training separation.

Runtime:
- Loads frozen model from disk.
- Provides probability forecasts only.
- Explicitly blocks retraining.

Offline:
- `train_hmm_em` fits a Gaussian HMM using EM/Baum-Welch.
"""

from __future__ import annotations

import math
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


DEFAULT_STATES = ["LOW_VOL", "HIGH_VOL", "CRISIS", "TRANSITION"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float_array(x: Sequence[float]) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError("feature vector must be 1-D")
    return arr


def _regularize_covariance(cov: np.ndarray, min_diag: float = 1e-6) -> np.ndarray:
    """
    Return a finite, symmetric, positive-definite covariance proxy.
    """
    mat = np.asarray(cov, dtype=float)
    if mat.ndim != 2:
        return np.eye(1, dtype=float) * min_diag
    d0, d1 = mat.shape
    if d0 != d1:
        d = min(d0, d1)
        if d <= 0:
            return np.eye(1, dtype=float) * min_diag
        mat = mat[:d, :d]
    d = mat.shape[0]
    mat = np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)
    mat = 0.5 * (mat + mat.T)
    mat = mat + np.eye(d, dtype=float) * float(min_diag)
    try:
        eigvals, eigvecs = np.linalg.eigh(mat)
        eigvals = np.clip(eigvals, float(min_diag), None)
        mat = eigvecs @ np.diag(eigvals) @ eigvecs.T
        mat = 0.5 * (mat + mat.T)
    except Exception:
        mat = np.eye(d, dtype=float) * max(float(min_diag), 1e-4)
    return mat


@dataclass
class FrozenRegimeHMM:
    states: List[str]
    transition_matrix: np.ndarray
    emission_means: np.ndarray
    emission_covs: np.ndarray
    initial_probs: np.ndarray
    feature_names: List[str]
    model_version: str
    trained_at: str
    training_rows: int
    metadata: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "states": list(self.states),
            "transition_matrix": np.asarray(self.transition_matrix, dtype=float),
            "emission_means": np.asarray(self.emission_means, dtype=float),
            "emission_covs": np.asarray(self.emission_covs, dtype=float),
            "initial_probs": np.asarray(self.initial_probs, dtype=float),
            "feature_names": list(self.feature_names),
            "model_version": str(self.model_version),
            "trained_at": str(self.trained_at),
            "training_rows": int(self.training_rows),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "FrozenRegimeHMM":
        return cls(
            states=list(payload["states"]),
            transition_matrix=np.asarray(payload["transition_matrix"], dtype=float),
            emission_means=np.asarray(payload["emission_means"], dtype=float),
            emission_covs=np.asarray(payload["emission_covs"], dtype=float),
            initial_probs=np.asarray(payload["initial_probs"], dtype=float),
            feature_names=list(payload.get("feature_names", [])),
            model_version=str(payload.get("model_version", "unknown")),
            trained_at=str(payload.get("trained_at", "")),
            training_rows=int(payload.get("training_rows", 0)),
            metadata=dict(payload.get("metadata", {})),
        )


class RegimeProbabilityEngine:
    """
    Runtime engine that only consumes a frozen HMM.

    Daily retraining is explicitly prohibited in runtime code.
    """

    def __init__(
        self,
        model_path: str | Path = "data/models/regime_hmm_latest.pkl",
        states: Optional[Sequence[str]] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.states = list(states or DEFAULT_STATES)
        self._model: Optional[FrozenRegimeHMM] = None

    @property
    def model(self) -> Optional[FrozenRegimeHMM]:
        if self._model is not None:
            return self._model
        if not self.model_path.exists():
            return None
        try:
            with self.model_path.open("rb") as f:
                payload = pickle.load(f)
            model = FrozenRegimeHMM.from_payload(payload)
            self._model = model
            return model
        except Exception:
            return None

    def refresh_model(self) -> None:
        self._model = None

    def predict(
        self,
        feature_vector: Sequence[float],
        prev_probs: Optional[Sequence[float]] = None,
    ) -> Dict[str, Any]:
        model = self.model
        if model is None:
            probs = np.ones(len(self.states), dtype=float) / max(1, len(self.states))
            return {
                "timestamp": _now_iso(),
                "probabilities": {s: float(p) for s, p in zip(self.states, probs)},
                "confidence": 0.0,
                "source": "fallback_uniform",
                "model_path": str(self.model_path),
                "model_version": "unavailable",
                "stale": True,
                "reason_codes": ["missing_frozen_hmm_model"],
            }

        x = _as_float_array(feature_vector)
        k = len(model.states)
        if len(x) != model.emission_means.shape[1]:
            probs = np.ones(k, dtype=float) / k
            return {
                "timestamp": _now_iso(),
                "probabilities": {s: float(p) for s, p in zip(model.states, probs)},
                "confidence": 0.0,
                "source": "fallback_shape_mismatch",
                "model_path": str(self.model_path),
                "model_version": str(model.model_version),
                "stale": True,
                "reason_codes": ["feature_dimension_mismatch"],
            }

        prior = (
            np.asarray(prev_probs, dtype=float)
            if prev_probs is not None
            else np.asarray(model.initial_probs, dtype=float)
        )
        prior = np.clip(prior, 1e-12, None)
        prior = prior / prior.sum()
        predicted = prior @ model.transition_matrix
        predicted = np.clip(predicted, 1e-12, None)
        predicted = predicted / predicted.sum()

        log_likelihoods = np.array(
            [
                _gaussian_logpdf(
                    x,
                    model.emission_means[idx],
                    model.emission_covs[idx],
                )
                for idx in range(k)
            ],
            dtype=float,
        )
        log_likelihoods = np.nan_to_num(log_likelihoods, nan=-1e6, posinf=1e6, neginf=-1e6)
        max_log = float(np.max(log_likelihoods)) if log_likelihoods.size else -1e6
        if not np.isfinite(max_log):
            probs = np.ones(k, dtype=float) / k
            return {
                "timestamp": _now_iso(),
                "probabilities": {s: float(p) for s, p in zip(model.states, probs)},
                "confidence": 0.0,
                "source": "fallback_invalid_likelihood",
                "model_path": str(self.model_path),
                "model_version": str(model.model_version),
                "stale": True,
                "reason_codes": ["invalid_emission_likelihoods"],
            }
        emission = np.exp(log_likelihoods - max_log)
        posterior = predicted * emission
        posterior = np.nan_to_num(posterior, nan=0.0, posinf=0.0, neginf=0.0)
        if float(posterior.sum()) <= 1e-12:
            posterior = np.ones(k, dtype=float) / k
        else:
            posterior = np.clip(posterior, 1e-12, None)
            posterior = posterior / posterior.sum()
        confidence = float(_entropy_confidence(posterior))
        return {
            "timestamp": _now_iso(),
            "probabilities": {state: float(posterior[i]) for i, state in enumerate(model.states)},
            "confidence": confidence,
            "source": "frozen_hmm_runtime",
            "model_path": str(self.model_path),
            "model_version": str(model.model_version),
            "stale": False,
            "reason_codes": [],
        }

    def fit_em(self, *_: Any, **__: Any) -> None:
        raise RuntimeError(
            "Runtime retraining is prohibited. Use scripts/train_regime_hmm.py (monthly schedule)."
        )


def _gaussian_logpdf(x: np.ndarray, mean: np.ndarray, cov: np.ndarray) -> float:
    d = len(x)
    cov_reg = _regularize_covariance(np.asarray(cov, dtype=float), min_diag=1e-6)
    if cov_reg.shape != (d, d):
        cov_reg = np.eye(d, dtype=float) * 1e-3
    try:
        sign, logdet = np.linalg.slogdet(cov_reg)
        if (not np.isfinite(sign)) or (not np.isfinite(logdet)) or sign <= 0:
            cov_reg = _regularize_covariance(cov_reg, min_diag=1e-3)
            sign, logdet = np.linalg.slogdet(cov_reg)
        if (not np.isfinite(sign)) or (not np.isfinite(logdet)) or sign <= 0:
            return -1e6
        inv = np.linalg.inv(cov_reg)
        diff = x - mean
        quad = float(diff.T @ inv @ diff)
        if not np.isfinite(quad):
            return -1e6
        return float(-0.5 * (d * math.log(2 * math.pi) + logdet + quad))
    except Exception:
        return -1e6


def _entropy_confidence(probabilities: np.ndarray) -> float:
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-12, None)
    p = p / p.sum()
    entropy = -float(np.sum(p * np.log(p)))
    max_entropy = math.log(len(p)) if len(p) > 1 else 1.0
    return max(0.0, min(1.0, 1.0 - entropy / max_entropy))


def train_hmm_em(
    features: np.ndarray,
    states: Optional[Sequence[str]] = None,
    max_iter: int = 60,
    tol: float = 1e-4,
    smoothing: float = 0.02,
    random_state: int = 7,
    feature_names: Optional[Sequence[str]] = None,
) -> Tuple[FrozenRegimeHMM, Dict[str, Any]]:
    """
    Offline EM training for Gaussian HMM.
    """
    rng = np.random.default_rng(random_state)
    x = np.asarray(features, dtype=float)
    if x.ndim != 2 or x.shape[0] < 5:
        raise ValueError("features must be (T, D) with at least 5 rows")
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

    t, d = x.shape
    state_names = list(states or DEFAULT_STATES)
    k = len(state_names)
    if t < k + 1:
        raise ValueError("insufficient rows for number of states")

    init_idx = rng.choice(t, size=k, replace=False)
    means = np.asarray(x[init_idx], dtype=float)
    base_cov = np.cov(x.T) if t > 2 else np.eye(d, dtype=float)
    if base_cov.ndim != 2:
        base_cov = np.eye(d, dtype=float)
    base_cov = _regularize_covariance(base_cov, min_diag=1e-6)
    covs = np.array([base_cov.copy() for _ in range(k)], dtype=float)
    transition = np.full((k, k), 1.0 / k, dtype=float)
    for i in range(k):
        transition[i, i] = min(0.90, transition[i, i] + 0.25)
    transition = transition / transition.sum(axis=1, keepdims=True)
    initial = np.full(k, 1.0 / k, dtype=float)

    prev_ll = -np.inf
    log_likelihoods: List[float] = []
    converged = False
    n_iter = 0

    for n_iter in range(1, max_iter + 1):
        b = np.zeros((t, k), dtype=float)
        for j in range(k):
            ll = np.array([_gaussian_logpdf(row, means[j], covs[j]) for row in x], dtype=float)
            ll = np.nan_to_num(ll, nan=-1e6, posinf=1e6, neginf=-1e6)
            ll = ll - float(np.max(ll))
            b[:, j] = np.exp(ll)
        b = np.clip(b, 1e-12, None)

        alpha = np.zeros((t, k), dtype=float)
        scale = np.zeros(t, dtype=float)
        alpha[0] = initial * b[0]
        scale[0] = alpha[0].sum()
        alpha[0] /= max(scale[0], 1e-12)
        for step in range(1, t):
            alpha[step] = (alpha[step - 1] @ transition) * b[step]
            scale[step] = alpha[step].sum()
            alpha[step] /= max(scale[step], 1e-12)

        beta = np.zeros((t, k), dtype=float)
        beta[-1] = np.ones(k, dtype=float)
        for step in range(t - 2, -1, -1):
            beta[step] = transition @ (b[step + 1] * beta[step + 1])
            beta[step] /= max(beta[step].sum(), 1e-12)

        gamma = alpha * beta
        gamma /= np.clip(gamma.sum(axis=1, keepdims=True), 1e-12, None)

        xi = np.zeros((t - 1, k, k), dtype=float)
        for step in range(t - 1):
            numer = (
                alpha[step][:, None]
                * transition
                * (b[step + 1][None, :] * beta[step + 1][None, :])
            )
            denom = np.clip(numer.sum(), 1e-12, None)
            xi[step] = numer / denom

        initial = np.clip(gamma[0], 1e-12, None)
        initial /= initial.sum()

        trans_numer = xi.sum(axis=0) + smoothing
        trans_denom = gamma[:-1].sum(axis=0)[:, None] + smoothing * k
        transition = trans_numer / np.clip(trans_denom, 1e-12, None)
        transition = transition / np.clip(transition.sum(axis=1, keepdims=True), 1e-12, None)

        for j in range(k):
            weights = gamma[:, j]
            w_sum = float(np.sum(weights))
            if w_sum <= 1e-8:
                continue
            means[j] = np.sum(x * weights[:, None], axis=0) / w_sum
            diff = x - means[j]
            cov = (diff * weights[:, None]).T @ diff / w_sum
            covs[j] = _regularize_covariance(cov, min_diag=1e-6)

        ll_value = float(np.sum(np.log(np.clip(scale, 1e-12, None))))
        log_likelihoods.append(ll_value)
        if np.isfinite(prev_ll) and abs(ll_value - prev_ll) < tol:
            converged = True
            break
        prev_ll = ll_value

    model = FrozenRegimeHMM(
        states=state_names,
        transition_matrix=transition,
        emission_means=means,
        emission_covs=covs,
        initial_probs=initial,
        feature_names=list(feature_names or [f"f{i}" for i in range(d)]),
        model_version="v4-hmm-em-1",
        trained_at=_now_iso(),
        training_rows=int(t),
        metadata={
            "max_iter": int(max_iter),
            "tol": float(tol),
            "smoothing": float(smoothing),
            "converged": bool(converged),
            "iterations": int(n_iter),
            "final_log_likelihood": float(log_likelihoods[-1]) if log_likelihoods else None,
        },
    )
    diagnostics = {
        "converged": bool(converged),
        "iterations": int(n_iter),
        "training_rows": int(t),
        "feature_dim": int(d),
        "log_likelihood_path": log_likelihoods,
    }
    return model, diagnostics
