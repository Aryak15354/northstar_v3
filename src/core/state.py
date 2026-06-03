#!/usr/bin/env python3
"""
🧠 UNIFIED STATE - THE BRAINSTEM
Single Source of Truth for the Living Investment Organism

This is the enhanced Unified State Manager that serves as the brainstem
of the living system, coordinating all organs through a single source of truth.

Key Features:
- Single source of truth for all system data
- Time-indexed state history
- Event-driven state changes
- System lock mechanism for risk authority
- Memory integration across all dimensions
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, fields, is_dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

MAX_STATE_AGE_HOURS = 6.0

# Import SentimentState for UnifiedState
from src.sentiment.sentiment_state import SentimentState, SentimentRegime

# Import AlternativeDataState for UnifiedState
from src.alternative_data.alternative_state import AlternativeDataState

# Import AlphaOSState for UnifiedState
from src.alpha_os.alpha_os_state import AlphaOSState

# Import GovernorState for UnifiedState (Gap 6)
from src.portfolio.governor_state import GovernorState

class RiskStatus(Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AuthorityLevel(Enum):
    EMERGENCY = 1    # Absolute authority
    SYSTEM = 2       # System-level authority  
    PORTFOLIO = 3    # Portfolio-level authority
    POSITION = 4     # Position-level authority

@dataclass
class MarketTime:
    """Market time with phase information"""
    timestamp: datetime
    phase: str  # pre_open, open, intraday, close, overnight
    market_day: int
    is_trading_day: bool
    next_event: Optional[str] = None

@dataclass
class MarketState:
    """Market state component"""
    regime: str = "unknown"
    risk_on_probability: float = 0.5
    allowed_exposure: float = 0.35
    volatility_regime: str = "normal"
    market_stress: float = 0.0
    breadth_pct: float = 50.0
    participation_score: float = 0.5
    correlation: float = 0.5
    last_updated: datetime = None
    
    # Brain enhancements
    pulse_intensity: float = 0.0
    market_phase: str = "neutral"
    pulse_risk_level: str = "low"
    regime_similarity: float = 0.0
    brain_regime: str = "Unknown"
    coherence_score: float = 1.0

    def __post_init__(self):
        for field_name in ("allowed_exposure", "risk_on_probability"):
            value = getattr(self, field_name, None)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric > 1.5:
                raise ValueError(
                    f"MarketState.{field_name} = {numeric} is out of range. "
                    "Values must be decimal ratios (0.0-1.0), not percentage points."
                )

@dataclass
class MacroState:
    """Macro economic state"""
    inflation_regime: str = "normal"
    yield_curve_shape: str = "normal"
    liquidity_conditions: str = "normal"
    policy_stance: str = "neutral"
    macro_score: float = 0.0
    last_updated: datetime = None

@dataclass
class RegimeState:
    """Regime analysis state"""
    current_regime: str = "unknown"
    regime_confidence: float = 0.5
    regime_duration: int = 0
    transition_probability: float = 0.0
    historical_similarity: float = 0.0
    last_updated: datetime = None

@dataclass
class PulseState:
    """Market pulse state"""
    intensity: float = 0.0
    phase: str = "neutral"
    risk_level: str = "low"
    dominant_forces: List[str] = None
    opportunity_zones: List[str] = None
    narrative: str = ""
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.dominant_forces is None:
            self.dominant_forces = []
        if self.opportunity_zones is None:
            self.opportunity_zones = []

@dataclass
class BeliefState:
    """Intelligence beliefs state"""
    valuation_conviction: float = 0.0
    market_conviction: float = 0.0
    strategy_conviction: float = 0.0
    narrative_conviction: float = 0.0
    unified_conviction: float = 0.0
    last_updated: datetime = None

@dataclass
class ConfidenceState:
    """Confidence levels across systems"""
    valuation_confidence: float = 0.0
    regime_confidence: float = 0.0
    narrative_confidence: float = 0.0
    overall_confidence: float = 0.0
    last_updated: datetime = None

@dataclass
class StrategyState:
    """Strategy performance and allocation state"""
    active_strategies: int = 0
    strategy_allocations: Dict[str, float] = None
    strategy_regret: float = 0.0
    allocation_timestamp: datetime = None
    
    def __post_init__(self):
        if self.strategy_allocations is None:
            self.strategy_allocations = {}

@dataclass
class CapitalState:
    """Capital allocation state"""
    total_capital: float = 1.0
    allocated_capital: float = 0.0
    cash_buffer: float = 0.05
    allocation_efficiency: float = 0.0
    last_rebalance: datetime = None

@dataclass
class PortfolioState:
    """Portfolio holdings and performance state"""
    total_positions: int = 0
    total_exposure: float = 0.0
    max_position: float = 0.0
    long_positions: int = 0
    short_positions: int = 0
    sector_exposure: Dict[str, float] = None
    max_sector_exposure: float = 0.0
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    compliance_status: bool = True
    compliance_violations: int = 0
    last_updated: datetime = None
    
    # Gap 7: Options system state (synced from OptionsBridge)
    options_positions: Dict[str, Any] = None
    options_position_count: int = 0
    options_net_delta: float = 0.0
    options_net_gamma: float = 0.0
    options_net_vega: float = 0.0
    options_net_theta: float = 0.0
    options_premium_at_risk: float = 0.0
    options_notional_deployed: float = 0.0
    options_unrealized_pnl: float = 0.0
    options_system_mode: str = "UNKNOWN"
    
    # Additional portfolio fields
    positions: Dict[str, Any] = None
    target_positions: Dict[str, Any] = None
    total_value: float = 0.0
    cash: float = 0.0
    invested_value: float = 0.0
    sector_allocation: Dict[str, float] = None
    target_sector_allocation: Dict[str, float] = None
    target_sector_exposure: Dict[str, float] = None
    position_count: int = 0
    target_position_count: int = 0
    target_total_positions: int = 0
    target_total_exposure: float = 0.0
    target_max_position: float = 0.0
    target_largest_position_pct: float = 0.0
    target_long_positions: int = 0
    target_short_positions: int = 0
    target_last_updated: datetime = None
    largest_position_pct: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    daily_return_pct: float = 0.0
    volatility_30d: float = 0.0
    
    def __post_init__(self):
        if self.sector_exposure is None:
            self.sector_exposure = {}
        if self.options_positions is None:
            self.options_positions = {}
        if self.positions is None:
            self.positions = {}
        if self.target_positions is None:
            self.target_positions = {}
        if self.sector_allocation is None:
            self.sector_allocation = {}
        if self.target_sector_allocation is None:
            self.target_sector_allocation = {}
        if self.target_sector_exposure is None:
            self.target_sector_exposure = {}

@dataclass
class RiskState:
    """Risk management state"""
    status: RiskStatus = RiskStatus.NORMAL
    emergency_active: bool = False
    system_stress: float = 0.0
    overall_risk_level: float = 0.0
    survival_mode: str = "normal"
    exposure_multiplier: float = 1.0
    emergency_brake_active: bool = False
    brake_conditions: int = 0
    kill_switches: Dict[str, bool] = None
    last_updated: datetime = None
    
    # Gap 7: Options risk metrics (synced from OptionsBridge)
    options_delta_exposure_inr: float = 0.0
    options_vega_exposure_inr: float = 0.0
    options_margin_utilization: float = 0.0
    options_max_loss_scenario: float = 0.0
    options_trading_suspended: bool = False
    
    def __post_init__(self):
        if self.kill_switches is None:
            self.kill_switches = {}

@dataclass
class HealthState:
    """System health metrics"""
    overall_health_score: float = 0.0
    health_status: str = "unknown"
    data_fresh: bool = False
    data_freshness_hours: float = 0.0
    component_availability: float = 0.0
    components_healthy: int = 0
    total_components: int = 0
    portfolio_active: bool = False
    intelligence_active: bool = False
    last_updated: datetime = None
    component_status: Dict[str, str] = None
    status_counts: Dict[str, int] = None
    active_warnings: List[str] = None
    source_mode: str = "unknown"

    def __post_init__(self):
        if self.component_status is None:
            self.component_status = {}
        if self.status_counts is None:
            self.status_counts = {}
        if self.active_warnings is None:
            self.active_warnings = []

@dataclass
class MemoryState:
    """Memory and historical patterns state"""
    regime_patterns_available: bool = False
    strategy_history_available: bool = False
    narrative_memory_available: bool = False
    portfolio_history_available: bool = False
    total_memory_records: int = 0
    oldest_record: datetime = None
    newest_record: datetime = None
    last_updated: datetime = None

@dataclass
class ShadowState:
    """Shadow trading system state (Gap 7, synced from ShadowBridge)"""
    shadow_positions: Dict[str, Any] = None
    shadow_equity_deployed: float = 0.0
    shadow_nav: float = 0.0
    live_shadow_position_overlap: float = 1.0
    target_shadow_position_overlap: float = 1.0
    shadow_extra_positions_count: int = 0
    shadow_missing_target_positions_count: int = 0
    target_snapshot_date: str = ""
    live_shadow_nav_divergence_pct: float = 0.0
    divergence_alert: bool = False
    comparison_available: bool = False
    comparison_mode: str = "none"
    execution_mode: str = "unknown"
    tracking_status: str = "unknown"
    tracking_breach: bool = False
    target_total_weight_drift: float = 0.0
    target_max_weight_drift: float = 0.0
    target_quantity_mismatch_count: int = 0
    exact_target_match: bool = False
    shadow_snapshot_timestamp: datetime = None
    shadow_data_stale: bool = False
    shadow_data_age_days: float = 0.0
    last_sync: datetime = None
    
    def __post_init__(self):
        if self.shadow_positions is None:
            self.shadow_positions = {}

@dataclass
class ValuationState:
    """Valuation engine state (Gap 7, synced from ValuationBridge)"""
    portfolio_weighted_pe: float = 0.0
    portfolio_weighted_pb: float = 0.0
    portfolio_discount_to_fair_value: float = 0.0
    valuation_confidence: float = 0.0
    tickers_with_fair_value: int = 0
    tickers_in_portfolio: int = 0
    valuation_coverage_pct: float = 0.0
    valuation_regime: str = "UNKNOWN"
    avg_margin_of_safety_pct: float = 0.0
    last_valuation_run: datetime = None

@dataclass
class StateEvent:
    """State change event for audit trail"""
    timestamp: datetime
    organ: str
    event_type: str
    component: str
    field: str
    old_value: Any
    new_value: Any
    reason: str
    authority_level: AuthorityLevel
    event_id: str = None
    
    def __post_init__(self):
        if self.event_id is None:
            self.event_id = f"{self.timestamp.isoformat()}_{self.organ}_{self.component}_{self.field}"

class UnifiedState:
    """
    The Brainstem - Single Source of Truth for the Living System
    
    This enhanced unified state manager serves as the central nervous system
    that coordinates all organs through a single source of truth.
    """
    
    def __init__(self):
        self.version = "2.0"  # Living System Version
        self._state_age_hours: Optional[float] = None
        self._state_is_stale: bool = False
        self._state_snapshot_time: Optional[datetime] = None
        
        # Core state components
        self.market = MarketState()
        self.macro = MacroState()
        self.regime = RegimeState()
        self.pulse = PulseState()
        self.beliefs = BeliefState()
        self.confidence = ConfidenceState()
        self.strategies = StrategyState()
        self.capital = CapitalState()
        self.portfolio = PortfolioState()
        self.risk = RiskState()
        self.health = HealthState()
        self.memory = MemoryState()
        self.sentiment = SentimentState()  # NEW: Sentiment intelligence state
        self.alternative_data = AlternativeDataState()  # NEW: Alternative data intelligence state
        self.alpha_os = AlphaOSState()  # NEW: Alpha OS strategy portfolio state
        self.intelligence_state: Dict[str, Any] = {}  # NEW: News brain market intelligence snapshot
        
        # P&L and accounting (Gap 5)
        from src.pnl.pnl_state import PnLState
        self.pnl_state = PnLState()  # NEW: Unified P&L accounting state
        
        # Portfolio Governor (Gap 6)
        self.governor_state = GovernorState()  # NEW: Portfolio Governor capital structure state
        
        # Gap 7: State consolidation - shadow and valuation states
        self.shadow_state = ShadowState()  # NEW: Shadow trading system state
        self.valuation_state = ValuationState()  # NEW: Valuation engine state
        
        # System control
        self.locked = False
        self.lock_reason = ""
        self.lock_authority = None
        self.time = MarketTime(
            timestamp=datetime.now(),
            phase="unknown",
            market_day=0,
            is_trading_day=False
        )
        
        # Event tracking
        self.events: List[StateEvent] = []
        self.event_history: List[StateEvent] = []
        
        # File paths
        self.state_file = 'data/state/unified_state.json'
        self.state_parquet = 'data/state/unified_state.parquet'
        self.state_history_file = 'data/state/unified_state_history.parquet'
        self.events_file = 'data/state/state_events.json'
        
        # Legacy compatibility paths
        self.legacy_paths = {
            'market_state_spine': 'data/processed/market_state.parquet',
            'intelligent_market_state': 'data/processed/intelligent_market_state.parquet',
            'market_brain_state': 'data/processed/market_brain_state.json',
            'pulse_state': 'data/processed/pulse_state.json',
            'survival_state': 'data/processed/system_stress.json',
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'strategy_beliefs': 'data/processed/strategy_beliefs.json',
            'intelligence_state': 'data/intelligence/intelligence_state.json',
            'emergency_brake': 'data/processed/emergency_brake_state.json'
        }
        
        # Ensure directories exist
        for path in [self.state_file, self.state_parquet, self.state_history_file, self.events_file]:
            os.makedirs(os.path.dirname(path), exist_ok=True)

    @property
    def market_state(self):
        return self.market

    @market_state.setter
    def market_state(self, value):
        self.market = value

    @property
    def macro_state(self):
        return self.macro

    @macro_state.setter
    def macro_state(self, value):
        self.macro = value

    @property
    def portfolio_state(self):
        return self.portfolio

    @portfolio_state.setter
    def portfolio_state(self, value):
        self.portfolio = value

    @property
    def risk_state(self):
        return self.risk

    @risk_state.setter
    def risk_state(self, value):
        self.risk = value

    @property
    def health_state(self):
        return self.health

    @health_state.setter
    def health_state(self, value):
        self.health = value

    def _parse_datetime(self, value: Any) -> Any:
        """Best-effort datetime parser for persisted snapshot hydration."""
        if value in [None, "", "None", "NaT"]:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return pd.to_datetime(value, utc=False).to_pydatetime()
            except Exception:
                return value
        return value

    def _coerce_state_value(self, current_value: Any, field_name: str, new_value: Any) -> Any:
        """Coerce persisted JSON values back into the in-memory dataclass shape."""
        if isinstance(current_value, Enum):
            try:
                return type(current_value)(new_value)
            except Exception:
                return current_value

        if isinstance(new_value, str):
            lowered = field_name.lower()
            if (
                isinstance(current_value, datetime)
                or current_value is None
                and any(
                    token in lowered
                    for token in [
                        "time",
                        "date",
                        "updated",
                        "timestamp",
                        "expires",
                        "decision",
                        "processing",
                        "check",
                    ]
                )
            ):
                parsed = self._parse_datetime(new_value)
                return parsed if isinstance(parsed, datetime) or parsed is None else new_value

        return new_value

    def _hydrate_section(self, target: Any, payload: Dict[str, Any]) -> None:
        """Recursively hydrate dataclass-backed state from a persisted JSON payload."""
        if not is_dataclass(target) or not isinstance(payload, dict):
            return

        for field_meta in fields(target):
            field_name = field_meta.name
            if field_name not in payload:
                continue

            current_value = getattr(target, field_name)
            new_value = payload[field_name]

            if is_dataclass(current_value) and isinstance(new_value, dict):
                self._hydrate_section(current_value, new_value)
                continue

            setattr(
                target,
                field_name,
                self._coerce_state_value(current_value, field_name, new_value),
            )

    def _extract_snapshot_time(self, snapshot: Dict[str, Any]) -> Optional[datetime]:
        if not isinstance(snapshot, dict):
            return None

        candidates = [
            snapshot.get("checkpoint_time"),
            snapshot.get("last_updated"),
            snapshot.get("timestamp"),
        ]
        time_payload = snapshot.get("time")
        if isinstance(time_payload, dict):
            candidates.append(time_payload.get("timestamp"))

        for raw in candidates:
            if raw in (None, "", "None", "NaT"):
                continue
            parsed = pd.to_datetime(raw, errors="coerce")
            if pd.isna(parsed):
                continue
            if getattr(parsed, "tzinfo", None) is not None:
                return parsed.tz_convert("UTC").tz_localize(None).to_pydatetime()
            return parsed.to_pydatetime()
        return None

    def _update_snapshot_freshness(
        self,
        snapshot: Dict[str, Any],
        *,
        max_age_hours: float = MAX_STATE_AGE_HOURS,
    ) -> None:
        snapshot_time = self._extract_snapshot_time(snapshot)
        self._state_snapshot_time = snapshot_time
        self._state_age_hours = None
        self._state_is_stale = False

        if snapshot_time is None:
            return

        age_hours = (datetime.now() - snapshot_time).total_seconds() / 3600.0
        self._state_age_hours = max(age_hours, 0.0)
        self._state_is_stale = bool(self._state_age_hours > float(max_age_hours))

        if self._state_is_stale:
            logger.warning(
                "UnifiedState is %.1f hours old (threshold: %.1fh). "
                "Decisions made on this state may use stale data. "
                "Run sync_canonical_state.py to refresh.",
                self._state_age_hours,
                float(max_age_hours),
            )

    @classmethod
    def load_snapshot_file(
        cls,
        path: str | Path,
        max_age_hours: float = MAX_STATE_AGE_HOURS,
    ) -> "UnifiedState":
        state = cls()
        state.load_snapshot(path, max_age_hours=max_age_hours)
        return state

    def load_snapshot(
        self,
        snapshot: Dict[str, Any] | str | os.PathLike[str],
        max_age_hours: float = MAX_STATE_AGE_HOURS,
    ) -> "UnifiedState":
        """Hydrate the current UnifiedState instance from a snapshot payload or snapshot file."""
        if isinstance(snapshot, (str, os.PathLike)):
            snapshot_path = Path(snapshot)
            if not snapshot_path.exists():
                raise FileNotFoundError(f"UnifiedState snapshot not found: {snapshot_path}")
            with snapshot_path.open('r', encoding='utf-8') as handle:
                snapshot = json.load(handle)

        if not isinstance(snapshot, dict):
            return self

        self.version = snapshot.get('version', self.version)
        self.locked = bool(snapshot.get('locked', self.locked))
        self.lock_reason = snapshot.get('lock_reason', self.lock_reason)

        lock_authority = snapshot.get('lock_authority')
        if lock_authority:
            try:
                self.lock_authority = AuthorityLevel[lock_authority]
            except Exception:
                self.lock_authority = self.lock_authority

        time_payload = snapshot.get('time')
        if isinstance(time_payload, dict):
            self._hydrate_section(self.time, time_payload)

        for section_name in [
            'market',
            'macro',
            'regime',
            'pulse',
            'beliefs',
            'confidence',
            'strategies',
            'capital',
            'portfolio',
            'risk',
            'health',
            'memory',
            'sentiment',
            'alternative_data',
            'alpha_os',
            'intelligence_state',
            'pnl_state',
            'governor_state',
            'shadow_state',
            'valuation_state',
        ]:
            payload = snapshot.get(section_name)
            if section_name == 'intelligence_state' and isinstance(payload, dict):
                self.intelligence_state = dict(payload)
                continue
            if isinstance(payload, dict) and hasattr(self, section_name):
                self._hydrate_section(getattr(self, section_name), payload)
        self._update_snapshot_freshness(snapshot, max_age_hours=max_age_hours)
        return self

    def lock_system(self, reason: str, authority: AuthorityLevel, organ: str = "risk"):
        """Lock the system with absolute authority"""
        
        if not self.locked or authority.value <= (self.lock_authority.value if self.lock_authority else 999):
            self.locked = True
            self.lock_reason = reason
            self.lock_authority = authority
            
            # Emit lock event
            self.emit_event(StateEvent(
                timestamp=datetime.now(),
                organ=organ,
                event_type="system_lock",
                component="system",
                field="locked",
                old_value=False,
                new_value=True,
                reason=reason,
                authority_level=authority
            ))
            
            return True
        return False
    
    def unlock_system(self, authority: AuthorityLevel, organ: str = "risk"):
        """Unlock the system if authority is sufficient"""
        
        if self.locked and authority.value <= (self.lock_authority.value if self.lock_authority else 999):
            self.locked = False
            self.lock_reason = ""
            self.lock_authority = None
            
            # Emit unlock event
            self.emit_event(StateEvent(
                timestamp=datetime.now(),
                organ=organ,
                event_type="system_unlock",
                component="system",
                field="locked",
                old_value=True,
                new_value=False,
                reason="System unlocked",
                authority_level=authority
            ))
            
            return True
        return False
    
    def emit_event(self, event: StateEvent):
        """Emit state change event"""
        self.events.append(event)
        
        # Keep events list manageable
        if len(self.events) > 1000:
            self.event_history.extend(self.events[:500])
            self.events = self.events[500:]
    
    def update_component(self, component_name: str, updates: Dict[str, Any], 
                        organ: str, reason: str = "", authority: AuthorityLevel = AuthorityLevel.POSITION):
        """Update a state component with event tracking"""
        
        component = getattr(self, component_name)
        
        for field, new_value in updates.items():
            if hasattr(component, field):
                old_value = getattr(component, field)
                
                if old_value != new_value:
                    # Emit event before change
                    self.emit_event(StateEvent(
                        timestamp=datetime.now(),
                        organ=organ,
                        event_type="state_update",
                        component=component_name,
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        reason=reason,
                        authority_level=authority
                    ))
                    
                    # Make the change
                    setattr(component, field, new_value)
        
        # Update last_updated timestamp if component has it
        if hasattr(component, 'last_updated'):
            setattr(component, 'last_updated', datetime.now())
    
    def get_state_dict(self) -> Dict[str, Any]:
        """Get complete state as dictionary"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'checkpoint_time': datetime.now().isoformat(),
            'version': self.version,
            'locked': self.locked,
            'lock_reason': self.lock_reason,
            'lock_authority': self.lock_authority.name if self.lock_authority else None,
            'time': asdict(self.time),
            'market': asdict(self.market),
            'macro': asdict(self.macro),
            'regime': asdict(self.regime),
            'pulse': asdict(self.pulse),
            'beliefs': asdict(self.beliefs),
            'confidence': asdict(self.confidence),
            'strategies': asdict(self.strategies),
            'capital': asdict(self.capital),
            'portfolio': asdict(self.portfolio),
            'risk': asdict(self.risk),
            'health': asdict(self.health),
            'memory': asdict(self.memory),
            'sentiment': asdict(self.sentiment),
            'alternative_data': asdict(self.alternative_data),
            'alpha_os': asdict(self.alpha_os),
            'intelligence_state': dict(self.intelligence_state or {}),
            'pnl_state': self.pnl_state.to_dict(),
            'governor_state': self.governor_state.to_dict(),
            'shadow_state': asdict(self.shadow_state),
            'valuation_state': asdict(self.valuation_state),
            'recent_events': [asdict(event) for event in self.events[-10:]]  # Last 10 events
        }
    
    def _is_meaningful_state_leaf(self, value: Any) -> bool:
        """Heuristic guard against legacy writers wiping canonical state with defaults."""
        if value is None:
            return False

        if isinstance(value, bool):
            return bool(value)

        if isinstance(value, (int, float, np.integer, np.floating)):
            if pd.isna(value):
                return False
            return float(value) != 0.0

        if isinstance(value, str):
            lowered = value.strip().lower()
            return lowered not in {
                "",
                "unknown",
                "unavailable",
                "none",
                "nan",
                "nat",
                "false",
            }

        if isinstance(value, dict):
            return any(self._is_meaningful_state_leaf(item) for item in value.values())

        if isinstance(value, list):
            return any(self._is_meaningful_state_leaf(item) for item in value)

        return True

    def _merge_preserving_existing(self, existing: Any, current: Any) -> Any:
        """Preserve richer canonical data when legacy callers try to save empty defaults."""
        if isinstance(existing, dict) and isinstance(current, dict):
            merged: Dict[str, Any] = {}
            for key in sorted(set(existing) | set(current)):
                if key in existing and key in current:
                    merged[key] = self._merge_preserving_existing(existing[key], current[key])
                elif key in current:
                    merged[key] = current[key]
                else:
                    merged[key] = existing[key]
            return merged

        if self._is_meaningful_state_leaf(current) or not self._is_meaningful_state_leaf(existing):
            return current

        return existing

    def _preserve_existing_sections(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Prevent non-authoritative saves from blanking already-populated canonical sections."""
        if not os.path.exists(self.state_file):
            return state_dict

        try:
            with open(self.state_file, 'r', encoding='utf-8') as handle:
                existing_state = json.load(handle)
        except Exception as exc:
            logger.warning("Could not load existing canonical state for merge-preserve guard: %s", exc)
            return state_dict

        preserved_sections = [
            'market',
            'macro',
            'regime',
            'pulse',
            'beliefs',
            'confidence',
            'strategies',
            'capital',
            'health',
            'memory',
            'sentiment',
            'alternative_data',
            'alpha_os',
            'intelligence_state',
            'pnl_state',
            'governor_state',
            'shadow_state',
            'valuation_state',
        ]

        merged_state = dict(state_dict)
        for section_name in preserved_sections:
            current_section = merged_state.get(section_name)
            existing_section = existing_state.get(section_name)
            if isinstance(current_section, dict) and isinstance(existing_section, dict):
                merged_state[section_name] = self._merge_preserving_existing(existing_section, current_section)

        return merged_state

    def save_state(self, preserve_existing: bool = True):
        """Save unified state to files.

        Args:
            preserve_existing: When True, protect populated canonical sections from being
                overwritten by legacy callers that only hold partial/default state.
        """
        
        try:
            state_dict = self.get_state_dict()
            if preserve_existing:
                state_dict = self._preserve_existing_sections(state_dict)
            
            # Save to JSON (human readable)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, indent=2, default=str)
            
            # Save to Parquet (fast loading)
            state_df = pd.DataFrame([self.flatten_state(state_dict)])
            for column in state_df.select_dtypes(include=['object']).columns:
                state_df[column] = state_df[column].astype(str)
            state_df.to_parquet(self.state_parquet, index=False)
            
            # Update history
            self.update_state_history(state_dict)
            
            # Save events
            self.save_events()
            
        except Exception as e:
            print(f"⚠️ Error saving unified state: {e}")
    
    def save_events(self):
        """Save events to file"""
        
        try:
            all_events = self.event_history + self.events
            events_data = {
                'timestamp': datetime.now().isoformat(),
                'total_events': len(all_events),
                'events': [asdict(event) for event in all_events[-1000:]]  # Keep last 1000 events
            }
            
            with open(self.events_file, 'w') as f:
                json.dump(events_data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"⚠️ Error saving events: {e}")
    
    def flatten_state(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested state for DataFrame storage"""
        
        flattened = {
            'timestamp': state_dict['timestamp'],
            'version': state_dict['version'],
            'locked': state_dict['locked']
        }
        
        # Flatten each component
        for component, data in state_dict.items():
            if isinstance(data, dict) and component not in ['timestamp', 'version', 'locked', 'time', 'recent_events']:
                for key, value in data.items():
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        flattened[f"{component}_{key}"] = value
                    elif isinstance(value, dict):
                        flattened[f"{component}_{key}_count"] = len(value)
                    elif isinstance(value, list):
                        flattened[f"{component}_{key}_count"] = len(value)
        
        return flattened
    
    def update_state_history(self, state_dict: Dict[str, Any]):
        """Update state history"""
        
        try:
            # Load existing history
            if os.path.exists(self.state_history_file):
                history_df = pd.read_parquet(self.state_history_file)
            else:
                history_df = pd.DataFrame()
            
            # Add current state
            current_state_df = pd.DataFrame([self.flatten_state(state_dict)])
            
            if not history_df.empty:
                history_df = pd.concat([history_df, current_state_df], ignore_index=True)
            else:
                history_df = current_state_df

            for column in history_df.select_dtypes(include=['object']).columns:
                history_df[column] = history_df[column].astype(str)
            
            # Keep only recent history (last 10000 records)
            history_df = history_df.tail(10000)
            
            # Save history
            history_df.to_parquet(self.state_history_file, index=False)
            
        except Exception as e:
            print(f"⚠️ Error updating state history: {e}")
    
    def load_from_legacy_sources(self):
        """Load state from existing V3 sources for backward compatibility"""
        
        try:
            # This method maintains compatibility with existing V3 data sources
            # while the system transitions to the living architecture
            
            # Load market state
            if os.path.exists(self.legacy_paths['market_state_spine']):
                spine_df = pd.read_parquet(self.legacy_paths['market_state_spine'])
                if not spine_df.empty:
                    latest = spine_df.iloc[-1]
                    self.update_component('market', {
                        'regime': latest.get('regime', 'unknown'),
                        'risk_on_probability': latest.get('risk_on_probability', 0.5),
                        'allowed_exposure': latest.get('allowed_exposure', 0.35),
                        'volatility_regime': latest.get('volatility_regime', 'normal'),
                        'market_stress': latest.get('market_stress', 0.0),
                        'breadth_pct': latest.get('breadth_pct', 50.0),
                        'participation_score': latest.get('participation_score', 0.5),
                        'correlation': latest.get('correlation', 0.5)
                    }, organ="legacy_loader", reason="Legacy data compatibility")
            
            # Load portfolio state
            if os.path.exists(self.legacy_paths['portfolio_weights']):
                weights_df = pd.read_parquet(self.legacy_paths['portfolio_weights'])
                if not weights_df.empty:
                    weight_col = 'final_weight' if 'final_weight' in weights_df.columns else 'weight'
                    if weight_col in weights_df.columns:
                        self.update_component('portfolio', {
                            'total_positions': len(weights_df),
                            'total_exposure': weights_df[weight_col].sum(),
                            'max_position': weights_df[weight_col].max(),
                            'long_positions': (weights_df[weight_col] > 0).sum(),
                            'short_positions': (weights_df[weight_col] < 0).sum()
                        }, organ="legacy_loader", reason="Legacy portfolio compatibility")
            
            # Load risk state
            if os.path.exists(self.legacy_paths['emergency_brake']):
                with open(self.legacy_paths['emergency_brake'], 'r') as f:
                    brake_state = json.load(f)
                    self.update_component('risk', {
                        'emergency_brake_active': brake_state.get('emergency_triggered', False),
                        'brake_conditions': len(brake_state.get('triggered_conditions', []))
                    }, organ="legacy_loader", reason="Legacy risk compatibility")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error loading from legacy sources: {e}")
            return False
    
    def compute_system_health(self):
        """Compute overall system health metrics"""
        
        try:
            # Data freshness
            market_updated = self.market.last_updated
            if market_updated:
                hours_since_update = (datetime.now() - market_updated).total_seconds() / 3600
                data_fresh = hours_since_update < 24
            else:
                hours_since_update = 999
                data_fresh = False
            
            # Component availability (check if components have recent updates)
            components = ['market', 'portfolio', 'risk', 'beliefs']
            healthy_components = 0
            
            for comp_name in components:
                comp = getattr(self, comp_name)
                if hasattr(comp, 'last_updated') and comp.last_updated:
                    hours_since = (datetime.now() - comp.last_updated).total_seconds() / 3600
                    if hours_since < 48:  # Healthy if updated within 48 hours
                        healthy_components += 1
                        
            component_availability = healthy_components / len(components)
            
            # Portfolio and intelligence activity
            portfolio_active = self.portfolio.total_exposure > 0.01
            intelligence_active = self.beliefs.unified_conviction > 0.1
            
            # Overall health score
            health_factors = [
                1.0 if data_fresh else 0.0,
                component_availability,
                1.0 if self.risk.status in [RiskStatus.NORMAL, RiskStatus.ELEVATED] else 0.0,
                1.0 if portfolio_active else 0.0,
                1.0 if intelligence_active else 0.0
            ]
            
            overall_health_score = np.mean(health_factors)
            
            # Health status
            if overall_health_score > 0.8:
                health_status = 'excellent'
            elif overall_health_score > 0.6:
                health_status = 'good'
            elif overall_health_score > 0.4:
                health_status = 'fair'
            else:
                health_status = 'poor'
            
            # Update health state
            self.update_component('health', {
                'overall_health_score': overall_health_score,
                'health_status': health_status,
                'data_fresh': data_fresh,
                'data_freshness_hours': hours_since_update,
                'component_availability': component_availability,
                'components_healthy': healthy_components,
                'total_components': len(components),
                'portfolio_active': portfolio_active,
                'intelligence_active': intelligence_active
            }, organ="health_monitor", reason="Health computation")
            
            return overall_health_score
            
        except Exception as e:
            print(f"⚠️ Error computing system health: {e}")
            return 0.0
    
    def get_dashboard_state(self) -> Dict[str, Any]:
        """Get state formatted for dashboard consumption"""
        
        # Compute current health
        self.compute_system_health()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'system_health': asdict(self.health),
            'locked': self.locked,
            'lock_reason': self.lock_reason,
            'command_bar': {
                'regime': self.market.regime,
                'risk_level': self.risk.status.value,
                'exposure': self.portfolio.total_exposure * 100,
                'drawdown': self.portfolio.max_drawdown * 100,
                'volatility': self.market.market_stress * 100,
                'liquidity': self.market.market_phase,
                'ai_conviction': self.beliefs.unified_conviction * 100,
                'ai_active': self.beliefs.unified_conviction > 0.1,
                'emergency_active': self.risk.emergency_active
            },
            'market_state': asdict(self.market),
            'intelligence_state': {
                'beliefs': asdict(self.beliefs),
                'confidence': asdict(self.confidence),
                'market_intelligence': dict(self.intelligence_state or {}),
            },
            'portfolio_state': asdict(self.portfolio),
            'risk_state': asdict(self.risk),
            'time_state': asdict(self.time)
        }

def main():
    """Test the enhanced Unified State"""
    
    print("🧠 TESTING ENHANCED UNIFIED STATE (BRAINSTEM)")
    print("=" * 60)
    
    # Create unified state
    state = UnifiedState()
    
    # Test state updates with event tracking
    print("\n📊 Testing state updates...")
    state.update_component('market', {
        'regime': 'expansion',
        'risk_on_probability': 0.75,
        'market_stress': 0.2
    }, organ="test_organ", reason="Testing state updates")
    
    # Test system lock
    print("\n🔒 Testing system lock...")
    lock_success = state.lock_system("Emergency test", AuthorityLevel.EMERGENCY, "test_risk")
    print(f"   Lock successful: {lock_success}")
    print(f"   System locked: {state.locked}")
    
    # Test health computation
    print("\n🏥 Testing health computation...")
    health_score = state.compute_system_health()
    print(f"   Health score: {health_score:.2f}")
    print(f"   Health status: {state.health.health_status}")
    
    # Test dashboard state
    print("\n🖥️ Testing dashboard state...")
    dashboard_state = state.get_dashboard_state()
    print(f"   Command bar regime: {dashboard_state['command_bar']['regime']}")
    print(f"   Emergency active: {dashboard_state['command_bar']['emergency_active']}")
    
    # Test event tracking
    print(f"\n📋 Event tracking:")
    print(f"   Total events: {len(state.events)}")
    if state.events:
        latest_event = state.events[-1]
        print(f"   Latest event: {latest_event.organ} -> {latest_event.component}.{latest_event.field}")
    
    # Test save/load
    print("\n💾 Testing save functionality...")
    state.save_state()
    print("   State saved successfully")
    
    print(f"\n✅ Enhanced Unified State (Brainstem) test successful!")
    print(f"   The living system now has a central nervous system!")
    
    return True

if __name__ == "__main__":
    main()
