# Northstar V3 Research-Only Boundary Audit

Date: 2026-04-04  
Workspace: `northstar_v3`  
Reference plan: `northstar_execution_plan_v2.docx`

## Purpose

This audit answers one question:

If Northstar V3 is no longer supposed to be an execution platform, and should instead become a research engine that verifies, backtests, and walk-forwards signals for a separate options system, what in the current repo is:

- bloating that mission
- no longer worth keeping in V3
- structurally breaking down
- too entangled to trust without a cleanup boundary

This is a boundary audit, not a feature-completeness audit.

## Plan Alignment

The execution plan in `northstar_execution_plan_v2.docx` is very clear about the target split:

- V3 should be the research and signal-validation source.
- The execution platform should own broker adapters, OMS, mock/live mode, fills, portfolio state, alerts, and dashboarding.
- The signal bridge should consume V3 output, not turn V3 into the execution runtime itself.

In other words, the plan implies:

- `v3` owns historical data prep, features, model training, backtests, walk-forward validation, and signal exports.
- the options system owns Upstox, portfolio, positions, fills, ledgers, slippage, live/paper mode, and operator tooling.

The current repo does not honor that separation.

## Executive Summary

Northstar V3 is currently a combined:

- research engine
- live/paper execution surface
- options runtime
- portfolio and PnL system
- dashboard application
- operator workspace
- artifact warehouse
- archive dump

That is the core reason it feels dirty and bloated.

The main conclusion from this audit is:

1. Do not keep trying to make `v3` both a research engine and an options platform.
2. Freeze a clean research boundary and move execution concerns out of `v3`.
3. Aggressively cut dashboard, live-trading, portfolio, broker, and operational surfaces from the canonical `v3` contract.
4. Treat large generated artifact trees and historical launchers as workspace clutter, not product code.

If we follow the plan you described, V3 should become much smaller and much stricter:

- historical datasets
- feature engineering
- model training
- backtests
- walk-forward and leakage control
- signal export contracts
- selected realism and validation checks

Everything else should be either deleted, archived, or relocated to the separate options system.

## Repo Surface Snapshot

Observed on 2026-04-04:

- `git status --short | wc -l`: `2150` dirty paths
- `data/`: `8.9G`, `36,264` files
- `tmp/`: `182M`, `3,759` files
- `scripts/`: `578` files
- `src/`: `2,213` files
- `tests/`: `1,274` files
- `docs/`: `259` files
- `_cold_archive/`: `1,026` files
- `src/dashboard/`: `67` files
- top-level root launchers: `10`

Notable monoliths:

- `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`: `11,593` lines
- `scripts/run_integrated_options_paper_engine.py`: `6,905` lines
- `src/research/research_controller.py`: `2,714` lines
- `src/research/feature_factory.py`: `2,669` lines
- `src/portfolio/portfolio_governor.py`: `2,120` lines

This is not just "a lot of code". It is too much unrelated surface area for one repo to serve as a trustworthy research core.

## What Is Making V3 Bloated

### 1. The canonical identity of the repo is still live-ops first

The repo README still defines V3 as an "operational quantitative trading workspace" that combines live orchestration, hedge governance, options runtime, and research:

- `README.md:3-16`
- `ROOT_FOLDER_README.md:5-31`

The canonical commands are still operator and runtime commands:

- `scripts/verify_live_system.py`
- `scripts/start_live_trading.sh`
- `scripts/stop_live_trading.sh`
- `scripts/preopen_checks.py`

This is the opposite of a research-only contract.

### 2. V3 contains a full options execution stack that belongs in the new options system

The repo currently includes:

- broker adapter: `src/options/upstox_adapter.py`
- strategy generation and runtime state: `src/options/*.py`
- position and state management: `src/options/position_manager.py`, `src/options/state_recovery.py`
- trade ledger and PnL logic: `src/options/trade_ledger.py`, `src/options/tax_aware_pnl_tracker.py`
- risk gates and survival rules: `src/options/trade_eligibility_validator.py`, `src/options/survival_rules_engine.py`
- integrated runtime loop: `scripts/run_integrated_options_paper_engine.py`
- quick-start launcher: `START_OPTIONS_SYSTEM.sh`

This surface is exactly what your separate options system should own.

### 3. V3 also contains portfolio, runtime, risk, PnL, and live-trading packages beyond `src/options`

Execution-related code is not isolated to one directory. It is spread across:

- `src/pnl/`
- `src/risk/`
- `src/live/`
- `src/portfolio/`
- `src/runtime/`
- `deployment/`
- `scripts/start_live_trading.sh`
- `scripts/stop_live_trading.sh`

That spread makes the repo harder to prune because the execution stack leaked into multiple domains.

### 4. The dashboard surface is far too large for a research-only repo

Observed dashboard sprawl:

- `src/dashboard/`: `67` files
- `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`: `11,593` lines
- multiple root launchers:
  - `launch_dashboard.sh`
  - `launch_dashboard.py`
  - `launch_dashboard_with_data.sh`
  - `launch_enhanced_dashboard.sh`
  - `launch_new_dashboard.sh`
  - `launch_old_dashboard.sh`
  - `launch_ultimate_dashboard_v2.sh`
  - `launch_comprehensive_dashboard.sh`

This is not a thin research artifact viewer. It is an application surface with several generations of launch paths and dashboard variants.

### 5. The validation layer is carrying too many "institutional/final/enhanced/phase3" generations

`src/validation/` has `89` Python files, including:

- `enhanced_backtesting_engine.py`
- `enhanced_walk_forward_engine.py`
- `walk_forward_engine.py`
- `multi_timeline_walk_forward_engine.py`
- `institutional_hardening.py`
- `production_readiness_certificate.py`
- `final_system_validation_certification.py`
- `phase3_*`
- `shadow_*`

This is a classic symptom of accumulation without retirement. There are multiple generations of the same intent, and many of them are clearly tied to live-system hardening rather than pure research validation.

### 6. Artifact-heavy workspace roots are overwhelming the signal

Even if some of this is intentionally generated, the current workspace shape adds cognitive and operational bloat:

- `data/`
- `logs/`
- `reports/`
- `tmp/`
- `snapshots/`
- `_cold_archive/`
- `archive/`

For a research engine, these should be sharply separated into:

- canonical inputs
- canonical outputs
- disposable/generated caches
- archives outside the main development surface

Right now they all sit together in one working tree.

## Boundary Violations Against a Research-Only V3

### 1. Research still reads live options runtime state

The research worker currently reads:

- `data/options/live/options_runtime_state.json`
- `data/options/live/market_data_latest.json`

Evidence:

- `scripts/run_research_worker.py:175-198`

That means the "research" loop is still coupled to the live options runtime state model.

For a clean research engine, this should be inverted:

- research consumes canonical historical datasets and optional frozen execution observations
- it should not depend on the live options runtime JSON contract

### 2. Research controller still exports into execution/governor concepts

The research controller imports:

- `CapitalAllocatorBridge`
- `PortfolioGovernorBridge`

Evidence:

- `src/research/research_controller.py:19-20`
- `src/research/research_controller.py:49-50`

These bridges are signs that research outputs are still shaped around downstream live-governance machinery. That is acceptable only if the boundary is explicit and thin. Right now it is part of the core controller.

### 3. The main daily runner is still a mixed research + live orchestration surface

`scripts/run_complete_v3_system.py` imports:

- alternative data runner
- state authority and shadow bridge
- live shadow publishing
- portfolio governor
- sentiment regime logic

Evidence:

- `scripts/run_complete_v3_system.py:24-34`

That file is a mixed orchestration layer, not a research-only entrypoint.

## What Should Be Cut Out of V3

This section separates "archive now" from "move first, then delete".

### A. Move out of V3 into the separate options system

These are not research-engine responsibilities:

- `src/options/`
- `src/pnl/`
- `src/risk/`
- `src/live/`
- execution-facing parts of `src/portfolio/`
- execution-facing parts of `src/runtime/`
- `deployment/`
- `.env.options` driven operator flows
- `scripts/run_integrated_options_paper_engine.py`
- `scripts/start_live_trading.sh`
- `scripts/stop_live_trading.sh`
- `scripts/verify_live_system.py`
- `scripts/preopen_checks.py`
- `START_OPTIONS_SYSTEM.sh`
- `START_LIVE_SYSTEM.sh`

Why:

- they are execution concerns
- they increase coupling to live state and broker behavior
- they are where the clearest logic drift and broken behavior currently exist

### B. Archive or delete from V3 immediately once a research-only contract is accepted

These are high-noise, low-value for a research-first repo:

- root dashboard launchers:
  - `launch_comprehensive_dashboard.sh`
  - `launch_dashboard.py`
  - `launch_dashboard.sh`
  - `launch_dashboard_with_data.sh`
  - `launch_enhanced_dashboard.sh`
  - `launch_new_dashboard.sh`
  - `launch_old_dashboard.sh`
  - `launch_ultimate_dashboard_v2.sh`
- most of `src/dashboard/`
- dashboard repair scripts and dashboard-only utilities
- operator docs that only describe live-stack behavior
- old archive material that still lives inside the active repo surface
- large disposable `tmp/` outputs

If you keep any dashboard in V3 at all, it should be a small read-only research report viewer, not a live war-room UI.

### C. Shrink hard inside `src/validation/`

Keep only the research-relevant kernel:

- data integrity
- leakage/temporal discipline
- walk-forward
- statistical significance
- execution realism/cost-model validation
- reproducibility/provenance

Candidates to review for retention:

- `src/research/walk_forward_validator.py`
- `src/validation/data_integrity.py`
- `src/validation/statistical_significance_gates.py`
- `src/validation/execution_realism_model.py`
- `src/validation/temporal_guard.py`
- `src/validation/provenance_system.py`
- `src/validation/audit_grade_reproducibility.py`

Likely delete or archive from V3:

- `phase3_*`
- `shadow_*`
- `production_*`
- `institutional_*`
- `final_*`
- multi-generation "enhanced" variants that only exist because older variants were never retired

### D. Treat `ns_uso/` as conditional, not default

If `ns_uso` is still a research signal source, keep only:

- batch ingestion/export
- canonical artifact generation
- research-facing loaders

Do not let V3 keep any dashboard/live-system hooks solely for `ns_uso`.

## What Should Stay in V3

If V3 becomes a research engine, the keep-set should look roughly like this:

- `src/research/`
- `src/factors/`
- `src/valuation/`
- research-relevant parts of `src/ingestion/`
- canonical data loaders and query utilities:
  - `src/data/`
  - `src/ingestion/`
- research configs under `config/` and `configs/`
- selected research scripts:
  - `scripts/run_research_worker.py`
  - Kaggle/research batch runners
  - dataset builders
  - export pipelines that produce signal artifacts
- selected tests:
  - research tests
  - data-contract tests
  - walk-forward and integrity tests

These are the pieces that match your goal of using V3 to verify, backtest, and walk-forward signals.

## Concrete Breakdowns and Issues

### 1. Active syntax break in dashboard code

`python3 -m compileall -q src scripts tests` fails with a syntax error:

- `src/dashboard/enhanced_dashboard.py:286`

The `else:` is mis-indented relative to the `with cols[1]:` block:

- `src/dashboard/enhanced_dashboard.py:278-287`

That means at least part of the dashboard surface is not even syntactically healthy.

### 2. Options runtime logic is failing its own tests

Sample run:

- `python3 -m pytest tests/options -q --maxfail=12`

Observed result:

- `7 failed`
- `174 passed`
- `5 errors`

Highest-signal failures:

- capital scaling math is wrong
  - `tests/options/test_capital_scaling.py`
  - failure traces point to `src/options/capital_scaling_engine.py`
- liquidity depth rule does not behave as expected
  - `tests/options/test_eligibility_validator.py`
  - logic in `src/options/trade_eligibility_validator.py`
- portfolio risk cap behavior and reporting disagree
  - `tests/options/test_survival_properties.py`
  - `tests/options/test_survival_rules.py`
  - logic in `src/options/survival_rules_engine.py`

This is important because these are not cosmetic issues. They sit in the exact areas that should never remain half-trusted inside a live or paper execution layer:

- sizing
- trade eligibility
- kill-switch behavior

### 3. Capital scaling engine has unit normalization drift

Config uses decimal increments:

- `config/options_trading.yaml:71-79`

But legacy normalization converts small decimals into percent-points:

- `src/options/capital_scaling_engine.py:136-149`
- `src/options/capital_scaling_engine.py:157-166`

That is why test expectations around `0.0125` are ending up at `0.015`.

This is exactly the kind of hidden unit-mixing bug that makes an execution stack unsafe to keep embedded in V3.

### 4. Survival rules use inconsistent risk-cap bases

Risk-cap enforcement path:

- `src/options/survival_rules_engine.py:355-407`

Status-summary path:

- `src/options/survival_rules_engine.py:718-726`

The enforcement path defaults to `self.base_capital * portfolio_risk_cap_pct`, while the summary path reports `performance.current_equity * portfolio_risk_cap_pct`.

That mismatch shows up directly in test failures and is a real contract problem.

### 5. Manual Upstox tests are sitting inside the automated suite

`tests/options/test_upstox_adapter_manual.py` explicitly says:

- "This is NOT an automated test - it requires live API access."

Evidence:

- `tests/options/test_upstox_adapter_manual.py:1-6`

But it is still named like a normal pytest file and produces fixture/setup errors under `pytest`.

That is a hygiene failure in the test surface and another sign that execution concerns were never cleanly separated from research-safe automation.

### 6. Options config is stale in live-sensitive places

Examples:

- Upstox rate limit is set to `1` request/sec:
  - `config/options_trading.yaml:17`
- event calendar is still hard-coded to `2024` dates:
  - `config/options_trading.yaml:139-186`

Even if the options stack were staying here, this would need immediate repair. Since the options stack is moving out, it is better treated as evidence that V3 should stop owning this live config altogether.

### 7. CI/integration drift still exists in the canonical runner

Sample run:

- `python3 -m pytest tests/integration -q --maxfail=12`

Observed result:

- `1 failed`
- `11 passed`

Failure:

- `tests/integration/test_market_refresh_fast_path.py::test_stage_plan_ci_gate_quick_skips_research_branch`

Expectation:

- last stage should be `"Canonical Datasets"`

Actual stage order:

- last stage is `"Market Data Freshness"`

Evidence:

- `tests/integration/test_market_refresh_fast_path.py:81-110`
- `scripts/run_complete_v3_system.py:1626-1637`

This is not a catastrophic failure, but it shows the canonical orchestration surface still drifts against its own tests.

## Why the Current Dashboard and Live Surface Are Not Worth Preserving in V3

The dashboard/live surface is expensive to keep for four reasons:

1. It is huge.
2. It has multiple generations of launchers and implementations.
3. It already contains syntax/runtime breakage.
4. It does not belong to the target architecture in your execution plan.

The strongest evidence is not just the size of `src/dashboard/northstar_v3_ultimate_integrated_dashboard.py`. It is that live operator scripts still explicitly refer to it:

- `scripts/start_live_trading.sh:67`
- `scripts/stop_live_trading.sh:32`
- `scripts/launch_northstar_v3_ultimate_integrated_dashboard_fixed.py:39`

That means the dashboard is part of the current operational identity of V3, not an optional research report layer.

## Recommended Target State for V3

### V3 should own

- historical canonical datasets
- feature generation
- factor and valuation research
- model training and selection
- backtests
- walk-forward validation
- leakage guards
- realism checks for research assumptions
- signal export artifacts
- signal-quality and provenance reports

### V3 should not own

- broker adapters
- market-hours execution loops
- OMS logic
- paper/live mode switching
- positions, ledgers, and fills
- production alerts
- runtime portfolio state
- live dashboards
- cron/operator stack for market sessions

## Recommended Cleanup Sequence

### Phase 1. Freeze the boundary

- Rewrite `README.md` and `ROOT_FOLDER_README.md` so V3 is explicitly a research engine.
- Define the output contract V3 will produce for the new options system:
  - signal parquet/json
  - metadata/version hash
  - backtest and walk-forward report bundle

### Phase 2. Relocate execution code before deletion

- Move `src/options/`, `src/pnl/`, `src/risk/`, `src/live/`, and execution-facing runtime/portfolio code to the separate options repo.
- Move live operator scripts with them.
- Move live config and `.env.options` behavior with them.

### Phase 3. Shrink V3 in place

- remove root launchers
- remove most dashboard code
- archive or delete live-system docs
- reduce `src/validation/` to the research-validation kernel

### Phase 4. Clean workspace clutter

- move or purge disposable `tmp/`
- isolate or remove old archive surfaces from the active repo
- stop treating generated data/log/report trees as part of the product surface

### Phase 5. Rebuild test ownership

- keep research/data/integrity tests in V3
- move options execution tests to the options system
- mark any real-network/manual tests so they do not run in automated CI

## Bottom Line

V3 is bloated because it still thinks it is the whole trading company.

Your plan says it should not be.

If you want V3 to become a clean research engine, the highest-value move is not incremental cleanup inside the current architecture. The highest-value move is to:

- declare a strict research-only boundary
- move execution responsibilities out
- delete the dashboard/live/operator baggage from the canonical V3 surface
- keep only the historical data, research, backtest, walk-forward, and signal-export core

That will give you a repo that is much easier to trust, test, and evolve.

## Suggested Immediate Delete/Move Decision List

### Move to the new options system

- `src/options/`
- `src/pnl/`
- `src/risk/`
- `src/live/`
- execution-facing pieces of `src/portfolio/`
- execution-facing pieces of `src/runtime/`
- `deployment/`
- `scripts/run_integrated_options_paper_engine.py`
- `scripts/start_live_trading.sh`
- `scripts/stop_live_trading.sh`
- `scripts/verify_live_system.py`
- `scripts/preopen_checks.py`
- `START_OPTIONS_SYSTEM.sh`
- `START_LIVE_SYSTEM.sh`

### Archive/delete from V3

- root `launch_*` files
- most of `src/dashboard/`
- dashboard repair/fix scripts
- live-only operational docs
- stale archive material in active paths
- large disposable `tmp/` outputs

### Keep in V3

- `src/research/`
- `src/factors/`
- `src/valuation/`
- research-relevant ingestion/data/query layers
- research configs
- research batch/export scripts
- research/data/integrity tests
- a trimmed validation kernel
