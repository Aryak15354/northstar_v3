"""
Tests for System Hygiene Rules

Verifies concentration limits and cooling periods.
"""

import pytest
from datetime import datetime, timedelta

from src.options.system_hygiene import SystemHygieneRules, TradeRecord, HygieneCheckResult
from src.options.regime_detector import Regime


@pytest.fixture
def hygiene_rules():
    """Create system hygiene rules with default config"""
    return SystemHygieneRules(
        concentration_lookback=2,
        cooling_lookback=2,
        iv_rank_extreme_threshold=0.90,
        iv_rank_extreme_low=0.10
    )


def test_initial_state(hygiene_rules):
    """Test initial state with no trades"""
    # Should allow any strategy
    result = hygiene_rules.check_strategy_concentration("iron_condor")
    assert result.allowed
    assert result.reason == "insufficient_history"
    
    # Should allow trading (no cooling)
    result = hygiene_rules.check_success_cooling(0.75)
    assert result.allowed
    assert result.reason == "insufficient_history"


def test_strategy_concentration_allowed(hygiene_rules):
    """Test strategy concentration allows diverse strategies"""
    # Add 2 different strategies
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should allow iron_condor (not 3rd consecutive)
    result = hygiene_rules.check_strategy_concentration("iron_condor")
    assert result.allowed
    assert result.reason == "concentration_ok"


def test_strategy_concentration_blocked(hygiene_rules):
    """Test strategy concentration blocks 3rd consecutive"""
    # Add 2 iron condors
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    
    # Should block 3rd iron condor
    result = hygiene_rules.check_strategy_concentration("iron_condor")
    assert not result.allowed
    assert result.reason == "strategy_concentration"
    assert "3rd consecutive" in result.details


def test_strategy_concentration_resets_with_different_strategy(hygiene_rules):
    """Test concentration counter resets with different strategy"""
    # Add 2 iron condors
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    
    # Add different strategy
    hygiene_rules.add_trade(
        "T3", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should now allow iron condor again
    result = hygiene_rules.check_strategy_concentration("iron_condor")
    assert result.allowed


def test_success_cooling_not_triggered_with_losses(hygiene_rules):
    """Test cooling not triggered if not all wins"""
    # Add 1 win, 1 loss
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, False, -500.0
    )
    
    # Should allow trading (not all profitable)
    result = hygiene_rules.check_success_cooling(0.75)
    assert result.allowed
    assert result.reason == "no_cooling_needed"


def test_success_cooling_triggered(hygiene_rules):
    """Test cooling triggered after 2 consecutive wins"""
    # Add 2 wins
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should block trading (cooling period)
    result = hygiene_rules.check_success_cooling(0.75)
    assert not result.allowed
    assert result.reason == "success_cooling"


def test_success_cooling_bypassed_extreme_high_iv(hygiene_rules):
    """Test cooling bypassed when IV extremely high"""
    # Add 2 wins
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should allow trading (IV extreme high)
    result = hygiene_rules.check_success_cooling(0.92)  # >90%
    assert result.allowed
    assert result.reason == "iv_extreme_high"


def test_success_cooling_bypassed_extreme_low_iv(hygiene_rules):
    """Test cooling bypassed when IV extremely low"""
    # Add 2 wins
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should allow trading (IV extreme low)
    result = hygiene_rules.check_success_cooling(0.08)  # <10%
    assert result.allowed
    assert result.reason == "iv_extreme_low"


def test_success_cooling_not_bypassed_moderate_iv(hygiene_rules):
    """Test cooling not bypassed with moderate IV"""
    # Add 2 wins
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should block trading (IV not extreme)
    result = hygiene_rules.check_success_cooling(0.50)
    assert not result.allowed
    assert result.reason == "success_cooling"


def test_check_all_hygiene_rules_pass(hygiene_rules):
    """Test all hygiene rules pass"""
    # Add 1 win, 1 loss (diverse strategies)
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, False, -500.0
    )
    
    # Should pass all checks
    result = hygiene_rules.check_all_hygiene_rules("long_straddle", 0.75)
    assert result.allowed
    assert result.reason == "all_checks_passed"


def test_check_all_hygiene_rules_fail_concentration(hygiene_rules):
    """Test all hygiene rules fail on concentration"""
    # Add 2 iron condors
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, False, -500.0
    )
    
    # Should fail on concentration
    result = hygiene_rules.check_all_hygiene_rules("iron_condor", 0.75)
    assert not result.allowed
    assert result.reason == "strategy_concentration"


def test_check_all_hygiene_rules_fail_cooling(hygiene_rules):
    """Test all hygiene rules fail on cooling"""
    # Add 2 wins (diverse strategies)
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 1000.0
    )
    
    # Should fail on cooling
    result = hygiene_rules.check_all_hygiene_rules("long_straddle", 0.75)
    assert not result.allowed
    assert result.reason == "success_cooling"


def test_get_recent_trades_summary(hygiene_rules):
    """Test recent trades summary"""
    # Add trades
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 800.0
    )
    hygiene_rules.add_trade(
        "T3", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, False, -500.0
    )
    
    summary = hygiene_rules.get_recent_trades_summary()
    
    assert summary['total_trades'] == 3
    assert summary['profitable_trades'] == 2
    assert summary['win_rate'] == pytest.approx(2/3)
    assert summary['consecutive_wins'] == 0
    assert summary['consecutive_losses'] == 1
    assert summary['strategy_distribution'] == {
        'iron_condor': 2,
        'calendar_spread': 1
    }


def test_consecutive_wins_count(hygiene_rules):
    """Test consecutive wins counting"""
    # Add 3 consecutive wins
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 800.0
    )
    hygiene_rules.add_trade(
        "T3", datetime.now(), "long_straddle", Regime.RISING_VOL_BUY, True, 1200.0
    )
    
    summary = hygiene_rules.get_recent_trades_summary()
    assert summary['consecutive_wins'] == 3
    assert summary['consecutive_losses'] == 0


def test_reset(hygiene_rules):
    """Test reset clears history"""
    # Add trades
    hygiene_rules.add_trade(
        "T1", datetime.now(), "iron_condor", Regime.LOW_VOL_SELL, True, 1000.0
    )
    hygiene_rules.add_trade(
        "T2", datetime.now(), "calendar_spread", Regime.HIGH_VOL_SELL, True, 800.0
    )
    
    # Reset
    hygiene_rules.reset()
    
    # Should be back to initial state
    summary = hygiene_rules.get_recent_trades_summary()
    assert summary['total_trades'] == 0
    
    result = hygiene_rules.check_strategy_concentration("iron_condor")
    assert result.allowed
    assert result.reason == "insufficient_history"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
