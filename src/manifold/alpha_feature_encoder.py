"""Feature encoding for structural alpha manifold mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

import numpy as np


@dataclass(frozen=True)
class AlphaFeatureRow:
    alpha_id: str
    family: str
    features: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": str(self.alpha_id),
            "family": str(self.family),
            "features": {str(k): float(v) for k, v in dict(self.features or {}).items()},
        }


class AlphaFeatureEncoder:
    """Builds a stable structural feature vector for each alpha."""

    def __init__(self, *, winsor_pct: float = 0.02):
        self.winsor_pct = float(np.clip(winsor_pct, 0.0, 0.20))

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
    def _max_drawdown(returns: np.ndarray) -> float:
        if returns.size == 0:
            return 0.0
        eq = np.cumprod(1.0 + returns)
        peaks = np.maximum.accumulate(eq)
        dd = (eq / np.maximum(peaks, 1e-12)) - 1.0
        return float(abs(np.min(dd)))

    @staticmethod
    def _skew(x: np.ndarray) -> float:
        if x.size < 3:
            return 0.0
        mu = float(np.mean(x))
        sd = float(np.std(x))
        if sd <= 1e-12:
            return 0.0
        z = (x - mu) / sd
        return float(np.mean(z**3))

    def _winsorize(self, mat: np.ndarray) -> np.ndarray:
        if mat.size == 0 or self.winsor_pct <= 0.0:
            return mat
        lo = np.quantile(mat, self.winsor_pct, axis=0)
        hi = np.quantile(mat, 1.0 - self.winsor_pct, axis=0)
        return np.clip(mat, lo, hi)

    @staticmethod
    def _zscore_columns(mat: np.ndarray) -> np.ndarray:
        if mat.size == 0:
            return mat
        mu = np.mean(mat, axis=0)
        sd = np.std(mat, axis=0)
        sd = np.where(sd <= 1e-10, 1.0, sd)
        return (mat - mu) / sd

    def encode(
        self,
        *,
        alpha_ids: List[str],
        expected_edges: Mapping[str, float],
        strategy_points: Mapping[str, Any] | None = None,
        return_series_map: Mapping[str, List[float]] | None = None,
        capacity_caps: Mapping[str, float] | None = None,
        factor_exposures: Mapping[str, Mapping[str, float]] | None = None,
    ) -> List[AlphaFeatureRow]:
        rows: List[AlphaFeatureRow] = []
        strategy_points = dict(strategy_points or {})
        return_series_map = dict(return_series_map or {})
        capacity_caps = dict(capacity_caps or {})
        factor_exposures = dict(factor_exposures or {})

        for sid in [str(x) for x in list(alpha_ids or [])]:
            pt = strategy_points.get(sid)
            returns = np.asarray(list(return_series_map.get(sid, []) or []), dtype=float)
            returns = returns[np.isfinite(returns)]
            if returns.size > 512:
                returns = returns[-512:]

            vol = float(np.std(returns)) if returns.size > 1 else 0.0
            turnover_proxy = float(np.mean(np.abs(np.diff(returns)))) if returns.size > 2 else 0.0
            sharpe_proxy = float(np.mean(returns) / (np.std(returns) + 1e-8)) if returns.size > 2 else 0.0
            maxdd = self._max_drawdown(returns)
            skew = self._skew(returns)

            factors = np.asarray(
                [self._safe_float(v, 0.0) for v in dict(factor_exposures.get(sid, {}) or {}).values()],
                dtype=float,
            )
            factor_l2 = float(np.linalg.norm(factors)) if factors.size > 0 else 0.0

            if pt is None:
                family = str(sid.split(":")[0] if ":" in sid else sid)
                wf_sharpe = sharpe_proxy if sharpe_proxy != 0.0 else self._safe_float(expected_edges.get(sid, 0.0), 0.0)
                mc_survival = 0.50
                regime_var = 0.0
                decay = 0.0
            else:
                family = str(sid.split(":")[0] if ":" in sid else sid)
                wf_sharpe = self._safe_float(getattr(pt, "avg_err", 0.0), 0.0)
                mc_survival = self._safe_float(getattr(pt, "certification_survival_ratio", 0.5), 0.5)
                regime_var = self._safe_float(getattr(pt, "regime_sensitivity", 0.0), 0.0)
                decay = abs(self._safe_float(getattr(pt, "edge_decay", 0.0), 0.0))

            features = {
                "wf_sharpe": float(wf_sharpe),
                "mc_survival": float(mc_survival),
                "max_drawdown": float(maxdd),
                "capacity": float(self._safe_float(capacity_caps.get(sid, 0.0), 0.0)),
                "turnover": float(turnover_proxy),
                "surface_svr": float(max(0.0, 1.0 - min(1.0, regime_var))),
                "surface_curvature": float(regime_var),
                "regime_variance": float(regime_var),
                "factor_loading_norm": float(factor_l2),
                "tail_skew": float(skew),
                "volatility_profile": float(vol),
                "phase6_decay_lambda": float(decay),
                "expected_edge": float(self._safe_float(expected_edges.get(sid, 0.0), 0.0)),
            }
            rows.append(AlphaFeatureRow(alpha_id=sid, family=family, features=features))

        if not rows:
            return []

        # Column normalization for metric stability across families.
        keys = list(rows[0].features.keys())
        mat = np.asarray([[r.features[k] for k in keys] for r in rows], dtype=float)
        mat = self._winsorize(mat)
        mat = self._zscore_columns(mat)

        norm_rows: List[AlphaFeatureRow] = []
        for i, r in enumerate(rows):
            norm_rows.append(
                AlphaFeatureRow(
                    alpha_id=r.alpha_id,
                    family=r.family,
                    features={k: float(mat[i, j]) for j, k in enumerate(keys)},
                )
            )
        return norm_rows
