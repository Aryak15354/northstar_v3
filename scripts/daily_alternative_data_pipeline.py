#!/usr/bin/env python3
"""Canonical daily alternative-data refresh pipeline for Northstar V3."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alternative_data.alternative_pipeline_runner import AlternativePipelineRunner
from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority


STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "alternative" / "alternative_pipeline_status.json"
STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"


def load_config() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "config" / "ingestion_config.yaml"
    if not config_path.exists():
        return {}
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _dataclass_leaf_updates(
    *,
    writer_id: str,
    section: str,
    obj: Any,
    reason: str,
) -> list[StateUpdate]:
    if not is_dataclass(obj):
        return []
    return [
        StateUpdate(
            writer_id=writer_id,
            section=section,
            field_path=field.name,
            new_value=getattr(obj, field.name),
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason=reason,
        )
        for field in fields(obj)
    ]


def _load_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh NSE-first alternative data and sync canonical state.")
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    parser.add_argument("--include-announcements", action="store_true", default=False, help="Deprecated no-op. NSE announcements now run by default.")
    parser.add_argument("--skip-collection", action="store_true", help="Skip scraper execution and only recompute/sync state.")
    parser.add_argument("--nse-period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1D")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    started = datetime.now()
    payload: dict[str, Any] = {
        "started_at": started.isoformat(),
        "collection": {"status": "SKIPPED"},
        "screener_processing": {"status": "PENDING"},
        "valuation_scores": {"status": "PENDING"},
        "state_sync": {"status": "PENDING"},
    }

    if not args.skip_collection:
        cmd = [
            sys.executable,
            "scripts/collect_all_alternative_data.py",
            "--start-year",
            str(args.start_year),
            "--end-year",
            str(args.end_year),
            "--nse-period",
            args.nse_period,
        ]
        cmd.append("--resume" if args.resume else "--no-resume")
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True)
        payload["collection"] = {
            "status": "SUCCESS" if proc.returncode == 0 else "FAILED",
            "return_code": int(proc.returncode),
            "command": cmd,
        }
        if proc.returncode != 0:
            STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return proc.returncode

    screener_proc = subprocess.run(
        [sys.executable, "scripts/load_screener_to_pipeline.py"],
        cwd=str(PROJECT_ROOT),
        text=True,
    )
    payload["screener_processing"] = {
        "status": "SUCCESS" if screener_proc.returncode == 0 else "FAILED",
        "return_code": int(screener_proc.returncode),
        "command": [sys.executable, "scripts/load_screener_to_pipeline.py"],
    }
    if screener_proc.returncode != 0:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return screener_proc.returncode

    valuation_proc = subprocess.run(
        [sys.executable, "scripts/compute_valuation_scores.py", "--date", "today"],
        cwd=str(PROJECT_ROOT),
        text=True,
    )
    payload["valuation_scores"] = {
        "status": "SUCCESS" if valuation_proc.returncode == 0 else "FAILED",
        "return_code": int(valuation_proc.returncode),
        "command": [sys.executable, "scripts/compute_valuation_scores.py", "--date", "today"],
    }
    if valuation_proc.returncode != 0:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return valuation_proc.returncode

    runner = AlternativePipelineRunner(config)
    result = runner.run(datetime.now(), force=True)
    state_obj = runner._last_processed_state or runner.compute_alternative_state(datetime.now())

    unified_state = _load_state()
    authority = StateAuthority(
        unified_state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="daily_alternative_pipeline",
        allowed_sections=["alternative_data"],
        priority=WritePriority.RESEARCH,
    )
    updates = _dataclass_leaf_updates(
        writer_id="daily_alternative_pipeline",
        section="alternative_data",
        obj=state_obj,
        reason="Daily alternative-data refresh",
    )
    applied = authority.batch_update(updates)
    if applied != len(updates):
        raise RuntimeError(f"alternative_state_sync_incomplete:{applied}/{len(updates)}")
    authority.checkpoint(force=True)

    payload["state_sync"] = {
        "status": "SUCCESS",
        "pipeline_status": result.status,
        "economic_activity_regime": getattr(state_obj.economic_activity_regime, "value", str(state_obj.economic_activity_regime)),
        "any_source_fresh": bool(state_obj.any_source_fresh),
        "all_sources_fresh": bool(state_obj.all_sources_fresh),
    }
    payload["finished_at"] = datetime.now().isoformat()
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
