# Workspace Guide

This repo is much larger than the surface you need to touch day to day.

## Canonical Surface

Use these areas as the primary working set:

- `src/`: authoritative product code
- `scripts/`: operational entrypoints, validators, and maintenance tools
- `config/`: runtime and research configuration
- `docs/operations/`: runbooks and repo guidance
- `tests/`: repo-level tests
- `ns_uso/`: canonical NS-USO sentiment/export surface

Treat these as generated or secondary unless you are debugging them directly:

- `data/`: runtime artifacts, caches, derived datasets
- `reports/`: generated reports and validations
- `snapshots/`: saved state snapshots
- `_cold_archive/`: historical archive material
- `archive/`: deprecated or archived source material
- `data/results/`, `truth_mode_runs/`: generated analysis and research outputs
- `.hypothesis/`, `.venv/`, `__pycache__/`: local tool/cache noise

Treat these roots as deprecated or quarantined:

- `dashboard/`: deprecated root; use `src/dashboard/app.py`
- `northstar/`: older parallel NS-USO surface; use `ns_uso/`
- `system/`: retired root; moved to `scripts/` and `data/state/`

## Start Here

If the tree feels overwhelming, start with:

- `make help`
- `make doctor`
- `make find q=sentiment`
- `python3 scripts/ns.py`
- `python3 scripts/ns.py catalog`
- `python3 scripts/ns.py gaps`

These give you the curated surface instead of the raw file list.

## Canonical Commands

These are the recommended entrypoints for current work:

- Daily full system: `python3 scripts/run_complete_v3_system.py`
- Morning readiness: `python3 scripts/preopen_checks.py`
- Morning pipeline: `python3 scripts/run_morning_pipeline.py`
- Dashboard: `bash scripts/launch_dashboard.sh`
- Unified launcher: `python3 scripts/northstar_v3_unified.py`
- EOD with unified P&L: `python3 scripts/eod_rebalance_with_pnl.py`
- Governed promotion: `python3 scripts/promote_research_model.py --help`

Compatibility wrappers that should not accumulate new logic:

- `python3 scripts/run_live_engine.py` -> forwards to `scripts/run_integrated_options_paper_engine.py`
- `python3 run_complete_v3_system.py` -> forwards to `scripts/run_complete_v3_system.py`

Gap validators:

- Gap 1: `python3 scripts/verify_gap1_fixes.py`
- Gap 2: `python3 scripts/validate_gap2_complete.py`
- Gap 3: `python3 scripts/validate_gap3_robust_complete.py`
- Gap 4: `python3 scripts/test_gap4_robust.py`
- Gap 5: `python3 scripts/validate_gap5_complete.py`
- Gap 6: `python3 scripts/validate_gap6_complete.py`
- Gap 7: `python3 scripts/validate_gap7_complete.py`

## Script Hygiene Rules

To stop the root `scripts/` directory from getting worse:

- New canonical operator entrypoints may live directly under `scripts/`.
- One-off debugging scripts should go under `scripts/debug/`.
- Analysis and audits should go under `scripts/analysis/`.
- Cleanup and repo-maintenance work should go under `scripts/cleanup/`.
- CI-only helpers should go under `scripts/ci/`.
- Temporary experiment/fix scripts should not stay in `scripts/` root once the work is complete.

## Mental Model

Think of the repo in three layers:

- Product layer: `src/`, `config/`, `tests/`
- Operator layer: a small curated subset of `scripts/`
- Artifact layer: `data/`, `reports/`, `snapshots/`

Most daily work should stay in the first two layers.

If `git status` looks overwhelming, it is usually artifact-layer noise rather than product-code churn.
Check `reports/README.md` and `snapshots/README.md` before treating those areas as primary working surfaces.
