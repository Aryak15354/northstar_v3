#!/usr/bin/env python3
"""
🚀 LAUNCH NORTHSTAR UNIFIED TERMINAL
Master launcher for the ultimate hedge fund command center

This launcher:
1. Builds the initial snapshot
2. Starts the snapshot scheduler (optional)
3. Launches the unified terminal

Usage:
    python launch_unified_terminal.py                    # Full system with scheduler
    python launch_unified_terminal.py --no-scheduler    # Terminal only
    python launch_unified_terminal.py --build-only      # Build snapshot and exit
"""

import sys
import os
import argparse
import subprocess
import threading
import time
from datetime import datetime

def print_banner():
    """Print the unified terminal banner"""
    print("🧭 NORTHSTAR UNIFIED TERMINAL LAUNCHER")
    print("=" * 60)
    print("The Ultimate Hedge Fund Command Center")
    print("War Room + Portfolio Command + Intelligence Organism")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def build_initial_snapshot():
    """Build the initial snapshot"""
    print("🧠 BUILDING INITIAL SNAPSHOT")
    print("-" * 40)
    
    try:
        # Add src to path
        
        from intelligence.build_dashboard_snapshot import build_unified_snapshot
        
        snapshot = build_unified_snapshot()
        
        if snapshot:
            health_grade = snapshot.get('health', {}).get('grade', 'Unknown')
            print(f"✅ Initial snapshot built successfully - Health: {health_grade}")
            return True
        else:
            print("❌ Initial snapshot build failed")
            return False
            
    except Exception as e:
        print(f"❌ Initial snapshot error: {e}")
        return False

def start_snapshot_scheduler():
    """Start the snapshot scheduler in background"""
    print("⏰ STARTING SNAPSHOT SCHEDULER")
    print("-" * 40)
    
    try:
        # Start scheduler as subprocess
        scheduler_process = subprocess.Popen([
            sys.executable, 
            'src/automation/snapshot_scheduler.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("✅ Snapshot scheduler started in background")
        print("   Building fresh snapshots every 5 minutes...")
        
        return scheduler_process
        
    except Exception as e:
        print(f"❌ Scheduler start error: {e}")
        return None

def launch_terminal():
    """Launch the unified terminal"""
    print("🧭 LAUNCHING UNIFIED TERMINAL")
    print("-" * 40)
    
    try:
        # Launch Streamlit app
        cmd = [
            sys.executable, 
            '-m', 'streamlit', 
            'run', 
            'northstar_unified_terminal.py',
            '--server.port=8501',
            '--server.address=localhost',
            '--browser.gatherUsageStats=false'
        ]
        
        print("🚀 Starting Streamlit server...")
        print("   URL: http://localhost:8501")
        print("   Press Ctrl+C to stop")
        print()
        
        # Run Streamlit
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n🛑 Terminal stopped by user")
    except Exception as e:
        print(f"❌ Terminal launch error: {e}")

def check_dependencies():
    """Check if required dependencies are available"""
    print("🔍 CHECKING DEPENDENCIES")
    print("-" * 40)
    
    required_packages = ['streamlit', 'pandas', 'plotly', 'numpy']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All dependencies available")
    return True

def check_data_structure():
    """Check if data directories exist"""
    print("📁 CHECKING DATA STRUCTURE")
    print("-" * 40)
    
    required_dirs = [
        'data/processed',
        'data/portfolio',
        'data/intelligence',
        'data/macro/factors',
        'src/dashboard',
        'src/intelligence',
        'src/automation'
    ]
    
    missing_dirs = []
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ⚠️ {dir_path} - CREATING")
            os.makedirs(dir_path, exist_ok=True)
    
    print("✅ Data structure ready")
    return True

def main():
    """Main launcher function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Northstar Unified Terminal Launcher')
    parser.add_argument('--no-scheduler', action='store_true', help='Launch terminal without scheduler')
    parser.add_argument('--build-only', action='store_true', help='Build snapshot and exit')
    parser.add_argument('--check-only', action='store_true', help='Check dependencies and exit')
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check data structure
    if not check_data_structure():
        sys.exit(1)
    
    if args.check_only:
        print("✅ All checks passed - system ready")
        sys.exit(0)
    
    # Build initial snapshot
    if not build_initial_snapshot():
        print("⚠️ Initial snapshot failed - continuing anyway...")
    
    if args.build_only:
        print("✅ Snapshot built - exiting")
        sys.exit(0)
    
    # Start scheduler (unless disabled)
    scheduler_process = None
    if not args.no_scheduler:
        scheduler_process = start_snapshot_scheduler()
        time.sleep(2)  # Give scheduler time to start
    
    try:
        # Launch terminal
        launch_terminal()
        
    finally:
        # Clean up scheduler if running
        if scheduler_process:
            print("\n🛑 Stopping snapshot scheduler...")
            scheduler_process.terminate()
            scheduler_process.wait()
            print("✅ Scheduler stopped")

if __name__ == "__main__":
    main()