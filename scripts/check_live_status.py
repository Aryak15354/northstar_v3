#!/usr/bin/env python3
"""
Check Live System Status

Quick status check for the live engine and dashboard.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import subprocess

def check_engine_status():
    """Check if engine is running"""
    pid_file = Path("engine.pid")
    
    if not pid_file.exists():
        return False, None, "Not running (no PID file)"
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        try:
            os.kill(pid, 0)
            return True, pid, "Running"
        except ProcessLookupError:
            return False, pid, "Stale PID (process not found)"
    except Exception as e:
        return False, None, f"Error: {e}"


def check_latest_snapshot():
    """Check latest state snapshot"""
    snapshot_file = Path("snapshots/current_state.json")
    
    if not snapshot_file.exists():
        return None, "No snapshot found"
    
    try:
        with open(snapshot_file, 'r') as f:
            state = json.load(f)
        
        timestamp = datetime.fromisoformat(state['timestamp'])
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo is not None else datetime.now()
        age_seconds = (now - timestamp).total_seconds()
        
        return state, f"{age_seconds:.0f} seconds old"
    except Exception as e:
        return None, f"Error reading: {e}"


def check_dashboard():
    """Check if dashboard is running"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'streamlit.*volatility_dashboard'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return True, pids[0] if pids else None
        else:
            return False, None
    except Exception as e:
        return False, None


def main():
    print("=" * 60)
    print("LIVE SYSTEM STATUS CHECK")
    print("=" * 60)
    print()
    
    # Check engine
    print("🔧 ENGINE STATUS")
    print("-" * 60)
    running, pid, status = check_engine_status()
    
    if running:
        print(f"✅ Status: {status}")
        print(f"   PID: {pid}")
    else:
        print(f"❌ Status: {status}")
        if pid:
            print(f"   Last PID: {pid}")
    print()
    
    # Check latest snapshot
    print("📊 LATEST DATA")
    print("-" * 60)
    state, info = check_latest_snapshot()
    
    if state:
        print(f"✅ Snapshot: {info}")
        print(f"   Cycle: {state.get('cycle', 'N/A')}")
        print(f"   Regime: {state.get('regime', 'N/A')}")
        
        market_data = state.get('market_data', {})
        print(f"   NIFTY: ₹{market_data.get('NIFTY_price', 0):,.2f}")
        print(f"   BANKNIFTY: ₹{market_data.get('BANKNIFTY_price', 0):,.2f}")
        print(f"   Option Contracts: {market_data.get('option_contracts', 0)}")
        
        greeks = state.get('portfolio_greeks', {})
        print(f"   Greeks: Δ={greeks.get('delta', 0):.2f}, "
              f"Γ={greeks.get('gamma', 0):.3f}, "
              f"ν={greeks.get('vega', 0):.2f}")
    else:
        print(f"❌ Snapshot: {info}")
    print()
    
    # Check dashboard
    print("📈 DASHBOARD STATUS")
    print("-" * 60)
    dash_running, dash_pid = check_dashboard()
    
    if dash_running:
        print(f"✅ Status: Running")
        print(f"   PID: {dash_pid}")
        print(f"   URL: http://localhost:8501")
    else:
        print(f"❌ Status: Not running")
    print()
    
    # Check logs
    print("📝 LOG FILES")
    print("-" * 60)
    
    log_files = [
        ("Engine Log", "logs/live_engine.log"),
        ("Console Log", "logs/engine_console.log"),
        ("Alerts Log", "logs/alerts.log")
    ]
    
    for name, path in log_files:
        log_path = Path(path)
        if log_path.exists():
            size = log_path.stat().st_size
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            age = (datetime.now() - mtime).total_seconds()
            print(f"✅ {name}: {size:,} bytes (updated {age:.0f}s ago)")
        else:
            print(f"❌ {name}: Not found")
    print()
    
    # Check snapshots
    print("💾 SNAPSHOTS")
    print("-" * 60)
    
    snapshot_dir = Path("snapshots")
    if snapshot_dir.exists():
        snapshots = list(snapshot_dir.glob("*.json"))
        print(f"✅ Total snapshots: {len(snapshots)}")
        
        if snapshots:
            latest = max(snapshots, key=lambda p: p.stat().st_mtime)
            oldest = min(snapshots, key=lambda p: p.stat().st_mtime)
            
            latest_time = datetime.fromtimestamp(latest.stat().st_mtime)
            oldest_time = datetime.fromtimestamp(oldest.stat().st_mtime)
            
            print(f"   Latest: {latest.name}")
            print(f"   Oldest: {oldest.name}")
            print(f"   Time span: {(latest_time - oldest_time).total_seconds() / 3600:.1f} hours")
    else:
        print(f"❌ Snapshot directory not found")
    print()
    
    # Overall status
    print("=" * 60)
    print("OVERALL STATUS")
    print("=" * 60)
    
    if running and state and dash_running:
        print("✅ System is FULLY OPERATIONAL")
        print("   - Engine fetching live data")
        print("   - Dashboard displaying real-time updates")
        print("   - All components working")
    elif running and state:
        print("⚠️  System is PARTIALLY OPERATIONAL")
        print("   - Engine running")
        print("   - Dashboard not running (start with: streamlit run dashboard/volatility_dashboard.py)")
    elif running:
        print("⚠️  System is STARTING")
        print("   - Engine running but no data yet")
        print("   - Wait a moment for first cycle to complete")
    else:
        print("❌ System is NOT RUNNING")
        print("   - Start with: ./START_LIVE_SYSTEM.sh")
    
    print("=" * 60)
    print()
    
    # Return exit code
    return 0 if (running and state) else 1


if __name__ == "__main__":
    sys.exit(main())
