# Northstar V3 Repository Manifest

This manifest defines what belongs in the public source tree.

## Canonical Source Surface

- `run.py`: primary local entrypoint for dashboard, update, health, and status modes.
- `src/`: production library code.
- `scripts/`: operator, data, research, and CI scripts.
- `tests/`: active production and contract tests.
- `configs/`: public configuration templates and non-secret runtime config.
- `docs/`: maintained public documentation.
- `.github/workflows/`: CI gates.

## Runtime And Generated Artifacts

These paths are local-only and must not be tracked:

- `data/`
- `logs/`
- `tmp/`
- `reports/`
- `snapshots/`
- `runs/`
- `analysis_results/`
- `dist/kaggle/`
- `catboost_info/`
- virtual environments such as `.venv/` and `venv/`

## Archived Or Legacy Material

- `tests/legacy/` is excluded from default pytest collection and stores stale tests until their contracts are rewritten.
- Historical `archive/` and `backups/` trees are not part of the public production source surface.

## Public Safety Rules

- No `.env`, `.env.options`, private keys, broker tokens, or credential backups may be tracked.
- No machine-local absolute paths such as developer home directories or external drive mounts may appear in active public files.
- Production code must fail closed when live data or broker credentials are unavailable.
- Mock, synthetic, and demo behavior must stay in tests, examples, research, or explicitly named non-production paths.

## Required Local Gate

Run this before pushing:

```bash
python3 run.py --mode health --verbose
python3 -m pytest -q tests/intelligence/test_no_synthetic_data.py tests/test_health_exit_codes.py tests/test_dashboard_data_contract.py tests/test_signal_loader_canonical_paths.py
python3 -m pytest -q tests/intelligence_observer
```
