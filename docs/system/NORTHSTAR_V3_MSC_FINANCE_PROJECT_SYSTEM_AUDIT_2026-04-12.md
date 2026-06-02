# Northstar V3 MSc Finance Project System Audit

Date: 2026-04-12  
Workspace: `/Users/aryakghoshal/Downloads/northstar/northstar_v3`  
Prepared for: MSc Finance university project report preparation  
Audit type: Architecture, finance methodology, data, model, execution, governance, and operational readiness audit  

## 1. Executive Summary

Northstar V3 is not a small single-purpose script. It is a large quantitative finance operating workspace that combines Indian equity research, alternative data ingestion, sentiment intelligence, market regime classification, portfolio governance, options strategy logic, paper/live execution orchestration, PnL accounting, dashboards, and experiment infrastructure.

For an MSc Finance submission, the strongest and most defensible framing is:

> Northstar V3 is an integrated quantitative investment research and trading decision-support system for Indian equities and index/stock options. It combines point-in-time market and fundamental data, alternative data, sentiment and shock intelligence, regime-aware portfolio allocation, options risk controls, and governed research workflows. Its implementation is broad and advanced, but the repository currently shows signs of active transition: live execution, research, dashboarding, generated artifacts, archived material, and experimental code coexist in one workspace.

The system is academically rich because it touches many finance concepts:

- Cross-sectional equity ranking and factor modelling.
- Regime-aware asset allocation.
- Alternative data and sentiment overlays.
- Point-in-time data discipline and look-ahead bias controls.
- Options strategy selection and risk gating.
- Drawdown, NAV, Sharpe/Sortino/Calmar, cost drag, turnover, liquidity, and risk budgets.
- Research governance, model promotion, audit logs, and reproducibility.
- Practical operational issues: stale data, token management, scheduler design, dashboard observability, and failure modes.

The most important caveat is that the workspace should not be described as a clean, finished, fully production-certified system without qualification. Current evidence shows:

- A very large dirty worktree with many modified, deleted, and untracked files.
- Large generated data and temporary artifact areas.
- Documentation drift between older "complete" claims and newer audits.
- Mixed research and execution responsibilities inside one repository.
- Some current tests pass and test collection is healthy, but a targeted regression slice still has failures.
- Some config and documentation surfaces are stale or transitional, such as a 2024 options event calendar and V3/V4 naming drift.

For the university report, the best approach is to present the project as a sophisticated evolving quantitative finance platform, then explicitly discuss limitations and future improvements. That will read as much more credible than overclaiming production maturity.

## 2. Audit Scope and Evidence Base

This audit was prepared from repository inspection rather than live market verification. It uses:

- Current source files under `src/`, `scripts/`, `config/`, `tests/`, `docs/`, and `audit/`.
- Current root documentation such as `README.md`, `ROOT_FOLDER_README.md`, and `config/system_surface.yaml`.
- Existing historical audit documents in `audit/`.
- Existing system overview documentation in `docs/system/`.
- Targeted test collection and regression runs.
- Directory scale checks and artifact size checks.

Current evidence gathered during this audit:

- `src` contains 870 Python files, excluding `__pycache__`.
- `scripts` contains 593 Python files, excluding `__pycache__`.
- `tests` contains 287 Python files, excluding `__pycache__`.
- `python3 -m pytest --collect-only -q tests` collected 1995 tests successfully.
- A targeted test slice ran with 15 tests passing and 2 tests failing.
- The workspace has very large data and temporary areas: `data` is about 9.0 GB and `tmp` is about 5.6 GB.

This audit did not perform:

- A full test suite execution.
- A live broker authentication test.
- A live Upstox order placement or market data session.
- A full dashboard UI inspection.
- A full independent recalculation of every dataset freshness metric.
- A security audit of credentials.
- A legal or compliance audit.

Therefore, this document is best treated as a deep system audit and project-report foundation, not as a production certification.

## 3. Current Repository Scale

Current measured repository scale:

| Area | Observation |
|---|---:|
| Python files in `src` | 870 |
| Python files in `scripts` | 593 |
| Python files in `tests` | 287 |
| Tests collected | 1995 |
| `src` disk usage | about 38 MB |
| `scripts` disk usage | about 22 MB |
| `tests` disk usage | about 26 MB |
| `data` disk usage | about 9.0 GB |
| `tmp` disk usage | about 5.6 GB |
| `docs` disk usage | about 5.1 MB |
| `audit` disk usage | about 12 MB |

This scale matters for the project report. It shows that Northstar V3 is more like a research and operations platform than a small coursework backtest. It also creates maintainability risks: when the codebase is this broad, strict boundaries, reproducibility, and clear source-of-truth documents become important.

## 4. Current Operating Identity

The current `README.md` describes Northstar V3 as an operational quantitative trading workspace for Indian equities and options. It includes:

- Live trading orchestration.
- Portfolio and hedge governance.
- Sentiment and alternative data ingestion.
- End-of-day market-state refresh.
- A separate research stack.
- Cron-based daily operations.
- Manual token refresh steps for Upstox access.

The documented daily operating model is:

- Before the trading day, update `UPSTOX_ACCESS_TOKEN` in `.env.options`.
- Around 08:50 IST on trading days, run the live trading-day orchestrator.
- During market hours, keep market refresh, sentiment, options runtime, ledger/accounting sync, and loop restarts alive.
- After 15:30 IST, run end-of-day refresh for market state, alternative data, dashboard artifacts, and strict checks.
- On Saturdays, run weekend maintenance.
- At 20:45 IST daily, run backup.

Key commands documented in the root README include:

```bash
python3 scripts/verify_live_system.py --for-tomorrow
bash scripts/start_live_trading.sh
bash scripts/stop_live_trading.sh
scripts/manage_cron.sh show
python3 scripts/preopen_checks.py
python3 scripts/run_research_worker.py --once --manual-run
python3 scripts/run_complete_v3_system.py --quick
python3 scripts/runners/refresh_v3_artifacts.py --quick --skip-index --skip-integrity-audit
```

For project-report language, this means the system can be described as:

- A live-aware quantitative finance system.
- A research platform with model governance.
- A portfolio operating system.
- A dashboard and monitoring environment.
- A hybrid equity and options decision system.

However, it should not be described as a cleanly separated research-only platform, because execution and research currently share code, state, data, and runtime assumptions.

## 5. Strategic Boundary Assessment

An important existing audit, `audit/V3_RESEARCH_ENGINE_BOUNDARY_AUDIT_2026-04-04.md`, argues that Northstar V3 should ideally be split into:

- A research engine.
- A separate execution/options system.

That audit found that the repository currently includes:

- Historical data preparation.
- Feature engineering.
- Model training and walk-forward validation.
- Signal export.
- Broker adapters.
- Options runtime.
- Live/paper trading flows.
- Portfolio state.
- Dashboards.
- Alerts.
- Generated artifacts.
- Archive material.

The clean target architecture would be:

| System | Should own |
|---|---|
| Research V3 | Historical data, PIT feature engineering, model training, backtests, walk-forward validation, signal export, research governance |
| Execution/options system | Broker adapters, OMS, live/paper execution, fills, portfolio state, runtime risk, dashboards, alerts |

Current state does not fully respect that split. For example, `scripts/run_research_worker.py` reads live options runtime state such as:

- `data/options/live/options_runtime_state.json`
- `data/options/live/market_data_latest.json`

This is a boundary leak: a pure research engine should not depend on live runtime state unless it is explicitly importing a snapshot as an input artifact.

For an MSc Finance report, this is useful. You can include a "System Boundary and Future Work" section and say:

- The current implementation is intentionally integrated for experimentation and operations.
- A future institutional design would separate research from execution.
- This would improve reproducibility, compliance, risk control, and deployment safety.

## 6. Canonical Surface and Repository Layout

The file `config/system_surface.yaml` identifies the intended system surface:

| Surface | Role |
|---|---|
| `src/` | Core Python package surface |
| `scripts/` | Operational runners, ingestion scripts, research and maintenance scripts |
| `tests/` | Test surface |
| `config/` | Runtime, ingestion, portfolio, options, and system configuration |
| `docs/operations/` | Operational guidance |
| `ns_uso/` | Northstar USO surface |
| `data/` | Active generated and canonical data |
| `logs/` | Runtime logs |
| `models/` | Model artifacts |
| `universe/` | Universe and reference artifacts |

The same config also marks some areas as generated, quarantined, or deprecated:

| Category | Examples |
|---|---|
| Generated active | `data/`, `logs/`, `models/`, `universe/` |
| Quarantined/generated | `_cold_archive/`, `archive/`, `data/results/analysis/`, `reports/`, `snapshots/`, `fund_grade_reports/` |
| Deprecated root surfaces | `dashboard/`, `northstar/`, `system/` |

The root `ROOT_FOLDER_README.md` reinforces that the primary working set is:

- `src/`
- `scripts/`
- `config/`
- `docs/operations/`
- `tests/`
- `ns_uso/`

It also warns against treating legacy root launchers, generated artifacts, and archive folders as primary source.

Academic interpretation:

- The codebase is mature enough to have a declared source surface.
- It is also messy enough that an audit must distinguish canonical files from legacy or generated files.
- This distinction should be explicitly described in the report methodology.

## 7. High-Level Architecture

Northstar V3 can be understood as a layered system:

1. Data ingestion and canonical data layer.
2. Point-in-time and feature engineering layer.
3. Sentiment, alternative data, macro, and news intelligence layer.
4. Market state and unified state authority layer.
5. Equity scoring and research model layer.
6. Portfolio governor and capital allocation layer.
7. Options strategy and risk-control layer.
8. PnL, ledger, NAV, and reconciliation layer.
9. Dashboard and monitoring layer.
10. Orchestration and automation layer.
11. Research governance and experiment-management layer.

Conceptual flow:

```text
Raw data sources
  -> ingestion registry and loaders
  -> canonical datasets
  -> PIT feature engineering
  -> sentiment, alternative, macro, valuation, and factor signals
  -> market state engine
  -> unified state authority
  -> scoring, research, and portfolio governor
  -> equity allocation and options strategy selection
  -> runtime accounting, PnL, NAV, reconciliation
  -> dashboard, reports, and audit logs
```

This layered framing is appropriate for an MSc Finance project because it connects software architecture to investment process design.

## 8. Data Architecture

Northstar V3 uses a broad data universe. Existing system documentation from 2026-03-22 reported the following historical data inventory. Treat these counts as a historical snapshot, not as guaranteed current counts:

| Dataset | Historical snapshot |
|---|---:|
| Prices | 2,003,406 rows |
| Price date range | 1996-01-01 to 2026-03-19 |
| Price tickers | 500 |
| Company news | 284,887 rows |
| Company news date range | 1997-10-02 to 2026-03-20 |
| Company news tickers | 4,154 |
| Market news | 32,722 rows |
| Company sentiment | 111,459 rows |
| Market sentiment | 5,858 rows |
| Annual fundamentals | 7,628 rows |
| Quarterly fundamentals | 5,841 rows |
| Shareholding | 5,718 rows |
| CEA power daily | 2,489 rows |
| RBI macro | 48,739 rows |
| Bulk deals | 226,058 rows |
| Promoter pledge | 2,785 rows |
| Announcements | 8,763 rows |
| Ticker master | 4,159 rows |

Major data categories:

- Equity prices.
- Fundamental financial statements.
- Shareholding data.
- Macro data from RBI and related sources.
- GST-related economic activity proxies.
- Power demand and generation data.
- Bulk deal and smart-money flow data.
- Credit rating updates.
- Promoter pledge data.
- Company announcements.
- Company and market news.
- Sentiment outputs.
- Options live and historical data.
- Reference universe files.
- Corporate actions.
- Experiment manifests and Kaggle artifacts.

The strongest technical theme is not only that the system ingests data, but that it tries to enforce:

- Point-in-time alignment.
- Release calendar discipline.
- Reporting lag discipline.
- Real-data-only constraints.
- Freshness checks.
- Schema expectations.
- Audit logs.

These are very relevant for a finance university report because they address look-ahead bias and data leakage.

## 9. Ingestion Configuration

`config/ingestion_config.yaml` defines many of the data layout assumptions. It includes:

- PIT strict mode.
- Reporting lag assumptions.
- Price paths.
- Screener paths.
- Macro paths.
- GST paths.
- Power data paths.
- Credit data paths.
- Bulk deal paths.
- Promoter pledge paths.
- Sentiment canonical paths.
- Options historical, EOD, and cache paths.
- Universe and corporate action paths.
- Release calendar paths.
- Macro feature paths.

The research data manager is designed to use `IngestionRegistry`. This is important because it centralizes dataset paths and contracts instead of scattering file paths throughout the code.

Audit interpretation:

- This is a strong design pattern for reproducible research.
- The system still needs consistent enforcement everywhere, because older audits found mixed or duplicate config surfaces.
- The report should mention centralized ingestion as a design strength and config drift as a maintainability risk.

## 10. Point-in-Time Discipline

The file `src/signal_engineering/pit_audit.py` implements PIT timestamp logic. It includes:

- A `PITTimestampManager`.
- Safety buffers for publication and ingestion timestamps.
- Future timestamp validation.
- Business-day alignment.
- A persisted PIT audit log.

Important caveat:

- The code contains a TODO for full NSE calendar handling, so business-day logic should not be described as fully institution-grade unless verified.

PIT discipline also appears in:

- `src/research/dataset_manager.py`
- `src/research/feature_factory.py`
- `config/ingestion_config.yaml`
- Existing research runbook and Kaggle architecture docs.

For a finance report, this can support a section on avoiding look-ahead bias:

- Fundamentals should be lagged from announcement or reporting dates.
- Alternative data should only be available after release/ingestion.
- Research splits should be time-ordered.
- Model training should not see future observations.

## 11. Alternative Data Layer

The alternative data layer is implemented around:

- `src/alternative_data/alternative_pipeline_runner.py`
- `src/alternative_data/alternative_feature_block.py`
- Alternative data state in the unified state model.

The pipeline includes:

- GST.
- Power.
- Credit.
- Bulk deals.
- Promoter pledge.

The runner computes freshness and state, then updates `AlternativeDataState`.

Default freshness thresholds include:

| Source | Example threshold |
|---|---:|
| Bulk deals | 2 days |
| Power data | 5 days/business days |
| Credit | 7 days |
| GST | about 1.5 months / 45 days plus grace |
| Promoter pledges | 100 days |

The feature block converts raw alternative data into model-ready features. Example logic:

- GST YoY growth and deviation are converted into a regime score.
- Power data is transformed into an industrial activity proxy.
- Credit, bulk deals, and pledge signals become stock-level or market-level features.

An example from the GST regime logic:

| Condition | Regime interpretation |
|---|---|
| YoY > 10 percent and deviation > 0.5 | strong positive |
| YoY > 5 percent | positive |
| YoY < -5 percent and deviation < -0.5 | strong negative |
| YoY < 0 or deviation < -0.25 | negative |
| Otherwise | neutral |

Academic interpretation:

- Alternative data is being used as a macro and market microstructure proxy.
- GST and power can be framed as economic activity indicators.
- Bulk deals can be framed as institutional/smart-money flow.
- Promoter pledge can be framed as governance and financial stress risk.
- Credit events can be framed as balance-sheet and default-risk information.

## 12. Sentiment Layer

The sentiment system is centered around:

- `src/sentiment/sentiment_state.py`
- `src/sentiment/sentiment_regime.py`

`compute_sentiment_state` creates a formal sentiment state with:

- Regime.
- Trend.
- Z-score.
- Momentum.
- Volatility.
- Freshness.
- Company coverage.
- Crisis divergence.

The sentiment regime classifier is rule-based, not a black-box ML classifier. It uses:

- Exponential moving averages.
- Hysteresis.
- Panic/fear/neutral/euphoria thresholds.

Example thresholds:

| Region | Threshold logic |
|---|---|
| Panic | sentiment score below about -2 |
| Fear | sentiment score below about -0.5 |
| Neutral | sentiment between fear and euphoria |
| Euphoria | sentiment score above about 2 |

Freshness is strict. Overall freshness requires:

- Sentiment data to be fresh.
- Data lag not to exceed allowed thresholds.
- Company sentiment to exist.
- Company coverage to be positive.
- Company lag not to exceed allowed limits.

Academic interpretation:

- This supports a behavioral-finance overlay.
- It can be described as a sentiment risk adjustment rather than a primary return model.
- The use of hysteresis is useful because it reduces whipsaw regime changes.

## 13. News and Shock Intelligence

The news intelligence layer includes:

- `src/intelligence/news_brain/news_brain.py`
- `src/intelligence/news_brain/shock_classifier.py`
- `src/intelligence/shock_engine/shock_response_engine.py`

The news brain runs:

- Company news processing.
- Market news processing.
- Macro news processing.
- NLP shock classification.
- Sector impact logic.
- Options strategy selection based on shocks.

The shock classifier maps textual and quantitative signals into shock types. Inputs can include:

- Headlines.
- Crude oil signals.
- INR/currency movement.
- FII flow.
- VIX.
- Rate-hike language.
- Oil supply disruption language.

The shock response engine turns shock intelligence into:

- Portfolio reduction instructions.
- Hedge instructions.
- Beneficiary increase instructions.
- Options strategy instructions.

Academic interpretation:

- This is a macro-news-to-portfolio-control layer.
- It is useful for discussing event risk, geopolitical shocks, oil shocks, currency shocks, and volatility shocks.
- It should be described as a rule/NLP-assisted shock-response system unless a specific trained NLP model is verified.

## 14. Market State Engine

The market state system is centered around:

- `src/state/market_state.py`
- `src/core/state.py`
- `src/core/state_authority.py`

`src/state/market_state.py` contains a `MarketStateEngine`. It combines:

- Macro regime.
- Market health.
- Liquidity.
- Stress.
- Breadth.
- Participation.
- Correlation.
- Opportunity density.
- Risk-on probability.
- Allowed exposure.
- Sentiment fields.
- Market brain fields.

The market state system includes regime exposure limits such as:

| Regime | Example exposure limit |
|---|---:|
| Boom | 0.90 |
| Expansion | 0.70 |
| Late expansion | 0.55 |
| Neutral | 0.40 |
| Slowdown | 0.25 |
| Crisis | 0.10 |

The runner `scripts/run_complete_v3_system.py` performs freshness checks on:

- `data/processed/market_state.parquet`
- `data/options/live/market_data_latest.json`
- `data/processed/prices.parquet`

It can hard-abort during market hours if market data is stale beyond its configured threshold.

Academic interpretation:

- This is a regime-aware exposure control system.
- It is not merely a predictive model; it acts as a risk throttle.
- It connects macro regime, market microstructure, volatility, and sentiment into an exposure recommendation.

## 15. Unified State and State Authority

`src/core/state.py` defines the `UnifiedState` model. Existing docs describe this as the "brainstem" or single source of truth for the system.

The unified state includes dataclass-style sections for:

- Market state.
- Macro state.
- Regime state.
- Pulse and beliefs.
- Confidence.
- Strategy.
- Capital.
- Portfolio.
- Risk.
- Sentiment.
- Alternative data.
- Alpha OS.
- Governor state.
- Shadow state.
- Valuation.

An important guard exists in `MarketState.__post_init__`:

- `allowed_exposure` and `risk_on_probability` are checked against impossible percent-point mistakes.
- Values greater than 1.5 are rejected as likely unit errors.

`src/core/state_authority.py` defines the write authority for state mutation. It includes:

- Registered writers.
- Allowed sections per writer.
- Writer priorities.
- Atomic batch updates.
- Rollback on error.
- Locks.
- Critical-section checkpointing for portfolio, risk, PnL, and governor state.
- State change logging to `data/state/state_change_log.jsonl`.

Writer priority classes include:

- Emergency.
- Live risk.
- Live trading.
- Bridge sync.
- Research.

Academic interpretation:

- This is a governance design, not only a data structure.
- It tries to prevent arbitrary components from mutating risk-critical state.
- It provides an audit trail for state transitions.

## 16. Full Daily Runner

`scripts/run_complete_v3_system.py` is the modern end-to-end daily runner. Its docstring describes it as the daily runner for "Gaps 1-7."

Important components imported by this runner include:

- `AlternativePipelineRunner`
- `StateFileManager`
- `UnifiedState`
- `StateAuthority`
- Runtime and shadow bridges.
- `IngestionRegistry`
- `refresh_shadow_reality_from_live_artifacts`
- `PortfolioGovernor`
- `SentimentRegimeClassifier`
- `compute_sentiment_state`

It loads configuration pieces from:

- Ingestion config.
- PnL config.
- Portfolio governor config.
- Sentiment config.
- NLP config.
- Valuation config.

Default starting capital is 10,000,000 INR in the portfolio governor area, while the options config uses a separate 500,000 INR capital base. This is not necessarily wrong, but it should be explained clearly in a project report if both appear in results.

Audit interpretation:

- The daily runner is the main state-refresh spine.
- It is broader than a backtest runner.
- It performs data freshness checks, state updates, and cross-component integration.

## 17. Trading Day Orchestrator

`scripts/run_trading_day_orchestrator.py` is the main live operating loop for trading days. It coordinates:

- Intraday market refresh.
- Upstox options engine loop.
- Sentiment loop.
- Restarting loops if processes exit.
- End-of-day market ingestion.
- RBI macro chain.
- Market state integration.
- Complete V3 computation stack.

It writes status artifacts such as:

- `data/options/live/trading_day_orchestrator_status.json`
- End-of-day state.
- Lock files.
- Options heartbeat and status.
- Sentiment status.
- Market status.
- Accounting snapshots.

Default underlyings include:

- NIFTY
- BANKNIFTY
- FINNIFTY
- RELIANCE
- TCS
- HDFCBANK
- INFY
- ICICIBANK
- SBIN

Academic interpretation:

- This is a practical trading operations layer.
- It shows how research signals and state logic are converted into daily operating flows.
- It should be separated from pure research claims in the report.

## 18. Portfolio Governor

The portfolio governor is implemented in:

- `src/portfolio/governor.py`
- `config/portfolio_governor_config.yaml`

Its role is to determine capital structure before allocation. The process described by the code includes:

- Read regime signals.
- Read crisis and drawdown information.
- Read NAV.
- Select base capital structure.
- Apply modifiers.
- Enforce hard limits.
- Validate capital weights sum correctly.
- Write history.
- Inject budgets.
- Emit an event.

The config sets:

- Starting capital: 10,000,000 INR.
- Default equity allocation: 70 percent.
- Default options allocation: 15 percent.
- Default cash allocation: 15 percent.

The regime table includes:

| Regime | Equity | Options | Cash |
|---|---:|---:|---:|
| FULL_DEPLOYMENT | 0.90 | 0.08 | 0.02 |
| STANDARD | 0.75 | 0.15 | 0.10 |
| CAUTIOUS | 0.60 | 0.20 | 0.20 |
| DEFENSIVE | 0.40 | 0.20 | 0.40 |
| CAPITAL_PRESERVATION | 0.15 | 0.10 | 0.75 |

Caution score weights include:

| Input | Weight |
|---|---:|
| Market regime | 0.30 |
| Volatility | 0.15 |
| Macro | 0.20 |
| Sentiment | 0.15 |
| Economic activity | 0.10 |
| Crisis | 0.10 |

Hard limits include:

- Minimum equity.
- Maximum equity.
- Minimum cash.
- Maximum options.
- Other allocation constraints.

The governor refuses stale unified state. This is important because it prevents allocation decisions from being based on outdated risk data.

Academic interpretation:

- The governor is a rules-based capital allocation system.
- It implements regime-aware portfolio construction.
- It links macro, sentiment, volatility, and crisis probability to asset allocation.
- It is a good place to discuss risk management as a first-class system component.

## 19. Equity Scoring and Turnover Control

The equity scoring surface includes:

- `src/scoring/daily_scorer.py`
- `src/scoring/northstar_model.py`
- Research models and feature blocks.

The daily scorer:

- Loads latest data.
- Loads or applies regime logic.
- Scores stocks.
- Applies sentiment overlays.
- Applies macro sector tilts.
- Outputs a ranked list.

Turnover control appears in `apply_turnover_constraint`:

- Previous holdings can be retained if rank remains within a threshold.
- Top-N selection is used.
- Maximum turnover defaults around 30 percent in the inspected implementation.

Cross-sectional prediction transformations include:

- Z-score.
- Rank.
- Rank power.
- Tanh.

Academic interpretation:

- This is a realistic portfolio-construction detail.
- Turnover control matters because transaction costs and market impact can destroy theoretical alpha.
- The report should distinguish raw model ranking from investable portfolio construction.

## 20. Research Engine

The research system includes:

- `src/research/research_engine.py`
- `src/research/research_controller.py`
- `src/research/dataset_manager.py`
- `src/research/feature_factory.py`
- `scripts/run_research_worker.py`
- `scripts/promote_research_model.py`
- Walk-forward validation scripts.
- Kaggle experiment architecture and runbooks.

The research engine is designed as a governed offline research orchestrator. It supports:

- Real-data-only mode.
- Strict anti-synthetic-data intent.
- Bayesian or strict model governance defaults.
- Model certification controls.
- Manual research runs.
- Scheduled research runs.
- Research memory and promotion controls.

Important current issue:

- `config/research_policy.yaml` currently contains only a comment: `# Runtime policy is encoded in chunk manifests for the chunked local builder.`
- The research engine code appears to fall back to a large default configuration if the config file is missing or invalid.

This is not necessarily a runtime failure, but it is an audit issue:

- Documentation implies a policy file may govern research.
- Current config does not explicitly encode that policy.
- Defaults hidden in code are harder to review in an academic report than explicit YAML policy.

For the project report:

- Present the research engine architecture.
- Mention that a current improvement would be to make the active research policy explicit in configuration.
- Avoid claiming that every research rule is visible in config unless you document the code fallback.

## 21. Research Dataset Manager

`src/research/dataset_manager.py` builds canonical research datasets. It uses:

- `IngestionRegistry`.
- `src.data.loaders`.
- `DuckDBQueryEngine`.
- `FeatureFactory`.
- `RegimeEngine`.
- Rolling splits.

It contains real-data-only controls:

- Required artifacts.
- Source keyword rejection for terms like mock, synthetic, sample data, demo data, and toy data.
- Point-in-time fundamental lag logic.
- Low-resource caps.

Academic interpretation:

- This is the center of research reproducibility.
- It can be described as a dataset construction and validation layer.
- It supports discussion of data leakage controls and training/validation discipline.

## 22. Feature Factory

`src/research/feature_factory.py` builds cross-sectional and time-series features. It supports:

- Point-in-time fundamentals.
- Screener data.
- Alternative data.
- Sentiment data.
- Macro data.
- Gap 9 academic factors.
- Valuation features.
- Academic factor registry.

PIT defaults include a 60-day fundamental lag in the inspected code path. The system uses `merge_asof_by_ticker` and grouped z-score/rank transformations.

Feature families include:

- Momentum.
- Value.
- Quality.
- Risk.
- Liquidity.
- Alternative data.
- Sentiment.
- Macro.
- Valuation.
- Academic factors.

Academic interpretation:

- This is a multi-factor feature factory.
- It combines finance theory factors with alternative and sentiment features.
- It is appropriate to discuss as a broad alpha research design rather than a single-model approach.

## 23. Valuation Layer

The valuation layer includes:

- `src/valuation/valuation_feature_block.py`
- DCF-related modules.
- Earnings quality analysis.
- Moat scoring.
- Bayesian valuation aggregation.

Feature examples include:

- Discount to fair value.
- Margin of safety.
- Owner earnings yield.
- DCF confidence.
- Moat score.
- ROCE.
- Revenue CAGR.
- Earnings consistency.
- Earnings quality.
- Accruals ratio.
- Debt safety.
- Interest coverage.
- Valuation composite.

Academic interpretation:

- This layer brings fundamental finance into the quant system.
- It connects intrinsic valuation concepts with cross-sectional ranking.
- It supports a hybrid fundamental-quant narrative.

## 24. Academic Factor Layer

The factor system includes:

- `src/factors/factor_registry.py`
- `src/factors/gap9_academic_factors.py`

Registered or implemented factors include:

- Betting-against-beta style factor.
- Amihud illiquidity.
- Piotroski F-score.
- MAX return.
- Earnings quality.
- Operating profitability.
- Earnings surprise.
- Promoter pledge.
- Bulk deal.
- Idiosyncratic volatility.

The registry can output:

- Raw factor values.
- Z-scores.
- Ranks.
- Availability information.

Academic interpretation:

- This creates a bridge between published asset-pricing literature and applied Indian market data.
- In the report, you can map each factor to an expected risk or behavioral rationale.

## 25. Kaggle and Experiment Architecture

The research documentation includes:

- `docs/research/KAGGLE_EXPERIMENT_ARCHITECTURE.md`
- `docs/research/KAGGLE_EXPERIMENT_RUNBOOK.md`

The architecture is config-driven:

- YAML configs define experiments.
- Notebooks remain thin.
- Versioned scripts do the work.
- Run artifacts are stored under `runs/{run_id}`.
- Manifests track dataset, config, environment, and run status.

Example artifacts include:

- `config_snapshot.yaml`
- `merged_config.yaml`
- `run_manifest.json`
- `dataset_manifest.json`
- `environment_manifest.json`
- `stage_status.json`
- `full_log.json`
- `window_events.jsonl`
- `summary.json`

Academic interpretation:

- This is a strong reproducibility story.
- It supports a methods section on experiment tracking.
- It also gives a clean way to present results without relying on local-only state.

## 26. Options System

The options system includes:

- `src/options/`
- `config/options_trading.yaml`
- `scripts/run_integrated_options_paper_engine.py`
- Upstox adapter logic.
- Strategy generator logic.
- Eligibility validation.
- Survival rules.
- Dashboard state contract.
- Strategy library definitions.

`src/options/README.md` describes an integrated options system with:

- Upstox integration.
- Regime detection.
- Strategy generation.
- Multi-layer risk controls.
- Tax-aware PnL.
- Dashboard support.
- Immutable audit trail.

Important documentation drift:

- The README contains many development-status checklist items that appear unchecked even while other parts of the system claim rich functionality.
- This should be treated as a current documentation inconsistency.

## 27. Options Strategy Generator

`src/options/enhanced_strategy_generator_v3.py` implements an options strategy generator. It handles:

- Imperfect option chains.
- Valid candidate generation.
- Premium fallback.
- Expiry selection.
- Strategy ordering by regime.

Strategy types visible in the inspected generator include:

- Iron condor.
- Iron butterfly.
- Calendar spread.
- Long straddle.
- Long strangle.
- Short strangle.
- Bull call spread.
- Bear put spread.

The wider strategy library includes many more strategies, such as:

- Protective put.
- Bear put spread.
- Ratio put spread.
- Collar.
- Delta hedge synthetic.
- Long call.
- Bull call spread.
- Call backspread.
- Naked put aggressive.
- Long straddle.
- Long strangle.

Audit interpretation:

- The library is broader than the generator surface.
- The report should distinguish "strategies defined in the library" from "strategies actively generated/traded."

## 28. Options Eligibility and Survival Rules

`src/options/trade_eligibility_validator.py` acts as a gatekeeper. It checks:

- IV rank thresholds.
- Liquidity.
- Bid-ask spread.
- Depth.
- Expiry hygiene.
- Event calendar risk.
- Vol-of-vol.
- Late-cycle protection.

`src/options/survival_rules_engine.py` acts as a safety layer. It checks:

- Weekly loss.
- Trauma state.
- Portfolio risk cap.
- Tax liquidity.
- Trade frequency.
- Time blocks.

Academic interpretation:

- This is a practical implementation of risk-first options trading.
- Options are not simply selected by expected payoff; they are filtered by survivability, liquidity, event risk, and portfolio constraints.

## 29. Options Configuration Issues

`config/options_trading.yaml` contains:

- Options capital base: 500,000 INR.
- Base risk: about 1 percent.
- Maximum risk: about 1.5 percent.
- Minimum risk: about 0.5 percent.
- Upstox rate limit: about 1 request per second.
- Allowed strategies list.
- Survival rules and portfolio risk caps.

Current audit issues:

- The event calendar contains stale 2024 dates.
- The config includes "Northstar V4 AlphaOS migration flags," which is naming drift inside a V3 system.
- The allowed strategy list is narrower than the full strategy library and generator surface.
- Older documentation may mention a 2 percent risk cap, while the current config shows a 4 percent portfolio risk cap in the survival section.
- Upstox token management remains partly manual through `.env.options`.

These issues are highly relevant to a report limitations section.

## 30. Upstox Adapter

`src/options/upstox_adapter.py` implements an Upstox API adapter. It includes:

- HTTP request logic.
- Bearer-token authentication.
- Rate limiting.
- Backoff/fail-fast behavior.
- Environment/config based token access.

Audit interpretation:

- This is a broker-integration surface, not pure research code.
- It increases operational realism.
- It also increases operational risk because broker tokens, live market connectivity, and endpoint changes must be managed carefully.

For the MSc report, you can describe this as an execution-adapter prototype or live-aware adapter, but avoid claiming live reliability unless you run and document a current live verification.

## 31. PnL, Ledger, NAV, and Accounting

The PnL and accounting layer includes:

- `src/pnl/ledger.py`
- `src/pnl/nav_calculator.py`
- `src/pnl/runtime_accounting_sync.py`

`src/pnl/ledger.py` defines an append-only master ledger. It includes books such as:

- Equity.
- Options.
- Cash.
- Shadow.

Ledger entry types include:

- Equity entries.
- Options entries.
- Cost entries.
- Cash entries.
- Correction entries.
- Shadow entries.

`src/pnl/nav_calculator.py` calculates:

- NAV.
- High-water mark.
- Drawdown.
- Net cash.
- Transaction costs.
- Total return.
- Annualized return.
- Volatility.
- Sharpe ratio.
- Sortino ratio.
- Calmar ratio.
- Win rate.
- Best and worst day.
- Cost drag.

Audit note:

- The NAV calculator docstring mentions compounding language, but the inspected implementation updates NAV using additive daily PnL. This may be correct given ledger design, but the wording should be clarified if used in a formal report.

`src/pnl/runtime_accounting_sync.py` integrates:

- Options trade ledger.
- PnL ledger.
- NAV.
- Reconciliation.
- Runtime store.
- State.
- Accounting reports.

Academic interpretation:

- This layer supports performance measurement and trading accountability.
- It is important for discussing realized vs paper performance and transaction cost realism.

## 32. Dashboard and Reporting

The canonical dashboard entrypoint is:

- `src/dashboard/app.py`

The dashboard renderer and support system include:

- `src/dashboard/integrated_dashboard.py`
- `src/dashboard/registry.py`
- `src/dashboard/data_contract.py`
- Dashboard loaders, layout, sections, and visual catalog.

The dashboard tabs include:

- Overview.
- Performance.
- Market.
- Sentiment.
- Portfolio.
- Risk.
- Options.
- Research.
- Alpha OS.

The data contract reads persisted artifacts such as:

- `data/state/unified_state.json`
- NAV data.
- Reconciliation data.
- PnL data.
- Market refresh status.
- Sentiment status.
- Alternative data status.
- Orchestrator status.
- Options runtime state.
- Options dashboard state.
- Options heartbeat.
- Valuation data.
- Portfolio data.
- Hub data.

The dashboard uses a live/static split and has periodic refresh fragments for some live areas.

Audit interpretation:

- The dashboard is a read-only monitoring and observability surface.
- It is useful for demonstrating system state in a project report.
- Legacy dashboard surfaces exist in the repository and should be avoided unless explicitly needed.

## 33. Current Testing Status

Current test setup is healthier than older audits implied. A `pytest.ini` now exists and configures:

- `testpaths = tests`
- Exclusion of generated/archive folders.
- Test file patterns.
- `addopts = -ra`

Current collection result:

```text
1995 tests collected in 11.28s
```

A targeted regression slice was run across alternative data, sentiment ingestion, no-synthetic-data checks, live shadow trading, shadow reality publisher, and market refresh fast path.

Result:

```text
15 passed, 2 failed in 3.43s
```

Passing areas in that slice included:

- Alternative data key contracts.
- Sentiment loader behavior.
- No-synthetic-data checks in selected paths.
- Daily shadow trader test coverage.

Failing tests:

1. `tests/live/test_shadow_reality_publisher.py::test_shadow_bridge_uses_fresh_published_shadow_snapshot`
   - Expected `authority.state.shadow_state.comparison_available is True`.
   - Actual value was `False`.
   - The state indicated `shadow_data_stale=False` but `comparison_available=False`.

2. `tests/integration/test_market_refresh_fast_path.py::test_stage_plan_ci_gate_quick_skips_research_branch`
   - Expected final stage name: `Canonical Datasets`.
   - Actual final stage name: `Market Data Freshness`.

Additional warning:

- Pytest emitted a `pytest_asyncio` deprecation warning about `asyncio_default_fixture_loop_scope` being unset.

Audit interpretation:

- Test discovery is in much better shape than older historical audits suggested.
- The current system is not fully green on the targeted slice.
- The two failures are integration/contract issues rather than trivial formatting issues.
- A full test run is still needed before claiming broad readiness.

## 34. Older Audit Findings That Are Now Partly Outdated

An older audit, `audit/COMPREHENSIVE_SYSTEM_ISSUES_AUDIT_2026-03-20.md`, reported serious issues such as:

- Missing pytest config.
- Test collection problems.
- Some missing modules in `src/operation` and `src/cohesion`.

Current inspection suggests at least some of these have changed:

- `pytest.ini` now exists.
- Test collection succeeds.
- Previously referenced modules such as `src/operation/crisis_validator.py`, `src/operation/performance_monitor.py`, `src/cohesion/integrated_data_pipeline.py`, `src/cohesion/performance_monitor.py`, and `src/macro_impact_engine/report_generator.py` exist now.

This means the older audit should not be copied into the MSc report as if it were fully current. Instead, use it as historical evidence of cleanup and evolution.

## 35. Older Audit Findings That Still Matter

Several older audit themes still appear relevant:

- Readiness checks can disagree.
- There are duplicate or overlapping config surfaces.
- Placeholder/mock/stub risk exists in active or legacy paths.
- Some documentation claims completion more strongly than current evidence supports.
- Options V3 integration is partial and operationally complex.
- Manual Upstox token rotation remains part of the workflow.
- Market brain real-data-only completeness should not be assumed everywhere without more testing.
- Reporting and PnL attribution may be less complete than high-level docs suggest.
- Repository hygiene and generated artifact sprawl remain real issues.

These should become a "Limitations and Future Improvements" section in the university report.

## 36. Formula and Calculation Audit Summary

The existing `audit/FORMULA_AND_CALCULATION_AUDIT_2026-03-21.md` scanned 1288 files and found 9423 calculation-bearing functions.

Highest-volume calculation categories in that audit were:

| Category | Functions |
|---|---:|
| scripts | 2612 |
| validation | 1205 |
| intelligence | 848 |
| dashboard | 739 |
| research | 430 |
| options | 385 |
| cohesion | 331 |
| volatility | 296 |
| operation | 288 |
| core | 273 |

Important dependency chain from that audit:

```text
ingestion freshness
  -> sentiment and alternative state
  -> market state
  -> governor capital structure
  -> scoring and allocation
  -> risk budgets and execution
  -> ledger and PnL
```

Valuation side-chain:

```text
financial statements and alternative credit/pledge data
  -> owner earnings, DCF, and forensic quality
  -> valuation posterior gap
  -> Kelly or allocation logic
```

Selected formula themes:

- Health score as weighted freshness and availability.
- Ratio normalization with clipping.
- Options Greeks aggregated by quantity.
- Premium at risk as risk cap minus remaining risk.
- Margin utilization as one minus remaining risk over risk cap.
- Sentiment z-score and momentum formulas.
- Alternative data freshness and regime formulas.
- Market state formulas for macro momentum, market health, volatility regime, opportunity density, risk-on probability, and allowed exposure.

Academic interpretation:

- The system is formula-heavy and multi-layered.
- It is important to explain only the formulas that matter to the report objective, rather than trying to reproduce all 9423 calculation-bearing functions.

## 37. Documentation Drift

Current documentation drift examples:

- `docs/operations/NORTHSTAR_OPERATIONAL_PLAYBOOK.md` still has a title referring to "Northstar V2 Operational Playbook."
- `config/options_trading.yaml` contains V4 AlphaOS migration naming inside a V3 system.
- `src/options/README.md` claims many options capabilities while also showing unchecked development checklist items.
- Older "complete" or "production-ready" docs should be treated as historical, not automatically current.
- `config/research_policy.yaml` is effectively empty except for a comment, while research docs discuss policy-driven governance.

Academic interpretation:

- This is normal in an actively evolving research system, but it must be disclosed.
- A clean report should use the newest verified architecture, not copy old completion language.

## 38. Worktree Hygiene and Artifact Risk

The worktree is extremely dirty. The `git status --short` output was very large, with modified, deleted, and untracked files. This matters because:

- It is hard to tell which changes are final.
- Generated files can pollute source review.
- Deleted older docs may still be referenced by memory or older reports.
- Untracked scripts may be experimental.
- A project report should not rely on uncommitted state unless it is deliberately describing the current local workspace.

Large generated areas include:

- `data/` at about 9.0 GB.
- `tmp/` at about 5.6 GB.
- Reports, snapshots, audit outputs, caches, and runtime state artifacts.

Recommendation:

- Before final university submission, create a clean "submission snapshot" branch or folder.
- Include only the report, selected code references, selected outputs, and reproducible commands.
- Do not submit the whole raw artifact warehouse unless required.

## 39. Security and Operational Risk

Potential operational risks:

- Manual access token update in `.env.options`.
- Live broker adapter surface in the same repo as research code.
- Runtime JSON state files as operational dependencies.
- Cron-based automation can silently fail if environment paths or credentials change.
- Stale event calendars can make options gating unreliable.
- Generated state can be mistaken for source truth.
- Large temp directories may hide obsolete artifacts.

For a finance report, frame this as:

- Operational risk.
- Model implementation risk.
- Data governance risk.
- Execution risk.
- Monitoring and controls.

Do not include secrets, access tokens, or live account identifiers in the university submission.

## 40. Current Risk Register

| Risk | Severity | Evidence | Recommended treatment |
|---|---|---|---|
| Research/execution boundary coupling | High | Research worker reads live options state | Separate research inputs from live runtime state |
| Dirty worktree | High | Very large `git status` output | Create clean submission snapshot |
| Stale options event calendar | High | 2024 event dates in options config | Update event calendar or disable event claims |
| Targeted test failures | Medium/High | 15 passed, 2 failed | Fix shadow comparison and CI stage ordering |
| Empty research policy config | Medium/High | `config/research_policy.yaml` comment-only | Make active policy explicit |
| Manual token rotation | Medium/High | README operational step | Treat as operational limitation |
| V3/V4 naming drift | Medium | Options config naming | Standardize naming |
| Strategy surface mismatch | Medium | Library broader than allowed config | Clarify active vs available strategies |
| Legacy dashboard/docs | Medium | Deprecated surfaces and old docs | Reference canonical dashboard only |
| Large generated artifacts | Medium | 9.0 GB data, 5.6 GB tmp | Separate artifacts from source |
| Async pytest warning | Low/Medium | pytest warning | Set fixture loop scope |
| Historical docs overclaim readiness | Medium | Older production-complete language | Use current audit caveats |

## 41. What You Can Defensibly Claim in the MSc Report

You can defensibly claim:

- The system implements a broad multi-layer quantitative finance architecture.
- It combines equities, options, macro, sentiment, alternative data, valuation, and factor signals.
- It has point-in-time and real-data-only design intent.
- It uses a unified state authority to govern state updates.
- It includes regime-aware portfolio governance.
- It includes options strategy selection and risk gating.
- It includes PnL, NAV, ledger, and dashboard surfaces.
- It includes research governance and experiment reproducibility architecture.
- It has a large test suite and currently collects 1995 tests.
- It is actively evolving and has identifiable limitations.

You should be cautious claiming:

- Fully production-ready status.
- Fully live-traded profitability.
- Fully real-data-only behavior everywhere.
- Fully automated broker execution without manual intervention.
- Fully clean separation between research and execution.
- Fully current event calendar.
- Fully green test suite.
- Fully audited security and compliance.

## 42. Suggested MSc Finance Report Structure

Recommended report chapters:

1. Introduction and motivation.
2. Research objective and finance problem statement.
3. Indian equity and options market context.
4. System architecture overview.
5. Data sources and point-in-time methodology.
6. Feature engineering: price, fundamental, macro, sentiment, alternative, and valuation features.
7. Research engine and experiment governance.
8. Market regime and unified state design.
9. Portfolio governor and capital allocation.
10. Options strategy and risk management layer.
11. PnL, NAV, and performance measurement.
12. Dashboard and monitoring.
13. Testing and validation evidence.
14. Limitations, risks, and boundary issues.
15. Future work.
16. Conclusion.
17. Appendix: code map, commands, selected configs, and formula summaries.

## 43. Suggested Project Abstract

Draft abstract you can adapt:

> This project presents Northstar V3, an integrated quantitative finance system for Indian equities and options. The system combines market data, fundamentals, macroeconomic indicators, alternative data, news sentiment, valuation features, and academic factors into a governed research and trading decision-support architecture. It includes point-in-time dataset construction, feature engineering, model research workflows, regime-aware market state estimation, portfolio capital governance, options strategy selection, PnL/NAV accounting, and dashboard-based monitoring. The project emphasizes practical investment-system design rather than isolated predictive modelling, with particular attention to data freshness, look-ahead bias, risk controls, turnover, drawdown, and operational governance. The audit also identifies current limitations, including research/execution boundary coupling, stale operational configs, documentation drift, and incomplete targeted test pass status.

## 44. Suggested Methodology Language

Use a methodology section like:

> The system follows a layered quantitative investment-process methodology. Raw market, fundamental, macro, sentiment, and alternative datasets are first normalized into canonical data stores. Point-in-time feature construction is then used to reduce look-ahead bias, particularly for fundamentals and delayed alternative data releases. Cross-sectional and time-series features feed the research and scoring stack, while market regime, sentiment, macro, and shock intelligence update a unified state model. Portfolio construction is governed through a regime-aware capital allocation layer that adjusts equity, options, and cash allocations based on caution signals and hard risk limits. Options strategies are filtered through liquidity, event, expiry, volatility, and survival rules before being reflected in runtime and accounting state. Performance is tracked through ledger, NAV, drawdown, and risk-adjusted metrics.

## 45. Suggested Limitations Language

Use a limitations section like:

> The current implementation should be interpreted as an evolving research and operational prototype rather than a final production-certified trading platform. Research and execution components currently coexist in the same repository, and some research flows read live options runtime artifacts. Certain configuration files show transitional naming or stale values, including an options event calendar with 2024 dates and V3/V4 naming drift. The repository also contains large generated artifacts and a highly dirty worktree, which complicates source-of-truth review. While test discovery currently succeeds with 1995 collected tests, a targeted regression run still produced two failures. Therefore, the system is best evaluated as a sophisticated architecture and implementation foundation, with clear future work around boundary separation, config cleanup, full test green status, and operational hardening.

## 46. Suggested Finance Concepts to Emphasize

Use these concepts in the report:

- Look-ahead bias.
- Survivorship bias.
- Point-in-time datasets.
- Cross-sectional alpha modelling.
- Factor investing.
- Alternative data.
- Sentiment overlays.
- Regime switching.
- Volatility regimes.
- Portfolio constraints.
- Drawdown management.
- Cash buffer management.
- Risk budgeting.
- Turnover control.
- Transaction cost drag.
- Liquidity constraints.
- Event risk.
- Options Greeks.
- Margin utilization.
- NAV.
- Sharpe ratio.
- Sortino ratio.
- Calmar ratio.
- Reconciliation.
- Research governance.
- Model promotion.
- Reproducibility.

## 47. Key File Map

| Area | Key files |
|---|---|
| Root overview | `README.md`, `ROOT_FOLDER_README.md` |
| System surface | `config/system_surface.yaml` |
| Operations guide | `docs/operations/WORKSPACE_GUIDE.md`, `docs/operations/NORTHSTAR_OPERATIONAL_PLAYBOOK.md` |
| Full runner | `scripts/run_complete_v3_system.py` |
| Trading orchestrator | `scripts/run_trading_day_orchestrator.py` |
| Canonical state sync | `scripts/runners/sync_canonical_state.py` |
| Unified state | `src/core/state.py` |
| State authority | `src/core/state_authority.py` |
| Market state | `src/state/market_state.py` |
| Portfolio governor | `src/portfolio/governor.py`, `config/portfolio_governor_config.yaml` |
| Scoring | `src/scoring/daily_scorer.py`, `src/scoring/northstar_model.py` |
| Research engine | `src/research/research_engine.py`, `scripts/run_research_worker.py` |
| Dataset manager | `src/research/dataset_manager.py` |
| Feature factory | `src/research/feature_factory.py` |
| Alternative data | `src/alternative_data/alternative_pipeline_runner.py`, `src/alternative_data/alternative_feature_block.py` |
| Sentiment | `src/sentiment/sentiment_state.py`, `src/sentiment/sentiment_regime.py` |
| News intelligence | `src/intelligence/news_brain/news_brain.py`, `src/intelligence/news_brain/shock_classifier.py` |
| Shock response | `src/intelligence/shock_engine/shock_response_engine.py` |
| Options config | `config/options_trading.yaml` |
| Options generator | `src/options/enhanced_strategy_generator_v3.py` |
| Options risk gates | `src/options/trade_eligibility_validator.py`, `src/options/survival_rules_engine.py` |
| Broker adapter | `src/options/upstox_adapter.py` |
| Options strategy library | `src/options/strategy_library/strategy_definitions.py` |
| Ledger and NAV | `src/pnl/ledger.py`, `src/pnl/nav_calculator.py`, `src/pnl/runtime_accounting_sync.py` |
| Dashboard | `src/dashboard/app.py`, `src/dashboard/integrated_dashboard.py`, `src/dashboard/registry.py`, `src/dashboard/data_contract.py` |
| Valuation | `src/valuation/valuation_feature_block.py` |
| Factors | `src/factors/factor_registry.py`, `src/factors/gap9_academic_factors.py` |
| PIT audit | `src/signal_engineering/pit_audit.py` |
| Kaggle experiments | `docs/research/KAGGLE_EXPERIMENT_ARCHITECTURE.md`, `docs/research/KAGGLE_EXPERIMENT_RUNBOOK.md` |
| Existing audits | `audit/COMPREHENSIVE_SYSTEM_ISSUES_AUDIT_2026-03-20.md`, `audit/FORMULA_AND_CALCULATION_AUDIT_2026-03-21.md`, `audit/V3_RESEARCH_ENGINE_BOUNDARY_AUDIT_2026-04-04.md` |

## 48. Reproducibility Commands Used for This Audit

Commands used or reflected during this audit included:

```bash
find src -path '*/__pycache__' -prune -o -type f -name '*.py' -print | wc -l
find scripts -path '*/__pycache__' -prune -o -type f -name '*.py' -print | wc -l
find tests -path '*/__pycache__' -prune -o -type f -name '*.py' -print | wc -l
du -sh src scripts tests data reports snapshots docs audit tmp
python3 -m pytest --collect-only -q tests
python3 -m pytest -q tests/alternative_data/test_alt_data_key_contracts.py tests/ingestion/test_sentiment_loader.py tests/intelligence/test_no_synthetic_data.py tests/live/test_daily_shadow_trader.py tests/live/test_shadow_reality_publisher.py tests/integration/test_market_refresh_fast_path.py
```

## 49. Practical Next Steps Before Final University Submission

Recommended cleanup before writing the final submitted report:

1. Create a clean report branch or snapshot.
2. Decide whether to frame Northstar V3 as an integrated platform or primarily as a research engine with execution prototype.
3. Update or explicitly caveat stale configs, especially the options event calendar.
4. Fix or document the two targeted test failures.
5. Make the active research policy explicit instead of relying on code defaults.
6. Separate generated artifacts from source evidence in the final submission.
7. Include only representative screenshots or outputs, not the full data warehouse.
8. Avoid including credentials or `.env` content.
9. Use current test evidence and avoid copying old "complete" claims without caveats.
10. Add an appendix with selected command outputs and key code paths.

## 50. Final Audit Conclusion

Northstar V3 is a substantial, ambitious, and technically rich quantitative finance system. Its strongest value for an MSc Finance submission is that it demonstrates a full investment-process architecture rather than only a predictive model. It covers data ingestion, PIT feature engineering, alternative data, sentiment, macro regime logic, unified state governance, portfolio allocation, options risk management, PnL accounting, dashboards, and research reproducibility.

The system also has real engineering and governance limitations. It currently blends research and live execution surfaces, contains stale or transitional configuration, has a very dirty worktree, and has targeted test failures. These limitations do not make the project weak. In fact, if presented honestly, they make the report stronger because they show awareness of real-world quant-system risks: data leakage, stale inputs, operational fragility, boundary design, and model governance.

The recommended academic framing is therefore:

> Northstar V3 is an evolving integrated quantitative investment research and trading decision-support platform. It demonstrates institutional-style design themes, especially around data discipline, regime-aware allocation, risk controls, and reproducibility, while also requiring further cleanup, boundary separation, and operational hardening before being represented as a fully production-grade trading system.
