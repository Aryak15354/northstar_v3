"""
Integration Test: Position Lifecycle

Tests the complete position lifecycle:
- Open position
- Daily MTM updates
- Exit condition monitoring
- Position close
- Greek aggregation

This verifies position management works end-to-end.
"""

import pytest
from datetime import datetime, date, timedelta
import pandas as pd

from src.options.position_manager import PositionManager, Position, PositionLeg, ExitReason
from src.options.strategy_generator import OptionStrategy, OptionLeg as StrategyLeg, Greeks, StrategyType
from src.options.options_regime_detector import Regime
from src.options.config_loader import ExitRulesConfig, GreekSafetyBandsConfig


@pytest.fixture
def position_manager():
    """Create position manager"""
    exit_config = ExitRulesConfig(
        profit_target_pct=0.55,
        stop_loss_pct=0.40,
        days_before_expiry=2,
        precedence=['stop_loss', 'gamma_escalation', 'regime_flip', 'time_decay', 'profit_target'],
        regime_flip_min_hold_minutes=30,
        regime_flip_confirmation_cycles=2,
        regime_flip_market_open_grace_minutes=30,
    )
    
    greek_config = GreekSafetyBandsConfig(
        delta_min=-0.2,
        delta_max=0.2,
        theta_min=0.0,
        vega_min=-0.3,
        vega_max=0.1,
        gamma_escalation={'spike_multiplier': 2.0}
    )
    
    return PositionManager(exit_config, greek_config)


@pytest.fixture
def sample_strategy():
    """Create sample iron condor strategy"""
    expiry_date = date.today() + timedelta(days=20)
    expiry_datetime = datetime.combine(expiry_date, datetime.min.time())
    
    legs = [
        StrategyLeg(
            strike=21500.0,
            option_type="CE",
            expiry=expiry_datetime,
            action="SELL",
            quantity=50,
            premium=100.0,
            greeks=Greeks(delta=0.20, gamma=0.01, theta=-10.0, vega=5.0),
            instrument_key="NSE_FO|NIFTY_21500_CE"
        ),
        StrategyLeg(
            strike=22000.0,
            option_type="CE",
            expiry=expiry_datetime,
            action="BUY",
            quantity=50,
            premium=50.0,
            greeks=Greeks(delta=0.10, gamma=0.005, theta=-5.0, vega=3.0),
            instrument_key="NSE_FO|NIFTY_22000_CE"
        ),
        StrategyLeg(
            strike=21000.0,
            option_type="PE",
            expiry=expiry_datetime,
            action="SELL",
            quantity=50,
            premium=100.0,
            greeks=Greeks(delta=-0.20, gamma=0.01, theta=-10.0, vega=5.0),
            instrument_key="NSE_FO|NIFTY_21000_PE"
        ),
        StrategyLeg(
            strike=20500.0,
            option_type="PE",
            expiry=expiry_datetime,
            action="BUY",
            quantity=50,
            premium=50.0,
            greeks=Greeks(delta=-0.10, gamma=0.005, theta=-5.0, vega=3.0),
            instrument_key="NSE_FO|NIFTY_20500_PE"
        ),
    ]
    
    return OptionStrategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=legs,
        underlying="NIFTY",
        underlying_price=21250.0,
        regime=Regime.LOW_VOL_SELL,
        max_loss=5000.0,
        max_profit=10000.0,
        net_credit_debit=10000.0,
        portfolio_greeks=Greeks(delta=0.0, gamma=0.03, theta=-30.0, vega=16.0),
        created_at=datetime.now(),
        expiry_date=expiry_datetime,
        days_to_expiry=20
    )


def test_open_position(position_manager, sample_strategy):
    """Test opening a position"""
    entry_time = datetime.now()
    
    position = position_manager.open_position(sample_strategy, entry_time)
    
    assert position.position_id.startswith("POS_")
    assert position.strategy_type == "iron_condor"
    assert position.regime_at_entry == Regime.LOW_VOL_SELL
    assert len(position.legs) == 4
    assert position.max_loss == 5000.0
    assert position.max_profit == 10000.0
    assert position.entry_credit_debit == 10000.0
    assert position.is_open()
    assert position.days_held == 0


def test_update_mtm(position_manager, sample_strategy):
    """Test mark-to-market update"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Create current option chain with updated prices
    # NOTE: option_type must match what's in position legs ('CE'/'PE')
    current_chain = pd.DataFrame([
        {
            'strike': 21500.0,
            'option_type': 'CE',  # Changed from 'call' to 'CE'
            'premium': 80.0,  # Down from 100
            'iv': 14.5,
            'delta': 0.18,
            'gamma': 0.01,
            'theta': -9.0,
            'vega': 4.5
        },
        {
            'strike': 22000.0,
            'option_type': 'CE',  # Changed from 'call' to 'CE'
            'premium': 40.0,  # Down from 50
            'iv': 13.5,
            'delta': 0.09,
            'gamma': 0.005,
            'theta': -4.5,
            'vega': 2.8
        },
        {
            'strike': 21000.0,
            'option_type': 'PE',  # Changed from 'put' to 'PE'
            'premium': 80.0,  # Down from 100
            'iv': 14.5,
            'delta': -0.18,
            'gamma': 0.01,
            'theta': -9.0,
            'vega': 4.5
        },
        {
            'strike': 20500.0,
            'option_type': 'PE',  # Changed from 'put' to 'PE'
            'premium': 40.0,  # Down from 50
            'iv': 13.5,
            'delta': -0.09,
            'gamma': 0.005,
            'theta': -4.5,
            'vega': 2.8
        },
    ])
    
    # Update MTM
    current_time = entry_time + timedelta(days=1)
    updated_position = position_manager.update_position_mtm(
        position, current_chain, current_time
    )
    
    # Check MTM calculation
    # Sold calls/puts: (100-80) * 50 * 2 = 2000 profit
    # Bought calls/puts: (50-40) * 50 * 2 = 1000 loss
    # Net: 2000 - 1000 = 1000 profit
    assert updated_position.unrealized_pnl > 0
    assert updated_position.days_held == 1


def test_profit_target_exit(position_manager, sample_strategy):
    """Test exit on profit target"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Simulate profit target hit (55% of max profit = 5500)
    position.unrealized_pnl = 5500.0
    
    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.LOW_VOL_SELL,
        date.today()
    )
    
    assert exit_signal is not None
    assert exit_signal.should_exit
    assert exit_signal.reason == ExitReason.PROFIT_TARGET


def test_stop_loss_exit(position_manager, sample_strategy):
    """Test exit on stop loss"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Simulate stop loss hit (40% of max loss = -2000)
    position.unrealized_pnl = -2000.0
    
    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.LOW_VOL_SELL,
        date.today()
    )
    
    assert exit_signal is not None
    assert exit_signal.should_exit
    assert exit_signal.reason == ExitReason.STOP_LOSS


def test_regime_flip_exit(position_manager, sample_strategy):
    """Test exit on regime flip"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Regime flips
    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.HIGH_VOL_SELL,  # Different from entry regime
        date.today()
    )
    
    assert exit_signal is not None
    assert exit_signal.should_exit
    assert exit_signal.reason == ExitReason.REGIME_FLIP


def test_regime_flip_exit_can_be_deferred(position_manager, sample_strategy):
    """Regime-flip exit should be suppressible until cooldown/confirmation is satisfied."""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    if position.greeks is not None:
        position.greeks.theta = 1.0

    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.HIGH_VOL_SELL,
        date.today(),
        current_time=entry_time + timedelta(minutes=5),
        regime_flip_exit_allowed=False,
    )

    assert exit_signal is None


def test_regime_flip_exit_respects_minimum_hold_minutes(position_manager, sample_strategy):
    """Minimum hold should suppress regime-flip exits even when caller marks the flip eligible."""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    if position.greeks is not None:
        position.greeks.theta = 1.0

    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.HIGH_VOL_SELL,
        date.today(),
        current_time=entry_time + timedelta(minutes=5),
        regime_flip_exit_allowed=True,
        minimum_hold_minutes=30.0,
    )

    assert exit_signal is None


def test_time_decay_exit(position_manager, sample_strategy):
    """Test exit approaching expiry"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # 1 day before expiry (threshold is 2 days)
    current_date = position.expiry - timedelta(days=1)
    
    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.LOW_VOL_SELL,
        current_date
    )
    
    assert exit_signal is not None
    assert exit_signal.should_exit
    assert exit_signal.reason == ExitReason.TIME_DECAY


def test_close_position(position_manager, sample_strategy):
    """Test closing a position"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Close position
    exit_time = entry_time + timedelta(days=5)
    closed_position = position_manager.close_position(
        position,
        exit_time,
        "profit_target"
    )
    
    assert not closed_position.is_open()
    assert closed_position.exit_time == exit_time
    assert closed_position.exit_reason == "profit_target"
    assert closed_position.realized_pnl is not None
    assert closed_position.days_held == 5
    
    # Position should be moved to closed list
    assert len(position_manager.get_open_positions()) == 0
    assert len(position_manager.get_closed_positions()) == 1


def test_portfolio_greeks_aggregation(position_manager, sample_strategy):
    """Test portfolio Greeks aggregation"""
    import time
    
    # Open 2 positions with different timestamps
    position1 = position_manager.open_position(
        sample_strategy,
        datetime.now()
    )
    
    time.sleep(0.01)  # Small delay to ensure different timestamp
    position2 = position_manager.open_position(
        sample_strategy,
        datetime.now()
    )
    
    # Calculate portfolio Greeks
    portfolio_greeks = position_manager.calculate_portfolio_greeks()
    
    # Should be sum of both positions
    assert portfolio_greeks.delta == pytest.approx(0.0, abs=0.1)  # Near neutral
    assert portfolio_greeks.gamma > 0
    assert portfolio_greeks.theta < 0  # Negative theta
    assert portfolio_greeks.vega > 0


def test_total_open_risk(position_manager, sample_strategy):
    """Test total open risk calculation"""
    # Open 2 positions with different timestamps to ensure unique IDs
    import time
    position_manager.open_position(sample_strategy, datetime.now())
    time.sleep(0.01)  # Small delay to ensure different timestamp
    position_manager.open_position(sample_strategy, datetime.now())
    
    total_risk = position_manager.get_total_open_risk()
    
    # Should be sum of max losses
    assert total_risk == 10000.0  # 2 * 5000


def test_exit_rule_precedence(position_manager, sample_strategy):
    """Test exit rule precedence (stop loss > regime flip)"""
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    # Trigger both stop loss and regime flip
    position.unrealized_pnl = -2000.0  # Stop loss
    
    exit_signal = position_manager.check_exit_conditions(
        position,
        Regime.HIGH_VOL_SELL,  # Regime flip
        date.today()
    )
    
    # Should exit on stop loss (higher priority)
    assert exit_signal.reason == ExitReason.STOP_LOSS


def test_get_summary(position_manager, sample_strategy):
    """Test position manager summary"""
    import time
    
    # Open 1 position
    position = position_manager.open_position(sample_strategy, datetime.now())
    position.unrealized_pnl = 1000.0
    
    # Close 1 position (with different timestamp)
    time.sleep(0.01)
    closed_position = position_manager.open_position(sample_strategy, datetime.now())
    position_manager.close_position(closed_position, datetime.now(), "profit_target")
    
    summary = position_manager.get_summary()
    
    assert summary['open_positions_count'] == 1
    assert summary['closed_positions_count'] == 1
    assert summary['total_open_risk'] == 5000.0
    assert summary['total_unrealized_pnl'] == 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
