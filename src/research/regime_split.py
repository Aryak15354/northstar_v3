"""Regime-aware split utilities."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def split_by_regime(frame: pd.DataFrame, regime_col: str = "regime") -> Dict[str, np.ndarray]:
    if frame.empty or regime_col not in frame.columns:
        return {}
    out: Dict[str, np.ndarray] = {}
    s = frame[regime_col].astype(str)
    for regime in sorted(s.dropna().unique()):
        out[str(regime)] = s.eq(str(regime)).to_numpy()
    return out
