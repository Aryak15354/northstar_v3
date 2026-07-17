# Northstar V3 Workspace Guide

This is the active operator map for the V3 workspace. It exists to keep day-to-day work on a small, coherent surface while preserving the larger research and historical data estate.

## Active Surface

- Product code: `src/`
- Active configuration: `config/`
- Tests: `tests/` and package-local `src/**/tests/`
- Durable data stores: `data/canonical/`, `data/raw/`, `data/processed/`, `data/options/`, `data/runtime/`, `data/pnl/`
- Operator commands: `make help`, `make doctor`, `python3 scripts/ns.py`

## Canonical Commands

- `make status`: current system health snapshot.
- `make data-contracts`: validates the canonical data artifacts and required schemas.
- `make test-collect`: verifies pytest can discover the test suite.
- `make test-fast`: fast smoke tests for repaired integration surfaces.
- `make preopen`: pre-market readiness checks.
- `make morning`: morning scoring pipeline.
- `make eod`: end-of-day rebalance and P&L sync.
- `make dashboard`: launch the dashboard.
- `python3 scripts/run_complete_v3_system.py`: modern end-to-end daily runner.

## Working Rules

- Do not delete historical market, fundamental, macro, options, news, sentiment, P&L, or runtime data unless a retention rule explicitly says it is disposable.
- Prefer canonical data contracts over direct ad hoc reads from legacy paths.
- Canonical contract definitions live in `src/data/artifact_contracts.py`; legacy aliases are recorded there for compatibility but should not be new write targets.
- Prefer `src.*` imports from product code.
- Keep one-off scripts out of the active operator path. If they remain useful, catalog them; if not, quarantine them.
- Generated reports belong in `reports/`; durable operating guidance belongs in `docs/`.

## Secondary Roots

These roots are useful but should not be treated as the active product spine:

- `reports/`
- `snapshots/`
- `archive/`
- `_cold_archive/`
- `notebooks/`
- `logs/`
- research campaign folders

## Current Integration Priority

1. Keep test collection green.
2. Keep operator navigation truthful.
3. Repair central orchestration and import conventions.
4. Enforce canonical data contracts and freshness.
5. Quarantine obsolete scripts only after dependency checks.
