# Unified Volatility Engine - Operator Guide

## Table of Contents

1. [System Configuration](#system-configuration)
2. [Daily Operations](#daily-operations)
3. [Monitoring and Alerts](#monitoring-and-alerts)
4. [Emergency Procedures](#emergency-procedures)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)

---

## System Configuration

### Initial Setup

1. **Install Dependencies**

```bash
pip install -r requirements.txt
```

2. **Configure System Parameters**

Edit `config/production.yaml`:

```yaml
# Position Limits
position_limits:
  per_underlying: 100
  total: 500
  max_concentration: 0.20  # 20% max per underlying

# Greeks Limits
greeks_limits:
  delta: 1000
  gamma: 500
  vega: 10000
  theta: -500

# Risk Thresholds
risk_thresholds:
  var_95: 50000  # $50k max VaR at 95%
  var_99: 100000  # $100k max VaR at 99%
  cvar_95: 75000  # $75k max CVaR at 95%
  max_drawdown: 0.15  # 15% max drawdown

# Regime-Conditional Adjustments
regime_adjustments:
  crisis:
    position_limits_multiplier: 0.5  # Halve limits in crisis
    short_vol_allowed: false
    max_leverage: 1.0
  high_vol:
    position_limits_multiplier: 0.75
    short_vol_allowed: true
    max_leverage: 1.5
  low_vol:
    position_limits_multiplier: 1.0
    short_vol_allowed: true
    max_leverage: 2.0

# Execution Parameters
execution:
  default_order_type: "LIMIT"
  limit_price_offset: 0.05  # 5 cents better than mid
  time_in_force: "DAY"
  preferred_venues: ["CBOE", "ISE", "PHLX"]
  min_liquidity: 1000  # contracts

# Performance Monitoring
monitoring:
  pnl_update_frequency: 60  # seconds
  greeks_update_frequency: 30  # seconds
  risk_check_frequency: 300  # seconds
  performance_degradation_threshold: 0.3  # 30% Sharpe decline

# State Persistence
persistence:
  snapshot_frequency: 300  # seconds (5 minutes)
  snapshot_directory: "snapshots/"
  max_snapshots: 100  # Keep last 100 snapshots
```

3. **Validate Configuration**

```bash
python scripts/validate_config.py config/production.yaml
```

4. **Initialize State**

```bash
python scripts/initialize_state.py --config config/production.yaml
```

---

### Configuration Profiles

Three pre-configured profiles are available:

#### Aggressive Profile (`config/aggressive.yaml`)
- Higher position limits
- Higher Greeks limits
- More leverage (2.5x)
- Suitable for experienced operators in stable markets

#### Moderate Profile (`config/moderate.yaml`)
- Balanced risk/reward
- Standard limits
- Moderate leverage (1.5x)
- **Recommended for most users**

#### Conservative Profile (`config/conservative.yaml`)
- Tight position limits
- Strict Greeks limits
- Low leverage (1.0x)
- Suitable for risk-averse operators or volatile markets

To switch profiles:

```bash
python scripts/load_config.py config/conservative.yaml
```

---

## Daily Operations

### Pre-Market Checklist

**Time: 30 minutes before market open**

1. **Review Overnight Positions**

```bash
python scripts/review_positions.py
```

Check:
- Current positions and Greeks
- Overnight P&L
- Any corporate actions (dividends, splits)
- Expiring options

2. **Verify System Health**

```bash
python scripts/health_check.py
```

Validates:
- All components initialized
- Market data feed connected
- Execution venues accessible
- State persistence working

3. **Load Latest State**

```bash
python scripts/load_state.py snapshots/latest.json
```

4. **Review Risk Limits**

```bash
python scripts/show_risk_limits.py
```

Verify limits are appropriate for current market regime.

5. **Start System**

```bash
python scripts/start_engine.py --config config/production.yaml
```

---

### Intraday Operations

**Market Hours: Continuous monitoring**

1. **Monitor Dashboard**

Access real-time dashboard:
```bash
streamlit run dashboard/volatility_dashboard.py
```

Key metrics to watch:
- Portfolio P&L (total, realized, unrealized)
- Portfolio Greeks (delta, gamma, vega, theta)
- Current regime and probabilities
- Risk metrics (VaR, CVaR, max drawdown)
- Active strategies and allocations

2. **Review Trading Activity**

Every hour, check:
- Strategies generated and approved
- Orders submitted and filled
- Execution quality (slippage, fill rates)
- Any rejected trades (review reasons)

3. **Monitor Alerts**

Watch for:
- Greeks approaching limits
- Risk metrics breaching thresholds
- Performance degradation warnings
- Component errors

4. **Regime Changes**

When regime changes:
- Review automatic limit adjustments
- Verify capital reallocation
- Check strategy mix adaptation
- Monitor for any issues

---

### End-of-Day Procedures

**Time: After market close**

1. **Final Rebalancing**

```bash
python scripts/eod_rebalance.py
```

2. **Generate Reports**

```bash
python scripts/generate_eod_reports.py --date 2026-02-11
```

Reports generated:
- Daily P&L summary
- Greeks evolution
- Performance attribution
- Risk metrics
- Trade log
- Audit trail

3. **Review Performance**

```bash
python scripts/performance_review.py --date 2026-02-11
```

Analyze:
- Total P&L vs target
- Sharpe ratio
- Win rate
- Max drawdown
- Greeks P&L decomposition
- Alpha vs beta

4. **Save State Snapshot**

```bash
python scripts/save_state.py snapshots/eod_20260211.json
```

5. **Archive Logs**

```bash
python scripts/archive_logs.py --date 2026-02-11
```

6. **Shutdown System**

```bash
python scripts/shutdown_engine.py
```

Performs:
- Cancel all pending orders
- Save final state
- Archive audit trail
- Graceful component shutdown

---

## Monitoring and Alerts

### Real-Time Monitoring

#### Dashboard Panels

1. **P&L Panel**
   - Total P&L (today, week, month, year)
   - Realized vs unrealized
   - P&L by strategy bucket
   - P&L by underlying

2. **Greeks Panel**
   - Portfolio Greeks with limit bars
   - Greeks by underlying
   - Greeks evolution charts
   - Scenario analysis results

3. **Regime Panel**
   - Current regime with probabilities
   - Regime history chart
   - Transition alerts
   - Regime-conditional limits

4. **Risk Panel**
   - VaR/CVaR gauges
   - Maximum drawdown
   - Stress test results
   - Risk alerts

5. **Execution Panel**
   - Active orders
   - Fill rates
   - Slippage analysis
   - Venue performance

6. **Performance Panel**
   - Sharpe ratio
   - Sortino ratio
   - Win rate
   - Performance attribution

---

### Alert Configuration

Edit `config/alerts.yaml`:

```yaml
alerts:
  # Greeks Alerts
  greeks_warning_threshold: 0.8  # 80% of limit
  greeks_critical_threshold: 0.95  # 95% of limit
  
  # Risk Alerts
  var_warning_threshold: 0.8
  var_critical_threshold: 0.95
  drawdown_warning: 0.10  # 10%
  drawdown_critical: 0.15  # 15%
  
  # Performance Alerts
  sharpe_degradation_threshold: 0.3  # 30% decline
  consecutive_losses_threshold: 5
  
  # Execution Alerts
  fill_rate_warning: 0.8  # 80% fill rate
  slippage_warning: 0.02  # 2% slippage
  
  # Notification Channels
  channels:
    - type: "email"
      recipients: ["trader@firm.com", "risk@firm.com"]
      severity: ["WARNING", "CRITICAL"]
    - type: "slack"
      webhook: "https://hooks.slack.com/..."
      severity: ["CRITICAL"]
    - type: "sms"
      numbers: ["+1234567890"]
      severity: ["CRITICAL"]
```

---

### Alert Response Procedures

#### Greeks Warning (80% of limit)
1. Review current positions
2. Identify largest contributors
3. Consider reducing exposure
4. Monitor closely

#### Greeks Critical (95% of limit)
1. **Immediate action required**
2. Reduce positions to bring below 90%
3. Halt new trades in that Greek
4. Document actions in audit trail

#### VaR Breach
1. Review Monte Carlo simulation results
2. Identify worst-case scenarios
3. Consider hedging or position reduction
4. Escalate to risk manager

#### Drawdown Warning (10%)
1. Review recent trades
2. Analyze what went wrong
3. Consider reducing position sizes
4. Review strategy allocations

#### Drawdown Critical (15%)
1. **Emergency action triggered**
2. System automatically reduces positions
3. Review and approve emergency actions
4. Investigate root cause
5. Consider halting trading

#### Performance Degradation
1. Review recent performance vs historical
2. Analyze regime changes
3. Check if strategy assumptions still valid
4. Consider strategy adjustments

#### Component Error
1. Check error logs
2. Attempt automatic recovery
3. If recovery fails, manual intervention required
4. Document issue and resolution

---

## Emergency Procedures

### Emergency Action Types

#### 1. Reduce Positions

**Trigger**: Greeks approaching limits, VaR breach

**Action**:
```bash
python scripts/emergency_reduce.py --percentage 50
```

Reduces all positions by specified percentage.

**Manual Override**:
```python
from volatility.risk_authority import UnifiedRiskAuthority

risk_authority.execute_emergency_action(
    action="reduce_positions",
    state=current_state,
    params={"reduction_pct": 0.5}
)
```

---

#### 2. Liquidate Positions

**Trigger**: Severe drawdown, margin call, system failure

**Action**:
```bash
python scripts/emergency_liquidate.py --strategy dispersion
```

Liquidates all positions in specified strategy bucket.

**Manual Override**:
```python
risk_authority.execute_emergency_action(
    action="liquidate_positions",
    state=current_state,
    params={"strategy_bucket": "dispersion"}
)
```

---

#### 3. Hedge Exposure

**Trigger**: Directional exposure too high, market stress

**Action**:
```bash
python scripts/emergency_hedge.py --greek delta --target 0
```

Adds hedges to neutralize specified Greek.

**Manual Override**:
```python
risk_authority.execute_emergency_action(
    action="hedge_exposure",
    state=current_state,
    params={"greek": "delta", "target": 0}
)
```

---

#### 4. Halt Trading

**Trigger**: System malfunction, extreme market conditions

**Action**:
```bash
python scripts/emergency_halt.py
```

Stops all new trades, cancels pending orders.

**Manual Override**:
```python
risk_authority.execute_emergency_action(
    action="halt_trading",
    state=current_state,
    params={}
)
```

To resume:
```bash
python scripts/resume_trading.py
```

---

### Emergency Contact Escalation

1. **Level 1 - Operator** (You)
   - Handle routine alerts
   - Execute standard procedures
   - Monitor system health

2. **Level 2 - Senior Trader**
   - Escalate if unable to resolve
   - Complex trading decisions
   - Strategy adjustments

3. **Level 3 - Risk Manager**
   - Escalate for risk limit breaches
   - Emergency action approval
   - System-wide issues

4. **Level 4 - CTO/CRO**
   - Escalate for critical system failures
   - Major risk events
   - Regulatory issues

---

## Troubleshooting

### Common Issues

#### Issue: Market Data Feed Disconnected

**Symptoms**: Stale prices, no IV updates

**Resolution**:
1. Check network connectivity
2. Verify API credentials
3. Restart data feed:
   ```bash
   python scripts/restart_data_feed.py
   ```
4. If persists, switch to backup feed

---

#### Issue: Execution Venue Unavailable

**Symptoms**: Orders not submitting, rejections

**Resolution**:
1. Check venue status page
2. Switch to alternate venue:
   ```bash
   python scripts/switch_venue.py --from CBOE --to ISE
   ```
3. Notify execution team

---

#### Issue: Greeks Computation Slow

**Symptoms**: Latency > 50ms, dashboard lag

**Resolution**:
1. Check CPU usage
2. Verify number of positions (should be <1000)
3. Restart Greeks aggregator:
   ```bash
   python scripts/restart_component.py --component greeks_aggregator
   ```
4. If persists, investigate performance regression

---

#### Issue: State Persistence Failure

**Symptoms**: Cannot save/load snapshots

**Resolution**:
1. Check disk space
2. Verify write permissions on snapshot directory
3. Validate state consistency:
   ```bash
   python scripts/validate_state.py
   ```
4. If corrupted, restore from previous snapshot:
   ```bash
   python scripts/restore_state.py snapshots/previous.json
   ```

---

#### Issue: Risk Authority Rejecting All Trades

**Symptoms**: No trades approved, all rejected

**Resolution**:
1. Check current risk limits:
   ```bash
   python scripts/show_risk_limits.py
   ```
2. Review current positions and Greeks
3. Verify limits not too tight for current regime
4. If limits appropriate, investigate position sizing
5. Check audit trail for rejection reasons:
   ```bash
   python scripts/show_audit_trail.py --recent 10
   ```

---

#### Issue: Performance Degradation Alert

**Symptoms**: Sharpe ratio declining, losses increasing

**Resolution**:
1. Review recent performance:
   ```bash
   python scripts/performance_analysis.py --days 30
   ```
2. Check if regime changed
3. Analyze losing trades
4. Consider:
   - Reducing position sizes
   - Adjusting strategy mix
   - Tightening risk limits
5. Consult with senior trader

---

### Log Analysis

**View recent logs**:
```bash
tail -f logs/volatility_engine.log
```

**Search for errors**:
```bash
grep ERROR logs/volatility_engine.log
```

**Component-specific logs**:
```bash
grep "volatility.risk_authority" logs/volatility_engine.log
```

**Export logs for analysis**:
```bash
python scripts/export_logs.py --start 2026-02-11 --end 2026-02-11 --output logs_20260211.csv
```

---

## Maintenance

### Daily Maintenance

1. **Review Logs** (5 minutes)
   - Check for errors or warnings
   - Verify all components healthy

2. **Verify Backups** (2 minutes)
   - Confirm snapshots being saved
   - Check backup integrity

3. **Monitor Disk Space** (1 minute)
   - Ensure sufficient space for logs and snapshots
   - Clean up old files if needed

---

### Weekly Maintenance

1. **Performance Review** (30 minutes)
   - Analyze week's performance
   - Compare to targets
   - Identify areas for improvement

2. **Risk Limit Review** (15 minutes)
   - Verify limits still appropriate
   - Adjust if needed based on market conditions

3. **Strategy Review** (30 minutes)
   - Analyze strategy performance
   - Review capital allocations
   - Consider adjustments

4. **System Health Check** (15 minutes)
   ```bash
   python scripts/weekly_health_check.py
   ```

5. **Archive Old Data** (10 minutes)
   ```bash
   python scripts/archive_old_data.py --older-than 30
   ```

---

### Monthly Maintenance

1. **Comprehensive Performance Review** (2 hours)
   - Full month analysis
   - Attribution analysis
   - Regime-conditional performance
   - Strategy effectiveness

2. **Risk Model Validation** (1 hour)
   - Backtest risk models
   - Validate VaR accuracy
   - Review stress test scenarios

3. **Configuration Review** (1 hour)
   - Review all configuration parameters
   - Update if needed
   - Document changes

4. **System Updates** (1 hour)
   - Update dependencies
   - Apply security patches
   - Test in staging environment

5. **Disaster Recovery Test** (2 hours)
   - Simulate system failure
   - Practice recovery procedures
   - Verify backups work

---

### Quarterly Maintenance

1. **Full System Audit** (1 day)
   - Review all code changes
   - Validate test coverage
   - Performance regression testing
   - Security audit

2. **Strategy Backtesting** (1 day)
   - Backtest all strategies on recent data
   - Validate assumptions still hold
   - Identify improvements

3. **Documentation Update** (4 hours)
   - Update operator guide
   - Document new procedures
   - Update configuration examples

---

## Best Practices

### Risk Management

1. **Always respect risk limits** - Never override without approval
2. **Monitor Greeks continuously** - Don't let them approach limits
3. **Diversify strategies** - Don't concentrate in one approach
4. **Use stop-losses** - Define maximum acceptable loss
5. **Document all decisions** - Maintain complete audit trail

### Execution

1. **Check liquidity before trading** - Ensure sufficient volume
2. **Use limit orders** - Avoid market orders in illiquid options
3. **Monitor slippage** - Track execution quality
4. **Stagger large orders** - Don't move the market
5. **Verify fills** - Confirm all orders executed correctly

### Performance

1. **Track attribution** - Understand where P&L comes from
2. **Compare to benchmarks** - Measure relative performance
3. **Analyze by regime** - Performance varies by market conditions
4. **Learn from losses** - Every loss is a learning opportunity
5. **Celebrate wins** - But don't get overconfident

### System Operations

1. **Test in staging first** - Never change production directly
2. **Keep backups** - Multiple snapshots, multiple locations
3. **Monitor continuously** - Don't leave system unattended
4. **Document everything** - Future you will thank you
5. **Stay calm in emergencies** - Follow procedures, don't panic

---

## Support

### Internal Support

- **Trading Desk**: trading@firm.com
- **Risk Management**: risk@firm.com
- **Technology**: tech@firm.com
- **On-Call**: +1-234-567-8900

### External Support

- **Market Data Vendor**: support@datavendor.com
- **Execution Broker**: support@broker.com
- **System Vendor**: support@vendor.com

### Documentation

- Architecture: `docs/UNIFIED_VOLATILITY_ENGINE_ARCHITECTURE.md`
- API Reference: `docs/API_REFERENCE.md`
- Performance: `docs/PERFORMANCE_OPTIMIZATION_SUMMARY.md`
- Migration Guide: `docs/MIGRATION_GUIDE.md`

---

## Appendix

### Keyboard Shortcuts (Dashboard)

- `Ctrl+R`: Refresh all panels
- `Ctrl+P`: Pause/resume updates
- `Ctrl+E`: Export current view
- `Ctrl+H`: Show/hide help
- `Ctrl+Q`: Quit dashboard

### CLI Quick Reference

```bash
# Start system
python scripts/start_engine.py --config config/production.yaml

# Stop system
python scripts/shutdown_engine.py

# Check status
python scripts/status.py

# View positions
python scripts/show_positions.py

# View Greeks
python scripts/show_greeks.py

# View risk metrics
python scripts/show_risk.py

# Emergency halt
python scripts/emergency_halt.py

# Resume trading
python scripts/resume_trading.py
```

### Configuration File Locations

- Production: `config/production.yaml`
- Staging: `config/staging.yaml`
- Development: `config/development.yaml`
- Alerts: `config/alerts.yaml`
- Venues: `config/venues.yaml`

### Data File Locations

- Snapshots: `snapshots/`
- Logs: `logs/`
- Reports: `reports/`
- Backups: `backups/`
- Archives: `archives/`
