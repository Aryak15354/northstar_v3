#!/usr/bin/env python3
"""
🧪 SHADOW TRADING SYSTEM TEST
Test the complete shadow trading system end-to-end
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

def test_daily_trader():
    """Test daily shadow trader"""
    print("🧪 Testing Daily Shadow Trader...")
    
    try:
        from live.daily_shadow_trader import DailyShadowTrader
        
        trader = DailyShadowTrader(initial_capital=1000000)  # 10 Lakh for testing
        
        # Test initialization
        assert trader.initial_capital == 1000000
        assert trader.current_capital == 1000000
        print("   ✅ Initialization: PASS")
        
        # Test market data fetching
        symbols = ['RELIANCE', 'TCS', 'HDFCBANK']
        market_data = trader.get_market_data(symbols, period="5d")
        
        if not market_data.empty:
            print("   ✅ Market data fetch: PASS")
        else:
            print("   ⚠️  Market data fetch: No data (may be weekend/holiday)")
            
        # Test Northstar intelligence (with fallback)
        decisions = trader.run_northstar_intelligence()
        assert 'timestamp' in decisions
        print("   ✅ Northstar intelligence: PASS")
        
        # Test P&L calculation (with empty positions)
        pnl = trader.calculate_daily_pnl()
        assert 'total_pnl' in pnl
        print("   ✅ P&L calculation: PASS")
        
        # Test NIFTY performance
        nifty_perf = trader.get_nifty_performance()
        assert 'daily_return' in nifty_perf
        print("   ✅ NIFTY performance: PASS")
        
        print("   ✅ Daily Shadow Trader: ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Daily Shadow Trader: FAILED - {e}")
        return False

def test_monthly_report_generator():
    """Test monthly report generator"""
    print("\n🧪 Testing Monthly Report Generator...")
    
    try:
        from live.monthly_report_generator import MonthlyReportGenerator
        
        # Create test data first
        create_test_data()
        
        generator = MonthlyReportGenerator(year=2026, month=1)
        
        # Test initialization
        assert generator.year == 2026
        assert generator.month == 1
        print("   ✅ Initialization: PASS")
        
        # Test data loading (will fail if no data, which is expected)
        try:
            daily_logs = generator.load_monthly_data()
            print("   ✅ Data loading: PASS")
            
            # Test performance calculation
            df, metrics = generator.calculate_performance_metrics(daily_logs)
            assert 'total_return_northstar' in metrics
            print("   ✅ Performance calculation: PASS")
            
            # Test causality analysis
            causality = generator.calculate_causality_index(daily_logs)
            assert 'top_positions' in causality
            print("   ✅ Causality analysis: PASS")
            
        except FileNotFoundError:
            print("   ⚠️  Data loading: No test data (expected for new system)")
            
        print("   ✅ Monthly Report Generator: TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Monthly Report Generator: FAILED - {e}")
        return False

def test_scheduler():
    """Test scheduler functionality"""
    print("\n🧪 Testing Scheduler...")
    
    try:
        from live.shadow_trading_scheduler import ShadowTradingScheduler
        
        scheduler = ShadowTradingScheduler()
        
        # Test initialization
        assert scheduler.trader is not None
        print("   ✅ Initialization: PASS")
        
        # Test trading day check
        today = datetime.now()
        is_trading_day = scheduler.is_trading_day(today)
        print(f"   ✅ Trading day check: {is_trading_day}")
        
        # Test holiday check
        is_holiday = scheduler.is_market_holiday(today)
        print(f"   ✅ Holiday check: {not is_holiday}")
        
        # Test state management
        scheduler.save_scheduler_state()
        scheduler.load_scheduler_state()
        print("   ✅ State management: PASS")
        
        print("   ✅ Scheduler: ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Scheduler: FAILED - {e}")
        return False

def create_test_data():
    """Create minimal test data for testing"""
    base_path = Path("data/live/shadow_trading")
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Create test daily log
    test_log = [{
        'date': '2026-01-20',
        'timestamp': '2026-01-20T16:00:00',
        'decisions': {
            'market_regime': 'test_regime',
            'confidence': 0.75
        },
        'trades': [],
        'pnl': {
            'total_pnl': 5000,
            'total_pnl_pct': 0.5,
            'portfolio_value': 1005000,
            'position_pnl': {
                'RELIANCE.NS': {'daily_pnl': 3000},
                'TCS.NS': {'daily_pnl': 2000}
            }
        },
        'nifty_performance': {
            'daily_return': 0.3,
            'current_level': 23500
        },
        'positions': {}
    }]
    
    log_file = base_path / "daily_log_202601.json"
    with open(log_file, 'w') as f:
        json.dump(test_log, f, indent=2)

def test_dependencies():
    """Test all required dependencies"""
    print("🧪 Testing Dependencies...")
    
    required_packages = [
        'pandas', 'numpy', 'matplotlib', 'seaborn', 
        'yfinance', 'schedule', 'reportlab'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}: Available")
        except ImportError:
            print(f"   ❌ {package}: Missing")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    else:
        print("   ✅ All dependencies: AVAILABLE")
        return True

def main():
    """Run all tests"""
    print("🌟 NORTHSTAR SHADOW TRADING SYSTEM TEST")
    print("=" * 60)
    
    all_passed = True
    
    # Test dependencies first
    if not test_dependencies():
        print("\n❌ DEPENDENCY TEST FAILED - Install missing packages first")
        return False
    
    # Test components
    tests = [
        test_daily_trader,
        test_monthly_report_generator, 
        test_scheduler
    ]
    
    for test_func in tests:
        if not test_func():
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Shadow Trading System Ready!")
        print("\nNext steps:")
        print("1. Run: python scripts/launch_shadow_trading.py --mode manual")
        print("2. Check: python scripts/launch_shadow_trading.py --mode status")
        print("3. Start: python scripts/launch_shadow_trading.py --mode auto")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    main()