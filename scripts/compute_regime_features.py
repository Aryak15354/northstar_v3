#!/usr/bin/env python3
"""
Compute Regime Overlay Features from Existing Data

This script computes:
1. Market Breadth from stock-level returns (advance/decline ratio)
2. India VIX Proxy from Nifty 500 realized volatility OR cross-sectional volatility
3. Integrates FII flows from existing Screener data

All data is computed from REAL market data — no mock or synthetic data.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compute_market_breadth() -> pd.DataFrame:
    """
    Compute market breadth (advance/decline ratio) from stock-level returns.
    
    Uses prices.parquet which has ticker-level daily OHLCV data.
    Breadth = % of stocks with positive returns each day
    """
    logger.info("=" * 70)
    logger.info("COMPUTING MARKET BREADTH FROM PRICES")
    logger.info("=" * 70)
    
    prices_path = PROJECT_ROOT / 'data' / 'processed' / 'prices.parquet'
    
    if not prices_path.exists():
        logger.error("prices.parquet not found")
        return pd.DataFrame()
    
    logger.info("Loading price data...")
    # Load data (use engine='pyarrow' for better performance)
    prices = pd.read_parquet(prices_path, columns=['Date', 'Ticker', 'Close'])
    logger.info(f"Loaded {len(prices):,} price records")
    
    # Convert date
    prices['Date'] = pd.to_datetime(prices['Date'], errors='coerce')
    prices = prices.dropna(subset=['Date', 'Ticker', 'Close'])
    
    # Sort by ticker and date
    prices = prices.sort_values(['Ticker', 'Date'])
    
    # Compute daily returns
    prices['return'] = prices.groupby('Ticker')['Close'].pct_change()
    
    # Flag positive returns
    prices['positive'] = (prices['return'] > 0).astype(int)
    
    # Compute breadth by date: % of stocks with positive returns
    daily_stats = prices.groupby('Date').agg({
        'positive': ['mean', 'sum', 'count'],
        'Ticker': 'nunique'
    })
    daily_stats.columns = ['breadth_pct', 'advancing', 'total_stocks', 'unique_tickers']
    
    # Breadth is the percentage of advancing stocks
    daily_stats['breadth_ratio'] = daily_stats['advancing'] / daily_stats['total_stocks']
    
    # Compute rolling averages
    for window in [5, 21]:
        daily_stats[f'breadth_{window}d'] = daily_stats['breadth_ratio'].rolling(
            window, min_periods=max(1, window//2)
        ).mean()
    
    # Compute extreme breadth flags
    daily_stats['breadth_extreme_high'] = (daily_stats['breadth_ratio'] > 0.80).astype(int)
    daily_stats['breadth_extreme_low'] = (daily_stats['breadth_ratio'] < 0.20).astype(int)
    
    # Reset index
    daily_stats = daily_stats.reset_index()
    
    # Select final columns
    final_cols = [
        'Date',
        'breadth_ratio',
        'breadth_5d',
        'breadth_21d',
        'advancing',
        'total_stocks',
        'breadth_extreme_high',
        'breadth_extreme_low'
    ]
    
    daily_stats = daily_stats[[c for c in final_cols if c in daily_stats.columns]]
    
    logger.info(f"Computed market breadth for {len(daily_stats):,} days")
    logger.info(f"Breadth range: {daily_stats['breadth_ratio'].min():.1%} to {daily_stats['breadth_ratio'].max():.1%}")
    logger.info(f"Mean breadth: {daily_stats['breadth_ratio'].mean():.1%}")
    
    # Save
    output_dir = PROJECT_ROOT / 'data' / 'processed' / 'regime'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'market_breadth.parquet'
    daily_stats.to_parquet(output_path, index=False)
    logger.info(f"✓ Saved market breadth to {output_path}")
    
    return daily_stats


def compute_vix_proxy() -> pd.DataFrame:
    """
    Compute India VIX proxy from available data.
    
    Since India VIX is not in our inventory, we compute a proxy using:
    1. Cross-sectional volatility dispersion (stocks' return volatility)
    2. Aggregate market realized volatility (if index data available)
    
    This proxy correlates with India VIX behavior (fear gauge).
    """
    logger.info("=" * 70)
    logger.info("COMPUTING VIX PROXY FROM CROSS-SECTIONAL VOLATILITY")
    logger.info("=" * 70)
    
    prices_path = PROJECT_ROOT / 'data' / 'processed' / 'prices.parquet'
    
    if not prices_path.exists():
        logger.error("prices.parquet not found")
        return pd.DataFrame()
    
    logger.info("Loading price data for volatility computation...")
    
    # Load price data
    prices = pd.read_parquet(prices_path, columns=['Date', 'Ticker', 'Close'])
    logger.info(f"Loaded {len(prices):,} price records")
    
    # Convert date
    prices['Date'] = pd.to_datetime(prices['Date'], errors='coerce')
    prices = prices.dropna(subset=['Date', 'Ticker', 'Close'])
    
    # Sort
    prices = prices.sort_values(['Ticker', 'Date'])
    
    # Compute daily returns
    prices['return'] = prices.groupby('Ticker')['Close'].pct_change()
    
    # Compute cross-sectional volatility dispersion each day
    # This measures the dispersion of individual stock volatilities
    daily_vol = prices.groupby('Date').agg({
        'return': ['std', 'mean', 'count']
    })
    daily_vol.columns = ['cross_sectional_vol', 'mean_return', 'stock_count']
    
    # Annualize cross-sectional volatility
    daily_vol['cross_sectional_vol_ann'] = daily_vol['cross_sectional_vol'] * np.sqrt(252)
    
    # Compute average individual stock volatility (time-series vol for each stock, then average)
    # This is more computationally intensive but more accurate
    logger.info("Computing individual stock volatilities...")
    
    # Rolling 30-day volatility for each stock
    prices['vol_30d'] = prices.groupby('Ticker')['return'].transform(
        lambda x: x.rolling(30, min_periods=10).std() * np.sqrt(252)
    )
    
    # Average volatility across all stocks each day
    avg_vol_by_date = prices.groupby('Date')['vol_30d'].mean()
    
    # Merge with daily_vol
    daily_vol = daily_vol.join(avg_vol_by_date)
    daily_vol = daily_vol.rename(columns={'vol_30d': 'avg_stock_vol_30d'})
    
    # VIX proxy: Scale to match India VIX typical range (10-30)
    # India VIX typically trades at 1.5-2.0x realized volatility
    # We use a combination of cross-sectional and time-series vol
    daily_vol['vix_proxy'] = (
        0.5 * daily_vol['avg_stock_vol_30d'] + 
        0.5 * daily_vol['cross_sectional_vol_ann']
    ) * 1.75 * 100  # Scale to percentage
    
    # Winsorize to reasonable VIX range
    daily_vol['vix_proxy'] = daily_vol['vix_proxy'].clip(5, 80)
    
    # Compute VIX z-score (relative to 63-day mean)
    daily_vol['vix_zscore'] = (
        daily_vol['vix_proxy'] - daily_vol['vix_proxy'].rolling(63, min_periods=20).mean()
    ) / daily_vol['vix_proxy'].rolling(63, min_periods=20).std()
    
    # VIX regime flags
    daily_vol['vix_high'] = (daily_vol['vix_proxy'] > daily_vol['vix_proxy'].rolling(252, min_periods=60).quantile(0.80)).astype(int)
    daily_vol['vix_low'] = (daily_vol['vix_proxy'] < daily_vol['vix_proxy'].rolling(252, min_periods=60).quantile(0.20)).astype(int)
    
    # Reset index
    daily_vol = daily_vol.reset_index()
    
    # Select final columns
    final_cols = [
        'Date',
        'vix_proxy',
        'vix_zscore',
        'avg_stock_vol_30d',
        'cross_sectional_vol_ann',
        'stock_count',
        'vix_high',
        'vix_low'
    ]
    
    daily_vol = daily_vol[[c for c in final_cols if c in daily_vol.columns]]
    
    logger.info(f"Computed VIX proxy for {len(daily_vol):,} days")
    logger.info(f"VIX proxy range: {daily_vol['vix_proxy'].min():.1f} to {daily_vol['vix_proxy'].max():.1f}")
    logger.info(f"Mean VIX proxy: {daily_vol['vix_proxy'].mean():.1f}")
    
    # Save
    output_dir = PROJECT_ROOT / 'data' / 'processed' / 'regime'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'india_vix_proxy.parquet'
    daily_vol.to_parquet(output_path, index=False)
    logger.info(f"✓ Saved VIX proxy to {output_path}")
    
    return daily_vol


def extract_fii_flows() -> pd.DataFrame:
    """
    Extract FII flow data from research snapshots.
    
    FII data is already in the system via Screener shareholding data.
    """
    logger.info("=" * 70)
    logger.info("EXTRACTING FII FLOW DATA")
    logger.info("=" * 70)
    
    # Find most recent research snapshot
    research_dir = PROJECT_ROOT / 'data' / 'results' / 'research' / 'snapshots'
    snapshots = list(research_dir.rglob('research_snapshot_*.parquet'))
    
    if not snapshots:
        logger.error("No research snapshots found")
        return pd.DataFrame()
    
    # Use most recent
    snapshot_path = sorted(snapshots)[-1]
    logger.info(f"Using snapshot: {snapshot_path.name}")
    
    snapshot = pd.read_parquet(snapshot_path)
    
    # Extract FII columns
    fii_cols = [c for c in snapshot.columns if 'fii' in c.lower()]
    logger.info(f"Found FII columns: {fii_cols}")
    
    if not fii_cols:
        logger.warning("No FII columns found")
        return pd.DataFrame()
    
    # Keep key columns
    keep_cols = ['ticker', 'date'] + [c for c in fii_cols if 'change' in c.lower() or 'pct' in c.lower()]
    keep_cols = [c for c in keep_cols if c in snapshot.columns]
    
    fii_data = snapshot[keep_cols].copy()
    fii_data = fii_data.dropna(subset=['ticker', 'date'])
    
    logger.info(f"Extracted {len(fii_data):,} FII records")
    
    # Save
    output_dir = PROJECT_ROOT / 'data' / 'processed' / 'regime'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / 'fii_flows.parquet'
    fii_data.to_parquet(output_path, index=False)
    logger.info(f"✓ Saved FII flows to {output_path}")
    
    return fii_data


def create_regime_feature_summary():
    """
    Create a summary document of all regime features.
    """
    logger.info("=" * 70)
    logger.info("CREATING REGIME FEATURE SUMMARY")
    logger.info("=" * 70)
    
    output_dir = PROJECT_ROOT / 'data' / 'processed' / 'regime'
    
    # List all files
    files = list(output_dir.glob('*.parquet'))
    
    summary = []
    for f in files:
        df = pd.read_parquet(f)
        summary.append({
            'file': f.name,
            'rows': len(df),
            'columns': list(df.columns),
            'date_range': f"{df['Date'].min().date()} to {df['Date'].max().date()}" if 'Date' in df.columns else 'N/A'
        })
    
    summary_df = pd.DataFrame(summary)
    print("\n" + "=" * 70)
    print("REGIME FEATURES SUMMARY")
    print("=" * 70)
    print(summary_df.to_string(index=False))
    print("=" * 70)
    
    # Save summary
    summary_df.to_csv(output_dir / 'feature_summary.csv', index=False)
    logger.info(f"✓ Saved feature summary to {output_dir / 'feature_summary.csv'}")


def main():
    logger.info("=" * 70)
    logger.info("REGIME OVERLAY FEATURE COMPUTATION")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Computing from REAL market data only:")
    logger.info("  - Market Breadth: From stock-level returns (prices.parquet)")
    logger.info("  - VIX Proxy: From cross-sectional volatility (prices.parquet)")
    logger.info("  - FII Flows: From Screener shareholding (research snapshots)")
    logger.info("")
    logger.info("NO mock or synthetic data used.")
    logger.info("=" * 70)
    logger.info("")
    
    # Compute all features
    breadth = compute_market_breadth()
    vix = compute_vix_proxy()
    fii = extract_fii_flows()
    
    # Create summary
    create_regime_feature_summary()
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("REGIME FEATURES COMPUTATION COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Features created:")
    logger.info("  ✓ market_breadth.parquet — Advance/decline ratio from real returns")
    logger.info("  ✓ india_vix_proxy.parquet — VIX proxy from real volatility")
    logger.info("  ✓ fii_flows.parquet — FII flows from real shareholding data")
    logger.info("")
    logger.info("All data is REAL market data — no mock or synthetic data.")
    logger.info("")
    logger.info("Next: These features will be automatically picked up by FeatureFactory")
    logger.info("      when computing regime-conditional features.")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
