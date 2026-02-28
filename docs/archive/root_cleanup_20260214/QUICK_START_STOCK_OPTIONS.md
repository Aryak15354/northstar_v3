# Quick Start: Stock Options Trading

## 🎉 Integration Complete!

The dry run system now supports **205 stocks** + **4 indices** = **209 total underlyings** for options trading.

## ✅ Validation Status

All integration tests passed:
- ✓ Stock loader (205 stocks)
- ✓ Top 20 liquid stocks
- ✓ 18 sector categories
- ✓ Instrument key format (NSE_EQ|ISIN)

## 🚀 Quick Start Commands

### 1. Test Single Stock (Recommended First Step)

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying RELIANCE
```

**Expected output**: Fetches ~107 option contracts for RELIANCE

### 2. Monitor Top 20 Liquid Stocks

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying TOP_LIQUID_STOCKS
```

**Stocks monitored**: ITC, ONGC, SBIN, NATIONALUM, TCS, GAIL, HINDZINC, VEDL, CANBK, LICI, TATASTEEL, COALINDIA, HDFCBANK, SAIL, WIPRO, BANKINDIA, PIIND, RELIANCE, SUNPHARMA, TIINDIA

### 3. Monitor Financial Services Sector (53 stocks)

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying "Financial Services"
```

### 4. Monitor All 4 Indices (Default)

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying ALL_INDICES
```

**Indices**: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY

### 5. Continuous Monitoring (14 days)

```bash
# Top liquid stocks - check every 2 hours
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 14 \
  --interval 120 \
  --underlying TOP_LIQUID_STOCKS
```

## 📊 Available Selection Options

| Option | Description | Count |
|--------|-------------|-------|
| `ALL_INDICES` | All 4 indices | 4 |
| `ALL_STOCKS` | All stocks with options | 205 |
| `TOP_LIQUID_STOCKS` | Top 20 by liquidity | 20 |
| `RECOMMENDED_STOCKS` | Beginner-friendly | 20 |
| `NIFTY`, `BANKNIFTY`, etc. | Single index | 1 |
| `RELIANCE`, `TCS`, etc. | Single stock | 1 |
| `"Financial Services"` | Sector name | Varies |

## 🏢 Available Sectors

```bash
# View all sectors
python -c "from src.options.stock_options_loader import get_stock_loader; \
           print('\n'.join(get_stock_loader().get_sectors()))"
```

**18 Sectors**:
- Financial Services (53 stocks)
- Capital Goods (21 stocks)
- Healthcare (18 stocks)
- Automobile and Auto Components (14 stocks)
- Information Technology (13 stocks)
- Fast Moving Consumer Goods (12 stocks)
- Consumer Durables (10 stocks)
- Metals & Mining (10 stocks)
- Consumer Services (9 stocks)
- Oil Gas & Consumable Fuels (9 stocks)
- Power (8 stocks)
- Realty (6 stocks)
- Construction Materials (5 stocks)
- Chemicals (5 stocks)
- Services (5 stocks)
- Construction (3 stocks)
- Telecommunication (3 stocks)
- Textiles (1 stock)

## 🧪 Run Integration Tests

```bash
python scripts/test_stock_options_integration.py
```

**Expected**: All 4 tests pass ✅

## ⚠️ Rate Limiting

Upstox API: **1 request/second**

**Safe intervals**:
- 4 indices: 60 minutes ✅
- 20 stocks: 120 minutes ✅
- 53 stocks (Financial Services): 180 minutes ✅
- 205 stocks: 240 minutes (4 hours) ✅

## 📈 Sample Output

```
2026-02-10 15:55:57 - INFO - Monitoring single stock: RELIANCE (Reliance Industries Ltd.)
2026-02-10 15:55:57 - INFO - Step 1: Fetching option chain from Upstox...
2026-02-10 15:55:57 - INFO - Found next expiry for RELIANCE from API: 2026-02-24
2026-02-10 15:55:58 - INFO - Fetched 107 option contracts
2026-02-10 15:55:58 - INFO - Current ATM IV: 0.1764
2026-02-10 15:55:58 - INFO - Regime: rising_vol_buy
2026-02-10 15:55:58 - INFO - Confidence: 70.00%
```

## 🎯 Recommended Workflow

### Week 1: Indices Only
```bash
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 7 \
  --interval 60 \
  --underlying ALL_INDICES
```

### Week 2: Add Top Liquid Stocks
```bash
# Terminal 1: Indices
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 7 \
  --interval 60 \
  --underlying ALL_INDICES

# Terminal 2: Top stocks
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 7 \
  --interval 120 \
  --underlying TOP_LIQUID_STOCKS
```

### Week 3+: Sector Focus
```bash
# Focus on sector you understand
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 14 \
  --interval 120 \
  --underlying "Information Technology"
```

## 📚 Documentation

- **Complete Guide**: `docs/options/STOCK_OPTIONS_GUIDE.md`
- **Integration Summary**: `STOCK_OPTIONS_INTEGRATION_COMPLETE.md`
- **Dry Run Guide**: `docs/options/DRY_RUN_GUIDE.md`

## 🔍 Explore Available Stocks

```python
from src.options.stock_options_loader import get_stock_loader

loader = get_stock_loader()

# All stocks
print(f"Total: {len(loader.get_all_symbols())} stocks")

# Search
results = loader.search_stocks('bank')
for stock in results:
    print(f"{stock.symbol} - {stock.name} (Lot: {stock.lot_size})")

# By sector
it_stocks = loader.get_by_sector('Information Technology')
for stock in it_stocks:
    print(f"{stock.symbol} - {stock.name}")
```

## ✨ Key Features

✅ **205 stocks** with options trading
✅ **18 sectors** for focused monitoring
✅ **Automatic ISIN lookup** for instrument keys
✅ **Flexible selection** (indices, stocks, sectors)
✅ **Liquidity-based recommendations**
✅ **Automatic lot size handling**
✅ **Monthly expiry support** for stocks
✅ **Rate limit compliance**

## 🎊 Ready to Use!

The system is fully integrated and tested. Start with:

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying TOP_LIQUID_STOCKS
```

Then expand to continuous monitoring and sector-based strategies.

---

**Last Updated**: February 10, 2026
**Status**: ✅ Production Ready
**Total Underlyings**: 209 (4 indices + 205 stocks)
