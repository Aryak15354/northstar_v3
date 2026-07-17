#!/usr/bin/env python3
"""
Resume Trading Script

Resumes trading after emergency halt.
"""

import sys
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.execution.trading_halt import HALT_FLAG_PATH


def resume_trading():
    """Resume trading after halt"""
    print("=" * 60)
    print("Resume Trading")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    halt_file = HALT_FLAG_PATH

    if not halt_file.exists():
        print("❌ No halt flag found. Trading is not halted.")
        return False

    # Remove halt flag
    halt_file.unlink()

    print("\n✅ Trading resumed")
    print("System will accept new trading activity.")

    # Log to file
    log_file = PROJECT_ROOT / "logs" / "emergency.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a') as f:
        f.write(f"{datetime.now()} - TRADING RESUMED\n")

    return True


def main():
    success = resume_trading()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
