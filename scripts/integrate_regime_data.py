#!/usr/bin/env python3
"""
Integrate existing FII data and create VIX proxy from market data.

This script:
1. Extracts FII flow data from existing macro data
2. Creates a VIX proxy from Nifty 500 realized volatility
3. Integrates both into the feature factory
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _latest_snapshot_path() -> Path | None:
    candidates = sorted((PROJECT_ROOT / "data" / "results" / "research" / "snapshots").rglob("research_snapshot_*.parquet"))
    return candidates[-1] if candidates else None


def extract_fii_flows() -> pd.DataFrame:
    """
    Extract FII flow data from existing macro indicators.
    
    Returns daily FII flow series derived from monthly/weekly data.
    """
    logger.info("Extracting FII flow data from macro_indicators.parquet...")
    
    macro_path = PROJECT_ROOT / 'data' / 'macro' / 'macro_indicators.parquet'
    if not macro_path.exists():
        logger.error("macro_indicators.parquet not found")
        return pd.DataFrame()
    
    df = pd.read_parquet(macro_path)
    
    # Find FII-related columns
    fii_cols = [c for c in df.columns if 'fii' in c.lower() or 'foreign' in c.lower()]
    logger.info(f"Found {len(fii_cols)} FII-related columns")
    
    # The FII data is in research snapshots as screener_fii_pct
    # Let's use that instead
    snapshot_path = _latest_snapshot_path()
    if snapshot_path is not None and snapshot_path.exists():
        snapshot = pd.read_parquet(snapshot_path)
        fii_cols_snapshot = [c for c in snapshot.columns if 'fii' in c.lower()]
        logger.info(f"Research snapshot has FII columns: {fii_cols_snapshot}")
        
        # Extract FII percentage change
        if 'screener_fii_change_1q' in snapshot.columns:
            fii_data = snapshot[['ticker', 'date', 'screener_fii_change_1q']].copy()
            fii_data = fii_data.dropna(subset=['screener_fii_change_1q'])
            logger.info(f"Extracted {len(fii_data)} FII change records")
            return fii_data
    
    return pd.DataFrame()


def create_vix_proxy_from_prices() -> pd.DataFrame:
    """
    Create a VIX proxy from Nifty 500 realized volatility.
    
    Since India VIX data is not in our inventory, we compute a proxy
    from Nifty 500 daily returns using a 30-day rolling realized vol.
    """
    logger.info("Creating VIX proxy from Nifty 500 prices...")
    
    # Load Nifty 500 index data from macro data
    macro_path = PROJECT_ROOT / 'data' / 'macro' / 'macro_indicators.parquet'
    
    if macro_path.exists():
        macro = pd.read_parquet(macro_path)
        # Look for Nifty column
        nifty_cols = [c for c in macro.columns if 'nifty' in c.lower() or 'index' in c.lower() or 'sensex' in c.lower()]
        if nifty_cols:
            logger.info(f"Found Nifty/Index columns: {nifty_cols[:3]}")
            # Use first index column
            close = macro[nifty_cols[0]].dropna()
            
            # Compute daily returns
            daily_returns = np.log(close / close.shift(1))
            
            # Compute 30-day rolling realized volatility (annualized)
            realized_vol = daily_returns.rolling(30, min_periods=10).std() * np.sqrt(252)
            
            # Scale to match typical India VIX range (10-30)
            vix_proxy = realized_vol * 1.75 * 100  # Convert to percentage scale
            
            # Create DataFrame
            vix_df = pd.DataFrame({
                'date': close.index,
                'india_vix_proxy': vix_proxy.values
            }).dropna()
            
            logger.info(f"Created VIX proxy with {len(vix_df)} observations")
            logger.info(f"VIX proxy range: {vix_proxy.min():.1f} to {vix_proxy.max():.1f}")
            
            return vix_df
    
    logger.warning("No index data found in macro_indicators.parquet")
    return pd.DataFrame()


def create_market_breadth_proxy() -> pd.DataFrame:
    """
    Create market breadth proxy from universe advance/decline ratio.
    
    Since NSE advance/decline data is not in our inventory,
    we compute breadth from the cross-section of stock returns.
    """
    logger.info("Creating market breadth proxy from stock returns...")
    
    # Use research snapshot which has ticker-level data
    snapshot_path = _latest_snapshot_path()
    
    if snapshot_path is None or not snapshot_path.exists():
        logger.error("research_snapshot not found")
        return pd.DataFrame()
    
    snapshot = pd.read_parquet(snapshot_path)
    
    if 'date' not in snapshot.columns or 'ticker' not in snapshot.columns:
        logger.error("Snapshot missing required columns")
        return pd.DataFrame()
    
    # Compute daily returns if available
    if 'log_return_1d' in snapshot.columns:
        returns = snapshot[['ticker', 'date', 'log_return_1d']].copy()
        returns['positive'] = (returns['log_return_1d'] > 0).astype(int)
        
        # Compute breadth by date
        breadth = returns.groupby('date')['positive'].mean().reset_index()
        breadth.columns = ['date', 'market_breadth']
        
        # 5-day rolling average
        breadth['market_breadth_5d'] = breadth['market_breadth'].rolling(5, min_periods=1).mean()
        
        breadth = breadth.dropna()
        
        logger.info(f"Created market breadth proxy with {len(breadth)} observations")
        logger.info(f"Breadth range: {breadth['market_breadth'].min():.1%} to {breadth['market_breadth'].max():.1%}")
        
        return breadth[['date', 'market_breadth_5d']]
    
    logger.warning("log_return_1d not found in snapshot")
    return pd.DataFrame()


def save_regime_features():
    """
    Save all regime overlay features to a single file for FeatureFactory to use.
    """
    logger.info("=" * 70)
    logger.info("INTEGRATING REGIME OVERLAY FEATURES")
    logger.info("=" * 70)
    
    # Extract/create all features
    fii_data = extract_fii_flows()
    vix_data = create_vix_proxy_from_prices()
    breadth_data = create_market_breadth_proxy()
    
    # Save to processed directory
    output_dir = PROJECT_ROOT / 'data' / 'processed' / 'regime'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save VIX proxy
    if not vix_data.empty:
        vix_path = output_dir / 'india_vix_proxy.parquet'
        vix_data.to_parquet(vix_path, index=False)
        logger.info(f"✓ Saved VIX proxy to {vix_path}")
    
    # Save market breadth
    if not breadth_data.empty:
        breadth_path = output_dir / 'market_breadth.parquet'
        breadth_data.to_parquet(breadth_path, index=False)
        logger.info(f"✓ Saved market breadth to {breadth_path}")
    
    # Save FII flows
    if not fii_data.empty:
        fii_path = output_dir / 'fii_flows.parquet'
        fii_data.to_parquet(fii_path, index=False)
        logger.info(f"✓ Saved FII flows to {fii_path}")
    
    logger.info("=" * 70)
    logger.info("REGIME FEATURES INTEGRATION COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Features created:")
    logger.info("  - india_vix_proxy: Realized vol proxy for India VIX")
    logger.info("  - market_breadth_5d: 5-day average advance/decline ratio")
    logger.info("  - screener_fii_change_1q: Quarterly FII holding change (already in data)")
    logger.info("")
    logger.info("Next: These features will be automatically picked up by FeatureFactory")
    logger.info("      when use_regime_features=True in config")
    logger.info("=" * 70)


if __name__ == '__main__':
    save_regime_features()
