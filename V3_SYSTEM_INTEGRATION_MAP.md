# Northstar V3 System Integration Map

## 1. Primary Runtimes

- Intraday orchestrator:
  - `scripts/run_trading_day_orchestrator.py`
  - Runs:
    - Options live loop (`scripts/run_integrated_options_paper_engine.py`, continuous mode)
    - NS-USO sentiment loop (`scripts/run_ns_uso_sentiment_loop.py`)
  - After market close, runs EOD pipeline.

- Full/quick V3 orchestrator:
  - `run_complete_v3_system.py`
  - Phases:
    1. Data ingestion (`src/ingestion/integrated_data_pipeline.py`)
    2. System update (`scripts/runners/simple_system_update.py`, `scripts/runners/refresh_v3_artifacts.py`)
    3. Optional heavier validation/backtest/shadow/report phases
    4. Integration alignment checks
    5. Optional dashboard launch

- Scheduler entrypoint:
  - `run_daily_v3.py`
  - Calls `run_complete_v3_system.py` with quick/full mode.


## 2. Data Integration Spine

- RBI + market ingestion:
  - `src/ingestion/integrated_data_pipeline.py`
  - Inputs:
    - RBI: scraper -> processor -> cleaner artifacts under `data/macro/*`
    - Market: yfinance/index feeds under `data/raw/prices_daily`, `data/options/live/market_data_latest.json`
  - Output:
    - Unified market state artifacts consumed by portfolio, options overlay, and dashboard.

- Macro-conditioned alpha layer:
  - `scripts/macro_conditioned_signal_audit.py`
  - Output:
    - `data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet`
    - `data/processed/macro_conditioned_alpha/composite_ic_summary.csv`
    - `data/processed/macro_conditioned_alpha/latest_regime_conditioned_weights.csv`
    - `data/processed/macro_conditioned_alpha/macro_conditioned_audit_report.json`

- Mandatory robustness tests:
  - `scripts/macro_conditioned_mandatory_tests.py`
  - Output:
    - `reports/signal_audit/macro_conditioned_mandatory/*`


## 3. Portfolio and Options Linkage

- Portfolio governor:
  - `src/portfolio/portfolio_governor.py`
  - Consumes macro-conditioned snapshot.
  - Default regime authority is `intelligent_market_state` (single source of truth).
  - Dual-engine (trend/crisis) is advisory by default and does not override exposure/regime unless explicitly enabled.
  - Override switch:
    - `NS_USE_DUAL_ENGINE_OVERRIDE=1`
  - Blends legacy opportunity score with macro-conditioned rank.
  - Writes canonical portfolio artifacts (`data/processed/portfolio_weights.parquet`, analytics json).

- Options engine:
  - `scripts/run_integrated_options_paper_engine.py`
  - Uses live/near-live option chain + regime/risk overlay and writes dashboard state.


## 4. Dashboard Integration

- Main app:
  - `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`
- Data hub:
  - `src/dashboard/v3_data_hub.py`
- Macro tab now displays:
  - RBI macro factor tape
  - Macro-conditioned composite IC (equal vs regime-conditioned)
  - Mandatory robustness flags
  - Latest per-asset macro-conditioned snapshot
  - Latest regime-conditioned signal weights


## 5. Wiring Fixes Applied

1. `run_complete_v3_system.py`
   - Added `--no-dashboard` (automation-safe)
   - Added `--skip-options-cycle`
   - Phase 2 can skip single-shot options cycle when needed

2. `run_daily_v3.py`
   - Corrected behavior so daily runs do not accidentally start dashboard-only mode
   - Defaults to non-interactive (`--no-dashboard`) unless explicitly requested

3. `scripts/run_trading_day_orchestrator.py`
   - EOD full-run step now uses `run_complete_v3_system.py` instead of legacy script
   - Added EOD control flags:
     - `--eod-v3-mode {quick,full}`
     - `--eod-force-data`
     - `--eod-skip-integration-alignment`
   - EOD V3 call is non-interactive and skips post-close options single cycle

4. `src/portfolio/portfolio_governor.py`
   - Fixed normalization for `ai_allowed_exposure` and `ai_risk_on_probability` so both `%` and `[0,1]` inputs are handled correctly
   - Enforced single-regime-authority default (intelligent state) to prevent crisis-engine hard overrides from forcing 0% exposure in conflicting states
   - Added regime alignment diagnostics (`regime_authority`, `regime_alignment`, engine advisory regime/exposure)

5. `scripts/runners/refresh_v3_artifacts.py`
   - `market_pulse` now runs via module path (`-m src.intelligence.market_brain.market_pulse`) to avoid relative-import runtime errors
   - `regime_feed` now uses intelligent-state regime authority by default and records authority metadata in `data/processed/regime_intelligence_feed.json`
   - `daily_narrative` now prefers intelligent-state regime + allowed exposure
   - `portfolio_analytics` now carries intelligence integration fields (regime, authority, alignment)

6. `scripts/runners/run_edge_half_life.py`
   - Added explicit run summary output (`strategies`, `ok`, `insufficient`, top-3 remaining half-life) for observability

7. `src/intelligence/market_brain/regime_memory.py`
   - Added persisted PCA model path (`data/models/regime_pca.pkl`) and load-on-inference fallback
   - Removed runtime failure in pulse regime matching when TensorFlow is unavailable


## 6. Recommended Runtime Commands

- Intraday trading-day orchestration (market hours + EOD):
  - `python3 scripts/run_trading_day_orchestrator.py --run-once-day --aggressive`

- EOD-only full V3 refresh (no dashboard, no options single cycle):
  - `python3 run_complete_v3_system.py --quick --no-dashboard --skip-options-cycle --force-data`

- Refresh dashboard artifacts only:
  - `python3 scripts/runners/refresh_v3_artifacts.py --quick`

- If you intentionally want dual-engine to override canonical regime/exposure:
  - `NS_USE_DUAL_ENGINE_OVERRIDE=1 python3 scripts/runners/refresh_v3_artifacts.py --quick`

- Recompute macro-conditioned alpha + mandatory tests:
  - `python3 scripts/macro_conditioned_signal_audit.py --horizon 20 --lookback-days 504 --min-obs 20 --output-dir data/processed/macro_conditioned_alpha`
  - `python3 scripts/macro_conditioned_mandatory_tests.py --lookback-days 504 --min-obs 20`
