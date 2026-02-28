#!/usr/bin/env python3
"""
Crowding penalty system for capacity realism.

Penalizes capital when portfolio/factor correlations exceed crowding thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass
class CrowdingConfig:
    """Configuration for crowding penalties."""

    correlation_threshold: float = 0.70
    threshold_penalty: float = 0.50
    min_penalty: float = 0.10
    rolling_window: int = 63


class CrowdingPenaltySystem:
    """ETF factor crowding analyzer with multiplicative penalty application."""

    def __init__(self, config: CrowdingConfig | None = None):
        self.config = config or CrowdingConfig()

    def compute_rolling_correlations(
        self,
        strategy_returns: pd.Series | pd.DataFrame,
        etf_returns: pd.DataFrame,
    ) -> Dict[str, float]:
        """Compute rolling-window correlations versus ETF/factor return streams."""

        if isinstance(strategy_returns, pd.DataFrame):
            if strategy_returns.empty:
                return {}
            if "portfolio_return" in strategy_returns.columns:
                base = pd.to_numeric(strategy_returns["portfolio_return"], errors="coerce")
            else:
                base = pd.to_numeric(strategy_returns.iloc[:, 0], errors="coerce")
        else:
            base = pd.to_numeric(strategy_returns, errors="coerce")

        base = base.dropna().tail(self.config.rolling_window)
        if base.empty or etf_returns.empty:
            return {}

        out: Dict[str, float] = {}
        for col in etf_returns.columns:
            x = pd.to_numeric(etf_returns[col], errors="coerce").dropna().tail(self.config.rolling_window)
            aligned = pd.concat([base, x], axis=1, join="inner").dropna()
            if len(aligned) >= 5:
                corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
                out[str(col)] = float(corr) if pd.notna(corr) else 0.0
            else:
                out[str(col)] = 0.0
        return out

    # Compatibility wrappers used by capacity specs/integration docs.
    def calculate_etf_correlation(
        self,
        strategy_returns: pd.Series | pd.DataFrame,
        etf_returns: pd.DataFrame,
    ) -> Dict[str, float]:
        return self.compute_rolling_correlations(strategy_returns, etf_returns)

    def penalty_for_correlation(self, correlation: float) -> float:
        """
        Compute factor penalty multiplier from correlation.

        Rule:
        - corr <= threshold => 1.0 (no penalty)
        - corr > threshold  => <= 0.5 and decays as correlation approaches 1
        """

        corr = float(correlation)
        if corr <= self.config.correlation_threshold:
            return 1.0

        span = max(1e-6, 1.0 - self.config.correlation_threshold)
        overshoot = min(1.0, (corr - self.config.correlation_threshold) / span)
        penalty = self.config.threshold_penalty * (1.0 - overshoot)
        return float(max(self.config.min_penalty, penalty))

    def combined_penalty(self, correlations: Mapping[str, float]) -> float:
        """Compute multiplicative combined penalty across crowded factors."""

        crowded = [self.penalty_for_correlation(v) for v in correlations.values() if float(v) > self.config.correlation_threshold]
        if not crowded:
            return 1.0
        return float(np.prod(crowded))

    def apply_penalties(
        self,
        allocations: Mapping[str, float],
        correlations: Mapping[str, float],
        whitelist: Sequence[str] | None = None,
    ) -> Dict[str, float]:
        """Apply crowding penalties to non-whitelisted allocations."""

        wl = {str(x) for x in (whitelist or [])}
        penalty = self.combined_penalty(correlations)
        out: Dict[str, float] = {}
        for key, value in allocations.items():
            if str(key) in wl:
                out[str(key)] = float(value)
            else:
                out[str(key)] = float(value) * penalty
        return out

    def apply_crowding_penalty(
        self,
        weights: Mapping[str, float],
        correlations: Mapping[str, float],
        whitelist: Sequence[str] | None = None,
    ) -> Dict[str, float]:
        return self.apply_penalties(weights, correlations, whitelist=whitelist)

    def generate_factor_exposure_report(self, correlations: Mapping[str, float]) -> pd.DataFrame:
        """Generate tabular factor exposure + penalty diagnostics."""

        rows = []
        for factor, corr in correlations.items():
            corr_val = float(corr)
            penalty = self.penalty_for_correlation(corr_val)
            rows.append(
                {
                    "factor": str(factor),
                    "correlation": corr_val,
                    "crowded": corr_val > self.config.correlation_threshold,
                    "penalty_multiplier": penalty,
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("correlation", ascending=False).reset_index(drop=True)
        return df

    def get_factor_exposures(self, correlations: Mapping[str, float]) -> Dict[str, float]:
        """Return simplified factor exposure dict for dashboards/reports."""
        return {str(k): float(v) for k, v in correlations.items()}
