# Northstar V3 System Logic Audit

Date: 2026-03-21

## Scope

This audit explains how the system is programmed to work today by tracing the current canonical entrypoints, the shared state model, and the main domain subsystems under `src/`.

Important boundary:

- This repo contains both active production surfaces and older/legacy/compatibility code.
- This audit treats the `scripts/` operator surface plus the `src/` modules it actively calls as canonical.
- Older roots and compatibility wrappers are documented separately so they are not confused with the live path.

## Executive Summary

Northstar V3 is programmed as a multi-layer operating workspace for Indian equities and options:

1. `scripts/` is the operator and scheduling layer.
2. `src/ingestion` and related pipelines build point-in-time-safe datasets.
3. `src/core/state.py` plus `src/core/state_authority.py` form the canonical shared-state model.
4. Equity, options, sentiment, alternative data, portfolio governance, PnL, and risk each compute their own artifacts and then sync into unified state.
5. The dashboard is mostly a read-only projection over persisted artifacts, not the execution authority.

In practical terms, the system does not behave like one monolithic application. It behaves like a coordinated artifact-and-state pipeline:

- scripts run jobs
- jobs write parquet/json/sqlite artifacts
- canonical sync consolidates those artifacts into `data/state/unified_state.json`
- dashboards and checks read from that consolidated state plus direct domain artifacts

## Canonical Runtime Surface

These are the current authoritative entrypoints discovered from the repo docs and code:

- `scripts/run_trading_day_orchestrator.py`
- `scripts/run_complete_v3_system.py`
- `scripts/preopen_checks.py`
- `scripts/run_morning_pipeline.py`
- `scripts/runners/sync_live_books_to_runtime.py`
- `scripts/runners/refresh_runtime_accounting.py`
- `src/dashboard/app.py`

Key wrappers that are not supposed to own business logic:

- `run_complete_v3_system.py` forwards to `scripts/run_complete_v3_system.py`
- `run_daily_v3.py` is a scheduler-friendly wrapper around the canonical runner
- `src/dashboard/unified_dashboard_coordinator.py` is a launcher/logging wrapper

## Architecture Model

The current codebase is best understood as 6 layers.

### 1. Operator Layer

This is the automation shell of the system.

- Starts the live stack
- schedules intraday loops
- runs preflight and end-of-day steps
- restarts failed loops
- writes operator status/log files

Main files:

- `scripts/start_live_trading.sh`
- `scripts/stop_live_trading.sh`
- `scripts/run_trading_day_orchestrator.py`
- `scripts/run_complete_v3_system.py`

### 2. Data Ingestion Layer

This is the authoritative data-read layer.

- `src/ingestion/base_loader.py` defines common rules: PIT enforcement, freshness checking, caching, schema handling
- `src/ingestion/ingestion_registry.py` is the single facade used by higher layers
- loaders are split by domain: market, fundamentals, macro, alternative, sentiment, options

The design intent is explicit: all consumers should read via `IngestionRegistry` instead of touching raw files directly.

### 3. Domain Compute Layer

This is where actual business logic is computed.

Examples:

- sentiment regime classification
- alternative data interpretation
- portfolio capital structure
- options strategy generation and execution gating
- valuation feature calculation
- daily scoring and ranking
- PnL, reconciliation, and NAV

### 4. Shared State Layer

This is the in-memory and persisted coordination layer.

- `src/core/state.py` defines the unified state dataclasses
- `src/core/state_authority.py` is the only intended mutation interface
- writers register allowed sections and priorities
- updates are logged to `data/state/state_change_log.jsonl`
- checkpoints are written to `data/state/unified_state.json`

This is the main control-plane contract of the system.

### 5. Runtime Truth Layer

For live positions and execution history, the system uses stronger runtime authorities:

- `data/runtime/portfolio_runtime.db` as PRS SQLite event store
- `data/portfolio/current_positions.json` as recovery/checkpoint view
- `data/pnl/master_ledger.parquet` as immutable accounting ledger

Bridges reconcile these layers into unified state.

### 6. Read Model / UI Layer

Dashboards and APIs mainly read from persisted surfaces.

- Streamlit dashboard: `src/dashboard/app.py` -> `src/dashboard/integrated_dashboard.py`
- dashboard contract: `src/dashboard/data_contract.py`
- API: `src/api/server.py`

These are mostly consumers, not authorities.

## Operational Flow

## A. Live Trading Day Flow

The live stack starts from `scripts/start_live_trading.sh`.

It does 2 things:

1. launches the Streamlit dashboard
2. launches `scripts/run_trading_day_orchestrator.py`

The trading-day orchestrator is the live supervisor.

Before market open it:

- waits for trading day/open time
- runs preflight steps unless skipped
- writes status into `data/options/live/trading_day_orchestrator_status.json`
- acquires a single-instance lock so multiple orchestrators cannot run together

Its preflight bundle includes:

- Upstox connectivity check
- one-shot sentiment refresh
- alternative data preflight
- runtime book sync
- runtime accounting refresh
- current positions snapshot
- strict runtime checks
- full `preopen_checks.py`

During market hours it supervises three loops:

- market refresh loop
- options engine loop
- sentiment loop

Those loops are launched as subprocesses and monitored for:

- unexpected process exit
- stale heartbeats/status files
- failed statuses

If a loop dies or gets stale, the orchestrator stops and restarts it up to a configured limit.

Every intraday cycle window, it also runs a runtime sync bundle:

- sync live books into runtime
- refresh accounting
- snapshot current positions
- run strict options runtime checks

After market close it runs the EOD pipeline:

- runtime book sync
- runtime accounting refresh
- current positions snapshot
- forced market refresh
- forced RBI update
- market-state integration
- alternative data refresh
- artifact refresh
- optional periodic reports
- optional options backtester refresh
- strict system update check

## B. Daily Full-System Refresh Flow

The canonical full-system batch runner is `scripts/run_complete_v3_system.py`.

It has 3 modes:

- `--dashboard-only`
- `--data-only`
- full mode

Its stage plan in quick mode is intentionally limited to refreshed data and canonical state sync. Full mode adds research/backtest layers.

Core stages:

1. market refresh
2. RBI macro update
3. macro feature refresh
4. optional alternative data refresh
5. screener processing
6. valuation score warmup
7. news and sentiment refresh
8. canonical dataset build
9. market data freshness gate
10. optional research/backtests/beliefs/regret/tailwinds
11. capital allocator
12. live score generation
13. opportunity surface
14. portfolio construction
15. current positions sync
16. runtime book sync
17. runtime accounting
18. strategy surface sync
19. canonical state sync
20. optional preopen checks and morning pipeline

This script is effectively the repo’s main artifact production backbone.

It also writes structured run artifacts under:

- `data/operations/complete_v3_runs/<run_id>/`

## C. Morning Scoring Flow

The morning signal-generation path is `scripts/run_morning_pipeline.py`.

It supports:

- `xgboost`
- `transformer`
- `tcn`
- `all` for side-by-side comparison

The main scorer is `src/scoring/daily_scorer.py`.

Its logic:

1. resolve the as-of date
2. load the latest PIT-safe feature snapshot
3. determine regime via `RegimeEngine`
4. load the correct regime-conditional model
5. score the universe
6. apply sentiment overlay
7. apply macro tilts
8. persist canonical scores to `data/processed/scores.parquet`
9. archive a dated copy in `data/processed/score_history/`

The scorer also contains turnover-control logic so the new ranked list does not rotate too aggressively relative to the previous portfolio.

## Shared State Logic

The central shared object is `UnifiedState` in `src/core/state.py`.

Major sections include:

- `market`
- `macro`
- `regime`
- `beliefs`
- `portfolio`
- `risk`
- `health`
- `sentiment`
- `alternative_data`
- `alpha_os`
- `pnl_state`
- `governor_state`
- `shadow_state`
- `valuation_state`

Important behavior:

- dataclass-backed sections carry normalized operational values, not raw datasets
- `load_snapshot()` hydrates persisted JSON back into the in-memory dataclass shape
- legacy aliases like `market_state` and `risk_state` are still supported for compatibility

`StateAuthority` adds the safety model around this:

- writers must register their allowed sections
- updates are field-level, not whole-object rewrites
- writes are lock-protected
- critical sections trigger checkpointing
- every update is logged with writer, section, field path, priority, source, and reason

This means the intended state mutation contract is:

- compute state elsewhere
- push only the resulting interpreted fields through `StateAuthority`

## Canonical State Sync Logic

The most important consolidation function in the repo is `sync_canonical_state()` inside `scripts/run_complete_v3_system.py`.

This function reconstructs the current system state from many artifact surfaces and writes the result into unified state.

It does all of the following:

- loads existing unified state if present
- creates a `StateAuthority`
- registers `complete_v3_runner` as a state writer
- runs `IngestionRegistry.health_check()` and data lineage reporting
- reads processed market/intelligence artifacts into core market/macro/regime/belief fields
- computes a fresh `SentimentState`
- runs the alternative data pipeline and computes `AlternativeDataState`
- loads Alpha OS strategy registry and strategy weights
- reads options runtime JSON and converts it into portfolio and risk fields
- reads PnL/NAV/reconciliation snapshots
- runs runtime and shadow bridges if their sources exist
- writes equity portfolio data into unified state
- writes health metrics
- computes portfolio-governor capital structure and syncs `GovernorState`
- checkpoints unified state
- refreshes a legacy processed risk snapshot for downstream compatibility

This is the main “brain assembly” step of the current system.

## Data Ingestion Logic

The ingestion layer is one of the cleanest parts of the current architecture.

Common rules from `src/ingestion/base_loader.py`:

- every loader accepts `as_of_date`
- PIT violations are checked explicitly
- freshness thresholds are configurable
- stale-but-usable data can warn; too-stale data can error
- loader-local caching avoids repeated disk reads in a run

Domain specifics:

- `MarketLoader` loads prices, applies corporate actions, handles delistings/symbol migrations, and enforces no-lookahead
- `FundamentalLoader` enforces publication lags for annual/quarterly/shareholding data
- `SentimentLoader` reads canonical company and market sentiment with explicit availability dates
- `AlternativeDataLoader` handles GST, power, credit, bulk deals, and promoter pledges with PIT-safe availability logic

Architecturally, this means research and live features are meant to share the same read rules.

## Sentiment Logic

Sentiment is split into 3 levels.

### 1. Raw/processed sentiment loading

Handled by `src/ingestion/sentiment_loader.py`.

It loads:

- company sentiment
- market sentiment

and filters strictly on `AvailabilityDate <= as_of_date`.

### 2. Regime classification

Handled by `src/sentiment/sentiment_regime.py`.

It uses:

- smoothed sentiment values
- threshold bands
- hysteresis

Hysteresis is important: regimes do not flip immediately on small boundary moves.

### 3. Unified sentiment state

Handled by `compute_sentiment_state()` in `src/sentiment/sentiment_state.py`.

It converts the raw time series into an interpreted `SentimentState`:

- sentiment regime
- trend
- z-score
- 1w and 1m momentum
- volatility
- confidence
- freshness
- company coverage
- crisis signal
- divergence vs market action

The design intent is explicit in code comments: downstream systems should consume interpretations, not redo sentiment math.

## Alternative Data Logic

Alternative data is also split into 2 layers.

### 1. Source loading

Handled by `src/ingestion/alternative_loader.py`.

It PIT-loads:

- GST
- power consumption
- credit ratings
- bulk deals
- promoter pledges

### 2. Interpretation pipeline

Handled by `src/alternative_data/alternative_pipeline_runner.py`.

This runner:

- checks whether each source is fresh
- computes market-level alternative features
- translates them into state objects:
  - `GSTSignalState`
  - `PowerSignalState`
  - `CreditSignalState`
  - `SmartMoneyState`
  - `PromoterRiskState`
- computes a composite `economic_activity_regime`
- records whether any/all sources are fresh

Like sentiment, this layer exists so the rest of the system consumes interpreted signals instead of raw source data.

## Portfolio Governance Logic

Top-level capital allocation authority lives in `src/portfolio/governor.py`.

The Governor decides the day’s capital structure before lower-level allocation logic runs.

Its sequence is:

1. read current market, volatility, macro, sentiment, and alternative-data regimes from unified state
2. read crisis probability if a crisis engine is connected
3. read current drawdown and NAV from `pnl_state`
4. compute a scalar caution score
5. map the caution score to a capital-structure regime
6. load base fractions for equity, options, and cash
7. apply modifiers:
   - drawdown modifier
   - recovery modifier
   - crisis override
   - NAV size protection
8. enforce hard limits
9. normalize weights to sum to 1
10. convert fractions into INR budgets
11. write the result into `GovernorState`

So the Governor is not a position picker. It is the top-down capital budget controller.

## Alpha OS Logic

Alpha OS is the strategy catalog and strategy-weight surface.

The main registry lives in `src/alpha_os/strategy_registry.py`.

It tracks:

- strategy lifecycle status
- validation evidence
- live performance
- probation/retirement/redundancy state
- regime activations
- status history

During canonical sync, the system reads this registry plus posterior/runtime strategy weights and projects them into unified `alpha_os` state.

This makes Alpha OS primarily a strategy-governance and allocation metadata layer, not the central execution engine itself.

## Options Runtime Logic

The options sleeve is one of the most complex subsystems and has its own mini-operating system.

The live loop entrypoint is:

- `scripts/run_integrated_options_paper_engine.py`

That engine wires together:

- Upstox adapter
- regime detector
- strategy generator
- eligibility validator
- capital scaling engine
- survival rules engine
- position manager
- tax-aware PnL tracker
- trade ledger
- event publisher
- Alpha OS adapter
- canonical sentiment context
- PRS runtime service
- runtime accounting sync

The options loop writes and maintains:

- runtime state JSON
- dashboard state JSON
- heartbeat JSON
- loop status JSON

The options dashboard contract in `src/options/dashboard_state_contract.py` normalizes that runtime payload into a stable schema for UI consumers.

Conceptually, the options engine does this each cycle:

1. read live market/options context
2. determine current regime
3. generate candidate strategies
4. validate eligibility and risk
5. manage open positions and exits
6. write runtime/dashboard/heartbeat artifacts
7. sync into PRS/runtime accounting layers

## PRS Runtime Logic

The Portfolio Runtime Service in `src/runtime/portfolio_runtime_service.py` is the canonical mutation authority for runtime portfolio state.

Its backing store is `src/runtime/storage.py`, a SQLite event store with:

- portfolio events
- execution fills
- portfolio snapshots
- stress matrices
- lifecycle tables
- runtime controls
- certification snapshots

The PRS service is designed as an event-driven state machine:

- proposal
- decision
- execution
- state materialization

It also coordinates:

- capital allocation policy
- risk budget manager
- liquidity gate
- certification gate
- rebalance trigger engine
- shock engine
- adaptive regime/parameter engines
- research evolution hooks
- alpha mortality control

This is the strongest “single-writer runtime truth” subsystem in the repo.

## Runtime Sync and Reconciliation Logic

Because the repo has multiple state representations, it uses bridges.

### Runtime bridge

`src/core/state_bridges/runtime_bridge.py` synchronizes:

1. `portfolio_runtime.db`
2. `UnifiedState.portfolio`
3. `data/portfolio/current_positions.json`

Its authority model is explicit:

- DB = transactional authority
- unified state = operational authority
- JSON checkpoint = recovery authority

### Shadow bridge

`src/core/state_bridges/shadow_bridge.py` reads shadow portfolio state and syncs:

- shadow positions
- shadow NAV
- live-vs-shadow position overlap
- live-vs-shadow NAV divergence

### Accounting refresh

`src/pnl/runtime_accounting_sync.py` is the canonical accounting rebuild step.

It regenerates:

- master ledger rows
- NAV history
- reconciliation outputs
- accounting snapshot
- runtime DB accounting controls

It pulls from:

- equity PnL artifacts
- current positions
- options trade ledger/runtime state
- shadow PnL
- runtime DB
- unified state

## PnL Logic

PnL is structured around immutable accounting surfaces.

Main components:

- `src/pnl/ledger.py`: append-only unified ledger
- `src/pnl/nav_calculator.py`: NAV, returns, drawdown, cash position
- `src/pnl/reconciliation.py`: canonical-vs-derived consistency checks
- `src/pnl/attribution.py`: strategy/regime/sector/cost attribution
- `src/pnl/execution_quality.py`: slippage, shortfall, fill-rate metrics

Design principles in code:

- append-only
- double-entry intent
- PIT-safe timestamps
- multi-book support: equity, options, cash, shadow

This is one of the more institutionally-structured parts of the repo.

## Risk Logic

Risk is split between newer deterministic gates and older batch protection modules.

### Deterministic trade gate

`src/risk/risk_policy.py` plus `src/risk/risk_controller.py`

This path is policy-driven and deterministic:

- immutable risk policy
- position risk cap
- portfolio risk cap
- max drawdown gate
- weekly trade cap
- event calendar staleness gate
- optional alternative-risk checks

### Survival containment

`src/risk/survival_core_mode.py`

This is a hard containment override system.

It activates when enough structural stress conditions fire and then:

- clamps gross exposure
- disables short convexity
- freezes growth/new risk behavior

### Artifact-based kill/risk modules

There are also older/batch-style modules such as:

- `src/risk/liquidity_kill_switch.py`
- `src/risk/portfolio_kill_switches.py`
- `src/risk/emergency_brake.py`
- `src/risk/portfolio_risk_controller.py`

These still encode important logic, but they are not the clearest single live authority in the current architecture.

## Dashboard Logic

The canonical UI entrypoint is `src/dashboard/app.py`.

It simply calls `render_dashboard()` from `src/dashboard/integrated_dashboard.py`.

The integrated dashboard logic is:

1. load static data bundle
2. render sidebar filters
3. choose active tab via registry
4. periodically refresh live fragments
5. compose bundle from static, intraday, live options, and runtime risk data
6. route the filtered bundle to section renderers

The dashboard registry declares:

- tab order
- live tabs
- visual registry

The dashboard data contract in `src/dashboard/data_contract.py` reads authoritative persisted surfaces including:

- unified state
- NAV history
- reconciliation logs
- runtime state
- market/sentiment/orchestrator status
- state change logs
- options governance and chains
- valuation and portfolio history

So the dashboard is a curated read model over many persisted artifacts.

## API Logic

`src/api/server.py` exposes a FastAPI surface for snapshots, time series, strategies, holdings, charts, and health.

Based on current code, this API is more of a secondary interface than the primary live operating surface.

It reads persisted artifacts directly and does not appear to be the system’s execution backbone.

## Intelligence Observer Logic

`src/intelligence_observer/` is a separate analysis/observer layer with strong guardrails.

It includes:

- lagged snapshot builder
- temporal isolation
- authority firewall
- read-only observer context
- question engines for regime, stress, portfolio structure, and meta integrity
- observer scheduler

This subsystem is programmed to observe the system with temporal and authority restrictions, rather than directly trade.

## Validation and Audit Logic

The repo contains a very large validation surface:

- `src/validation/` has 89 Python files
- combined `tests/` plus embedded `*/tests/` files total 101 files

This suggests heavy emphasis on validation, scenario testing, shadow comparison, and certification, though this audit did not execute the test suite.

## Main Persistence Surfaces

The most important persisted artifacts in the current architecture are:

### Unified coordination state

- `data/state/unified_state.json`
- `data/state/state_change_log.jsonl`
- `data/state/unified_state_history.parquet`

### Runtime truth

- `data/runtime/portfolio_runtime.db`
- `data/portfolio/current_positions.json`

### Accounting truth

- `data/pnl/master_ledger.parquet`
- `data/pnl/nav_history.parquet`
- `data/pnl/reconciliation_log.parquet`
- `data/pnl/accounting_snapshot.json`

### Options live surfaces

- `data/options/live/options_runtime_state.json`
- `data/options/live/options_dashboard_state.json`
- `data/options/live/live_engine_heartbeat.json`
- `data/options/live/options_loop_status.json`

### Portfolio/research artifacts

- `data/processed/portfolio_weights.parquet`
- `data/processed/portfolio_analytics.json`
- `data/processed/scores.parquet`
- `data/processed/score_history/*.parquet`
- `data/processed/market_state.parquet`

## What Is Live vs What Looks Legacy

The repo contains multiple overlapping systems. These are the main distinctions.

### Canonical today

- `scripts/run_trading_day_orchestrator.py`
- `scripts/run_complete_v3_system.py`
- `src/core/state.py`
- `src/core/state_authority.py`
- `src/runtime/portfolio_runtime_service.py`
- `src/dashboard/app.py`

### Compatibility or likely non-canonical surfaces

- `src/orchestrator/system_orchestrator.py`
- `src/orchestrator/master_orchestrator.py`
- `src/state/unified_state_manager.py`
- `src/dashboard/unified_dashboard_coordinator.py`
- root launchers that only forward or are explicitly marked legacy

### Mixed/partially live

- older risk controllers and kill-switch modules
- large historical dashboards under `src/dashboard/*ultimate*` and `*comprehensive*`
- older operational docs with V2 naming

## Audit Findings

### 1. The real architecture is artifact-driven, not service-driven

The system is programmed around persisted parquet/json/sqlite outputs and periodic synchronization, not around one always-on typed application process.

Effect:

- good operational resilience and inspectability
- higher risk of drift between artifacts if sync steps are skipped

### 2. Canonical state is centralized, but compute is decentralized

Many modules compute their own truth first, then sync results into `UnifiedState`.

Effect:

- modular domain logic
- strong need for the canonical sync stage

### 3. Options runtime is the most stateful and operationally complex subsystem

It has its own:

- live loop
- JSON runtime state
- dashboard state
- heartbeat/status files
- PRS runtime DB
- trade ledger
- accounting sync

Effect:

- powerful live operating surface
- also the highest operational coordination burden

### 4. Equity and options are intentionally stitched together rather than natively unified

The repo unifies them through:

- runtime sync
- accounting sync
- canonical state sync
- dashboard contracts

Effect:

- practical integration
- but several bridge layers are required to keep them aligned

### 5. The repo still carries legacy overlap

There are multiple state managers, orchestrators, dashboards, and risk surfaces.

Effect:

- understanding the system requires knowing which surfaces are current
- wrong entrypoint choice can easily lead to confusion

## Recommended Mental Model

If you want to reason about this system correctly, use this model:

1. `scripts/` decides when things run.
2. `src/ingestion` decides what data is valid to read.
3. domain modules compute interpreted signals and artifacts.
4. PRS/runtime and PnL subsystems hold transactional truth.
5. canonical state sync assembles a system-wide operating picture.
6. dashboards and APIs read from that operating picture and nearby artifacts.

## Bottom Line

Northstar V3 is programmed as a coordinated hedge-fund workspace, not as a single app.

Its strongest current design patterns are:

- PIT-safe ingestion
- explicit shared-state authority
- immutable-style accounting surfaces
- supervised process orchestration
- read-only dashboard projections

Its main complexity comes from:

- multiple overlapping generations of architecture
- bridge-heavy equity/options integration
- many artifact surfaces that must remain synchronized

If future cleanup is needed, the safest consolidation targets are:

1. legacy orchestrators
2. duplicate state readers/managers
3. non-canonical dashboard variants
4. older batch risk modules whose authority is unclear relative to PRS and unified state
