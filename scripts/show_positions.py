#!/usr/bin/env python3
"""
Show Positions Script

Displays current portfolio positions.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pathlib import Path
import json
from datetime import datetime
from tabulate import tabulate


def load_latest_state():
    """Load latest state snapshot"""
    snapshot_dir = Path("snapshots")
    if not snapshot_dir.exists():
        return None
    
    snapshots = list(snapshot_dir.glob("*.json"))
    if not snapshots:
        return None
    
    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    
    with open(latest, 'r') as f:
        return json.load(f)


def show_positions():
    """Display positions"""
    print("=" * 80)
    print("Portfolio Positions")
    print(f"Time: {datetime.now()}")
    print("=" * 80)
    
    state = load_latest_state()
    if not state:
        print("❌ No state snapshot found")
        return
    
    positions = state.get('positions', [])
    
    if not positions:
        print("No positions")
        return
    
    # Format positions for display
    table_data = []
    for pos in positions:
        table_data.append([
            pos.get('underlying', 'N/A'),
            pos.get('option_type', 'N/A'),
            pos.get('strike', 'N/A'),
            pos.get('expiry', 'N/A'),
            pos.get('quantity', 0),
            f"${pos.get('spot', 0):.2f}",
            f"{pos.get('iv', 0):.2%}"
        ])
    
    headers = ['Underlying', 'Type', 'Strike', 'Expiry', 'Qty', 'Spot', 'IV']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    print(f"\nTotal Positions: {len(positions)}")


def main():
    try:
        show_positions()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
