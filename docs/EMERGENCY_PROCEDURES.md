# Emergency Procedures - Unified Volatility Engine

## Quick Reference Card

**KEEP THIS ACCESSIBLE AT ALL TIMES**

### Emergency Contacts

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Senior Trader | [NAME] | [PHONE] | [EMAIL] |
| Risk Manager | [NAME] | [PHONE] | [EMAIL] |
| CTO | [NAME] | [PHONE] | [EMAIL] |
| CRO | [NAME] | [PHONE] | [EMAIL] |

### Emergency Commands

```bash
# HALT ALL TRADING IMMEDIATELY
python scripts/emergency_halt.py

# LIQUIDATE ALL POSITIONS
python scripts/emergency_liquidate.py --all

# REDUCE POSITIONS BY 50%
python scripts/emergency_reduce.py --percentage 50

# HEDGE DELTA TO ZERO
python scripts/emergency_hedge.py --greek delta --target 0
```

---

## Emergency Scenarios

### Scenario 1: Greeks Limit Breach

**Trigger**: Portfolio Greeks exceed 95% of configured limits

**Severity**: HIGH

**Immediate Actions**:

1. **Identify the Greek** that breached:
   ```bash
   python scripts/show_greeks.py --highlight-violations
   ```

2. **Review largest contributors**:
   ```bash
   python scripts/show_positions.py --sort-by delta  # or gamma, vega, etc.
   ```

3. **Reduce exposure**:
   ```bash
   # Option A: Reduce specific positions
   python scripts/reduce_position.py --underlying SPY --percentage 30
   
   # Option B: Add offsetting hedge
   python scripts/emergency_hedge.py --greek delta --target 500
   ```

4. **Verify Greeks back below 90%**:
   ```bash
   python scripts/show_greeks.py
   ```

5. **Document actions**:
   ```bash
   python scripts/log_emergency_action.py \
     --type "greeks_breach" \
     --action "reduced_spy_positions" \
     --reason "delta_exceeded_limit"
   ```

6. **Notify risk manager** via email/Slack

**Follow-Up**:
- Review why limit was approached
- Consider adjusting position sizing
- Update risk limits if appropriate

---

### Scenario 2: VaR/CVaR Breach

**Trigger**: Value-at-Risk or Conditional VaR exceeds configured thresholds

**Severity**: CRITICAL

**Immediate Actions**:

1. **Review risk metrics**:
   ```bash
   python scripts/show_risk_metrics.py --detailed
   ```

2. **Identify worst-case scenarios**:
   ```bash
   python scripts/show_worst_scenarios.py
   ```

3. **Run stress tests**:
   ```bash
   python scripts/run_stress_tests.py --all
   ```

4. **Determine action**:
   - If VaR < 110% of limit: Reduce positions by 25%
   - If VaR < 120% of limit: Reduce positions by 50%
   - If VaR > 120% of limit: Liquidate high-risk positions

5. **Execute reduction**:
   ```bash
   python scripts/emergency_reduce.py --percentage 50
   ```

6. **Re-run risk metrics**:
   ```bash
   python scripts/show_risk_metrics.py
   ```

7. **Escalate to Risk Manager immediately**

**Follow-Up**:
- Full risk model review
- Validate Monte Carlo assumptions
- Review correlation estimates
- Consider tightening limits

---

### Scenario 3: Severe Drawdown (>15%)

**Trigger**: Portfolio down more than 15% from peak

**Severity**: CRITICAL

**Immediate Actions**:

1. **HALT ALL NEW TRADING**:
   ```bash
   python scripts/emergency_halt.py
   ```

2. **Review current positions**:
   ```bash
   python scripts/show_positions.py --with-pnl
   ```

3. **Identify losing positions**:
   ```bash
   python scripts/show_losers.py --threshold -5000
   ```

4. **Analyze what went wrong**:
   ```bash
   python scripts/analyze_drawdown.py --start-date [PEAK_DATE]
   ```

5. **Conference call with**:
   - Senior Trader
   - Risk Manager
   - CTO/CRO

6. **Decide on action** (requires approval):
   - Option A: Hold positions (if temporary market dislocation)
   - Option B: Reduce positions by 50%
   - Option C: Liquidate all positions

7. **Execute approved action**:
   ```bash
   # If Option B approved
   python scripts/emergency_reduce.py --percentage 50
   
   # If Option C approved
   python scripts/emergency_liquidate.py --all
   ```

8. **Document everything**:
   ```bash
   python scripts/generate_incident_report.py \
     --type "severe_drawdown" \
     --date [DATE]
   ```

**Follow-Up**:
- Full post-mortem analysis
- Review all strategy assumptions
- Validate risk models
- Consider system improvements
- Update procedures based on learnings

---

### Scenario 4: Market Data Feed Failure

**Trigger**: No market data updates for >60 seconds

**Severity**: HIGH

**Immediate Actions**:

1. **Verify feed status**:
   ```bash
   python scripts/check_data_feed.py
   ```

2. **Attempt reconnection**:
   ```bash
   python scripts/restart_data_feed.py
   ```

3. **If reconnection fails, switch to backup**:
   ```bash
   python scripts/switch_to_backup_feed.py
   ```

4. **If backup also fails**:
   ```bash
   # HALT TRADING - cannot trade without data
   python scripts/emergency_halt.py
   ```

5. **Notify**:
   - Data vendor support
   - Technology team
   - Senior trader

6. **Monitor positions manually** using broker platform

7. **Once feed restored**:
   ```bash
   # Verify data quality
   python scripts/validate_data_feed.py
   
   # Resume trading if data looks good
   python scripts/resume_trading.py
   ```

**Follow-Up**:
- Review feed reliability
- Consider additional backup feeds
- Test failover procedures

---

### Scenario 5: Execution Venue Failure

**Trigger**: Cannot submit orders, all orders rejected

**Severity**: MEDIUM-HIGH

**Immediate Actions**:

1. **Verify venue status**:
   ```bash
   python scripts/check_venue_status.py --venue CBOE
   ```

2. **Switch to alternate venue**:
   ```bash
   python scripts/switch_venue.py --from CBOE --to ISE
   ```

3. **Retry failed orders**:
   ```bash
   python scripts/retry_orders.py --venue ISE
   ```

4. **If all venues down**:
   ```bash
   # HALT NEW TRADING
   python scripts/emergency_halt.py
   
   # Monitor existing positions
   python scripts/monitor_positions.py
   ```

5. **Notify**:
   - Execution broker
   - Technology team
   - Senior trader

6. **Manual execution** if critical:
   - Use broker phone line
   - Document all manual trades
   - Update system state manually

**Follow-Up**:
- Review venue reliability
- Diversify across more venues
- Test multi-venue routing

---

### Scenario 6: Component Failure

**Trigger**: Critical component crashes or becomes unresponsive

**Severity**: MEDIUM-HIGH

**Immediate Actions**:

1. **Identify failed component**:
   ```bash
   python scripts/component_health_check.py
   ```

2. **Review error logs**:
   ```bash
   tail -100 logs/volatility_engine.log | grep ERROR
   ```

3. **Attempt component restart**:
   ```bash
   python scripts/restart_component.py --component [COMPONENT_NAME]
   ```

4. **If restart fails**:
   ```bash
   # HALT TRADING
   python scripts/emergency_halt.py
   
   # Save current state
   python scripts/save_state.py snapshots/emergency_$(date +%Y%m%d_%H%M%S).json
   ```

5. **Escalate to Technology team**

6. **If critical component (RiskAuthority, StateEngine)**:
   - Do NOT resume trading until fixed
   - Manual oversight required

7. **If non-critical component**:
   - May resume with degraded functionality
   - Document limitations
   - Monitor closely

**Follow-Up**:
- Root cause analysis
- Add error handling
- Improve component resilience
- Add health checks

---

### Scenario 7: Regime Transition to Crisis

**Trigger**: Regime detector classifies market as "crisis" (VIX > 30)

**Severity**: HIGH

**Immediate Actions**:

1. **Verify regime classification**:
   ```bash
   python scripts/show_regime.py --detailed
   ```

2. **System automatically**:
   - Tightens risk limits (50% reduction)
   - Halts short volatility strategies
   - Reduces leverage to 1.0x
   - Reallocates capital defensively

3. **Review automatic adjustments**:
   ```bash
   python scripts/show_regime_adjustments.py
   ```

4. **Manual review required**:
   ```bash
   # Check current positions
   python scripts/show_positions.py
   
   # Check Greeks
   python scripts/show_greeks.py
   
   # Check risk metrics
   python scripts/show_risk_metrics.py
   ```

5. **Consider additional actions**:
   - Reduce overall exposure
   - Add protective hedges
   - Increase cash allocation

6. **Execute if needed**:
   ```bash
   python scripts/emergency_reduce.py --percentage 30
   python scripts/add_protective_hedges.py
   ```

7. **Notify senior trader and risk manager**

8. **Increase monitoring frequency**:
   - Check dashboard every 15 minutes
   - Review positions hourly
   - Daily risk review

**Follow-Up**:
- Monitor for regime exit
- Review crisis performance
- Validate crisis procedures worked
- Update crisis playbook

---

### Scenario 8: Margin Call

**Trigger**: Broker issues margin call, must reduce positions

**Severity**: CRITICAL

**Immediate Actions**:

1. **Verify margin requirement**:
   ```bash
   python scripts/show_margin.py
   ```

2. **Calculate required reduction**:
   ```bash
   python scripts/calculate_margin_reduction.py
   ```

3. **Identify positions to liquidate**:
   - Prioritize: Lowest conviction, highest margin usage
   ```bash
   python scripts/select_liquidation_candidates.py --margin-call
   ```

4. **Execute liquidation**:
   ```bash
   python scripts/liquidate_positions.py --positions [POSITION_IDS]
   ```

5. **Verify margin satisfied**:
   ```bash
   python scripts/show_margin.py
   ```

6. **If still insufficient, liquidate more**:
   ```bash
   python scripts/emergency_liquidate.py --percentage 50
   ```

7. **Document all actions**:
   ```bash
   python scripts/log_margin_call.py --date [DATE] --amount [AMOUNT]
   ```

8. **Notify**:
   - Senior trader (immediately)
   - Risk manager (immediately)
   - CTO/CRO (within 1 hour)

**Follow-Up**:
- Review what caused margin call
- Improve margin monitoring
- Add margin buffer to limits
- Consider reducing leverage

---

### Scenario 9: System Compromise / Security Breach

**Trigger**: Suspected unauthorized access or malicious activity

**Severity**: CRITICAL

**Immediate Actions**:

1. **HALT ALL TRADING IMMEDIATELY**:
   ```bash
   python scripts/emergency_halt.py
   ```

2. **DISCONNECT FROM NETWORK**:
   ```bash
   python scripts/disconnect_network.py
   ```

3. **SAVE CURRENT STATE**:
   ```bash
   python scripts/save_state.py snapshots/security_incident_$(date +%Y%m%d_%H%M%S).json
   ```

4. **NOTIFY IMMEDIATELY**:
   - CTO (call, don't email)
   - Security team
   - CRO

5. **DO NOT**:
   - Resume trading
   - Reconnect to network
   - Modify any files
   - Delete any logs

6. **PRESERVE EVIDENCE**:
   - Copy all logs
   - Screenshot current state
   - Document timeline

7. **AWAIT INSTRUCTIONS** from security team

**Follow-Up**:
- Full security audit
- Forensic analysis
- Review access controls
- Update security procedures
- Regulatory notification if required

---

### Scenario 10: Regulatory Inquiry

**Trigger**: Regulator requests information or investigation

**Severity**: HIGH

**Immediate Actions**:

1. **DO NOT PANIC**

2. **NOTIFY IMMEDIATELY**:
   - Chief Compliance Officer
   - General Counsel
   - CRO

3. **PRESERVE ALL DATA**:
   ```bash
   python scripts/preserve_audit_trail.py --start-date [DATE] --end-date [DATE]
   ```

4. **DO NOT**:
   - Delete any data
   - Modify any logs
   - Discuss with anyone except legal/compliance

5. **GATHER REQUESTED INFORMATION**:
   ```bash
   python scripts/generate_regulatory_report.py --date-range [RANGE]
   ```

6. **AWAIT INSTRUCTIONS** from legal/compliance

**Follow-Up**:
- Cooperate fully with inquiry
- Review compliance procedures
- Update documentation
- Training if needed

---

## Emergency Decision Tree

```
Is trading system operational?
├─ NO → Scenario 4, 5, or 6
└─ YES → Continue

Are risk limits breached?
├─ YES → Scenario 1 or 2
└─ NO → Continue

Is drawdown > 15%?
├─ YES → Scenario 3
└─ NO → Continue

Is regime = crisis?
├─ YES → Scenario 7
└─ NO → Continue

Margin call received?
├─ YES → Scenario 8
└─ NO → Continue

Security breach suspected?
├─ YES → Scenario 9
└─ NO → Continue

Regulatory inquiry?
├─ YES → Scenario 10
└─ NO → Normal operations
```

---

## Post-Emergency Procedures

### After Any Emergency

1. **Generate incident report**:
   ```bash
   python scripts/generate_incident_report.py \
     --type [TYPE] \
     --date [DATE] \
     --severity [SEVERITY]
   ```

2. **Conduct post-mortem**:
   - What happened?
   - Why did it happen?
   - What was the impact?
   - What worked well?
   - What could be improved?

3. **Update procedures**:
   - Document lessons learned
   - Update emergency procedures
   - Add new checks/alerts
   - Improve monitoring

4. **Test improvements**:
   - Simulate scenario again
   - Verify procedures work
   - Train team on updates

5. **Archive documentation**:
   ```bash
   python scripts/archive_incident.py --incident-id [ID]
   ```

---

## Emergency Drills

### Monthly Drill Schedule

- **Week 1**: Greeks limit breach drill
- **Week 2**: Data feed failure drill
- **Week 3**: Component failure drill
- **Week 4**: Drawdown response drill

### Drill Procedure

1. **Announce drill** (don't surprise operators)
2. **Simulate scenario** in staging environment
3. **Execute emergency procedures**
4. **Time response**
5. **Debrief**:
   - What went well?
   - What was confusing?
   - What took too long?
6. **Update procedures** based on feedback

---

## Emergency Kit

### Physical Items

- [ ] Printed copy of this document
- [ ] Emergency contact list
- [ ] Backup laptop (charged)
- [ ] Mobile hotspot (for network backup)
- [ ] Broker phone numbers
- [ ] USB drive with system backups

### Digital Items

- [ ] Latest system snapshot
- [ ] Configuration backups
- [ ] Emergency scripts tested
- [ ] Audit trail archives
- [ ] Documentation up to date

### Knowledge Items

- [ ] All operators trained on procedures
- [ ] Emergency drills completed monthly
- [ ] Contact information verified
- [ ] Escalation paths clear
- [ ] Decision authority documented

---

## Remember

1. **Stay Calm** - Panic makes things worse
2. **Follow Procedures** - They exist for a reason
3. **Document Everything** - You'll need it later
4. **Escalate When Needed** - Don't try to handle everything alone
5. **Learn from Incidents** - Every emergency is a learning opportunity

**When in doubt, HALT TRADING and escalate.**
