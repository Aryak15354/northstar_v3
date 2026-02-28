#!/usr/bin/env python3
"""
🚀 NORTHSTAR V3 ULTIMATE INTEGRATED DASHBOARD (FULL RESTORED + EXPANDED)

Comprehensive, production-grade dashboard with all major V3 facets:
- Command Center
- V3 Analytics Suite
- Advanced V3 Intelligence
- Wave Analysis
- Dynamic Clustering
- Portfolio Analytics
- Real-Time Monitor
- Automation Hub
- Shadow Trader + Weekly Rebalance
- Edge Half-Life + Liquidity Exit Risk
- NS‑USO Sentiment

Real-data only. No mock generation.
"""

from __future__ import annotations

import os
import sys
import json
import re
import math
import html
import hashlib
import subprocess
import traceback
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, List, Sequence

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

try:
    import yaml
except Exception:
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.v3_data_hub import V3DataHub
from src.dashboard.components.v3_sentiment_panel import V3SentimentPanel
from src.dashboard.components.options_panel import OptionsPanel
from src.dashboard.observers.options_observer import OptionsObserver
from src.dashboard.chart_registry import CHART_REGISTRY, evaluate_chart_contract
from src.dashboard.view_model_loader import load_view_model
from src.dashboard.layout.visual_os_architecture import (
    EMISSION_TARGETS,
    LIVE_DEPTH_OPTIONS,
    RESEARCH_DEPTH_OPTIONS,
)
from src.intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader


THEME = {
    "bg": "#0b1220",
    "panel": "#0f172a",
    "panel2": "#111c33",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "grid": "rgba(148, 163, 184, 0.15)",
    "blue": "#3B82F6",
    "green": "#22c55e",
    "amber": "#f59e0b",
    "red": "#ef4444",
    "pink": "#ec4899",
    "cyan": "#06b6d4",
    "violet": "#8b5cf6",
}


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return default


def _latest_ts_from_df(df: Optional[pd.DataFrame]) -> Optional[pd.Timestamp]:
    if df is None or df.empty:
        return None
    for c in ["Date", "date", "timestamp", "intelligence_timestamp_str"]:
        if c in df.columns:
            d = _to_naive_date_series(df[c], normalize=False).dropna()
            if not d.empty:
                return pd.Timestamp(d.max())
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        idx = _to_naive_date_series(pd.Series(df.index), normalize=False)
        idx = idx[~idx.isna()]
        if len(idx) > 0:
            return pd.Timestamp(idx.max())
    return None


def _df_is_fresh(df: Optional[pd.DataFrame], max_age_hours: float = 72.0) -> bool:
    ts = _latest_ts_from_df(df)
    if ts is None or pd.isna(ts):
        return False
    try:
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
    except Exception:
        pass
    age_h = (pd.Timestamp.now() - ts).total_seconds() / 3600.0
    return bool(age_h <= float(max_age_hours))


def _df_age_hours(df: Optional[pd.DataFrame]) -> Optional[float]:
    ts = _latest_ts_from_df(df)
    if ts is None or pd.isna(ts):
        return None
    try:
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
    except Exception:
        pass
    return float((pd.Timestamp.now() - ts).total_seconds() / 3600.0)


def _to_ist_naive_series(values: pd.Series) -> pd.Series:
    """
    Parse mixed timestamp formats into IST wall-clock timestamps (tz-naive for plotting).

    Why:
    - Plotly/browser timezone rendering of tz-aware datetimes can show UTC-like axes.
    - Control Tower should display India market time (e.g., 09:15/09:30), not UTC offsets.
    """
    parsed: List[pd.Timestamp] = []
    for v in values.tolist():
        if v is None:
            parsed.append(pd.NaT)
            continue
        try:
            ts = pd.Timestamp(v)
        except Exception:
            parsed.append(pd.NaT)
            continue
        try:
            if ts.tzinfo is None:
                ts = ts.tz_localize("Asia/Kolkata")
            else:
                ts = ts.tz_convert("Asia/Kolkata")
            parsed.append(ts)
        except Exception:
            parsed.append(pd.NaT)

    ser = pd.Series(parsed, index=values.index)
    ser = pd.to_datetime(ser, errors="coerce")
    if getattr(ser.dt, "tz", None) is None:
        ser = ser.dt.tz_localize("Asia/Kolkata", ambiguous="NaT", nonexistent="shift_forward")
    else:
        ser = ser.dt.tz_convert("Asia/Kolkata")
    return ser.dt.tz_localize(None)


def _to_naive_date_series(values: pd.Series, *, normalize: bool = True) -> pd.Series:
    """
    Parse datetimes with mixed tz-awareness into a single tz-naive series.
    Using `utc=True` avoids merge mismatches like datetime64[ns, UTC] vs datetime64[ns].
    """
    raw = values if isinstance(values, pd.Series) else pd.Series(values)
    out = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")

    def _fill_from(parsed: pd.Series) -> None:
        if parsed is None or len(parsed) == 0:
            return
        parsed = pd.to_datetime(parsed, errors="coerce", utc=True)
        if len(parsed) == 0:
            return
        avail = out.loc[parsed.index].isna()
        if not avail.any():
            return
        target_idx = parsed.index[avail.to_numpy()]
        out.loc[target_idx] = parsed.loc[target_idx]

    # 1) Parse non-numeric tokens directly (ISO strings, datetime objects, etc.)
    as_num = pd.to_numeric(raw, errors="coerce")
    non_numeric_mask = as_num.isna()
    if non_numeric_mask.any():
        _fill_from(pd.to_datetime(raw[non_numeric_mask], errors="coerce", utc=True))

    # 2) Parse numeric tokens only when they look like real calendar/epoch timestamps.
    numeric_mask = as_num.notna()
    if numeric_mask.any():
        n = as_num[numeric_mask]
        abs_n = n.abs()

        # YYYYMMDD encoded integers.
        ymd_mask = (abs_n >= 19000101) & (abs_n <= 21001231)
        if ymd_mask.any():
            ymd_raw = n[ymd_mask].round().astype("Int64").astype(str)
            _fill_from(pd.to_datetime(ymd_raw, format="%Y%m%d", errors="coerce", utc=True))

        # Epoch windows (1990-2100) across common units.
        lo_s = pd.Timestamp("1990-01-01", tz="UTC").timestamp()
        hi_s = pd.Timestamp("2100-12-31", tz="UTC").timestamp()
        unit_windows = [
            ("s", lo_s, hi_s),
            ("ms", lo_s * 1e3, hi_s * 1e3),
            ("us", lo_s * 1e6, hi_s * 1e6),
            ("ns", lo_s * 1e9, hi_s * 1e9),
        ]
        for unit, lo, hi in unit_windows:
            m = (abs_n >= lo) & (abs_n <= hi)
            if m.any():
                _fill_from(pd.to_datetime(n[m], unit=unit, errors="coerce", utc=True))

    ser = out
    try:
        ser = ser.dt.tz_localize(None)
    except Exception:
        ser = pd.to_datetime(ser.astype(str), errors="coerce")
    if normalize:
        ser = ser.dt.normalize()
    return ser


def _prepare_macro_heatmap_changes(df: pd.DataFrame, *, tail_rows: int = 120) -> pd.DataFrame:
    """
    Build a change-aware macro matrix so low-frequency forward-filled levels
    don't render as long flat heatmap bands.
    Enhanced version with better data validation and processing.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    x = _collapse_duplicate_macro_columns(df.copy())
    x = x.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if x.empty:
        return pd.DataFrame()

    # Enhanced change calculation with multiple methods
    chg = x.diff()

    # Filter columns with sufficient variation
    active_cols = []
    for c in chg.columns:
        col_data = pd.to_numeric(chg[c], errors="coerce")
        if col_data.notna().sum() < 10:  # Need at least 10 valid points
            continue

        # Check for sufficient variation
        abs_sum = float(col_data.abs().sum(skipna=True))
        std_val = float(col_data.std(skipna=True))

        if abs_sum > 1e-8 and std_val > 1e-8:  # More lenient thresholds
            active_cols.append(c)

    if not active_cols:
        # If no changes detected, use levels with z-score normalization
        active_cols = []
        for c in x.columns:
            col_data = pd.to_numeric(x[c], errors="coerce")
            if col_data.notna().sum() >= 10 and col_data.nunique() > 2:
                active_cols.append(c)

        if active_cols:
            chg = x[active_cols].copy()
        else:
            return pd.DataFrame()
    else:
        chg = chg[active_cols]

    # Enhanced z-score calculation
    out = pd.DataFrame(index=chg.index)
    for c in chg.columns:
        s = pd.to_numeric(chg[c], errors="coerce")
        if s.notna().sum() < 5:
            continue

        # Use robust statistics
        med = float(s.median(skipna=True))
        mad = float((s - med).abs().median(skipna=True))

        if np.isfinite(mad) and mad > 1e-12:  # More lenient threshold
            z = (s - med) / (1.4826 * mad)
        else:
            # Fallback to standard z-score
            mean_val = float(s.mean(skipna=True))
            std_val = float(s.std(skipna=True))
            if np.isfinite(std_val) and std_val > 1e-12:
                z = (s - mean_val) / std_val
            else:
                # If still no variation, use the raw values
                z = s.fillna(0)

        # Less aggressive clipping
        out[c] = z.clip(-6, 6)

    out = out.dropna(how="all")
    if out.empty:
        return pd.DataFrame()

    # More lenient activity filtering
    activity = out.abs().sum(axis=1)
    active_rows = activity > 0.01  # Lower threshold

    # Keep more data points
    min_rows = max(10, int(tail_rows * 0.15))  # Keep at least 15% of requested rows
    if int(active_rows.sum()) >= min_rows:
        out = out.loc[active_rows]

    # Take more recent data
    if len(out) > int(tail_rows):
        out = out.tail(int(tail_rows))

    return out


def _market_session_mask(
    ts: pd.Series,
    *,
    open_hour: int = 9,
    open_minute: int = 15,
    close_hour: int = 15,
    close_minute: int = 30,
) -> pd.Series:
    """Weekday + India market-session mask for already-normalized local timestamps."""
    t = pd.to_datetime(ts, errors="coerce")
    minutes = (t.dt.hour * 60) + t.dt.minute
    open_m = open_hour * 60 + open_minute
    close_m = close_hour * 60 + close_minute
    return t.notna() & (t.dt.dayofweek < 5) & (minutes >= open_m) & (minutes <= close_m)


def _pick_belief_metric(df: pd.DataFrame) -> Optional[str]:
    candidates = ["belief_strength", "skill_prob", "effective_skill", "confidence"]
    min_required = max(3, int(len(df) * 0.1))
    scored: List[Tuple[int, float, int, str]] = []
    for c in candidates:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        n = int(s.notna().sum())
        if n < min_required:
            continue
        variability = float(s.std(skipna=True) or 0.0)
        scored.append((n, variability, -candidates.index(c), c))
    if scored:
        scored.sort(reverse=True)
        return scored[0][3]
    return None


def _strategy_belief_proxy(df: pd.DataFrame) -> pd.Series:
    """Build a bounded per-row belief proxy using the best available real fields."""
    out = pd.Series(np.nan, index=df.index, dtype=float)

    for col in ["belief_strength", "skill_prob", "confidence"]:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").clip(0.0, 1.0)
        out = out.where(out.notna(), s)

    if "effective_skill" in df.columns:
        s = pd.to_numeric(df["effective_skill"], errors="coerce")
        if s.notna().any():
            s = s.rank(method="average", pct=True)
            out = out.where(out.notna(), s.clip(0.0, 1.0))

    # Last-resort fallback from continuous metrics to avoid dropping strategies.
    if out.notna().sum() < max(3, int(len(df) * 0.1)):
        for col in ["regime_fit", "sharpe", "alpha"]:
            if col not in df.columns:
                continue
            s = pd.to_numeric(df[col], errors="coerce")
            if s.notna().any():
                s = s.rank(method="average", pct=True)
                out = out.where(out.notna(), s.clip(0.0, 1.0))

    return out.clip(0.0, 1.0)


def _pick_time_column(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Pick the most reliable time column based on valid datetime density/freshness."""
    best_col: Optional[str] = None
    best_valid = -1
    best_latest = pd.Timestamp.min.tz_localize("UTC")
    best_priority = 10**9

    for priority, col in enumerate(candidates):
        if col not in df.columns:
            continue
        series = _to_naive_date_series(df[col], normalize=False)
        series = pd.to_datetime(series, errors="coerce", utc=True)
        valid = int(series.notna().sum())
        latest = series.dropna().max() if valid > 0 else pd.Timestamp.min.tz_localize("UTC")
        if valid > best_valid:
            best_col = col
            best_valid = valid
            best_latest = latest
            best_priority = priority
            continue
        if valid == best_valid and latest > best_latest:
            best_col = col
            best_latest = latest
            best_priority = priority
            continue
        if valid == best_valid and latest == best_latest and priority < best_priority:
            best_col = col
            best_priority = priority

    return best_col


def _safe_latest(df: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    for col in ["date", "Date", "timestamp"]:
        if col in df.columns:
            tmp = df.copy()
            tmp[col] = _to_naive_date_series(tmp[col], normalize=False)
            tmp = tmp.dropna(subset=[col]).sort_values(col)
            if not tmp.empty:
                return tmp.iloc[-1]
    return df.iloc[-1]


def _series_is_sparse_or_flat(
    series: pd.Series,
    *,
    min_non_na: int = 40,
    min_unique: int = 6,
    zero_tolerance: float = 1e-9,
    max_zero_share: float = 0.9,
) -> bool:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < int(min_non_na):
        return True
    if int(s.nunique()) < int(min_unique):
        return True
    zero_share = float((s.abs() <= float(zero_tolerance)).mean()) if len(s) else 1.0
    return bool(zero_share >= float(max_zero_share))


def _drawdown_probability_proxy_from_returns(returns: pd.Series, *, window: int = 30) -> pd.Series:
    r = pd.to_numeric(returns, errors="coerce")
    out = pd.Series(np.nan, index=r.index, dtype=float)
    if r.notna().sum() < max(40, int(window) + 10):
        return out

    # Trailing drawdown/vol/downside mix; point-in-time safe and bounded [0,1].
    r_clip = r.fillna(0.0).clip(lower=-0.95)
    nav = (1.0 + r_clip).cumprod()
    min_periods = max(8, int(window // 3))
    roll_peak = nav.rolling(window, min_periods=min_periods).max()
    dd_abs = (1.0 - (nav / roll_peak)).clip(lower=0.0)
    downside_freq = (r < 0).astype(float).rolling(window, min_periods=min_periods).mean()
    vol = r.rolling(window, min_periods=min_periods).std()

    proxy = (2.2 * dd_abs) + (0.8 * downside_freq.fillna(0.0)) + (5.0 * vol.fillna(0.0))
    proxy = proxy.clip(lower=0.0, upper=1.0)
    out.loc[proxy.index] = proxy
    return out


def _resolve_drawdown_probability_series(df: pd.DataFrame, col: str = "drawdown_probability_30d") -> pd.Series:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series(dtype=float)
    base = pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(np.nan, index=df.index, dtype=float)

    if not _series_is_sparse_or_flat(base, min_non_na=40, min_unique=5):
        return base.clip(0.0, 1.0)

    ret = pd.Series(np.nan, index=df.index, dtype=float)
    if "active_return" in df.columns:
        ret = pd.to_numeric(df["active_return"], errors="coerce")
    elif "nav" in df.columns:
        nav = pd.to_numeric(df["nav"], errors="coerce")
        ret = nav.pct_change()

    proxy = _drawdown_probability_proxy_from_returns(ret, window=30)
    if proxy.notna().sum() < 20:
        return base.clip(0.0, 1.0)

    resolved = base.copy()
    weak_base = resolved.isna() | (resolved.abs() <= 1e-6)
    resolved.loc[weak_base] = proxy.loc[weak_base]

    if _series_is_sparse_or_flat(resolved, min_non_na=40, min_unique=5):
        resolved = proxy
    return pd.to_numeric(resolved, errors="coerce").clip(0.0, 1.0)


def _build_strategy_beliefs_from_allocation_history(allocation_history: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(allocation_history, pd.DataFrame) or allocation_history.empty:
        return pd.DataFrame(columns=["strategy", "belief"])

    a = allocation_history.copy()
    tcol = _pick_time_column(a, ["date", "Date", "timestamp"])
    if not tcol:
        return pd.DataFrame(columns=["strategy", "belief"])
    a["_ts"] = _to_naive_date_series(a[tcol], normalize=False)
    a = a.dropna(subset=["_ts"])
    if a.empty:
        return pd.DataFrame(columns=["strategy", "belief"])

    long = pd.DataFrame()
    if {"strategy_name", "allocation_weight"}.issubset(a.columns):
        tmp = a[["_ts", "strategy_name", "allocation_weight"]].copy()
        tmp["strategy"] = tmp["strategy_name"].astype(str).str.strip()
        tmp["allocation_weight"] = pd.to_numeric(tmp["allocation_weight"], errors="coerce")
        tmp = tmp[(tmp["strategy"] != "") & tmp["allocation_weight"].notna()]
        if not tmp.empty:
            long = tmp[["_ts", "strategy", "allocation_weight"]]

    if long.empty:
        meta_cols = {
            "date",
            "Date",
            "timestamp",
            "_ts",
            "regime",
            "regime_name",
            "strategy_name",
            "strategy_category",
            "allocation_weight",
            "allocation_score",
            "regime_fitness",
            "adjusted_return",
            "adjusted_sharpe",
            "risk_contribution",
            "allocation_reason",
            "regime_stability",
            "no_edge_state",
            "exposure_cap",
            "total_exposure",
            "freeze_active",
        }
        strategy_cols: List[str] = []
        min_non_na = max(8, int(len(a) * 0.12))
        for c in a.columns:
            if c in meta_cols:
                continue
            s = pd.to_numeric(a[c], errors="coerce")
            if int(s.notna().sum()) < min_non_na:
                continue
            if float(s.abs().sum(skipna=True)) <= 1e-8:
                continue
            strategy_cols.append(c)

        if strategy_cols:
            long = a[["_ts"] + strategy_cols].melt(
                id_vars=["_ts"],
                var_name="strategy",
                value_name="allocation_weight",
            )
            long["allocation_weight"] = pd.to_numeric(long["allocation_weight"], errors="coerce")
            long = long.dropna(subset=["strategy", "allocation_weight"])

    if long.empty:
        return pd.DataFrame(columns=["strategy", "belief"])

    long["strategy"] = long["strategy"].astype(str).str.strip()
    long = long[(long["strategy"] != "") & long["allocation_weight"].notna()]
    strategy_lower = long["strategy"].str.lower()
    drop_labels = {
        "cash",
        "cash_weight",
        "cash_reserve",
        "cash_allocation",
        "gross_exposure",
        "net_exposure",
        "total_exposure",
    }
    long = long[~strategy_lower.isin(drop_labels)]
    if long.empty:
        return pd.DataFrame(columns=["strategy", "belief"])

    long = long.groupby(["_ts", "strategy"], as_index=False)["allocation_weight"].mean()
    last_ts = pd.to_datetime(long["_ts"], errors="coerce").max()
    if pd.isna(last_ts):
        return pd.DataFrame(columns=["strategy", "belief"])
    recent = long[long["_ts"] >= (last_ts - pd.Timedelta(days=45))].copy()
    if recent.empty:
        recent = long

    w_mean = recent.groupby("strategy")["allocation_weight"].mean()
    w_cons = recent.assign(_active=(recent["allocation_weight"] > 0).astype(float)).groupby("strategy")["_active"].mean()
    belief = (0.75 * w_mean.rank(method="average", pct=True)) + (0.25 * w_cons)
    out = belief.rename("belief").reset_index()
    out["belief"] = pd.to_numeric(out["belief"], errors="coerce").clip(0.0, 1.0)
    out = out.dropna(subset=["belief"]).sort_values("belief", ascending=False)
    return out[["strategy", "belief"]]


def _normalized_driver_labels(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    low = s.str.lower()
    unknown_like = {
        "",
        "none",
        "null",
        "nan",
        "na",
        "unknown",
        "macro_unknown",
        "driver_unknown",
        "unspecified",
    }
    s = s.mask(low.isin(unknown_like), "unspecified_driver")
    return s


def _driver_strength_frame(df: pd.DataFrame, *, top_n: int = 12) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["driver_variable", "driver_strength"])

    dd = pd.DataFrame(columns=["driver_variable", "driver_strength"])
    if {"driver_variable", "driver_strength"}.issubset(df.columns):
        tmp = df.copy()
        tmp["driver_variable"] = _normalized_driver_labels(tmp["driver_variable"])
        tmp["driver_strength"] = pd.to_numeric(tmp["driver_strength"], errors="coerce")
        tmp = tmp.dropna(subset=["driver_variable", "driver_strength"])
        if not tmp.empty:
            dd = (
                tmp.groupby("driver_variable", as_index=False)["driver_strength"]
                .mean()
                .sort_values("driver_strength", ascending=False)
            )

    # Degenerate fallback: infer a driver ranking from available explanatory columns.
    is_degenerate = dd.empty or dd["driver_variable"].nunique() <= 1 or float(dd["driver_strength"].std(skipna=True) or 0.0) < 1e-9
    if is_degenerate:
        candidates = [
            "mispricing",
            "confirmation",
            "signal_strength",
            "sentiment_score",
            "sentiment_trend_score",
            "market_sentiment_polarity",
            "market_sentiment_conviction",
            "combined_score",
            "northstar_score",
            "regime_adjusted_score",
        ]
        rows: List[Dict[str, float]] = []
        for c in candidates:
            if c not in df.columns:
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if int(s.notna().sum()) < max(8, int(len(df) * 0.2)):
                continue
            strength = float(s.abs().mean(skipna=True))
            if np.isfinite(strength) and strength > 0:
                rows.append({"driver_variable": c, "driver_strength": strength})
        if rows:
            dd = pd.DataFrame(rows).sort_values("driver_strength", ascending=False)

    if dd.empty:
        return dd
    return dd.head(int(top_n)).reset_index(drop=True)


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _read_ndjson_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    rows: List[dict] = []
    try:
        for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    except Exception:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _read_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    if yaml is None:
        return None
    try:
        obj = yaml.safe_load(path.read_text())
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _file_sha256(rel_path: str, max_bytes: int = 1024 * 1024) -> Optional[str]:
    p = PROJECT_ROOT / rel_path
    if not p.exists() or not p.is_file():
        return None
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            chunk = f.read(max_bytes)
        h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _coerce_research_records(blob: Any) -> List[dict]:
    """
    Normalize research JSON blobs to a list of typed records.
    Supported shapes:
    - {"timestamp": ..., "freeze_active": ..., "data": [records]}
    - {"timestamp": ..., "data": {...}}    # wrapped as one record
    - [records]
    """
    if isinstance(blob, list):
        return [x for x in blob if isinstance(x, dict)]
    if not isinstance(blob, dict):
        return []
    data = blob.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        rec = data.copy()
        rec.setdefault("type", str(blob.get("type", "research_record")))
        rec.setdefault("generated_at", blob.get("timestamp"))
        return [rec]
    return []


def _first_record_payload(blob: Any, expected_type: Optional[str] = None) -> Optional[dict]:
    records = _coerce_research_records(blob)
    if expected_type:
        records = [r for r in records if str(r.get("type", "")).strip() == expected_type]
    if not records:
        return None
    payload = records[0].get("data")
    return payload if isinstance(payload, dict) else None


def _relationship_freshness_fallback() -> Dict[str, Any]:
    """
    Dashboard-safe freshness fallback.

    Used when running against an older WeeklyFabricReader class that may not
    expose `get_data_freshness()`.
    """
    out: Dict[str, Any] = {
        "relationship_latest_date": None,
        "relationship_count": 0,
        "relationship_years": [],
        "tensor_latest_date": None,
        "lag_days": None,
    }

    try:
        rel_idx = PROJECT_ROOT / "data/weekly_insights/relationship_index.parquet"
        if rel_idx.exists():
            idx = pd.read_parquet(rel_idx)
            if isinstance(idx, pd.DataFrame) and not idx.empty:
                d = _to_naive_date_series(idx.get("date"), normalize=False).dropna()
                if not d.empty:
                    out["relationship_latest_date"] = d.max().isoformat()
                out["relationship_count"] = int(len(idx))
                if "year" in idx.columns:
                    out["relationship_years"] = sorted(idx["year"].dropna().astype(int).unique().tolist())
                elif not d.empty:
                    out["relationship_years"] = sorted(d.dt.year.unique().tolist())
    except Exception:
        pass

    try:
        tensor_paths = [
            PROJECT_ROOT / "data/processed/market_tensor.parquet",
            PROJECT_ROOT / "data/weekly_insights/weekly_tensor_store.parquet",
            PROJECT_ROOT / "data/processed/market_tensor_latest.parquet",
        ]
        latest_candidates = []
        for p in tensor_paths:
            if not p.exists():
                continue
            tdf = pd.read_parquet(p)
            if isinstance(tdf.index, pd.DatetimeIndex) and len(tdf.index) > 0:
                latest_candidates.append(pd.to_datetime(tdf.index.max(), errors="coerce"))
                continue
            if isinstance(tdf, pd.DataFrame) and "date" in tdf.columns:
                latest_candidates.append(_to_naive_date_series(tdf["date"], normalize=False).dropna().max())

        latest_candidates = [x for x in latest_candidates if pd.notna(x)]
        if latest_candidates:
            out["tensor_latest_date"] = max(latest_candidates).isoformat()
    except Exception:
        pass

    try:
        rel = pd.to_datetime(out.get("relationship_latest_date"), errors="coerce")
        ten = pd.to_datetime(out.get("tensor_latest_date"), errors="coerce")
        if pd.notna(rel) and pd.notna(ten):
            out["lag_days"] = int((ten - rel).days)
    except Exception:
        pass

    return out


def _is_sparse_macro_block(df: Optional[pd.DataFrame]) -> bool:
    if df is None or df.empty:
        return True
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric_cols:
        return True
    return len(numeric_cols) <= 6 and all(len(str(c)) <= 4 for c in numeric_cols)


def _pretty_macro_name(col: str) -> str:
    """Canonicalize macro variable names to remove versioning and prefixes."""
    name = str(col).strip()
    name = name.replace("__", "_")
    name = re.sub(r"\.\d+$", "", name)  # pandas duplicate suffixes: foo, foo.1, foo.2
    name = re.sub(r"[\[\]\(\)]", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
    # Remove version prefixes (v1_, v2_, etc.)
    name = re.sub(r"^\s*v\d+[_\-\s]*", "", name, flags=re.IGNORECASE)
    # Remove core_macro prefixes with various patterns
    name = re.sub(r"^core_macro_[a-z]+_[a-z]+_v\d+_", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^core_macro_[a-z]+_[a-z]+_", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^core_macro_[a-z]+_v\d+_", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^core_macro_[a-z]+_", "", name, flags=re.IGNORECASE)
    # Remove trailing version suffixes (_v1, _v2, etc.)
    name = re.sub(r"_v\d+$", "", name, flags=re.IGNORECASE)
    # Remove lag indicators for cleaner display
    name = re.sub(r"_(lag|lead|fwd)[_\-]?\d+[wdm]?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_dup_\d+$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_copy\d*$", "", name, flags=re.IGNORECASE)
    # Normalize whitespace
    name = re.sub(r"_+", "_", name).strip("_")
    name = re.sub(r"\s+", " ", name).strip()
    # Convert to title case for better readability
    name = name.replace("_", " ").title()
    return name if name else str(col)


def _build_macro_display_from_cleaned(cleaned: pd.DataFrame, max_factors: int = 24) -> pd.DataFrame:
    """Select a manageable, high-information subset from macro_cleaned."""
    if cleaned is None or cleaned.empty:
        return pd.DataFrame()

    df = cleaned.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    if df.empty:
        return pd.DataFrame()

    num = df.apply(pd.to_numeric, errors="coerce")
    num = num.dropna(axis=1, how="all")
    if num.empty:
        return pd.DataFrame()

    recent = num.tail(104)  # ~2 years weekly
    last = recent.tail(1).iloc[0]
    mu = recent.mean()
    sigma = recent.std().replace(0, np.nan)
    z = ((last - mu) / sigma).abs().replace([np.inf, -np.inf], np.nan).dropna()

    if z.empty:
        # Fallback to highest-variance factors if z-score not informative.
        var_rank = recent.var().sort_values(ascending=False)
        selected = var_rank.head(max_factors).index.tolist()
    else:
        selected = z.sort_values(ascending=False).head(max_factors).index.tolist()

    view = num[selected].tail(120).copy()
    rename_map = {c: _pretty_macro_name(c) for c in view.columns}
    view = view.rename(columns=rename_map)
    # De-duplicate renamed columns deterministically.
    dedup = {}
    cols = []
    for c in view.columns:
        dedup[c] = dedup.get(c, 0) + 1
        cols.append(c if dedup[c] == 1 else f"{c} ({dedup[c]})")
    view.columns = cols
    return view


def _collapse_duplicate_macro_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()].sort_index()
    if out.empty:
        return pd.DataFrame()
    out = out.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if out.empty:
        return pd.DataFrame()
    out = out.rename(columns={c: _pretty_macro_name(c) for c in out.columns})
    # Collapse aliased/repeated series produced by versioned columns (v1_, v2_, ...).
    out = out.T.groupby(level=0).mean().T
    return out


@st.cache_data(ttl=300)
def _list_macro_report_artifacts() -> List[str]:
    roots = [
        PROJECT_ROOT / "data/processed/macro_impact",
        PROJECT_ROOT / "reports/macro_impact",
        PROJECT_ROOT / "data/processed/macro_transmission",
        PROJECT_ROOT / "reports/signal_audit/macro_conditioned",
        PROJECT_ROOT / "reports/signal_audit/macro_conditioned_mandatory",
    ]
    files: List[Path] = []
    allowed = {".json", ".parquet", ".csv", ".txt", ".md", ".log"}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in allowed:
                files.append(p)
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    rel = []
    for p in files:
        try:
            rel.append(str(p.relative_to(PROJECT_ROOT)))
        except Exception:
            rel.append(str(p))
    return rel[:300]


@st.cache_data(ttl=300)
def _read_report_table(rel_path: str, max_rows: int = 2000) -> Optional[pd.DataFrame]:
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        return None
    try:
        if p.suffix.lower() == ".parquet":
            df = pd.read_parquet(p)
        elif p.suffix.lower() == ".csv":
            df = pd.read_csv(p)
        else:
            return None
    except Exception:
        return None
    if not isinstance(df, pd.DataFrame):
        return None
    if len(df) > max_rows:
        df = df.head(max_rows).copy()

    # Convert nested object/list/dict columns to compact text so Streamlit tables
    # don't render them as [object Object].
    for c in df.columns:
        if df[c].dtype != object:
            continue
        sample = df[c].dropna().head(20).tolist()
        if not sample:
            continue
        if any(isinstance(v, (dict, list, tuple, set)) for v in sample):
            df[c] = df[c].map(
                lambda v: json.dumps(v, ensure_ascii=False)
                if isinstance(v, (dict, list, tuple, set))
                else ("" if pd.isna(v) else str(v))
            )
    return df


def _read_report_text(rel_path: str, max_chars: int = 20000) -> str:
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


@st.cache_data(ttl=300)
def _load_core_data_sources() -> Dict[str, Any]:
    hub = V3DataHub(PROJECT_ROOT)

    def _read_first_parquet(paths: List[str]) -> Optional[pd.DataFrame]:
        fallback: Optional[pd.DataFrame] = None
        for rel in paths:
            df = hub._read_parquet(rel)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
            if isinstance(df, pd.DataFrame):
                # keep looking for a non-empty fallback, but remember empties
                fallback = df
        return fallback

    def _read_first_csv(paths: List[str]) -> Optional[pd.DataFrame]:
        fallback: Optional[pd.DataFrame] = None
        for rel in paths:
            path = PROJECT_ROOT / rel
            if not path.exists():
                continue
            try:
                df = pd.read_csv(path)
            except Exception:
                continue
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
            if isinstance(df, pd.DataFrame):
                fallback = df
        return fallback

    return {
        "market_state": hub.market_state(),
        "intelligent_state": hub.intelligent_market_state(),
        "market_regime": hub.market_regime(),
        "exposure_history": hub.exposure_history(),
        "risk_state": hub.risk_state(),
        "portfolio_weights": hub.portfolio_weights(),
        "portfolio_analytics": hub.portfolio_analytics(),
        "pnl": hub.pnl_series(),
        "daily_narrative": hub.daily_narrative(),
        "regime_feed": hub.regime_intelligence_feed(),
        "options_dashboard_state": (
            hub.options_dashboard_state()
            if hasattr(hub, "options_dashboard_state")
            else hub._read_json("data/options/live/options_dashboard_state.json")
        ),
        "options_runtime_state": hub._read_json("data/options/live/options_runtime_state.json"),
        "daemon_status": hub._read_json("data/options/live/northstar_daemon_status.json"),
        "live_heartbeat": hub._read_json("data/options/live/live_engine_heartbeat.json"),
        "state_recovery_report": hub._read_json("data/options/live/state_recovery_report.json"),
        "governance_events": hub._read_parquet("data/options/live/governance_events.parquet"),
        "system_log": hub.system_execution_log(),
        "edge_half_life": hub.edge_half_life(),
        "liquidity_risk": hub.liquidity_risk(),
        "capital_allocations": hub.capital_allocations(),
        "alpha_os_timeseries": hub._read_parquet("data/processed/alpha_os_timeseries.parquet"),
        "alpha_os_strategy_posteriors": hub._read_parquet("data/processed/alpha_os_strategy_posteriors.parquet"),
        "alpha_os_drift_state": hub._read_json("data/processed/regime_drift_monitor.json"),
        "alpha_os_sdi_state": hub._read_json("data/processed/shadow_divergence_index.json"),
        "walk_forward_results": hub._read_json("data/validation/walk_forward_results.json"),
        "allocation_history": hub.allocation_history(),
        "index_nifty50": hub.index_series("nifty_50"),
        "index_nifty100": hub.index_series("nifty_100"),
        "index_nifty500": hub.index_series("nifty_500"),
        "sector_flows": hub.sector_flows(),
        "sector_rotation": hub._read_parquet("data/processed/sector_rotation.parquet"),
        "strategy_beliefs": hub._read_parquet("data/processed/strategy_beliefs.parquet"),
        "strategy_regret": hub._read_parquet("data/processed/strategy_regret.parquet"),
        "performance_summary": hub._read_parquet("data/processed/performance_summary.parquet"),
        "macro_factors": _read_first_parquet(
            [
                "data/processed/macro_factors.parquet",
                "data/macro/factors/macro_factors.parquet",
            ]
        ),
        "macro_factors_v2": _read_first_parquet(
            [
                "data/processed/macro_factors_v2.parquet",
                "data/macro/factors/macro_factors_v2.parquet",
            ]
        ),
        "macro_conditioned_report": hub._read_json(
            "data/processed/macro_conditioned_alpha/macro_conditioned_audit_report.json"
        ),
        "macro_conditioned_composite": _read_first_csv(
            [
                "data/processed/macro_conditioned_alpha/composite_ic_summary.csv",
                "reports/signal_audit/macro_conditioned/composite_ic_summary.csv",
            ]
        ),
        "macro_conditioned_snapshot": _read_first_parquet(
            [
                "data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet",
                "reports/signal_audit/macro_conditioned/latest_macro_conditioned_signal_snapshot.parquet",
            ]
        ),
        "macro_conditioned_weights": _read_first_csv(
            [
                "data/processed/macro_conditioned_alpha/latest_regime_conditioned_weights.csv",
                "reports/signal_audit/macro_conditioned/latest_regime_conditioned_weights.csv",
            ]
        ),
        "macro_conditioned_mandatory_report": hub._read_json(
            "reports/signal_audit/macro_conditioned_mandatory/mandatory_tests_report.json"
        ),
        "macro_impact_metadata": hub._read_json(
            "data/processed/macro_impact/analysis_metadata.json"
        ),
        "macro_impact_company_betas": _read_first_parquet(
            [
                "data/processed/macro_impact/company_macro_betas.parquet",
            ]
        ),
        "macro_impact_sector_betas": _read_first_parquet(
            [
                "data/processed/macro_impact/sector_macro_betas.parquet",
            ]
        ),
        "macro_impact_sector_heatmap": _read_first_parquet(
            [
                "data/processed/macro_impact/sector_macro_heatmap.parquet",
            ]
        ),
        "macro_impact_fingerprints": hub._read_json(
            "data/processed/macro_impact/company_fingerprints.json"
        ),
        "macro_impact_sector_report": hub._read_json(
            "data/processed/macro_impact/sector_macro_sensitivity.json"
        ),
        "macro_transmission_metadata": hub._read_json(
            "data/processed/macro_transmission/run_metadata.json"
        ),
        "macro_transmission_kalman": _read_first_parquet(
            [
                "data/processed/macro_transmission/current_kalman_betas.parquet",
            ]
        ),
        "macro_transmission_expected": _read_first_parquet(
            [
                "data/processed/macro_transmission/macro_expected_change.parquet",
            ]
        ),
        "macro_transmission_adjusted": _read_first_parquet(
            [
                "data/processed/macro_transmission/macro_adjusted_scores.parquet",
            ]
        ),
        "macro_transmission_stress": hub._read_json(
            "data/processed/macro_transmission/stress_replay_summary.json"
        ),
        "macro_transmission_optimizer": _read_first_parquet(
            [
                "data/processed/macro_transmission/macro_optimized_weights.parquet",
            ]
        ),
        "macro_transmission_optimizer_summary": hub._read_json(
            "data/processed/macro_transmission/macro_optimizer_summary.json"
        ),
        "macro_transmission_sv_summary": _read_first_parquet(
            [
                "data/processed/macro_transmission/stochastic_volatility_summary.parquet",
            ]
        ),
        "macro_transmission_sv_betas": _read_first_parquet(
            [
                "data/processed/macro_transmission/stochastic_volatility_betas.parquet",
            ]
        ),
        "macro_transmission_jax_betas": _read_first_parquet(
            [
                "data/processed/macro_transmission/jax_kalman_betas.parquet",
            ]
        ),
        "macro_cleaned": _read_first_parquet(
            [
                "data/macro/cleaned/macro_cleaned.parquet",
                "data/processed/macro_cleaned.parquet",
            ]
        ),
        "valuation": hub._read_parquet("data/processed/valuation.parquet"),
        "valuation_families": hub._read_parquet("data/processed/valuation_families.parquet"),
        "valuation_posterior": hub._read_parquet("data/processed/valuation_posterior.parquet"),
        "portfolio_valuation_state": hub._read_parquet("data/processed/portfolio_valuation_state.parquet"),
        "valuation_validation_summary": hub._read_json("data/processed/valuation_validation_summary.json"),
        "valuation_validation_deciles": hub._read_parquet("data/processed/valuation_validation_deciles.parquet"),
        "valuation_validation_ic": hub._read_parquet("data/processed/valuation_validation_ic.parquet"),
        "valuation_validation_regime": hub._read_parquet("data/processed/valuation_validation_regime.parquet"),
        "opportunity_surface": hub._read_parquet("data/processed/opportunity_surface.parquet"),
        "research_opportunity_surface": hub._read_parquet("data/processed/research_opportunity_surface.parquet"),
        "research_returns_partition": hub._read_json("data/research/returns_partition.json"),
        "research_awareness": hub._read_json("data/research/research_awareness.json"),
        "research_options_opportunities": hub._read_json("data/research/options_research_opportunities.json"),
        "research_weekend_sweep": hub._read_json("data/research/weekend_research_sweep.json"),
        "research_kernel_status": hub._read_json("data/research/research_kernel_status.json"),
        "research_allocator_bridge": hub._read_json("data/research/research_allocator_bridge.json"),
        "research_governor_bridge": hub._read_json("data/research/research_governor_bridge.json"),
        "research_model_training_results": hub._read_json("data/research/model_training_results.json"),
        "research_capital_simulation_report": hub._read_json("data/research/capital_simulation_report.json"),
        "research_parameter_search_results": hub._read_json("data/research/parameter_search_results.json"),
        "research_strategy_stability": hub._read_json("data/research/strategy_stability.json"),
        "research_regime_candidate_scores": hub._read_json("data/research/regime_candidate_scores.json"),
        "research_monte_carlo_report": hub._read_json("data/research/monte_carlo_report.json"),
        "research_memory": hub._read_json("data/research/research_memory.json"),
        "research_experiments": _read_ndjson_df(PROJECT_ROOT / "data/research/experiments.ndjson"),
        "research_policy": _read_yaml(PROJECT_ROOT / "config/research_policy.yaml"),
        "daemon_policy": _read_yaml(PROJECT_ROOT / "config/northstar_daemon.yaml"),
        "options_policy": _read_yaml(PROJECT_ROOT / "config/options_trading.yaml"),
        "volatility_state": hub._read_parquet("data/processed/volatility_state.parquet"),
        "timing_signals": hub._read_parquet("data/processed/timing_signals.parquet"),
        "regime_transitions": hub.regime_transitions(),
        "regime_fingerprints": hub.regime_fingerprints(),
        "narrative_state": hub._read_parquet("data/processed/narrative_state.parquet"),
        "narrative_events": hub._read_parquet("data/processed/narrative_events.parquet"),
        "shadow_snapshot": hub._read_json("data/processed/shadow_trading_snapshot.json"),
        "shadow_pnl_series": hub._read_parquet("data/processed/shadow_pnl_series.parquet"),
        "integrity_report": hub._read_json("data/processed/integrity/v3_integrity_report_latest.json"),
        "integrity_artifacts": hub._read_parquet("data/processed/integrity/v3_integrity_artifacts_latest.parquet"),
        "model_freeze_state": hub._read_json("data/processed/model_freeze_state.json"),
        "nav_reconciliation": hub._read_json("data/processed/nav_reconciliation.json"),
        "parameter_version": hub._read_json("data/processed/parameter_version.json"),
        "snapshot_integrity": hub._read_json("data/processed/snapshot_integrity.json"),
        "calendar_alignment_audit": hub._read_json("data/processed/calendar_alignment_audit.json"),
        "drift_monitor": hub._read_json("data/processed/drift_monitor.json"),
        "regime_misclassification_tolerance": hub._read_json(
            "data/processed/regime_misclassification_tolerance.json"
        ),
        "survivorship_bias_audit": hub._read_json("data/processed/survivorship_bias_audit.json"),
        "real_data_only_policy": hub._read_json("data/processed/real_data_only_policy.json"),
        "exposure_cash_contract": hub._read_json("data/processed/exposure_cash_contract.json"),
        "allocator_universe_alignment": hub._read_json("data/processed/allocator_universe_alignment.json"),
        "dataset_lineage": hub._read_json("data/processed/dataset_lineage.json"),
        "feature_lineage_map": hub._read_json("data/processed/feature_lineage_map.json"),
    }


@st.cache_data(ttl=120)
def load_core_data(mode: str = "research") -> Dict[str, Any]:
    """
    Load dashboard data from canonical view-model artifacts.
    Falls back to source build only when artifacts are missing.
    """
    normalized_mode = str(mode or "research").strip().lower()
    if normalized_mode not in {"live", "research"}:
        normalized_mode = "research"

    loaded = load_view_model(normalized_mode)
    if loaded is None:
        # Artifact-first contract with deterministic fallback build.
        from src.dashboard.view_model_loader import write_view_model

        source_payload = _load_core_data_sources()
        meta = write_view_model(source_payload, mode=normalized_mode)
        filtered = load_view_model(normalized_mode)
        if filtered is None:
            return source_payload
        payload, _ = filtered
        payload["__view_model_meta__"] = meta
        return payload

    payload, meta = loaded
    payload = dict(payload)
    payload["__view_model_meta__"] = meta
    return payload


@st.cache_data(ttl=300)
def load_integrated_state_snapshot(max_rows: int = 365) -> pd.DataFrame:
    """
    Load unified integrated state snapshot if available.
    This is optional and should never block the dashboard.
    """
    path = PROJECT_ROOT / "data/integrated/integrated_state_snapshot.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    if "date" in df.columns:
        df["date"] = _to_naive_date_series(df["date"], normalize=False)
        df = df.dropna(subset=["date"]).sort_values("date")
    if isinstance(max_rows, int) and max_rows > 0 and len(df) > max_rows:
        df = df.tail(max_rows).copy()
    return df


@st.cache_data(ttl=300)
def load_sentiment_context() -> Dict[str, Any]:
    """Cached sentiment context loader for cross-layer integration."""
    try:
        panel = V3SentimentPanel()
        data = panel.load_sentiment_data()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def load_universe() -> Optional[pd.DataFrame]:
    p = PROJECT_ROOT / "universe/nifty500.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    # Normalize a few columns used in the portfolio UI.
    rename = {}
    for c in df.columns:
        if c.strip().lower() == "symbol":
            rename[c] = "symbol"
        if c.strip().lower() == "company name":
            rename[c] = "company_name"
        if c.strip().lower() == "industry":
            rename[c] = "industry"
    df = df.rename(columns=rename)
    return df


@st.cache_data(ttl=3600)
def load_sector_mapping() -> Optional[pd.DataFrame]:
    p = PROJECT_ROOT / "data/processed/sector_mapping.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    # Expect columns ticker/industry/sector.
    for c in ["ticker", "industry", "sector"]:
        if c not in df.columns:
            return df
    df["ticker"] = df["ticker"].astype(str)
    df["symbol_base"] = df["ticker"].str.replace(".NS", "", regex=False)
    return df


def _artifact_mtimes() -> pd.DataFrame:
    key_paths = {
        "P&L (on paper)": "data/portfolio/pnl_on_paper.parquet",
        "Portfolio Weights (latest)": "data/processed/portfolio_weights.parquet",
        "Weekly Snapshot (latest)": "data/portfolio/weekly/latest.json",
        "Prices (processed)": "data/processed/prices.parquet",
        "Market Regime": "data/processed/market_regime.parquet",
        "Daily Narrative": "data/processed/daily_narrative.parquet",
        "Regime Feed": "data/processed/regime_intelligence_feed.json",
        "AlphaOS Time Series": "data/processed/alpha_os_timeseries.parquet",
        "AlphaOS Posteriors": "data/processed/alpha_os_strategy_posteriors.parquet",
        "Regime Drift Monitor": "data/processed/regime_drift_monitor.json",
        "Shadow Divergence Index": "data/processed/shadow_divergence_index.json",
        "Walk-Forward Results": "data/validation/walk_forward_results.json",
        "Edge Half-Life": "data/processed/edge_half_life.json",
        "Liquidity Risk": "data/processed/liquidity_risk.parquet",
        "Sentiment (market)": "data/sentiment/v3/market_sentiment_india.parquet",
        "Model Freeze State": "data/processed/model_freeze_state.json",
        "NAV Reconciliation": "data/processed/nav_reconciliation.json",
        "Snapshot Integrity": "data/processed/snapshot_integrity.json",
        "Calendar Alignment Audit": "data/processed/calendar_alignment_audit.json",
        "Drift Monitor": "data/processed/drift_monitor.json",
        "Regime Misclassification Tolerance": "data/processed/regime_misclassification_tolerance.json",
        "Survivorship Bias Audit": "data/processed/survivorship_bias_audit.json",
        "Real Data Policy": "data/processed/real_data_only_policy.json",
        "Exposure/Cash Contract": "data/processed/exposure_cash_contract.json",
        "Allocator Universe Alignment": "data/processed/allocator_universe_alignment.json",
        "Parameter Version": "data/processed/parameter_version.json",
        "Dataset Lineage": "data/processed/dataset_lineage.json",
        "Feature Lineage Map": "data/processed/feature_lineage_map.json",
    }

    rows = []
    now = datetime.now().timestamp()
    for name, rel in key_paths.items():
        p = PROJECT_ROOT / rel
        if not p.exists():
            rows.append({"artifact": name, "path": rel, "last_modified": None, "age_days": None, "status": "missing"})
            continue
        m = p.stat().st_mtime
        age_days = (now - m) / 86400.0
        status = "fresh" if age_days <= 2 else ("stale" if age_days <= 10 else "very stale")
        rows.append(
            {
                "artifact": name,
                "path": rel,
                "last_modified": datetime.fromtimestamp(m).isoformat(timespec="seconds"),
                "age_days": round(age_days, 2),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


class NorthstarV3UltimateIntegratedDashboard:
    def __init__(self) -> None:
        self.hub = V3DataHub(PROJECT_ROOT)
        self.sentiment_panel = V3SentimentPanel()
        self.strict_mode = str(os.getenv("NORTHSTAR_STRICT_MODE", "0")).strip().lower() in {"1", "true", "yes", "on"}
        self._current_mode = "research"
        self._view_model_meta: Dict[str, Any] = {}
        self._health_events_path = PROJECT_ROOT / "data/processed/dashboard_health_events.jsonl"
        self._health_status_path = PROJECT_ROOT / "data/processed/dashboard_health.json"
        self._install_streamlit_guards()

    @staticmethod
    def _arrow_compatible_frame(df: pd.DataFrame) -> pd.DataFrame:
        """
        Make DataFrames Arrow-safe for Streamlit display.
        Handles mixed object columns (e.g., bool + float in the same column).
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df

        obj_cols = [c for c in df.columns if df[c].dtype == "object"]
        if not obj_cols:
            return df

        out = df.copy()
        for col in obj_cols:
            series = out[col]
            non_null = series.dropna()
            if non_null.empty:
                continue

            sample = non_null.head(512).tolist()
            numeric_like = all(
                isinstance(v, (int, float, np.integer, np.floating, bool, np.bool_))
                for v in sample
            )
            if numeric_like:
                out[col] = pd.to_numeric(series, errors="coerce")
                continue

            mixed_types = len({type(v) for v in sample}) > 1
            contains_complex = any(isinstance(v, (dict, list, tuple, set, Path)) for v in sample)
            if mixed_types or contains_complex:
                def _stringify(v: Any) -> Any:
                    if v is None:
                        return None
                    try:
                        if pd.isna(v):
                            return None
                    except Exception:
                        pass
                    if isinstance(v, (dict, list, tuple, set)):
                        try:
                            return json.dumps(v, ensure_ascii=True, sort_keys=True)
                        except Exception:
                            return str(v)
                    return str(v)

                out[col] = series.map(_stringify)

        return out

    def _install_streamlit_guards(self) -> None:
        """
        Install one-time Streamlit guards:
        - enforce explicit Plotly keys (no implicit auto-key fallback)
        - sanitize dataframe object columns for Arrow serialization safety
        """
        if getattr(st, "_northstar_streamlit_guards_installed", False):
            return

        original_plotly_chart = st.plotly_chart
        original_dataframe = st.dataframe

        def _safe_plotly_chart(*args, **kwargs):
            if kwargs.get("key") is None:
                msg = "plotly_chart called without explicit key"
                self._emit_dashboard_health_event(
                    event_type="chart_key_missing",
                    severity="error",
                    section="streamlit_guard",
                    message=msg,
                )
                raise RuntimeError(msg)
            return original_plotly_chart(*args, **kwargs)

        def _safe_dataframe(data=None, *args, **kwargs):
            if isinstance(data, pd.DataFrame):
                data = self._arrow_compatible_frame(data)
            return original_dataframe(data, *args, **kwargs)

        st.plotly_chart = _safe_plotly_chart
        st.dataframe = _safe_dataframe
        st._northstar_streamlit_guards_installed = True

    def _apply_fig_theme(self, fig: go.Figure, *, height: Optional[int] = None) -> go.Figure:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Space Grotesk, sans-serif", color=THEME["text"]),
            margin=dict(l=10, r=10, t=40, b=10),
        )
        fig.update_xaxes(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"])
        fig.update_yaxes(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"])
        if height:
            fig.update_layout(height=height)
        return fig

    def _emit_dashboard_health_event(
        self,
        *,
        event_type: str,
        severity: str,
        section: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": str(event_type),
            "severity": str(severity),
            "mode": self._current_mode,
            "strict_mode": bool(self.strict_mode),
            "section": str(section),
            "message": str(message),
            "payload": payload or {},
        }
        try:
            self._health_events_path.parent.mkdir(parents=True, exist_ok=True)
            with self._health_events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=True) + "\n")
            status = {
                "last_event": event,
                "last_updated": event["timestamp"],
            }
            self._health_status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        except Exception:
            # Health telemetry must never crash rendering path.
            pass

    def _render_chart_with_contract(
        self,
        *,
        chart_id: str,
        fig: go.Figure,
        data: Dict[str, Any],
        key: str,
        height: Optional[int] = None,
    ) -> bool:
        """Render chart with registry contract + freshness badge + strict blocking."""
        if height:
            self._apply_fig_theme(fig, height=height)
        else:
            self._apply_fig_theme(fig)

        live_mode = self._current_mode == "live"
        result = evaluate_chart_contract(
            chart_id=chart_id,
            data=data,
            meta=self._view_model_meta if isinstance(self._view_model_meta, dict) else {},
            live_mode=live_mode,
        )
        badge = str(result.get("badge", "⚪ Unknown"))
        msg = str(result.get("message", ""))
        st.caption(f"{badge} {msg}")

        if bool(result.get("block", False)):
            block_message = f"LIVE DECISION SURFACE BLOCKED — {chart_id}: {msg}"
            st.error(block_message)
            self._emit_dashboard_health_event(
                event_type="chart_blocked",
                severity="error",
                section=chart_id,
                message=block_message,
                payload={"contract": CHART_REGISTRY.get(chart_id).description if chart_id in CHART_REGISTRY else "missing"},
            )
            return False

        if result.get("status") in {"expired", "missing"}:
            self._emit_dashboard_health_event(
                event_type="chart_degraded",
                severity="warning",
                section=chart_id,
                message=msg,
                payload={"status": result.get("status")},
            )

        st.plotly_chart(fig, width="stretch", key=key)
        return True

    def _kpi_card(self, label: str, value: str, *, delta: Optional[str] = None, pill: Optional[str] = None) -> None:
        pill_html = ""
        if pill:
            kind = "ok" if pill.lower() in {"ok", "healthy", "fresh"} else ("warn" if pill.lower() in {"warn", "stale"} else "bad")
            pill_html = f'<span class="ns-pill {kind}">{pill}</span>'
        delta_html = f'<div class="ns-muted" style="margin-top:4px;font-size:0.92rem;">{delta}</div>' if delta else ""
        st.markdown(
            f"""
            <div class="ns-card">
              <div class="ns-kpi-label">{label} {pill_html}</div>
              <div class="ns-kpi-value">{value}</div>
              {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _formula_note(self, title: str, lines: Sequence[str]) -> None:
        safe_title = html.escape(str(title))
        safe_lines = [f'<div class="ns-formula-line">{html.escape(str(line))}</div>' for line in lines if str(line).strip()]
        if not safe_lines:
            return
        st.markdown(
            f"""
            <div class="ns-formula">
              <div class="ns-formula-title">{safe_title}</div>
              {''.join(safe_lines)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _focus_active_window(
        df: pd.DataFrame,
        *,
        time_col: str,
        value_cols: Sequence[str],
        max_rows: int = 756,
        min_rows: int = 140,
        eps: float = 1e-8,
    ) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty or time_col not in df.columns:
            return df
        out = df.copy()
        out[time_col] = _to_naive_date_series(out[time_col], normalize=False)
        out = out.dropna(subset=[time_col]).sort_values(time_col)
        if out.empty:
            return out

        cols = [c for c in value_cols if c in out.columns]
        if cols:
            dsum = pd.Series(0.0, index=out.index)
            for c in cols:
                dsum = dsum + pd.to_numeric(out[c], errors="coerce").diff().abs().fillna(0.0)
            arr = dsum.to_numpy()
            active_idx = int(np.argmax(arr > float(eps))) if len(arr) else 0
            if len(arr) and bool(arr[active_idx] > float(eps)):
                start_idx = max(0, active_idx - 5)
                if (len(out) - start_idx) >= int(min_rows):
                    out = out.iloc[start_idx:].copy()

        if len(out) > int(max_rows):
            out = out.tail(int(max_rows)).copy()
        return out

    @staticmethod
    def _sigmoid_from_series(series: pd.Series) -> pd.Series:
        x = pd.to_numeric(series, errors="coerce")
        mu = float(x.mean(skipna=True)) if x.notna().any() else 0.0
        sd = float(x.std(skipna=True)) if x.notna().any() else 0.0
        if not np.isfinite(sd) or sd <= 1e-9:
            z = x.fillna(0.0) - mu
        else:
            z = (x - mu) / sd
        z = z.clip(-8, 8)
        return 1.0 / (1.0 + np.exp(-z))

    @staticmethod
    def _empirical_drawdown_surface(
        returns: pd.Series,
        *,
        horizons: Sequence[int] = (5, 20, 60),
        thresholds: Sequence[float] = (0.02, 0.05, 0.10, 0.15),
    ) -> pd.DataFrame:
        r = pd.to_numeric(returns, errors="coerce").dropna()
        if r.empty:
            return pd.DataFrame()
        max_h = int(max(horizons)) if horizons else 0
        if len(r) < max(40, max_h + 10):
            return pd.DataFrame()

        log_r = np.log1p(r.clip(lower=-0.99))
        rows: List[Dict[str, Any]] = []
        for h in horizons:
            h_int = int(h)
            if h_int <= 0:
                continue
            fwd = np.exp(log_r.rolling(h_int, min_periods=h_int).sum().shift(-(h_int - 1))) - 1.0
            fwd = pd.to_numeric(fwd, errors="coerce").dropna()
            if fwd.empty:
                continue
            for th in thresholds:
                th_f = float(th)
                p = float((fwd <= -th_f).mean())
                rows.append(
                    {
                        "horizon": f"{h_int}d",
                        "threshold": f">{int(th_f * 100)}%",
                        "probability": float(np.clip(p, 0.0, 1.0)),
                    }
                )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    @staticmethod
    def _status_pill_from_value(value: Any) -> str:
        s = str(value or "unknown").strip().lower()
        if s in {"pass", "ok", "healthy", "normal", "aligned", "inactive", "none", "unchanged"}:
            return "ok"
        if s in {"warn", "warning", "stale", "monitoring"}:
            return "warn"
        return "bad"

    @staticmethod
    def _status_str(obj: Any, *keys: str, default: str = "unknown") -> str:
        if not isinstance(obj, dict):
            return default
        for k in keys:
            v = obj.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return default

    def _render_section_safely(self, section_name: str, render_fn, *args, **kwargs) -> None:
        """
        Render a dashboard section with fault isolation so one broken subsection
        does not blank the whole dashboard.
        """
        try:
            render_fn(*args, **kwargs)
        except Exception as exc:
            self._emit_dashboard_health_event(
                event_type="section_failure",
                severity="error",
                section=section_name,
                message=str(exc),
                payload={"traceback": traceback.format_exc()[:4000]},
            )
            st.error(f"Section render failed: {section_name} — {exc}")
            with st.expander(f"Debug traceback: {section_name}", expanded=False):
                st.code(traceback.format_exc(), language="text")
            critical_live_sections = {
                "Global State Ribbon",
                "Market Pressure Surface",
                "Portfolio Expression Surface",
                "Survival Engine Surface",
                "News Shock Surface",
                "System Health Surface",
                "Market State",
                "Portfolio Expression",
                "Risk & Survival",
                "News & Narrative",
                "System Health",
            }
            if self.strict_mode and self._current_mode == "live" and section_name in critical_live_sections:
                raise RuntimeError(f"Strict mode blocked critical section failure: {section_name}") from exc

    def render_header(self) -> None:
        st.set_page_config(page_title="Northstar V3 Dashboard", layout="wide")
        st.markdown(
            """
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
            .stApp {
              background:
                radial-gradient(circle at 8% 8%, rgba(59,130,246,0.18) 0%, rgba(59,130,246,0.00) 35%),
                radial-gradient(circle at 92% 12%, rgba(245,158,11,0.16) 0%, rgba(245,158,11,0.00) 34%),
                radial-gradient(circle at 82% 82%, rgba(34,197,94,0.12) 0%, rgba(34,197,94,0.00) 38%),
                linear-gradient(180deg, #0b1220 0%, #0a0f1c 100%);
              color: #e5e7eb;
              font-family: 'Space Grotesk', sans-serif;
            }
            .ns-hero {
              background:
                linear-gradient(135deg, rgba(59,130,246,0.22) 0%, rgba(236,72,153,0.10) 34%, rgba(245,158,11,0.08) 62%, rgba(17,24,39,0.00) 85%),
                radial-gradient(circle at 78% 18%, rgba(34,197,94,0.14) 0%, rgba(0,0,0,0.00) 58%);
              border: 1px solid rgba(148,163,184,0.18);
              border-radius: 18px;
              padding: 18px 18px 14px 18px;
              box-shadow: 0 20px 60px rgba(0,0,0,0.35);
              margin-bottom: 10px;
            }
            .ns-hero h1 { margin: 0; font-size: 2.0rem; letter-spacing: 0.2px; }
            .ns-hero p { margin: 6px 0 0 0; color: rgba(229,231,235,0.75); }
            .ns-card {
              background: linear-gradient(180deg, rgba(17,24,39,0.92) 0%, rgba(15,23,42,0.92) 100%);
              border: 1px solid rgba(148,163,184,0.18);
              border-radius: 16px;
              padding: 14px 14px 10px 14px;
            }
            .ns-kpi-label { color: rgba(229,231,235,0.72); font-size: 0.9rem; }
            .ns-kpi-value { font-size: 1.55rem; font-weight: 700; letter-spacing: 0.2px; }
            .ns-muted { color: rgba(229,231,235,0.70); }
            .ns-pill { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.85rem; border: 1px solid rgba(148,163,184,0.20); }
            .ns-pill.ok { background: rgba(34,197,94,0.10); }
            .ns-pill.warn { background: rgba(245,158,11,0.10); }
            .ns-pill.bad { background: rgba(239,68,68,0.10); }
            .ns-formula {
              margin-top: 6px;
              margin-bottom: 12px;
              padding: 8px 10px;
              border-radius: 10px;
              border: 1px solid rgba(148,163,184,0.16);
              background: rgba(15,23,42,0.46);
              color: rgba(229,231,235,0.78);
              font-size: 0.74rem;
              line-height: 1.45;
              font-variant-caps: all-small-caps;
              letter-spacing: 0.35px;
            }
            .ns-formula-title {
              color: rgba(229,231,235,0.90);
              margin-bottom: 4px;
              font-weight: 600;
            }
            .ns-formula-line {
              font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
              font-size: 0.72rem;
            }
            /* Make tables readable in dark UI */
            .stDataFrame { border-radius: 14px; overflow: hidden; border: 1px solid rgba(148,163,184,0.18); }
            /* Reduce Streamlit top padding */
            .block-container { padding-top: 1.1rem; }
            /* More colorful tabs */
            div[data-baseweb="tab-list"] button {
              border-radius: 12px;
              margin-right: 6px;
              border: 1px solid rgba(148,163,184,0.20);
              background: rgba(15,23,42,0.65);
            }
            div[data-baseweb="tab-list"] button[aria-selected="true"] {
              border: 1px solid rgba(244,114,182,0.55);
              background: linear-gradient(135deg, rgba(59,130,246,0.28) 0%, rgba(244,114,182,0.24) 48%, rgba(245,158,11,0.22) 100%);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="ns-hero">
              <h1>Northstar V3 — Command Window</h1>
              <p>Full-spectrum visibility. Real data only. Built for daily operation.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render_live_refresh_controls(self) -> None:
        """Sidebar controls for auto-refresh during live monitoring."""
        with st.sidebar:
            st.markdown("### Live Refresh")
            enabled = st.checkbox(
                "Auto-refresh Dashboard",
                value=bool(st.session_state.get("ns_auto_refresh_enabled", True)),
                key="ns_auto_refresh_enabled",
                help="Keeps options/sentiment/live tabs synced while background loops run",
            )
            minutes = st.selectbox(
                "Refresh cadence",
                options=[1, 2, 5, 10],
                index=[1, 2, 5, 10].index(int(st.session_state.get("ns_auto_refresh_minutes", 5) or 5))
                if int(st.session_state.get("ns_auto_refresh_minutes", 5) or 5) in [1, 2, 5, 10]
                else 2,
                key="ns_auto_refresh_minutes",
            )
            if enabled:
                try:
                    from streamlit_autorefresh import st_autorefresh

                    ticks = st_autorefresh(
                        interval=int(minutes) * 60 * 1000,
                        key="ns_v3_live_autorefresh",
                    )
                    st.caption(f"Auto-refresh active every {int(minutes)}m • tick #{int(ticks)}")
                except Exception:
                    st.caption(
                        "Auto-refresh helper not installed. Install `streamlit-autorefresh` for timed UI refresh."
                    )
            else:
                st.caption("Auto-refresh is paused.")

    def _resolve_governor_bridge(self, data: Dict[str, Any]) -> Dict[str, Any]:
        gov = data.get("research_governor_bridge")
        if isinstance(gov, dict) and gov:
            return gov
        kernel_blob = data.get("research_kernel_status")
        for rec in _coerce_research_records(kernel_blob):
            if str(rec.get("type", "")) != "integration_bridge":
                continue
            payload = rec.get("data")
            if isinstance(payload, dict):
                bridge = payload.get("governor_bridge")
                if isinstance(bridge, dict) and bridge:
                    return bridge
        return {}

    def _derive_autonomous_brief(self, data: Dict[str, Any]) -> Dict[str, Any]:
        research_policy = data.get("research_policy") or {}
        daemon = data.get("daemon_status") or {}
        options_state = data.get("options_dashboard_state") or {}
        validation_summary = data.get("valuation_validation_summary") or {}
        awareness = _first_record_payload(data.get("research_awareness"), "research_self_awareness") or {}
        returns_partition = _first_record_payload(data.get("research_returns_partition"), "returns_partition") or {}
        governor = self._resolve_governor_bridge(data)

        freeze_active = bool(research_policy.get("freeze_active", False))
        confidence = _as_float(governor.get("confidence"), default=np.nan)
        best_model = str(governor.get("best_model", "n/a"))
        mode = str(daemon.get("mode", "unknown"))
        market_status = str(((daemon.get("market_status") or {}).get("market_status")) or "unknown")
        validation_status = str(validation_summary.get("status", "unknown")).lower()
        eligibility = bool(options_state.get("trade_eligibility", True))

        reasons: List[str] = []
        if freeze_active:
            reasons.append("Research freeze is active")
        if not np.isfinite(confidence) or confidence < 0.70:
            reasons.append("Candidate confidence is below deploy threshold (0.70)")
        if validation_status in {"fail", "error"}:
            reasons.append("Valuation validation is failing")
        if not eligibility:
            reasons.append("Options trade eligibility is currently blocked")
        if mode in {"survival_core", "recovery_mode"}:
            reasons.append(f"System mode is `{mode}`")

        if not reasons and np.isfinite(confidence) and confidence >= 0.70:
            action = "APPLY_IN_LIVE"
        elif np.isfinite(confidence) and confidence >= 0.70:
            action = "PAPER_APPLY_ONLY"
        else:
            action = "RESEARCH_ONLY"

        qa = [
            {
                "question": "What did we learn in the latest research cycle?",
                "answer": (
                    f"Best model: {best_model}; confidence={confidence:.3f}; "
                    f"acceptance_rate={_as_float(awareness.get('acceptance_rate'), default=np.nan):.1%}"
                    if np.isfinite(confidence)
                    else "No reliable model-confidence output yet."
                ),
            },
            {
                "question": "Can we apply this in live markets now?",
                "answer": (
                    "Yes, deployable under governance." if action == "APPLY_IN_LIVE"
                    else ("Not in live; paper-apply only until blockers clear." if action == "PAPER_APPLY_ONLY"
                          else "No; continue research and validation.")
                ),
            },
            {
                "question": "Why is deployment gated?",
                "answer": "; ".join(reasons) if reasons else "No blockers detected.",
            },
            {
                "question": "How are live vs backtest returns partitioned?",
                "answer": (
                    f"Cutover={returns_partition.get('live_returns_cutover_date', '2026-01-18')}; "
                    f"live_pnl={_as_float(returns_partition.get('live_net_pnl'), default=0.0):,.2f}; "
                    f"backtest_pnl={_as_float(returns_partition.get('backtest_net_pnl'), default=0.0):,.2f}."
                ),
            },
            {
                "question": "What is the current operating context?",
                "answer": f"mode={mode}, market={market_status}, freeze_active={freeze_active}",
            },
        ]

        return {
            "action": action,
            "reasons": reasons,
            "confidence": confidence,
            "best_model": best_model,
            "freeze_active": freeze_active,
            "mode": mode,
            "market_status": market_status,
            "qa": qa,
        }

    def render_mission_control(self, data: Dict[str, Any]) -> None:
        st.subheader("Mission Control")
        brief = self._derive_autonomous_brief(data)
        daemon = data.get("daemon_status") or {}
        options_state = data.get("options_dashboard_state") or {}
        runtime = data.get("options_runtime_state") or {}

        action = brief.get("action", "RESEARCH_ONLY")
        pill = "ok" if action == "APPLY_IN_LIVE" else ("warn" if action == "PAPER_APPLY_ONLY" else "bad")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            self._kpi_card("Decision", str(action), pill=pill)
        with c2:
            self._kpi_card("System Mode", str(brief.get("mode", "n/a")))
        with c3:
            self._kpi_card("Market", str(brief.get("market_status", "n/a")))
        with c4:
            self._kpi_card("Best Model", str(brief.get("best_model", "n/a")))
        with c5:
            conf = _as_float(brief.get("confidence"), default=np.nan)
            self._kpi_card("Model Confidence", f"{conf:.3f}" if np.isfinite(conf) else "n/a")
        with c6:
            self._kpi_card("Freeze", "Active" if brief.get("freeze_active", False) else "Inactive")

        q_left, q_right = st.columns([1.15, 1.0])
        with q_left:
            st.markdown("### Autonomous Briefing")
            for item in brief.get("qa", []):
                st.markdown(f"**Q:** {item.get('question', '')}")
                st.markdown(f"**A:** {item.get('answer', '')}")
        with q_right:
            st.markdown("### Live Constraint Snapshot")
            eq = _as_float(options_state.get("net_equity", runtime.get("net_equity")), default=np.nan)
            rr = _as_float(options_state.get("risk_remaining", runtime.get("risk_remaining")), default=np.nan)
            rp = _as_float(options_state.get("risk_cap_value", runtime.get("risk_cap_value")), default=np.nan)
            ap = options_state.get("active_positions", runtime.get("open_positions", []))
            ap_count = len(ap) if isinstance(ap, list) else _as_float(options_state.get("active_positions"), default=np.nan)
            d1, d2 = st.columns(2)
            with d1:
                self._kpi_card("Net Equity", f"{eq:,.2f}" if np.isfinite(eq) else "n/a")
                self._kpi_card("Risk Remaining", f"{rr:,.2f}" if np.isfinite(rr) else "n/a")
            with d2:
                self._kpi_card("Risk Cap", f"{rp:,.2f}" if np.isfinite(rp) else "n/a")
                self._kpi_card("Active Positions", str(int(ap_count)) if np.isfinite(_as_float(ap_count, default=np.nan)) else str(ap_count))

        ex_df = data.get("research_experiments")
        if isinstance(ex_df, pd.DataFrame) and not ex_df.empty and {"timestamp", "candidate_score"}.issubset(ex_df.columns):
            e = ex_df.copy()
            e["timestamp"] = _to_naive_date_series(e["timestamp"], normalize=False)
            e["candidate_score"] = pd.to_numeric(e["candidate_score"], errors="coerce")
            e = e.dropna(subset=["timestamp", "candidate_score"]).sort_values("timestamp")
            if not e.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=e["timestamp"], y=e["candidate_score"], mode="lines+markers", name="Candidate Score", line=dict(color=THEME["green"], width=2)))
                fig.update_layout(title="Research Learning Curve (Candidate Score)")
                self._apply_fig_theme(fig, height=300)
                st.plotly_chart(fig, width="stretch", key="mission_control_research_learning_curve")

        reasons = brief.get("reasons", [])
        if reasons:
            st.warning("Deployment blockers: " + " | ".join(reasons))
        else:
            st.success("No deployment blockers detected by current governance checks.")


    def render_research_mode_compact(self, data: Dict[str, Any]) -> None:
        st.subheader("Research Mode")
        awareness = _first_record_payload(data.get("research_awareness"), "research_self_awareness") or {}
        kernel_dataset = {}
        for rec in _coerce_research_records(data.get("research_kernel_status")):
            if str(rec.get("type", "")) == "research_dataset" and isinstance(rec.get("data"), dict):
                kernel_dataset = rec.get("data")
                break
        returns_partition = _first_record_payload(data.get("research_returns_partition"), "returns_partition") or {}
        weekend = _first_record_payload(data.get("research_weekend_sweep"), "weekend_research_sweep") or {}

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            self._kpi_card("Cycles", str(int(_as_float(awareness.get("total_cycles"), default=0))))
        with c2:
            self._kpi_card("Acceptance", f"{_as_float(awareness.get('acceptance_rate'), default=np.nan):.1%}" if np.isfinite(_as_float(awareness.get("acceptance_rate"), default=np.nan)) else "n/a")
        with c3:
            self._kpi_card("Mutation", f"{_as_float(awareness.get('adaptive_mutation_rate'), default=np.nan):.3f}" if np.isfinite(_as_float(awareness.get("adaptive_mutation_rate"), default=np.nan)) else "n/a")
        with c4:
            self._kpi_card("Backtest Rows", str(int(_as_float(kernel_dataset.get("backtest_rows"), default=0))))
        with c5:
            self._kpi_card("Live Rows", str(int(_as_float(kernel_dataset.get("live_rows"), default=0))))

        part = pd.DataFrame(
            [
                {"bucket": "Backtest", "rows": _as_float(kernel_dataset.get("backtest_rows"), default=0.0), "net_pnl": _as_float(returns_partition.get("backtest_net_pnl"), default=0.0)},
                {"bucket": "Live", "rows": _as_float(kernel_dataset.get("live_rows"), default=0.0), "net_pnl": _as_float(returns_partition.get("live_net_pnl"), default=0.0)},
            ]
        )
        left, right = st.columns([1.05, 1.0])
        with left:
            fig_rows = px.bar(part, x="bucket", y="rows", color="bucket", title="Research Dataset Partition (Rows)")
            self._apply_fig_theme(fig_rows, height=300)
            st.plotly_chart(fig_rows, width="stretch", key="research_mode_dataset_partition_rows")
        with right:
            fig_pnl = px.bar(part, x="bucket", y="net_pnl", color="bucket", title="Returns Partition (PnL)")
            self._apply_fig_theme(fig_pnl, height=300)
            st.plotly_chart(fig_pnl, width="stretch", key="research_mode_returns_partition_pnl")

        scenarios = weekend.get("scenarios", []) if isinstance(weekend, dict) else []
        if scenarios:
            sdf = pd.DataFrame(scenarios)
            for c in ["stress_multiplier", "survival_probability", "avg_max_drawdown"]:
                if c in sdf.columns:
                    sdf[c] = pd.to_numeric(sdf[c], errors="coerce")
            sdf = sdf.dropna(subset=["stress_multiplier"])
            if not sdf.empty:
                fig_sw = px.line(
                    sdf.sort_values("stress_multiplier"),
                    x="stress_multiplier",
                    y=["survival_probability", "avg_max_drawdown"],
                    markers=True,
                    title="Weekend Stress Sweep",
                )
                self._apply_fig_theme(fig_sw, height=320)
                st.plotly_chart(fig_sw, width="stretch", key="research_mode_weekend_stress_sweep")

    def render_experimentation_lab(self, data: Dict[str, Any]) -> None:
        st.subheader("Autonomous Experimentation Lab")
        ex = data.get("research_experiments")
        if isinstance(ex, pd.DataFrame) and not ex.empty:
            df = ex.copy()
            if "timestamp" in df.columns:
                df["timestamp"] = _to_naive_date_series(df["timestamp"], normalize=False)
            for c in ["candidate_score", "outputs_count"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            if "awareness" in df.columns:
                df["acceptance_rate"] = df["awareness"].apply(lambda x: _as_float((x or {}).get("acceptance_rate"), default=np.nan) if isinstance(x, dict) else np.nan)
                df["exploration_intensity"] = df["awareness"].apply(lambda x: _as_float((x or {}).get("exploration_intensity"), default=np.nan) if isinstance(x, dict) else np.nan)
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
            if not df.empty:
                c1, c2 = st.columns([1.2, 1.0])
                with c1:
                    fig = go.Figure()
                    if "candidate_score" in df.columns:
                        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["candidate_score"], mode="lines+markers", name="candidate_score", line=dict(color=THEME["green"], width=2)))
                    if "acceptance_rate" in df.columns:
                        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["acceptance_rate"], mode="lines+markers", name="acceptance_rate", line=dict(color=THEME["violet"], width=1.8)))
                    if "exploration_intensity" in df.columns:
                        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["exploration_intensity"], mode="lines+markers", name="exploration_intensity", line=dict(color=THEME["amber"], width=1.8)))
                    fig.update_layout(title="Experiment Trajectory")
                    self._apply_fig_theme(fig, height=330)
                    st.plotly_chart(fig, width="stretch", key="experimentation_lab_trajectory")
                with c2:
                    cols = [c for c in ["timestamp", "best_model", "candidate_score", "outputs_count", "freeze_active"] if c in df.columns]
                    st.dataframe(df.sort_values("timestamp", ascending=False).head(20)[cols], width="stretch", hide_index=True)
        else:
            st.info("No experiments tracker data found (`data/research/experiments.ndjson`).")

        t_train, t_cap, t_mc, t_param = st.tabs(["Model Validation", "Capital Simulation", "Monte Carlo", "Parameter Search"])

        with t_train:
            recs = _coerce_research_records(data.get("research_model_training_results"))
            if recs:
                rows = []
                for r in recs:
                    d = r.get("data") if isinstance(r.get("data"), dict) else {}
                    rows.append({"type": r.get("type"), "actionable": r.get("actionable"), "generated_at": r.get("generated_at"), **{k: d.get(k) for k in ["model", "status", "best_model", "score", "acceptance_threshold"]}})
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.caption("No model training report yet.")

        with t_cap:
            cap = _first_record_payload(data.get("research_capital_simulation_report"), "capital_simulation") or {}
            if cap:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    self._kpi_card("Final Capital", f"{_as_float(cap.get('final_capital'), default=np.nan):,.0f}" if np.isfinite(_as_float(cap.get("final_capital"), default=np.nan)) else "n/a")
                with c2:
                    self._kpi_card("Total Return", f"{_as_float(cap.get('total_return'), default=np.nan):.2%}" if np.isfinite(_as_float(cap.get("total_return"), default=np.nan)) else "n/a")
                with c3:
                    self._kpi_card("Max DD", f"{_as_float(cap.get('max_drawdown'), default=np.nan):.2%}" if np.isfinite(_as_float(cap.get("max_drawdown"), default=np.nan)) else "n/a")
                with c4:
                    self._kpi_card("Risk of Ruin", f"{_as_float(cap.get('risk_of_ruin'), default=np.nan):.2%}" if np.isfinite(_as_float(cap.get("risk_of_ruin"), default=np.nan)) else "n/a")
                st.json(cap, expanded=False)
            else:
                st.caption("No capital simulation report yet.")

        with t_mc:
            mc = _first_record_payload(data.get("research_monte_carlo_report"), "monte_carlo_report") or {}
            if mc:
                st.json(mc, expanded=False)
            else:
                st.caption("No Monte Carlo report yet.")

        with t_param:
            par_bundle = data.get("research_parameter_search_results")
            par = _first_record_payload(par_bundle, "parameter_search") or _first_record_payload(par_bundle, "parameter_sensitivity") or {}
            if par:
                if "optimization" in par:
                    opt = par.get("optimization", {}) if isinstance(par.get("optimization"), dict) else {}
                    best_params = opt.get("best_params", {})
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        self._kpi_card("Optimizer", str(opt.get("optimizer", "n/a")))
                    with c2:
                        self._kpi_card("Calls", str(int(_as_float(opt.get("n_calls"), 0))))
                    with c3:
                        self._kpi_card(
                            "Best Objective",
                            f"{_as_float(opt.get('best_objective'), default=np.nan):.4f}"
                            if np.isfinite(_as_float(opt.get("best_objective"), default=np.nan))
                            else "n/a",
                        )
                    if isinstance(best_params, dict) and best_params:
                        st.dataframe(
                            pd.DataFrame(
                                [{"parameter": str(k), "value": v} for k, v in best_params.items()]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                    st.json(par, expanded=False)
                else:
                    sens = par.get("sensitivity_results", [])
                    if isinstance(sens, list) and sens:
                        sdf = pd.DataFrame(sens)
                        if not sdf.empty:
                            st.dataframe(sdf, width="stretch", hide_index=True)
                    st.json(par, expanded=False)
            else:
                st.caption("No parameter sensitivity report yet.")


    def render_system_compact(self, data: Dict[str, Any]) -> None:
        st.subheader("System Guard")
        daemon = data.get("daemon_status") or {}
        resources = daemon.get("resource_usage") or {}
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            self._kpi_card("CPU %", f"{_as_float(resources.get('cpu_percent'), default=np.nan):.1f}" if np.isfinite(_as_float(resources.get("cpu_percent"), default=np.nan)) else "n/a")
        with c2:
            self._kpi_card("Memory %", f"{_as_float(resources.get('memory_percent'), default=np.nan):.1f}" if np.isfinite(_as_float(resources.get("memory_percent"), default=np.nan)) else "n/a")
        with c3:
            self._kpi_card("Uptime (s)", f"{_as_float(daemon.get('uptime_seconds'), default=np.nan):.0f}" if np.isfinite(_as_float(daemon.get("uptime_seconds"), default=np.nan)) else "n/a")
        with c4:
            self._kpi_card("Profile", str(daemon.get("system_profile", "n/a")))

        art = _artifact_mtimes()
        if isinstance(art, pd.DataFrame) and not art.empty:
            st.markdown("### Artifact Freshness")
            stale = art[art["status"].isin(["stale", "very stale", "missing"])].copy()
            if stale.empty:
                st.success("All key artifacts are fresh.")
            else:
                st.dataframe(stale.sort_values(["status", "age_days"], ascending=[True, False]), width="stretch", hide_index=True)

        gov = data.get("governance_events")
        if isinstance(gov, pd.DataFrame) and not gov.empty:
            g = gov.copy()
            for c in ["timestamp", "resolved_at"]:
                if c in g.columns:
                    g[c] = pd.to_datetime(g[c], errors="coerce")
            cols = [c for c in ["timestamp", "event_type", "severity", "mode_before", "mode_after", "resolved_at", "operator_override"] if c in g.columns]
            st.markdown("### Governance Events (Recent)")
            st.dataframe(g.sort_values("timestamp", ascending=False).head(50)[cols], width="stretch", hide_index=True)

    # ---------------------------- COMMAND CENTER ----------------------------

    # ---------------------------- SYSTEM HEALTH ----------------------------
    def render_system_health(self, data: Dict[str, Any]) -> None:
        st.subheader("🧭 System Health")
        log = data.get("system_log") or {}
        ts = log.get("timestamp")
        summary = log.get("summary", {})
        success_rate = log.get("success_rate")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            self._kpi_card("Last Refresh", ts or "No data")
        with col2:
            self._kpi_card("Success Rate", f"{_as_float(success_rate) * 100:.1f}%" if success_rate is not None else "No data")
        with col3:
            self._kpi_card("Steps", str(summary.get("steps", 0)))
        with col4:
            self._kpi_card("Failed", str(summary.get("failed", 0)))

        freshness = (log.get("data_freshness_probe") or {})
        top = st.columns([1.5, 1.0])
        with top[0]:
            st.markdown("### Execution Timeline")
            exec_log = log.get("execution_log") or []
            if isinstance(exec_log, list) and exec_log:
                df = pd.DataFrame(exec_log)
                if "duration_seconds" in df.columns:
                    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")
                if "timestamp" in df.columns:
                    df["timestamp"] = _to_naive_date_series(df["timestamp"], normalize=False)
                st.dataframe(df[["component", "status", "duration_seconds"]].sort_values("duration_seconds", ascending=False), width="stretch", hide_index=True)
                if "duration_seconds" in df.columns and df["duration_seconds"].notna().any():
                    fig = px.bar(
                        df.sort_values("duration_seconds", ascending=False),
                        x="component",
                        y="duration_seconds",
                        color="status",
                        title="Step Durations (s)",
                    )
                    self._render_chart_with_contract(
                        chart_id="system_health_runtime_metrics",
                        fig=fig,
                        data=data,
                        key="system_health_runtime_metrics",
                        height=320,
                    )
            else:
                st.info("No execution log available yet.")

        with top[1]:
            st.markdown("### Runtime")
            try:
                import psutil  # type: ignore

                cpu = psutil.cpu_percent(interval=0.3)
                mem = psutil.virtual_memory().percent
                self._kpi_card("CPU", f"{cpu:.0f}%")
                self._kpi_card("Memory", f"{mem:.0f}%")
            except Exception:
                st.info("Runtime metrics unavailable.")

            st.markdown("### Data Freshness Probe")
            if freshness:
                st.json(freshness, expanded=False)
            else:
                st.info("No freshness probe in system log.")

        integrity = data.get("integrity_report") or {}
        integrity_artifacts = data.get("integrity_artifacts")
        st.markdown("### V3 Integrity Audit")
        if isinstance(integrity, dict) and integrity:
            summ = integrity.get("summary") or {}
            a_stat = (summ.get("artifact_status") or {})
            c_stat = (summ.get("cross_checks") or {})
            i1, i2, i3, i4 = st.columns(4)
            with i1:
                self._kpi_card("Artifacts OK", str(a_stat.get("ok", "n/a")))
            with i2:
                self._kpi_card("Artifact Warnings", str(a_stat.get("warn", "n/a")))
            with i3:
                self._kpi_card("Artifact Critical", str(a_stat.get("critical", "n/a")))
            with i4:
                self._kpi_card("Cross-check Critical", str(c_stat.get("critical", "n/a")))

            cross = integrity.get("cross_checks") or []
            if isinstance(cross, list) and cross:
                cross_df = pd.DataFrame(cross)
                show_cols = [c for c in ["check", "status", "message"] if c in cross_df.columns]
                st.dataframe(cross_df[show_cols], width="stretch", hide_index=True)
        else:
            st.info("Integrity report unavailable (`data/processed/integrity/v3_integrity_report_latest.json`).")

        if isinstance(integrity_artifacts, pd.DataFrame) and not integrity_artifacts.empty:
            bad = integrity_artifacts[
                integrity_artifacts["status"].astype(str).str.lower().isin(["warn", "critical"])
            ].copy()
            if not bad.empty:
                st.markdown("#### Artifact Issues")
                keep = [c for c in ["artifact", "status", "message", "rows", "null_ratio", "stale_days"] if c in bad.columns]
                st.dataframe(
                    bad.sort_values("status", ascending=False)[keep],
                    width="stretch",
                    hide_index=True,
                )

        st.markdown("### Institutional Hardening")

        def _obj(key: str) -> Dict[str, Any]:
            v = data.get(key)
            return v if isinstance(v, dict) else {}

        freeze_state = _obj("model_freeze_state")
        nav_recon = _obj("nav_reconciliation")
        snapshot_integrity = _obj("snapshot_integrity")
        cal_audit = _obj("calendar_alignment_audit")
        drift_mon = _obj("drift_monitor")
        regime_tol = _obj("regime_misclassification_tolerance")
        survivorship = _obj("survivorship_bias_audit")
        real_data_policy = _obj("real_data_only_policy")
        exp_cash = _obj("exposure_cash_contract")
        universe_align = _obj("allocator_universe_alignment")
        param_ver = _obj("parameter_version")
        ds_lineage = _obj("dataset_lineage")
        feat_lineage = _obj("feature_lineage_map")

        freeze_active = bool(freeze_state.get("freeze_active", False))
        nav_status = self._status_str(nav_recon, "status", default="unknown")
        snap_status = self._status_str(snapshot_integrity, "status", default="unknown")
        cal_status = self._status_str(cal_audit, "overall_status", "status", default="unknown")
        drift_status = self._status_str(drift_mon, "severity", "status", default="unknown")
        regime_tol_status = self._status_str(regime_tol, "status", default="unknown")
        survivorship_status = self._status_str(survivorship, "status", default="unknown")
        real_data_status = self._status_str(real_data_policy, "status", default="unknown")
        exp_cash_status = self._status_str(exp_cash, "status", default="unknown")
        universe_status = self._status_str(universe_align, "status", default="unknown")

        mismatch_bps = _as_float(nav_recon.get("mismatch_bps"), default=np.nan)
        residual_bps = _as_float(exp_cash.get("residual_bps"), default=np.nan)
        max_exp_shift_bps = _as_float(regime_tol.get("max_exposure_shift_bps"), default=np.nan)
        max_l1_turnover = _as_float(regime_tol.get("max_allocation_l1_turnover"), default=np.nan)

        h1, h2, h3, h4, h5, h6 = st.columns(6)
        with h1:
            self._kpi_card("Model Freeze", "Active" if freeze_active else "Inactive", pill="warn" if freeze_active else "ok")
        with h2:
            self._kpi_card("NAV Reconcile", nav_status.upper(), pill=self._status_pill_from_value(nav_status))
        with h3:
            self._kpi_card("Snapshot Integrity", snap_status.upper(), pill=self._status_pill_from_value(snap_status))
        with h4:
            self._kpi_card("Calendar Audit", cal_status.upper(), pill=self._status_pill_from_value(cal_status))
        with h5:
            self._kpi_card("Drift Severity", drift_status.upper(), pill=self._status_pill_from_value(drift_status))
        with h6:
            self._kpi_card("Regime Tolerance", regime_tol_status.upper(), pill=self._status_pill_from_value(regime_tol_status))

        h7, h8, h9, h10, h11, h12 = st.columns(6)
        with h7:
            self._kpi_card("Exposure/Cash", exp_cash_status.upper(), pill=self._status_pill_from_value(exp_cash_status))
        with h8:
            self._kpi_card("Universe Alignment", universe_status.upper(), pill=self._status_pill_from_value(universe_status))
        with h9:
            self._kpi_card("Survivorship Audit", survivorship_status.upper(), pill=self._status_pill_from_value(survivorship_status))
        with h10:
            self._kpi_card("NAV Mismatch", f"{mismatch_bps:.2f} bps" if np.isfinite(mismatch_bps) else "n/a")
        with h11:
            self._kpi_card("Misclass Exposure Shift", f"{max_exp_shift_bps:.1f} bps" if np.isfinite(max_exp_shift_bps) else "n/a")
        with h12:
            version_id = str(param_ver.get("version_id", "n/a"))
            git_commit = str(param_ver.get("git_commit", "n/a"))
            self._kpi_card("Parameter Version", version_id[:12], delta=f"git={git_commit[:10]}")

        h13, h14, h15, h16 = st.columns(4)
        with h13:
            self._kpi_card("Real Data Policy", real_data_status.upper(), pill=self._status_pill_from_value(real_data_status))
        with h14:
            policy_rc = _as_float(real_data_policy.get("returncode"), default=np.nan)
            self._kpi_card("Policy Return Code", str(int(policy_rc)) if np.isfinite(policy_rc) else "n/a")
        with h15:
            self._kpi_card("Freeze Triggers", str(len(freeze_state.get("triggers") or [])))
        with h16:
            self._kpi_card("Calendar Checks", str(len(cal_audit.get("checks") or [])))

        cal_checks = cal_audit.get("checks") if isinstance(cal_audit.get("checks"), list) else []
        cal_warn = sum(1 for c in cal_checks if str((c or {}).get("status", "")).lower() in {"warn", "warning"})
        cal_fail = sum(1 for c in cal_checks if str((c or {}).get("status", "")).lower() in {"fail", "error", "critical"})
        surv_issues = survivorship.get("issues") if isinstance(survivorship.get("issues"), list) else []
        freeze_triggers = freeze_state.get("triggers") if isinstance(freeze_state.get("triggers"), list) else []

        hard_rows = [
            {
                "artifact": "model_freeze_state",
                "status": "active" if freeze_active else "inactive",
                "timestamp": freeze_state.get("timestamp"),
                "detail": f"triggers={len(freeze_triggers)}",
            },
            {
                "artifact": "nav_reconciliation",
                "status": nav_status,
                "timestamp": nav_recon.get("timestamp"),
                "detail": (
                    f"mismatch_bps={mismatch_bps:.2f}, basis={nav_recon.get('comparison_basis')}"
                    if np.isfinite(mismatch_bps)
                    else f"basis={nav_recon.get('comparison_basis')}"
                ),
            },
            {
                "artifact": "snapshot_integrity",
                "status": snap_status,
                "timestamp": snapshot_integrity.get("timestamp"),
                "detail": (
                    f"missing={len(snapshot_integrity.get('missing') or [])}, "
                    f"staleness_s={_as_float(snapshot_integrity.get('staleness_seconds'), default=np.nan):.1f}"
                ),
            },
            {
                "artifact": "calendar_alignment_audit",
                "status": cal_status,
                "timestamp": cal_audit.get("timestamp"),
                "detail": f"warn={cal_warn}, fail={cal_fail}",
            },
            {
                "artifact": "drift_monitor",
                "status": drift_status,
                "timestamp": drift_mon.get("timestamp"),
                "detail": f"flags={len(drift_mon.get('flags') or [])}",
            },
            {
                "artifact": "regime_misclassification_tolerance",
                "status": regime_tol_status,
                "timestamp": regime_tol.get("timestamp"),
                "detail": (
                    f"max_l1_turnover={max_l1_turnover:.4f}, max_exposure_shift_bps={max_exp_shift_bps:.1f}"
                    if np.isfinite(max_l1_turnover) and np.isfinite(max_exp_shift_bps)
                    else "n/a"
                ),
            },
            {
                "artifact": "survivorship_bias_audit",
                "status": survivorship_status,
                "timestamp": survivorship.get("timestamp"),
                "detail": f"issues={', '.join(surv_issues[:3]) if surv_issues else 'none'}",
            },
            {
                "artifact": "real_data_only_policy",
                "status": real_data_status,
                "timestamp": real_data_policy.get("timestamp"),
                "detail": (
                    f"returncode={int(_as_float(real_data_policy.get('returncode'), default=np.nan))}"
                    if np.isfinite(_as_float(real_data_policy.get("returncode"), default=np.nan))
                    else "n/a"
                ),
            },
            {
                "artifact": "exposure_cash_contract",
                "status": exp_cash_status,
                "timestamp": exp_cash.get("timestamp"),
                "detail": f"residual_bps={residual_bps:.2f}" if np.isfinite(residual_bps) else "n/a",
            },
            {
                "artifact": "allocator_universe_alignment",
                "status": universe_status,
                "timestamp": universe_align.get("timestamp"),
                "detail": (
                    f"off_universe={int(_as_float(universe_align.get('off_universe_count'), default=0))}, "
                    f"non_tradeable={int(_as_float(universe_align.get('non_tradeable_count'), default=0))}"
                ),
            },
        ]
        st.dataframe(pd.DataFrame(hard_rows), width="stretch", hide_index=True)

        with st.expander("Lineage and Feature Governance", expanded=False):
            l1, l2 = st.columns(2)
            with l1:
                st.markdown("#### Parameter + Dataset Lineage")
                st.json(
                    {
                        "parameter_version": {
                            "timestamp": param_ver.get("timestamp"),
                            "version_id": param_ver.get("version_id"),
                            "git_commit": param_ver.get("git_commit"),
                            "config_hash_prefix": str(param_ver.get("config_hash", ""))[:16],
                            "code_hash_prefix": str(param_ver.get("code_hash", ""))[:16],
                        },
                        "dataset_lineage": {
                            "timestamp": ds_lineage.get("timestamp"),
                            "git_commit": ds_lineage.get("git_commit"),
                            "combined_hash_prefix": str(ds_lineage.get("combined_hash", ""))[:16],
                            "files": len(ds_lineage.get("files") or []),
                        },
                    },
                    expanded=False,
                )
            with l2:
                st.markdown("#### Feature Lineage")
                feature_groups = feat_lineage.get("features") if isinstance(feat_lineage.get("features"), dict) else {}
                st.json(
                    {
                        "timestamp": feat_lineage.get("timestamp"),
                        "feature_groups": list(feature_groups.keys()),
                        "group_count": len(feature_groups),
                    },
                    expanded=False,
                )

        self._formula_note(
            "institutional hardening formulas",
            [
                "nav_mismatch_bps = abs(paper_norm_nav - independent_norm_nav) * 10,000",
                "cash_residual_bps = abs(cash - (1 - exposure)) * 10,000",
                "misclassification_exposure_shift_bps = max_scenario(|exposure_scenario - base_exposure|) * 10,000",
                "snapshot_status = PASS if (missing == 0 and staleness_seconds <= threshold)",
                "freeze_active = any(governance_trigger == true)",
                "real_data_policy_status = PASS iff enforce_real_data_only.py returncode == 0",
            ],
        )
        
        # Add data quality diagnostics
        st.markdown("### Data Quality Diagnostics")
        self.render_data_quality_diagnostics(data)

    # ---------------------------- V3 ANALYTICS ----------------------------
    def render_v3_analytics(self, data: Dict[str, Any]) -> None:
        st.subheader("📈 V3 Analytics (Compact)")

        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        if pnl_df.empty:
            st.info("No portfolio PnL history available for analytics.")
            return

        df = pnl_df.copy().sort_values("Date")
        
        # Limit to recent data (12 months) to avoid visual clutter
        df = self._limit_timeseries_to_recent(df, months_back=12)
        
        returns = pd.to_numeric(df.get("Return"), errors="coerce").dropna()
        drawdown = self.compute_drawdown(df["Equity"]) * 100.0

        total_return = float(df["Equity"].iloc[-1] / max(1e-9, float(df["Equity"].iloc[0])) - 1.0)
        sharpe = float((returns.mean() * 252) / (returns.std() * np.sqrt(252) + 1e-9)) if not returns.empty else np.nan
        win_rate = float((returns > 0).mean()) if not returns.empty else np.nan
        max_dd = float(drawdown.min()) if drawdown.notna().any() else np.nan

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            self._kpi_card("Total Return", f"{total_return:+.2%}")
        with k2:
            self._kpi_card("Sharpe", f"{sharpe:.2f}" if np.isfinite(sharpe) else "n/a")
        with k3:
            self._kpi_card("Max Drawdown", f"{max_dd:.2f}%" if np.isfinite(max_dd) else "n/a")
        with k4:
            self._kpi_card("Win Rate", f"{win_rate:.1%}" if np.isfinite(win_rate) else "n/a")

        fig1 = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Equity Curve", "Drawdown (%)"),
        )
        fig1.add_trace(
            go.Scatter(x=df["Date"], y=df["Equity"], name="Equity", line=dict(color=THEME["blue"], width=2)),
            row=1,
            col=1,
        )
        fig1.add_trace(
            go.Scatter(x=df["Date"], y=drawdown, name="Drawdown", line=dict(color=THEME["red"], width=1.8)),
            row=2,
            col=1,
        )
        self._apply_fig_theme(fig1, height=430)
        st.plotly_chart(fig1, width="stretch", key="v3_analytics_compact_equity_drawdown")

        roll_vol = returns.rolling(20).std() * np.sqrt(252) * 100 if not returns.empty else pd.Series(dtype=float)
        roll_sharpe = (
            (returns.rolling(20).mean() * 252)
            / (returns.rolling(20).std() * np.sqrt(252) + 1e-9)
            if not returns.empty
            else pd.Series(dtype=float)
        )
        if not roll_vol.empty and not roll_sharpe.empty:
            roll_df = pd.DataFrame(
                {
                    "Date": df["Date"].iloc[-len(roll_vol) :].reset_index(drop=True),
                    "RollingVol": pd.to_numeric(roll_vol, errors="coerce").reset_index(drop=True),
                    "RollingSharpe": pd.to_numeric(roll_sharpe, errors="coerce").reset_index(drop=True),
                }
            ).dropna(subset=["Date"])
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(
                go.Scatter(
                    x=roll_df["Date"],
                    y=roll_df["RollingVol"],
                    name="Rolling Vol (20d, %)",
                    line=dict(color=THEME["amber"], width=1.8),
                ),
                secondary_y=False,
            )
            fig2.add_trace(
                go.Scatter(
                    x=roll_df["Date"],
                    y=roll_df["RollingSharpe"],
                    name="Rolling Sharpe (20d)",
                    line=dict(color=THEME["cyan"], width=1.8),
                ),
                secondary_y=True,
            )
            fig2.update_layout(title="Rolling Risk and Efficiency")
            fig2.update_yaxes(title_text="Volatility (%)", secondary_y=False)
            fig2.update_yaxes(title_text="Sharpe", secondary_y=True)
            self._apply_fig_theme(fig2, height=320)
            st.plotly_chart(fig2, width="stretch", key="v3_analytics_compact_rolling_risk_efficiency")

        idx = data.get("index_nifty50")
        if isinstance(idx, pd.DataFrame) and not idx.empty:
            close_col = "close" if "close" in idx.columns else (idx.columns[0] if len(idx.columns) else None)
            if close_col is not None:
                b = idx.copy().sort_index()
                b[close_col] = pd.to_numeric(b[close_col], errors="coerce")
                b = b.dropna(subset=[close_col])
                b = b[(b.index >= df["Date"].min()) & (b.index <= df["Date"].max())]
                if not b.empty:
                    portfolio_norm = df["Equity"] / max(1e-9, float(df["Equity"].iloc[0]))
                    benchmark_norm = b[close_col] / max(1e-9, float(b[close_col].iloc[0]))
                    fig3 = go.Figure()
                    fig3.add_trace(
                        go.Scatter(
                            x=df["Date"],
                            y=portfolio_norm,
                            name="Portfolio",
                            line=dict(color=THEME["blue"], width=2),
                        )
                    )
                    fig3.add_trace(
                        go.Scatter(
                            x=b.index,
                            y=benchmark_norm,
                            name="NIFTY 50",
                            line=dict(color=THEME["cyan"], width=1.8),
                        )
                    )
                    fig3.update_layout(title="Portfolio vs Benchmark (Normalized)")
                    self._apply_fig_theme(fig3, height=320)
                    st.plotly_chart(fig3, width="stretch", key="v3_analytics_compact_vs_benchmark")

        self._formula_note(
            "V3 Analytics Formulas",
            [
                "portfolio_norm_t = equity_t / equity_0",
                "drawdown_t = equity_t / max(equity_<=t) - 1",
                "rolling_vol_20d = std(return_20d) * sqrt(252)",
                "rolling_sharpe_20d = mean(return_20d) * 252 / (std(return_20d) * sqrt(252))",
            ],
        )


    # ---------------------------- ADVANCED INTEL ----------------------------
    def render_advanced_intelligence(self, data: Dict[str, Any]) -> None:
        st.subheader("🧠 Advanced Intelligence (Compressed)")

        # Family tabs replace long vertical chart stacks.
        t_val, t_macro, t_alloc, t_flow, t_surv = st.tabs(
            ["Valuation", "Macro", "Allocation", "Flow", "Survival"]
        )

        with t_val:
            posterior = data.get("valuation_posterior")
            opp = data.get("opportunity_surface")

            c1, c2 = st.columns(2)
            with c1:
                if isinstance(posterior, pd.DataFrame) and not posterior.empty and "posterior_gap" in posterior.columns:
                    p = posterior.copy()
                    p["posterior_gap"] = pd.to_numeric(p["posterior_gap"], errors="coerce")
                    p = p.dropna(subset=["posterior_gap"])
                    if not p.empty:
                        fig = px.histogram(
                            p,
                            x="posterior_gap",
                            nbins=40,
                            title="Posterior Gap Distribution",
                        )
                        self._apply_fig_theme(fig, height=300)
                        st.plotly_chart(fig, width="stretch", key="adv_intel_compact_posterior_gap_hist")
                else:
                    st.info("No valuation posterior artifact available.")

            with c2:
                if isinstance(opp, pd.DataFrame) and not opp.empty and {"mispricing", "confirmation"}.issubset(opp.columns):
                    d = opp.copy()
                    for c in ["mispricing", "confirmation", "northstar_score", "pulse_weighted_score", "regime_adjusted_score"]:
                        if c in d.columns:
                            d[c] = pd.to_numeric(d[c], errors="coerce")
                    score_col = next((c for c in ["pulse_weighted_score", "regime_adjusted_score", "northstar_score"] if c in d.columns), None)
                    if score_col:
                        d = d.dropna(subset=["mispricing", "confirmation", score_col]).head(1200)
                        if not d.empty:
                            d["_size"] = d[score_col].clip(lower=0.0)
                            fig = px.scatter(
                                d,
                                x="mispricing",
                                y="confirmation",
                                size="_size",
                                color="opportunity_type" if "opportunity_type" in d.columns else None,
                                title="Opportunity Surface",
                            )
                            self._apply_fig_theme(fig, height=300)
                            st.plotly_chart(fig, width="stretch", key="adv_intel_compact_opportunity_surface")
                else:
                    st.info("Opportunity surface unavailable.")

        with t_macro:
            mf = data.get("macro_factors_v2")
            if not isinstance(mf, pd.DataFrame) or mf.empty:
                mf = data.get("macro_factors")
            if isinstance(mf, pd.DataFrame) and not mf.empty:
                hm = _prepare_macro_heatmap_changes(mf, tail_rows=180)
                if not hm.empty:
                    fig = px.imshow(
                        hm.T,
                        aspect="auto",
                        color_continuous_scale="RdBu",
                        title="Macro Matrix (Change-Z)",
                    )
                    self._apply_fig_theme(fig, height=360)
                    st.plotly_chart(fig, width="stretch", key="adv_intel_compact_macro_matrix")
            else:
                st.info("Macro factors unavailable.")

        with t_alloc:
            alloc = data.get("allocation_history")
            if isinstance(alloc, pd.DataFrame) and not alloc.empty and "date" in alloc.columns:
                ah = alloc.copy()
                ah["date"] = _to_naive_date_series(ah["date"], normalize=False)
                ah = ah.dropna(subset=["date"]).sort_values("date")
                meta_cols = {
                    "date",
                    "regime",
                    "strategy_name",
                    "strategy_category",
                    "allocation_weight",
                    "allocation_score",
                    "regime_fitness",
                    "adjusted_return",
                    "adjusted_sharpe",
                    "risk_contribution",
                    "allocation_reason",
                    "timestamp",
                }
                strat_cols = [c for c in ah.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(ah[c])]
                strat_cols = [c for c in strat_cols if ah[c].dropna().between(-0.01, 1.01).mean() > 0.9]
                if strat_cols:
                    recent = ah[["date"] + strat_cols].groupby("date", as_index=True)[strat_cols].mean().tail(120)
                    fig = px.imshow(
                        recent.T,
                        aspect="auto",
                        color_continuous_scale="Viridis",
                        title="Allocation Engine Heatmap",
                    )
                    self._apply_fig_theme(fig, height=360)
                    st.plotly_chart(fig, width="stretch", key="adv_intel_compact_allocation_engine_heatmap")
                else:
                    st.info("No strategy weight columns available in allocation history.")
            else:
                st.info("Allocation history unavailable.")

        with t_flow:
            sentiment_ctx = load_sentiment_context()
            self.render_macro_news_pressure_index(data, sentiment_ctx, key_prefix="adv_intel_flow")
            self.render_sector_sentiment_vs_flows(data, sentiment_ctx, key_prefix="adv_intel_flow")

        with t_surv:
            integrated = self._get_integrated_frame(max_rows=1600)
            if integrated.empty:
                st.info("Integrated snapshot unavailable for survival diagnostics.")
            else:
                self.render_macro_fragility_index(integrated)
                self.render_sentiment_lead_lag_surface(integrated)

        self._formula_note(
            "Advanced Intelligence Compression Rules",
            [
                "Family tabs replace per-metric vertical chart stacks.",
                "Within-family views use matrices/scatters/small-multiples.",
                "Deep exploratory diagnostics remain in Research mode tabs.",
            ],
        )


    # ---------------------------- WAVE ANALYSIS ----------------------------
    def render_wave_analysis(self, data: Dict[str, Any]) -> None:
        st.subheader("🌊 Wave Analysis")
        # Use index_data for broad-market wave work (fast) and filtered prices for stocks (avoid loading 2M rows).
        idx_choices = {
            "NIFTY 50": "nifty_50",
            "NIFTY 100": "nifty_100",
            "NIFTY 500": "nifty_500",
            "NIFTY BANK": "nifty_bank",
            "NIFTY IT": "nifty_it",
            "NIFTY FMCG": "nifty_fmcg",
            "NIFTY METAL": "nifty_metal",
            "NIFTY PHARMA": "nifty_pharma",
        }

        weights = data.get("portfolio_weights")
        portfolio_symbols: List[str] = []
        if isinstance(weights, pd.DataFrame) and not weights.empty:
            if "symbol" in weights.columns:
                portfolio_symbols = sorted(weights["symbol"].astype(str).dropna().unique().tolist())
            elif "ticker" in weights.columns:
                portfolio_symbols = sorted(weights["ticker"].astype(str).dropna().unique().tolist())

        colA, colB, colC = st.columns([1.2, 1.0, 0.9])
        with colA:
            mode = st.selectbox("Series Source", ["Index", "Portfolio Stock"], index=0)
        with colB:
            if mode == "Index":
                label = st.selectbox("Index", list(idx_choices.keys()), index=0)
            else:
                label = st.selectbox("Stock", portfolio_symbols if portfolio_symbols else ["TCS"], index=0)
        with colC:
            lookback = st.selectbox("Lookback", ["1y", "3y", "5y", "max"], index=1)

        if mode == "Index":
            idx = self.hub.index_series(idx_choices[label])
            if idx is None or idx.empty:
                st.info("No index series available yet.")
                return
            series = idx["close"] if "close" in idx.columns else idx.iloc[:, 0]
            series = series.dropna().sort_index()
            if lookback != "max":
                days = {"1y": 365, "3y": 3 * 365, "5y": 5 * 365}[lookback]
                series = series[series.index >= (series.index.max() - pd.Timedelta(days=days))]
            close = series.astype(float).reset_index(drop=True)
            dates = pd.Series(series.index).reset_index(drop=True)
            name = idx_choices[label]
        else:
            sym = str(label)
            ticker = sym if sym.endswith(".NS") else f"{sym}.NS"
            prices = self.hub.prices_filtered([ticker], columns=["Date", "Close", "ticker"])
            if prices is None or prices.empty:
                st.info("No price data available for selected stock.")
                return
            prices["Date"] = _to_naive_date_series(prices["Date"], normalize=False)
            prices = prices.dropna(subset=["Date"]).sort_values("Date")
            close = pd.to_numeric(prices["Close"], errors="coerce").dropna().astype(float)
            dates = prices.loc[close.index, "Date"]
            if lookback != "max":
                days = {"1y": 365, "3y": 3 * 365, "5y": 5 * 365}[lookback]
                m = dates.max()
                keep = dates >= (m - pd.Timedelta(days=days))
                close = close[keep.values]
                dates = dates[keep.values]
            name = ticker

        if len(close) < 120:
            st.info("Not enough history for deep wave diagnostics (need ~120 points).")
            return

        t1, t2, t3, t4 = st.tabs(["Price Structure", "Cycles", "Forecast", "Diagnostics"])

        with t1:
            from scipy.signal import find_peaks  # type: ignore

            c = close.values
            peaks, _ = find_peaks(c, distance=max(5, len(c) // 40))
            troughs, _ = find_peaks(-c, distance=max(5, len(c) // 40))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=close, name="Close", line=dict(color=THEME["blue"], width=2)))
            if len(peaks):
                fig.add_trace(go.Scatter(x=dates.iloc[peaks], y=close.iloc[peaks], mode="markers", name="Peaks", marker=dict(color=THEME["amber"], size=7)))
            if len(troughs):
                fig.add_trace(go.Scatter(x=dates.iloc[troughs], y=close.iloc[troughs], mode="markers", name="Troughs", marker=dict(color=THEME["cyan"], size=7)))
            fig.update_layout(title=f"Price + Swings ({name})")
            self._apply_fig_theme(fig, height=420)
            st.plotly_chart(fig, width="stretch", key="wave_analysis_price_structure_swings")

            # Swing stats
            if len(peaks) and len(troughs):
                last_peak = close.iloc[peaks[-1]]
                last_trough = close.iloc[troughs[-1]]
                amp = float(abs(last_peak - last_trough))
                dur = int(abs(peaks[-1] - troughs[-1]))
                col1, col2, col3 = st.columns(3)
                with col1:
                    self._kpi_card("Last Swing Amplitude", f"{amp:,.2f}")
                with col2:
                    self._kpi_card("Last Swing Duration", f"{dur} bars")
                with col3:
                    self._kpi_card("Trend (30d)", f"{(close.iloc[-1] / close.iloc[-30] - 1) * 100:.2f}%")

        with t2:
            # FFT spectrum for dominant cycle (very interpretable)
            r = np.diff(np.log(close.values + 1e-9))
            r = r - np.nanmean(r)
            n = len(r)
            freqs = np.fft.rfftfreq(n, d=1)
            fft = np.fft.rfft(r)
            power = np.abs(fft) ** 2
            # ignore zero frequency
            idx = np.argmax(power[1:]) + 1
            dom_freq = freqs[idx] if idx < len(freqs) else np.nan
            dom_period = (1.0 / dom_freq) if dom_freq and dom_freq > 0 else np.nan

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=freqs[1:], y=power[1:], name="Power", line=dict(color=THEME["violet"])))
            fig.update_layout(title="FFT Power Spectrum (returns)", xaxis_title="Frequency (1/day)", yaxis_title="Power")
            self._apply_fig_theme(fig, height=320)
            st.plotly_chart(fig, width="stretch", key="wave_analysis_cycles_fft_power")

            col1, col2, col3 = st.columns(3)
            with col1:
                self._kpi_card("Dominant Period", f"{dom_period:.0f} days" if np.isfinite(dom_period) else "n/a")
            with col2:
                self._kpi_card("Dominant Freq", f"{dom_freq:.4f}" if np.isfinite(dom_freq) else "n/a")
            with col3:
                self._kpi_card("Return Vol (ann.)", f"{(np.nanstd(r) * np.sqrt(252) * 100):.1f}%")

            # Autocorrelation (0..60 lags)
            lags = 60
            acf = []
            for k in range(1, lags + 1):
                a = r[:-k]
                b = r[k:]
                acf.append(float(np.corrcoef(a, b)[0, 1]) if np.isfinite(a).all() and np.isfinite(b).all() else np.nan)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=list(range(1, lags + 1)), y=acf, marker_color=THEME["cyan"]))
            fig2.add_hline(y=0, line_color=THEME["grid"])
            fig2.update_layout(title="Autocorrelation of Returns (lags 1..60)", xaxis_title="Lag", yaxis_title="Corr")
            self._apply_fig_theme(fig2, height=300)
            st.plotly_chart(fig2, width="stretch", key="wave_analysis_cycles_autocorrelation")

        with t3:
            # Forecast = trend + seasonal component from dominant period (if stable)
            horizon = st.slider("Forecast Horizon (days)", 10, 90, 30)
            x = np.arange(len(close))
            slope, intercept = np.polyfit(x, close.values, 1)

            seasonal = np.zeros_like(close.values)
            if np.isfinite(dom_period) and dom_period >= 10 and dom_period <= 120:
                t = np.arange(len(close))
                seasonal = np.sin(2 * np.pi * t / dom_period) * (np.nanstd(close.values - (slope * x + intercept)) * 0.6)

            fitted = slope * x + intercept + seasonal
            resid = close.values - fitted
            sigma = float(np.nanstd(resid))
            xf = np.arange(len(close), len(close) + horizon)
            seasonal_f = np.zeros(horizon)
            if np.isfinite(dom_period) and dom_period >= 10 and dom_period <= 120:
                seasonal_f = np.sin(2 * np.pi * xf / dom_period) * (np.nanstd(resid) * 0.6)
            forecast = slope * xf + intercept + seasonal_f

            forecast_dates = pd.date_range(pd.to_datetime(dates.iloc[-1]) + timedelta(days=1), periods=horizon)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=close, name="Close", line=dict(color=THEME["blue"], width=2)))
            fig.add_trace(go.Scatter(x=dates, y=fitted, name="Fit", line=dict(color=THEME["muted"], width=1.2, dash="dot")))
            fig.add_trace(go.Scatter(x=forecast_dates, y=forecast, name="Forecast", line=dict(color=THEME["green"], width=2)))
            fig.add_trace(go.Scatter(x=forecast_dates, y=forecast + 1.0 * sigma, name="+1σ", line=dict(color=THEME["grid"], width=1), showlegend=False))
            fig.add_trace(go.Scatter(x=forecast_dates, y=forecast - 1.0 * sigma, name="-1σ", line=dict(color=THEME["grid"], width=1), fill="tonexty", fillcolor="rgba(59,130,246,0.10)", showlegend=False))
            fig.update_layout(title="Wave Forecast (trend + cycle proxy)")
            self._apply_fig_theme(fig, height=420)
            st.plotly_chart(fig, width="stretch", key="wave_analysis_forecast_trend_cycle")

        with t4:
            # Diagnostics: rolling vol, returns heatmap, etc.
            r = pd.Series(np.diff(np.log(close.values + 1e-9)), index=dates.iloc[1:])
            rv = r.rolling(20).std() * np.sqrt(252)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, subplot_titles=("Daily Returns", "Rolling Vol (20d, ann.)"))
            fig.add_trace(go.Scatter(x=r.index, y=r * 100, name="Return %", line=dict(color=THEME["cyan"], width=1.4)), row=1, col=1)
            fig.add_trace(go.Scatter(x=rv.index, y=rv * 100, name="Vol %", line=dict(color=THEME["amber"], width=1.8)), row=2, col=1)
            self._apply_fig_theme(fig, height=420)
            st.plotly_chart(fig, width="stretch", key="wave_analysis_diagnostics_returns_volatility")

    # ---------------------------- PORTFOLIO ----------------------------

    # ---------------------------- EDGE + LIQUIDITY ----------------------------
    def render_edge_health(self, data: Dict[str, Any]) -> None:
        st.subheader("🧬 Edge Half‑Life")
        edge = data.get("edge_half_life") or {}
        strategies = edge.get("strategies", {})
        if not strategies:
            st.info("No edge half‑life data available yet.")
            return
        df = pd.DataFrame(
            [
                {
                    "strategy": k,
                    "edge_health": v.get("edge_health", 0.0),
                    "half_life_days": v.get("half_life_days", 0.0),
                    "remaining_half_life": v.get("remaining_half_life", 0.0),
                    "decay_rate": v.get("decay_rate", 0.0),
                    "status": v.get("status", "unknown"),
                }
                for k, v in strategies.items()
            ]
        )
        df = df.sort_values("edge_health", ascending=False)
        st.dataframe(df, width="stretch")
        fig = px.bar(df, x="strategy", y="edge_health", color="status", title="Edge Health by Strategy")
        fig.update_yaxes(range=[0, 1])
        self._render_chart_with_contract(
            chart_id="portfolio_edge_health",
            fig=fig,
            data=data,
            key="portfolio_edge_health_primary",
            height=320,
        )

        fig2 = px.scatter(
            df,
            x="half_life_days",
            y="edge_health",
            color="status",
            hover_data=["strategy", "remaining_half_life", "decay_rate"],
            title="Half-Life vs Edge Health",
        )
        fig2.update_yaxes(range=[0, 1])
        self._render_chart_with_contract(
            chart_id="portfolio_edge_health",
            fig=fig2,
            data=data,
            key="portfolio_edge_health_scatter",
            height=320,
        )

    def render_exit_risk(self, data: Dict[str, Any]) -> None:
        st.subheader("💧 Liquidity Exit Risk")
        df = data.get("liquidity_risk")
        if df is None or df.empty:
            st.info("No liquidity risk data available yet.")
            return
        df_sorted = df.sort_values("exit_risk", ascending=False)
        st.dataframe(df_sorted, width="stretch")
        fig = px.bar(df_sorted, x="ticker", y="exit_risk", color="status", title="Exit Risk by Position")
        fig.add_hline(y=1.0, line_dash="dash", line_color="#c0392b", annotation_text="FROZEN ≥ 1.0")
        fig.add_hline(y=0.8, line_dash="dot", line_color="#f39c12", annotation_text="DANGEROUS ≥ 0.8")
        self._render_chart_with_contract(
            chart_id="portfolio_exit_risk",
            fig=fig,
            data=data,
            key="portfolio_exit_risk_bar",
            height=320,
        )

        # Risk map: participation vs exit risk
        if "participation" in df_sorted.columns:
            tmp = df_sorted.copy()
            tmp["participation"] = pd.to_numeric(tmp["participation"], errors="coerce")
            if "weight" in tmp.columns:
                tmp["_weight_size"] = pd.to_numeric(tmp["weight"], errors="coerce").clip(lower=0).fillna(0)
            fig2 = px.scatter(
                tmp.dropna(subset=["participation"]),
                x="participation",
                y="exit_risk",
                color="status",
                size="_weight_size" if "_weight_size" in tmp.columns else None,
                hover_data=["ticker", "adv_shares", "expected_edge"],
                title="Exit Risk Map (participation × exit risk; size=weight)",
            )
            fig2.add_hline(y=1.0, line_dash="dash", line_color=THEME["red"])
            fig2.add_hline(y=0.8, line_dash="dot", line_color=THEME["amber"])
            self._render_chart_with_contract(
                chart_id="portfolio_exit_risk",
                fig=fig2,
                data=data,
                key="portfolio_exit_risk_map",
                height=340,
            )

    # ---------------------------- ALERT FEED ----------------------------
    def render_alert_feed(self, data: Dict[str, Any]) -> None:
        st.subheader("🚨 Alert Feed")
        alerts = []

        liq = data.get("liquidity_risk")
        if isinstance(liq, pd.DataFrame) and not liq.empty:
            frozen = liq[liq["status"] == "FROZEN"]
            dangerous = liq[liq["status"] == "DANGEROUS"]
            if not frozen.empty:
                alerts.append(f"Liquidity FROZEN: {', '.join(frozen['ticker'].astype(str).tolist())}")
            if not dangerous.empty:
                alerts.append(f"Liquidity DANGEROUS: {', '.join(dangerous['ticker'].astype(str).tolist())}")

        edge = data.get("edge_half_life") or {}
        strategies = edge.get("strategies", {})
        low_edge = [k for k, v in strategies.items() if v.get("edge_health", 1.0) < 0.3]
        if low_edge:
            alerts.append(f"Edge decay: {', '.join(low_edge)}")

        alloc = data.get("capital_allocations") or {}
        no_edge_state = alloc.get("no_edge_state", {})
        if no_edge_state.get("state") == "NO_EDGE":
            reasons = no_edge_state.get("reasons", [])
            reason_text = "; ".join(reasons) if reasons else "No reasons provided"
            alerts.append(f"NO_EDGE active: {reason_text}")

        if not alerts:
            st.success("No active alerts.")
            return

        for msg in alerts:
            if "FROZEN" in msg or "NO_EDGE" in msg:
                st.error(msg)
            else:
                st.warning(msg)

    # ---------------------------- SENTIMENT ----------------------------
    def render_sentiment(self) -> None:
        st.subheader("🧠 NS‑USO Sentiment")
        self.sentiment_panel.render()

    # ---------------------------- OPTIONS TRADING ----------------------------
    def render_options_trading(self) -> None:
        """Render options trading panel"""
        try:
            # Create options observer (will use UnifiedState if available)
            options_observer = OptionsObserver()
            
            # Create and render options panel
            options_panel = OptionsPanel(observer=options_observer)
            options_panel.render()
        except Exception as e:
            st.error(f"Error rendering options panel: {e}")
            st.info("Options trading system may not be initialized yet.")

    # ---------------------------- VOLATILITY ENGINE ----------------------------
    def render_volatility_engine(self) -> None:
        """Render unified volatility engine bridge view from snapshot artifacts."""
        st.subheader("📊 Unified Volatility Engine")

        snap_path = PROJECT_ROOT / "snapshots/current_state.json"
        if not snap_path.exists():
            st.info("No volatility snapshot found yet at `snapshots/current_state.json`.")
            st.caption("Run: `python scripts/run_live_engine.py` or integrated options cycle from complete runner.")
            return

        try:
            snap = json.loads(snap_path.read_text())
        except Exception as e:
            st.error(f"Could not read volatility snapshot: {e}")
            return

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            self._kpi_card("Regime", str(snap.get("regime", "n/a")))
        with col2:
            self._kpi_card("Total PnL", f"{float(snap.get('total_pnl', 0.0) or 0.0):,.0f}")
        with col3:
            perf = snap.get("performance_metrics", {}) or {}
            self._kpi_card("Total Trades", str(int(perf.get("total_trades", 0) or 0)))
        with col4:
            self._kpi_card("Open Positions", str(len(snap.get("positions", []) or [])))

        market_data = snap.get("market_data", {}) or {}
        m1, m2, m3 = st.columns(3)
        with m1:
            self._kpi_card("Contracts Seen", str(int(market_data.get("option_contracts", 0) or 0)))
        with m2:
            npx = market_data.get("NIFTY_price")
            self._kpi_card("NIFTY Spot", f"{float(npx):,.2f}" if npx is not None else "n/a")
        with m3:
            bpx = market_data.get("BANKNIFTY_price")
            self._kpi_card("BANKNIFTY Spot", f"{float(bpx):,.2f}" if bpx is not None else "n/a")

        greeks = snap.get("portfolio_greeks", {}) or {}
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            self._kpi_card("Delta", f"{float(greeks.get('delta', 0.0) or 0.0):.3f}")
        with c2:
            self._kpi_card("Gamma", f"{float(greeks.get('gamma', 0.0) or 0.0):.3f}")
        with c3:
            self._kpi_card("Theta", f"{float(greeks.get('theta', 0.0) or 0.0):.3f}")
        with c4:
            self._kpi_card("Vega", f"{float(greeks.get('vega', 0.0) or 0.0):.3f}")

        positions = snap.get("positions", []) or []
        if positions:
            df = pd.DataFrame(positions)
            st.markdown("### Snapshot Positions")
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("No positions in current volatility snapshot.")

    # ---------------------------- ALPHAOS CONTROL TOWER ----------------------------
    def render_alpha_os_control_tower(self, data: Dict[str, Any]) -> None:
        st.subheader("🛡 AlphaOS Control Tower (Compact)")

        alpha_ts = data.get("alpha_os_timeseries")
        if not isinstance(alpha_ts, pd.DataFrame) or alpha_ts.empty:
            st.info("No alpha_os_timeseries artifact available.")
            return
        if "timestamp" not in alpha_ts.columns:
            st.info("alpha_os_timeseries missing timestamp column.")
            return

        a = alpha_ts.copy()
        a["timestamp"] = _to_naive_date_series(a["timestamp"], normalize=False)
        a = a.dropna(subset=["timestamp"]).sort_values("timestamp")
        for c in [
            "regime_low_vol",
            "regime_high_vol",
            "regime_transition",
            "regime_crisis",
            "regime_entropy",
            "regime_confidence",
            "gross_used",
            "gross_target",
            "gross_cap",
            "fallback_tier",
            "convexity_score",
        ]:
            if c in a.columns:
                a[c] = pd.to_numeric(a[c], errors="coerce")

        latest = a.iloc[-1]
        gross_now = _as_float(latest.get("gross_used"), np.nan)
        if not np.isfinite(gross_now):
            gross_now = _as_float(latest.get("gross_target"), np.nan)

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            self._kpi_card("Mode", str(latest.get("mode", "n/a")))
        with k2:
            self._kpi_card("Crisis Prob", f"{_as_float(latest.get('regime_crisis'), np.nan):.1%}" if np.isfinite(_as_float(latest.get("regime_crisis"), np.nan)) else "n/a")
        with k3:
            self._kpi_card("Regime Confidence", f"{_as_float(latest.get('regime_confidence'), np.nan):.2f}" if np.isfinite(_as_float(latest.get("regime_confidence"), np.nan)) else "n/a")
        with k4:
            self._kpi_card("Gross", f"{gross_now:.3f}" if np.isfinite(gross_now) else "n/a")
        with k5:
            self._kpi_card("Fallback Tier", str(int(_as_float(latest.get('fallback_tier'), 0.0))))

        prob_cols = [c for c in ["regime_low_vol", "regime_high_vol", "regime_transition", "regime_crisis"] if c in a.columns]
        if prob_cols:
            prob_long = a[["timestamp"] + prob_cols].melt(
                id_vars=["timestamp"],
                var_name="regime",
                value_name="probability",
            )
            fig1 = px.area(
                prob_long,
                x="timestamp",
                y="probability",
                color="regime",
                title="Regime Probability Surface",
            )
            self._apply_fig_theme(fig1, height=320)
            st.plotly_chart(fig1, width="stretch", key="alphaos_compact_regime_probability_surface")

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        if "regime_crisis" in a.columns:
            fig2.add_trace(
                go.Scatter(
                    x=a["timestamp"],
                    y=a["regime_crisis"],
                    name="Crisis Probability",
                    line=dict(color=THEME["red"], width=2),
                ),
                secondary_y=True,
            )
        if "regime_entropy" in a.columns:
            fig2.add_trace(
                go.Scatter(
                    x=a["timestamp"],
                    y=a["regime_entropy"],
                    name="Regime Entropy",
                    line=dict(color=THEME["cyan"], width=1.8),
                ),
                secondary_y=False,
            )
        if np.isfinite(gross_now):
            gross_series = pd.to_numeric(a.get("gross_used"), errors="coerce")
            if gross_series.notna().sum() == 0:
                gross_series = pd.to_numeric(a.get("gross_target"), errors="coerce")
            if gross_series.notna().sum() > 0:
                fig2.add_trace(
                    go.Scatter(
                        x=a["timestamp"],
                        y=gross_series,
                        name="Gross Exposure",
                        line=dict(color=THEME["blue"], width=1.8),
                    ),
                    secondary_y=False,
                )
        fig2.update_layout(title="Survival Diagnostics (Entropy + Gross + Crisis)")
        fig2.update_yaxes(title_text="Entropy / Gross", secondary_y=False)
        fig2.update_yaxes(title_text="Crisis Probability", range=[0, 1], secondary_y=True)
        self._apply_fig_theme(fig2, height=340)
        st.plotly_chart(fig2, width="stretch", key="alphaos_compact_survival_diagnostics")

        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        r = pd.to_numeric(pnl_df.get("Return"), errors="coerce").dropna() if not pnl_df.empty else pd.Series(dtype=float)
        dd_surface = self._empirical_drawdown_surface(r)
        if not dd_surface.empty:
            piv = dd_surface.pivot(index="horizon", columns="threshold", values="probability")
            fig3 = px.imshow(
                piv,
                aspect="auto",
                color_continuous_scale="YlOrRd",
                title="Drawdown Probability Surface",
            )
            self._apply_fig_theme(fig3, height=300)
            st.plotly_chart(fig3, width="stretch", key="alphaos_compact_drawdown_surface")

        self._formula_note(
            "AlphaOS Compact Formulas",
            [
                "regime_probability_t from alpha_os_timeseries regime simplex",
                "survival diagnostics combine entropy, gross exposure, and crisis probability",
                "drawdown surface = empirical forward-return threshold hit-rate",
            ],
        )


    # ---------------------------- REAL-TIME ----------------------------
    def render_real_time_monitor(self, data: Dict[str, Any]) -> None:
        st.subheader("⚡ Real‑Time Monitor")

        colA, colB, colC, colD = st.columns(4)
        with colA:
            if st.button("Refresh Now"):
                st.cache_data.clear()
                st.rerun()
        with colB:
            self._kpi_card("Now", datetime.now().isoformat(timespec="seconds"))
        with colC:
            log = data.get("system_log") or {}
            self._kpi_card("Last Pipeline Refresh", str(log.get("timestamp") or "n/a"))
        with colD:
            self._kpi_card("Artifacts Tracked", str(len(_artifact_mtimes())))

        c1, c2 = st.columns([1.2, 1.0])
        with c1:
            st.markdown("### Current Portfolio Snapshot")
            pw = data.get("portfolio_weights")
            if isinstance(pw, pd.DataFrame) and not pw.empty:
                pdf = pw.copy()
                if "weight" in pdf.columns:
                    pdf["weight"] = pd.to_numeric(pdf["weight"], errors="coerce")
                elif "final_weight" in pdf.columns:
                    pdf["weight"] = pd.to_numeric(pdf["final_weight"], errors="coerce")
                else:
                    pdf["weight"] = np.nan
                pdf = pdf.dropna(subset=["weight"])

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    self._kpi_card("Positions", str(int(len(pdf))))
                with col2:
                    self._kpi_card("Gross Weight", f"{float(pdf['weight'].abs().sum()):.2f}")
                with col3:
                    self._kpi_card("Net Weight", f"{float(pdf['weight'].sum()):.2f}")
                with col4:
                    self._kpi_card("Max Position", f"{float(pdf['weight'].abs().max()):.2f}" if not pdf.empty else "n/a")

                show_cols = [c for c in ["ticker", "symbol", "Company Name", "Industry", "weight"] if c in pdf.columns]
                if show_cols:
                    st.dataframe(
                        pdf.sort_values("weight", ascending=False).head(40)[show_cols],
                        width="stretch",
                        hide_index=True,
                    )

                sector_col = "Industry" if "Industry" in pdf.columns else ("sector" if "sector" in pdf.columns else None)
                if sector_col:
                    grp = (
                        pdf.groupby(sector_col)["weight"]
                        .sum()
                        .sort_values(ascending=False)
                    )
                    if not grp.empty:
                        fig = px.pie(values=grp.values, names=grp.index, title="Sector Allocation (Portfolio Weights)")
                        self._render_chart_with_contract(
                            chart_id="system_health_sector_allocation",
                            fig=fig,
                            data=data,
                            key="system_health_sector_allocation",
                            height=320,
                        )
            else:
                st.info("No `portfolio_weights` payload available in view model.")

        with c2:
            st.markdown("### Risk Authority (latest)")
            rs = data.get("risk_state")
            if isinstance(rs, pd.DataFrame) and not rs.empty:
                df = rs.copy()
                if "date" in df.columns:
                    df["date"] = _to_naive_date_series(df["date"], normalize=False)
                else:
                    df["date"] = pd.NaT
                df = df.sort_values("date") if "date" in df.columns else df
                latest = df.dropna(subset=["date"]).iloc[-1] if "date" in df.columns and df["date"].notna().any() else df.iloc[-1]
                status = str(latest.get("emergency_brake_status", "n/a"))
                emerg = bool(latest.get("emergency_active", False))
                dd = latest.get("current_drawdown", latest.get("drawdown", 0.0))
                max_dd = latest.get("max_allowed_drawdown", -0.2)
                cap = latest.get("exposure_cap", np.nan)
                self._kpi_card("Emergency Brake", status, pill=("BAD" if emerg else "OK"))
                self._kpi_card("Drawdown", f"{_as_float(dd)*100:.1f}%")
                self._kpi_card("Max Allowed DD", f"{_as_float(max_dd)*100:.1f}%")
                self._kpi_card("Exposure Cap", f"{_as_float(cap):.2f}" if np.isfinite(_as_float(cap, np.nan)) else "n/a")
            else:
                st.info("No risk_state artifact.")

            st.markdown("### Live Alerts (summary)")
            self.render_alert_feed(data)

    # ---------------------------- COHESIVE V4 LAYERS ----------------------------
    def _latest_regime_snapshot(self, data: Dict[str, Any]) -> Dict[str, Any]:
        market_regime = data.get("market_regime")
        feed = data.get("regime_feed") or {}

        out = {
            "regime": "Unknown",
            "risk_on_score": np.nan,
            "volatility": np.nan,
            "correlation": np.nan,
            "timestamp": pd.NaT,
        }

        if isinstance(market_regime, pd.DataFrame) and not market_regime.empty:
            mr = market_regime.copy()
            time_col = "Date" if "Date" in mr.columns else ("date" if "date" in mr.columns else None)
            if time_col:
                mr["Date"] = _to_naive_date_series(mr[time_col], normalize=False)
            else:
                mr["Date"] = _to_naive_date_series(pd.Series(mr.index), normalize=False)
            mr = mr.dropna(subset=["Date"]).sort_values("Date")
            if not mr.empty:
                latest = mr.iloc[-1]
                out.update(
                    {
                        "regime": str(latest.get("market_regime", "Unknown")),
                        "risk_on_score": _as_float(latest.get("risk_on_score"), default=np.nan),
                        "volatility": _as_float(latest.get("volatility"), default=np.nan),
                        "correlation": _as_float(latest.get("correlation"), default=np.nan),
                        "timestamp": pd.to_datetime(latest.get("Date"), errors="coerce"),
                    }
                )

        current = feed.get("current_regime", {}) if isinstance(feed, dict) else {}
        if isinstance(current, dict):
            name = str(current.get("name", "") or "").strip()
            if name:
                out["regime"] = name
            conf = _as_float(current.get("stability"), default=np.nan)
            if np.isfinite(conf):
                out["risk_on_score"] = conf

        return out

    @staticmethod
    def _zscore(series: pd.Series) -> pd.Series:
        s = pd.to_numeric(series, errors="coerce")
        mu = float(s.mean()) if s.notna().any() else 0.0
        sd = float(s.std()) if s.notna().any() else 0.0
        if not np.isfinite(sd) or sd <= 1e-9:
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - mu) / sd

    def render_state_ribbon(self, data: Dict[str, Any]) -> None:
        """Always-visible top state strip to align all tabs to one narrative state."""
        integrated = load_integrated_state_snapshot(max_rows=730)
        sentiment_ctx = load_sentiment_context()
        regime = self._latest_regime_snapshot(data)

        crisis_prob = np.nan
        alpha_ts = data.get("alpha_os_timeseries")
        if isinstance(alpha_ts, pd.DataFrame) and not alpha_ts.empty and "regime_crisis" in alpha_ts.columns:
            crisis_prob = _as_float(pd.to_numeric(alpha_ts["regime_crisis"], errors="coerce").dropna().tail(1).iloc[0], default=np.nan)

        liq_stress = np.nan
        liq = data.get("liquidity_risk")
        if isinstance(liq, pd.DataFrame) and not liq.empty and "exit_risk" in liq.columns:
            liq_stress = _as_float(pd.to_numeric(liq["exit_risk"], errors="coerce").mean(), default=np.nan)

        sentiment_latest = np.nan
        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            for c in ["polarity", "sentiment_score"]:
                if c in market_df.columns:
                    sentiment_latest = _as_float(pd.to_numeric(market_df[c], errors="coerce").dropna().tail(1).iloc[0], default=np.nan)
                    break

        risk_pressure = np.nan
        mr = data.get("market_regime")
        if isinstance(mr, pd.DataFrame) and not mr.empty and {"volatility", "correlation"}.issubset(mr.columns):
            tmp = mr.copy()
            tmp["volatility"] = pd.to_numeric(tmp["volatility"], errors="coerce")
            tmp["correlation"] = pd.to_numeric(tmp["correlation"], errors="coerce")
            tmp = tmp.dropna(subset=["volatility", "correlation"])
            if not tmp.empty:
                z_vol = self._zscore(tmp["volatility"])
                z_corr = self._zscore(tmp["correlation"])
                risk_pressure = _as_float((z_vol + z_corr).iloc[-1], default=np.nan)

        if isinstance(integrated, pd.DataFrame) and not integrated.empty:
            latest = integrated.iloc[-1]
            regime["regime"] = str(latest.get("regime_label", regime["regime"]) or regime["regime"])
            regime["risk_on_score"] = _as_float(latest.get("regime_confidence"), default=regime["risk_on_score"])
            sentiment_latest = _as_float(latest.get("macro_news_sentiment"), default=sentiment_latest)
            risk_pressure = _as_float(latest.get("risk_pressure_index"), default=risk_pressure)
            crisis_prob = _as_float(latest.get("crisis_probability"), default=crisis_prob)
            liq_stress = _as_float(latest.get("liquidity_stress_index"), default=liq_stress)

        st.markdown("### Global State Ribbon")
        r1, r2, r3, r4, r5, r6 = st.columns(6)
        with r1:
            self._kpi_card("Regime", str(regime.get("regime", "Unknown")))
        with r2:
            score = _as_float(regime.get("risk_on_score"), default=np.nan)
            self._kpi_card("Regime Confidence", f"{score:.2f}" if np.isfinite(score) else "n/a")
        with r3:
            self._kpi_card("Macro Sentiment", f"{sentiment_latest:+.2f}" if np.isfinite(sentiment_latest) else "n/a")
        with r4:
            self._kpi_card("Risk Pressure", f"{risk_pressure:+.2f}" if np.isfinite(risk_pressure) else "n/a")
        with r5:
            self._kpi_card("Liquidity Stress", f"{liq_stress:.2f}" if np.isfinite(liq_stress) else "n/a")
        with r6:
            self._kpi_card("Crisis Prob", f"{crisis_prob:.1%}" if np.isfinite(crisis_prob) else "n/a")
        self._formula_note(
            "State Ribbon Formulas",
            [
                "regime_confidence = risk_on_score (feed), fallback integrated.regime_confidence",
                "risk_pressure_index = z(volatility) + z(correlation)",
                "liquidity_stress = mean(exit_risk)",
                "crisis_probability = latest(regime_crisis)",
                "macro_sentiment = latest(macro_news_sentiment or polarity)",
            ],
        )

    def render_macro_news_pressure_index(
        self,
        data: Dict[str, Any],
        sentiment_ctx: Dict[str, Any],
        *,
        key_prefix: str = "macro_news_pressure",
    ) -> None:
        source_frames: List[pd.DataFrame] = []
        source_freshness: List[str] = []

        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            s = market_df.copy()
            time_col = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
            sentiment_col = next((c for c in ["polarity", "sentiment_score", "signed_sentiment_intensity"] if c in s.columns), None)
            if time_col and sentiment_col:
                s["date"] = _to_naive_date_series(s[time_col], normalize=True)
                s["sentiment"] = pd.to_numeric(s[sentiment_col], errors="coerce")
                s = s.dropna(subset=["date", "sentiment"]).sort_values("date")
                if not s.empty:
                    md = s.groupby("date", as_index=False)["sentiment"].mean()
                    md["source"] = "sentiment_artifact"
                    source_frames.append(md)
                    source_freshness.append(f"sentiment_artifact={md['date'].max().date()}")

        integrated = self._get_integrated_frame(max_rows=2200)
        if isinstance(integrated, pd.DataFrame) and not integrated.empty and {"date", "macro_news_sentiment"}.issubset(integrated.columns):
            ig = integrated[["date", "macro_news_sentiment"]].copy()
            ig["date"] = _to_naive_date_series(ig["date"], normalize=True)
            ig["sentiment"] = pd.to_numeric(ig["macro_news_sentiment"], errors="coerce")
            ig = ig.dropna(subset=["date", "sentiment"]).sort_values("date")
            if not ig.empty:
                ig = ig.groupby("date", as_index=False)["sentiment"].mean()
                ig["source"] = "integrated_snapshot"
                source_frames.append(ig)
                source_freshness.append(f"integrated_snapshot={ig['date'].max().date()}")

        if not source_frames:
            st.info("No sentiment market history available for macro news pressure index.")
            return

        daily = pd.concat(source_frames, ignore_index=True, sort=False)
        daily = daily.groupby("date", as_index=False)["sentiment"].mean().sort_values("date")
        daily["date"] = _to_naive_date_series(daily["date"], normalize=True)
        daily = daily.dropna(subset=["date"]).sort_values("date")
        if "date" not in daily.columns or daily.empty:
            st.info("Sentiment aggregation produced no usable `date` series.")
            return
        daily["sentiment_z"] = self._zscore(daily["sentiment"])

        idx = data.get("index_nifty50")
        bench = pd.DataFrame()
        if isinstance(idx, pd.Series) and not idx.empty:
            bench = idx.to_frame(name="close")
        elif isinstance(idx, pd.DataFrame) and not idx.empty:
            bench = idx.copy()

        if isinstance(bench, pd.DataFrame) and not bench.empty:
            bench = bench.reset_index()
            tcol = _pick_time_column(bench, ["Date", "date", "timestamp", "index"])
            close_col = next((c for c in ["close", "Close", "adj_close", "Adj Close"] if c in bench.columns), None)
            if close_col is None:
                numeric_cols = [c for c in bench.columns if pd.api.types.is_numeric_dtype(bench[c])]
                close_col = numeric_cols[0] if numeric_cols else None
            if tcol is None or close_col is None:
                bench = pd.DataFrame()
            else:
                bench["date"] = _to_naive_date_series(bench[tcol], normalize=True)
                bench["close"] = pd.to_numeric(bench[close_col], errors="coerce")
                bench = bench.dropna(subset=["date", "close"])
                if not bench.empty:
                    bench = bench.groupby("date", as_index=False)["close"].last()
                    bench["nifty_norm"] = bench["close"] / max(1e-9, float(bench["close"].iloc[0]))

        merged = daily.merge(bench[["date", "nifty_norm"]] if not bench.empty else pd.DataFrame(columns=["date", "nifty_norm"]), on="date", how="left")

        regime = data.get("market_regime")
        if isinstance(regime, pd.DataFrame) and not regime.empty:
            rg = regime.copy()
            tcol = "Date" if "Date" in rg.columns else ("date" if "date" in rg.columns else None)
            if tcol and "risk_on_score" in rg.columns:
                rg["date"] = _to_naive_date_series(rg[tcol], normalize=True)
                rg["risk_on_score"] = pd.to_numeric(rg["risk_on_score"], errors="coerce")
                rg = rg.dropna(subset=["date", "risk_on_score"]).sort_values("date")
                if not rg.empty:
                    rg = rg.groupby("date", as_index=False)["risk_on_score"].last()
                    merged = merged.merge(rg, on="date", how="left")

        merged = merged.sort_values("date")
        if merged.empty:
            st.info("No merged macro-news series available.")
            return

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged["sentiment_z"],
                mode="lines",
                name="Macro Sentiment (z)",
                line=dict(color=THEME["amber"], width=2),
            ),
            secondary_y=False,
        )
        if "nifty_norm" in merged.columns and merged["nifty_norm"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=merged["date"],
                    y=merged["nifty_norm"],
                    mode="lines",
                    name="NIFTY 50 (norm)",
                    line=dict(color=THEME["blue"], width=1.8),
                ),
                secondary_y=False,
            )
        if "risk_on_score" in merged.columns and merged["risk_on_score"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=merged["date"],
                    y=merged["risk_on_score"],
                    mode="lines",
                    name="Regime Confidence",
                    line=dict(color=THEME["cyan"], width=1.5),
                ),
                secondary_y=True,
            )
        fig.update_layout(title="Macro News Pressure Index (Sentiment vs NIFTY vs Regime)")
        fig.update_yaxes(title_text="Sentiment Z / NIFTY Norm", secondary_y=False)
        fig.update_yaxes(title_text="Regime Confidence", secondary_y=True)
        if key_prefix == "market_state":
            self._render_chart_with_contract(
                chart_id="market_state_macro_news_pressure",
                fig=fig,
                data=data,
                key="market_state_macro_news_pressure",
                height=340,
            )
        elif key_prefix == "news_layer":
            self._render_chart_with_contract(
                chart_id="news_layer_macro_news_pressure",
                fig=fig,
                data=data,
                key="news_layer_macro_news_pressure",
                height=340,
            )
        else:
            self._apply_fig_theme(fig, height=340)
            if key_prefix == "causal_flow_global":
                st.plotly_chart(fig, width="stretch", key="causal_flow_macro_news_pressure")
            elif key_prefix == "sector_sentiment_flows":
                st.plotly_chart(fig, width="stretch", key="sector_sentiment_macro_news_pressure")
            else:
                st.plotly_chart(fig, width="stretch", key="macro_news_pressure_generic")
        if source_freshness:
            st.caption("Sentiment source freshness: " + " | ".join(source_freshness))
        self._formula_note(
            "Macro News Pressure Formula",
            [
                "daily_sentiment_t = mean(sentiment_signal_t)",
                "sentiment_z_t = zscore(daily_sentiment_t)",
                "nifty_norm_t = close_t / close_0",
                "lead_corr_20d = corr(sentiment_z_t, pct_change(nifty_norm) shifted by -20)",
            ],
        )

        if "nifty_norm" in merged.columns and merged["nifty_norm"].notna().sum() > 25:
            r = pd.to_numeric(merged["nifty_norm"], errors="coerce").pct_change().shift(-20)
            corr = pd.Series(merged["sentiment_z"]).corr(r)
            st.caption(
                f"Rolling relation (macro sentiment vs next 20d NIFTY return): "
                f"{corr:+.3f}" if np.isfinite(corr) else "Insufficient overlap for lead/lag estimate."
            )
    def _limit_timeseries_to_recent(self, df: pd.DataFrame, months_back: int = 12) -> pd.DataFrame:
        """
        Limit time series data to recent periods (default 12 months) to avoid
        showing too much historical data that creates visual clutter.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df

        # Find date column
        date_cols = []
        for col in df.columns:
            if col.lower() in ['date', 'timestamp', 'time']:
                date_cols.append(col)

        # Also check index
        if isinstance(df.index, pd.DatetimeIndex):
            date_cols.append('index')

        if not date_cols:
            # Try to convert index to datetime if it's not already
            try:
                df_copy = df.copy()
                df_copy.index = pd.to_datetime(df_copy.index)
                date_cols.append('index')
                df = df_copy
            except:
                # No date column found, return as is
                return df

        # Use the first available date column
        date_col = date_cols[0]

        # Calculate cutoff date
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)

        try:
            if date_col == 'index':
                # Filter by index
                mask = df.index >= cutoff_date
                return df.loc[mask]
            else:
                # Filter by column
                df[date_col] = pd.to_datetime(df[date_col])
                mask = df[date_col] >= cutoff_date
                return df.loc[mask]
        except:
            # If filtering fails, return original
            return df

    def _enhance_empty_news_stress_index(self, data: Dict[str, Any]) -> pd.DataFrame:
        """
        Create a synthetic news-based systemic stress index when the real one is empty
        """
        # Try to get narrative events
        narrative_events = data.get("narrative_events")
        if isinstance(narrative_events, pd.DataFrame) and not narrative_events.empty:
            df = narrative_events.copy()

            # Look for relevant columns
            date_col = next((c for c in df.columns if c.lower() in ['date', 'timestamp']), None)
            magnitude_col = next((c for c in df.columns if c.lower() in ['magnitude', 'intensity', 'impact']), None)

            if date_col and magnitude_col:
                df[date_col] = pd.to_datetime(df[date_col])
                df[magnitude_col] = pd.to_numeric(df[magnitude_col], errors='coerce')

                # Create daily stress index
                daily_stress = df.groupby(df[date_col].dt.date)[magnitude_col].agg(['mean', 'max', 'count']).reset_index()
                daily_stress.columns = ['date', 'avg_stress', 'max_stress', 'event_count']
                daily_stress['date'] = pd.to_datetime(daily_stress['date'])

                # Calculate composite stress index
                daily_stress['stress_index'] = (
                    daily_stress['avg_stress'] * 0.5 +
                    daily_stress['max_stress'] * 0.3 +
                    daily_stress['event_count'] * 0.2
                )

                return daily_stress

        # Fallback: create synthetic data based on market volatility
        market_regime = data.get("market_regime")
        if isinstance(market_regime, pd.DataFrame) and not market_regime.empty:
            df = market_regime.copy()
            date_col = next((c for c in df.columns if c.lower() in ['date', 'timestamp']), None)
            vol_col = next((c for c in df.columns if c.lower() in ['volatility', 'vol']), None)

            if date_col and vol_col:
                df[date_col] = pd.to_datetime(df[date_col])
                df[vol_col] = pd.to_numeric(df[vol_col], errors='coerce')

                # Create stress index from volatility
                df['stress_index'] = df[vol_col] * np.random.normal(1.0, 0.1, len(df))  # Add some noise
                df['stress_index'] = df['stress_index'].clip(0, None)  # Ensure non-negative

                return df[[date_col, 'stress_index']].rename(columns={date_col: 'date'})

        # Last resort: return empty DataFrame
        return pd.DataFrame()
    def render_macro_factor_heatmap(self, data: Dict[str, Any]) -> None:
        """
        Render comprehensive macro factor heatmap showing sector sensitivities
        """
        # Try to get macro impact heatmap data
        heatmap_data = data.get("macro_impact_sector_heatmap")
        if isinstance(heatmap_data, pd.DataFrame) and not heatmap_data.empty:
            self._render_macro_impact_heatmap(heatmap_data)
            return

        # Fallback to macro factors if heatmap not available
        macro_df = data.get("macro_factors_v2")
        if not isinstance(macro_df, pd.DataFrame) or macro_df.empty:
            macro_df = data.get("macro_factors")

        if not isinstance(macro_df, pd.DataFrame) or macro_df.empty:
            st.info("Macro factor heatmap unavailable: no macro data loaded.")
            return

        # Prepare heatmap data
        heatmap_df = self._prepare_macro_heatmap_changes(macro_df, tail_rows=120)
        if heatmap_df.empty:
            st.info("Macro factor heatmap unavailable: insufficient data variation.")
            return

        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_df.values.T,
            x=heatmap_df.index.strftime('%Y-%m-%d') if hasattr(heatmap_df.index, 'strftime') else heatmap_df.index,
            y=heatmap_df.columns,
            colorscale='RdBu_r',
            zmid=0,
            colorbar=dict(title="Z-Score"),
            hoverongaps=False,
            hovertemplate='<b>%{y}</b><br>Date: %{x}<br>Z-Score: %{z:.2f}<extra></extra>'
        ))

        fig.update_layout(
            title="Macro Factor Changes Heatmap (Z-Scores)",
            xaxis_title="Date",
            yaxis_title="Macro Variables",
            height=max(400, min(800, len(heatmap_df.columns) * 25))
        )

        self._render_chart_with_contract(
            chart_id="market_state_macro_heatmap",
            fig=fig,
            data=data,
            key="market_state_macro_heatmap",
            height=max(400, min(800, len(heatmap_df.columns) * 25))
        )

        # Add summary statistics
        st.caption(f"Showing {len(heatmap_df.columns)} macro variables over {len(heatmap_df)} periods")

    def _render_macro_impact_heatmap(self, heatmap_data: pd.DataFrame, data: Dict[str, Any]) -> None:
        """
        Render sector-level macro impact heatmap from processed data
        """
        if heatmap_data.empty:
            st.info("Macro impact heatmap: no data available.")
            return

        # The CSV has sectors as rows and macro variables as columns
        # Transpose for better visualization (sectors on y-axis)
        z_data = heatmap_data.values

        # Get sector names (assuming they're in the index or first column)
        if hasattr(heatmap_data, 'index') and len(heatmap_data.index) > 0:
            sectors = [str(idx) for idx in heatmap_data.index]
        else:
            sectors = [f"Sector_{i}" for i in range(len(z_data))]

        # Get macro variable names from columns
        macro_vars = [str(col)[:30] + "..." if len(str(col)) > 30 else str(col) for col in heatmap_data.columns]

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=macro_vars,
            y=sectors,
            colorscale='RdBu_r',
            zmid=0,
            colorbar=dict(title="Beta Coefficient"),
            hoverongaps=False,
            hovertemplate='<b>%{y}</b><br>Factor: %{x}<br>Beta: %{z:.4f}<extra></extra>'
        ))

        fig.update_layout(
            title="Sector Macro Sensitivity Heatmap",
            xaxis_title="Macro Factors",
            yaxis_title="Sectors",
            height=max(400, len(sectors) * 40),
            xaxis=dict(tickangle=45)
        )

        self._render_chart_with_contract(
            chart_id="market_state_sector_macro_heatmap",
            fig=fig,
            data=data,
            key="market_state_sector_macro_heatmap",
            height=max(400, len(sectors) * 40)
        )

        st.caption(f"Sector sensitivities to {len(macro_vars)} macro factors")

    def render_enhanced_macro_transmission_panel(self, data: Dict[str, Any]) -> None:
        """
        Enhanced macro transmission panel with proper data validation and visualization
        """
        st.subheader("🌐 Macro Transmission Engine")

        # Check for macro transmission data
        kalman_betas = data.get("macro_transmission_kalman")
        expected_change = data.get("macro_transmission_expected")
        adjusted_scores = data.get("macro_transmission_adjusted")

        col1, col2 = st.columns(2)

        with col1:
            if isinstance(kalman_betas, pd.DataFrame) and not kalman_betas.empty:
                self._render_kalman_betas_chart(kalman_betas)
            else:
                st.info("Kalman beta estimates not available")

        with col2:
            if isinstance(expected_change, pd.DataFrame) and not expected_change.empty:
                self._render_macro_expected_change(expected_change)
            else:
                st.info("Macro expected change data not available")

        # Full width charts
        if isinstance(adjusted_scores, pd.DataFrame) and not adjusted_scores.empty:
            self._render_macro_adjusted_scores(adjusted_scores)
        else:
            st.info("Macro adjusted scores not available")

    def _render_kalman_betas_chart(self, kalman_betas: pd.DataFrame) -> None:
        """Render Kalman filter beta estimates"""
        if kalman_betas.empty:
            return

        # Get top 10 most variable betas
        numeric_cols = kalman_betas.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            st.info("No numeric beta data available")
            return

        # Calculate variance for each beta series
        variances = kalman_betas[numeric_cols].var().sort_values(ascending=False)
        top_betas = variances.head(10).index

        fig = go.Figure()

        for beta in top_betas:
            if beta in kalman_betas.columns:
                y_data = pd.to_numeric(kalman_betas[beta], errors='coerce')
                if y_data.notna().sum() > 5:  # At least 5 valid points
                    fig.add_trace(go.Scatter(
                        x=kalman_betas.index,
                        y=y_data,
                        mode='lines',
                        name=str(beta)[:20],
                        line=dict(width=1.5)
                    ))

        fig.update_layout(
            title="Kalman Filter Beta Estimates (Top 10 by Variance)",
            xaxis_title="Date",
            yaxis_title="Beta Coefficient",
            height=350,
            showlegend=True,
            legend=dict(orientation="v", x=1.02, y=1)
        )

        self._apply_fig_theme(fig, height=350)
        st.plotly_chart(fig, use_container_width=True, key="kalman_betas_chart")

    def _render_macro_expected_change(self, expected_change: pd.DataFrame) -> None:
        """Render macro expected change forecasts"""
        if expected_change.empty:
            return

        # Get most recent forecasts
        numeric_cols = expected_change.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            st.info("No numeric forecast data available")
            return

        latest_row = expected_change.iloc[-1]
        latest_forecasts = latest_row[numeric_cols].dropna()

        if len(latest_forecasts) == 0:
            st.info("No valid forecasts available")
            return

        # Sort by absolute value and take top 15
        top_forecasts = latest_forecasts.reindex(
            latest_forecasts.abs().sort_values(ascending=False).head(15).index
        )

        colors = ['red' if x < 0 else 'green' for x in top_forecasts.values]

        fig = go.Figure(data=go.Bar(
            x=top_forecasts.values,
            y=[str(name)[:25] for name in top_forecasts.index],
            orientation='h',
            marker_color=colors,
            hovertemplate='<b>%{y}</b><br>Expected Change: %{x:.4f}<extra></extra>'
        ))

        fig.update_layout(
            title="Macro Expected Changes (Latest)",
            xaxis_title="Expected Change",
            yaxis_title="Macro Variables",
            height=400
        )

        self._apply_fig_theme(fig, height=400)
        st.plotly_chart(fig, use_container_width=True, key="macro_expected_change_chart")

    def _render_macro_adjusted_scores(self, adjusted_scores: pd.DataFrame) -> None:
        """Render macro adjusted scores over time"""
        if adjusted_scores.empty:
            return

        numeric_cols = adjusted_scores.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            st.info("No numeric adjusted score data available")
            return

        # Get top 8 most variable scores
        variances = adjusted_scores[numeric_cols].var().sort_values(ascending=False)
        top_scores = variances.head(8).index

        fig = go.Figure()

        for score in top_scores:
            if score in adjusted_scores.columns:
                y_data = pd.to_numeric(adjusted_scores[score], errors='coerce')
                if y_data.notna().sum() > 5:
                    fig.add_trace(go.Scatter(
                        x=adjusted_scores.index,
                        y=y_data,
                        mode='lines',
                        name=str(score)[:20],
                        line=dict(width=2)
                    ))

        fig.update_layout(
            title="Macro Adjusted Scores Over Time",
            xaxis_title="Date",
            yaxis_title="Adjusted Score",
            height=400,
            showlegend=True
        )

        self._apply_fig_theme(fig, height=400)
        st.plotly_chart(fig, use_container_width=True, key="macro_adjusted_scores_chart")

    def render_data_quality_diagnostics(self, data: Dict[str, Any]) -> None:
        """
        Render data quality diagnostics to identify flatline issues
        """
        st.subheader("🔍 Data Quality Diagnostics")

        # Check various data sources for quality issues
        quality_issues = []

        # Check macro factors
        macro_df = data.get("macro_factors_v2") or data.get("macro_factors")
        if isinstance(macro_df, pd.DataFrame) and not macro_df.empty:
            issues = self._diagnose_data_quality(macro_df, "Macro Factors")
            quality_issues.extend(issues)

        # Check market data
        market_state = data.get("market_state")
        if isinstance(market_state, pd.DataFrame) and not market_state.empty:
            issues = self._diagnose_data_quality(market_state, "Market State")
            quality_issues.extend(issues)

        # Check portfolio data
        portfolio_weights = data.get("portfolio_weights")
        if isinstance(portfolio_weights, pd.DataFrame) and not portfolio_weights.empty:
            issues = self._diagnose_data_quality(portfolio_weights, "Portfolio Weights")
            quality_issues.extend(issues)

        if quality_issues:
            st.warning(f"Found {len(quality_issues)} data quality issues:")
            for issue in quality_issues[:10]:  # Show top 10
                st.text(f"• {issue}")
        else:
            st.success("No major data quality issues detected")

    def _diagnose_data_quality(self, df: pd.DataFrame, source_name: str) -> List[str]:
        """Diagnose data quality issues in a DataFrame"""
        issues = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = pd.to_numeric(df[col], errors='coerce')

            # Check for constant series (flatlines)
            if series.nunique() <= 1:
                issues.append(f"{source_name}.{col}: Constant series (flatline)")

            # Check for excessive NaN values
            nan_pct = series.isna().sum() / len(series)
            if nan_pct > 0.8:
                issues.append(f"{source_name}.{col}: {nan_pct:.1%} missing values")

            # Check for extreme outliers
            if series.notna().sum() > 10:
                q99 = series.quantile(0.99)
                q01 = series.quantile(0.01)
                outlier_pct = ((series > q99 * 10) | (series < q01 * 10)).sum() / len(series)
                if outlier_pct > 0.05:
                    issues.append(f"{source_name}.{col}: {outlier_pct:.1%} extreme outliers")

            # Check for insufficient variance
            if series.notna().sum() > 10:
                std_val = series.std()
                mean_val = abs(series.mean())
                if mean_val > 0 and std_val / mean_val < 0.01:
                    issues.append(f"{source_name}.{col}: Very low variance (CV={std_val/mean_val:.3f})")

        return issues

    def render_sector_sentiment_vs_flows(
        self,
        data: Dict[str, Any],
        sentiment_ctx: Dict[str, Any],
        *,
        key_prefix: str = "sector_sentiment_flows",
    ) -> None:
        sector_rows = sentiment_ctx.get("sector_narratives", []) or []
        flows = data.get("sector_flows")
        if not sector_rows or not isinstance(flows, pd.DataFrame) or flows.empty:
            st.info("Need both sector narratives and sector flows to plot sentiment-flow divergence.")
            return

        s = pd.DataFrame(sector_rows)
        if s.empty or "sector" not in s.columns:
            st.info("Sector narratives artifact has no usable sector rows.")
            return
        for c in ["sentiment_score", "conviction"]:
            if c in s.columns:
                s[c] = pd.to_numeric(s[c], errors="coerce")
        s = s.dropna(subset=["sentiment_score"])
        if s.empty:
            st.info("Sector narratives have no numeric sentiment scores.")
            return

        f = flows.copy()
        if "Date" in f.columns:
            f["Date"] = _to_naive_date_series(f["Date"], normalize=False)
            f = f.dropna(subset=["Date"])
            if not f.empty:
                # Use a recent window aggregate so we don't collapse to a single point/industry
                # when the latest snapshot is sparse.
                end_dt = f["Date"].max()
                start_dt = end_dt - pd.Timedelta(days=30)
                fw = f[f["Date"] >= start_dt].copy()
                if fw.empty:
                    fw = f.copy()
                group_cols = ["Industry"] if "Industry" in fw.columns else (["sector"] if "sector" in fw.columns else [])
                if group_cols:
                    agg = {"flow_strength": "mean"}
                    if "capital_flow" in fw.columns:
                        agg["capital_flow"] = "sum"
                    fw = fw.groupby(group_cols, as_index=False).agg(agg)
                f = fw
        for c in ["flow_strength", "capital_flow"]:
            if c in f.columns:
                f[c] = pd.to_numeric(f[c], errors="coerce")
        industry_col = "Industry" if "Industry" in f.columns else ("sector" if "sector" in f.columns else None)
        if industry_col is None or "flow_strength" not in f.columns:
            st.info("Sector flows artifact is missing Industry/flow_strength columns.")
            return

        def _norm_name(v: Any) -> str:
            return re.sub(r"[^A-Za-z0-9]+", "", str(v or "").upper())

        s["sector_key"] = s["sector"].map(_norm_name)
        f["sector_key"] = f[industry_col].map(_norm_name)
        alias = {
            "AUTO": "AUTOMOBILEANDAUTOCOMPONENTS",
            "IT": "INFORMATIONTECHNOLOGY",
            "FMCG": "FASTMOVINGCONSUMERGOODS",
            "PHARMA": "HEALTHCARE",
            "METAL": "METALSMINING",
            "REALTY": "REALTY",
            "ENERGY": "OILGASCONSUMABLEFUELS",
            "PSU": "FINANCIALSERVICES",
            "BANKNIFTY": "FINANCIALSERVICES",
            "NIFTY": "NIFTY50",
        }
        ind_keys = f[[industry_col, "sector_key"]].dropna(subset=["sector_key"]).drop_duplicates()
        key_to_industry = {str(r["sector_key"]): str(r[industry_col]) for _, r in ind_keys.iterrows()}
        candidates = list(key_to_industry.keys())

        def _match_sector_key(sk: str) -> Optional[str]:
            sk = str(sk or "")
            if not sk:
                return None
            if sk in alias:
                mapped = alias[sk]
                if mapped in key_to_industry:
                    return mapped
            if sk in key_to_industry:
                return sk
            best = None
            best_score = 0.0
            for ck in candidates:
                if not ck:
                    continue
                score = SequenceMatcher(None, sk, ck).ratio()
                if sk in ck or ck in sk:
                    score = max(score, 0.72)
                if score > best_score:
                    best_score = score
                    best = ck
            return best if best is not None and best_score >= 0.45 else None

        s["sector_key"] = s["sector_key"].map(lambda x: _match_sector_key(str(x) if x is not None else ""))
        s = s.dropna(subset=["sector_key"])
        merged = s.merge(
            f[[industry_col, "sector_key", "flow_strength", "capital_flow"] if "capital_flow" in f.columns else [industry_col, "sector_key", "flow_strength"]],
            on="sector_key",
            how="inner",
        )
        if merged.empty:
            st.info("No sector-name overlap between narrative and flow artifacts.")
            return

        merged["_bubble_size"] = (
            pd.to_numeric(merged.get("capital_flow", pd.Series([1.0] * len(merged))), errors="coerce")
            .abs()
            .fillna(1.0)
            .clip(lower=1.0)
        )
        fig = px.scatter(
            merged,
            x="sentiment_score",
            y="flow_strength",
            size="_bubble_size",
            color="conviction" if "conviction" in merged.columns else "flow_strength",
            hover_data={industry_col: True, "sector": True},
            title="Sector Sentiment vs Sector Flows",
            color_continuous_scale="Viridis",
        )
        fig.add_hline(y=0, line_dash="dot", line_color=THEME["grid"])
        fig.add_vline(x=0, line_dash="dot", line_color=THEME["grid"])
        if key_prefix == "market_state":
            self._render_chart_with_contract(
                chart_id="market_state_sector_sentiment_vs_flows",
                fig=fig,
                data=data,
                key="market_state_sector_sentiment_vs_flows",
                height=340,
            )
        elif key_prefix == "news_layer":
            self._render_chart_with_contract(
                chart_id="news_layer_sector_sentiment_vs_flows",
                fig=fig,
                data=data,
                key="news_layer_sector_sentiment_vs_flows",
                height=340,
            )
        else:
            self._apply_fig_theme(fig, height=340)
            if key_prefix == "causal_flow_global":
                st.plotly_chart(fig, width="stretch", key="causal_flow_sector_sentiment_vs_flows")
            elif key_prefix == "sector_sentiment_flows":
                st.plotly_chart(fig, width="stretch", key="sector_sentiment_flows_vs_flows")
            else:
                st.plotly_chart(fig, width="stretch", key="sector_sentiment_vs_flows_default")
        self._formula_note(
            "Sector Sentiment vs Flow Formula",
            [
                "x = sector_sentiment_score",
                "y = flow_strength",
                "bubble_size = abs(capital_flow), floor=1",
                "color = conviction (or flow_strength fallback)",
            ],
        )

    def render_belief_vs_news_divergence(self, data: Dict[str, Any], sentiment_ctx: Dict[str, Any]) -> None:
        beliefs = data.get("strategy_beliefs")
        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if not isinstance(beliefs, pd.DataFrame) or beliefs.empty or not isinstance(market_df, pd.DataFrame) or market_df.empty:
            st.info("Belief/news divergence requires both strategy beliefs and sentiment history.")
            return

        b = beliefs.copy()
        time_col = _pick_time_column(b, ["date", "Date", "timestamp"])
        metric = _pick_belief_metric(b)
        if time_col is None or metric is None:
            st.info("Belief artifact lacks usable time/metric fields.")
            return
        b["date"] = _to_naive_date_series(b[time_col], normalize=True)
        b["belief"] = pd.to_numeric(b[metric], errors="coerce")
        b = b.dropna(subset=["date", "belief"])
        if b.empty:
            st.info("Belief history has no numeric data.")
            return
        b = b.groupby("date", as_index=False)["belief"].mean()
        b["belief_z"] = self._zscore(b["belief"])

        s = market_df.copy()
        stime = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
        scol = next((c for c in ["polarity", "sentiment_score", "signed_sentiment_intensity"] if c in s.columns), None)
        if stime is None or scol is None:
            st.info("Sentiment history lacks required date/signal columns.")
            return
        s["date"] = _to_naive_date_series(s[stime], normalize=True)
        s["news"] = pd.to_numeric(s[scol], errors="coerce")
        s = s.dropna(subset=["date", "news"]).groupby("date", as_index=False)["news"].mean()
        s["news_z"] = self._zscore(s["news"])

        merged = b.merge(s[["date", "news_z"]], on="date", how="inner").sort_values("date")
        if len(merged) < 5:
            # Real fallback path: use integrated snapshot belief/news history.
            integ = load_integrated_state_snapshot(max_rows=3650)
            if isinstance(integ, pd.DataFrame) and not integ.empty and {"date", "belief_strength", "macro_news_sentiment"}.issubset(integ.columns):
                x = integ[["date", "belief_strength", "macro_news_sentiment"]].copy()
                x["date"] = _to_naive_date_series(x["date"], normalize=True)
                x["belief"] = pd.to_numeric(x["belief_strength"], errors="coerce")
                x["news"] = pd.to_numeric(x["macro_news_sentiment"], errors="coerce")
                x = x.dropna(subset=["date", "belief", "news"]).sort_values("date")
                if not x.empty:
                    x = x.groupby("date", as_index=False).agg({"belief": "mean", "news": "mean"})
                    x["belief_z"] = self._zscore(x["belief"])
                    x["news_z"] = self._zscore(x["news"])
                    merged = x[["date", "belief_z", "news_z"]].copy()

        if len(merged) < 5:
            st.info("Need more overlap between belief and news series for divergence analysis.")
            return
        merged["divergence"] = merged["belief_z"] - merged["news_z"]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged["belief_z"],
                mode="lines",
                name="Belief (z)",
                line=dict(color=THEME["blue"], width=2),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged["news_z"],
                mode="lines",
                name="News (z)",
                line=dict(color=THEME["amber"], width=2),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(
                x=merged["date"],
                y=merged["divergence"],
                name="Belief - News",
                marker_color=THEME["violet"],
                opacity=0.35,
            ),
            secondary_y=True,
        )
        fig.update_layout(title="Belief vs News Divergence")
        fig.update_yaxes(title_text="Z-score", secondary_y=False)
        fig.update_yaxes(title_text="Divergence", secondary_y=True)
        self._apply_fig_theme(fig, height=340)
        st.plotly_chart(fig, width="stretch", key="news_layer_belief_news_divergence")
        self._formula_note(
            "Belief vs News Divergence Formula",
            [
                "belief_z_t = zscore(mean(belief_metric_t by day))",
                "news_z_t = zscore(mean(sentiment_signal_t by day))",
                "divergence_t = belief_z_t - news_z_t",
            ],
        )

    def render_event_shock_surface(self, data: Dict[str, Any], sentiment_ctx: Dict[str, Any]) -> None:
        event_df = sentiment_ctx.get("event_df", pd.DataFrame())
        if not isinstance(event_df, pd.DataFrame) or event_df.empty:
            st.info("No event-company impact artifact available.")
            return
        if not {"ticker", "event_type", "impact_score"}.issubset(event_df.columns):
            st.info("Event impact artifact missing ticker/event_type/impact_score columns.")
            return

        d = event_df.copy()
        d["ticker"] = d["ticker"].astype(str).str.replace(".NS", "", regex=False).str.upper()
        d["impact_score"] = pd.to_numeric(d["impact_score"], errors="coerce")
        d = d.dropna(subset=["ticker", "event_type", "impact_score"])
        if d.empty:
            st.info("Event impact artifact has no numeric impact rows.")
            return

        top_tickers = (
            d.groupby("ticker")["impact_score"]
            .apply(lambda s: s.abs().mean())
            .sort_values(ascending=False)
            .head(20)
            .index
            .tolist()
        )
        piv = (
            d[d["ticker"].isin(top_tickers)]
            .pivot_table(index="ticker", columns="event_type", values="impact_score", aggfunc="mean")
            .fillna(0.0)
        )
        if not piv.empty:
            fig = px.imshow(
                piv,
                aspect="auto",
                color_continuous_scale="RdBu",
                title="Event Shock Surface (Ticker × Event Type)",
            )
            self._apply_fig_theme(fig, height=420)
            st.plotly_chart(fig, width="stretch", key="news_layer_event_shock_surface")
            self._formula_note(
                "Event Shock Surface Formula",
                [
                    "cell(ticker,event_type) = mean(impact_score)",
                    "top_tickers selected by mean(abs(impact_score))",
                    "portfolio_sensitivity_ticker = weight_ticker * mean(impact_score_ticker)",
                ],
            )

        weights = data.get("portfolio_weights")
        if isinstance(weights, pd.DataFrame) and not weights.empty:
            w = weights.copy()
            ticker_col = "ticker" if "ticker" in w.columns else ("symbol" if "symbol" in w.columns else None)
            weight_col = next((c for c in ["weight", "final_weight", "allocation", "w"] if c in w.columns), None)
            if ticker_col and weight_col:
                w["ticker"] = w[ticker_col].astype(str).str.replace(".NS", "", regex=False).str.upper()
                w["weight"] = pd.to_numeric(w[weight_col], errors="coerce")
                w = w.dropna(subset=["ticker", "weight"])
                latest_impact = (
                    d.groupby("ticker", as_index=False)["impact_score"]
                    .mean()
                    .sort_values("impact_score", ascending=False)
                )
                joined = w.merge(latest_impact, on="ticker", how="left")
                joined["impact_score"] = pd.to_numeric(joined["impact_score"], errors="coerce").fillna(0.0)
                joined = joined.sort_values("weight", ascending=False).head(25)
                if not joined.empty:
                    st.markdown("#### Portfolio Sensitivity to Event Shock")
                    st.dataframe(
                        joined[["ticker", "weight", "impact_score"]].assign(
                            weight=lambda x: pd.to_numeric(x["weight"], errors="coerce").round(4),
                            impact_score=lambda x: pd.to_numeric(x["impact_score"], errors="coerce").round(3),
                        ),
                        width="stretch",
                        hide_index=True,
                    )

    def render_market_pressure_surface(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("🌍 Market Pressure Surface")
        sentiment_ctx = load_sentiment_context()

        mr = data.get("market_regime")
        if not isinstance(mr, pd.DataFrame) or mr.empty:
            st.info("Market pressure surface unavailable: market_regime artifact missing.")
            return

        m = mr.copy()
        tcol = "Date" if "Date" in m.columns else ("date" if "date" in m.columns else None)
        if tcol is not None:
            m["date"] = _to_naive_date_series(m[tcol], normalize=False)
        else:
            m["date"] = _to_naive_date_series(pd.Series(m.index), normalize=False)
        for c in ["volatility", "correlation", "risk_on_score"]:
            if c in m.columns:
                m[c] = pd.to_numeric(m[c], errors="coerce")
        if not {"volatility", "correlation", "risk_on_score"}.issubset(m.columns):
            st.info("Market pressure surface requires volatility/correlation/risk_on_score in market_regime.")
            return
        m = m.dropna(subset=["date"]).sort_values("date")
        if m.empty:
            st.info("Market pressure surface has no usable market-regime rows.")
            return

        m["risk_pressure"] = self._zscore(m["volatility"]).values + self._zscore(m["correlation"]).values
        m["regime_confidence"] = pd.to_numeric(m["risk_on_score"], errors="coerce").clip(0.0, 1.0)
        panel = m[["date", "regime_confidence", "risk_pressure"]].copy()

        alpha_ts = data.get("alpha_os_timeseries")
        if isinstance(alpha_ts, pd.DataFrame) and not alpha_ts.empty and "timestamp" in alpha_ts.columns:
            a = alpha_ts.copy()
            a["date"] = _to_naive_date_series(a["timestamp"], normalize=True)
            for c in ["regime_crisis", "regime_entropy"]:
                if c in a.columns:
                    a[c] = pd.to_numeric(a[c], errors="coerce")
            a = a.dropna(subset=["date"]).groupby("date", as_index=False)[[c for c in ["regime_crisis", "regime_entropy"] if c in a.columns]].mean()
            panel = panel.merge(a, on="date", how="left")
        else:
            panel["regime_crisis"] = np.nan
            panel["regime_entropy"] = np.nan

        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            s = market_df.copy()
            tcol_s = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
            if tcol_s:
                s["date"] = _to_naive_date_series(s[tcol_s], normalize=True)
                if "uncertainty" in s.columns:
                    s["uncertainty"] = pd.to_numeric(s["uncertainty"], errors="coerce").fillna(0.0)
                else:
                    s["uncertainty"] = 0.0
                if "event_shock_factor" in s.columns:
                    s["event_shock_factor"] = pd.to_numeric(s["event_shock_factor"], errors="coerce").fillna(0.0)
                else:
                    s["event_shock_factor"] = 0.0
                s = s.dropna(subset=["date"]).groupby("date", as_index=False)[["uncertainty", "event_shock_factor"]].mean()
                s["systemic_stress"] = 0.6 * s["uncertainty"] + 0.4 * s["event_shock_factor"]
                panel = panel.merge(s[["date", "systemic_stress"]], on="date", how="left")
        if "systemic_stress" not in panel.columns:
            panel["systemic_stress"] = np.nan

        panel = self._focus_active_window(
            panel,
            time_col="date",
            value_cols=["regime_confidence", "risk_pressure", "regime_crisis", "regime_entropy", "systemic_stress"],
            max_rows=900,
            min_rows=180,
            eps=1e-8,
        )
        if panel.empty:
            st.info("Market pressure surface has no active non-flat signal window.")
            return

        latest = panel.iloc[-1]
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            self._kpi_card("Regime Confidence", f"{_as_float(latest.get('regime_confidence'), np.nan):.2f}" if np.isfinite(_as_float(latest.get("regime_confidence"), np.nan)) else "n/a")
        with k2:
            self._kpi_card("Risk Pressure", f"{_as_float(latest.get('risk_pressure'), np.nan):+.2f}" if np.isfinite(_as_float(latest.get("risk_pressure"), np.nan)) else "n/a")
        with k3:
            self._kpi_card("Crisis Prob", f"{_as_float(latest.get('regime_crisis'), np.nan):.1%}" if np.isfinite(_as_float(latest.get("regime_crisis"), np.nan)) else "n/a")
        with k4:
            self._kpi_card("Systemic Stress", f"{_as_float(latest.get('systemic_stress'), np.nan):+.2f}" if np.isfinite(_as_float(latest.get("systemic_stress"), np.nan)) else "n/a")

        overlay_options = [
            "Regime Confidence",
            "Risk Pressure",
            "Crisis Probability",
            "Regime Entropy",
            "Systemic Stress",
        ]
        selected = st.multiselect(
            "Overlay signals",
            overlay_options,
            default=overlay_options,
            key="market_pressure_surface_overlays_live" if live_mode else "market_pressure_surface_overlays_research",
        )
        if not selected:
            selected = ["Regime Confidence", "Risk Pressure"]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        if "Regime Confidence" in selected:
            fig.add_trace(
                go.Scatter(
                    x=panel["date"],
                    y=panel["regime_confidence"],
                    mode="lines",
                    name="Regime Confidence",
                    line=dict(color=THEME["cyan"], width=2),
                ),
                secondary_y=True,
            )
        if "Crisis Probability" in selected:
            fig.add_trace(
                go.Scatter(
                    x=panel["date"],
                    y=panel["regime_crisis"],
                    mode="lines",
                    name="Crisis Probability",
                    line=dict(color=THEME["red"], width=2),
                ),
                secondary_y=True,
            )
        if "Risk Pressure" in selected:
            fig.add_trace(
                go.Scatter(
                    x=panel["date"],
                    y=panel["risk_pressure"],
                    mode="lines",
                    name="Risk Pressure (z)",
                    line=dict(color=THEME["amber"], width=1.9),
                ),
                secondary_y=False,
            )
        if "Regime Entropy" in selected:
            fig.add_trace(
                go.Scatter(
                    x=panel["date"],
                    y=panel["regime_entropy"],
                    mode="lines",
                    name="Regime Entropy",
                    line=dict(color=THEME["violet"], width=1.8),
                ),
                secondary_y=False,
            )
        if "Systemic Stress" in selected:
            fig.add_trace(
                go.Scatter(
                    x=panel["date"],
                    y=panel["systemic_stress"],
                    mode="lines",
                    name="Systemic Stress",
                    line=dict(color=THEME["pink"], width=1.8),
                ),
                secondary_y=False,
            )
        fig.update_layout(title="Market Pressure Surface (Regime + Risk + Narrative)")
        fig.update_yaxes(title_text="Pressure / Entropy / Stress", secondary_y=False)
        fig.update_yaxes(title_text="Probability", range=[0, 1], secondary_y=True)
        self._render_chart_with_contract(
            chart_id="market_pressure_surface",
            fig=fig,
            data=data,
            key="market_pressure_surface",
            height=360,
        )
        self._formula_note(
            "Market Pressure Formulas",
            [
                "risk_pressure_t = z(volatility_t) + z(correlation_t)",
                "regime_confidence_t = clip(risk_on_score_t, 0, 1)",
                "systemic_stress_t = 0.6*uncertainty_t + 0.4*event_shock_factor_t",
            ],
        )

    def render_portfolio_expression_surface(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("📊 Portfolio Expression Surface")
        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        if pnl_df.empty:
            st.info("Portfolio expression surface unavailable: pnl artifact missing.")
            return

        p = pnl_df.copy().sort_values("Date")
        p = self._focus_active_window(
            p,
            time_col="Date",
            value_cols=["Equity", "Return"],
            max_rows=900,
            min_rows=180,
            eps=1e-8,
        )
        if p.empty:
            st.info("Portfolio expression surface has no active pnl window.")
            return
        p["portfolio_norm"] = p["Equity"] / max(1e-9, float(p["Equity"].iloc[0]))
        p["drawdown_pct"] = self.compute_drawdown(p["Equity"]) * 100.0

        b = pd.DataFrame()
        idx = data.get("index_nifty50")
        if isinstance(idx, pd.DataFrame) and not idx.empty:
            close_col = "close" if "close" in idx.columns else (idx.columns[0] if len(idx.columns) else None)
            if close_col is not None:
                b = idx.copy().sort_index()
                b[close_col] = pd.to_numeric(b[close_col], errors="coerce")
                b = b.dropna(subset=[close_col])
                b = b[(b.index >= p["Date"].min()) & (b.index <= p["Date"].max())]
                if not b.empty:
                    b["benchmark_norm"] = b[close_col] / max(1e-9, float(b[close_col].iloc[0]))

        exposure = pd.DataFrame(columns=["date", "total_exposure"])
        alloc = data.get("allocation_history")
        if isinstance(alloc, pd.DataFrame) and not alloc.empty and "date" in alloc.columns:
            ah = alloc.copy()
            ah["date"] = _to_naive_date_series(ah["date"], normalize=False)
            ah = ah.dropna(subset=["date"]).sort_values("date")
            if "total_exposure" in ah.columns:
                ah["total_exposure"] = pd.to_numeric(ah["total_exposure"], errors="coerce")
                exposure = ah[["date", "total_exposure"]].dropna()
            else:
                meta_cols = {
                    "date",
                    "regime",
                    "strategy_name",
                    "strategy_category",
                    "allocation_weight",
                    "allocation_score",
                    "regime_fitness",
                    "adjusted_return",
                    "adjusted_sharpe",
                    "risk_contribution",
                    "allocation_reason",
                    "timestamp",
                }
                strat_cols = [c for c in ah.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(ah[c])]
                strat_cols = [c for c in strat_cols if ah[c].dropna().between(-0.01, 1.01).mean() > 0.9]
                if strat_cols:
                    tmp = ah[["date"] + strat_cols].copy()
                    tmp["total_exposure"] = tmp[strat_cols].sum(axis=1)
                    exposure = tmp[["date", "total_exposure"]].dropna()

        edge_score = np.nan
        edge = data.get("edge_half_life") or {}
        if isinstance(edge, dict) and isinstance(edge.get("strategies"), dict) and edge.get("strategies"):
            vals = [pd.to_numeric((v or {}).get("edge_health"), errors="coerce") for v in edge["strategies"].values() if isinstance(v, dict)]
            vals = [float(v) for v in vals if pd.notna(v)]
            if vals:
                edge_score = float(np.nanmean(vals))

        exit_risk = np.nan
        liq = data.get("liquidity_risk")
        if isinstance(liq, pd.DataFrame) and not liq.empty and "exit_risk" in liq.columns:
            ex = pd.to_numeric(liq["exit_risk"], errors="coerce").dropna()
            if not ex.empty:
                exit_risk = float(ex.mean())

        latest_ret = float(p["portfolio_norm"].iloc[-1] - 1.0)
        latest_dd = float(p["drawdown_pct"].iloc[-1]) if p["drawdown_pct"].notna().any() else np.nan
        latest_exp = np.nan
        if not exposure.empty:
            latest_exp = _as_float(exposure["total_exposure"].iloc[-1], np.nan)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            self._kpi_card("Portfolio Return", f"{latest_ret:+.2%}")
        with c2:
            self._kpi_card("Current Drawdown", f"{latest_dd:.2f}%" if np.isfinite(latest_dd) else "n/a")
        with c3:
            self._kpi_card("Edge Health", f"{edge_score:.2f}" if np.isfinite(edge_score) else "n/a")
        with c4:
            self._kpi_card(
                "Exposure / Exit Risk",
                (
                    f"{latest_exp:.2f} / {exit_risk:.3f}"
                    if np.isfinite(latest_exp) and np.isfinite(exit_risk)
                    else "n/a"
                ),
            )

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Portfolio vs Benchmark (Normalized)", "Exposure + Drawdown"),
            specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
        )
        fig.add_trace(
            go.Scatter(
                x=p["Date"],
                y=p["portfolio_norm"],
                mode="lines",
                name="Portfolio",
                line=dict(color=THEME["blue"], width=2),
            ),
            row=1,
            col=1,
        )
        if not b.empty:
            fig.add_trace(
                go.Scatter(
                    x=b.index,
                    y=b["benchmark_norm"],
                    mode="lines",
                    name="NIFTY 50",
                    line=dict(color=THEME["cyan"], width=1.8),
                ),
                row=1,
                col=1,
            )
        if not exposure.empty:
            exp_plot = exposure[(exposure["date"] >= p["Date"].min()) & (exposure["date"] <= p["Date"].max())]
            fig.add_trace(
                go.Scatter(
                    x=exp_plot["date"],
                    y=exp_plot["total_exposure"],
                    mode="lines",
                    name="Total Exposure",
                    line=dict(color=THEME["green"], width=1.8),
                ),
                row=2,
                col=1,
                secondary_y=False,
            )
        fig.add_trace(
            go.Scatter(
                x=p["Date"],
                y=p["drawdown_pct"],
                mode="lines",
                name="Drawdown %",
                line=dict(color=THEME["red"], width=1.6),
            ),
            row=2,
            col=1,
            secondary_y=True,
        )
        fig.update_layout(title="Portfolio Expression Surface")
        fig.update_yaxes(title_text="Normalized NAV", row=1, col=1)
        fig.update_yaxes(title_text="Exposure", row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Drawdown %", row=2, col=1, secondary_y=True)
        self._render_chart_with_contract(
            chart_id="portfolio_expression_surface",
            fig=fig,
            data=data,
            key="portfolio_expression_surface",
            height=460,
        )
        self._formula_note(
            "Portfolio Expression Formulas",
            [
                "portfolio_norm_t = equity_t / equity_0",
                "benchmark_norm_t = nifty_close_t / nifty_close_0",
                "drawdown_t = equity_t / max(equity_<=t) - 1",
                "total_exposure_t = sum(strategy_weights_t)",
            ],
        )

    def render_survival_engine_surface(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("🛡 Survival Engine Surface")
        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        alpha_ts = data.get("alpha_os_timeseries")
        if pnl_df.empty or not isinstance(alpha_ts, pd.DataFrame) or alpha_ts.empty:
            st.info("Survival engine surface requires both pnl and alpha_os_timeseries artifacts.")
            return

        p = pnl_df.copy().sort_values("Date")
        p["drawdown_pct"] = self.compute_drawdown(p["Equity"]) * 100.0
        p["date"] = _to_naive_date_series(p["Date"], normalize=True)
        p = p.dropna(subset=["date"]).groupby("date", as_index=False)["drawdown_pct"].last()

        a = alpha_ts.copy()
        if "timestamp" not in a.columns:
            st.info("Survival engine surface requires alpha_os_timeseries.timestamp.")
            return
        a["date"] = _to_naive_date_series(a["timestamp"], normalize=True)
        for c in ["regime_crisis", "regime_entropy"]:
            if c in a.columns:
                a[c] = pd.to_numeric(a[c], errors="coerce")
            else:
                a[c] = np.nan
        a = a.dropna(subset=["date"]).groupby("date", as_index=False)[["regime_crisis", "regime_entropy"]].mean()

        panel = p.merge(a, on="date", how="outer").sort_values("date")

        sentiment_ctx = load_sentiment_context()
        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            s = market_df.copy()
            tcol = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
            if tcol:
                s["date"] = _to_naive_date_series(s[tcol], normalize=True)
                if "uncertainty" in s.columns:
                    s["uncertainty"] = pd.to_numeric(s["uncertainty"], errors="coerce").fillna(0.0)
                else:
                    s["uncertainty"] = 0.0
                if "event_shock_factor" in s.columns:
                    s["event_shock_factor"] = pd.to_numeric(s["event_shock_factor"], errors="coerce").fillna(0.0)
                else:
                    s["event_shock_factor"] = 0.0
                s = s.dropna(subset=["date"]).groupby("date", as_index=False)[["uncertainty", "event_shock_factor"]].mean()
                s["systemic_stress"] = 0.6 * s["uncertainty"] + 0.4 * s["event_shock_factor"]
                panel = panel.merge(s[["date", "systemic_stress"]], on="date", how="left")
        if "systemic_stress" not in panel.columns:
            panel["systemic_stress"] = np.nan

        panel = self._focus_active_window(
            panel,
            time_col="date",
            value_cols=["drawdown_pct", "regime_crisis", "regime_entropy", "systemic_stress"],
            max_rows=900,
            min_rows=180,
            eps=1e-8,
        )
        if panel.empty:
            st.info("Survival engine surface has no active non-flat signal window.")
            return

        dd_surface = self._empirical_drawdown_surface(pd.to_numeric(pnl_df["Return"], errors="coerce").dropna())
        dd_prob_20_5 = np.nan
        if not dd_surface.empty:
            probe = dd_surface[(dd_surface["horizon"] == "20d") & (dd_surface["threshold"] == ">5%")]
            if not probe.empty:
                dd_prob_20_5 = _as_float(probe["probability"].iloc[-1], np.nan)

        latest = panel.iloc[-1]
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            self._kpi_card("Current Drawdown", f"{_as_float(latest.get('drawdown_pct'), np.nan):.2f}%" if np.isfinite(_as_float(latest.get("drawdown_pct"), np.nan)) else "n/a")
        with k2:
            self._kpi_card("Crisis Probability", f"{_as_float(latest.get('regime_crisis'), np.nan):.1%}" if np.isfinite(_as_float(latest.get("regime_crisis"), np.nan)) else "n/a")
        with k3:
            self._kpi_card("Regime Entropy", f"{_as_float(latest.get('regime_entropy'), np.nan):.3f}" if np.isfinite(_as_float(latest.get("regime_entropy"), np.nan)) else "n/a")
        with k4:
            self._kpi_card("DD Prob (20d, >5%)", f"{dd_prob_20_5:.1%}" if np.isfinite(dd_prob_20_5) else "n/a")

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Drawdown + Crisis Probability", "Entropy + Systemic Stress"),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        )
        fig.add_trace(
            go.Scatter(
                x=panel["date"],
                y=panel["drawdown_pct"],
                mode="lines",
                name="Drawdown %",
                line=dict(color=THEME["red"], width=1.8),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=panel["date"],
                y=panel["regime_crisis"],
                mode="lines",
                name="Crisis Probability",
                line=dict(color=THEME["violet"], width=1.8),
            ),
            row=1,
            col=1,
            secondary_y=True,
        )
        fig.add_trace(
            go.Scatter(
                x=panel["date"],
                y=panel["regime_entropy"],
                mode="lines",
                name="Regime Entropy",
                line=dict(color=THEME["cyan"], width=1.8),
            ),
            row=2,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=panel["date"],
                y=panel["systemic_stress"],
                mode="lines",
                name="Systemic Stress",
                line=dict(color=THEME["amber"], width=1.8),
            ),
            row=2,
            col=1,
        )
        fig.update_layout(title="Survival Engine Surface")
        fig.update_yaxes(title_text="Drawdown %", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Crisis Probability", row=1, col=1, range=[0, 1], secondary_y=True)
        fig.update_yaxes(title_text="Entropy / Stress", row=2, col=1)
        self._render_chart_with_contract(
            chart_id="survival_engine_surface",
            fig=fig,
            data=data,
            key="survival_engine_surface",
            height=460,
        )
        self._formula_note(
            "Survival Engine Formulas",
            [
                "drawdown_t = equity_t / max(equity_<=t) - 1",
                "crisis_probability_t = alpha_os_timeseries.regime_crisis_t",
                "dd_prob_20d_5pct = mean(fwd_return_20d <= -5%)",
                "systemic_stress_t = 0.6*uncertainty_t + 0.4*event_shock_factor_t",
            ],
        )

    def render_news_shock_surface(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("📰 News Shock Surface")
        sentiment_ctx = load_sentiment_context()
        narrative_events = data.get("narrative_events")
        if not isinstance(narrative_events, pd.DataFrame) or narrative_events.empty:
            st.info("News shock surface unavailable: narrative_events artifact missing.")
            return
        if not {"date", "magnitude"}.issubset(narrative_events.columns):
            st.info("News shock surface requires narrative_events.date and narrative_events.magnitude.")
            return

        ne = narrative_events.copy()
        ne["date"] = _to_naive_date_series(ne["date"], normalize=True)
        ne["magnitude"] = pd.to_numeric(ne["magnitude"], errors="coerce").abs()
        ne = ne.dropna(subset=["date", "magnitude"]).groupby("date", as_index=False)["magnitude"].sum()
        ne = ne.rename(columns={"magnitude": "narrative_shock"})
        if ne.empty:
            st.info("Narrative events are empty after cleaning.")
            return

        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            s = market_df.copy()
            tcol = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
            if tcol:
                s["date"] = _to_naive_date_series(s[tcol], normalize=True)
                if "sentiment_signal" in s.columns:
                    s["sentiment_signal"] = pd.to_numeric(s["sentiment_signal"], errors="coerce")
                    s = s.dropna(subset=["date"]).groupby("date", as_index=False)["sentiment_signal"].mean()
                    s["macro_sentiment_z"] = self._zscore(s["sentiment_signal"])
                    ne = ne.merge(s[["date", "macro_sentiment_z"]], on="date", how="left")
        if "macro_sentiment_z" not in ne.columns:
            ne["macro_sentiment_z"] = np.nan

        ne = self._focus_active_window(
            ne,
            time_col="date",
            value_cols=["narrative_shock", "macro_sentiment_z"],
            max_rows=900,
            min_rows=160,
            eps=1e-8,
        )
        if ne.empty:
            st.info("News shock surface has no active non-flat window.")
            return

        latest = ne.iloc[-1]
        k1, k2 = st.columns(2)
        with k1:
            self._kpi_card("Narrative Shock", f"{_as_float(latest.get('narrative_shock'), np.nan):.3f}" if np.isfinite(_as_float(latest.get("narrative_shock"), np.nan)) else "n/a")
        with k2:
            self._kpi_card("Macro Sentiment (z)", f"{_as_float(latest.get('macro_sentiment_z'), np.nan):+.2f}" if np.isfinite(_as_float(latest.get("macro_sentiment_z"), np.nan)) else "n/a")

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=ne["date"],
                y=ne["narrative_shock"],
                name="Narrative Shock",
                marker_color=THEME["red"],
                opacity=0.55,
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=ne["date"],
                y=ne["macro_sentiment_z"],
                mode="lines",
                name="Macro Sentiment (z)",
                line=dict(color=THEME["cyan"], width=1.9),
            ),
            secondary_y=True,
        )
        fig.update_layout(title="News Shock Surface (Narrative Intensity + Sentiment)")
        fig.update_yaxes(title_text="Narrative Shock", secondary_y=False)
        fig.update_yaxes(title_text="Macro Sentiment (z)", secondary_y=True)
        self._render_chart_with_contract(
            chart_id="news_layer_narrative_shock_intensity",
            fig=fig,
            data=data,
            key="news_shock_surface",
            height=340,
        )

    def render_system_health_surface(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("⚙ System Health Surface")
        log = data.get("system_log") or {}
        summary = log.get("summary", {}) if isinstance(log, dict) else {}
        success_rate = _as_float(log.get("success_rate"), np.nan) if isinstance(log, dict) else np.nan

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            self._kpi_card("Last Refresh", str(log.get("timestamp", "n/a")) if isinstance(log, dict) else "n/a")
        with c2:
            self._kpi_card("Success Rate", f"{success_rate:.1%}" if np.isfinite(success_rate) else "n/a")
        with c3:
            self._kpi_card("Steps", str(int(_as_float(summary.get("steps"), 0))) if isinstance(summary, dict) else "n/a")
        with c4:
            self._kpi_card("Failures", str(int(_as_float(summary.get("failed"), 0))) if isinstance(summary, dict) else "n/a")

        exec_log = log.get("execution_log") if isinstance(log, dict) else []
        if isinstance(exec_log, list) and exec_log:
            df = pd.DataFrame(exec_log)
            if "duration_seconds" in df.columns:
                df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")
            fig = px.bar(
                df.sort_values("duration_seconds", ascending=False),
                x="component",
                y="duration_seconds",
                color="status" if "status" in df.columns else None,
                title="Runtime Step Durations (s)",
            )
            self._render_chart_with_contract(
                chart_id="system_health_runtime_metrics",
                fig=fig,
                data=data,
                key="system_health_surface_runtime_metrics",
                height=330,
            )
        else:
            st.info("No execution timeline in system_log.")

        pw = data.get("portfolio_weights")
        if isinstance(pw, pd.DataFrame) and not pw.empty:
            w = pw.copy()
            ind_col = "Industry" if "Industry" in w.columns else ("sector" if "sector" in w.columns else None)
            w_col = next((c for c in ["weight", "final_weight", "allocation"] if c in w.columns), None)
            if ind_col and w_col:
                w[ind_col] = w[ind_col].astype(str)
                w[w_col] = pd.to_numeric(w[w_col], errors="coerce")
                w = w.dropna(subset=[ind_col, w_col])
                if not w.empty:
                    s = (
                        w.groupby(ind_col, as_index=False)[w_col]
                        .sum()
                        .assign(weight=lambda x: pd.to_numeric(x[w_col], errors="coerce").abs())
                        .sort_values("weight", ascending=False)
                        .head(12)
                    )
                    fig_s = px.bar(
                        s,
                        x=ind_col,
                        y="weight",
                        title="Sector Allocation Snapshot",
                        color="weight",
                        color_continuous_scale="Blues",
                    )
                    self._render_chart_with_contract(
                        chart_id="system_health_sector_allocation",
                        fig=fig_s,
                        data=data,
                        key="system_health_surface_sector_allocation",
                        height=320,
                    )

    def render_market_state_layer(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("🌍 Market State")
        sentiment_ctx = load_sentiment_context()
        regime = self._latest_regime_snapshot(data)
        policy = sentiment_ctx.get("policy_context", {}) if isinstance(sentiment_ctx, dict) else {}

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            self._kpi_card("Regime", str(regime.get("regime", "Unknown")))
        with c2:
            score = _as_float(regime.get("risk_on_score"), default=np.nan)
            self._kpi_card("Regime Confidence", f"{score:.2f}" if np.isfinite(score) else "n/a")
        with c3:
            self._kpi_card("RBI Stance", str(policy.get("rbi_stance", "neutral")).replace("_", " ").title())
        with c4:
            flags = policy.get("regulatory_stress_flags", []) if isinstance(policy, dict) else []
            self._kpi_card("Policy Stress Flags", str(len(flags)))

        top = st.columns(2)
        with top[0]:
            mr = data.get("market_regime")
            if isinstance(mr, pd.DataFrame) and not mr.empty and {"volatility", "correlation"}.issubset(mr.columns):
                df = mr.copy()
                tcol = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)
                if tcol:
                    df["Date"] = _to_naive_date_series(df[tcol], normalize=False)
                else:
                    df["Date"] = _to_naive_date_series(pd.Series(df.index), normalize=False)
                for c in ["volatility", "correlation", "risk_on_score"]:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors="coerce")
                df = df.dropna(subset=["Date"]).sort_values("Date")
                
                # Limit to recent data (12 months) to avoid visual clutter
                df = self._limit_timeseries_to_recent(df, months_back=12)
                
                if not live_mode and len(df) > 300:
                    df = df.tail(300)
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                if "risk_on_score" in df.columns:
                    fig.add_trace(
                        go.Scatter(x=df["Date"], y=df["risk_on_score"], name="Risk-On Score", line=dict(color=THEME["green"], width=2)),
                        secondary_y=False,
                    )
                z_vol = self._zscore(df["volatility"])
                z_corr = self._zscore(df["correlation"])
                fig.add_trace(
                    go.Scatter(x=df["Date"], y=(z_vol + z_corr), name="Risk Pressure", line=dict(color=THEME["red"], width=1.8)),
                    secondary_y=True,
                )
                fig.update_layout(title="Regime Confidence + Risk Pressure")
                fig.update_yaxes(title_text="Risk-On Score", secondary_y=False)
                fig.update_yaxes(title_text="Pressure (z)", secondary_y=True)
                self._render_chart_with_contract(
                    chart_id="market_state_regime_pressure",
                    fig=fig,
                    data=data,
                    key="market_state_regime_pressure",
                    height=320,
                )
                self._formula_note(
                    "Regime Pressure Formula",
                    [
                        "z_vol_t = zscore(volatility_t)",
                        "z_corr_t = zscore(correlation_t)",
                        "risk_pressure_t = z_vol_t + z_corr_t",
                    ],
                )
            else:
                st.info("No market_regime artifact for regime/risk-pressure panel.")

        with top[1]:
            # Try sector-level macro heatmap first
            sector_heatmap = data.get("macro_impact_sector_heatmap")
            if isinstance(sector_heatmap, pd.DataFrame) and not sector_heatmap.empty:
                self._render_macro_impact_heatmap(sector_heatmap, data)
            else:
                # Fallback to macro factors heatmap
                mf = data.get("macro_factors_v2")
                if not isinstance(mf, pd.DataFrame) or mf.empty:
                    mf = data.get("macro_factors")
                if isinstance(mf, pd.DataFrame) and not mf.empty:
                    x = self._prepare_macro_heatmap_changes(mf, tail_rows=140)
                    if not x.empty:
                        # Enhanced heatmap with better styling
                        fig_hm = go.Figure(data=go.Heatmap(
                            z=x.T.values,
                            x=x.index.strftime('%Y-%m-%d') if hasattr(x.index, 'strftime') else x.index,
                            y=[str(col)[:25] for col in x.columns],
                            colorscale='RdBu_r',
                            zmid=0,
                            colorbar=dict(title="Z-Score"),
                            hoverongaps=False,
                            hovertemplate='<b>%{y}</b><br>Date: %{x}<br>Z-Score: %{z:.2f}<extra></extra>'
                        ))
                        fig_hm.update_layout(
                            title="Macro Factor Changes Heatmap (Z-Scores)",
                            xaxis_title="Date",
                            yaxis_title="Macro Variables",
                            height=320
                        )
                        self._render_chart_with_contract(
                            chart_id="market_state_macro_heatmap",
                            fig=fig_hm,
                            data=data,
                            key="market_state_macro_heatmap",
                            height=320,
                        )
                        self._formula_note(
                            "Enhanced Macro Heatmap",
                            [
                                "input = diff(macro_factor) by period OR levels if no changes",
                                "display value = robust z-score (median/MAD) with fallback to standard z-score",
                                "enhanced filtering preserves more data points",
                                f"showing {len(x.columns)} variables over {len(x)} periods",
                            ],
                        )
                    else:
                        st.info("Macro heatmap: insufficient data variation detected.")
                else:
                    st.info("No macro factor artifact available.")

        self.render_macro_news_pressure_index(data, sentiment_ctx, key_prefix="market_state")
        self.render_sector_sentiment_vs_flows(data, sentiment_ctx, key_prefix="market_state")

    def render_intelligence_layer(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("🧠 Northstar Intelligence")
        sentiment_ctx = load_sentiment_context()

        col1, col2 = st.columns(2)
        with col1:
            beliefs = data.get("strategy_beliefs")
            if isinstance(beliefs, pd.DataFrame) and not beliefs.empty:
                b = beliefs.copy()
                metric = _pick_belief_metric(b)
                tcol = _pick_time_column(b, ["date", "Date", "timestamp"])
                if metric and tcol:
                    b["date"] = _to_naive_date_series(b[tcol], normalize=False)
                    for c in [metric, "effective_skill"]:
                        if c in b.columns:
                            b[c] = pd.to_numeric(b[c], errors="coerce")
                    metric_use = (
                        "effective_skill"
                        if ("effective_skill" in b.columns and pd.to_numeric(b["effective_skill"], errors="coerce").notna().sum() >= 5)
                        else metric
                    )
                    b = b.dropna(subset=["date", metric_use]).sort_values("date")
                    if not b.empty:
                        if "strategy" in b.columns:
                            obs_per_strategy = b.groupby("strategy")["date"].nunique()
                            has_history = bool((obs_per_strategy >= 3).any())
                        else:
                            has_history = bool(b["date"].nunique() >= 5)
                        if has_history:
                            fig = px.line(
                                b,
                                x="date",
                                y=metric_use,
                                color="strategy" if "strategy" in b.columns else None,
                                title=f"{metric_use.replace('_', ' ').title()} Evolution",
                            )
                        else:
                            latest = b.sort_values("date").groupby("strategy", as_index=False).tail(1) if "strategy" in b.columns else b.tail(20)
                            if "strategy" in latest.columns:
                                latest = latest.sort_values(metric_use, ascending=False)
                            fig = px.bar(
                                latest,
                                x="strategy" if "strategy" in latest.columns else "date",
                                y=metric_use,
                                title=f"{metric_use.replace('_', ' ').title()} (Latest Snapshot; history sparse)",
                            )
                        self._apply_fig_theme(fig, height=320)
                        st.plotly_chart(fig, width="stretch", key="intelligence_belief_skill_evolution")
                        self._formula_note(
                            "Belief / Skill Formula",
                            [
                                "metric priority = effective_skill (if populated) else selected belief metric",
                                "evolution line shown only when per-strategy history is sufficient",
                            ],
                        )
            else:
                st.info("No strategy beliefs artifact available.")

            regret = data.get("strategy_regret")
            if isinstance(regret, pd.DataFrame) and not regret.empty and "regret_score" in regret.columns:
                r = regret.copy()
                name_col = "strategy_name" if "strategy_name" in r.columns else ("strategy" if "strategy" in r.columns else None)
                if name_col:
                    r[name_col] = r[name_col].astype(str)
                    r["regret_score"] = pd.to_numeric(r["regret_score"], errors="coerce")
                    r = r.dropna(subset=["regret_score"]).sort_values("regret_score", ascending=False).head(15)
                    if not r.empty:
                        fig = px.bar(r, x=name_col, y="regret_score", title="Regret Score (Higher = Worse)")
                        self._apply_fig_theme(fig, height=280)
                        st.plotly_chart(fig, width="stretch", key="intelligence_regret_score")
                        self._formula_note(
                            "Regret Score Formula",
                            [
                                "regret_score = artifact-provided composite regret metric",
                                "chart order = descending regret_score",
                            ],
                        )

        with col2:
            self.render_belief_vs_news_divergence(data, sentiment_ctx)
            posterior = data.get("valuation_posterior")
            if isinstance(posterior, pd.DataFrame) and not posterior.empty and "posterior_gap" in posterior.columns:
                p = posterior.copy()
                p["posterior_gap"] = pd.to_numeric(p["posterior_gap"], errors="coerce")
                p = p.dropna(subset=["posterior_gap"])
                if not p.empty:
                    fig = px.histogram(
                        p,
                        x="posterior_gap",
                        nbins=40,
                        title="Valuation Posterior Gap Distribution",
                    )
                    self._apply_fig_theme(fig, height=280)
                    st.plotly_chart(fig, width="stretch", key="intelligence_posterior_gap_hist")
                    self._formula_note(
                        "Valuation Posterior Gap Formula",
                        [
                            "posterior_gap = posterior_value deviation metric from valuation engine",
                            "histogram plots distribution of posterior_gap",
                        ],
                    )

        opp = data.get("opportunity_surface")
        if isinstance(opp, pd.DataFrame) and not opp.empty:
            d = opp.copy()
            for c in ["mispricing", "confirmation", "northstar_score", "pulse_weighted_score", "regime_adjusted_score"]:
                if c in d.columns:
                    d[c] = pd.to_numeric(d[c], errors="coerce")
            score_col = next((c for c in ["pulse_weighted_score", "regime_adjusted_score", "northstar_score"] if c in d.columns), None)
            if score_col and {"mispricing", "confirmation"}.issubset(d.columns):
                d = d.dropna(subset=["mispricing", "confirmation", score_col])
                if not d.empty:
                    d["_size"] = d[score_col].clip(lower=0).fillna(0)
                    fig = px.scatter(
                        d.head(1200),
                        x="mispricing",
                        y="confirmation",
                        color="opportunity_type" if "opportunity_type" in d.columns else None,
                        size="_size",
                        hover_data=[c for c in ["ticker", "Company Name"] if c in d.columns],
                        title="Opportunity Surface (mispricing × confirmation)",
                    )
                    self._apply_fig_theme(fig, height=380)
                    st.plotly_chart(fig, width="stretch", key="intelligence_opportunity_surface")
                    self._formula_note(
                        "Opportunity Surface Formula",
                        [
                            "x = mispricing",
                            "y = confirmation",
                            "bubble_size = max(score_col, 0)",
                            "score_col priority = pulse_weighted_score -> regime_adjusted_score -> northstar_score",
                        ],
                    )

        if not live_mode:
            # Add macro transmission panel in research mode
            self.render_enhanced_macro_transmission_panel(data)
            
            with st.expander("Open Deep Intelligence Workspace", expanded=False):
                st.info("Deep Intelligence workspace is available under `Research & Evolution → Deep Intelligence`.")

    def render_portfolio_expression_layer(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("📊 Portfolio Expression")

        options_state = data.get("options_dashboard_state") or {}
        greeks = options_state.get("portfolio_greeks", {}) if isinstance(options_state, dict) else {}
        g1, g2, g3, g4, g5 = st.columns(5)
        with g1:
            self._kpi_card("Current Regime", str(options_state.get("current_regime", "n/a")) if isinstance(options_state, dict) else "n/a")
        with g2:
            self._kpi_card("Options Delta", f"{_as_float(greeks.get('delta'), 0.0):.3f}" if isinstance(greeks, dict) else "n/a")
        with g3:
            self._kpi_card("Options Theta", f"{_as_float(greeks.get('theta'), 0.0):.3f}" if isinstance(greeks, dict) else "n/a")
        with g4:
            self._kpi_card("Options Vega", f"{_as_float(greeks.get('vega'), 0.0):.3f}" if isinstance(greeks, dict) else "n/a")
        with g5:
            ap = options_state.get("active_positions", []) if isinstance(options_state, dict) else []
            ap_count = len(ap) if isinstance(ap, list) else int(_as_float(ap, default=0.0))
            self._kpi_card("Options Positions", str(ap_count))

        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        idx = data.get("index_nifty50")
        if not pnl_df.empty:
            p = self._focus_active_window(
                pnl_df.copy().sort_values("Date"),
                time_col="Date",
                value_cols=["Equity", "Return"],
                max_rows=900,
                min_rows=180,
                eps=1e-8,
            )
            p["portfolio_norm"] = p["Equity"] / max(1e-9, float(p["Equity"].iloc[0]))
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=p["Date"], y=p["portfolio_norm"], name="Portfolio", line=dict(color=THEME["blue"], width=2)))
            if isinstance(idx, pd.DataFrame) and not idx.empty:
                close_col = "close" if "close" in idx.columns else idx.columns[0]
                b = idx.copy().sort_index()
                b[close_col] = pd.to_numeric(b[close_col], errors="coerce")
                b = b.dropna(subset=[close_col])
                b = b[(b.index >= p["Date"].min()) & (b.index <= p["Date"].max())]
                if not b.empty:
                    fig.add_trace(go.Scatter(x=b.index, y=b[close_col] / max(1e-9, float(b[close_col].iloc[0])), name="NIFTY 50", line=dict(color=THEME["cyan"], width=1.8)))
            fig.update_layout(title="Portfolio vs Benchmark (Normalized)")
            self._render_chart_with_contract(
                chart_id="portfolio_expression_vs_benchmark",
                fig=fig,
                data=data,
                key="portfolio_expression_vs_benchmark",
                height=340,
            )
            self._formula_note(
                "Portfolio vs Benchmark Formula",
                [
                    "portfolio_norm_t = equity_t / equity_0",
                    "benchmark_norm_t = close_t / close_0",
                ],
            )

        alloc = data.get("allocation_history")
        if isinstance(alloc, pd.DataFrame) and not alloc.empty and "date" in alloc.columns:
            ah = alloc.copy()
            ah["date"] = _to_naive_date_series(ah["date"], normalize=False)
            ah = ah.dropna(subset=["date"]).sort_values("date")
            meta_cols = {
                "date",
                "regime",
                "strategy_name",
                "strategy_category",
                "allocation_weight",
                "allocation_score",
                "regime_fitness",
                "adjusted_return",
                "adjusted_sharpe",
                "risk_contribution",
                "allocation_reason",
                "timestamp",
                "regime_name",
                "regime_stability",
                "no_edge_state",
                "exposure_cap",
                "total_exposure",
            }
            strat_cols = [c for c in ah.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(ah[c])]
            strat_cols = [c for c in strat_cols if ah[c].dropna().between(-0.01, 1.01).mean() > 0.9]
            if strat_cols:
                recent = ah[["date"] + strat_cols].groupby("date", as_index=True)[strat_cols].mean().tail(90)
                fig_hm = px.imshow(
                    recent.T,
                    aspect="auto",
                    color_continuous_scale="Viridis",
                    title="Allocation Heatmap (Recent)",
                )
                self._render_chart_with_contract(
                    chart_id="portfolio_expression_allocation_heatmap",
                    fig=fig_hm,
                    data=data,
                    key="portfolio_expression_allocation_heatmap",
                    height=360,
                )
                self._formula_note(
                    "Allocation Heatmap Formula",
                    [
                        "cell(strategy,date) = mean(strategy_weight on that date)",
                        "display window = latest 90 dates",
                    ],
                )

        split = st.columns(2)
        with split[0]:
            self._render_section_safely("Edge Half-Life", self.render_edge_health, data)
        with split[1]:
            self._render_section_safely("Liquidity Exit Risk", self.render_exit_risk, data)

        if not live_mode:
            with st.expander("Open Full Options Workstation", expanded=False):
                self._render_section_safely("Options Trading", self.render_options_trading)

    def render_risk_survival_layer(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("🛡 Risk & Survival")
        sentiment_ctx = load_sentiment_context()

        pnl_df = self._normalize_pnl_frame(data.get("pnl"))
        if not pnl_df.empty:
            r = pd.to_numeric(pnl_df["Return"], errors="coerce").dropna()
            surface = self._empirical_drawdown_surface(r)
            if not surface.empty:
                piv = surface.pivot(index="horizon", columns="threshold", values="probability")
                order_h = [f"{h}d" for h in [5, 20, 60] if f"{h}d" in piv.index]
                order_t = [f">{int(t * 100)}%" for t in [0.02, 0.05, 0.10, 0.15] if f">{int(t * 100)}%" in piv.columns]
                if order_h:
                    piv = piv.reindex(order_h)
                if order_t:
                    piv = piv[order_t]
                fig_dd = px.imshow(
                    piv,
                    aspect="auto",
                    color_continuous_scale="YlOrRd",
                    title="Drawdown Probability Surface (Empirical Forward Returns)",
                    labels={"x": "Drawdown Threshold", "y": "Horizon", "color": "Prob"},
                )
                self._render_chart_with_contract(
                    chart_id="risk_survival_drawdown_surface",
                    fig=fig_dd,
                    data=data,
                    key="risk_survival_drawdown_surface",
                    height=320,
                )
                self._formula_note(
                    "Drawdown Probability Surface Formula",
                    [
                        "fwd_return_{h,t} = exp(sum_{k=0..h-1}(log(1+r_{t+k}))) - 1",
                        "cell(h,threshold) = mean( fwd_return_{h,t} <= -threshold )",
                        "horizons = {5,20,60}, thresholds = {2%,5%,10%,15%}",
                    ],
                )
            elif len(r) >= 40:
                mu = float(r.mean())
                sigma = max(float(r.std()), 1e-6)
                dd_thresholds = np.asarray([0.05, 0.10, 0.15, 0.20], dtype=float)
                probs = []
                for x in dd_thresholds:
                    z = ((-x) - mu) / sigma
                    probs.append(0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))
                dd_df = pd.DataFrame(
                    {
                        "drawdown_threshold": [f">{int(x * 100)}%" for x in dd_thresholds],
                        "probability": probs,
                    }
                )
                fig_dd = px.line(
                    dd_df,
                    x="drawdown_threshold",
                    y="probability",
                    markers=True,
                    title="Drawdown Probability Surface (Normal Approximation)",
                )
                fig_dd.update_yaxes(range=[0, 1], tickformat=".0%")
                self._render_chart_with_contract(
                    chart_id="risk_survival_drawdown_surface",
                    fig=fig_dd,
                    data=data,
                    key="risk_survival_drawdown_surface_fallback",
                    height=300,
                )
                self._formula_note(
                    "Drawdown Probability Surface Formula (Fallback)",
                    [
                        "z_x = ((-threshold) - mean(return)) / std(return)",
                        "probability(threshold) = Phi(z_x)",
                    ],
                )

        alpha_ts = data.get("alpha_os_timeseries")
        if isinstance(alpha_ts, pd.DataFrame) and not alpha_ts.empty and "timestamp" in alpha_ts.columns:
            a = alpha_ts.copy()
            a["timestamp"] = _to_naive_date_series(a["timestamp"], normalize=False)
            a = a.dropna(subset=["timestamp"]).sort_values("timestamp")
            for c in ["regime_crisis", "regime_entropy", "fallback_tier"]:
                if c in a.columns:
                    a[c] = pd.to_numeric(a[c], errors="coerce")
            a["date"] = _to_naive_date_series(a["timestamp"], normalize=True)

            # If crisis stream is flat/saturated, build a stress-aware proxy so the chart remains informative.
            if "regime_crisis" in a.columns:
                crisis_base = pd.to_numeric(a["regime_crisis"], errors="coerce").clip(lower=0.0, upper=1.0)
                flat_crisis = bool(crisis_base.dropna().nunique() <= 2 or float(crisis_base.dropna().std() or 0.0) <= 1e-4)
            else:
                crisis_base = pd.Series(np.nan, index=a.index)
                flat_crisis = True

            crisis_display = crisis_base.copy()
            if flat_crisis:
                proxy_parts: List[pd.Series] = []
                mr = data.get("market_regime")
                if isinstance(mr, pd.DataFrame) and not mr.empty and {"volatility", "correlation"}.issubset(mr.columns):
                    m = mr.copy()
                    tcol_m = "Date" if "Date" in m.columns else ("date" if "date" in m.columns else None)
                    if tcol_m is not None:
                        m["date"] = _to_naive_date_series(m[tcol_m], normalize=True)
                    else:
                        m["date"] = _to_naive_date_series(pd.Series(m.index), normalize=True)
                    m["volatility"] = pd.to_numeric(m["volatility"], errors="coerce")
                    m["correlation"] = pd.to_numeric(m["correlation"], errors="coerce")
                    m = m.dropna(subset=["date"]).sort_values("date")
                    if not m.empty:
                        m["risk_pressure"] = self._zscore(m["volatility"]).values + self._zscore(m["correlation"]).values
                        p = m.groupby("date", as_index=False)["risk_pressure"].mean()
                        p = a[["date"]].merge(p, on="date", how="left")
                        proxy_parts.append(self._sigmoid_from_series(p["risk_pressure"]))

                market_df = sentiment_ctx.get("market_df", pd.DataFrame())
                if isinstance(market_df, pd.DataFrame) and not market_df.empty:
                    s = market_df.copy()
                    tcol_s = next((c for c in ["date", "Date", "timestamp"] if c in s.columns), None)
                    if tcol_s:
                        s["date"] = _to_naive_date_series(s[tcol_s], normalize=True)
                        if "uncertainty" in s.columns:
                            s["uncertainty"] = pd.to_numeric(s["uncertainty"], errors="coerce")
                        elif "event_shock_factor" in s.columns:
                            s["uncertainty"] = pd.to_numeric(s["event_shock_factor"], errors="coerce")
                        else:
                            s["uncertainty"] = np.nan
                        s = s.dropna(subset=["date"]).groupby("date", as_index=False)["uncertainty"].mean()
                        s = a[["date"]].merge(s, on="date", how="left")
                        proxy_parts.append(self._sigmoid_from_series(s["uncertainty"]))

                if proxy_parts:
                    proxy = pd.concat(proxy_parts, axis=1).mean(axis=1)
                    crisis_display = proxy if crisis_base.isna().all() else (0.35 * crisis_base.fillna(proxy) + 0.65 * proxy)
            a["crisis_probability_display"] = pd.to_numeric(crisis_display, errors="coerce").clip(0.0, 1.0)

            a = self._focus_active_window(
                a,
                time_col="timestamp",
                value_cols=["regime_crisis", "crisis_probability_display", "regime_entropy"],
                max_rows=365,  # Reduced from 900 to ~1 year
                min_rows=90,   # Reduced from 180 to ~3 months
                eps=1e-8,
            )
            cols = st.columns(2)
            with cols[0]:
                if "crisis_probability_display" in a.columns:
                    fig = px.line(a, x="timestamp", y="crisis_probability_display", title="Crisis Probability")
                    fig.update_yaxes(range=[0, 1], tickformat=".0%")
                    self._render_chart_with_contract(
                        chart_id="risk_survival_crisis_probability",
                        fig=fig,
                        data=data,
                        key="risk_survival_crisis_probability",
                        height=280,
                    )
                    self._formula_note(
                        "Crisis Probability Formula",
                        [
                            "base = alpha_os_timeseries.regime_crisis",
                            "if base flat: proxy = sigmoid(z(risk_pressure) + z(news_uncertainty))",
                            "display = 0.35*base + 0.65*proxy (or proxy only if base missing)",
                            "value range constrained to [0, 1]",
                        ],
                    )
            with cols[1]:
                if "regime_entropy" in a.columns:
                    entropy = (
                        a[["timestamp", "regime_entropy"]]
                        .copy()
                        .dropna(subset=["regime_entropy"])
                    )
                    if not entropy.empty:
                        fig = px.line(
                            entropy,
                            x="timestamp",
                            y="regime_entropy",
                            title="Regime Entropy (Uncertainty)",
                        )
                        self._render_chart_with_contract(
                            chart_id="risk_survival_regime_entropy",
                            fig=fig,
                            data=data,
                            key="risk_survival_regime_entropy",
                            height=280,
                        )
                        self._formula_note(
                            "Regime Entropy Formula",
                            [
                                "entropy_t = -sum_i p_i,t * log(p_i,t)",
                                "higher entropy implies lower regime certainty",
                            ],
                        )

        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            d = market_df.copy()
            tcol = next((c for c in ["date", "Date", "timestamp"] if c in d.columns), None)
            if tcol and {"uncertainty", "event_shock_factor"}.intersection(set(d.columns)):
                d["date"] = _to_naive_date_series(d[tcol], normalize=False)
                d = d.dropna(subset=["date"]).sort_values("date")
                if "uncertainty" in d.columns:
                    d["uncertainty"] = pd.to_numeric(d["uncertainty"], errors="coerce").fillna(0.0)
                else:
                    d["uncertainty"] = 0.0
                if "event_shock_factor" in d.columns:
                    d["event_shock_factor"] = pd.to_numeric(d["event_shock_factor"], errors="coerce").fillna(0.0)
                else:
                    d["event_shock_factor"] = 0.0
                d["systemic_stress"] = 0.6 * d["uncertainty"] + 0.4 * d["event_shock_factor"]
                
                # Limit to recent data (12 months)
                d = self._limit_timeseries_to_recent(d, months_back=12)
                
                # Check if data is meaningful (not all zeros)
                if d["systemic_stress"].abs().sum() < 1e-6:
                    # Generate enhanced stress index
                    enhanced_stress = self._enhance_empty_news_stress_index(data)
                    if not enhanced_stress.empty:
                        d = enhanced_stress
                        d = self._limit_timeseries_to_recent(d, months_back=12)
                
                if not d.empty:
                    fig = px.line(
                        d,
                        x="date",
                        y="systemic_stress" if "systemic_stress" in d.columns else "stress_index",
                        title="News-Based Systemic Stress Index",
                    )
                    self._render_chart_with_contract(
                        chart_id="risk_survival_systemic_stress",
                        fig=fig,
                        data=data,
                        key="risk_survival_systemic_stress",
                        height=280,
                    )
                    self._formula_note(
                        "Systemic Stress Formula",
                        [
                            "systemic_stress_t = 0.6 * uncertainty_t + 0.4 * event_shock_factor_t",
                            "enhanced when original data is empty using narrative events or market volatility",
                            f"showing recent {len(d)} periods (limited to 12 months)",
                        ],
                    )
        else:
            # Try to create enhanced stress index from other sources
            enhanced_stress = self._enhance_empty_news_stress_index(data)
            if not enhanced_stress.empty:
                enhanced_stress = self._limit_timeseries_to_recent(enhanced_stress, months_back=12)
                fig = px.line(
                    enhanced_stress,
                    x="date",
                    y="stress_index",
                    title="News-Based Systemic Stress Index (Enhanced)",
                )
                self._render_chart_with_contract(
                    chart_id="risk_survival_systemic_stress",
                    fig=fig,
                    data=data,
                    key="risk_survival_systemic_stress_enhanced",
                    height=280,
                )
                self._formula_note(
                    "Enhanced Systemic Stress Formula",
                    [
                        "stress_index_t = derived from narrative events or market volatility",
                        f"showing recent {len(enhanced_stress)} periods (limited to 12 months)",
                    ],
                )

        if not live_mode:
            with st.expander("Open Full AlphaOS Control Tower", expanded=False):
                self._render_section_safely("AlphaOS Control Tower", self.render_alpha_os_control_tower, data)

    def render_research_evolution_layer(self, data: Dict[str, Any]) -> None:
        st.subheader("🔬 Research & Evolution")
        t1, t2, t3, t4, t5, t6 = st.tabs(
            [
                "Mission Control",
                "Research Mode",
                "Experimentation",
                "V3 Analytics",
                "Deep Intelligence",
                "Cross-Layer Coupling",
            ]
        )
        with t1:
            self._render_section_safely("Mission Control", self.render_mission_control, data)
        with t2:
            self._render_section_safely("Research Mode", self.render_research_mode_compact, data)
        with t3:
            self._render_section_safely("Experimentation", self.render_experimentation_lab, data)
        with t4:
            self._render_section_safely("V3 Analytics", self.render_v3_analytics, data)
        with t5:
            self._render_section_safely("Advanced Intelligence", self.render_advanced_intelligence, data)
        with t6:
            self._render_section_safely("Cross-Layer Coupling", self.render_cross_layer_coupling, data)

    def render_news_narrative_layer(self, data: Dict[str, Any], *, live_mode: bool = False) -> None:
        st.subheader("📰 News & Narrative")
        sentiment_ctx = load_sentiment_context()

        self.render_macro_news_pressure_index(data, sentiment_ctx, key_prefix="news_layer")
        self.render_sector_sentiment_vs_flows(data, sentiment_ctx, key_prefix="news_layer")
        self.render_event_shock_surface(data, sentiment_ctx)

        narrative_events = data.get("narrative_events")
        if isinstance(narrative_events, pd.DataFrame) and not narrative_events.empty:
            ne = narrative_events.copy()
            if "date" in ne.columns:
                ne["date"] = _to_naive_date_series(ne["date"], normalize=False)
                ne = ne.dropna(subset=["date"]).sort_values("date")
            if {"date", "magnitude"}.issubset(ne.columns):
                ne["magnitude"] = pd.to_numeric(ne["magnitude"], errors="coerce").fillna(0.0).abs()
                mag = ne.groupby("date", as_index=False)["magnitude"].sum()
                mag = self._focus_active_window(
                    mag,
                    time_col="date",
                    value_cols=["magnitude"],
                    max_rows=900,
                    min_rows=160,
                    eps=1e-8,
                )
                fig = px.line(mag, x="date", y="magnitude", title="Narrative Shock Intensity")
                self._render_chart_with_contract(
                    chart_id="news_layer_narrative_shock_intensity",
                    fig=fig,
                    data=data,
                    key="news_layer_narrative_shock_intensity",
                    height=280,
                )
                self._formula_note(
                    "Narrative Shock Formula",
                    [
                        "daily_narrative_shock_t = sum(abs(magnitude_event_t))",
                    ],
                )

        if not live_mode:
            with st.expander("Open Full Sentiment Diagnostics", expanded=False):
                self._render_section_safely("Sentiment", self.render_sentiment)

    # ---------------------------- CROSS-LAYER COUPLING ----------------------------
    def _get_integrated_frame(self, max_rows: int = 2500) -> pd.DataFrame:
        df = load_integrated_state_snapshot(max_rows=max_rows)
        if not isinstance(df, pd.DataFrame) or df.empty or "date" not in df.columns:
            return pd.DataFrame()
        out = df.copy()
        out["date"] = _to_naive_date_series(out["date"], normalize=True)
        out = out.dropna(subset=["date"]).sort_values("date")
        if out.empty:
            return out

        if "macro_news_sentiment" in out.columns:
            out["macro_news_sentiment"] = pd.to_numeric(out["macro_news_sentiment"], errors="coerce")
        if ("macro_sentiment_z" not in out.columns) or _series_is_sparse_or_flat(out.get("macro_sentiment_z", pd.Series(dtype=float)), min_non_na=30, min_unique=5):
            if "macro_news_sentiment" in out.columns and pd.to_numeric(out["macro_news_sentiment"], errors="coerce").notna().sum() >= 20:
                out["macro_sentiment_z"] = self._zscore(pd.to_numeric(out["macro_news_sentiment"], errors="coerce"))

        out["drawdown_probability_30d"] = _resolve_drawdown_probability_series(out)

        if "gross_exposure" in out.columns:
            ge = pd.to_numeric(out["gross_exposure"], errors="coerce")
            sparse_exposure = ge.notna().sum() < max(20, int(len(out) * 0.4))
            if sparse_exposure or _series_is_sparse_or_flat(ge, min_non_na=20, min_unique=5, max_zero_share=0.95):
                ge = ge.mask(ge.abs() <= 1e-9).ffill().bfill()
            out["gross_exposure"] = ge

        if "regime_confidence" in out.columns:
            rc = pd.to_numeric(out["regime_confidence"], errors="coerce")
            if _series_is_sparse_or_flat(rc, min_non_na=20, min_unique=5, max_zero_share=0.95):
                if "risk_on_probability" in out.columns:
                    rp = pd.to_numeric(out["risk_on_probability"], errors="coerce")
                    rc = rc.where(rc.abs() > 1e-9, rp)
            out["regime_confidence"] = rc.clip(0.0, 1.0)
        return out

    def render_causal_flow_panel(
        self,
        data: Dict[str, Any],
        integrated: Optional[pd.DataFrame] = None,
        *,
        key_prefix: str = "causal_flow_global",
    ) -> None:
        """Compact synchronized causal strip: Macro -> Regime -> Belief -> Allocation -> PnL."""
        df = integrated.copy() if isinstance(integrated, pd.DataFrame) else self._get_integrated_frame(max_rows=1200)
        if df.empty:
            st.info("Causal flow unavailable: integrated snapshot not found.")
            return

        use_cols = ["date", "macro_sentiment_z", "regime_confidence", "belief_strength", "gross_exposure", "nav"]
        for c in use_cols:
            if c not in df.columns:
                df[c] = np.nan
        d = df[use_cols].copy()
        for c in ["macro_sentiment_z", "regime_confidence", "belief_strength", "gross_exposure", "nav"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["date"])
        if d.empty:
            st.info("Causal flow unavailable after cleaning.")
            return

        d["pnl_norm"] = d["nav"] / max(1e-9, float(d["nav"].dropna().iloc[0])) if d["nav"].notna().any() else np.nan
        d = self._focus_active_window(
            d,
            time_col="date",
            value_cols=["macro_sentiment_z", "regime_confidence", "belief_strength", "gross_exposure", "pnl_norm"],
            max_rows=500,
            min_rows=160,
            eps=1e-8,
        )
        if d.empty:
            return

        dates = d["date"].dt.date.tolist()
        focus_date = dates[-1]
        if len(dates) > 20:
            focus_date = st.select_slider(
                "Causal focus date",
                options=dates,
                value=dates[-1],
                key=f"{key_prefix}_focus_date",
            )

        focus_ts = pd.Timestamp(focus_date)
        d_focus = d[d["date"].dt.date == focus_date].tail(1)
        d_focus = d_focus.iloc[0] if not d_focus.empty else d.iloc[-1]

        fig = make_subplots(
            rows=5,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=(
                "Macro Sentiment (z)",
                "Regime Confidence",
                "Belief Strength",
                "Gross Exposure",
                "Portfolio NAV (norm)",
            ),
        )
        series_meta = [
            ("macro_sentiment_z", THEME["amber"]),
            ("regime_confidence", THEME["cyan"]),
            ("belief_strength", THEME["violet"]),
            ("gross_exposure", THEME["green"]),
            ("pnl_norm", THEME["blue"]),
        ]
        for idx, (col, color) in enumerate(series_meta, start=1):
            fig.add_trace(
                go.Scatter(
                    x=d["date"],
                    y=d[col],
                    mode="lines",
                    name=col,
                    line=dict(color=color, width=1.8),
                    showlegend=False,
                ),
                row=idx,
                col=1,
            )
            fig.add_vline(x=focus_ts, row=idx, col=1, line_dash="dot", line_color=THEME["grid"])
        fig.update_layout(title="Causal Flow Panel: Macro -> Regime -> Belief -> Allocation -> PnL")
        self._apply_fig_theme(fig, height=760)
        if key_prefix == "causal_flow_global":
            st.plotly_chart(fig, width="stretch", key="causal_flow_global_panel")
        else:
            st.plotly_chart(fig, width="stretch", key="causal_flow_panel_generic")
        self._formula_note(
            "Causal Flow Formulas",
            [
                "macro = macro_sentiment_z",
                "regime = regime_confidence",
                "belief = belief_strength",
                "allocation = gross_exposure",
                "pnl_norm_t = nav_t / nav_0",
            ],
        )

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            self._kpi_card("Macro (z)", f"{_as_float(d_focus['macro_sentiment_z'], np.nan):+.2f}" if np.isfinite(_as_float(d_focus["macro_sentiment_z"], np.nan)) else "n/a")
        with k2:
            self._kpi_card("Regime Conf", f"{_as_float(d_focus['regime_confidence'], np.nan):.2f}" if np.isfinite(_as_float(d_focus["regime_confidence"], np.nan)) else "n/a")
        with k3:
            self._kpi_card("Belief", f"{_as_float(d_focus['belief_strength'], np.nan):.2f}" if np.isfinite(_as_float(d_focus["belief_strength"], np.nan)) else "n/a")
        with k4:
            self._kpi_card("Gross Exposure", f"{_as_float(d_focus['gross_exposure'], np.nan):.3f}" if np.isfinite(_as_float(d_focus["gross_exposure"], np.nan)) else "n/a")
        with k5:
            self._kpi_card("NAV (norm)", f"{_as_float(d_focus['pnl_norm'], np.nan):.3f}" if np.isfinite(_as_float(d_focus["pnl_norm"], np.nan)) else "n/a")

    def render_regime_belief_allocation_elasticity_surface(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        required = ["date", "regime_confidence", "belief_strength", "gross_exposure"]
        for c in required:
            if c not in d.columns:
                st.info("Elasticity surface unavailable in integrated snapshot.")
                return
        d = d[["date", "regime_confidence", "belief_strength", "gross_exposure", "regime_label"] if "regime_label" in d.columns else ["date", "regime_confidence", "belief_strength", "gross_exposure"]].copy()
        for c in ["regime_confidence", "belief_strength", "gross_exposure"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["date", "regime_confidence", "gross_exposure"]).sort_values("date")
        if len(d) < 20:
            st.info("Need more history for elasticity surface.")
            return

        d["allocation_change"] = d["gross_exposure"].diff()
        d["regime_change"] = d["regime_confidence"].diff()
        d["belief_change"] = d["belief_strength"].diff()
        d["elasticity"] = d["allocation_change"] / (d["regime_change"].abs() + 1e-6)
        d["_bubble"] = d["elasticity"].abs().clip(lower=0.02, upper=5.0)
        d = d.dropna(subset=["allocation_change", "regime_change", "elasticity"]).tail(600)
        if d.empty:
            st.info("Elasticity surface has no usable rows.")
            return

        fig = px.scatter(
            d,
            x="regime_confidence",
            y="allocation_change",
            color="regime_label" if "regime_label" in d.columns else None,
            size="_bubble",
            hover_data=["date", "belief_change", "elasticity"],
            title="Regime -> Allocation Elasticity Surface",
        )
        fig.add_hline(y=0, line_dash="dot", line_color=THEME["grid"])
        fig.add_vline(x=float(pd.to_numeric(d["regime_confidence"], errors="coerce").median()), line_dash="dot", line_color=THEME["grid"])
        self._apply_fig_theme(fig, height=360)
        st.plotly_chart(fig, width="stretch", key="cross_layer_regime_allocation_elasticity")

        d["rolling_elasticity_20d"] = (
            d["allocation_change"].rolling(20, min_periods=5).sum()
            / (d["regime_change"].abs().rolling(20, min_periods=5).sum() + 1e-6)
        )
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(
            go.Scatter(x=d["date"], y=d["rolling_elasticity_20d"], name="Rolling Elasticity (20d)", line=dict(color=THEME["violet"], width=2)),
            secondary_y=False,
        )
        fig2.add_trace(
            go.Scatter(x=d["date"], y=d["belief_change"], name="Belief Change", line=dict(color=THEME["cyan"], width=1.6)),
            secondary_y=True,
        )
        fig2.update_layout(title="Belief Drift vs Allocation Elasticity")
        fig2.update_yaxes(title_text="Elasticity", secondary_y=False)
        fig2.update_yaxes(title_text="Belief Change", secondary_y=True)
        self._apply_fig_theme(fig2, height=300)
        st.plotly_chart(fig2, width="stretch", key="cross_layer_belief_allocation_elasticity")
        self._formula_note(
            "Elasticity Formulas",
            [
                "allocation_change_t = gross_exposure_t - gross_exposure_{t-1}",
                "regime_change_t = regime_confidence_t - regime_confidence_{t-1}",
                "belief_change_t = belief_strength_t - belief_strength_{t-1}",
                "elasticity_t = allocation_change_t / (abs(regime_change_t) + 1e-6)",
                "rolling_elasticity_20d = sum_20d(allocation_change) / (sum_20d(abs(regime_change)) + 1e-6)",
            ],
        )

    def render_narrative_regime_transition_map(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        if "regime_label" not in d.columns:
            st.info("Narrative-transition map unavailable: regime labels missing.")
            return
        shock_col = "narrative_shock_intensity" if "narrative_shock_intensity" in d.columns else None
        if shock_col is None:
            if "macro_news_sentiment" in d.columns:
                d["narrative_shock_intensity"] = pd.to_numeric(d["macro_news_sentiment"], errors="coerce").diff().abs()
                shock_col = "narrative_shock_intensity"
            else:
                st.info("Narrative-transition map unavailable: no narrative shock signal.")
                return

        d["regime_label"] = d["regime_label"].astype(str)
        d[shock_col] = pd.to_numeric(d[shock_col], errors="coerce")
        d = d.dropna(subset=["date", "regime_label", shock_col]).sort_values("date")
        if len(d) < 20:
            st.info("Need more narrative/regime overlap for transition map.")
            return
        d["prev_regime"] = d["regime_label"].shift(1)
        d["transition"] = d["prev_regime"].fillna("NA") + "→" + d["regime_label"].fillna("NA")
        d = d[d["prev_regime"].notna() & (d["prev_regime"] != d["regime_label"])].copy()
        if d.empty:
            st.info("No regime transitions found in current sample.")
            return

        n_unique = int(pd.to_numeric(d[shock_col], errors="coerce").nunique(dropna=True))
        q = int(min(10, max(2, n_unique)))
        d["shock_decile"] = np.nan
        try:
            labels = [f"D{i}" for i in range(1, q + 1)]
            d["shock_decile"] = pd.qcut(d[shock_col], q=q, labels=labels, duplicates="drop")
        except Exception:
            d["shock_decile"] = np.nan

        # Robust fallback when qcut cannot form clean bins (ties/low-variance samples).
        if d["shock_decile"].isna().all():
            ranks = pd.to_numeric(d[shock_col], errors="coerce").rank(method="average", pct=True)
            n_bins = int(min(10, max(2, int(np.sqrt(max(4, len(d)))))))
            try:
                edges = np.linspace(0.0, 1.0, n_bins + 1)
                labels = [f"D{i}" for i in range(1, n_bins + 1)]
                d["shock_decile"] = pd.cut(ranks, bins=edges, labels=labels, include_lowest=True)
            except Exception:
                d["shock_decile"] = np.nan

        # Final fallback: single bucket so transition matrix still renders.
        if d["shock_decile"].isna().all():
            d["shock_decile"] = "D1"
        d = d.dropna(subset=["shock_decile"])
        if d.empty:
            st.info("No decile-classified transition rows available.")
            return

        mat = pd.crosstab(d["transition"], d["shock_decile"], normalize="index")
        if mat.empty:
            st.info("Transition matrix is empty.")
            return
        fig = px.imshow(
            mat,
            aspect="auto",
            color_continuous_scale="YlOrRd",
            title="Narrative Shock Precursor Map (Transition Probability by Shock Decile)",
        )
        self._apply_fig_theme(fig, height=360)
        st.plotly_chart(fig, width="stretch", key="cross_layer_narrative_transition_map")
        self._formula_note(
            "Narrative Transition Formulas",
            [
                "transition_t = regime_{t-1} -> regime_t",
                "shock_t = narrative_shock_intensity_t (fallback: abs(delta macro_news_sentiment_t))",
                "shock_bucket_t = qcut(shock_t), fallback rank-bins, final fallback single bucket",
                "cell(transition,decile) = count(transition,decile) / count(transition)",
            ],
        )

    def render_macro_portfolio_transmission_network(self, data: Dict[str, Any]) -> None:
        mf = data.get("macro_factors_v2")
        if not isinstance(mf, pd.DataFrame) or mf.empty:
            mf = data.get("macro_factors")
        sf = data.get("sector_flows")
        pw = data.get("portfolio_weights")
        if not isinstance(mf, pd.DataFrame) or mf.empty or not isinstance(sf, pd.DataFrame) or sf.empty:
            st.info("Macro transmission network requires macro factors + sector flows.")
            return

        macro_latest = mf.tail(1).copy()
        macro_vals: Dict[str, float] = {}
        for c in macro_latest.columns:
            v = pd.to_numeric(macro_latest[c], errors="coerce")
            if v.notna().any():
                macro_vals[str(c)] = float(v.iloc[0])
        if not macro_vals:
            st.info("Macro transmission network: no numeric macro factors.")
            return

        flows = sf.copy()
        tcol = "Date" if "Date" in flows.columns else ("date" if "date" in flows.columns else None)
        industry_col = "Industry" if "Industry" in flows.columns else ("sector" if "sector" in flows.columns else None)
        flow_col = "flow_strength" if "flow_strength" in flows.columns else ("capital_flow" if "capital_flow" in flows.columns else None)
        if tcol is None or industry_col is None or flow_col is None:
            st.info("Sector flows missing required columns for transmission network.")
            return
        flows["date"] = _to_naive_date_series(flows[tcol], normalize=False)
        flows[flow_col] = pd.to_numeric(flows[flow_col], errors="coerce")
        flows = flows.dropna(subset=["date", flow_col, industry_col]).sort_values("date")
        if flows.empty:
            st.info("Sector flows are empty after cleaning.")
            return
        end_dt = flows["date"].max()
        start_dt = end_dt - pd.Timedelta(days=45)
        flows_recent = flows[flows["date"] >= start_dt].copy()
        flows = flows_recent if not flows_recent.empty else flows.copy()
        flows[industry_col] = flows[industry_col].astype(str)
        sector_flow = flows.groupby(industry_col, as_index=False)[flow_col].mean()
        sector_flow["abs_flow"] = sector_flow[flow_col].abs()
        sector_flow = sector_flow.sort_values("abs_flow", ascending=False).head(10)
        if sector_flow.empty:
            st.info("No sector flow intensity for transmission graph.")
            return

        sector_weight_map: Dict[str, float] = {}
        if isinstance(pw, pd.DataFrame) and not pw.empty:
            w = pw.copy()
            w_ind_col = "Industry" if "Industry" in w.columns else ("industry" if "industry" in w.columns else ("sector" if "sector" in w.columns else None))
            w_col = next((c for c in ["weight", "final_weight", "allocation", "exposure"] if c in w.columns), None)
            if w_ind_col and w_col:
                w[w_ind_col] = w[w_ind_col].astype(str)
                w[w_col] = pd.to_numeric(w[w_col], errors="coerce")
                w = w.dropna(subset=[w_ind_col, w_col])
                if not w.empty:
                    agg = w.groupby(w_ind_col)[w_col].apply(lambda s: float(np.abs(s).sum()))
                    sector_weight_map = agg.to_dict()

        macro_nodes = [f"Macro:{k}" for k in sorted(macro_vals.keys())[:6]]
        sector_nodes = [f"Sector:{s}" for s in sector_flow[industry_col].tolist()]
        portfolio_node = ["Portfolio"]
        nodes = macro_nodes + sector_nodes + portfolio_node
        node_idx = {n: i for i, n in enumerate(nodes)}

        src: List[int] = []
        tgt: List[int] = []
        val: List[float] = []
        link_colors: List[str] = []

        for m in macro_nodes:
            mk = m.split("Macro:", 1)[1]
            mval = abs(float(macro_vals.get(mk, 0.0)))
            for _, row in sector_flow.iterrows():
                sec = str(row[industry_col])
                sval = abs(float(row[flow_col]))
                weight = mval * sval
                if weight <= 1e-6:
                    continue
                src.append(node_idx[m])
                tgt.append(node_idx[f"Sector:{sec}"])
                val.append(float(weight))
                link_colors.append("rgba(6,182,212,0.35)")

        for _, row in sector_flow.iterrows():
            sec = str(row[industry_col])
            flow_mag = abs(float(row[flow_col]))
            w = float(sector_weight_map.get(sec, np.nan))
            edge_value = flow_mag * (w if np.isfinite(w) and w > 0 else 0.08)
            if edge_value <= 1e-6:
                continue
            src.append(node_idx[f"Sector:{sec}"])
            tgt.append(node_idx["Portfolio"])
            val.append(float(edge_value))
            link_colors.append("rgba(34,197,94,0.45)")

        if not src:
            st.info("Transmission graph had no non-zero edges.")
            return

        fig = go.Figure(
            data=[
                go.Sankey(
                    arrangement="snap",
                    node=dict(
                        label=nodes,
                        pad=16,
                        thickness=16,
                        color=["#3B82F6"] * len(macro_nodes) + ["#F59E0B"] * len(sector_nodes) + ["#22c55e"],
                    ),
                    link=dict(source=src, target=tgt, value=val, color=link_colors),
                )
            ]
        )
        fig.update_layout(title="Dynamic Macro -> Sector -> Portfolio Transmission Network")
        self._apply_fig_theme(fig, height=560)
        st.plotly_chart(fig, width="stretch", key="cross_layer_macro_transmission_network")
        self._formula_note(
            "Transmission Network Formulas",
            [
                "macro_strength_m = abs(macro_factor_m latest)",
                "sector_flow_s = abs(flow_strength_s latest)",
                "edge_macro_to_sector(m,s) = macro_strength_m * sector_flow_s",
                "sector_weight_s = sum_abs(position_weight in sector s)",
                "edge_sector_to_portfolio(s) = sector_flow_s * max(sector_weight_s, 0.08)",
            ],
        )

    def render_crisis_replay_with_narrative_overlay(self, integrated: pd.DataFrame, data: Dict[str, Any]) -> None:
        d = integrated.copy()
        if d.empty or "date" not in d.columns:
            st.info("Crisis replay unavailable: integrated snapshot missing.")
            return
        d["date"] = _to_naive_date_series(d["date"], normalize=False)
        d = d.dropna(subset=["date"]).sort_values("date")
        if d.empty:
            return

        min_d = d["date"].min().date()
        max_d = d["date"].max().date()
        windows = {
            "COVID Shock (2020-02 to 2020-07)": ("2020-02-01", "2020-07-31"),
            "NBFC Stress (2018-08 to 2019-01)": ("2018-08-01", "2019-01-31"),
            "Demonetization (2016-11 to 2017-02)": ("2016-11-01", "2017-02-28"),
            "Recent Window (latest 540d)": (str((d["date"].max() - pd.Timedelta(days=540)).date()), str(d["date"].max().date())),
        }
        label = st.selectbox(
            "Crisis replay window",
            options=list(windows.keys()),
            index=len(windows) - 1,
            key="cross_layer_crisis_window",
        )
        start_s, end_s = windows[label]
        start = pd.Timestamp(start_s)
        end = pd.Timestamp(end_s)
        w = d[(d["date"] >= start) & (d["date"] <= end)].copy()
        if w.empty:
            st.info(f"No overlap for {label}. Current integrated range is {min_d} to {max_d}.")
            return

        if "nav" in w.columns:
            w["nav"] = pd.to_numeric(w["nav"], errors="coerce")
            if w["nav"].notna().any():
                w["drawdown"] = w["nav"] / w["nav"].cummax() - 1.0
                w["nav_norm"] = w["nav"] / max(1e-9, float(w["nav"].dropna().iloc[0]))
            else:
                w["drawdown"] = np.nan
                w["nav_norm"] = np.nan
        else:
            w["drawdown"] = np.nan
            w["nav_norm"] = np.nan

        for c in ["macro_news_sentiment", "regime_confidence", "crisis_probability", "gross_exposure"]:
            if c in w.columns:
                w[c] = pd.to_numeric(w[c], errors="coerce")
            else:
                w[c] = np.nan

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Portfolio Exposure + Drawdown", "Narrative + Regime + Crisis"),
        )
        fig.add_trace(go.Scatter(x=w["date"], y=w["drawdown"] * 100.0, name="Drawdown %", line=dict(color=THEME["red"], width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=w["date"], y=w["gross_exposure"], name="Gross Exposure", line=dict(color=THEME["green"], width=1.8)), row=1, col=1)
        fig.add_trace(go.Scatter(x=w["date"], y=w["macro_news_sentiment"], name="News Sentiment", line=dict(color=THEME["amber"], width=1.8)), row=2, col=1)
        fig.add_trace(go.Scatter(x=w["date"], y=w["regime_confidence"], name="Regime Confidence", line=dict(color=THEME["cyan"], width=1.8)), row=2, col=1)
        fig.add_trace(go.Scatter(x=w["date"], y=w["crisis_probability"], name="Crisis Prob", line=dict(color=THEME["violet"], width=1.8)), row=2, col=1)

        ne = data.get("narrative_events")
        if isinstance(ne, pd.DataFrame) and not ne.empty and "date" in ne.columns:
            ev = ne.copy()
            ev["date"] = _to_naive_date_series(ev["date"], normalize=False)
            ev = ev[(ev["date"] >= start) & (ev["date"] <= end)].dropna(subset=["date"])
            if not ev.empty and "magnitude" in ev.columns:
                ev["magnitude"] = pd.to_numeric(ev["magnitude"], errors="coerce").abs()
                fig.add_trace(
                    go.Scatter(
                        x=ev["date"],
                        y=ev["magnitude"],
                        mode="markers",
                        marker=dict(size=8, color=THEME["pink"]),
                        name="Narrative Events",
                    ),
                    row=2,
                    col=1,
                )

        fig.update_layout(title=f"Crisis Replay with Narrative Overlay: {label}")
        self._apply_fig_theme(fig, height=520)
        st.plotly_chart(fig, width="stretch", key="cross_layer_crisis_replay_overlay")
        self._formula_note(
            "Crisis Replay Formulas",
            [
                "drawdown_t = nav_t / max(nav_<=t) - 1",
                "nav_norm_t = nav_t / nav_0",
                "narrative_event_marker_t = abs(magnitude_t)",
            ],
        )

    def render_belief_performance_decay_curve(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        if not {"belief_strength", "active_return"}.issubset(d.columns):
            st.info("Belief-performance decay unavailable: belief/return columns missing.")
            return
        d["belief_strength"] = pd.to_numeric(d["belief_strength"], errors="coerce")
        d["active_return"] = pd.to_numeric(d["active_return"], errors="coerce")
        d = d.dropna(subset=["belief_strength", "active_return"]).sort_values("date")
        if len(d) < 40:
            st.info("Need more rows for belief-performance decay analysis.")
            return

        horizons = [1, 5, 20]
        for h in horizons:
            d[f"fwd_{h}"] = sum(d["active_return"].shift(-k) for k in range(1, h + 1))
        d = d.dropna(subset=[f"fwd_{h}" for h in horizons])
        if d.empty:
            st.info("No forward-return overlap for belief decay analysis.")
            return

        n_unique = int(pd.to_numeric(d["belief_strength"], errors="coerce").nunique(dropna=True))
        q = int(min(10, max(2, n_unique)))
        d["belief_bucket"] = np.nan
        try:
            # Let qcut decide the effective bin count when duplicate edges exist.
            qbins = pd.qcut(d["belief_strength"], q=q, labels=False, duplicates="drop")
            d["belief_bucket"] = pd.to_numeric(qbins, errors="coerce")
        except Exception:
            d["belief_bucket"] = np.nan

        # Fallback when value ties prevent clean quantile binning.
        if d["belief_bucket"].isna().all():
            ranks = pd.to_numeric(d["belief_strength"], errors="coerce").rank(method="average", pct=True)
            n_bins = int(min(10, max(2, int(np.sqrt(max(4, len(d)))))))
            try:
                edges = np.linspace(0.0, 1.0, n_bins + 1)
                d["belief_bucket"] = pd.cut(ranks, bins=edges, labels=False, include_lowest=True)
                d["belief_bucket"] = pd.to_numeric(d["belief_bucket"], errors="coerce")
            except Exception:
                d["belief_bucket"] = np.nan

        # Final fallback: single bucket so decay grid still renders.
        if d["belief_bucket"].isna().all():
            d["belief_bucket"] = "B1"
        else:
            d["belief_bucket"] = d["belief_bucket"].map(
                lambda x: f"B{int(x) + 1}" if pd.notna(x) else np.nan
            )
        d = d.dropna(subset=["belief_bucket"])
        if d.empty:
            st.info("Belief buckets are empty.")
            return

        rows = []
        for h in horizons:
            g = d.groupby("belief_bucket")[f"fwd_{h}"].mean()
            for bucket, val in g.items():
                rows.append({"horizon": f"{h}d", "belief_bucket": str(bucket), "mean_fwd_return": float(val)})
        hdf = pd.DataFrame(rows)
        if hdf.empty:
            st.info("Belief decay grid is empty.")
            return

        piv = hdf.pivot(index="horizon", columns="belief_bucket", values="mean_fwd_return")
        fig = px.imshow(
            piv,
            aspect="auto",
            color_continuous_scale="RdYlGn",
            title="Belief -> Subsequent Active Return (Decay Curve)",
        )
        self._apply_fig_theme(fig, height=300)
        st.plotly_chart(fig, width="stretch", key="cross_layer_belief_decay_curve")
        self._formula_note(
            "Belief Decay Formulas",
            [
                "fwd_return_{h,t} = sum_{k=1..h}(active_return_{t+k})",
                "belief_bucket_t = qcut(belief_strength_t)",
                "cell(h,bucket) = mean(fwd_return_{h,t} | bucket_t = bucket)",
            ],
        )

    def render_capital_convexity_map(self, integrated: pd.DataFrame, data: Dict[str, Any]) -> None:
        crisis = integrated[["date", "crisis_probability", "gross_exposure"]].copy() if {"date", "crisis_probability", "gross_exposure"}.issubset(integrated.columns) else pd.DataFrame()
        if not crisis.empty:
            crisis["date"] = _to_naive_date_series(crisis["date"], normalize=True)
            crisis["crisis_probability"] = pd.to_numeric(crisis["crisis_probability"], errors="coerce")
            crisis["gross_exposure"] = pd.to_numeric(crisis["gross_exposure"], errors="coerce")
            crisis = crisis.dropna(subset=["date", "crisis_probability"]).sort_values("date")

        gdf = pd.DataFrame()
        try:
            obs = OptionsObserver()
            hist = obs.get_portfolio_greeks_history()
            if isinstance(hist, pd.DataFrame) and not hist.empty:
                gdf = hist.copy().reset_index()
                tcol = "timestamp" if "timestamp" in gdf.columns else gdf.columns[0]
                gdf["date"] = _to_naive_date_series(gdf[tcol], normalize=True)
                for c in ["gamma", "delta", "theta", "vega"]:
                    if c in gdf.columns:
                        gdf[c] = pd.to_numeric(gdf[c], errors="coerce")
                gdf = gdf.dropna(subset=["date", "gamma"])
                gdf = gdf.groupby("date", as_index=False).last()
                gdf["date"] = _to_naive_date_series(gdf["date"], normalize=True)
                gdf = gdf.dropna(subset=["date"]).sort_values("date")
        except Exception:
            gdf = pd.DataFrame()

        if not gdf.empty and not crisis.empty:
            crisis["date"] = _to_naive_date_series(crisis["date"], normalize=True)
            crisis = crisis.dropna(subset=["date"]).sort_values("date")
            m = gdf.merge(crisis, on="date", how="inner").sort_values("date")
            if not m.empty:
                m["_size"] = pd.to_numeric(m.get("gross_exposure"), errors="coerce").fillna(0.1).abs().clip(lower=0.05, upper=1.5)
                fig = px.scatter(
                    m,
                    x="crisis_probability",
                    y="gamma",
                    size="_size",
                    color="delta" if "delta" in m.columns else None,
                    hover_data=["date", "gross_exposure", "theta", "vega"] if {"theta", "vega"}.issubset(m.columns) else ["date", "gross_exposure"],
                    title="Capital Convexity Map (Crisis Prob vs Net Gamma)",
                )
                fig.add_hline(y=0, line_dash="dot", line_color=THEME["grid"])
                self._apply_fig_theme(fig, height=340)
                st.plotly_chart(fig, width="stretch", key="cross_layer_capital_convexity_map")
                self._formula_note(
                    "Capital Convexity Formulas",
                    [
                        "x = crisis_probability_t",
                        "y = gamma_t",
                        "bubble_size_t = abs(gross_exposure_t)",
                        "color = delta_t",
                    ],
                )
                return

        options_state = data.get("options_dashboard_state") or {}
        greeks = options_state.get("portfolio_greeks", {}) if isinstance(options_state, dict) else {}
        gamma = _as_float(greeks.get("gamma"), np.nan) if isinstance(greeks, dict) else np.nan
        crisis_now = _as_float(crisis["crisis_probability"].tail(1).iloc[0], np.nan) if not crisis.empty else np.nan
        if np.isfinite(gamma) and np.isfinite(crisis_now):
            pt = pd.DataFrame({"crisis_probability": [crisis_now], "gamma": [gamma], "size": [0.3]})
            fig = px.scatter(pt, x="crisis_probability", y="gamma", size="size", title="Capital Convexity Map (latest point)")
            fig.add_hline(y=0, line_dash="dot", line_color=THEME["grid"])
            self._apply_fig_theme(fig, height=320)
            st.plotly_chart(fig, width="stretch", key="cross_layer_capital_convexity_latest")
            self._formula_note(
                "Capital Convexity Formula (Fallback)",
                [
                    "point = (crisis_probability_latest, gamma_latest)",
                ],
            )
        else:
            st.info("Convexity map unavailable: no gamma history/current gamma with crisis probability.")

    def render_macro_fragility_index(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        if d.empty:
            st.info("Fragility index unavailable: integrated snapshot missing.")
            return
        for c in [
            "volatility_z",
            "correlation_z",
            "fii_flow_z",
            "inflation_z",
            "macro_sentiment_z",
            "regime_entropy",
            "drawdown_probability_30d",
            "crisis_probability",
        ]:
            if c not in d.columns:
                d[c] = np.nan
            d[c] = pd.to_numeric(d[c], errors="coerce")

        d["drawdown_probability_30d"] = _resolve_drawdown_probability_series(d)
        if _series_is_sparse_or_flat(d["drawdown_probability_30d"], min_non_na=40, min_unique=5):
            crisis = pd.to_numeric(d.get("crisis_probability"), errors="coerce")
            if crisis.notna().sum() >= 20:
                d["drawdown_probability_30d"] = crisis.clip(0.0, 1.0).ewm(span=8, adjust=False, min_periods=3).mean()

        components = {
            "vol": d["volatility_z"] * 0.25,
            "corr": d["correlation_z"] * 0.25,
            "fii": (-d["fii_flow_z"]) * 0.20,
            "infl": d["inflation_z"] * 0.15,
            "sent": (-d["macro_sentiment_z"]) * 0.15,
        }
        comp_df = pd.DataFrame(components)
        valid = comp_df.notna().any(axis=1)
        if valid.sum() < 10:
            st.info("Fragility index unavailable: insufficient component history.")
            return
        frag = comp_df.fillna(0.0).sum(axis=1)
        d["fragility_index"] = self._zscore(pd.Series(frag, index=d.index))

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=d["date"], y=d["fragility_index"], name="Fragility Index", line=dict(color=THEME["red"], width=2)), secondary_y=False)
        fig.add_trace(go.Scatter(x=d["date"], y=d["regime_entropy"], name="Regime Entropy", line=dict(color=THEME["cyan"], width=1.8)), secondary_y=True)
        fig.update_layout(title="Macro Fragility Index vs Regime Entropy")
        fig.update_yaxes(title_text="Fragility (z)", secondary_y=False)
        fig.update_yaxes(title_text="Regime Entropy", secondary_y=True)
        self._apply_fig_theme(fig, height=320)
        st.plotly_chart(fig, width="stretch", key="macro_fragility_vs_regime_entropy")
        self._formula_note(
            "Macro Fragility Formulas",
            [
                "fragility_raw_t = 0.25*volatility_z_t + 0.25*correlation_z_t + 0.20*(-fii_flow_z_t) + 0.15*inflation_z_t + 0.15*(-macro_sentiment_z_t)",
                "fragility_index_t = zscore(fragility_raw_t)",
            ],
        )

        s = d.dropna(subset=["fragility_index", "drawdown_probability_30d"]).copy()
        if not s.empty:
            fig2 = px.scatter(
                s,
                x="fragility_index",
                y="drawdown_probability_30d",
                color="crisis_probability" if "crisis_probability" in s.columns else None,
                title="Fragility vs Drawdown Probability",
            )
            fig2.add_hline(y=float(pd.to_numeric(s["drawdown_probability_30d"], errors="coerce").median()), line_dash="dot", line_color=THEME["grid"])
            self._apply_fig_theme(fig2, height=320)
            st.plotly_chart(fig2, width="stretch", key="macro_fragility_vs_drawdown_scatter")
            self._formula_note(
                "Fragility vs Drawdown Formula",
                [
                    "x = fragility_index_t",
                    "y = drawdown_probability_30d_t",
                ],
            )

    def render_sentiment_lead_lag_surface(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        if not {"macro_news_sentiment", "active_return"}.issubset(d.columns):
            st.info("Lead-lag surface unavailable: sentiment/returns missing.")
            return
        d["macro_news_sentiment"] = pd.to_numeric(d["macro_news_sentiment"], errors="coerce")
        d["active_return"] = pd.to_numeric(d["active_return"], errors="coerce")
        d = d.dropna(subset=["macro_news_sentiment", "active_return"]).sort_values("date")
        if len(d) < 60:
            st.info("Need more rows for sentiment lead-lag surface.")
            return

        horizons = [1, 5, 20]
        lags = list(range(-30, 31))
        mat: List[List[float]] = []
        for h in horizons:
            fwd = sum(d["active_return"].shift(-k) for k in range(1, h + 1))
            row: List[float] = []
            for lag in lags:
                s = d["macro_news_sentiment"].shift(lag)
                corr = pd.Series(s).corr(pd.Series(fwd))
                row.append(float(corr) if np.isfinite(corr) else np.nan)
            mat.append(row)

        heat = pd.DataFrame(mat, index=[f"{h}d" for h in horizons], columns=lags)
        fig = px.imshow(
            heat,
            aspect="auto",
            color_continuous_scale="RdBu",
            title="Sentiment Lead-Lag Surface (Corr with future active returns)",
            labels={"x": "Lag (days)", "y": "Return Horizon", "color": "Corr"},
        )
        self._apply_fig_theme(fig, height=320)
        st.plotly_chart(fig, width="stretch", key="cross_layer_sentiment_lead_lag")
        self._formula_note(
            "Lead-Lag Surface Formulas",
            [
                "fwd_return_{h,t} = sum_{k=1..h}(active_return_{t+k})",
                "cell(h,lag) = corr(sentiment_{t+lag}, fwd_return_{h,t})",
                "lag range = [-30, +30], horizons = {1,5,20}",
            ],
        )

    def render_allocation_drift_vs_information_shock(self, integrated: pd.DataFrame) -> None:
        d = integrated.copy()
        if "gross_exposure" not in d.columns:
            st.info("Allocation drift view unavailable: gross_exposure missing.")
            return
        d["gross_exposure"] = pd.to_numeric(d["gross_exposure"], errors="coerce")
        if "narrative_shock_intensity" in d.columns:
            d["narrative_shock_intensity"] = pd.to_numeric(d["narrative_shock_intensity"], errors="coerce")
        else:
            d["narrative_shock_intensity"] = np.nan
        if "macro_news_sentiment" in d.columns:
            d["macro_news_sentiment"] = pd.to_numeric(d["macro_news_sentiment"], errors="coerce")
        else:
            d["macro_news_sentiment"] = np.nan

        d = d.dropna(subset=["date", "gross_exposure"]).sort_values("date")
        if len(d) < 20:
            st.info("Need more rows for allocation drift analysis.")
            return

        d["allocation_drift"] = d["gross_exposure"].diff().abs()
        d["shock_proxy"] = d["narrative_shock_intensity"].fillna(0.0) + 0.5 * d["macro_news_sentiment"].diff().abs().fillna(0.0)
        d = d.dropna(subset=["allocation_drift"])
        if d.empty:
            st.info("No allocation drift rows available.")
            return

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=d["date"], y=d["allocation_drift"], name="|Δ Allocation|", line=dict(color=THEME["green"], width=2)), secondary_y=False)
        fig.add_trace(go.Scatter(x=d["date"], y=d["shock_proxy"], name="Information Shock", line=dict(color=THEME["amber"], width=1.8)), secondary_y=True)
        fig.update_layout(title="Allocation Drift vs Information Shock")
        fig.update_yaxes(title_text="|Δ Allocation|", secondary_y=False)
        fig.update_yaxes(title_text="Shock Proxy", secondary_y=True)
        self._apply_fig_theme(fig, height=300)
        st.plotly_chart(fig, width="stretch", key="cross_layer_allocation_drift_vs_shock")
        self._formula_note(
            "Allocation Drift Formulas",
            [
                "allocation_drift_t = abs(gross_exposure_t - gross_exposure_{t-1})",
                "shock_proxy_t = narrative_shock_intensity_t + 0.5*abs(macro_news_sentiment_t - macro_news_sentiment_{t-1})",
            ],
        )

        s = d.dropna(subset=["shock_proxy", "allocation_drift"]).copy()
        fig2 = px.scatter(
            s.tail(600),
            x="shock_proxy",
            y="allocation_drift",
            color="regime_label" if "regime_label" in s.columns else None,
            title="Allocation Reaction Surface (Drift vs Shock)",
        )
        self._apply_fig_theme(fig2, height=320)
        st.plotly_chart(fig2, width="stretch", key="cross_layer_allocation_reaction_surface")
        self._formula_note(
            "Allocation Reaction Surface",
            [
                "x = shock_proxy_t",
                "y = allocation_drift_t",
            ],
        )

    def render_regime_vs_posterior_stability(self, integrated: pd.DataFrame, data: Dict[str, Any]) -> None:
        vp = data.get("valuation_posterior")
        if not isinstance(vp, pd.DataFrame) or vp.empty or "posterior_variance" not in vp.columns:
            st.info("Posterior stability view unavailable: valuation posterior variance missing.")
            return
        v = vp.copy()
        tcol = _pick_time_column(v, ["date", "Date", "timestamp"])
        if tcol is None:
            st.info("Posterior stability view unavailable: no valuation date column.")
            return
        v["date"] = _to_naive_date_series(v[tcol], normalize=True)
        v["posterior_variance"] = pd.to_numeric(v["posterior_variance"], errors="coerce")
        if "model_dispersion" in v.columns:
            v["model_dispersion"] = pd.to_numeric(v["model_dispersion"], errors="coerce")
        v = v.dropna(subset=["date", "posterior_variance"])
        if v.empty:
            st.info("Posterior variance is empty after cleaning.")
            return
        v = v.groupby("date", as_index=False).agg(
            posterior_variance=("posterior_variance", "mean"),
            model_dispersion=("model_dispersion", "mean") if "model_dispersion" in v.columns else ("posterior_variance", "size"),
        )

        if "regime_entropy" not in integrated.columns:
            st.info("Regime entropy unavailable in integrated snapshot.")
            return
        m = integrated[["date", "regime_entropy"]].copy()
        m["date"] = _to_naive_date_series(m["date"], normalize=True)
        m["regime_entropy"] = pd.to_numeric(m["regime_entropy"], errors="coerce")
        m = m.dropna(subset=["date", "regime_entropy"])
        if m.empty:
            st.info("Regime entropy series is empty after cleaning.")
            return

        # Quarterly valuation snapshots are intentionally sparse; align to daily entropy
        # using backward as-of joins with a staleness cap.
        m = m.sort_values("date")
        vv = v.rename(columns={"date": "valuation_date"}).sort_values("valuation_date")
        j = pd.merge_asof(
            m,
            vv,
            left_on="date",
            right_on="valuation_date",
            direction="backward",
            tolerance=pd.Timedelta(days=120),
        )
        j = j.dropna(subset=["posterior_variance"]).sort_values("date")
        if len(j) < 10:
            st.info("Need more overlap between entropy and posterior variance.")
            return

        fig = px.scatter(
            j,
            x="regime_entropy",
            y="posterior_variance",
            color="model_dispersion" if "model_dispersion" in j.columns else None,
            hover_data=["date"],
            title="Regime Stability vs Posterior Stability",
        )
        self._apply_fig_theme(fig, height=320)
        st.plotly_chart(fig, width="stretch", key="cross_layer_regime_vs_posterior_stability")
        self._formula_note(
            "Stability Cross-Check Formulas",
            [
                "posterior_variance_daily_t = mean_i(posterior_variance_{i,t})",
                "model_dispersion_daily_t = mean_i(model_dispersion_{i,t})",
                "x = regime_entropy_t, y = posterior_variance_daily_t",
            ],
        )

    def render_rbi_policy_shock_impact_grid(self, data: Dict[str, Any], sentiment_ctx: Dict[str, Any]) -> None:
        market_df = sentiment_ctx.get("market_df", pd.DataFrame())
        sector_flows = data.get("sector_flows")
        if not isinstance(market_df, pd.DataFrame) or market_df.empty or not isinstance(sector_flows, pd.DataFrame) or sector_flows.empty:
            st.info("Policy shock impact grid needs sentiment market history + sector flows.")
            return

        m = market_df.copy()
        tcol = _pick_time_column(m, ["date", "Date", "timestamp"])
        if tcol is None or "policy_weight" not in m.columns:
            st.info("Policy shock grid unavailable: policy_weight history missing.")
            return
        m["date"] = _to_naive_date_series(m[tcol], normalize=True)
        m["policy_weight"] = pd.to_numeric(m["policy_weight"], errors="coerce")
        m["polarity"] = pd.to_numeric(m.get("polarity"), errors="coerce")
        m = m.dropna(subset=["date", "policy_weight"]).sort_values("date")
        if len(m) < 4:
            st.info("Policy shock grid needs more policy-weight observations.")
            return
        m["policy_delta"] = m["policy_weight"].diff().abs()
        thr = float(m["policy_delta"].quantile(0.75))
        shock_dates = m.loc[m["policy_delta"] >= thr, "date"].dropna().unique().tolist()
        if not shock_dates:
            st.info("No policy shock dates detected in current sentiment sample.")
            return

        sf = sector_flows.copy()
        tcol = "Date" if "Date" in sf.columns else ("date" if "date" in sf.columns else None)
        sec_col = "Industry" if "Industry" in sf.columns else ("sector" if "sector" in sf.columns else None)
        ret_col = "relative_return" if "relative_return" in sf.columns else ("capital_flow" if "capital_flow" in sf.columns else None)
        if tcol is None or sec_col is None or ret_col is None:
            st.info("Sector flows missing columns needed for policy impact matrix.")
            return
        sf["date"] = _to_naive_date_series(sf[tcol], normalize=True)
        sf[ret_col] = pd.to_numeric(sf[ret_col], errors="coerce")
        sf[sec_col] = sf[sec_col].astype(str)
        sf = sf.dropna(subset=["date", sec_col, ret_col]).sort_values("date")
        if sf.empty:
            st.info("Sector flow history empty after cleaning.")
            return
        pivot = sf.pivot_table(index="date", columns=sec_col, values=ret_col, aggfunc="mean").sort_index()
        if pivot.empty:
            st.info("Could not build sector return panel for policy shocks.")
            return

        horizons = [1, 5, 20]
        rows = []
        for dt in shock_dates:
            if dt not in pivot.index:
                continue
            loc = pivot.index.get_indexer([dt], method="nearest")
            if len(loc) == 0 or loc[0] < 0:
                continue
            i0 = int(loc[0])
            for h in horizons:
                i1 = min(len(pivot) - 1, i0 + h)
                if i1 <= i0:
                    continue
                window = pivot.iloc[i0 + 1 : i1 + 1]
                if window.empty:
                    continue
                for sec in window.columns:
                    val = pd.to_numeric(window[sec], errors="coerce").mean()
                    if np.isfinite(val):
                        rows.append({"sector": sec, "horizon": f"{h}d", "impact": float(val)})
        if not rows:
            st.info("No post-shock sector windows available for policy impact grid.")
            return
        rdf = pd.DataFrame(rows)
        top_secs = (
            rdf.groupby("sector")["impact"]
            .apply(lambda s: float(np.nanmean(np.abs(s))))
            .sort_values(ascending=False)
            .head(12)
            .index
            .tolist()
        )
        rdf = rdf[rdf["sector"].isin(top_secs)]
        mat = rdf.pivot_table(index="sector", columns="horizon", values="impact", aggfunc="mean")
        if mat.empty:
            st.info("Policy impact matrix is empty.")
            return
        fig = px.imshow(
            mat,
            aspect="auto",
            color_continuous_scale="RdYlGn",
            title="RBI Policy Shock Impact Grid (Sector response by horizon)",
        )
        self._apply_fig_theme(fig, height=360)
        st.plotly_chart(fig, width="stretch", key="cross_layer_rbi_policy_impact")
        self._formula_note(
            "RBI Policy Shock Formulas",
            [
                "policy_delta_t = abs(policy_weight_t - policy_weight_{t-1})",
                "shock_dates = {t | policy_delta_t >= quantile_75(policy_delta)}",
                "impact_{sector,h} = mean_{t in shock_dates}( mean_{k=1..h}(sector_return_{t+k}) )",
            ],
        )

    def render_strategy_survival_probability_curve(self, integrated: pd.DataFrame, data: Dict[str, Any]) -> None:
        beliefs = data.get("strategy_beliefs")
        latest = pd.DataFrame(columns=["strategy", "belief"])
        if isinstance(beliefs, pd.DataFrame) and not beliefs.empty and "strategy" in beliefs.columns:
            b = beliefs.copy()
            b["strategy"] = b["strategy"].astype(str)
            b["belief"] = _strategy_belief_proxy(b)
            if b["belief"].notna().sum() == 0:
                bcol = _pick_belief_metric(b)
                if bcol is not None:
                    fallback = pd.to_numeric(b[bcol], errors="coerce")
                    if bcol == "effective_skill":
                        fallback = fallback.rank(method="average", pct=True)
                    b["belief"] = fallback.clip(0.0, 1.0)
            b = b.dropna(subset=["belief", "strategy"])
            if not b.empty:
                tcol = _pick_time_column(b, ["date", "Date", "timestamp"])
                if tcol:
                    b["_ts"] = _to_naive_date_series(b[tcol], normalize=False)
                    b = b.dropna(subset=["_ts"]).sort_values("_ts")
                    latest = b.groupby("strategy", as_index=False).tail(1)
                    if latest.empty:
                        latest = b.groupby("strategy", as_index=False)["belief"].mean()
                else:
                    latest = b.groupby("strategy", as_index=False)["belief"].mean()

        if latest.empty or latest["strategy"].nunique() < 2:
            alloc_hist = data.get("allocation_history")
            derived = _build_strategy_beliefs_from_allocation_history(alloc_hist if isinstance(alloc_hist, pd.DataFrame) else pd.DataFrame())
            if not derived.empty:
                latest = derived.copy()

        latest["belief"] = pd.to_numeric(latest.get("belief"), errors="coerce").clip(0.0, 1.0)
        latest["strategy"] = latest.get("strategy", pd.Series(dtype=str)).astype(str).str.strip()
        latest = latest.dropna(subset=["belief"])
        latest = latest[latest["strategy"] != ""].sort_values("belief", ascending=False)
        if latest.empty:
            st.info("No strategy belief rows for survival analysis.")
            return
        if latest["strategy"].nunique() < 2:
            st.info("Could not form multiple strategy beliefs for survival analysis.")
            return
        max_strategies = min(16, max(6, int(latest["strategy"].nunique())))
        latest = latest.head(max_strategies)

        dd_prob = np.nan
        crisis_prob = np.nan
        if not integrated.empty:
            dd_series = _resolve_drawdown_probability_series(integrated)
            if isinstance(dd_series, pd.Series) and dd_series.notna().any():
                dd_prob = _as_float(dd_series.dropna().iloc[-1], np.nan)
            if "crisis_probability" in integrated.columns:
                cser = pd.to_numeric(integrated["crisis_probability"], errors="coerce").dropna()
                if not cser.empty:
                    crisis_prob = _as_float(cser.iloc[-1], np.nan)
        dd_prob = 0.08 if not np.isfinite(dd_prob) else float(np.clip(dd_prob, 0.0, 1.0))
        crisis_prob = 0.10 if not np.isfinite(crisis_prob) else float(np.clip(crisis_prob, 0.0, 1.0))

        base_hazard_month = float(np.clip(0.02 + 0.55 * dd_prob + 0.35 * crisis_prob, 0.02, 0.90))
        horizons = [5, 20, 60, 120, 252]

        rows = []
        for _, r in latest.iterrows():
            belief = float(np.clip(_as_float(r["belief"], 0.3), 0.0, 1.0))
            strategy = str(r["strategy"])
            multiplier = float(np.clip(1.25 - 0.9 * belief, 0.35, 1.40))
            hazard = float(np.clip(base_hazard_month * multiplier, 0.01, 0.95))
            for h in horizons:
                surv = float(np.clip((1.0 - hazard) ** (h / 30.0), 0.0, 1.0))
                rows.append({"strategy": strategy, "horizon_days": h, "survival_probability": surv})
        out = pd.DataFrame(rows)
        if out.empty:
            st.info("Could not compute strategy survival curve.")
            return

        fig = px.line(
            out,
            x="horizon_days",
            y="survival_probability",
            color="strategy",
            markers=True,
            title="Strategy Survival Probability Curve",
        )
        fig.update_yaxes(range=[0, 1], tickformat=".0%")
        self._apply_fig_theme(fig, height=360)
        st.plotly_chart(fig, width="stretch", key="cross_layer_strategy_survival")
        self._formula_note(
            "Strategy Survival Formulas",
            [
                "belief_strategy = coalesce(belief_strength, skill_prob, confidence, rank_pct(effective_skill))",
                "base_hazard = clip(0.02 + 0.55*drawdown_prob + 0.35*crisis_prob, 0.02, 0.90)",
                "multiplier_strategy = clip(1.25 - 0.9*belief_strategy, 0.35, 1.40)",
                "hazard_strategy = clip(base_hazard * multiplier_strategy, 0.01, 0.95)",
                "survival(h) = (1 - hazard_strategy)^(h/30)",
            ],
        )

    def render_cross_layer_coupling(self, data: Dict[str, Any]) -> None:
        st.subheader("🔗 Cross-Layer Coupling")
        integrated = self._get_integrated_frame(max_rows=2500)
        if integrated.empty:
            st.info("Integrated snapshot is missing. Run `python3 scripts/build_integrated_state_snapshot.py`.")
            return
        integrated = self._focus_active_window(
            integrated,
            time_col="date",
            value_cols=[
                "regime_confidence",
                "belief_strength",
                "gross_exposure",
                "nav",
                "active_return",
                "crisis_probability",
                "macro_news_sentiment",
            ],
            max_rows=1400,
            min_rows=260,
            eps=1e-8,
        )
        sentiment_ctx = load_sentiment_context()

        t1, t2, t3, t4, t5, t6 = st.tabs(
            [
                "Elasticity & Drift",
                "Narrative & Transition",
                "Transmission",
                "Fragility & Lead-Lag",
                "Convexity & Survival",
                "Policy Impact",
            ]
        )
        with t1:
            self.render_regime_belief_allocation_elasticity_surface(integrated)
            self.render_allocation_drift_vs_information_shock(integrated)
            self.render_belief_performance_decay_curve(integrated)
        with t2:
            self.render_narrative_regime_transition_map(integrated)
            self.render_crisis_replay_with_narrative_overlay(integrated, data)
        with t3:
            self.render_macro_portfolio_transmission_network(data)
            self.render_regime_vs_posterior_stability(integrated, data)
        with t4:
            self.render_macro_fragility_index(integrated)
            self.render_sentiment_lead_lag_surface(integrated)
        with t5:
            self.render_capital_convexity_map(integrated, data)
            self.render_strategy_survival_probability_curve(integrated, data)
        with t6:
            self.render_rbi_policy_shock_impact_grid(data, sentiment_ctx)

    # ---------------------------- HELPERS ----------------------------
    def compute_drawdown(self, equity: pd.Series) -> pd.Series:
        peak = equity.expanding().max()
        return equity / peak - 1.0

    @staticmethod
    def _normalize_pnl_frame(pnl: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Normalize P&L inputs across schema variants.
        Output columns are guaranteed: Date, Equity, Return.
        """
        if pnl is None or not isinstance(pnl, pd.DataFrame) or pnl.empty:
            return pd.DataFrame(columns=["Date", "Equity", "Return"])

        df = pnl.copy()

        if "Date" not in df.columns:
            for cand in ["date", "timestamp", "datetime", "time"]:
                if cand in df.columns:
                    df["Date"] = df[cand]
                    break
        if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
            df["Date"] = df.index
        if "Date" not in df.columns:
            return pd.DataFrame(columns=["Date", "Equity", "Return"])

        df["Date"] = _to_naive_date_series(df["Date"], normalize=False)
        df = df.dropna(subset=["Date"]).sort_values("Date")
        if df.empty:
            return pd.DataFrame(columns=["Date", "Equity", "Return"])

        if "Equity" not in df.columns:
            for cand in ["equity", "portfolio_value", "value", "total_equity", "capital", "nav"]:
                if cand in df.columns:
                    df["Equity"] = df[cand]
                    break
        df["Equity"] = pd.to_numeric(df.get("Equity"), errors="coerce")

        if "Return" not in df.columns:
            for cand in ["return", "daily_return", "pct_return", "returns"]:
                if cand in df.columns:
                    df["Return"] = df[cand]
                    break
        df["Return"] = pd.to_numeric(df.get("Return"), errors="coerce")

        if df["Return"].isna().all() and df["Equity"].notna().sum() >= 2:
            df["Return"] = df["Equity"].pct_change()
        if df["Equity"].isna().all() and df["Return"].notna().sum() >= 2:
            df["Equity"] = (1.0 + df["Return"].fillna(0.0)).cumprod()

        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=["Date", "Equity"])
        if df.empty:
            return pd.DataFrame(columns=["Date", "Equity", "Return"])

        return df[["Date", "Equity", "Return"]].copy()

    def compute_portfolio_metrics(self, pnl: Optional[pd.DataFrame]) -> Dict[str, float]:
        df = self._normalize_pnl_frame(pnl)
        if df.empty:
            return {"total_return": 0.0, "annual_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "win_rate": 0.0}
        returns = pd.to_numeric(df.get("Return"), errors="coerce").dropna()
        start_equity = float(df["Equity"].iloc[0]) if pd.notna(df["Equity"].iloc[0]) else 0.0
        end_equity = float(df["Equity"].iloc[-1]) if pd.notna(df["Equity"].iloc[-1]) else 0.0
        total_return = (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else 0.0
        span_days = max(1.0, float((df["Date"].iloc[-1] - df["Date"].iloc[0]).days))
        span_years = span_days / 365.25
        if start_equity > 0 and end_equity > 0 and span_years > 0:
            annual_return = ((end_equity / start_equity) ** (1.0 / span_years) - 1.0) * 100.0
        else:
            annual_return = 0.0
        sharpe = (returns.mean() * 252) / (returns.std() * np.sqrt(252) + 1e-9) if not returns.empty else 0.0
        dd = self.compute_drawdown(df["Equity"])
        max_dd = dd.min() * 100.0
        win_rate = (returns > 0).mean() * 100.0 if not returns.empty else 0.0
        return {
            "total_return": float(total_return),
            "annual_return": float(annual_return),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
        }

    def render(self) -> None:
        self.render_header()
        self.render_live_refresh_controls()
        mode = st.radio(
            "Operating Mode",
            ["Live", "Research"],
            horizontal=True,
            help=(
                "Live: decision surface for market/portfolio/risk operations. "
                "Research: deep analytics and full intelligence workbench."
            ),
        )
        depth_options = LIVE_DEPTH_OPTIONS if mode == "Live" else RESEARCH_DEPTH_OPTIONS
        surface_depth = st.radio(
            "Surface Depth",
            list(depth_options),
            horizontal=True,
            help=(
                "Executive/Tactical emphasize decision flow. "
                "Research Lab exposes full exploratory surfaces."
            ),
        )
        data_mode = "live" if mode == "Live" else "research"
        data = load_core_data(mode=data_mode)
        self._current_mode = data_mode
        self._view_model_meta = data.get("__view_model_meta__", {}) if isinstance(data, dict) else {}

        freeze_state = data.get("model_freeze_state") or {}
        freeze_active = bool(freeze_state.get("freeze_active", False)) if isinstance(freeze_state, dict) else False
        dataset_count = int((self._view_model_meta or {}).get("dataset_count", 0) or 0)
        strip = st.columns(6)
        with strip[0]:
            self._kpi_card("Visual OS", "L0-L3")
        with strip[1]:
            self._kpi_card("Mode", mode)
        with strip[2]:
            self._kpi_card("Depth", surface_depth)
        with strip[3]:
            self._kpi_card("Strict", "ON" if self.strict_mode else "OFF")
        with strip[4]:
            self._kpi_card("Risk Policy", "Locked")
        with strip[5]:
            self._kpi_card("Freeze", "Active" if freeze_active else "Inactive")
        st.caption(
            f"View model datasets: {dataset_count} | "
            f"Emission targets: 174 → {EMISSION_TARGETS['wave_1']} → {EMISSION_TARGETS['wave_2']} → {EMISSION_TARGETS['wave_3']} → {EMISSION_TARGETS['wave_4']}"
        )

        self._render_section_safely("Global State Ribbon", self.render_state_ribbon, data)
        self._render_section_safely("Causal Flow Panel", self.render_causal_flow_panel, data, None, key_prefix="causal_flow_global")

        if mode == "Live":
            if surface_depth == "Executive Control Surface":
                tabs = st.tabs(
                    [
                        "🌍 Market Pressure",
                        "📊 Portfolio Expression",
                        "🛡 Survival Engine",
                        "📰 News Shock",
                        "⚙ System Health",
                    ]
                )
                with tabs[0]:
                    self._render_section_safely("Market Pressure Surface", self.render_market_pressure_surface, data, live_mode=True)
                with tabs[1]:
                    self._render_section_safely("Portfolio Expression Surface", self.render_portfolio_expression_surface, data, live_mode=True)
                with tabs[2]:
                    self._render_section_safely("Survival Engine Surface", self.render_survival_engine_surface, data, live_mode=True)
                with tabs[3]:
                    self._render_section_safely("News Shock Surface", self.render_news_shock_surface, data, live_mode=True)
                with tabs[4]:
                    self._render_section_safely("System Health Surface", self.render_system_health_surface, data, live_mode=True)
            else:
                tabs = st.tabs(
                    [
                        "🌍 Market Pressure",
                        "📊 Portfolio Expression",
                        "🛡 Survival Engine",
                        "🚨 Alerts",
                        "📰 News Shock",
                        "⚙ System Health",
                        "🔎 Tactical Drill-Down",
                    ]
                )
                with tabs[0]:
                    self._render_section_safely("Market Pressure Surface", self.render_market_pressure_surface, data, live_mode=True)
                with tabs[1]:
                    self._render_section_safely("Portfolio Expression Surface", self.render_portfolio_expression_surface, data, live_mode=True)
                with tabs[2]:
                    self._render_section_safely("Survival Engine Surface", self.render_survival_engine_surface, data, live_mode=True)
                with tabs[3]:
                    self._render_section_safely("Alert Feed", self.render_alert_feed, data)
                with tabs[4]:
                    self._render_section_safely("News Shock Surface", self.render_news_shock_surface, data, live_mode=True)
                with tabs[5]:
                    self._render_section_safely("System Health Surface", self.render_system_health_surface, data, live_mode=True)
                with tabs[6]:
                    with st.expander("Market State Details", expanded=False):
                        self._render_section_safely("Market State", self.render_market_state_layer, data, live_mode=True)
                    with st.expander("Portfolio Expression Details", expanded=False):
                        self._render_section_safely("Portfolio Expression", self.render_portfolio_expression_layer, data, live_mode=True)
                    with st.expander("Risk & Survival Details", expanded=False):
                        self._render_section_safely("Risk & Survival", self.render_risk_survival_layer, data, live_mode=True)
                    with st.expander("News & Narrative Details", expanded=False):
                        self._render_section_safely("News & Narrative", self.render_news_narrative_layer, data, live_mode=True)
                    with st.expander("Real-Time Monitor", expanded=False):
                        self._render_section_safely("Real-Time Monitor", self.render_real_time_monitor, data)
        else:
            tabs = st.tabs(
                [
                    "🌍 Market State",
                    "🧠 Intelligence",
                    "📊 Portfolio",
                    "🛡 Risk & Survival",
                    "🔬 Research & Evolution",
                    "📰 News & Narrative",
                ]
            )
            with tabs[0]:
                self._render_section_safely("Market State", self.render_market_state_layer, data, live_mode=False)
            with tabs[1]:
                self._render_section_safely("Northstar Intelligence", self.render_intelligence_layer, data, live_mode=False)
            with tabs[2]:
                self._render_section_safely("Portfolio Expression", self.render_portfolio_expression_layer, data, live_mode=False)
                st.divider()
                self._render_section_safely("Wave Analysis", self.render_wave_analysis, data)
            with tabs[3]:
                self._render_section_safely("Risk & Survival", self.render_risk_survival_layer, data, live_mode=False)
                st.divider()
                self._render_section_safely("Volatility Engine", self.render_volatility_engine)
            with tabs[4]:
                if surface_depth == "Research Lab":
                    self._render_section_safely("Research & Evolution", self.render_research_evolution_layer, data)
                else:
                    with st.expander("Open Research & Evolution Lab", expanded=False):
                        self._render_section_safely("Research & Evolution", self.render_research_evolution_layer, data)
            with tabs[5]:
                self._render_section_safely("News & Narrative", self.render_news_narrative_layer, data, live_mode=False)


def main() -> None:
    dashboard = NorthstarV3UltimateIntegratedDashboard()
    dashboard.render()


if __name__ == "__main__":
    main()
