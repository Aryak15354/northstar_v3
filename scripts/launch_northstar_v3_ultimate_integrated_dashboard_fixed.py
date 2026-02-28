#!/usr/bin/env python3
"""
🚀 LAUNCH NORTHSTAR V3 ULTIMATE INTEGRATED DASHBOARD - FIXED VERSION
Launch the complete V3 Ultimate Dashboard with all missing methods integrated

This script launches the fully integrated dashboard that combines:
- ALL features from the Enhanced V3 Dashboard (2242 lines)
- Complete V3 Observer Architecture integration
- Fixed broken functionality and zero values
- Extensive visualization and explainability features

Features Fixed:
✅ All missing methods from enhanced dashboard integrated
✅ Portfolio tracking with stock-level performance
✅ Wave analysis with pattern detection and forecasting
✅ Dynamic clustering with temporal evolution
✅ Automation hub with scheduling and execution history
✅ Real-time monitoring with system health
✅ Comprehensive fallback methods for robustness
✅ V3 Observer integration (when available)
✅ Consistent data integration (no hardcoded values)

Access: http://localhost:8517
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Launch the fixed Northstar V3 Ultimate Integrated Dashboard"""
    
    print("🚀 Launching Northstar V3 Ultimate Integrated Dashboard - FIXED VERSION")
    print("=" * 80)
    
    # Get project root
    project_root = Path(__file__).parent.parent
    dashboard_path = project_root / "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py"
    
    # Verify dashboard exists
    if not dashboard_path.exists():
        print(f"❌ Dashboard not found at: {dashboard_path}")
        return
    
    print(f"📂 Project Root: {project_root}")
    print(f"📊 Dashboard Path: {dashboard_path}")
    print()
    
    print("🔧 Features Integrated:")
    print("  ✅ All Enhanced V3 Dashboard methods (2242 lines)")
    print("  ✅ Portfolio tracking with NIFTY benchmarks")
    print("  ✅ Wave analysis with Elliott Wave detection")
    print("  ✅ Dynamic clustering with K-Means, Hierarchical, DBSCAN")
    print("  ✅ Real-time monitoring with system health gauges")
    print("  ✅ Automation hub with scheduling and execution history")
    print("  ✅ V3 Observer Architecture integration")
    print("  ✅ Comprehensive fallback methods")
    print("  ✅ Fixed broken functionality and zero values")
    print("  ✅ Integrated state snapshot prebuild before launch")
    print()

    print("🧱 Building integrated state snapshot...")
    snapshot_cmd = [sys.executable, "-u", "scripts/build_integrated_state_snapshot.py", "--lookback-days", "1825"]
    try:
        snap_proc = subprocess.run(snapshot_cmd, cwd=project_root)
        if snap_proc.returncode != 0:
            print("⚠️ Snapshot build failed; continuing with dashboard launch.")
    except Exception as exc:
        print(f"⚠️ Snapshot build exception: {exc}. Continuing with dashboard launch.")
    
    print("🌐 Starting Streamlit server...")
    print("📍 URL: http://localhost:8517")
    print("⏹️  Press Ctrl+C to stop")
    print("=" * 80)
    
    try:
        # Launch streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run",
            str(dashboard_path),
            "--server.port=8517",
            "--server.headless=true",
            "--browser.gatherUsageStats=false"
        ]
        
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")

if __name__ == "__main__":
    main()
