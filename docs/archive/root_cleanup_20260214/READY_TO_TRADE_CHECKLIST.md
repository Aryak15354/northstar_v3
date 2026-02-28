# ✅ Ready to Trade - Pre-Flight Checklist

## 🎯 System Status: READY FOR AGGRESSIVE PAPER TRADING

Use this checklist before starting your first trading session.

---

## 📋 Pre-Flight Checklist

### 1. Environment Setup

- [ ] `.env.options` file exists and contains your credentials
- [ ] `UPSTOX_API_KEY` is set
- [ ] `UPSTOX_API_SECRET` is set
- [ ] `UPSTOX_REDIRECT_URI` is set
- [ ] Python environment activated (`northstar_v7_env_m1`)
- [ ] All dependencies installed

**Verify:**
```bash
cat .env.options | grep -E "UPSTOX_API_KEY|UPSTOX_API_SECRET"
```

---

### 2. Token Management

- [ ] Upstox token refreshed today
- [ ] Token refresh script tested
- [ ] Token validation passed

**Verify:**
```bash
python scripts/refresh_upstox_token.py
# Follow the prompts
```

---

### 3. Configuration

- [ ] `config/options_trading.yaml` reviewed
- [ ] Base capital set correctly
- [ ] Risk percentages appropriate
- [ ] Underlyings list configured
- [ ] Position limits set

**Verify:**
```bash
grep -A 5 "capital:" config/options_trading.yaml
```

---

### 4. Data Directories

- [ ] `data/options/` directory exists
- [ ] `data/options/chains_cache/` directory exists
- [ ] `data/dashboard/` directory exists
- [ ] Write permissions verified

**Verify:**
```bash
mkdir -p data/options/chains_cache data/dashboard
ls -la data/options/
```

---

### 5. System Components

- [ ] Core engine compiles without errors
- [ ] Dashboard loads successfully
- [ ] Token refresh script works
- [ ] Emergency scripts accessible

**Verify:**
```bash
python3 -m py_compile scripts/run_integrated_options_paper_engine.py
python3 -m py_compile scripts/refresh_upstox_token.py
python3 -m py_compile scripts/emergency_reduce.py
```

---

### 6. Documentation

- [ ] Read `OPTIONS_INTEGRATION_COMPLETE.md`
- [ ] Read `docs/OPTIONS_V3_INTEGRATION_GUIDE.md`
- [ ] Understand aggressive mode behavior
- [ ] Know emergency procedures

**Key Docs:**
- Integration guide: `docs/OPTIONS_V3_INTEGRATION_GUIDE.md`
- Emergency procedures: `docs/EMERGENCY_PROCEDURES.md`

---

### 7. Test Run

- [ ] Single cycle test completed successfully
- [ ] Dashboard displays data
- [ ] Position state files created
- [ ] No critical errors in logs

**Test:**
```bash
python scripts/run_integrated_options_paper_engine.py \
    --mode single \
    --underlyings NIFTY \
    --aggressive
```

**Expected Output:**
- Fetches option chain
- Detects regime
- Generates strategy (if regime is actionable)
- Creates position state files
- Updates dashboard

---

### 8. Monitoring Setup

- [ ] Know how to check positions (`scripts/status.py`)
- [ ] Know how to check health (`scripts/health_check.py`)
- [ ] Dashboard URL bookmarked (http://localhost:8501)
- [ ] Emergency procedures memorized

**Quick Commands:**
```bash
# Status
python scripts/status.py

# Health
python scripts/health_check.py

# Emergency
python scripts/emergency_reduce.py --close-all
```

---

### 9. Risk Management

- [ ] Understand capital scaling rules
- [ ] Know position limits
- [ ] Understand max loss per trade
- [ ] Emergency stop procedure clear

**Key Limits:**
- Base risk: 1.0% per trade
- Max risk: 1.5% per trade
- Max open positions: Check config
- Max loss per position: Check config

---

### 10. Aggressive Mode Understanding

- [ ] Understand regime override logic
- [ ] Know increased trade frequency
- [ ] Aware of relaxed filters
- [ ] Comfortable with higher activity

**Aggressive Mode:**
- Runs every 5 minutes
- Treats NEUTRAL as actionable
- More trades = more data
- Higher capital utilization

---

## 🚀 Launch Sequence

Once all items are checked, you're ready to start:

### Option A: Interactive Menu (Recommended)

```bash
./START_OPTIONS_SYSTEM.sh
# Choose option 3: Aggressive mode
```

### Option B: Direct Command

```bash
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 5 \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY \
    --aggressive \
    --market-hours-only
```

### Option C: Full V3 System

```bash
python run_complete_v3_system.py --quick
# Options engine runs automatically
```

---

## 📊 First Hour Checklist

After starting, verify within the first hour:

- [ ] Engine is running without crashes
- [ ] Option chains fetching successfully
- [ ] Regimes being detected
- [ ] Strategies being generated
- [ ] Dashboard updating
- [ ] Position state files updating

**Monitor:**
```bash
# In another terminal
watch -n 60 python scripts/status.py
```

---

## 🎯 First Day Goals

- [ ] System runs for full trading day
- [ ] At least 1 trade executed
- [ ] Dashboard shows accurate data
- [ ] P&L calculations correct
- [ ] No system crashes
- [ ] Logs reviewed for errors

---

## 📈 First Week Goals

- [ ] 10+ trades executed
- [ ] Multiple regime transitions observed
- [ ] Capital scaling working
- [ ] All strategies tested
- [ ] Performance metrics collected
- [ ] Config adjustments documented

---

## 🚨 Emergency Contacts

### If Something Goes Wrong

1. **Stop the engine**: Press `Ctrl+C`
2. **Close positions**: `python scripts/emergency_reduce.py --close-all`
3. **Check logs**: Review console output
4. **Check state**: `python scripts/status.py`
5. **Review docs**: `docs/EMERGENCY_PROCEDURES.md`

### Common Issues

| Issue | Solution |
|-------|----------|
| Token expired | `python scripts/refresh_upstox_token.py` |
| No trades | Use `--aggressive` flag |
| API errors | Check internet, verify token |
| Dashboard stale | Delete cache, restart |

---

## ✅ Final Verification

Before you start trading, answer these questions:

1. **Do you understand what aggressive mode does?**
   - [ ] Yes, I understand it trades more frequently

2. **Do you know how to stop the system?**
   - [ ] Yes, Ctrl+C or emergency_reduce.py

3. **Do you know how to monitor positions?**
   - [ ] Yes, dashboard and status.py

4. **Do you understand this is paper trading?**
   - [ ] Yes, no real money at risk

5. **Are you ready to monitor actively?**
   - [ ] Yes, I will check regularly

---

## 🎉 You're Ready!

If all items are checked, you're ready to start aggressive paper trading.

### Launch Command

```bash
./START_OPTIONS_SYSTEM.sh
```

Choose option 3 for aggressive mode.

### Monitor

Visit: http://localhost:8501 (Options tab)

### Daily Routine

```bash
# Morning
python scripts/refresh_upstox_token.py
./START_OPTIONS_SYSTEM.sh

# Throughout day
# Monitor dashboard

# Evening
python scripts/status.py
# Review and document
```

---

**Good luck and happy trading! 📈🚀**

---

## 📝 Notes Section

Use this space to document your first session:

**Date Started**: _______________

**Initial Observations**:
- 
- 
- 

**Issues Encountered**:
- 
- 
- 

**Config Changes Made**:
- 
- 
- 

**Performance Notes**:
- 
- 
- 

---

**Checklist Completed**: [ ]  
**Ready to Trade**: [ ]  
**First Trade Executed**: [ ]  
**First Day Complete**: [ ]  
**First Week Complete**: [ ]
