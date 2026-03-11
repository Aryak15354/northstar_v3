"""Phase 7 durability model: robust-score expectation by family/params/regime."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class DurabilityPrediction:
    expected_durability: float
    uncertainty: float
    family_base: float
    local_param_score: float
    regime_score: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "expected_durability": float(self.expected_durability),
            "uncertainty": float(self.uncertainty),
            "family_base": float(self.family_base),
            "local_param_score": float(self.local_param_score),
            "regime_score": float(self.regime_score),
        }


class DurabilityModel:
    """Lightweight nonparametric model for E[Y | family, theta, regime]."""

    def __init__(self, *, kernel_bandwidth: float = 1.0, min_samples: int = 5):
        self.kernel_bandwidth = float(max(1e-6, kernel_bandwidth))
        self.min_samples = int(max(1, min_samples))
        self.family_stats: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _numeric_dict(payload: Mapping[str, Any] | None) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in dict(payload or {}).items():
            try:
                fv = float(v)
            except Exception:
                continue
            if np.isfinite(fv):
                out[str(k)] = float(fv)
        return out

    @staticmethod
    def _vectorize(payload: Mapping[str, float], keys: Sequence[str]) -> np.ndarray:
        return np.asarray([float(payload.get(str(k), 0.0)) for k in keys], dtype=float)

    @staticmethod
    def _regime_key(payload: Mapping[str, Any] | None) -> str:
        p = dict(payload or {})
        if "regime" in p:
            return str(p.get("regime", "unknown") or "unknown")
        if "state" in p:
            return str(p.get("state", "unknown") or "unknown")
        if "state_id" in p:
            return f"state_{p.get('state_id')}"
        return "unknown"

    def fit(self, experiences: Iterable[Mapping[str, Any]]) -> None:
        by_family: Dict[str, List[Dict[str, Any]]] = {}
        for item in list(experiences or []):
            p = dict(item or {})
            family = str(p.get("family", "unknown") or "unknown")
            dur = float(max(0.0, min(1.0, p.get("durability_score", 0.0) or 0.0)))
            params = self._numeric_dict(p.get("parameter_vector", p.get("params", {})))
            regime = dict(p.get("regime_features", p.get("regime", {})) or {})
            by_family.setdefault(family, []).append(
                {
                    "durability": dur,
                    "params": params,
                    "regime": regime,
                }
            )

        stats: Dict[str, Dict[str, Any]] = {}
        for family, rows in by_family.items():
            if not rows:
                continue
            y = np.asarray([float(r["durability"]) for r in rows], dtype=float)
            mean = float(np.mean(y))
            std = float(np.std(y, ddof=1)) if y.size > 1 else 0.0

            key_union = set()
            for r in rows:
                key_union.update(dict(r.get("params", {})).keys())
            param_keys = sorted(str(k) for k in key_union)
            vectors = [self._vectorize(dict(r.get("params", {})), param_keys) for r in rows]

            regime_scores: Dict[str, List[float]] = {}
            for r in rows:
                rk = self._regime_key(r.get("regime", {}))
                regime_scores.setdefault(rk, []).append(float(r.get("durability", 0.0)))
            regime_mean = {k: float(sum(v) / len(v)) for k, v in regime_scores.items() if v}

            stats[family] = {
                "mean": mean,
                "std": float(max(0.01, std)),
                "n": int(len(rows)),
                "param_keys": param_keys,
                "param_vectors": vectors,
                "scores": [float(r["durability"]) for r in rows],
                "regime_mean": regime_mean,
            }
        self.family_stats = stats

    def family_expectations(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for family, st in dict(self.family_stats or {}).items():
            out[str(family)] = float(st.get("mean", 0.0) or 0.0)
        return out

    def predict(
        self,
        *,
        family: str,
        parameter_vector: Mapping[str, Any] | None,
        regime_features: Mapping[str, Any] | None,
    ) -> DurabilityPrediction:
        fam = str(family or "unknown")
        st = dict(self.family_stats.get(fam, {}) or {})
        if not st:
            return DurabilityPrediction(
                expected_durability=0.5,
                uncertainty=0.5,
                family_base=0.5,
                local_param_score=0.5,
                regime_score=0.5,
            )

        family_base = float(st.get("mean", 0.5) or 0.5)
        n = int(st.get("n", 0) or 0)
        uncertainty = float(1.0 / max(np.sqrt(max(1, n)), 1.0))

        param_keys = list(st.get("param_keys", []) or [])
        local_param = family_base
        if param_keys and n >= self.min_samples:
            x = self._vectorize(self._numeric_dict(parameter_vector), param_keys)
            hist_vectors = list(st.get("param_vectors", []) or [])
            scores = list(st.get("scores", []) or [])
            weighted = 0.0
            weight_sum = 0.0
            bw2 = max(self.kernel_bandwidth ** 2, 1e-8)
            for vec, score in zip(hist_vectors, scores):
                v = np.asarray(vec, dtype=float)
                dist2 = float(np.sum((x - v) ** 2))
                w = float(exp(-dist2 / (2.0 * bw2)))
                weighted += w * float(score)
                weight_sum += w
            if weight_sum > 1e-12:
                local_param = float(weighted / weight_sum)

        regime_key = self._regime_key(regime_features)
        regime_mean = dict(st.get("regime_mean", {}) or {})
        regime_score = float(regime_mean.get(regime_key, family_base))

        expected = (0.55 * family_base) + (0.30 * local_param) + (0.15 * regime_score)
        expected = float(max(0.0, min(1.0, expected)))

        return DurabilityPrediction(
            expected_durability=expected,
            uncertainty=uncertainty,
            family_base=float(family_base),
            local_param_score=float(local_param),
            regime_score=float(regime_score),
        )
