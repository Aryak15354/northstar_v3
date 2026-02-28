#!/usr/bin/env python3
"""
📡 DASHBOARD DATA LOADER (REAL DATA ONLY)

Clean, production-safe snapshot loader for dashboards.
No mock/synthetic data is ever generated.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import streamlit as st
import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub
from src.dashboard.adapters.unified_dashboard_adapter import UnifiedDashboardAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = PROJECT_ROOT / "data/processed/cache/dashboard_snapshot.parquet"


def _safe_read_parquet(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def build_dashboard_snapshot() -> Dict[str, Any]:
    """
    Build a compact, real-data snapshot for fast dashboard loads.
    """
    hub = V3DataHub(PROJECT_ROOT)
    adapter = UnifiedDashboardAdapter()

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "market": {},
        "portfolio": {},
        "intelligence": {},
        "risk": {},
        "validation": {},
        "automation": {},
    }

    # Market / regime context
    market_df = hub.intelligent_market_state() or hub.market_state()
    if market_df is not None and not market_df.empty:
        df = market_df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date")
            latest = df.iloc[-1]
        elif "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp")
            latest = df.iloc[-1]
        else:
            latest = df.iloc[-1]
        snapshot["market"] = {
            "regime": latest.get("macro_regime") or latest.get("regime") or latest.get("market_regime"),
            "risk_on_probability": latest.get("risk_on_probability") or latest.get("risk_on"),
            "allowed_exposure": latest.get("allowed_exposure"),
            "macro_score": latest.get("macro_score"),
        }

    # Portfolio snapshot
    weights = hub.portfolio_weights()
    if weights is not None and not weights.empty:
        wdf = weights.copy()
        weight_col = None
        for c in ["weight", "final_weight", "w", "allocation"]:
            if c in wdf.columns:
                weight_col = c
                break
        if weight_col:
            w = pd.to_numeric(wdf[weight_col], errors="coerce").dropna()
            if not w.empty:
                snapshot["portfolio"] = {
                    "n_positions": int(len(wdf)),
                    "total_exposure": float(w.sum()),
                }

    # Intelligence + risk summaries (real observers)
    try:
        snapshot["intelligence"] = adapter.intelligence().intelligence_summary()
    except Exception:
        snapshot["intelligence"] = {}
    try:
        snapshot["risk"] = adapter.risk().risk_summary()
    except Exception:
        snapshot["risk"] = {}
    try:
        snapshot["validation"] = adapter.validation().validation_summary()
    except Exception:
        snapshot["validation"] = {}
    try:
        snapshot["automation"] = adapter.automation().automation_summary()
    except Exception:
        snapshot["automation"] = {}

    # Persist to parquet cache
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([snapshot]).to_parquet(SNAPSHOT_PATH, index=False)
    return snapshot


def build_live_snapshot() -> Dict[str, Any]:
    """Alias for build_dashboard_snapshot (kept for compatibility)."""
    return build_dashboard_snapshot()


@st.cache_data(ttl=300)
def load_unified_snapshot() -> Dict[str, Any]:
    """
    Load cached snapshot; rebuild if missing.
    """
    if not SNAPSHOT_PATH.exists():
        return build_dashboard_snapshot()

    df = _safe_read_parquet(SNAPSHOT_PATH)
    if df.empty:
        return build_dashboard_snapshot()

    try:
        row = df.iloc[-1].to_dict()
        return row
    except Exception:
        return build_dashboard_snapshot()


@st.cache_data(ttl=300)
def load_timeseries(file_path: str) -> pd.DataFrame:
    """Load time series data with caching (real data only)."""
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()

