# Unified Data Ingestion Layer for Northstar V3

## Overview

The unified data ingestion layer is the **single, authoritative gateway** for all data access in the Northstar V3 system. It replaces scattered data loading logic across multiple modules with a centralized, consistent, and PIT-compliant approach.

## Key Features

1. **Point-in-Time (PIT) Compliance**: Enforces temporal discipline to prevent lookahead bias
2. **Data Freshness Checking**: Detects stale data with configurable thresholds
3. **Standardized Return Types**: Always returns pandas DataFrame or Series
4. **Structured Logging**: Tracks loader name, as_of_date, rows returned, load time
5. **LRU Caching**: Avoids redundant disk reads within a single run
6. **Graceful Error Handling**: Returns empty DataFrames with correct schema on errors

## Architecture

```
src/ingestion/
├── __init__.py                  # Public API exports
├── base_loader.py               # Abstract base class for all loaders
├── market_loader.py             # Daily price data + corporate actions
├── fundamental_loader.py        # Screener.in fundamentals with reporting lags
├── macro_loader.py              # RBI macro data with release calendar
├── alternative_loader.py        # GST, power, credit, bulk deals, pledges
├── sentiment_loader.py          # Company and market sentiment
├── options_loader.py            # Historical and live option chains
├── ingestion_registry.py        # Single entry point (facade)
└── tests/                       # Test suite
    ├── test_market_loader.py
    ├── test_fundamental_loader.py
    └── ...
```

## Usage

### Basic Usage

```python
from src.ingestion import IngestionRegistry
from datetime import datetime

# Initialize registry (loads config automatically)
registry = IngestionRegistry()

# Or provide custom config
registry = IngestionRegistry(config=my_config)

# Load market data
as_of_date = datetime(2024, 1, 15)
prices = registry.market.load(
    as_of_date=as_of_date,
    tickers=['RELIANCE', 'TCS', 'INFY'],
    fields=['Open', 'High', 'Low', 'Close', 'Volume']
)

# Load fundamentals
fundamentals = registry.fundamentals.load_financials(
    as_of_date=as_of_date,
    tickers=['RELIANCE'],
    statement_type='income_statement',
    frequency='annual'
)

# Load macro data
macro = registry.macro.load_rbi_data(
    as_of_date=as_of_date,
    indicators=['cpi', 'iip', 'gdp']
)

# Load alternative data
alt_data = registry.alternative.load_all_alternative(
    as_of_date=as_of_date,
    tickers=['RELIANCE']
)

# Load sentiment
sentiment = registry.sentiment.load_company_sentiment(
    as_of_date=as_of_date,
    tickers=['RELIANCE'],
    lookback_days=30
)

# Load options
options = registry.options.load_historical_chains(
    as_of_date=as_of_date,
    underlying='NIFTY'
)
```

### Health Check

```python
# Check data freshness and availability
health = registry.health_check(as_of_date=datetime.now())

for source, status in health.items():
    print(f"{source}: {status['status']}")
    if status['warning']:
        print(f"  Warning: {status['warning']}")
```

### Data Lineage Report

```python
# Generate audit report
report = registry.get_data_lineage_report(as_of_date=datetime.now())

print(f"Universe size: {report['data_sources']['market']['universe_size']}")
print(f"Tickers with data: {report['data_sources']['market']['tickers_with_data']}")
```

## Point-in-Time (PIT) Enforcement

### Why PIT Matters

Lookahead bias is the #1 cause of backtest overfitting. The ingestion layer prevents this by:

1. **Filtering data by as_of_date**: Only returns data available on or before the specified date
2. **Applying reporting lags**: Fundamentals have 60-90 day lags, macro has indicator-specific lags
3. **Validating temporal consistency**: Raises `PITViolationError` if any row has a date after as_of_date

### Reporting Lags

| Data Type | Lag (days) | Rationale |
|-----------|------------|-----------|
| Quarterly results | 60 | Companies report ~45-60 days after quarter end |
| Annual results | 90 | Annual reports take up to 90 days |
| Shareholding pattern | 21 | Published ~21 days after quarter end |
| GST data | 15 | Released ~10-15 days after month end |
| CPI | 12 | Released ~12 days after month end |
| IIP | 42 | Released ~6 weeks after month end |
| GDP | 60 | Released ~2 months after quarter end |
| Sentiment | 1 | Today's sentiment uses yesterday's news |

### Example: Fundamental PIT Enforcement

```python
# Load financials as of July 1, 2024
as_of_date = datetime(2024, 7, 1)
df = registry.fundamentals.load_financials(as_of_date)

# Q1 FY25 ended June 30, 2024
# With 60-day lag, results available ~August 29, 2024
# Therefore, Q1 FY25 results will NOT be in the returned data
# This prevents lookahead bias
```

## Data Freshness

The system checks file modification times and emits warnings/errors based on staleness thresholds:

| Data Source | Soft Threshold | Hard Threshold |
|-------------|----------------|----------------|
| Market data | 48 hours | 120 hours |
| Macro data | 168 hours (1 week) | 720 hours (30 days) |
| Sentiment | 72 hours | N/A |
| Options | 24 hours | N/A |

- **Soft threshold**: Emits `StaleDataWarning` (logged but doesn't raise)
- **Hard threshold**: Raises `StaleDataError` (blocks execution)

## Configuration

Add this to your `config.yaml`:

```yaml
ingestion:
  cache_ttl_seconds: 300
  
  staleness_thresholds:
    market_data_soft_hours: 48
    market_data_hard_hours: 120
    macro_data_soft_hours: 168
    macro_data_hard_hours: 720
    sentiment_soft_hours: 72
    options_soft_hours: 24
  
  pit:
    enabled: true
    strict_mode: true
  
  reporting_lags:
    quarterly_results: 60
    annual_results: 90
    shareholding_pattern: 21
  
  paths:
    prices_daily: "data/processed/prices.parquet"
    screener_financials: "data/raw/vendors/screener/financials"
    macro: "data/macro"
    # ... (see config/ingestion_config.yaml for full list)
```

## Testing

Run the test suite:

```bash
# Run all ingestion tests
pytest src/ingestion/tests/

# Run specific test file
pytest src/ingestion/tests/test_market_loader.py

# Run with verbose output
pytest src/ingestion/tests/ -v

# Run specific test
pytest src/ingestion/tests/test_market_loader.py::test_pit_enforcement
```

### Critical Tests

1. **test_pit_enforcement**: Verifies no data after as_of_date
2. **test_universe_survivorship_safe**: Verifies universe changes over time
3. **test_corporate_action_adjustment**: Verifies splits/dividends applied
4. **test_returns_live_mode**: Verifies forward returns are NaN in live mode
5. **test_quarterly_reporting_lag**: Verifies 60-day lag for quarterly results
6. **test_research_and_live_feature_parity**: Verifies research and live paths produce identical features

## Migration Guide

### Before (Scattered Loading)

```python
# Old way - each module loads data independently
import pandas as pd

# In intelligence_stack.py
prices = pd.read_parquet('data/processed/prices.parquet')
fundamentals = pd.read_csv('data/processed/screener_fundamentals_annual.csv')

# In research/dataset_manager.py
prices = pd.read_parquet('data/processed/prices.parquet')  # Different path?
fundamentals = load_fundamentals_artifact()  # Different loader?

# Result: Different data, different PIT enforcement, different bugs
```

### After (Unified Loading)

```python
# New way - single entry point
from src.ingestion import IngestionRegistry

registry = IngestionRegistry()

# In intelligence_stack.py
prices = registry.market.load(as_of_date=today)
fundamentals = registry.fundamentals.load_financials(as_of_date=today)

# In research/dataset_manager.py
prices = registry.market.load(as_of_date=today)
fundamentals = registry.fundamentals.load_financials(as_of_date=today)

# Result: Same data, same PIT enforcement, same correctness
```

### Refactoring Checklist

- [ ] Replace all `pd.read_parquet()` calls with `registry.market.load()`
- [ ] Replace all `pd.read_csv()` calls with appropriate loader
- [ ] Remove custom PIT enforcement logic (now handled by loaders)
- [ ] Remove custom freshness checks (now handled by loaders)
- [ ] Remove file path strings (now in config)
- [ ] Add `as_of_date` parameter to all data loading calls
- [ ] Run integration test to verify feature parity

## Error Handling

The ingestion layer defines custom exceptions:

```python
from src.ingestion import (
    PITViolationError,      # Lookahead bias detected
    StaleDataError,         # Data too old (hard threshold)
    StaleDataWarning,       # Data old (soft threshold)
    DataNotFoundError,      # Expected file doesn't exist
    DataSchemaError,        # Data doesn't match expected schema
)

try:
    df = registry.market.load(as_of_date)
except PITViolationError as e:
    # Critical: lookahead bias detected
    logger.error(f"PIT violation: {e}")
    raise
except StaleDataError as e:
    # Critical: data too old
    logger.error(f"Stale data: {e}")
    # Fall back to cached data or abort
except DataNotFoundError as e:
    # Expected file missing
    logger.warning(f"Data not found: {e}")
    # Return empty DataFrame or use fallback
```

## Performance

### Caching

The ingestion layer uses in-memory LRU caching with configurable TTL:

```python
# First call: loads from disk
df1 = registry.market.load(as_of_date, tickers=['RELIANCE'])  # ~500ms

# Second call within TTL: returns cached copy
df2 = registry.market.load(as_of_date, tickers=['RELIANCE'])  # ~1ms

# After TTL expires: reloads from disk
time.sleep(301)  # TTL is 300 seconds
df3 = registry.market.load(as_of_date, tickers=['RELIANCE'])  # ~500ms
```

### Clear Cache

```python
# Clear cache for a specific loader
registry.market.clear_cache()

# Clear all caches
registry.clear_all_caches()
```

## Extending the Ingestion Layer

To add a new data source:

1. Create a new loader class inheriting from `BaseLoader`
2. Implement the `load()` method
3. Add PIT enforcement using `self._validate_pit()`
4. Add freshness checking using `self._check_freshness()`
5. Register the loader in `IngestionRegistry`
6. Add configuration paths to `config/ingestion_config.yaml`
7. Write tests in `src/ingestion/tests/`

Example:

```python
from .base_loader import BaseLoader

class MyNewLoader(BaseLoader):
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        # Load data
        df = pd.read_parquet(self._resolve_path('my_data'))
        
        # PIT enforcement
        df = df[df['Date'] <= as_of_date]
        self._validate_pit(df, 'Date', as_of_date)
        
        # Freshness check
        self._check_freshness(
            self._resolve_path('my_data'),
            max_age_hours=24
        )
        
        return df
```

## Troubleshooting

### "PITViolationError: Found dates after as_of_date"

**Cause**: Data contains future dates (lookahead bias)

**Solution**: Check the data source for incorrect dates or disable strict mode temporarily to debug

### "StaleDataError: Data critically stale"

**Cause**: Data file hasn't been updated recently

**Solution**: Run the data update pipeline or adjust staleness thresholds

### "DataNotFoundError: Data file not found"

**Cause**: Expected data file doesn't exist

**Solution**: Check file paths in config, run data collection scripts

### Empty DataFrame returned

**Cause**: No data available for the specified as_of_date or tickers

**Solution**: Check data availability, verify as_of_date is within data range

## Best Practices

1. **Always specify as_of_date**: Never load data without a point-in-time date
2. **Use strict PIT mode in production**: Set `pit.strict_mode: true` in config
3. **Monitor data freshness**: Run `health_check()` before critical operations
4. **Cache appropriately**: Use default TTL for most cases, clear cache when needed
5. **Test feature parity**: Verify research and live paths produce identical results
6. **Log data lineage**: Use `get_data_lineage_report()` for audit trails
7. **Handle errors gracefully**: Catch specific exceptions and provide fallbacks

## Success Criteria

The ingestion layer is considered complete when:

- [x] All loaders implemented (market, fundamentals, macro, alternative, sentiment, options)
- [x] PIT enforcement working correctly
- [x] Freshness checking implemented
- [x] Caching working
- [x] Configuration system in place
- [ ] All tests passing
- [ ] Existing modules refactored to use registry
- [ ] Feature parity test passing (research vs live)
- [ ] Documentation complete
- [ ] Health check integrated into startup sequence

## Next Steps

1. Run the test suite and fix any failures
2. Refactor `src/intelligence/data_pipeline.py` to use registry
3. Refactor `src/research/dataset_manager.py` to use registry
4. Run feature parity integration test
5. Wire `health_check()` into `START_LIVE_SYSTEM.sh`
6. Update all data loading calls across the codebase
7. Remove old data loading code

## Support

For questions or issues:
- Check this README first
- Review test files for usage examples
- Check logs for detailed error messages
- Consult the main system documentation
