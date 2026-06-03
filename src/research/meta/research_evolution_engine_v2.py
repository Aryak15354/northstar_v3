"""Phase 7 orchestrator: self-adjusting research policy updates."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping

from .alpha_experience_memory import AlphaExperienceMemory
from .compute_allocator import StabilityWeightedComputeAllocator
from .durability_model import DurabilityModel
from .manifold_diversity_engine import ManifoldDiversityEngine
from .meta_policy_store import MetaPolicyStore
from .parameter_space_adapter import ParameterSpaceAdapter


class ResearchEvolutionEngineV2:
    def __init__(
        self,
        *,
        memory: AlphaExperienceMemory,
        durability_model: DurabilityModel | None = None,
        compute_allocator: StabilityWeightedComputeAllocator | None = None,
        diversity_engine: ManifoldDiversityEngine | None = None,
        space_adapter: ParameterSpaceAdapter | None = None,
        policy_store: MetaPolicyStore | None = None,
        min_history_to_adapt: int = 20,
        base_exploration_rate: float = 0.20,
    ):
        self.memory = memory
        self.durability_model = durability_model or DurabilityModel()
        self.compute_allocator = compute_allocator or StabilityWeightedComputeAllocator()
        self.diversity_engine = diversity_engine or ManifoldDiversityEngine()
        self.space_adapter = space_adapter or ParameterSpaceAdapter()
        self.policy_store = policy_store or MetaPolicyStore()
        self.min_history_to_adapt = int(max(1, min_history_to_adapt))
        self.base_exploration_rate = float(max(0.01, min(0.90, base_exploration_rate)))

    @staticmethod
    def _numeric_param_bounds(records: Iterable[Mapping[str, Any]]) -> Dict[str, tuple[float, float]]:
        vals: Dict[str, List[float]] = defaultdict(list)
        for row in records:
            params = dict(row.get("parameter_vector", row.get("params", {})) or {})
            for k, v in params.items():
                try:
                    fv = float(v)
                except Exception:
                    continue
                vals[str(k)].append(float(fv))
        out: Dict[str, tuple[float, float]] = {}
        for k, arr in vals.items():
            if len(arr) < 2:
                continue
            out[k] = (float(min(arr)), float(max(arr)))
        return out

    def run_cycle(
        self,
        *,
        experiments: Iterable[Mapping[str, Any]],
        safe_parameter_bounds: Mapping[str, Mapping[str, tuple[float, float]]] | None = None,
        history_limit: int = 5000,
    ) -> Dict[str, Any]:
        inserted = self.memory.append_experiments(experiments)
        history_objs = self.memory.fetch_recent(limit=history_limit)
        history = [x.to_dict() for x in history_objs]
        n_hist = len(history)
        policy_prev = self.policy_store.load()

        if n_hist == 0:
            payload = {
                "status": "no_data",
                "inserted": int(inserted),
                "history_count": 0,
                "family_compute_weights": dict(policy_prev.get("family_compute_weights", {}) or {}),
                "parameter_bounds": dict(policy_prev.get("parameter_bounds", {}) or {}),
                "resolution_map": dict(policy_prev.get("resolution_map", {}) or {}),
                "exploration_rate": float(policy_prev.get("exploration_rate", self.base_exploration_rate) or self.base_exploration_rate),
            }
            return self.policy_store.save(payload)

        self.durability_model.fit(history)
        fam_expect = self.durability_model.family_expectations()
        mem_stats = self.memory.family_metrics(limit=history_limit)
        density = self.diversity_engine.snapshot(history)

        family_stats: Dict[str, Dict[str, float]] = {}
        families = sorted(set(fam_expect.keys()) | set(mem_stats.keys()) | set(density.family_density.keys()))
        for fam in families:
            family_stats[fam] = {
                "expected_durability": float(fam_expect.get(fam, 0.0)),
                "durability_mean": float(dict(mem_stats.get(fam, {}) or {}).get("durability_mean", 0.0)),
                "fragility_mean": float(dict(mem_stats.get(fam, {}) or {}).get("fragility_mean", 0.0)),
                "cluster_density": float(density.family_density.get(fam, 0.0)),
            }

        prev_weights = dict(policy_prev.get("family_compute_weights", {}) or {})
        alloc = self.compute_allocator.allocate(
            family_stats=family_stats,
            previous_weights=prev_weights,
        )

        next_bounds: Dict[str, Dict[str, List[float]]] = {}
        resolution_map = dict(policy_prev.get("resolution_map", {}) or {})
        by_family: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in history:
            fam = str(row.get("family", "unknown") or "unknown")
            by_family[fam].append(dict(row))

        prev_policy_bounds = dict(policy_prev.get("parameter_bounds", {}) or {})
        for fam, rows in by_family.items():
            current_bounds_raw = dict(prev_policy_bounds.get(fam, {}) or {})
            current_bounds = {
                str(k): (float(v[0]), float(v[1]))
                for k, v in current_bounds_raw.items()
                if isinstance(v, (list, tuple)) and len(v) >= 2
            }
            if not current_bounds:
                current_bounds = self._numeric_param_bounds(rows)
            safe_bounds = dict((safe_parameter_bounds or {}).get(fam, {}) or {})
            if not safe_bounds:
                safe_bounds = dict(current_bounds)
            if n_hist < self.min_history_to_adapt:
                adapted_bounds = current_bounds
                res_scale = float(resolution_map.get(fam, 1.0) or 1.0)
            else:
                update = self.space_adapter.adapt_family(
                    family_records=rows,
                    current_bounds=current_bounds,
                    safe_bounds=safe_bounds,
                )
                adapted_bounds = update.bounds
                prev_scale = float(resolution_map.get(fam, 1.0) or 1.0)
                res_scale = float(max(0.5, min(2.0, prev_scale * float(update.resolution_scale))))
            next_bounds[fam] = {k: [float(v[0]), float(v[1])] for k, v in adapted_bounds.items()}
            resolution_map[fam] = float(res_scale)

        avg_n = sum(float(v.get("count", 0.0)) for v in mem_stats.values()) / max(1.0, float(len(mem_stats) or 1))
        exploration_rate = float(max(0.05, min(0.35, self.base_exploration_rate / (1.0 + (0.02 * avg_n)))))

        payload = {
            "status": "updated",
            "inserted": int(inserted),
            "history_count": int(n_hist),
            "family_compute_weights": dict(alloc.family_weights),
            "parameter_bounds": dict(next_bounds),
            "resolution_map": {str(k): float(v) for k, v in dict(resolution_map).items()},
            "exploration_rate": float(exploration_rate),
            "diagnostics": {
                "family_stats": family_stats,
                "allocation": alloc.to_dict(),
                "diversity": density.to_dict(),
                "min_history_to_adapt": int(self.min_history_to_adapt),
            },
        }
        return self.policy_store.save(payload)
