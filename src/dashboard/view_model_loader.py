#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEW_MODEL_DIR = PROJECT_ROOT / "data/processed"

LIVE_KEYS = {
    "market_state",
    "intelligent_state",
    "market_regime",
    "risk_state",
    "portfolio_weights",
    "portfolio_analytics",
    "pnl",
    "daily_narrative",
    "regime_feed",
    "options_dashboard_state",
    "options_runtime_state",
    "daemon_status",
    "live_heartbeat",
    "system_log",
    "edge_half_life",
    "liquidity_risk",
    "capital_allocations",
    "alpha_os_timeseries",
    "allocation_history",
    "index_nifty50",
    "sector_flows",
    "sector_rotation",
    "macro_factors",
    "macro_factors_v2",
    "strategy_beliefs",
    "strategy_regret",
    "integrity_report",
    "integrity_artifacts",
    "model_freeze_state",
    "narrative_events",
}


def _strict_mode() -> bool:
    return str(os.getenv("NORTHSTAR_STRICT_MODE", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _latest_ts(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for col in ["Date", "date", "timestamp", "datetime", "time", "intelligence_timestamp_str"]:
        if col in df.columns:
            dts = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
            if not dts.empty:
                return pd.Timestamp(dts.max())
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        idx = pd.to_datetime(pd.Series(df.index), errors="coerce", utc=True).dropna()
        if not idx.empty:
            return pd.Timestamp(idx.max())
    return None


def _payload_meta(value: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"status": "missing", "kind": type(value).__name__}
    if value is None:
        return meta
    if isinstance(value, pd.DataFrame):
        meta.update({
            "status": "ok_df" if not value.empty else "empty_df",
            "rows": int(len(value)),
            "cols": int(len(value.columns)),
            "columns": [str(c) for c in value.columns[:100]],
        })
        ts = _latest_ts(value)
        if ts is not None and not pd.isna(ts):
            now = pd.Timestamp.now(tz="UTC")
            age_hours = float((now - ts).total_seconds() / 3600.0)
            meta["latest_ts"] = ts.isoformat()
            meta["age_hours"] = round(age_hours, 3)
        return meta
    if isinstance(value, dict):
        meta.update({"status": "ok_dict" if value else "empty_dict", "keys": sorted(value.keys())[:200]})
        return meta
    if isinstance(value, list):
        meta.update({"status": "ok_list" if value else "empty_list", "len": len(value)})
        return meta
    if isinstance(value, str):
        meta.update({"status": "ok_str" if value else "empty_str", "len": len(value)})
        return meta
    meta.update({"status": "ok_value"})
    return meta


def _filter_payload(data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    if mode == "live":
        out = {k: v for k, v in data.items() if k in LIVE_KEYS}
        return out
    return dict(data)


@dataclass(frozen=True)
class ViewModelPaths:
    mode: str

    @property
    def payload_path(self) -> Path:
        return VIEW_MODEL_DIR / f"dashboard_view_model_{self.mode}.pkl"

    @property
    def meta_path(self) -> Path:
        return VIEW_MODEL_DIR / f"dashboard_view_model_{self.mode}.json"


def write_view_model(data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    mode = mode.strip().lower()
    if mode not in {"live", "research"}:
        raise ValueError(f"invalid mode: {mode}")

    VIEW_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    paths = ViewModelPaths(mode=mode)
    payload = _filter_payload(data, mode)
    dataset_meta = {k: _payload_meta(v) for k, v in payload.items()}

    meta = {
        "schema_version": "1.0.0",
        "generated_at": _now_iso(),
        "mode": mode,
        "strict_mode": _strict_mode(),
        "dataset_count": len(payload),
        "datasets": dataset_meta,
    }

    with paths.payload_path.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    paths.meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_view_model(mode: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    mode = mode.strip().lower()
    if mode not in {"live", "research"}:
        raise ValueError(f"invalid mode: {mode}")

    paths = ViewModelPaths(mode=mode)
    if not paths.payload_path.exists() or not paths.meta_path.exists():
        return None

    try:
        payload = pickle.loads(paths.payload_path.read_bytes())
        if not isinstance(payload, dict):
            return None
        meta = json.loads(paths.meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return None
    except Exception:
        return None

    return payload, meta


def dataset_age_hours(meta: Dict[str, Any], key: str) -> Optional[float]:
    ds = (meta.get("datasets") or {}).get(key)
    if not isinstance(ds, dict):
        return None
    age = ds.get("age_hours")
    try:
        return float(age)
    except Exception:
        return None
