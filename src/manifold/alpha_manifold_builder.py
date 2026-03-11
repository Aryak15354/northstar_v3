"""Phase 8 alpha manifold builder and snapshot artifact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np

from .alpha_feature_encoder import AlphaFeatureEncoder
from .cluster_detector import ClusterDetector
from .diversity_monitor import DiversityMonitor
from .structural_distance_engine import StructuralDistanceEngine


@dataclass(frozen=True)
class AlphaManifoldSnapshot:
    alpha_ids: List[str]
    features: Dict[str, Dict[str, float]]
    distance_matrix: Dict[str, Dict[str, float]]
    cluster_map: Dict[str, str]
    redundancy_scores: Dict[str, float]
    local_density: Dict[str, float]
    complementarity_scores: Dict[str, float]
    diversity_score: float
    cluster_weight_distribution: Dict[str, float]
    overcrowding_flag: bool
    structural_fragility_index: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_ids": [str(x) for x in list(self.alpha_ids or [])],
            "features": {
                str(k): {str(f): float(v) for f, v in dict(m or {}).items()}
                for k, m in dict(self.features or {}).items()
            },
            "distance_matrix": {
                str(i): {str(j): float(v) for j, v in dict(row or {}).items()}
                for i, row in dict(self.distance_matrix or {}).items()
            },
            "cluster_map": {str(k): str(v) for k, v in dict(self.cluster_map or {}).items()},
            "redundancy_scores": {str(k): float(v) for k, v in dict(self.redundancy_scores or {}).items()},
            "local_density": {str(k): float(v) for k, v in dict(self.local_density or {}).items()},
            "complementarity_scores": {
                str(k): float(v) for k, v in dict(self.complementarity_scores or {}).items()
            },
            "diversity_score": float(self.diversity_score),
            "cluster_weight_distribution": {
                str(k): float(v) for k, v in dict(self.cluster_weight_distribution or {}).items()
            },
            "overcrowding_flag": bool(self.overcrowding_flag),
            "structural_fragility_index": float(self.structural_fragility_index),
        }


class AlphaManifoldBuilder:
    """Builds structural manifold snapshots from strategy diagnostics + returns."""

    def __init__(
        self,
        *,
        feature_encoder: AlphaFeatureEncoder | None = None,
        distance_engine: StructuralDistanceEngine | None = None,
        cluster_detector: ClusterDetector | None = None,
        diversity_monitor: DiversityMonitor | None = None,
    ):
        self.feature_encoder = feature_encoder or AlphaFeatureEncoder()
        self.distance_engine = distance_engine or StructuralDistanceEngine()
        self.cluster_detector = cluster_detector or ClusterDetector()
        self.diversity_monitor = diversity_monitor or DiversityMonitor()

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    @staticmethod
    def _return_correlation(
        alpha_ids: List[str],
        return_series_map: Mapping[str, List[float]] | None,
    ) -> Dict[str, Dict[str, float]]:
        ids = [str(x) for x in list(alpha_ids or [])]
        out: Dict[str, Dict[str, float]] = {sid: {} for sid in ids}
        series_map = dict(return_series_map or {})
        mats: Dict[str, np.ndarray] = {}
        for sid in ids:
            arr = np.asarray(list(series_map.get(sid, []) or []), dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size > 256:
                arr = arr[-256:]
            mats[sid] = arr
        for i, si in enumerate(ids):
            for j, sj in enumerate(ids):
                if i == j:
                    out[si][sj] = 1.0
                    continue
                ai = mats.get(si, np.asarray([], dtype=float))
                aj = mats.get(sj, np.asarray([], dtype=float))
                m = min(len(ai), len(aj))
                if m < 8:
                    out[si][sj] = 0.0
                    continue
                x = ai[-m:]
                y = aj[-m:]
                sx = float(np.std(x))
                sy = float(np.std(y))
                if sx <= 1e-10 or sy <= 1e-10:
                    out[si][sj] = 0.0
                    continue
                c = float(np.corrcoef(x, y)[0, 1])
                out[si][sj] = float(np.clip(c, -0.99, 0.99)) if np.isfinite(c) else 0.0
        return out

    def build(
        self,
        *,
        alpha_ids: List[str],
        expected_edges: Mapping[str, float],
        strategy_points: Mapping[str, Any] | None = None,
        return_series_map: Mapping[str, List[float]] | None = None,
        capacity_caps: Mapping[str, float] | None = None,
        factor_exposures: Mapping[str, Mapping[str, float]] | None = None,
        weights: Mapping[str, float] | None = None,
    ) -> AlphaManifoldSnapshot:
        ids = [str(x) for x in list(alpha_ids or [])]
        if not ids:
            return AlphaManifoldSnapshot(
                alpha_ids=[],
                features={},
                distance_matrix={},
                cluster_map={},
                redundancy_scores={},
                local_density={},
                complementarity_scores={},
                diversity_score=0.0,
                cluster_weight_distribution={},
                overcrowding_flag=False,
                structural_fragility_index=0.0,
            )

        rows = self.feature_encoder.encode(
            alpha_ids=ids,
            expected_edges=expected_edges,
            strategy_points=strategy_points,
            return_series_map=return_series_map,
            capacity_caps=capacity_caps,
            factor_exposures=factor_exposures,
        )
        dist = self.distance_engine.compute([r.to_dict() for r in rows])
        clusters = self.cluster_detector.detect(alpha_ids=dist.alpha_ids, distance_matrix=dist.distance_matrix)
        corr = self._return_correlation(ids, return_series_map)
        diversity = self.diversity_monitor.evaluate(
            alpha_ids=dist.alpha_ids,
            distance_matrix=dist.distance_matrix,
            cluster_map=clusters.cluster_map,
            weights=weights,
            return_corr=corr,
        )

        return AlphaManifoldSnapshot(
            alpha_ids=dist.alpha_ids,
            features={r.alpha_id: dict(r.features) for r in rows},
            distance_matrix=dict(dist.distance_matrix),
            cluster_map=dict(clusters.cluster_map),
            redundancy_scores=dict(diversity.redundancy_scores),
            local_density=dict(diversity.local_density),
            complementarity_scores=dict(diversity.complementarity_scores),
            diversity_score=float(diversity.diversity_score),
            cluster_weight_distribution=dict(diversity.cluster_weight_distribution),
            overcrowding_flag=bool(diversity.overcrowding_flag),
            structural_fragility_index=float(diversity.structural_fragility_index),
        )
