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
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "logs" / "ns_uso_sentiment_loop.log"
STATUS_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "sentiment_loop_status.json"
RUNNER = PROJECT_ROOT / "ns_uso" / "scripts" / "run_v3_sentiment_cycle.py"
MARKET_SENTIMENT_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "market_sentiment_india.parquet"
STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_state import compute_sentiment_state


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
    STATUS_PATH.write_text(json.dumps(payload, indent=2, default=str))


def _deep_merge(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_config() -> dict:
    config: dict = {}
    for path in (
        PROJECT_ROOT / "config" / "ingestion_config.yaml",
        PROJECT_ROOT / "config" / "sentiment_config.yaml",
    ):
        if not path.exists():
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            config = _deep_merge(config, payload)
    return config


def _load_unified_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return state


def _dataclass_leaf_updates(
    *,
    writer_id: str,
    section: str,
    obj: Any,
    reason: str,
) -> list[StateUpdate]:
    updates: list[StateUpdate] = []
    if not is_dataclass(obj):
        return updates
    for field in fields(obj):
        updates.append(
            StateUpdate(
                writer_id=writer_id,
                section=section,
                field_path=field.name,
                new_value=getattr(obj, field.name),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason=reason,
            )
        )
    return updates


def _sync_canonical_sentiment_state(finished: datetime) -> Dict[str, Any]:
    config = _load_config()
    registry = IngestionRegistry(config)
    state = _load_unified_state()
    classifier = SentimentRegimeClassifier(config)
    sentiment_state = compute_sentiment_state(
        registry=registry,
        as_of_date=finished,
        sentiment_regime_classifier=classifier,
        market_state=state.market,
    )

    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="ns_uso_sentiment_loop",
        allowed_sections=["sentiment", "health"],
        priority=WritePriority.RESEARCH,
    )

    updates = _dataclass_leaf_updates(
        writer_id="ns_uso_sentiment_loop",
        section="sentiment",
        obj=sentiment_state,
        reason="NS-USO sentiment loop refresh",
    )
    applied = authority.batch_update(updates)
    if applied != len(updates):
        raise RuntimeError(f"ns_uso_sentiment_sync_incomplete:{applied}/{len(updates)}")

    authority.batch_update(
        [
            StateUpdate(
                writer_id="ns_uso_sentiment_loop",
                section="health",
                field_path="intelligence_active",
                new_value=bool(sentiment_state.is_fresh),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="NS-USO sentiment loop refresh",
            )
        ]
    )
    authority.checkpoint(force=True)

    return {
        "market_sentiment_regime": getattr(
            sentiment_state.market_sentiment_regime,
            "value",
            str(sentiment_state.market_sentiment_regime),
        ),
        "is_fresh": bool(sentiment_state.is_fresh),
        "companies_with_coverage": int(sentiment_state.companies_with_coverage),
        "pipeline_last_run": sentiment_state.pipeline_last_run,
        "state_path": str(STATE_PATH),
    }


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


def _refresh_processed_sentiment(logger: logging.Logger) -> Dict[str, Any]:
    export_cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/export_sentiment_to_v3.py"),
        "--output-dir",
        str(PROJECT_ROOT / "data/processed/sentiment"),
        "--incremental",
    ]
    proc = subprocess.run(export_cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    if output:
        logger.info("Processed sentiment export output: %s", output[-4000:])
    return {
        "return_code": int(proc.returncode),
        "command": " ".join(export_cmd),
        "ok": proc.returncode == 0,
    }


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
    if proc.returncode == 0:
        export_result = _refresh_processed_sentiment(logger)
        payload["processed_export"] = export_result
        try:
            payload["canonical_state"] = _sync_canonical_sentiment_state(finished)
        except Exception as exc:
            logger.warning("Canonical sentiment sync failed after NS-USO cycle: %s", exc)
            payload["canonical_state_error"] = str(exc)
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
