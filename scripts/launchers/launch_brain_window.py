#!/usr/bin/env python3
"""
🧠 NORTHSTAR V3 DASHBOARD LAUNCHER
Launch the official Northstar V3 Dashboard

This launches the official comprehensive dashboard with real-time
system monitoring and institutional-grade analytics.
"""

import subprocess
import sys
import os
import time
from datetime import datetime

def launch_v3_dashboard():
    """Launch the official V3 dashboard"""
    
    print("🎯 NORTHSTAR V3 DASHBOARD")
    print("=" * 40)
    print("   Official V3 Interface")
    print("   Comprehensive Analytics")
    print(f"   Launched: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if system data is available
    data_files = [
        "data/processed/market_state.parquet",
        "data/processed/strategy_beliefs.parquet",
        "data/processed/portfolio_weights.parquet"
    ]
    
    missing_files = [f for f in data_files if not os.path.exists(f)]
    
    if missing_files:
        print("⚠️  WARNING: Some system data files are missing:")
        for file in missing_files:
            print(f"   - {file}")
        print()
        print("🔄 Run data update first:")
        print("   python run.py --mode update")
        print("   or")
        print("   python run_complete_v3_system.py --quick")
        print()
        
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("🛑 Launch cancelled")
            return False
    
    # Launch V3 Dashboard
    print("🚀 Launching Northstar V3 Dashboard...")
    print("   This will open in your browser at http://localhost:8512")
    print("   Press Ctrl+C to stop the dashboard")
    print()
    
    try:
        # Use the main dashboard launcher
        cmd = [sys.executable, "launch_dashboard.py"]
        
        print(f"   Command: {' '.join(cmd)}")
        print("   Starting dashboard server...")
        print()
        
        # Launch the dashboard
        process = subprocess.run(cmd)
        
        return process.returncode == 0
        
    except KeyboardInterrupt:
        print(f"\n🛑 Dashboard stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error launching dashboard: {e}")
        return False

def main():
    """Main function"""
    
    success = launch_v3_dashboard()
    
    if success:
        print("\n✅ Dashboard session completed")
    else:
        print("\n❌ Dashboard launch failed")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())