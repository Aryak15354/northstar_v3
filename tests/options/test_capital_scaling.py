"""
Tests for Capital Scaling Engine

Verifies dynamic risk adjustment based on performance.
"""

import pytest
from datetime import datetime, timedelta

from src.options.capital_scaling_engine import CapitalScalingEngine, ScalingState


@pytest.fixture
def scaling_engine():
    """Create capital scaling engine with default config"""
    return CapitalScalingEngine(
        base_capital=500000.0,
        base_risk_pct=0.01,
        max_risk_pct=0.015,
        min_risk_pct=0.005,
        profit_milestone_pct=0.08,
        profit_scaling_increment=0.0025,
        drawdown_threshold_1=0.03,
        drawdown_threshold_2=0.05,
        drawdown_descaling_1=0.0025,
        drawdown_descaling_2=0.005,
        min_weeks_before_scaling=8,
        recovery_profitable_trades=2
    )


def test_initial_state(scaling_engine):
    """Test initial scaling state"""
    state = scaling_engine.get_state()
    
    assert state.current_risk_pct == 0.01
    assert state.equity_high_water_mark == 500000.0
    assert state.current_equity == 500000.0
    assert state.weeks_live == 0
    assert state.consecutive_profitable_trades == 0


def test_profit_scaling(scaling_engine):
    """Test risk increases after profit milestone"""
    # Simulate 8 weeks passing
    scaling_engine.state.weeks_live = 8
    
    # Simulate 8% profit
    new_equity = 540000.0  # +8%
    scaling_engine.update_equity(new_equity)
    
    state = scaling_engine.get_state()
    assert state.current_risk_pct == 0.0125  # 1.0% + 0.25%
    assert state.equity_high_water_mark == 540000.0


def test_risk_ceiling(scaling_engine):
    """Test risk never exceeds max ceiling"""
    scaling_engine.state.weeks_live = 8
    
    # Simulate 20% profit (should hit ceiling)
    new_equity = 600000.0  # +20%
    scaling_engine.update_equity(new_equity)
    
    state = scaling_engine.get_state()
    assert state.current_risk_pct == 0.015  # Capped at max


def test_drawdown_descaling(scaling_engine):
    """Test risk decreases during drawdown"""
    scaling_engine.state.weeks_live = 8
    
    # Simulate 4% drawdown
    new_equity = 480000.0  # -4%
    scaling_engine.update_equity(new_equity)
    
    state = scaling_engine.get_state()
    assert state.current_risk_pct == 0.0075  # 1.0% - 0.25%


def test_severe_drawdown(scaling_engine):
    """Test severe drawdown descaling"""
    scaling_engine.state.weeks_live = 8
    
    # Simulate 6% drawdown
    new_equity = 470000.0  # -6%
    scaling_engine.update_equity(new_equity)
    
    state = scaling_engine.get_state()
    assert state.current_risk_pct == 0.005  # 1.0% - 0.5%


def test_time_requirement(scaling_engine):
    """Test no scaling before 8 weeks"""
    # Only 4 weeks live
    scaling_engine.state.weeks_live = 4
    
    # Simulate 10% profit
    new_equity = 550000.0
    scaling_engine.update_equity(new_equity)
    
    state = scaling_engine.get_state()
    assert state.current_risk_pct == 0.01  # No change


def test_recovery_condition(scaling_engine):
    """Test recovery requires equity at HWM + 2 profitable trades"""
    scaling_engine.state.weeks_live = 8
    
    # Simulate drawdown
    scaling_engine.update_equity(480000.0)
    assert scaling_engine.state.current_risk_pct == 0.0075
    
    # Recover to HWM but no profitable trades yet
    scaling_engine.update_equity(500000.0)
    assert scaling_engine.state.current_risk_pct == 0.0075  # Still descaled
    
    # Add 2 profitable trades
    scaling_engine.record_trade_result(True)
    scaling_engine.record_trade_result(True)
    
    # Now should recover
    scaling_engine.update_equity(500000.0)
    assert scaling_engine.state.current_risk_pct == 0.01  # Back to base


def test_calculate_position_size(scaling_engine):
    """Test position size calculation"""
    scaling_engine.state.weeks_live = 8
    
    # At base risk (1%)
    max_loss = 10000.0
    lot_size = 50
    
    quantity = scaling_engine.calculate_position_size(max_loss, lot_size)
    
    # Risk = 1% of 500k = 5000
    # Quantity = 5000 / 10000 * 50 = 25 (rounded to lot size)
    assert quantity == 50  # Rounded up to nearest lot


def test_get_summary(scaling_engine):
    """Test scaling summary"""
    scaling_engine.state.weeks_live = 8
    scaling_engine.update_equity(540000.0)  # +8% profit
    
    summary = scaling_engine.get_summary()
    
    assert summary['current_risk_pct'] == 0.0125
    assert summary['equity_high_water_mark'] == 540000.0
    assert summary['current_equity'] == 540000.0
    assert summary['weeks_live'] == 8
    assert summary['drawdown_pct'] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
