# 🚀 Quick Start Guide - Options Trading System

## ✅ Your System is Working!

The options engine is operational and ready to trade. Here's everything you need to know.

---

## 🎯 Current Status

- ✅ System initialized successfully
- ✅ Fetching option chains from Upstox
- ✅ Detecting volatility regimes
- ✅ Generating strategies
- ✅ Validating trades (being conservative)
- ⏳ Waiting for high-quality trade setups

**Why no trades yet?** System is being conservative about liquidity. This is GOOD - it's protecting your capital!

---

## 🚀 Three Ways to Run

### 1. Indices Only (Conservative - Current Setup)

```bash
# Start the system
echo "3" | ./START_OPTIONS_SYSTEM.sh

# Or directly:
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 5 \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY \
    --aggressive
```

**Pros**: Fast, focused, less API calls  
**Cons**: Fewer opportunities (only 3 underlyings)

### 2. Indices + Stocks (Recommended)

```bash
# Run with stocks included
./scripts/run_with_stocks.sh

# Or directly:
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 15 \
    --underlyings "NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN" \
    --aggressive
```

**Pros**: More opportunities, diversified  
**Cons**: Takes longer per cycle (3-5 min)

### 3. Single Test Cycle

```bash
# Quick test with one underlying
./scripts/test_single_cycle.sh NIFTY

# Or with stocks
./scripts/test_single_cycle.sh "NIFTY,RELIANCE,TCS"
```

**Use for**: Testing, debugging, checking system health

---

## 📊 Monitor Your System

### Real-Time Monitor

```bash
# Check current status
python scripts/monitor_options.py

# Auto-refresh every 30 seconds
watch -n 30 python scripts/monitor_options.py
```

### Check Data Files

```bash
# Runtime state
cat data/options/live/options_runtime_state.json | python -m json.tool

# View regime history
python -c "import pandas as pd; print(pd.read_parquet('data/options/regime_history.parquet').tail(10))"

# View IV history
python -c "import pandas as pd; print(pd.read_parquet('data/options/iv_history.parquet').tail(10))"

# View cached chains
ls -lh data/options/chains_cache/
```

---

## 🎯 Getting Your First Trade

### Option A: Add More Underlyings

More underlyings = more opportunities:

```bash
./scripts/run_with_stocks.sh
```

### Option B: Relax Liquidity (Not Recommended Initially)

Edit `config/options_trading.yaml`:

```yaml
execution:
  min_liquidity_multiplier: 1.5  # From 2.0
```

### Option C: Run During Market Hours

Better liquidity during 9:15 AM - 3:30 PM IST:

```bash
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 5 \
    --underlyings "NIFTY,BANKNIFTY,FINNIFTY" \
    --aggressive \
    --market-hours-only
```

---

## 🔧 Common Commands

```bash
# Start trading (indices only)
echo "3" | ./START_OPTIONS_SYSTEM.sh

# Start trading (with stocks)
./scripts/run_with_stocks.sh

# Test single cycle
./scripts/test_single_cycle.sh NIFTY

# Monitor system
python scripts/monitor_options.py

# Check status
python scripts/status.py

# Health check
python scripts/health_check.py

# Emergency stop
# Press Ctrl+C in the running terminal

# Close all positions
python scripts/emergency_reduce.py --close-all
```

---

## 📈 What to Expect

### First Hour
- System fetches option chains
- Detects volatility regimes
- Generates strategies
- May or may not open trades (depends on conditions)

### Throughout Day
- Checks every 5-15 minutes (depending on interval)
- Opens trades when:
  - Regime is actionable
  - Strategy passes all checks
  - Liquidity is sufficient
  - Risk limits not exceeded

### End of Day
- All data saved
- State persisted
- Ready for next day

---

## 🐛 Troubleshooting

### "No trades generated"

**Causes**:
1. Regime not actionable → Use `--aggressive` flag
2. Liquidity insufficient → Add more underlyings or relax constraints
3. Position limits reached → Check `python scripts/monitor_options.py`
4. Outside market hours → Use `--market-hours-only` or run during trading hours

**Solution**: Add stocks with `./scripts/run_with_stocks.sh`

### "Token expired"

```bash
python scripts/refresh_upstox_token.py
```

### "API errors"

- Check internet connection
- Verify token is valid
- Check Upstox API status
- System will use cached chains automatically

### "System seems stuck"

Not stuck! Fetching chains takes time:
- 1 underlying: ~30 seconds
- 3 underlyings: ~2 minutes
- 9 underlyings: ~5 minutes

---

## 📊 Understanding the Output

### Successful Chain Fetch
```
INFO - Fetched 186 option contracts
INFO - Fetched 202 option contracts
```
✅ System is working

### Strategy Generated
```
INFO - Generated Calendar Spread: debit=8909.87, max_loss=8909.87, RR=0.78
```
✅ Strategy logic working

### Trade Rejected
```
WARNING - Trade REJECTED: 1 violations - Insufficient liquidity
```
✅ Risk management working (protecting capital)

### Trade Opened
```
INFO - Opened position: calendar_spread_NIFTY_...
```
🎉 First trade!

---

## 🎯 Your Action Plan

### Today
1. ✅ Verify system is running (you've done this!)
2. ⏳ Choose: Indices only OR Indices + Stocks
3. ⏳ Start continuous mode
4. ⏳ Monitor for first trade

### This Week
1. Run system daily during market hours
2. Monitor regime detection
3. Track strategy generation
4. Collect first 10 trades

### This Month
1. Analyze trade performance
2. Tune parameters based on data
3. Test all strategy types
4. Prepare for live trading

---

## 💡 Pro Tips

1. **Start Conservative**: Indices only is fine for first week
2. **Monitor Actively**: Check every hour initially
3. **Trust the System**: Rejections are good (protecting capital)
4. **Be Patient**: Quality > quantity in options
5. **Document**: Keep notes on what you observe

---

## 📞 Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│ QUICK COMMANDS                                          │
├─────────────────────────────────────────────────────────┤
│ Start (indices):  echo "3" | ./START_OPTIONS_SYSTEM.sh │
│ Start (stocks):   ./scripts/run_with_stocks.sh         │
│ Test:             ./scripts/test_single_cycle.sh NIFTY │
│ Monitor:          python scripts/monitor_options.py    │
│ Stop:             Ctrl+C                                │
│ Emergency:        python scripts/emergency_reduce.py   │
│ Token:            python scripts/refresh_upstox_token.py│
└─────────────────────────────────────────────────────────┘
```

---

## ✅ You're Ready!

Your system is operational and ready to trade. Choose your approach:

**Conservative** (Recommended for first week):
```bash
echo "3" | ./START_OPTIONS_SYSTEM.sh
```

**Aggressive** (More opportunities):
```bash
./scripts/run_with_stocks.sh
```

**Test First**:
```bash
./scripts/test_single_cycle.sh NIFTY
```

---

**Happy Trading! 📈🚀**

For detailed docs, see:
- `SYSTEM_WORKING_SUMMARY.md` - Current status
- `docs/OPTIONS_V3_INTEGRATION_GUIDE.md` - Complete guide
- `READY_TO_TRADE_CHECKLIST.md` - Pre-flight checklist
