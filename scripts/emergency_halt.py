#!/usr/bin/env python3
"""
Emergency Halt Script

Immediately halts all trading activity.
"""

import sys
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.execution.trading_halt import HALT_FLAG_PATH


def emergency_halt():
    """Emergency halt - stop all trading"""
    print("=" * 60)
    print("⚠️  EMERGENCY HALT ⚠️")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    # Create halt flag file at the single canonical location that the runtime
    # execution gate (src/execution/trading_halt.py) and preopen checks read.
    halt_file = str(HALT_FLAG_PATH)
    with open(halt_file, 'w') as f:
        f.write(f"Trading halted at {datetime.now()}\n")
        f.write("Reason: Manual emergency halt\n")
    
    print("\n✅ Trading halted")
    print(f"Halt flag created: {halt_file}")
    print("\nAll new trading activity will be blocked.")
    print("Existing orders remain active.")
    print("\nTo resume trading, run: python scripts/resume_trading.py")
    
    # Log to file
    log_file = PROJECT_ROOT / "logs" / "emergency.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a') as f:
        f.write(f"{datetime.now()} - EMERGENCY HALT\n")
    
    return True


def main():
    success = emergency_halt()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
