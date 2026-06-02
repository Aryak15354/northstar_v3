"""Debug strategy generation"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.options.strategy_generator import StrategyGenerator
from src.options.options_regime_detector import Regime
from src.options.config_loader import get_config


def create_option_chain(spot: float) -> pd.DataFrame:
    """Create sample option chain with realistic deltas"""
    
    now = datetime.now()
    expiry = now + timedelta(days=35)
    
    # Need very wide strike range to get low delta options (5-10 delta)
    strikes = np.arange(spot - 5000, spot + 5000, 50)
    
    option_data = []
    for strike in strikes:
        moneyness = strike / spot
        iv = 0.15 + 0.05 * (1 - moneyness)**2
        
        # Simplified delta model
        # For calls: delta ≈ N(d1) where d1 depends on moneyness
        # Approximation: delta decreases linearly with OTM %
        
        pct_diff = (strike - spot) / spot  # Positive for OTM calls, negative for ITM calls
        
        # Call delta: 0.5 at ATM, decreases to ~0 as strike increases
        # At +5% OTM: delta ≈ 0.18
        # At +10% OTM: delta ≈ 0.08
        # At +15% OTM: delta ≈ 0.03
        if pct_diff >= 0:  # OTM or ATM call
            # Linear approximation: delta = 0.5 - 6.4 * pct_diff
            # At 5% OTM: 0.5 - 6.4*0.05 = 0.18
            # At 10% OTM: 0.5 - 6.4*0.10 = 0.14 (adjust)
            call_delta = max(0.01, 0.5 - 3.2 * pct_diff)
        else:  # ITM call
            # ITM calls have delta > 0.5, approaching 1.0
            call_delta = min(0.99, 0.5 - 3.2 * pct_diff)
        
        # Put delta = call delta - 1
        put_delta = call_delta - 1
        
        # Call
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
            'instrument_key': f'NSE_FO|{int(strike)}CE'
        })
        
        # Put
        option_data.append({
            'strike': strike,
            'option_type': 'PE',
            'expiry': expiry,
            'iv': iv * 1.1,
            'underlying_price': spot,
            'bid': 100,
            'ask': 110,
            'ltp': 105,
            'oi': 1000,
            'delta': put_delta,
            'gamma': 0.001,
            'theta': -0.5,
            'vega': 0.1,
            'instrument_key': f'NSE_FO|{int(strike)}PE'
        })
    
    return pd.DataFrame(option_data)


if __name__ == '__main__':
    spot = 25867
    chain = create_option_chain(spot)
    
    print(f"Total options: {len(chain)}")
    print(f"Expiries: {chain['expiry'].unique()}")
    
    # Find options with target deltas
    print(f"\n" + "="*60)
    print("Looking for Iron Condor strikes:")
    print("="*60)
    
    calls = chain[chain['option_type'] == 'CE'].sort_values('strike')
    puts = chain[chain['option_type'] == 'PE'].sort_values('strike')
    
    print(f"\nCalls with delta 0.16-0.20 (short call):")
    short_calls = calls[(calls['delta'] >= 0.16) & (calls['delta'] <= 0.20)]
    print(short_calls[['strike', 'delta']])
    
    print(f"\nCalls with delta 0.05-0.10 (long call):")
    long_calls = calls[(calls['delta'] >= 0.05) & (calls['delta'] <= 0.10)]
    print(long_calls[['strike', 'delta']])
    
    print(f"\nPuts with delta -0.16 to -0.20 (short put):")
    short_puts = puts[(puts['delta'] >= -0.20) & (puts['delta'] <= -0.16)]
    print(short_puts[['strike', 'delta']])
    
    print(f"\nPuts with delta -0.05 to -0.10 (long put):")
    long_puts = puts[(puts['delta'] >= -0.10) & (puts['delta'] <= -0.05)]
    print(long_puts[['strike', 'delta']])
    
    # Test strategy generation
    config = get_config()
    generator = StrategyGenerator(config.strategies)
    
    print("\n" + "="*60)
    print("Testing Iron Condor generation")
    print("="*60)
    
    strategy = generator.generate_strategy(
        regime=Regime.LOW_VOL_SELL,
        option_chain=chain,
        underlying='NIFTY'
    )
    
    if strategy:
        print(f"✓ Strategy generated successfully!")
        print(f"  Type: {strategy.strategy_type.value}")
        print(f"  Legs: {len(strategy.legs)}")
        for i, leg in enumerate(strategy.legs):
            print(f"  Leg {i+1}: {leg.action} {leg.option_type} @ {leg.strike} (delta={leg.greeks.delta:.4f})")
    else:
        print("✗ Strategy generation failed")
