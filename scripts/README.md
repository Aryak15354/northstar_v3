# Scripts

The raw `scripts/` tree is large. Do not treat every file here as an equal entrypoint.

## Use This First

- `make help`
- `make doctor`
- `make find q=sentiment`
- `python3 scripts/ns.py`
- `python3 scripts/ns.py catalog`
- `python3 scripts/ns.py gaps`

Those commands point you to the curated operational surface.

## Canonical Entry Points

These are the main scripts most people should care about:

- `scripts/run_complete_v3_system.py`: complete daily Gap 1-7 system run
- `scripts/northstar_v3_unified.py`: unified launcher
- `scripts/preopen_checks.py`: pre-market readiness checks
- `scripts/run_morning_pipeline.py`: morning pipeline
- `scripts/eod_rebalance_with_pnl.py`: EOD processing on the unified P&L path
- `scripts/promote_research_model.py`: governed model promotion
- `scripts/launch_dashboard.sh`: dashboard launch

Compatibility wrappers:

- `scripts/run_live_engine.py`: wrapper that forwards to `scripts/run_integrated_options_paper_engine.py`

Gap validators:

- `scripts/verify_gap1_fixes.py`
- `scripts/validate_gap2_complete.py`
- `scripts/validate_gap3_robust_complete.py`
- `scripts/test_gap4_robust.py`
- `scripts/validate_gap5_complete.py`
- `scripts/validate_gap6_complete.py`
- `scripts/validate_gap7_complete.py`

## Subdirectories

- `scripts/analysis/`: research and audit-style analysis
- `scripts/ci/`: CI helpers
- `scripts/cleanup/`: repo and workspace cleanup utilities
- `scripts/debug/`: debugging helpers
- `scripts/launchers/`: launcher wrappers
- `scripts/runners/`: focused component runners
- `scripts/tests/`: script-specific tests
- `scripts/utilities/`: shared utilities

## Working Rule

If you are adding a new script:

- put canonical operational entrypoints in `scripts/`
- put one-off or investigative tools in a subdirectory
- avoid leaving temporary `fix_*`, `debug_*`, or `demo_*` scripts in the root once the work is done

## Further Reading

- [Workspace Guide](../docs/operations/WORKSPACE_GUIDE.md)
- [Script Catalog](../docs/operations/SCRIPT_CATALOG.md)
