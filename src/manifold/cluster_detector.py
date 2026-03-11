"""Density-based clustering over structural distance matrices."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class ClusterSnapshot:
    cluster_map: Dict[str, str]
    n_clusters: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_map": {str(k): str(v) for k, v in dict(self.cluster_map or {}).items()},
            "n_clusters": int(self.n_clusters),
        }


class ClusterDetector:
    """A small DBSCAN-like clustering implementation using precomputed distance."""

    def __init__(self, *, eps: float = 1.25, min_pts: int = 2):
        self.eps = float(max(1e-6, eps))
        self.min_pts = int(max(1, min_pts))

    def detect(
        self,
        *,
        alpha_ids: List[str],
        distance_matrix: Mapping[str, Mapping[str, float]],
    ) -> ClusterSnapshot:
        ids = [str(x) for x in list(alpha_ids or [])]
        if not ids:
            return ClusterSnapshot(cluster_map={}, n_clusters=0)
        if len(ids) == 1:
            sid = ids[0]
            return ClusterSnapshot(cluster_map={sid: "cluster_0"}, n_clusters=1)

        n = len(ids)
        dist = np.zeros((n, n), dtype=float)
        for i, si in enumerate(ids):
            row = dict(distance_matrix.get(si, {}) or {})
            for j, sj in enumerate(ids):
                if i == j:
                    continue
                dist[i, j] = float(max(0.0, float(row.get(sj, row.get(si, 0.0)) or 0.0)))

        neighbors = [set(np.where(dist[i] <= self.eps)[0].tolist()) - {i} for i in range(n)]
        visited = np.zeros(n, dtype=bool)
        labels = np.full(n, -1, dtype=int)
        cluster_id = 0

        for i in range(n):
            if visited[i]:
                continue
            visited[i] = True
            if len(neighbors[i]) + 1 < self.min_pts:
                continue
            labels[i] = cluster_id
            queue = deque(neighbors[i])
            while queue:
                j = queue.popleft()
                if not visited[j]:
                    visited[j] = True
                    if len(neighbors[j]) + 1 >= self.min_pts:
                        for k in neighbors[j]:
                            if k not in queue:
                                queue.append(k)
                if labels[j] == -1:
                    labels[j] = cluster_id
            cluster_id += 1

        # Promote noise points to singleton clusters for allocator constraints.
        for i in range(n):
            if labels[i] < 0:
                labels[i] = cluster_id
                cluster_id += 1

        cluster_map = {ids[i]: f"cluster_{int(labels[i])}" for i in range(n)}
        return ClusterSnapshot(cluster_map=cluster_map, n_clusters=int(len(set(labels.tolist()))))
