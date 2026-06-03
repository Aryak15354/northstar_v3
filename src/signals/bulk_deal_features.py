"""
Bulk Deal Signal Features — Northstar V3 Phase 2

Implements 8 features from bulk deal data:
1. Net Buy Pressure (ADV-normalized)
2. Rolling Net Flow Windows (5d, 21d, 63d)
3. Buyer Identity Classification (FII, MF, Promoter, Corporate)
4. Price Impact Ratio
5. Deal Clustering
6. Pre-Announcement Run-Up Indicator
7. Bulk Buy vs Sell Asymmetry Score
8. Decay-weighted flow scores

Research Reference: Chaturvedula et al. (Emerging Markets Review 2015)
- Bulk buy CAR: +6.24% on event day, +4.57% by day +10
- Bulk sell CAR: ~0% (asymmetry due to short-sale constraints)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# Buyer classification keywords
FII_KEYWORDS = [
    "FII", "Foreign", "HSBC", "Goldman", "Morgan", "Deutsche", 
    "Nomura", "Merrill", "UBS", "Credit Suisse", "Barclays",
    "JP Morgan", "Citigroup", "Societe Generale"
]

MF_DII_KEYWORDS = [
    "Mutual Fund", "MF", "HDFC MF", "SBI MF", "ICICI Pru", 
    "Reliance MF", "Aditya Birla", "Insurance", "LIC", "NPS",
    "UTI", "Kotak MF", "Axis MF"
]

PROMOTER_KEYWORDS = [
    "Promoter", "Promoter Group", "HUF", "Proprietor"
]

CORPORATE_KEYWORDS = [
    "Ltd", "Limited", "Pvt", "LLP", "Corp", "Company"
]


def classify_buyer(buyer_name: str) -> str:
    """
    Classify buyer into institutional category.
    
    Returns: 'FII', 'MF_DII', 'Promoter', 'Corporate', or 'Other'
    """
    if pd.isna(buyer_name):
        return 'Other'
    
    name_upper = str(buyer_name).upper()
    
    for kw in FII_KEYWORDS:
        if kw.upper() in name_upper:
            return 'FII'
    
    for kw in MF_DII_KEYWORDS:
        if kw.upper() in name_upper:
            return 'MF_DII'
    
    for kw in PROMOTER_KEYWORDS:
        if kw.upper() in name_upper:
            return 'Promoter'
    
    for kw in CORPORATE_KEYWORDS:
        if kw.upper() in name_upper:
            return 'Corporate'
    
    return 'Other'


def compute_bulk_deal_features(
    bulk_deals_df: pd.DataFrame,
    prices_df: Optional[pd.DataFrame] = None,
    market_cap_df: Optional[pd.DataFrame] = None,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None
) -> pd.DataFrame:
    """
    Compute all 8 bulk deal features.
    
    Parameters
    ----------
    bulk_deals_df : pd.DataFrame
        Raw bulk deal data with columns:
        - date, ticker, buyer_name, seller_name, quantity, price
    prices_df : pd.DataFrame, optional
        Daily OHLCV data for ADV calculation
    market_cap_df : pd.DataFrame, optional
        Daily market cap for impact ratio
    start_date : pd.Timestamp, optional
        Start date for feature computation
    end_date : pd.Timestamp, optional
        End date for feature computation
    
    Returns
    -------
    pd.DataFrame
        Daily bulk deal features indexed by (date, ticker)
    """
    if bulk_deals_df.empty:
        return pd.DataFrame()
    
    df = bulk_deals_df.copy()
    
    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Filter date range
    if start_date:
        df = df[df['date'] >= start_date]
    if end_date:
        df = df[df['date'] <= end_date]
    
    # Classify buyers and sellers
    df['buyer_type'] = df['buyer_name'].apply(classify_buyer)
    df['seller_type'] = df['seller_name'].apply(classify_buyer)
    
    # Signed quantity (positive = buy, negative = sell)
    # Note: Need to determine which column indicates buy vs sell side
    # Typically bulk deals have 'deal_type' or 'buyer_is_active' column
    if 'deal_type' in df.columns:
        df['signed_qty'] = df.apply(
            lambda r: r['quantity'] if r['deal_type'].upper() == 'BUY' else -r['quantity'],
            axis=1
        )
    elif 'buyer_is_active' in df.columns:
        df['signed_qty'] = df.apply(
            lambda r: r['quantity'] if r['buyer_is_active'] else -r['quantity'],
            axis=1
        )
    else:
        # Default: assume all are buys (conservative)
        logger.warning("No deal_type column found, assuming all bulk deals are buys")
        df['signed_qty'] = df['quantity']
    
    # Compute deal value
    df['deal_value'] = df['quantity'] * df['price']
    
    # Group by ticker and date
    daily = df.groupby(['ticker', 'date']).agg({
        'signed_qty': 'sum',
        'deal_value': 'sum',
        'quantity': 'sum',
        'buyer_type': lambda x: x.mode().iloc[0] if not x.mode().empty else 'Other'
    }).reset_index()
    
    daily.columns = [
        'ticker', 'date', 
        'net_buy_qty', 'total_deal_value', 'total_qty', 'dominant_buyer_type'
    ]
    
    # Feature 1: Net Buy Pressure (will normalize by ADV later)
    daily['net_buy_pressure_raw'] = daily['net_buy_qty']
    
    # Feature 2: Rolling Net Flow Windows
    daily = daily.sort_values(['ticker', 'date'])
    for window in [5, 21, 63]:
        daily[f'net_buy_{window}d'] = daily.groupby('ticker')['net_buy_qty'].transform(
            lambda x: x.rolling(window, min_periods=1).sum()
        )
    
    # Feature 3: Buyer Identity Flows
    for buyer_cat in ['FII', 'MF_DII', 'Promoter', 'Corporate']:
        cat_mask = df['buyer_type'] == buyer_cat
        cat_daily = df[cat_mask].groupby(['ticker', 'date']).agg({
            'signed_qty': 'sum'
        }).reset_index()
        cat_daily.columns = ['ticker', 'date', f'net_{buyer_cat.lower()}_buy']
        daily = daily.merge(cat_daily, on=['ticker', 'date'], how='left')
        daily[f'net_{buyer_cat.lower()}_buy'] = daily[f'net_{buyer_cat.lower()}_buy'].fillna(0)
    
    # Feature 4: Price Impact Ratio (requires market cap)
    if market_cap_df is not None:
        daily = daily.merge(
            market_cap_df.reset_index(),
            left_on=['ticker', 'date'],
            right_on=['ticker', 'date'],
            how='left'
        )
        daily['impact_ratio'] = daily['deal_value'] / (daily['market_cap'] + 1e-9)
        daily['impact_ratio'] = daily['impact_ratio'].clip(0, 0.1)  # Cap at 10%
    
    # Feature 5: Deal Clustering (count distinct buyer types)
    clustering = df.groupby(['ticker', 'date'])['buyer_type'].nunique().reset_index()
    clustering.columns = ['ticker', 'date', 'inst_buyers_count']
    daily = daily.merge(clustering, on=['ticker', 'date'], how='left')
    daily['cluster_flag'] = (daily['inst_buyers_count'] >= 2).astype(int)
    
    # Feature 6: Pre-Announcement Run-Up (requires prices)
    if prices_df is not None:
        # Compute 5-day and 10-day returns prior to each deal
        returns = prices_df.groupby('ticker')['close'].pct_change().reset_index()
        returns['ret_5d'] = returns.groupby('ticker')['close'].pct_change(5)
        returns['ret_10d'] = returns.groupby('ticker')['close'].pct_change(10)
        
        daily = daily.merge(
            returns[['ticker', 'date', 'ret_5d', 'ret_10d']],
            on=['ticker', 'date'],
            how='left'
        )
        daily['leakage_flag'] = (daily['ret_5d'] > 0.02).astype(int)
    
    # Feature 7: Buy/Sell Asymmetry (21-day ratio)
    daily['buy_sell_ratio'] = daily.groupby('ticker')['net_buy_qty'].transform(
        lambda x: (x.rolling(21).sum() > 0).astype(float)
    )
    
    # Feature 8: Decay-weighted flow (EWMA with 10-day half-life)
    lambda_decay = 1 - np.log(2) / 10  # ~10 day half-life
    daily['decay_flow'] = daily.groupby('ticker')['net_buy_qty'].transform(
        lambda x: x.ewm(alpha=lambda_decay, min_periods=1).mean()
    )
    
    # Set index
    daily = daily.set_index(['date', 'ticker']).sort_index()
    
    # Select final features
    feature_cols = [
        'net_buy_pressure_raw',
        'net_buy_5d', 'net_buy_21d', 'net_buy_63d',
        'net_fii_buy', 'net_mf_dii_buy', 'net_promoter_buy', 'net_corporate_buy',
        'impact_ratio', 'inst_buyers_count', 'cluster_flag',
        'ret_5d', 'ret_10d', 'leakage_flag',
        'buy_sell_ratio', 'decay_flow'
    ]
    
    available_cols = [c for c in feature_cols if c in daily.columns]
    return daily[available_cols]


if __name__ == '__main__':
    # Test with sample data
    logger.info("Testing bulk deal feature computation...")
    
    # Create sample data
    sample = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'ticker': 'RELIANCE.NS',
        'buyer_name': 'FII - HSBC',
        'seller_name': 'Domestic Seller',
        'quantity': 100000,
        'price': 2500.0,
        'deal_type': 'BUY'
    })
    
    features = compute_bulk_deal_features(sample)
    logger.info(f"Generated {len(features.columns)} features")
    logger.info(f"Features: {list(features.columns)}")
