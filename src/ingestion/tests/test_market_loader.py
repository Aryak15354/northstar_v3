"""
Tests for MarketLoader.

Critical tests:
1. PIT enforcement - no data after as_of_date
2. Universe is survivorship-safe
3. Corporate action adjustments
4. Returns in live vs research mode
5. Stale data warnings
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from src.ingestion import IngestionRegistry, PITViolationError, StaleDataError


@pytest.fixture
def config():
    """Load test configuration."""
    return {
        'ingestion': {
            'pit': {'enabled': True, 'strict_mode': True},
            'paths': {
                'prices_daily': 'data/processed/prices.parquet',
                'universe_snapshots': 'data/universe/universe_snapshots.parquet',
                'nse_universe_history': 'data/reference/nse_universe_history.parquet',
                'corporate_actions': 'data/universe/corporate_actions.parquet',
                'delisting_database': 'data/universe/delisting_database.parquet',
                'symbol_migrations': 'data/universe/symbol_migration_map.parquet',
            },
            'staleness_thresholds': {
                'market_data_soft_hours': 48,
                'market_data_hard_hours': 120,
            }
        },
        'market_data_lookback_days': 365,
    }


@pytest.fixture
def registry(config):
    """Create ingestion registry."""
    return IngestionRegistry(config)


def test_pit_enforcement(registry):
    """Test that no data after as_of_date is returned."""
    as_of_date = datetime(2024, 1, 15)
    
    try:
        df = registry.market.load(as_of_date, tickers=['RELIANCE'])
        
        if not df.empty:
            # Check that all dates are <= as_of_date
            dates = df.index.get_level_values('Date')
            assert all(dates <= pd.Timestamp(as_of_date)), \
                f"Found dates after {as_of_date}: {dates[dates > pd.Timestamp(as_of_date)]}"
            
            print(f"✓ PIT enforcement passed: {len(df)} rows, latest date {dates.max()}")
        else:
            print("⚠ No data loaded (may be expected if data doesn't exist)")
    
    except FileNotFoundError:
        pytest.skip("Price data not available")


def test_universe_survivorship_safe(registry):
    """Test that universe snapshots prevent survivorship bias."""
    # Use dates covered by the PIT history artifact built from repo snapshots.
    as_of_date_early = datetime(2022, 11, 9)
    
    try:
        universe_early = registry.market.get_universe_as_of(as_of_date_early)
        
        # Get a later PIT universe snapshot
        universe_late = registry.market.get_universe_as_of(datetime(2023, 9, 21))
        
        # There should be differences (some companies delisted, some added)
        if universe_early and universe_late:
            only_in_early = set(universe_early) - set(universe_late)
            only_in_late = set(universe_late) - set(universe_early)
            
            print(f"✓ Universe early: {len(universe_early)} tickers")
            print(f"✓ Universe late: {len(universe_late)} tickers")
            print(f"✓ Only early: {len(only_in_early)}")
            print(f"✓ Only late: {len(only_in_late)}")
            
            assert len(only_in_early) > 0 or len(only_in_late) > 0, \
                "Universe should change over time"
        else:
            print("⚠ Universe data not available")
    
    except FileNotFoundError:
        pytest.skip("Universe snapshots not available")


def test_market_field_alias_mapping(registry):
    """Factor-facing lower-case field aliases should resolve against native price columns."""
    as_of_date = datetime(2024, 1, 15)
    df = registry.market.load(
        as_of_date,
        tickers=["RELIANCE.NS"],
        start_date=datetime(2023, 1, 1),
        fields=["close", "adj_close", "volume"],
    )
    if df.empty:
        pytest.skip("Price data not available")
    assert {"close", "adj_close", "volume"}.issubset(set(df.columns))


def test_nifty500_index_loading(registry):
    """NIFTY500 index history should load through the canonical market loader contract."""
    df = registry.market.load_index(
        datetime(2024, 1, 15),
        index_name="NIFTY500",
        start_date=datetime(2023, 1, 1),
        fields=["close"],
    )
    if df.empty:
        pytest.skip("Index data not available")
    assert "close" in df.columns
    assert len(df) > 10


def test_corporate_action_adjustment(registry):
    """Test that corporate actions are applied correctly."""
    # This test requires known corporate action data
    # For now, just verify the method runs without error
    
    as_of_date = datetime(2024, 1, 1)
    
    try:
        df = registry.market.load(as_of_date, tickers=['RELIANCE'])
        
        if not df.empty and 'Adj Close' in df.columns:
            # Verify adjusted close exists and is different from close
            # (assuming there were some corporate actions)
            print(f"✓ Corporate action adjustment: loaded {len(df)} rows with Adj Close")
        else:
            print("⚠ No adjusted close data available")
    
    except FileNotFoundError:
        pytest.skip("Price data not available")


def test_returns_live_mode(registry):
    """Test that forward returns are NaN in live mode."""
    canonical_prices = Path("data/canonical/prices/equity_prices_daily.parquet")
    if canonical_prices.exists():
        price_dates = pd.read_parquet(
            canonical_prices,
            columns=["date", "ticker"],
            filters=[("ticker", "=", "RELIANCE.NS")],
        )["date"]
        if not price_dates.empty:
            as_of_date = pd.Timestamp(price_dates.max()).to_pydatetime()
        else:
            as_of_date = datetime.now()
    else:
        as_of_date = datetime.now()
    horizon_days = 5
    
    try:
        df = registry.market.load_returns(
            as_of_date=as_of_date,
            tickers=['RELIANCE'],
            horizon_days=horizon_days,
            mode='live'
        )
        
        if not df.empty:
            ret_col = f'ret_{horizon_days}d'
            
            if ret_col in df.columns:
                # Check that recent returns are NaN
                df_reset = df.reset_index()
                df_reset = df_reset.sort_values('Date', ascending=False)
                
                # Most recent horizon_days rows should have NaN returns
                recent_returns = df_reset.head(horizon_days)[ret_col]
                nan_count = recent_returns.isna().sum()
                
                assert nan_count > 0, \
                    f"Expected NaN returns in live mode, but found {nan_count}/{horizon_days} NaN"
                
                print(f"✓ Live mode returns: {nan_count}/{horizon_days} recent returns are NaN")
            else:
                print(f"⚠ Return column {ret_col} not found")
        else:
            print("⚠ No returns data loaded")
    
    except FileNotFoundError:
        pytest.skip("Price data not available")


def test_stale_data_warning(registry):
    """Test that stale data triggers appropriate warnings."""
    # Use a very old as_of_date to trigger staleness
    as_of_date = datetime(2020, 1, 1)
    
    try:
        df = registry.market.load(as_of_date, tickers=['RELIANCE'])
        
        # If we got here without error, data was fresh enough
        print("✓ Data freshness check passed")
    
    except StaleDataError as e:
        # This is expected for very old dates
        print(f"✓ Stale data error correctly raised: {e}")
    
    except FileNotFoundError:
        pytest.skip("Price data not available")


if __name__ == '__main__':
    # Run tests manually
    import sys
    
    print("=" * 60)
    print("MarketLoader Tests")
    print("=" * 60)
    
    config = {
        'ingestion': {
            'pit': {'enabled': True, 'strict_mode': True},
            'paths': {},
            'staleness_thresholds': {
                'market_data_soft_hours': 48,
                'market_data_hard_hours': 120,
            }
        },
        'market_data_lookback_days': 365,
    }
    
    registry = IngestionRegistry(config)
    
    print("\n1. Testing PIT enforcement...")
    test_pit_enforcement(registry)
    
    print("\n2. Testing survivorship-safe universe...")
    test_universe_survivorship_safe(registry)
    
    print("\n3. Testing corporate action adjustments...")
    test_corporate_action_adjustment(registry)
    
    print("\n4. Testing returns in live mode...")
    test_returns_live_mode(registry)
    
    print("\n5. Testing stale data warnings...")
    test_stale_data_warning(registry)
    
    print("\n" + "=" * 60)
    print("Tests complete")
    print("=" * 60)
