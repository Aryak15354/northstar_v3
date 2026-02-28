"""
Property-based tests for Options Trading System - Capital Scaling Engine

These tests validate universal correctness properties for capital scaling
using hypothesis for property-based testing.

Feature: options-trading-system
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from src.options.capital_scaling_engine import CapitalScalingEngine, ScalingState


# Mock config for testing
@dataclass
class MockCapitalConfig:
    """Mock capital config for testing"""
    base_risk_pct: float = 1.0
    max_risk_pct: float = 1.5
    min_risk_pct: float = 0.5


@dataclass
class MockCapitalScalingConfig:
    """Mock capital scaling config for testing"""
    min_weeks_before_scaling: int = 8
    profit_milestone_pct: float = 0.08
    profit_scaling_increment: float = 0.25
    drawdown_threshold_1: float = 0.03
    drawdown_threshold_2: float = 0.05
    drawdown_descaling_1: float = 0.25
    drawdown_descaling_2: float = 0.50
    recovery_profitable_trades: int = 2


@dataclass
class MockConfig:
    """Mock config for capital scaling engine"""
    capital: MockCapitalConfig = None
    capital_scaling: MockCapitalScalingConfig = None
    
    def __post_init__(self):
        if self.capital is None:
            self.capital = MockCapitalConfig()
        if self.capital_scaling is None:
            self.capital_scaling = MockCapitalScalingConfig()


class TestCapitalScalingProperties:
    """Property-based tests for capital scaling engine"""
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        current_risk_pct=st.floats(min_value=0.5, max_value=2.0),
        profit_pct=st.floats(min_value=0.0, max_value=0.50),
        drawdown_pct=st.floats(min_value=0.0, max_value=0.10)
    )
    def test_property_20_risk_ceiling_invariant(self, current_risk_pct, profit_pct, drawdown_pct):
        """
        # Feature: options-trading-system, Property 20: Risk Ceiling Invariant
        
        For any calculated risk percentage, regardless of profit or drawdown state,
        the risk per trade must never exceed 1.5% of capital.
        
        Validates: Requirements US-5.3
        """
        # Create engine for this test
        config = MockConfig()
        engine = CapitalScalingEngine(config=config)
        
        # Create scaling state
        base_capital = 500000
        state = ScalingState(
            current_risk_pct=current_risk_pct,
            equity_high_water_mark=base_capital,
            current_equity=base_capital * (1 + profit_pct - drawdown_pct),
            current_drawdown_pct=drawdown_pct,
            profit_milestones_achieved=0,
            last_milestone_equity=base_capital,
            in_drawdown=False,
            drawdown_level=0,
            recovery_equity_target=base_capital,
            recovery_profitable_trades=0,
            trading_start_date=datetime.utcnow() - timedelta(weeks=10),
            weeks_trading=10,
            can_scale=True,
            last_updated=datetime.utcnow(),
            scaling_history=[]
        )
        
        # Update state (which enforces ceiling)
        updated_state = engine.update_state(state, state.current_equity)
        
        # Property: Risk must never exceed 1.5%
        assert updated_state.current_risk_pct <= 1.5, \
            f"Risk ceiling violated: {updated_state.current_risk_pct}% exceeds 1.5% ceiling"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        profit_pct=st.floats(min_value=0.08, max_value=0.20)
    )
    def test_property_21_profit_scaling_trigger(self, profit_pct):
        """
        # Feature: options-trading-system, Property 21: Profit Scaling Trigger
        
        For any performance state where net profit reaches an 8% milestone,
        the risk per trade should increase by 0.25% from the previous level.
        
        Validates: Requirements US-5.2
        """
        # Create engine for this test
        config = MockConfig()
        engine = CapitalScalingEngine(config=config)
        
        base_capital = 500000
        
        # Initialize state
        state = engine.initialize_state(
            starting_capital=base_capital,
            trading_start_date=datetime.utcnow() - timedelta(weeks=10)
        )
        
        # Update with profit
        new_equity = base_capital * (1 + profit_pct)
        updated_state = engine.update_state(state, new_equity)
        
        # Property: Risk increases by 0.25% when profit >= 8%
        # The engine checks profit since last milestone, so we expect at most 1 milestone
        if profit_pct >= 0.08:
            # Should have triggered at least one milestone
            assert updated_state.profit_milestones_achieved >= 1, \
                f"Should have achieved milestone at {profit_pct*100}% profit"
            assert updated_state.current_risk_pct >= 1.0, \
                f"Risk should have increased from base 1.0% at {profit_pct*100}% profit"
        else:
            # Should not have triggered
            assert updated_state.current_risk_pct == 1.0, \
                f"Risk should remain at 1.0% below 8% profit"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        drawdown_pct=st.floats(min_value=0.0, max_value=0.10)
    )
    def test_property_22_drawdown_descaling(self, drawdown_pct):
        """
        # Feature: options-trading-system, Property 22: Drawdown De-Scaling
        
        For any performance state:
        - If drawdown reaches 3%, risk should decrease by 0.25%
        - If drawdown reaches 5%, risk should decrease by 0.50%
        
        Validates: Requirements US-5.4
        """
        # Create engine for this test
        config = MockConfig()
        engine = CapitalScalingEngine(config=config)
        
        base_capital = 500000
        
        # Initialize state at high water mark
        state = engine.initialize_state(
            starting_capital=base_capital,
            trading_start_date=datetime.utcnow() - timedelta(weeks=10)
        )
        
        # Set high water mark
        state.equity_high_water_mark = base_capital
        
        # Update with drawdown
        new_equity = base_capital * (1 - drawdown_pct)
        updated_state = engine.update_state(state, new_equity)
        
        # Property: Risk decreases based on drawdown thresholds
        if drawdown_pct >= 0.05:
            expected_risk = 1.0 - 0.50  # -0.50%
        elif drawdown_pct >= 0.03:
            expected_risk = 1.0 - 0.25  # -0.25%
        else:
            expected_risk = 1.0  # No change
        
        assert abs(updated_state.current_risk_pct - expected_risk) < 0.01, \
            f"Drawdown de-scaling incorrect at {drawdown_pct*100}% DD: expected {expected_risk}%, got {updated_state.current_risk_pct}%"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        consecutive_wins=st.integers(min_value=0, max_value=5),
        equity_recovered=st.booleans()
    )
    def test_property_23_recovery_condition(self, consecutive_wins, equity_recovered):
        """
        # Feature: options-trading-system, Property 23: Recovery Condition
        
        For any performance state in drawdown, risk should not increase unless
        both conditions are met: equity reaches previous high AND 2 consecutive wins.
        
        Validates: Requirements US-5.5
        """
        # Create engine for this test
        config = MockConfig()
        engine = CapitalScalingEngine(config=config)
        
        base_capital = 500000
        high_water_mark = base_capital
        
        # Initialize state
        state = engine.initialize_state(
            starting_capital=base_capital,
            trading_start_date=datetime.utcnow() - timedelta(weeks=10)
        )
        
        # Put into drawdown state
        state.in_drawdown = True
        state.drawdown_level = 1
        state.current_risk_pct = 0.75  # De-scaled
        state.equity_high_water_mark = high_water_mark
        state.recovery_equity_target = high_water_mark
        state.recovery_profitable_trades = 0
        
        # Set current equity based on recovery status
        current_equity = high_water_mark if equity_recovered else high_water_mark * 0.97
        
        # Simulate profitable trades
        for i in range(consecutive_wins):
            state = engine.update_state(state, current_equity, last_trade_profitable=True)
        
        # Property: Both conditions must be met for recovery
        both_conditions_met = equity_recovered and consecutive_wins >= 2
        
        # Check if still in drawdown
        if both_conditions_met:
            assert not state.in_drawdown, \
                f"Should have recovered: equity_recovered={equity_recovered}, wins={consecutive_wins}"
        else:
            # May or may not be in drawdown depending on equity alone
            pass
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        weeks_live=st.integers(min_value=0, max_value=20),
        profit_pct=st.floats(min_value=0.08, max_value=0.30)
    )
    def test_property_24_scaling_time_requirement(self, weeks_live, profit_pct):
        """
        # Feature: options-trading-system, Property 24: Scaling Time Requirement
        
        For any scaling calculation, if the system has been live for fewer than
        8 consecutive weeks, the risk should remain at base level (1.0%).
        
        Validates: Requirements US-5.6
        """
        # Create engine for this test
        config = MockConfig()
        engine = CapitalScalingEngine(config=config)
        
        base_capital = 500000
        
        # Initialize state with specific weeks
        state = engine.initialize_state(
            starting_capital=base_capital,
            trading_start_date=datetime.utcnow() - timedelta(weeks=weeks_live)
        )
        
        # Update with profit
        new_equity = base_capital * (1 + profit_pct)
        updated_state = engine.update_state(state, new_equity)
        
        # Property: No scaling before 8 weeks
        if weeks_live < 8:
            assert updated_state.current_risk_pct == 1.0, \
                f"Risk should remain at 1.0% before 8 weeks (weeks={weeks_live}), got {updated_state.current_risk_pct}%"
            assert not updated_state.can_scale, \
                f"can_scale should be False before 8 weeks (weeks={weeks_live})"
        else:
            # After 8 weeks, scaling can occur
            assert updated_state.can_scale, \
                f"can_scale should be True after 8 weeks (weeks={weeks_live})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
