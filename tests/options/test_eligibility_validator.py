"""
Tests for Trade Eligibility Validator

Tests all validation rules:
- IV rank thresholds
- Liquidity spread
- Liquidity depth
- Expiry hygiene
- Event calendar
- Late-cycle protection
- Vol-of-vol blocking
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.options.trade_eligibility_validator import (
    TradeEligibilityValidator,
    ValidationResult,
    ValidationRule
)
from src.options.options_regime_detector import Regime, RegimeState, RegimeMetrics
from src.options.strategy_generator import (
    OptionStrategy,
    StrategyType,
    OptionLeg,
    Greeks
)
from src.options.config_loader import get_config


@pytest.fixture
def config():
    """Get test configuration"""
    return get_config()


@pytest.fixture
def validator(config):
    """Create validator instance"""
    return TradeEligibilityValidator(config)


@pytest.fixture
def sample_option_chain():
    """Create sample option chain with good liquidity"""
    strikes = np.arange(25000, 26500, 50)
    spot = 25867
    
    option_data = []
    for strike in strikes:
        moneyness = strike / spot
        base_iv = 0.15
        iv = base_iv + 0.05 * (1 - moneyness)**2
        
        # Good liquidity
        mid = max(10, 100 * (1 - abs(moneyness - 1)))
        spread = mid * 0.05  # 5% spread (within limit)
        
        for option_type in ['CE', 'PE']:
            option_data.append({
                'strike': strike,
                'option_type': option_type,
                'expiry': datetime.now() + timedelta(days=30),
                'iv': iv * (1.1 if option_type == 'PE' else 1.0),
                'underlying_price': spot,
                'bid': mid - spread/2,
                'ask': mid + spread/2,
                'bid_qty': 200,  # Good depth
                'ltp': mid,
                'delta': 0.5 - (strike - spot) / (2 * spot) if option_type == 'CE' else -0.5 + (strike - spot) / (2 * spot)
            })
    
    return pd.DataFrame(option_data)


@pytest.fixture
def sample_regime_state():
    """Create sample regime state"""
    return RegimeState(
        regime=Regime.LOW_VOL_SELL,
        metrics=RegimeMetrics(
            current_iv=0.18,
            iv_rank=0.75,  # Above 70% threshold
            iv_position=0.70,
            iv_trend="stable",
            iv_5d_ma=0.18,
            iv_20d_ma=0.17,
            skew=0.05,
            vol_of_vol_elevated=False,
            underlying_regime="NORMAL",
            days_in_regime=5  # Below late-cycle threshold
        ),
        timestamp=datetime.now(),
        confidence=0.85,
        reason="Test regime"
    )


@pytest.fixture
def sample_iron_condor():
    """Create sample Iron Condor strategy"""
    expiry = datetime.now() + timedelta(days=30)
    
    # Use strikes that exist in sample_option_chain (25000-26450 in 50-point increments)
    # Spot is 25867, so:
    # Short call: 26050 (slightly OTM)
    # Long call: 26250 (further OTM)
    # Short put: 25650 (slightly OTM)
    # Long put: 25450 (further OTM)
    
    legs = [
        OptionLeg(
            strike=26050,
            option_type='CE',
            expiry=expiry,
            action='SELL',
            quantity=50,
            premium=50,
            greeks=Greeks(delta=0.18, gamma=0.01, theta=-5, vega=10),
            instrument_key='NSE_FO|12345'
        ),
        OptionLeg(
            strike=26250,
            option_type='CE',
            expiry=expiry,
            action='BUY',
            quantity=50,
            premium=30,
            greeks=Greeks(delta=0.08, gamma=0.005, theta=-2, vega=5),
            instrument_key='NSE_FO|12346'
        ),
        OptionLeg(
            strike=25650,
            option_type='PE',
            expiry=expiry,
            action='SELL',
            quantity=50,
            premium=50,
            greeks=Greeks(delta=-0.18, gamma=0.01, theta=-5, vega=10),
            instrument_key='NSE_FO|12347'
        ),
        OptionLeg(
            strike=25450,
            option_type='PE',
            expiry=expiry,
            action='BUY',
            quantity=50,
            premium=30,
            greeks=Greeks(delta=-0.08, gamma=0.005, theta=-2, vega=5),
            instrument_key='NSE_FO|12348'
        )
    ]
    
    portfolio_greeks = Greeks(delta=0.0, gamma=0.03, theta=-10, vega=20)
    
    return OptionStrategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=legs,
        underlying='NIFTY',
        underlying_price=25867,
        regime=Regime.LOW_VOL_SELL,
        max_loss=10000,
        max_profit=4000,
        net_credit_debit=4000,
        portfolio_greeks=portfolio_greeks,
        created_at=datetime.now(),
        expiry_date=expiry,
        days_to_expiry=30,
        is_valid=True
    )


class TestIVRankThreshold:
    """Test IV rank threshold validation"""
    
    def test_low_vol_sell_above_threshold(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """LOW_VOL_SELL with IV rank > 70% should pass"""
        sample_regime_state.metrics.iv_rank = 0.75
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.IV_RANK_THRESHOLD] is True
    
    def test_low_vol_sell_below_threshold(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """LOW_VOL_SELL with IV rank < 70% should fail"""
        sample_regime_state.metrics.iv_rank = 0.65
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.IV_RANK_THRESHOLD] is False
        assert not result.is_eligible
        assert any("IV rank" in v for v in result.violations)
    
    def test_high_vol_sell_above_threshold(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """HIGH_VOL_SELL with IV rank > 80% should pass"""
        sample_regime_state.regime = Regime.HIGH_VOL_SELL
        sample_regime_state.metrics.iv_rank = 0.85
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.IV_RANK_THRESHOLD] is True
    
    def test_high_vol_sell_below_threshold(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """HIGH_VOL_SELL with IV rank < 80% should fail"""
        sample_regime_state.regime = Regime.HIGH_VOL_SELL
        sample_regime_state.metrics.iv_rank = 0.75
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.IV_RANK_THRESHOLD] is False
        assert not result.is_eligible
    
    def test_rising_vol_buy_below_threshold(self, validator, sample_regime_state, sample_option_chain):
        """RISING_VOL_BUY with IV rank < 30% should pass"""
        sample_regime_state.regime = Regime.RISING_VOL_BUY
        sample_regime_state.metrics.iv_rank = 0.25
        
        # Create long straddle
        expiry = datetime.now() + timedelta(days=30)
        legs = [
            OptionLeg(
                strike=25867,
                option_type='CE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12345'
            ),
            OptionLeg(
                strike=25867,
                option_type='PE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=-0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12346'
            )
        ]
        
        strategy = OptionStrategy(
            strategy_type=StrategyType.LONG_STRADDLE,
            legs=legs,
            underlying='NIFTY',
            underlying_price=25867,
            regime=Regime.RISING_VOL_BUY,
            max_loss=20000,
            max_profit=40000,
            net_credit_debit=-20000,
            portfolio_greeks=Greeks(delta=0.0, gamma=0.04, theta=-20, vega=40),
            created_at=datetime.now(),
            expiry_date=expiry,
            days_to_expiry=30,
            is_valid=True
        )
        
        result = validator.validate_trade(strategy, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.IV_RANK_THRESHOLD] is True


class TestLiquidityChecks:
    """Test liquidity validation"""
    
    def test_good_liquidity_spread(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Good bid-ask spread should pass"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.LIQUIDITY_SPREAD] is True
    
    def test_wide_spread(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Wide bid-ask spread should fail"""
        # Make spread 15% (above 8% limit)
        sample_option_chain['ask'] = sample_option_chain['bid'] * 1.15
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.LIQUIDITY_SPREAD] is False
        assert not result.is_eligible
        assert any("Spread" in v for v in result.violations)
    
    def test_good_liquidity_depth(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Good bid quantity should pass"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.LIQUIDITY_DEPTH] is True
    
    def test_insufficient_depth(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Insufficient bid quantity should fail"""
        # Set bid_qty to 50 (need 100 for 50 lot size × 2 multiplier)
        sample_option_chain['bid_qty'] = 50
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.LIQUIDITY_DEPTH] is False
        assert not result.is_eligible
        assert any("liquidity" in v.lower() for v in result.violations)


class TestExpiryHygiene:
    """Test expiry hygiene validation"""
    
    def test_sufficient_days_to_expiry(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """30 days to expiry should pass"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.EXPIRY_HYGIENE] is True
    
    def test_insufficient_days_to_expiry(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """< 5 days to expiry should fail"""
        # Set expiry to 3 days
        sample_iron_condor.expiry_date = datetime.now() + timedelta(days=3)
        sample_iron_condor.days_to_expiry = 3
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.EXPIRY_HYGIENE] is False
        assert not result.is_eligible
        assert any("expiry" in v.lower() for v in result.violations)


class TestEventCalendar:
    """Test event calendar validation"""
    
    def test_no_event_nearby(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """No event nearby should pass"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        # Should pass (assuming no events in test config near current date)
        assert result.rule_results[ValidationRule.EVENT_CALENDAR] is True
    
    def test_long_vol_allowed_near_event(self, validator, sample_regime_state, sample_option_chain):
        """Long-vol strategies allowed near events"""
        # Create long straddle
        expiry = datetime.now() + timedelta(days=30)
        legs = [
            OptionLeg(
                strike=25867,
                option_type='CE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12345'
            ),
            OptionLeg(
                strike=25867,
                option_type='PE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=-0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12346'
            )
        ]
        
        strategy = OptionStrategy(
            strategy_type=StrategyType.LONG_STRADDLE,
            legs=legs,
            underlying='NIFTY',
            underlying_price=25867,
            regime=Regime.RISING_VOL_BUY,
            max_loss=20000,
            max_profit=40000,
            net_credit_debit=-20000,
            portfolio_greeks=Greeks(delta=0.0, gamma=0.04, theta=-20, vega=40),
            created_at=datetime.now(),
            expiry_date=expiry,
            days_to_expiry=30,
            is_valid=True
        )
        
        result = validator.validate_trade(strategy, sample_regime_state, sample_option_chain)
        
        # Long-vol should pass even near events
        assert result.rule_results[ValidationRule.EVENT_CALENDAR] is True


class TestVolOfVol:
    """Test vol-of-vol validation"""
    
    def test_normal_vol_of_vol(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Normal vol-of-vol should pass"""
        sample_regime_state.metrics.vol_of_vol_elevated = False
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.VOL_OF_VOL] is True
    
    def test_elevated_vol_of_vol_blocks_short_vol(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Elevated vol-of-vol should block short-vol"""
        sample_regime_state.metrics.vol_of_vol_elevated = True
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.VOL_OF_VOL] is False
        assert not result.is_eligible
        assert any("vol-of-vol" in v.lower() for v in result.violations)
    
    def test_elevated_vol_of_vol_allows_long_vol(self, validator, sample_regime_state, sample_option_chain):
        """Elevated vol-of-vol should allow long-vol"""
        sample_regime_state.metrics.vol_of_vol_elevated = True
        
        # Create long straddle
        expiry = datetime.now() + timedelta(days=30)
        legs = [
            OptionLeg(
                strike=25867,
                option_type='CE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12345'
            ),
            OptionLeg(
                strike=25867,
                option_type='PE',
                expiry=expiry,
                action='BUY',
                quantity=50,
                premium=200,
                greeks=Greeks(delta=-0.5, gamma=0.02, theta=-10, vega=20),
                instrument_key='NSE_FO|12346'
            )
        ]
        
        strategy = OptionStrategy(
            strategy_type=StrategyType.LONG_STRADDLE,
            legs=legs,
            underlying='NIFTY',
            underlying_price=25867,
            regime=Regime.RISING_VOL_BUY,
            max_loss=20000,
            max_profit=40000,
            net_credit_debit=-20000,
            portfolio_greeks=Greeks(delta=0.0, gamma=0.04, theta=-20, vega=40),
            created_at=datetime.now(),
            expiry_date=expiry,
            days_to_expiry=30,
            is_valid=True
        )
        
        result = validator.validate_trade(strategy, sample_regime_state, sample_option_chain)
        
        assert result.rule_results[ValidationRule.VOL_OF_VOL] is True


class TestLateCycleProtection:
    """Test late-cycle protection"""
    
    def test_early_cycle_full_size(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Early in cycle should get full size"""
        sample_regime_state.metrics.days_in_regime = 5
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.size_adjustment == 1.0
        assert result.rule_results[ValidationRule.LATE_CYCLE_PROTECTION] is True
    
    def test_late_cycle_reduced_size(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Late in cycle should get reduced size"""
        sample_regime_state.metrics.days_in_regime = 15  # > 10 day threshold
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.size_adjustment == 0.5  # 50% reduction
        assert result.rule_results[ValidationRule.LATE_CYCLE_PROTECTION] is False
        assert len(result.warnings) > 0
        assert any("late-cycle" in w.lower() for w in result.warnings)
    
    def test_late_cycle_only_applies_to_low_vol_sell(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Late-cycle protection only applies to LOW_VOL_SELL"""
        sample_regime_state.regime = Regime.HIGH_VOL_SELL
        sample_regime_state.metrics.days_in_regime = 15
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        # Should not apply to HIGH_VOL_SELL
        assert result.size_adjustment == 1.0


class TestIntegration:
    """Integration tests"""
    
    def test_all_checks_pass(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """All checks passing should result in eligible trade"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert result.is_eligible
        assert len(result.violations) == 0
        assert result.size_adjustment == 1.0
    
    def test_multiple_violations(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Multiple violations should all be reported"""
        # Set up multiple violations
        sample_regime_state.metrics.iv_rank = 0.65  # Below threshold
        sample_regime_state.metrics.vol_of_vol_elevated = True  # Blocks short-vol
        sample_iron_condor.days_to_expiry = 3  # Too close to expiry
        
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        assert not result.is_eligible
        assert len(result.violations) >= 3
    
    def test_validation_result_serialization(self, validator, sample_iron_condor, sample_regime_state, sample_option_chain):
        """Validation result should serialize to dict"""
        result = validator.validate_trade(sample_iron_condor, sample_regime_state, sample_option_chain)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'is_eligible' in result_dict
        assert 'violations' in result_dict
        assert 'warnings' in result_dict
        assert 'size_adjustment' in result_dict
        assert 'rule_results' in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
