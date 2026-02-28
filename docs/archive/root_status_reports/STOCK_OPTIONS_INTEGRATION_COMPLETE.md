# Stock Options Integration Complete ✅

## Summary

Successfully integrated **205 stocks** with options trading into the dry run monitoring system. The system now supports both indices and stocks with flexible selection options.

## What Was Done

### 1. Stock Options Discovery
- Scanned all 501 stocks in Nifty 500 index
- Discovered 205 stocks (40.9%) with options trading available
- Generated complete mapping with ISINs, lot sizes, and sectors
- Identified top 20 most liquid stocks by contract count

### 2. System Integration
- Updated `StockOptionsLoader` to use complete mapping (205 stocks)
- Enhanced `UpstoxAdapter.fetch_option_chain()` to support stock instrument keys
- Modified `DryRunMonitor._get_next_expiry()` to handle both indices and stocks
- Added flexible underlying selection in argument parser

### 3. Selection Options
The dry run script now supports:
- **ALL_INDICES** - All 4 indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY)
- **ALL_STOCKS** - All 205 stocks with options
- **TOP_LIQUID_STOCKS** - Top 20 most liquid stocks
- **RECOMMENDED_STOCKS** - Beginner-friendly stocks
- **Single index** - e.g., NIFTY, BANKNIFTY
- **Single stock** - e.g., RELIANCE, TCS
- **Sector name** - e.g., Banking, IT

### 4. Documentation
- Created comprehensive `STOCK_OPTIONS_GUIDE.md`
- Includes usage examples, sector breakdown, lot sizes
- Rate limiting recommendations
- Troubleshooting guide

## Files Modified

1. **scripts/dry_run_options_system.py**
   - Added stock_loader initialization
   - Updated `_get_next_expiry()` for stock support
   - Enhanced argument parser with flexible selection
   - Added instrument_key parameter passing

2. **src/options/stock_options_loader.py**
   - Changed default config to `stock_options_mapping_complete.yaml`

3. **src/options/upstox_adapter.py**
   - Added optional `instrument_key` parameter to `fetch_option_chain()`
   - Supports both index and stock instrument keys

4. **docs/options/STOCK_OPTIONS_GUIDE.md** (NEW)
   - Complete usage guide for stock options

## Usage Examples

### Monitor Top 20 Liquid Stocks (Recommended Start)
```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying TOP_LIQUID_STOCKS
```

### Monitor Banking Sector
```bash
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 7 \
  --interval 60 \
  --underlying Banking
```

### Monitor Single Stock
```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying RELIANCE
```

### Monitor All Indices (Default)
```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying ALL_INDICES
```

## Top 20 Most Liquid Stocks

By contract count (highest liquidity):

1. ITC (495 contracts, Lot: 1600)
2. ONGC (441 contracts, Lot: 2250)
3. SBIN (397 contracts, Lot: 750)
4. NATIONALUM (395 contracts, Lot: 3750)
5. TCS (331 contracts, Lot: 175)
6. GAIL (324 contracts, Lot: 3150)
7. HINDZINC (323 contracts, Lot: 1225)
8. VEDL (319 contracts, Lot: 1150)
9. CANBK (314 contracts, Lot: 6750)
10. LICI (310 contracts, Lot: 700)
11. TATASTEEL (310 contracts, Lot: 5500)
12. COALINDIA (305 contracts, Lot: 1350)
13. HDFCBANK (298 contracts, Lot: 550)
14. SAIL (291 contracts, Lot: 4700)
15. WIPRO (291 contracts, Lot: 3000)
16. BANKINDIA (290 contracts, Lot: 5200)
17. PIIND (290 contracts, Lot: 175)
18. RELIANCE (287 contracts, Lot: 500)
19. SUNPHARMA (287 contracts, Lot: 350)
20. TIINDIA (281 contracts, Lot: 200)

## Sector Distribution

- Financial Services: 53 stocks
- Capital Goods: 21 stocks
- Healthcare: 18 stocks
- Automobile: 14 stocks
- IT: 13 stocks
- FMCG: 12 stocks
- Consumer Durables: 10 stocks
- Metals & Mining: 10 stocks
- Consumer Services: 9 stocks
- Oil & Gas: 9 stocks
- Power: 8 stocks
- Realty: 6 stocks
- Construction Materials: 5 stocks
- Chemicals: 5 stocks
- Services: 5 stocks
- Construction: 3 stocks
- Telecom: 3 stocks
- Textiles: 1 stock

**Total: 205 stocks across 18 sectors**

## Rate Limiting Guidelines

Upstox API: 1 request/second

**Safe intervals**:
- 4 indices: 60 minutes ✅
- 20 stocks: 120 minutes ✅
- 50 stocks: 180 minutes ✅
- 205 stocks: 240 minutes (4 hours) ✅

## Key Features

✅ Automatic ISIN-based instrument key lookup
✅ Support for both weekly (indices) and monthly (stocks) expiries
✅ Flexible selection: indices, stocks, sectors, or combinations
✅ Automatic lot size handling per stock
✅ Sector-based filtering (18 sectors)
✅ Liquidity-based recommendations
✅ Complete Nifty 500 coverage (40.9% have options)

## Data Files

- `config/stock_options_mapping_complete.yaml` - 205 stocks with ISINs, lot sizes, sectors
- `data/options/stocks_with_options.csv` - Discovery results
- `universe/nifty500.csv` - Source universe (501 stocks)

## Next Steps

1. **Test with top liquid stocks** - Start with TOP_LIQUID_STOCKS
2. **Validate stock option chains** - Ensure data quality
3. **Monitor sector-wise** - Focus on 1-2 sectors initially
4. **Expand gradually** - Add more stocks as system proves stable

## Important Notes

- Stock options typically have **monthly expiries** (not weekly)
- Liquidity varies significantly between stocks
- System automatically validates OI > 0 for all contracts
- Lot sizes range from 15 (PAGEIND) to 71,475 (IDEA)
- Start with recommended stocks for better execution

## Testing Checklist

- [ ] Test single stock monitoring (e.g., RELIANCE)
- [ ] Test top liquid stocks (20 stocks)
- [ ] Test sector monitoring (e.g., Banking)
- [ ] Test continuous mode with stocks
- [ ] Verify instrument key lookup works
- [ ] Validate expiry date fetching for stocks
- [ ] Check lot size accuracy
- [ ] Confirm rate limiting compliance

## Status

🟢 **READY FOR TESTING**

The system is fully integrated and ready to monitor stock options alongside indices. Start with TOP_LIQUID_STOCKS for initial validation.

---

**Date**: February 10, 2026
**Total Stocks Available**: 205
**Total Indices Available**: 4
**Total Underlyings**: 209
