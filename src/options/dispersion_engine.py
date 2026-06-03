"""
Institutional dispersion analytics for index vs constituents vol.
"""

from __future__ import annotations

from typing import Dict, Iterable

import numpy as np


class DispersionEngine:
    def compute_implied_correlation(
        self,
        index_iv: float,
        constituent_ivs: Iterable[float],
        weights: Iterable[float],
    ) -> float:
        iv = np.asarray(list(constituent_ivs), dtype=float)
        w = np.asarray(list(weights), dtype=float)
        if iv.size == 0 or iv.size != w.size:
            return 0.0
        iv = np.clip(iv, 1e-8, None)
        w = np.clip(w, 0.0, None)
        if float(w.sum()) <= 1e-12:
            return 0.0
        w = w / w.sum()

        sigma_index2 = float(index_iv) ** 2
        weighted_var = float(np.sum((w ** 2) * (iv ** 2)))
        pairwise = 0.0
        for i in range(len(w)):
            for j in range(i + 1, len(w)):
                pairwise += float(w[i] * w[j] * iv[i] * iv[j])
        denom = max(2.0 * pairwise, 1e-12)
        rho = (sigma_index2 - weighted_var) / denom
        return float(np.clip(rho, -1.0, 1.0))

    def compute_signal(
        self,
        implied_corr: float,
        realized_corr: float,
    ) -> Dict[str, float | str]:
        spread = float(implied_corr - realized_corr)
        if spread > 0.08:
            stance = "short_index_long_single_name_vol"
        elif spread < -0.08:
            stance = "long_index_vol"
        else:
            stance = "neutral"
        return {
            "dispersion_spread": spread,
            "stance": stance,
        }
