# Options System V3 Integration Guide

## Overview

The options trading system is now fully integrated into the Northstar V3 platform. This guide covers:

1. **Daily Token Refresh** - How to update your Upstox access token
2. **Running Options Cycles** - Automated and manual execution
3. **Dashboard Integration** - Monitoring options positions alongside equity portfolio
4. **Historical Data** - Bootstrapping and maintaining option chain history
5. **Troubleshooting** - Common issues and solutions

---

## 1. Daily Token Refresh

Upstox access tokens expire after 24 hours. You must refresh your token each trading day before market hours.

### Quick Start

```bash
# Run the token refresh script
python scripts/refresh_upstox_token.py
```

### Manual Process

1. **Visit Authorization URL** (provided by script)
2. **Log in** to Upstox and authorize the app
3. **Copy the redirect URL** from your browser
4. **Paste it** into the script prompt
5. **Token is saved** to `.env.options` automatically

### Automation (Optional)

You can automate token refresh using a cron job or scheduler, but you'll need to handle the OAuth flow programmatically. For most users, running the script manually each morning is simplest.

---

## 2. Running Options Cycles

### Integrated with V3 System

The options engine runs automatically as part of the complete V3 system:

```bash
# Full system run (includes options)
python run_complete_v3_system.py

# Quick run (skips backtesting)
python run_complete_v3_system.py --quick
```

### Standalone Options Engine

For focused options trading without the full V3 pipeline:

```bash
# Single cycle (manual execution)
python scripts/run_integrated_options_paper_engine.py \
    --mode single \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY \
    --aggressive

# Continuous mode (runs every N minutes)
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 15 \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY \
    --aggressive

# Market hours only
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 5 \
    --market-hours-only \
    --aggressive

# Using seconds instead of minutes
python scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-seconds 300 \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY \
    --aggressive
```

### Configuration

Edit `config/options_trading.yaml` to customize:

- **Capital**: Base capital, risk percentages, scaling rules
- **Underlyings**: Which indices/stocks to trade
- **Strategies**: Enable/disable specific option strategies
- **Risk Limits**: Position limits, max loss, Greeks constraints
- **Execution**: Slippage, commissions, market hours

---

## 3. Dashboard Integration

### Unified Dashboard

The main V3 dashboard now includes an **Options** tab:

```bash
# Launch integrated dashboard
python run_complete_v3_system.py
# Then visit: http://localhost:8501
```

### Volatility Dashboard (Standalone)

For detailed options-only monitoring:

```bash
# Launch volatility dashboard
python scripts/run_live_engine.py
# Then visit: http://localhost:8502
```

### Dashboard Features

- **Live Positions**: Current open positions with P&L
- **Trade History**: All executed trades with performance metrics
- **Regime Detection**: Current volatility regime per underlying
- **Greeks Exposure**: Portfolio-level Greeks aggregation
- **Capital Scaling**: Dynamic risk adjustment based on performance
- **Eligibility Checks**: Real-time trade validation status

---

## 4. Historical Data

### Why Historical Data?

- **Backtesting**: Test strategies on past market conditions
- **Regime Calibration**: Train volatility regime detector
- **IV Surface Modeling**: Build accurate implied volatility surfaces
- **Offline Fallback**: Continue operations when API is unavailable

### Collecting Historical Chains

```bash
# Quick start (last 30 days)
bash scripts/quick_start_historical_collection.sh

# Full collection (custom date range)
python scripts/collect_historical_option_chains.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --underlyings NIFTY,BANKNIFTY,FINNIFTY
```

### Daily EOD Collection

Set up a cron job to collect end-of-day chains:

```bash
# Add to crontab (runs at 4 PM IST daily)
0 16 * * 1-5 cd /path/to/northstar_v3 && python scripts/daily_eod_option_chain_collector.py
```

### Validating Historical Data

```bash
# Check data quality and coverage
python scripts/validate_historical_data.py
```

---

## 5. Aggressive Mode

Aggressive mode increases trade frequency and position sizing:

### What It Does

1. **Regime Override**: Treats NEUTRAL regime as actionable
   - If IV rank ≥ 50%: Sell premium (LOW_VOL_SELL)
   - If IV rank < 50%: Buy options (RISING_VOL_BUY)

2. **Relaxed Filters**: Loosens some eligibility constraints
   - Allows trades in borderline regimes
   - Accepts slightly wider bid-ask spreads

3. **Position Scaling**: Uses capital scaling engine aggressively
   - Scales up faster after profitable milestones
   - Maintains higher base risk percentage

### When to Use

- **High Conviction**: You have strong views on market direction
- **Volatile Markets**: Frequent regime changes create opportunities
- **Testing Phase**: Generating more trades for strategy validation

### When NOT to Use

- **Uncertain Markets**: Low confidence in regime detection
- **Capital Preservation**: Prioritizing safety over returns
- **Live Trading Start**: Begin conservatively, scale up gradually

---

## 6. Offline Fallback

The system now includes offline fallback for API outages:

### Chain Cache

- **Automatic**: Successful API fetches are cached to disk
- **Location**: `data/options/chains_cache/`
- **Retention**: Last 10 chains per underlying
- **Usage**: Automatically loaded when API fails

### Manual Cache Seeding

```bash
# Pre-populate cache before market hours
python scripts/run_integrated_options_paper_engine.py --mode single
```

---

## 7. Monitoring & Alerts

### Key Files to Watch

```
data/options/
├── trade_ledger.parquet          # All trades
├── positions_state.json          # Current positions
├── capital_scaling_state.json    # Risk scaling state
└── chains_cache/                 # Cached option chains

data/dashboard/
└── options_dashboard.parquet     # Dashboard snapshot
```

### Health Checks

```bash
# Check system status
python scripts/health_check.py

# View current positions
python scripts/status.py
```

### Emergency Procedures

```bash
# Close all positions immediately
python scripts/emergency_reduce.py --close-all

# Reduce exposure by 50%
python scripts/emergency_reduce.py --reduce-by 0.5
```

---

## 8. Troubleshooting

### Token Issues

**Problem**: `401 Unauthorized` errors

**Solution**:
```bash
# Refresh token
python scripts/refresh_upstox_token.py

# Verify token in .env.options
grep UPSTOX_ACCESS_TOKEN .env.options
```

### No Trades Generated

**Problem**: Cycles run but no trades are opened

**Possible Causes**:
1. **Regime Not Actionable**: Current regime doesn't match any strategy
   - Solution: Use `--aggressive` flag or wait for regime change
   
2. **Eligibility Failures**: Trades rejected by validation rules
   - Check: `data/options/positions_state.json` → `last_eligibility_checks`
   - Solution: Review and adjust eligibility rules in config

3. **Position Limits**: Already at max open positions
   - Check: `data/options/positions_state.json` → `open_positions`
   - Solution: Close some positions or increase limits

4. **Capital Constraints**: Insufficient capital for position sizing
   - Check: `data/options/capital_scaling_state.json`
   - Solution: Increase base capital or reduce position size

### API Rate Limits

**Problem**: `429 Too Many Requests` errors

**Solution**:
```yaml
# In config/options_trading.yaml
upstox:
  rate_limit_delay: 1.0  # Increase delay between requests
```

### Stale Dashboard Data

**Problem**: Dashboard shows old data

**Solution**:
```bash
# Force refresh
rm data/dashboard/options_dashboard.parquet
python scripts/run_integrated_options_paper_engine.py --mode single
```

### Timezone Issues

**Problem**: Trades executed at wrong times

**Solution**:
```python
# Verify system timezone
python -c "from datetime import datetime; print(datetime.now().astimezone())"

# Should show IST (UTC+5:30)
```

---

## 9. Performance Optimization

### Reduce API Calls

```yaml
# In config/options_trading.yaml
execution:
  cache_chains: true
  cache_ttl_seconds: 300  # 5 minutes
```

### Parallel Underlying Processing

```python
# In scripts/run_integrated_options_paper_engine.py
# Set max_workers for concurrent chain fetches
executor = ThreadPoolExecutor(max_workers=3)
```

### Database Optimization

```bash
# Compact trade ledger (monthly)
python scripts/compact_trade_ledger.py
```

---

## 10. Next Steps

### Week 1: Paper Trading

- Run in `--aggressive` mode to generate trades
- Monitor dashboard daily
- Review trade decisions and P&L
- Adjust config based on observations

### Week 2-4: Strategy Refinement

- Analyze trade performance by strategy type
- Tune eligibility rules
- Optimize position sizing
- Test different regime detection parameters

### Month 2+: Live Trading Preparation

- Validate capital scaling behavior
- Test emergency procedures
- Set up monitoring alerts
- Document your trading rules
- Start with small capital allocation

---

## Support & Resources

- **Architecture**: `docs/UNIFIED_VOLATILITY_ENGINE_ARCHITECTURE.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Operator Guide**: `docs/OPERATOR_GUIDE.md`
- **Emergency Procedures**: `docs/EMERGENCY_PROCEDURES.md`

---

## Quick Reference

```bash
# Daily routine
python scripts/refresh_upstox_token.py
python run_complete_v3_system.py --quick

# Monitor
python scripts/status.py
python scripts/health_check.py

# Emergency
python scripts/emergency_reduce.py --close-all
```

---

**Last Updated**: 2026-02-12  
**Version**: 3.0.0  
**Status**: Production Ready
