# Northstar V3 Data Integrity and Synthetic Usage Audit Report

Date: 2026-02-04
Auditor: Cascade (agentic AI)
Scope: Full repository review of data provenance, synthetic/mock usage, and hardcoded calculations affecting dashboards, Market Brain, validation, and reporting.

---

## Executive Summary

- Multiple code paths can surface synthetic/mock data and hardcoded defaults to user-facing dashboards and internal components when real data is missing.
- The most critical issue is in `src/intelligence/market_brain/real_data_integrator.py`: the "real" RBI yield extraction currently generates synthetic yield data rather than parsing official RBI sources.
- Dashboards (including the Brain Window/unified dashboards) contain silent fallbacks that fabricate plausible values when source files are missing, risking false confidence in production environments.
- Sample data generation scripts write into the same `data/**` locations used by production dashboards, making it easy to confuse synthetic artifacts with real datasets without provenance tagging.
- A path configuration system exists to remove hardcoded paths, but migration scripts contain TODO placeholders and are not completed.

Risk level: Critical for real-data fidelity and investor-facing integrity unless guarded in production.

---

## Critical Findings (Must Fix)

- Real Data Integrator uses synthetic yields
  - File: `src/intelligence/market_brain/real_data_integrator.py`
  - Function: `extract_real_yield_data`
  - Issue: Despite the module header asserting "NO synthetic", it creates yield series via `np.random.uniform` for RBI yield curve and rates and saves to `data/macro/yields.csv`. This is synthetic, not parsed from RBI.
  - Impact: Any downstream using yields will be fed fabricated data.
  - Fix: Implement real parsing of RBI CSVs/APIs; remove random generation; add schema/quality checks and fail closed if inputs absent.

- Dashboards silently fabricate fallback data
  - File: `src/dashboard/snapshot_loader.py`
  - Methods: `_load_system_state_view`, `_load_risk_state_view`, `_load_engine_state_view`, `_load_validation_state_view`, `_load_intelligence_state_view`
  - Issue: On missing files or exceptions, returns hardcoded values (e.g., `allowed_exposure=0.65`, `current_drawdown=-0.03`, fixed engine metrics, "mock value" cache stats).
  - Impact: Constitutional cockpit can display synthetic views without provenance flag, creating false health/regime signals.
  - Fix: In production, fail closed (return None or explicit "DATA_UNAVAILABLE" with red banner). Add provenance banner and require a `NORTHSTAR_ALLOW_SYNTHETIC=true` env var only in dev/tests to enable fallbacks.

- Unified dashboard snapshot builder uses permissive defaults
  - File: `src/dashboard/data_loader.py`
  - Issue: On any load error, snapshot is created with generic defaults (e.g., `allowed_exposure: 50`, `market_vol: 15`, etc.) and `build_live_snapshot()` hardcodes values.
  - Impact: User-facing dashboards can show synthetic KPIs as if valid.
  - Fix: Same guard pattern: production mode must error if critical inputs are missing. Embed provenance metadata in snapshot and propagate to UI badges.

- Sample data generation pollutes production paths
  - File: `scripts/create_comprehensive_sample_data.py`
  - Issue: Writes numerous synthetic artifacts into `data/processed`, `data/backtests`, `data/validation` which are the same locations consumed by dashboards.
  - Impact: High risk of misinterpreting sample artifacts as real outputs.
  - Fix: Redirect all sample outputs to `data/sample/**` and add "provenance":"sample" markers; require explicit CLI flag. Do not write to canonical production file names.

---

## High-Severity Findings

- Mock data sources in cohesion layer (tests OK, prod risk if imported)
  - File: `src/cohesion/sample_data_sources.py`
  - Classes: `MockMarketDataSource`, `MockMacroDataSource`, `MockFundamentalDataSource`
  - Finding: Properly placed but ensure these are never referenced from production orchestrators. Current grep shows usage confined to tests.
  - Action: Add unit test asserting these classes are not imported by non-test modules.

- Migration script with TODO placeholders for hardcoded paths
  - File: `scripts/migrate_hardcoded_references.py`
  - Issue: Contains placeholder replacements like `# TODO: Replace ...` and string literals `get_report_path('system', filename)` that would be invalid if applied directly.
  - Impact: If used, could break code or leave hardcoded paths.
  - Action: Replace with real refactors using `src/cohesion/path_configuration.py` helpers. Remove or quarantine this script.

- Randomness and seeded behavior in dashboards/tests
  - Files: many sample/demo scripts and tests intentionally use randomness. Ensure none of these scripts are part of production automation or cron.
  - Action: Verify deployment manifests exclude demo/sample scripts.

---

## Medium-Severity Findings

- V3 Sentiment Loader neutral fallback
  - File: `src/intelligence/market_brain/v3_sentiment_loader.py`
  - Behavior: Returns neutral sentiment when artifacts missing (safe), but provenance not surfaced.
  - Action: Include `provenance: neutral_fallback` and timestamp; UI should badge this state.

- Data provenance not enforced
  - Issue: No repository-wide provenance schema for data files consumed by dashboards (e.g., `market_state.parquet`, `portfolio_weights.parquet`).
  - Action: Introduce small sidecar JSON files or embedded parquet metadata fields: `provenance`, `generator`, `data_source_version`, `created_by`, `environment`.

---

## Low-Severity Findings

- Terminology drift in documentation vs code
  - Some docs assert "no synthetic" while code paths do generate synthetic fallbacks. Align docs with actual behavior or, preferably, fix code and maintain guarantees.

---

## Concrete Evidence Snippets

- Synthetic RBI yields (must fix):
  - `src/intelligence/market_brain/real_data_integrator.py:206-227` uses `np.random.uniform` to fabricate 3M/6M/1Y/10Y and policy rates, saved as `data/macro/yields.csv`.

- Dashboard mock fallbacks:
  - `src/dashboard/snapshot_loader.py:407-423`, `472-487`, `525-538`, `579-597`, `634-648` hardcode plausible values when files missing.

- Sample data writing to production paths:
  - `scripts/create_comprehensive_sample_data.py` writes `data/processed/*`, `data/backtests/*`, `data/validation/*` without provenance or dev-only guard.

---

## Remediation Plan (Recommended Sequence)

1) Remove synthetic generation from Real Data Integrator
   - Implement RBI CSV parsing/pipelines; validate schemas; delete `np.random` code.
   - Add `--strict` mode default True: if files missing, raise with actionable guidance.

2) Fail closed in dashboards for production
   - Add env flag `NORTHSTAR_ALLOW_SYNTHETIC` (default false). When false, any fallback raises and shows a red "Data unavailable" panel rather than fabricated values.
   - Add provenance badges ("real", "sample", "fallback") across panels.

3) Quarantine sample data generation
   - Change outputs to `data/sample/**`; never write to canonical production filenames.
   - Embed provenance markers and watermarks; program dashboards to ignore `data/sample/**` unless in dev mode.

4) Enforce path configuration, finish migration
   - Replace remaining hardcoded paths via `src/cohesion/path_configuration.py`.
   - Remove/lock `scripts/migrate_hardcoded_references.py` after proper refactors.

5) Add automated safeguards
   - CI checks: grep ban for `np.random` in non-test ingestion paths and for fallback blocks without `ALLOW_SYNTHETIC` guards.
   - Unit tests asserting no mock classes are imported outside tests.
   - Data contract tests verifying required files exist and have provenance=real in production builds.

---

## Acceptance Criteria

- No code path in production mode can surface synthetic or fallback data without explicit red-badged warning and provenance metadata.
- `real_data_integrator` reads actual RBI/NSE sources; yields/parquet artifacts have non-zero completeness, correct schemas, and pass quality checks.
- Dashboards display provenance badges and error states rather than fabricated values when inputs missing.
- Sample/demo scripts cannot overwrite canonical production datasets.

---

## Verification Checklist

- [ ] Remove `np.random` yield generation from Real Data Integrator; add RBI parsing.
- [ ] Add `NORTHSTAR_ALLOW_SYNTHETIC` guard and provenance badges in snapshot_loader and data_loader fallbacks.
- [ ] Redirect sample outputs to `data/sample/**` and tag provenance.
- [ ] Implement CI grep rules and unit tests to block regressions.
- [ ] Validate dashboards against a clean environment to ensure no synthetic fallbacks appear.

---

## Appendix: Files Reviewed (sampled key ones)

- Documentation: `NORTHSTAR_V3_COMPLETE_SYSTEM_DOCUMENTATION.md`
- Dashboards: `src/dashboard/data_loader.py`, `src/dashboard/snapshot_loader.py`
- Market Brain: `src/intelligence/market_brain/real_data_integrator.py`, `v3_sentiment_loader.py`
- Cohesion/Config: `src/cohesion/path_configuration.py`, `cache_manager.py`
- Sample/Mocks: `scripts/create_comprehensive_sample_data.py`, `src/cohesion/sample_data_sources.py`
- Entry point: `run.py`

End of report.
