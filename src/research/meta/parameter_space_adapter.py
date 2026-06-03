"""Adaptive parameter-bound updater driven by durability outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple

import numpy as np


@dataclass(frozen=True)
class ParameterSpaceUpdate:
    bounds: Dict[str, Tuple[float, float]]
    resolution_scale: float
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bounds": {str(k): [float(v[0]), float(v[1])] for k, v in dict(self.bounds or {}).items()},
            "resolution_scale": float(self.resolution_scale),
            "diagnostics": dict(self.diagnostics or {}),
        }


class ParameterSpaceAdapter:
    def __init__(
        self,
        *,
        contraction_quantile: float = 0.65,
        bound_inertia: float = 0.70,
        max_shift_pct: float = 0.20,
        min_span_ratio: float = 0.10,
    ):
        self.contraction_quantile = float(min(max(0.0, contraction_quantile), 1.0))
        self.bound_inertia = float(min(max(0.0, bound_inertia), 0.98))
        self.max_shift_pct = float(max(0.0, max_shift_pct))
        self.min_span_ratio = float(max(1e-3, min_span_ratio))

    @staticmethod
    def _numeric_params(payload: Mapping[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in dict(payload or {}).items():
            try:
                fv = float(v)
            except Exception:
                continue
            if np.isfinite(fv):
                out[str(k)] = float(fv)
        return out

    def adapt_family(
        self,
        *,
        family_records: Iterable[Mapping[str, Any]],
        current_bounds: Mapping[str, Tuple[float, float]],
        safe_bounds: Mapping[str, Tuple[float, float]] | None = None,
    ) -> ParameterSpaceUpdate:
        records = [dict(r or {}) for r in list(family_records or [])]
        cur = {
            str(k): (float(v[0]), float(v[1]))
            for k, v in dict(current_bounds or {}).items()
            if isinstance(v, (list, tuple)) and len(v) >= 2
        }
        safe = {
            str(k): (float(v[0]), float(v[1]))
            for k, v in dict(safe_bounds or cur).items()
            if isinstance(v, (list, tuple)) and len(v) >= 2
        }
        if not cur or not records:
            return ParameterSpaceUpdate(bounds=cur, resolution_scale=1.0, diagnostics={"reason": "insufficient_data"})

        scores = np.asarray([float(max(0.0, min(1.0, r.get("durability_score", 0.0) or 0.0))) for r in records], dtype=float)
        cutoff = float(np.quantile(scores, self.contraction_quantile)) if scores.size > 0 else 0.0
        selected = [r for r, s in zip(records, scores.tolist()) if float(s) >= cutoff]
        if not selected:
            selected = records

        next_bounds: Dict[str, Tuple[float, float]] = {}
        diagnostics: Dict[str, Any] = {"selected_records": int(len(selected)), "score_cutoff": float(cutoff), "params": {}}
        for param, (old_lo, old_hi) in cur.items():
            if old_hi <= old_lo:
                next_bounds[param] = (old_lo, old_hi)
                continue
            safe_lo, safe_hi = safe.get(param, (old_lo, old_hi))
            safe_lo = float(min(safe_lo, safe_hi))
            safe_hi = float(max(safe_lo, safe_hi))
            old_span = float(max(1e-8, old_hi - old_lo))
            min_span = float(max(1e-8, self.min_span_ratio * (safe_hi - safe_lo)))

            vals = []
            for row in selected:
                params = self._numeric_params(row.get("parameter_vector", row.get("params", {})))
                if param in params:
                    vals.append(float(params[param]))
            if len(vals) < 3:
                next_bounds[param] = (old_lo, old_hi)
                diagnostics["params"][param] = {"reason": "insufficient_param_points"}
                continue

            q10 = float(np.quantile(vals, 0.10))
            q90 = float(np.quantile(vals, 0.90))
            span = float(max(q90 - q10, min_span))
            pad = float(0.15 * span)
            cand_lo = q10 - pad
            cand_hi = q90 + pad

            # Bound shift cap.
            max_shift = float(self.max_shift_pct * old_span)
            cand_lo = float(max(old_lo - max_shift, min(old_lo + max_shift, cand_lo)))
            cand_hi = float(max(old_hi - max_shift, min(old_hi + max_shift, cand_hi)))
            if cand_hi <= cand_lo:
                cand_lo, cand_hi = old_lo, old_hi

            blended_lo = (self.bound_inertia * old_lo) + ((1.0 - self.bound_inertia) * cand_lo)
            blended_hi = (self.bound_inertia * old_hi) + ((1.0 - self.bound_inertia) * cand_hi)

            new_lo = float(max(safe_lo, min(safe_hi, blended_lo)))
            new_hi = float(max(new_lo + min_span, min(safe_hi, blended_hi)))
            if new_hi > safe_hi:
                new_hi = float(safe_hi)
                new_lo = float(max(safe_lo, new_hi - min_span))

            next_bounds[param] = (new_lo, new_hi)
            diagnostics["params"][param] = {
                "old": [float(old_lo), float(old_hi)],
                "candidate": [float(cand_lo), float(cand_hi)],
                "new": [float(new_lo), float(new_hi)],
            }

        old_span_total = sum(max(1e-8, hi - lo) for lo, hi in cur.values())
        new_span_total = sum(max(1e-8, hi - lo) for lo, hi in next_bounds.values())
        ratio = float(new_span_total / max(old_span_total, 1e-8))
        if ratio < 0.80:
            resolution_scale = 1.25
        elif ratio > 1.10:
            resolution_scale = 0.90
        else:
            resolution_scale = 1.0

        diagnostics["span_ratio"] = ratio
        return ParameterSpaceUpdate(
            bounds=next_bounds,
            resolution_scale=float(resolution_scale),
            diagnostics=diagnostics,
        )
