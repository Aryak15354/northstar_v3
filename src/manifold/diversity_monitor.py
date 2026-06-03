"""Diversity and redundancy metrics over alpha manifold distances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class DiversitySnapshot:
    redundancy_scores: Dict[str, float]
    local_density: Dict[str, float]
    complementarity_scores: Dict[str, float]
    diversity_score: float
    structural_fragility_index: float
    cluster_weight_distribution: Dict[str, float]
    overcrowding_flag: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "redundancy_scores": {str(k): float(v) for k, v in dict(self.redundancy_scores or {}).items()},
            "local_density": {str(k): float(v) for k, v in dict(self.local_density or {}).items()},
            "complementarity_scores": {str(k): float(v) for k, v in dict(self.complementarity_scores or {}).items()},
            "diversity_score": float(self.diversity_score),
            "structural_fragility_index": float(self.structural_fragility_index),
            "cluster_weight_distribution": {
                str(k): float(v) for k, v in dict(self.cluster_weight_distribution or {}).items()
            },
            "overcrowding_flag": bool(self.overcrowding_flag),
        }


class DiversityMonitor:
    def __init__(self, *, kernel_sigma: float = 1.0, overcrowding_cluster_cap: float = 0.65):
        self.kernel_sigma = float(max(1e-6, kernel_sigma))
        self.overcrowding_cluster_cap = float(np.clip(overcrowding_cluster_cap, 0.10, 1.0))

    def evaluate(
        self,
        *,
        alpha_ids: List[str],
        distance_matrix: Mapping[str, Mapping[str, float]],
        cluster_map: Mapping[str, str],
        weights: Mapping[str, float] | None = None,
        return_corr: Mapping[str, Mapping[str, float]] | None = None,
    ) -> DiversitySnapshot:
        ids = [str(x) for x in list(alpha_ids or [])]
        n = len(ids)
        if n == 0:
            return DiversitySnapshot(
                redundancy_scores={},
                local_density={},
                complementarity_scores={},
                diversity_score=0.0,
                structural_fragility_index=0.0,
                cluster_weight_distribution={},
                overcrowding_flag=False,
            )

        dist = np.zeros((n, n), dtype=float)
        for i, si in enumerate(ids):
            row = dict(distance_matrix.get(si, {}) or {})
            for j, sj in enumerate(ids):
                dist[i, j] = float(max(0.0, row.get(sj, 0.0)))

        kernel = np.exp(-dist / max(self.kernel_sigma, 1e-6))
        np.fill_diagonal(kernel, 0.0)
        redundancy = np.sum(kernel, axis=1)
        density = redundancy / max(1.0, float(n - 1))

        if weights:
            w = np.asarray([float(max(0.0, weights.get(sid, 0.0))) for sid in ids], dtype=float)
            total_w = float(np.sum(w))
            if total_w > 0.0:
                w = w / total_w
            diversity_score = float(w @ dist @ w)
        else:
            mask = ~np.eye(n, dtype=bool)
            diversity_score = float(np.mean(dist[mask])) if np.any(mask) else 0.0

        cluster_weight_distribution: Dict[str, float] = {}
        for sid in ids:
            cl = str(cluster_map.get(sid, sid))
            cluster_weight_distribution[cl] = cluster_weight_distribution.get(cl, 0.0) + float(
                max(0.0, dict(weights or {}).get(sid, 1.0 / max(1, n)))
            )
        total_cluster = float(sum(cluster_weight_distribution.values()))
        if total_cluster > 0.0:
            for k in list(cluster_weight_distribution.keys()):
                cluster_weight_distribution[k] = float(cluster_weight_distribution[k] / total_cluster)

        max_cluster = float(max(cluster_weight_distribution.values())) if cluster_weight_distribution else 0.0
        fragility = float(max_cluster / max(1e-8, diversity_score + 1e-6)) if diversity_score > 0.0 else float("inf")
        overcrowding = bool(max_cluster >= self.overcrowding_cluster_cap)

        comp_scores: Dict[str, float] = {}
        corr_map = dict(return_corr or {})
        for i, sid in enumerate(ids):
            d_rank = float(np.mean(dist[i])) if n > 1 else 0.0
            if corr_map:
                crow = dict(corr_map.get(sid, {}) or {})
                corr_vals = [abs(float(crow.get(other, 0.0))) for other in ids if other != sid]
                corr_term = float(np.mean(corr_vals)) if corr_vals else 0.0
            else:
                corr_term = 0.0
            comp_scores[sid] = float(d_rank * (1.0 - np.clip(corr_term, 0.0, 1.0)))

        return DiversitySnapshot(
            redundancy_scores={ids[i]: float(redundancy[i]) for i in range(n)},
            local_density={ids[i]: float(density[i]) for i in range(n)},
            complementarity_scores=comp_scores,
            diversity_score=float(max(0.0, diversity_score)),
            structural_fragility_index=float(fragility),
            cluster_weight_distribution=cluster_weight_distribution,
            overcrowding_flag=overcrowding,
        )
