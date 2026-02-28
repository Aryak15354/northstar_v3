"""
Correlation-aware strategy diversification controls.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping

import numpy as np
import pandas as pd


class StrategyCorrelationEngine:
    def __init__(self, max_pairwise_corr: float = 0.70) -> None:
        self.max_pairwise_corr = float(max_pairwise_corr)

    def compute(
        self,
        pnl_history: Mapping[str, Iterable[float]],
    ) -> Dict[str, object]:
        series_map: Dict[str, pd.Series] = {}
        for k, v in pnl_history.items():
            vals = list(v)
            if not vals:
                continue
            series_map[str(k)] = pd.Series(vals, dtype=float)
        if not series_map:
            frame = pd.DataFrame()
        else:
            # Use aligned series to tolerate unequal history lengths across strategies.
            frame = pd.concat(series_map, axis=1)
        if frame.empty or frame.shape[1] < 2:
            return {
                "correlation_matrix": {},
                "violations": [],
                "effective_rank": 1,
                "compression_ratio": 1.0,
            }

        corr = frame.corr().fillna(0.0)
        violations: List[Dict[str, object]] = []
        cols = list(corr.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                value = float(corr.iloc[i, j])
                if abs(value) > self.max_pairwise_corr:
                    violations.append(
                        {
                            "strategy_a": cols[i],
                            "strategy_b": cols[j],
                            "correlation": value,
                        }
                    )

        eigvals = np.linalg.eigvalsh(corr.to_numpy(dtype=float))
        eigvals = np.clip(eigvals, 1e-12, None)
        weights = eigvals / eigvals.sum()
        entropy_rank = float(np.exp(-np.sum(weights * np.log(weights))))
        compression_ratio = float(entropy_rank / len(eigvals))

        return {
            "correlation_matrix": corr.round(6).to_dict(),
            "violations": violations,
            "effective_rank": entropy_rank,
            "compression_ratio": compression_ratio,
        }
