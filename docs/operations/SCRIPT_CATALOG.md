# Script Catalog

This catalog keeps the operator surface small. The raw `scripts/` tree is large and contains production runners, research utilities, backfills, demos, validators, debug helpers, and historical fix scripts.

## Canonical Entry Points

- `scripts/run_complete_v3_system.py`: modern end-to-end daily runner.
- `scripts/preopen_checks.py`: pre-market readiness checks.
- `scripts/run_morning_pipeline.py`: morning scoring pipeline.
- `scripts/eod_rebalance_with_pnl.py`: end-of-day rebalance and P&L sync.
- `scripts/promote_research_model.py`: governed model promotion.
- `scripts/launch_dashboard.sh`: dashboard launcher.
- `scripts/system_status_report.py`: current system health report.
- `scripts/ns.py`: navigation helper.

## Validation Commands

- `python3 -m pytest --collect-only -q`
- `python3 scripts/ci/check_canonical_artifact_contracts.py`
- `python3 scripts/ci/check_no_tracked_deadweight.py`
- `python3 scripts/ci/check_archive_import_isolation.py`
- `python3 scripts/ci/check_no_secrets.py`

## Gap Validators

- `scripts/verify_gap1_fixes.py`
- `scripts/validate_gap2_complete.py`
- `scripts/validate_gap3_robust_complete.py`
- `scripts/test_gap4_robust.py`
- `scripts/validate_gap5_complete.py`
- `scripts/validate_gap6_complete.py`
- `scripts/validate_gap7_complete.py`

## Working Rule

Prefer the canonical entry points above. Treat other root scripts as migration, repair, research, or debug utilities until they are explicitly promoted into this catalog.
