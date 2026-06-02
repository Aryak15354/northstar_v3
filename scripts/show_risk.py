#!/usr/bin/env python3
"""
Show Risk Metrics Script

Displays current risk metrics and limits.
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


def show_risk():
    """Display risk metrics"""
    print("=" * 80)
    print("Risk Metrics")
    print(f"Time: {datetime.now()}")
    print("=" * 80)
    
    state = load_latest_state()
    if not state:
        print("❌ No state snapshot found")
        return
    
    risk_metrics = state.get('risk_metrics', {})
    
    if not risk_metrics:
        print("No risk metrics available")
        return
    
    # VaR metrics
    print("\n📉 Value at Risk (VaR):")
    table_data = [
        ['VaR 95%', f"${risk_metrics.get('var_95', 0):,.2f}"],
        ['VaR 99%', f"${risk_metrics.get('var_99', 0):,.2f}"],
        ['VaR 99.9%', f"${risk_metrics.get('var_999', 0):,.2f}"],
        ['CVaR 95%', f"${risk_metrics.get('cvar_95', 0):,.2f}"],
    ]
    print(tabulate(table_data, headers=['Metric', 'Value'], tablefmt='grid'))
    
    # Drawdown
    print("\n📊 Drawdown:")
    table_data = [
        ['Current Drawdown', f"{risk_metrics.get('current_drawdown', 0):.2%}"],
        ['Max Drawdown', f"{risk_metrics.get('max_drawdown', 0):.2%}"],
    ]
    print(tabulate(table_data, headers=['Metric', 'Value'], tablefmt='grid'))
    
    # Position limits
    print("\n🎯 Position Limits:")
    positions = len(state.get('positions', []))
    table_data = [
        ['Current Positions', str(positions)],
        ['Position Limit', 'N/A'],  # Would come from config
    ]
    print(tabulate(table_data, headers=['Metric', 'Value'], tablefmt='grid'))


def main():
    try:
        show_risk()
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
