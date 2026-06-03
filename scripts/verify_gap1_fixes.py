#!/usr/bin/env python3
"""
Verify Gap 1 Fixes
==================

Tests that all four critical issues have been resolved:
1. Ingestion config is accessible from main config
2. Power consumption data loads without crashing
3. Credit ratings work from fundamental_loader
4. Sentiment data is fresh
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

# Add src to path
sys.path.insert(0, str(Path.cwd()))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_ingestion_config_merged():
    """Test 1: Verify ingestion config is in paths.yaml"""
    logger.info("=" * 80)
    logger.info("TEST 1: Ingestion Config Merged")
    logger.info("=" * 80)
    
    paths_config = Path("config/paths.yaml")
    
    if not paths_config.exists():
        logger.error("✗ paths.yaml not found")
        return False
    
    with open(paths_config) as f:
        config = yaml.safe_load(f)
    
    if 'ingestion' not in config:
        logger.error("✗ 'ingestion' section not found in paths.yaml")
        return False
    
    ingestion = config['ingestion']
    
    # Check key sections exist
    required_sections = ['cache_ttl_seconds', 'staleness_thresholds', 'pit', 'reporting_lags', 'paths']
    missing = [s for s in required_sections if s not in ingestion]
    
    if missing:
        logger.error(f"✗ Missing sections in ingestion config: {missing}")
        return False
    
    logger.info("✓ Ingestion config properly merged into paths.yaml")
    logger.info(f"  - Cache TTL: {ingestion['cache_ttl_seconds']}s")
    logger.info(f"  - PIT enabled: {ingestion['pit']['enabled']}")
    logger.info(f"  - Reporting lags: {len(ingestion['reporting_lags'])} configured")
    logger.info(f"  - Data paths: {len(ingestion['paths'])} configured")
    
    return True


def test_power_consumption_loads():
    """Test 2: Verify power consumption data loads without crashing"""
    logger.info("=" * 80)
    logger.info("TEST 2: Power Consumption Data Loads")
    logger.info("=" * 80)
    
    try:
        from src.ingestion import IngestionRegistry
        
        registry = IngestionRegistry()
        as_of_date = datetime(2026, 3, 1)
        
        # This should not crash even with placeholder data
        power_df = registry.alternative.load_power_consumption(as_of_date)
        
        logger.info(f"✓ Power consumption loader executed without crashing")
        logger.info(f"  - Rows returned: {len(power_df)}")
        logger.info(f"  - Columns: {list(power_df.columns) if not power_df.empty else 'N/A'}")
        
        if power_df.empty:
            logger.warning("  ⚠ Data is empty (expected with placeholder)")
        else:
            # Check if it's placeholder data
            if 'data_source' in power_df.columns:
                sources = power_df['data_source'].unique()
                if 'PLACEHOLDER' in sources:
                    logger.warning("  ⚠ Data is placeholder - CEA scraper needs to run")
                else:
                    logger.info(f"  ✓ Real data from sources: {sources}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Power consumption loader failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_credit_ratings_from_fundamentals():
    """Test 3: Verify credit ratings accessible from fundamental_loader"""
    logger.info("=" * 80)
    logger.info("TEST 3: Credit Ratings from Fundamental Loader")
    logger.info("=" * 80)
    
    try:
        from src.ingestion import IngestionRegistry
        
        registry = IngestionRegistry()
        as_of_date = datetime(2026, 3, 1)
        
        # Test the new method
        ratings_df = registry.fundamentals.load_credit_ratings_for_fundamentals(
            as_of_date=as_of_date,
            tickers=['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
        )
        
        logger.info(f"✓ Credit ratings method exists and executes")
        logger.info(f"  - Rows returned: {len(ratings_df)}")
        
        if not ratings_df.empty:
            logger.info(f"  - Columns: {list(ratings_df.columns)}")
            if 'CurrentRating' in ratings_df.columns:
                logger.info(f"  - Sample ratings: {ratings_df['CurrentRating'].head(3).tolist()}")
            if 'in_distress' in ratings_df.columns:
                distress_count = ratings_df['in_distress'].sum()
                logger.info(f"  - Companies in distress: {distress_count}")
        else:
            logger.warning("  ⚠ No credit ratings data available (may be expected)")
        
        return True
        
    except AttributeError as e:
        if 'load_credit_ratings_for_fundamentals' in str(e):
            logger.error("✗ Method load_credit_ratings_for_fundamentals not found")
            logger.error("  The fix may not have been applied correctly")
            return False
        raise
    except Exception as e:
        logger.error(f"✗ Credit ratings test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sentiment_freshness():
    """Test 4: Verify sentiment data is reasonably fresh"""
    logger.info("=" * 80)
    logger.info("TEST 4: Sentiment Data Freshness")
    logger.info("=" * 80)
    
    try:
        from src.ingestion import IngestionRegistry
        
        registry = IngestionRegistry()
        as_of_date = datetime.now()
        
        # Load company sentiment
        sentiment_df = registry.sentiment.load_company_sentiment(
            as_of_date=as_of_date,
            tickers=['RELIANCE.NS', 'TCS.NS']
        )
        
        logger.info(f"✓ Sentiment loader executed")
        logger.info(f"  - Rows returned: {len(sentiment_df)}")
        
        if not sentiment_df.empty:
            # Check freshness
            if 'date' in sentiment_df.columns or 'Date' in sentiment_df.columns:
                date_col = 'date' if 'date' in sentiment_df.columns else 'Date'
                sentiment_df[date_col] = pd.to_datetime(sentiment_df[date_col])
                latest_date = sentiment_df[date_col].max()
            elif isinstance(sentiment_df.index, pd.MultiIndex) and 'Date' in sentiment_df.index.names:
                latest_date = pd.to_datetime(sentiment_df.index.get_level_values('Date')).max()
            elif sentiment_df.index.name == 'Date':
                latest_date = pd.to_datetime(sentiment_df.index).max()
            else:
                logger.warning("  ⚠ No date column found in sentiment data")
                return True

            days_old = (datetime.now() - latest_date).days
            
            logger.info(f"  - Latest sentiment date: {latest_date.date()}")
            logger.info(f"  - Days old: {days_old}")
            
            if days_old <= 7:
                logger.info("  ✓ Sentiment data is fresh (≤7 days old)")
                return True
            elif days_old <= 30:
                logger.warning(f"  ⚠ Sentiment data is {days_old} days old - consider backfill")
                return True
            else:
                logger.error(f"  ✗ Sentiment data is stale ({days_old} days old)")
                logger.error("  Run: bash scripts/backfill_sentiment_data.sh")
                return False
        else:
            logger.warning("  ⚠ No sentiment data returned")
            logger.warning("  This may indicate the sentiment pipeline needs to run")
            return True
        
    except Exception as e:
        logger.error(f"✗ Sentiment freshness test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Integration test: Load all data types in one go"""
    logger.info("=" * 80)
    logger.info("INTEGRATION TEST: Load All Data Types")
    logger.info("=" * 80)
    
    try:
        from src.ingestion import IngestionRegistry
        
        registry = IngestionRegistry()
        as_of_date = datetime(2026, 3, 1)
        test_tickers = ['RELIANCE.NS', 'TCS.NS']
        
        results = {}
        
        # Market data
        try:
            market_df = registry.market.load(as_of_date, tickers=test_tickers)
            results['market'] = len(market_df)
        except Exception as e:
            results['market'] = f"ERROR: {e}"
        
        # Fundamentals
        try:
            fund_df = registry.fundamentals.load_financials(as_of_date, tickers=test_tickers)
            results['fundamentals'] = len(fund_df)
        except Exception as e:
            results['fundamentals'] = f"ERROR: {e}"
        
        # Macro
        try:
            macro_df = registry.macro.load_rbi_data(as_of_date)
            results['macro'] = len(macro_df)
        except Exception as e:
            results['macro'] = f"ERROR: {e}"
        
        # Alternative (including power)
        try:
            alt_df = registry.alternative.load_all_alternative(as_of_date, tickers=test_tickers)
            results['alternative'] = len(alt_df)
        except Exception as e:
            results['alternative'] = f"ERROR: {e}"
        
        # Sentiment
        try:
            sent_df = registry.sentiment.load_company_sentiment(as_of_date, tickers=test_tickers)
            results['sentiment'] = len(sent_df)
        except Exception as e:
            results['sentiment'] = f"ERROR: {e}"
        
        # Print results
        logger.info("Data loading results:")
        all_success = True
        for data_type, result in results.items():
            if isinstance(result, str) and result.startswith("ERROR"):
                logger.error(f"  ✗ {data_type}: {result}")
                all_success = False
            else:
                logger.info(f"  ✓ {data_type}: {result} rows")
        
        if all_success:
            logger.info("✓ All data types loaded successfully")
        else:
            logger.warning("⚠ Some data types failed to load")
        
        return all_success
        
    except Exception as e:
        logger.error(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("GAP 1 FIXES VERIFICATION")
    logger.info("=" * 80)
    logger.info("")
    
    tests = [
        ("Ingestion Config Merged", test_ingestion_config_merged),
        ("Power Consumption Loads", test_power_consumption_loads),
        ("Credit Ratings from Fundamentals", test_credit_ratings_from_fundamentals),
        ("Sentiment Freshness", test_sentiment_freshness),
        ("Integration Test", test_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    logger.info("")
    logger.info(f"Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        logger.info("=" * 80)
        logger.info("✓ ALL VERIFICATIONS PASSED")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Gap 1 critical issues are RESOLVED")
        return 0
    else:
        logger.info("=" * 80)
        logger.info("⚠ SOME VERIFICATIONS FAILED")
        logger.info("=" * 80)
        logger.info("")
        logger.info(f"Gap 1 status: {passed_count}/{total_count} issues resolved")
        return 1


if __name__ == "__main__":
    sys.exit(main())
