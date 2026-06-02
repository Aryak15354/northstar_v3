"""
Simple End-to-End Integration Test for Options Trading System

This test validates that the core components can be instantiated
and work together in a basic pipeline.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.options.options_regime_detector import RegimeDetector, Regime
from src.options.strategy_generator import StrategyGenerator
from src.options.trade_eligibility_validator import TradeEligibilityValidator
from src.options.config_loader import get_config


def test_end_to_end_pipeline():
    """
    Test complete signal generation pipeline
    
    Validates:
    1. Configuration loads correctly
    2. Regime detection works with mock data
    3. Strategy generation works
    4. Trade eligibility validation works
    5. All components integrate correctly
    """
    print("\n=== End-to-End Pipeline Test ===\n")
    
    # Step 1: Load configuration
    print("Step 1: Loading configuration...")
    config = get_config()
    assert config is not None
    print("  ✓ Configuration loaded\n")
    
    # Step 2: Create mock option chain
    print("Step 2: Creating mock option chain...")
    spot = 25000.0
    strikes = np.arange(24000, 26000, 100)
    
    option_data = []
    for strike in strikes:
        moneyness = strike / spot
        base_iv = 0.15
        iv = base_iv + 0.05 * (1 - moneyness)**2
        mid = max(10, 100 * (1 - abs(moneyness - 1)))
        spread = mid * 0.05
        
        option_data.append({
            'strike': float(strike),
            'option_type': 'CE',
            'expiry': datetime.now() + timedelta(days=30),
            'iv': iv,
            'underlying_price': spot,
            'bid': mid - spread/2,
            'ask': mid + spread/2,
            'bid_qty': 100,
            'ask_qty': 100,
            'ltp': mid,
            'delta': 0.5 - (strike - spot) / (2 * spot),
            'gamma': 0.001,
            'theta': -0.05,
            'vega': 0.1
        })
    
    option_chain = pd.DataFrame(option_data)
    print(f"  ✓ Created option chain with {len(option_chain)} options\n")
    
    # Step 3: Create mock IV history
    print("Step 3: Creating mock IV history...")
    iv_history = pd.Series([0.10 + 0.10 * (i / 252) for i in range(252)])
    print(f"  ✓ Created IV history with {len(iv_history)} days\n")
    
    # Step 4: Detect regime
    print("Step 4: Detecting regime...")
    detector = RegimeDetector(config.regime_detection)
    regime_state = detector.detect_regime(
        option_chain,
        iv_history,
        underlying_regime="NORMAL"
    )
    
    print(f"  ✓ Regime detected: {regime_state.regime.value}")
    print(f"    IV Rank: {regime_state.metrics.iv_rank:.2%}")
    print(f"    Confidence: {regime_state.confidence:.2%}")
    print(f"    Days in regime: {regime_state.metrics.days_in_regime}\n")
    
    assert regime_state.regime in [
        Regime.LOW_VOL_SELL,
        Regime.HIGH_VOL_SELL,
        Regime.RISING_VOL_BUY,
        Regime.NEUTRAL,
        Regime.CRASH_HEDGE
    ]
    
    # Step 5: Generate strategy
    print("Step 5: Generating strategy...")
    generator = StrategyGenerator(config.strategies)
    strategy = generator.generate_strategy(
        regime_state.regime,
        option_chain,
        'NIFTY'
    )
    
    if strategy:
        print(f"  ✓ Strategy generated: {strategy.strategy_type.value}")
        print(f"    Legs: {len(strategy.legs)}")
        print(f"    Max Loss: ₹{strategy.max_loss:,.0f}")
        print(f"    Max Profit: ₹{strategy.max_profit:,.0f}")
        print(f"    Valid: {strategy.is_valid}\n")
        
        assert strategy.is_valid
        assert len(strategy.legs) > 0
        
        # Step 6: Validate trade eligibility
        print("Step 6: Validating trade eligibility...")
        validator = TradeEligibilityValidator(config)
        validation_result = validator.validate_trade(
            strategy,
            regime_state,
            option_chain
        )
        
        print(f"  ✓ Validation complete")
        print(f"    Eligible: {validation_result.is_eligible}")
        print(f"    Size Adjustment: {validation_result.size_adjustment:.0%}")
        print(f"    Violations: {len(validation_result.violations)}")
        if validation_result.violations:
            for v in validation_result.violations:
                print(f"      - {v}")
        print(f"    Warnings: {len(validation_result.warnings)}")
        if validation_result.warnings:
            for w in validation_result.warnings:
                print(f"      - {w}\n")
        
        assert validation_result.size_adjustment >= 0.0
        assert validation_result.size_adjustment <= 1.0
    else:
        print(f"  ✓ No strategy generated for {regime_state.regime.value} regime")
        print("    (This is expected for NEUTRAL or CRASH_HEDGE regimes)\n")
    
    print("=" * 50)
    print("✓ END-TO-END PIPELINE TEST PASSED")
    print("=" * 50)


if __name__ == "__main__":
    test_end_to_end_pipeline()
