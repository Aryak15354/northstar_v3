"""
AlternativeDataState — The formal representation of alternative data signals in Northstar V3's UnifiedState.

Design principle: AlternativeDataState contains interpreted signals, not raw data.
Other components consume regime labels, normalized scores, and flag booleans from here.
They do not do math on raw GST rupee figures or raw pledge percentages.

This state object is updated:
  - At system startup (loaded from last run's output)
  - After the morning alternative data pipeline run
  - NOT during market hours (alt data is not real-time — it's daily/monthly)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class EconomicActivityRegime(str, Enum):
    CONTRACTION    = "CONTRACTION"    # GST + power both deteriorating
    SLOWING        = "SLOWING"        # One deteriorating, one flat
    NEUTRAL        = "NEUTRAL"        # Neither clearly directional
    RECOVERING     = "RECOVERING"     # One improving from a low base
    EXPANSION      = "EXPANSION"      # GST + power both clearly growing
    UNAVAILABLE    = "UNAVAILABLE"    # Data not fresh enough to classify


class SmartMoneySignal(str, Enum):
    STRONG_ACCUMULATION  = "STRONG_ACCUMULATION"  # Broad institutional buying
    MILD_ACCUMULATION    = "MILD_ACCUMULATION"
    NEUTRAL              = "NEUTRAL"
    MILD_DISTRIBUTION    = "MILD_DISTRIBUTION"
    STRONG_DISTRIBUTION  = "STRONG_DISTRIBUTION"  # Broad institutional selling
    UNAVAILABLE          = "UNAVAILABLE"


@dataclass
class GSTSignalState:
    regime: EconomicActivityRegime = EconomicActivityRegime.UNAVAILABLE
    mom_growth_pct: float = 0.0           # Month-over-month growth %
    yoy_growth_pct: float = 0.0           # Year-over-year growth %
    deviation_from_trend: float = 0.0     # Z-score vs rolling 12m trend
    trend_direction: str = "UNKNOWN"      # "ACCELERATING", "STABLE", "DECELERATING"
    last_data_month: Optional[datetime] = None
    is_fresh: bool = False


@dataclass
class PowerSignalState:
    regime: EconomicActivityRegime = EconomicActivityRegime.UNAVAILABLE
    yoy_growth_pct: float = 0.0
    deviation_from_seasonal: float = 0.0  # Z-score vs same period in prior years
    industrial_proxy_score: float = 0.0   # Composite score, 0-100
    last_data_date: Optional[datetime] = None
    is_fresh: bool = False


@dataclass
class CreditSignalState:
    market_upgrade_ratio: float = 0.0     # Upgrades / (Upgrades + Downgrades) over 90d
    net_credit_momentum: float = 0.0      # Upgrades minus downgrades, normalized
    distressed_company_count: int = 0     # Companies with sub-investment-grade ratings
    recent_downgrade_count: int = 0       # Downgrades in the past 30 days
    high_yield_stress_flag: bool = False  # True if distressed count surging
    last_data_date: Optional[datetime] = None
    is_fresh: bool = False


@dataclass
class SmartMoneyState:
    market_signal: SmartMoneySignal = SmartMoneySignal.UNAVAILABLE
    net_institutional_flow_score: float = 0.0   # -1.0 to +1.0, normalized
    accumulation_breadth: float = 0.0            # % of universe seeing net buying
    distribution_breadth: float = 0.0           # % of universe seeing net selling
    high_conviction_buys: int = 0               # Tickers with strong accumulation signal
    high_conviction_sells: int = 0
    last_data_date: Optional[datetime] = None
    is_fresh: bool = False


@dataclass
class PromoterRiskState:
    market_avg_pledge_pct: float = 0.0          # Market-wide avg promoter pledge %
    high_pledge_company_count: int = 0          # Companies with pledge > 30%
    pledge_increasing_count: int = 0            # Companies where pledge grew QoQ
    systemic_pledge_risk: bool = False          # True if broad pledge deterioration
    last_data_quarter: Optional[datetime] = None
    is_fresh: bool = False


@dataclass
class AlternativeDataState:
    gst: GSTSignalState = field(default_factory=GSTSignalState)
    power: PowerSignalState = field(default_factory=PowerSignalState)
    credit: CreditSignalState = field(default_factory=CreditSignalState)
    smart_money: SmartMoneyState = field(default_factory=SmartMoneyState)
    promoter_risk: PromoterRiskState = field(default_factory=PromoterRiskState)
    
    # Composite economic activity regime combining GST + power
    economic_activity_regime: EconomicActivityRegime = EconomicActivityRegime.UNAVAILABLE
    
    # Overall alternative data freshness
    any_source_fresh: bool = False
    all_sources_fresh: bool = False
    last_updated: Optional[datetime] = None
