# Dry Run Setup Complete ✅

## What We've Built

A comprehensive dry-run system that runs your options trading system with **real Upstox API data** but **WITHOUT executing any trades**. This allows you to validate the system for 1-2 weeks before going live.

## Files Created

### 1. Main Dry Run Script
**`scripts/dry_run_options_system.py`**
- Complete signal generation pipeline with real API data
- Fetches live option chains from Upstox
- Runs regime detection, strategy generation, eligibility checks
- Validates all kill switches and survival rules
- Logs every decision without executing trades
- Generates comprehensive reports

### 2. Documentation
**`docs/options/DRY_RUN_GUIDE.md`**
- Complete guide with setup instructions
- Detailed explanation of what gets validated
- Output file descriptions
- Monitoring guidelines
- Troubleshooting section
- Configuration tuning tips

**`docs/options/DRY_RUN_QUICK_START.md`**
- Quick reference card
- One-command startup
- Daily monitoring checklist
- Red flags to watch for
- PASS/FAIL criteria

## API Credentials Configured

Your Upstox credentials are already set in the script:
- **API Key**: your_upstox_api_key_here
- **API Secret**: your_upstox_api_secret_here
- **Access Token**: REDACTED_ROTATE_REQUIRED

**Note**: Access token expires daily. Generate new token from Upstox dashboard each day.

## What Gets Validated

### ✅ Regime Detection Accuracy
- IV rank calculations (252-day history)
- Regime classification (LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, CRASH_HEDGE, NEUTRAL)
- Regime persistence (2-day requirement)
- Vol-of-vol detection (blocks short-vol when elevated)
- Equity crisis integration (blocks short-vol during CRISIS)

### ✅ Strategy Generation Quality
- **Iron Condor**: Strike selection by delta (16-20 short, 5-10 long), premium adequacy (≥25% max loss)
- **Calendar Spread**: Near-term (7-14 days) vs far-term (30-45 days) ATM
- **Long Straddle**: ATM call + put (30-60 days)
- Lot size validation (NIFTY: 50, BANKNIFTY: 15)
- Greek calculations and portfolio aggregation

### ✅ Signal Frequency
- **Target**: ~2 trades per week maximum
- Validates system is selective, not overactive
- Tracks signal rate over time
- Flags if too high (>3/week) or too low (<0.5/week)

### ✅ Kill Switch Behavior
1. **Weekly Loss Limit**: 2% weekly loss → halt trading
2. **Trauma Rule**: Single trade loses >80% max loss → block short-vol for 2 weeks
3. **Portfolio Risk Cap**: Total open risk >2% capital → reject new trades
4. **Tax Liquidity**: YTD tax > cash buffer → halt trading
5. **Frequency Limits**: Max 2 trades/week
6. **Time Blocks**: Monday 9:15-10:00 AM IST, Thursday (expiry day)

### ✅ Eligibility Rules
- IV rank thresholds (70% for LOW_VOL_SELL, 80% for HIGH_VOL_SELL, <30% for RISING_VOL_BUY)
- Liquidity checks (bid-ask spread ≤8%, bid qty ≥2× lot size)
- Expiry hygiene (min 5 days to expiry)
- Event calendar blocks (2 days before RBI/CPI/WPI)
- Late-cycle protection (50% size reduction after 10 days in LOW_VOL_SELL)

## How to Run

### Quick Start (Recommended)

```bash
# Create directories
mkdir -p logs data/dry_run

# Run 14-day continuous monitoring
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

This will:
- Check every 60 minutes
- Monitor both NIFTY and BANKNIFTY
- Run for 14 days
- Generate daily summaries
- Create final validation report

### Test Run (Single Cycle)

```bash
# Test with single check
python scripts/dry_run_options_system.py --mode single --underlying NIFTY
```

Use this to verify everything works before starting continuous monitoring.

## Output Files

All saved to `data/dry_run/`:

### 1. `cycle_results.csv`
Every check cycle with:
- Timestamp, underlying, regime detected
- Signal generated (yes/no)
- Strategy type, max loss/profit
- Rejection reasons

### 2. `signals.log`
Detailed log of every signal:
- Full strategy details
- Position sizing
- Capital at risk
- Greeks

### 3. `final_report.txt`
Summary report:
- Total cycles run
- Signals generated
- Signal frequency (per week)
- Regime distribution
- Strategy distribution
- Top rejection reasons
- **PASS/FAIL validation**

### 4. `logs/dry_run.log`
Complete system log with all decisions and reasoning.

## Daily Monitoring

Check these daily:

1. **Signal Count**: Should be ~0-1 per day (2-3 per week)
2. **API Errors**: Should be <5%
3. **Regime Changes**: Should see different regimes over time
4. **Rejection Reasons**: Track patterns (most common: regime not persistent, liquidity issues)
5. **Kill Switch Activations**: Should see time blocks (Monday morning, Thursday)

## Validation Criteria

### ✅ PASS (Ready for Paper Trading)
- Signal frequency: 1-2.5 signals per week
- Multiple regime types detected
- All generated strategies pass validation
- Kill switches functioning correctly
- API reliability >95%
- No missing/invalid data

### ❌ FAIL (Need Adjustments)
- Signal frequency <0.5 or >3 per week
- Only one regime detected entire period
- Strategies fail validation checks
- Kill switches not triggering when they should
- Frequent API errors (>10%)
- Missing/invalid option chain data

## Red Flags 🚩

Stop and review if you see:

1. **Signal frequency >3/week**: System too aggressive
2. **No signals for 2+ weeks**: System too conservative or data issues
3. **Repeated API errors**: Check credentials/connectivity
4. **Invalid strategies**: Check option chain data quality
5. **All trades rejected for same reason**: Configuration issue

## Troubleshooting

### Access Token Expired (401 Error)
**Solution**: Generate new token daily from Upstox dashboard
```bash
export UPSTOX_ACCESS_TOKEN="your_new_token"
```

### Empty Option Chain
**Solution**: 
- Check market hours (9:15 AM - 3:30 PM IST)
- Verify expiry date is valid (weekly Thursday)

### Rate Limit Exceeded
**Solution**: Increase check interval
```bash
python scripts/dry_run_options_system.py --interval 120  # 2 hours
```

### No Signals Generated
**Possible reasons** (all normal):
- Regime not persistent (need 2 days)
- IV rank not in tradeable zone
- Time blocks active (Monday morning, Thursday)
- Event calendar blocks (near RBI/CPI/WPI)

## Configuration Tuning

If needed, edit `config/options_trading.yaml`:

### Make More Selective (Fewer Signals)
```yaml
regime_detection:
  regime_persistence_days: 3  # Increase from 2

eligibility:
  max_bid_ask_spread_pct: 0.06  # Stricter liquidity

survival_rules:
  max_trades_per_week: 1  # Decrease from 2
```

### Make More Active (More Signals)
```yaml
regime_detection:
  regime_persistence_days: 1  # Decrease from 2
  low_vol_sell_iv_rank: 0.65  # Lower threshold

eligibility:
  max_bid_ask_spread_pct: 0.10  # Looser liquidity
```

## Next Steps

### After 1-2 Weeks:

1. **Review Final Report**
   - Check signal frequency (target: ~2/week)
   - Verify regime distribution
   - Review rejection reasons

2. **If PASS**:
   - Manually verify a few generated strategies
   - Start paper trading (manual execution, small size)
   - After 2-4 successful paper trades → Go live with full size

3. **If FAIL**:
   - Identify root cause from logs
   - Adjust configuration
   - Run another 1-2 week dry run
   - Do NOT go live until validation passes

## Important Reminders

🚨 **This is a DRY RUN - No trades are executed**

✅ **Validate for 1-2 weeks minimum before going live**

📊 **Target: ~2 signals per week (selectivity over activity)**

🛡️ **Kill switches must work correctly before going live**

⏰ **Access tokens expire daily - regenerate as needed**

🔍 **Monitor daily, review weekly, validate thoroughly**

## Support

If you encounter issues:

1. Check `logs/dry_run.log` for detailed error messages
2. Review `data/dry_run/cycle_results.csv` for patterns
3. Verify Upstox API credentials and connectivity
4. Ensure market is open during checks (9:15 AM - 3:30 PM IST)
5. Check system time is set to IST

## Ready to Start?

```bash
# Create directories
mkdir -p logs data/dry_run

# Start 14-day validation
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

**Monitor daily. Review weekly. Validate thoroughly. Good luck! 🚀**

---

## Summary

You now have a complete dry-run system that will:
- ✅ Fetch real option chain data from Upstox
- ✅ Run complete signal generation pipeline
- ✅ Validate regime detection accuracy
- ✅ Test strategy generation quality
- ✅ Monitor signal frequency (~2/week target)
- ✅ Verify kill switch behavior
- ✅ Log all decisions without executing trades
- ✅ Generate comprehensive validation reports

Run for 1-2 weeks, validate thoroughly, then proceed to paper trading. The system is designed to be selective and safe - "not dying in options" is the priority.
