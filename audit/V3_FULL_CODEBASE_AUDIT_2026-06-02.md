# Northstar V3 Full Codebase Audit

Date: 2026-06-02
Workspace: `/Users/aryakghoshal/Downloads/northstar/northstar_v3`

## Executive Summary

Northstar V3 is a real, working, multi-surface quantitative research and trading workspace, but it is not a clean product repository. It contains a viable operational spine, active source code, CI/static guards, test coverage, and dashboard/runtime paths. It also contains very large local artifact trees, old launchers, historical gap-completion scripts, archived/deprecated code, generated data, two virtual environments, tmp experiment outputs, and thousands of dirty Git entries.

The short version:

- There is a connected core: `run.py`, `scripts/run_complete_v3_system.py`, `scripts/run_trading_day_orchestrator.py`, canonical dashboard `src/dashboard/app.py`, state authority, ingestion, sentiment, alternative data, research, portfolio, runtime, P&L, options, and risk modules.
- The full workspace is enormous: about `81,448` files, dominated by `data/`, `tmp/`, `.venv/`, and `venv/`.
- The public/active-ish source surface is much smaller but still large: about `4,723` non-generated files after excluding obvious local-only roots, including `src/` 1,516 files, `scripts/` 758, `tests/` 754, and `_cold_archive/` 936.
- The active Python surface parses cleanly in the static CI definition: `1,801` active Python files parsed successfully by `scripts/ci/check_active_python_parse.py`.
- Pytest collection succeeds: `1,898` tests collected.
- Focused smoke tests passed: `27 passed`, `14 warnings`.
- `run.py --mode health --verbose` currently fails because canonical market data is stale by about `354` hours. Broker token and ledger checks pass.
- The repo is currently very dirty: thousands of tracked deletions/modifications plus hundreds of untracked files. Any cleanup must be deliberate; do not assume `git status` noise is disposable without classifying it.
- There is dashboard split-brain: `run.py --mode dashboard` launches `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`, while the documented canonical dashboard and most launchers use `src/dashboard/app.py`.
- The scripts surface is overgrown: `617` Python scripts under `scripts/`, including `425` root-level Python scripts. The repo has a curated command surface, but the raw tree is not self-explanatory.

## Scope And Method

This audit intentionally looked at the whole workspace, then separated it into layers:

- Full filesystem inventory, including generated/local-only roots.
- Public/active-ish source inventory, excluding obvious runtime/deadweight roots.
- Git dirty-state classification.
- Canonical documentation and command-surface review.
- Static Python parsing and import/reachability analysis.
- Daily runner dry-run plan review.
- Dashboard, CI, config, tests, data/artifact, archive, `arya`, and `ns_uso` surface review.
- Focused validation commands.

Important limitation: static reachability is not the same as runtime truth. Many scripts call each other by subprocess, path strings, cron, shell launchers, and data artifacts. Where this audit says "not statically reached", read that as "not reached from the canonical roots in static import/path tracing", not guaranteed dead code.

## Full Workspace Size

Full tree scan, excluding `.git` only:

| Area | Files | Approx Size |
|---|---:|---:|
| `data/` | 41,120 | 9,212.78 MiB |
| `.venv/` | 13,154 | 458.13 MiB |
| `venv/` | 12,171 | 443.34 MiB |
| `tmp/` | 8,113 | 7,645.37 MiB |
| `src/` | 1,516 | 25.16 MiB |
| `_cold_archive/` | 936 | 13.82 MiB |
| `scripts/` | 758 | 10.55 MiB |
| `tests/` | 754 | 12.17 MiB |
| `.hypothesis/` | 682 | 0.59 MiB |
| `snapshots/` | 619 | 5.83 MiB |
| `reports/` | 612 | 17.82 MiB |
| `docs/` | 266 | 4.70 MiB |
| `logs/` | 221 | 39.35 MiB |

The workspace is not just a source repository. It is a source repo plus live/generated data lake, model/runtime state, reports, logs, caches, experiment outputs, and local Python environments.

Largest extension classes:

| Extension | Files | Approx Size |
|---|---:|---:|
| `.py` | 23,473 | 342.44 MiB |
| `.csv` | 15,812 | 3,994.54 MiB |
| `.json` | 14,493 | 2,782.16 MiB |
| `.parquet` | 10,119 | 5,565.22 MiB |
| `.pt` | 71 | 1,466.21 MiB |
| `.npz` | 63 | 994.76 MiB |

Most `.py` files in the full tree are not product code; many live inside `.venv/`, `venv/`, and `tmp/`.

## Active/Public Source Boundary

After excluding obvious local-only/generated roots such as `.git`, `.venv`, `venv`, `data`, `tmp`, `logs`, `snapshots`, `reports`, `.hypothesis`, `.pytest_cache`, `dist`, `catboost_info`, `truth_mode_runs`, and `models`, the tree still has about `4,723` files.

Top active-ish areas:

| Area | Files |
|---|---:|
| `src/` | 1,516 |
| `_cold_archive/` | 936 |
| `scripts/` | 758 |
| `tests/` | 754 |
| `docs/` | 266 |
| `arya/` | 91 |
| `notebooks/` | 67 |
| `.kiro/` | 57 |
| `config/` | 50 |
| `audit/` | 37 |
| `archive/` | 35 |

The active Python code, excluding venv/data/tmp/generated roots, is roughly:

| Area | Python Files |
|---|---:|
| `src/` | 870 |
| `scripts/` | 619 |
| `_cold_archive/` | 597 |
| `tests/` | 299 |
| `arya/` | 45 |

Formal CI active roots are narrower: `arya`, `scripts`, `src`, `tests`, and `run.py`, while skipping archive/generated/local roots. That active set parsed cleanly.

## Git State

The worktree is extremely dirty.

Observed status categories:

| Status | Count |
|---|---:|
| staged deletions `D ` | 1,928 |
| unstaged modifications ` M` | 446 |
| untracked `??` | 401 |
| unstaged deletions ` D` | 303 |
| staged additions `A ` | 12 |
| staged renames `R ` | 12 |
| staged modifications `M ` | 8 |

Top dirty buckets:

| Bucket | Main Status | Count | Meaning |
|---|---|---:|---|
| `backups/` | staged deletion | 690 | old backup tree removed from tracked surface |
| `reports/` | staged deletion | 677 | generated/historical reports removed from tracked surface |
| `snapshots/` | staged deletion | 519 | generated snapshots removed from tracked surface |
| `scripts/` | unstaged modified/untracked/deleted | 544+ | active script churn plus new scripts |
| `src/` | modified/untracked/deleted | 174+ | active source churn |
| `test_schemas/` | unstaged deletion | 142 | old root fixture/schema cleanup |
| `tests/` | modified/untracked/renamed/deleted | 100+ | active test churn and legacy relocation |
| `github_repo/` | unstaged deletion | 35 | old/deprecated public repo export removed |

Interpretation: the dirty state looks like an in-progress public/stabilization cleanup that removed generated deadweight and introduced new active surfaces. It should not be blindly reverted or blindly committed. It needs a staged cleanup/review plan.

## Canonical Surface According To Repo Docs

Multiple docs agree on the broad boundary:

- Product code: `src/`, `config/`, `tests/`
- Operator scripts: curated subset of `scripts/`
- Documentation: `docs/operations/`, `docs/research/`, `docs/system/`, `docs/dashboards/`
- Sentiment/export bridge: `ns_uso/`
- Generated/local-only: `data/`, `logs/`, `tmp/`, `reports/`, `snapshots/`, virtual environments
- Archived/deprecated: `_cold_archive/`, `archive/`, `backups/`, `tests/legacy/`

The canonical commands exposed by `scripts/ns.py`, `Makefile`, and `docs/operations/WORKSPACE_GUIDE.md` are:

- Daily full system: `python3 scripts/run_complete_v3_system.py`
- Unified launcher: `python3 scripts/northstar_v3_unified.py`
- Preopen checks: `python3 scripts/preopen_checks.py`
- Morning pipeline: `python3 scripts/run_morning_pipeline.py`
- Dashboard: `bash scripts/launch_dashboard.sh`
- EOD P&L: `python3 scripts/eod_rebalance_with_pnl.py`
- Governed promotion: `python3 scripts/promote_research_model.py --help`
- Gap validators: `scripts/verify_gap1_fixes.py`, `scripts/validate_gap2_complete.py`, `scripts/validate_gap3_robust_complete.py`, `scripts/test_gap4_robust.py`, `scripts/validate_gap5_complete.py`, `scripts/validate_gap6_complete.py`, `scripts/validate_gap7_complete.py`

There is also a local-operator routine in `ROOT_FOLDER_README.md`:

- Weekdays `08:50 IST`: `scripts/run_trading_day_orchestrator.py`
- Intraday loops: market loop, sentiment loop, options runtime, stale-loop recycling, runtime/accounting sync
- After `15:30 IST`: EOD prices, RBI update, market-state integration, alternative data refresh, artifact refresh, strict system check
- Saturday maintenance and daily backup scripts

This creates two valid views:

- Public canonical surface: `run.py`, `make`, CI, docs, `scripts/ns.py`.
- Actual local operator surface: cron/orchestrator and live trading scripts.

Both should be documented together, because an operator needs the latter and a public reviewer needs the former.

## Connected Operational Spine

The most connected daily spine is `scripts/run_complete_v3_system.py`.

Dry-run full plan on 2026-06-02 produced these stages:

1. Market Refresh
2. RBI Macro
3. Macro Features
4. Alternative Data
5. Screener Scrape
6. Screener Processing
7. Valuation Scores
8. News And Sentiment
9. Canonical Datasets
10. Market Data Freshness
11. Research Surface
12. Strategy Backtests
13. Strategy Beliefs
14. Strategy Regret
15. Strategy Tailwinds
16. Capital Allocator
17. Live Scores
18. Opportunity Surface
19. Portfolio Construction
20. Current Positions Sync
21. Runtime Book Sync
22. Runtime Accounting
23. Strategy Surface Sync
24. Canonical State Sync
25. Preopen Checks
26. Morning Pipeline
27. Gap 1 Proof
28. Gap 2 Proof
29. Gap 3 Proof
30. Gap 4 Proof
31. Gap 5 Proof
32. Gap 6 Proof
33. Gap 7 Proof

Quick mode is intentionally narrower:

1. Market Refresh
2. RBI Macro
3. Macro Features
4. Screener Processing
5. Valuation Scores
6. News And Sentiment
7. Canonical Datasets
8. Market Data Freshness

Connected modules in this spine include:

- `src.ingestion`
- `src.sentiment`
- `src.alternative_data`
- `src.core.state`
- `src.core.state_authority`
- `src.core.state_bridges`
- `src.live.shadow_reality_publisher`
- `src.portfolio.governor`
- `src.pnl`
- `src.runtime`
- `src.research`
- `src.dashboard.data_contract`
- `src.options`

This is the clearest answer to "what is connected": the complete runner is the main integration artery.

## Intraday/Trading-Day Spine

`scripts/run_trading_day_orchestrator.py` is the live scheduler/orchestrator surface. It manages:

- Market loop: `scripts/run_5min_market_updates.py`
- Sentiment loop: `scripts/run_ns_uso_sentiment_loop.py`
- Options loop: `scripts/run_integrated_options_paper_engine.py`
- No-edge and canonical sync commands
- Intraday intelligence cycles
- EOD pipeline
- Process restart and lock/status files under `data/options/live/`

It is more important for live operation than `run.py`, even though `run.py` is the public canonical entrypoint.

## Dashboard Surfaces

There are at least two major dashboard generations still present:

| Dashboard | Status |
|---|---|
| `src/dashboard/app.py` | Documented canonical modular dashboard |
| `src/dashboard/integrated_dashboard.py` | Renderer used by canonical app |
| `src/dashboard/registry.py` / `visual_catalog.py` | Visual registry and builders |
| `src/dashboard/data_contract.py` | Authoritative read contract over persisted artifacts |
| `src/dashboard/sections/` | Modular sections: Overview, Performance, Market, Sentiment, Portfolio, Risk, Options, Research, Alpha OS |
| `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py` | Older/huge restored integrated dashboard, still used by `run.py --mode dashboard` |
| `src/dashboard/comprehensive_dashboard.py`, `enhanced_dashboard.py`, `ultimate_dashboard_v2.py` | Secondary/legacy dashboard variants |

Important inconsistency:

- `src/dashboard/README.md` says `src/dashboard/app.py` is canonical and `northstar_v3_ultimate_integrated_dashboard.py` is deprecated.
- `scripts/launch_dashboard.sh`, root `launch_dashboard.sh`, `scripts/start_live_trading.sh`, and `scripts/run_live_trading_system.sh` use `src/dashboard/app.py`.
- `run.py --mode dashboard` still uses `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`.

Classification:

- Built/connected: `src/dashboard/app.py` path, data contract, registry, sections, launch scripts.
- Built but legacy/conflicting: `northstar_v3_ultimate_integrated_dashboard.py`.
- Partial/secondary: comprehensive/enhanced/ultimate V2 dashboard variants.

Recommended action: make `run.py` launch `src/dashboard/app.py` or explicitly document why `run.py` is intentionally pointed at the old dashboard.

## Major Source Areas

Static code stats for `src/`:

| Subdir | Python Files | Lines | Classes | Functions | Static Readiness |
|---|---:|---:|---:|---:|---|
| `validation` | 89 | 65,013 | 334 | 1,540 | huge, heavily tested, but many phase/task-era modules |
| `intelligence` | 92 | 46,403 | 181 | 1,165 | active, broad, mixed live/research/legacy |
| `dashboard` | 68 | 37,314 | 37 | 928 | active but split across old/new dashboards |
| `research` | 72 | 25,745 | 79 | 711 | active and broad, includes Kaggle/governed research |
| `options` | 49 | 18,455 | 107 | 526 | active, tests and live scripts connect it |
| `volatility` | 21 | 14,080 | 137 | 372 | built, older volatility/options stack, partly superseded by `src/options` |
| `core` | 20 | 13,346 | 89 | 413 | active state/event/authority spine |
| `cohesion` | 28 | 13,344 | 157 | 564 | active support layer, many tests/imports |
| `operation` | 18 | 11,317 | 76 | 348 | imported by many validation/task tests |
| `runtime` | 30 | 9,009 | 72 | 313 | active runtime/PRS layer |
| `ingestion` | 21 | 8,155 | 24 | 212 | active data ingestion |
| `portfolio` | 20 | 7,612 | 17 | 216 | active governor/portfolio layer |
| `valuation` | 31 | 5,686 | 30 | 155 | present, partially connected |
| `nlp` | 33 | 3,230 | 22 | 130 | active tests; connected to news/sentiment |
| `factors` | 28 | 3,308 | 18 | 108 | factor library and tests |
| `reporting` | 25 | 3,114 | 4 | 89 | built report sections, not central to daily run |
| `alpha_os` | 9 | 2,238 | 17 | 70 | active, covered by tests and promotion surface |
| `alternative_data` | 8 | 2,992 | 14 | 71 | active in daily run |
| `sentiment` | 11 | 2,647 | 10 | 59 | active in daily run |
| `risk` | 11 | 2,182 | 18 | 67 | active and CI-guarded |
| `execution` | 6 | 1,446 | 8 | 43 | active enough to be required by `run.py health` |

## Static Connectivity Summary

Starting from canonical roots, static import/path tracing found `421` reachable modules out of `1,542` code modules excluding tests and archives.

High-connectivity source areas:

- `src/core`: 16 of 20 reachable, 18 imported by code.
- `src/dashboard`: 38 of 68 reachable, 51 imported by code.
- `src/intelligence`: 42 of 92 reachable, 72 imported by code.
- `src/research`: 40 of 72 reachable, 64 imported by code.
- `src/options`: 24 of 49 reachable, 33 imported by code, 23 imported by tests.
- `src/risk`: 9 of 11 reachable, 10 imported by code.
- `src/runtime`: only 5 of 30 reached from canonical roots, but 29 imported by code. This indicates runtime is connected through internal import graph, scripts, and tests rather than a single top-level import path.
- `src/validation`: only 5 of 89 reached from canonical roots, but 67 imported by code and 49 by tests. This is a large validation/task-era surface, not the primary live spine.

Low or non-reached areas from canonical roots:

- `src/api/server.py`
- `src/scheduler/daily_update.py`
- much of `src/preprocessing`
- much of `src/processing`
- much of `src/macro_impact_engine`
- several `src/strategic` modules
- many old dashboard variants and panel files
- several old valuation test files under `src/valuation/tests`

These are not necessarily useless. They are just not clearly part of the current canonical live/daily path.

## Scripts Surface

The script catalog reports:

- Root Python scripts under `scripts/`: `425`
- Root shell scripts under `scripts/`: `34`
- Total Python scripts under `scripts/`: `617`

Script buckets:

| Bucket | Python Files | Interpretation |
|---|---:|---|
| root `scripts/` | 425 | too large; mixed active, historical, one-off, repair, validation, demo |
| `scripts/kaggle` | 100 | active research/Kaggle experiment surface |
| `scripts/runners` | 23 | connected runtime/state/accounting runner scripts |
| `scripts/ci` | 20 | active CI guardrails |
| `scripts/research` | 15 | research experiments/utilities |
| `scripts/cleanup` | 11 | cleanup/migration tooling |
| `scripts/launchers` | 8 | secondary launchers |

Categories observed in root `scripts/`:

- Audits, backfills, builders, checks, completion scripts, creators, debug scripts, demos, downloaders, execution runners, fetchers, fix-up scripts, generators, implementation scripts, integration scripts, launchers, monitors, scrapers, tests, validators, verification scripts.

Classification:

- Built/connected: curated command surface and scripts called by `run_complete_v3_system.py`, `run_trading_day_orchestrator.py`, `Makefile`, CI.
- Built but sprawling: Kaggle/research scripts, many validators, many gap-completion scripts.
- Likely stale/one-off: `fix_*`, `complete_*`, many `demo_*`, `test_*` scripts under root `scripts/`, old launchers.

Recommended action: keep the curated catalog, then move non-canonical one-offs under `scripts/archive/`, `scripts/debug/`, `scripts/analysis/`, or `_cold_archive/` after checking references.

## Tests And CI

Observed validation:

- `python3 -m py_compile run.py scripts/run_complete_v3_system.py scripts/preopen_checks.py scripts/run_morning_pipeline.py src/dashboard/app.py src/dashboard/northstar_v3_ultimate_integrated_dashboard.py` passed.
- `python3 -m pytest --collect-only -q` collected `1,898` tests successfully.
- Focused smoke suite passed: `27 passed`, `14 warnings`.

Focused smoke command:

```bash
python3 -m pytest -q \
  tests/options/test_dashboard_state_contract.py \
  src/core/tests/test_state_authority.py \
  tests/test_health_exit_codes.py \
  tests/test_dashboard_data_contract.py \
  tests/test_signal_loader_canonical_paths.py
```

CI workflow `v4-stabilization-ci.yml` contains meaningful gates:

- active Python parse
- zero-byte reachable module check
- secret scan
- local path scan
- tracked deadweight scan
- lazy import checks in risk/execution path
- risk clock injection
- risk policy immutability
- execution anti-bypass
- direct runtime mutation import guard
- dashboard chart registry contract
- options/risk test subset
- strict runtime gate
- drift detection
- alpha lab diagnostics
- reachability regression
- archive isolation

`v4-shadow-delta.yml` runs a scheduled/runtime delta gate.

Risks:

- `data/processed/test_count_baseline.json` reports `baseline_count: 1`, while collection found `1,898` tests. The health check passes because a baseline exists, not because it is meaningful.
- Full tests were not run in this audit, only collection and focused smoke tests.

## Health Status

`python3 run.py --mode status --verbose`:

- Strict mode: off
- CI gate mode: off
- Freeze active: false
- Freeze triggers still list `negative_sharpe`
- Dashboard file according to `run.py`: `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`

`python3 run.py --mode health --verbose`:

- Static integrity checks passed.
- Broker connectivity check passed because a token is resolvable locally.
- Ledger integrity passed; master ledger has capital seed entries.
- Code freeze baseline passed.
- Workspace guide staleness passed.
- Test count baseline passed, but the baseline itself is bad/stale.
- Overall failed because market data freshness failed: freshest canonical market artifact was about `353.9` hours old.

Operational classification:

- The code can parse and focused tests pass.
- The live system is not currently ready for trading decisions because market data is stale.

## Config Surface

`config/` is the runtime/operator config area. It includes:

- market configs: `config/markets/`
- operation configs: `config/operation/operation_config.yaml`, `config/operation_config.yaml`
- options configs: `config/options/`, `config/options_trading.yaml`, `config/stock_options_mapping*.yaml`
- runtime policies: `portfolio_governor_config.yaml`, `pnl_config.yaml`, `research_policy*.yaml`, `strategy_surface_policy.json`, `system_surface.yaml`
- ingestion/sentiment/NLP/valuation configs
- dashboard/logging/venue configs

`configs/` is research/experiment configuration:

- `configs/experiment_base.yaml`
- `configs/experiments/`
- `configs/feature_sets/`
- `configs/model_configs/`
- `configs/plan_2026_04_05/`
- regime configs

Risk:

- Both `config/` and `configs/` are active-ish but mean different things. New work should not add to both casually.
- `.DS_Store` exists under `config/` and `configs/`, but generated/deadweight checks should prevent tracking.

## Data And Artifact Surface

`data/` is a complete local runtime/data lake, not a source folder. Major branches include:

- `data/canonical/`: canonical alternative/fundamentals/macro/news/prices/reference/sentiment.
- `data/processed/`: processed market, macro, scores, sentiment, benchmark, regime, valuation, strategy, runtime.
- `data/options/`: live options state, historical option chains, caches, backtest reports.
- `data/runtime/`: runtime DBs, repair/quarantine/runs.
- `data/pnl/`: master ledger, NAV, reconciliations, accounting.
- `data/portfolio/`: portfolio state/history/logs.
- `data/state/`: unified state and state logs.
- `data/sentiment/`, `data/news/`, `data/nlp/`: text/sentiment surfaces.
- `data/research/`, `data/results/`, `data/backtests/`, `data/model_registry/`: research artifacts.
- `data/validation/`, `data/testing/`, `data/reports/`: validation outputs.

This data tree is central to actual operation, but it should not be treated as source. The audit confirms it is the dominant size source in the workspace.

## Research And Kaggle Surface

Research is substantial and real. Main components:

- `src/research/`: research engine, controller, dataset manager, feature factory, model adapters, training pipeline, run registry, alpha lab, alpha factory, meta research.
- `scripts/kaggle/`: 100 Python files across dated plans and experiments.
- root section scripts: `run_section_legacy_01_08.py`, `run_section_ratio_09_12.py`, `run_section_sector_13_16.py`, `run_section_regime_17_19.py`, `run_section_redemption_20_23.py`, `run_section_signal_24_25.py`, `run_section_verification_26_27.py`. These are each about 0.46 MiB and appear to be copied/generated experiment section runners.
- `configs/`, `notebooks/`, `northstar_ratio_campaign_fresh/`, `northstar_sector_regime_campaign_fresh/`.

Classification:

- Built/connected: governed research worker, promotion scripts, dataset/feature/model infrastructure, Kaggle plan scripts.
- Partial/noisy: multiple dated Kaggle plans and copied root section runners. They need a research index identifying the latest blessed path.

## Arya Surface

`arya/` is a separate local ML/LLM-style pipeline:

- data collection/cleaning/provenance
- tokeniser training
- transformer model
- training
- SFT and DPO
- inference
- eval gates
- `arya/northstar_bridge.py`
- docs and production source config

Tests under `tests/arya/` collect successfully. This appears actively developed but separate from the core Northstar trading spine. Treat it as a sidecar product unless explicitly integrated via the bridge.

Classification: built sidecar, not central live trading path.

## NS-USO Surface

`ns_uso/` contains:

- `config/v3_batch_sources.yaml`
- export artifacts under `ns_uso/exports/v3/`
- scripts: `produce_v3_exports.py`, `run_v3_batch_ingestion.py`, `run_v3_sentiment_cycle.py`

This is explicitly called canonical in `ROOT_FOLDER_README.md` and `WORKSPACE_GUIDE.md` for sentiment/export bridging.

Classification: built and connected to sentiment/intelligence workflows.

## Archives And Deprecated Roots

Archived/deprecated material exists in multiple places:

- `_cold_archive/`: large historical archive material.
- `archive/`: now small, mostly `gap_docs`.
- `backups/`: currently empty-ish locally but many tracked deletions indicate older backup trees were removed.
- `tests/legacy/`: old intelligence observer tests and reports.
- deprecated root references in docs: old `dashboard/`, `northstar/`, `system/` roots.

CI has an archive isolation check, and `run.py` explicitly checks that archive paths/modules are not imported.

Classification:

- `_cold_archive/`, `archive/`, `backups/`: not active product surfaces.
- `tests/legacy/`: quarantine, not default pytest collection.

## What Is Fully Built

These areas look materially built and connected:

- Core state and state authority: `src/core/state.py`, `src/core/state_authority.py`, state bridges.
- Daily complete runner: `scripts/run_complete_v3_system.py`.
- Trading-day orchestrator: `scripts/run_trading_day_orchestrator.py`.
- Preopen checks: `scripts/preopen_checks.py`.
- Morning scorer pipeline: `scripts/run_morning_pipeline.py`.
- Canonical dashboard app path: `src/dashboard/app.py`, `src/dashboard/integrated_dashboard.py`, `src/dashboard/data_contract.py`, registry/sections.
- Options runtime and tests: `src/options/`, options test suite, live options scripts.
- Risk policy/controller: `src/risk/`, CI checks.
- P&L and runtime accounting: `src/pnl/`, runtime sync/accounting scripts.
- Sentiment and NS-USO bridge: `src/sentiment/`, `src/intelligence/news_brain/`, `ns_uso/`.
- Alternative data and valuation cache paths used by complete runner.
- Research/Kaggle infrastructure, though it is sprawling.
- CI/stabilization guardrails.

## What Is Partially Built Or Ambiguous

These areas exist but have ambiguity, stale variants, or weak canonical ownership:

- Dashboard variants: old ultimate dashboard still wired in `run.py`.
- `src/validation/`: huge, test-heavy, task-era modules; not the main daily spine.
- `src/volatility/`: older volatility system overlaps with newer `src/options`.
- `src/macro_impact_engine` and `src/macro_transmission_engine`: built modules, examples, limited connection to daily spine.
- `src/strategic`, `src/manifold`, portions of `src/processing`, `src/preprocessing`: present, but not clearly canonical.
- `scripts/` root: too many one-off repair/demo/test/gap scripts.
- Research root section scripts: likely generated/current for a specific Kaggle campaign, but should be moved/indexed.
- `arya/`: built sidecar but not central to live trading unless the bridge is explicitly enabled.

## What Is Not Connected Or Likely Legacy

Static analysis found many files not reachable from canonical roots and not imported by active code/tests. Examples include:

- `src/api/server.py`
- `src/scheduler/daily_update.py`
- old dashboard variants/panels
- several `src/preprocessing/*` modules
- much of `src/processing/*`
- most `src/macro_impact_engine/*`
- several `src/strategic/*` modules
- parts of `src/valuation/*`
- test modules living inside `src/*/tests/`
- many root `scripts/fix_*`, `scripts/complete_*`, `scripts/demo_*`, and `scripts/test_*`

These should go into a formal "quarantine pending owner" list before deletion.

## Major Risks

1. **Dirty state is too large to reason about casually.**
   There are thousands of staged/unstaged changes. A cleanup commit could accidentally mix source changes, generated deletion, public-readiness work, and active feature work.

2. **Dashboard canonical path conflict.**
   `run.py` and dashboard docs disagree. This is the most obvious "what is connected?" mismatch.

3. **Market data stale.**
   Health fails because market data is stale by about `354` hours. The live system should be considered not trade-ready until refreshed.

4. **Scripts root is overgrown.**
   Operators cannot infer what matters from filenames. The script catalog helps, but the root is still a minefield.

5. **Generated/local data dominates workspace.**
   `data/` and `tmp/` together exceed 16 GiB. This makes scans, backups, and mental load expensive.

6. **Test baseline health check is misleading.**
   Health baseline says one test; actual collection says 1,898 tests.

7. **Credential/local secret surface exists locally.**
   Prior public readiness audit says `.env.options`, backups, `_cold_archive`, and `universe/northstar-key.pem` contain sensitive local material. This audit did not print or inspect secrets, but the risk remains.

8. **Multiple config namespaces.**
   `config/` and `configs/` are both meaningful. Without discipline, runtime and research config can drift.

9. **Archive material still physically present.**
   `_cold_archive/` is excluded from active CI, but local presence increases accidental upload/copy risk.

10. **Huge validation/task-era surface.**
    Many modules are "built" in the sense that they parse and test, but not necessarily in the sense of being part of today's live operating system.

## Recommended Cleanup Order

Do not start by deleting files. Start by establishing boundaries.

1. Freeze a branch or checkpoint before cleanup.
2. Fix the dashboard canonical mismatch: decide whether `run.py` should launch `src/dashboard/app.py`.
3. Refresh or deliberately mark stale market data so health status is honest.
4. Regenerate `data/processed/test_count_baseline.json` or remove that health check.
5. Split Git changes into buckets:
   - public hygiene docs/config/CI
   - active source changes
   - test changes
   - generated/artifact deletions
   - archive/deprecated-root removals
6. Create a script quarantine manifest:
   - canonical scripts
   - called-by-canonical scripts
   - CI scripts
   - research/Kaggle scripts
   - one-off historical scripts
7. Create a dashboard quarantine manifest:
   - canonical app modules
   - old dashboard variants
   - unused panels/tabs
8. Create a data retention policy:
   - required live state
   - required test fixtures
   - regenerable runtime artifacts
   - cold storage only
9. Move or document root section runners and dated Kaggle plans.
10. Only then remove or archive stale code.

## Current Validation Evidence

Commands run during this audit:

```bash
python3 scripts/ns.py
python3 scripts/ns.py catalog
python3 scripts/ns.py doctor
python3 scripts/ns.py gaps
python3 scripts/run_complete_v3_system.py --dry-run --date today
python3 scripts/run_complete_v3_system.py --dry-run --quick --date today
python3 run.py --mode status --verbose
python3 run.py --mode health --verbose
python3 -m py_compile run.py scripts/run_complete_v3_system.py scripts/preopen_checks.py scripts/run_morning_pipeline.py src/dashboard/app.py src/dashboard/northstar_v3_ultimate_integrated_dashboard.py
python3 -m pytest --collect-only -q
python3 -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py tests/test_health_exit_codes.py tests/test_dashboard_data_contract.py tests/test_signal_loader_canonical_paths.py
```

Results:

- Curated script surface printed successfully.
- Daily full and quick dry-run plans printed successfully.
- `run.py --mode status` succeeded.
- `run.py --mode health` failed only at runtime readiness because market data is stale.
- Active Python parse guard reported `1,801` active Python files parsed successfully.
- No machine-local absolute paths found in active public files by CI guard.
- No generated/archive/runtime deadweight tracked by CI guard.
- No obvious secrets found in tracked files by CI guard.
- Pytest collection: `1,898` tests collected.
- Focused smoke tests: `27 passed`, `14 warnings`.

## Bottom Line

Northstar V3 is not a failed or disconnected repo. It has a real operational core and meaningful safeguards. But the repository is currently carrying several historical layers at once: live trading system, research lab, dashboard generations, validation/task-era code, generated data lake, local runtime state, public-readiness cleanup, archives, and experiments.

The next work should not be "rewrite everything." It should be boundary-setting:

- one canonical live path,
- one canonical dashboard path,
- one canonical script catalog,
- one active source boundary,
- one archive policy,
- one data retention policy,
- and a staged Git cleanup that keeps active behavior separate from artifact removal.

