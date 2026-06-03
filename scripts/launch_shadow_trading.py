#!/usr/bin/env python3
"""
🚀 NORTHSTAR SHADOW TRADING LAUNCHER
Easy launcher for the shadow trading system

Usage:
    # Start automated daily trading (runs continuously)
    python scripts/launch_shadow_trading.py --mode auto
    
    # Run trading once manually
    python scripts/launch_shadow_trading.py --mode manual
    
    # Generate monthly report
    python scripts/launch_shadow_trading.py --mode report --month 1 --year 2026
    
    # Check system status
    python scripts/launch_shadow_trading.py --mode status
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = [
        'pandas', 'numpy', 'matplotlib', 'seaborn', 
        'yfinance', 'schedule', 'reportlab'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Missing required packages:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nInstall with: pip install " + " ".join(missing))
        return False
    
    return True

def setup_directories():
    """Setup required directories"""
    base_path = Path("data/live/shadow_trading")
    
    directories = [
        base_path,
        base_path / "positions",
        base_path / "pnl", 
        base_path / "decisions",
        base_path / "reports",
        base_path / "logs"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        
    print("✅ Directories setup complete")

def run_auto_mode():
    """Run automated shadow trading scheduler"""
    print("🌟 Starting Northstar Shadow Trading Scheduler...")
    print("This will run continuously and execute trades daily at 4 PM")
    print("Press Ctrl+C to stop\n")
    
    from live.shadow_trading_scheduler import ShadowTradingScheduler
    
    scheduler = ShadowTradingScheduler()
    scheduler.run_scheduler()

def run_manual_mode():
    """Run manual shadow trading once"""
    print("🔧 Running manual shadow trading...")
    
    from live.daily_shadow_trader import DailyShadowTrader
    
    trader = DailyShadowTrader()
    # Force trading even on weekends for testing
    result = trader.run_daily_shadow_trading(force_trading=True)
    
    if result and result.get('success'):
        if result.get('skipped'):
            print(f"⚠️  Trading skipped: {result.get('reason')}")
        else:
            print("✅ Manual trading completed successfully")
    else:
        print(f"❌ Manual trading failed: {result.get('error') if result else 'Unknown error'}")
        
    return result

def run_report_mode(year, month):
    """Generate monthly report"""
    print(f"📊 Generating monthly report for {year}-{month:02d}...")
    
    from live.monthly_report_generator import MonthlyReportGenerator
    
    generator = MonthlyReportGenerator(year=year, month=month)
    result = generator.generate_monthly_report()
    
    if result.get('success'):
        print(f"✅ Report generated: {result['pdf_path']}")
    else:
        print(f"❌ Report generation failed: {result.get('error')}")
        
    return result

def check_status():
    """Check system status"""
    print("🔍 Checking Northstar Shadow Trading System Status...")
    print("=" * 60)
    
    # Check directories
    base_path = Path("data/live/shadow_trading")
    
    if base_path.exists():
        print("✅ Base directory exists")
        
        # Check subdirectories
        subdirs = ['positions', 'pnl', 'decisions', 'reports', 'logs']
        for subdir in subdirs:
            path = base_path / subdir
            if path.exists():
                file_count = len(list(path.glob('*')))
                print(f"✅ {subdir}: {file_count} files")
            else:
                print(f"❌ {subdir}: Missing")
    else:
        print("❌ Base directory missing")
        
    # Check state files
    state_file = base_path / "trading_state.json"
    if state_file.exists():
        print("✅ Trading state file exists")
        
        import json
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            print(f"   Last trading day: {state.get('last_trading_day', 'Never')}")
            print(f"   Current capital: ₹{state.get('current_capital', 0):,.0f}")
            print(f"   Active positions: {len(state.get('positions', {}))}")
            
        except Exception as e:
            print(f"❌ Error reading state file: {e}")
    else:
        print("⚠️  No trading state file (system not started yet)")
        
    # Check recent activity
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Check if traded today
    positions_file = base_path / "positions" / f"positions_{today}.json"
    if positions_file.exists():
        print(f"✅ Traded today ({today})")
    else:
        print(f"⚠️  No trading activity today ({today})")
        
    # Check monthly reports
    reports_dir = base_path / "reports"
    if reports_dir.exists():
        pdf_files = list(reports_dir.glob('*.pdf'))
        print(f"📊 Monthly reports generated: {len(pdf_files)}")
        
        if pdf_files:
            latest_report = max(pdf_files, key=lambda x: x.stat().st_mtime)
            print(f"   Latest report: {latest_report.name}")
    
    print("=" * 60)

def main():
    """Main launcher"""
    parser = argparse.ArgumentParser(description='Northstar Shadow Trading Launcher')
    parser.add_argument('--mode', choices=['auto', 'manual', 'report', 'status'], 
                       default='status', help='Operation mode')
    parser.add_argument('--year', type=int, help='Year for report generation')
    parser.add_argument('--month', type=int, help='Month for report generation')
    
    args = parser.parse_args()
    
    print("🌟 NORTHSTAR SHADOW TRADING SYSTEM")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return
        
    # Setup directories
    setup_directories()
    
    # Run based on mode
    if args.mode == 'auto':
        run_auto_mode()
        
    elif args.mode == 'manual':
        run_manual_mode()
        
    elif args.mode == 'report':
        year = args.year or datetime.now().year
        month = args.month or datetime.now().month
        run_report_mode(year, month)
        
    elif args.mode == 'status':
        check_status()

if __name__ == "__main__":
    main()