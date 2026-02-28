"""
Property-based tests for Options Trading System - Survival Rules Engine

These tests validate universal correctness properties for survival rules
using hypothesis for property-based testing.

Feature: options-trading-system
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta, date
import pytz
from dataclasses import dataclass
from typing import List, Dict

from src.options.survival_rules_engine import SurvivalRulesEngine, Trade, Position, PerformanceMetrics


IST = pytz.timezone('Asia/Kolkata')


# Mock config for testing
@dataclass
class MockSurvivalRulesConfig:
    """Mock survival rules config for testing"""
    weekly_loss_limit_pct: float = 0.02
    trauma_loss_threshold_pct: float = 0.80
    trauma_cooldown_weeks: int = 2
    portfolio_risk_cap_pct: float = 0.02
    max_trades_per_week: int = 2
    no_trade_times: List[Dict[str, str]] = None
    no_trade_days: List[str] = None
    
    def __post_init__(self):
        if self.no_trade_times is None:
            self.no_trade_times = [
                {"day": "Monday", "start": "09:15", "end": "10:00"}
            ]
        if self.no_trade_days is None:
            self.no_trade_days = ["Tuesday"]


class TestSurvivalRulesProperties:
    """Property-based tests for survival rules engine"""
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        weekly_loss_pct=st.floats(min_value=0.01, max_value=0.10),
        capital=st.floats(min_value=100000, max_value=1000000)
    )
    def test_property_25_weekly_loss_kill_switch(self, weekly_loss_pct, capital):
        """
        # Feature: options-trading-system, Property 25: Weekly Loss Kill Switch
        
        For any weekly P&L calculation, if the loss reaches or exceeds 2% of capital,
        the kill switch should activate and block all new trades.
        
        Validates: Requirements US-6.1
        """
        # Create engine for this test
        config = MockSurvivalRulesConfig()
        survival_engine = SurvivalRulesEngine(config=config, base_capital=capital)
        
        # Create trades with weekly loss
        current_time = IST.localize(datetime(2024, 1, 15, 14, 30))  # Monday afternoon
        weekly_pnl = -1 * weekly_loss_pct * capital
        
        # Create a closed trade with the loss
        closed_trades = [
            Trade(
                trade_id="test_trade_1",
                strategy_type="iron_condor",
                entry_time=current_time - timedelta(days=2),
                exit_time=current_time,
                max_loss=abs(weekly_pnl),
                realized_pnl=weekly_pnl,
                is_short_vol=True
            )
        ]
        
        # Check kill switch via check_all_kill_switches
        status = survival_engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=closed_trades,
            performance=PerformanceMetrics(
                current_equity=capital,
                ytd_gross_profits=0,
                ytd_tax_liability=0,
                cash_buffer=0
            ),
            current_time=current_time
        )
        
        # Property: If loss >= 2% capital, kill switch should activate
        if weekly_loss_pct >= 0.02:
            assert status.active is True, f"Kill switch should activate at {weekly_loss_pct*100}% loss"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        loss_pct=st.floats(min_value=0.0, max_value=1.0),
        max_loss=st.floats(min_value=1000, max_value=10000)
    )
    def test_property_26_trauma_rule_activation(self, loss_pct, max_loss):
        """
        # Feature: options-trading-system, Property 26: Trauma Rule Activation
        
        For any closed trade that loses more than 80% of its maximum loss,
        short-vol strategies should be blocked for 2 weeks.
        
        Validates: Requirements US-6.2
        """
        # Create engine
        config = MockSurvivalRulesConfig()
        survival_engine = SurvivalRulesEngine(config=config, base_capital=500000)
        
        # Create a trade with specified loss
        actual_loss = -1 * loss_pct * max_loss
        current_time = IST.localize(datetime(2024, 1, 15, 14, 30))
        
        closed_trades = [
            Trade(
                trade_id="trauma_trade_1",
                strategy_type="iron_condor",
                entry_time=current_time - timedelta(days=5),
                exit_time=current_time,
                max_loss=max_loss,
                realized_pnl=actual_loss,
                is_short_vol=True
            )
        ]
        
        # Check kill switch
        status = survival_engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=closed_trades,
            performance=PerformanceMetrics(
                current_equity=500000,
                ytd_gross_profits=0,
                ytd_tax_liability=0,
                cash_buffer=0
            ),
            current_time=current_time
        )
        
        # Property: If loss > 80% of max_loss, trauma rule activates
        if loss_pct > 0.80:
            assert status.active is True, f"Trauma rule should activate at {loss_pct*100}% of max loss"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        num_positions=st.integers(min_value=1, max_value=3),
        risk_per_position_pct=st.floats(min_value=0.005, max_value=0.015)
    )
    def test_property_27_portfolio_risk_cap(self, num_positions, risk_per_position_pct):
        """
        # Feature: options-trading-system, Property 27: Portfolio Risk Cap
        
        For any portfolio of open positions, the sum of maximum losses
        must not exceed 2% of capital.
        
        Validates: Requirements US-6.3
        """
        capital = 500000
        config = MockSurvivalRulesConfig()
        survival_engine = SurvivalRulesEngine(config=config, base_capital=capital)
        
        current_time = IST.localize(datetime(2024, 1, 15, 14, 30))
        
        # Create positions
        positions = []
        total_max_loss = 0
        
        for i in range(num_positions):
            max_loss = capital * risk_per_position_pct
            total_max_loss += max_loss
            
            positions.append(Position(
                position_id=f"pos_{i}",
                strategy_type="iron_condor",
                max_loss=max_loss,
                entry_time=current_time,
                is_short_vol=True
            ))
        
        # Create a proposed trade
        proposed_trade = Position(
            position_id="proposed",
            strategy_type="iron_condor",
            max_loss=capital * 0.005,  # Small additional risk
            entry_time=current_time,
            is_short_vol=True
        )
        
        # Check portfolio risk cap
        status = survival_engine.check_all_kill_switches(
            open_positions=positions,
            closed_trades=[],
            performance=PerformanceMetrics(
                current_equity=capital,
                ytd_gross_profits=0,
                ytd_tax_liability=0,
                cash_buffer=0
            ),
            current_time=current_time,
            proposed_trade=proposed_trade
        )
        
        # Property: Total max loss should not exceed 2% of capital
        total_risk_pct = (total_max_loss + proposed_trade.max_loss) / capital
        
        if total_risk_pct > 0.02:
            assert status.active is True, f"Portfolio risk cap should trigger at {total_risk_pct*100}% risk"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
