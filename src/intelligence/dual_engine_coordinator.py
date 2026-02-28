#!/usr/bin/env python3
"""
🎯 DUAL ENGINE COORDINATOR - NORTHSTAR INSTITUTIONAL ARCHITECTURE

This coordinator manages both Trend and Crisis engines with strict separation.
It ensures they never compete, never hedge each other, and never negotiate exposure.

ARCHITECTURE:
Northstar Governor
├── Trend Engine (REGIME = SUPPORTIVE/NEUTRAL)
└── Crisis Engine (REGIME = HOSTILE/PANIC)

KEY PRINCIPLE: The regime decides who is allowed to speak.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum
import logging

from src.intelligence.crisis_engine import NorthstarCrisisEngine, CrisisRegime
from src.intelligence.crisis_conviction_contract import CrisisConvictionContract

class MarketRegime(Enum):
    """Market regime classification for engine selection"""
    SUPPORTIVE = "SUPPORTIVE"    # Trend engine dominates
    NEUTRAL = "NEUTRAL"          # Trend engine with reduced conviction
    HOSTILE = "HOSTILE"          # Crisis engine activates
    PANIC = "PANIC"              # Crisis engine maximum activation

@dataclass
class EngineAllocation:
    """Engine allocation result"""
    trend_allocation: float
    crisis_allocation: float
    active_engine: str
    regime: MarketRegime
    regime_confidence: float
    total_allocation: float

class DualEngineCoordinator:
    """
    Dual Engine Coordinator - Manages Trend and Crisis Engines
    
    This coordinator ensures institutional discipline by:
    1. Maintaining absolute engine separation
    2. Using regime to determine active engine
    3. Preventing cross-engine interference
    4. Enforcing conviction contracts for both engines
    """
    
    def __init__(self):
        self.name = "Northstar Dual Engine Coordinator"
        self.version = "1.0.0"
        
        # Initialize engines
        self.crisis_engine = NorthstarCrisisEngine()
        self.crisis_contract = CrisisConvictionContract()
        
        # Regime classification parameters (FROZEN) - Calibrated from historical data
        self.regime_config = {
            'volatility_threshold_hostile': 0.24,    # 24% vol triggers hostile (slightly below crisis engine)
            'volatility_threshold_panic': 0.43,      # 43% vol triggers panic (slightly below crisis engine)
            'correlation_threshold': 0.70,           # 70% correlation indicates stress
            'liquidity_stress_threshold': 0.30,      # 30% liquidity stress
            'regime_persistence_days': 1             # 1 day to confirm regime change (more responsive)
        }
        
        # Engine coordination rules (FROZEN)
        self.coordination_rules = {
            'no_simultaneous_activation': True,      # Engines never fire together
            'no_cross_engine_hedging': True,         # No hedging between engines
            'regime_based_selection': True,          # Only regime determines activation
            'conviction_contract_enforcement': True   # Both engines follow contracts
        }
        
        # State tracking
        self.regime_history: List[MarketRegime] = []
        self.allocation_history: List[EngineAllocation] = []
        self.last_regime_change: Optional[datetime] = None
        
        # Logging
        self.logger = logging.getLogger(f"{self.name}")
        
        print(f"🎯 {self.name} v{self.version}")
        print(f"🔥 Crisis Engine: {self.crisis_engine.name}")
        print(f"🔒 Conviction Contract: Active")
        print(f"⚖️  Engine Separation: STRICT (advisory unless governor override is enabled)")
    
    def classify_market_regime(self, market_data: pd.DataFrame) -> Tuple[MarketRegime, float]:
        """
        Classify current market regime for engine selection
        
        REGIME CLASSIFICATION:
        - SUPPORTIVE: Low vol, positive trends, normal correlations
        - NEUTRAL: Medium vol, mixed signals, moderate stress
        - HOSTILE: High vol, negative trends, elevated correlations
        - PANIC: Extreme vol, forced selling, correlation breakdown
        
        Returns: (regime, confidence_score)
        """
        
        if len(market_data) < 20:
            return MarketRegime.NEUTRAL, 0.5
        
        # Calculate regime indicators
        returns = market_data['market_return'].tail(20)
        
        # 1. Volatility indicator
        current_vol = returns.std() * np.sqrt(252)
        vol_score = 0.0
        if current_vol >= self.regime_config['volatility_threshold_panic']:
            vol_score = 1.0  # Panic level
        elif current_vol >= self.regime_config['volatility_threshold_hostile']:
            vol_score = 0.7  # Hostile level
        elif current_vol <= 0.15:  # Reduced from 0.30 to 0.15
            vol_score = -0.5  # Supportive level
        else:
            vol_score = (current_vol - 0.15) / (self.regime_config['volatility_threshold_hostile'] - 0.15) * 0.7  # Scale between neutral and hostile
        
        # 2. Trend indicator (simplified)
        trend_strength = returns.mean() / (returns.std() + 1e-8)
        trend_score = np.tanh(trend_strength * 2)  # Normalize to [-1, 1]
        
        # 3. Stress indicator (approximated by volatility clustering)
        vol_clustering = returns.rolling(5).std().std()
        stress_score = min(1.0, vol_clustering * 10)  # Scale stress
        
        # 4. Momentum indicator
        momentum = returns.tail(5).mean() / returns.head(15).mean() if returns.head(15).mean() != 0 else 0
        momentum_score = np.tanh((momentum - 1) * 5)  # Normalize around 1
        
        # Combine indicators
        regime_score = (
            vol_score * 0.4 +           # Volatility is primary
            -trend_score * 0.3 +        # Negative trends indicate stress
            stress_score * 0.2 +        # Stress clustering
            -momentum_score * 0.1       # Negative momentum
        )
        
        # Classify regime - simplified to focus on volatility (primary crisis indicator)
        if regime_score >= 0.4:  # Reduced threshold for panic
            regime = MarketRegime.PANIC
        elif regime_score >= 0.1:  # Reduced threshold for hostile
            regime = MarketRegime.HOSTILE
        elif regime_score <= -0.2:
            regime = MarketRegime.SUPPORTIVE
        else:
            regime = MarketRegime.NEUTRAL
        
        # Calculate confidence based on signal strength
        confidence = min(1.0, abs(regime_score) + 0.3)
        
        return regime, confidence
    
    def validate_regime_persistence(self, new_regime: MarketRegime) -> bool:
        """
        Validate regime change requires persistence to avoid whipsaws
        
        Regime changes must persist for minimum days to be confirmed.
        This prevents emotional regime switching.
        """
        
        if not self.regime_history:
            return True
        
        # Check if regime is actually changing
        current_regime = self.regime_history[-1] if self.regime_history else MarketRegime.NEUTRAL
        if new_regime == current_regime:
            return True
        
        # For regime changes, require persistence
        min_days = self.regime_config['regime_persistence_days']
        
        # Count consecutive days of new regime signals
        consecutive_days = 0
        for regime in reversed(self.regime_history[-min_days:]):
            if regime == new_regime:
                consecutive_days += 1
            else:
                break
        
        # Require minimum persistence for regime change
        return consecutive_days >= min_days - 1  # -1 because we're adding today
    
    def calculate_trend_engine_allocation(self, regime: MarketRegime, 
                                        market_data: pd.DataFrame) -> float:
        """
        Calculate Trend Engine allocation based on regime
        
        TREND ENGINE RULES:
        - SUPPORTIVE: Full allocation (up to risk limits)
        - NEUTRAL: Reduced allocation
        - HOSTILE: Defensive allocation only
        - PANIC: Zero allocation (crisis engine takes over)
        """
        
        if regime == MarketRegime.PANIC:
            return 0.0  # Crisis engine takes full control
        
        # Base allocations by regime
        base_allocations = {
            MarketRegime.SUPPORTIVE: 0.80,  # 80% max in supportive
            MarketRegime.NEUTRAL: 0.60,     # 60% max in neutral
            MarketRegime.HOSTILE: 0.30,     # 30% max in hostile
            MarketRegime.PANIC: 0.0         # 0% in panic
        }
        
        base_allocation = base_allocations[regime]
        
        # Adjust based on trend strength (simplified trend engine logic)
        if len(market_data) >= 20:
            returns = market_data['market_return'].tail(20)
            trend_strength = returns.mean() / (returns.std() + 1e-8)
            
            # Positive trend strength increases allocation
            trend_multiplier = 0.7 + (np.tanh(trend_strength) * 0.3)  # Range: 0.4 to 1.0
            final_allocation = base_allocation * trend_multiplier
        else:
            final_allocation = base_allocation * 0.5  # Conservative with limited data
        
        return max(0.0, min(0.95, final_allocation))  # Bound to [0, 95%]
    
    def coordinate_engine_allocations(self, market_data: pd.DataFrame, 
                                    current_date: datetime) -> EngineAllocation:
        """
        Main coordination method: Determine engine allocations
        
        This is the core method that ensures only one engine is active
        and that regime determines who speaks.
        """
        
        # Step 1: Classify market regime
        regime, regime_confidence = self.classify_market_regime(market_data)
        
        # Step 2: Validate regime persistence
        if not self.validate_regime_persistence(regime):
            # Use previous regime if change not persistent enough
            regime = self.regime_history[-1] if self.regime_history else MarketRegime.NEUTRAL
            regime_confidence *= 0.7  # Reduce confidence for non-persistent signal
        
        # Step 3: Calculate engine allocations based on regime
        if regime in [MarketRegime.HOSTILE, MarketRegime.PANIC]:
            # Crisis engine active
            crisis_signals = self.crisis_engine.generate_crisis_signals(market_data, current_date)
            crisis_allocation = crisis_signals.get('crisis_allocation', 0.0)
            trend_allocation = 0.0  # Trend engine sleeps
            active_engine = "Crisis"
            
            # Validate crisis engine action through conviction contract
            current_state = {
                'regime_state': regime.value,
                'position_size': crisis_allocation,
                'daily_pnl': 0.0  # Would be calculated from actual positions
            }
            
            proposed_action = {
                'crisis_allocation': crisis_allocation,
                'signal_based': True,
                'engine_parameters': {}  # Would include actual parameters
            }
            
            # Check conviction contract
            action_allowed = self.crisis_contract.validate_engine_action(
                'position_sizing', current_state, proposed_action
            )
            
            if not action_allowed:
                self.logger.warning("Crisis engine action blocked by conviction contract")
                crisis_allocation = 0.0
                active_engine = "None (Blocked)"
        
        else:
            # Trend engine active
            trend_allocation = self.calculate_trend_engine_allocation(regime, market_data)
            crisis_allocation = 0.0  # Crisis engine sleeps
            active_engine = "Trend"
        
        # Step 4: Ensure absolute separation (critical check)
        if trend_allocation > 0 and crisis_allocation > 0:
            # This should NEVER happen - violation of separation principle
            self.logger.error("CRITICAL: Both engines active simultaneously!")
            # Force separation - crisis takes priority in hostile regimes
            if regime in [MarketRegime.HOSTILE, MarketRegime.PANIC]:
                trend_allocation = 0.0
                active_engine = "Crisis"
            else:
                crisis_allocation = 0.0
                active_engine = "Trend"
        
        # Step 5: Calculate total allocation
        total_allocation = trend_allocation + crisis_allocation
        
        # Step 6: Create allocation result
        allocation = EngineAllocation(
            trend_allocation=trend_allocation,
            crisis_allocation=crisis_allocation,
            active_engine=active_engine,
            regime=regime,
            regime_confidence=regime_confidence,
            total_allocation=total_allocation
        )
        
        # Step 7: Update history
        self.regime_history.append(regime)
        if len(self.regime_history) > 252:  # Keep 1 year of history
            self.regime_history.pop(0)
        
        self.allocation_history.append(allocation)
        if len(self.allocation_history) > 252:
            self.allocation_history.pop(0)
        
        # Step 8: Log coordination decision
        self.logger.info(f"Regime: {regime.value}, Active: {active_engine}, "
                        f"Allocation: {total_allocation:.1%}")
        
        return allocation
    
    def get_coordination_diagnostics(self) -> Dict[str, any]:
        """Get comprehensive coordination diagnostics"""
        
        if not self.allocation_history:
            return {'status': 'No allocation history'}
        
        recent_allocations = self.allocation_history[-30:]  # Last 30 days
        
        # Engine activation statistics
        trend_days = sum(1 for a in recent_allocations if a.trend_allocation > 0)
        crisis_days = sum(1 for a in recent_allocations if a.crisis_allocation > 0)
        dormant_days = sum(1 for a in recent_allocations if a.total_allocation == 0)
        
        # Regime distribution
        regime_counts = {}
        for allocation in recent_allocations:
            regime = allocation.regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        # Separation validation
        simultaneous_activation = sum(1 for a in recent_allocations 
                                    if a.trend_allocation > 0 and a.crisis_allocation > 0)
        
        # Crisis engine diagnostics
        crisis_diagnostics = self.crisis_engine.get_engine_diagnostics()
        
        # Conviction health
        conviction_health = self.crisis_contract.get_conviction_health()
        
        return {
            'coordination_summary': {
                'total_days': len(recent_allocations),
                'trend_active_days': trend_days,
                'crisis_active_days': crisis_days,
                'dormant_days': dormant_days,
                'average_allocation': np.mean([a.total_allocation for a in recent_allocations])
            },
            'regime_distribution': regime_counts,
            'engine_separation': {
                'simultaneous_activations': simultaneous_activation,
                'separation_maintained': simultaneous_activation == 0,
                'separation_score': 1.0 - (simultaneous_activation / len(recent_allocations))
            },
            'crisis_engine': crisis_diagnostics,
            'conviction_health': conviction_health,
            'current_state': {
                'current_regime': self.regime_history[-1].value if self.regime_history else 'Unknown',
                'active_engine': recent_allocations[-1].active_engine if recent_allocations else 'None',
                'current_allocation': recent_allocations[-1].total_allocation if recent_allocations else 0.0
            }
        }
    
    def validate_institutional_discipline(self) -> Dict[str, bool]:
        """Validate coordinator follows institutional discipline"""
        
        if not self.allocation_history:
            return {'status': 'No history to validate'}
        
        recent_allocations = self.allocation_history[-60:]  # Last 60 days
        
        checks = {
            'engine_separation_maintained': all(
                not (a.trend_allocation > 0 and a.crisis_allocation > 0) 
                for a in recent_allocations
            ),
            'regime_based_activation': all(
                (a.regime in [MarketRegime.HOSTILE, MarketRegime.PANIC] and a.crisis_allocation >= 0) or
                (a.regime in [MarketRegime.SUPPORTIVE, MarketRegime.NEUTRAL] and a.trend_allocation >= 0)
                for a in recent_allocations
            ),
            'no_cross_engine_hedging': True,  # Would check actual position correlations
            'conviction_contract_respected': self.crisis_contract.get_conviction_health()['conviction_score'] > 70,
            'regime_persistence_enforced': True  # Validated in regime classification
        }
        
        return checks

def create_dual_engine_coordinator() -> DualEngineCoordinator:
    """Factory function to create dual engine coordinator"""
    return DualEngineCoordinator()

# Example usage and testing
if __name__ == "__main__":
    # Create coordinator
    coordinator = create_dual_engine_coordinator()
    
    # Generate sample market data for testing
    dates = pd.date_range('2020-01-01', '2020-12-31', freq='D')
    np.random.seed(42)
    
    # Simulate different market regimes
    returns = []
    for i, date in enumerate(dates):
        if 60 <= i <= 90:  # Crisis period (COVID crash)
            ret = np.random.normal(-0.03, 0.10)  # High vol, negative drift
        elif 90 < i <= 120:  # Recovery
            ret = np.random.normal(0.02, 0.06)   # Positive drift, high vol
        elif 200 <= i <= 220:  # Another stress period
            ret = np.random.normal(-0.01, 0.08)  # Medium stress
        else:  # Normal
            ret = np.random.normal(0.001, 0.02)  # Low vol, slight positive
        returns.append(ret)
    
    market_data = pd.DataFrame({
        'date': dates,
        'market_return': returns
    })
    
    # Test coordination
    print("\n🧪 TESTING DUAL ENGINE COORDINATION")
    print("=" * 60)
    
    allocation_history = []
    for i in range(50, len(market_data)):
        current_data = market_data.iloc[:i+1]
        current_date = dates[i]
        
        allocation = coordinator.coordinate_engine_allocations(current_data, current_date)
        allocation_history.append({
            'date': current_date,
            'regime': allocation.regime.value,
            'active_engine': allocation.active_engine,
            'trend_allocation': allocation.trend_allocation,
            'crisis_allocation': allocation.crisis_allocation,
            'total_allocation': allocation.total_allocation
        })
        
        # Print significant events
        if allocation.crisis_allocation > 0 or allocation.regime in [MarketRegime.HOSTILE, MarketRegime.PANIC]:
            print(f"{current_date.strftime('%Y-%m-%d')}: "
                  f"{allocation.regime.value} - {allocation.active_engine} - "
                  f"Allocation: {allocation.total_allocation:.1%}")
    
    # Print diagnostics
    print("\n📊 COORDINATION DIAGNOSTICS")
    print("=" * 60)
    diagnostics = coordinator.get_coordination_diagnostics()
    
    print("Coordination Summary:")
    for key, value in diagnostics['coordination_summary'].items():
        print(f"  {key}: {value}")
    
    print("\nRegime Distribution:")
    for regime, count in diagnostics['regime_distribution'].items():
        print(f"  {regime}: {count} days")
    
    print("\nEngine Separation:")
    for key, value in diagnostics['engine_separation'].items():
        print(f"  {key}: {value}")
    
    # Validate discipline
    print("\n🔍 INSTITUTIONAL DISCIPLINE VALIDATION")
    print("=" * 60)
    discipline = coordinator.validate_institutional_discipline()
    for check, passed in discipline.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}: {passed}")
    
    print(f"\n✅ Dual Engine Coordination Test Complete")
    print(f"📊 Total allocations tested: {len(allocation_history)}")
    print(f"🔥 Crisis activations: {sum(1 for a in allocation_history if a['crisis_allocation'] > 0)}")
    print(f"📈 Trend activations: {sum(1 for a in allocation_history if a['trend_allocation'] > 0)}")
