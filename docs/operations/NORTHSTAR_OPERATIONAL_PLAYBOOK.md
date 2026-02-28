# Northstar V2 Operational Playbook

## Overview

This playbook provides operational procedures for managing the Northstar V2 trading system with persistence, resilience, and governance controls.

## Daily Operations

### Pre-Market Checklist (8:30 AM IST)

1. **System Health Check**
   ```bash
   python scripts/preopen_checks.py
   ```
   - Verify daemon is running
   - Check process locks and heartbeats
   - Validate time synchronization
   - Review overnight governance events

2. **State Integrity Verification**
   - Check for WAL interrupted operations
   - Verify accounting equation integrity
   - Review position reconciliation
   - Validate risk cap calculations

3. **Market Data Connectivity**
   - Test Upstox API connection
   - Verify option chain data availability
   - Check underlying price feeds
   - Validate instrument mappings

4. **One-Shot Diagnostic Snapshot**
   ```bash
   python scripts/northstar_daemon.py --diagnostic-mode --config config/northstar_daemon.yaml
   ```
   - Inspect active locks and owning PIDs
   - Confirm current mode + constraints
   - Check WAL interrupted operation count
   - Verify runtime checksum integrity
   - Confirm ledger last-write visibility

### Market Hours Monitoring (9:30 AM - 3:30 PM IST)

1. **Live Engine Monitoring**
   - Monitor heartbeat freshness (< 2x cycle interval)
   - Watch for governance alerts
   - Track mode transitions
   - Monitor resource usage

2. **Risk Management**
   - Verify dynamic risk caps are updating
   - Monitor position concentration
   - Check drawdown levels
   - Watch for survival mode triggers

3. **Performance Tracking**
   - Monitor realized/unrealized PnL
   - Track strategy performance
   - Watch for accounting mismatches
   - Monitor execution quality

### Post-Market Procedures (4:00 PM IST)

1. **End-of-Day Reconciliation**
   ```bash
   python scripts/eod_reconciliation.py
   ```
   - Create EOD snapshot
   - Reconcile positions with broker
   - Update weekly anchors if needed
   - Archive daily logs

2. **Research Activities**
   - Run research cycle (if not frozen)
   - Review strategy performance
   - Update model registry
   - Generate performance reports

## System Modes and Responses

### Normal Operation Mode
- **Characteristics**: All systems healthy, no governance constraints
- **Actions**: Standard trading operations, research enabled
- **Monitoring**: Standard monitoring intervals

### Governance Constrained Mode
- **Triggers**: Drift elevated, fallback tier ≥2, SDI >0.4, drawdown >8%
- **Constraints**: Scaling up disabled, increased monitoring
- **Actions**: 
  - Review trigger causes
  - Consider position adjustments
  - Monitor for improvement

### Survival Core Mode
- **Triggers**: Crisis probability high, convexity breach, drawdown >12%
- **Constraints**: New risk blocked, research disabled, position reduction
- **Actions**:
  - Immediate risk assessment
  - Consider emergency position reduction
  - Escalate to operator
  - Prepare for manual intervention

### Recovery Mode
- **Triggers**: State corruption, WAL interruption, manual trigger
- **Constraints**: Minimal operations only, manual approval required
- **Actions**:
  - Stop all automated trading
  - Assess state corruption extent
  - Rebuild from ledger if needed
  - Manual verification before resuming

## Incident Response Procedures

### Heartbeat Stale Alert
1. Check live engine process status
2. Review recent logs for errors
3. Attempt automatic restart (daemon handles this)
4. If restart fails, manual investigation required
5. Check system resources and connectivity

### Accounting Integrity Violation
1. **IMMEDIATE**: Block new risk automatically
2. Compare canonical vs reported equity
3. Review recent position updates
4. Check ledger for inconsistencies
5. Trigger reconciliation process
6. Manual verification before resuming

### Clock Drift Excessive
1. Check system time synchronization
2. Verify NTP service status
3. Compare with reference time sources
4. If drift >30 seconds, consider trading halt
5. Synchronize system clock
6. Monitor for stability

### Memory/CPU Resource Pressure
1. Check process memory usage
2. Restart research worker if needed (automatic)
3. Throttle research during market hours (automatic)
4. Monitor for memory leaks
5. Consider system restart if persistent

## Weekly Operations

### Weekly Review (Sundays)
```bash
python scripts/weekly_research_review.py
```

1. **Performance Review**
   - Calculate weekly returns
   - Analyze strategy performance
   - Review risk metrics
   - Update weekly equity anchor

2. **System Health Assessment**
   - Review governance events
   - Analyze mode transitions
   - Check error rates
   - Assess resource usage trends

3. **Research Review**
   - Review research outputs
   - Evaluate model performance
   - Consider parameter adjustments
   - Plan research priorities

### Capital Tier Review
1. Evaluate scaling triggers
2. Review stability metrics
3. Assess performance requirements
4. Make tier adjustment decisions
5. Document rationale

## Emergency Procedures

### Emergency Stop
```bash
python scripts/emergency_reduce.py --stop-all
```
- Stops all automated trading
- Maintains monitoring only
- Requires manual restart

### Position Reduction
```bash
python scripts/emergency_reduce.py --reduce-50pct
```
- Reduces position sizes by 50%
- Maintains system operation
- Logs all actions

### Recovery Mode Activation
```bash
python scripts/northstar_daemon.py --recovery-mode
```
- Rebuilds state from ledger
- Disables research and scaling
- Requires manual verification

## Monitoring and Alerts

### Key Metrics to Monitor
- Heartbeat freshness
- Accounting integrity
- Risk utilization
- Mode transitions
- Resource usage
- Performance metrics

### Alert Escalation
1. **Info**: Log only
2. **Warning**: Dashboard alert
3. **Error**: Email notification (if configured)
4. **Critical**: Immediate operator attention

### Log Locations
- Daemon logs: `logs/northstar_daemon.log`
- Engine logs: `logs/options_integrated_engine.log`
- Governance events: `data/options/live/governance_events.parquet`
- WAL journal: `data/options/live/write_journal.log`

## Configuration Management

### Key Configuration Files
- `config/northstar_daemon.yaml` - Main daemon configuration
- `config/research_policy.yaml` - Research governance
- `.env.options` - API credentials and secrets

### Configuration Changes
1. Test changes in development environment
2. Backup current configuration
3. Apply changes during market closed hours
4. Verify system startup
5. Monitor for issues

## Backup and Recovery

### Daily Backups
- Source of truth directories:
  - `data/options/`
  - `data/model_registry/`
  - `data/research/`
- Recommended external destination: `/Volumes/NORTHSTAR_BACKUP/northstar_v3`
- Manual run:
  ```bash
  python scripts/backup_northstar_data.py --destination-root /Volumes/NORTHSTAR_BACKUP/northstar_v3 --verify
  ```
- Enable daily automation:
  ```bash
  BACKUP_DEST=/Volumes/NORTHSTAR_BACKUP/northstar_v3 scripts/manage_cron.sh add-backup
  ```

### Recovery Procedures
1. Identify corruption extent
2. Stop affected processes
3. Restore from backup if needed
4. Rebuild state from ledger
5. Verify integrity before resuming

## Runtime State Safety

### Manual Edit Rule
- Do not edit `data/options/live/options_runtime_state.json` manually in normal operations.
- Runtime integrity is checksum-guarded; out-of-band edits are treated as tamper/corruption signals.
- Allowed exception: documented recovery operation only.
- If runtime edits are required for recovery:
  1. Stop daemon and live engine.
  2. Run recovery mode (`--recovery-mode`) to rebuild from ledger.
  3. Resume only after integrity checks pass.

## Pre-Deployment Resilience Gate

Before enabling full live deployment, run a resilience dry-run with fault injections.

### 72-Hour Gate
```bash
python scripts/run_chaos_dry_run.py --duration-hours 72 --system-profile minimal --config config/northstar_daemon.yaml
```

### Fast Validation (quick smoke)
```bash
python scripts/run_chaos_dry_run.py --duration-hours 1 --quick --system-profile minimal --config config/northstar_daemon.yaml
```

The harness injects:
- WAL interruption
- Runtime corruption
- Stale heartbeat
- Governance mode transition triggers
- Research freeze trigger check
- Artificial drawdown/de-scaling pressure

Outputs:
- `data/options/live/chaos_dry_run_report.json`
- `logs/chaos_dry_run_daemon.log`

## Performance Optimization

### Resource Management
- Monitor memory usage trends
- Optimize research scheduling
- Manage log file sizes
- Clean up old data files

### System Tuning
- Adjust monitoring intervals
- Optimize database queries
- Tune garbage collection
- Monitor network latency

## Compliance and Audit

### Audit Trail
- All trades logged in ledger
- Governance events tracked
- Mode transitions recorded
- Configuration changes logged

### Reporting
- Daily performance summaries
- Weekly risk reports
- Monthly system health reports
- Quarterly compliance reviews

## Troubleshooting Guide

### Common Issues
1. **Process won't start**: Check lock files, permissions
2. **High memory usage**: Restart research worker
3. **Slow performance**: Check CPU usage, disk I/O
4. **Data inconsistencies**: Run reconciliation
5. **API errors**: Check credentials, rate limits

### Diagnostic Commands
```bash
# System status
python scripts/status.py

# Health check
python scripts/health_check.py

# Process monitoring
ps aux | grep northstar

# Resource usage
top -p $(cat data/options/live/northstar_daemon_status.json | jq -r '.daemon_pid')
```

## Contact Information

### Escalation Contacts
- Primary Operator: [Contact Info]
- Technical Support: [Contact Info]
- Emergency Contact: [Contact Info]

### System Information
- System Version: Northstar V2
- Deployment Environment: [Production/Staging]
- Last Updated: [Date]
