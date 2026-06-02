# Root Folder Readme

This file is for the machine operator working inside the local workspace.

## What Matters In Root

These are the root-level files you should actually care about:

- `README.md`: repo overview
- `ROOT_FOLDER_README.md`: local operator guide
- `.env.options`: live credentials, including the Upstox access token
- `run.py`: canonical high-level entrypoint
- `run_daily_v3.py`: scheduler-friendly daily runner
- `run_complete_v3_system.py`: compatibility wrapper that forwards to `scripts/run_complete_v3_system.py`
- `scripts/`: the real operational surface
- `ns_uso/`: canonical NS-USO sentiment/export surface
- `config/`, `src/`, `tests/`: product code and config

## Your Normal Routine

On trading days:

1. Before `08:50 IST`, update `UPSTOX_ACCESS_TOKEN` in `.env.options`.
2. Do not manually start the live system unless you are recovering from a failure.
3. If you want research after market close, run `python3 scripts/run_research_worker.py --once --manual-run`.

Everything else is intended to run automatically.

## Automation That Runs By Itself

- Weekdays `08:50 IST`: `scripts/run_trading_day_orchestrator.py`
- Intraday: market loop, sentiment loop, options runtime, stale-loop recycling, runtime/accounting sync
- After `15:30 IST`: EOD prices, RBI update, market-state integration, alternative data refresh, artifact refresh, strict system check
- Saturdays `10:30 IST`: `scripts/run_weekend_maintenance.py`
- Daily `20:45 IST`: `scripts/backup_northstar_data.py --verify`

## Commands You May Actually Use

- Readiness check: `python3 scripts/verify_live_system.py --for-tomorrow`
- Manual fallback start: `bash scripts/start_live_trading.sh`
- Stop live stack: `bash scripts/stop_live_trading.sh`
- Show installed schedule: `scripts/manage_cron.sh show`
- Pre-open guardrail check: `python3 scripts/preopen_checks.py`

## What To Ignore

- `docs/archive/root_status_reports/top_level_legacy_20260319/`: archived progress and status notes removed from root during cleanup
- `reports/archive/root_exports_20260319/`: archived root-level exports
- `data/`, `logs/`, `reports/`, `snapshots/`: large generated surfaces
- `dashboard/`, `northstar/`, `system/`: deprecated roots that should not be used as primary surfaces
- Legacy root launchers such as `START_LIVE_SYSTEM.sh`, `START_OPTIONS_SYSTEM.sh`, and `launch_*.sh`: these are not the canonical live path anymore

## If Something Looks Wrong

Start with:

- `python3 scripts/verify_live_system.py --for-tomorrow`
- `python3 scripts/preopen_checks.py`

If those pass, the automated surface is generally healthy and ready to take over again.
