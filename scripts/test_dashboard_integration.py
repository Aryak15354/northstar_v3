#!/usr/bin/env python3
"""
Test script to verify dashboard integration with options system
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from pathlib import Path
from datetime import datetime

def test_dashboard_data_loading():
    """Test that dashboard can load options system data"""
    
    # Check if options dashboard state file exists
    options_state_file = Path("data/options/live/options_dashboard_state.json")
    
    if not options_state_file.exists():
        print("❌ Options dashboard state file not found")
        return False
    
    try:
        # Load the data
        with open(options_state_file, 'r') as f:
            state = json.load(f)
        
        print("✅ Successfully loaded options dashboard state")
        
        # Check key sections
        required_sections = [
            'timestamp',
            'current_regime',
            'active_positions',
            'closed_positions',
            'portfolio_greeks',
            'ytd',
            'trade_metrics',
            'options_cycle'
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in state:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"⚠️  Missing sections: {missing_sections}")
        else:
            print("✅ All required sections present")
        
        # Print summary statistics
        print(f"\n📊 Data Summary:")
        print(f"   Timestamp: {state.get('timestamp', 'N/A')}")
        print(f"   Current Regime: {state.get('current_regime', 'N/A')}")
        print(f"   Active Positions: {len(state.get('active_positions', []))}")
        print(f"   Closed Positions: {len(state.get('closed_positions', []))}")
        print(f"   YTD Net P&L: ${state.get('ytd', {}).get('ytd_net_pnl', 0):,.2f}")
        print(f"   Total Trades: {state.get('trade_metrics', {}).get('total_trades', 0)}")
        print(f"   Win Rate: {state.get('trade_metrics', {}).get('win_rate', 0):.1%}")
        
        # Check portfolio Greeks
        portfolio_greeks = state.get('portfolio_greeks', {})
        print(f"\n📈 Portfolio Greeks:")
        print(f"   Delta: {portfolio_greeks.get('delta', 0):.2f}")
        print(f"   Gamma: {portfolio_greeks.get('gamma', 0):.2f}")
        print(f"   Vega: {portfolio_greeks.get('vega', 0):.2f}")
        print(f"   Theta: {portfolio_greeks.get('theta', 0):.2f}")
        
        # Check options cycle
        options_cycle = state.get('options_cycle', {})
        underlyings = options_cycle.get('underlyings', [])
        print(f"\n🔄 Options Cycle:")
        print(f"   Configured Underlyings: {len(options_cycle.get('underlyings_configured', []))}")
        print(f"   Processed Underlyings: {len(underlyings)}")
        
        if underlyings:
            status_counts = {}
            for underlying in underlyings:
                status = underlying.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print(f"   Status Distribution:")
            for status, count in status_counts.items():
                print(f"     {status}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading options dashboard state: {e}")
        return False

def test_dashboard_import():
    """Test that dashboard module can be imported"""
    
    try:
        from dashboard.volatility_dashboard import load_latest_state
        print("✅ Dashboard module imported successfully")
        
        # Test loading state
        state = load_latest_state()
        if state:
            print("✅ Dashboard can load state data")
            print(f"   State timestamp: {state.get('timestamp', 'N/A')}")
            return True
        else:
            print("⚠️  Dashboard loaded but no state data available")
            return False
            
    except Exception as e:
        print(f"❌ Error importing dashboard: {e}")
        return False

def main():
    """Run all tests"""
    
    print("🧪 Testing Dashboard Integration with Options System")
    print("=" * 60)
    
    # Test 1: Data loading
    print("\n1. Testing options data loading...")
    data_test = test_dashboard_data_loading()
    
    # Test 2: Dashboard import
    print("\n2. Testing dashboard import...")
    import_test = test_dashboard_import()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"   Data Loading: {'✅ PASS' if data_test else '❌ FAIL'}")
    print(f"   Dashboard Import: {'✅ PASS' if import_test else '❌ FAIL'}")
    
    if data_test and import_test:
        print("\n🎉 All tests passed! Dashboard integration is working.")
        print("\n💡 To run the dashboard:")
        print("   streamlit run src/dashboard/app.py")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return data_test and import_test

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
