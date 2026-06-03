#!/usr/bin/env python3
"""
Load Nifty 500 Total Return Index Data

This script loads benchmark data for P&L comparison.
For now, we'll use Nifty 50 as a proxy until Nifty 500 TR is available.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def load_nifty_benchmark() -> pd.DataFrame:
    """
    Load Nifty benchmark data.
    
    Priority order:
    1. data/processed/nifty500_tr.parquet (Nifty 500 Total Return)
    2. data/processed/nifty50_tr.parquet (Nifty 50 Total Return)
    3. data/processed/nifty.parquet (Nifty 50 Price Index)
    """
    
    # Try Nifty 500 TR first
    nifty500_path = Path("data/processed/nifty500_tr.parquet")
    if nifty500_path.exists():
        print("✓ Loading Nifty 500 Total Return index")
        df = pd.read_parquet(nifty500_path)
        df['benchmark'] = 'NIFTY500_TR'
        return df
    
    # Try Nifty 50 TR
    nifty50tr_path = Path("data/processed/nifty50_tr.parquet")
    if nifty50tr_path.exists():
        print("✓ Loading Nifty 50 Total Return index")
        df = pd.read_parquet(nifty50tr_path)
        df['benchmark'] = 'NIFTY50_TR'
        return df
    
    # Fallback to Nifty 50 Price Index
    nifty_path = Path("data/processed/nifty.parquet")
    if nifty_path.exists():
        print("⚠ Loading Nifty 50 Price Index (fallback - not total return)")
        df = pd.read_parquet(nifty_path)
        df['benchmark'] = 'NIFTY50'
        return df
    
    print("✗ No benchmark data found")
    return None


def create_synthetic_benchmark(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Create synthetic benchmark for testing.
    Assumes 12% annualized return with 15% volatility.
    """
    print("⚠ Creating synthetic benchmark data for testing")
    
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Daily return parameters
    daily_return_mean = 0.12 / 252  # 12% annualized
    daily_return_std = 0.15 / np.sqrt(252)  # 15% annualized vol
    
    # Generate random returns
    np.random.seed(42)
    daily_returns = np.random.normal(daily_return_mean, daily_return_std, len(dates))
    
    # Compute cumulative index
    index_values = 10000 * (1 + daily_returns).cumprod()
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': index_values,
        'benchmark': 'SYNTHETIC_NIFTY500_TR'
    })
    
    return df


def prepare_benchmark_for_nav_calculator(
    benchmark_df: pd.DataFrame,
    date_col: str = 'Date',
    value_col: str = 'Close'
) -> pd.Series:
    """
    Prepare benchmark data as a Series indexed by date with daily returns.
    """
    if benchmark_df is None or benchmark_df.empty:
        return pd.Series(dtype=float)
    
    # Auto-detect date column if not found
    if date_col not in benchmark_df.columns:
        # Try common date column names
        for col in ['date', 'DATE', 'timestamp', 'Timestamp']:
            if col in benchmark_df.columns:
                date_col = col
                break
        else:
            # If still not found, use index if it's datetime
            if pd.api.types.is_datetime64_any_dtype(benchmark_df.index):
                benchmark_df = benchmark_df.reset_index()
                date_col = benchmark_df.columns[0]
    
    # Auto-detect value column if not found
    if value_col not in benchmark_df.columns:
        # Try common value column names
        for col in ['close', 'CLOSE', 'value', 'Value', 'price', 'Price']:
            if col in benchmark_df.columns:
                value_col = col
                break
    
    # Ensure date column is datetime
    benchmark_df[date_col] = pd.to_datetime(benchmark_df[date_col])
    
    # Set date as index
    benchmark_df = benchmark_df.set_index(date_col)
    
    # Compute daily returns
    returns = benchmark_df[value_col].pct_change().fillna(0)
    
    return returns


def main():
    """Load and prepare benchmark data"""
    print("=" * 60)
    print("Loading Benchmark Data for P&L Comparison")
    print("=" * 60)
    
    # Try to load real benchmark
    benchmark_df = load_nifty_benchmark()
    
    # If no real data, create synthetic
    if benchmark_df is None:
        benchmark_df = create_synthetic_benchmark('2024-09-01', datetime.now().strftime('%Y-%m-%d'))
    
    # Prepare for NAV calculator
    benchmark_returns = prepare_benchmark_for_nav_calculator(benchmark_df)
    
    print(f"\n✓ Benchmark data prepared")
    print(f"  Date range: {benchmark_returns.index.min()} to {benchmark_returns.index.max()}")
    print(f"  Total days: {len(benchmark_returns)}")
    print(f"  Mean daily return: {benchmark_returns.mean():.4%}")
    print(f"  Daily volatility: {benchmark_returns.std():.4%}")
    
    # Save prepared benchmark
    output_path = Path("data/pnl/benchmark_returns.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    benchmark_returns_df = benchmark_returns.reset_index()
    benchmark_returns_df.columns = ['date', 'return']
    benchmark_returns_df.to_parquet(output_path, index=False)
    
    print(f"\n✓ Saved to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
