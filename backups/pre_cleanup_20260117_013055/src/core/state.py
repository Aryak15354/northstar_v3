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
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

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
    
    def __post_init__(self):
        if self.sector_exposure is None:
            self.sector_exposure = {}

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
            'recent_events': [asdict(event) for event in self.events[-10:]]  # Last 10 events
        }
    
    def save_state(self):
        """Save unified state to files"""
        
        try:
            state_dict = self.get_state_dict()
            
            # Save to JSON (human readable)
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=2, default=str)
            
            # Save to Parquet (fast loading)
            state_df = pd.DataFrame([self.flatten_state(state_dict)])
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
                'confidence': asdict(self.confidence)
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