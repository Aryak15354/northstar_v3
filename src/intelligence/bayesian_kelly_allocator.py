"""
Always-feasible Bayesian Kelly allocator with tiered soft-constraint relaxation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np


@dataclass
class AllocatorConfig:
    max_leverage: float = 1.0
    min_confidence: float = 0.20
    drawdown_lambda: float = 5.0
    fallback_gross_fraction: float = 0.30
    valuation_bridge_enabled: bool = True
    valuation_beta: float = 0.12
    valuation_beta_min: float = 0.02
    valuation_beta_max: float = 0.35
    valuation_gap_clip: float = 0.50
    hard_limits: Dict[str, float] = field(
        default_factory=lambda: {
            "gross_cap": 1.0,
            "net_cap": 0.40,
        }
    )
    soft_limits: Dict[str, float] = field(
        default_factory=lambda: {
            "cvar_target": 0.24,
            "vol_target": 0.18,
            "drawdown_probability_max": 0.25,
            "liquidity_penalty_max": 0.70,
            "convexity_preference_max": 0.80,
        }
    )


class BayesianKellyAllocator:
    """
    Tiered allocator policy:
    1) honor hard constraints,
    2) attempt soft constraints,
    3) relax soft constraints by ladder,
    4) fallback heuristic (never halt cycle).
    """

    def __init__(self, config: Optional[AllocatorConfig] = None) -> None:
        self.config = config or AllocatorConfig()

    def allocate(
        self,
        regime_probs: Mapping[str, float],
        strategy_posteriors: Mapping[str, Mapping[str, float]],
        *,
        current_drawdown: float = 0.0,
        model_confidence: float = 1.0,
        hard_limits: Optional[Mapping[str, float]] = None,
        soft_limits: Optional[Mapping[str, float]] = None,
        valuation_inputs: Optional[Mapping[str, float]] = None,
        risk_veto_active: bool = False,
        veto_reasons: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        veto_reasons = list(veto_reasons or [])
        hard = {**self.config.hard_limits, **dict(hard_limits or {})}
        soft = {**self.config.soft_limits, **dict(soft_limits or {})}
        reason_codes: List[str] = []
        valuation_payload = self._normalize_valuation_inputs(valuation_inputs, regime_probs)

        if risk_veto_active:
            return {
                "weights": {k: 0.0 for k in strategy_posteriors.keys()},
                "used_fallback": False,
                "fallback_level": None,
                "reason_codes": ["hard_risk_veto_active", *veto_reasons],
                "hard_limits": hard,
                "soft_limits": soft,
                "metrics": {"valuation_bridge": valuation_payload},
            }

        try:
            base = self._base_weights(
                regime_probs=regime_probs,
                strategy_posteriors=strategy_posteriors,
                current_drawdown=current_drawdown,
                model_confidence=model_confidence,
                valuation_inputs=valuation_payload,
            )
            base = self._apply_hard_caps(base, hard)
            candidate, feasible, metrics = self._fit_to_soft_constraints(
                base, strategy_posteriors, soft, valuation_inputs=valuation_payload
            )
            if feasible:
                metrics["valuation_bridge"] = valuation_payload
                return {
                    "weights": candidate,
                    "used_fallback": False,
                    "fallback_level": None,
                    "reason_codes": reason_codes,
                    "hard_limits": hard,
                    "soft_limits": soft,
                    "metrics": metrics,
                }

            # Step 1: relax soft penalties (keep bounds).
            reason_codes.append("relax_soft_penalties")
            penalty_relaxed = self._base_weights(
                regime_probs=regime_probs,
                strategy_posteriors=strategy_posteriors,
                current_drawdown=current_drawdown,
                model_confidence=model_confidence,
                ignore_penalties=True,
                valuation_inputs=valuation_payload,
            )
            penalty_relaxed = self._apply_hard_caps(penalty_relaxed, hard)
            candidate, feasible, metrics = self._fit_to_soft_constraints(
                penalty_relaxed, strategy_posteriors, soft, valuation_inputs=valuation_payload
            )
            if feasible:
                metrics["valuation_bridge"] = valuation_payload
                return {
                    "weights": candidate,
                    "used_fallback": False,
                    "fallback_level": "tier1_relax_penalties",
                    "reason_codes": reason_codes,
                    "hard_limits": hard,
                    "soft_limits": soft,
                    "metrics": metrics,
                }

            # Step 2: widen soft bounds.
            reason_codes.append("widen_soft_bounds")
            soft_wide = dict(soft)
            for key in list(soft_wide.keys()):
                soft_wide[key] = float(soft_wide[key]) * 1.35
            candidate, feasible, metrics = self._fit_to_soft_constraints(
                penalty_relaxed, strategy_posteriors, soft_wide, valuation_inputs=valuation_payload
            )
            if feasible:
                metrics["valuation_bridge"] = valuation_payload
                return {
                    "weights": candidate,
                    "used_fallback": False,
                    "fallback_level": "tier2_widen_bounds",
                    "reason_codes": reason_codes,
                    "hard_limits": hard,
                    "soft_limits": soft_wide,
                    "metrics": metrics,
                }

            # Step 3: drop lowest-priority soft constraints.
            reason_codes.append("drop_low_priority_soft_constraints")
            soft_reduced = {
                "vol_target": float(soft_wide.get("vol_target", 0.20)),
            }
            candidate, feasible, metrics = self._fit_to_soft_constraints(
                penalty_relaxed, strategy_posteriors, soft_reduced, valuation_inputs=valuation_payload
            )
            if feasible:
                metrics["valuation_bridge"] = valuation_payload
                return {
                    "weights": candidate,
                    "used_fallback": False,
                    "fallback_level": "tier3_drop_constraints",
                    "reason_codes": reason_codes,
                    "hard_limits": hard,
                    "soft_limits": soft_reduced,
                    "metrics": metrics,
                }

            # Step 4: safe heuristic fallback.
            reason_codes.append("fallback_heuristic_allocation")
            fallback = self._heuristic_fallback(strategy_posteriors, hard)
            fallback = self._apply_hard_caps(fallback, hard)
            metrics = self._compute_soft_metrics(fallback, strategy_posteriors, valuation_inputs=valuation_payload)
            metrics["valuation_bridge"] = valuation_payload
            return {
                "weights": fallback,
                "used_fallback": True,
                "fallback_level": "tier4_safe_heuristic",
                "reason_codes": reason_codes,
                "hard_limits": hard,
                "soft_limits": soft_reduced,
                "metrics": metrics,
            }
        except Exception as exc:
            fallback = self._heuristic_fallback(strategy_posteriors, hard)
            fallback = self._apply_hard_caps(fallback, hard)
            return {
                "weights": fallback,
                "used_fallback": True,
                "fallback_level": "exception_safe_heuristic",
                "reason_codes": ["allocator_exception", str(exc)],
                "hard_limits": hard,
                "soft_limits": soft,
                "metrics": {
                    **self._compute_soft_metrics(fallback, strategy_posteriors, valuation_inputs=valuation_payload),
                    "valuation_bridge": valuation_payload,
                },
            }

    def _base_weights(
        self,
        regime_probs: Mapping[str, float],
        strategy_posteriors: Mapping[str, Mapping[str, float]],
        current_drawdown: float,
        model_confidence: float,
        ignore_penalties: bool = False,
        valuation_inputs: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, float]:
        confidence = max(float(model_confidence), float(self.config.min_confidence))
        dd_modifier = float(np.exp(-self.config.drawdown_lambda * max(0.0, float(current_drawdown))))
        val = self._normalize_valuation_inputs(valuation_inputs, regime_probs)
        out: Dict[str, float] = {}
        for strategy, stats in strategy_posteriors.items():
            mu_signal = float(stats.get("posterior_mean", 0.0) or 0.0)
            post_var = float(stats.get("posterior_variance", 0.0) or 0.0)
            vol = max(float(stats.get("volatility", 0.0) or 0.0), 1e-6)
            credibility = float(stats.get("credibility", 0.5) or 0.5)
            regime_multiplier = float(self._regime_multiplier(strategy, regime_probs, stats))
            alignment = float(stats.get("valuation_alignment", val.get("default_alignment", 1.0)) or 1.0)
            alignment = float(np.clip(alignment, -2.0, 2.0))
            mu_total = mu_signal + float(val.get("beta", 0.0)) * float(val.get("gap", 0.0)) * alignment * float(
                val.get("macro_compression", 1.0)
            )
            # Closed-form bridge: gamma = beta^2
            sigma_eff_sq = (vol ** 2) + post_var + float(val.get("gamma", 0.0)) * float(val.get("variance", 0.0))
            kelly = mu_total / (sigma_eff_sq + 1e-8)
            penalty = 1.0
            if not ignore_penalties:
                penalty *= float(stats.get("crowding_penalty", 1.0) or 1.0)
                penalty *= float(stats.get("convexity_penalty", 1.0) or 1.0)
            out[strategy] = float(kelly * regime_multiplier * dd_modifier * confidence * credibility * penalty)
        return out

    def _regime_multiplier(
        self,
        strategy: str,
        regime_probs: Mapping[str, float],
        stats: Mapping[str, float],
    ) -> float:
        # Optional direct mapping in stats.
        if "regime_multiplier" in stats:
            return float(stats.get("regime_multiplier", 1.0) or 1.0)

        s = strategy.lower()
        default_map = {
            "short_vol": {"LOW_VOL": 1.2, "HIGH_VOL": 0.9, "CRISIS": 0.1, "TRANSITION": 0.7},
            "long_vol": {"LOW_VOL": 0.4, "HIGH_VOL": 1.0, "CRISIS": 1.6, "TRANSITION": 1.2},
            "dispersion": {"LOW_VOL": 0.9, "HIGH_VOL": 1.0, "CRISIS": 0.8, "TRANSITION": 1.1},
        }
        key = "short_vol" if "short" in s else ("long_vol" if "long" in s else ("dispersion" if "dispersion" in s else "dispersion"))
        mapping = default_map[key]
        return float(sum(float(prob) * float(mapping.get(regime, 1.0)) for regime, prob in regime_probs.items()))

    def _apply_hard_caps(self, weights: Mapping[str, float], hard: Mapping[str, float]) -> Dict[str, float]:
        out = {k: float(v) for k, v in weights.items()}
        if not out:
            return out
        gross_cap = max(0.0, float(hard.get("gross_cap", self.config.max_leverage)))
        net_cap = max(0.0, float(hard.get("net_cap", 1.0)))
        gross = float(sum(abs(v) for v in out.values()))
        if gross > gross_cap and gross > 1e-12:
            scale = gross_cap / gross
            out = {k: v * scale for k, v in out.items()}
        net = float(sum(out.values()))
        if abs(net) > net_cap and abs(net) > 1e-12:
            delta = (abs(net) - net_cap) * np.sign(net)
            gross_nonzero = float(sum(abs(v) for v in out.values()))
            if gross_nonzero > 1e-12:
                out = {k: v - (abs(v) / gross_nonzero) * delta for k, v in out.items()}
        return out

    def _fit_to_soft_constraints(
        self,
        weights: Mapping[str, float],
        strategy_posteriors: Mapping[str, Mapping[str, float]],
        soft_limits: Mapping[str, float],
        valuation_inputs: Optional[Mapping[str, float]] = None,
    ) -> Tuple[Dict[str, float], bool, Dict[str, float]]:
        w = {k: float(v) for k, v in weights.items()}
        if not w:
            return w, True, {}
        for _ in range(30):
            metrics = self._compute_soft_metrics(w, strategy_posteriors, valuation_inputs=valuation_inputs)
            scale = 1.0
            if "cvar_target" in soft_limits and metrics["cvar_proxy"] > float(soft_limits["cvar_target"]):
                scale = min(scale, float(soft_limits["cvar_target"]) / max(metrics["cvar_proxy"], 1e-12))
            if "vol_target" in soft_limits and metrics["vol_proxy"] > float(soft_limits["vol_target"]):
                scale = min(scale, float(soft_limits["vol_target"]) / max(metrics["vol_proxy"], 1e-12))
            if (
                "drawdown_probability_max" in soft_limits
                and metrics["drawdown_probability_proxy"] > float(soft_limits["drawdown_probability_max"])
            ):
                scale = min(
                    scale,
                    float(soft_limits["drawdown_probability_max"]) / max(metrics["drawdown_probability_proxy"], 1e-12),
                )
            if (
                "liquidity_penalty_max" in soft_limits
                and metrics["liquidity_penalty"] > float(soft_limits["liquidity_penalty_max"])
            ):
                scale = min(scale, float(soft_limits["liquidity_penalty_max"]) / max(metrics["liquidity_penalty"], 1e-12))
            if (
                "convexity_preference_max" in soft_limits
                and metrics["convexity_proxy"] > float(soft_limits["convexity_preference_max"])
            ):
                scale = min(scale, float(soft_limits["convexity_preference_max"]) / max(metrics["convexity_proxy"], 1e-12))

            if scale >= 0.999:
                return w, True, metrics
            shrink = max(0.50, min(0.98, float(scale)))
            w = {k: v * shrink for k, v in w.items()}
        return w, False, self._compute_soft_metrics(w, strategy_posteriors, valuation_inputs=valuation_inputs)

    def _compute_soft_metrics(
        self,
        weights: Mapping[str, float],
        strategy_posteriors: Mapping[str, Mapping[str, float]],
        valuation_inputs: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, float]:
        val = self._normalize_valuation_inputs(valuation_inputs, {})
        vol_proxy_sq = 0.0
        cvar_proxy = 0.0
        liquidity_penalty = 0.0
        convexity_proxy = 0.0
        mean_return = 0.0
        for strategy, weight in weights.items():
            stats = strategy_posteriors.get(strategy, {})
            vol = max(float(stats.get("volatility", 0.0) or 0.0), 1e-6)
            mu_signal = float(stats.get("posterior_mean", 0.0) or 0.0)
            liquidity = float(stats.get("liquidity_score", 0.3) or 0.3)
            convexity = float(stats.get("convexity_score", 0.2) or 0.2)
            alignment = float(stats.get("valuation_alignment", val.get("default_alignment", 1.0)) or 1.0)
            alignment = float(np.clip(alignment, -2.0, 2.0))
            mu_total = mu_signal + float(val.get("beta", 0.0)) * float(val.get("gap", 0.0)) * alignment * float(
                val.get("macro_compression", 1.0)
            )
            sigma_eff = float(np.sqrt(max(vol ** 2 + float(val.get("gamma", 0.0)) * float(val.get("variance", 0.0)), 1e-12)))
            vol_proxy_sq += (float(weight) * sigma_eff) ** 2
            cvar_proxy += abs(float(weight)) * sigma_eff * 2.33
            liquidity_penalty += abs(float(weight)) * max(0.0, liquidity)
            convexity_proxy += abs(float(weight)) * max(0.0, convexity)
            mean_return += float(weight) * mu_total

        vol_proxy = float(np.sqrt(max(vol_proxy_sq, 0.0)))
        dd_prob_proxy = float(np.clip(0.5 + (cvar_proxy - max(mean_return, -0.5)) * 0.5, 0.0, 1.0))
        return {
            "vol_proxy": vol_proxy,
            "cvar_proxy": float(cvar_proxy),
            "liquidity_penalty": float(liquidity_penalty),
            "convexity_proxy": float(convexity_proxy),
            "drawdown_probability_proxy": dd_prob_proxy,
            "expected_return_proxy": float(mean_return),
            "valuation_mu_shift_proxy": float(val.get("beta", 0.0) * val.get("gap", 0.0) * val.get("macro_compression", 1.0)),
            "valuation_sigma_penalty_proxy": float(val.get("gamma", 0.0) * val.get("variance", 0.0)),
        }

    def _normalize_valuation_inputs(
        self,
        valuation_inputs: Optional[Mapping[str, float]],
        regime_probs: Mapping[str, float],
    ) -> Dict[str, float]:
        default = {
            "enabled": False,
            "gap": 0.0,
            "variance": 0.0,
            "macro_compression": 1.0,
            "beta": 0.0,
            "gamma": 0.0,
            "default_alignment": 1.0,
            "market_percentile": 0.5,
            "bubble_probability": 0.0,
        }
        if not self.config.valuation_bridge_enabled:
            return default

        raw = dict(valuation_inputs or {})
        gap = float(raw.get("posterior_gap", raw.get("gap", 0.0)) or 0.0)
        gap = float(np.clip(gap, -float(self.config.valuation_gap_clip), float(self.config.valuation_gap_clip)))
        variance = max(0.0, float(raw.get("posterior_variance", raw.get("variance", 0.0)) or 0.0))
        market_percentile = float(np.clip(float(raw.get("market_percentile", 0.5) or 0.5), 0.0, 1.0))
        macro_compression = float(raw.get("macro_compression", 1.0) or 1.0)
        macro_compression = float(np.clip(macro_compression, 0.50, 1.50))
        bubble_probability = float(np.clip(float(raw.get("bubble_probability", 0.0) or 0.0), 0.0, 1.0))
        crisis_prob = float(np.clip(float(regime_probs.get("CRISIS", 0.0) or 0.0), 0.0, 1.0))

        beta_base = float(raw.get("beta", self.config.valuation_beta) or self.config.valuation_beta)
        beta_scaled = beta_base * (1.0 - 0.50 * crisis_prob) * (1.0 - 0.35 * bubble_probability)
        beta = float(np.clip(beta_scaled, self.config.valuation_beta_min, self.config.valuation_beta_max))
        gamma = float(beta ** 2)
        return {
            "enabled": True,
            "gap": gap,
            "variance": variance,
            "macro_compression": macro_compression,
            "beta": beta,
            "gamma": gamma,
            "default_alignment": float(raw.get("default_alignment", 1.0) or 1.0),
            "market_percentile": market_percentile,
            "bubble_probability": bubble_probability,
        }

    def _heuristic_fallback(
        self,
        strategy_posteriors: Mapping[str, Mapping[str, float]],
        hard: Mapping[str, float],
    ) -> Dict[str, float]:
        if not strategy_posteriors:
            return {}
        gross_cap = max(0.0, float(hard.get("gross_cap", 1.0)))
        gross_target = gross_cap * float(self.config.fallback_gross_fraction)
        if gross_target <= 0:
            return {k: 0.0 for k in strategy_posteriors.keys()}

        scored: List[Tuple[str, float]] = []
        for strategy, stats in strategy_posteriors.items():
            sharpe = float(stats.get("adjusted_sharpe", 0.0) or 0.0)
            credibility = float(stats.get("credibility", 0.0) or 0.0)
            score = max(0.0, sharpe) * max(0.0, credibility)
            if score > 0:
                scored.append((strategy, score))

        if not scored:
            return {k: 0.0 for k in strategy_posteriors.keys()}

        scored.sort(key=lambda x: x[1], reverse=True)
        keep = scored[: min(4, len(scored))]
        total = float(sum(x[1] for x in keep))
        if total <= 1e-12:
            return {k: 0.0 for k in strategy_posteriors.keys()}

        out = {k: 0.0 for k in strategy_posteriors.keys()}
        for strategy, score in keep:
            out[strategy] = gross_target * (score / total)
        return out
