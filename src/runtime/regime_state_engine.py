"""Probabilistic multi-layer regime state engine with structural-break gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class RegimeStateOutput:
    timestamp_utc: str
    state_probabilities: Dict[str, float]
    dominant_state: str
    confidence: float
    entropy: float
    persistence_days: int
    transition_confirmed: bool
    structural_break: bool
    risk_multiplier: float
    macro_regime: Dict[str, Any] = field(default_factory=dict)
    vol_state: Dict[str, Any] = field(default_factory=dict)
    liquidity_state: Dict[str, Any] = field(default_factory=dict)
    cross_sectional_state: Dict[str, Any] = field(default_factory=dict)
    observation: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BayesianRegimeStateEngine:
    """
    Online Bayesian-style regime filtering.

    - Hidden state transitions are estimated with Dirichlet-smoothed counts.
    - Emissions are adaptive Gaussian (online EW updates).
    - Confidence uses posterior entropy.
    - Structural breaks use CUSUM over composite regime stress score.
    """

    DEFAULT_FEATURE_KEYS = (
        "trend_signal",
        "vol_percentile",
        "vol_of_vol",
        "liquidity_quality",
        "impact_risk",
        "crowding_signal",
        "breadth",
        "correlation",
    )

    def __init__(
        self,
        *,
        n_states: int = 3,
        feature_keys: Optional[List[str]] = None,
        min_multiplier: float = 0.70,
        confidence_threshold: float = 0.80,
        min_persistence_days: int = 5,
        cusum_k: float = 0.01,
        cusum_h: float = 0.12,
        emission_lr: float = 0.03,
    ):
        self.n_states = max(2, int(n_states))
        self.feature_keys = list(feature_keys or self.DEFAULT_FEATURE_KEYS)
        self.n_features = len(self.feature_keys)
        self.min_multiplier = float(np.clip(min_multiplier, 0.10, 1.0))
        self.confidence_threshold = float(np.clip(confidence_threshold, 0.1, 0.99))
        self.min_persistence_days = max(1, int(min_persistence_days))
        self.cusum_k = float(max(1e-6, cusum_k))
        self.cusum_h = float(max(1e-4, cusum_h))
        self.emission_lr = float(np.clip(emission_lr, 1e-4, 0.25))

        self.transition_counts = self._init_transition_counts(self.n_states)
        self.transition_matrix = self._normalize_rows(self.transition_counts)
        self.means, self.covs = self._init_emissions(self.n_states, self.n_features)
        self.posterior = np.ones(self.n_states, dtype=float) / float(self.n_states)
        self.prev_dominant_idx = int(np.argmax(self.posterior))
        self.persistence_days = 1
        self._last_persistence_date: Optional[date] = None
        self.state_risk = np.linspace(0.20, 1.0, self.n_states, dtype=float)

        self._cusum_pos = 0.0
        self._cusum_neg = 0.0
        self._score_ema = 0.5

    @staticmethod
    def _coerce_date(value: Optional[str]) -> date:
        if value:
            try:
                return datetime.fromisoformat(str(value)).date()
            except Exception:
                pass
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _day_gap(a: date, b: date) -> int:
        try:
            d = (b - a).days
        except Exception:
            return 1
        return max(1, int(d))

    @staticmethod
    def _normalize_rows(mat: np.ndarray) -> np.ndarray:
        out = np.asarray(mat, dtype=float).copy()
        rs = out.sum(axis=1, keepdims=True)
        rs = np.where(rs <= 1e-12, 1.0, rs)
        return out / rs

    @staticmethod
    def _init_transition_counts(n_states: int) -> np.ndarray:
        counts = np.ones((n_states, n_states), dtype=float)
        for i in range(n_states):
            counts[i, i] = 20.0
        return counts

    @staticmethod
    def _init_emissions(n_states: int, n_features: int) -> tuple[np.ndarray, np.ndarray]:
        means = np.zeros((n_states, n_features), dtype=float)
        # Encode a monotonic risk ladder from low -> high.
        for k in range(n_states):
            level = float(k) / float(max(1, n_states - 1))
            means[k, :] = np.asarray(
                [
                    1.0 - (2.0 * level),  # trend signal from +1 to -1
                    level,  # vol percentile
                    level,  # vol-of-vol
                    1.0 - level,  # liquidity quality
                    level,  # impact risk
                    level,  # crowding
                    1.0 - level,  # breadth
                    level,  # correlation stress
                ],
                dtype=float,
            )
        covs = np.stack([np.eye(n_features, dtype=float) * 0.08 for _ in range(n_states)], axis=0)
        return means, covs

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def _gaussian_likelihood(self, x: np.ndarray) -> np.ndarray:
        logp = np.zeros(self.n_states, dtype=float)
        for k in range(self.n_states):
            mu = self.means[k]
            cov = self.covs[k]
            cov = 0.5 * (cov + cov.T)
            cov = cov + (1e-8 * np.eye(self.n_features, dtype=float))
            try:
                inv = np.linalg.inv(cov)
                sign, logdet = np.linalg.slogdet(cov)
                if sign <= 0:
                    raise ValueError("non_pos_cov")
                d = x - mu
                logp[k] = -0.5 * (float(d.T @ inv @ d) + logdet + (self.n_features * np.log(2.0 * np.pi)))
            except Exception:
                logp[k] = -1e6
        m = float(np.max(logp))
        probs = np.exp(logp - m)
        s = float(np.sum(probs))
        if s <= 1e-12:
            return np.ones(self.n_states, dtype=float) / float(self.n_states)
        return probs / s

    def _update_emissions(self, x: np.ndarray, posterior: np.ndarray) -> None:
        for k in range(self.n_states):
            w = float(np.clip(self.emission_lr * posterior[k], 0.0, 0.25))
            if w <= 1e-8:
                continue
            mu_old = self.means[k]
            mu_new = ((1.0 - w) * mu_old) + (w * x)
            d = x - mu_new
            cov_old = self.covs[k]
            cov_new = ((1.0 - w) * cov_old) + (w * np.outer(d, d))
            cov_new = 0.5 * (cov_new + cov_new.T)
            cov_new = cov_new + (1e-8 * np.eye(self.n_features, dtype=float))
            self.means[k] = mu_new
            self.covs[k] = cov_new

    def _update_transition(self, new_dominant_idx: int) -> None:
        prev = int(self.prev_dominant_idx)
        cur = int(new_dominant_idx)
        self.transition_counts[prev, cur] += 1.0
        self.transition_matrix = self._normalize_rows(self.transition_counts)

    def _update_cusum(self, stress_score: float) -> bool:
        beta = 0.04
        self._score_ema = ((1.0 - beta) * self._score_ema) + (beta * float(stress_score))
        d = float(stress_score - self._score_ema)
        self._cusum_pos = max(0.0, self._cusum_pos + d - self.cusum_k)
        self._cusum_neg = min(0.0, self._cusum_neg + d + self.cusum_k)
        if self._cusum_pos > self.cusum_h or abs(self._cusum_neg) > self.cusum_h:
            self._cusum_pos = 0.0
            self._cusum_neg = 0.0
            return True
        return False

    def _build_layer_outputs(self, x: np.ndarray, expected_risk: float) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        trend = float(x[0])
        vol = float(np.clip(x[1], 0.0, 1.0))
        vol_of_vol = float(np.clip(x[2], 0.0, 1.0))
        liq_quality = float(np.clip(x[3], 0.0, 1.0))
        impact = float(np.clip(x[4], 0.0, 1.0))
        crowding = float(np.clip(x[5], 0.0, 1.0))
        breadth = float(np.clip(x[6], 0.0, 1.0))
        corr = float(np.clip(x[7], 0.0, 1.0))

        trend_label = "flat"
        if trend > 0.10:
            trend_label = "up"
        elif trend < -0.10:
            trend_label = "down"

        vol_state = "mid"
        if vol < 0.30:
            vol_state = "low"
        elif vol > 0.70:
            vol_state = "high"

        risk_state = "risk_on" if expected_risk < 0.55 else "risk_off"
        macro = {
            "trend": trend_label,
            "vol_state": vol_state,
            "risk_state": risk_state,
        }
        vol_layer = {
            "level": vol,
            "cluster_intensity": vol_of_vol,
            "shock_detected": bool((vol > 0.85) or (vol_of_vol > 0.80)),
        }
        liq_layer = {
            "liquidity_quality": liq_quality,
            "impact_risk": impact,
            "crowding_signal": crowding,
        }
        cross = {
            "breadth": breadth,
            "factor_correlation": corr,
            "dispersion_state": "narrow" if breadth < 0.35 else ("wide" if breadth > 0.65 else "normal"),
        }
        return macro, vol_layer, liq_layer, cross

    @classmethod
    def build_observation(
        cls,
        *,
        proposal: Optional[Any] = None,
        portfolio_snapshot: Optional[Dict[str, Any]] = None,
        risk_snapshot: Optional[Dict[str, Any]] = None,
        market_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        ps = dict(portfolio_snapshot or {})
        rs = dict(risk_snapshot or {})
        ms = dict(market_snapshot or {})
        regime_ctx = dict(ps.get("regime_context", {}) or {})
        inst = {}
        if proposal is not None:
            inst = dict(getattr(proposal, "instrument_plan", {}) or {})

        trend_signal = cls._safe_float(
            rs.get("trend_signal", ms.get("trend_signal", regime_ctx.get("trend_signal", 0.0))),
            0.0,
        )
        trend_signal = float(np.clip(trend_signal, -1.0, 1.0))
        vol_percentile = cls._safe_float(rs.get("vol_percentile", rs.get("vol_multiplier", 1.0) - 1.0), 0.5)
        vol_percentile = float(np.clip(vol_percentile, 0.0, 1.0))
        vol_of_vol = cls._safe_float(rs.get("vol_of_vol", ms.get("vol_of_vol", 0.5)), 0.5)
        vol_of_vol = float(np.clip(vol_of_vol, 0.0, 1.0))
        liquidity_quality = cls._safe_float(
            rs.get("liquidity_quality", ms.get("liquidity_quality", 0.5)),
            0.5,
        )
        liquidity_quality = float(np.clip(liquidity_quality, 0.0, 1.0))
        impact_risk = cls._safe_float(
            rs.get("impact_risk", ms.get("impact_risk", rs.get("estimated_slippage_bps", 5.0) / 50.0)),
            0.5,
        )
        impact_risk = float(np.clip(impact_risk, 0.0, 1.0))
        crowding_signal = cls._safe_float(rs.get("crowding_signal", ms.get("crowding_signal", 0.5)), 0.5)
        crowding_signal = float(np.clip(crowding_signal, 0.0, 1.0))
        breadth = cls._safe_float(rs.get("breadth", ms.get("breadth", 0.5)), 0.5)
        breadth = float(np.clip(breadth, 0.0, 1.0))
        correlation = cls._safe_float(rs.get("correlation", ms.get("correlation", 0.5)), 0.5)
        correlation = float(np.clip(correlation, 0.0, 1.0))

        if inst:
            # Slightly penalize sell-side impact state when liquidity is weak.
            side = str(inst.get("side", "buy") or "buy").strip().lower()
            if side == "sell":
                impact_risk = float(np.clip(impact_risk + 0.05, 0.0, 1.0))

        return {
            "trend_signal": trend_signal,
            "vol_percentile": vol_percentile,
            "vol_of_vol": vol_of_vol,
            "liquidity_quality": liquidity_quality,
            "impact_risk": impact_risk,
            "crowding_signal": crowding_signal,
            "breadth": breadth,
            "correlation": correlation,
        }

    def update(self, observation: Dict[str, float], *, timestamp_utc: Optional[str] = None) -> RegimeStateOutput:
        x = np.asarray(
            [self._safe_float(observation.get(k, 0.0), 0.0) for k in self.feature_keys],
            dtype=float,
        )
        x = x.reshape(self.n_features,)

        likelihood = self._gaussian_likelihood(x)
        prediction = self.transition_matrix.T @ self.posterior
        posterior = likelihood * prediction
        s = float(np.sum(posterior))
        if s <= 1e-12:
            posterior = np.ones(self.n_states, dtype=float) / float(self.n_states)
        else:
            posterior = posterior / s

        entropy = float(-np.sum(posterior * np.log(np.clip(posterior, 1e-12, 1.0))))
        confidence = float(np.clip(1.0 - (entropy / np.log(float(self.n_states))), 0.0, 1.0))
        dominant_idx = int(np.argmax(posterior))
        dominant_state = f"state_{dominant_idx}"

        ts = timestamp_utc or datetime.now(timezone.utc).isoformat()
        obs_date = self._coerce_date(ts)
        if dominant_idx != self.prev_dominant_idx:
            self.persistence_days = 1
            self._last_persistence_date = obs_date
        else:
            if self._last_persistence_date is None:
                self.persistence_days = max(1, int(self.persistence_days))
                self._last_persistence_date = obs_date
            elif obs_date > self._last_persistence_date:
                self.persistence_days += self._day_gap(self._last_persistence_date, obs_date)
                self._last_persistence_date = obs_date
        self._update_transition(dominant_idx)
        self.prev_dominant_idx = dominant_idx
        self._update_emissions(x, posterior)

        expected_risk = float(np.dot(posterior, self.state_risk))
        stress_score = float(np.clip((0.60 * x[1]) + (0.25 * x[4]) + (0.15 * x[7]), 0.0, 1.0))
        structural_break = self._update_cusum(stress_score)

        transition_confirmed = bool(
            (confidence >= self.confidence_threshold)
            and (self.persistence_days >= self.min_persistence_days)
        )
        risk_multiplier = float(np.clip(1.0 - (expected_risk * (1.0 - self.min_multiplier)), self.min_multiplier, 1.0))

        macro, vol_state, liq, cross = self._build_layer_outputs(x, expected_risk)
        out = RegimeStateOutput(
            timestamp_utc=ts,
            state_probabilities={f"state_{i}": float(posterior[i]) for i in range(self.n_states)},
            dominant_state=dominant_state,
            confidence=confidence,
            entropy=entropy,
            persistence_days=int(self.persistence_days),
            transition_confirmed=transition_confirmed,
            structural_break=bool(structural_break),
            risk_multiplier=risk_multiplier,
            macro_regime=macro,
            vol_state=vol_state,
            liquidity_state=liq,
            cross_sectional_state=cross,
            observation={k: float(observation.get(k, 0.0)) for k in self.feature_keys},
        )
        self.posterior = posterior
        return out

    def to_state_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "n_states": int(self.n_states),
            "feature_keys": list(self.feature_keys),
            "transition_counts": self.transition_counts.tolist(),
            "transition_matrix": self.transition_matrix.tolist(),
            "means": self.means.tolist(),
            "covs": self.covs.tolist(),
            "posterior": self.posterior.tolist(),
            "prev_dominant_idx": int(self.prev_dominant_idx),
            "persistence_days": int(self.persistence_days),
            "last_persistence_date": self._last_persistence_date.isoformat()
            if self._last_persistence_date
            else "",
            "state_risk": self.state_risk.tolist(),
            "cusum_pos": float(self._cusum_pos),
            "cusum_neg": float(self._cusum_neg),
            "score_ema": float(self._score_ema),
        }

    def load_state_dict(self, payload: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        try:
            if int(payload.get("n_states", self.n_states)) != self.n_states:
                return
            feature_keys = list(payload.get("feature_keys", self.feature_keys) or self.feature_keys)
            if len(feature_keys) != self.n_features:
                return
            self.transition_counts = np.asarray(
                payload.get("transition_counts", self.transition_counts),
                dtype=float,
            ).reshape(self.n_states, self.n_states)
            self.transition_matrix = self._normalize_rows(
                np.asarray(payload.get("transition_matrix", self.transition_matrix), dtype=float).reshape(
                    self.n_states,
                    self.n_states,
                )
            )
            self.means = np.asarray(payload.get("means", self.means), dtype=float).reshape(
                self.n_states,
                self.n_features,
            )
            self.covs = np.asarray(payload.get("covs", self.covs), dtype=float).reshape(
                self.n_states,
                self.n_features,
                self.n_features,
            )
            posterior = np.asarray(payload.get("posterior", self.posterior), dtype=float).reshape(self.n_states,)
            s = float(np.sum(posterior))
            if s <= 1e-12:
                posterior = np.ones(self.n_states, dtype=float) / float(self.n_states)
            else:
                posterior = posterior / s
            self.posterior = posterior
            self.prev_dominant_idx = int(payload.get("prev_dominant_idx", int(np.argmax(self.posterior))) or 0)
            self.persistence_days = max(1, int(payload.get("persistence_days", self.persistence_days) or 1))
            date_raw = str(payload.get("last_persistence_date", "") or "")
            self._last_persistence_date = None
            if date_raw:
                try:
                    self._last_persistence_date = date.fromisoformat(date_raw)
                except Exception:
                    self._last_persistence_date = None
            self.state_risk = np.asarray(payload.get("state_risk", self.state_risk), dtype=float).reshape(
                self.n_states,
            )
            self._cusum_pos = float(payload.get("cusum_pos", self._cusum_pos) or 0.0)
            self._cusum_neg = float(payload.get("cusum_neg", self._cusum_neg) or 0.0)
            self._score_ema = float(payload.get("score_ema", self._score_ema) or 0.5)
        except Exception:
            # Keep engine operational with existing in-memory defaults.
            return
