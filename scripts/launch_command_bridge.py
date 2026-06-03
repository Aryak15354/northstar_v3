#!/usr/bin/env python3
"""
🚀 LAUNCH NORTHSTAR COMMAND BRIDGE
Bloomberg-Grade Trading Floor Interface

This launches the ultimate command bridge for the living capital organism.
"""

import subprocess
import sys
import os
from pathlib import Path

def launch_command_bridge():
    """Launch the Northstar Command Bridge"""
    
    print("🧭 LAUNCHING NORTHSTAR COMMAND BRIDGE")
    print("=" * 60)
    print("Bloomberg-Grade Trading Floor Interface")
    print()
    
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dashboard_path = project_root / "src" / "dashboard" / "northstar_command_bridge.py"
    
    if not dashboard_path.exists():
        print(f"❌ Command bridge not found at: {dashboard_path}")
        return False
    
    print(f"📍 Dashboard location: {dashboard_path}")
    print()
    print("🎯 COMMAND BRIDGE FEATURES:")
    print("   • Market Reality Bar - Bloomberg headline style")
    print("   • Brain + Belief Panel - Cognitive layer with explainable AI")
    print("   • Portfolio & Capital Panel - Where investors stare")
    print("   • Risk Spine - Visually intimidating risk management")
    print("   • Execution & Memory - Institutional audit trail")
    print()
    print("🚀 Starting Streamlit server...")
    print("   URL will be: http://localhost:8501")
    print("   Press Ctrl+C to stop")
    print()
    
    try:
        # Launch streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port=8501",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false",
            "--server.headless=false"
        ]
        
        # Change to project root directory
        os.chdir(project_root)
        
        # Run the command
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching command bridge: {e}")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Command bridge stopped by user")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main execution"""
    
    success = launch_command_bridge()
    
    if success:
        print("\n✅ Command bridge session completed successfully")
    else:
        print("\n❌ Command bridge failed to launch")
        print("\nTroubleshooting:")
        print("1. Ensure Streamlit is installed: pip install streamlit")
        print("2. Check that all required files exist")
        print("3. Verify Python path and dependencies")

if __name__ == "__main__":
    main()