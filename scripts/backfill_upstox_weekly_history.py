#!/usr/bin/env python3
"""
Backfill Upstox option history with weekly candles and emit a strict coverage report.

This wrapper intentionally separates:
1) Data pull attempt
2) Coverage audit (what actually came back)

So long-range requests (e.g. start year 2000) never look "successful" unless
coverage really matches expectation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


IST = timezone(timedelta(hours=5, minutes=30))
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def _interval_tag(interval: str) -> str:
    raw = str(interval or "").strip().lower()
    return (
        raw.replace("minute", "m")
        .replace("day", "d")
        .replace("week", "w")
        .replace("/", "_")
        .replace(" ", "_")
    )


@dataclass
class CoverageRow:
    symbol: str
    file_path: str
    rows: int
    unique_dates: int
    min_date: str
    max_date: str
    span_days: int


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upstox weekly long-history backfill + coverage audit")
    p.add_argument("--start-date", type=str, default="2000-01-01")
    p.add_argument("--end-date", type=str, default=_today_ist())
    p.add_argument("--underlyings", type=str, default="NIFTY500_PLUS_INDICES")
    p.add_argument("--output-dir", type=str, default="data/options/historical")
    p.add_argument("--candle-interval", type=str, default="1week")
    p.add_argument("--request-interval-seconds", type=float, default=0.90)
    p.add_argument("--max-retries", type=int, default=6)
    p.add_argument("--future-expiry-days", type=int, default=45)
    p.add_argument(
        "--contract-listing-lookback-days",
        type=int,
        default=0,
        help="Per-contract pre-expiry lookback cap (set 0 to disable clamp)",
    )
    p.add_argument("--max-underlyings", type=int, default=0)
    p.add_argument("--max-contracts-per-underlying", type=int, default=0)
    p.add_argument("--progress-every-contracts", type=int, default=50)
    p.add_argument("--upstox-access-token", type=str, default="")
    p.add_argument("--resume-dir", type=str, default="")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--refresh-instruments", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip network pull and only run coverage audit on existing files",
    )
    p.add_argument(
        "--strict-start-date",
        action="store_true",
        help="Fail if returned coverage starts materially after requested start-date",
    )
    p.add_argument(
        "--require-expired-api",
        action="store_true",
        help=(
            "Fail if provider diagnostics say expired-instruments API is unavailable. "
            "Recommended for deep-history gating."
        ),
    )
    p.add_argument(
        "--strict-tolerance-days",
        type=int,
        default=21,
        help="Allowed lag (days) between requested start and observed global min before strict failure",
    )
    p.add_argument(
        "--coverage-report-path",
        type=str,
        default="",
        help="Optional report output path (default: data/options/historical/coverage_reports/...)",
    )
    return p.parse_args()


def _build_cmd(args: argparse.Namespace) -> List[str]:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/build_groww_option_universe.py"),
        "--provider",
        "upstox",
        "--start-date",
        str(args.start_date),
        "--end-date",
        str(args.end_date),
        "--underlyings",
        str(args.underlyings),
        "--output-dir",
        str(args.output_dir),
        "--candle-interval",
        str(args.candle_interval),
        "--request-interval-seconds",
        str(float(args.request_interval_seconds)),
        "--max-retries",
        str(int(args.max_retries)),
        "--future-expiry-days",
        str(int(args.future_expiry_days)),
        "--contract-listing-lookback-days",
        str(int(args.contract_listing_lookback_days)),
        "--progress-every-contracts",
        str(int(args.progress_every_contracts)),
    ]
    if str(args.upstox_access_token).strip():
        cmd.extend(["--upstox-access-token", str(args.upstox_access_token).strip()])
    if int(args.max_underlyings) > 0:
        cmd.extend(["--max-underlyings", str(int(args.max_underlyings))])
    if int(args.max_contracts_per_underlying) > 0:
        cmd.extend(["--max-contracts-per-underlying", str(int(args.max_contracts_per_underlying))])
    if str(args.resume_dir).strip():
        cmd.extend(["--resume-dir", str(args.resume_dir).strip()])
    if bool(args.no_resume):
        cmd.append("--no-resume")
    if bool(args.refresh_instruments):
        cmd.append("--refresh-instruments")
    if bool(args.overwrite):
        cmd.append("--overwrite")
    if bool(args.verbose):
        cmd.append("--verbose")
    return cmd


def _scan_coverage(base_output_dir: Path, candle_interval: str) -> Dict[str, object]:
    interval = _interval_tag(candle_interval)
    target_dir = base_output_dir if interval == "1d" else (base_output_dir / interval)

    rows: List[CoverageRow] = []
    if target_dir.exists():
        for fp in sorted(target_dir.glob("*_option_chains.parquet")):
            try:
                frame = pd.read_parquet(fp, columns=["date"])
            except Exception:
                continue
            if frame.empty:
                continue
            dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
            if dates.empty:
                continue
            min_dt = dates.min().date()
            max_dt = dates.max().date()
            rows.append(
                CoverageRow(
                    symbol=fp.name.replace("_option_chains.parquet", "").upper(),
                    file_path=str(fp),
                    rows=int(len(frame)),
                    unique_dates=int(dates.dt.date.nunique()),
                    min_date=min_dt.isoformat(),
                    max_date=max_dt.isoformat(),
                    span_days=max(0, int((max_dt - min_dt).days)),
                )
            )

    if not rows:
        return {
            "target_dir": str(target_dir),
            "files": 0,
            "global_min_date": "",
            "global_max_date": "",
            "rows": [],
        }

    min_dates = pd.to_datetime([r.min_date for r in rows], errors="coerce")
    max_dates = pd.to_datetime([r.max_date for r in rows], errors="coerce")
    return {
        "target_dir": str(target_dir),
        "files": len(rows),
        "global_min_date": str(min_dates.min().date()) if len(min_dates.dropna()) else "",
        "global_max_date": str(max_dates.max().date()) if len(max_dates.dropna()) else "",
        "rows": [r.__dict__ for r in rows],
    }


def _write_report(report: Dict[str, object], args: argparse.Namespace) -> Path:
    if str(args.coverage_report_path).strip():
        out = Path(str(args.coverage_report_path).strip()).expanduser()
    else:
        reports_dir = Path(args.output_dir) / "coverage_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = reports_dir / f"upstox_weekly_coverage_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    latest = out.parent / "upstox_weekly_coverage_latest.json"
    latest.write_text(json.dumps(report, indent=2))
    return out


def main() -> int:
    args = _parse_args()
    cmd = _build_cmd(args)

    started = datetime.now(IST)
    if bool(args.skip_build):
        print("Skipping build step (--skip-build); running coverage audit only.")
        proc = subprocess.CompletedProcess(args=cmd, returncode=0)
        build_executed = False
    else:
        print("Running:", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False)
        build_executed = True
    finished = datetime.now(IST)

    output_root = Path(args.output_dir)
    interval_tag = _interval_tag(args.candle_interval)
    builder_output_dir = output_root if interval_tag == "1d" else (output_root / interval_tag)

    coverage = _scan_coverage(output_root, args.candle_interval)
    report: Dict[str, object] = {
        "generated_at_ist": finished.isoformat(),
        "started_at_ist": started.isoformat(),
        "requested": {
            "provider": "upstox",
            "start_date": str(args.start_date),
            "end_date": str(args.end_date),
            "underlyings": str(args.underlyings),
            "candle_interval": str(args.candle_interval),
            "contract_listing_lookback_days": int(args.contract_listing_lookback_days),
        },
        "builder_command": cmd,
        "builder_executed": bool(build_executed),
        "builder_return_code": (int(proc.returncode) if build_executed else None),
        "coverage": coverage,
    }

    manifest_path = builder_output_dir / "upstox_universe_manifest_latest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            diag = manifest.get("provider_diagnostics")
            if isinstance(diag, dict):
                report["provider_diagnostics"] = diag
        except Exception:
            pass

    strict_failed = False
    strict_reason = ""
    if bool(args.strict_start_date):
        req_start = pd.to_datetime(str(args.start_date), errors="coerce")
        got_start = pd.to_datetime(str(coverage.get("global_min_date", "")), errors="coerce")
        if pd.notna(req_start) and pd.notna(got_start):
            lag_days = int((got_start - req_start).days)
            report["strict_start_check"] = {
                "requested_start": str(req_start.date()),
                "observed_global_start": str(got_start.date()),
                "lag_days": lag_days,
                "tolerance_days": int(args.strict_tolerance_days),
            }
            if lag_days > int(args.strict_tolerance_days):
                strict_failed = True
                strict_reason = (
                    f"Coverage starts {lag_days} days after requested start "
                    f"(tolerance {int(args.strict_tolerance_days)} days)"
                )

    if bool(args.require_expired_api):
        diag = report.get("provider_diagnostics")
        expired_state = ""
        if isinstance(diag, dict):
            expired_state = str(diag.get("expired_instruments_api", "")).strip().lower()
        if expired_state != "available":
            strict_failed = True
            reason = "expired-instruments API unavailable"
            strict_reason = f"{strict_reason}; {reason}" if strict_reason else reason

    report["strict_failed"] = bool(strict_failed)
    if strict_reason:
        report["strict_failure_reason"] = strict_reason

    report_path = _write_report(report, args)
    print(f"Coverage report: {report_path}")
    print(
        "Observed coverage:",
        coverage.get("global_min_date", ""),
        "->",
        coverage.get("global_max_date", ""),
        f"(files={coverage.get('files', 0)})",
    )

    if build_executed and proc.returncode != 0:
        return int(proc.returncode)
    if strict_failed:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
