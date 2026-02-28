# Northstar V3 Deep Audit (2026-02-28)

## Scope
- Objective: identify obsolete code/folders, broken integrations, and mathematical/risk logic defects.
- Method:
  - Static dependency and reachability analysis from runtime entrypoints.
  - Syntax validity scan across Python files.
  - Targeted test execution for options + validation integration surfaces.
  - Manual inspection of orchestrators, launchers, and risk/math modules.

## Executive Summary
- The repo has major drift between "declared architecture" and executable architecture.
- There are multiple critical risk/math inconsistencies in the options stack.
- A large volume of scripts are legacy or disconnected from active entrypoints.
- Core automation path appears to be:
  - `run_complete_v3_system.py`
  - `run_daily_v3.py`
  - `scripts/run_trading_day_orchestrator.py`
  - `scripts/run_integrated_options_paper_engine.py`
  - `scripts/runners/refresh_v3_artifacts.py`
  - `src/automation/northstar_scheduler.py`

## Coverage Checklist (Second-Pass Completeness)
- Completed:
  - Structure inventory (`~30k` files total, filtered source audit over `1135` `.py` files).
  - Syntax parse sweep for Python files.
  - Reachability/dependency analysis from active entrypoints.
  - Missing-path scan across `py/sh/md/yaml/json/toml`.
  - Runtime smoke for key entrypoints (`run.py`, `run_complete_v3_system.py`, `run_daily_v3.py`).
  - Targeted tests:
    - `tests/options` (full + failing module subset)
    - `tests/integration`
    - `tests/validation` collection health via broader run.
- Not fully exhaustive (remaining residual risk):
  - No full dynamic execution of every legacy script.
  - No network/live-API behavior verification (sandboxed/offline constraints).
  - No semantic correctness proof for every research/valuation model not reachable from active runtime graph.

---

## Critical Findings

### 1) Capital scaling math has unit-mixing bug in legacy constructor path
- Files:
  - `src/options/capital_scaling_engine.py`
  - `tests/options/test_capital_scaling.py`
- Evidence:
  - `_normalize_percent_points` converts `0.0025 -> 0.25` (percent-points), while legacy fixture passes base/max/min as decimals (`0.01`, `0.015`, `0.005`).
  - This causes `state.current_risk_pct` to jump directly to cap (`0.015`) on first milestone and to floor (`0.005`) on first drawdown.
- Test signal:
  - `tests/options/test_capital_scaling.py` failures:
    - `test_profit_scaling`
    - `test_drawdown_descaling`
    - `test_recovery_condition`
    - `test_get_summary`

### 2) Portfolio risk cap logic is inconsistent across modules
- Files:
  - `config/options_trading.yaml`
  - `src/options/survival_rules_engine.py`
  - `src/options/options_risk_validator.py`
  - `scripts/run_integrated_options_paper_engine.py`
- Evidence:
  - Config sets `portfolio_risk_cap_pct: 0.04` (4%).
  - `OptionsRiskValidator` hardcodes 2% (`0.02`), independent of config.
  - `SurvivalRulesEngine` check uses base capital by default.
  - Status summary uses current equity for cap display.
  - Integrated options runner computes dynamic cap from net equity and passes override.
- Impact:
  - Different risk cap values can apply depending on which validator/path is used.
  - Diagnostics can disagree with enforcement basis.

### 3) Aggressive mode defaults materially increase risk limits by default
- File:
  - `scripts/run_integrated_options_paper_engine.py`
- Evidence:
  - `aggressive=True` by default.
  - Weekly trade cap forced to effectively unbounded in aggressive mode.
  - `AGGRESSIVE_DEFAULT_PORTFOLIO_RISK_CAP_PCT = 0.10` (10%) when no CLI override is supplied.
- Impact:
  - Default runtime behavior can exceed intended conservative risk policy without explicit operator intent.

### 4) Event calendar risk guard is stale and effectively disabled
- Files:
  - `config/options_trading.yaml`
  - `src/options/trade_eligibility_validator.py`
- Evidence:
  - Event dates in config are from 2024.
  - Validator checks future dates relative to current time.
- Impact:
  - As of 2026-02-28, event-blocking protection does not activate for current RBI/CPI/WPI/budget windows.

---

## Integration Breaks (High)

### 5) Main README + `run.py` dashboard flow is broken
- Files:
  - `README.md`
  - `run.py`
  - `scripts/launchers/launch_dashboard.py`
  - `scripts/launchers/launch_brain_window.py`
- Evidence:
  - `README.md` and `run.py` reference root `launch_dashboard.py`, `launch_brain_window.py`, `check_system_status.py`.
  - Those root files are missing.
  - Launcher wrappers also delegate to missing root `launch_dashboard.py`.
- Impact:
  - Publicly documented and legacy-compatible launch paths fail.

### 6) `run_complete_v3_system.py` exposes dashboard modes that point to missing files
- File:
  - `run_complete_v3_system.py`
- Evidence:
  - Dashboard map includes:
    - `src/dashboard/northstar_v3_comprehensive_dashboard.py` (missing)
    - `src/dashboard/enhanced_v3_dashboard.py` (missing)
  - `brain` target exists.
- Impact:
  - `--dashboard unified` and `--dashboard professional` are broken modes.

### 7) Legacy ingestion coordinator references missing pipeline script
- File:
  - `src/ingestion/data_pipeline_coordinator.py`
- Evidence:
  - Calls `eod_options_pipeline.py`, which is missing.
- Impact:
  - This coordinator path is not executable end-to-end.

### 8) Cohesion layer import paths are stale
- Files:
  - `src/cohesion/health_monitor.py`
  - `src/cohesion/error_handler.py`
  - `src/cohesion/audit_logger.py`
  - `src/cohesion/dependency_bootstrap.py`
- Evidence:
  - Imports `src.service_interfaces` and `src.dependency_container` (missing).
  - Actual files exist under `src/cohesion/...`.
- Impact:
  - Cohesion/validation modules crash on import and are partially disconnected.

### 9) Validation architecture module imports non-existent class
- File:
  - `src/validation/v3_architecture_integration.py`
- Evidence:
  - Imports `Orchestrator` from `src.core.orchestrator`.
  - `src.core.orchestrator` defines `OrganOrchestrator`, not `Orchestrator`.
- Impact:
  - Module import fails; validation flow unusable.

---

## Test/Quality State

### 10) Validation test suite is structurally broken (collection stage)
- Command:
  - `python3 -m pytest -q tests/options tests/validation tests/integration --maxfail=40`
- Result:
  - 26 collection errors in validation tests before execution.
- Main causes:
  - Syntax errors (`unmatched ')'`) in many `tests/validation/*.py`.
  - Missing-module imports from stale cohesion paths.
  - Missing class imports (e.g., `Orchestrator`).

### 11) Options test suite has failing risk/math and contract checks
- Command:
  - `python3 -m pytest -q tests/options --maxfail=50`
- Result:
  - `9 failed, 170 passed, 7 errors`
- Key failures:
  - Capital scaling math (unit mismatch behavior).
  - Portfolio risk cap boundary behavior.
  - Risk summary cap inconsistency.
  - Liquidity depth expectation drift.
  - Ledger schema drift in tests vs implementation.

### 12) Syntax health: 32 Python files fail to parse
- Includes:
  - Many `tests/validation/*.py`.
  - Multiple scripts in `scripts/` with syntax defects.

### 13) Entry-point runtime smoke found additional hard failures
- Commands:
  - `python3 run.py --mode dashboard --dashboard brain`
  - `python3 run.py --mode update --quick`
  - `python3 run_complete_v3_system.py --dashboard-only --dashboard unified --port 8520`
- Findings:
  - `run.py --mode dashboard` fails immediately because `launch_dashboard.py` is missing.
  - `run.py --mode update` logs repeated memory serialization failures (`Timestamp` not JSON serializable), compatibility patch failure (`No module named 'cohesion'`), and risk-organ initialization failure (`UnifiedRiskCoordinator` undefined).
  - `run_complete_v3_system.py` marks dashboard launch as success even when Streamlit exits with file-not-found for missing dashboard file.

### 14) Reachable-path unresolved local imports remain
- Reachability analysis from active runtime entrypoints found:
  - `77` reachable modules.
  - `10` unresolved local-style imports in reachable modules.
- Notable unresolved imports:
  - `src/orchestrator/master_orchestrator.py` imports `cohesion.*`, `orchestrator.*`, `intelligence.*` (path-style drift).
  - `src/dashboard/v3_data_hub.py` imports `src.data.query_engine` (path present, but indicates split import conventions).
  - `src/intelligence/market_brain/brain_orchestrator.py` references `cohesion.state_file_manager` style.

### 15) Zero-byte Python files (silent placeholders) detected
- Count: `19` zero-byte `.py` files across active trees.
- Includes:
  - `src/options/backtest_engine.py`
  - `src/options/backtest_reporter.py`
  - `src/ingestion/rbi_cleaner.py`
  - `src/live/simple_shadow_trader.py`
  - `src/utils/helpers.py`
  - several scripts/tests placeholders
- Impact:
  - These can appear as implemented modules but contain no executable logic, increasing false confidence and integration drift.

### 16) Shell/ops scripts contain stale launch references
- Script scan found missing referenced targets in operational shell scripts, including:
  - `scripts/launch_dashboard.sh -> src/dashboard/northstar_command_bridge.py` (missing)
  - `scripts/launch_comprehensive_dashboard.sh -> src/dashboard/northstar_v3_comprehensive_dashboard.py` (missing)
  - `scripts/launch_ultimate_dashboard.sh -> src/dashboard/ultimate_northstar_dashboard.py` (missing)
  - `deployment/development/start_northstar.sh -> scripts/start_system_integration.py` (missing)
  - `deployment/development/start_northstar.sh -> scripts/start_monitoring.py` (missing)

### 17) Integration test surface is narrower than architecture claims
- `tests/integration` currently passes (`6 passed`), but tests are concentrated on sentiment bridge compatibility.
- They do not cover failing dashboard-launch paths or living-system update path failures above.

---

## Obsolete / Disconnected Footprint

## Reachability Snapshot (from primary runtime entrypoints)
- `src/` high-disconnection areas:
  - `src/research`: 39 files, 0 reachable
  - `src/operation`: 18 files, 0 reachable
  - `src/intelligence_observer`: 33 files, 0 reachable
  - `src/valuation`: 25 files, 1 reachable
  - `src/dashboard`: 31 files, 6 reachable
  - `src/validation`: 91 files, 18 reachable
- `scripts/` high-disconnection areas:
  - `scripts/(root)`: 300 files, 32 reachable
  - `scripts/cleanup`: 11 files, 0 reachable
  - `scripts/analysis`: 5 files, 0 reachable
  - `scripts/utilities`: 3 files, 0 reachable
  - `scripts/debug`: 4 files, 0 reachable

## Static dependency orphan counts
- `src` files with no inbound references and not on core reachable graph: `172`
- `scripts` files with no inbound references and not on core reachable graph: `196`

## Clearly archival
- `archive/obsolete_cleanup_20260211/`
- `archive/deprecated/*`
- Large generated/history stores (`snapshots/`, `logs/`, `backups/`) are operational artifacts, not active source.

---

## Properly Integrated (Relatively Strong)
- `run_complete_v3_system.py` primary quick/full pipeline, including artifact refresh and optional options cycle.
- `run_daily_v3.py` scheduler-safe wrapper around `run_complete_v3_system.py`.
- `scripts/run_trading_day_orchestrator.py` intraday process supervision + EOD pipeline trigger.
- `scripts/run_ns_uso_sentiment_loop.py` uses `ns_uso/scripts/run_v3_sentiment_cycle.py` (existing path).
- `scripts/runners/refresh_v3_artifacts.py` has explicit fallbacks when some scripts/artifacts are absent.

---

## Immediate Remediation Plan (Ordered)

### Phase A: Safety-Critical Math and Risk (first)
- Normalize capital scaling units consistently for both config and legacy constructor.
- Unify portfolio risk cap basis and source of truth across:
  - survival rules
  - options risk validator
  - integrated options runner
  - status summaries
- Change aggressive defaults to explicit opt-in (disable by default for production runs).
- Refresh event calendar to current/future dates and add stale-calendar guard.

### Phase B: Fix Broken Entrypoints and Runtime Contracts
- Repair dashboard launch chain (`run.py`, launcher wrappers, README commands).
- Remove/disable dashboard modes that map to missing files, or restore those files.
- Patch stale import paths in cohesion and validation modules.
- Resolve `Orchestrator` vs `OrganOrchestrator` naming mismatch.
- Fix false-positive dashboard launch success in `run_complete_v3_system.py` (verify child process health before marking success).
- Fix living-system risk wrapper initialization (`UnifiedRiskCoordinator` reference) and memory serialization (`Timestamp` in JSON payloads).

### Phase C: Rationalize Legacy Surface
- Mark deprecated scripts as `archive/` or `deprecated/` formally.
- Keep one canonical sentiment batch path (`ns_uso` vs `northstar`) and remove mock-based duplicate usage from active docs/tests.
- Split `scripts/` into:
  - production runners
  - one-off repair/migration tools
  - demos/tests

### Phase D: Test Recovery
- First restore syntax validity in `tests/validation`.
- Then restore import validity for cohesion/validation tests.
- Establish CI gate:
  - syntax check
  - import smoke test
  - options critical suite
  - core pipeline smoke (non-network mode)

---

## Artifacts Generated by This Audit
- `audit/static_dependency_audit_20260228.txt`
- `audit/reachability_by_subdir_20260228.txt`
- `audit/missing_file_references_20260228.txt`
- `audit/missing_script_literals_ast_20260228.txt`
- `audit/unresolved_local_imports_20260228.txt`
- `audit/missing_path_references_all_text_20260228.txt`
- `audit/duplicate_python_files_20260228.txt`
- `audit/missing_script_refs_in_shell_20260228.txt`
- `audit/zero_byte_python_files_20260228.txt`
