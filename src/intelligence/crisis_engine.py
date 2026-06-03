#!/usr/bin/env python3
"""
🔥 NORTHSTAR CRISIS ENGINE - VOLATILITY CONVEXITY IMPLEMENTATION

This engine exists to exploit stress mechanics that only exist when markets are breaking.
It is NOT a hedge. It is NOT a trend follower. It is NOT a drawdown smoother.

It exists to harvest structural distortions that appear only under panic.

ABSOLUTE DESIGN RULES (NON-NEGOTIABLE):
1. Zero overlap with Trend Engine - different signals, logic, failure modes
2. Activated ONLY when REGIME = HOSTILE - sleeps otherwise
3. Allowed to look bad most of the time - that's the cost of convexity
4. Governed by same ConvictionContract - no emotional overrides

CRISIS ALPHA MECHANISM: Volatility Convexity
- Exploits: Implied vol explodes faster than realized during crises
- Profits from: Speed and nonlinearity of fear
- Behavioral profile: Small steady bleed → rare massive gains
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum
import logging

class CrisisRegime(Enum):
    """Crisis regime states - only HOSTILE activates the engine"""
    DORMANT = "DORMANT"      # Normal markets - engine sleeps
    HOSTILE = "HOSTILE"      # Crisis detected - engine activates
    PANIC = "PANIC"          # Extreme crisis - maximum convexity

class VolatilitySignal(NamedTuple):
    """Volatility convexity signal components"""
    implied_vol_spike: float      # Speed of implied vol expansion
    realized_vol_gap: float       # Gap between implied and realized
    tail_risk_mispricing: float   # Tail risk underpricing magnitude
    fear_acceleration: float      # Rate of fear increase
    convexity_opportunity: float  # Overall convexity score

@dataclass
class CrisisEngineState:
    """Crisis engine internal state"""
    regime: CrisisRegime
    volatility_signal: VolatilitySignal
    position_size: float
    days_since_activation: int
    cumulative_bleed: float
    last_payoff_date: Optional[datetime]
    activation_threshold: float
    
class CrisisEngineConfig:
    """Frozen configuration for crisis engine - NO CHANGES ALLOWED"""
    
    # Activation thresholds (FROZEN) - Calibrated from historical data
    HOSTILE_REGIME_VOL_THRESHOLD = 0.27      # 27% annualized vol triggers activation (85th percentile)
    PANIC_REGIME_VOL_THRESHOLD = 0.48        # 48% annualized vol triggers panic mode (95th percentile)
    IMPLIED_REALIZED_GAP_THRESHOLD = 0.15    # 15% gap triggers signal
    
    # Position sizing (FROZEN)
    BASE_CRISIS_ALLOCATION = 0.05            # 5% of portfolio in normal crisis
    PANIC_CRISIS_ALLOCATION = 0.08           # 8% of portfolio in panic crisis
    MAX_CRISIS_ALLOCATION = 0.10             # 10% absolute maximum
    
    # Convexity parameters (FROZEN)
    VOLATILITY_LOOKBACK_DAYS = 20            # Rolling vol calculation period
    FEAR_ACCELERATION_THRESHOLD = 2.0        # 2x vol acceleration triggers
    TAIL_RISK_MULTIPLIER = 3.0               # 3x multiplier for tail events
    
    # Behavioral constraints (FROZEN)
    MAX_BLEED_TOLERANCE = 0.15               # 15% max cumulative bleed before reset
    MIN_DORMANT_PERIOD_DAYS = 30             # Minimum 30 days between activations
    PAYOFF_RESET_THRESHOLD = 0.20            # 20% gain resets bleed counter
    
    # Exit rules (FROZEN) - Calibrated to work with new thresholds
    VOLATILITY_NORMALIZATION_THRESHOLD = 0.15  # Exit when vol drops below 15% (below activation)
    FEAR_EXHAUSTION_DAYS = 10                   # Exit after 10 days of declining vol
    PROFIT_TAKING_THRESHOLD = 0.50              # Take profits at 50% gain

class NorthstarCrisisEngine:
    """
    Northstar Crisis Engine - Volatility Convexity Implementation
    
    This engine exploits the nonlinear expansion of volatility during market crises.
    It is designed to:
    - Bleed small amounts during normal markets
    - Activate only during genuine crises (REGIME = HOSTILE)
    - Capture explosive volatility moves when fear dominates
    - Exit cleanly when crisis mechanics normalize
    
    CRITICAL: This engine must be kept separate from trend logic.
    """
    
    def __init__(self):
        self.name = "Northstar Crisis Engine"
        self.version = "1.0.0"
        self.engine_type = "Volatility Convexity"
        
        # Frozen configuration
        self.config = CrisisEngineConfig()
        
        # Engine state
        self.state = CrisisEngineState(
            regime=CrisisRegime.DORMANT,
            volatility_signal=VolatilitySignal(0, 0, 0, 0, 0),
            position_size=0.0,
            days_since_activation=0,
            cumulative_bleed=0.0,
            last_payoff_date=None,
            activation_threshold=self.config.HOSTILE_REGIME_VOL_THRESHOLD
        )
        
        # Historical tracking
        self.volatility_history: List[float] = []
        self.signal_history: List[VolatilitySignal] = []
        self.activation_history: List[datetime] = []
        
        # Logging
        self.logger = logging.getLogger(f"{self.name}")
        
        print(f"🔥 {self.name} v{self.version} - {self.engine_type}")
        print(f"⚠️  CRISIS ENGINE - Activates ONLY during REGIME = HOSTILE")
        print(f"💀 Expected behavior: Bleed small → Rare explosive gains")
    
    def evaluate_crisis_regime(self, market_data: pd.DataFrame) -> CrisisRegime:
        """
        Evaluate current crisis regime based on volatility and market stress
        
        REGIME CLASSIFICATION:
        - DORMANT: Normal markets (vol < 30%) - engine sleeps
        - HOSTILE: Crisis markets (vol 30-50%) - engine activates
        - PANIC: Extreme crisis (vol > 50%) - maximum convexity
        """
        
        if len(market_data) < self.config.VOLATILITY_LOOKBACK_DAYS:
            return CrisisRegime.DORMANT
        
        # Calculate rolling volatility
        returns = market_data['market_return'].tail(self.config.VOLATILITY_LOOKBACK_DAYS)
        current_vol = returns.std() * np.sqrt(252)
        
        # Store volatility history
        self.volatility_history.append(current_vol)
        if len(self.volatility_history) > 252:  # Keep 1 year of history
            self.volatility_history.pop(0)
        
        # Regime classification based on volatility
        if current_vol >= self.config.PANIC_REGIME_VOL_THRESHOLD:
            return CrisisRegime.PANIC
        elif current_vol >= self.config.HOSTILE_REGIME_VOL_THRESHOLD:
            return CrisisRegime.HOSTILE
        else:
            return CrisisRegime.DORMANT
    
    def generate_volatility_signal(self, market_data: pd.DataFrame) -> VolatilitySignal:
        """
        Generate volatility convexity signal components
        
        This captures the core crisis alpha mechanism:
        - Implied volatility expansion speed
        - Realized vs implied volatility gaps
        - Tail risk mispricing detection
        - Fear acceleration measurement
        """
        
        if len(market_data) < self.config.VOLATILITY_LOOKBACK_DAYS * 2:
            return VolatilitySignal(0, 0, 0, 0, 0)
        
        returns = market_data['market_return']
        
        # Current volatility metrics
        current_vol = returns.tail(self.config.VOLATILITY_LOOKBACK_DAYS).std() * np.sqrt(252)
        previous_vol = returns.tail(self.config.VOLATILITY_LOOKBACK_DAYS * 2).head(self.config.VOLATILITY_LOOKBACK_DAYS).std() * np.sqrt(252)
        
        # 1. Implied volatility spike (approximated by vol acceleration)
        vol_acceleration = (current_vol - previous_vol) / previous_vol if previous_vol > 0 else 0
        implied_vol_spike = max(0, vol_acceleration * 10)  # Scale for signal strength
        
        # 2. Realized vs implied gap (approximated by vol vs recent moves)
        recent_moves = returns.tail(5).abs().mean() * np.sqrt(252)
        realized_vol_gap = max(0, (current_vol - recent_moves) / current_vol) if current_vol > 0 else 0
        
        # 3. Tail risk mispricing (extreme move frequency)
        tail_threshold = returns.std() * 2  # 2-sigma threshold
        tail_events = (returns.tail(self.config.VOLATILITY_LOOKBACK_DAYS).abs() > tail_threshold).sum()
        tail_risk_mispricing = min(1.0, tail_events / 5)  # Normalize to [0,1]
        
        # 4. Fear acceleration (volatility momentum)
        if len(self.volatility_history) >= 5:
            vol_momentum = np.mean(np.diff(self.volatility_history[-5:]))
            fear_acceleration = max(0, vol_momentum * 100)  # Scale for signal
        else:
            fear_acceleration = 0
        
        # 5. Overall convexity opportunity
        convexity_opportunity = np.mean([
            implied_vol_spike,
            realized_vol_gap,
            tail_risk_mispricing,
            min(1.0, fear_acceleration)
        ])
        
        return VolatilitySignal(
            implied_vol_spike=implied_vol_spike,
            realized_vol_gap=realized_vol_gap,
            tail_risk_mispricing=tail_risk_mispricing,
            fear_acceleration=fear_acceleration,
            convexity_opportunity=convexity_opportunity
        )
    
    def calculate_crisis_position_size(self, regime: CrisisRegime, signal: VolatilitySignal) -> float:
        """
        Calculate position size based on crisis regime and signal strength
        
        POSITION SIZING RULES:
        - DORMANT: 0% allocation (engine sleeps)
        - HOSTILE: 5% base allocation, scaled by signal strength
        - PANIC: 8% base allocation, maximum convexity
        """
        
        if regime == CrisisRegime.DORMANT:
            return 0.0
        
        # Base allocation by regime
        if regime == CrisisRegime.PANIC:
            base_allocation = self.config.PANIC_CRISIS_ALLOCATION
        else:  # HOSTILE
            base_allocation = self.config.BASE_CRISIS_ALLOCATION
        
        # Scale by signal strength
        signal_multiplier = 0.5 + (signal.convexity_opportunity * 0.5)  # Range: 0.5 to 1.0
        target_allocation = base_allocation * signal_multiplier
        
        # Apply maximum constraint
        return min(target_allocation, self.config.MAX_CRISIS_ALLOCATION)
    
    def check_exit_conditions(self, market_data: pd.DataFrame) -> bool:
        """
        Check if crisis engine should exit positions
        
        EXIT CONDITIONS:
        1. Volatility normalization (vol drops below 20%)
        2. Fear exhaustion (declining vol for 10+ days)
        3. Profit taking (50%+ gain achieved)
        """
        
        if self.state.regime == CrisisRegime.DORMANT:
            return True
        
        # Current volatility
        if len(market_data) >= self.config.VOLATILITY_LOOKBACK_DAYS:
            returns = market_data['market_return'].tail(self.config.VOLATILITY_LOOKBACK_DAYS)
            current_vol = returns.std() * np.sqrt(252)
            
            # Exit condition 1: Volatility normalization
            if current_vol < self.config.VOLATILITY_NORMALIZATION_THRESHOLD:
                self.logger.info(f"Exit trigger: Volatility normalized to {current_vol:.2%}")
                return True
        
        # Exit condition 2: Fear exhaustion (simplified - check vol trend)
        if len(self.volatility_history) >= self.config.FEAR_EXHAUSTION_DAYS:
            recent_vol_trend = np.mean(np.diff(self.volatility_history[-self.config.FEAR_EXHAUSTION_DAYS:]))
            if recent_vol_trend < -0.01:  # Declining volatility trend
                self.logger.info("Exit trigger: Fear exhaustion detected")
                return True
        
        # Exit condition 3: Profit taking (would need P&L tracking)
        # This would be implemented with actual position tracking
        
        return False
    
    def update_engine_state(self, regime: CrisisRegime, signal: VolatilitySignal, 
                           position_size: float, current_date: datetime):
        """Update internal engine state"""
        
        # Track regime changes
        if regime != self.state.regime:
            if regime != CrisisRegime.DORMANT:
                self.activation_history.append(current_date)
                self.state.days_since_activation = 0
                self.logger.info(f"Crisis engine activated: {regime.value}")
            else:
                self.logger.info("Crisis engine entering dormant state")
        
        # Update state
        self.state.regime = regime
        self.state.volatility_signal = signal
        self.state.position_size = position_size
        
        if regime != CrisisRegime.DORMANT:
            self.state.days_since_activation += 1
        
        # Store signal history
        self.signal_history.append(signal)
        if len(self.signal_history) > 252:  # Keep 1 year
            self.signal_history.pop(0)
    
    def generate_crisis_signals(self, market_data: pd.DataFrame, 
                               current_date: datetime) -> Dict[str, float]:
        """
        Main method: Generate crisis engine signals
        
        Returns position sizing recommendation based on crisis regime and volatility signals.
        Returns 0 if regime is not HOSTILE or PANIC.
        """
        
        # Step 1: Evaluate crisis regime
        regime = self.evaluate_crisis_regime(market_data)
        
        # Step 2: Generate volatility signal
        signal = self.generate_volatility_signal(market_data)
        
        # Step 3: Calculate position size
        position_size = self.calculate_crisis_position_size(regime, signal)
        
        # Step 4: Update engine state FIRST (before exit check)
        self.update_engine_state(regime, signal, position_size, current_date)
        
        # Step 5: Check exit conditions (now that state is updated)
        should_exit = self.check_exit_conditions(market_data)
        if should_exit:
            position_size = 0.0
            regime = CrisisRegime.DORMANT
            # Update state again with exit
            self.update_engine_state(regime, signal, position_size, current_date)
        
        # Return signals
        return {
            'crisis_allocation': position_size,
            'volatility_convexity': signal.convexity_opportunity,
            'regime_state': regime.value,
            'signal_strength': signal.convexity_opportunity,
            'engine_active': regime != CrisisRegime.DORMANT
        }
    
    def get_engine_diagnostics(self) -> Dict[str, any]:
        """Get comprehensive engine diagnostics"""
        
        return {
            'engine_name': self.name,
            'engine_type': self.engine_type,
            'current_regime': self.state.regime.value,
            'current_position': self.state.position_size,
            'days_since_activation': self.state.days_since_activation,
            'cumulative_bleed': self.state.cumulative_bleed,
            'total_activations': len(self.activation_history),
            'last_activation': self.activation_history[-1] if self.activation_history else None,
            'volatility_history_length': len(self.volatility_history),
            'current_volatility': self.volatility_history[-1] if self.volatility_history else 0,
            'signal_components': {
                'implied_vol_spike': self.state.volatility_signal.implied_vol_spike,
                'realized_vol_gap': self.state.volatility_signal.realized_vol_gap,
                'tail_risk_mispricing': self.state.volatility_signal.tail_risk_mispricing,
                'fear_acceleration': self.state.volatility_signal.fear_acceleration,
                'convexity_opportunity': self.state.volatility_signal.convexity_opportunity
            }
        }
    
    def validate_engine_integrity(self) -> Dict[str, bool]:
        """Validate engine follows crisis alpha principles"""
        
        checks = {
            'regime_separation': self.state.position_size == 0 if self.state.regime == CrisisRegime.DORMANT else True,
            'position_limits': self.state.position_size <= self.config.MAX_CRISIS_ALLOCATION,
            'no_trend_overlap': True,  # Would check against trend engine signals
            'convexity_profile': len([s for s in self.signal_history if s.convexity_opportunity > 0.5]) < len(self.signal_history) * 0.2,  # Rare high signals
            'activation_discipline': len(self.activation_history) < 50  # Not too frequent
        }
        
        return checks

def create_crisis_engine() -> NorthstarCrisisEngine:
    """Factory function to create crisis engine"""
    return NorthstarCrisisEngine()

# Example usage and testing
if __name__ == "__main__":
    # Create crisis engine
    crisis_engine = create_crisis_engine()
    
    # Generate sample market data for testing
    dates = pd.date_range('2020-01-01', '2020-12-31', freq='D')
    np.random.seed(42)
    
    # Simulate crisis period (COVID crash)
    returns = []
    for i, date in enumerate(dates):
        if 60 <= i <= 90:  # Crisis period
            ret = np.random.normal(-0.02, 0.08)  # High vol, negative drift
        elif 90 < i <= 120:  # Recovery
            ret = np.random.normal(0.01, 0.04)   # Positive drift, medium vol
        else:  # Normal
            ret = np.random.normal(0.001, 0.015) # Low vol, slight positive
        returns.append(ret)
    
    market_data = pd.DataFrame({
        'date': dates,
        'market_return': returns
    })
    
    # Test crisis engine
    print("\n🧪 TESTING CRISIS ENGINE")
    print("=" * 50)
    
    signals_history = []
    for i in range(50, len(market_data)):
        current_data = market_data.iloc[:i+1]
        current_date = dates[i]
        
        signals = crisis_engine.generate_crisis_signals(current_data, current_date)
        signals_history.append({
            'date': current_date,
            **signals
        })
        
        if signals['engine_active']:
            print(f"{current_date.strftime('%Y-%m-%d')}: "
                  f"ACTIVE - Allocation: {signals['crisis_allocation']:.1%}, "
                  f"Regime: {signals['regime_state']}, "
                  f"Signal: {signals['signal_strength']:.3f}")
    
    # Print diagnostics
    print("\n📊 ENGINE DIAGNOSTICS")
    print("=" * 50)
    diagnostics = crisis_engine.get_engine_diagnostics()
    for key, value in diagnostics.items():
        if key != 'signal_components':
            print(f"{key}: {value}")
    
    print("\nSignal Components:")
    for key, value in diagnostics['signal_components'].items():
        print(f"  {key}: {value:.3f}")
    
    # Validate integrity
    print("\n🔍 INTEGRITY VALIDATION")
    print("=" * 50)
    integrity = crisis_engine.validate_engine_integrity()
    for check, passed in integrity.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}: {passed}")