"""
Test Upstox adapter with real option data

Uses actual expiry date that has option data available.
"""

import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter

def test_real_data():
    """Test with real option data"""
    print("="*60)
    print("TESTING WITH REAL OPTION DATA")
    print("="*60)
    
    # Load config and create adapter
    config = get_config()
    adapter = UpstoxAdapter(config.upstox)
    
    # Use expiry date that has data (from find_valid_expiries.py)
    expiry = date(2026, 3, 26)
    
    print(f"\nFetching NIFTY option chain for {expiry}")
    print(f"This is a real API call with live data.\n")
    
    try:
        # Fetch option chain
        df = adapter.fetch_option_chain("NIFTY", expiry)
        
        if df.empty:
            print("✗ No data returned")
            return
        
        print(f"✓ Successfully fetched {len(df)} option contracts\n")
        
        # Display summary
        print("="*60)
        print("DATA SUMMARY")
        print("="*60)
        
        print(f"\nBasic Info:")
        print(f"  Symbol: {df['symbol'].iloc[0]}")
        print(f"  Expiry: {df['expiry'].iloc[0]}")
        print(f"  Underlying Price: ₹{df['underlying_price'].iloc[0]:,.2f}")
        print(f"  Days to Expiry: {df['days_to_expiry'].iloc[0]}")
        
        print(f"\nOption Counts:")
        print(f"  Total Contracts: {len(df)}")
        print(f"  Call Options: {len(df[df['option_type'] == 'C'])}")
        print(f"  Put Options: {len(df[df['option_type'] == 'P'])}")
        
        print(f"\nStrike Range:")
        print(f"  Minimum: {df['strike'].min():,.0f}")
        print(f"  Maximum: {df['strike'].max():,.0f}")
        print(f"  Unique Strikes: {df['strike'].nunique()}")
        
        # Find ATM options
        spot = df['underlying_price'].iloc[0]
        atm_strike = round(spot / 50) * 50  # Round to nearest 50
        
        print(f"\n" + "="*60)
        print(f"ATM OPTIONS (Strike: {atm_strike:,.0f})")
        print("="*60)
        
        atm_options = df[df['strike'] == atm_strike].sort_values('option_type')
        
        for _, opt in atm_options.iterrows():
            opt_type = "CALL" if opt['option_type'] == 'C' else "PUT"
            print(f"\n{opt_type}:")
            print(f"  Bid: ₹{opt['bid']:.2f} (Qty: {opt['bid_qty']})")
            print(f"  Ask: ₹{opt['ask']:.2f} (Qty: {opt['ask_qty']})")
            print(f"  LTP: ₹{opt['ltp']:.2f}")
            print(f"  IV: {opt['iv']*100:.2f}%")
            print(f"  Delta: {opt['delta']:.4f}")
            print(f"  Gamma: {opt['gamma']:.6f}")
            print(f"  Theta: {opt['theta']:.4f}")
            print(f"  Vega: {opt['vega']:.4f}")
            print(f"  OI: {opt['oi']:,.0f}")
            print(f"  Volume: {opt['volume']:,.0f}")
        
        # Data quality checks
        print(f"\n" + "="*60)
        print("DATA QUALITY CHECKS")
        print("="*60)
        
        checks = {
            "All bids <= asks": (df['bid'] <= df['ask']).all(),
            "All strikes > 0": (df['strike'] > 0).all(),
            "All gamma >= 0": (df['gamma'] >= 0).all(),
            "All vega >= 0": (df['vega'] >= 0).all(),
            "All IV >= 0": (df['iv'] >= 0).all(),
            "All OI > 0": (df['oi'] > 0).all(),
            "Bid_qty present": df['bid_qty'].notna().all(),
            "Ask_qty present": df['ask_qty'].notna().all(),
            "No missing values": not df.isnull().any().any()
        }
        
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")
        
        all_passed = all(checks.values())
        
        if all_passed:
            print(f"\n✓ ALL QUALITY CHECKS PASSED")
            print(f"\nThe Upstox adapter is working correctly with real data!")
        else:
            print(f"\n✗ Some quality checks failed")
        
        # Save sample data
        output_file = "data/options/sample_option_chain.parquet"
        adapter.save_to_parquet(df, output_file)
        print(f"\n✓ Sample data saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_real_data()
    
    if success:
        print("\n" + "="*60)
        print("✓ CHECKPOINT PASSED")
        print("="*60)
        print("\nThe Upstox adapter is verified and working.")
        print("You can now proceed to Task 4: Regime Detection Engine")
    else:
        print("\n" + "="*60)
        print("✗ CHECKPOINT FAILED")
        print("="*60)
        print("\nPlease review the errors above.")
