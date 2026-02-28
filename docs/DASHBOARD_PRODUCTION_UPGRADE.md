# Northstar V3 Dashboard (Production Upgrade)

This document explains what we changed to make the V3 dashboard production-ready, real-data-only, and substantially more informative (30–40+ charts across tabs).

## How To Run

### Dashboard
```bash
python3 -m streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py --server.port 8517
```

If you prefer the launcher:
```bash
python3 scripts/launch_northstar_v3_ultimate_integrated_dashboard_fixed.py
```

### Refresh Artifacts (Real Data Only)
```bash
python3 scripts/runners/refresh_v3_artifacts.py
```

### Full Pipeline
```bash
python3 run_complete_v3_system.py
```

### Daily Scheduler (Hands-Off)
```bash
python3 scripts/northstar_daily_scheduler.py --hour 18 --minute 0
```

## What “Production-Grade” Means Here

1. No synthetic/mock generation in the dashboard.
2. Missing artifacts do not crash the app; panels show “No data yet” plus the exact artifact path.
3. Heavy artifacts (like full `prices.parquet`) are not loaded unless needed and are filtered via Parquet predicate pushdown.
4. Every panel ties back to an on-disk artifact and indicates staleness via the “Freshness” table.

## Key Additions

### Edge Half-Life (EdgeHealth)
Artifacts:
- `data/processed/edge_half_life.json`
- `data/processed/edge_half_life.parquet`

Runner:
- `python3 scripts/runners/run_edge_half_life.py`

Dashboard:
- Tab `Edge + Liquidity`:
  - Edge Health by strategy (bar)
  - Half-life vs edge health (scatter)

### Liquidity Kill Switch (ExitRisk)
Artifacts:
- `data/processed/liquidity_risk.json`
- `data/processed/liquidity_risk.parquet`

Runner:
- `python3 scripts/runners/run_liquidity_risk.py`

Dashboard:
- Tab `Edge + Liquidity`:
  - Exit risk by position (bar, thresholds)
  - Participation × ExitRisk risk-map (scatter; size=weight)

### Real-Time + Automation
Dashboard:
- Tab `Real‑Time`: quick refresh button, current positions view, risk authority snapshot, alerts.
- Tab `Automation`: canonical commands, pipeline status + staleness, NS‑USO bridge status, one-click refresh utilities.

## NS‑USO Sentiment Bridge

Bridge runner:
```bash
python3 ns_uso/scripts/run_v3_batch_ingestion.py
```

Expected export directory:
- Set `NS_USO_EXPORT_DIR=/path/to/ns_uso/exports/v3`, or
- Place artifacts under `ns_uso/exports/v3/`

V3 target directory (what the dashboard reads):
- `data/sentiment/v3/`

Required files:
- `market_sentiment_india.parquet`
- `sector_narratives.parquet`
- `policy_context.json`

Optional file:
- `v3_sentiment_summary.json` (written by the bridge if no data exists / status marker)

## Main Dashboard Tabs (What They Use)

1. Command Center
   - `data/portfolio/pnl_on_paper.parquet`
   - `data/processed/index_data/nifty_50.parquet`
   - Freshness from various artifact mtimes

2. System Health
   - `data/processed/system_execution_log.json`
   - `data/processed/*` mtimes

3. V3 Analytics
   - `data/portfolio/pnl_on_paper.parquet`
   - `data/processed/performance_summary.parquet` (if present)

4. Advanced Intelligence
   - `data/processed/strategy_beliefs.parquet`
   - `data/processed/strategy_regret.parquet`
   - `data/processed/allocation_history.parquet`
   - `data/processed/market_regime.parquet`
   - `data/processed/regime_transitions.parquet`
   - `data/processed/macro_factors.parquet`
   - `data/processed/opportunity_surface.parquet`
   - `data/processed/narrative_state.parquet`
   - `data/processed/narrative_events.parquet`
   - `data/processed/attribution/comprehensive_attribution_*.json` (latest)

5. Wave Analysis
   - Indices: `data/processed/index_data/*.parquet`
   - Stocks: `data/processed/prices.parquet` (filtered by ticker)

6. Clustering
   - `data/processed/market_regime.parquet`

7. Portfolio Tracking
   - `data/portfolio/weekly/latest.json` + latest weekly snapshot parquet
   - Fallback: `data/processed/portfolio_weights.parquet`
   - `universe/nifty500.csv` and `data/processed/sector_mapping.csv` for industry/sector mapping
   - `data/processed/volatility_state.parquet`
   - `data/processed/liquidity_risk.parquet`

8. Shadow + Rebalance
   - `data/live/shadow_trading/pnl/pnl_*.json`
   - `data/portfolio/weekly/*.parquet`
   - `data/portfolio/trades/*.parquet`

9. Alerts
   - `data/processed/liquidity_risk.parquet`
   - `data/processed/edge_half_life.json`
   - `data/processed/capital_allocations.json` (NO_EDGE reasons if present)

10. Sentiment
   - `data/sentiment/v3/*`

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`
The dashboard now injects the project root into `sys.path` at runtime. If you still see this:
1. Ensure you’re running from the repo root: `northstar_v3/`
2. Run via: `python3 -m streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`

### “Benchmark stays flat”
Check the index artifact date range:
- `data/processed/index_data/nifty_50.parquet`

The dashboard aligns benchmark dates to the portfolio P&L range.

