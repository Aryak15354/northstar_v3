# Stock Options Trading Guide

## Overview

The dry run system now supports **205 stocks** with options trading, in addition to the 4 indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY).

## Quick Start

### Monitor Top Liquid Stocks (Recommended for Beginners)

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying TOP_LIQUID_STOCKS
```

This monitors the 20 most liquid stocks:
- ITC, ONGC, SBIN, NATIONALUM, TCS
- GAIL, HINDZINC, VEDL, CANBK, LICI
- TATASTEEL, COALINDIA, HDFCBANK, SAIL, WIPRO
- BANKINDIA, PIIND, RELIANCE, SUNPHARMA, TIINDIA

### Monitor All Indices (Default)

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying ALL_INDICES
```

### Monitor Single Stock

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying RELIANCE
```

### Monitor Stocks by Sector

```bash
# Banking sector
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying Banking

# IT sector
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying "Information Technology"
```

### Monitor All 205 Stocks (Advanced)

```bash
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 14 \
  --interval 120 \
  --underlying ALL_STOCKS
```

**Warning**: This will check 205 stocks every 2 hours. Use longer intervals to avoid rate limits.

## Available Sectors

- **Financial Services** (53 stocks) - Banking, NBFCs, Insurance
- **Information Technology** (13 stocks) - TCS, Infosys, Wipro, etc.
- **Healthcare** (18 stocks) - Pharma and hospitals
- **Automobile and Auto Components** (14 stocks)
- **Capital Goods** (21 stocks) - Engineering, defense
- **Fast Moving Consumer Goods** (12 stocks)
- **Metals & Mining** (10 stocks)
- **Oil Gas & Consumable Fuels** (9 stocks)
- **Power** (8 stocks)
- **Consumer Durables** (10 stocks)
- **Consumer Services** (9 stocks)
- **Construction** (3 stocks)
- **Construction Materials** (5 stocks) - Cement
- **Chemicals** (5 stocks)
- **Realty** (6 stocks)
- **Services** (5 stocks) - Logistics, aviation
- **Telecommunication** (3 stocks)
- **Textiles** (1 stock)

## Stock Selection Criteria

All 205 stocks meet these criteria:
- Listed on NSE with options trading
- Part of Nifty 500 index
- Sufficient liquidity for options
- Complete ISIN mapping for API access

## Recommended Stocks for Beginners

These 20 stocks have the highest liquidity (most contracts available):

```bash
python scripts/dry_run_options_system.py \
  --mode single \
  --underlying RECOMMENDED_STOCKS
```

Stocks: ITC, ONGC, SBIN, NATIONALUM, TCS, GAIL, HINDZINC, VEDL, CANBK, LICI, TATASTEEL, COALINDIA, HDFCBANK, SAIL, WIPRO, BANKINDIA, PIIND, RELIANCE, SUNPHARMA, TIINDIA

## Continuous Monitoring Examples

### Monitor Banking Sector for 7 Days

```bash
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 7 \
  --interval 60 \
  --underlying Banking
```

### Monitor Top Stocks + All Indices

Run two separate processes:

```bash
# Terminal 1: Indices
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 14 \
  --interval 60 \
  --underlying ALL_INDICES

# Terminal 2: Top stocks
python scripts/dry_run_options_system.py \
  --mode continuous \
  --duration 14 \
  --interval 120 \
  --underlying TOP_LIQUID_STOCKS
```

## Rate Limiting Considerations

Upstox API has rate limits:
- 1 request per second
- Daily limits apply

**Recommendations**:
- For 4 indices: 60-minute intervals (safe)
- For 20 stocks: 120-minute intervals (safe)
- For 205 stocks: 240-minute intervals (4 hours) or longer
- Single checks: No restrictions

## Lot Sizes

Stock options have varying lot sizes. Examples:
- **Small lots** (easier to trade):
  - PAGEIND: 15
  - SHREECEM: 25
  - MARUTI: 50
  - ULTRACEMCO: 50
  
- **Medium lots** (most common):
  - TCS: 175
  - RELIANCE: 500
  - HDFCBANK: 550
  - ITC: 1600

- **Large lots** (higher capital required):
  - MOTHERSON: 6150
  - GMRAIRPORT: 6975
  - SUZLON: 9025
  - IDEA: 71,475

The system automatically uses correct lot sizes for position sizing.

## Data Files

- **Complete mapping**: `config/stock_options_mapping_complete.yaml` (205 stocks)
- **Discovery results**: `data/options/stocks_with_options.csv`
- **Universe source**: `universe/nifty500.csv` (501 stocks)

## Viewing Available Stocks

```python
from src.options.stock_options_loader import get_stock_loader

loader = get_stock_loader()

# All stocks
print(f"Total stocks: {len(loader.get_all_symbols())}")

# By sector
banking_stocks = loader.get_by_sector('Banking')
for stock in banking_stocks:
    print(f"{stock.symbol} - {stock.name} (Lot: {stock.lot_size})")

# Search
results = loader.search_stocks('tata')
for stock in results:
    print(f"{stock.symbol} - {stock.name}")
```

## Next Steps

1. **Start with indices** - Get familiar with the system
2. **Try top liquid stocks** - Test with high-liquidity stocks
3. **Focus on sectors** - Specialize in 1-2 sectors you understand
4. **Expand gradually** - Add more stocks as you gain confidence

## Important Notes

- Stock options typically have **monthly expiries** (not weekly like indices)
- Liquidity varies significantly between stocks
- Always check bid-ask spreads before trading
- The system validates liquidity automatically (OI > 0 required)
- Start with recommended stocks for better execution

## Troubleshooting

**Empty option chain for a stock?**
- Stock may have monthly expiries only
- Check if market is open
- Verify stock symbol is correct

**Too many API calls?**
- Increase `--interval` value
- Reduce number of stocks monitored
- Use sector-based monitoring instead of ALL_STOCKS

**Stock not found?**
- Check if stock is in Nifty 500
- Verify stock has options trading
- Use exact symbol from `data/options/stocks_with_options.csv`
