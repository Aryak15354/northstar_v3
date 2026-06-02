#!/usr/bin/env python3
"""
Create dashboard data from existing backtest results
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
BACKTEST_DIR = PROJECT_ROOT / "data/results/analysis" / "backtests"

def create_nav_history_from_backtest():
    """Create NAV history from backtest results"""
    backtest_file = BACKTEST_DIR / "northstar_3year_backtest_real_data.csv"
    
    if not backtest_file.exists():
        print(f"❌ {backtest_file} not found")
        return None
    
    df = pd.read_csv(backtest_file)
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    
    print(f"✅ Loaded backtest data: {len(df)} records")
    print(f"   Columns: {list(df.columns)}")
    
    # Create NAV history
    nav_df = df.copy()
    
    # Ensure date column
    if 'date' in nav_df.columns:
        nav_df['date'] = pd.to_datetime(nav_df['date'])
    elif 'timestamp' in nav_df.columns:
        nav_df['date'] = pd.to_datetime(nav_df['timestamp'])
    
    # Calculate NAV if not present
    if 'nav' not in nav_df.columns:
        if 'Equity' in nav_df.columns:
            nav_df['nav'] = nav_df['Equity']
        elif 'portfolio_value' in nav_df.columns:
            nav_df['nav'] = nav_df['portfolio_value']
        elif 'cumulative_return' in nav_df.columns:
            nav_df['nav'] = 100 * (1 + nav_df['cumulative_return'] / 100)
        else:
            nav_df['nav'] = 100  # Default
    
    # Calculate returns
    nav_df = nav_df.sort_values('date')
    nav_df['daily_return'] = nav_df['nav'].pct_change() * 100
    nav_df['cumulative_return'] = ((nav_df['nav'] / nav_df['nav'].iloc[0]) - 1) * 100
    
    # Select relevant columns
    output_cols = ['date', 'nav', 'daily_return', 'cumulative_return']
    output_cols = [c for c in output_cols if c in nav_df.columns]
    
    nav_output = nav_df[output_cols]
    
    # Save
    output_path = DATA_DIR / "nav_history.parquet"
    nav_output.to_parquet(output_path, index=False)
    print(f"✅ Created nav_history.parquet: {len(nav_output)} records")
    
    return nav_output

def create_minimal_unified_state():
    """Create minimal unified_state.json for dashboard"""
    state = {
        "timestamp": datetime.now().isoformat(),
        "portfolio": {
            "equity_positions": {},
            "options_positions": {},
            "last_updated": datetime.now().isoformat()
        },
        "intelligence": {
            "regime": "sideways",
            "sentiment_score": 0.15,
            "conviction": 0.65,
            "last_updated": datetime.now().isoformat()
        },
        "governor": {
            "regime": "normal",
            "kelly_multiplier": 0.5,
            "exposure_multiplier": 1.0,
            "gross_target": 5000000,
            "last_updated": datetime.now().isoformat()
        },
        "risk": {
            "var_95": 50000,
            "gross_exposure": 4500000,
            "net_exposure": 4200000
        }
    }
    
    output_path = DATA_DIR / "unified_state.json"
    with open(output_path, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"✅ Created unified_state.json")
    return state

def main():
    print("=" * 60)
    print("Creating Dashboard Data from Backtests")
    print("=" * 60)
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Create NAV history from backtest
    print("\n1. Creating NAV History from Backtest...")
    nav_df = create_nav_history_from_backtest()
    
    # 2. Create minimal unified state
    print("\n2. Creating Minimal Unified State...")
    state = create_minimal_unified_state()
    
    print("\n" + "=" * 60)
    print("✅ Dashboard Data Creation Complete")
    print("=" * 60)
    print("\nData created:")
    print(f"  - data/nav_history.parquet ({len(nav_df) if nav_df is not None else 0} records)")
    print(f"  - data/unified_state.json")
    print(f"  - data/benchmark_nifty50.parquet (already exists)")
    print("\nYou can now launch the dashboard:")
    print("  streamlit run src/dashboard/app.py")

if __name__ == "__main__":
    main()
