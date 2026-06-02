from __future__ import annotations

from datetime import datetime

from src.intelligence.news_brain.news_signal_state import (
    CompanySignal,
    MacroSignal,
    MarketIntelligenceState,
    MarketSignal,
    ShockDirection,
    ShockSeverity,
    ShockType,
    iv_regime_from_vix,
)
from src.intelligence.news_brain.sector_impact_engine import SectorImpactEngine
from src.intelligence.shock_engine.shock_knowledge_base import get_shock_profile


NOW = datetime(2026, 3, 19, 9, 15)


def make_company_signal(
    ticker: str,
    sector: str,
    signal_type: str = "company_news",
    direction: ShockDirection = ShockDirection.BEARISH,
    severity: ShockSeverity = ShockSeverity.MODERATE,
    headline: str = "",
    confidence: float = 0.8,
    is_bellwether: bool = False,
) -> CompanySignal:
    return CompanySignal(
        ticker=ticker,
        sector=sector,
        signal_type=signal_type,
        direction=direction,
        severity=severity,
        headline=headline or f"{ticker} signal",
        source="test",
        published_at=NOW,
        availability_date=NOW,
        confidence=confidence,
        is_bellwether=is_bellwether,
    )


def make_market_signal(
    signal_type: str,
    direction: ShockDirection,
    severity: ShockSeverity,
    headline: str,
    confidence: float = 0.8,
    estimated_nifty_move_pct: float = 0.0,
    affected_sectors: list[str] | None = None,
    fii_net_flow_crores: float = 0.0,
) -> MarketSignal:
    return MarketSignal(
        signal_type=signal_type,
        direction=direction,
        severity=severity,
        headline=headline,
        source="test",
        published_at=NOW,
        availability_date=NOW,
        confidence=confidence,
        estimated_nifty_move_pct=estimated_nifty_move_pct,
        affected_sectors=list(affected_sectors or []),
        fii_net_flow_crores=fii_net_flow_crores,
    )


def make_macro_signal(
    signal_type: str,
    shock_type: ShockType,
    direction: ShockDirection,
    severity: ShockSeverity,
    headline: str,
    confidence: float = 0.85,
    estimated_nifty_move_pct: float = 0.0,
    crude_price_change_pct: float = 0.0,
    inr_usd_change_pct: float = 0.0,
    affected_sectors: list[str] | None = None,
) -> MacroSignal:
    return MacroSignal(
        signal_type=signal_type,
        shock_type=shock_type,
        direction=direction,
        severity=severity,
        headline=headline,
        source="test",
        published_at=NOW,
        availability_date=NOW,
        confidence=confidence,
        estimated_nifty_move_pct=estimated_nifty_move_pct,
        crude_price_change_pct=crude_price_change_pct,
        inr_usd_change_pct=inr_usd_change_pct,
        affected_sectors=list(affected_sectors or []),
    )


def build_state(
    shock_type: ShockType,
    shock_severity: ShockSeverity | None = None,
    shock_direction: ShockDirection | None = None,
    company_signals: list[CompanySignal] | None = None,
    market_signals: list[MarketSignal] | None = None,
    macro_signals: list[MacroSignal] | None = None,
    secondary_shock_type: ShockType | None = None,
    vix_level: float = 18.0,
    shock_confidence: float = 0.82,
) -> MarketIntelligenceState:
    company_signals = list(company_signals or [])
    market_signals = list(market_signals or [])
    macro_signals = list(macro_signals or [])

    profile = get_shock_profile(shock_type.value)
    market_impact = float(profile.get("market_level_impact", 0.0) or 0.0)
    if shock_direction is None:
        if market_impact > 0.0:
            shock_direction = ShockDirection.BULLISH
        elif market_impact < 0.0:
            shock_direction = ShockDirection.BEARISH
        else:
            shock_direction = ShockDirection.NEUTRAL
    if shock_severity is None:
        shock_severity = ShockSeverity.NONE if shock_type == ShockType.NONE else ShockSeverity.HIGH

    sector_impacts = SectorImpactEngine().compute(
        primary_shock_type=shock_type,
        secondary_shock_type=secondary_shock_type,
        shock_severity=shock_severity,
        shock_direction=shock_direction,
        company_signals=company_signals,
        market_signals=market_signals,
        macro_signals=macro_signals,
    )

    return MarketIntelligenceState(
        computed_at=NOW,
        company_signals=company_signals,
        market_signals=market_signals,
        macro_signals=macro_signals,
        tickers_negative=[signal.ticker for signal in company_signals if signal.direction == ShockDirection.BEARISH],
        tickers_positive=[signal.ticker for signal in company_signals if signal.direction == ShockDirection.BULLISH],
        primary_shock_type=shock_type,
        secondary_shock_type=secondary_shock_type,
        shock_severity=shock_severity,
        shock_direction=shock_direction,
        shock_confidence=shock_confidence,
        shock_detected_at=NOW if shock_type != ShockType.NONE else None,
        shock_description=shock_type.value,
        rbi_stance="neutral",
        global_risk_appetite="neutral",
        crude_direction=ShockDirection.NEUTRAL,
        crude_change_pct=0.0,
        inr_direction=ShockDirection.NEUTRAL,
        inr_change_pct=0.0,
        vix_level=vix_level,
        iv_regime=iv_regime_from_vix(vix_level),
        sector_impacts=sector_impacts,
        requires_immediate_hedge=shock_severity >= ShockSeverity.HIGH,
        requires_portfolio_rebalance=any(item.rebalance_required for item in sector_impacts.values()),
        options_opportunity_detected=any(item.opportunity_trade for item in sector_impacts.values()) or shock_severity == ShockSeverity.NONE,
        sources_used=["test"],
        freshness_minutes=0.0,
        is_stale=False,
        available=True,
    )
