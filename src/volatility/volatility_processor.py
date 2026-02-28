"""
Volatility Processing Utilities

Consolidated from:
- src/processing/volatility_engine.py: Realized volatility and regime classification
- src/processing/options_volatility.py: Options-specific volatility metrics

Provides utility functions for calculating realized volatility metrics.
These are used to populate the VolatilityState managed by VolatilityStateEngine.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_realized_volatility(
    prices: pd.Series,
    window: int = 30,
    annualization_factor: float = 252.0
) -> float:
    """
    Calculate realized volatility from price series
    
    Args:
        prices: Price series (must be sorted by date)
        window: Rolling window for volatility calculation
        annualization_factor: Factor to annualize volatility (252 for daily data)
    
    Returns:
        Annualized realized volatility
    """
    if len(prices) < window + 1:
        return np.nan
    
    returns = prices.pct_change().dropna()
    
    if len(returns) < window:
        return np.nan
    
    vol = returns.tail(window).std() * np.sqrt(annualization_factor)
    
    return float(vol)


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    window: int = 14
) -> float:
    """
    Calculate Average True Range (ATR)
    
    Args:
        high: High price series
        low: Low price series
        window: Rolling window for ATR calculation
    
    Returns:
        Average True Range
    """
    if len(high) < window or len(low) < window:
        return np.nan
    
    true_range = (high - low).tail(window)
    atr = true_range.mean()
    
    return float(atr)


def classify_volatility_regime(
    current_vol: float,
    vol_history: pd.Series,
    low_threshold: float = 0.33,
    high_threshold: float = 0.66
) -> str:
    """
    Classify volatility regime based on percentile rank
    
    Args:
        current_vol: Current volatility level
        vol_history: Historical volatility series for percentile calculation
        low_threshold: Percentile threshold for low volatility (default 33rd)
        high_threshold: Percentile threshold for high volatility (default 66th)
    
    Returns:
        Regime classification: "Low", "Normal", or "High"
    """
    if pd.isna(current_vol) or vol_history.empty:
        return "Normal"
    
    # Calculate percentile rank
    vol_pct = (vol_history < current_vol).sum() / len(vol_history)
    
    if vol_pct < low_threshold:
        return "Low"
    elif vol_pct < high_threshold:
        return "Normal"
    else:
        return "High"


def calculate_volatility_percentile(
    current_vol: float,
    vol_history: pd.Series
) -> float:
    """
    Calculate volatility percentile rank
    
    Args:
        current_vol: Current volatility level
        vol_history: Historical volatility series
    
    Returns:
        Percentile rank (0-1)
    """
    if pd.isna(current_vol) or vol_history.empty:
        return 0.5
    
    percentile = (vol_history < current_vol).sum() / len(vol_history)
    
    return float(percentile)


def process_ticker_volatility(
    ticker_data: pd.DataFrame,
    vol_window: int = 30,
    atr_window: int = 14,
    percentile_window: int = 252
) -> Dict[str, float]:
    """
    Process volatility metrics for a single ticker
    
    Args:
        ticker_data: DataFrame with columns: Date, Close, High, Low
        vol_window: Window for realized volatility calculation
        atr_window: Window for ATR calculation
        percentile_window: Window for percentile rank calculation
    
    Returns:
        Dictionary with volatility metrics:
        - realized_vol: Annualized realized volatility
        - volatility_percentile: Percentile rank (0-1)
        - atr: Average True Range
        - volatility_regime: "Low", "Normal", or "High"
    """
    # Sort by date
    ticker_data = ticker_data.sort_values('Date')
    
    # Calculate realized volatility
    realized_vol = calculate_realized_volatility(
        ticker_data['Close'],
        window=vol_window
    )
    
    # Calculate ATR
    atr = calculate_atr(
        ticker_data['High'],
        ticker_data['Low'],
        window=atr_window
    )
    
    # Calculate volatility history for percentile
    returns = ticker_data['Close'].pct_change()
    vol_history = returns.rolling(vol_window).std() * np.sqrt(252)
    vol_history = vol_history.dropna().tail(percentile_window)
    
    # Calculate percentile
    vol_percentile = calculate_volatility_percentile(realized_vol, vol_history)
    
    # Classify regime
    vol_regime = classify_volatility_regime(realized_vol, vol_history)
    
    return {
        'realized_vol': realized_vol,
        'volatility_percentile': vol_percentile,
        'atr': atr,
        'volatility_regime': vol_regime
    }


def process_universe_volatility(
    prices_df: pd.DataFrame,
    vol_window: int = 30,
    atr_window: int = 14,
    percentile_window: int = 252
) -> pd.DataFrame:
    """
    Process volatility metrics for entire universe
    
    Args:
        prices_df: DataFrame with columns: ticker, Date, Close, High, Low
        vol_window: Window for realized volatility calculation
        atr_window: Window for ATR calculation
        percentile_window: Window for percentile rank calculation
    
    Returns:
        DataFrame with volatility metrics per ticker
    """
    records = []
    
    for ticker, ticker_data in prices_df.groupby('ticker'):
        try:
            metrics = process_ticker_volatility(
                ticker_data,
                vol_window=vol_window,
                atr_window=atr_window,
                percentile_window=percentile_window
            )
            
            # Skip if volatility calculation failed
            if pd.isna(metrics['realized_vol']):
                continue
            
            records.append({
                'ticker': ticker,
                **metrics
            })
            
        except Exception as e:
            logger.warning(f"Error processing volatility for {ticker}: {e}")
            continue
    
    return pd.DataFrame(records)


def calculate_implied_realized_spread(
    implied_vol: float,
    realized_vol: float
) -> float:
    """
    Calculate spread between implied and realized volatility
    
    Positive spread indicates implied > realized (options expensive)
    Negative spread indicates implied < realized (options cheap)
    
    Args:
        implied_vol: Implied volatility
        realized_vol: Realized volatility
    
    Returns:
        Volatility spread (implied - realized)
    """
    if pd.isna(implied_vol) or pd.isna(realized_vol):
        return np.nan
    
    return float(implied_vol - realized_vol)


def calculate_volatility_risk_premium(
    implied_vol: float,
    realized_vol: float
) -> float:
    """
    Calculate volatility risk premium
    
    VRP = (Implied - Realized) / Implied
    
    Positive VRP indicates options are expensive relative to realized vol
    
    Args:
        implied_vol: Implied volatility
        realized_vol: Realized volatility
    
    Returns:
        Volatility risk premium (0-1)
    """
    if pd.isna(implied_vol) or pd.isna(realized_vol) or implied_vol == 0:
        return np.nan
    
    vrp = (implied_vol - realized_vol) / implied_vol
    
    return float(vrp)
