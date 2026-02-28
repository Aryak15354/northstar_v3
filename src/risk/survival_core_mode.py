"""
Deterministic Survival-Core containment mode.

Purpose:
- Override normal allocation behavior during structural instability.
- Provide hard, non-negotiable containment directives.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Mapping, Optional, Tuple


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SurvivalCoreConfig:
    crisis_prob_activate: float = 0.60
    crisis_prob_deactivate: float = 0.40
    convexity_threshold: float = 0.15
    drawdown_critical: float = 0.12
    entropy_threshold_ratio: float = 0.75
    min_active_cycles: int = 3
    gross_clamp_fraction: float = 0.40
    vol_target_multiplier: float = 0.50
    short_convexity_threshold: float = 0.0


class SurvivalCoreMode:
    """
    Hard crash-containment logic.

    Activation:
    - Any 2 of 4 conditions.
    Exit:
    - Crisis prob < deactivate threshold AND drawdown < 50% of critical threshold,
      after minimum active cycles.
    """

    def __init__(self, config: Optional[SurvivalCoreConfig] = None) -> None:
        self.config = config or SurvivalCoreConfig()
        self.active: bool = False
        self.active_cycles: int = 0
        self.activated_at: Optional[str] = None
        self.last_reason_codes: list[str] = []

    def evaluate(
        self,
        *,
        crisis_probability: float,
        convexity_score: float,
        drawdown: float,
        entropy: float,
        n_states: int = 4,
    ) -> Dict[str, object]:
        max_entropy = 0.0
        if n_states > 1:
            # ln(K) upper bound; ratio threshold is applied to this scale.
            from math import log

            max_entropy = float(log(n_states))
        entropy_threshold = float(self.config.entropy_threshold_ratio * max_entropy)

        cond = {
            "crisis_probability": float(crisis_probability) > float(self.config.crisis_prob_activate),
            "convexity_score": float(convexity_score) > float(self.config.convexity_threshold),
            "drawdown": float(drawdown) > float(self.config.drawdown_critical),
            "entropy": float(entropy) > float(entropy_threshold),
        }
        trigger_count = int(sum(1 for v in cond.values() if bool(v)))
        reason_codes = [f"survival_trigger:{k}" for k, v in cond.items() if bool(v)]

        if not self.active:
            if trigger_count >= 2:
                self.active = True
                self.active_cycles = 1
                self.activated_at = _utc_iso()
                self.last_reason_codes = reason_codes or ["survival_trigger:unknown"]
        else:
            self.active_cycles += 1
            can_exit = self.active_cycles >= int(self.config.min_active_cycles)
            if can_exit and (
                float(crisis_probability) < float(self.config.crisis_prob_deactivate)
                and float(drawdown) < float(self.config.drawdown_critical) * 0.5
            ):
                self.active = False
                self.active_cycles = 0
                self.activated_at = None
                self.last_reason_codes = []
            elif reason_codes:
                self.last_reason_codes = reason_codes

        directives = {
            "gross_multiplier": float(self.config.gross_clamp_fraction) if self.active else 1.0,
            "disable_short_convexity": bool(self.active),
            "cvar_only": bool(self.active),
            "vol_target_multiplier": float(self.config.vol_target_multiplier) if self.active else 1.0,
            "meta_freeze_shrink_only": bool(self.active),
            "lock_new_risk": bool(self.active),
        }
        return {
            "active": bool(self.active),
            "active_cycles": int(self.active_cycles),
            "activated_at": self.activated_at,
            "trigger_count": int(trigger_count),
            "conditions": cond,
            "reason_codes": list(self.last_reason_codes),
            "directives": directives,
        }

    def apply_overrides(
        self,
        *,
        weights: Mapping[str, float],
        strategy_metadata: Mapping[str, Mapping[str, float | bool]] | None = None,
        allowed_gross_cap: float,
    ) -> Tuple[Dict[str, float], Dict[str, object]]:
        out = {k: float(v) for k, v in dict(weights).items()}
        strategy_metadata = strategy_metadata or {}
        report: Dict[str, object] = {
            "active": bool(self.active),
            "short_convexity_disabled": False,
            "gross_clamped": False,
            "reason_codes": list(self.last_reason_codes),
            "lock_new_risk": bool(self.active),
        }
        if not self.active:
            return out, report

        # Disable short-convexity exposures.
        disabled_count = 0
        for strategy, weight in list(out.items()):
            meta = strategy_metadata.get(strategy, {})
            if self._is_short_convexity(strategy, weight, meta):
                out[strategy] = 0.0
                disabled_count += 1
        if disabled_count > 0:
            report["short_convexity_disabled"] = True
            report["short_convexity_disabled_count"] = int(disabled_count)

        # Clamp gross exposure.
        gross = float(sum(abs(v) for v in out.values()))
        gross_cap = max(0.0, float(allowed_gross_cap) * float(self.config.gross_clamp_fraction))
        if gross > gross_cap and gross > 1e-12:
            scale = gross_cap / gross
            out = {k: float(v * scale) for k, v in out.items()}
            report["gross_clamped"] = True
            report["gross_scale"] = float(scale)
        report["gross_target_cap"] = float(gross_cap)
        report["gross_after"] = float(sum(abs(v) for v in out.values()))
        return out, report

    def _is_short_convexity(
        self,
        strategy: str,
        weight: float,
        meta: Mapping[str, float | bool],
    ) -> bool:
        # Optional explicit metadata wins.
        if bool(meta.get("is_short_convexity", False)):
            return True
        convexity_score = float(meta.get("convexity_score", 0.0) or 0.0)
        if convexity_score > float(self.config.short_convexity_threshold):
            # Treat positive capital assigned to negative-convexity strategy as disallowed.
            if float(weight) > 0:
                return True

        token = str(strategy or "").strip().lower()
        if not token:
            return False
        short_tokens = ("short", "iron_condor", "iron_butterfly", "strangle", "income", "carry")
        return any(t in token for t in short_tokens) and float(weight) > 0
