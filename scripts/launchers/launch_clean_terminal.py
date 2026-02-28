#!/usr/bin/env python3
"""
🚀 LAUNCH CLEAN TERMINAL
Simple launcher for the clean, working version
"""

import subprocess
import sys
from datetime import datetime

def main():
    print("🧭 LAUNCHING NORTHSTAR CLEAN TERMINAL")
    print("=" * 50)
    print("Clean, functional hedge fund command center")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        print("🚀 Starting clean terminal...")
        print("   URL: http://localhost:8503")
        print("   Press Ctrl+C to stop")
        print()
        
        # Launch Streamlit
        cmd = [
            sys.executable, 
            '-m', 'streamlit', 
            'run', 
            'northstar_clean_terminal.py',
            '--server.port=8503',
            '--server.address=localhost',
            '--browser.gatherUsageStats=false'
        ]
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n🛑 Clean terminal stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()