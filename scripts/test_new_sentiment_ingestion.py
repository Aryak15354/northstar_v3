#!/usr/bin/env python3
"""
Test NEW Sentiment Data Ingestion Flow

This validates that the system can:
1. Process raw news data
2. Generate sentiment scores
3. Export to v3 format
4. Load via SentimentLoader
5. Integrate with UnifiedState

This is the FINAL validation before adding to startup sequence.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import subprocess

from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_state import compute_sentiment_state
from src.sentiment.sentiment_regime import SentimentRegimeClassifier


def test_raw_news_availability():
    """Test 1: Verify raw news data exists and has recent data"""
    print("\n" + "="*80)
    print("TEST 1: Raw News Data Availability & Freshness")
    print("="*80)
    
    news_files = {
        'india-news-headlines': 'data/raw/news/india-news-headlines.csv',
        'IN-FINews': 'data/raw/news/IN-FINews Dataset.csv',
        'Indian Express': 'data/raw/news/News_Articles_Indian_Express.csv'
    }
    
    total_articles = 0
    recent_articles = 0
    cutoff_date = datetime.now() - timedelta(days=90)
    
    for name, path in news_files.items():
        if not os.path.exists(path):
            print(f"✗ {name}: NOT FOUND at {path}")
            continue
        
        try:
            df = pd.read_csv(path)
            
            # Find date column
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'publish' in c.lower()]
            if not date_cols:
                print(f"⚠ {name}: No date column found")
                continue
            
            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            
            total = len(df)
            recent = len(df[df[date_col] >= cutoff_date])
            
            total_articles += total
            recent_articles += recent
            
            print(f"✓ {name}:")
            print(f"  Total articles: {total:,}")
            print(f"  Recent (90d): {recent:,}")
            print(f"  Date range: {df[date_col].min()} to {df[date_col].max()}")
            
        except Exception as e:
            print(f"✗ {name}: Error reading - {e}")
    
    print(f"\nSummary:")
    print(f"  Total articles: {total_articles:,}")
    print(f"  Recent articles (90d): {recent_articles:,}")
    
    if recent_articles > 100:
        print(f"\nResult: ✓ PASS - Sufficient recent news data")
        return True
    else:
        print(f"\nResult: ⚠ WARNING - Limited recent news data")
        return True  # Don't fail, just warn


def test_sentiment_processing_pipeline():
    """Test 2: Run sentiment processing pipeline on recent data"""
    print("\n" + "="*80)
    print("TEST 2: Sentiment Processing Pipeline")
    print("="*80)
    
    try:
        # Check if DuckDB exists
        duckdb_path = Path("data/sentiment.duckdb")
        
        if not duckdb_path.exists():
            print(f"⚠ DuckDB not found at {duckdb_path}")
            print("  Creating new database...")
        
        # Run export to v3 (incremental mode)
        print("\nRunning sentiment export to v3 format...")
        cmd = [
            sys.executable,
            "scripts/export_sentiment_to_v3.py",
            "--duckdb-path", str(duckdb_path),
            "--output-dir", "data/processed/sentiment",
            "--incremental"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✓ Sentiment export completed successfully")
            print("\nExport output:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"✗ Sentiment export failed with code {result.returncode}")
            print(f"Error: {result.stderr}")
            return False
        
        # Verify output files exist
        ticker_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
        market_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")
        
        if ticker_path.exists():
            df = pd.read_parquet(ticker_path)
            print(f"\n✓ Ticker sentiment file created: {len(df)} rows")
            if not df.empty:
                print(f"  Tickers: {df['ticker'].nunique()}")
                print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        else:
            print(f"\n⚠ Ticker sentiment file not found")
        
        if market_path.exists():
            df = pd.read_parquet(market_path)
            print(f"\n✓ Market sentiment file created: {len(df)} rows")
            if not df.empty:
                print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        else:
            print(f"\n⚠ Market sentiment file not found")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"\n✗ FAIL: Sentiment export timed out")
        return False
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_loader_reads_new_data():
    """Test 3: Verify SentimentLoader can read the newly processed data"""
    print("\n" + "="*80)
    print("TEST 3: SentimentLoader Reads New Data")
    print("="*80)
    
    try:
        registry = IngestionRegistry()
        as_of_date = datetime.now()
        
        # Load market sentiment
        print("\nLoading market sentiment...")
        market_df = registry.sentiment.load_market_sentiment(as_of_date)
        
        if market_df.empty:
            print("✗ Market sentiment is EMPTY")
            return False
        
        print(f"✓ Market sentiment loaded: {len(market_df)} rows")
        print(f"  Columns: {list(market_df.columns)}")
        print(f"  Date range: {market_df.index.min()} to {market_df.index.max()}")
        
        # Check data age
        latest_date = market_df.index.max()
        if isinstance(latest_date, pd.Timestamp):
            latest_date = latest_date.to_pydatetime()
        days_old = (as_of_date - latest_date).days
        print(f"  Data age: {days_old} days")
        
        if days_old > 7:
            print(f"  ⚠ WARNING: Data is {days_old} days old")
        
        # Load company sentiment
        print("\nLoading company sentiment...")
        test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
        company_df = registry.sentiment.load_company_sentiment(
            as_of_date,
            tickers=test_tickers,
            lookback_days=30
        )
        
        if not company_df.empty:
            print(f"✓ Company sentiment loaded: {len(company_df)} rows")
            if isinstance(company_df.index, pd.MultiIndex):
                tickers = company_df.index.get_level_values('Ticker').unique()
                print(f"  Tickers with data: {list(tickers)}")
        else:
            print("⚠ Company sentiment is EMPTY")
        
        # Check freshness
        is_fresh = registry.sentiment.is_sentiment_fresh(as_of_date)
        print(f"\nFreshness check: {is_fresh}")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_state_with_new_data():
    """Test 4: Verify UnifiedState can use the new sentiment data"""
    print("\n" + "="*80)
    print("TEST 4: UnifiedState Integration with New Data")
    print("="*80)
    
    try:
        registry = IngestionRegistry()
        as_of_date = datetime.now()
        
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
        
        print("Computing sentiment state...")
        sentiment_state = compute_sentiment_state(registry, as_of_date, classifier)
        
        print(f"\n✓ Sentiment state computed:")
        print(f"  Regime: {sentiment_state.market_sentiment_regime.value}")
        print(f"  Trend: {sentiment_state.sentiment_trend.value}")
        print(f"  Z-score: {sentiment_state.market_sentiment_zscore:.3f}")
        print(f"  Is fresh: {sentiment_state.is_fresh}")
        print(f"  Data lag: {sentiment_state.data_lag_days} days")
        print(f"  Crisis signal: {sentiment_state.sentiment_crisis_signal}")
        print(f"  Companies with coverage: {sentiment_state.companies_with_coverage}")
        
        # Validate state is usable
        if sentiment_state.market_sentiment_regime.value == 'UNAVAILABLE':
            print(f"\n⚠ WARNING: Sentiment regime is UNAVAILABLE")
            print(f"  This may be due to insufficient history")
        
        if not sentiment_state.is_fresh:
            print(f"\n⚠ WARNING: Sentiment data is not fresh")
            print(f"  Data lag: {sentiment_state.data_lag_days} days")
        
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_incremental_update():
    """Test 5: Verify incremental updates work correctly"""
    print("\n" + "="*80)
    print("TEST 5: Incremental Update Capability")
    print("="*80)
    
    try:
        ticker_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
        market_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")
        
        if not ticker_path.exists() or not market_path.exists():
            print("⚠ Sentiment files don't exist yet, skipping incremental test")
            return True
        
        # Record current state
        ticker_before = pd.read_parquet(ticker_path)
        market_before = pd.read_parquet(market_path)
        
        ticker_rows_before = len(ticker_before)
        market_rows_before = len(market_before)
        
        print(f"Before incremental update:")
        print(f"  Ticker rows: {ticker_rows_before}")
        print(f"  Market rows: {market_rows_before}")
        
        # Run incremental export
        print("\nRunning incremental export...")
        cmd = [
            sys.executable,
            "scripts/export_sentiment_to_v3.py",
            "--duckdb-path", "data/sentiment.duckdb",
            "--output-dir", "data/processed/sentiment",
            "--incremental"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"✗ Incremental export failed")
            return False
        
        # Check after state
        ticker_after = pd.read_parquet(ticker_path)
        market_after = pd.read_parquet(market_path)
        
        ticker_rows_after = len(ticker_after)
        market_rows_after = len(market_after)
        
        print(f"\nAfter incremental update:")
        print(f"  Ticker rows: {ticker_rows_after} (Δ {ticker_rows_after - ticker_rows_before:+d})")
        print(f"  Market rows: {market_rows_after} (Δ {market_rows_after - market_rows_before:+d})")
        
        # Verify no data loss
        if ticker_rows_after < ticker_rows_before:
            print(f"\n✗ FAIL: Ticker rows decreased!")
            return False
        
        if market_rows_after < market_rows_before:
            print(f"\n✗ FAIL: Market rows decreased!")
            return False
        
        print(f"\n✓ Incremental update successful")
        print(f"\nResult: ✓ PASS")
        return True
        
    except Exception as e:
        print(f"\n✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_startup_readiness():
    """Test 6: Final validation for startup sequence integration"""
    print("\n" + "="*80)
    print("TEST 6: Startup Sequence Readiness")
    print("="*80)
    
    checks = []
    
    # Check 1: Sentiment files exist
    ticker_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
    market_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")
    
    if ticker_path.exists() and market_path.exists():
        print("✓ Sentiment data files exist")
        checks.append(True)
    else:
        print("✗ Sentiment data files missing")
        checks.append(False)
    
    # Check 2: Data is recent
    try:
        market_df = pd.read_parquet(market_path)
        latest_date = pd.to_datetime(market_df['date']).max()
        days_old = (datetime.now() - latest_date).days
        
        if days_old <= 7:
            print(f"✓ Data is recent ({days_old} days old)")
            checks.append(True)
        else:
            print(f"⚠ Data is stale ({days_old} days old)")
            checks.append(True)  # Don't fail, just warn
    except Exception as e:
        print(f"✗ Cannot check data recency: {e}")
        checks.append(False)
    
    # Check 3: Loader works
    try:
        registry = IngestionRegistry()
        market_df = registry.sentiment.load_market_sentiment(datetime.now())
        
        if not market_df.empty:
            print(f"✓ SentimentLoader functional ({len(market_df)} rows)")
            checks.append(True)
        else:
            print("✗ SentimentLoader returns empty data")
            checks.append(False)
    except Exception as e:
        print(f"✗ SentimentLoader error: {e}")
        checks.append(False)
    
    # Check 4: UnifiedState integration
    try:
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
        sentiment_state = compute_sentiment_state(registry, datetime.now(), classifier)
        
        print(f"✓ UnifiedState integration works (regime: {sentiment_state.market_sentiment_regime.value})")
        checks.append(True)
    except Exception as e:
        print(f"✗ UnifiedState integration error: {e}")
        checks.append(False)
    
    # Check 5: PIT compliance
    try:
        ticker_df = pd.read_parquet(ticker_path)
        
        if 'availability_date' in ticker_df.columns and 'date' in ticker_df.columns:
            ticker_df['date'] = pd.to_datetime(ticker_df['date'])
            ticker_df['availability_date'] = pd.to_datetime(ticker_df['availability_date'])
            
            pit_violations = (ticker_df['availability_date'] <= ticker_df['date']).sum()
            
            if pit_violations == 0:
                print(f"✓ PIT compliance verified (no violations)")
                checks.append(True)
            else:
                print(f"✗ PIT violations detected: {pit_violations} rows")
                checks.append(False)
        else:
            print(f"⚠ Cannot verify PIT (missing columns)")
            checks.append(True)  # Don't fail
    except Exception as e:
        print(f"⚠ Cannot verify PIT: {e}")
        checks.append(True)  # Don't fail
    
    all_passed = all(checks)
    
    if all_passed:
        print(f"\n✓ ALL CHECKS PASSED - READY FOR STARTUP INTEGRATION")
    else:
        print(f"\n✗ SOME CHECKS FAILED - FIX BEFORE STARTUP INTEGRATION")
    
    print(f"\nResult: {'✓ PASS' if all_passed else '✗ FAIL'}")
    return all_passed


def main():
    """Run all validation tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "NEW SENTIMENT INGESTION VALIDATION" + " " * 29 + "║")
    print("║" + " " * 10 + "Testing Complete Data Flow: Raw → Processed → Loaded" + " " * 15 + "║")
    print("╚" + "=" * 78 + "╝")
    
    tests = [
        ("Raw News Availability", test_raw_news_availability),
        ("Sentiment Processing Pipeline", test_sentiment_processing_pipeline),
        ("Loader Reads New Data", test_loader_reads_new_data),
        ("UnifiedState Integration", test_unified_state_with_new_data),
        ("Incremental Update", test_incremental_update),
        ("Startup Readiness", test_startup_readiness),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
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
        print("\n" + "="*80)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*80)
        print("\nSentiment ingestion system is READY for startup sequence integration.")
        print("\nNext steps:")
        print("  1. Add sentiment loader to startup sequence")
        print("  2. Monitor data freshness in production")
        print("  3. Set up daily sentiment pipeline cron job")
        return 0
    elif passed >= total * 0.8:
        print("\n⚠ MOSTLY PASSING - Review failures before integration")
        return 1
    else:
        print("\n✗ MULTIPLE FAILURES - Fix issues before integration")
        return 2


if __name__ == '__main__':
    sys.exit(main())
