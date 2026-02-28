# Northstar V3 Production-Grade Upgrade

This document summarizes the production-grade wiring work for the V3 system, the NS‑USO sentiment integration, and the new stable dashboard.

## Goals
- Real‑data‑only end-to-end execution
- Clear phase sequencing for daily runs
- Canonical state writes (single source of truth)
- Stable dashboard that never fabricates data
- Sentiment integration via NS‑USO artifacts

## What Changed
### 1) NS‑USO sentiment integration (real‑data‑only)
- Script updated: `ns_uso/scripts/run_v3_batch_ingestion.py`
- Behavior:
  - Copies real NS‑USO artifacts into `data/sentiment/v3/`
  - Writes `v3_sentiment_summary.json` with status
  - Never fabricates sentiment
- Expected artifacts:
  - `market_sentiment_india.parquet`
  - `sector_narratives.parquet`
  - `policy_context.json`

### 2) Canonical state discipline (write once, read many)
- `src/state/market_state.py`
  - Writes `market_state.parquet` via `StateFileManager` (atomic, validated)
- `src/portfolio/portfolio_governor.py`
  - Writes `portfolio_weights.parquet` and `portfolio_analytics.json` via `StateFileManager`
- `src/risk/unified_risk_coordinator.py`
  - Writes `risk_state.parquet` via `StateFileManager`
  - Keeps the JSON risk snapshot for logs

### 3) Dashboard stability
- Rebuilt data access layer (clean, real‑data‑only)
  - `src/dashboard/v3_data_hub.py`
- Rebuilt V3 sentiment panel (clean)
  - `src/dashboard/components/v3_sentiment_panel.py`
- Rebuilt unified dashboard coordinator
  - `src/dashboard/unified_dashboard_coordinator.py`
- Rebuilt P&L chart generator
  - `src/dashboard/generate_pnl_chart_data.py`
- Replaced broken “ultimate integrated” dashboard with a stable, production edition
  - `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`

### 4) Execution visibility
- `scripts/runners/refresh_v3_artifacts.py`
  - Now embeds `v3_sentiment_summary.json` in the execution log

## Daily Runbook
### Full run
```
python3 run_complete_v3_system.py
```

### Quick run
```
python3 run_complete_v3_system.py --quick
```

### Dashboard
```
streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py --server.port 8517
```

## NS‑USO Integration
Provide an export directory with the sentiment artifacts. You can set:
```
NS_USO_EXPORT_DIR=/absolute/path/to/ns_uso/exports/v3
```
The ingestion step copies those artifacts into `data/sentiment/v3/`.

## Notes
- No synthetic data is created in the dashboard or the NS‑USO ingestion step.
- If a data artifact is missing, the dashboard shows “No data yet”.
- The canonical write policy is enforced for market state, portfolio weights, and risk state.

## Next Enhancements (Optional)
- Add Edge Half‑Life and Liquidity Kill Switch modules
- Extend dashboard to show EdgeHealth and ExitRisk
- Add a scheduled runner (cron or systemd) for daily refresh

## Additions: Edge Half‑Life + Liquidity Kill Switch + Scheduler

### Edge Half‑Life
- Module: `src/intelligence/edge_half_life.py`
- Runner: `scripts/runners/run_edge_half_life.py`
- Outputs:
  - `data/processed/edge_half_life.json`
  - `data/processed/edge_half_life.parquet`
- Integrated into capital allocation as a decay multiplier (capital decay).

### Liquidity Kill Switch
- Module: `src/risk/liquidity_kill_switch.py`
- Runner: `scripts/runners/run_liquidity_risk.py`
- Outputs:
  - `data/processed/liquidity_risk.json`
  - `data/processed/liquidity_risk.parquet`
- Integrated into `UnifiedRiskCoordinator` as a liquidity‑aware exposure cap.

### Scheduler
- Script: `scripts/northstar_daily_scheduler.py`
- Usage:
```
python3 scripts/northstar_daily_scheduler.py --hour 18 --minute 0
```
This runs the full pipeline daily at the specified local time.
