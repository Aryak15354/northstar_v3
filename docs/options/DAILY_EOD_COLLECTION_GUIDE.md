# Daily EOD Option Chain Collection Guide

## The Reality: No Historical Data from Upstox API

**Important Discovery**: Upstox API does **NOT** provide historical option chain data. The `/v2/option/chain` endpoint only returns current/live market data.

This is a common limitation across broker APIs - they provide real-time data, not historical time-series data.

## Solution: Daily EOD Collection

Instead of fetching historical data, we **collect data daily** going forward. This builds a historical database over time.

### How It Works

1. **After market close** (3:30 PM IST), run the EOD collector
2. Script fetches today's option chain data
3. Data is appended to historical parquet files
4. Over time, you build a comprehensive historical database

## Setup Daily Collection

### Manual Run (Test First)

```bash
# Test with single underlying
python scripts/daily_eod_option_chain_collector.py --underlying NIFTY

# Collect all indices
python scripts/daily_eod_option_chain_collector.py --underlying ALL_INDICES

# Collect top stocks
python scripts/daily_eod_option_chain_collector.py --underlying TOP_LIQUID_STOCKS
```

### Automated with Cron (Recommended)

#### 1. Make script executable
```bash
chmod +x scripts/daily_eod_option_chain_collector.py
```

#### 2. Create wrapper script
```bash
cat > scripts/run_daily_eod_collection.sh << 'EOF'
#!/bin/bash

# Daily EOD Collection Wrapper
# Activates conda environment and runs collection

cd /path/to/northstar_v3

# Activate conda environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate northstar_v7_env_m1

# Run collection
python scripts/daily_eod_option_chain_collector.py --underlying ALL_INDICES

# Optional: Also collect top stocks
# python scripts/daily_eod_option_chain_collector.py --underlying TOP_LIQUID_STOCKS

EOF

chmod +x scripts/run_daily_eod_collection.sh
```

#### 3. Setup cron job
```bash
# Edit crontab
crontab -e

# Add this line (runs at 4:00 PM IST, Monday-Friday)
0 16 * * 1-5 /path/to/northstar_v3/scripts/run_daily_eod_collection.sh >> /path/to/northstar_v3/logs/cron_eod_collection.log 2>&1
```

**Cron Schedule Explained**:
- `0 16 * * 1-5` = 4:00 PM, Monday to Friday
- Runs after market close (3:30 PM)
- Skips weekends automatically

#### 4. Verify cron is set
```bash
crontab -l
```

## What Gets Collected

For each trading day:
- Complete option chain (all strikes, CE & PE)
- Greeks (Delta, Gamma, Theta, Vega)
- Implied Volatility
- Open Interest & OI changes
- Bid/Ask prices & quantities
- Volume & LTP
- Underlying price

## Data Accumulation

| Days | Data Size (4 indices) | Data Size (20 stocks) |
|------|----------------------|----------------------|
| 30 | ~200 MB | ~500 MB |
| 90 | ~600 MB | ~1.5 GB |
| 252 | ~1.6 GB | ~4 GB |
| 504 | ~3.2 GB | ~8 GB |

## Monitoring

### Check if collection ran
```bash
tail -50 logs/daily_eod_collection.log
```

### View collected data
```bash
ls -lh data/options/historical/
```

### Check data for specific underlying
```python
import pandas as pd

df = pd.read_parquet('data/options/historical/nifty_option_chains.parquet')
print(f"Records: {len(df):,}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Trading days: {df['date'].nunique()}")
```

## Alternative: Third-Party Data Sources

If you need historical data immediately, consider:

### 1. NSE Historical Data
- NSE provides historical option data
- Download from: https://www.nseindia.com/
- Format: CSV files (need parsing)
- Free but requires manual download

### 2. Commercial Data Providers
- **TrueData**: Historical options data
- **Algomojo**: Historical tick data
- **QuantInsti**: Historical options database
- Cost: ₹5,000 - ₹50,000/year

### 3. Web Scraping (Advanced)
- Scrape historical data from NSE website
- Requires handling CAPTCHAs and rate limits
- Legal gray area - check NSE terms

### 4. Options Backtesting Platforms
- **Opstra**: Has historical data
- **Sensibull**: Historical options analytics
- **Quantsapp**: Historical options database

## Recommended Approach

### Phase 1: Start Daily Collection (Today)
```bash
# Setup cron job
crontab -e

# Add daily collection at 4 PM
0 16 * * 1-5 /path/to/scripts/run_daily_eod_collection.sh
```

### Phase 2: Get Recent Historical Data (Optional)
If you need data from the past:
1. Check NSE website for downloadable historical data
2. Consider commercial providers for comprehensive data
3. Use daily collection going forward

### Phase 3: Build Database Over Time
- After 30 days: Enough for initial backtesting
- After 90 days: Good for strategy validation
- After 252 days: Comprehensive 1-year dataset

## Troubleshooting

### Cron job not running?
```bash
# Check cron service
ps aux | grep cron

# Check cron logs (macOS)
log show --predicate 'process == "cron"' --last 1h

# Test script manually
./scripts/run_daily_eod_collection.sh
```

### Empty data collected?
- Market might be closed
- Check if it's a holiday
- Verify Upstox token is valid
- Check logs for errors

### Token expired?
Upstox tokens expire daily. Options:
1. Regenerate token daily (manual)
2. Implement OAuth refresh flow (advanced)
3. Use long-lived API keys if available

## Best Practices

1. **Run after market close** (4:00 PM IST)
2. **Monitor logs daily** for first week
3. **Validate data weekly** with validation script
4. **Backup data monthly** to external storage
5. **Document gaps** (holidays, failures)

## Data Validation

Run weekly to ensure quality:
```bash
python scripts/validate_historical_data.py --underlying ALL_INDICES
```

## Summary

**Reality**: Upstox API doesn't provide historical data

**Solution**: Daily EOD collection builds historical database over time

**Timeline**:
- Day 1: Setup cron job
- Day 30: Enough data for initial backtesting
- Day 90: Good dataset for strategy validation
- Day 252: Comprehensive 1-year historical database

**Start today** to begin building your historical options database!

---

**Note**: The original `collect_historical_option_chains.py` script won't work for past dates due to API limitations. Use `daily_eod_option_chain_collector.py` instead for ongoing collection.
