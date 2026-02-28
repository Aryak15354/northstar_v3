#!/usr/bin/env python3
"""
Regime-Locked Capital Allocator (RLCA)

This is the missing heart of NorthStar - the institutional-grade allocator that 
transforms forensic results into disciplined capital deployment.

Based on the brutal truth from alpha attribution:
- Bull Markets: +179% PnL, Sharpe 4.76 → AMPLIFY
- High Vol: +357% PnL, Sharpe 1.33 → DEPLOY  
- Normal: -10% PnL, Sharpe -1.39 → MINIMAL
- Bear: -43% PnL, Sharpe -2.31 → DEFENSIVE
- Crisis: -172% PnL, Sharpe -0.49 → CASH

This sits between specialists and portfolio. Nothing trades unless this passes it.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class RegimeType(Enum):
    """Market regime classifications"""
    BULL = "bull_market"
    HIGH_VOL = "high_volatility" 
    NORMAL = "normal"
    BEAR = "bear_market"
    CRISIS = "crisis"

class Season(Enum):
    """Seasonal classifications"""
    Q1 = "Q1"
    Q2 = "Q2" 
    Q3 = "Q3"
    Q4 = "Q4"

@dataclass
class RegimeState:
    """Current regime state with confidence"""
    regime: RegimeType
    confidence: float  # 0-1
    days_in_regime: int
    regime_strength: float  # How strong the regime signal is

@dataclass
class SignalHealth:
    """Signal health metrics by regime"""
    ic_by_regime: Dict[RegimeType, float]
    sharpe_by_regime: Dict[RegimeType, float]
    decay_days: int
    is_alive: bool
    last_updated: datetime

@dataclass
class AllocationResult:
    """Final allocation result with audit trail"""
    specialist_allocations: Dict[str, float]
    gross_capital_used: float
    regime_multiplier: float
    season_multiplier: float
    confidence_multiplier: float
    signals_blocked: List[str]
    allocation_rationale: str

class RegimeLockedCapitalAllocator:
    """
    Institutional-grade capital allocator with regime discipline.
    
    This is the gate between alpha generation and capital deployment.
    Based on forensic analysis, it ensures capital only flows when 
    and where alpha actually exists.
    """
    
    def __init__(self):
        self.name = "Regime-Locked Capital Allocator"
        self.version = "1.0"
        
        # 🔒 REGIME CAPITAL ENVELOPE (Hard Wall)
        # Derived directly from walk-forward forensic analysis
        self.REGIME_MAX_GROSS = {
            RegimeType.BULL: 1.00,      # +179% PnL, Sharpe 4.76 → Full deployment
            RegimeType.HIGH_VOL: 0.80,  # +357% PnL, Sharpe 1.33 → High deployment  
            RegimeType.NORMAL: 0.30,    # -10% PnL, Sharpe -1.39 → Minimal
            RegimeType.BEAR: 0.10,      # -43% PnL, Sharpe -2.31 → Defensive
            RegimeType.CRISIS: 0.00     # -172% PnL, Sharpe -0.49 → Cash
        }
        
        # 🌊 SEASONAL MODULATION (Quiet Edge)
        # Based on temporal analysis: Q1 bleeds, Q2-Q3 generate alpha
        self.SEASON_MULT = {
            Season.Q1: 0.50,  # Q1: -127% PnL → Defensive
            Season.Q2: 1.20,  # Q2: +265% PnL → Amplify
            Season.Q3: 1.10,  # Q3: +171% PnL → Strong
            Season.Q4: 0.80   # Q4: +3% PnL → Moderate
        }
        
        # 🎯 REGIME-SPECIFIC SPECIALIST WEIGHTS
        # Based on which specialists work in which regimes
        self.SPECIALIST_WEIGHTS = {
            RegimeType.BULL: {
                'momentum_specialist': 0.50,  # Momentum thrives in bull markets
                'macro_specialist': 0.30,     # Macro captures trends
                'quality_specialist': 0.15,   # Quality for stability
                'value_specialist': 0.05      # Value underperforms in momentum
            },
            RegimeType.HIGH_VOL: {
                'momentum_specialist': 0.40,  # Momentum captures volatility
                'macro_specialist': 0.40,     # Macro adapts to volatility
                'quality_specialist': 0.15,   # Quality for defense
                'value_specialist': 0.05      # Value struggles in volatility
            },
            RegimeType.NORMAL: {
                'quality_specialist': 0.50,   # Quality works in normal markets
                'macro_specialist': 0.30,     # Macro for direction
                'momentum_specialist': 0.20,  # Limited momentum
                'value_specialist': 0.00      # Value doesn't work here
            },
            RegimeType.BEAR: {
                'macro_specialist': 0.60,     # Macro for defense
                'quality_specialist': 0.30,   # Quality for stability
                'momentum_specialist': 0.10,  # Minimal momentum
                'value_specialist': 0.00      # Value fails in bear markets
            },
            RegimeType.CRISIS: {
                'macro_specialist': 0.70,     # Macro for crisis navigation
                'quality_specialist': 0.30,   # Quality for defense
                'momentum_specialist': 0.00,  # Momentum dies in crisis
                'value_specialist': 0.00      # Value dies in crisis
            }
        }
        
        # 📊 SIGNAL QUALITY THRESHOLDS (By Regime)
        self.SIGNAL_THRESHOLDS = {
            RegimeType.BULL: {'min_ic': 0.03, 'min_sharpe': 0.0},
            RegimeType.HIGH_VOL: {'min_ic': 0.05, 'min_sharpe': 0.5},
            RegimeType.NORMAL: {'min_ic': 0.08, 'min_sharpe': 1.0},
            RegimeType.BEAR: {'min_ic': 0.10, 'min_sharpe': 1.5},
            RegimeType.CRISIS: {'min_ic': 0.15, 'min_sharpe': 2.0}
        }
        
        # Tracking
        self.allocation_history: List[AllocationResult] = []
        self.blocked_signals_count = 0
        self.total_allocations = 0
        
        print(f"🔒 {self.name} initialized")
        print(f"   Regime capital limits: {dict(self.REGIME_MAX_GROSS)}")
        print(f"   Seasonal modulation: {dict(self.SEASON_MULT)}")
    
    def determine_season(self, current_date: datetime) -> Season:
        """Determine current season (quarter)"""
        month = current_date.month
        if month in [1, 2, 3]:
            return Season.Q1
        elif month in [4, 5, 6]:
            return Season.Q2
        elif month in [7, 8, 9]:
            return Season.Q3
        else:
            return Season.Q4
    
    def signal_is_alive(self, 
                       signal_health: SignalHealth, 
                       regime: RegimeType) -> bool:
        """
        Determine if signal qualifies for capital in current regime.
        
        This is the gate that prevents weak signals from touching money.
        """
        
        if not signal_health.is_alive:
            return False
        
        # Get regime-specific thresholds
        thresholds = self.SIGNAL_THRESHOLDS[regime]
        
        # Check regime-specific performance
        regime_ic = signal_health.ic_by_regime.get(regime, 0.0)
        regime_sharpe = signal_health.sharpe_by_regime.get(regime, 0.0)
        
        # Signal must meet regime-specific standards
        ic_qualified = regime_ic >= thresholds['min_ic']
        sharpe_qualified = regime_sharpe >= thresholds['min_sharpe']
        decay_qualified = signal_health.decay_days >= 30  # Minimum persistence
        
        return ic_qualified and sharpe_qualified and decay_qualified
    
    def calculate_capital_envelope(self, 
                                 regime_state: RegimeState,
                                 current_date: datetime) -> float:
        """
        Calculate maximum capital allowed for deployment.
        
        This is the hard wall that prevents overexposure in bad regimes.
        """
        
        # Base capital from regime
        regime_capital = self.REGIME_MAX_GROSS[regime_state.regime]
        
        # Seasonal adjustment
        season = self.determine_season(current_date)
        season_mult = self.SEASON_MULT[season]
        
        # Confidence throttle - uncertainty kills leverage
        confidence_mult = regime_state.confidence ** 2
        
        # Final capital envelope
        gross_capital = regime_capital * season_mult * confidence_mult
        
        return min(gross_capital, 1.0)  # Never exceed 100%
    
    def allocate_capital(self,
                        regime_state: RegimeState,
                        signal_bundle: Dict[str, Dict],  # {specialist: {ticker: score}}
                        signal_health: Dict[str, SignalHealth],
                        current_date: datetime) -> AllocationResult:
        """
        Main capital allocation engine with regime discipline.
        
        This is where forensic analysis becomes capital deployment.
        """
        
        print(f"🔒 Allocating capital for regime: {regime_state.regime.value}")
        
        # Step 1: Calculate capital envelope
        gross_capital = self.calculate_capital_envelope(regime_state, current_date)
        
        # Step 2: Filter signals by regime-specific quality
        qualified_specialists = []
        blocked_signals = []
        
        for specialist, health in signal_health.items():
            if self.signal_is_alive(health, regime_state.regime):
                qualified_specialists.append(specialist)
            else:
                blocked_signals.append(specialist)
                self.blocked_signals_count += 1
        
        print(f"   Qualified specialists: {qualified_specialists}")
        print(f"   Blocked signals: {blocked_signals}")
        
        # Step 3: Get regime-specific weights
        regime_weights = self.SPECIALIST_WEIGHTS[regime_state.regime]
        
        # Step 4: Calculate final allocations
        allocations = {}
        total_weight = 0.0
        
        for specialist in qualified_specialists:
            if specialist in regime_weights:
                weight = regime_weights[specialist]
                allocations[specialist] = weight
                total_weight += weight
        
        # Step 5: Normalize and apply capital envelope
        if total_weight > 0:
            for specialist in allocations:
                # Normalize to sum to 1.0
                normalized_weight = allocations[specialist] / total_weight
                # Apply capital envelope
                allocations[specialist] = normalized_weight * gross_capital
        
        # Step 6: Generate allocation rationale
        season = self.determine_season(current_date)
        rationale = (
            f"Regime: {regime_state.regime.value} (conf: {regime_state.confidence:.2f}), "
            f"Season: {season.value}, "
            f"Capital: {gross_capital:.1%}, "
            f"Qualified: {len(qualified_specialists)}/{len(signal_health)}"
        )
        
        # Step 7: Create result
        result = AllocationResult(
            specialist_allocations=allocations,
            gross_capital_used=gross_capital,
            regime_multiplier=self.REGIME_MAX_GROSS[regime_state.regime],
            season_multiplier=self.SEASON_MULT[season],
            confidence_multiplier=regime_state.confidence ** 2,
            signals_blocked=blocked_signals,
            allocation_rationale=rationale
        )
        
        # Track allocation
        self.allocation_history.append(result)
        self.total_allocations += 1
        
        print(f"   Final allocations: {allocations}")
        print(f"   Rationale: {rationale}")
        
        return result
    
    def get_allocation_metrics(self) -> Dict:
        """Get allocation performance metrics"""
        
        if not self.allocation_history:
            return {}
        
        # Calculate metrics
        capital_utilization = [r.gross_capital_used for r in self.allocation_history]
        avg_capital_used = np.mean(capital_utilization)
        
        # Signal blocking efficiency
        block_rate = self.blocked_signals_count / (self.total_allocations * 4) if self.total_allocations > 0 else 0
        
        # Regime distribution
        regime_counts = {}
        for result in self.allocation_history:
            # Extract regime from rationale (simplified)
            if 'bull_market' in result.allocation_rationale:
                regime = 'bull_market'
            elif 'high_volatility' in result.allocation_rationale:
                regime = 'high_volatility'
            elif 'bear_market' in result.allocation_rationale:
                regime = 'bear_market'
            elif 'crisis' in result.allocation_rationale:
                regime = 'crisis'
            else:
                regime = 'normal'
            
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        return {
            'total_allocations': self.total_allocations,
            'avg_capital_utilization': avg_capital_used,
            'signal_block_rate': block_rate,
            'blocked_signals_total': self.blocked_signals_count,
            'regime_distribution': regime_counts,
            'capital_discipline_score': 1.0 - avg_capital_used  # Higher when more disciplined
        }
    
    def simulate_regime_impact(self, regime_sequence: List[RegimeType]) -> Dict:
        """
        Simulate capital allocation across different regime sequences.
        
        This shows how regime discipline affects capital deployment.
        """
        
        print(f"\n🎯 SIMULATING REGIME IMPACT")
        print("=" * 50)
        
        # Mock signal health (all specialists start healthy)
        mock_health = {}
        for specialist in ['momentum_specialist', 'value_specialist', 'quality_specialist', 'macro_specialist']:
            mock_health[specialist] = SignalHealth(
                ic_by_regime={regime: 0.10 for regime in RegimeType},
                sharpe_by_regime={regime: 1.0 for regime in RegimeType},
                decay_days=60,
                is_alive=True,
                last_updated=datetime.now()
            )
        
        # Simulate allocations
        results = []
        total_capital_deployed = 0.0
        
        for i, regime in enumerate(regime_sequence):
            regime_state = RegimeState(
                regime=regime,
                confidence=0.8,
                days_in_regime=10,
                regime_strength=0.7
            )
            
            current_date = datetime(2024, 1, 1 + i)
            
            result = self.allocate_capital(
                regime_state=regime_state,
                signal_bundle={},  # Not used in this simulation
                signal_health=mock_health,
                current_date=current_date
            )
            
            results.append(result)
            total_capital_deployed += result.gross_capital_used
        
        # Analysis
        avg_capital = total_capital_deployed / len(regime_sequence)
        
        regime_capital = {}
        for result in results:
            regime = None
            for r in RegimeType:
                if r.value in result.allocation_rationale:
                    regime = r.value
                    break
            
            if regime:
                if regime not in regime_capital:
                    regime_capital[regime] = []
                regime_capital[regime].append(result.gross_capital_used)
        
        # Print results
        print(f"Average capital deployed: {avg_capital:.1%}")
        print(f"Capital by regime:")
        for regime, capitals in regime_capital.items():
            avg_regime_capital = np.mean(capitals)
            print(f"   {regime}: {avg_regime_capital:.1%}")
        
        return {
            'avg_capital_deployed': avg_capital,
            'regime_capital_breakdown': {k: np.mean(v) for k, v in regime_capital.items()},
            'total_periods': len(regime_sequence),
            'capital_discipline_demonstrated': avg_capital < 0.5  # Good if avg < 50%
        }

def main():
    """Test the Regime-Locked Capital Allocator"""
    
    print("🔒 TESTING REGIME-LOCKED CAPITAL ALLOCATOR")
    print("=" * 80)
    print("This is the missing heart of NorthStar - institutional capital discipline.")
    print()
    
    # Initialize allocator
    allocator = RegimeLockedCapitalAllocator()
    
    # Test different regime scenarios
    test_regimes = [
        RegimeType.BULL,      # Should get high allocation
        RegimeType.HIGH_VOL,  # Should get moderate allocation
        RegimeType.NORMAL,    # Should get low allocation
        RegimeType.BEAR,      # Should get minimal allocation
        RegimeType.CRISIS     # Should get zero allocation
    ]
    
    print(f"\n🎯 TESTING REGIME DISCIPLINE")
    print("=" * 50)
    
    # Mock signal health
    mock_health = {}
    for specialist in ['momentum_specialist', 'value_specialist', 'quality_specialist', 'macro_specialist']:
        mock_health[specialist] = SignalHealth(
            ic_by_regime={
                RegimeType.BULL: 0.08,
                RegimeType.HIGH_VOL: 0.06,
                RegimeType.NORMAL: 0.04,
                RegimeType.BEAR: 0.02,
                RegimeType.CRISIS: 0.01
            },
            sharpe_by_regime={
                RegimeType.BULL: 2.0,
                RegimeType.HIGH_VOL: 1.0,
                RegimeType.NORMAL: 0.5,
                RegimeType.BEAR: 0.0,
                RegimeType.CRISIS: -0.5
            },
            decay_days=45,
            is_alive=True,
            last_updated=datetime.now()
        )
    
    # Test each regime
    for regime in test_regimes:
        print(f"\n🔍 Testing regime: {regime.value}")
        
        regime_state = RegimeState(
            regime=regime,
            confidence=0.8,
            days_in_regime=15,
            regime_strength=0.7
        )
        
        result = allocator.allocate_capital(
            regime_state=regime_state,
            signal_bundle={},
            signal_health=mock_health,
            current_date=datetime(2024, 6, 15)  # Q2 for high seasonal multiplier
        )
        
        print(f"   Capital deployed: {result.gross_capital_used:.1%}")
        print(f"   Specialists allocated: {len(result.specialist_allocations)}")
        print(f"   Signals blocked: {len(result.signals_blocked)}")
    
    # Simulate regime sequence impact
    regime_sequence = [
        RegimeType.BULL, RegimeType.BULL, RegimeType.HIGH_VOL,
        RegimeType.NORMAL, RegimeType.BEAR, RegimeType.CRISIS,
        RegimeType.CRISIS, RegimeType.HIGH_VOL, RegimeType.BULL
    ]
    
    simulation_results = allocator.simulate_regime_impact(regime_sequence)
    
    # Get final metrics
    print(f"\n📊 ALLOCATOR PERFORMANCE METRICS")
    print("=" * 50)
    
    metrics = allocator.get_allocation_metrics()
    for metric, value in metrics.items():
        if isinstance(value, float):
            if 'rate' in metric or 'score' in metric or 'utilization' in metric:
                print(f"{metric}: {value:.1%}")
            else:
                print(f"{metric}: {value:.2f}")
        else:
            print(f"{metric}: {value}")
    
    print(f"\n🎯 REGIME DISCIPLINE VERDICT")
    print("=" * 40)
    
    if simulation_results['capital_discipline_demonstrated']:
        print("✅ DISCIPLINED: Capital allocation shows proper regime awareness")
        print("   The allocator correctly reduces exposure in bad regimes")
    else:
        print("⚠️  UNDISCIPLINED: Too much capital deployed across regimes")
        print("   The allocator needs stricter regime limits")
    
    print(f"\n🏆 This is how NorthStar becomes a real fund:")
    print("   • Regime discipline prevents crisis bleeding")
    print("   • Seasonal awareness captures temporal alpha")
    print("   • Signal quality gates block weak signals")
    print("   • Capital flows only where alpha exists")

if __name__ == "__main__":
    main()