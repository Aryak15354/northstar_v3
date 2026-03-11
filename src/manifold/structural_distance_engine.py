"""Structural distance computation for alpha manifold embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class DistanceSnapshot:
    alpha_ids: List[str]
    distance_matrix: Dict[str, Dict[str, float]]
    covariance: List[List[float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_ids": [str(x) for x in list(self.alpha_ids or [])],
            "distance_matrix": {
                str(i): {str(j): float(v) for j, v in dict(row or {}).items()}
                for i, row in dict(self.distance_matrix or {}).items()
            },
            "covariance": [list(map(float, row)) for row in list(self.covariance or [])],
        }


class StructuralDistanceEngine:
    def __init__(self, *, ridge: float = 1e-4):
        self.ridge = float(max(1e-10, ridge))

    def compute(self, alpha_rows: List[Mapping[str, Any]]) -> DistanceSnapshot:
        rows = [dict(r or {}) for r in list(alpha_rows or [])]
        if not rows:
            return DistanceSnapshot(alpha_ids=[], distance_matrix={}, covariance=[])

        alpha_ids = [str(r.get("alpha_id", f"alpha_{i}")) for i, r in enumerate(rows)]
        feat_keys = sorted(set().union(*[set(dict(r.get("features", {}) or {}).keys()) for r in rows]))
        mat = np.asarray(
            [
                [float(dict(r.get("features", {}) or {}).get(k, 0.0)) for k in feat_keys]
                for r in rows
            ],
            dtype=float,
        )
        if mat.shape[0] <= 1:
            return DistanceSnapshot(
                alpha_ids=alpha_ids,
                distance_matrix={alpha_ids[0]: {alpha_ids[0]: 0.0}},
                covariance=[[1.0]],
            )

        cov = np.cov(mat, rowvar=False)
        if np.ndim(cov) == 0:
            cov = np.asarray([[float(cov)]], dtype=float)
        cov = np.asarray(cov, dtype=float)
        cov = 0.5 * (cov + cov.T)
        cov = cov + (self.ridge * np.eye(cov.shape[0]))
        try:
            inv_cov = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            inv_cov = np.linalg.pinv(cov)

        n = len(alpha_ids)
        dist = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(i + 1, n):
                d = mat[i] - mat[j]
                md = float(np.sqrt(max(0.0, d @ inv_cov @ d)))
                dist[i, j] = md
                dist[j, i] = md

        out: Dict[str, Dict[str, float]] = {}
        for i, sid in enumerate(alpha_ids):
            out[sid] = {alpha_ids[j]: float(dist[i, j]) for j in range(n)}

        return DistanceSnapshot(
            alpha_ids=alpha_ids,
            distance_matrix=out,
            covariance=cov.tolist(),
        )
