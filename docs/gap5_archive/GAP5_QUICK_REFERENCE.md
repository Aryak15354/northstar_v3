# Gap 5 Quick Reference

## Basic Usage

### Record Trades
```python
from src.pnl.ledger import UnifiedPnLLedger

ledger = UnifiedPnLLedger()

# Equity trade
ledger.record_equity_trade("RELIANCE", 100, 2500.0, "momentum", -125.0)

# Options trade
ledger.record_options_trade("NIFTY", 50, 200.0, "CE", 25000.0, 
                           expiry, greeks, "volatility", -50.0)

# Flush to disk
ledger.flush()
```

### Query Ledger
```python
# All entries
df = ledger.query()

# Filter by date
df = ledger.query(start_date=date1, end_date=date2)

# Filter by book
df = ledger.query(books=[LedgerBook.EQUITY])

# Filter by strategy
df = ledger.query(strategy_ids=["momentum_specialist"])
```

### Compute NAV
```python
from src.pnl.nav_calculator import NAVCalculator

nav_calc = NAVCalculator(ledger, config)
nav_df = nav_calc.compute_daily_nav(start_date, end_date)
metrics = nav_calc.compute_performance_metrics(start_date, end_date)
```

### P&L Attribution
```python
from src.pnl.attribution import PnLAttributor

attributor = PnLAttributor(ledger, registry, config)
strategy_attr = attributor.compute_strategy_attribution(start, end)
```

### Reconciliation
```python
from src.pnl.reconciliation import PnLReconciler

reconciler = PnLReconciler(ledger, nav_calc, config)
result = reconciler.run_daily_reconciliation(date)
```

## Key Files

- **Ledger**: `data/pnl/master_ledger.parquet`
- **NAV**: `data/pnl/nav_history.parquet`
- **Attribution**: `data/pnl/attribution_daily.parquet`
- **Reconciliation**: `data/pnl/reconciliation_log.parquet`

## Validation

```bash
# Run validation
python scripts/validate_gap5_complete.py

# Run tests
pytest src/pnl/tests/test_ledger.py -v

# Run demo
python examples/gap5_pnl_demo.py
```

## Status: ✅ COMPLETE
