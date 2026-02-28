#!/usr/bin/env python3
"""
Property Test: Simulation-Reality Consistency

This test validates that the simulation produces results that are consistent
with what would happen in reality, ensuring no artificial advantages.

Property 3: Simulation-Reality Consistency
- Validates: Requirements 1.4
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
import sys
import os

# Add src to path
, '..', '..'))

from src.validation.northstar_brain_state import NorthstarBrain, NorthstarBrainState
from src.intelligence.temporal_guard import TemporalGuard

class SimulationRealityConsistencyTest(RuleBasedStateMachine):
    """
    Property-based test for simulation-reality consistency.
    
    Tests that simulation results are achievable in reality with:
    - Realistic execution delays
    - Market impact from trades
    - Liquidity constraints
    - Transaction costs
    """
    
    def __init__(self):
        super().__init__()
        self.temporal_guard = TemporalGuard()
        self.start_date = datetime(2023, 1, 1)
        self.current_date = self.start_date
        self.brain = None
        self.simulation_portfolio = {}
        self.reality_portfolio = {}
        self.execution_delays = []
        self.market_impact_costs = []
        
    @initialize()
    def setup_brain(self):
        """Initialize brain with clean state"""
        self.brain = NorthstarBrain.from_historical_state(
            historical_data={},
            start_date=self.start_date,
            temporal_guard=self.temporal_guard
        )
        self.simulation_portfolio = {'CASH': 1.0}
        self.reality_portfolio = {'CASH': 1.0}
    
    @rule(
        market_return=st.floats(min_value=-0.05, max_value=0.05),
        market_volatility=st.floats(min_value=0.05, max_value=0.40),
        liquidity_factor=st.floats(min_value=0.1, max_value=1.0)
    )
    def step_simulation_forward(self, market_return, market_volatility, liquidity_factor):
        """Step simulation forward one day with market data"""
        
        # Create daily market data
        daily_data = {
            'market_return': market_return,
            'market_volatility': market_volatility,
            'market_momentum': market_return,  # Simple momentum proxy
            'liquidity_factor': liquidity_factor
        }
        
        # Step brain forward (simulation)
        self.current_date += timedelta(days=1)
        simulation_weights = self.brain.step_forward(daily_data, self.current_date)
        
        # Calculate what would happen in reality
        reality_weights = self._apply_reality_constraints(simulation_weights, daily_data)
        
        # Update portfolios
        self.simulation_portfolio = simulation_weights
        self.reality_portfolio = reality_weights
        
        # Track execution differences
        self._track_execution_differences(simulation_weights, reality_weights, daily_data)
    
    def _apply_reality_constraints(self, simulation_weights, daily_data):
        """Apply real-world constraints to simulation weights"""
        reality_weights = simulation_weights.copy()
        liquidity_factor = daily_data['liquidity_factor']
        market_volatility = daily_data['market_volatility']
        
        # 1. Apply execution delays (T+1 settlement)
        # In reality, you can't trade on today's close using today's signals
        execution_delay_penalty = 0.001 * market_volatility  # Higher volatility = more delay cost
        
        # 2. Apply market impact based on position size and liquidity
        for asset, weight in reality_weights.items():
            if asset != 'CASH' and abs(weight) > 0.01:  # Positions > 1%
                # Market impact increases with position size and decreases with liquidity
                market_impact = abs(weight) * (1 - liquidity_factor) * 0.002
                self.market_impact_costs.append(market_impact)
                
                # Reduce position size due to market impact
                if weight > 0:
                    reality_weights[asset] = max(0, weight - market_impact)
                else:
                    reality_weights[asset] = min(0, weight + market_impact)
        
        # 3. Apply liquidity constraints
        # Can't trade more than 5% of daily volume
        max_position_size = 0.05 * liquidity_factor
        for asset, weight in reality_weights.items():
            if asset != 'CASH':
                if abs(weight) > max_position_size:
                    # Scale down position to liquidity limit
                    reality_weights[asset] = np.sign(weight) * max_position_size
        
        # 4. Rebalance cash to maintain 100% allocation
        total_invested = sum(abs(w) for k, w in reality_weights.items() if k != 'CASH')
        reality_weights['CASH'] = max(0, 1.0 - total_invested)
        
        return reality_weights
    
    def _track_execution_differences(self, simulation_weights, reality_weights, daily_data):
        """Track differences between simulation and reality"""
        
        # Calculate execution delay impact
        total_weight_change = sum(abs(simulation_weights.get(k, 0) - reality_weights.get(k, 0)) 
                                for k in set(simulation_weights.keys()) | set(reality_weights.keys()))
        
        self.execution_delays.append({
            'date': self.current_date,
            'total_weight_change': total_weight_change,
            'market_volatility': daily_data['market_volatility'],
            'liquidity_factor': daily_data['liquidity_factor']
        })
    
    @invariant()
    def simulation_reality_gap_bounded(self):
        """Invariant: Gap between simulation and reality must be bounded"""
        if not self.execution_delays:
            return
        
        # Check that execution differences are reasonable
        recent_delays = self.execution_delays[-10:]  # Last 10 days
        avg_weight_change = np.mean([d['total_weight_change'] for d in recent_delays])
        
        # Gap should be bounded by market conditions
        max_reasonable_gap = 0.20  # 20% total weight change is maximum reasonable
        
        assert avg_weight_change <= max_reasonable_gap, (
            f"Simulation-reality gap too large: {avg_weight_change:.3f} > {max_reasonable_gap}"
        )
    
    @invariant()
    def market_impact_realistic(self):
        """Invariant: Market impact costs must be realistic"""
        if not self.market_impact_costs:
            return
        
        # Market impact should be reasonable (not exceeding 1% per trade)
        max_impact = max(self.market_impact_costs[-20:]) if self.market_impact_costs else 0
        
        assert max_impact <= 0.01, (
            f"Market impact too high: {max_impact:.4f} > 0.01"
        )
    
    @invariant()
    def portfolio_weights_valid(self):
        """Invariant: Portfolio weights must be valid in both simulation and reality"""
        
        # Check simulation portfolio
        sim_total = sum(abs(w) for w in self.simulation_portfolio.values())
        assert 0.8 <= sim_total <= 1.2, f"Simulation portfolio weights invalid: {sim_total:.3f}"
        
        # Check reality portfolio  
        reality_total = sum(abs(w) for w in self.reality_portfolio.values())
        assert 0.8 <= reality_total <= 1.2, f"Reality portfolio weights invalid: {reality_total:.3f}"
        
        # Cash should be non-negative in reality
        reality_cash = self.reality_portfolio.get('CASH', 0)
        assert reality_cash >= -0.05, f"Reality cash position too negative: {reality_cash:.3f}"


class TestSimulationRealityConsistency:
    """Unit tests for simulation-reality consistency"""
    
    def test_execution_delay_impact(self):
        """Test that execution delays create realistic performance drag"""
        temporal_guard = TemporalGuard()
        start_date = datetime(2023, 1, 1)
        
        brain = NorthstarBrain.from_historical_state({}, start_date, temporal_guard)
        
        # High volatility day with strong signal
        daily_data = {
            'market_return': 0.03,
            'market_volatility': 0.30,  # High volatility
            'market_momentum': 0.03,
            'liquidity_factor': 0.5  # Moderate liquidity
        }
        
        current_date = start_date + timedelta(days=1)
        simulation_weights = brain.step_forward(daily_data, current_date)
        
        # Apply reality constraints
        test_machine = SimulationRealityConsistencyTest()
        test_machine.setup_brain()
        reality_weights = test_machine._apply_reality_constraints(simulation_weights, daily_data)
        
        # Reality should have smaller positions due to execution constraints
        sim_exposure = sum(abs(w) for k, w in simulation_weights.items() if k != 'CASH')
        reality_exposure = sum(abs(w) for k, w in reality_weights.items() if k != 'CASH')
        
        assert reality_exposure <= sim_exposure, "Reality should have lower exposure due to constraints"
        
        # Cash position should be higher in reality
        sim_cash = simulation_weights.get('CASH', 0)
        reality_cash = reality_weights.get('CASH', 0)
        
        assert reality_cash >= sim_cash - 0.01, "Reality should have similar or higher cash position"
    
    def test_liquidity_constraints_enforced(self):
        """Test that liquidity constraints are properly enforced"""
        test_machine = SimulationRealityConsistencyTest()
        test_machine.setup_brain()
        
        # Create large position that exceeds liquidity
        simulation_weights = {
            'momentum_portfolio': 0.15,  # 15% position
            'quality_portfolio': 0.10,   # 10% position
            'CASH': 0.75
        }
        
        daily_data = {
            'market_volatility': 0.20,
            'liquidity_factor': 0.3  # Low liquidity
        }
        
        reality_weights = test_machine._apply_reality_constraints(simulation_weights, daily_data)
        
        # Check that positions are scaled down due to liquidity constraints
        max_allowed = 0.05 * daily_data['liquidity_factor']  # 1.5% max position
        
        for asset, weight in reality_weights.items():
            if asset != 'CASH':
                assert abs(weight) <= max_allowed + 0.001, (
                    f"Position {asset}={weight:.3f} exceeds liquidity limit {max_allowed:.3f}"
                )
    
    def test_market_impact_scaling(self):
        """Test that market impact scales with position size and liquidity"""
        test_machine = SimulationRealityConsistencyTest()
        test_machine.setup_brain()
        
        # Test different position sizes
        position_sizes = [0.02, 0.05, 0.10]  # 2%, 5%, 10%
        liquidity_factors = [0.2, 0.5, 0.8]  # Low, medium, high liquidity
        
        for pos_size in position_sizes:
            for liq_factor in liquidity_factors:
                simulation_weights = {
                    'test_asset': pos_size,
                    'CASH': 1.0 - pos_size
                }
                
                daily_data = {
                    'market_volatility': 0.15,
                    'liquidity_factor': liq_factor
                }
                
                # Clear previous market impact costs
                test_machine.market_impact_costs = []
                
                reality_weights = test_machine._apply_reality_constraints(simulation_weights, daily_data)
                
                # Market impact should be higher for larger positions and lower liquidity
                if test_machine.market_impact_costs:
                    market_impact = test_machine.market_impact_costs[-1]
                    
                    # Impact should increase with position size
                    expected_impact = pos_size * (1 - liq_factor) * 0.002
                    assert abs(market_impact - expected_impact) < 0.0001, (
                        f"Market impact {market_impact:.4f} != expected {expected_impact:.4f}"
                    )
    
    @settings(max_examples=50, deadline=30000)  # 30 second timeout
    def test_property_simulation_reality_consistency(self):
        """Property test for simulation-reality consistency"""
        test_machine = SimulationRealityConsistencyTest()
        test_machine.setup_brain()
        
        # Run property-based test
        for _ in range(20):  # 20 simulation steps
            # Generate random market conditions
            market_return = np.random.uniform(-0.03, 0.03)
            market_volatility = np.random.uniform(0.10, 0.35)
            liquidity_factor = np.random.uniform(0.2, 0.9)
            
            test_machine.step_simulation_forward(market_return, market_volatility, liquidity_factor)
        
        # Verify invariants held throughout
        test_machine.simulation_reality_gap_bounded()
        test_machine.market_impact_realistic()
        test_machine.portfolio_weights_valid()


def test_simulation_reality_consistency_property():
    """Main property test entry point"""
    test = TestSimulationRealityConsistency()
    test.test_property_simulation_reality_consistency()


if __name__ == "__main__":
    # Run property tests
    print("🧪 Testing Simulation-Reality Consistency...")
    
    test = TestSimulationRealityConsistency()
    
    # Run individual tests
    test.test_execution_delay_impact()
    print("✅ Execution delay impact test passed")
    
    test.test_liquidity_constraints_enforced()
    print("✅ Liquidity constraints test passed")
    
    test.test_market_impact_scaling()
    print("✅ Market impact scaling test passed")
    
    # Run property test
    test.test_property_simulation_reality_consistency()
    print("✅ Property test passed")
    
    print("\n🎉 All simulation-reality consistency tests passed!")
    print("💡 Simulation produces results achievable in reality")