#!/usr/bin/env python3
"""
Run one NS-USO sentiment cycle with guaranteed artifact production.

Flow:
1) Try strict NS-USO export ingestion.
2) If status != success, generate exports from live Northstar artifacts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path

import pandas as pd

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "v3_sentiment_summary.json"
MARKET_EXPORT_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "market_sentiment_india.parquet"
COMPANY_EXPORT_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "company_sentiment_trends.parquet"
IST = ZoneInfo("Asia/Kolkata") if ZoneInfo else None
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)


def _read_status() -> str:
    if not SUMMARY_PATH.exists():
        return ""
    try:
        payload = json.loads(SUMMARY_PATH.read_text())
    except Exception:
        return ""
    return str(payload.get("status", "")).strip().lower()


def _run(script_rel_path: str) -> int:
    cmd = [sys.executable, str(PROJECT_ROOT / script_rel_path)]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return int(proc.returncode)


def _now_ist_naive() -> datetime:
    now = datetime.now(IST) if IST else datetime.now()
    return now.replace(tzinfo=None)


def _freshness_threshold(now_local: datetime) -> timedelta:
    current_time = now_local.time()
    if now_local.weekday() < 5 and MARKET_OPEN <= current_time <= MARKET_CLOSE:
        return timedelta(minutes=20)
    if now_local.weekday() < 5:
        return timedelta(hours=18)
    return timedelta(hours=72)


def _latest_parquet_timestamp(path: Path, candidates: list[str]) -> pd.Timestamp | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None

    for column in candidates:
        if column not in df.columns:
            continue
        values = pd.to_datetime(df[column], errors="coerce").dropna()
        if values.empty:
            continue
        latest = pd.Timestamp(values.max())
        if latest.tzinfo is not None:
            latest = latest.tz_convert(IST).tz_localize(None) if IST else latest.tz_localize(None)
        return latest
    return None


def _artifacts_are_fresh() -> tuple[bool, dict]:
    now_local = _now_ist_naive()
    threshold = _freshness_threshold(now_local)
    market_ts = _latest_parquet_timestamp(MARKET_EXPORT_PATH, ["date", "Date", "timestamp"])
    company_ts = _latest_parquet_timestamp(COMPANY_EXPORT_PATH, ["timestamp", "date", "Date"])
    payload = {
        "now_ist": now_local.isoformat(),
        "threshold_minutes": round(threshold.total_seconds() / 60.0, 2),
        "market_latest": market_ts.isoformat() if market_ts is not None else None,
        "company_latest": company_ts.isoformat() if company_ts is not None else None,
    }
    if market_ts is None or company_ts is None:
        payload["reason"] = "missing_or_unreadable_exports"
        return False, payload

    market_age = now_local - market_ts.to_pydatetime()
    company_age = now_local - company_ts.to_pydatetime()
    payload["market_age_minutes"] = round(market_age.total_seconds() / 60.0, 2)
    payload["company_age_minutes"] = round(company_age.total_seconds() / 60.0, 2)
    payload["fresh"] = market_age <= threshold and company_age <= threshold
    if not payload["fresh"]:
        payload["reason"] = "stale_exports"
    return bool(payload["fresh"]), payload


def main() -> int:
    rc = _run("ns_uso/scripts/run_v3_batch_ingestion.py")
    status = _read_status()
    fresh, freshness_payload = _artifacts_are_fresh()

    if rc == 0 and status == "success" and fresh:
        print("✅ NS-USO ingestion succeeded from export artifacts.")
        return 0

    if status == "success" and not fresh:
        print(f"⚠️ NS-USO exports are stale; invoking live fallback producer ({freshness_payload}).")

    print("⚠️ NS-USO exports unavailable for this cycle; running live fallback producer...")
    fallback_rc = _run("ns_uso/scripts/produce_v3_exports.py")
    fallback_status = _read_status()
    fallback_fresh, fallback_payload = _artifacts_are_fresh()

    if fallback_rc == 0 and fallback_status == "success" and fallback_fresh:
        print("✅ NS-USO fallback producer succeeded.")
        return 0

    if fallback_status == "success" and not fallback_fresh:
        print(f"⚠️ NS-USO fallback producer completed but artifacts are still stale ({fallback_payload}).")

    print("❌ NS-USO sentiment cycle failed to produce successful artifacts.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
