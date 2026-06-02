"""
Test Strategy Generator

Tests strategy generation for all regime types.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.options.strategy_generator import StrategyGenerator, StrategyType
from src.options.options_regime_detector import Regime
from src.options.config_loader import get_config


def create_option_chain_with_expiries(spot: float, num_strikes: int = 40) -> pd.DataFrame:
    """Create sample option chain with multiple expiries"""
    
    # Create multiple expiries
    now = datetime.now()
    expiries = [
        now + timedelta(days=10),   # Near-term
        now + timedelta(days=35),   # Mid-term
        now + timedelta(days=50)    # Far-term
    ]
    
    # Need very wide strike range to get low delta options (5-10 delta)
    strikes = np.arange(spot - 5000, spot + 5000, 50)
    
    option_data = []
    for expiry in expiries:
        for strike in strikes:
            # Simple IV smile
            moneyness = strike / spot
            iv = 0.15 + 0.05 * (1 - moneyness)**2
            
            # Simplified delta model
            # For calls: delta decreases linearly with OTM %
            pct_diff = (strike - spot) / spot
            
            if pct_diff >= 0:  # OTM or ATM call
                call_delta = max(0.01, 0.5 - 3.2 * pct_diff)
            else:  # ITM call
                call_delta = min(0.99, 0.5 - 3.2 * pct_diff)
            
            put_delta = call_delta - 1
            
            # Call option
            option_data.append({
                'strike': strike,
                'option_type': 'CE',
                'expiry': expiry,
                'iv': iv,
                'underlying_price': spot,
                'bid': 100,
                'ask': 110,
                'ltp': 105,
                'oi': 1000,
                'delta': call_delta,
                'gamma': 0.001,
                'theta': -0.5,
                'vega': 0.1,
                'instrument_key': f'NSE_FO|{int(strike)}CE{expiry.strftime("%d%b%y").upper()}'
            })
            
            # Put option
            option_data.append({
                'strike': strike,
                'option_type': 'PE',
                'expiry': expiry,
                'iv': iv * 1.1,  # Put skew
                'underlying_price': spot,
                'bid': 100,
                'ask': 110,
                'ltp': 105,
                'oi': 1000,
                'delta': put_delta,
                'gamma': 0.001,
                'theta': -0.5,
                'vega': 0.1,
                'instrument_key': f'NSE_FO|{int(strike)}PE{expiry.strftime("%d%b%y").upper()}'
            })
    
    return pd.DataFrame(option_data)


def test_strategy_generation():
    """Test strategy generation for all regimes"""
    print("="*60)
    print("STRATEGY GENERATION TESTS")
    print("="*60)
    
    config = get_config()
    generator = StrategyGenerator(config.strategies)
    
    spot = 25867
    option_chain = create_option_chain_with_expiries(spot)
    
    # Test 1: Iron Condor for LOW_VOL_SELL
    print("\n" + "="*60)
    print("TEST 1: Iron Condor (LOW_VOL_SELL)")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.LOW_VOL_SELL,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    assert strategy is not None, "Strategy should be generated for LOW_VOL_SELL"
    assert strategy.strategy_type == StrategyType.IRON_CONDOR
    assert len(strategy.legs) == 4, "Iron Condor should have 4 legs"
    assert strategy.is_valid, f"Strategy should be valid: {strategy.validation_errors}"
    
    print(f"Strategy Type: {strategy.strategy_type.value}")
    print(f"Legs: {len(strategy.legs)}")
    print(f"Max Loss: ₹{strategy.max_loss:.2f}")
    print(f"Max Profit: ₹{strategy.max_profit:.2f}")
    print(f"Net Credit: ₹{strategy.net_credit_debit:.2f}")
    print(f"Risk/Reward: {strategy.risk_reward_ratio:.2f}")
    print(f"Portfolio Delta: {strategy.portfolio_greeks.delta:.4f}")
    print(f"Portfolio Theta: {strategy.portfolio_greeks.theta:.4f}")
    print(f"Valid: {strategy.is_valid}")
    print("✓ Test 1 passed")
    
    # Test 2: Calendar Spread for RISING_VOL_BUY
    print("\n" + "="*60)
    print("TEST 2: Calendar Spread (RISING_VOL_BUY)")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.RISING_VOL_BUY,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    assert strategy is not None, "Strategy should be generated for RISING_VOL_BUY"
    assert strategy.strategy_type == StrategyType.CALENDAR_SPREAD
    assert len(strategy.legs) == 2, "Calendar Spread should have 2 legs"
    
    print(f"Strategy Type: {strategy.strategy_type.value}")
    print(f"Legs: {len(strategy.legs)}")
    print(f"Max Loss: ₹{strategy.max_loss:.2f}")
    print(f"Max Profit: ₹{strategy.max_profit:.2f}")
    print(f"Net Debit: ₹{abs(strategy.net_credit_debit):.2f}")
    print(f"Valid: {strategy.is_valid}")
    print("✓ Test 2 passed")
    
    # Test 3: Long Straddle for CRASH_HEDGE
    print("\n" + "="*60)
    print("TEST 3: Long Straddle (CRASH_HEDGE)")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.CRASH_HEDGE,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    assert strategy is not None, "Strategy should be generated for CRASH_HEDGE"
    assert strategy.strategy_type == StrategyType.LONG_STRADDLE
    assert len(strategy.legs) == 2, "Long Straddle should have 2 legs"
    
    # Check that we have one call and one put
    call_legs = [leg for leg in strategy.legs if leg.option_type == 'CE']
    put_legs = [leg for leg in strategy.legs if leg.option_type == 'PE']
    assert len(call_legs) == 1, "Should have 1 call leg"
    assert len(put_legs) == 1, "Should have 1 put leg"
    assert call_legs[0].strike == put_legs[0].strike, "Call and put should have same strike"
    
    print(f"Strategy Type: {strategy.strategy_type.value}")
    print(f"Legs: {len(strategy.legs)}")
    print(f"ATM Strike: {strategy.legs[0].strike}")
    print(f"Max Loss: ₹{strategy.max_loss:.2f}")
    print(f"Max Profit: ₹{strategy.max_profit:.2f}")
    print(f"Total Cost: ₹{strategy.max_loss:.2f}")
    print(f"Valid: {strategy.is_valid}")
    print("✓ Test 3 passed")
    
    # Test 4: No strategy for NEUTRAL
    print("\n" + "="*60)
    print("TEST 4: No Strategy (NEUTRAL)")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.NEUTRAL,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    assert strategy is None, "No strategy should be generated for NEUTRAL"
    print("✓ Test 4 passed - NEUTRAL correctly returns None")
    
    # Test 5: Lot size validation
    print("\n" + "="*60)
    print("TEST 5: Lot Size Validation")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.LOW_VOL_SELL,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    lot_size = generator._get_lot_size('NIFTY')
    print(f"NIFTY lot size: {lot_size}")
    
    for i, leg in enumerate(strategy.legs):
        print(f"Leg {i+1}: {leg.action} {leg.quantity} x {leg.option_type} @ {leg.strike}")
        assert leg.quantity % lot_size == 0, f"Leg quantity {leg.quantity} not multiple of {lot_size}"
    
    print("✓ Test 5 passed - All legs have valid lot sizes")
    
    # Test 6: Strategy serialization
    print("\n" + "="*60)
    print("TEST 6: Strategy Serialization")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.LOW_VOL_SELL,
        option_chain=option_chain,
        underlying='NIFTY'
    )
    
    strategy_dict = strategy.to_dict()
    
    assert 'strategy_type' in strategy_dict
    assert 'legs' in strategy_dict
    assert 'max_loss' in strategy_dict
    assert 'portfolio_greeks' in strategy_dict
    
    print(f"Serialized keys: {list(strategy_dict.keys())}")
    print("✓ Test 6 passed - Strategy serialization works")
    
    print("\n" + "="*60)
    print("ALL STRATEGY GENERATION TESTS PASSED")
    print("="*60)


if __name__ == '__main__':
    test_strategy_generation()
