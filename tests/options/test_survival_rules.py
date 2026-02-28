"""
Tests for Survival Rules Engine

Tests all kill switches and circuit breakers to ensure they trigger correctly.
"""

import pytest
from datetime import datetime, timedelta, time
from typing import List
import pytz

from src.options.survival_rules_engine import (
    SurvivalRulesEngine,
    KillSwitchStatus,
    KillSwitchType,
    Trade,
    Position,
    PerformanceMetrics
)
from src.options.config_loader import SurvivalRulesConfig

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


@pytest.fixture
def survival_config():
    """Create test survival rules configuration"""
    return SurvivalRulesConfig(
        weekly_loss_limit_pct=0.02,  # 2%
        trauma_loss_threshold_pct=0.80,  # 80%
        trauma_cooldown_weeks=2,
        portfolio_risk_cap_pct=0.02,  # 2%
        max_trades_per_week=2,
        no_trade_times=[
            {"day": "Monday", "start": "09:15", "end": "10:00"}
        ],
        no_trade_days=["Tuesday"]
    )


@pytest.fixture
def engine(survival_config):
    """Create survival rules engine"""
    return SurvivalRulesEngine(survival_config, base_capital=500000)


@pytest.fixture
def base_performance():
    """Create base performance metrics"""
    return PerformanceMetrics(
        current_equity=500000,
        ytd_gross_profits=50000,
        ytd_tax_liability=15000,
        cash_buffer=15000  # 30% of gross profits
    )


def create_trade(
    trade_id: str,
    entry_time: datetime,
    exit_time: datetime,
    max_loss: float,
    realized_pnl: float,
    is_short_vol: bool = True
) -> Trade:
    """Helper to create trade"""
    return Trade(
        trade_id=trade_id,
        strategy_type="iron_condor" if is_short_vol else "long_straddle",
        entry_time=entry_time,
        exit_time=exit_time,
        max_loss=max_loss,
        realized_pnl=realized_pnl,
        is_short_vol=is_short_vol
    )


def create_position(
    position_id: str,
    max_loss: float,
    entry_time: datetime,
    is_short_vol: bool = True
) -> Position:
    """Helper to create position"""
    return Position(
        position_id=position_id,
        strategy_type="iron_condor" if is_short_vol else "long_straddle",
        max_loss=max_loss,
        entry_time=entry_time,
        is_short_vol=is_short_vol
    )


class TestWeeklyLossKillSwitch:
    """Test weekly loss kill switch"""
    
    def test_no_trigger_within_limit(self, engine):
        """Test no trigger when loss within limit"""
        # Wednesday 2:00 PM IST
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Monday entry, Wednesday exit with small loss
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-2000  # 0.4% loss (within 2% limit)
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert not status.active
        assert KillSwitchType.WEEKLY_LOSS.value not in status.triggered_rules
    
    def test_trigger_exceeds_limit(self, engine):
        """Test trigger when weekly loss exceeds 2%"""
        # Wednesday 2:00 PM IST
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Two trades this week with total loss > 2%
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 9, 13, 0)),
                max_loss=5000,
                realized_pnl=-6000  # 1.2% loss
            ),
            create_trade(
                "T2",
                entry_time=IST.localize(datetime(2024, 1, 9, 14, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-5000  # 1.0% loss
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert status.active
        assert KillSwitchType.WEEKLY_LOSS.value in status.triggered_rules
        assert status.override_allowed  # Only kill switch that allows override
        assert status.cooldown_until is not None
    
    def test_reset_on_monday_915am(self, engine):
        """Test weekly loss resets on Monday 9:15 AM IST"""
        # Previous week: big loss
        prev_week_trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-12000  # 2.4% loss
            )
        ]
        
        # Check on previous Friday - should trigger
        friday = IST.localize(datetime(2024, 1, 12, 15, 0))
        status_friday = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=prev_week_trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=friday
        )
        assert status_friday.active
        
        # Check on next Monday 10:30 AM (after time block) - should NOT trigger (new week)
        monday = IST.localize(datetime(2024, 1, 15, 10, 30))
        status_monday = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=prev_week_trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=monday
        )
        # Weekly loss should be cleared, but trauma may still be active
        assert KillSwitchType.WEEKLY_LOSS.value not in status_monday.triggered_rules
    
    def test_override_mechanism(self, engine):
        """Test weekly loss override with 48h cooling"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Loss exceeds limit (but not trauma threshold)
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=15000,  # Higher max loss
                realized_pnl=-11000  # 2.2% loss, but only 73% of max loss (below trauma)
            )
        ]
        
        # Should trigger weekly loss only
        status_before = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        assert status_before.active
        assert KillSwitchType.WEEKLY_LOSS.value in status_before.triggered_rules
        
        # Set override
        engine.set_weekly_loss_override(current_time, cooling_period_hours=48)
        
        # Should NOT trigger during override
        status_after = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        assert not status_after.active


class TestTraumaRule:
    """Test single-trade trauma rule"""
    
    def test_no_trigger_below_threshold(self, engine):
        """Test no trigger when loss below 80% threshold"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Trade loses 70% of max loss (below 80% threshold)
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-3500,  # 70% of max loss
                is_short_vol=True
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert not status.active
        assert KillSwitchType.TRAUMA.value not in status.triggered_rules
    
    def test_trigger_exceeds_threshold(self, engine):
        """Test trigger when loss exceeds 80% threshold"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Trade loses 85% of max loss
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-4250,  # 85% of max loss
                is_short_vol=True
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert status.active
        assert KillSwitchType.TRAUMA.value in status.triggered_rules
        assert engine.trauma_cooldown_until is not None
        
        # Cooldown should be 2 weeks
        expected_cooldown = current_time + timedelta(weeks=2)
        assert engine.trauma_cooldown_until == expected_cooldown
    
    def test_only_applies_to_short_vol(self, engine):
        """Test trauma rule only applies to short-vol strategies"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Long straddle loses 90% (not short-vol)
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-4500,  # 90% of max loss
                is_short_vol=False  # Long vol strategy
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert not status.active
        assert KillSwitchType.TRAUMA.value not in status.triggered_rules
    
    def test_cooldown_persists(self, engine):
        """Test trauma cooldown persists for 2 weeks"""
        # Trigger trauma on Wednesday
        trigger_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=-4250,  # 85% of max loss
                is_short_vol=True
            )
        ]
        
        # Trigger trauma
        engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=trigger_time
        )
        
        # Check 1 week later - should still be active
        one_week_later = trigger_time + timedelta(weeks=1)
        status_week1 = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=one_week_later
        )
        assert status_week1.active
        assert KillSwitchType.TRAUMA.value in status_week1.triggered_rules
        
        # Check 2 weeks + 1 day later (use Wednesday to avoid time blocks)
        two_weeks_later = IST.localize(datetime(2024, 1, 31, 14, 0))  # Wednesday
        status_week2 = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=two_weeks_later
        )
        assert not status_week2.active


class TestPortfolioRiskCap:
    """Test portfolio risk cap"""
    
    def test_no_trigger_within_cap(self, engine):
        """Test no trigger when total risk within 2% cap"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # One open position with 1% risk
        open_positions = [
            create_position("P1", max_loss=5000, entry_time=current_time)
        ]
        
        # Proposed trade with 0.8% risk (total 1.8%, within 2% cap)
        proposed = create_position("P2", max_loss=4000, entry_time=current_time)
        
        status = engine.check_all_kill_switches(
            open_positions=open_positions,
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time,
            proposed_trade=proposed
        )
        
        assert not status.active
        assert KillSwitchType.PORTFOLIO_RISK_CAP.value not in status.triggered_rules
    
    def test_trigger_exceeds_cap(self, engine):
        """Test trigger when total risk exceeds 2% cap"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # One open position with 1.5% risk
        open_positions = [
            create_position("P1", max_loss=7500, entry_time=current_time)
        ]
        
        # Proposed trade with 1% risk (total 2.5%, exceeds 2% cap)
        proposed = create_position("P2", max_loss=5000, entry_time=current_time)
        
        status = engine.check_all_kill_switches(
            open_positions=open_positions,
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time,
            proposed_trade=proposed
        )
        
        assert status.active
        assert KillSwitchType.PORTFOLIO_RISK_CAP.value in status.triggered_rules
    
    def test_multiple_open_positions(self, engine):
        """Test risk cap with multiple open positions"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Two open positions totaling 1.6% risk
        open_positions = [
            create_position("P1", max_loss=4000, entry_time=current_time),
            create_position("P2", max_loss=4000, entry_time=current_time)
        ]
        
        # Proposed trade with 0.6% risk (total 2.2%, exceeds cap)
        proposed = create_position("P3", max_loss=3000, entry_time=current_time)
        
        status = engine.check_all_kill_switches(
            open_positions=open_positions,
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time,
            proposed_trade=proposed
        )
        
        assert status.active
        assert KillSwitchType.PORTFOLIO_RISK_CAP.value in status.triggered_rules


class TestTaxLiquidityCheck:
    """Test tax liquidity check"""
    
    def test_no_trigger_within_buffer(self, engine):
        """Test no trigger when tax liability within cash buffer"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Tax liability = ₹15,000, cash buffer = ₹15,000
        performance = PerformanceMetrics(
            current_equity=500000,
            ytd_gross_profits=50000,
            ytd_tax_liability=15000,
            cash_buffer=15000
        )
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=performance,
            current_time=current_time
        )
        
        assert not status.active
        assert KillSwitchType.TAX_LIQUIDITY.value not in status.triggered_rules
    
    def test_trigger_exceeds_buffer(self, engine):
        """Test trigger when tax liability exceeds cash buffer"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        # Tax liability = ₹20,000, cash buffer = ₹15,000
        performance = PerformanceMetrics(
            current_equity=500000,
            ytd_gross_profits=50000,
            ytd_tax_liability=20000,
            cash_buffer=15000
        )
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=performance,
            current_time=current_time
        )
        
        assert status.active
        assert KillSwitchType.TAX_LIQUIDITY.value in status.triggered_rules


class TestFrequencyLimits:
    """Test weekly trade frequency limits"""
    
    def test_no_trigger_below_limit(self, engine):
        """Test no trigger when trades below weekly limit"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))  # Wednesday
        
        # One trade this week (limit is 2)
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 9, 10, 0)),  # Tuesday
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=1000
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert not status.active
        assert KillSwitchType.FREQUENCY_LIMIT.value not in status.triggered_rules
    
    def test_trigger_at_limit(self, engine):
        """Test trigger when weekly trade limit reached"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))  # Wednesday
        
        # Two trades this week (limit is 2)
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),  # Monday
                exit_time=IST.localize(datetime(2024, 1, 9, 13, 0)),
                max_loss=5000,
                realized_pnl=1000
            ),
            create_trade(
                "T2",
                entry_time=IST.localize(datetime(2024, 1, 9, 14, 0)),  # Tuesday
                exit_time=IST.localize(datetime(2024, 1, 10, 13, 0)),
                max_loss=5000,
                realized_pnl=1000
            )
        ]
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=trades,
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=current_time
        )
        
        assert status.active
        assert KillSwitchType.FREQUENCY_LIMIT.value in status.triggered_rules


class TestTimeBlocks:
    """Test time-based trading blocks"""
    
    def test_monday_morning_block(self, engine):
        """Test no trading Monday 9:15-10:00 AM IST"""
        # Monday 9:30 AM IST (within block)
        blocked_time = IST.localize(datetime(2024, 1, 8, 9, 30))
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=blocked_time
        )
        
        assert status.active
        assert KillSwitchType.TIME_BLOCK.value in status.triggered_rules
        assert "Monday" in status.reason
    
    def test_monday_after_block(self, engine):
        """Test trading allowed Monday after 10:00 AM IST"""
        # Monday 10:01 AM IST (after block)
        allowed_time = IST.localize(datetime(2024, 1, 8, 10, 1))
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=allowed_time
        )
        
        assert not status.active
    
    def test_tuesday_expiry_block(self, engine):
        """Test no trading on Tuesday (NIFTY weekly expiry day)"""
        # Tuesday 2:00 PM IST
        tuesday = IST.localize(datetime(2024, 1, 9, 14, 0))
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=tuesday
        )

        assert status.active
        assert KillSwitchType.TIME_BLOCK.value in status.triggered_rules
        assert "Tuesday" in status.reason

    def test_other_days_allowed(self, engine):
        """Test trading allowed on other days"""
        # Wednesday 2:00 PM IST
        wednesday = IST.localize(datetime(2024, 1, 10, 14, 0))
        
        status = engine.check_all_kill_switches(
            open_positions=[],
            closed_trades=[],
            performance=PerformanceMetrics(500000, 0, 0, 0),
            current_time=wednesday
        )
        
        assert not status.active


class TestStatusSummary:
    """Test status summary generation"""
    
    def test_status_summary(self, engine):
        """Test comprehensive status summary"""
        current_time = IST.localize(datetime(2024, 1, 10, 14, 0))  # Wednesday
        
        # Some trades and positions
        trades = [
            create_trade(
                "T1",
                entry_time=IST.localize(datetime(2024, 1, 8, 10, 0)),
                exit_time=IST.localize(datetime(2024, 1, 9, 13, 0)),
                max_loss=5000,
                realized_pnl=-2000
            )
        ]
        
        positions = [
            create_position("P1", max_loss=5000, entry_time=current_time)
        ]
        
        performance = PerformanceMetrics(
            current_equity=498000,
            ytd_gross_profits=10000,
            ytd_tax_liability=3000,
            cash_buffer=3000
        )
        
        summary = engine.get_status_summary(
            open_positions=positions,
            closed_trades=trades,
            performance=performance,
            current_time=current_time
        )
        
        # Verify summary contains all expected fields
        assert "weekly_pnl" in summary
        assert "weekly_loss_limit" in summary
        assert "weekly_trade_count" in summary
        assert "portfolio_risk" in summary
        assert "portfolio_risk_cap" in summary
        assert "trauma_cooldown_active" in summary
        assert "tax_liability" in summary
        assert "cash_buffer" in summary
        assert "week_start" in summary
        assert "week_end" in summary
        assert "next_reset" in summary
        
        # Verify calculations
        assert summary["weekly_pnl"] == -2000
        assert summary["weekly_loss_limit"] == 10000  # 2% of 500k
        assert summary["weekly_trade_count"] == 1
        assert summary["portfolio_risk"] == 5000
        assert summary["portfolio_risk_cap"] == 10000  # 2% of 500k


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
