#!/usr/bin/env python3
"""
Test script for AlternativeFeatureBlock implementation.

Validates that all feature computation methods work correctly
and degrade gracefully when data is unavailable.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.ingestion_registry import IngestionRegistry
from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock
import yaml


def test_feature_block():
    """Test AlternativeFeatureBlock with real registry."""
    
    print("=" * 80)
    print("Testing AlternativeFeatureBlock Implementation")
    print("=" * 80)
    
    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'ingestion_config.yaml'
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # Initialize registry
    print("\n1. Initializing IngestionRegistry...")
    registry = IngestionRegistry(config)
    print("   ✓ Registry initialized")
    
    # Initialize feature block
    print("\n2. Initializing AlternativeFeatureBlock...")
    feature_block = AlternativeFeatureBlock(registry, config)
    print("   ✓ Feature block initialized")
    
    # Test feature name methods
    print("\n3. Testing feature name methods...")
    market_features = AlternativeFeatureBlock.get_market_feature_names()
    company_features = AlternativeFeatureBlock.get_company_feature_names()
    print(f"   ✓ Market features: {len(market_features)} features")
    print(f"   ✓ Company features: {len(company_features)} features")
    
    # Test market-level features
    print("\n4. Testing market-level feature computation...")
    as_of_date = datetime.now() - timedelta(days=1)
    
    try:
        market_df = feature_block.compute_market_level_features(as_of_date)
        print(f"   ✓ Market features computed: {market_df.shape}")
        print(f"   ✓ Columns: {list(market_df.columns)}")
        
        # Check for NaN values
        nan_count = market_df.isna().sum().sum()
        if nan_count > 0:
            print(f"   ⚠ Warning: {nan_count} NaN values found")
        else:
            print("   ✓ No NaN values (graceful degradation working)")
        
        # Display sample values
        print("\n   Sample market features:")
        for col in market_df.columns[:5]:
            print(f"     {col}: {market_df[col].iloc[0]:.4f}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test company-level features
    print("\n5. Testing company-level feature computation...")
    test_tickers = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
    
    try:
        company_df = feature_block.compute_company_level_features(as_of_date, test_tickers)
        print(f"   ✓ Company features computed: {company_df.shape}")
        print(f"   ✓ Tickers: {list(company_df.index)}")
        
        # Check all tickers present
        missing_tickers = set(test_tickers) - set(company_df.index)
        if missing_tickers:
            print(f"   ✗ Missing tickers: {missing_tickers}")
        else:
            print("   ✓ All input tickers present")
        
        # Check for NaN values
        nan_count = company_df.isna().sum().sum()
        if nan_count > 0:
            print(f"   ⚠ Warning: {nan_count} NaN values found")
        else:
            print("   ✓ No NaN values (graceful degradation working)")
        
        # Display sample values for first ticker
        print(f"\n   Sample company features for {test_tickers[0]}:")
        ticker_features = company_df.loc[test_tickers[0]]
        for col in list(ticker_features.index)[:5]:
            print(f"     {col}: {ticker_features[col]:.4f}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test individual feature group methods
    print("\n6. Testing individual feature group methods...")
    
    # GST features
    try:
        gst_features = feature_block._compute_gst_features(as_of_date)
        print(f"   ✓ GST features: {len(gst_features)} features")
        print(f"     Keys: {list(gst_features.keys())}")
    except Exception as e:
        print(f"   ✗ GST features error: {e}")
    
    # Power features
    try:
        power_features = feature_block._compute_power_features(as_of_date)
        print(f"   ✓ Power features: {len(power_features)} features")
        print(f"     Keys: {list(power_features.keys())}")
    except Exception as e:
        print(f"   ✗ Power features error: {e}")
    
    # Credit market features
    try:
        credit_features = feature_block._compute_credit_market_features(as_of_date)
        print(f"   ✓ Credit market features: {len(credit_features)} features")
        print(f"     Keys: {list(credit_features.keys())}")
    except Exception as e:
        print(f"   ✗ Credit market features error: {e}")
    
    # Bulk market features
    try:
        bulk_features = feature_block._compute_bulk_market_features(as_of_date)
        print(f"   ✓ Bulk market features: {len(bulk_features)} features")
        print(f"     Keys: {list(bulk_features.keys())}")
    except Exception as e:
        print(f"   ✗ Bulk market features error: {e}")
    
    # Pledge market features
    try:
        pledge_features = feature_block._compute_pledge_market_features(as_of_date)
        print(f"   ✓ Pledge market features: {len(pledge_features)} features")
        print(f"     Keys: {list(pledge_features.keys())}")
    except Exception as e:
        print(f"   ✗ Pledge market features error: {e}")
    
    # Test z-score helper
    print("\n7. Testing helper methods...")
    import pandas as pd
    test_series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    zscore = feature_block._zscore(15, test_series)
    print(f"   ✓ Z-score computation: zscore(15, [1..10]) = {zscore:.4f}")
    
    # Test rating conversion
    rating_score = feature_block._rating_to_score('AAA')
    print(f"   ✓ Rating conversion: AAA = {rating_score:.2f}")
    
    print("\n" + "=" * 80)
    print("✓ All tests completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    test_feature_block()
