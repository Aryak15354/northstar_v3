#!/usr/bin/env python3
"""Canonical intraday sentiment refresh loop for Northstar V3."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import fields, is_dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_pipeline_runner import SentimentPipelineRunner
from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_state import compute_sentiment_state


IST = ZoneInfo("Asia/Kolkata")
LOG_PATH = PROJECT_ROOT / "logs" / "sentiment_loop.log"
STATUS_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "sentiment_loop_status.json"
STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"


def _deep_merge(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    config: dict[str, Any] = {}
    for raw_path in [
        PROJECT_ROOT / "config" / "ingestion_config.yaml",
        PROJECT_ROOT / "config" / "sentiment_config.yaml",
    ]:
        if not raw_path.exists():
            continue
        payload = yaml.safe_load(raw_path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            config = _deep_merge(config, payload)

    sentiment_section = dict(config.get("sentiment", {}) or {})
    sentiment_section.setdefault("duckdb_path", "data/sentiment.duckdb")
    sentiment_section.setdefault("processed_output_dir", "data/processed/sentiment")
    sentiment_section.setdefault("v3_output_dir", "data/sentiment/v3")
    config["sentiment"] = sentiment_section
    return config


def configure_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("northstar.sentiment_loop")
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


def _market_hours(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    return dt_time(9, 15) <= now.time() <= dt_time(15, 30)


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
        value = getattr(obj, field.name)
        updates.append(
            StateUpdate(
                writer_id=writer_id,
                section=section,
                field_path=field.name,
                new_value=value,
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason=reason,
            )
        )
    return updates


def _load_unified_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return state


def _write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def run_sentiment_update(config: dict[str, Any], logger: logging.Logger, *, force: bool = False) -> dict[str, Any]:
    now = datetime.now(IST)
    logger.info("Starting sentiment refresh at %s", now.isoformat())

    runner = SentimentPipelineRunner(config)
    pipeline_result = runner.run(as_of_date=now, force=force)

    registry = IngestionRegistry(config)
    classifier = SentimentRegimeClassifier(config)
    unified_state = _load_unified_state()
    sentiment_state = compute_sentiment_state(
        registry=registry,
        as_of_date=now,
        sentiment_regime_classifier=classifier,
        market_state=unified_state.market,
    )

    authority = StateAuthority(
        unified_state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="sentiment_loop",
        allowed_sections=["sentiment", "health"],
        priority=WritePriority.RESEARCH,
    )

    sentiment_updates = _dataclass_leaf_updates(
        writer_id="sentiment_loop",
        section="sentiment",
        obj=sentiment_state,
        reason="Intraday sentiment refresh",
    )
    applied = authority.batch_update(sentiment_updates)
    if applied != len(sentiment_updates):
        raise RuntimeError(f"sentiment_state_sync_incomplete:{applied}/{len(sentiment_updates)}")

    health_updates = [
        StateUpdate(
            writer_id="sentiment_loop",
            section="health",
            field_path="intelligence_active",
            new_value=bool(sentiment_state.is_fresh),
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Intraday sentiment refresh",
        )
    ]
    authority.batch_update(health_updates)
    authority.checkpoint(force=True)

    payload = {
        "timestamp": now.isoformat(),
        "status": pipeline_result.status,
        "pipeline": {
            "articles_processed": int(pipeline_result.articles_processed),
            "companies_covered": int(pipeline_result.companies_covered),
            "market_score_today": float(pipeline_result.market_score_today),
            "run_duration_seconds": float(pipeline_result.run_duration_seconds),
            "errors": list(pipeline_result.errors),
        },
        "canonical_state": {
            "market_sentiment_regime": getattr(
                sentiment_state.market_sentiment_regime,
                "value",
                str(sentiment_state.market_sentiment_regime),
            ),
            "is_fresh": bool(sentiment_state.is_fresh),
            "companies_with_coverage": int(sentiment_state.companies_with_coverage),
            "pipeline_last_run": sentiment_state.pipeline_last_run,
        },
        "state_path": str(STATE_PATH),
    }
    _write_status(payload)
    logger.info(
        "Sentiment refresh complete: status=%s regime=%s fresh=%s coverage=%s",
        pipeline_result.status,
        payload["canonical_state"]["market_sentiment_regime"],
        payload["canonical_state"]["is_fresh"],
        payload["canonical_state"]["companies_with_coverage"],
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical intraday sentiment refresh loop.")
    parser.add_argument("--interval-minutes", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-outside-market-hours", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logger()
    config = load_config()
    interval_seconds = max(60.0, float(args.interval_minutes) * 60.0)

    try:
        while True:
            now = datetime.now(IST)
            if not args.allow_outside_market_hours and not _market_hours(now):
                payload = {
                    "timestamp": now.isoformat(),
                    "status": "SKIPPED",
                    "reason": "outside_market_hours",
                }
                _write_status(payload)
                logger.info("Skipping sentiment refresh outside market hours")
            else:
                run_sentiment_update(config, logger, force=bool(args.force))
            if args.once:
                return 0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Sentiment loop interrupted by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
