"""
Meta allocator guardrails to prevent whipsaw de-allocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

import numpy as np


def _clip(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, v)))


@dataclass
class MetaAllocatorConfig:
    regret_half_life_days: int = 20
    hysteresis_relative_change: float = 0.10
    max_weight_shift_per_cycle: float = 0.15
    min_gross_exposure_floor: float = 0.25


class MetaAllocator:
    """
    Applies meta-learning control overlays on top of allocator outputs.
    """

    def __init__(self, config: Optional[MetaAllocatorConfig] = None) -> None:
        self.config = config or MetaAllocatorConfig()
        self._regret_ewma: Dict[str, float] = {}
        self._confidence_ewma: Dict[str, float] = {}
        self._credibility_prev: Dict[str, float] = {}

    def apply(
        self,
        proposed_weights: Mapping[str, float],
        strategy_metrics: Mapping[str, Mapping[str, float]],
        *,
        allowed_gross_cap: float,
        previous_weights: Optional[Mapping[str, float]] = None,
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        prev = {k: float(v) for k, v in (previous_weights or {}).items()}
        out = {k: float(v) for k, v in proposed_weights.items()}
        reason_codes = []
        alpha = self._ewma_alpha(max(1, int(self.config.regret_half_life_days)))
        hysteresis_active = False
        max_delta_applied = False
        floor_applied = False

        for strategy, weight in list(out.items()):
            metrics = strategy_metrics.get(strategy, {})
            regret_raw = _clip(float(metrics.get("regret", 0.0) or 0.0), 0.0, 1.0)
            conf_raw = _clip(float(metrics.get("confidence", metrics.get("credibility", 0.5)) or 0.5), 0.0, 1.0)

            old_regret = self._regret_ewma.get(strategy, regret_raw)
            old_conf = self._confidence_ewma.get(strategy, conf_raw)
            regret_ewma = alpha * regret_raw + (1.0 - alpha) * old_regret
            conf_ewma = alpha * conf_raw + (1.0 - alpha) * old_conf
            self._regret_ewma[strategy] = float(regret_ewma)
            self._confidence_ewma[strategy] = float(conf_ewma)

            credibility = _clip(conf_ewma * (1.0 - regret_ewma), 0.0, 1.0)
            prev_credibility = self._credibility_prev.get(strategy, credibility)
            rel_change = abs(credibility - prev_credibility) / max(1e-6, abs(prev_credibility))
            self._credibility_prev[strategy] = float(credibility)

            if rel_change < float(self.config.hysteresis_relative_change):
                # Hold close to previous allocation inside hysteresis band.
                hysteresis_active = True
                if strategy in prev:
                    out[strategy] = float(0.80 * prev[strategy] + 0.20 * weight)
                continue

            # Outside hysteresis band, apply smooth credibility multiplier.
            out[strategy] = float(weight * (0.65 + 0.70 * credibility))

        # Bound per-cycle changes to prevent sudden swings.
        cap = float(self.config.max_weight_shift_per_cycle)
        for strategy, weight in list(out.items()):
            old = float(prev.get(strategy, 0.0))
            delta = weight - old
            if abs(delta) > cap:
                max_delta_applied = True
                out[strategy] = float(old + np.sign(delta) * cap)

        # Keep a gross exposure floor when meta confidence drops.
        gross = float(sum(abs(v) for v in out.values()))
        floor = max(0.0, float(allowed_gross_cap) * float(self.config.min_gross_exposure_floor))
        if floor > 0 and gross < floor and gross > 1e-12:
            scale = floor / gross
            out = {k: float(v * scale) for k, v in out.items()}
            floor_applied = True
        elif floor > 0 and gross <= 1e-12 and prev:
            prev_gross = float(sum(abs(v) for v in prev.values()))
            if prev_gross > 1e-12:
                scale = floor / prev_gross
                out = {k: float(v * scale) for k, v in prev.items()}
                floor_applied = True
                reason_codes.append("meta_floor_restored_from_previous")

        if hysteresis_active:
            reason_codes.append("meta_hysteresis_band_active")
        if max_delta_applied:
            reason_codes.append("meta_max_delta_cap_applied")
        if floor_applied:
            reason_codes.append("meta_gross_exposure_floor_applied")

        avg_regret = float(np.mean(list(self._regret_ewma.values()))) if self._regret_ewma else 0.0
        avg_conf = float(np.mean(list(self._confidence_ewma.values()))) if self._confidence_ewma else 0.0
        credibility_deltas = []
        for k in out.keys():
            metric_cred = float(strategy_metrics.get(k, {}).get("credibility", 0.5))
            prev_cred = float(self._credibility_prev.get(k, metric_cred))
            credibility_deltas.append(abs(prev_cred - metric_cred))
        proposed_gross = float(sum(abs(v) for v in proposed_weights.values()))
        out_gross = float(sum(abs(v) for v in out.values()))
        adjustment_multiplier = 1.0 if proposed_gross <= 1e-12 else float(out_gross / proposed_gross)
        feedback = {
            "regret_ewma": avg_regret,
            "confidence_ewma": avg_conf,
            "credibility_relative_change": float(np.mean(credibility_deltas)) if credibility_deltas else 0.0,
            "adjustment_multiplier": adjustment_multiplier,
            "hysteresis_active": bool(hysteresis_active),
            "max_delta_applied": bool(max_delta_applied),
            "exposure_floor_applied": bool(floor_applied),
            "reason_codes": reason_codes,
        }
        return out, feedback

    @staticmethod
    def _ewma_alpha(half_life_days: int) -> float:
        # alpha chosen so weight decays by 50% over half-life horizon.
        return float(1.0 - np.exp(np.log(0.5) / max(1, half_life_days)))
