"""Temporal drift tracker for manifold snapshots (Phase 8/6 bridge)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

import numpy as np


@dataclass(frozen=True)
class ManifoldDriftSnapshot:
    alpha_drift: Dict[str, float]
    mean_drift: float
    max_drift: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_drift": {str(k): float(v) for k, v in dict(self.alpha_drift or {}).items()},
            "mean_drift": float(self.mean_drift),
            "max_drift": float(self.max_drift),
        }


class ManifoldDriftTracker:
    def compute(
        self,
        *,
        previous_features: Mapping[str, Mapping[str, float]] | None,
        current_features: Mapping[str, Mapping[str, float]] | None,
    ) -> ManifoldDriftSnapshot:
        prev = dict(previous_features or {})
        curr = dict(current_features or {})
        if not prev or not curr:
            return ManifoldDriftSnapshot(alpha_drift={}, mean_drift=0.0, max_drift=0.0)

        drifts: Dict[str, float] = {}
        for sid, f_now in curr.items():
            if sid not in prev:
                continue
            f_prev = dict(prev.get(sid, {}) or {})
            keys = sorted(set(f_prev.keys()) | set(dict(f_now or {}).keys()))
            if not keys:
                continue
            a = np.asarray([float(f_prev.get(k, 0.0)) for k in keys], dtype=float)
            b = np.asarray([float(dict(f_now or {}).get(k, 0.0)) for k in keys], dtype=float)
            drifts[str(sid)] = float(np.linalg.norm(b - a))

        if not drifts:
            return ManifoldDriftSnapshot(alpha_drift={}, mean_drift=0.0, max_drift=0.0)
        vals = np.asarray(list(drifts.values()), dtype=float)
        return ManifoldDriftSnapshot(
            alpha_drift=drifts,
            mean_drift=float(np.mean(vals)),
            max_drift=float(np.max(vals)),
        )
