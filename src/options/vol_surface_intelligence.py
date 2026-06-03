"""
Multi-dimensional volatility surface intelligence.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd


class VolSurfaceIntelligence:
    def compute(
        self,
        option_chain: pd.DataFrame,
        *,
        iv_history: Optional[Iterable[float]] = None,
        realized_vol: Optional[float] = None,
    ) -> Dict[str, float]:
        if option_chain is None or option_chain.empty:
            return {
                "iv_percentile_252d": 0.5,
                "term_structure_slope": 0.0,
                "skew_curvature": 0.0,
                "realized_implied_spread": 0.0,
                "vol_of_vol_proxy": 0.0,
            }

        chain = option_chain.copy()
        chain["iv"] = pd.to_numeric(chain.get("iv"), errors="coerce")
        chain["strike"] = pd.to_numeric(chain.get("strike"), errors="coerce")
        chain["underlying_price"] = pd.to_numeric(chain.get("underlying_price"), errors="coerce")
        chain["expiry"] = pd.to_datetime(chain.get("expiry"), errors="coerce")
        chain = chain.dropna(subset=["iv", "strike", "underlying_price", "expiry"])
        if chain.empty:
            return {
                "iv_percentile_252d": 0.5,
                "term_structure_slope": 0.0,
                "skew_curvature": 0.0,
                "realized_implied_spread": 0.0,
                "vol_of_vol_proxy": 0.0,
            }

        atm_iv = float(chain["iv"].median())
        hist = np.asarray(list(iv_history or []), dtype=float)
        hist = hist[np.isfinite(hist)]
        if hist.size > 1:
            hist_tail = hist[-252:]
            iv_percentile = float((hist_tail <= atm_iv).mean())
            vol_of_vol = float(np.std(hist_tail[-20:]) / max(np.std(hist_tail), 1e-8))
        else:
            iv_percentile = 0.5
            vol_of_vol = 0.0

        # Term structure slope: front IV / back IV - 1.
        per_expiry = chain.groupby(chain["expiry"].dt.date)["iv"].median().sort_index()
        if per_expiry.shape[0] >= 2:
            front = float(per_expiry.iloc[0])
            back = float(per_expiry.iloc[-1])
            term_slope = float(front / max(back, 1e-8) - 1.0)
        else:
            term_slope = 0.0

        # Skew curvature from quadratic fit of normalized strike -> IV.
        rel_strike = chain["strike"] / chain["underlying_price"] - 1.0
        if rel_strike.shape[0] >= 5:
            x = rel_strike.to_numpy(dtype=float)
            y = chain["iv"].to_numpy(dtype=float)
            coeffs = np.polyfit(x, y, deg=2)
            skew_curvature = float(2.0 * coeffs[0])
        else:
            skew_curvature = 0.0

        realized_implied_spread = float(atm_iv - float(realized_vol or atm_iv))

        return {
            "iv_percentile_252d": iv_percentile,
            "term_structure_slope": term_slope,
            "skew_curvature": skew_curvature,
            "realized_implied_spread": realized_implied_spread,
            "vol_of_vol_proxy": vol_of_vol,
        }
