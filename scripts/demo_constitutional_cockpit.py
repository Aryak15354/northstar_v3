#!/usr/bin/env python3
"""
🏛️ DEMO CONSTITUTIONAL COCKPIT
Quick demo launch without interactive prompts

This script demonstrates the constitutional cockpit with real V3 data.
"""

import os
import sys
import subprocess
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def main():
    """Demo launch of constitutional cockpit"""
    
    print("🏛️ NORTHSTAR V3 CONSTITUTIONAL COCKPIT - DEMO")
    print("=" * 60)
    print("Launching constitutional cockpit with sample data...")
    print("=" * 60)
    print()
    
    # Ensure sample data exists
    print("📊 Checking sample data...")
    
    # Run test to create sample data if needed
    test_script = os.path.join(project_root, 'scripts', 'test_constitutional_cockpit.py')
    try:
        result = subprocess.run([sys.executable, test_script], 
                              capture_output=True, text=True, cwd=project_root)
        if result.returncode != 0:
            print("❌ Failed to create sample data")
            print(result.stdout)
            print(result.stderr)
            return 1
        print("✅ Sample data ready")
    except Exception as e:
        print(f"❌ Error preparing sample data: {e}")
        return 1
    
    print()
    
    # Launch constitutional cockpit
    print("🚀 Launching Constitutional Cockpit...")
    
    cockpit_path = os.path.join(project_root, 'src', 'dashboard', 'constitutional_cockpit.py')
    
    try:
        cmd = [
            sys.executable, '-m', 'streamlit', 'run', cockpit_path,
            '--server.port', '8501',
            '--server.address', 'localhost',
            '--server.headless', 'false',
            '--browser.gatherUsageStats', 'false',
            '--theme.base', 'light',
            '--theme.primaryColor', '#1e40af',
            '--theme.backgroundColor', '#ffffff',
            '--theme.secondaryBackgroundColor', '#f8fafc'
        ]
        
        print(f"📊 Constitutional Cockpit available at: http://localhost:8501")
        print()
        print("🏛️ CONSTITUTIONAL COCKPIT FEATURES:")
        print("   Panel 1 — SYSTEM STATE: System health and behavior")
        print("   Panel 2 — RISK AUTHORITY: Who is in charge right now")
        print("   Panel 3 — ENGINE BEHAVIOR: Engine behavior, not performance")
        print("   Panel 4 — VALIDATION & TRUTH: System honesty checks")
        print("   Panel 5 — INTELLIGENCE OBSERVER: Understanding, not action")
        print()
        print("🔒 CONSTITUTIONAL DESIGN:")
        print("   ✅ READ-ONLY: Zero write access")
        print("   ✅ BEHAVIOR FOCUS: Shows behavior, not performance")
        print("   ✅ EMOTION REDUCTION: Reduces emotion, increases trust")
        print("   ✅ TEMPORAL ISOLATION: All data lagged minimum 1 hour")
        print()
        print("Press Ctrl+C to stop the dashboard")
        print("=" * 60)
        
        # Run Streamlit
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n🛑 Constitutional Cockpit stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Failed to launch Constitutional Cockpit: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())