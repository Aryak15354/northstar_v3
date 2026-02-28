#!/usr/bin/env python3
"""
🚀 LAUNCH INTEGRATED NORTHSTAR V3
Master launcher for the complete hedge fund operating system

This launcher runs the complete integrated system:
1. System orchestration (strategies, backtests, capital allocation)
2. Portfolio construction with strategy blending
3. Dashboard launch with full intelligence

Usage:
    python launch_integrated_northstar.py                    # Full system
    python launch_integrated_northstar.py --quick           # Skip orchestration
    python launch_integrated_northstar.py --dashboard-only  # Dashboard only
"""

import sys
import os
import argparse
import subprocess
from datetime import datetime

def print_banner():
    """Print integrated system banner"""
    print("🚀 NORTHSTAR V3 - INTEGRATED HEDGE FUND OPERATING SYSTEM")
    print("=" * 70)
    print("Complete institutional-grade investment intelligence with strategy blending")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def run_system_orchestration():
    """Run complete system orchestration"""
    print("🧬 RUNNING COMPLETE SYSTEM ORCHESTRATION")
    print("=" * 50)
    
    try:
        from src.orchestrator.system_orchestrator import SystemOrchestrator
        
        orchestrator = SystemOrchestrator()
        success = orchestrator.run_complete_system()
        
        if success:
            print("✅ System orchestration completed successfully")
            return True
        else:
            print("⚠️ System orchestration partially successful")
            return False
            
    except Exception as e:
        print(f"❌ System orchestration error: {e}")
        return False

def run_data_update():
    """Run basic data update"""
    print("📊 RUNNING DATA UPDATE")
    print("=" * 30)
    
    try:
        result = subprocess.run([sys.executable, 'update_all_systems.py'], 
                              capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            print("✅ Data update completed")
            return True
        else:
            print("⚠️ Data update had issues")
            print(result.stdout[-500:] if result.stdout else "")
            return False
    except Exception as e:
        print(f"❌ Data update error: {e}")
        return False

def launch_dashboard(dashboard_type='trading_desk'):
    """Launch the specified dashboard"""
    
    dashboard_files = {
        'trading_desk': 'northstar_trading_desk.py',
        'professional': 'northstar_professional.py',
        'intelligence': 'northstar_intelligence_organism.py'
    }
    
    dashboard_file = dashboard_files.get(dashboard_type, 'northstar_trading_desk.py')
    
    print(f"🚀 LAUNCHING {dashboard_type.upper().replace('_', ' ')} DASHBOARD")
    print("=" * 50)
    print("Dashboard will open in your browser...")
    print("Press Ctrl+C to stop the dashboard")
    print()
    
    try:
        subprocess.run([sys.executable, '-m', 'streamlit', 'run', dashboard_file])
    except KeyboardInterrupt:
        print("\n👋 Dashboard closed")
    except Exception as e:
        print(f"❌ Dashboard error: {e}")

def validate_system():
    """Quick system validation"""
    print("🔍 VALIDATING SYSTEM COMPONENTS")
    print("=" * 40)
    
    # Check key files
    key_files = [
        ('data/processed/scores.parquet', 'Stock scores'),
        ('data/processed/market_state.parquet', 'Market state'),
        ('data/processed/portfolio_weights.parquet', 'Portfolio weights'),
        ('data/processed/strategy_portfolios', 'Strategy portfolios'),
        ('data/processed/backtests', 'Backtest results'),
        ('data/processed/capital_allocations.json', 'Capital allocations'),
    ]
    
    valid_components = 0
    
    for filepath, description in key_files:
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                file_count = len([f for f in os.listdir(filepath) if f.endswith('.parquet')])
                if file_count > 0:
                    print(f"   ✅ {description}: {file_count} files")
                    valid_components += 1
                else:
                    print(f"   ❌ {description}: empty directory")
            else:
                print(f"   ✅ {description}: available")
                valid_components += 1
        else:
            print(f"   ❌ {description}: missing")
    
    system_health = valid_components / len(key_files)
    
    if system_health >= 0.8:
        print(f"\n✅ System Health: {system_health:.1%} - Ready for operation")
        return True
    else:
        print(f"\n⚠️ System Health: {system_health:.1%} - Some components missing")
        return False

def main():
    """Main launcher"""
    
    parser = argparse.ArgumentParser(description='Launch Integrated Northstar V3')
    parser.add_argument('--quick', action='store_true', 
                       help='Skip system orchestration, run data update only')
    parser.add_argument('--dashboard-only', action='store_true',
                       help='Launch dashboard without any updates')
    parser.add_argument('--dashboard', choices=['trading_desk', 'professional', 'intelligence'],
                       default='trading_desk', help='Choose dashboard type')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate system, do not launch')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Validate system first
    system_valid = validate_system()
    
    if args.validate_only:
        return system_valid
    
    if args.dashboard_only:
        print("🚀 Launching dashboard without updates...")
        launch_dashboard(args.dashboard)
        return True
    
    # Run updates based on mode
    if args.quick:
        print("⚡ Quick mode: Running data update only...")
        update_success = run_data_update()
    else:
        print("🧬 Full mode: Running complete system orchestration...")
        update_success = run_system_orchestration()
        
        # Fallback to data update if orchestration fails
        if not update_success:
            print("\n🔄 Falling back to data update...")
            update_success = run_data_update()
    
    # Launch dashboard regardless of update success
    print(f"\n🚀 Launching {args.dashboard.replace('_', ' ').title()} Dashboard...")
    print("=" * 50)
    
    if update_success:
        print("✅ System fully updated - launching with complete intelligence")
    else:
        print("⚠️ System partially updated - launching with available data")
    
    print()
    launch_dashboard(args.dashboard)
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Launcher interrupted")
    except Exception as e:
        print(f"\n❌ Launcher error: {e}")
        sys.exit(1)