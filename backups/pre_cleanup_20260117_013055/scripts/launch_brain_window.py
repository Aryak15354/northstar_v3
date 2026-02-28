#!/usr/bin/env python3
"""
🧠 BRAIN WINDOW LAUNCHER
Launch the Northstar Living System Brain Window

This launcher replaces the existing dashboard coordinators and launches
the new Brain Window that reads exclusively from unified state.
"""

import os
import sys
import subprocess
from datetime import datetime

def launch_brain_window():
    """Launch the Brain Window dashboard"""
    
    print("🧠 LAUNCHING NORTHSTAR BRAIN WINDOW")
    print("=" * 50)
    
    # Check if Brain Window exists
    brain_window_path = os.path.join(project_root, 'src', 'dashboard', 'brain_window.py')
    
    if not os.path.exists(brain_window_path):
        print(f"❌ Brain Window not found: {brain_window_path}")
        return False
    
    print(f"✅ Brain Window found: {brain_window_path}")
    
    # Launch with Streamlit
    try:
        print(f"🚀 Starting Brain Window interface...")
        print(f"🌐 Access at: http://localhost:8501")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("🧠 BRAIN WINDOW - LIVING SYSTEM INTERFACE")
        print("• Reads exclusively from Unified State")
        print("• Never computes truth independently") 
        print("• Sends intents to living system")
        print("• Bloomberg-style professional display")
        print()
        
        # Launch Streamlit
        cmd = [sys.executable, '-m', 'streamlit', 'run', brain_window_path, 
               '--server.headless', 'false', '--server.port', '8501']
        
        subprocess.run(cmd)
        
        return True
        
    except KeyboardInterrupt:
        print("\n🛑 Brain Window stopped by user")
        return True
        
    except Exception as e:
        print(f"❌ Failed to launch Brain Window: {e}")
        return False

def main():
    """Main execution"""
    
    success = launch_brain_window()
    
    if success:
        print("✅ Brain Window session completed")
    else:
        print("❌ Brain Window launch failed")
    
    return success

if __name__ == "__main__":
    main()