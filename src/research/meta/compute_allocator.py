"""Compute-budget allocator with stability and exploration constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ComputeAllocation:
    family_weights: Dict[str, float]
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_weights": {str(k): float(v) for k, v in dict(self.family_weights or {}).items()},
            "diagnostics": dict(self.diagnostics or {}),
        }


class StabilityWeightedComputeAllocator:
    def __init__(
        self,
        *,
        min_family_weight: float = 0.05,
        max_family_weight: float = 0.50,
        inertia: float = 0.70,
        diversity_penalty: float = 0.60,
    ):
        self.min_family_weight = float(max(0.0, min_family_weight))
        self.max_family_weight = float(max(self.min_family_weight, max_family_weight))
        self.inertia = float(min(max(0.0, inertia), 0.98))
        self.diversity_penalty = float(max(0.0, diversity_penalty))

    @staticmethod
    def _norm(weights: Dict[str, float]) -> Dict[str, float]:
        vals = {str(k): float(max(0.0, v)) for k, v in dict(weights or {}).items()}
        total = float(sum(vals.values()))
        if total <= 1e-12:
            n = max(1, len(vals))
            return {k: float(1.0 / n) for k in vals}
        return {k: float(v / total) for k, v in vals.items()}

    def allocate(
        self,
        *,
        family_stats: Mapping[str, Mapping[str, float]],
        previous_weights: Mapping[str, float] | None,
    ) -> ComputeAllocation:
        fams = sorted(str(k) for k in dict(family_stats or {}).keys())
        if not fams:
            return ComputeAllocation(family_weights={}, diagnostics={"reason": "empty_family_stats"})

        raw: Dict[str, float] = {}
        diag: Dict[str, Any] = {"family_scores": {}}
        for fam in fams:
            st = dict(dict(family_stats or {}).get(fam, {}) or {})
            durability = float(max(0.0, st.get("expected_durability", st.get("durability_mean", 0.0)) or 0.0))
            fragility = float(max(0.0, st.get("fragility_mean", st.get("fragility", 0.0)) or 0.0))
            density = float(max(0.0, st.get("cluster_density", st.get("density", 0.0)) or 0.0))
            score = durability / (1.0 + fragility + (self.diversity_penalty * density))
            score = float(max(1e-6, score))
            raw[fam] = score
            diag["family_scores"][fam] = {
                "durability": float(durability),
                "fragility": float(fragility),
                "density": float(density),
                "raw_score": float(score),
            }

        target = self._norm(raw)

        # Exploration floor + max cap.
        n = len(fams)
        min_w = min(self.min_family_weight, 1.0 / max(1, n))
        clipped = {fam: float(min(self.max_family_weight, max(min_w, target.get(fam, 0.0)))) for fam in fams}
        clipped = self._norm(clipped)

        prev = {str(k): float(max(0.0, v)) for k, v in dict(previous_weights or {}).items()}
        if prev:
            for fam in fams:
                prev.setdefault(fam, 0.0)
            prev = self._norm(prev)
            blended = {
                fam: float((self.inertia * prev.get(fam, 0.0)) + ((1.0 - self.inertia) * clipped.get(fam, 0.0)))
                for fam in fams
            }
            weights = self._norm(blended)
        else:
            weights = clipped

        # Re-apply constraints after inertia.
        weights = {fam: float(min(self.max_family_weight, max(min_w, weights.get(fam, 0.0)))) for fam in fams}
        weights = self._norm(weights)

        diag["min_family_weight"] = float(min_w)
        diag["max_family_weight"] = float(self.max_family_weight)
        diag["inertia"] = float(self.inertia)
        return ComputeAllocation(family_weights=weights, diagnostics=diag)
