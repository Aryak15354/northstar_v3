#!/usr/bin/env python3
"""
Resume Trading Script

Resumes trading after emergency halt.
"""

import sys
import os
from datetime import datetime
from pathlib import Path


def resume_trading():
    """Resume trading after halt"""
    print("=" * 60)
    print("Resume Trading")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    halt_file = "TRADING_HALTED"
    
    if not Path(halt_file).exists():
        print("❌ No halt flag found. Trading is not halted.")
        return False
    
    # Remove halt flag
    os.remove(halt_file)
    
    print("\n✅ Trading resumed")
    print("System will accept new trading activity.")
    
    # Log to file
    log_file = Path("logs/emergency.log")
    with open(log_file, 'a') as f:
        f.write(f"{datetime.now()} - TRADING RESUMED\n")
    
    return True


def main():
    success = resume_trading()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
