#!/usr/bin/env python3
"""
Run NS-USO sentiment cycle continuously at a fixed cadence.

Default cadence is 5 minutes so sentiment artifacts stay aligned with
the integrated options engine loop.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "ns_uso_sentiment_loop.log"
STATUS_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "sentiment_loop_status.json"
RUNNER = PROJECT_ROOT / "ns_uso" / "scripts" / "run_v3_sentiment_cycle.py"
MARKET_SENTIMENT_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "market_sentiment_india.parquet"


def _configure_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ns_uso.sentiment_loop")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(LOG_PATH)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    if sys.stdout.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


def _write_status(payload: Dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2))


def _sentiment_snapshot() -> Dict[str, Any]:
    if not MARKET_SENTIMENT_PATH.exists():
        return {}
    try:
        df = pd.read_parquet(MARKET_SENTIMENT_PATH)
        if not isinstance(df, pd.DataFrame) or df.empty:
            return {}
        row = df.iloc[-1].to_dict()
        prev = df.iloc[-2].to_dict() if len(df) >= 2 else {}
        polarity = float(row.get("polarity", 0.0) or 0.0)
        uncertainty = float(row.get("uncertainty", 0.0) or 0.0)
        conviction = float(row.get("conviction", 1.0) or 1.0)
        delta_polarity = float(row.get("delta_polarity", polarity - float(prev.get("polarity", 0.0) or 0.0)) or 0.0)
        delta_uncertainty = float(
            row.get("delta_uncertainty", uncertainty - float(prev.get("uncertainty", 0.0) or 0.0)) or 0.0
        )
        return {
            "rows": int(len(df)),
            "polarity": polarity,
            "uncertainty": uncertainty,
            "conviction": conviction,
            "micro_shift_score": float(row.get("micro_shift_score", 0.0) or 0.0),
            "change_velocity": float(row.get("change_velocity", 0.0) or 0.0),
            "delta_polarity": delta_polarity,
            "delta_uncertainty": delta_uncertainty,
            "dominant_theme": str(row.get("dominant_theme", "unknown") or "unknown"),
        }
    except Exception:
        return {}


def _run_cycle(logger: logging.Logger) -> Dict[str, Any]:
    started = datetime.now().astimezone()
    cmd = [sys.executable, str(RUNNER)]
    logger.info("Running sentiment cycle: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    finished = datetime.now().astimezone()
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    output = output.strip()
    if output:
        logger.info("Cycle output: %s", output[-4000:])
    status = "success" if proc.returncode == 0 else "failed"
    payload = {
        "timestamp": finished.isoformat(),
        "status": status,
        "return_code": int(proc.returncode),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "runner": str(RUNNER),
    }
    snapshot = _sentiment_snapshot()
    if snapshot:
        payload["sentiment_snapshot"] = snapshot
    _write_status(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NS-USO sentiment cycle continuously.")
    parser.add_argument("--interval-minutes", type=float, default=5.0, help="Loop cadence in minutes (default: 5).")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    args = parser.parse_args()

    logger = _configure_logger()
    if not RUNNER.exists():
        logger.error("Sentiment runner missing: %s", RUNNER)
        return 1

    interval_seconds = max(10.0, float(args.interval_minutes) * 60.0)
    logger.info("Starting NS-USO sentiment loop (interval=%ss)", interval_seconds)

    try:
        while True:
            started = time.time()
            result = _run_cycle(logger)
            logger.info("Cycle status=%s rc=%s", result.get("status"), result.get("return_code"))
            if args.once:
                return 0 if int(result.get("return_code", 1)) == 0 else 1
            elapsed = time.time() - started
            sleep_for = max(1.0, interval_seconds - elapsed)
            logger.info("Sleeping %.1fs before next cycle", sleep_for)
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        logger.info("Sentiment loop interrupted by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
