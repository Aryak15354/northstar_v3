# 🌟 NORTHSTAR SHADOW TRADING SYSTEM
## 3-Month Live Track Record Builder

This system runs Northstar in shadow mode every trading day to build a clean institutional-grade track record.

## 📋 What You Get

### Daily (5 days/week):
- ✅ **Daily Positions**: Complete position snapshots
- ✅ **Daily P&L**: Northstar vs NIFTY performance  
- ✅ **Daily Decisions**: Full decision audit trail
- ✅ **Risk Metrics**: Drawdown, volatility, Sharpe ratio
- ✅ **Automated Execution**: Runs at 4 PM after market close

### Monthly:
- 📊 **One-Page PDF Report**: Professional institutional format
- 📈 **Performance Charts**: Northstar vs NIFTY comparison
- 📉 **Drawdown Analysis**: Risk visualization
- 🎯 **Causality Index**: Top 3 performance drivers
- 📧 **Email Reports**: (Optional) Automated delivery

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install pandas numpy matplotlib seaborn yfinance schedule reportlab
```

### 2. Start Shadow Trading
```bash
# Start automated daily trading (runs continuously)
python scripts/launch_shadow_trading.py --mode auto

# Or run once manually for testing
python scripts/launch_shadow_trading.py --mode manual
```

### 3. Check Status
```bash
python scripts/launch_shadow_trading.py --mode status
```

### 4. Generate Monthly Report
```bash
# Generate report for current month
python scripts/launch_shadow_trading.py --mode report

# Generate report for specific month
python scripts/launch_shadow_trading.py --mode report --year 2026 --month 1
```

## 📁 Data Structure

```
data/live/shadow_trading/
├── positions/           # Daily position files
│   ├── positions_2026-01-20.json
│   └── positions_2026-01-21.json
├── pnl/                # Daily P&L files
│   ├── pnl_2026-01-20.json
│   └── pnl_2026-01-21.json
├── decisions/          # Daily decision files
│   ├── decisions_2026-01-20.json
│   └── decisions_2026-01-21.json
├── reports/            # Monthly PDF reports
│   ├── northstar_monthly_report_202601.pdf
│   └── performance_chart_202601.png
├── logs/               # System logs
│   └── scheduler_202601.log
├── trading_state.json  # Current system state
└── daily_log_202601.json  # Consolidated daily logs
```

## ⏰ Automated Schedule

The system runs automatically with this schedule:

- **Daily Trading**: Weekdays at 4:00 PM (after market close)
- **Monthly Reports**: Generated in first 5 days of new month
- **Health Checks**: Every hour during market hours
- **Market Holidays**: Automatically skipped

## 📊 Sample Monthly Report Contents

### Executive Summary Table
| Metric | Northstar | NIFTY 50 | Outperformance |
|--------|-----------|----------|----------------|
| Total Return | 2.45% | 1.23% | +1.22% |
| Volatility | 12.3% | 15.7% | -3.4% |
| Sharpe Ratio | 1.85 | 0.78 | +1.07 |
| Max Drawdown | -1.2% | -2.8% | +1.6% |
| Win Rate | 68% | - | - |

### Performance Charts
- **Cumulative Returns**: Northstar vs NIFTY line chart
- **Daily Returns**: Bar chart of daily performance
- **Drawdown Chart**: Risk visualization over time

### Causality Index (Top 3 Drivers)
1. **RELIANCE.NS**: ₹45,000 contribution (12 active days)
2. **TCS.NS**: ₹32,000 contribution (8 active days)  
3. **HDFCBANK.NS**: ₹28,000 contribution (15 active days)

## 🔧 Configuration

### Market Holidays
Edit `src/live/shadow_trading_scheduler.py` to update market holidays:

```python
self.market_holidays_2026 = [
    '2026-01-26',  # Republic Day
    '2026-03-14',  # Holi
    # Add more holidays...
]
```

### Initial Capital
Default: ₹1 Crore (10,000,000 INR)

Change in `src/live/daily_shadow_trader.py`:
```python
def __init__(self, initial_capital=10000000):  # Change this value
```

### Trading Time
Default: 4:00 PM (after market close)

Change in `src/live/shadow_trading_scheduler.py`:
```python
schedule.every().monday.at("16:00").do(self.run_daily_trading)  # Change time
```

## 📈 Performance Tracking

### Key Metrics Tracked:
- **Total Return**: Cumulative performance
- **Daily Returns**: Day-by-day performance
- **Volatility**: Annualized standard deviation
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Worst peak-to-trough decline
- **Win Rate**: Percentage of positive days
- **Outperformance**: Excess return vs NIFTY

### Benchmark Comparison:
- **Primary Benchmark**: NIFTY 50 (^NSEI)
- **Data Source**: Yahoo Finance
- **Frequency**: Daily comparison
- **Attribution**: Position-level contribution analysis

## 🛠️ Troubleshooting

### Common Issues:

1. **"No market data available"**
   - Check internet connection
   - Verify Yahoo Finance is accessible
   - Check if symbols are correct (should end with .NS)

2. **"Missing required packages"**
   ```bash
   pip install pandas numpy matplotlib seaborn yfinance schedule reportlab
   ```

3. **"Permission denied" errors**
   - Ensure write permissions to `data/` directory
   - Run with appropriate user permissions

4. **"TensorFlow errors"**
   - System falls back to CPU-only mode automatically
   - No action needed - this is expected on M1 Macs

### Log Files:
- **Scheduler logs**: `data/live/shadow_trading/logs/scheduler_YYYYMM.log`
- **Trading logs**: `data/live/shadow_trading/shadow_trader_YYYYMM.log`

## 🎯 3-Month Track Record Goal

### Week 1-4: Foundation
- ✅ Daily shadow trading operational
- ✅ All logging systems working
- ✅ First monthly report generated

### Week 5-8: Optimization  
- ✅ Performance attribution working
- ✅ Risk metrics stable
- ✅ Second monthly report

### Week 9-12: Validation
- ✅ Consistent outperformance tracking
- ✅ Drawdown analysis complete
- ✅ Third monthly report
- ✅ **Clean 3-month track record ready**

## 📧 Optional: Email Notifications

To add email notifications, install additional package:
```bash
pip install smtplib
```

Then modify the scheduler to send daily/monthly email updates.

## 🔒 Security Notes

- **No Real Money**: This is shadow trading only
- **Data Privacy**: All data stored locally
- **API Limits**: Yahoo Finance has rate limits
- **Backup**: Regularly backup the `data/live/shadow_trading/` directory

## 📞 Support

If you encounter issues:
1. Check the log files first
2. Run status check: `python scripts/launch_shadow_trading.py --mode status`
3. Try manual mode to test: `python scripts/launch_shadow_trading.py --mode manual`

---

## 🎉 Success Metrics

After 3 months, you'll have:
- **60+ trading days** of clean data
- **3 professional PDF reports** 
- **Complete audit trail** of all decisions
- **Institutional-grade track record**
- **Performance attribution** analysis
- **Risk-adjusted metrics**

This is **FAR more valuable** than additional code - it's real execution proof that institutional investors want to see.

**Start today and build your track record!** 🚀