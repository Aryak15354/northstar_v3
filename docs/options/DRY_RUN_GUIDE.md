# Dry Run Guide - Options Trading System

## Overview

The dry run script runs the complete options trading system with **real Upstox API data** but **WITHOUT executing any trades**. This allows you to validate the system for 1-2 weeks before going live.

## What Gets Validated

### 1. Regime Detection Accuracy
- IV rank calculations
- Regime classification (LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, etc.)
- Regime persistence (2-day requirement)
- Vol-of-vol detection
- Equity crisis integration

### 2. Strategy Generation Quality
- Iron Condor construction (strike selection, delta targeting)
- Calendar Spread construction
- Long Straddle construction
- Premium adequacy checks
- Lot size validation

### 3. Signal Frequency
- **Target: ~2 trades/week maximum**
- Validates that system is selective, not overactive
- Tracks signal rate over time

### 4. Kill Switch Behavior
- Weekly loss limit (2%)
- Trauma rule (>80% loss blocks short-vol for 2 weeks)
- Portfolio risk cap (2% total)
- Tax liquidity check
- Frequency limits (max 2 trades/week)
- Time-based blocks (Monday 9:15-10:00 AM, Thursday expiry)

### 5. Eligibility Rules
- IV rank thresholds
- Liquidity checks (bid-ask spread, depth)
- Expiry hygiene (min 5 days)
- Event calendar blocks
- Late-cycle protection

## Setup

### 1. API Credentials

Your Upstox credentials are already configured in the script:
- **API Key**: d54cd69b-6ced-4003-a5e3-b25e5608b660
- **API Secret**: jxmubrf4nd
- **Access Token**: (provided - expires daily)

**Note**: Access tokens expire daily. You'll need to generate a new token each day from the Upstox dashboard.

### 2. Environment Setup

```bash
# Create logs directory
mkdir -p logs

# Create data directory
mkdir -p data/dry_run

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

## Running the Dry Run

### Single Cycle (Test Run)

Run a single check to verify everything works:

```bash
python scripts/dry_run_options_system.py --mode single --underlying NIFTY
```

This will:
1. Fetch current option chain from Upstox
2. Detect market regime
3. Generate strategy (if applicable)
4. Check all eligibility rules
5. Check all kill switches
6. Log the decision

### Continuous Monitoring (1-2 Weeks)

Run continuous monitoring for validation:

```bash
# Monitor for 14 days, check every hour
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

Parameters:
- `--duration`: Days to monitor (default: 14)
- `--interval`: Minutes between checks (default: 60)
- `--underlying`: NIFTY, BANKNIFTY, or BOTH

### Recommended Schedule

**Week 1-2**: Hourly checks during market hours (9:15 AM - 3:30 PM IST)
```bash
# Run during market hours only
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

## Output Files

All output is saved to `data/dry_run/`:

### 1. `cycle_results.csv`
Complete log of every check cycle:
- Timestamp
- Underlying
- Signal generated (yes/no)
- Regime detected
- Strategy type
- Max loss/profit
- Rejection reasons

### 2. `signals.log`
Detailed log of every signal generated:
- Full strategy details
- Position sizing
- Capital at risk
- Greeks

### 3. `final_report.txt`
Summary report at end of dry run:
- Total cycles run
- Signals generated
- Signal frequency (per week)
- Regime distribution
- Strategy distribution
- Top rejection reasons
- **PASS/FAIL validation**

### 4. `logs/dry_run.log`
Complete system log with all decisions and reasoning.

## Monitoring During Dry Run

### Daily Checks

1. **Signal Frequency**: Should see ~2 signals per week maximum
   - If seeing more: System too aggressive, review thresholds
   - If seeing less: System too conservative, but acceptable

2. **Regime Detection**: Should see regime changes
   - LOW_VOL_SELL: Most common in stable markets
   - HIGH_VOL_SELL: During elevated volatility
   - RISING_VOL_BUY: Rare, during vol expansion
   - NEUTRAL: When no clear regime

3. **Rejection Reasons**: Track why trades are rejected
   - Most common: Regime not persistent, liquidity issues
   - Kill switches: Should be rare (good sign)

4. **Kill Switch Activations**: Should be ZERO in dry run
   - If kill switches trigger: Review configuration
   - Weekly loss: Not applicable (no real trades)
   - Time blocks: Should see Monday morning and Thursday blocks

### Red Flags

⚠️ **Stop and review if you see:**

1. **Signal frequency > 3/week**: System too aggressive
2. **No signals for 2+ weeks**: System too conservative or data issues
3. **Repeated API errors**: Check Upstox credentials/connectivity
4. **Invalid strategies**: Check option chain data quality
5. **All trades rejected for same reason**: Configuration issue

## Validation Criteria

After 1-2 weeks, the system should show:

### ✅ PASS Criteria

1. **Signal Frequency**: 1-2.5 signals per week
2. **Regime Detection**: Multiple regime types detected
3. **Strategy Quality**: All generated strategies pass validation
4. **Kill Switches**: Functioning correctly (time blocks work)
5. **API Reliability**: <5% API error rate
6. **Data Quality**: No missing/invalid option chain data

### ❌ FAIL Criteria

1. Signal frequency >3/week or <0.5/week
2. Only one regime detected entire period
3. Strategies fail validation checks
4. Kill switches not triggering when they should
5. Frequent API errors (>10%)
6. Missing/invalid data

## Troubleshooting

### Access Token Expired

**Error**: `401 Unauthorized`

**Solution**: Generate new access token from Upstox dashboard
1. Go to https://api.upstox.com/
2. Login and generate new token
3. Update token in script or set environment variable:
   ```bash
   export UPSTOX_ACCESS_TOKEN="your_new_token"
   ```

### Empty Option Chain

**Error**: `Empty option chain received`

**Solution**: 
- Check if market is open (9:15 AM - 3:30 PM IST)
- Verify expiry date is valid (weekly Thursday)
- Check Upstox API status

### Rate Limit Exceeded

**Error**: `Rate limit exceeded`

**Solution**: Script already implements rate limiting (1 req/sec)
- If still seeing errors, increase interval between checks
- Use `--interval 120` (2 hours) instead of 60 minutes

### No Signals Generated

**Possible reasons**:
1. Regime not persistent (need 2 days) - **Normal**
2. IV rank not in tradeable zone - **Normal**
3. Liquidity issues - Check option chain quality
4. Time blocks active - Check if Monday morning or Thursday
5. Event calendar blocks - Check if near RBI/CPI/WPI dates

## Next Steps After Dry Run

### If PASS:

1. Review final report thoroughly
2. Verify signal quality manually (check a few strategies)
3. Confirm kill switches work as expected
4. **Proceed to paper trading** (manual execution with small size)
5. After 2-4 successful paper trades, go live with full size

### If FAIL:

1. Identify root cause from logs
2. Adjust configuration:
   - IV rank thresholds
   - Regime persistence days
   - Liquidity requirements
   - Event calendar
3. Run another 1-2 week dry run
4. Do NOT go live until validation passes

## Configuration Adjustments

If you need to tune the system, edit `config/options_trading.yaml`:

### Make System More Selective (Fewer Signals)
```yaml
regime_detection:
  regime_persistence_days: 3  # Increase from 2
  
eligibility:
  max_bid_ask_spread_pct: 0.06  # Decrease from 0.08 (stricter liquidity)
  
survival_rules:
  max_trades_per_week: 1  # Decrease from 2
```

### Make System More Active (More Signals)
```yaml
regime_detection:
  regime_persistence_days: 1  # Decrease from 2
  low_vol_sell_iv_rank: 0.65  # Decrease from 0.70
  
eligibility:
  max_bid_ask_spread_pct: 0.10  # Increase from 0.08 (looser liquidity)
```

## Support

If you encounter issues:

1. Check `logs/dry_run.log` for detailed error messages
2. Review `data/dry_run/cycle_results.csv` for patterns
3. Verify Upstox API credentials and connectivity
4. Ensure market is open during checks
5. Check system time is set to IST

## Important Reminders

🚨 **This is a DRY RUN - No trades are executed**

✅ **Validate for 1-2 weeks minimum before going live**

📊 **Target: ~2 signals per week (selectivity over activity)**

🛡️ **Kill switches must work correctly before going live**

⏰ **Access tokens expire daily - regenerate as needed**

---

**Ready to start?**

```bash
python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH
```

Monitor daily, review weekly, validate thoroughly. Good luck! 🚀
