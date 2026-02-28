# Black Swan Day Runbook

## Overview

This runbook provides specific procedures for managing the Northstar V2 system during extreme market events (Black Swan days) characterized by:
- VIX spike >40
- Market gaps >5%
- Correlation breakdown
- Extreme volatility events

## Immediate Response (First 15 Minutes)

### 1. Situation Assessment
```bash
# Quick system status
python scripts/black_swan_snapshot.py --immediate

# One-shot structured diagnostics
python scripts/northstar_daemon.py --diagnostic-mode --config config/northstar_daemon.yaml
```

**Check immediately:**
- [ ] Current system mode (should auto-transition to Survival Core)
- [ ] Position exposure and risk
- [ ] Market data feeds operational
- [ ] System resource usage
- [ ] Recent governance events

### 2. Risk Assessment
- [ ] Total portfolio exposure
- [ ] Short volatility exposure (highest risk)
- [ ] Correlation-dependent strategies
- [ ] Liquidity of current positions
- [ ] Margin requirements and available capital

### 3. Communication
- [ ] Notify key stakeholders
- [ ] Document event start time
- [ ] Begin incident log
- [ ] Prepare for extended monitoring

## Automated System Responses

The system should automatically:
- [ ] Transition to Survival Core mode
- [ ] Block new risk taking
- [ ] Increase monitoring frequency
- [ ] Generate governance alerts
- [ ] Disable research activities

**Verify these responses occurred:**
```bash
# Check current mode from diagnostic snapshot (preferred)
python scripts/northstar_daemon.py --diagnostic-mode --config config/northstar_daemon.yaml | jq '.current_mode'

# Check recent governance events
python -c "
import pandas as pd
df = pd.read_parquet('data/options/live/governance_events.parquet')
print(df.tail(10)[['timestamp', 'event_type', 'severity']])
"
```

Do not manually edit `data/options/live/options_runtime_state.json` during black swan handling except under explicit recovery procedure.

## Position Management Strategy

### Phase 1: Immediate Triage (0-30 minutes)

1. **Identify High-Risk Positions**
   - Short volatility strategies
   - Correlation-dependent trades
   - Large notional exposures
   - Illiquid positions

2. **Emergency Hedging**
   ```bash
   # Generate emergency hedge recommendations
   python scripts/emergency_hedge_calculator.py --black-swan-mode
   ```
   
   Consider:
   - VIX calls for short vol protection
   - Index puts for directional protection
   - Correlation hedges if applicable

3. **Liquidity Assessment**
   - Check bid-ask spreads
   - Assess market depth
   - Identify positions that may be difficult to exit

### Phase 2: Strategic Response (30 minutes - 2 hours)

1. **Position Reduction Decision Matrix**

   | Position Type | Risk Level | Action |
   |---------------|------------|--------|
   | Short Vol (naked) | Critical | Close immediately |
   | Short Vol (hedged) | High | Reduce 50-75% |
   | Long Vol | Low | Hold/Add |
   | Dispersion | Medium | Assess correlation |
   | Gamma Scalping | Medium | Reduce if illiquid |

2. **Execution Strategy**
   - Prioritize most liquid positions
   - Use market orders for critical exits
   - Accept slippage for risk reduction
   - Monitor execution quality

### Phase 3: Stabilization (2-6 hours)

1. **Portfolio Rebalancing**
   - Assess remaining exposure
   - Rebalance to target risk levels
   - Consider opportunistic positions
   - Update risk parameters

2. **System Recalibration**
   - Update volatility models
   - Recalibrate correlation assumptions
   - Adjust risk limits if needed
   - Review strategy parameters

## Monitoring Intensification

### Real-Time Monitoring (Every 5 minutes)
- [ ] Portfolio P&L
- [ ] Individual position P&L
- [ ] VIX level and term structure
- [ ] Underlying price movements
- [ ] Bid-ask spreads and liquidity
- [ ] System performance and errors

### Enhanced Reporting (Every 15 minutes)
```bash
# Generate enhanced monitoring report
python scripts/black_swan_monitoring.py --interval 15
```

- [ ] Risk metrics update
- [ ] Stress test results
- [ ] Liquidity assessment
- [ ] Correlation breakdown analysis
- [ ] Volatility surface changes

## Decision Framework

### Position Exit Criteria
Exit positions if:
- [ ] P&L loss exceeds 2x normal daily limit
- [ ] Bid-ask spread >5x normal
- [ ] Position becomes illiquid
- [ ] Correlation assumptions break down
- [ ] Margin requirements spike

### Hold/Add Criteria
Consider holding or adding if:
- [ ] Position is naturally hedged
- [ ] Long volatility with room to run
- [ ] Dispersion trade with correlation breakdown
- [ ] Adequate liquidity remains

## System Mode Management

### Survival Core Mode Verification
Ensure the following constraints are active:
- [ ] New risk blocked
- [ ] Research disabled
- [ ] Scaling up disabled
- [ ] Position reduction forced
- [ ] Monitoring increased

### Manual Override Procedures
If manual intervention needed:
```bash
# Force mode transition
python scripts/mode_controller.py --force-mode survival_core --reason "Black swan event"

# Emergency position reduction
python scripts/emergency_reduce.py --black-swan-mode --reduce-pct 50
```

## Communication Protocols

### Internal Communication
- [ ] Immediate notification to risk manager
- [ ] Update to senior management within 30 minutes
- [ ] Hourly updates during active phase
- [ ] End-of-day comprehensive report

### External Communication
- [ ] Broker notification if margin issues
- [ ] Regulatory reporting if required
- [ ] Client communication if applicable

## Recovery Procedures

### Market Stabilization Phase
When markets begin to stabilize:

1. **Gradual Re-engagement**
   - Assess new market regime
   - Update model parameters
   - Test with small positions
   - Gradually increase exposure

2. **System Mode Transition**
   - Monitor for stability indicators
   - Transition from Survival Core to Governance Constrained
   - Eventually return to Normal Operation
   - Document lessons learned

### Post-Event Analysis
```bash
# Generate comprehensive post-event report
python scripts/black_swan_analysis.py --event-date $(date +%Y-%m-%d)
```

1. **Performance Analysis**
   - Calculate event P&L impact
   - Analyze strategy performance
   - Assess hedging effectiveness
   - Review execution quality

2. **System Performance Review**
   - Evaluate automated responses
   - Review decision timing
   - Assess monitoring effectiveness
   - Identify improvement areas

3. **Model Updates**
   - Recalibrate risk models
   - Update correlation assumptions
   - Adjust volatility parameters
   - Enhance stress testing

## Lessons Learned Integration

### Immediate Updates (Within 24 hours)
- [ ] Update risk limits based on experience
- [ ] Adjust automated response thresholds
- [ ] Enhance monitoring alerts
- [ ] Update hedging strategies

### Strategic Updates (Within 1 week)
- [ ] Review and update this runbook
- [ ] Enhance system automation
- [ ] Improve risk management tools
- [ ] Update training materials

## Black Swan Event Checklist

### Pre-Event Preparation
- [ ] Runbook reviewed and updated
- [ ] Emergency contacts verified
- [ ] System monitoring tools tested
- [ ] Hedging strategies prepared
- [ ] Risk limits appropriate

### During Event
- [ ] Immediate assessment completed
- [ ] Automated responses verified
- [ ] Position management executed
- [ ] Enhanced monitoring active
- [ ] Communication protocols followed

### Post-Event
- [ ] Comprehensive analysis completed
- [ ] Lessons learned documented
- [ ] System updates implemented
- [ ] Runbook updated
- [ ] Team debriefing conducted

## Emergency Contacts

### Primary Response Team
- Risk Manager: [Contact]
- System Administrator: [Contact]
- Senior Management: [Contact]

### External Contacts
- Broker Risk Desk: [Contact]
- Technology Support: [Contact]
- Regulatory Contact: [Contact]

## Key Commands Reference

```bash
# System status and health
python scripts/status.py
python scripts/health_check.py

# Emergency actions
python scripts/emergency_reduce.py --help
python scripts/black_swan_snapshot.py --help

# Mode management
python scripts/mode_controller.py --help

# Monitoring and reporting
python scripts/black_swan_monitoring.py --help
python scripts/black_swan_analysis.py --help
```

## Appendix: Black Swan Indicators

### Market Indicators
- VIX >40 (Critical: >50)
- Market gap >5% (Critical: >10%)
- Correlation <0.2 (breakdown)
- Volume >3x average
- Bid-ask spreads >5x normal

### System Indicators
- Multiple governance alerts
- Survival mode activation
- Accounting integrity violations
- Resource pressure alerts
- Heartbeat irregularities

### Position Indicators
- P&L swings >5x normal
- Margin calls or warnings
- Execution failures
- Liquidity deterioration
- Model breakdown signals

---

**Document Version**: 2.0  
**Last Updated**: [Date]  
**Next Review**: [Date + 3 months]  
**Owner**: Risk Management Team
