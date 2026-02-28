# 🚀 START YOUR DRY RUN HERE

## Quick Start (3 Steps)

### Step 1: Setup
```bash
bash scripts/setup_dry_run.sh
```

### Step 2: Test (Single Cycle)
```bash
python scripts/dry_run_options_system.py --mode single --underlying NIFTY
```

### Step 3: Start 14-Day Validation
```bash
python scripts/dry_run_options_system.py \
    --mode continuous \
    --duration 14 \
    --interval 60 \
    --underlying BOTH
```

---

## What This Does

✅ **Fetches real option chain data** from Upstox API  
✅ **Runs complete signal generation** (regime → strategy → eligibility → kill switches)  
✅ **Logs all decisions** without executing trades  
✅ **Validates system** for 1-2 weeks  
✅ **Generates reports** with PASS/FAIL criteria  

---

## Your API Credentials

Already configured in the script:
- **API Key**: d54cd69b-6ced-4003-a5e3-b25e5608b660
- **API Secret**: jxmubrf4nd
- **Access Token**: (expires daily - regenerate from Upstox)

⚠️ **Token expires daily** - generate new one from Upstox dashboard each day

### How to Get New Token Daily

1. Go to https://api.upstox.com/
2. Login → Apps → Your App → Generate Token
3. Copy the new token
4. Set it:
   ```bash
   export UPSTOX_ACCESS_TOKEN="your_new_token"
   ```

📖 **Full guide**: `docs/options/TOKEN_REFRESH_GUIDE.md`

---

## What to Expect

### Signal Frequency
- **Target**: ~2 signals per week
- **Acceptable**: 1-2.5 signals/week
- **Too high**: >3 signals/week
- **Too low**: <0.5 signals/week

### Regime Types
- **LOW_VOL_SELL**: Most common (stable markets)
- **HIGH_VOL_SELL**: Elevated volatility
- **RISING_VOL_BUY**: Rare (vol expansion)
- **NEUTRAL**: No clear regime
- **CRASH_HEDGE**: Extreme conditions

### Kill Switches (Should Block)
- Monday 9:15-10:00 AM IST
- Thursday (expiry day)
- 2 days before RBI/CPI/WPI
- After 2 trades in same week

---

## Output Files

### `data/dry_run/cycle_results.csv`
Every check cycle logged

### `data/dry_run/signals.log`
Detailed signal information

### `data/dry_run/final_report.txt`
Summary with PASS/FAIL

### `logs/dry_run.log`
Complete system log

---

## Daily Checklist

- [ ] Check signal count (~0-1 per day)
- [ ] Review API errors (<5%)
- [ ] Monitor regime changes
- [ ] Track rejection reasons
- [ ] Verify kill switches work

---

## Validation Criteria

### ✅ PASS
- Signal frequency: 1-2.5/week
- Multiple regimes detected
- Strategies pass validation
- Kill switches work
- API reliability >95%

### ❌ FAIL
- Signal frequency <0.5 or >3/week
- Only one regime detected
- Strategies fail validation
- Kill switches not working
- API errors >10%

---

## After 1-2 Weeks

### If PASS:
1. Review final report
2. Verify strategies manually
3. Start paper trading (small size)
4. After 2-4 successful trades → Go live

### If FAIL:
1. Identify root cause
2. Adjust configuration
3. Run another dry run
4. Do NOT go live

---

## Troubleshooting

### Token Expired (401)
```bash
export UPSTOX_ACCESS_TOKEN="your_new_token"
```

### Empty Option Chain
- Check market hours (9:15 AM - 3:30 PM IST)
- Verify expiry date

### Rate Limit
```bash
python scripts/dry_run_options_system.py --interval 120
```

---

## Documentation

📖 **Quick Reference**: `docs/options/DRY_RUN_QUICK_START.md`  
📚 **Complete Guide**: `docs/options/DRY_RUN_GUIDE.md`  
✅ **Setup Summary**: `DRY_RUN_SETUP_COMPLETE.md`  

---

## Ready?

```bash
# Setup
bash scripts/setup_dry_run.sh

# Test
python scripts/dry_run_options_system.py --mode single --underlying NIFTY

# Start 14-day validation
python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH
```

**Monitor daily. Review weekly. Validate thoroughly. 🚀**

---

## Important Reminders

🚨 **DRY RUN = NO TRADES EXECUTED**  
⏱️ **Validate 1-2 weeks minimum**  
📊 **Target: ~2 signals/week**  
🛡️ **Kill switches must work**  
🔄 **Token expires daily**  

---

**Questions?** Check the guides in `docs/options/`

**Ready to start?** Run the commands above! 🎯
