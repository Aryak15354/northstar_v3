#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required artifact: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"Empty artifact: {path}")


def _check_parquet(path: Path, required_cols: set[str]) -> dict:
    _require_file(path)
    df = pd.read_parquet(path)
    if df.empty:
        raise RuntimeError(f"Parquet has zero rows: {path}")
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise RuntimeError(f"Missing columns {missing}: {path}")
    return {"rows": int(len(df)), "columns": int(len(df.columns))}


def _check_view_model(mode: str) -> dict:
    payload_path = ROOT / f"data/processed/dashboard_view_model_{mode}.pkl"
    meta_path = ROOT / f"data/processed/dashboard_view_model_{mode}.json"
    _require_file(payload_path)
    _require_file(meta_path)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise RuntimeError(f"dashboard view model meta must be object: {meta_path}")
    if str(meta.get("mode")) != mode:
        raise RuntimeError(f"dashboard view model mode mismatch for {mode}")
    dataset_count = int(meta.get("dataset_count", 0) or 0)
    if dataset_count <= 0:
        raise RuntimeError(f"dashboard view model dataset_count must be > 0 for {mode}")
    datasets = meta.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise RuntimeError(f"dashboard view model datasets metadata missing for {mode}")
    return {
        "mode": mode,
        "dataset_count": dataset_count,
        "meta_keys": sorted(meta.keys()),
    }


def main() -> int:
    scores = _check_parquet(
        ROOT / "data/processed/scores.parquet",
        {"ticker"},
    )
    portfolio = _check_parquet(
        ROOT / "data/processed/portfolio_weights.parquet",
        {"weight"},
    )
    beliefs = _check_parquet(
        ROOT / "data/processed/strategy_beliefs.parquet",
        {"strategy"},
    )

    system_status_path = ROOT / "data/processed/system_status.json"
    _require_file(system_status_path)
    status = json.loads(system_status_path.read_text(encoding="utf-8"))
    if not isinstance(status, dict):
        raise RuntimeError("system_status.json must contain an object")
    for key in ("last_update", "system_operational"):
        if key not in status:
            raise RuntimeError(f"system_status missing key: {key}")

    report = {
        "check": "strict_system_update_check",
        "scores": scores,
        "portfolio": portfolio,
        "beliefs": beliefs,
        "system_status_keys": sorted(status.keys()),
        "dashboard_view_model_live": _check_view_model("live"),
        "dashboard_view_model_research": _check_view_model("research"),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
