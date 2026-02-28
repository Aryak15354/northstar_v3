#!/usr/bin/env python3
"""
Shutdown Engine Script

Gracefully shuts down the Unified Volatility Engine.
"""

import sys
import os
import signal
from pathlib import Path
from datetime import datetime


def shutdown_engine():
    """Shutdown the engine"""
    print("=" * 60)
    print("Unified Volatility Engine - Shutdown")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    pid_file = "engine.pid"
    
    if not Path(pid_file).exists():
        print("❌ Engine PID file not found. Is the engine running?")
        return False
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        print(f"Sending shutdown signal to PID {pid}...")
        os.kill(pid, signal.SIGINT)
        
        # Wait for shutdown
        import time
        for i in range(10):
            if not Path(pid_file).exists():
                print("✅ Engine shut down successfully")
                return True
            time.sleep(1)
            print(".", end="", flush=True)
        
        print("\n⚠️  Engine did not shut down gracefully, forcing...")
        os.kill(pid, signal.SIGKILL)
        if Path(pid_file).exists():
            os.remove(pid_file)
        print("✅ Engine forcefully stopped")
        return True
        
    except ProcessLookupError:
        print("❌ Process not found. Cleaning up PID file...")
        if Path(pid_file).exists():
            os.remove(pid_file)
        return False
    except Exception as e:
        print(f"❌ Shutdown failed: {e}")
        return False


def main():
    success = shutdown_engine()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
