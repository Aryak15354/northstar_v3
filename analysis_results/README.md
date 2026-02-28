# Analysis Results

This directory contains all analysis results generated from the Northstar V3 system.

## Structure

- `backtests/` - 3-year backtest results for all strategies
- `live_trading/` - 6-month live trading data extraction
- `summaries/` - Performance summaries and unified reports

## Generated on
2026-01-27 20:40:11

## Key Files

### Backtests
- `northstar_all_strategies_3year_backtest.csv` - Complete backtest data (4,032 observations)
- `northstar_all_strategies_summary.csv` - Performance summary for 16 strategies

### Live Trading
- `live_trading_data_summary.csv` - Overview of all live data sources
- `live_data_portfolio_pnl.csv` - Live PnL tracking (124 records)
- `live_data_shadow_execution_log.csv` - Execution records

### Top Strategy Performance
1. sector_tilt_mom: 53.4% return, 2.58 Sharpe
2. dual_momentum: 55.8% return, 2.39 Sharpe
3. mom_vol_adj: 51.4% return, 2.26 Sharpe
