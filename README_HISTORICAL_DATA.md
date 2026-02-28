# Historical Option Chain Data Collection

## 🎯 Quick Start

### Build Offline Universe With Groww (NIFTY500 + Indices)
```bash
export GROWW_API_KEY="your_api_key"
export GROWW_API_SECRET="your_api_secret"
python scripts/build_groww_option_universe.py --days 45 --underlyings NIFTY500_PLUS_INDICES
```

This writes engine-ready files to `data/options/historical/*_option_chains.parquet`.
For 5 years (chunked automatically into Groww-compatible windows):
```bash
python scripts/build_groww_option_universe.py \
  --years 5 \
  --end-date 2026-02-13 \
  --underlyings NIFTY500_PLUS_INDICES
```

If you get `403 Access forbidden for this request`, run:
```bash
python scripts/diagnose_groww_permissions.py
```
Your Groww token must include historical/backtesting permission; live-data-only
roles will fail for `/historical/*` endpoints.

To test the exact Python SDK call path (`GrowwAPI.get_historical_candle_data`) before full build:
```bash
python3 scripts/test_groww_sdk_historical.py \
  --symbol RELIANCE \
  --segment CASH \
  --start-time "2026-02-10 09:15:00" \
  --end-time "2026-02-10 15:30:00" \
  --interval-minutes 5
```

To force universe builder candle pulls through Python SDK:
```bash
python3 scripts/build_groww_option_universe.py \
  --years 5 \
  --underlyings NIFTY500_PLUS_INDICES \
  --use-python-sdk \
  --no-contracts-api
```

For multi-horizon collection in one go (daily + weekly + 5-minute):
```bash
python3 scripts/build_groww_option_universe_multi_horizon.py \
  --underlyings NIFTY500_PLUS_INDICES \
  --daily-years 3 \
  --weekly-years 10 \
  --intraday-days 90 \
  --use-python-sdk \
  --no-contracts-api
```

SDK historical interval limits are enforced in chunking logic (from Groww docs):
- `1minute`: 7 days
- `5minute`: 15 days
- `10minute`: 30 days
- `60minute`: 150 days
- `240minute`: 365 days
- `1day`: 1080 days
- `1week`: long history (script chunks conservatively)

If you have an older contracts dump (with columns like `trading_symbol`,
`groww_symbol`, `expiry_date`, `strike_price`), merge it during build:
```bash
python3 scripts/build_groww_option_universe.py \
  --days 45 \
  --underlyings BANKNIFTY,BANKINDIA \
  --use-python-sdk \
  --no-contracts-api \
  --extra-contracts-file /absolute/path/to/your_historical_contracts.csv
```

If your environment cannot resolve `growwapi-assets.groww.in`, first download
`instrument.csv` manually and run:
```bash
python scripts/build_groww_option_universe.py \
  --days 45 \
  --underlyings NIFTY500_PLUS_INDICES \
  --instrument-master-file /absolute/path/to/instrument.csv
```

### Test Run (5 minutes)
```bash
./scripts/quick_start_historical_collection.sh
# Select option 1: Test Run
```

### Recommended: Collect All Indices (3 hours)
```bash
python scripts/collect_historical_option_chains.py --days 90 --underlying ALL_INDICES
```

### Validate Data
```bash
python scripts/validate_historical_data.py --underlying ALL_INDICES
```

## 📚 Documentation

- **Complete Guide**: `docs/options/HISTORICAL_DATA_COLLECTION_GUIDE.md`
- **Setup Summary**: `HISTORICAL_DATA_COLLECTION_SETUP.md`

## 🚀 Collection Phases

### Phase 1: Indices (Start Here)
```bash
# 90 days - Recommended for initial backtesting
python scripts/collect_historical_option_chains.py --days 90 --underlying ALL_INDICES

# 1 year - For comprehensive analysis
python scripts/collect_historical_option_chains.py --days 252 --underlying ALL_INDICES
```

### Phase 2: Top Liquid Stocks
```bash
python scripts/collect_historical_option_chains.py --days 90 --underlying TOP_LIQUID_STOCKS
```

### Phase 3: Specific Sectors
```bash
python scripts/collect_historical_option_chains.py --days 90 --underlying "Financial Services"
python scripts/collect_historical_option_chains.py --days 90 --underlying "Information Technology"
```

## 📊 What Gets Collected

For each trading day:
- Complete option chain (all strikes, CE & PE)
- Greeks (Delta, Gamma, Theta, Vega)
- Implied Volatility
- Open Interest & OI changes
- Bid/Ask prices & quantities
- Volume & LTP
- Underlying price

## 💾 Output Location

```
data/options/historical/
├── nifty_option_chains.parquet
├── nifty_summary.txt
├── banknifty_option_chains.parquet
├── reliance_option_chains.parquet
└── collection_report_*.txt
```

## ⚡ Key Features

✅ Supports 209 underlyings (4 indices + 205 stocks)
✅ Automatic rate limiting
✅ Incremental saving (resume from interruptions)
✅ Comprehensive validation (10 quality checks)
✅ Progress tracking & logging
✅ Error recovery

## ⏱️ Estimated Times

| Scope | Days | Time | Data Size |
|-------|------|------|-----------|
| 1 Index | 30 | 15 min | 50 MB |
| 1 Index | 90 | 45 min | 150 MB |
| 4 Indices | 90 | 3 hours | 600 MB |
| 4 Indices | 252 | 8 hours | 1.6 GB |
| 20 Stocks | 90 | 4 hours | 1.5 GB |

## 🔍 Validation

After collection, always validate:
```bash
python scripts/validate_historical_data.py --underlying NIFTY
```

Checks:
- Temporal consistency
- No duplicates
- Valid Greeks & IV ranges
- Missing values < 10%
- Date gaps detection

## 🛠️ Troubleshooting

### Token Expired
Upstox tokens expire daily. Regenerate:
1. Go to Upstox Developer Console
2. Generate new access token
3. Update `.env.options`

### Rate Limit
Script handles automatically. If issues persist:
- Wait 5 minutes
- Restart script (resumes from last saved point)

### Empty Data
Normal for:
- Weekends/holidays
- Very old dates
- Low-liquidity stocks

## 📈 Next Steps

1. **Collect data** (start with indices)
2. **Validate quality**
3. **Run backtests**
4. **Analyze results**

## 🎓 Example Workflow

```bash
# 1. Collect 90 days for NIFTY
python scripts/collect_historical_option_chains.py --days 90 --underlying NIFTY

# 2. Validate
python scripts/validate_historical_data.py --underlying NIFTY

# 3. View summary
cat data/options/historical/nifty_summary.txt

# 4. Run backtest
python scripts/backtest_options_system.py \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --underlying NIFTY
```

## 📝 Important Notes

- **API Limits**: 1 request/second (handled automatically)
- **Token Expiry**: Daily (regenerate before long collections)
- **Historical Greeks**: May be calculated, not actual values
- **Expiry Approximation**: Indices=Thursday, Stocks=Month-end Thursday

## 🎯 Recommended Start

For first-time users:
```bash
# Test with 7 days
python scripts/collect_historical_option_chains.py --days 7 --underlying NIFTY

# Then collect 90 days for all indices
python scripts/collect_historical_option_chains.py --days 90 --underlying ALL_INDICES
```

---

**Status**: ✅ Ready to Use
**Total Underlyings**: 209 (4 indices + 205 stocks)
**Date**: February 10, 2026
