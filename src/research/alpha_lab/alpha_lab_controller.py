"""Alpha Lab discovery harness controller."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

import numpy as np

from ..research_types import ResearchDataset
from ..training_pipeline import TrainingPipeline
from .hypothesis_registry import AlphaHypothesis
from .parameter_surface_explorer import ParameterSurfaceExplorer, SurfacePointResult, SurfaceThresholds
from .robustness_tester import RobustnessTester
from .store import AlphaLabStore


@dataclass(frozen=True)
class AlphaLabThresholds:
    min_test_sharpe: float = 0.70
    min_fold_pass_ratio: float = 0.60
    min_stability_score: float = 0.60
    max_stress_drag: float = 0.40
    min_robustness_score: float = 0.60
    min_turnover: float = 0.0
    max_turnover: float = 5.0
    phase2_enabled: bool = True
    phase2_max_parameter_combinations: int = 200


class AlphaLabController:
    """Discovery harness that evaluates hypotheses over deterministic walk-forward folds."""

    def __init__(
        self,
        *,
        pipeline: TrainingPipeline,
        store: AlphaLabStore | None = None,
        robustness_tester: RobustnessTester | None = None,
        surface_explorer: ParameterSurfaceExplorer | None = None,
        thresholds: AlphaLabThresholds | None = None,
    ):
        self.pipeline = pipeline
        self.store = store or AlphaLabStore()
        self.robustness_tester = robustness_tester or RobustnessTester()
        self.thresholds = thresholds or AlphaLabThresholds()
        self.surface_explorer = surface_explorer or ParameterSurfaceExplorer(
            SurfaceThresholds(min_test_sharpe=float(max(0.0, self.thresholds.min_test_sharpe)))
        )

    @staticmethod
    def _param_hash(params: Dict[str, Any]) -> str:
        raw = json.dumps(dict(params or {}), sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _param_grid_iter(grid: Dict[str, List[Any]]) -> Iterable[Dict[str, Any]]:
        if not grid:
            yield {}
            return
        keys = sorted(grid)
        values = [list(grid.get(k, [])) for k in keys]
        if any(len(v) == 0 for v in values):
            yield {}
            return
        stack: List[Tuple[int, Dict[str, Any]]] = [(0, {})]
        while stack:
            idx, cur = stack.pop()
            if idx >= len(keys):
                yield dict(cur)
                continue
            key = keys[idx]
            vals = values[idx]
            for v in reversed(vals):
                nxt = dict(cur)
                nxt[key] = v
                stack.append((idx + 1, nxt))

    def evaluate_walk_forward(
        self,
        *,
        hypothesis: AlphaHypothesis,
        dataset: ResearchDataset,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        model = hypothesis.model_factory(dict(params or {}))
        result = self.pipeline.run(model=model, dataset=dataset)
        windows = list(result.get("windows", []) or [])
        aggregate = dict(result.get("aggregate_metrics", {}) or {})
        fold_rows: List[Dict[str, Any]] = []
        for i, w in enumerate(windows):
            metrics = dict(getattr(w, "metrics", {}) or {})
            fold_rows.append(
                {
                    "fold_id": int(i),
                    "train_sharpe": float(metrics.get("train_sharpe", 0.0) or 0.0),
                    "test_sharpe": float(metrics.get("sharpe", 0.0) or 0.0),
                    "max_dd": float(metrics.get("max_drawdown", 0.0) or 0.0),
                    "turnover": float(metrics.get("turnover", 0.0) or 0.0),
                    "stress_drag": float(metrics.get("stress_drag", 0.0) or 0.0),
                    "stability_score": float(aggregate.get("stability_score", 0.0) or 0.0),
                    "train_start": str(getattr(w, "train_start", "")),
                    "train_end": str(getattr(w, "train_end", "")),
                    "test_start": str(getattr(w, "test_start", "")),
                    "test_end": str(getattr(w, "test_end", "")),
                    "regime": str(metrics.get("regime", "") or ""),
                }
            )
        return {"result": result, "aggregate_metrics": aggregate, "fold_rows": fold_rows}

    def run_robustness_tests(self, aggregate_metrics: Dict[str, Any]) -> Dict[str, float]:
        return self.robustness_tester.score(aggregate_metrics)

    def _promotion_decision(
        self,
        *,
        fold_rows: List[Dict[str, Any]],
        aggregate_metrics: Dict[str, Any],
        robustness: Dict[str, float],
    ) -> Tuple[bool, str]:
        if not fold_rows:
            return False, "no_fold_rows"

        test_sharpes = np.asarray([float(r.get("test_sharpe", 0.0) or 0.0) for r in fold_rows], dtype=float)
        turnover = np.asarray([float(r.get("turnover", 0.0) or 0.0) for r in fold_rows], dtype=float)
        stress_drag = np.asarray([float(r.get("stress_drag", 0.0) or 0.0) for r in fold_rows], dtype=float)
        pass_ratio = float((test_sharpes > self.thresholds.min_test_sharpe).mean()) if len(test_sharpes) else 0.0
        no_crash = bool(np.all(test_sharpes >= -0.5))
        stable = float(aggregate_metrics.get("stability_score", 0.0) or 0.0) >= self.thresholds.min_stability_score
        stress_ok = float(np.mean(stress_drag)) <= self.thresholds.max_stress_drag if len(stress_drag) else True
        turnover_ok = True
        if len(turnover):
            avg_turnover = float(np.mean(turnover))
            turnover_ok = self.thresholds.min_turnover <= avg_turnover <= self.thresholds.max_turnover
        robust = float(robustness.get("robustness_score", 0.0) or 0.0) >= self.thresholds.min_robustness_score

        if pass_ratio < self.thresholds.min_fold_pass_ratio:
            return False, "fold_pass_ratio_below_threshold"
        if not no_crash:
            return False, "fold_sharpe_crash"
        if not stable:
            return False, "stability_below_threshold"
        if not stress_ok:
            return False, "stress_drag_above_threshold"
        if not turnover_ok:
            return False, "turnover_out_of_bounds"
        if not robust:
            return False, "robustness_below_threshold"
        return True, "promote"

    def run_hypothesis_suite(
        self,
        *,
        dataset: ResearchDataset,
        hypotheses: Iterable[AlphaHypothesis],
    ) -> Dict[str, Any]:
        all_rows: List[Dict[str, Any]] = []
        survivors: List[Dict[str, Any]] = []
        for hypothesis in hypotheses:
            params_grid = list(self._param_grid_iter(hypothesis.parameter_grid))
            max_points = max(1, int(self.thresholds.phase2_max_parameter_combinations))
            grid_truncated = False
            if len(params_grid) > max_points:
                params_grid = params_grid[:max_points]
                grid_truncated = True

            hypothesis_rows: List[Dict[str, Any]] = []
            for params in params_grid:
                wf = self.evaluate_walk_forward(hypothesis=hypothesis, dataset=dataset, params=params)
                aggregate = dict(wf.get("aggregate_metrics", {}) or {})
                fold_rows = list(wf.get("fold_rows", []) or [])
                robustness = self.run_robustness_tests(aggregate)
                parameter_hash = self._param_hash(params)

                self.store.write_fold_rows(
                    hypothesis_name=hypothesis.name,
                    parameter_hash=parameter_hash,
                    rows=fold_rows,
                )
                self.store.write_robustness(
                    hypothesis_name=hypothesis.name,
                    parameter_hash=parameter_hash,
                    robustness_payload=robustness,
                )
                hypothesis_rows.append(
                    {
                        "hypothesis_name": hypothesis.name,
                        "parameter_hash": parameter_hash,
                        "params": dict(params),
                        "aggregate_metrics": aggregate,
                        "fold_rows": fold_rows,
                        "robustness": robustness,
                    }
                )

            surface_by_hash: Dict[str, SurfacePointResult] = {}
            if bool(self.thresholds.phase2_enabled):
                surface_rows = self.surface_explorer.evaluate(
                    hypothesis_rows,
                    parameter_grid=hypothesis.parameter_grid,
                )
                surface_by_hash = {str(r.parameter_hash): r for r in surface_rows}
                for s in surface_rows:
                    self.store.write_surface_result(
                        hypothesis_name=hypothesis.name,
                        parameter_hash=str(s.parameter_hash),
                        surface_payload=s.to_dict(),
                    )

            for base_row in hypothesis_rows:
                parameter_hash = str(base_row.get("parameter_hash", ""))
                surface = surface_by_hash.get(parameter_hash)
                surface_payload = (
                    surface.to_dict()
                    if surface is not None
                    else {
                        "status": "candidate",
                        "reject_reason": "phase2_disabled",
                        "train_sharpe": float(dict(base_row.get("aggregate_metrics", {}) or {}).get("avg_sharpe", 0.0) or 0.0),
                        "test_sharpe": float(dict(base_row.get("aggregate_metrics", {}) or {}).get("avg_sharpe", 0.0) or 0.0),
                    }
                )

                promoted = False
                reason = "phase2_reject"
                if str(surface_payload.get("status", "candidate")) == "candidate":
                    promoted, reason = self._promotion_decision(
                        fold_rows=list(base_row.get("fold_rows", []) or []),
                        aggregate_metrics=dict(base_row.get("aggregate_metrics", {}) or {}),
                        robustness=dict(base_row.get("robustness", {}) or {}),
                    )
                else:
                    reason = f"phase2_{str(surface_payload.get('reject_reason', 'reject'))}"

                row = {
                    "hypothesis_name": hypothesis.name,
                    "parameter_hash": parameter_hash,
                    "params": dict(base_row.get("params", {}) or {}),
                    "promoted": bool(promoted),
                    "reason": str(reason),
                    "aggregate_metrics": dict(base_row.get("aggregate_metrics", {}) or {}),
                    "robustness": dict(base_row.get("robustness", {}) or {}),
                    "surface_metrics": surface_payload,
                    "phase2_status": str(surface_payload.get("status", "unknown")),
                    "phase2_reason": str(surface_payload.get("reject_reason", "")),
                    "phase2_grid_truncated": bool(grid_truncated),
                }
                all_rows.append(row)
                if promoted:
                    survivors.append(row)

        return {
            "evaluated": all_rows,
            "survivors": survivors,
            "survivor_count": int(len(survivors)),
            "evaluated_count": int(len(all_rows)),
        }

    def promote_survivors(
        self,
        survivors: Iterable[Dict[str, Any]],
        *,
        certification_hook: Any | None = None,
    ) -> Dict[str, Any]:
        promotions: List[Dict[str, Any]] = []
        for row in survivors:
            payload = dict(row or {})
            promote_ok = True
            reason = "promoted"
            if callable(certification_hook):
                hook_out = certification_hook(payload)
                if isinstance(hook_out, tuple) and len(hook_out) == 2:
                    promote_ok = bool(hook_out[0])
                    reason = str(hook_out[1])
                else:
                    promote_ok = bool(hook_out)
                    reason = "certification_hook_rejected" if not promote_ok else "promoted"
            promotion_id = f"alphalab_{uuid4().hex[:16]}"
            self.store.write_promotion(
                promotion_id=promotion_id,
                hypothesis_name=str(payload.get("hypothesis_name", "")),
                parameter_hash=str(payload.get("parameter_hash", "")),
                promoted=bool(promote_ok),
                reason=str(reason),
                payload=payload,
            )
            promotions.append(
                {
                    "promotion_id": promotion_id,
                    "hypothesis_name": str(payload.get("hypothesis_name", "")),
                    "parameter_hash": str(payload.get("parameter_hash", "")),
                    "promoted": bool(promote_ok),
                    "reason": str(reason),
                }
            )
        return {"promotions": promotions, "promotion_count": int(len(promotions))}
