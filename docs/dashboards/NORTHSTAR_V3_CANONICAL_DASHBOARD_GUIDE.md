# Northstar V3 Canonical Dashboard Guide

## Purpose

The Northstar V3 canonical dashboard is the single integrated visualization surface for the V3 system after the Gap 8 cutover. It is intended to be a real-data-first Streamlit app that reads the current system state, operational artifacts, research outputs, risk surfaces, Alpha OS telemetry, options runtime, valuation outputs, and unified P&L artifacts. When a required source is missing, the dashboard should now surface unavailability explicitly instead of fabricating healthy-looking state.

This guide documents:

- the canonical launch path
- the dashboard architecture
- the real data sources it reads
- the layout and section model
- the complete visualization inventory
- the operational and troubleshooting model

## Canonical Entry Points

- App entrypoint: `src/dashboard/app.py`
- Integrated renderer: `src/dashboard/integrated_dashboard.py`
- Read contract: `src/dashboard/data_contract.py`
- Secondary read hub: `src/dashboard/v3_data_hub.py`
- Primary launcher: `launch_dashboard.sh`
- Secondary launcher: `scripts/launch_dashboard.sh`

## Launch Commands

### Recommended

```bash
./launch_dashboard.sh --dev
```

### Production Mode

```bash
./launch_dashboard.sh
```

### Custom Port

```bash
./launch_dashboard.sh --port 8502 --dev
```

### Direct Streamlit Launch

```bash
python3 -m streamlit run src/dashboard/app.py
```

Important:

- Do not add a trailing `.` after `app.py`.
- The launcher now falls back to `python3 -m streamlit` automatically if `streamlit` is not on the shell `PATH`.
- The launcher also tolerates messy `.env` and `.env.options` files instead of aborting early.

## Design Principles

- Single dashboard authority: one app, one integrated layout, one visualization catalog.
- Real data only: no synthetic demo panels, no fake fallbacks, no mock placeholder charts.
- Canonical state first: `data/state/unified_state.json` remains the highest-level shared state surface.
- Artifact-driven rendering: the dashboard reads persisted outputs rather than recomputing system logic inline.
- Honest degradation: if a real dataset is missing, the panel should fail honestly instead of inventing values.
- Scalable layout: the integrated board groups visuals into sections so the system can hold 100+ charts without turning into an unmanageable monolith.

## Architecture

### 1. `src/dashboard/app.py`

This is the Streamlit entrypoint. It:

- sets the Streamlit page configuration
- imports the canonical renderer
- calls `render_dashboard()`

It contains no business logic and no dashboard-specific data assembly.

### 2. `src/dashboard/integrated_dashboard.py`

This is the main integrated dashboard layer. It:

- loads the full dashboard data bundle
- applies layout and styling
- defines the section order
- defines the visualization specification model
- renders the sidebar, hero, data manifest, and section boards
- binds every chart to a unique Streamlit key

It currently exposes:

- 8 dashboard sections
- 112 visualization modules
- section-scoped rendering and full-board rendering

### 3. `src/dashboard/data_contract.py`

This is the authoritative read-only contract for persisted dashboard data. It:

- loads canonical state
- loads P&L and benchmark data
- loads reconciliation and pipeline-status artifacts
- exposes normalized getters for dashboard consumers
- labels values with source, timestamp, and freshness

Key contract surfaces now include:

- benchmark history
- regime history
- macro state
- trades
- orders
- real-time risk
- pipeline health
- automation health
- state write log
- options IV surface
- options Greeks history
- portfolio history
- governor decisions
- valuation summary
- DCF components

### 4. `src/dashboard/v3_data_hub.py`

This is the lower-level read hub for persisted artifacts. It provides lightweight artifact loading and normalization for:

- market state
- portfolio weights
- sector flows
- daily narrative
- allocation history
- portfolio analytics
- benchmark index series

## Section Model

The canonical dashboard is organized into 8 sections:

1. Executive Overview
2. Performance & P&L
3. Market & Regime
4. Sentiment & Alternative Data
5. Portfolio & Governor
6. Options & Risk
7. Valuation & Research
8. Alpha OS & Operations

Current visualization count by section:

- Executive Overview: 8
- Performance & P&L: 16
- Market & Regime: 15
- Sentiment & Alternative Data: 14
- Portfolio & Governor: 15
- Options & Risk: 14
- Valuation & Research: 16
- Alpha OS & Operations: 14

Total visualization modules: 112

## Data Sources

The dashboard is not limited to one or two files anymore. It uses a layered real-data bundle.

### Canonical State

- `data/state/unified_state.json`
- `data/state/unified_state_history.parquet`
- `data/state/state_change_log.jsonl`
- `data/state/reconciliation_reports.parquet`

### Unified P&L and Benchmark

- `data/pnl/nav_history.parquet`
- `data/pnl/master_ledger.parquet`
- `data/pnl/reconciliation_log.parquet`
- `data/pnl/execution_quality.parquet`
- `data/pnl/benchmark_returns.parquet`
- `data/processed/benchmark/nifty50.parquet`
- `data/processed/shadow_pnl_series.parquet`

### Market, Regime, and Portfolio Artifacts

- `data/processed/market_state.parquet`
- `data/processed/intelligent_market_state.parquet`
- `data/processed/unified_daily.parquet`
- `data/processed/exposure_history.parquet`
- `data/processed/portfolio_weights.parquet`
- `data/processed/unified_portfolio.parquet`
- `data/processed/allocation_history.parquet`
- `data/processed/stock_roles.parquet`
- `data/processed/scores.parquet`
- `data/processed/strategy_performance.parquet`
- `data/processed/strategy_beliefs.parquet`
- `data/processed/strategy_regret.parquet`
- `data/processed/sector_flows.parquet`
- `data/processed/sector_rotation.parquet`

### Sentiment Artifacts

- `data/processed/sentiment/market_sentiment_daily.parquet`
- `data/processed/sentiment/ticker_sentiment_daily.parquet`
- `data/processed/sentiment/daily_sentiment_aggregated.parquet`

Market sentiment fallback logic:

- first use `market_sentiment_daily.parquet`
- if market polarity, conviction, uncertainty, or news volume are null there, aggregate them from `ticker_sentiment_daily.parquet`
- if ticker-derived aggregation is absent, fall back to `daily_sentiment_aggregated.parquet`

This keeps the dashboard real-data-only while still rendering the sentiment panels robustly.

### Alternative Data and Screener Artifacts

- `data/processed/alternative/bulk_deals_nse_all.parquet`
- `data/processed/alternative/credit_ratings_nse_all.parquet`
- `data/processed/alternative/promoter_pledge_all.csv`
- `data/processed/alternative/announcements_all.csv`
- `data/processed/screener_metadata.csv`
- `data/processed/screener_shareholding.csv`

### Options and Runtime Artifacts

- `data/options/live/nifty_options_latest.parquet`
- `data/options/live/options_runtime_state.json`
- `data/options/live/options_dashboard_state.json`
- `data/options/live/governance_events.parquet`
- `data/options/live/live_engine_heartbeat.json`
- `data/options/live/trading_day_orchestrator_status.json`

### Valuation and Research Artifacts

- `data/processed/valuation.parquet`
- `data/processed/valuation_families.parquet`
- `data/processed/valuation_posterior.parquet`
- `data/processed/valuation_engines.parquet`
- `data/processed/cohesive_alpha_feed.parquet`

### Alpha OS and Operational Artifacts

- `data/processed/alpha_os_timeseries.parquet`
- `data/processed/alpha_os_strategy_posteriors.parquet`
- `data/processed/system_execution_log.json`
- `data/processed/market_refresh_status.json`
- `data/sentiment/v3/sentiment_loop_status.json`
- `data/processed/alternative/alternative_pipeline_status.json`

## Freshness Model

The dashboard contract tags values using:

- `LIVE`
- `RECENT`
- `STALE`
- `OLD`
- `UNKNOWN`

Freshness is computed from the persisted artifact timestamps, not from browser render time alone.

## Layout Model

### Hero Layer

The top hero area summarizes:

- current NAV
- current market regime
- current sentiment regime
- active Alpha OS strategy count
- health score
- valuation coverage

It also shows freshness pills for:

- market pipeline
- sentiment pipeline
- alternative pipeline
- orchestrator
- options runtime
- heartbeat

### Sidebar

The sidebar controls:

- section selection
- full-board vs section mode
- data manifest visibility
- manual refresh

Default landing view is a single section rather than the full board, which keeps initial render manageable.

### Data Manifest

The data manifest shows the active dashboard sources and age metrics so the operator can quickly see whether a panel problem is a rendering issue or a stale artifact issue.

## Complete Visualization Inventory

### Executive Overview

- Portfolio vs NIFTY 50 (Indexed)
- Governor Capital Fractions
- Today's P&L Mix
- Regime Timeline
- Alpha OS Regime Probabilities
- Data Pipeline Age (Hours)
- System Component Status Mix
- Runtime Surface Age (Hours)

### Performance & P&L

- Total NAV
- Equity-Only NAV
- Options P&L Sleeve
- Daily Return
- Drawdown
- High Water Mark
- Net Cash Position
- Cumulative Transaction Costs
- Daily Return Distribution
- Monthly Returns Heatmap (%)
- Ledger Net P&L by Book
- Ledger Net P&L by Strategy
- Ledger Notional by Entry Type
- Trade Size Distribution
- Average Slippage (bps)
- Canonical NAV vs Shadow Portfolio Value

### Market & Regime

- Risk-On Probability
- Stress Score
- Macro Score
- Market Breadth
- Participation Score
- Market Correlation
- Allowed Equity Exposure
- Market Health Score
- Regime Timeline
- Regime Transition Matrix
- Volatility Regime Counts
- Risk-On Probability vs Stress Score
- Unified Daily Macro Score
- Unified Daily Max Equity Exposure
- Allowed vs Actual Exposure

### Sentiment & Alternative Data

- India Market Polarity
- India Market Conviction
- India Market Uncertainty
- Global Risk Sentiment
- Market News Volume
- Daily Sentiment Mean
- Daily Conviction Mean
- Daily Uncertainty Mean
- Headline Count
- Top Positive Ticker Sentiment
- Top Negative Ticker Sentiment
- Ticker Sentiment Coverage by Source
- Bulk Deals Count by Day
- Announcement Categories

### Portfolio & Governor

- Current Portfolio Weights
- Portfolio Weight by Role
- Sector Exposure by Weight
- Mispricing vs Final Weight
- Top Northstar Scores in Current Portfolio
- Strategy Allocation Time Series
- Allocation Heatmap (Recent)
- Governor Equity Fraction History
- Governor Options Fraction History
- Governor Cash Fraction History
- Governor Capital Fractions
- Governor Budget Allocation (INR)
- NSE Universe Stock-Role Distribution
- Alpha OS Strategy Weights
- Strategy Total Return

### Options & Risk

- IV Smile by Strike
- Open Interest by Strike
- Volume by Strike
- Delta by Strike
- Gamma by Strike
- Theta by Strike
- Vega by Strike
- Moneyness vs IV
- Option Chain IV Heatmap
- Active Option Positions: Net Greeks
- Active Option Positions by Underlying
- Options Governance Events
- Runtime IV History by Underlying
- Cross-Sectional Volatility Regimes

### Valuation & Research

- Margin of Safety Distribution
- Top Margin of Safety Names
- Moat Score Distribution
- P/E vs P/B
- Top Owner-Earnings Yield
- Margin of Safety by Industry
- Market Cap vs Margin of Safety
- Quality vs Final Value Index
- Posterior Gap Distribution
- Posterior Gap vs Confidence
- Valuation-Family Gap Heatmap
- Top Composite Engine Z-Scores
- Valuation Engine Agreement
- Top Cohesive Alpha Scores
- Cohesive Alpha Score Distribution
- Score Quintile Distribution

### Alpha OS & Operations

- Alpha OS Regime Probabilities
- Alpha OS Regime Entropy
- Alpha OS Capacity & Utilization
- Alpha OS Risk Stack
- Latest Alpha OS Strategy Weights
- Alpha OS Posterior Mean vs Final Weight
- Strategy Regret Scores
- Strategy Belief Strength
- Data Pipeline Age (Hours)
- System Component Status Mix
- Canonical State Writes by Section
- State Write Intensity
- Runtime Surface Age (Hours)
- Strategy Sharpe vs Max Drawdown

## Readability and Layout Optimizations

The integrated dashboard includes several structural quality improvements:

- every Plotly panel has an explicit unique Streamlit key
- long-label bar charts auto-switch to horizontal mode
- tall heatmaps scale their height based on row count
- dense line charts use larger heights automatically
- unavailable data is handled explicitly instead of collapsing the entire board

## Current Operational Reality

At the time of the latest hardening:

- all 112 visualization modules render
- zero dashboard panels are currently unavailable
- the market-sentiment panels are backed by real ticker-derived aggregation when the direct market-level file has null fields
- the launcher works in both `streamlit` and `python3 -m streamlit` environments

## Troubleshooting

### `StreamlitDuplicateElementId`

Cause:

- multiple Plotly charts were being rendered without unique keys

Fix:

- every chart now renders with `key=f"plotly_{spec.visual_id}"`

### `streamlit: command not found`

Cause:

- shell does not expose the `streamlit` binary

Fix:

- the launcher now falls back automatically to `python3 -m streamlit`

### Launcher treats `--dev` as the port

Cause:

- old launcher argument parsing only handled `--port` if it was the first argument

Fix:

- the launcher now uses full argument parsing for `--dev`, `--prod`, `--port`, and numeric port values

### Dashboard starts but a panel is weak or odd-looking

Likely causes:

- the underlying artifact is stale
- the artifact has sparse rows
- the artifact schema is real but operationally incomplete

How to inspect:

```bash
python3 scripts/system_status_report.py
python3 scripts/validate_gap8_dashboard.py
python3 -m pytest -q tests/test_dashboard_data_contract.py
```

### Direct Streamlit launch fails

Use:

```bash
python3 -m streamlit run src/dashboard/app.py
```

Do not use:

```bash
python3 -m streamlit run src/dashboard/app.py.
```

The trailing `.` makes Streamlit think the target has no valid `.py` extension.

## Validation

The dashboard should validate with:

```bash
python3 scripts/validate_gap8_dashboard.py
python3 -m pytest -q tests/test_dashboard_data_contract.py
```

## Extension Model

When adding a new visualization:

1. add the real dataset to the dashboard bundle
2. normalize it at load time, not inside every panel
3. add a `VisualSpec`
4. assign it to one of the existing sections
5. ensure it renders honestly on missing data
6. keep the source real-data-only

When adding a new data surface:

1. prefer `DashboardDataContract` for normalized dashboard-facing reads
2. use `V3DataHub` for lightweight artifact loading and normalization
3. avoid introducing a second dashboard authority or ad hoc inline loaders

## Related Files

- `src/dashboard/app.py`
- `src/dashboard/integrated_dashboard.py`
- `src/dashboard/data_contract.py`
- `src/dashboard/v3_data_hub.py`
- `launch_dashboard.sh`
- `scripts/launch_dashboard.sh`
- `scripts/start_live_trading.sh`
- `scripts/run_live_trading_system.sh`
- `scripts/validate_gap8_dashboard.py`
- `tests/test_dashboard_data_contract.py`
