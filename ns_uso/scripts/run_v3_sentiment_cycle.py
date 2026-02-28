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
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "v3_sentiment_summary.json"


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


def main() -> int:
    rc = _run("ns_uso/scripts/run_v3_batch_ingestion.py")
    status = _read_status()

    if rc == 0 and status == "success":
        print("✅ NS-USO ingestion succeeded from export artifacts.")
        return 0

    print("⚠️ NS-USO exports unavailable for this cycle; running live fallback producer...")
    fallback_rc = _run("ns_uso/scripts/produce_v3_exports.py")
    fallback_status = _read_status()

    if fallback_rc == 0 and fallback_status == "success":
        print("✅ NS-USO fallback producer succeeded.")
        return 0

    print("❌ NS-USO sentiment cycle failed to produce successful artifacts.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
