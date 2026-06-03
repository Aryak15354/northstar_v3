"""Evolutionary mutation utilities for strategy/model search."""

from __future__ import annotations

from typing import Any, Dict, List

import random


class MutationEngine:
    def __init__(self, random_state: int = 42):
        self.random_state = int(random_state)
        random.seed(self.random_state)

    def mutate_params(self, params: Dict[str, Any], mutation_rate: float = 0.30) -> Dict[str, Any]:
        out = dict(params)
        for k, v in list(out.items()):
            if random.random() > mutation_rate:
                continue
            if isinstance(v, (int, float)):
                scale = random.uniform(0.8, 1.25)
                nv = v * scale
                out[k] = int(round(nv)) if isinstance(v, int) else float(nv)
        return out

    def mutate_feature_set(self, features: List[str], drop_rate: float = 0.10, add_candidates: List[str] | None = None) -> List[str]:
        if not features:
            return features
        keep = [f for f in features if random.random() > drop_rate]
        if add_candidates:
            for c in add_candidates:
                if c not in keep and random.random() < 0.05:
                    keep.append(c)
        return keep or features[:]

    def recombine(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        keys = sorted(set(a.keys()) | set(b.keys()))
        for k in keys:
            if random.random() < 0.5:
                out[k] = a.get(k, b.get(k))
            else:
                out[k] = b.get(k, a.get(k))
        return out
