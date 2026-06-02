# Dry Run Quick Start

## 🚀 Start Dry Run (1-2 Weeks)

```bash
# Create directories
mkdir -p logs data/dry_run

# Run continuous monitoring for 14 days
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

## 📊 What to Expect

### Signal Frequency
- **Target**: ~2 signals per week
- **Acceptable**: 1-2.5 signals/week
- **Too high**: >3 signals/week (system too aggressive)
- **Too low**: <0.5 signals/week (system too conservative)

### Regime Distribution
- **LOW_VOL_SELL**: Most common (stable markets)
- **HIGH_VOL_SELL**: During elevated volatility
- **RISING_VOL_BUY**: Rare (vol expansion)
- **NEUTRAL**: No clear regime
- **CRASH_HEDGE**: Extreme conditions

### Kill Switches (Should Block Trades)
- ✅ Monday 9:15-10:00 AM IST (opening volatility)
- ✅ Thursday (expiry day)
- ✅ 2 days before RBI/CPI/WPI events
- ✅ After 2 trades in same week

## 📁 Output Files

### `data/dry_run/cycle_results.csv`
Every check cycle logged with:
- Timestamp, underlying, regime
- Signal generated (yes/no)
- Strategy type, max loss/profit
- Rejection reasons

### `data/dry_run/signals.log`
Detailed log of every signal:
- Full strategy details
- Position sizing
- Capital at risk

### `data/dry_run/final_report.txt`
Summary at end:
- Total signals generated
- Signal frequency (per week)
- **PASS/FAIL validation**

### `logs/dry_run.log`
Complete system log with all decisions.

## 🔍 Daily Monitoring

Check these daily:

1. **Signal count**: Should be ~0-1 per day
2. **API errors**: Should be <5%
3. **Regime changes**: Should see different regimes
4. **Rejection reasons**: Track patterns

## ⚠️ Red Flags

Stop and review if:
- Signal frequency >3/week
- No signals for 2+ weeks
- Repeated API errors
- All trades rejected for same reason

## 🔧 Troubleshooting

### Access Token Expired (401 Error)
Generate new token daily from Upstox dashboard:
```bash
export UPSTOX_ACCESS_TOKEN="your_new_token"
```

### Empty Option Chain
- Check market hours (9:15 AM - 3:30 PM IST)
- Verify expiry date is valid

### Rate Limit Exceeded
Increase check interval:
```bash
python scripts/dry_run_options_system.py --interval 120  # 2 hours
```

## ✅ Validation Criteria

### PASS (Ready for Paper Trading)
- ✅ Signal frequency: 1-2.5/week
- ✅ Multiple regimes detected
- ✅ All strategies pass validation
- ✅ Kill switches work correctly
- ✅ API reliability >95%

### FAIL (Need Adjustments)
- ❌ Signal frequency <0.5 or >3/week
- ❌ Only one regime detected
- ❌ Strategies fail validation
- ❌ Kill switches not working
- ❌ API errors >10%

## 🎯 Next Steps

### After PASS:
1. Review final report
2. Manually verify a few strategies
3. Start paper trading (manual execution, small size)
4. After 2-4 successful paper trades → Go live

### After FAIL:
1. Identify root cause from logs
2. Adjust configuration in `config/options_trading.yaml`
3. Run another 1-2 week dry run
4. Do NOT go live until validation passes

## 📞 API Credentials

Already configured in script:
- **API Key**: your_upstox_api_key_here
- **API Secret**: your_upstox_api_secret_here
- **Access Token**: (expires daily - regenerate from Upstox)

## 🛡️ Safety Reminders

- 🚨 **DRY RUN = NO TRADES EXECUTED**
- ⏱️ **Validate 1-2 weeks minimum**
- 📊 **Target: ~2 signals/week**
- 🔒 **Kill switches must work**
- 🔄 **Token expires daily**

---

**Ready? Let's go!**

```bash
python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH
```

Monitor daily. Review weekly. Validate thoroughly. 🚀
