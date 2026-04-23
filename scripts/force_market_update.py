#!/usr/bin/env python3
"""Canonical market refresh for Northstar V3."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "market_refresh_status.json"
MARKET_DATA_PATH = PROJECT_ROOT / "data" / "options" / "live" / "market_data_latest.json"
MARKET_STATE_PATH = PROJECT_ROOT / "data" / "processed" / "market_state.parquet"


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _fast_market_refresh_enabled() -> bool:
    return _env_flag("NORTHSTAR_FAST_MARKET_REFRESH") or _env_flag("NORTHSTAR_CI_GATE")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_market_state_stub(now_iso: str) -> None:
    MARKET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "timestamp": now_iso,
                "regime": "ci_fast_refresh",
                "allowed_exposure": 1.0,
                "volatility_regime": "ci_fast_refresh",
                "health_score": 1.0,
                "risk_on_probability": 0.5,
                "breadth_pct": 0.0,
                "confidence": 1.0,
            }
        ]
    ).to_parquet(MARKET_STATE_PATH, index=False)


def _run_fast_refresh() -> int:
    started = datetime.now()
    now_iso = started.isoformat()

    market_payload: dict[str, object] = {}
    if MARKET_DATA_PATH.exists():
        try:
            existing = json.loads(MARKET_DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                market_payload = dict(existing)
        except Exception:
            market_payload = {}

    indices = market_payload.get("indices")
    if not isinstance(indices, dict):
        indices = {}

    market_payload.update(
        {
            "timestamp": now_iso,
            "market_state": str(market_payload.get("market_state") or "ci_fast_refresh"),
            "source": "scripts/force_market_update.py",
            "refresh_mode": "ci_fast_path",
            "indices": indices,
        }
    )
    _write_json(MARKET_DATA_PATH, market_payload)
    _write_market_state_stub(now_iso)

    payload = {
        "started_at": now_iso,
        "finished_at": datetime.now().isoformat(),
        "pipeline_status": "SUCCESS",
        "mode": "ci_fast_path",
        "market_data_path": str(MARKET_DATA_PATH),
        "market_state_path": str(MARKET_STATE_PATH),
        "index_count": len(indices),
    }
    _write_json(STATUS_PATH, payload)
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _run_full_refresh() -> int:
    from src.ingestion.integrated_data_pipeline import IntegratedDataPipeline

    started = datetime.now()
    payload: dict[str, object] = {
        "started_at": started.isoformat(),
        "mode": "full_refresh",
        "market_data_path": str(MARKET_DATA_PATH),
    }

    pipeline = IntegratedDataPipeline()
    ok = pipeline.run_full_pipeline(market_only=True, force_market=True)
    payload["pipeline_status"] = "SUCCESS" if ok else "FAILED"
    payload["finished_at"] = datetime.now().isoformat()
    _write_json(STATUS_PATH, payload)
    print(json.dumps(payload, indent=2, default=str))
    return 0 if ok else 1


def main() -> int:
    if _fast_market_refresh_enabled():
        return _run_fast_refresh()
    return _run_full_refresh()


if __name__ == "__main__":
    raise SystemExit(main())
