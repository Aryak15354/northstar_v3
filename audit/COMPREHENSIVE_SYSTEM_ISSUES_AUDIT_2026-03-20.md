# Comprehensive System Issues Audit

Date: 2026-03-20  
Repo: `northstar_v3`  
Audit type: repo-wide static and operational integrity review

## Purpose

This document is a comprehensive issue inventory for the current state of the system. The goal is not to explain how the system is supposed to work. The goal is to document what is currently preventing it from being trustworthy, maintainable, and consistently operable.

This pass focused on:

- repository structure and operator surface
- import graph and package integrity
- validation and test discovery
- active data contracts and column/schema mismatches
- configuration drift
- canonical entrypoint drift
- placeholder, mock, synthetic, and stub logic still present in active code
- repo hygiene and scale problems that make debugging harder

This is an evidence-based audit from the current workspace state on 2026-03-20. It is comprehensive for the issues observed in this pass, but it is not a proof that no other defects exist.

## Method Used

The review used a combination of file inspection, structural search, and executable validation surfaces. Commands run included:

- `make doctor`
- `python3 -m pytest --collect-only`
- `python3 -m pytest tests --collect-only`
- `python3 -m compileall -q src scripts tests run.py run_daily_v3.py run_complete_v3_system.py`
- `make gap-all`
- `python3 scripts/test_gap4_robust.py`
- `python3 scripts/validate_gap5_complete.py`
- `python3 scripts/validate_gap6_complete.py`
- `python3 scripts/validate_gap7_complete.py`
- `python3 scripts/verify_live_system.py --for-tomorrow`
- `python3 scripts/preopen_checks.py`
- `python3 run.py --mode health`
- parquet schema inspection for active sentiment and market-state artifacts
- targeted `rg`, `find`, `nl`, and repo-wide scans for duplicates, placeholders, and missing imports

## Repo Snapshot

`make doctor` reported:

- root Python scripts: 412
- Python scripts under `scripts/`: 483
- tracked `.hypothesis` files: 3516
- tracked snapshots: 519
- tracked reports: 677
- top git-noise buckets: `.hypothesis` 3454, `backups` 690, `scripts` 479, `reports` 234, `src` 186, `tests` 45

This matters because the repo is large enough that operational ambiguity is now a defect in itself. The current tree makes it too easy to use the wrong surface, inspect the wrong config, or trust a stale validator.

## Overall Assessment

The system is not currently in a trustworthy "single source of truth" state.

The core problems are not only bugs. The more serious problem is drift:

- docs, wrappers, validators, and runtime entrypoints are not aligned
- data files and consuming code disagree on schemas
- active tests fail during collection because modules were moved or deleted but imports were not updated
- readiness checks disagree with each other
- several "canonical" paths still contain placeholder or mock behavior

There are working components in the repo, but the system as a whole is not yet coherent enough to rely on status green lights at face value.

## Severity Guide

- `Critical`: directly blocks trust, execution readiness, or basic validation
- `High`: likely to produce wrong behavior or silent regressions
- `Medium`: maintainability and debugging hazards that will keep causing breakage
- `Low`: real cleanup items that are not first-order blockers

## Findings

### 1. Critical: test discovery and validation are not under control

Evidence:

- There is no `pytest.ini`, `pyproject.toml`, `tox.ini`, or `setup.cfg` in repo root.
- `python3 -m pytest --collect-only` reported `rootdir: /Users/aryakghoshal/Downloads` and collected `1963 items / 97 errors`.
- The same collection output showed `_cold_archive` content being collected as if it were active test code.
- `python3 -m pytest tests --collect-only` still reported `rootdir: /Users/aryakghoshal/Downloads` and collected `1649 items / 9 errors`.

Why this is a system issue:

- The absence of repo-local pytest config means test discovery is being driven by the parent directory instead of the repository.
- Archived material under `_cold_archive/` is not excluded from discovery, even though `docs/operations/WORKSPACE_GUIDE.md` says `_cold_archive/` should be treated as historical material.
- A broken test harness means green or red test signals are not reliable engineering signals.

Concrete active collection failures:

- `tests/test_macro_impact_engine.py` imports `src.macro_impact_engine`, which fails because `src/macro_impact_engine/__init__.py:42` imports non-existent `report_generator`.
- `tests/validation/test_system_integration_validation.py` fails because `src.cohesion.integrated_data_pipeline` is missing.
- `tests/validation/test_task11_performance_properties.py` fails because `src.cohesion.performance_monitor` is missing.
- `tests/validation/test_task13_operation_orchestration_properties.py` and `tests/validation/test_task15_system_integration_properties.py` fail because `src/operation/master_operation_controller.py:34` and `:37` import non-existent `crisis_validator` and `performance_monitor`.
- `tests/validation/test_task2_crisis_validator_properties.py` fails because `src.operation.crisis_validator` is missing.
- `tests/validation/test_task6_integrated_data_pipeline_*` fail because `src.cohesion.integrated_data_pipeline` is missing.
- `tests/validation/test_task6_performance_monitor_properties.py` fails because `operation.performance_monitor` is missing.

Impact:

- Current test status cannot be used as a release gate.
- Archived code is capable of poisoning current CI/debugging work.
- Missing-module regressions are hidden behind discovery noise.

Repair direction:

1. Add repo-local pytest configuration immediately.
2. Restrict discovery to `tests/`.
3. Explicitly exclude `_cold_archive`, `archive`, `data`, `reports`, and generated roots.
4. Fix the current 9 active collection errors before trusting any broader validation suite.

### 2. Critical: internal package structure is drifting faster than imports are being maintained

Evidence from active code:

- `src/operation/master_operation_controller.py:34` imports `.crisis_validator`, but `src/operation/crisis_validator.py` does not exist.
- `src/operation/master_operation_controller.py:37` imports `.performance_monitor`, but `src/operation/performance_monitor.py` does not exist.
- `src/macro_impact_engine/__init__.py:42` imports `.report_generator`, but `src/macro_impact_engine/report_generator.py` does not exist.
- `src/cohesion/dependency_bootstrap.py:81-108` imports top-level modules such as `src.configuration_manager`, `src.error_handler`, and `src.audit_logger`; several of these are not present at the referenced paths.
- `scripts/run_final_comprehensive_validation.py:37`, `:81`, and `:92` import `operation.crisis_validator` and `operation.performance_monitor`, which do not exist in the visible `src/operation` package.
- `scripts/run_final_comprehensive_validation.py:56-65` duplicates Task 3 as another `AlphaValidator` check instead of validating a distinct subsystem.

Visible package inventory:

- `find src/operation -maxdepth 1 -type f` shows only:
  `alpha_validator.py`, `backtest_orchestrator.py`, `live_operation_controller.py`, `master_operation_controller.py`, `report_manager.py`, `stress_testing_system.py`, `system_validation_suite.py`, `walk_forward_analysis_engine.py`, plus support files.
- The files `crisis_validator.py` and `performance_monitor.py` are absent from that package.

Why this is dangerous:

- This is not one isolated broken import. It is a package relocation problem.
- The codebase contains multiple generations of import style: `src.foo`, relative imports, and `sys.path` patching in scripts.
- Some scripts only work because they modify `sys.path` ad hoc. That hides package integrity issues until a different entrypoint or test runner is used.

Impact:

- Modules appear "implemented" in docs and validators but are not importable from current package locations.
- Refactors cannot be trusted because the repo lacks a stable package contract.

Repair direction:

1. Decide which package names are canonical.
2. Remove dead imports and dead wrappers.
3. Restore or delete ghost modules, but do not leave references to both states.
4. Stop relying on `sys.path.insert(...)` as a compatibility mechanism for production code.

### 3. Critical: validator expectations do not match the current runtime surface

#### 3.1 Gap 4 validator is testing a surface that no longer exists

Evidence:

- `scripts/run_live_engine.py:2` describes itself as a compatibility launcher.
- `scripts/run_live_engine.py:53-56` just `execv`s `scripts/run_integrated_options_paper_engine.py`.
- `scripts/test_gap4_robust.py:184-201` searches the text of `scripts/run_live_engine.py` for:
  - `_check_hot_reload_signals`
  - `_hot_load_strategy`
  - `_hot_unload_strategy`
  - `self._check_hot_reload_signals()`
- Running `python3 scripts/test_gap4_robust.py` fails on exactly those missing methods.

Observed result:

- Test 1 passed.
- Test 2 passed.
- Test 3 failed with `Missing required methods: ['_check_hot_reload_signals', '_hot_load_strategy', '_hot_unload_strategy']`.

Interpretation:

- The validator is asserting implementation details against an old file.
- The current runtime surface moved to `scripts/run_integrated_options_paper_engine.py`, but the validator was not rewritten.

#### 3.2 Gap 7 is "incomplete" only because active documentation is missing

Evidence:

- `python3 scripts/validate_gap7_complete.py` reported `50/51` checks passed.
- The only failure was missing `GAP7_STATE_CONSOLIDATION_COMPLETE.md`.
- The file exists only in archived/doc-storage locations, not the active root-level location the validator expects.

Interpretation:

- This is not a code failure. It is documentation and validator path drift.
- That still matters because the validator currently reports the gap as incomplete.

#### 3.3 Runtime version labeling is inconsistent

Evidence:

- `README.md:1` identifies the repo as `Northstar V3`.
- `run.py:2` says `Northstar V4 canonical runtime entrypoint`.
- `run.py:78` prints `NORTHSTAR V4 ENTRYPOINT`.
- `ROOT_FOLDER_README.md:12` still presents `run.py` as the canonical high-level entrypoint for the V3 workspace.

Impact:

- Operators and maintainers cannot tell which version label is authoritative.
- Validators and docs are increasingly tied to wrappers rather than the real implementation files.

Repair direction:

1. Rewrite validators against the actual canonical implementation surface.
2. Decide whether this workspace is V3-with-V4-runtime or simply V3.
3. Rename or re-document wrappers so they do not look like primary implementations.

### 4. Critical: operational readiness checks disagree, and one of them contains a likely false-fail rule

Evidence:

- `python3 scripts/verify_live_system.py --for-tomorrow` ended with `SYSTEM READY - Standby checks passed (with non-blocking warnings)`.
- `python3 scripts/preopen_checks.py` ended with `SUMMARY: FAIL`.
- `python3 run.py --mode health` returned a JSON payload with `overall_status: fail` because of `code_freeze`, while the process still exited successfully because strict mode was off.

Observed failure details from `preopen_checks.py`:

- `RUNTIME_ACCOUNTING_SANITY: rebalance.core.sync batch count 0 for trade_date=2026-03-20`
- `MARKET_DATA: Upstox access token is configured but rejected by broker API`

The token failure is a real operational blocker. The runtime-accounting failure looks like a logic defect in the check itself:

- `scripts/preopen_checks.py:187-191` defaults `trade_date_ist` to `datetime.now(INDIA_TZ).date()`.
- `scripts/preopen_checks.py:195-200` requires exactly one same-day `rebalance.core.sync` batch.
- `scripts/preopen_checks.py:711-737` treats failure of that condition as a hard pre-open failure.
- The check was run at `2026-03-20 04:10 IST`, which is before the Friday session started.

Interpretation:

- Requiring a same-day `rebalance.core.sync` batch before the trading day has begun is likely incorrect.
- This creates a false-red status that competes with the real-red status from the rejected broker token.

Secondary readiness inconsistency:

- `run.py --mode health` marks `code_freeze` as failed because 21 files differ from baseline.
- Since strict mode is off, the process exits without enforcing that failure.
- That means the JSON says "fail" while the shell-level behavior says "pass enough to continue".

Impact:

- The system currently emits conflicting health signals.
- Operators cannot easily distinguish "real blocker" from "check logic defect" from "non-strict warning masquerading as fail".

Repair direction:

1. Separate hard trade blockers from maintenance/status drift.
2. Make pre-open accounting sanity context-aware for pre-session runs.
3. Make `run.py --mode health` exit behavior match the reported severity, or rename the status levels.

### 5. Critical: sentiment data contracts are inconsistent across files, config, loaders, and dashboards

This is one of the most important structural issues in the repo.

#### 5.1 Actual on-disk schemas do not match consumer assumptions

Observed data files:

| File | Rows | Columns | Key columns |
| --- | ---: | ---: | --- |
| `data/sentiment/v3/company_sentiment_trends.parquet` | 300 | 15 | `timestamp`, `ticker`, `northstar_score`, `cohesive_alpha_score`, `sentiment_score`, `trend_score` |
| `data/processed/sentiment/ticker_sentiment_daily.parquet` | 1755 | 9 | `ticker`, `date`, `availability_date`, `sentiment_polarity`, `sentiment_conviction` |
| `data/canonical/sentiment/company_sentiment_daily.parquet` | 1755 | 9 | same 9-column daily sentiment schema |
| `data/processed/sentiment/market_sentiment_daily.parquet` | 108 | 7 | `date`, `availability_date`, `india_market_polarity`, `india_market_conviction` |
| `data/canonical/sentiment/market_sentiment_daily.parquet` | 108 | 7 | same 7-column market schema |

Critical mismatch:

- `data/sentiment/v3/company_sentiment_trends.parquet` does **not** contain `sentiment_polarity`.
- A direct check confirmed:
  - `has sentiment_polarity False`
  - `KeyError 'sentiment_polarity'` when calling `nlargest(..., 'sentiment_polarity')`

#### 5.2 Dashboards are hard-coded to the wrong column for the V3 company sentiment file

Evidence:

- `src/dashboard/comprehensive_dashboard.py:956-968` says it is using actual column `sentiment_polarity` from `company_sentiment_trends.parquet` and then calls `df.nlargest(20, 'sentiment_polarity')`.
- `src/dashboard/ultimate_dashboard_v2.py:869-880` does the same.

These statements are incorrect relative to the on-disk schema.

#### 5.3 The loader changes source contract at runtime depending on file presence

Evidence:

- `src/ingestion/sentiment_loader.py:117-125` prefers `data/sentiment/v3/company_sentiment_trends.parquet`, then falls back to processed sentiment.
- `src/ingestion/sentiment_loader.py:143-170` infers a date column and synthesizes `AvailabilityDate`.
- `src/ingestion/sentiment_loader.py:206-210` uses heuristic matching if `sentiment_score` is absent by taking the first column whose name contains `sentiment` or `score`.
- `src/ingestion/sentiment_loader.py:253-257` uses configured market sentiment path, but falls back to processed market sentiment if missing.
- `src/ingestion/sentiment_loader.py:283-287` synthesizes `sentiment_score` from either `polarity` or `india_market_polarity`.

Why this is risky:

- The same loader can return materially different schemas from different source families.
- A consumer can appear to work in one environment and fail in another depending on which file exists.
- The heuristics are convenient, but they weaken type/column contracts instead of enforcing them.

#### 5.4 Configs do not agree on which sentiment family is canonical

Evidence:

- `config/research_policy.yaml:141-142` points dataset sentiment to V3 files.
- `config/research_policy.yaml:310-311` points feature sentiment to canonical daily files.
- `config/research_policy_altdata.yaml:94-95` points to V3 files.
- `config/research_policy_transformer.yaml:49-50` points to processed daily files.
- `config/ingestion_config.yaml:46-48` points to V3 for company source family but processed for company/market access paths.
- `config/paths.yaml:76-78` mirrors the same mixed strategy.

Impact:

- There is no single authoritative sentiment contract in the system.
- Loader logic, dashboards, research pipelines, and config all permit different answers to "what is company sentiment data?"

Repair direction:

1. Choose exactly one canonical company sentiment schema.
2. Choose exactly one canonical market sentiment schema.
3. Add explicit schema validators for those artifacts.
4. Update dashboards and loaders to consume the chosen schema without heuristics where possible.

### 6. High: configuration is duplicated and materially divergent

#### 6.1 Two operation configs exist with different shapes

Evidence:

- `config/operation_config.yaml` contains nested sections such as `system`, `performance_thresholds`, `alerts`, `reporting`, `backtesting`, and `walk_forward`.
- `config/operation/operation_config.yaml` is shaped differently, with flattened top-level keys like `max_concurrent_operations`, `max_drawdown_threshold`, `reporting_config`, and `alert_settings`.
- `src/operation/operation_config_manager.py:47-50` defaults to `config/operation`.
- `src/operation/operation_config_manager.py:76` loads `config/operation/operation_config.yaml` by default.
- `scripts/check_v3_system_status.py:242` checks for `config/operation_config.yaml` instead.

Interpretation:

- Different parts of the system are treating different files as the "real" operation config.
- This is a classic split-brain configuration problem.

#### 6.2 Ingestion path families are mixed between raw and processed surfaces

Evidence:

- `config/ingestion_config.yaml:39-45` mixes processed CSV outputs and raw alternative-data directories for similar concepts.
- `config/paths.yaml:73-75` points `credit_ratings`, `bulk_deals`, and `promoter_pledges` to raw directories instead.

Impact:

- Different consumers may load different stages of the same dataset family and produce incompatible outputs.

Repair direction:

1. Keep one active operation config.
2. Archive or delete the other.
3. Define one canonical path per dataset stage and make naming explicit: `raw`, `processed`, `canonical`, or `v3_export`.

### 7. High: placeholder, mock, synthetic, and stub code remains in active execution surfaces

Repo-wide scan excluding archives, generated data, and local environments found:

- `TODO`: 27
- `placeholder`: 161
- `mock data`: 68
- `synthetic data`: 55
- `stub`: 20

Important examples:

- `src/dashboard/snapshot_loader.py:407-423`, `:472-487`, `:525-538`, `:579-597`, `:634-648` fall back to mock system, risk, engine, validation, and intelligence state data.
- `src/intelligence/build_dashboard_snapshot.py:172-200` generates "realistic mock performance data" when PnL looks flat.
- `src/volatility/market_data_feed.py:94-95` logs a warning and returns `100.0` mock stock prices because stock price fetch is not implemented.
- `src/cohesion/data_source_factory.py:1-90` is explicitly a stub implementation and returns empty DataFrames from `StubDataSource.read_data()`.
- `scripts/eod_rebalance_with_pnl.py:59-80` contains four placeholder loaders returning `{}` for current positions, EOD prices, options positions, and options EOD prices.

Why this is serious:

- Several of these files are not archived experiments. They sit on active-looking paths and are named as if they are production surfaces.
- Mock fallback logic in dashboards can make the system look healthy when it is actually missing data.
- Placeholder EOD loaders mean an operator can invoke a supposedly canonical flow that is not connected to real state.

Repair direction:

1. Separate demo/mock-only surfaces from production surfaces.
2. Remove mock fallbacks from any file advertised as canonical.
3. If a fallback must exist, make it impossible to confuse with real data by tagging the output and failing loudly in strict mode.

### 8. High: some "canonical" operator surfaces are wrappers or placeholders, not authoritative implementations

Evidence:

- `scripts/run_live_engine.py` is a compatibility wrapper, not the implementation.
- `run_complete_v3_system.py` at repo root is a wrapper delegating to `scripts/run_complete_v3_system.py`.
- `scripts/README.md:20-25` and `scripts/ns.py:17-24` present `scripts/eod_rebalance_with_pnl.py` as a canonical surface.
- `Makefile:90-91` also routes `make eod` to `scripts/eod_rebalance_with_pnl.py`.
- That file still uses placeholder functions for portfolio and options state loading.

Impact:

- A user can follow the documented path and still land on an incomplete implementation.
- Wrappers and compatibility shims are being documented as if they are system truth.

Repair direction:

1. Mark wrappers explicitly as wrappers in docs and command catalogs.
2. Only designate files as canonical if they are fully wired to real data and real control flow.

### 9. High: repo hygiene is actively degrading maintainability

Evidence:

- `.gitignore` includes `.venv/`, `data/`, `.hypothesis/`, and `_cold_archive/`.
- Despite that, `git ls-files '.hypothesis/**'` shows many tracked `.hypothesis` files.
- `make doctor` counted 3516 tracked `.hypothesis` files.
- `docs/operations/SCRIPT_CATALOG.md:25-27` says root Python scripts are 392 and scripts are 459.
- `make doctor` currently reports 412 and 483 instead.

Interpretation:

- Generated/stateful testing artifacts are already committed into the repository history.
- Published repo-shape documentation is stale.
- The scale of script sprawl has exceeded the navigation documents intended to simplify it.

Secondary hygiene problems:

- There are many local `__pycache__` directories across `src/`, `tests/`, and `scripts/`.
- The git worktree is extremely noisy.
- The script surface still contains many `fix_*`, `demo_*`, `complete_*`, and `validate_*` files in root-level areas.

Impact:

- Search quality degrades.
- Human review quality degrades.
- It becomes harder to tell "current product code" from "one-off repair script" from "archived idea still sitting in the main surface."

### 10. Medium: duplicate and parallel implementations are multiplying cognitive overhead

A repo-wide basename scan excluding archives, generated data, and local environments found 19 duplicate non-`__init__` Python basenames. High-signal duplicates include:

- `src/intelligence/temporal_guard.py`
- `src/cohesion/temporal_guard.py`
- `src/validation/temporal_guard.py`

- `src/intelligence/capital_allocator.py`
- `src/runtime/capital_allocator.py`

- `src/core/state.py`
- `src/runtime/state.py`

- `src/cohesion/unified_state_manager.py`
- `src/state/unified_state_manager.py`

- `src/options/strategy_generator.py`
- `src/volatility/strategy_generator.py`

- `src/operation/stress_testing_system.py`
- `src/intelligence/stress_testing_system.py`

- repo-root `run_complete_v3_system.py`
- `scripts/run_complete_v3_system.py`

Why this matters:

- Duplicate basenames are not automatically wrong, but in this repo they correlate strongly with parallel subsystem evolution and incomplete migration.
- It increases the chance of importing or editing the wrong module.

### 11. Medium: at least one active module is effectively broken or nonsensical, not merely incomplete

Evidence:

- `src/dashboard/consistent_data_manager.py:22-23` declares an empty `ConsistentDataManager`.
- `src/dashboard/consistent_data_manager.py:26-28` calls undefined `get_data_manager()`.
- `src/dashboard/consistent_data_manager.py:30` contains an obviously invalid/garbled `if __name__ == "__main__"` expression.
- `src/dashboard/consistent_data_manager.py:33` calls `manager.get_data_summary()` even though the class defines no such method.

Interpretation:

- This file is not a partially wired implementation. It is effectively dead or corrupted code.
- It should either be removed or rebuilt.

### 12. Medium: deprecation and compatibility warnings are already appearing under the current Python version

Evidence:

- The workspace is running Python `3.13.2`.
- `src/portfolio/governor.py:208` and `:661` use `datetime.utcnow()`.
- Gap 6 validation emitted deprecation warnings tied to those lines.

Impact:

- This is not today's main blocker, but it is a signal that compatibility debt is already surfacing on the interpreter version in use.

### 13. Medium: docs accurately describe the ideal working set, but not the actual state of the repo

Evidence:

- `docs/operations/WORKSPACE_GUIDE.md:7-23` correctly says `src/`, `scripts/`, `config/`, `docs/operations/`, and `tests/` are the working set and that `_cold_archive`, `archive`, `analysis_results`, `.hypothesis`, and `__pycache__` are secondary or generated.
- The repo reality does not match that guidance:
  - `_cold_archive` is still entering pytest discovery.
  - `.hypothesis` files are tracked.
  - script catalog counts are stale.
  - canonical entrypoint labels include wrappers and placeholders.

Interpretation:

- The guidance itself is mostly good.
- Enforcement and cleanup did not keep up with the guidance.

## Things That Are Actually Working or Partially Working

This repo is not uniformly broken. A few surfaces appear materially healthier than others:

- `python3 scripts/verify_live_system.py --for-tomorrow` completed successfully and produced a coherent standby-readiness summary.
- `scripts/test_gap4_robust.py` shows strategy registry bootstrap and strategy tailwinds integration both working.
- `scripts/validate_gap7_complete.py` shows the underlying Gap 7 code surface is largely present; the failure is documentation placement.
- The processed and canonical daily sentiment files exist and have internally coherent daily schemas.
- `scripts/preopen_checks.py` reported several real passes:
  - state integrity
  - ledger underlying attribution
  - WAL status
  - governance events
  - governor capital structure
  - alternative data presence
  - sentiment data presence
  - disk space
  - log activity

This is important because the system is recoverable. The problem is not absence of all functionality. The problem is lack of coherence across the functionality that does exist.

## Expanded Coverage: Build-State Map

The first version of this audit focused on hard breakages. This extension adds build-state classification.

Not everything in the repo is equally mature. The codebase currently contains four different categories of subsystem:

- `Built and active, but drifting`: production-shaped surfaces that work in some paths but are inconsistent across docs, schemas, wrappers, or validators.
- `Partially built`: real logic exists, but critical behavior is still placeholder, manual, or fallback-based.
- `Planned or legacy-stale`: presented as major architecture, but key modes or integrations were never completed.
- `Low-confidence / not deeply behavior-validated in this pass`: no immediate structural red flags found, but this audit did not fully validate runtime behavior there.

### Subsystem Classification

| Subsystem | Current state | Severity | Notes |
| --- | --- | --- | --- |
| `core/` + `state/` + `runtime/` | built but drifting | High | Gap 7 state consolidation is mostly present, but runtime/readiness surfaces still disagree. |
| `ingestion/` + sentiment loaders | built but drifting | Critical | Live schema/path switching makes contracts unstable. |
| `dashboard/` | built but drifting | High | Real-data-only claims are contradicted by mock fallbacks and column mismatches. |
| `options/` runtime | partially built | High | Core logic exists, but V3 integration and token rotation remain incomplete/manual. |
| `operation/` | partially built / broken imports | Critical | Package surface is missing modules required by active imports and tests. |
| `cohesion/` dependency layer | partially built / scaffolding-heavy | High | Interface and DI scaffolding exists, but concrete integrations are incomplete or stubbed. |
| `intelligence/market_brain/` | partially built | High | Real-data claims are overstated; synthetic fallback and not-yet-built pieces remain. |
| `pnl/` | partially built | Medium | Core ledger/NAV surfaces exist, but benchmark, reconciliation, and reporting details are incomplete. |
| `reporting/` | partially built | Medium | Most section/rendering code exists, but the institutional reporting layer is still skeletal. |
| `orchestrator/` | planned/legacy-stale | High | Marketed as master control plane, but import path is broken and major modes are not implemented. |
| `research/` | mostly built, shallowly audited | Medium | Adapters and pipelines exist; this pass found fewer structural issues, but no deep behavioral validation. |
| `valuation/` | mostly built, shallowly audited | Medium | Static scan was cleaner than many packages; still not deeply runtime-validated in this pass. |
| `alternative_data/`, `automation/`, `api/`, `live/`, `preprocessing/`, `processing/`, `scheduler/`, `strategic/`, `manifold/`, `execution/`, `macro_transmission_engine/` | low-confidence / not deeply behavior-validated | Unknown | No top-tier blockers surfaced in the shallow scan, but these areas were not audited as deeply as dashboard/options/operation/sentiment/state. |

### Static Heat Map by Package

A package-level scan of `src/` showed where incompleteness is concentrated:

- `validation/`: 89 files, `39` placeholder hits, `6` mock-data hits, `4` synthetic-data hits
- `intelligence/`: 72 files, `8` mock-data hits, `7` synthetic-data hits, `2` `NotImplementedError` sites
- `dashboard/`: 66 files, `10` placeholder hits, `7` mock-data hits, `4` synthetic-data hits
- `cohesion/`: 26 files, `10` stub hits, `63` pass-only functions, `3` pass-only classes
- `operation/`: 16 files, `10` placeholder hits, `3` mock-data hits
- `pnl/`: 11 files, `9` TODO hits

Interpretation:

- `validation`, `dashboard`, `intelligence`, `operation`, and `cohesion` carry the highest concentration of structural incompleteness.
- Not every pass-only function is a bug because some are abstract interfaces, but in this repo the pass/stub density is still a strong marker of unfinished subsystem boundaries.

## Additional Findings From Expanded Search

### 14. High: completion and production-readiness documents systematically overstate current system maturity

There are multiple docs that claim system completion, test completeness, or “real data only” behavior that does not match the current codebase.

Evidence:

- `docs/SYSTEM_VALIDATION_REPORT.md:373-377` says the Unified Volatility Engine is `READY FOR DEPLOYMENT` and that all phases are complete and all tests are passing.
- `docs/completion_reports/NORTHSTAR_V3_COMPLETE_SYSTEM_DOCUMENTATION.md:10-12` describes a complete 5-phase, 7-coordinator unified system.
- `src/options/V3_INTEGRATION_COMPLETE.md:1-5` says options integration is complete and first-class.
- `docs/dashboards/NORTHSTAR_V3_CANONICAL_DASHBOARD_GUIDE.md:59-63` says the dashboard uses real data only and should fail honestly instead of inventing values.
- `docs/market-brain/MARKET_BRAIN_ISSUES_RESOLVED.md:91-99` says all synthetic data was removed.

Contradicting code:

- `src/dashboard/snapshot_loader.py:407-423`, `:472-487`, `:525-538`, `:579-597`, and `:634-648` still inject mock dashboard state.
- `src/dashboard/data_loader.py:3-7`, `src/dashboard/real_data_loader.py:3-6`, and `src/dashboard/README.md:30-35` all make real-data-only claims that are not true for the broader dashboard surface.
- `src/intelligence/market_brain/m1_safe_regime_memory.py:109-143` still creates and persists synthetic market tensor data.
- `src/intelligence/market_brain/real_data_integrator.py:342-344` says real fundamentals extraction is not yet implemented.
- `src/options/upstox_adapter.py:265-299` still depends on manual local token rotation rather than a true refresh flow.

Impact:

- Documentation is currently a false-positive surface.
- Operators and maintainers can easily trust “complete” or “production-ready” claims that are no longer justified.

### 15. High: the master orchestrator / unified coordinator story is still partially aspirational

Evidence:

- `src/orchestrator/master_orchestrator.py:3-23` presents itself as the supreme controller for a unified 7-subsystem architecture.
- `src/orchestrator/master_orchestrator.py:26` imports `from cohesion.dependency_container import get_dependency_container`.
- A direct import smoke test failed: `src.orchestrator.master_orchestrator FAIL ModuleNotFoundError No module named 'cohesion'`.
- `src/orchestrator/master_orchestrator.py:575-598` says both live trading mode and backtesting mode are not yet implemented and will be implemented in future phases.
- `docs/phases/NORTHSTAR_V3_PHASE_1_COMPLETE.md:145-156` explicitly says the system works even when unified coordinators are not yet implemented.

Why this matters:

- This is not just a stale file name. The repo still contains an architectural story that was planned, documented, and partially scaffolded, but not actually completed.
- The doc set is internally contradictory: one set of documents says the unified coordinator future still lies ahead; another says the full multi-phase unified architecture is complete.

Classification:

- `planned/legacy-stale`, not production-trustworthy.

### 16. High: options V3 integration is only partially complete

Evidence:

- `src/options/V3_INTEGRATION_COMPLETE.md:1-5` says options V3 integration is complete.
- `src/options/options_risk_validator.py:38-47` attempts to import `github_repo.src.risk.risk_coordinator`.
- `github_repo/src/risk/risk_coordinator.py` is missing in this workspace.
- `src/options/options_risk_validator.py:52-104` falls back to local stand-in classes when that import is unavailable.
- `src/options/v3_risk_integration.py:33-40` also tries to import `github_repo.src.risk.risk_coordinator`.
- `src/options/v3_risk_integration.py:94-96` warns and returns `False` when the V3 RiskCoordinator is unavailable.
- `src/options/options_risk_validator.py` itself imports successfully, but that does not mean the real V3 coordinator integration exists.
- `tests/options/test_v3_integration.py:1-12` frames these as V3 integration tests, but the tested surface can still run in fallback mode because the external coordinator dependency is absent.

Operational gap:

- `src/options/upstox_adapter.py:265-299` exposes `refresh_token()`, but it is not a broker-side token-refresh implementation. It only reloads locally rotated credentials and raises if a new token is not manually provided.
- `docs/options/TOKEN_REFRESH_GUIDE.md:58-64` still describes the failure mode as a manual OAuth/token replacement process.

Classification:

- `partially built`.

Severity reasoning:

- High for production readiness because risk integration and broker auth are two of the most safety-critical options surfaces.

### 17. Medium: the market-brain “real data only” story is still incomplete

Evidence:

- `docs/market-brain/MARKET_BRAIN_ISSUES_RESOLVED.md:91-99` says all synthetic data was removed.
- `src/intelligence/market_brain/m1_safe_regime_memory.py:109-143` still generates and persists synthetic tensor data when the real tensor is missing.
- `src/intelligence/market_brain/real_data_integrator.py:206-249` still allows synthetic yields in development mode.
- `src/intelligence/market_brain/real_data_integrator.py:342-344` says real fundamentals extraction is not yet implemented.

Interpretation:

- The subsystem is not fake, but it is not fully real-data-only either.
- It should be classified as partially built, with the highest uncertainty around data-source completeness rather than around file existence.

### 18. Medium: the institutional reporting layer is still skeletal, but is wired into active intelligence code

Evidence:

- `src/reporting/institutional_reporting_system.py:6-14` defines `InstitutionalReportingSystem`, but `record_daily_data()` is just `pass` and `generate_monthly_report()` returns `{}`.
- `src/intelligence/institutional_alpha_engine.py:232` creates `self.institutional_reporter`.
- `src/intelligence/institutional_alpha_engine.py:798-800` calls `self.institutional_reporter.record_daily_data(...)`.
- `src/intelligence/institutional_alpha_engine.py:879-887` delegates monthly report generation to the same skeletal reporter.
- `src/intelligence/institutional_alpha_engine.py:791-792` also still injects mock crowding and mock decay values into reporting payloads.

Impact:

- The reporting layer exists as a shape, but not yet as a trustworthy institutional output surface.

Classification:

- `partially built`.

### 19. Medium: PnL and paper-fund analytics are still incomplete in benchmark and attribution dimensions

Evidence:

- `src/pnl/paper_fund.py:82-85` leaves benchmark return and information ratio as TODO-backed placeholders.
- `src/pnl/paper_fund.py:193-200` leaves benchmark comparison and execution-quality loading unfinished.
- `src/pnl/attribution.py:90-93` and `:320` include TODO-backed placeholder calculations.
- `src/pnl/reconciliation.py:197` and `:216` leave reconciliation checks partially implemented.
- `scripts/eod_rebalance_with_pnl.py:59-80` still depends on placeholder portfolio and price loaders.

Interpretation:

- Core accounting surfaces exist, but analytical completeness is not there yet.
- This is less severe than the import/schema issues, but it matters for trust in fund-style performance reporting and post-trade analysis.

Classification:

- `partially built`.

### 20. Medium: some strategy/governor support surfaces are still intentionally incomplete

Evidence:

- `src/portfolio/tuning.py:3-14` describes the tuning pipeline as supporting grid and random search, with Bayesian search still a stub and full historical reselection still deferred.

Interpretation:

- This is not a catastrophic defect, but it is a good example of a subsystem that should not be treated as feature-complete just because the file exists and runs.

Classification:

- `partially built`, lower urgency than operation/options/sentiment issues.

## Areas Still Not Deeply Researched

This audit has now gone wider than the first pass, but it still did not deeply validate every subsystem behaviorally.

The following areas were reviewed structurally, not exhaustively:

- `src/valuation/`
- `src/research/`
- `src/alternative_data/`
- `src/automation/`
- `src/api/`
- `src/live/`
- `src/preprocessing/`
- `src/processing/`
- `src/scheduler/`
- `src/strategic/`
- `src/manifold/`
- `src/execution/`
- `src/macro_transmission_engine/`

What "not deeply researched" means here:

- syntax and file presence were reviewed
- placeholder/stub/mock signals were scanned
- some import and test-surface checks were run
- no deep end-to-end behavioral validation was performed for those packages in this pass

That means:

- absence of a finding there does **not** mean the subsystem is healthy
- it means this report currently has lower confidence for those areas than for dashboard/options/operation/state/sentiment/cohesion/intelligence

## Repair Order Recommended

The right repair sequence is not "fix random bugs." The right sequence is to restore system coherence first.

### Phase 1: Re-establish a trustworthy validation surface

1. Add pytest configuration and stop archive discovery.
2. Fix the 9 active collection errors.
3. Decide which validators are still authoritative and which are stale.

### Phase 2: Collapse split-brain package and config surfaces

1. Resolve missing modules and dead imports in `src/operation`, `src/macro_impact_engine`, and `src/cohesion`.
2. Keep one operation config surface.
3. Keep one canonical runtime version label.

### Phase 3: Normalize data contracts

1. Pick one canonical company sentiment schema.
2. Pick one canonical market sentiment schema.
3. Update dashboards, loaders, and research configs to that contract.
4. Add artifact schema checks so this drift cannot recur silently.

### Phase 4: Remove fake-green behavior from active paths

1. Eliminate mock dashboard fallbacks from production surfaces.
2. Replace placeholder EOD loaders with real integrations or hard failure.
3. Remove stub data factories from any path that claims to be production-ready.

### Phase 5: Clean the repo so future debugging is tractable

1. Stop tracking `.hypothesis`.
2. regenerate and trust one script catalog only after cleanup
3. archive or remove obsolete fix/demo/completion scripts from the main surface
4. clean duplicate basenames where they represent competing subsystem generations

## Most Important Root Cause

The deepest problem is not one broken module or one failing check.

The deepest problem is that the repo currently has too many competing truths:

- more than one "canonical" entrypoint
- more than one operation config
- more than one sentiment schema family in live use
- more than one state/runtime/version story
- more than one layer of validation, with different assumptions

Until that is reduced, fixes will keep landing in the wrong layer and the system will keep feeling unpredictable.

## Bottom Line

The system contains useful working components, but it is still suffering from coherence failure.

If you try to "just run it" without first fixing the contract drift, you will keep getting exactly the pattern seen in this audit:

- one readiness script says green
- another says red
- a validator fails because it points at a wrapper
- a dashboard breaks because the file it reads does not have the column it expects
- tests fail before they even start because imports and package boundaries drifted

The immediate priority is to restore one authoritative shape for:

- test discovery
- package imports
- configs
- canonical entrypoints
- sentiment schemas

After that, the remaining issues become normal engineering work instead of system archaeology.
