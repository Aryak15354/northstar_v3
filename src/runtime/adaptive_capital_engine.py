"""Adaptive capital scaler for dynamic runtime multipliers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


@dataclass(frozen=True)
class AdaptiveCapitalDecision:
    regime_multiplier: float
    kelly_alpha: float
    kelly_estimation_error: float
    drift_z_score: float
    liquidity_multiplier: float
    vol_target_multiplier: float
    survival_multiplier: float
    inertia_applied: float
    final_multiplier: float
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime_multiplier": float(self.regime_multiplier),
            "kelly_alpha": float(self.kelly_alpha),
            "kelly_estimation_error": float(self.kelly_estimation_error),
            "drift_z_score": float(self.drift_z_score),
            "liquidity_multiplier": float(self.liquidity_multiplier),
            "vol_target_multiplier": float(self.vol_target_multiplier),
            "survival_multiplier": float(self.survival_multiplier),
            "inertia_applied": float(self.inertia_applied),
            "final_multiplier": float(self.final_multiplier),
            "status": str(self.status),
        }


class AdaptiveCapitalEngine:
    """Regime-aware, liquidity-aware, and volatility-targeted sizing scaler."""

    def __init__(
        self,
        *,
        target_volatility: float = 0.12,
        min_multiplier: float = 0.35,
        max_multiplier: float = 1.25,
        min_kelly_alpha: float = 0.30,
        min_liquidity_multiplier: float = 0.50,
        max_vol_target_multiplier: float = 1.25,
        max_drift_penalty: float = 0.35,
    ):
        self.target_volatility = float(max(1e-4, target_volatility))
        self.min_multiplier = float(np.clip(min_multiplier, 0.05, 2.0))
        self.max_multiplier = float(np.clip(max_multiplier, self.min_multiplier, 3.0))
        self.min_kelly_alpha = float(np.clip(min_kelly_alpha, 0.05, 1.0))
        self.min_liquidity_multiplier = float(np.clip(min_liquidity_multiplier, 0.05, 1.0))
        self.max_vol_target_multiplier = float(np.clip(max_vol_target_multiplier, 1.0, 3.0))
        self.max_drift_penalty = float(np.clip(max_drift_penalty, 0.0, 0.95))

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    def _liquidity_multiplier(self, risk_snapshot: Dict[str, Any]) -> float:
        spread = self._safe_float(risk_snapshot.get("spread_bps", 0.0), 0.0)
        slippage = self._safe_float(risk_snapshot.get("estimated_slippage_bps", spread), spread)
        liq_factor_raw = self._safe_float(risk_snapshot.get("liquidity_factor", 1.0), 1.0)
        liq_factor = max(1.0, liq_factor_raw + (max(0.0, slippage - 5.0) / 50.0))
        multiplier = 1.0 / liq_factor
        return float(np.clip(multiplier, self.min_liquidity_multiplier, 1.0))

    def _vol_target_multiplier(self, risk_snapshot: Dict[str, Any]) -> float:
        realized_vol = self._safe_float(
            risk_snapshot.get("realized_volatility", risk_snapshot.get("portfolio_volatility", 0.0)),
            0.0,
        )
        if realized_vol <= 1e-8:
            return 1.0
        mult = float(self.target_volatility / realized_vol)
        return float(np.clip(mult, 0.40, self.max_vol_target_multiplier))

    def scale(
        self,
        *,
        risk_snapshot: Dict[str, Any] | None,
        survival_probability: float = 1.0,
        regime_multiplier: float = 1.0,
        estimation_error: float = 0.0,
        live_sharpe: float | None = None,
        expected_sharpe: float | None = None,
        mc_sharpe_std: float | None = None,
        prior_multiplier: float = 1.0,
        inertia: float = 0.0,
    ) -> AdaptiveCapitalDecision:
        rs = dict(risk_snapshot or {})
        survival_probability = float(np.clip(survival_probability, 0.0, 1.0))
        regime_multiplier = float(np.clip(regime_multiplier, 0.50, 1.50))
        inertia = float(np.clip(inertia, 0.0, 0.95))
        prior_multiplier = float(np.clip(prior_multiplier, self.min_multiplier, self.max_multiplier))
        estimation_error = float(max(0.0, estimation_error))

        kelly_alpha_raw = float(survival_probability / (1.0 + estimation_error))
        kelly_alpha = float(np.clip(kelly_alpha_raw, self.min_kelly_alpha, 1.0))
        survival_multiplier = float(np.clip(0.50 + (0.50 * survival_probability), 0.60, 1.0))
        liquidity_multiplier = self._liquidity_multiplier(rs)
        vol_target_multiplier = self._vol_target_multiplier(rs)
        drift_z = 0.0
        if (live_sharpe is not None) and (expected_sharpe is not None):
            denom = float(max(1e-6, self._safe_float(mc_sharpe_std, 0.20)))
            drift_z = float((float(live_sharpe) - float(expected_sharpe)) / denom)
        drift_penalty = 0.0
        if drift_z < 0.0:
            drift_penalty = float(np.clip(abs(drift_z) * 0.10, 0.0, self.max_drift_penalty))
        drift_multiplier = float(np.clip(1.0 - drift_penalty, 0.50, 1.0))

        raw = regime_multiplier * kelly_alpha * survival_multiplier * liquidity_multiplier * vol_target_multiplier * drift_multiplier
        raw = float(np.clip(raw, self.min_multiplier, self.max_multiplier))
        final = float((inertia * prior_multiplier) + ((1.0 - inertia) * raw))
        final = float(np.clip(final, self.min_multiplier, self.max_multiplier))
        status = "scaled_down" if final < 0.95 else "neutral"
        if final > 1.01:
            status = "scaled_up"

        return AdaptiveCapitalDecision(
            regime_multiplier=regime_multiplier,
            kelly_alpha=kelly_alpha,
            kelly_estimation_error=estimation_error,
            drift_z_score=drift_z,
            liquidity_multiplier=liquidity_multiplier,
            vol_target_multiplier=vol_target_multiplier,
            survival_multiplier=survival_multiplier,
            inertia_applied=inertia,
            final_multiplier=final,
            status=status,
        )
