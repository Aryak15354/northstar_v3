"""NLP-powered shock classification for the Northstar V3 news brain."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable

from src.intelligence.news_brain.news_signal_state import (
    CompanySignal,
    MacroSignal,
    MarketSignal,
    ShockDirection,
    ShockSeverity,
    ShockType,
    severity_from_move_pct,
)
from src.intelligence.shock_engine.shock_knowledge_base import get_shock_profile

logger = logging.getLogger(__name__)


EVENT_TYPE_TO_SHOCK: dict[str, ShockType] = {
    "macro_rate_hike": ShockType.RATE_HIKE_RBI,
    "macro_rate_cut": ShockType.RATE_CUT_RBI,
    "macro_crude_spike": ShockType.OIL_PRICE_SPIKE,
    "macro_geopolitical": ShockType.GEOPOLITICAL_CONFLICT,
    "macro_fii_outflow": ShockType.FII_OUTFLOW,
    "macro_fii_inflow": ShockType.FII_INFLOW,
    "macro_inflation_high": ShockType.INFLATION_SURPRISE_HIGH,
    "macro_inflation_low": ShockType.INFLATION_SURPRISE_LOW,
    "earnings_beat": ShockType.EARNINGS_BEAT_SECTOR,
    "earnings_miss": ShockType.EARNINGS_MISS_SECTOR,
    "regulatory_action_negative": ShockType.REGULATORY_NEGATIVE,
    "regulatory_action_positive": ShockType.REGULATORY_POSITIVE,
    "capex_announcement": ShockType.CAPEX_CYCLE_ACCELERATION,
}

DIRECTION_TRUST_THRESHOLD = 0.75
_DEFAULT_CLASSIFIER: "NLPShockClassifier | None" = None


@dataclass
class ShockAssessment:
    shock_type: ShockType
    score: float
    confidence: float
    severity: ShockSeverity
    direction: ShockDirection


def _sign_to_direction(value: float) -> ShockDirection:
    if value > 0.05:
        return ShockDirection.BULLISH
    if value < -0.05:
        return ShockDirection.BEARISH
    return ShockDirection.NEUTRAL


def _signal_severity(signal: Any) -> ShockSeverity:
    candidate = getattr(signal, "severity", None)
    if isinstance(candidate, ShockSeverity):
        return candidate
    move = abs(float(getattr(signal, "estimated_nifty_move_pct", 0.0) or 0.0))
    return severity_from_move_pct(move)


class NLPShockClassifier:
    """Drop-in replacement for the legacy keyword shock classifier."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline

            self._pipeline = NewsNLPPipeline(self._config)
        return self._pipeline

    def determine_shock_summary(
        self,
        company_signals: list[CompanySignal],
        market_signals: list[MarketSignal],
        macro_signals: list[MacroSignal],
        india_vix: float,
        crude_change_pct: float,
        inr_change_pct: float,
        fii_net_crores: float,
    ) -> dict[str, object]:
        assessments = self.rank_shocks(
            company_signals=company_signals,
            market_signals=market_signals,
            macro_signals=macro_signals,
            india_vix=india_vix,
            crude_change_pct=crude_change_pct,
            inr_change_pct=inr_change_pct,
            fii_net_crores=fii_net_crores,
        )
        if not assessments:
            return {
                "primary_shock_type": ShockType.NONE,
                "secondary_shock_type": None,
                "shock_severity": ShockSeverity.NONE,
                "shock_direction": ShockDirection.NEUTRAL,
                "shock_confidence": 0.0,
                "ranked_shocks": [],
            }
        primary = assessments[0]
        secondary = None
        for candidate in assessments[1:]:
            if candidate.shock_type == primary.shock_type:
                continue
            if candidate.score >= primary.score * 0.55:
                secondary = candidate.shock_type
                break
        return {
            "primary_shock_type": primary.shock_type,
            "secondary_shock_type": secondary,
            "shock_severity": primary.severity,
            "shock_direction": primary.direction,
            "shock_confidence": float(primary.confidence),
            "ranked_shocks": assessments,
        }

    def classify_from_signals(
        self,
        macro_signals: list[MacroSignal],
        market_signals: list[MarketSignal],
        india_vix: float = 0.0,
        crude_change_pct: float = 0.0,
        inr_change_pct: float = 0.0,
        fii_net_crores: float = 0.0,
    ) -> tuple[ShockType, ShockSeverity, ShockDirection, float]:
        summary = self.determine_shock_summary(
            company_signals=[],
            market_signals=market_signals,
            macro_signals=macro_signals,
            india_vix=india_vix,
            crude_change_pct=crude_change_pct,
            inr_change_pct=inr_change_pct,
            fii_net_crores=fii_net_crores,
        )
        return (
            summary["primary_shock_type"],
            summary["shock_severity"],
            summary["shock_direction"],
            float(summary["shock_confidence"]),
        )

    def classify_single_headline(self, headline: str) -> tuple[ShockType, float, ShockDirection]:
        clean = str(headline or "").strip()
        if not clean:
            return ShockType.NONE, 0.0, ShockDirection.NEUTRAL
        lower = clean.lower()
        if self._is_rate_hike_negated(lower):
            return ShockType.NONE, 0.70, ShockDirection.NEUTRAL
        if self._looks_like_oil_supply_disruption(lower):
            return ShockType.OIL_SUPPLY_DISRUPTION, 0.86, ShockDirection.BEARISH
        if "tightens monetary policy" in lower or "hawkish monetary policy" in lower:
            return ShockType.RATE_HIKE_RBI, 0.74, ShockDirection.BEARISH

        result = self._get_pipeline().process_document(headline=clean)
        if result is None:
            return ShockType.NONE, 0.0, ShockDirection.NEUTRAL
        shock_type = self._shock_from_document(result.headline, result.event.event_type if result.event else "unknown")
        if shock_type == ShockType.NONE:
            return ShockType.NONE, 0.0, ShockDirection.NEUTRAL
        direction = self._direction_from_result(result)
        confidence = float((result.event.confidence if result.event else 0.5) * max(result.conviction, 0.6))
        return shock_type, min(confidence, 0.99), direction

    def rank_shocks(
        self,
        company_signals: list[CompanySignal],
        market_signals: list[MarketSignal],
        macro_signals: list[MacroSignal],
        india_vix: float,
        crude_change_pct: float,
        inr_change_pct: float,
        fii_net_crores: float,
    ) -> list[ShockAssessment]:
        candidates: list[ShockAssessment] = []
        quant = self._quantitative_trigger(crude_change_pct, inr_change_pct, fii_net_crores, india_vix)
        if quant is not None:
            candidates.append(quant)

        for signal in macro_signals:
            assessment = self._assessment_from_signal(signal)
            if assessment is not None:
                candidates.append(assessment)
        for signal in market_signals:
            assessment = self._assessment_from_signal(signal)
            if assessment is not None:
                candidates.append(assessment)
        for signal in company_signals:
            assessment = self._assessment_from_signal(signal)
            if assessment is not None:
                candidates.append(assessment)

        merged: dict[ShockType, ShockAssessment] = {}
        for item in candidates:
            current = merged.get(item.shock_type)
            if current is None or (item.score, item.confidence, int(item.severity)) > (current.score, current.confidence, int(current.severity)):
                merged[item.shock_type] = item
        return sorted(merged.values(), key=lambda item: (item.score, item.confidence, int(item.severity)), reverse=True)

    def _quantitative_trigger(
        self,
        crude_change_pct: float,
        inr_change_pct: float,
        fii_net_crores: float,
        india_vix: float,
    ) -> ShockAssessment | None:
        if crude_change_pct > 15.0:
            return ShockAssessment(ShockType.OIL_SUPPLY_DISRUPTION, 1.20, 0.95, ShockSeverity.EXTREME, ShockDirection.BEARISH)
        if crude_change_pct > 8.0:
            return ShockAssessment(ShockType.OIL_PRICE_SPIKE, 1.00, 0.92, ShockSeverity.SEVERE, ShockDirection.BEARISH)
        if crude_change_pct > 5.0:
            return ShockAssessment(ShockType.OIL_PRICE_SPIKE, 0.82, 0.85, ShockSeverity.HIGH, ShockDirection.BEARISH)
        if inr_change_pct < -2.5:
            return ShockAssessment(ShockType.INR_DEPRECIATION, 0.95, 0.90, ShockSeverity.SEVERE, ShockDirection.BEARISH)
        if inr_change_pct < -1.5:
            return ShockAssessment(ShockType.INR_DEPRECIATION, 0.82, 0.85, ShockSeverity.HIGH, ShockDirection.BEARISH)
        if fii_net_crores < -8000.0:
            return ShockAssessment(ShockType.FII_OUTFLOW, 0.92, 0.90, ShockSeverity.SEVERE, ShockDirection.BEARISH)
        if fii_net_crores < -3000.0:
            return ShockAssessment(ShockType.FII_OUTFLOW, 0.76, 0.82, ShockSeverity.HIGH, ShockDirection.BEARISH)
        if india_vix > 35.0:
            return ShockAssessment(ShockType.UNKNOWN_HIGH_MAGNITUDE, 0.70, 0.88, ShockSeverity.EXTREME, ShockDirection.BEARISH)
        return None

    def _assessment_from_signal(self, signal: Any) -> ShockAssessment | None:
        shock_type = getattr(signal, "shock_type", ShockType.NONE)
        headline = str(getattr(signal, "headline", "") or "")
        signal_type = str(getattr(signal, "signal_type", "") or "")
        direction = getattr(signal, "direction", ShockDirection.NEUTRAL)
        confidence = float(getattr(signal, "confidence", 0.0) or 0.0)
        severity = _signal_severity(signal)

        if shock_type == ShockType.NONE:
            mapped = self._shock_from_signal_type(signal_type, headline)
            shock_type = mapped
        if shock_type == ShockType.NONE:
            return None
        score = 0.25 + 0.12 * int(severity) + 0.45 * confidence
        if isinstance(signal, MacroSignal):
            score += 0.25
        elif isinstance(signal, MarketSignal):
            score += 0.08
        if shock_type in {ShockType.OIL_SUPPLY_DISRUPTION, ShockType.GEOPOLITICAL_CONFLICT} and self._looks_like_oil_supply_disruption(headline.lower()):
            shock_type = ShockType.OIL_SUPPLY_DISRUPTION
            score += 0.18
            direction = ShockDirection.BEARISH
        if direction == ShockDirection.NEUTRAL:
            profile = get_shock_profile(shock_type.value)
            direction = _sign_to_direction(float(profile.get("market_level_impact", 0.0) or 0.0))
        return ShockAssessment(shock_type, float(score), min(confidence if confidence > 0 else 0.55, 0.99), severity, direction)

    def _shock_from_signal_type(self, signal_type: str, headline: str) -> ShockType:
        token = str(signal_type or "").strip().lower()
        if token in EVENT_TYPE_TO_SHOCK:
            return EVENT_TYPE_TO_SHOCK[token]
        if token.startswith("oil_price"):
            return ShockType.OIL_PRICE_SPIKE
        if token.startswith("fii_outflow"):
            return ShockType.FII_OUTFLOW
        if token.startswith("fii_inflow"):
            return ShockType.FII_INFLOW
        if token.startswith("inr_depreciation"):
            return ShockType.INR_DEPRECIATION
        if token.startswith("inr_appreciation"):
            return ShockType.INR_APPRECIATION
        if token.startswith("rbi_rate_hike"):
            return ShockType.RATE_HIKE_RBI
        if token.startswith("rbi_rate_cut"):
            return ShockType.RATE_CUT_RBI
        return self._shock_from_document(headline, token)

    def _shock_from_document(self, headline: str, event_type: str) -> ShockType:
        lower = str(headline or "").lower()
        if self._is_rate_hike_negated(lower):
            return ShockType.NONE
        if self._looks_like_oil_supply_disruption(lower):
            return ShockType.OIL_SUPPLY_DISRUPTION
        if any(token in lower for token in ("airstrike", "missile", "war", "conflict", "invasion", "military action", "attack")):
            return ShockType.GEOPOLITICAL_CONFLICT
        if "tightens monetary policy" in lower or "hawkish monetary policy" in lower:
            return ShockType.RATE_HIKE_RBI
        return EVENT_TYPE_TO_SHOCK.get(str(event_type or "").strip().lower(), ShockType.NONE)

    def _direction_from_result(self, result: Any) -> ShockDirection:
        direction = ShockDirection.NEUTRAL
        if result.event is not None:
            direction = {
                "positive": ShockDirection.BULLISH,
                "negative": ShockDirection.BEARISH,
                "neutral": ShockDirection.NEUTRAL,
                "unknown": ShockDirection.NEUTRAL,
            }.get(result.event.expected_direction, ShockDirection.NEUTRAL)
        if result.sentiment is not None and float(result.sentiment.confidence) >= DIRECTION_TRUST_THRESHOLD:
            if float(result.polarity) < -0.15:
                return ShockDirection.BEARISH
            if float(result.polarity) > 0.15:
                return ShockDirection.BULLISH
        return direction

    @staticmethod
    def _is_rate_hike_negated(text: str) -> bool:
        return any(
            phrase in text
            for phrase in (
                "rate hike fears subside",
                "repo rate unchanged",
                "keeps repo rate unchanged",
                "holds repo rate",
                "holds rates",
                "did not raise",
                "no rate hike",
            )
        )

    @staticmethod
    def _looks_like_oil_supply_disruption(text: str) -> bool:
        transport = any(token in text for token in ("tanker", "shipping lane", "route", "supply route", "pipeline", "strait"))
        disruption = any(token in text for token in ("obstructed", "blocked", "disrupted", "seized", "attack", "missile", "blockade"))
        geography = any(token in text for token in ("hormuz", "red sea", "suez", "gulf"))
        return (transport and disruption) or (geography and disruption)


def _get_default_classifier(config: dict[str, Any] | None = None) -> NLPShockClassifier:
    global _DEFAULT_CLASSIFIER
    if config is not None:
        return NLPShockClassifier(config)
    if _DEFAULT_CLASSIFIER is None:
        _DEFAULT_CLASSIFIER = NLPShockClassifier({})
    return _DEFAULT_CLASSIFIER


def determine_shock_summary(
    company_signals: list[CompanySignal],
    market_signals: list[MarketSignal],
    macro_signals: list[MacroSignal],
    india_vix: float,
    crude_change_pct: float,
    inr_change_pct: float,
    fii_net_crores: float,
) -> dict[str, object]:
    return _get_default_classifier().determine_shock_summary(
        company_signals=company_signals,
        market_signals=market_signals,
        macro_signals=macro_signals,
        india_vix=india_vix,
        crude_change_pct=crude_change_pct,
        inr_change_pct=inr_change_pct,
        fii_net_crores=fii_net_crores,
    )


def rank_shocks(
    company_signals: list[CompanySignal],
    market_signals: list[MarketSignal],
    macro_signals: list[MacroSignal],
    india_vix: float,
    crude_change_pct: float,
    inr_change_pct: float,
    fii_net_crores: float,
) -> list[ShockAssessment]:
    return _get_default_classifier().rank_shocks(
        company_signals=company_signals,
        market_signals=market_signals,
        macro_signals=macro_signals,
        india_vix=india_vix,
        crude_change_pct=crude_change_pct,
        inr_change_pct=inr_change_pct,
        fii_net_crores=fii_net_crores,
    )


def classify_shock(
    company_signals: list[CompanySignal],
    market_signals: list[MarketSignal],
    macro_signals: list[MacroSignal],
    india_vix: float,
    crude_change_pct: float,
    inr_change_pct: float,
    fii_net_crores: float,
) -> tuple[ShockType, ShockSeverity, ShockDirection, float]:
    return _get_default_classifier().classify_from_signals(
        macro_signals=macro_signals,
        market_signals=market_signals,
        india_vix=india_vix,
        crude_change_pct=crude_change_pct,
        inr_change_pct=inr_change_pct,
        fii_net_crores=fii_net_crores,
    )


ShockClassifier = NLPShockClassifier
