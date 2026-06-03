"""
Tests for FundamentalLoader - PIT enforcement with reporting lags.

Critical tests:
1. Quarterly reporting lag (60 days)
2. Annual reporting lag (90 days)
3. Column normalization
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.ingestion import IngestionRegistry, PITViolationError


@pytest.fixture
def registry():
    config = {
        'ingestion': {
            'pit': {'enabled': True, 'strict_mode': True},
            'reporting_lags': {
                'quarterly_results': 60,
                'annual_results': 90,
                'shareholding_pattern': 21
            },
            'paths': {}
        }
    }
    return IngestionRegistry(config)


def test_quarterly_reporting_lag(registry):
    """Test that Q1 FY25 results (ended June 30) are NOT available on July 1."""
    # Q1 ended June 30, 2024
    # Results available ~60 days later (late August)
    as_of_date = datetime(2024, 7, 1)
    
    try:
        df = registry.fundamentals.load_financials(
            as_of_date=as_of_date,
            tickers=['RELIANCE'],
            frequency='quarterly'
        )
        
        if not df.empty and 'ReportDate' in df.index.names:
            report_dates = df.index.get_level_values('ReportDate')
            q1_2024 = pd.Timestamp('2024-06-30')
            
            # Q1 2024 should NOT be in the data
            assert q1_2024 not in report_dates, \
                f"Q1 FY25 results should not be available on {as_of_date}"
            
            print(f"✓ Quarterly lag enforced: Q1 2024 not in data as of {as_of_date}")
        else:
            print("⚠ No quarterly data available")
    except FileNotFoundError:
        pytest.skip("Fundamental data not available")


def test_annual_reporting_lag(registry):
    """Test that FY24 annual results (ended March 31) respect 90-day lag."""
    # FY24 ended March 31, 2024
    # Results available ~90 days later (late June/early July)
    as_of_date = datetime(2024, 5, 1)  # Too early
    
    try:
        df = registry.fundamentals.load_financials(
            as_of_date=as_of_date,
            tickers=['RELIANCE'],
            frequency='annual'
        )
        
        if not df.empty and 'ReportDate' in df.index.names:
            report_dates = df.index.get_level_values('ReportDate')
            fy24 = pd.Timestamp('2024-03-31')
            
            # FY24 should NOT be available on May 1
            assert fy24 not in report_dates, \
                f"FY24 results should not be available on {as_of_date} (90-day lag)"
            
            print(f"✓ Annual lag enforced: FY24 not in data as of {as_of_date}")
        else:
            print("⚠ No annual data available")
    except FileNotFoundError:
        pytest.skip("Fundamental data not available")


def test_column_normalization(registry):
    """Test that Screener column names are standardized."""
    as_of_date = datetime.now()
    
    try:
        df = registry.fundamentals.load_financials(
            as_of_date=as_of_date,
            tickers=['RELIANCE'],
            frequency='annual'
        )
        
        if not df.empty:
            # Check for standardized column names (not raw Screener names)
            expected_cols = ['Revenue', 'NetIncome', 'EBITDA', 'TotalAssets', 'Equity']
            found_cols = [c for c in expected_cols if c in df.columns]
            
            if found_cols:
                print(f"✓ Column normalization: found {len(found_cols)} standardized columns")
            else:
                print("⚠ No standardized columns found (may need config)")
        else:
            print("⚠ No fundamental data available")
    except FileNotFoundError:
        pytest.skip("Fundamental data not available")


def test_factor_financials_annual_adapter_uses_annual_observations(registry):
    """Annual factor adapter should not drift into later quarterly rows for the same fiscal year."""
    as_of_date = datetime(2024, 9, 15)

    records = registry.fundamentals.get_factor_financials(
        as_of_date=as_of_date,
        tickers=['RELIANCE'],
        frequency='annual',
        periods=2,
    )
    payload = records.get('RELIANCE.NS') or records.get('RELIANCE') or {}
    current = payload.get('current', {})
    prior = payload.get('prior', {})

    if not current:
        pytest.skip("Annual factor records not available")

    current_report = pd.to_datetime(current.get('report_date'), errors='coerce')
    prior_report = pd.to_datetime(prior.get('report_date'), errors='coerce')

    assert pd.notna(current_report)
    assert current_report.month not in {6, 9, 12}, (
        "Annual factor adapter should select the fiscal-year observation, "
        "not a later quarterly row from the same fiscal year."
    )
    if pd.notna(prior_report):
        assert prior_report <= current_report


def test_factor_financials_reporting_lag_buffer_is_respected(registry):
    """Factor-facing adapter should support a stricter safety lag than raw availability."""
    as_of_date = datetime(2024, 6, 14)

    buffered = registry.fundamentals.get_factor_financials(
        as_of_date=as_of_date,
        tickers=['RELIANCE'],
        frequency='annual',
        periods=2,
        reporting_lag_days=90,
    )
    payload = buffered.get('RELIANCE.NS') or buffered.get('RELIANCE') or {}
    current = payload.get('current', {})
    current_report = pd.to_datetime(current.get('report_date'), errors='coerce')

    if pd.isna(current_report):
        pytest.skip("Annual factor records not available")

    assert current_report <= pd.Timestamp('2023-12-31'), (
        "A 90-day safety lag should keep FY2024 annual data out of the factor-facing "
        "adapter as of 2024-06-14."
    )


if __name__ == '__main__':
    print("=" * 60)
    print("FundamentalLoader Tests")
    print("=" * 60)
    
    registry = IngestionRegistry()
    
    print("\n1. Testing quarterly reporting lag...")
    test_quarterly_reporting_lag(registry)
    
    print("\n2. Testing annual reporting lag...")
    test_annual_reporting_lag(registry)
    
    print("\n3. Testing column normalization...")
    test_column_normalization(registry)
    
    print("\n" + "=" * 60)
