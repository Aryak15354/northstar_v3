#!/usr/bin/env python3
"""
Show Greeks Script

Displays current portfolio Greeks.
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


def show_greeks():
    """Display Greeks"""
    print("=" * 80)
    print("Portfolio Greeks")
    print(f"Time: {datetime.now()}")
    print("=" * 80)
    
    state = load_latest_state()
    if not state:
        print("❌ No state snapshot found")
        return
    
    greeks = state.get('portfolio_greeks', {})
    
    if not greeks:
        print("No Greeks data available")
        return
    
    # Portfolio-level Greeks
    print("\n📊 Portfolio Greeks:")
    table_data = [
        ['Delta', f"{greeks.get('delta', 0):.2f}"],
        ['Gamma', f"{greeks.get('gamma', 0):.2f}"],
        ['Vega', f"{greeks.get('vega', 0):.2f}"],
        ['Theta', f"{greeks.get('theta', 0):.2f}"],
        ['Rho', f"{greeks.get('rho', 0):.2f}"],
    ]
    print(tabulate(table_data, headers=['Greek', 'Value'], tablefmt='grid'))
    
    # Per-underlying breakdown
    by_underlying = greeks.get('by_underlying', {})
    if by_underlying:
        print("\n📈 Greeks by Underlying:")
        table_data = []
        for underlying, und_greeks in by_underlying.items():
            table_data.append([
                underlying,
                f"{und_greeks.get('delta', 0):.2f}",
                f"{und_greeks.get('gamma', 0):.2f}",
                f"{und_greeks.get('vega', 0):.2f}",
                f"{und_greeks.get('theta', 0):.2f}"
            ])
        headers = ['Underlying', 'Delta', 'Gamma', 'Vega', 'Theta']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))


def main():
    try:
        show_greeks()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
