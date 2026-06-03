"""Manifold-density estimator for cross-family exploration diversity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping

import numpy as np


@dataclass(frozen=True)
class DiversitySnapshot:
    family_density: Dict[str, float]
    global_density: float
    n_points: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_density": {str(k): float(v) for k, v in dict(self.family_density or {}).items()},
            "global_density": float(self.global_density),
            "n_points": int(self.n_points),
        }


class ManifoldDiversityEngine:
    def __init__(self, *, radius: float = 0.75):
        self.radius = float(max(1e-6, radius))

    @staticmethod
    def _feature_vector(payload: Mapping[str, Any]) -> np.ndarray:
        p = dict(payload or {})
        metrics = dict(p.get("metrics", {}) or {})
        vals = [
            float(metrics.get("wf_sharpe", metrics.get("test_sharpe", 0.0)) or 0.0),
            float(metrics.get("mc_survival", metrics.get("survival_probability", 0.0)) or 0.0),
            float(metrics.get("phase6_longevity", metrics.get("longevity", 0.0)) or 0.0),
            float(p.get("durability_score", 0.0) or 0.0),
            float(metrics.get("surface_fragility", metrics.get("fragility", 0.0)) or 0.0),
        ]
        return np.asarray(vals, dtype=float)

    def snapshot(self, experiences: Iterable[Mapping[str, Any]]) -> DiversitySnapshot:
        rows = [dict(x or {}) for x in list(experiences or [])]
        if not rows:
            return DiversitySnapshot(family_density={}, global_density=0.0, n_points=0)

        vectors = np.asarray([self._feature_vector(r) for r in rows], dtype=float)
        n = int(vectors.shape[0])
        if n <= 1:
            fam = str(rows[0].get("family", "unknown") or "unknown")
            return DiversitySnapshot(family_density={fam: 0.0}, global_density=0.0, n_points=n)

        density_scores = np.zeros(n, dtype=float)
        for i in range(n):
            d = np.linalg.norm(vectors - vectors[i], axis=1)
            neighbors = float(np.sum(d <= self.radius)) - 1.0
            density_scores[i] = max(0.0, neighbors / max(1.0, float(n - 1)))

        fam_buckets: Dict[str, List[float]] = {}
        for i, row in enumerate(rows):
            fam = str(row.get("family", "unknown") or "unknown")
            fam_buckets.setdefault(fam, []).append(float(density_scores[i]))

        fam_density = {
            fam: float(sum(vals) / max(1, len(vals)))
            for fam, vals in fam_buckets.items()
        }
        global_density = float(np.mean(density_scores))
        return DiversitySnapshot(
            family_density=fam_density,
            global_density=global_density,
            n_points=n,
        )
