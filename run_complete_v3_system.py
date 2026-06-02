#!/usr/bin/env python3
"""
COMPATIBILITY WRAPPER - NOT THE PRIMARY IMPLEMENTATION.

This root-level script forwards legacy calls to scripts/run_complete_v3_system.py.
Do not add business logic here.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CANONICAL_RUNNER = PROJECT_ROOT / "scripts" / "run_complete_v3_system.py"
DASHBOARD_LAUNCHER = PROJECT_ROOT / "launch_dashboard.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for the canonical Northstar V3 runner."
    )
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument("--quick", action="store_true", help="Run the canonical pipeline in quick mode.")
    parser.add_argument("--data-only", action="store_true", help="Refresh data and canonical state only.")
    parser.add_argument("--dashboard-only", action="store_true", help="Launch only the canonical dashboard.")
    parser.add_argument(
        "--dashboard",
        default="brain",
        choices=["brain", "unified", "professional"],
        help="Legacy compatibility flag. All values map to the canonical dashboard.",
    )
    parser.add_argument("--port", type=int, default=8517, help="Dashboard port for compatibility launches.")
    parser.add_argument("--proof-level", choices=["none", "standard", "full"], default="standard")
    parser.add_argument("--dry-run", action="store_true", help="Print the canonical execution plan without running stages.")
    parser.add_argument("--force-gst", action="store_true", help="Force GST refresh even before the scheduled monthly window.")
    parser.add_argument("--include-announcements", action="store_true", help="Retained for compatibility; forwarded to the canonical runner.")
    parser.add_argument("--alt-start-year", type=int, default=2024)
    parser.add_argument("--alt-end-year", type=int, default=datetime.now().year)
    parser.add_argument("--screener-max-tickers", type=int, default=0)
    parser.add_argument("--news-sources", type=str, default="bse,rss")
    parser.add_argument("--news-max-tickers", type=int, default=0)
    parser.add_argument("--news-max-months", type=int, default=0)
    parser.add_argument("--force-data", action="store_true", help="Legacy no-op retained for CLI compatibility.")
    parser.add_argument(
        "--sentiment-cycles",
        type=int,
        default=1,
        help="Legacy no-op retained for scheduler compatibility.",
    )
    parser.add_argument(
        "--sentiment-interval-minutes",
        type=int,
        default=180,
        help="Legacy no-op retained for scheduler compatibility.",
    )
    parser.add_argument(
        "--block-sentiment-cycles",
        action="store_true",
        help="Legacy no-op retained for scheduler compatibility.",
    )
    parser.add_argument(
        "--skip-options-cycle",
        action="store_true",
        help="Legacy no-op. The canonical daily runner does not invoke the old options cycle.",
    )
    financials_group = parser.add_mutually_exclusive_group()
    financials_group.add_argument(
        "--update-quarterly-financials",
        action="store_true",
        help="Legacy no-op retained for CLI compatibility.",
    )
    financials_group.add_argument(
        "--refresh-quarterly-financials",
        action="store_true",
        help="Legacy no-op retained for CLI compatibility.",
    )
    parser.add_argument("--macro-heavy", action="store_true", help="Legacy no-op retained for CLI compatibility.")
    parser.add_argument("--skip-macro-impact", action="store_true", help="Legacy no-op retained for CLI compatibility.")
    parser.add_argument(
        "--skip-macro-transmission",
        action="store_true",
        help="Legacy no-op retained for CLI compatibility.",
    )
    parser.add_argument("--skip-integrity-audit", action="store_true", help="Legacy no-op retained for CLI compatibility.")
    parser.add_argument("--no-dashboard", action="store_true", help="Do not launch the dashboard after the canonical run.")
    parser.add_argument(
        "--skip-integration-alignment",
        action="store_true",
        help="Legacy no-op retained for CLI compatibility.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    return parser.parse_args()


def _ensure_target(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _launch_dashboard(port: int) -> int:
    _ensure_target(DASHBOARD_LAUNCHER, "dashboard launcher")
    cmd = [sys.executable, str(DASHBOARD_LAUNCHER), "--port", str(port)]
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def _canonical_command(args: argparse.Namespace) -> list[str]:
    _ensure_target(CANONICAL_RUNNER, "canonical runner")
    cmd = [
        sys.executable,
        str(CANONICAL_RUNNER),
        "--date",
        args.date,
        "--proof-level",
        args.proof_level,
        "--alt-start-year",
        str(args.alt_start_year),
        "--alt-end-year",
        str(args.alt_end_year),
        "--screener-max-tickers",
        str(args.screener_max_tickers),
        "--news-sources",
        args.news_sources,
        "--news-max-tickers",
        str(args.news_max_tickers),
        "--news-max-months",
        str(args.news_max_months),
    ]
    if args.quick:
        cmd.append("--quick")
    if args.data_only:
        cmd.append("--data-only")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.force_gst:
        cmd.append("--force-gst")
    if args.include_announcements:
        cmd.append("--include-announcements")
    return cmd


def _ignored_legacy_flags(args: argparse.Namespace) -> list[str]:
    ignored: list[str] = []
    legacy_pairs = [
        ("--force-data", args.force_data),
        ("--sentiment-cycles", args.sentiment_cycles != 1),
        ("--sentiment-interval-minutes", args.sentiment_interval_minutes != 180),
        ("--block-sentiment-cycles", args.block_sentiment_cycles),
        ("--skip-options-cycle", args.skip_options_cycle),
        ("--update-quarterly-financials", args.update_quarterly_financials),
        ("--refresh-quarterly-financials", args.refresh_quarterly_financials),
        ("--macro-heavy", args.macro_heavy),
        ("--skip-macro-impact", args.skip_macro_impact),
        ("--skip-macro-transmission", args.skip_macro_transmission),
        ("--skip-integrity-audit", args.skip_integrity_audit),
        ("--skip-integration-alignment", args.skip_integration_alignment),
    ]
    for name, enabled in legacy_pairs:
        if enabled:
            ignored.append(name)
    return ignored


def main() -> int:
    args = parse_args()
    print("Northstar V3 compatibility entrypoint")
    print("Delegating to scripts/run_complete_v3_system.py")
    ignored = _ignored_legacy_flags(args)
    if ignored:
        print(f"Ignoring legacy flags: {', '.join(ignored)}")

    if args.dashboard_only:
        return _launch_dashboard(args.port)

    command = _canonical_command(args)
    rc = subprocess.call(command, cwd=str(PROJECT_ROOT))
    if rc != 0:
        return int(rc)

    if args.no_dashboard or args.data_only or args.dry_run:
        return 0

    return _launch_dashboard(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
