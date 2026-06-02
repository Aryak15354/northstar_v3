from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.intelligence.news_brain.layers.company_news_layer import CompanyNewsLayer
from src.intelligence.news_brain.layers.macro_news_layer import MacroNewsLayer
from src.intelligence.news_brain.layers.market_news_layer import MarketNewsLayer
from src.intelligence.news_brain.news_signal_state import (
    MarketIntelligenceState,
    NIFTY500_SECTORS,
    ShockDirection,
    ShockSeverity,
    ShockType,
    direction_from_score,
    intelligence_state_to_dict,
    iv_regime_from_vix,
)
from src.intelligence.news_brain.sector_impact_engine import SectorImpactEngine
from src.intelligence.news_brain.shock_classifier import NLPShockClassifier


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class NewsBrain:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = self._load_config(config)
        self.company_layer = CompanyNewsLayer(self.config)
        self.market_layer = MarketNewsLayer(self.config)
        self.macro_layer = MacroNewsLayer(self.config)
        self._shock_classifier = NLPShockClassifier(self.config)
        self.sector_impact_engine = SectorImpactEngine()
        brain_cfg = self.config.get("news_brain", {})
        freshness_cfg = dict(brain_cfg.get("freshness", {}) or {})
        self.stale_threshold_minutes = float(brain_cfg.get("stale_threshold_minutes", 30.0))
        self.company_max_age_minutes = float(
            freshness_cfg.get("company_max_age_minutes", brain_cfg.get("company_max_age_minutes", 4_320.0))
        )
        self.market_max_age_minutes = float(
            freshness_cfg.get("market_max_age_minutes", brain_cfg.get("market_max_age_minutes", 2_880.0))
        )
        self.macro_max_age_minutes = float(
            freshness_cfg.get("macro_max_age_minutes", brain_cfg.get("macro_max_age_minutes", 64_800.0))
        )
        self.snapshot_path = PROJECT_ROOT / "data" / "intelligence" / "market_intelligence_state.json"

    def run_cycle(self, as_of_datetime: datetime | None = None) -> MarketIntelligenceState:
        as_of_datetime = as_of_datetime or datetime.now()
        company_signals = self.company_layer.run(as_of_datetime)
        market_context = self.market_layer.run(as_of_datetime)
        macro_context = self.macro_layer.run(as_of_datetime)

        market_signals = list(market_context.get("market_signals", []) or [])
        macro_signals = list(macro_context.get("macro_signals", []) or [])

        vix_level = float(market_context.get("vix_level", 0.0) or 0.0)
        crude_change_pct = float(macro_context.get("crude_change_pct", market_context.get("crude_change_pct", 0.0)) or 0.0)
        inr_change_pct = float(macro_context.get("inr_change_pct", market_context.get("inr_change_pct", 0.0)) or 0.0)
        fii_net_crores = float(market_context.get("fii_net_crores", 0.0) or 0.0)

        summary = self._shock_classifier.determine_shock_summary(
            company_signals=company_signals,
            market_signals=market_signals,
            macro_signals=macro_signals,
            india_vix=vix_level,
            crude_change_pct=crude_change_pct,
            inr_change_pct=inr_change_pct,
            fii_net_crores=fii_net_crores,
        )

        primary_shock = summary["primary_shock_type"]
        secondary_shock = summary["secondary_shock_type"]
        shock_severity = summary["shock_severity"]
        shock_direction = summary["shock_direction"]
        shock_confidence = float(summary["shock_confidence"] or 0.0)

        sector_impacts = self.sector_impact_engine.compute(
            primary_shock_type=primary_shock,
            secondary_shock_type=secondary_shock,
            shock_severity=shock_severity,
            shock_direction=shock_direction,
            company_signals=company_signals,
            market_signals=market_signals,
            macro_signals=macro_signals,
        )

        freshness_status = self._evaluate_freshness(
            as_of_datetime=as_of_datetime,
            company_signals=company_signals,
            market_context=market_context,
            macro_context=macro_context,
        )
        freshness_minutes = float(freshness_status["freshness_minutes"])
        is_stale = bool(freshness_status["is_stale"])

        state = MarketIntelligenceState(
            computed_at=as_of_datetime,
            company_signals=company_signals,
            market_signals=market_signals,
            macro_signals=macro_signals,
            tickers_negative=sorted({_ticker(signal.ticker) for signal in company_signals if signal.direction == ShockDirection.BEARISH}),
            tickers_positive=sorted({_ticker(signal.ticker) for signal in company_signals if signal.direction == ShockDirection.BULLISH}),
            primary_shock_type=primary_shock,
            secondary_shock_type=secondary_shock,
            shock_severity=shock_severity,
            shock_direction=shock_direction,
            shock_confidence=shock_confidence,
            shock_detected_at=as_of_datetime if primary_shock != ShockType.NONE else None,
            shock_description=self._describe(primary_shock, secondary_shock, shock_direction, shock_severity),
            rbi_stance=str(macro_context.get("rbi_stance", "neutral") or "neutral"),
            global_risk_appetite=str(macro_context.get("global_risk_appetite", "neutral") or "neutral"),
            crude_direction=direction_from_score(-crude_change_pct),
            crude_change_pct=crude_change_pct,
            inr_direction=ShockDirection.BEARISH if inr_change_pct < 0 else ShockDirection.BULLISH if inr_change_pct > 0 else ShockDirection.NEUTRAL,
            inr_change_pct=inr_change_pct,
            vix_level=vix_level,
            iv_regime=iv_regime_from_vix(vix_level),
            sector_impacts=sector_impacts,
            requires_immediate_hedge=bool(shock_severity >= ShockSeverity.HIGH or any(item.hedge_required for item in sector_impacts.values())),
            requires_portfolio_rebalance=bool(any(item.rebalance_required for item in sector_impacts.values())),
            options_opportunity_detected=bool(any(item.opportunity_trade for item in sector_impacts.values()) or shock_severity == ShockSeverity.NONE),
            selected_option_strategies=[],
            sources_used=sorted(
                {
                    *(str(signal.source) for signal in company_signals),
                    *(str(signal.source) for signal in market_signals),
                    *(str(signal.source) for signal in macro_signals),
                    "nlp_pipeline",
                }
            ),
            freshness_minutes=float(freshness_minutes),
            is_stale=is_stale,
            available=bool(company_signals or market_signals or macro_signals or primary_shock == ShockType.NONE),
        )

        try:
            from src.options.strategy_library.strategy_selector import StrategySelector

            selector = StrategySelector(self.config)
            state.selected_option_strategies = selector.select(
                state,
                current_iv_surface={"vix": vix_level, "iv_rank": self._iv_rank_from_vix(vix_level)},
            )
        except Exception:
            state.selected_option_strategies = []

        self._write_snapshot(state)
        return state

    def _evaluate_freshness(
        self,
        *,
        as_of_datetime: datetime,
        company_signals: list[Any],
        market_context: dict[str, Any],
        macro_context: dict[str, Any],
    ) -> dict[str, Any]:
        company_timestamp = max(
            (
                getattr(signal, "availability_date", None) or getattr(signal, "published_at", None)
                for signal in company_signals
            ),
            default=None,
        )
        layer_timestamps = {
            "company": company_timestamp,
            "market": self._context_timestamp(
                as_of_datetime,
                market_context,
                explicit_keys=["latest_data_at", "latest_market_data_at", "latest_signal_at"],
                fallback_keys=["vix_level", "fii_net_crores", "breadth_pct", "crude_change_pct", "inr_change_pct"],
            ),
            "macro": self._context_timestamp(
                as_of_datetime,
                macro_context,
                explicit_keys=["latest_data_at", "latest_macro_data_at", "latest_signal_at"],
                fallback_keys=["rbi_stance", "global_risk_appetite", "crude_change_pct", "inr_change_pct"],
            ),
        }
        thresholds = {
            "company": self.company_max_age_minutes,
            "market": self.market_max_age_minutes,
            "macro": self.macro_max_age_minutes,
        }
        layer_ages = {
            layer: self._age_minutes(as_of_datetime, timestamp)
            for layer, timestamp in layer_timestamps.items()
            if timestamp is not None
        }
        fresh_layers = {
            layer: age <= thresholds[layer]
            for layer, age in layer_ages.items()
        }
        return {
            "freshness_minutes": min(layer_ages.values()) if layer_ages else 999.0,
            "is_stale": not any(fresh_layers.values()),
        }

    def _load_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(config or {})
        config_path = PROJECT_ROOT / "config" / "intelligence_brain.yaml"
        if config_path.exists():
            file_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            merged = _deep_merge(dict(file_cfg), merged)
        nlp_path = PROJECT_ROOT / "config" / "nlp_config.yaml"
        if nlp_path.exists():
            nlp_cfg = yaml.safe_load(nlp_path.read_text(encoding="utf-8")) or {}
            merged = _deep_merge(dict(nlp_cfg), merged)
        return merged

    def _write_snapshot(self, state: MarketIntelligenceState) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(
            json.dumps(intelligence_state_to_dict(state), indent=2, default=str),
            encoding="utf-8",
        )

    @staticmethod
    def _describe(
        primary: ShockType,
        secondary: ShockType | None,
        direction: ShockDirection,
        severity: ShockSeverity,
    ) -> str:
        if primary == ShockType.NONE:
            return "No actionable macro shock detected"
        parts = [f"{primary.value} {direction.value} {severity.name.lower()}"]
        if secondary:
            parts.append(f"secondary={secondary.value}")
        return " | ".join(parts)

    @staticmethod
    def _iv_rank_from_vix(vix_level: float) -> float:
        vix = float(vix_level or 0.0)
        if vix <= 12.0:
            return 15.0
        if vix <= 18.0:
            return 35.0
        if vix <= 25.0:
            return 60.0
        if vix <= 35.0:
            return 82.0
        return 95.0

    @staticmethod
    def _age_minutes(as_of_datetime: datetime, timestamp: Any) -> float:
        parsed = _coerce_datetime(timestamp)
        if parsed is None:
            return 999.0
        return max((as_of_datetime - parsed).total_seconds() / 60.0, 0.0)

    @staticmethod
    def _context_timestamp(
        as_of_datetime: datetime,
        context: dict[str, Any],
        *,
        explicit_keys: list[str],
        fallback_keys: list[str],
    ) -> datetime | None:
        for key in explicit_keys:
            parsed = _coerce_datetime(context.get(key))
            if parsed is not None:
                return parsed
        if any(key in context for key in fallback_keys):
            return as_of_datetime
        return None


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _ticker(value: str) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, "", "None"):
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    if getattr(parsed, "tzinfo", None) is not None:
        parsed = parsed.tz_convert("UTC").tz_localize(None)
    return parsed.to_pydatetime()
