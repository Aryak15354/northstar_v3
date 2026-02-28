"""
Northstar V4 AlphaOS adapter.

Law A1 enforcement:
- Adapter is extension-only.
- It consumes canonical state/artifacts only.
- It does not ingest/rebuild raw market feeds.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub
from src.intelligence.bayesian_kelly_allocator import AllocatorConfig, BayesianKellyAllocator
from src.intelligence.flow_analysis_engine import FlowAnalysisEngine
from src.intelligence.meta_allocator import MetaAllocator, MetaAllocatorConfig
from src.intelligence.strategy_edge_engine import EdgeEngineConfig, StrategyEdgeEngine
from src.models.regime_probability_engine import RegimeProbabilityEngine
from src.models.vol_carry_forecaster import VolCarryForecaster
from src.options.dispersion_engine import DispersionEngine
from src.options.vol_surface_intelligence import VolSurfaceIntelligence
from src.portfolio.strategy_correlation_engine import StrategyCorrelationEngine
from src.risk.portfolio_risk_controller import PortfolioRiskController
from src.risk.survival_core_mode import SurvivalCoreConfig, SurvivalCoreMode
from src.risk.stress_scenario_engine import StressScenarioEngine
from src.validation.regime_drift_monitor import RegimeDriftConfig, RegimeDriftMonitor
from src.validation.shadow_divergence_index import SDIConfig, ShadowDivergenceIndex
from src.volatility.alpha_os_types import (
    AllocationIntent,
    AlphaOSContext,
    MetaFeedback,
    RegimeProbabilitySnapshot,
    RiskBudgetSnapshot,
    StrategyPosterior,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        out = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if out.tzinfo is None:
            return out.replace(tzinfo=timezone.utc)
        return out.astimezone(timezone.utc)
    except Exception:
        return None


def _entropy_from_probs(regime_probs: Mapping[str, float]) -> float:
    if not regime_probs:
        return 0.0
    arr = np.asarray([float(v) for v in regime_probs.values()], dtype=float)
    arr = np.clip(arr, 1e-12, None)
    arr = arr / arr.sum()
    return float(-np.sum(arr * np.log(arr)))


class AlphaOSAdapter:
    def __init__(self, project_root: Path, config: Any) -> None:
        self.project_root = Path(project_root)
        self.config = config
        self.data_hub = V3DataHub(project_root=self.project_root)

        self.regime_engine = RegimeProbabilityEngine(model_path=self.project_root / config.hmm_model_path)
        self.vol_surface = VolSurfaceIntelligence()
        self.flow_engine = FlowAnalysisEngine()
        self.edge_engine = StrategyEdgeEngine(EdgeEngineConfig())
        self.allocator = BayesianKellyAllocator(
            AllocatorConfig(
                valuation_bridge_enabled=bool(getattr(config, "valuation_bridge_enabled", True)),
                valuation_beta=float(getattr(config, "valuation_beta", 0.12) or 0.12),
            )
        )
        self.meta_allocator = MetaAllocator(
            MetaAllocatorConfig(
                regret_half_life_days=int(config.meta_regret_half_life_days),
                hysteresis_relative_change=float(config.meta_hysteresis_relative_change),
                max_weight_shift_per_cycle=float(config.meta_max_weight_shift_per_cycle),
                min_gross_exposure_floor=float(config.meta_min_gross_exposure_floor),
            )
        )
        self.dispersion_engine = DispersionEngine()
        self.correlation_engine = StrategyCorrelationEngine(max_pairwise_corr=0.70)
        self.vol_carry = VolCarryForecaster()
        self.stress_engine = StressScenarioEngine()
        self.risk_controller = PortfolioRiskController()
        self.survival_core = SurvivalCoreMode(SurvivalCoreConfig())
        self.regime_drift_monitor = RegimeDriftMonitor(
            RegimeDriftConfig(),
            state_path=self.project_root / "data/processed/regime_drift_monitor.json",
        )
        self.shadow_divergence = ShadowDivergenceIndex(
            SDIConfig(),
            state_path=self.project_root / "data/processed/shadow_divergence_index.json",
        )
        self._last_regime_probs: Optional[List[float]] = None

    def evaluate_cycle(self, context: AlphaOSContext) -> AllocationIntent:
        now = _utc_now()
        mode = self._mode()
        contract_ok, contract_reason, canonical_payload = self._validate_contract(context, now)
        legacy_alloc = self._load_legacy_allocation(canonical_payload)

        if not contract_ok:
            return AllocationIntent(
                timestamp=_to_iso(now),
                mode="blocked_contract_violation",
                strategy_weights=dict(legacy_alloc),
                gross_target=float(sum(abs(v) for v in legacy_alloc.values())),
                net_target=float(sum(legacy_alloc.values())),
                used_fallback=True,
                fallback_level="contract_block",
                reason_codes=["adapter_contract_blocked", contract_reason],
                diagnostics={"contract": {"ok": False, "reason": contract_reason}},
                legacy_allocation=canonical_payload.get("capital_allocations", {}),
            )

        canonical_state = context.canonical_state
        chain_cache = context.additional_inputs.get("chain_cache", {})
        primary_chain = self._primary_chain(chain_cache)
        iv_hist = context.additional_inputs.get("iv_series", [])
        realized_vol = context.additional_inputs.get("realized_vol")

        surface = self.vol_surface.compute(primary_chain, iv_history=iv_hist, realized_vol=realized_vol)
        regime_features = self._regime_features(canonical_state, surface)
        regime_raw = self.regime_engine.predict(regime_features, prev_probs=self._last_regime_probs)
        regime_probs = regime_raw.get("probabilities", {}) or {}
        self._last_regime_probs = [float(v) for _, v in sorted(regime_probs.items(), key=lambda x: x[0])]
        regime_snapshot = RegimeProbabilitySnapshot(
            timestamp=str(regime_raw.get("timestamp")),
            probabilities={k: float(v) for k, v in regime_probs.items()},
            confidence=float(regime_raw.get("confidence", 0.0) or 0.0),
            source=str(regime_raw.get("source", "unknown")),
            model_path=str(regime_raw.get("model_path", "")),
            model_version=str(regime_raw.get("model_version", "")),
            stale=bool(regime_raw.get("stale", False)),
            reason_codes=list(regime_raw.get("reason_codes", []) or []),
        )
        dominant_regime = (
            max(regime_probs.items(), key=lambda item: float(item[1]))[0]
            if regime_probs
            else "TRANSITION"
        )
        drift = self.regime_drift_monitor.update(
            feature_vector=regime_features,
            regime_probs=regime_probs,
            model=self.regime_engine.model,
            dominant_regime=dominant_regime,
        )

        flow = self.flow_engine.compute_crowding_score(
            primary_chain,
            skew_extremity=abs(float(surface.get("skew_curvature", 0.0))),
            iv_percentile=float(surface.get("iv_percentile_252d", 0.5)),
        )
        closed_positions = canonical_state.get("closed_positions", []) if isinstance(canonical_state, dict) else []
        returns_by_strategy = self._returns_by_strategy(closed_positions)
        strategy_metrics = self._strategy_metrics_payload(canonical_payload)
        crowding_scores = {k: float(flow["crowding_score"]) for k in returns_by_strategy.keys()}
        convexity_scores = {k: float(abs(surface.get("skew_curvature", 0.0))) for k in returns_by_strategy.keys()}

        posteriors = self.edge_engine.estimate(
            returns_by_strategy=returns_by_strategy,
            regime_probs=regime_probs,
            crowding_scores=crowding_scores,
            convexity_scores=convexity_scores,
        )
        if not posteriors:
            posteriors = {k: v for k, v in self.edge_engine.estimate({"legacy_core": [0.0]}, regime_probs).items()}
        posteriors = self._apply_valuation_alignment(posteriors)
        valuation_bridge = self._load_valuation_bridge_inputs()
        valuation_bridge["beta"] = float(getattr(self.config, "valuation_beta", 0.12) or 0.12)

        portfolio_greeks = canonical_state.get("portfolio_greeks", {}) if isinstance(canonical_state, dict) else {}
        weekly_risk = canonical_state.get("weekly_risk_usage", {}) if isinstance(canonical_state, dict) else {}
        spot_sigma = max(0.01, float(surface.get("vol_of_vol_proxy", 0.0)) + 0.10)
        stress = self.stress_engine.evaluate(
            delta=float(portfolio_greeks.get("delta", 0.0) or 0.0),
            gamma=float(portfolio_greeks.get("gamma", 0.0) or 0.0),
            vega=float(portfolio_greeks.get("vega", 0.0) or 0.0),
            theta=float(portfolio_greeks.get("theta", 0.0) or 0.0),
            portfolio_value=max(1.0, float(context.additional_inputs.get("current_equity", 0.0) or 0.0) or 1.0),
            spot_sigma=spot_sigma,
        )
        risk = self.risk_controller.evaluate_convexity_budget(
            delta_exposure=float(portfolio_greeks.get("delta", 0.0) or 0.0),
            gamma_exposure=float(portfolio_greeks.get("gamma", 0.0) or 0.0),
            vega_exposure=float(portfolio_greeks.get("vega", 0.0) or 0.0),
            underlying_vol=max(0.01, float(surface.get("term_structure_slope", 0.0)) + 0.15),
            vol_of_vol=float(surface.get("vol_of_vol_proxy", 0.0) or 0.0),
            liquidity_spread_pct=float(context.additional_inputs.get("liquidity_spread_pct", 0.0) or 0.0),
            portfolio_value=max(1.0, float(context.additional_inputs.get("current_equity", 0.0) or 0.0) or 1.0),
            gap_risk_score=float(stress.get("gap_risk_score", 0.0) or 0.0),
        )

        hard_limits = {
            "gross_cap": float(context.max_gross_cap),
            "net_cap": float(context.max_net_cap),
        }
        soft_limits = {
            "vol_target": 0.18,
            "cvar_target": 0.24,
            "drawdown_probability_max": 0.25,
            "liquidity_penalty_max": 0.70,
            "convexity_preference_max": 0.80,
        }
        if bool(drift.get("drift_detected", False)):
            reduction = float((drift.get("recommended_actions", {}) or {}).get("gross_reduction_fraction", 0.0) or 0.0)
            hard_limits["gross_cap"] = max(0.0, hard_limits["gross_cap"] * (1.0 - reduction))

        drawdown = max(0.0, float(context.current_drawdown))
        model_confidence = float(regime_snapshot.confidence)
        if bool(drift.get("drift_detected", False)):
            model_confidence = max(0.1, model_confidence * 0.8)
        allocator_result = self.allocator.allocate(
            regime_probs=regime_probs,
            strategy_posteriors=posteriors,
            current_drawdown=drawdown,
            model_confidence=model_confidence,
            hard_limits=hard_limits,
            soft_limits=soft_limits,
            valuation_inputs=valuation_bridge,
            risk_veto_active=bool(context.risk_veto_active or risk.get("veto_active", False)),
            veto_reasons=list(context.risk_veto_reasons) + list(risk.get("veto_reasons", [])),
        )

        base_weights = allocator_result.get("weights", {}) or {}
        prev_weights = context.current_weights or legacy_alloc
        meta_adjusted, meta_feedback_raw = self.meta_allocator.apply(
            proposed_weights=base_weights,
            strategy_metrics=self._merge_strategy_meta_inputs(posteriors, strategy_metrics),
            allowed_gross_cap=float(context.max_gross_cap),
            previous_weights=prev_weights,
        )

        survival_state = self.survival_core.evaluate(
            crisis_probability=float(regime_probs.get("CRISIS", 0.0) or 0.0),
            convexity_score=float(risk.get("convexity_score", 0.0) or 0.0),
            drawdown=drawdown,
            entropy=_entropy_from_probs(regime_probs),
            n_states=max(2, len(regime_probs) or 4),
        )
        strategy_meta = {
            strategy: {
                "convexity_score": float(stats.get("convexity_score", 0.0) or 0.0),
                "is_short_convexity": ("short" in strategy.lower() or "income" in strategy.lower()),
            }
            for strategy, stats in posteriors.items()
        }
        alpha_weights, survival_directives = self.survival_core.apply_overrides(
            weights=meta_adjusted,
            strategy_metadata=strategy_meta,
            allowed_gross_cap=float(context.max_gross_cap),
        )

        final_weights = alpha_weights if mode == "enforce" else dict(legacy_alloc)
        if mode == "shadow":
            final_weights = dict(legacy_alloc)
        elif mode == "disabled":
            final_weights = dict(legacy_alloc)

        strategy_posteriors = [
            StrategyPosterior(
                strategy_name=name,
                posterior_mean=float(stats.get("posterior_mean", 0.0)),
                posterior_variance=float(stats.get("posterior_variance", 0.0)),
                volatility=float(stats.get("volatility", 0.0)),
                adjusted_sharpe=float(stats.get("adjusted_sharpe", 0.0)),
                credibility=float(stats.get("credibility", 0.0)),
                crowding_penalty=float(stats.get("crowding_penalty", 1.0)),
                convexity_penalty=float(stats.get("convexity_penalty", 1.0)),
                information_ratio=float(strategy_metrics.get(name, {}).get("information_ratio", 0.0)),
            )
            for name, stats in posteriors.items()
        ]
        risk_snapshot = RiskBudgetSnapshot(
            gross_cap=float(context.max_gross_cap),
            net_cap=float(context.max_net_cap),
            gross_used=float(sum(abs(v) for v in final_weights.values())),
            net_used=float(sum(final_weights.values())),
            convexity_score=float(risk.get("convexity_score", 0.0)),
            gap_risk_score=float(risk.get("gap_risk_score", 0.0)),
            crowding_score=float(flow.get("crowding_score", 0.0)),
            liquidity_adjusted_vega=float(risk.get("liquidity_adjusted_vega", 0.0)),
            veto_active=bool(context.risk_veto_active or risk.get("veto_active", False)),
            veto_reasons=list(context.risk_veto_reasons) + list(risk.get("veto_reasons", [])),
            hard_limits={k: float(v) for k, v in hard_limits.items()},
            soft_limits={k: float(v) for k, v in soft_limits.items()},
        )
        meta_feedback = MetaFeedback(
            regret_ewma=float(meta_feedback_raw.get("regret_ewma", 0.0)),
            confidence_ewma=float(meta_feedback_raw.get("confidence_ewma", 0.0)),
            credibility_relative_change=float(meta_feedback_raw.get("credibility_relative_change", 0.0)),
            adjustment_multiplier=float(meta_feedback_raw.get("adjustment_multiplier", 1.0)),
            hysteresis_active=bool(meta_feedback_raw.get("hysteresis_active", False)),
            max_delta_applied=bool(meta_feedback_raw.get("max_delta_applied", False)),
            exposure_floor_applied=bool(meta_feedback_raw.get("exposure_floor_applied", False)),
            reason_codes=list(meta_feedback_raw.get("reason_codes", [])),
        )

        carry = self.vol_carry.forecast(
            implied_vol=max(0.01, float(surface.get("iv_percentile_252d", 0.5)) + 0.12),
            expected_realized_vol=max(0.01, float(realized_vol or 0.12)),
            term_slope=float(surface.get("term_structure_slope", 0.0)),
            skew_decay=-float(surface.get("skew_curvature", 0.0)),
            seasonality_score=float(context.additional_inputs.get("seasonality_score", 0.0) or 0.0),
        )
        dispersion = self._dispersion_payload(context)
        corr = self.correlation_engine.compute({k: v for k, v in returns_by_strategy.items() if len(v) >= 3})
        alpha_expected_return = self._expected_return(alpha_weights, posteriors)
        legacy_expected_return = self._expected_return(legacy_alloc, posteriors)
        legacy_convexity = self._legacy_convexity_proxy(context, risk)
        sdi = self.shadow_divergence.update(
            alpha_weights=alpha_weights,
            legacy_weights=legacy_alloc,
            alpha_convexity=float(risk.get("convexity_score", 0.0) or 0.0),
            legacy_convexity=float(legacy_convexity),
            alpha_expected_return=float(alpha_expected_return),
            legacy_expected_return=float(legacy_expected_return),
            regime_label=dominant_regime,
        )

        reason_codes = list(allocator_result.get("reason_codes", []))
        reason_codes.extend(meta_feedback.reason_codes)
        if bool(drift.get("drift_detected", False)):
            reason_codes.append("regime_drift_detected")
        if bool(survival_state.get("active", False)):
            reason_codes.append("survival_core_active")
        if float(sdi.get("sdi", 0.0) or 0.0) > 0.35:
            reason_codes.append("shadow_divergence_elevated")
        if mode == "shadow":
            reason_codes.append("shadow_mode_dual_write")
        if mode == "disabled":
            reason_codes.append("alpha_os_disabled")

        return AllocationIntent(
            timestamp=_to_iso(now),
            mode=mode,
            strategy_weights={k: float(v) for k, v in final_weights.items()},
            gross_target=float(sum(abs(v) for v in final_weights.values())),
            net_target=float(sum(final_weights.values())),
            used_fallback=bool(allocator_result.get("used_fallback", False)),
            fallback_level=allocator_result.get("fallback_level"),
            reason_codes=reason_codes,
            diagnostics={
                "contract": {"ok": True, "reason": "ok"},
                "surface": surface,
                "flow": flow,
                "stress": stress,
                "allocator_metrics": allocator_result.get("metrics", {}),
                "valuation_bridge": valuation_bridge,
                "carry": carry,
                "dispersion": dispersion,
                "strategy_correlation": corr,
                "drift": drift,
                "survival_core": {
                    "state": survival_state,
                    "directives_applied": survival_directives,
                },
                "shadow_divergence_index": sdi,
                "alpha_os_weights": {k: float(v) for k, v in alpha_weights.items()},
                "legacy_weights": {k: float(v) for k, v in legacy_alloc.items()},
            },
            regime_snapshot=regime_snapshot,
            strategy_posteriors=strategy_posteriors,
            risk_budget=risk_snapshot,
            meta_feedback=meta_feedback,
            legacy_allocation=canonical_payload.get("capital_allocations", {}),
        )

    def _mode(self) -> str:
        if not bool(self.config.enabled):
            return "disabled"
        if bool(self.config.enforce_mode):
            return "enforce"
        if bool(self.config.shadow_mode):
            return "shadow"
        return "shadow"

    def _validate_contract(
        self,
        context: AlphaOSContext,
        now: datetime,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        required_state_keys = [
            "timestamp",
            "portfolio_greeks",
            "weekly_risk_usage",
            "portfolio_risk_usage",
            "options_cycle",
        ]
        state = context.canonical_state if isinstance(context.canonical_state, dict) else {}
        for key in required_state_keys:
            if key not in state:
                return False, f"missing_canonical_state_key:{key}", {}

        max_age = int(self.config.canonical_state_max_age_seconds)
        ts = _parse_ts(str(state.get("timestamp", "")))
        if ts is None:
            return False, "invalid_canonical_state_timestamp", {}
        age_sec = (now - ts).total_seconds()
        if age_sec > max_age:
            return False, f"stale_canonical_state:{int(age_sec)}s>{max_age}s", {}

        cap_path = self.project_root / "data/processed/capital_allocations.json"
        regime_path = self.project_root / "data/processed/regime_intelligence_feed.json"
        for path in [cap_path, regime_path]:
            if not path.exists():
                return False, f"missing_canonical_artifact:{path.name}", {}
            age = now.timestamp() - path.stat().st_mtime
            if age > max_age:
                return False, f"stale_canonical_artifact:{path.name}:{int(age)}s>{max_age}s", {}

        payload = {
            "capital_allocations": self.data_hub.capital_allocations() or {},
            "regime_intelligence_feed": self.data_hub.regime_intelligence_feed() or {},
        }
        return True, "ok", payload

    def _load_legacy_allocation(self, canonical_payload: Mapping[str, Any]) -> Dict[str, float]:
        cap = canonical_payload.get("capital_allocations", {}) if isinstance(canonical_payload, dict) else {}
        if not isinstance(cap, dict):
            return {}
        for key in ["strategy_allocations", "allocations", "weights", "allocation_weights"]:
            value = cap.get(key)
            if isinstance(value, dict):
                return {str(k): float(v) for k, v in value.items() if self._is_number(v)}
        return {}

    @staticmethod
    def _is_number(v: Any) -> bool:
        try:
            float(v)
            return True
        except Exception:
            return False

    def _primary_chain(self, chain_cache: Any) -> pd.DataFrame:
        if isinstance(chain_cache, dict):
            for _, frame in chain_cache.items():
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame
        return pd.DataFrame()

    def _regime_features(self, state: Mapping[str, Any], surface: Mapping[str, float]) -> List[float]:
        regime_metrics = state.get("regime_metrics", {}) if isinstance(state.get("regime_metrics"), dict) else {}
        iv_rank = float(regime_metrics.get("iv_rank", surface.get("iv_percentile_252d", 0.5)) or 0.5)
        iv_percentile = float(surface.get("iv_percentile_252d", iv_rank))
        term_slope = float(surface.get("term_structure_slope", 0.0))
        realized_spread = float(surface.get("realized_implied_spread", 0.0))
        skew_curvature = float(surface.get("skew_curvature", 0.0))
        vol_of_vol = float(surface.get("vol_of_vol_proxy", 0.0))
        risk_pct = float((state.get("portfolio_risk_usage", {}) or {}).get("risk_pct", 0.0) or 0.0)
        return [
            iv_percentile,
            iv_rank,
            term_slope,
            realized_spread,
            skew_curvature,
            vol_of_vol,
            risk_pct,
        ]

    def _returns_by_strategy(self, closed_positions: Iterable[Mapping[str, Any]]) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {}
        for row in closed_positions or []:
            if not isinstance(row, Mapping):
                continue
            strategy = str(row.get("strategy_type", "unknown") or "unknown")
            pnl = float(row.get("realized_pnl", 0.0) or 0.0)
            scale = max(1.0, abs(float(row.get("max_loss", 1.0) or 1.0)))
            ret = pnl / scale
            out.setdefault(strategy, []).append(float(ret))
        return out

    def _strategy_metrics_payload(self, canonical_payload: Mapping[str, Any]) -> Dict[str, Dict[str, float]]:
        cap = canonical_payload.get("capital_allocations", {}) if isinstance(canonical_payload, Mapping) else {}
        out: Dict[str, Dict[str, float]] = {}
        if isinstance(cap, dict):
            strategies = cap.get("strategies", {}) if isinstance(cap.get("strategies"), dict) else {}
            for key, value in strategies.items():
                if isinstance(value, Mapping):
                    out[str(key)] = {
                        "regret": float(value.get("regret", 0.0) or 0.0),
                        "confidence": float(value.get("confidence", 0.5) or 0.5),
                        "credibility": float(value.get("credibility", 0.5) or 0.5),
                        "information_ratio": float(value.get("information_ratio", 0.0) or 0.0),
                    }
        return out

    @staticmethod
    def _merge_strategy_meta_inputs(
        posteriors: Mapping[str, Mapping[str, float]],
        strategy_metrics: Mapping[str, Mapping[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        for strategy, stats in posteriors.items():
            prior = strategy_metrics.get(strategy, {})
            out[strategy] = {
                "regret": float(prior.get("regret", 1.0 - float(stats.get("credibility", 0.5)))),
                "confidence": float(prior.get("confidence", stats.get("credibility", 0.5))),
                "credibility": float(prior.get("credibility", stats.get("credibility", 0.5))),
                "information_ratio": float(prior.get("information_ratio", 0.0)),
            }
        return out

    @staticmethod
    def _apply_valuation_alignment(
        posteriors: Mapping[str, Mapping[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        """
        Add strategy-level valuation alignment used by BayesianKellyAllocator bridge.
        """
        out: Dict[str, Dict[str, float]] = {}
        for strategy, stats in posteriors.items():
            s = str(strategy).lower()
            if "short" in s and "long" not in s:
                align = -1.0
            elif "long" in s:
                align = 1.0
            elif "dispersion" in s:
                align = 0.35
            else:
                align = 0.20
            out[str(strategy)] = {**dict(stats), "valuation_alignment": float(align)}
        return out

    def _load_valuation_bridge_inputs(self) -> Dict[str, float]:
        """
        Load cross-sectional valuation posterior/state artifacts and return bridge inputs
        for the allocator.
        """
        bridge = {
            "posterior_gap": 0.0,
            "posterior_variance": 0.0,
            "macro_compression": 1.0,
            "market_percentile": 0.5,
            "bubble_probability": 0.0,
            "default_alignment": 1.0,
        }
        try:
            posterior = self.data_hub._read_parquet("data/processed/valuation_posterior.parquet")
            if isinstance(posterior, pd.DataFrame) and not posterior.empty:
                p = posterior.copy()
                p["posterior_gap"] = pd.to_numeric(p.get("posterior_gap"), errors="coerce")
                p["posterior_variance"] = pd.to_numeric(p.get("posterior_variance"), errors="coerce")
                p["posterior_confidence"] = pd.to_numeric(p.get("posterior_confidence"), errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
                if p["posterior_confidence"].sum() > 0:
                    w = p["posterior_confidence"].to_numpy(dtype=float)
                    bridge["posterior_gap"] = float(np.average(p["posterior_gap"].fillna(0.0), weights=w))
                    bridge["posterior_variance"] = float(np.average(p["posterior_variance"].fillna(0.0), weights=w))
                else:
                    bridge["posterior_gap"] = float(p["posterior_gap"].mean() or 0.0)
                    bridge["posterior_variance"] = float(p["posterior_variance"].mean() or 0.0)
                if "macro_compression" in p.columns:
                    bridge["macro_compression"] = float(pd.to_numeric(p["macro_compression"], errors="coerce").mean() or 1.0)
        except Exception:
            pass

        try:
            state = self.data_hub._read_parquet("data/processed/portfolio_valuation_state.parquet")
            if isinstance(state, pd.DataFrame) and not state.empty:
                s = state.copy()
                if "date" in s.columns:
                    s["date"] = pd.to_datetime(s["date"], errors="coerce")
                    s = s.sort_values("date")
                last = s.tail(1).iloc[0]
                bridge["market_percentile"] = float(last.get("market_percentile", bridge["market_percentile"]) or bridge["market_percentile"])
                bridge["bubble_probability"] = float(last.get("bubble_probability", bridge["bubble_probability"]) or bridge["bubble_probability"])
                if "aggregate_gap_mean" in last.index:
                    bridge["posterior_gap"] = float(last.get("aggregate_gap_mean", bridge["posterior_gap"]) or bridge["posterior_gap"])
                if "aggregate_gap_std" in last.index:
                    std = float(last.get("aggregate_gap_std", 0.0) or 0.0)
                    bridge["posterior_variance"] = max(bridge["posterior_variance"], std * std)
        except Exception:
            pass

        # Final clipping for allocator stability.
        bridge["posterior_gap"] = float(np.clip(bridge["posterior_gap"], -0.50, 0.50))
        bridge["posterior_variance"] = float(max(0.0, bridge["posterior_variance"]))
        bridge["macro_compression"] = float(np.clip(bridge["macro_compression"], 0.50, 1.50))
        bridge["market_percentile"] = float(np.clip(bridge["market_percentile"], 0.0, 1.0))
        bridge["bubble_probability"] = float(np.clip(bridge["bubble_probability"], 0.0, 1.0))
        return bridge

    def _dispersion_payload(self, context: AlphaOSContext) -> Dict[str, Any]:
        index_iv = float(context.additional_inputs.get("index_iv", 0.0) or 0.0)
        constituent_ivs = context.additional_inputs.get("constituent_ivs", [])
        weights = context.additional_inputs.get("constituent_weights", [])
        realized_corr = float(context.additional_inputs.get("realized_corr", 0.0) or 0.0)
        if index_iv <= 0.0 or not constituent_ivs or not weights:
            return {"dispersion_spread": 0.0, "stance": "neutral", "implied_corr": 0.0}
        implied = self.dispersion_engine.compute_implied_correlation(index_iv, constituent_ivs, weights)
        signal = self.dispersion_engine.compute_signal(implied, realized_corr)
        return {**signal, "implied_corr": implied, "realized_corr": realized_corr}

    @staticmethod
    def _expected_return(
        weights: Mapping[str, float],
        posteriors: Mapping[str, Mapping[str, float]],
    ) -> float:
        total = 0.0
        for strategy, weight in dict(weights).items():
            mu = float((posteriors.get(strategy, {}) or {}).get("posterior_mean", 0.0) or 0.0)
            total += float(weight) * mu
        return float(total)

    @staticmethod
    def _legacy_convexity_proxy(context: AlphaOSContext, risk_payload: Mapping[str, Any]) -> float:
        # Use current portfolio convexity proxy as legacy baseline when separate legacy path is unavailable.
        current_convexity = float((risk_payload or {}).get("convexity_score", 0.0) or 0.0)
        gross = max(1e-8, float(context.current_gross_exposure))
        return float(current_convexity * gross)
