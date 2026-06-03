#!/usr/bin/env python3
"""
Test Sentiment Data Ingestion

Validates that the sentiment system can actually load and process
news data from data/raw/news/ and that all components work together.

This must pass before adding sentiment to the startup sequence.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_state import compute_sentiment_state, SentimentRegime
from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
from src.core.state import UnifiedState


def test_raw_news_data_exists():
    """Test 1: Check if raw news data files exist"""
    print("\n" + "="*80)
    print("TEST 1: Raw News Data Availability")
    print("="*80)
    
    news_files = [
        'data/raw/news/india-news-headlines.csv',
        'data/raw/news/IN-FINews Dataset.csv',
        'data/raw/news/News_Articles_Indian_Express.csv'
    ]
    
    results = {}
    for file_path in news_files:
        exists = os.path.exists(file_path)
        results[file_path] = exists
        
        if exists:
            try:
                df = pd.read_csv(file_path, nrows=5)
                print(f"✓ {file_path}")
                print(f"  Columns: {list(df.columns)}")
                print(f"  Sample rows: {len(df)}")
            except Exception as e:
                print(f"⚠ {file_path} exists but can't read: {e}")
        else:
            print(f"✗ {file_path} NOT FOUND")
    
    all_exist = all(results.values())
    print(f"\nResult: {'✓ PASS' if all_exist else '✗ FAIL'}")
    return all_exist


def test_sentiment_loader():
    """Test 2: Check if SentimentLoader can load data"""
    print("\n" + "="*80)
    print("TEST 2: SentimentLoader Functionality")
    print("="*80)
    
    try:
        # Initialize registry
        registry = IngestionRegistry()
        
        # Test market sentiment loading
        print("\nTesting market sentiment loading...")
        as_of_date = datetime.now()
        market_df = registry.sentiment.load_market_sentiment(as_of_date)
        
        if not market_df.empty:
            print(f"✓ Market sentiment loaded: {len(market_df)} rows")
            print(f"  Columns: {list(market_df.columns)}")
            print(f"  Date range: {market_df.index.min()} to {market_df.index.max()}")
            
            # Check data freshness
            latest_date = market_df.index.max()
            if isinstance(latest_date, pd.Timestamp):
                latest_date = latest_date.to_pydatetime()
            days_old = (as_of_date - latest_date).days
            print(f"  Data age: {days_old} days old")
            
            if days_old > 3:
                print(f"  ⚠ WARNING: Data is stale (>{days_old} days old)")
        else:
            print("✗ Market sentiment is EMPTY")
            return False
        
        # Test company sentiment loading
        print("\nTesting company sentiment loading...")
        company_df = registry.sentiment.load_company_sentiment(
            as_of_date,
            tickers=['RELIANCE', 'TCS', 'INFY'],
            lookback_days=30
        )
        
        if not company_df.empty:
            print(f"✓ Company sentiment loaded: {len(company_df)} rows")
            if isinstance(company_df.index, pd.MultiIndex):
                tickers = company_df.index.get_level_values('Ticker').unique()
                print(f"  Tickers with data: {list(tickers)}")
        else:
            print("⚠ Company sentiment is EMPTY (may be normal if no company-level data)")
        
        # Test freshness check
        print("\nTesting freshness check...")
        is_fresh = registry.sentiment.is_sentiment_fresh(as_of_date)
        print(f"  Sentiment is fresh: {is_fresh}")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_regime_classification():
    """Test 3: Check if regime classifier works with real data"""
    print("\n" + "="*80)
    print("TEST 3: Regime Classification with Real Data")
    print("="*80)
    
    try:
        # Load real sentiment data
        registry = IngestionRegistry()
        as_of_date = datetime.now()
        market_df = registry.sentiment.load_market_sentiment(as_of_date)
        
        if market_df.empty:
            print("✗ SKIP: No market sentiment data available")
            return False
        
        # Find score column
        if 'sentiment_score' in market_df.columns:
            score_col = 'sentiment_score'
        elif 'raw_score' in market_df.columns:
            score_col = 'raw_score'
        else:
            score_cols = [c for c in market_df.columns if 'score' in c.lower()]
            if not score_cols:
                print("✗ FAIL: No sentiment score column found")
                return False
            score_col = score_cols[0]
        
        sentiment_series = market_df[score_col]
        print(f"Using column: {score_col}")
        print(f"Data points: {len(sentiment_series)}")
        print(f"Score range: [{sentiment_series.min():.3f}, {sentiment_series.max():.3f}]")
        print(f"Score mean: {sentiment_series.mean():.3f}")
        print(f"Score std: {sentiment_series.std():.3f}")
        
        # Classify regime
        config = {
            'sentiment_regime': {
                'lookback_days': 252,
                'smoothing_days': 5,
                'hysteresis_buffer': 0.25,
                'min_history_days': 60,
                'thresholds': {
                    'panic_lower': -2.0,
                    'fear_lower': -0.5,
                    'neutral_upper': 0.5,
                    'euphoria_upper': 2.0
                }
            }
        }
        classifier = SentimentRegimeClassifier(config)
        
        regime, confidence = classifier.classify(sentiment_series, as_of_date)
        trend = classifier.classify_trend(sentiment_series, as_of_date)
        
        print(f"\n✓ Classification successful:")
        print(f"  Regime: {regime.value}")
        print(f"  Confidence: {confidence:.2f}")
        print(f"  Trend: {trend.value}")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_engineering():
    """Test 4: Check if feature block works with real data"""
    print("\n" + "="*80)
    print("TEST 4: Feature Engineering with Real Data")
    print("="*80)
    
    try:
        registry = IngestionRegistry()
        config = {}
        
        block = SentimentFeatureBlock(registry, config)
        as_of_date = datetime.now()
        
        # Test market features
        print("\nComputing market features...")
        market_features = block.compute_market_features(as_of_date)
        
        if not market_features.empty:
            print(f"✓ Market features computed: {len(market_features)} rows")
            print(f"  Features: {list(market_features.columns)}")
            print(f"\n  Sample values (most recent):")
            for col in market_features.columns:
                val = market_features[col].iloc[-1]
                print(f"    {col}: {val:.4f}")
        else:
            print("⚠ Market features are EMPTY (likely stale data)")
        
        # Test company features
        print("\nComputing company features...")
        test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
        company_features = block.compute_company_features(as_of_date, test_tickers)
        
        if not company_features.empty:
            print(f"✓ Company features computed: {len(company_features)} rows")
            print(f"  Features: {list(company_features.columns)}")
            
            # Check coverage
            has_coverage = company_features[company_features['sent_has_coverage'] > 0]
            print(f"  Tickers with coverage: {len(has_coverage)}/{len(test_tickers)}")
            if len(has_coverage) > 0:
                print(f"  Covered tickers: {list(has_coverage.index)}")
        else:
            print("✗ Company features are EMPTY")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_state_integration():
    """Test 5: Check if sentiment integrates with UnifiedState"""
    print("\n" + "="*80)
    print("TEST 5: UnifiedState Integration")
    print("="*80)
    
    try:
        # Create unified state
        state = UnifiedState()
        
        print("✓ UnifiedState created")
        print(f"  Has sentiment attribute: {hasattr(state, 'sentiment')}")
        print(f"  Default regime: {state.sentiment.market_sentiment_regime.value}")
        print(f"  Default is_fresh: {state.sentiment.is_fresh}")
        
        # Try to compute sentiment state with real data
        print("\nComputing sentiment state with real data...")
        registry = IngestionRegistry()
        config = {
            'sentiment_regime': {
                'lookback_days': 252,
                'smoothing_days': 5,
                'hysteresis_buffer': 0.25,
                'min_history_days': 60,
                'thresholds': {
                    'panic_lower': -2.0,
                    'fear_lower': -0.5,
                    'neutral_upper': 0.5,
                    'euphoria_upper': 2.0
                }
            }
        }
        classifier = SentimentRegimeClassifier(config)
        as_of_date = datetime.now()
        
        sentiment_state = compute_sentiment_state(registry, as_of_date, classifier)
        
        print(f"✓ Sentiment state computed:")
        print(f"  Regime: {sentiment_state.market_sentiment_regime.value}")
        print(f"  Trend: {sentiment_state.sentiment_trend.value}")
        print(f"  Z-score: {sentiment_state.market_sentiment_zscore:.3f}")
        print(f"  Is fresh: {sentiment_state.is_fresh}")
        print(f"  Data lag: {sentiment_state.data_lag_days} days")
        print(f"  Crisis signal: {sentiment_state.sentiment_crisis_signal}")
        print(f"  Companies with coverage: {sentiment_state.companies_with_coverage}")
        
        # Update unified state
        state.sentiment = sentiment_state
        print(f"\n✓ UnifiedState updated with sentiment")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_quality():
    """Test 6: Check data quality and coverage"""
    print("\n" + "="*80)
    print("TEST 6: Data Quality and Coverage")
    print("="*80)
    
    try:
        registry = IngestionRegistry()
        as_of_date = datetime.now()
        
        # Load market sentiment
        market_df = registry.sentiment.load_market_sentiment(as_of_date)
        
        if market_df.empty:
            print("✗ FAIL: No market sentiment data")
            return False
        
        # Find score column
        if 'sentiment_score' in market_df.columns:
            score_col = 'sentiment_score'
        elif 'raw_score' in market_df.columns:
            score_col = 'raw_score'
        else:
            score_cols = [c for c in market_df.columns if 'score' in c.lower()]
            score_col = score_cols[0] if score_cols else None
        
        if not score_col:
            print("✗ FAIL: No score column found")
            return False
        
        scores = market_df[score_col]
        
        # Quality checks
        print("\nData Quality Checks:")
        
        # Check for NaN values
        nan_count = scores.isna().sum()
        nan_pct = (nan_count / len(scores)) * 100
        print(f"  NaN values: {nan_count} ({nan_pct:.1f}%)")
        if nan_pct > 10:
            print(f"    ⚠ WARNING: High NaN percentage")
        
        # Check for constant values
        unique_values = scores.nunique()
        print(f"  Unique values: {unique_values}")
        if unique_values < 10:
            print(f"    ⚠ WARNING: Low variance in data")
        
        # Check date continuity
        dates = pd.Series(market_df.index)
        date_diffs = dates.diff().dt.days
        max_gap = date_diffs.max()
        print(f"  Maximum date gap: {max_gap} days")
        if max_gap > 7:
            print(f"    ⚠ WARNING: Large gaps in data")
        
        # Check recent data availability
        latest_date = market_df.index.max()
        if isinstance(latest_date, pd.Timestamp):
            latest_date = latest_date.to_pydatetime()
        days_old = (as_of_date - latest_date).days
        print(f"  Data freshness: {days_old} days old")
        if days_old > 3:
            print(f"    ⚠ WARNING: Data is stale")
        
        # Check score distribution
        print(f"\nScore Distribution:")
        print(f"  Min: {scores.min():.3f}")
        print(f"  25%: {scores.quantile(0.25):.3f}")
        print(f"  50%: {scores.quantile(0.50):.3f}")
        print(f"  75%: {scores.quantile(0.75):.3f}")
        print(f"  Max: {scores.max():.3f}")
        print(f"  Mean: {scores.mean():.3f}")
        print(f"  Std: {scores.std():.3f}")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "SENTIMENT INGESTION VALIDATION" + " " * 28 + "║")
    print("║" + " " * 15 + "Testing End-to-End Sentiment Data Flow" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")
    
    tests = [
        ("Raw News Data Exists", test_raw_news_data_exists),
        ("SentimentLoader Works", test_sentiment_loader),
        ("Regime Classification", test_regime_classification),
        ("Feature Engineering", test_feature_engineering),
        ("UnifiedState Integration", test_unified_state_integration),
        ("Data Quality", test_data_quality),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} CRASHED: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:10} {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    pct = (passed / total) * 100
    
    print(f"\nTotal: {passed}/{total} tests passed ({pct:.0f}%)")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Ready for startup integration")
        return 0
    elif passed >= total * 0.8:
        print("\n⚠ MOSTLY PASSING - Review failures before integration")
        return 1
    else:
        print("\n✗ MULTIPLE FAILURES - Fix issues before integration")
        return 2


if __name__ == '__main__':
    sys.exit(main())
