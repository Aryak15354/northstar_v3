#!/usr/bin/env python3
"""
End-of-Day Rebalancing Script

Performs end-of-day portfolio rebalancing with unified P&L accounting.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from scripts.eod_rebalance_with_pnl import eod_rebalance_with_pnl


def main():
    """Run EOD rebalancing with unified P&L system"""
    print("=" * 60)
    print("End-of-Day Rebalancing (Unified P&L)")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    # Call the unified P&L EOD processing
    success = eod_rebalance_with_pnl()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
