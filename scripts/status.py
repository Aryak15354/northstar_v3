#!/usr/bin/env python3
"""
Status Script

Shows current status of the Unified Volatility Engine.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path
from datetime import datetime
import json


def check_engine_running():
    """Check if engine is running"""
    pid_file = "engine.pid"
    if not Path(pid_file).exists():
        return False, None
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        return True, pid
    except (ProcessLookupError, ValueError):
        return False, None


def get_latest_snapshot():
    """Get latest state snapshot"""
    snapshot_dir = Path("snapshots")
    if not snapshot_dir.exists():
        return None
    
    snapshots = list(snapshot_dir.glob("*.json"))
    if not snapshots:
        return None
    
    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    return latest


def show_status():
    """Show system status"""
    print("=" * 60)
    print("Unified Volatility Engine - Status")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    # Check if running
    running, pid = check_engine_running()
    if running:
        print(f"✅ Engine Status: RUNNING (PID: {pid})")
    else:
        print("❌ Engine Status: STOPPED")
    
    # Check latest snapshot
    latest_snapshot = get_latest_snapshot()
    if latest_snapshot:
        mtime = datetime.fromtimestamp(latest_snapshot.stat().st_mtime)
        print(f"\n📸 Latest Snapshot: {latest_snapshot.name}")
        print(f"   Time: {mtime}")
        print(f"   Size: {latest_snapshot.stat().st_size / 1024:.1f} KB")
        
        # Try to load snapshot info
        try:
            with open(latest_snapshot, 'r') as f:
                state = json.load(f)
            print(f"   Regime: {state.get('regime', 'unknown')}")
            print(f"   Positions: {len(state.get('positions', []))}")
        except:
            pass
    else:
        print("\n📸 Latest Snapshot: None")
    
    # Check logs
    log_file = Path("logs/engine.log")
    if log_file.exists():
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        size_kb = log_file.stat().st_size / 1024
        print(f"\n📝 Log File: {log_file}")
        print(f"   Last Modified: {mtime}")
        print(f"   Size: {size_kb:.1f} KB")
    else:
        print("\n📝 Log File: Not found")
    
    # Check disk space
    import shutil
    stat = shutil.disk_usage('.')
    free_gb = stat.free / (1024**3)
    total_gb = stat.total / (1024**3)
    used_pct = (stat.used / stat.total) * 100
    print(f"\n💾 Disk Space:")
    print(f"   Free: {free_gb:.1f} GB / {total_gb:.1f} GB")
    print(f"   Used: {used_pct:.1f}%")
    
    print("=" * 60)


def main():
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
