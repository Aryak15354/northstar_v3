# Quick Start: Real Trading with Upstox

## 🚀 Get Started in 5 Minutes

### Prerequisites
- ✅ Upstox trading account
- ✅ Upstox API credentials (API Key, Secret)
- ✅ Today's access token
- ✅ Python 3.8+ installed

### Step 1: Run Setup (2 minutes)

```bash
./scripts/setup_upstox_integration.sh
```

When prompted, enter:
1. **Upstox API Key**: Your API key from Upstox developer console
2. **Upstox API Secret**: Your API secret
3. **Upstox Access Token**: Today's token (get from Upstox)

The script will:
- Save credentials to `.env.options`
- Test API connection
- Run integration tests
- Verify everything works

### Step 2: Start Paper Trading (1 minute)

```bash
# Start engine in paper trading mode
python scripts/start_engine.py --config config/production_upstox.yaml --paper-trading

# In another terminal, launch dashboard
streamlit run dashboard/volatility_dashboard.py
```

Access dashboard at: **http://localhost:8501**

### Step 3: Monitor (Ongoing)

Watch the dashboard for:
- ✅ Real-time P&L
- ✅ Portfolio Greeks
- ✅ Risk metrics
- ✅ Position status
- ✅ Market regime
- ✅ Alerts

### Step 4: Go Live (After Testing)

Once comfortable with paper trading:

```bash
# Edit config to disable paper trading
# Set paper_trading.enabled: false in config/production_upstox.yaml

# Start live trading
python scripts/start_engine.py --config config/production_upstox.yaml
```

## 📊 What You Get

### Real-Time Data
- NIFTY, BANKNIFTY, FINNIFTY prices
- Complete option chains with Greeks
- IV surface across strikes and expiries
- Market regime detection

### Automated Trading
- Strategy generation based on regime
- Risk-managed position sizing
- Automatic Greeks balancing
- Stop-loss enforcement

### Professional Monitoring
- Institutional-grade dashboard
- Real-time P&L tracking
- Greeks utilization bars
- Risk metric gauges
- Execution quality metrics

## ⚙️ Configuration

### Capital (Edit `config/production_upstox.yaml`)

```yaml
capital:
  total_capital: 1000000  # ₹10 lakh (adjust to your capital)
  max_deployed: 0.80      # 80% max deployment
  per_trade_max: 50000    # ₹50k max per trade
```

### Position Limits

```yaml
position_limits:
  per_underlying: 50      # Max contracts per underlying
  total: 200              # Max total contracts
  max_concentration: 0.25 # 25% max per underlying
```

### Risk Thresholds

```yaml
risk_thresholds:
  var_95: 30000          # ₹30k max VaR
  max_drawdown: 0.12     # 12% max drawdown
  max_daily_loss: 15000  # ₹15k max daily loss
```

## 🔄 Daily Routine

### Morning (Before 9:15 AM)

```bash
# 1. Update access token (expires daily!)
# Edit .env.options with new token

# 2. Health check
python scripts/health_check.py

# 3. Start engine
python scripts/start_engine.py --config config/production_upstox.yaml

# 4. Launch dashboard
streamlit run dashboard/volatility_dashboard.py
```

### During Market Hours

- Monitor dashboard continuously
- Watch for alerts
- Review positions regularly
- Check Greeks utilization
- Monitor risk metrics

### End of Day (After 3:30 PM)

```bash
# 1. Generate reports
python scripts/generate_eod_reports.py

# 2. Save state
python scripts/save_state.py snapshots/eod_$(date +%Y%m%d).json

# 3. Shutdown
python scripts/shutdown_engine.py
```

## 🛡️ Safety Features

### Automatic Risk Controls
- ✅ Position limits enforced
- ✅ Greeks limits monitored
- ✅ Stop-losses automatic
- ✅ Drawdown protection
- ✅ Concentration limits

### Emergency Procedures
- 🛑 Emergency halt button
- 🔄 Auto-reduce on breach
- 🏥 Auto-hedge on delta breach
- 📧 Alert notifications

### Paper Trading Mode
- ✅ No real orders placed
- ✅ Simulated execution
- ✅ Real market data
- ✅ Full system testing

## 📱 Dashboard Features

### Overview Page
- Total P&L with Greeks decomposition
- Portfolio Greeks with utilization bars
- Market regime with probabilities
- Risk metrics (VaR, CVaR, drawdown)
- Recent alerts

### Detailed Pages
- **P&L**: Cumulative returns, strategy breakdown
- **Greeks**: Greeks vs limits, scenario analysis
- **Regime**: Regime history, characteristics
- **Risk**: VaR gauges, stress tests, drawdown chart
- **Positions**: Position table, P&L by position
- **Performance**: Sharpe ratio, alpha/beta, win rate
- **Strategy Allocation**: Capital by strategy
- **Execution Quality**: Fill rates, slippage, venues
- **Alerts**: Recent alerts with severity

## 🔧 Troubleshooting

### Token Expired
**Error**: `401 Unauthorized`

**Fix**:
1. Get new token from Upstox
2. Update `.env.options`
3. Restart engine

### Empty Option Chain
**Error**: No data returned

**Fix**:
- Check market hours (9:15 AM - 3:30 PM IST)
- Verify expiry date is valid
- Try different expiry

### Order Rejected
**Error**: Order not placed

**Fix**:
- Check margin available
- Verify instrument key
- Check price limits
- Review risk limits

## 📚 Documentation

- **Integration Guide**: `docs/UPSTOX_INTEGRATION_GUIDE.md`
- **Operator Guide**: `docs/OPERATOR_GUIDE.md`
- **Architecture**: `docs/UNIFIED_VOLATILITY_ENGINE_ARCHITECTURE.md`
- **Completion Summary**: `REAL_DATA_INTEGRATION_COMPLETE.md`

## 🆘 Support

### System Issues
```bash
# Check logs
tail -f logs/volatility_engine.log

# Run diagnostics
python scripts/health_check.py

# Test connection
python scripts/test_real_data_integration.py
```

### Upstox Support
- Website: https://upstox.com/support
- Email: support@upstox.com
- Phone: 022-6130-8888

## ⚠️ Important Notes

### Daily Token Update
⚠️ **Upstox tokens expire daily at 3:30 AM IST**
- Generate new token every morning
- Update `.env.options` before market open

### Trading Hours
- Market: 09:15 - 15:30 IST
- Trading: 09:30 - 15:00 IST (with buffers)

### Start Small
- Begin with paper trading
- Test for 1-2 weeks
- Start with 10% of limits
- Gradually increase

### Risk Management
- Always respect stop losses
- Monitor Greeks continuously
- Check risk metrics regularly
- Document all decisions

## 🎯 Success Checklist

Before going live:
- [ ] Paper trading tested for 1-2 weeks
- [ ] All integration tests passing
- [ ] Configuration reviewed and adjusted
- [ ] Risk limits appropriate for capital
- [ ] Emergency procedures understood
- [ ] Monitoring alerts configured
- [ ] Daily routine practiced
- [ ] Documentation reviewed

## 🚀 Ready to Trade!

You're all set! The system is production-ready with:
- ✅ Real-time market data
- ✅ Automated strategy generation
- ✅ Comprehensive risk management
- ✅ Professional monitoring
- ✅ Complete documentation

**Start with paper trading and gradually transition to live trading.**

Good luck! 📈

---

**Questions?** Check `docs/UPSTOX_INTEGRATION_GUIDE.md` for detailed information.
