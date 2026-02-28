# Options Trading System - Operator Runbook

## Overview

This runbook provides operational procedures for managing the Options Trading System. It covers routine operations, incident response, and system maintenance.

**Audience**: System operators, trading desk personnel, technical support

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Kill Switch Management](#kill-switch-management)
3. [Trade Rejection Review](#trade-rejection-review)
4. [Trade Ledger Audit](#trade-ledger-audit)
5. [Event Calendar Updates](#event-calendar-updates)
6. [System Health Monitoring](#system-health-monitoring)
7. [Incident Response](#incident-response)
8. [Maintenance Procedures](#maintenance-procedures)

---

## Daily Operations

### Pre-Market Checklist (Before 9:15 AM IST)

**Time**: 9:00 AM - 9:15 AM IST

1. **Verify System Status**
   ```bash
   # Check if dashboard is running
   ps aux | grep streamlit
   
   # Check logs for errors
   tail -n 50 logs/options_trading.log
   ```

2. **Check Kill Switch Status**
   - Open dashboard
   - Navigate to Options Trading panel
   - Verify "Kill Switch Status" section shows all green
   - If any red flags, follow [Kill Switch Management](#kill-switch-management)

3. **Review Weekly P&L**
   - Check "Weekly Risk Used" metric
   - If > 80%, prepare for potential weekly limit hit
   - If limit hit, no trading allowed until Monday reset

4. **Verify API Connectivity**
   ```bash
   # Test Upstox API connection
   python -c "from src.options.upstox_adapter import UpstoxAdapter; \
              adapter = UpstoxAdapter(); \
              print('API Status:', adapter.check_connection())"
   ```

5. **Check Event Calendar**
   - Review upcoming macro events
   - Verify 2-day buffer before events
   - Update calendar if needed (see [Event Calendar Updates](#event-calendar-updates))

### Intraday Monitoring (9:15 AM - 3:30 PM IST)

**Frequency**: Every 30 minutes

1. **Monitor Active Positions**
   - Check "Active Positions" table
   - Verify P&L updates are current
   - Look for exit signals

2. **Watch Portfolio Greeks**
   - Ensure all Greeks within safety bands
   - If violations, alert trader immediately
   - Document any Greek escalations

3. **Track Regime Changes**
   - Monitor "Current Regime" section
   - Note any regime flips
   - Check if positions need closing due to regime change

4. **Review System Logs**
   ```bash
   # Check for errors in last 30 minutes
   tail -n 100 logs/options_trading.log | grep ERROR
   
   # Check for warnings
   tail -n 100 logs/options_trading.log | grep WARN
   ```

### Post-Market Checklist (After 3:30 PM IST)

**Time**: 3:30 PM - 4:00 PM IST

1. **Review Day's Activity**
   - Check trade history for new trades
   - Verify all trades recorded in ledger
   - Calculate day's P&L

2. **Update Position Status**
   - Mark-to-market all positions
   - Update unrealized P&L
   - Check days to expiry for all positions

3. **Generate Daily Report**
   ```bash
   python scripts/generate_daily_options_report.py
   ```

4. **Backup Trade Ledger**
   ```bash
   cp data/options/trade_ledger.parquet \
      backups/trade_ledger_$(date +%Y%m%d).parquet
   ```

5. **Check for Alerts**
   - Review any system warnings
   - Document unusual events
   - Prepare notes for next day

---

## Kill Switch Management

### Types of Kill Switches

#### 1. Weekly Loss Limit (2%)

**Trigger**: Weekly P&L ≤ -2% of capital

**Status Check**:
```bash
python -c "from src.options.survival_rules_engine import SurvivalRulesEngine; \
           from src.options.config_loader import get_config; \
           config = get_config(); \
           engine = SurvivalRulesEngine(config.survival_rules, 100000); \
           print('Weekly Loss Status:', engine.get_weekly_loss_status())"
```

**Response Procedure**:
1. Verify kill switch is active on dashboard
2. Notify all traders - NO NEW TRADES until Monday reset
3. Review what caused the losses
4. Document lessons learned
5. Prepare risk review for Monday

**Reset**: Automatic at Monday 9:15 AM IST

**Override**: NOT ALLOWED - this is a hard stop

#### 2. Portfolio Risk Cap (2%)

**Trigger**: Sum of max losses across positions > 2% of capital

**Status Check**:
- Dashboard shows "Portfolio Risk" metric
- Red if > 2%

**Response Procedure**:
1. Calculate current portfolio risk:
   ```python
   total_risk = sum(position.max_loss for position in active_positions)
   risk_pct = total_risk / capital
   ```

2. If > 2%:
   - Block new trades
   - Identify positions to close
   - Close least favorable positions first
   - Recheck after each close

3. Once < 2%, new trades allowed

**Reset**: Automatic when positions closed

**Override**: NOT ALLOWED

#### 3. Trauma Rule

**Trigger**: Single trade loses > 80% of max loss

**Status Check**:
- Dashboard shows "Trauma Block Active" if triggered
- Shows block end date

**Response Procedure**:
1. Verify trauma trigger:
   - Check which trade triggered it
   - Review trade details
   - Calculate actual loss vs max loss

2. Document incident:
   - What went wrong?
   - Was it preventable?
   - What can be improved?

3. Notify traders:
   - Short-vol strategies blocked for 2 weeks
   - Long-vol strategies still allowed
   - Show block end date

4. Schedule post-mortem meeting

**Reset**: Automatic after 2 weeks

**Override**: Requires senior management approval + documented justification

#### 4. Tax Liquidity Check

**Trigger**: YTD tax liability > cash buffer

**Status Check**:
```bash
python -c "from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker; \
           tracker = TaxAwarePnLTracker(); \
           print('Tax Liability:', tracker.get_ytd_tax_liability())"
```

**Response Procedure**:
1. Calculate exact tax liability
2. Verify cash buffer amount
3. If triggered:
   - Block new trades
   - Set aside cash for taxes
   - Reduce position sizes
4. Resume trading once buffer restored

**Reset**: Manual after cash set aside

**Override**: NOT RECOMMENDED

### Kill Switch Override Process

**IMPORTANT**: Kill switches exist for capital protection. Overrides should be RARE.

**Override Authority**:
- Weekly Loss Limit: NO OVERRIDE
- Portfolio Risk Cap: NO OVERRIDE
- Trauma Rule: Senior Management Only
- Tax Liquidity: Risk Manager Approval

**Override Procedure**:
1. Document override request
2. Explain justification
3. Get required approval
4. Update system configuration
5. Log override in audit trail
6. Monitor closely

---

## Trade Rejection Review

### Daily Rejection Analysis

**When**: End of each trading day

**Procedure**:

1. **Extract Rejections**
   ```bash
   grep "Trade REJECTED" logs/options_trading.log | tail -n 20
   ```

2. **Categorize Rejections**
   - Regime not persistent
   - Vol-of-vol elevated
   - Liquidity issues
   - Event calendar blocks
   - Kill switch active
   - Other

3. **Analyze Patterns**
   - Are rejections increasing?
   - Is one category dominant?
   - Are rejections justified?

4. **Generate Report**
   ```python
   from src.options.reporting import generate_rejection_report
   report = generate_rejection_report(date='2026-02-10')
   print(report)
   ```

### Common Rejection Reasons

#### "Regime not persistent (< 2 days)"

**Meaning**: Regime hasn't stabilized yet

**Action**: Normal - wait for persistence

**Concern if**: Regime flipping daily (market indecision)

#### "Vol-of-vol elevated"

**Meaning**: Volatility is unstable

**Action**: Normal - avoid short-vol in unstable conditions

**Concern if**: Persists for > 1 week (unusual market stress)

#### "Insufficient liquidity"

**Meaning**: Bid-ask spread too wide or depth too low

**Action**: 
- Check if market-wide or specific strikes
- Consider different strikes
- Wait for better liquidity

**Concern if**: Persistent across all strikes (market stress)

#### "Macro event within 2 days"

**Meaning**: High-impact event approaching

**Action**: Normal - event calendar working as designed

**Concern if**: Event not in calendar (update needed)

### Escalation Criteria

Escalate to risk manager if:
- Rejection rate > 80% for 3 consecutive days
- New rejection reason appears
- System rejecting all trades despite favorable conditions
- Rejections don't match market reality

---

## Trade Ledger Audit

### Weekly Audit (Every Monday)

**Time**: 10:00 AM IST

**Procedure**:

1. **Load Trade Ledger**
   ```python
   import pandas as pd
   ledger = pd.read_parquet('data/options/trade_ledger.parquet')
   print(f"Total trades: {len(ledger)}")
   print(f"Date range: {ledger['timestamp'].min()} to {ledger['timestamp'].max()}")
   ```

2. **Verify Completeness**
   - Check all trades have entry records
   - Check closed trades have exit records
   - Verify no missing trade IDs

3. **Validate Data Integrity**
   ```python
   # Check for duplicates
   duplicates = ledger[ledger.duplicated(subset=['trade_id'], keep=False)]
   if not duplicates.empty:
       print("WARNING: Duplicate trade IDs found")
   
   # Check for missing required fields
   required_fields = ['trade_id', 'strategy_type', 'entry_timestamp', 'max_loss']
   for field in required_fields:
       missing = ledger[field].isna().sum()
       if missing > 0:
           print(f"WARNING: {missing} records missing {field}")
   ```

4. **Reconcile with Broker**
   - Export ledger trades
   - Compare with broker statements
   - Investigate discrepancies

5. **Calculate Metrics**
   ```python
   # Win rate
   closed_trades = ledger[ledger['exit_timestamp'].notna()]
   wins = (closed_trades['final_pnl'] > 0).sum()
   win_rate = wins / len(closed_trades) if len(closed_trades) > 0 else 0
   print(f"Win rate: {win_rate:.1%}")
   
   # Total P&L
   total_pnl = closed_trades['final_pnl'].sum()
   print(f"Total P&L: ₹{total_pnl:,.0f}")
   ```

6. **Generate Audit Report**
   ```bash
   python scripts/generate_ledger_audit_report.py --week=$(date +%Y-W%V)
   ```

### Monthly Audit (First Monday of Month)

**Additional Checks**:

1. **Tax Calculation Verification**
   ```python
   # Verify tax calculations
   profitable_trades = closed_trades[closed_trades['final_pnl'] > 0]
   calculated_tax = profitable_trades['tax'].sum()
   expected_tax = profitable_trades['final_pnl'].sum() * 0.30
   
   if abs(calculated_tax - expected_tax) > 100:
       print("WARNING: Tax calculation discrepancy")
   ```

2. **Cost Analysis**
   ```python
   # Analyze cost components
   total_costs = closed_trades['costs'].sum()
   avg_cost_per_trade = total_costs / len(closed_trades)
   print(f"Average cost per trade: ₹{avg_cost_per_trade:,.0f}")
   ```

3. **Archive Old Data**
   ```bash
   # Archive trades older than 1 year
   python scripts/archive_old_trades.py --older-than=365
   ```

---

## Event Calendar Updates

### When to Update

- New macro events announced (RBI policy, budget, etc.)
- Event dates changed
- New high-impact events identified
- Quarterly review

### Update Procedure

1. **Edit Configuration**
   ```bash
   nano config/options_trading.yaml
   ```

2. **Add New Event**
   ```yaml
   event_calendar:
     - event_type: "RBI_POLICY"
       dates:
         - "2026-04-10"  # Add new date
       buffer_days: 2
   ```

3. **Validate Configuration**
   ```bash
   python -c "from src.options.config_loader import get_config; \
              config = get_config(); \
              print('Events loaded:', len(config.event_calendar))"
   ```

4. **Test Event Blocking**
   ```bash
   python -m pytest tests/options/test_eligibility_validator.py::test_event_calendar -v
   ```

5. **Restart System**
   ```bash
   # Restart dashboard to load new config
   pkill -f streamlit
   streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py &
   ```

6. **Verify on Dashboard**
   - Check "Next Trade Eligibility"
   - Should show event block if within buffer

### Event Calendar Template

```yaml
event_calendar:
  # RBI Monetary Policy
  - event_type: "RBI_POLICY"
    dates:
      - "2026-02-07"
      - "2026-04-10"
      - "2026-06-08"
      - "2026-08-09"
      - "2026-10-09"
      - "2026-12-08"
    buffer_days: 2

  # Union Budget
  - event_type: "UNION_BUDGET"
    dates:
      - "2026-02-01"
    buffer_days: 3

  # FOMC Meetings
  - event_type: "FOMC"
    dates:
      - "2026-01-29"
      - "2026-03-19"
      - "2026-05-07"
      - "2026-06-18"
      - "2026-07-31"
      - "2026-09-18"
      - "2026-11-06"
      - "2026-12-17"
    buffer_days: 1

  # Quarterly Results
  - event_type: "EARNINGS_SEASON"
    dates:
      - "2026-01-15"  # Q3 FY26 start
      - "2026-04-15"  # Q4 FY26 start
      - "2026-07-15"  # Q1 FY27 start
      - "2026-10-15"  # Q2 FY27 start
    buffer_days: 0  # No block for earnings
```

---

## System Health Monitoring

### Real-Time Monitoring

**Dashboard Indicators**:

🟢 **Green**: All systems operational
🟡 **Yellow**: Warning - attention needed
🔴 **Red**: Critical - immediate action required

**Key Metrics to Watch**:

1. **API Connectivity**
   - Status: Connected / Disconnected
   - Last successful fetch timestamp
   - Rate limit usage

2. **Data Freshness**
   - Option chain last updated
   - IV history last updated
   - Position MTM last updated

3. **System Performance**
   - Dashboard response time
   - Log file size
   - Memory usage

### Health Check Script

Run every hour:

```bash
#!/bin/bash
# health_check.sh

echo "=== Options Trading System Health Check ==="
echo "Time: $(date)"
echo ""

# Check dashboard process
if pgrep -f "streamlit.*northstar" > /dev/null; then
    echo "✓ Dashboard: Running"
else
    echo "✗ Dashboard: NOT RUNNING"
    # Restart dashboard
    streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py &
fi

# Check log file size
LOG_SIZE=$(du -h logs/options_trading.log | cut -f1)
echo "✓ Log size: $LOG_SIZE"

# Check for recent errors
ERROR_COUNT=$(tail -n 1000 logs/options_trading.log | grep -c ERROR)
if [ $ERROR_COUNT -gt 10 ]; then
    echo "⚠ Errors in last 1000 lines: $ERROR_COUNT"
else
    echo "✓ Error count: $ERROR_COUNT"
fi

# Check disk space
DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo "⚠ Disk usage: ${DISK_USAGE}%"
else
    echo "✓ Disk usage: ${DISK_USAGE}%"
fi

echo ""
echo "=== Health Check Complete ==="
```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| API Errors | > 5/hour | > 20/hour |
| Dashboard Down | > 1 min | > 5 min |
| Log Errors | > 10/hour | > 50/hour |
| Disk Usage | > 80% | > 90% |
| Memory Usage | > 80% | > 95% |

---

## Incident Response

### Incident Classification

**P1 - Critical** (Response: Immediate)
- System completely down
- All trades failing
- Data corruption detected
- Kill switch malfunction

**P2 - High** (Response: < 30 minutes)
- Dashboard not updating
- API connectivity issues
- Position tracking errors
- Greek calculation failures

**P3 - Medium** (Response: < 2 hours)
- Slow performance
- Minor data discrepancies
- Non-critical warnings

**P4 - Low** (Response: Next business day)
- Documentation issues
- Enhancement requests
- Minor UI issues

### Incident Response Procedures

#### P1: System Down

1. **Immediate Actions**
   ```bash
   # Check system status
   systemctl status northstar-options
   
   # Check logs
   tail -n 100 logs/options_trading.log
   tail -n 100 logs/errors/options_errors.log
   ```

2. **Notify Stakeholders**
   - Alert all traders
   - Notify risk manager
   - Update status page

3. **Attempt Restart**
   ```bash
   # Restart dashboard
   pkill -f streamlit
   streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py &
   ```

4. **If Restart Fails**
   - Escalate to technical team
   - Switch to manual trading mode
   - Document all actions

#### P2: API Connectivity Issues

1. **Verify Issue**
   ```bash
   # Test API connection
   curl -I https://api.upstox.com/v2/
   
   # Check credentials
   echo $UPSTOX_API_KEY | wc -c
   ```

2. **Check Upstox Status**
   - Visit Upstox status page
   - Check for service disruptions

3. **Attempt Reconnection**
   ```python
   from src.options.upstox_adapter import UpstoxAdapter
   adapter = UpstoxAdapter()
   adapter.reconnect()
   ```

4. **Fallback**
   - Use cached data if available
   - Switch to manual data entry
   - Monitor for restoration

#### P3: Position Tracking Errors

1. **Identify Discrepancy**
   - Compare system positions with broker
   - Note differences

2. **Investigate Cause**
   - Check trade ledger
   - Review logs for errors
   - Verify data integrity

3. **Correct Data**
   ```python
   # Manual position correction (use with caution)
   from src.options.position_manager import PositionManager
   pm = PositionManager()
   pm.reconcile_positions()
   ```

4. **Prevent Recurrence**
   - Document root cause
   - Update validation logic
   - Add monitoring

---

## Maintenance Procedures

### Daily Maintenance

**Log Rotation**:
```bash
# Rotate logs if > 100MB
if [ $(stat -f%z logs/options_trading.log) -gt 104857600 ]; then
    mv logs/options_trading.log logs/options_trading_$(date +%Y%m%d).log
    touch logs/options_trading.log
fi
```

**Backup**:
```bash
# Backup trade ledger
cp data/options/trade_ledger.parquet \
   backups/trade_ledger_$(date +%Y%m%d).parquet
```

### Weekly Maintenance

**Sunday Evening** (After market close):

1. **Archive Old Logs**
   ```bash
   find logs/ -name "*.log" -mtime +30 -exec gzip {} \;
   ```

2. **Clean Temporary Files**
   ```bash
   rm -f /tmp/options_*.tmp
   ```

3. **Update Dependencies**
   ```bash
   pip list --outdated
   # Review and update if needed
   ```

4. **Run Full Test Suite**
   ```bash
   pytest tests/options/ -v --tb=short
   ```

### Monthly Maintenance

**First Sunday of Month**:

1. **System Backup**
   ```bash
   tar -czf backups/system_backup_$(date +%Y%m).tar.gz \
       config/ data/options/ logs/
   ```

2. **Performance Review**
   - Review system metrics
   - Analyze response times
   - Check resource usage

3. **Configuration Review**
   - Review all config parameters
   - Update if needed
   - Test changes

4. **Documentation Update**
   - Update runbook if procedures changed
   - Update user guide if features added
   - Review deployment checklist

---

## Emergency Contacts

**System Issues**:
- Technical Lead: [Contact Info]
- DevOps Team: [Contact Info]

**Trading Issues**:
- Risk Manager: [Contact Info]
- Trading Desk: [Contact Info]

**Upstox Support**:
- API Support: api@upstox.com
- Phone: [Support Number]

---

**Version**: 1.0  
**Last Updated**: 2026-02-10  
**Review Frequency**: Monthly
