#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

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


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required artifact: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"Empty artifact: {path}")


def _validate_index_data() -> dict:
    index_dir = ROOT / "data/processed/index_data"
    details = {}
    for name in INDEX_FILES:
        path = index_dir / name
        _require_file(path)
        df = pd.read_parquet(path)
        if df.empty:
            raise RuntimeError(f"Index data empty: {path}")
        required_cols = {"open", "high", "low", "close"}
        missing = sorted(required_cols - set(df.columns))
        if missing:
            raise RuntimeError(f"Index data missing columns {missing}: {path}")
        details[name] = int(len(df))
    return details


def _validate_market_state() -> dict:
    market_state_path = ROOT / "data/processed/market_state.parquet"
    _require_file(market_state_path)
    df = pd.read_parquet(market_state_path)
    if df.empty:
        raise RuntimeError("market_state.parquet has zero rows")
    required = {"macro_score", "risk_on_probability", "allowed_exposure"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"market_state missing columns: {missing}")
    time_cols = {"date", "Date", "timestamp"}
    if not any(col in df.columns for col in time_cols):
        raise RuntimeError(
            "market_state missing temporal column; expected one of ['date', 'Date', 'timestamp']"
        )
    return {"rows": int(len(df)), "columns": int(len(df.columns))}


def _validate_live_market_json() -> dict:
    path = ROOT / "data/options/live/market_data_latest.json"
    _require_file(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("market_data_latest.json must contain an object")
    indices = payload.get("indices")
    if not isinstance(indices, dict) or not indices:
        raise RuntimeError("market_data_latest.json missing indices payload")
    for key in ("NIFTY", "BANKNIFTY", "IT"):
        if key not in indices:
            raise RuntimeError(f"market_data_latest.json missing index: {key}")
    return {"index_count": len(indices)}


def main() -> int:
    report = {
        "check": "strict_data_ingestion_check",
        "index_data": _validate_index_data(),
        "market_state": _validate_market_state(),
        "market_json": _validate_live_market_json(),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
