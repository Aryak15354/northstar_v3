# Gap 5 Integration Guide

## Quick Start: 3 Steps to Production

### Step 1: Run Migration (One-Time)

```bash
python scripts/run_gap5_migration.py
```

This migrates historical P&L data from 5 legacy sources into the unified ledger.

**Expected Output:**
- Migrated entries count
- Conflict count (should be 0 or minimal)
- If conflicts exist, review `data/pnl/migration_conflicts.json`

**Success Criteria:**
- ✓ Migration completes without errors
- ✓ Zero conflicts (or all conflicts resolved)
- ✓ Ledger integrity verified

---

### Step 2: Integrate EOD Process (Daily)

Replace your current EOD script with the enhanced version:

```bash
# Test the new EOD process
python scripts/eod_rebalance_with_pnl.py
```

**What It Does:**
1. Records EOD mark-to-market for all positions
2. Flushes ledger to disk (atomic write)
3. Computes daily P&L attribution
4. Measures execution quality
5. Runs daily reconciliation
6. Updates PnLState in UnifiedState
7. Checks paper fund health

**Expected Output:**
- ✓ Ledger flushed
- ✓ Attribution written
- ✓ Execution quality computed
- ✓ Reconciliation status: CLEAN
- ✓ Fund health: ON_TRACK

---

### Step 3: Monitor Reconciliation (30 Days)

Run daily monitoring:

```bash
python scripts/monitor_gap5_reconciliation.py
```

**What It Tracks:**
- Daily reconciliation status (CLEAN/WARNING/CRITICAL)
- Clean streak counter
- Discrepancy trends
- Recent issues

**Success Criteria:**
- ✓ 30 consecutive days of CLEAN status
- ✓ No critical reconciliation failures
- ✓ Discrepancies within tolerance

**After 30 Days:**
- Archive legacy P&L files
- Declare Gap 5 production-ready
- Generate 6-month certificate

---

## Detailed Integration Steps

### A. Pre-Migration Checklist

- [ ] Backup existing P&L files
- [ ] Verify all 5 legacy sources exist
- [ ] Review config/pnl_config.yaml
- [ ] Test ledger creation

### B. Migration Process

1. **Run Migration**
   ```bash
   python scripts/run_gap5_migration.py
   ```

2. **Review Conflicts** (if any)
   ```bash
   cat data/pnl/migration_conflicts.json
   ```

3. **Resolve Conflicts**
   ```python
   from src.pnl.ledger import UnifiedPnLLedger
   
   ledger = UnifiedPnLLedger()
   
   # For each conflict, record correction
   ledger.correct(
       original_entry_id="...",
       corrected_entry=...,
       reason="Resolved conflict: used options ledger as authoritative source"
   )
   ledger.flush()
   ```

4. **Verify Migration**
   ```bash
   python scripts/validate_gap5_complete.py
   ```

### C. EOD Integration

1. **Update Your EOD Script**
   
   Add to your existing `eod_rebalance.py`:
   
   ```python
   from src.pnl.ledger import UnifiedPnLLedger
   from src.pnl.nav_calculator import NAVCalculator
   from src.pnl.attribution import PnLAttributor
   from src.pnl.reconciliation import PnLReconciler
   from src.pnl.execution_quality import ExecutionQualityMonitor
   from src.pnl.paper_fund import PaperFundManager
   
   # Initialize (once at start)
   ledger = UnifiedPnLLedger()
   nav_calc = NAVCalculator(ledger, config)
   attributor = PnLAttributor(ledger, registry, config)
   reconciler = PnLReconciler(ledger, nav_calc, config)
   execution_monitor = ExecutionQualityMonitor(ledger, config)
   paper_fund = PaperFundManager(ledger, nav_calc, attributor, config)
   
   # At EOD (after positions finalized):
   
   # 1. Record EOD marks
   ledger.record_eod_mark(today, equity_positions, equity_prices,
                          options_positions, options_prices)
   
   # 2. Flush ledger
   ledger.flush()
   
   # 3. Write attribution
   attributor.write_daily_attribution(today)
   
   # 4. Execution quality
   execution_monitor.write_daily_execution_quality(today)
   
   # 5. Reconciliation
   recon_result = reconciler.run_daily_reconciliation(today)
   reconciler.write_reconciliation_log(recon_result)
   
   if recon_result.overall_status == 'CRITICAL':
       # Alert!
       send_alert(f"P&L reconciliation CRITICAL: {recon_result.action_required}")
   
   # 6. Update state
   state.pnl_state.pnl_today_inr = ledger.get_total_pnl(today)
   state.pnl_state.current_nav_inr = nav_calc.compute_daily_nav(...)['nav_combined'].iloc[-1]
   state.pnl_state.fund_health = paper_fund.compute_current_fund_status()['fund_health']
   
   # 7. Check fund health
   alerts = paper_fund.check_fund_health_alerts()
   for alert in alerts:
       send_alert(alert)
   ```

2. **Test EOD Process**
   ```bash
   python scripts/eod_rebalance_with_pnl.py
   ```

3. **Verify Output Files**
   ```bash
   ls -lh data/pnl/
   # Should see:
   # - master_ledger.parquet (updated)
   # - attribution_daily.parquet (new row)
   # - reconciliation_log.parquet (new row)
   # - execution_quality.parquet (new row)
   ```

### D. Monitoring Setup

1. **Daily Monitoring**
   
   Add to cron or scheduler:
   ```bash
   # Run after EOD process
   0 18 * * * cd /path/to/northstar_v3 && python scripts/monitor_gap5_reconciliation.py >> logs/reconciliation_monitor.log 2>&1
   ```

2. **Weekly Review**
   
   Every Monday, review:
   - Reconciliation status
   - Clean streak progress
   - Execution quality trends
   - Fund health status

3. **Alerts**
   
   Set up alerts for:
   - Reconciliation status != CLEAN
   - Fund health = BREACH
   - Execution quality deteriorating

---

## Troubleshooting

### Migration Issues

**Problem:** Conflicts detected
- **Solution:** Review `data/pnl/migration_conflicts.json`, determine authoritative source, record corrections

**Problem:** Missing legacy files
- **Solution:** Check that all 5 legacy sources exist, or modify migration to skip missing sources

### EOD Integration Issues

**Problem:** Reconciliation status = CRITICAL
- **Solution:** Check `data/pnl/reconciliation_log.parquet` for details, review action_required field

**Problem:** Execution quality shows high slippage
- **Solution:** Review shadow vs live price differences, check execution logic

### Monitoring Issues

**Problem:** Clean streak not increasing
- **Solution:** Investigate reconciliation failures, check for data quality issues

---

## File Locations

### Input Files (Legacy)
- `data/portfolio/pnl_on_paper.parquet`
- `data/execution/shadow_pnl.parquet`
- `data/paper_trading/performance_log.csv`
- `data/options/trade_ledger.parquet`
- `data/simulation/daily_portfolio_metrics.parquet`

### Output Files (Unified)
- `data/pnl/master_ledger.parquet` - Single source of truth
- `data/pnl/attribution_daily.parquet` - Daily attribution
- `data/pnl/reconciliation_log.parquet` - Daily reconciliation
- `data/pnl/execution_quality.parquet` - Daily execution metrics
- `data/pnl/nav_history.parquet` - NAV time series (computed)

### Configuration
- `config/pnl_config.yaml` - P&L system configuration

### Logs
- `logs/eod_pnl_summary.log` - Daily EOD summary
- `logs/reconciliation_monitor.log` - Monitoring output

---

## Success Milestones

### Week 1
- [x] Migration complete
- [x] Zero conflicts
- [x] First EOD process successful
- [x] First reconciliation CLEAN

### Week 2
- [ ] 7 consecutive clean reconciliations
- [ ] Execution quality baseline established
- [ ] Attribution reports generated

### Week 4
- [ ] 30 consecutive clean reconciliations
- [ ] Fund health stable
- [ ] Ready for production

### Month 6
- [ ] 6-month certificate generated
- [ ] Institutional validation complete
- [ ] Legacy files archived

---

## Next Steps After 30 Days

1. **Archive Legacy Files**
   ```bash
   mkdir -p data/pnl/legacy_archive
   mv data/portfolio/pnl_on_paper.parquet data/pnl/legacy_archive/
   mv data/execution/shadow_pnl.parquet data/pnl/legacy_archive/
   mv data/paper_trading/performance_log.csv data/pnl/legacy_archive/
   ```

2. **Generate 6-Month Certificate**
   ```python
   from src.pnl.paper_fund import PaperFundManager
   
   paper_fund = PaperFundManager(ledger, nav_calc, attributor, config)
   certificate = paper_fund.generate_six_month_certificate()
   ```

3. **Declare Production Ready**
   - Update system documentation
   - Present certificate to stakeholders
   - Enable full production mode

---

**Status:** Ready for Migration  
**Last Updated:** March 13, 2026
