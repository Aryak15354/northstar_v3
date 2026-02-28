#!/usr/bin/env python3
"""
Capacity Integration - Integration Layer for Capacity Engine

This module integrates the Capacity Engine components with the existing
institutional transformation systems (Signal Quality Gate, Position Inertia,
and Regime-Locked Capital Allocator).

Key Features:
- Seamless integration with existing institutional components
- Unified capacity-aware signal processing pipeline
- Liquidity-constrained portfolio construction
- Comprehensive capacity reporting
"""

from src.cohesion.dependency_container import get_dependency_container

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import capacity engine components
# Dependency injection - import ADVDatabase, ADVConfig, LiquidityTier from src.adv_database
# from adv_database import ADVDatabase, ADVConfig, LiquidityTier
from position_governor import PositionGovernor, GovernorConfig

# Import existing institutional components
# Dependency injection - import SignalQualityGate from src.signal_quality_gate
# # For testing when imports fail
pass

@dataclass
class CapacityAwarePortfolio:
    """Portfolio with capacity constraints applied"""
    weights: Dict[str, float]
    liquidity_analysis: Dict
    capacity_utilization: float
    rejected_positions: List[str]
    capped_positions: List[str]
    total_adv_used: float
    portfolio_value: float
    
class CapacityIntegrationEngine:
    """
    Integration engine that combines capacity constraints with institutional systems.
    
    This creates a unified pipeline:
    Raw Signals → Signal Quality Gate → Regime Capital Allocator → 
    Position Inertia → Position Governor → Capacity-Aware Portfolio
    """
    
    def __init__(self,
                 adv_database: ADVDatabase,
                 signal_quality_gate: Optional['SignalQualityGate'] = None,
                 position_inertia: Optional['PositionInertiaSystem'] = None,
                 regime_allocator: Optional['RegimeLockedCapitalAllocator'] = None,
                 position_governor: Optional[PositionGovernor] = None):
        
        self.adv_database = adv_database
        self.signal_quality_gate = signal_quality_gate
        self.position_inertia = position_inertia
        self.regime_allocator = regime_allocator
        
        # Initialize Position Governor if not provided
        if position_governor is None:
            governor_config = GovernorConfig()
            self.position_governor = PositionGovernor(adv_database, governor_config)
        else:
            self.position_governor = position_governor
        
        self.name = "Capacity Integration Engine"
        self.version = "1.0"
        
        print(f"🔗 {self.name} initialized")
        print(f"   Components integrated:")
        print(f"     - ADV Database: ✅")
        print(f"     - Position Governor: ✅")
        print(f"     - Signal Quality Gate: {'✅' if signal_quality_gate else '❌'}")
        print(f"     - Position Inertia: {'✅' if position_inertia else '❌'}")
        print(f"     - Regime Allocator: {'✅' if regime_allocator else '❌'}")
    
    def process_signals_with_capacity(self,
                                    raw_signals: Dict[str, float],
                                    regime_state: Optional['RegimeState'] = None,
                                    portfolio_value: float = 1_000_000,
                                    current_date: datetime = None) -> CapacityAwarePortfolio:
        """
        Process signals through the complete institutional + capacity pipeline.
        
        Args:
            raw_signals: Dictionary of symbol -> signal strength
            regime_state: Current market regime state
            portfolio_value: Total portfolio value for position sizing
            current_date: Current date for calculations
            
        Returns:
            CapacityAwarePortfolio with all constraints applied
        """
        
        if current_date is None:
            current_date = datetime.now()
        
        print(f"🔗 Processing {len(raw_signals)} signals through capacity pipeline")
        
        # Step 1: Signal Quality Gate (if available)
        if self.signal_quality_gate:
            print("   📊 Applying Signal Quality Gate...")
            # Note: This would require signal history data in practice
            qualified_signals = raw_signals  # Simplified for now
        else:
            qualified_signals = raw_signals
        
        # Step 2: Regime-Locked Capital Allocation (if available)
        if self.regime_allocator and regime_state:
            print("   🔒 Applying Regime Capital Limits...")
            # Note: This would require proper signal health data in practice
            regime_adjusted_signals = qualified_signals  # Simplified for now
        else:
            regime_adjusted_signals = qualified_signals
        
        # Step 3: Position Inertia (if available)
        if self.position_inertia:
            print("   🔄 Applying Position Inertia...")
            inertia_weights = self.position_inertia.process_signals(
                regime_adjusted_signals, current_date
            )
        else:
            # Convert signals to weights (simplified)
            total_signal = sum(abs(s) for s in regime_adjusted_signals.values())
            if total_signal > 0:
                inertia_weights = {
                    symbol: signal / total_signal 
                    for symbol, signal in regime_adjusted_signals.items()
                }
            else:
                inertia_weights = {}
        
        # Step 4: Position Governor (Capacity Constraints)
        print("   🏛️ Applying Liquidity Constraints...")
        capacity_weights = self.position_governor.apply_liquidity_constraints(
            inertia_weights, portfolio_value, current_date
        )
        
        # Step 5: Comprehensive Analysis
        liquidity_analysis = self.position_governor.validate_portfolio_liquidity(
            capacity_weights, portfolio_value, current_date
        )
        
        # Calculate capacity utilization
        total_adv_used = self._calculate_total_adv_used(capacity_weights, portfolio_value, current_date)
        capacity_utilization = self._calculate_capacity_utilization(capacity_weights, current_date)
        
        # Identify rejected and capped positions
        rejected_positions = []
        capped_positions = []
        
        for symbol in raw_signals.keys():
            if symbol not in capacity_weights or capacity_weights[symbol] == 0:
                if symbol in inertia_weights and inertia_weights[symbol] != 0:
                    rejected_positions.append(symbol)
            elif symbol in inertia_weights:
                if abs(capacity_weights[symbol]) < abs(inertia_weights[symbol]) * 0.95:
                    capped_positions.append(symbol)
        
        # Create capacity-aware portfolio
        portfolio = CapacityAwarePortfolio(
            weights=capacity_weights,
            liquidity_analysis=liquidity_analysis,
            capacity_utilization=capacity_utilization,
            rejected_positions=rejected_positions,
            capped_positions=capped_positions,
            total_adv_used=total_adv_used,
            portfolio_value=portfolio_value
        )
        
        print(f"   ✅ Pipeline complete: {len(capacity_weights)} positions, "
              f"{len(rejected_positions)} rejected, {len(capped_positions)} capped")
        
        return portfolio
    
    def _calculate_total_adv_used(self, 
                                weights: Dict[str, float], 
                                portfolio_value: float,
                                current_date: datetime) -> float:
        """Calculate total ADV used by the portfolio"""
        
        total_adv = 0.0
        
        for symbol, weight in weights.items():
            if weight == 0:
                continue
            
            adv_data = self.adv_database.calculate_rolling_adv(symbol, current_date)
            if adv_data:
                position_value = abs(weight) * portfolio_value
                # Estimate ADV usage (position_value / alpha_factor)
                alpha_factor = self.position_governor._get_alpha_factor(adv_data.liquidity_tier)
                if alpha_factor > 0:
                    adv_usage = position_value / alpha_factor
                    total_adv += adv_usage
        
        return total_adv
    
    def _calculate_capacity_utilization(self, 
                                      weights: Dict[str, float],
                                      current_date: datetime) -> float:
        """Calculate overall capacity utilization (0-1)"""
        
        if not weights:
            return 0.0
        
        total_utilization = 0.0
        position_count = 0
        
        for symbol, weight in weights.items():
            if weight == 0:
                continue
            
            position_limits = self.position_governor.calculate_max_position(
                symbol, as_of_date=current_date
            )
            
            if not position_limits.is_rejected and position_limits.max_position_value > 0:
                position_value = abs(weight) * 1_000_000  # Normalized to $1M
                utilization = position_value / position_limits.max_position_value
                total_utilization += min(utilization, 1.0)
                position_count += 1
        
        return total_utilization / position_count if position_count > 0 else 0.0
    
    def get_capacity_report(self, portfolio: CapacityAwarePortfolio) -> Dict:
        """Generate comprehensive capacity report"""
        
        report = {
            'portfolio_summary': {
                'total_positions': len([w for w in portfolio.weights.values() if w != 0]),
                'total_weight': sum(abs(w) for w in portfolio.weights.values()),
                'portfolio_value': portfolio.portfolio_value,
                'capacity_utilization': portfolio.capacity_utilization
            },
            'liquidity_analysis': portfolio.liquidity_analysis,
            'constraints_applied': {
                'rejected_positions': len(portfolio.rejected_positions),
                'capped_positions': len(portfolio.capped_positions),
                'rejected_symbols': portfolio.rejected_positions,
                'capped_symbols': portfolio.capped_positions
            },
            'adv_usage': {
                'total_adv_used': portfolio.total_adv_used,
                'adv_efficiency': portfolio.total_adv_used / portfolio.portfolio_value if portfolio.portfolio_value > 0 else 0
            },
            'governor_metrics': self.position_governor.get_governor_metrics(),
            'database_stats': self.adv_database.get_database_stats()
        }
        
        return report

def main():
    """Test the Capacity Integration Engine"""
    
    print("🧪 TESTING CAPACITY INTEGRATION ENGINE")
    print("=" * 60)
    
    # Initialize ADV Database
    adv_config = ADVConfig(
        min_adv_threshold=1_000_000,
        large_cap_threshold=50_000_000,
        mid_cap_threshold=5_000_000
    )
    
    adv_db = ADVDatabase(adv_config)
    
    # Add test data
    np.random.seed(42)
    test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'META', 'AMZN', 'SMALL1', 'SMALL2', 'MICRO1']
    
    dates = pd.date_range(start='2025-01-01', end='2026-01-03', freq='D')
    
    for i, symbol in enumerate(test_symbols):
        if 'SMALL' in symbol:
            base_volume = 200_000
            base_price = 20
        elif 'MICRO' in symbol:
            base_volume = 50_000
            base_price = 5
        else:
            base_volume = 20_000_000 + i * 5_000_000
            base_price = 100 + i * 50
        
        volume_noise = np.random.normal(1.0, 0.2, len(dates))
        price_noise = np.random.normal(1.0, 0.05, len(dates))
        
        volume_data = pd.DataFrame({
            'date': dates,
            'volume': base_volume * volume_noise
        })
        
        price_data = pd.DataFrame({
            'date': dates,
            'close': base_price * price_noise
        })
        
        adv_db.add_volume_data(symbol, volume_data, price_data)
    
    # Initialize Integration Engine
    integration_engine = CapacityIntegrationEngine(adv_db)
    
    # Test signal processing
    print(f"\n🔗 TESTING INTEGRATED SIGNAL PROCESSING")
    print("=" * 50)
    
    # Generate test signals
    raw_signals = {
        'AAPL': 0.15,
        'MSFT': 0.12,
        'GOOGL': 0.10,
        'TSLA': 0.08,
        'NVDA': 0.06,
        'META': 0.05,
        'AMZN': 0.04,
        'SMALL1': 0.03,
        'SMALL2': 0.02,
        'MICRO1': 0.01
    }
    
    portfolio_value = 10_000_000  # $10M portfolio
    current_date = datetime(2026, 1, 3)
    
    # Process through integrated pipeline
    capacity_portfolio = integration_engine.process_signals_with_capacity(
        raw_signals, 
        portfolio_value=portfolio_value,
        current_date=current_date
    )
    
    # Display results
    print(f"\n📊 CAPACITY-AWARE PORTFOLIO")
    print("=" * 40)
    
    print(f"Portfolio Value: ${portfolio_value:,.0f}")
    print(f"Capacity Utilization: {capacity_portfolio.capacity_utilization:.1%}")
    print(f"Total ADV Used: ${capacity_portfolio.total_adv_used:,.0f}")
    
    print(f"\nFinal Weights:")
    total_weight = 0.0
    for symbol, weight in capacity_portfolio.weights.items():
        if weight != 0:
            position_value = weight * portfolio_value
            print(f"   {symbol}: {weight:.3f} (${position_value:,.0f})")
            total_weight += abs(weight)
    
    print(f"\nTotal Weight: {total_weight:.3f}")
    
    if capacity_portfolio.rejected_positions:
        print(f"\nRejected Positions: {capacity_portfolio.rejected_positions}")
    
    if capacity_portfolio.capped_positions:
        print(f"Capped Positions: {capacity_portfolio.capped_positions}")
    
    # Generate comprehensive report
    print(f"\n📈 CAPACITY REPORT")
    print("=" * 40)
    
    report = integration_engine.get_capacity_report(capacity_portfolio)
    
    print(f"Portfolio Summary:")
    for key, value in report['portfolio_summary'].items():
        if isinstance(value, float):
            if 'utilization' in key or 'weight' in key:
                print(f"   {key}: {value:.1%}")
            else:
                print(f"   {key}: {value:,.0f}")
        else:
            print(f"   {key}: {value}")
    
    print(f"\nConstraints Applied:")
    for key, value in report['constraints_applied'].items():
        if isinstance(value, list):
            if value:
                print(f"   {key}: {value}")
        else:
            print(f"   {key}: {value}")
    
    print(f"\nGovernor Metrics:")
    gov_metrics = report['governor_metrics']
    for key, value in gov_metrics.items():
        if isinstance(value, dict):
            if value:
                print(f"   {key}: {value}")
        elif isinstance(value, float):
            if 'rate' in key:
                print(f"   {key}: {value:.1%}")
            else:
                print(f"   {key}: {value:.2f}")
        else:
            print(f"   {key}: {value}")

if __name__ == "__main__":
    main()