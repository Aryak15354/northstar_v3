#!/usr/bin/env python3
from __future__ import annotations

import json
import pickle
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.bootstrap_runtime_gate_state import bootstrap_ci_runtime_state
from src.runtime import PortfolioRuntimeService

INDEX_FILES = [
    "nifty_50.parquet",
    "nifty_100.parquet",
    "nifty_500.parquet",
    "nifty_bank.parquet",
    "nifty_it.parquet",
    "nifty_fmcg.parquet",
    "nifty_auto.parquet",
    "nifty_pharma.parquet",
    "nifty_metal.parquet",
    "nifty_realty.parquet",
    "nifty_energy.parquet",
    "nifty_psu.parquet",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _load_freeze_state() -> Dict[str, Any]:
    path = ROOT / "data/processed/model_freeze_state.json"
    if not path.exists():
        return {"freeze_active": False, "triggers": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"freeze_active": False, "triggers": []}
    return {
        "freeze_active": bool(payload.get("freeze_active", False)),
        "triggers": payload.get("triggers") or [],
    }


def _ensure_dirs() -> None:
    for rel in [
        "data/processed/index_data",
        "data/processed",
        "data/options/live",
        "data/runtime",
        "data/processed/runtime",
        "reports/system",
    ]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def _write_index_data(now: datetime) -> None:
    base_dates = pd.date_range(end=now.date(), periods=5, freq="D")
    template = pd.DataFrame(
        {
            "date": base_dates,
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [1_000_000, 1_050_000, 1_100_000, 1_120_000, 1_150_000],
        }
    )
    index_dir = ROOT / "data/processed/index_data"
    for index_file in INDEX_FILES:
        template.to_parquet(index_dir / index_file, index=False)


def _write_market_state(now: datetime) -> None:
    market_state = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(now.date()),
                "macro_score": 0.42,
                "risk_on_probability": 0.61,
                "allowed_exposure": 0.75,
                "regime": "neutral",
            }
        ]
    )
    market_state.to_parquet(ROOT / "data/processed/market_state.parquet", index=False)

    market_json = {
        "timestamp": now.isoformat(),
        "indices": {
            "NIFTY": {"last_price": 22500.0, "change_pct": 0.12},
            "BANKNIFTY": {"last_price": 48200.0, "change_pct": -0.08},
            "IT": {"last_price": 36500.0, "change_pct": 0.21},
        },
    }
    (ROOT / "data/options/live/market_data_latest.json").write_text(
        json.dumps(market_json, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_system_update_artifacts(now: datetime) -> None:
    pd.DataFrame(
        [
            {"ticker": "RELIANCE", "score": 0.73, "as_of": now.isoformat()},
            {"ticker": "TCS", "score": 0.68, "as_of": now.isoformat()},
            {"ticker": "HDFCBANK", "score": 0.64, "as_of": now.isoformat()},
        ]
    ).to_parquet(ROOT / "data/processed/scores.parquet", index=False)

    pd.DataFrame(
        [
            {"date": pd.Timestamp(now.date()), "ticker": "RELIANCE", "weight": 0.30},
            {"date": pd.Timestamp(now.date()), "ticker": "TCS", "weight": 0.25},
            {"date": pd.Timestamp(now.date()), "ticker": "HDFCBANK", "weight": 0.20},
        ]
    ).to_parquet(ROOT / "data/processed/portfolio_weights.parquet", index=False)

    pd.DataFrame(
        [
            {"strategy": "quality_compounders", "belief": 0.71, "updated_at": now.isoformat()},
            {"strategy": "macro_regime", "belief": 0.63, "updated_at": now.isoformat()},
        ]
    ).to_parquet(ROOT / "data/processed/strategy_beliefs.parquet", index=False)

    status = {
        "last_update": now.isoformat(),
        "system_operational": True,
        "mode": "ci_gate_smoke",
    }
    (ROOT / "data/processed/system_status.json").write_text(
        json.dumps(status, indent=2) + "\n",
        encoding="utf-8",
    )

    for mode in ("live", "research"):
        payload_path = ROOT / f"data/processed/dashboard_view_model_{mode}.pkl"
        meta_path = ROOT / f"data/processed/dashboard_view_model_{mode}.json"
        with open(payload_path, "wb") as handle:
            pickle.dump(
                {
                    "mode": mode,
                    "datasets": {
                        "scores": ["RELIANCE", "TCS", "HDFCBANK"],
                        "weights": [0.30, 0.25, 0.20],
                    },
                },
                handle,
            )
        meta_path.write_text(
            json.dumps(
                {
                    "mode": mode,
                    "dataset_count": 2,
                    "datasets": {
                        "scores": {"rows": 3},
                        "weights": {"rows": 3},
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _bootstrap_runtime_db() -> Dict[str, Any]:
    prs = PortfolioRuntimeService(
        db_path=str(ROOT / "data/runtime/portfolio_runtime.db"),
        materialized_output_dir=str(ROOT / "data/processed/runtime"),
    )
    replay_result = prs.replay()
    prs.close()
    return replay_result


def _run_check(script_rel: str) -> Dict[str, Any]:
    cmd = [sys.executable, str(ROOT / script_rel)]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip())
        raise RuntimeError(f"{script_rel} failed with exit code {proc.returncode}")
    return {"script": script_rel, "returncode": proc.returncode}


def _write_candidate_report(now: datetime, replay_result: Dict[str, Any]) -> Path:
    freeze_state = _load_freeze_state()
    report = {
        "execution_summary": {
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "total_duration_seconds": 0.0,
            "total_duration_minutes": 0.0,
        },
        "phase_results": {
            "data_ingestion": {
                "status": "success",
                "details": ["CI smoke artifacts validated by strict_data_ingestion_check.py"],
            },
            "system_update": {
                "status": "success",
                "details": [
                    "CI smoke artifacts validated by strict_system_update_check.py",
                    "Options runtime contract validated by strict_options_runtime_check.py",
                ],
            },
            "runtime_replay": {
                "status": "success",
                "details": [json.dumps(replay_result, sort_keys=True)],
            },
        },
        "system_status": {
            "freeze_active": bool(freeze_state.get("freeze_active", False)),
            "freeze_triggers": list(freeze_state.get("triggers") or []),
            "ci_gate_mode": True,
            "candidate_type": "shadow_delta_smoke",
        },
        "summary": {
            "status": "success",
            "notes": ["Deterministic CI candidate generated from canonical bootstrap fixtures."],
        },
    }
    out = ROOT / "reports/system" / f"complete_system_run_{now.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    now = _now_utc()
    _ensure_dirs()
    bootstrap_ci_runtime_state()
    _write_index_data(now)
    _write_market_state(now)
    _write_system_update_artifacts(now)
    replay_result = _bootstrap_runtime_db()

    for script_rel in (
        "scripts/ci/strict_data_ingestion_check.py",
        "scripts/ci/strict_system_update_check.py",
        "scripts/ci/strict_options_runtime_check.py",
    ):
        _run_check(script_rel)

    report_path = _write_candidate_report(now, replay_result)
    print(
        json.dumps(
            {
                "status": "ok",
                "report_path": str(report_path),
                "replay_result": replay_result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
