# Analysis Scripts

Scripts used to extract and analyze Northstar V3 performance data.

## Scripts

- `extract_all_strategy_backtests.py` - Extract individual strategy backtests
- `extract_real_data_results.py` - Extract 3-year backtest and 6-month live data
- `extract_live_trading_comprehensive.py` - Comprehensive live data extraction
- `generate_3year_backtest.py` - Generate 3-year backtest results

## Usage

All scripts are designed to work with real data from the Northstar V3 system:

```bash
python extract_all_strategy_backtests.py      # Extract all strategy backtests
python extract_real_data_results.py           # Extract main results
python extract_live_trading_comprehensive.py  # Extract live trading data
```

## Data Sources

Scripts read from:
- `data/processed/backtests/` - Strategy backtest files
- `data/execution/` - Live trading execution data
- `data/portfolio/` - Portfolio state and PnL
- `data/shadow_reality/` - Shadow trading logs
