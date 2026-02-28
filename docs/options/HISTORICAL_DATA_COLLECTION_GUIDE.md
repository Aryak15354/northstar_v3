# Historical Option Chain Data Collection Guide

## Overview

This guide explains how to collect historical option chain data for backtesting the options trading system.

## Why Historical Data?

Historical option chain data is essential for:
- **Backtesting strategies** - Test regime detection and strategy generation
- **Validating system logic** - Ensure rules work across different market conditions
- **Performance analysis** - Measure expected returns and risk
- **Parameter optimization** - Tune thresholds and settings

## Data Requirements

For robust backtesting, we need:
- **Minimum**: 90 days (3 months) of data
- **Recommended**: 252 days (1 year) of data
- **Ideal**: 504 days (2 years) of data

### What Data is Collected

For each trading day, we collect:
- Complete option chain (all strikes, both CE and PE)
- Greeks (Delta, Gamma, Theta, Vega)
- Implied Volatility (IV)
- Open Interest (OI) and OI changes
- Bid/Ask prices and quantities
- Last Traded Price (LTP)
- Volume
- Underlying price

## Collection Script

### Basic Usage

```bash
# Collect last 30 days for all indices
python scripts/collect_historical_option_chains.py \
  --days 30 \
  --underlying ALL_INDICES
```

### Collection Options

#### 1. By Time Period

```bash
# Last N days
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying NIFTY

# Specific date range
python scripts/collect_historical_option_chains.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --underlying BANKNIFTY
```

#### 2. By Underlying Type

```bash
# All 4 indices
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying ALL_INDICES

# Top 20 liquid stocks
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying TOP_LIQUID_STOCKS

# All 205 stocks (WARNING: Takes hours!)
python scripts/collect_historical_option_chains.py \
  --days 30 \
  --underlying ALL_STOCKS

# Single stock
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying RELIANCE

# Sector
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying "Financial Services"
```

## Collection Strategy

### Phase 1: Indices (Start Here)

Collect data for all 4 indices first - they're most important for the system.

```bash
# Collect 1 year of data for all indices
python scripts/collect_historical_option_chains.py \
  --days 252 \
  --underlying ALL_INDICES
```

**Time estimate**: ~2-3 hours (with rate limiting)
**Data size**: ~500 MB - 1 GB

### Phase 2: Top Liquid Stocks

```bash
# Collect 90 days for top 20 stocks
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying TOP_LIQUID_STOCKS
```

**Time estimate**: ~3-4 hours
**Data size**: ~1-2 GB

### Phase 3: Sector-Specific (Optional)

If you want to focus on specific sectors:

```bash
# Financial Services (53 stocks)
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying "Financial Services"

# Information Technology (13 stocks)
python scripts/collect_historical_option_chains.py \
  --days 90 \
  --underlying "Information Technology"
```

### Phase 4: All Stocks (Advanced)

Only if you need comprehensive coverage:

```bash
# WARNING: This will take 10-15 hours!
python scripts/collect_historical_option_chains.py \
  --days 30 \
  --underlying ALL_STOCKS
```

## Rate Limiting

Upstox API limits: **1 request per second**

The script automatically:
- Waits 2 seconds between dates
- Waits 10 seconds between underlyings
- Saves incremental progress every 5 days
- Handles errors gracefully

**Do not run multiple collection scripts simultaneously!**

## Output Structure

Data is saved to: `data/options/historical/`

### Files Created

For each underlying:
```
data/options/historical/
├── nifty_option_chains.parquet       # Main data file
├── nifty_summary.txt                 # Collection summary
├── reliance_option_chains.parquet
├── reliance_summary.txt
└── collection_report_YYYYMMDD_HHMMSS.txt  # Overall report
```

### Data Format

Parquet files contain:
- `date` - Trading date
- `symbol` - Underlying symbol
- `expiry` - Option expiry date
- `strike` - Strike price
- `option_type` - 'CE' or 'PE'
- `bid`, `ask`, `ltp` - Prices
- `bid_qty`, `ask_qty` - Quantities
- `iv` - Implied Volatility
- `delta`, `gamma`, `theta`, `vega` - Greeks
- `oi` - Open Interest
- `change_oi` - OI change
- `volume` - Trading volume
- `underlying_price` - Spot price
- `days_to_expiry` - Days until expiry

## Monitoring Progress

The script logs to:
- Console (real-time progress)
- `logs/historical_collection.log` (detailed log)

Watch progress:
```bash
tail -f logs/historical_collection.log
```

## Handling Interruptions

The script saves incremental progress every 5 days. If interrupted:

1. Check what was collected:
```bash
ls -lh data/options/historical/
```

2. Resume from where it stopped:
```bash
# If you were collecting NIFTY from 2024-01-01 to 2024-12-31
# and it stopped at 2024-06-15, resume with:
python scripts/collect_historical_option_chains.py \
  --start-date 2024-06-16 \
  --end-date 2024-12-31 \
  --underlying NIFTY
```

3. Merge files if needed (see Data Management section)

## Data Validation

After collection, validate the data:

```bash
python scripts/validate_historical_data.py --underlying NIFTY
```

Checks:
- No missing dates (accounting for weekends/holidays)
- No duplicate records
- Valid Greeks (no NaN values)
- Temporal consistency (expiry >= date)
- Reasonable IV ranges (5% - 200%)

## Data Management

### Check Data Size

```bash
du -sh data/options/historical/
```

### View Summary

```bash
cat data/options/historical/nifty_summary.txt
```

### Load Data in Python

```python
import pandas as pd

# Load NIFTY data
df = pd.read_parquet('data/options/historical/nifty_option_chains.parquet')

print(f"Records: {len(df):,}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Trading days: {df['date'].nunique()}")
```

### Merge Multiple Collections

If you collected data in chunks:

```python
import pandas as pd
from pathlib import Path

# Load all NIFTY files
files = Path('data/options/historical').glob('nifty_*.parquet')
dfs = [pd.read_parquet(f) for f in files]

# Merge and deduplicate
merged = pd.concat(dfs, ignore_index=True)
merged = merged.drop_duplicates(
    subset=['date', 'symbol', 'expiry', 'strike', 'option_type']
)
merged = merged.sort_values(['date', 'expiry', 'strike', 'option_type'])

# Save merged file
merged.to_parquet('data/options/historical/nifty_option_chains.parquet', index=False)
```

## Troubleshooting

### "Access token expired"

Upstox tokens expire daily. Generate a new token:
1. Go to Upstox Developer Console
2. Generate new access token
3. Update `.env.options` file
4. Restart collection

### "Rate limit exceeded"

The script should handle this automatically. If you see this error:
- Wait 5 minutes
- Restart the script
- It will resume from where it stopped

### "Empty option chain"

This is normal for:
- Weekends and holidays
- Very old dates (before options were introduced)
- Stocks with low liquidity

The script skips these automatically.

### "No expiry found"

For historical dates, the script approximates expiries:
- Indices: Next Thursday
- Stocks: Last Thursday of month

This is a limitation of historical data collection.

## Best Practices

1. **Start small** - Test with 30 days for one underlying first
2. **Run overnight** - Large collections take hours
3. **Monitor logs** - Watch for errors
4. **Validate data** - Always run validation after collection
5. **Backup data** - Copy to external storage
6. **Document gaps** - Note any missing date ranges

## Estimated Collection Times

| Scope | Days | Time | Data Size |
|-------|------|------|-----------|
| 1 Index | 30 | 15 min | 50 MB |
| 1 Index | 90 | 45 min | 150 MB |
| 1 Index | 252 | 2 hours | 400 MB |
| 4 Indices | 90 | 3 hours | 600 MB |
| 4 Indices | 252 | 8 hours | 1.6 GB |
| 20 Stocks | 90 | 4 hours | 1.5 GB |
| 205 Stocks | 30 | 12 hours | 3 GB |
| 205 Stocks | 90 | 36 hours | 9 GB |

*Times include rate limiting delays*

## Next Steps

After collecting historical data:

1. **Validate data quality**
```bash
python scripts/validate_historical_data.py --underlying ALL_INDICES
```

2. **Run backtests**
```bash
python scripts/backtest_options_system.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --underlying NIFTY
```

3. **Analyze results**
```bash
python scripts/analyze_backtest_results.py \
  --report data/options/backtest_reports/nifty_backtest_20240101_20241231.json
```

## Support

For issues or questions:
- Check logs: `logs/historical_collection.log`
- Review summary files in `data/options/historical/`
- Validate data quality with validation script

---

**Important**: Historical option chain data from Upstox API may have limitations:
- Greeks might be calculated, not actual historical values
- Bid/ask spreads might not reflect actual market conditions
- Some old data might be missing or incomplete

For production trading, always validate strategies with recent live data before deployment.
