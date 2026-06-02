from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import IntEnum, Enum
from typing import Any, Optional


NIFTY500_SECTOR_COUNTS: dict[str, int] = {
    "Financial Services": 95,
    "Capital Goods": 64,
    "Healthcare": 52,
    "Automobile and Auto Components": 36,
    "Fast Moving Consumer Goods": 31,
    "Information Technology": 28,
    "Chemicals": 26,
    "Consumer Services": 26,
    "Oil Gas & Consumable Fuels": 19,
    "Consumer Durables": 19,
    "Power": 18,
    "Metals & Mining": 17,
    "Services": 13,
    "Construction": 12,
    "Construction Materials": 10,
    "Realty": 10,
    "Telecommunication": 10,
    "Textiles": 6,
    "Media Entertainment & Publication": 4,
    "Diversified": 3,
    "Forest Materials": 1,
}
NIFTY500_SECTORS: list[str] = list(NIFTY500_SECTOR_COUNTS.keys())


class ShockType(str, Enum):
    NONE = "none"
    OIL_PRICE_SPIKE = "oil_price_spike"
    OIL_SUPPLY_DISRUPTION = "oil_supply_disruption"
    RATE_HIKE_RBI = "rate_hike_rbi"
    RATE_CUT_RBI = "rate_cut_rbi"
    RATE_HIKE_FED = "rate_hike_fed"
    RATE_CUT_FED = "rate_cut_fed"
    INR_DEPRECIATION = "inr_depreciation"
    INR_APPRECIATION = "inr_appreciation"
    GEOPOLITICAL_CONFLICT = "geopolitical_conflict"
    FII_OUTFLOW = "fii_outflow"
    FII_INFLOW = "fii_inflow"
    INFLATION_SURPRISE_HIGH = "inflation_surprise_high"
    INFLATION_SURPRISE_LOW = "inflation_surprise_low"
    CHINA_SLOWDOWN = "china_slowdown"
    COMMODITY_CRASH = "commodity_crash"
    GLOBAL_RECESSION = "global_recession"
    US_TECH_CORRECTION = "us_tech_correction"
    EARNINGS_MISS_SECTOR = "earnings_miss_sector"
    EARNINGS_BEAT_SECTOR = "earnings_beat_sector"
    REGULATORY_NEGATIVE = "regulatory_negative"
    REGULATORY_POSITIVE = "regulatory_positive"
    CAPEX_CYCLE_ACCELERATION = "capex_cycle_acceleration"
    MONSOON_DEFICIT = "monsoon_deficit"
    MONSOON_NORMAL = "monsoon_normal"
    BUDGET_POSITIVE = "budget_positive"
    BUDGET_NEGATIVE = "budget_negative"
    CREDIT_RATING_DOWNGRADE = "credit_rating_downgrade"
    BANKING_STRESS = "banking_stress"
    UNKNOWN_HIGH_MAGNITUDE = "unknown_high_magnitude"


class ShockSeverity(IntEnum):
    NONE = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    EXTREME = 5


class ShockDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class IVRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class CompanySignal:
    ticker: str
    sector: str
    signal_type: str
    direction: ShockDirection
    severity: ShockSeverity
    headline: str
    source: str
    published_at: datetime
    availability_date: datetime
    confidence: float
    is_bellwether: bool = False
    estimated_stock_move_pct: float = 0.0
    related_tickers: list[str] = field(default_factory=list)


@dataclass
class MarketSignal:
    signal_type: str
    direction: ShockDirection
    severity: ShockSeverity
    headline: str
    source: str
    published_at: datetime
    availability_date: datetime
    confidence: float
    estimated_nifty_move_pct: float = 0.0
    affected_sectors: list[str] = field(default_factory=list)
    fii_net_flow_crores: float = 0.0
    dii_net_flow_crores: float = 0.0


@dataclass
class MacroSignal:
    signal_type: str
    shock_type: ShockType
    direction: ShockDirection
    severity: ShockSeverity
    headline: str
    source: str
    published_at: datetime
    availability_date: datetime
    confidence: float
    is_rbi: bool = False
    is_fed: bool = False
    is_geopolitical: bool = False
    crude_price_change_pct: float = 0.0
    inr_usd_change_pct: float = 0.0
    estimated_nifty_move_pct: float = 0.0
    affected_sectors: list[str] = field(default_factory=list)


@dataclass
class SectorImpact:
    sector: str
    impact_score: float
    direction: ShockDirection
    severity: ShockSeverity
    estimated_sector_move_pct: float
    time_horizon_days: int
    key_tickers_at_risk: list[str] = field(default_factory=list)
    key_tickers_to_benefit: list[str] = field(default_factory=list)
    rebalance_required: bool = False
    hedge_required: bool = False
    opportunity_trade: bool = False
    rationale: str = ""


@dataclass
class MarketIntelligenceState:
    computed_at: datetime
    company_signals: list[CompanySignal] = field(default_factory=list)
    market_signals: list[MarketSignal] = field(default_factory=list)
    macro_signals: list[MacroSignal] = field(default_factory=list)
    tickers_negative: list[str] = field(default_factory=list)
    tickers_positive: list[str] = field(default_factory=list)
    primary_shock_type: ShockType = ShockType.NONE
    secondary_shock_type: Optional[ShockType] = None
    shock_severity: ShockSeverity = ShockSeverity.NONE
    shock_direction: ShockDirection = ShockDirection.NEUTRAL
    shock_confidence: float = 0.0
    shock_detected_at: Optional[datetime] = None
    shock_description: str = ""
    rbi_stance: str = "neutral"
    global_risk_appetite: str = "neutral"
    crude_direction: ShockDirection = ShockDirection.NEUTRAL
    crude_change_pct: float = 0.0
    inr_direction: ShockDirection = ShockDirection.NEUTRAL
    inr_change_pct: float = 0.0
    vix_level: float = 0.0
    iv_regime: IVRegime = IVRegime.NORMAL
    sector_impacts: dict[str, SectorImpact] = field(default_factory=dict)
    requires_immediate_hedge: bool = False
    requires_portfolio_rebalance: bool = False
    options_opportunity_detected: bool = False
    selected_option_strategies: list[dict[str, Any]] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    freshness_minutes: float = 0.0
    is_stale: bool = False
    available: bool = True


def severity_from_move_pct(move_pct: float) -> ShockSeverity:
    absolute_move = abs(float(move_pct or 0.0))
    if absolute_move <= 0.0:
        return ShockSeverity.NONE
    if absolute_move < 0.5:
        return ShockSeverity.LOW
    if absolute_move < 1.5:
        return ShockSeverity.MODERATE
    if absolute_move < 3.0:
        return ShockSeverity.HIGH
    if absolute_move < 6.0:
        return ShockSeverity.SEVERE
    return ShockSeverity.EXTREME


def direction_from_score(score: float, neutral_band: float = 0.05) -> ShockDirection:
    numeric = float(score or 0.0)
    if numeric >= neutral_band:
        return ShockDirection.BULLISH
    if numeric <= -neutral_band:
        return ShockDirection.BEARISH
    return ShockDirection.NEUTRAL


def iv_regime_from_vix(vix_level: float) -> IVRegime:
    value = float(vix_level or 0.0)
    if value < 13.0:
        return IVRegime.LOW
    if value < 18.0:
        return IVRegime.NORMAL
    if value < 25.0:
        return IVRegime.ELEVATED
    if value < 35.0:
        return IVRegime.HIGH
    return IVRegime.EXTREME


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _serialize_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def intelligence_state_to_dict(state: MarketIntelligenceState) -> dict[str, Any]:
    return _serialize_value(state)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", "None"):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _restore_direction(value: Any) -> ShockDirection:
    try:
        return ShockDirection(str(value))
    except Exception:
        return ShockDirection.NEUTRAL


def _restore_severity(value: Any) -> ShockSeverity:
    try:
        return ShockSeverity(int(value))
    except Exception:
        return ShockSeverity.NONE


def deserialize_market_intelligence_state(payload: Optional[dict[str, Any]]) -> Optional[MarketIntelligenceState]:
    if not isinstance(payload, dict):
        return None

    sector_impacts: dict[str, SectorImpact] = {}
    for sector, raw in dict(payload.get("sector_impacts", {}) or {}).items():
        if not isinstance(raw, dict):
            continue
        sector_impacts[str(sector)] = SectorImpact(
            sector=str(raw.get("sector", sector)),
            impact_score=float(raw.get("impact_score", 0.0) or 0.0),
            direction=_restore_direction(raw.get("direction")),
            severity=_restore_severity(raw.get("severity")),
            estimated_sector_move_pct=float(raw.get("estimated_sector_move_pct", 0.0) or 0.0),
            time_horizon_days=int(raw.get("time_horizon_days", 0) or 0),
            key_tickers_at_risk=list(raw.get("key_tickers_at_risk", []) or []),
            key_tickers_to_benefit=list(raw.get("key_tickers_to_benefit", []) or []),
            rebalance_required=bool(raw.get("rebalance_required", False)),
            hedge_required=bool(raw.get("hedge_required", False)),
            opportunity_trade=bool(raw.get("opportunity_trade", False)),
            rationale=str(raw.get("rationale", "") or ""),
        )

    def _company(item: dict[str, Any]) -> CompanySignal:
        return CompanySignal(
            ticker=str(item.get("ticker", "") or ""),
            sector=str(item.get("sector", "Diversified") or "Diversified"),
            signal_type=str(item.get("signal_type", "") or ""),
            direction=_restore_direction(item.get("direction")),
            severity=_restore_severity(item.get("severity")),
            headline=str(item.get("headline", "") or ""),
            source=str(item.get("source", "") or ""),
            published_at=_parse_datetime(item.get("published_at")) or datetime.now(),
            availability_date=_parse_datetime(item.get("availability_date")) or datetime.now(),
            confidence=float(item.get("confidence", 0.0) or 0.0),
            is_bellwether=bool(item.get("is_bellwether", False)),
            estimated_stock_move_pct=float(item.get("estimated_stock_move_pct", 0.0) or 0.0),
            related_tickers=list(item.get("related_tickers", []) or []),
        )

    def _market(item: dict[str, Any]) -> MarketSignal:
        return MarketSignal(
            signal_type=str(item.get("signal_type", "") or ""),
            direction=_restore_direction(item.get("direction")),
            severity=_restore_severity(item.get("severity")),
            headline=str(item.get("headline", "") or ""),
            source=str(item.get("source", "") or ""),
            published_at=_parse_datetime(item.get("published_at")) or datetime.now(),
            availability_date=_parse_datetime(item.get("availability_date")) or datetime.now(),
            confidence=float(item.get("confidence", 0.0) or 0.0),
            estimated_nifty_move_pct=float(item.get("estimated_nifty_move_pct", 0.0) or 0.0),
            affected_sectors=list(item.get("affected_sectors", []) or []),
            fii_net_flow_crores=float(item.get("fii_net_flow_crores", 0.0) or 0.0),
            dii_net_flow_crores=float(item.get("dii_net_flow_crores", 0.0) or 0.0),
        )

    def _macro(item: dict[str, Any]) -> MacroSignal:
        try:
            shock_type = ShockType(str(item.get("shock_type", ShockType.NONE.value)))
        except Exception:
            shock_type = ShockType.NONE
        return MacroSignal(
            signal_type=str(item.get("signal_type", "") or ""),
            shock_type=shock_type,
            direction=_restore_direction(item.get("direction")),
            severity=_restore_severity(item.get("severity")),
            headline=str(item.get("headline", "") or ""),
            source=str(item.get("source", "") or ""),
            published_at=_parse_datetime(item.get("published_at")) or datetime.now(),
            availability_date=_parse_datetime(item.get("availability_date")) or datetime.now(),
            confidence=float(item.get("confidence", 0.0) or 0.0),
            is_rbi=bool(item.get("is_rbi", False)),
            is_fed=bool(item.get("is_fed", False)),
            is_geopolitical=bool(item.get("is_geopolitical", False)),
            crude_price_change_pct=float(item.get("crude_price_change_pct", 0.0) or 0.0),
            inr_usd_change_pct=float(item.get("inr_usd_change_pct", 0.0) or 0.0),
            estimated_nifty_move_pct=float(item.get("estimated_nifty_move_pct", 0.0) or 0.0),
            affected_sectors=list(item.get("affected_sectors", []) or []),
        )

    try:
        primary = ShockType(str(payload.get("primary_shock_type", ShockType.NONE.value)))
    except Exception:
        primary = ShockType.NONE
    secondary_raw = payload.get("secondary_shock_type")
    try:
        secondary = ShockType(str(secondary_raw)) if secondary_raw else None
    except Exception:
        secondary = None
    try:
        iv_regime = IVRegime(str(payload.get("iv_regime", IVRegime.NORMAL.value)))
    except Exception:
        iv_regime = IVRegime.NORMAL

    return MarketIntelligenceState(
        computed_at=_parse_datetime(payload.get("computed_at")) or datetime.now(),
        company_signals=[_company(item) for item in list(payload.get("company_signals", []) or []) if isinstance(item, dict)],
        market_signals=[_market(item) for item in list(payload.get("market_signals", []) or []) if isinstance(item, dict)],
        macro_signals=[_macro(item) for item in list(payload.get("macro_signals", []) or []) if isinstance(item, dict)],
        tickers_negative=list(payload.get("tickers_negative", []) or []),
        tickers_positive=list(payload.get("tickers_positive", []) or []),
        primary_shock_type=primary,
        secondary_shock_type=secondary,
        shock_severity=_restore_severity(payload.get("shock_severity")),
        shock_direction=_restore_direction(payload.get("shock_direction")),
        shock_confidence=float(payload.get("shock_confidence", 0.0) or 0.0),
        shock_detected_at=_parse_datetime(payload.get("shock_detected_at")),
        shock_description=str(payload.get("shock_description", "") or ""),
        rbi_stance=str(payload.get("rbi_stance", "neutral") or "neutral"),
        global_risk_appetite=str(payload.get("global_risk_appetite", "neutral") or "neutral"),
        crude_direction=_restore_direction(payload.get("crude_direction")),
        crude_change_pct=float(payload.get("crude_change_pct", 0.0) or 0.0),
        inr_direction=_restore_direction(payload.get("inr_direction")),
        inr_change_pct=float(payload.get("inr_change_pct", 0.0) or 0.0),
        vix_level=float(payload.get("vix_level", 0.0) or 0.0),
        iv_regime=iv_regime,
        sector_impacts=sector_impacts,
        requires_immediate_hedge=bool(payload.get("requires_immediate_hedge", False)),
        requires_portfolio_rebalance=bool(payload.get("requires_portfolio_rebalance", False)),
        options_opportunity_detected=bool(payload.get("options_opportunity_detected", False)),
        selected_option_strategies=list(payload.get("selected_option_strategies", []) or []),
        sources_used=list(payload.get("sources_used", []) or []),
        freshness_minutes=float(payload.get("freshness_minutes", 0.0) or 0.0),
        is_stale=bool(payload.get("is_stale", False)),
        available=bool(payload.get("available", True)),
    )
