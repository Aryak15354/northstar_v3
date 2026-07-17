#!/usr/bin/env python3
"""Cadence-aware daily data refresh entry point.

Runs only the data sources that are *due* today per config/refresh_cadence.yaml
(daily / weekly / monthly / quarterly), merging into existing local data, then
rebuilds canonical panels once if anything changed. Safe to run repeatedly --
each source runs at most once per its cadence period.

This is also the entry the northstar daemon spawns once per day.

Examples:
    python3 scripts/daily_data_refresh.py                 # run everything due today
    python3 scripts/daily_data_refresh.py --dry-run       # show what WOULD run
    python3 scripts/daily_data_refresh.py --only equity_prices cross_asset
    python3 scripts/daily_data_refresh.py --force --only fundamentals
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.refresh_scheduler import RefreshScheduler  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cadence-aware daily data refresh")
    p.add_argument("--dry-run", action="store_true", help="Show what would run without running it")
    p.add_argument("--force", action="store_true", help="Ignore cadence and run (respects --only)")
    p.add_argument("--only", nargs="*", default=None, help="Limit to these source names")
    p.add_argument("--config", type=Path, default=None, help="Override cadence config path")
    p.add_argument("--state", type=Path, default=None, help="Override refresh state path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    kwargs = {}
    if args.config:
        kwargs["config_path"] = args.config
    if args.state:
        kwargs["state_path"] = args.state
    scheduler = RefreshScheduler(**kwargs)

    report = scheduler.run(dry_run=args.dry_run, force=args.force, only=args.only)

    print(json.dumps(report, indent=2, default=str))

    # After fresh data lands, rebuild the ₹100cr paper fund so its NAV
    # auto-extends to the new price horizon (honest freeze + extend). Kept as a
    # decoupled subprocess so a fund-rebuild hiccup never blocks data refresh.
    if not args.dry_run and not report.get("failed"):
        import subprocess
        root = Path(__file__).resolve().parents[1]
        for script in ("run_paper_fund.py", "run_strategy_benchmarks.py"):
            try:
                subprocess.run([sys.executable, str(root / "scripts" / script)],
                               check=False, timeout=600)
            except Exception as exc:  # pragma: no cover
                logging.warning("paper-fund step %s failed: %s", script, exc)

    # Non-zero exit if any source (or the canonical rebuild) failed, so the
    # daemon / cron can surface the failure.
    return 1 if report.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
