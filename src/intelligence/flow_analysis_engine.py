"""
Strategy crowding and flow-pressure diagnostics.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


class FlowAnalysisEngine:
    def compute_crowding_score(
        self,
        option_chain: Optional[pd.DataFrame],
        *,
        skew_extremity: float = 0.0,
        iv_percentile: float = 0.5,
    ) -> Dict[str, float]:
        if option_chain is None or option_chain.empty:
            return {
                "crowding_score": 0.0,
                "oi_concentration": 0.0,
                "dealer_gamma_proxy": 0.0,
                "skew_position_bias": 0.0,
            }

        chain = option_chain.copy()
        oi_col = "open_interest" if "open_interest" in chain.columns else ("oi" if "oi" in chain.columns else None)
        if oi_col is None:
            oi_concentration = 0.0
        else:
            chain[oi_col] = pd.to_numeric(chain[oi_col], errors="coerce").fillna(0.0)
            total_oi = float(chain[oi_col].sum())
            if total_oi <= 1e-12:
                oi_concentration = 0.0
            else:
                weights = chain[oi_col].to_numpy(dtype=float) / total_oi
                oi_concentration = float(np.sum(weights ** 2))  # HHI

        gamma_proxy = 0.0
        if "gamma" in chain.columns and oi_col is not None:
            gamma = pd.to_numeric(chain["gamma"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            oi = pd.to_numeric(chain[oi_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            gamma_proxy = float(np.tanh(np.sum(np.abs(gamma) * oi) / max(np.sum(oi), 1e-8)))

        skew_bias = float(max(0.0, skew_extremity))
        iv_pct = float(np.clip(iv_percentile, 0.0, 1.0))
        crowding_score = float(
            np.clip(
                0.35 * oi_concentration + 0.30 * gamma_proxy + 0.20 * skew_bias + 0.15 * iv_pct,
                0.0,
                1.0,
            )
        )
        return {
            "crowding_score": crowding_score,
            "oi_concentration": float(oi_concentration),
            "dealer_gamma_proxy": float(gamma_proxy),
            "skew_position_bias": skew_bias,
        }
