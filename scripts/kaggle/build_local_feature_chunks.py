#!/usr/bin/env python3
"""Build a memory-bounded local feature dataset for Kaggle upload.

This script preserves the existing Northstar feature logic by delegating the
daily feature construction to ``DatasetManager`` and only changes the build
orchestration:

1. Build one date chunk at a time.
2. Add a warmup window so rolling features remain correct.
3. Add a forward buffer so horizon targets are not truncated at chunk edges.
4. Write weekly feature chunks plus an audit/manifest bundle.

The output is intended to be uploaded as a Kaggle dataset layer and merged on
Kaggle with ``scripts/kaggle/merge_chunked_feature_dataset.py``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import (  # noqa: E402
    _dataset_runtime_config,
    _effective_split_config,
    _maybe_rebuild_screener,
    _validate_raw_bundle_support_artifacts,
)
from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    attach_universe_annotations,
    build_market_cap_fields,
    infer_feature_unit_kind,
    build_plan_regime_labels,
    cast_feature_frame,
    cast_metadata_frame,
    generate_anchored_weekly_splits,
    json_ready,
    merge_regimes_into_panel,
    now_utc_iso,
    prepare_runtime_project,
    resolve_raw_bundle_dir,
    resample_daily_panel_to_weekly,
    select_feature_columns,
    working_directory,
    write_json,
)
from src.research.dataset_manager import DatasetManager  # noqa: E402


NON_SIGNAL_COLUMNS = {"date", "ticker"}
EXACT_PLAN_SYMBOLS = {
    "dxy": "DX-Y.NYB",
    "steel_hrc": "HRC=F",
    "coal": "MTF=F",
    "us_10y": "^TNX",
}
# A.3: do NOT pre-delete earnings_quality_ratio here. It was being dropped per
# chunk before the merge-time quality repair (repair_runtime_factor_families)
# could rebuild it, permanently removing one of the two originally-missing anchor
# factors from the chunked export. The merge step now repairs it from its proxy.
DEAD_EXPORT_COLUMNS: set[str] = set()
# E.8: only the BASE sparse columns are 0-filled (paired with an explicit
# _available flag). The derived _cs_z / _cs_rank columns are NOT 0-filled — a 0
# there would be indistinguishable from "genuinely at the cross-sectional
# average"; leaving them NaN (their natural value when the base is missing) keeps
# "no data" honest without needing the consumer to join the base availability flag.
SCHEMA_DEFAULT_FILL_VALUES = {
    "sector_dummy__NA_": 0.0,
    "pledge_pct": 0.0,
    "days_since_earnings": 0.0,
}
SPARSE_FEATURE_AVAILABILITY_FLAGS = {
    "pledge_pct": "pledge_pct_available",
    "rating_numeric": "rating_numeric_available",
    "days_since_earnings": "days_since_earnings_available",
}


class StepProgress:
    """Small stderr progress helper that keeps stdout machine-readable."""

    def __init__(self, title: str, total_steps: int, *, enabled: bool = True) -> None:
        self.title = str(title)
        self.total_steps = max(1, int(total_steps))
        self.enabled = bool(enabled)
        self.completed = 0
        self.started_at = time.monotonic()
        self.step_started_at = self.started_at
        self.current_label = ""
        self._stream = sys.stderr
        self._interactive = self.enabled and hasattr(self._stream, "isatty") and self._stream.isatty()
        self._stop_event = threading.Event()
        self._render_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._spinner = "|/-\\"

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        total = max(0, int(seconds))
        minutes, secs = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _progress_bar(self, spinner_idx: int = 0, *, done: bool = False) -> str:
        width = 28
        completed_ratio = min(1.0, max(0.0, self.completed / self.total_steps))
        filled = min(width, int(completed_ratio * width))
        bar = ["#"] * filled + ["-"] * (width - filled)
        if not done and self.completed < self.total_steps and width > 0:
            pulse_span = max(1, width // self.total_steps)
            pulse_offset = spinner_idx % pulse_span
            pulse_at = min(width - 1, filled + pulse_offset)
            bar[pulse_at] = self._spinner[spinner_idx % len(self._spinner)]
        return "".join(bar)

    def _render_line(self, *, done: bool = False, failed: bool = False) -> str:
        elapsed_total = self._fmt_elapsed(time.monotonic() - self.started_at)
        elapsed_step = self._fmt_elapsed(time.monotonic() - self.step_started_at)
        step_no = min(self.total_steps, self.completed + (0 if done or failed else 1))
        pct = (self.completed / self.total_steps) * 100.0 if self.total_steps else 100.0
        if done:
            pct = (self.completed / self.total_steps) * 100.0 if self.total_steps else 100.0
        spinner_idx = int((time.monotonic() - self.step_started_at) * 6.0)
        bar = self._progress_bar(spinner_idx, done=done or failed)
        status = "FAILED" if failed else ("DONE" if done else "RUN")
        label = self.current_label or "working"
        return (
            f"\r[{self.title}] [{bar}] "
            f"{step_no}/{self.total_steps} {pct:5.1f}% {status} {label} "
            f"| step {elapsed_step} | total {elapsed_total}"
        )

    def _animate(self) -> None:
        while not self._stop_event.wait(0.2):
            with self._lock:
                self._stream.write(self._render_line())
                self._stream.flush()

    def _start_step(self, label: str) -> None:
        if not self.enabled:
            return
        with self._lock:
            self.current_label = str(label)
            self.step_started_at = time.monotonic()
            self._stop_event.clear()
            if self._interactive:
                self._render_thread = threading.Thread(target=self._animate, daemon=True)
                self._render_thread.start()
            else:
                self._stream.write(f"[{self.title}] {self.completed + 1}/{self.total_steps} START {self.current_label}\n")
                self._stream.flush()

    def _finish_step(self, *, failed: bool = False) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._stop_event.set()
        if self._render_thread is not None:
            self._render_thread.join(timeout=1.0)
            self._render_thread = None
        if not failed:
            self.completed = min(self.total_steps, self.completed + 1)
        if self._interactive:
            with self._lock:
                self._stream.write(self._render_line(done=not failed, failed=failed) + "\n")
                self._stream.flush()
        elif failed:
            self._stream.write(f"[{self.title}] FAILED {self.current_label}\n")
            self._stream.flush()
        else:
            self._stream.write(f"[{self.title}] {self.completed}/{self.total_steps} DONE {self.current_label}\n")
            self._stream.flush()

    @contextmanager
    def step(self, label: str):
        self._start_step(label)
        try:
            yield
        except Exception:
            self._finish_step(failed=True)
            raise
        else:
            self._finish_step(failed=False)


@dataclass(frozen=True)
class DateChunk:
    chunk_id: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    warmup_start_date: pd.Timestamp
    build_end_date: pd.Timestamp

    @property
    def slug(self) -> str:
        return (
            f"chunk_{self.chunk_id:03d}_"
            f"{self.start_date.date().isoformat()}_"
            f"{self.end_date.date().isoformat()}"
        )


def _as_bool(raw: str | bool | None, *, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def _normalize_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts.normalize()


def _configure_thread_limits(max_threads: int) -> None:
    limit = str(max(1, int(max_threads)))
    for key in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "POLARS_MAX_THREADS",
    ]:
        os.environ[key] = limit


def _detect_price_bounds(raw_bundle_dir: Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    prices_path = raw_bundle_dir / "data" / "canonical" / "prices" / "equity_prices_daily.parquet"
    if not prices_path.exists():
        raise FileNotFoundError(f"canonical_prices_missing:{prices_path}")
    dates = pd.read_parquet(prices_path, columns=["date"])
    series = pd.to_datetime(dates["date"], errors="coerce").dropna()
    if series.empty:
        raise ValueError(f"canonical_prices_have_no_dates:{prices_path}")
    return _normalize_ts(series.min()), _normalize_ts(series.max())


def _build_chunks(
    *,
    global_start: pd.Timestamp,
    global_end: pd.Timestamp,
    chunk_months: int,
    warmup_days: int,
    forward_buffer_days: int,
) -> list[DateChunk]:
    chunks: list[DateChunk] = []
    current = _normalize_ts(global_start)
    chunk_idx = 0
    while current <= global_end:
        next_start = _normalize_ts(current + pd.DateOffset(months=max(1, int(chunk_months))))
        chunk_end = min(global_end, next_start - pd.Timedelta(days=1))
        chunks.append(
            DateChunk(
                chunk_id=chunk_idx,
                start_date=current,
                end_date=_normalize_ts(chunk_end),
                warmup_start_date=_normalize_ts(current - pd.Timedelta(days=max(0, int(warmup_days)))),
                build_end_date=_normalize_ts(chunk_end + pd.Timedelta(days=max(0, int(forward_buffer_days)))),
            )
        )
        current = _normalize_ts(chunk_end + pd.Timedelta(days=1))
        chunk_idx += 1
    return chunks


def _trim_chunk_window(frame: pd.DataFrame, chunk: DateChunk) -> pd.DataFrame:
    if frame is None or frame.empty or "date" not in frame.columns:
        return pd.DataFrame() if frame is None else frame.copy()
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.loc[(out["date"] >= chunk.start_date) & (out["date"] <= chunk.end_date)].copy()
    sort_cols = [col for col in ["date", "ticker"] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="mergesort")
    return out.reset_index(drop=True)


def _apply_feature_hygiene(weekly_panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = weekly_panel.copy()
    dropped_dead_features = [col for col in sorted(DEAD_EXPORT_COLUMNS) if col in out.columns]
    if dropped_dead_features:
        out = out.drop(columns=dropped_dead_features, errors="ignore")

    added_columns: list[str] = []
    filled_missing_counts: dict[str, int] = {}
    added_flags: list[str] = []

    def _ensure_numeric_column(column: str, default: float, *, fill_missing: bool) -> None:
        nonlocal out
        if column not in out.columns:
            out[column] = float(default)
            added_columns.append(column)
            return
        numeric = pd.to_numeric(out[column], errors="coerce")
        if fill_missing:
            missing = int(numeric.isna().sum())
            if missing > 0:
                filled_missing_counts[column] = int(filled_missing_counts.get(column, 0) + missing)
                numeric = numeric.fillna(default)
        out[column] = numeric.astype(float)

    for feature, flag_name in SPARSE_FEATURE_AVAILABILITY_FLAGS.items():
        if feature in out.columns:
            raw = pd.to_numeric(out[feature], errors="coerce")
            out[flag_name] = raw.notna().astype("float32")
            missing = int(raw.isna().sum())
            if missing > 0:
                filled_missing_counts[feature] = int(filled_missing_counts.get(feature, 0) + missing)
            out[feature] = raw.fillna(float(SCHEMA_DEFAULT_FILL_VALUES.get(feature, 0.0))).astype(float)
        else:
            out[feature] = float(SCHEMA_DEFAULT_FILL_VALUES.get(feature, 0.0))
            out[flag_name] = 0.0
            added_columns.append(feature)
        added_flags.append(flag_name)

    for flag_name in SPARSE_FEATURE_AVAILABILITY_FLAGS.values():
        if flag_name not in out.columns:
            out[flag_name] = 0.0
            added_flags.append(flag_name)
        else:
            out[flag_name] = pd.to_numeric(out[flag_name], errors="coerce").fillna(0.0).astype(float)

    for column, default in SCHEMA_DEFAULT_FILL_VALUES.items():
        _ensure_numeric_column(column, float(default), fill_missing=True)

    return (
        out,
        {
            "dropped_dead_features": dropped_dead_features,
            "added_schema_columns": sorted(dict.fromkeys(added_columns)),
            "added_availability_flags": sorted(dict.fromkeys(added_flags)),
            "filled_missing_counts": dict(sorted(filled_missing_counts.items())),
        },
    )


def _canonical_feature_column_order(columns: Iterable[str]) -> list[str]:
    names = [str(col) for col in columns]
    ordered: list[str] = []
    for name in ["date", "ticker"]:
        if name in names:
            ordered.append(name)
    middle = sorted({name for name in names if name not in {"date", "ticker", "target_weekly_return"}})
    ordered.extend(middle)
    if "target_weekly_return" in names:
        ordered.append("target_weekly_return")
    return ordered


def _stabilize_feature_chunk_schemas(
    *,
    chunk_rows: list[dict[str, Any]],
    canonical_columns: Sequence[str],
) -> list[dict[str, Any]]:
    canonical = [str(col) for col in canonical_columns]
    if not canonical:
        return []

    audits: list[dict[str, Any]] = []
    for row in chunk_rows:
        files = row.get("files") or {}
        raw_path = files.get("features")
        if not raw_path:
            continue
        path = Path(str(raw_path))
        if not path.exists():
            continue

        frame = pd.read_parquet(path)
        added_columns: list[str] = []
        for column in canonical:
            if column in frame.columns:
                continue
            if column == "date":
                frame[column] = pd.NaT
            elif column == "ticker":
                frame[column] = pd.Series([pd.NA] * len(frame), index=frame.index, dtype="string")
            else:
                frame[column] = float(SCHEMA_DEFAULT_FILL_VALUES.get(column, np.nan))
            added_columns.append(column)

        extra_columns = [column for column in frame.columns if str(column) not in canonical]
        if extra_columns:
            frame = frame.drop(columns=extra_columns, errors="ignore")

        for column in canonical:
            if column == "date":
                frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
            elif column == "ticker":
                frame[column] = frame[column].astype("string")
            else:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float32")

        frame = frame[canonical]
        frame.to_parquet(path, index=False)
        audits.append(
            {
                "chunk_id": int(row.get("chunk_id", 0) or 0),
                "path": str(path),
                "added_columns": sorted(added_columns),
                "extra_columns_removed": sorted(str(col) for col in extra_columns),
            }
        )

    return audits


def _build_dataset_frame(
    runtime_root: Path,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    max_tickers: int,
    max_rows: int,
    duckdb_threads: int,
    duckdb_memory_limit_mb: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    lookback_days = max(365, int((_normalize_ts(end_date) - _normalize_ts(start_date)).days) + 7)
    config_payload = _dataset_runtime_config(
        policy_path=runtime_root / "config" / "research_policy.yaml",
        start_date=start_date.date().isoformat(),
        end_date=end_date.date().isoformat(),
        lookback_days=lookback_days,
        max_tickers=max_tickers,
        max_rows=max_rows,
        low_resource_mode="false",
        profile="full",
    )
    config_payload["duckdb_threads"] = int(max(1, duckdb_threads))
    config_payload["duckdb_memory_limit_mb"] = int(max(256, duckdb_memory_limit_mb))
    config_payload["low_resource_mode"] = False

    with working_directory(runtime_root):
        manager = DatasetManager(project_root=runtime_root, config=config_payload)
        dataset = manager.build_research_dataset()
    return dataset.frame.copy(), dict(dataset.metadata or {})


def _load_cross_asset_weekly(raw_bundle_dir: Path) -> pd.DataFrame:
    path = raw_bundle_dir / "data" / "canonical" / "macro" / "cross_asset_prices_daily.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["date"])
    panel = pd.read_parquet(path)
    if panel.empty:
        return pd.DataFrame(columns=["date"])
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel = panel.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"], kind="mergesort")

    close = pd.to_numeric(panel["close"], errors="coerce")
    panel["ret_1d"] = close.groupby(panel["symbol"], sort=False).pct_change()
    panel["ret_20d"] = close.groupby(panel["symbol"], sort=False).pct_change(20)
    panel["diff_20d"] = close.groupby(panel["symbol"], sort=False).diff(20)
    panel["vol_20d"] = (
        panel["ret_1d"]
        .groupby(panel["symbol"], sort=False)
        .rolling(20, min_periods=10)
        .std()
        .reset_index(level=0, drop=True)
    )
    panel["week_end"] = panel["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    weekly = panel.groupby(["symbol", "week_end"], sort=True, as_index=False).tail(1).copy()
    weekly = weekly.rename(columns={"date": "week_source_date", "week_end": "date"})
    wide = weekly.pivot(index="date", columns="symbol", values=["ret_20d", "diff_20d", "vol_20d"])
    wide.columns = [f"{outer}_{inner}" for outer, inner in wide.columns.to_flat_index()]
    return wide.reset_index().sort_values("date", kind="mergesort").reset_index(drop=True)


def _load_vix_proxy_weekly(runtime_root: Path) -> pd.DataFrame:
    proxy_path = runtime_root / "data" / "processed" / "regime" / "india_vix_proxy.parquet"
    if not proxy_path.exists():
        return pd.DataFrame(columns=["date", "vix_india_4w"])
    proxy = pd.read_parquet(proxy_path)
    date_col = "Date" if "Date" in proxy.columns else "date"
    value_col = "vix_proxy" if "vix_proxy" in proxy.columns else None
    if value_col is None or date_col not in proxy.columns:
        return pd.DataFrame(columns=["date", "vix_india_4w"])
    proxy["date"] = pd.to_datetime(proxy[date_col], errors="coerce").dt.normalize()
    proxy[value_col] = pd.to_numeric(proxy[value_col], errors="coerce")
    proxy = proxy.dropna(subset=["date"]).sort_values("date", kind="mergesort")
    proxy["week_end"] = proxy["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    weekly = proxy.groupby("week_end", sort=True, as_index=False).tail(1).copy()
    weekly = weekly.drop(columns=["date"], errors="ignore").rename(columns={"week_end": "date"})
    weekly["vix_india_4w"] = weekly[value_col].pct_change(4)
    return weekly[["date", "vix_india_4w"]].drop_duplicates("date", keep="last").reset_index(drop=True)


def _load_coal_benchmark_weekly(runtime_root: Path) -> pd.DataFrame:
    benchmark_path = runtime_root / "data" / "processed" / "macro" / "coal_benchmark_daily.parquet"
    if not benchmark_path.exists():
        return pd.DataFrame(columns=["date", "coal_4w_return_fallback"])
    benchmark = pd.read_parquet(benchmark_path)
    date_col = "date" if "date" in benchmark.columns else ("Date" if "Date" in benchmark.columns else None)
    value_col = (
        "coal_price_usd_per_ton"
        if "coal_price_usd_per_ton" in benchmark.columns
        else ("coal_price" if "coal_price" in benchmark.columns else None)
    )
    if date_col is None or value_col is None:
        return pd.DataFrame(columns=["date", "coal_4w_return_fallback"])
    benchmark["date"] = pd.to_datetime(benchmark[date_col], errors="coerce").dt.normalize()
    benchmark[value_col] = pd.to_numeric(benchmark[value_col], errors="coerce")
    benchmark = benchmark.dropna(subset=["date", value_col]).sort_values("date", kind="mergesort")
    if benchmark.empty:
        return pd.DataFrame(columns=["date", "coal_4w_return_fallback"])
    benchmark["ret_20d"] = benchmark[value_col].pct_change(20)
    benchmark["week_end"] = benchmark["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    weekly = benchmark.groupby("week_end", sort=True, as_index=False).tail(1).copy()
    weekly = (
        weekly.drop(columns=["date"], errors="ignore")
        .rename(columns={"week_end": "date", "ret_20d": "coal_4w_return_fallback"})
    )
    return weekly[["date", "coal_4w_return_fallback"]].drop_duplicates("date", keep="last").reset_index(drop=True)


def _numeric(series: pd.Series | Any, length: int) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    if isinstance(series, (np.ndarray, list, tuple)):
        values = pd.Series(series)
        if len(values) < length:
            values = values.reindex(range(length))
        elif len(values) > length:
            values = values.iloc[:length].reset_index(drop=True)
        return pd.to_numeric(values, errors="coerce")
    if np.isscalar(series):
        fill = np.nan if series is None else series
        return pd.Series([fill] * length, index=range(length), dtype=float)
    return pd.Series(np.nan, index=range(length), dtype=float)


def _build_plan_signal_block(
    weekly_panel: pd.DataFrame,
    *,
    raw_bundle_dir: Path,
    runtime_root: Path,
    allow_proxies: bool,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    date_index = (
        weekly_panel[["date"]]
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date", kind="mergesort")
        .reset_index(drop=True)
    )
    out = date_index.copy()
    audit_rows: list[dict[str, Any]] = []

    def register_signal(
        name: str,
        series: pd.Series | Any,
        *,
        source: str,
        status: str,
        notes: str = "",
    ) -> None:
        values = _numeric(series, len(out))
        out[name] = values.to_numpy(dtype=float)
        audit_rows.append(
            {
                "signal": name,
                "status": status,
                "source": source,
                "notes": notes,
                "date_coverage_pct": float(values.notna().mean() * 100.0),
            }
        )

    cross_asset = _load_cross_asset_weekly(raw_bundle_dir)
    if not cross_asset.empty:
        merged = out.merge(cross_asset, on="date", how="left", sort=False)
    else:
        merged = out.copy()

    register_signal(
        "inrusd_4w_return",
        merged.get("ret_20d_USDINR=X"),
        source="cross_asset:USDINR=X",
        status="exact",
        notes="20 trading-day return, shifted one week before merge.",
    )
    register_signal(
        "inrusd_vol_4w",
        merged.get("vol_20d_USDINR=X"),
        source="cross_asset:USDINR=X",
        status="exact",
        notes="20 trading-day daily-return volatility, shifted one week before merge.",
    )
    register_signal(
        "crude_4w_return",
        merged.get("ret_20d_CL=F"),
        source="cross_asset:CL=F",
        status="exact",
        notes="20 trading-day crude return, shifted one week before merge.",
    )
    crude_values = _numeric(merged.get("ret_20d_CL=F"), len(merged))
    register_signal(
        "crude_shock",
        np.where(crude_values.notna(), (crude_values.abs() > 0.15).astype(float), np.nan),
        source="derived:crude_4w_return",
        status="derived",
        notes="1 when abs(crude_4w_return) > 15%, else 0.",
    )
    register_signal(
        "gold_4w_return",
        merged.get("ret_20d_GC=F"),
        source="cross_asset:GC=F",
        status="exact",
        notes="20 trading-day gold return, shifted one week before merge.",
    )
    register_signal(
        "copper_4w_return",
        merged.get("ret_20d_HG=F"),
        source="cross_asset:HG=F",
        status="exact",
        notes="20 trading-day copper return, shifted one week before merge.",
    )

    dxy_exact = merged.get(f"ret_20d_{EXACT_PLAN_SYMBOLS['dxy']}")
    if dxy_exact is not None and _numeric(dxy_exact, len(merged)).notna().any():
        register_signal(
            "dxy_4w_return",
            dxy_exact,
            source=f"cross_asset:{EXACT_PLAN_SYMBOLS['dxy']}",
            status="exact",
            notes="20 trading-day DXY return, shifted one week before merge.",
        )
    elif allow_proxies:
        register_signal(
            "dxy_4w_return",
            -_numeric(merged.get("ret_20d_EURUSD=X"), len(merged)),
            source="proxy:-EURUSD=X",
            status="proxy",
            notes="Direct DXY history is not staged locally; EURUSD inverse is used as the proxy.",
        )
    else:
        register_signal(
            "dxy_4w_return",
            pd.Series(np.nan, index=merged.index, dtype=float),
            source="missing:DXY",
            status="proxy_blocked",
            notes="Direct DXY history is unavailable locally and proxy usage is disabled.",
        )

    steel_exact = merged.get(f"ret_20d_{EXACT_PLAN_SYMBOLS['steel_hrc']}")
    if steel_exact is not None and _numeric(steel_exact, len(merged)).notna().any():
        register_signal(
            "steel_4w_return",
            steel_exact,
            source=f"cross_asset:{EXACT_PLAN_SYMBOLS['steel_hrc']}",
            status="exact",
            notes="20 trading-day hot-rolled coil return, shifted one week before merge.",
        )
    elif allow_proxies:
        register_signal(
            "steel_4w_return",
            merged.get("ret_20d_HG=F"),
            source="proxy:HG=F",
            status="proxy",
            notes="No direct steel/HRC series is staged locally; copper is used as the explicit proxy.",
        )
    else:
        register_signal(
            "steel_4w_return",
            pd.Series(np.nan, index=merged.index, dtype=float),
            source="missing:steel_or_hrc_series",
            status="missing",
            notes="No direct steel/HRC series is staged locally.",
        )

    coal_exact = _numeric(merged.get(f"ret_20d_{EXACT_PLAN_SYMBOLS['coal']}"), len(merged))
    coal_fallback_df = _load_coal_benchmark_weekly(runtime_root)
    if not coal_fallback_df.empty:
        coal_fallback = _numeric(
            out.merge(coal_fallback_df, on="date", how="left", sort=False).get("coal_4w_return_fallback"),
            len(out),
        )
    else:
        coal_fallback = pd.Series(np.nan, index=range(len(out)), dtype=float)
    exact_has = coal_exact.notna().any()
    fallback_has = coal_fallback.notna().any()
    if exact_has and fallback_has:
        coal_combined = coal_exact.combine_first(coal_fallback)
        fallback_fill_pct = float((coal_exact.isna() & coal_combined.notna()).mean() * 100.0)
        if fallback_fill_pct > 0.0:
            register_signal(
                "coal_4w_return",
                coal_combined,
                source=f"hybrid:{EXACT_PLAN_SYMBOLS['coal']}+fred:PCOALAUUSDM",
                status="hybrid",
                notes=(
                    "20 trading-day coal return from API2 coal futures when available; "
                    f"missing tail dates are filled with an official FRED coal benchmark fallback "
                    f"for {fallback_fill_pct:.1f}% of weekly dates."
                ),
            )
        else:
            register_signal(
                "coal_4w_return",
                coal_combined,
                source=f"cross_asset:{EXACT_PLAN_SYMBOLS['coal']}",
                status="exact",
                notes="20 trading-day coal return, shifted one week before merge.",
            )
    elif exact_has:
        register_signal(
            "coal_4w_return",
            coal_exact,
            source=f"cross_asset:{EXACT_PLAN_SYMBOLS['coal']}",
            status="exact",
            notes="20 trading-day coal return, shifted one week before merge.",
        )
    elif fallback_has:
        register_signal(
            "coal_4w_return",
            coal_fallback,
            source="benchmark:fred:PCOALAUUSDM",
            status="benchmark",
            notes=(
                "20 business-day return from the official FRED Australian coal benchmark, "
                "forward-filled from monthly observations after the next business day following month-end."
            ),
        )
    else:
        register_signal(
            "coal_4w_return",
            pd.Series(np.nan, index=merged.index, dtype=float),
            source="missing:coal_series",
            status="missing",
            notes="No coal price series is staged locally.",
        )

    panel_daily = (
        weekly_panel[["date", "rbi_repo_rate_level"]]
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date", kind="mergesort")
        if "rbi_repo_rate_level" in weekly_panel.columns
        else pd.DataFrame(columns=["date", "rbi_repo_rate_level"])
    )
    if not panel_daily.empty:
        repo_change = panel_daily["rbi_repo_rate_level"].diff()
        register_signal(
            "rbi_rate_chg",
            out.merge(panel_daily.assign(rbi_rate_chg=repo_change)[["date", "rbi_rate_chg"]], on="date", how="left")[
                "rbi_rate_chg"
            ],
            source="feature_factory:rbi_repo_rate_level",
            status="exact",
            notes="One-week-lagged change in the repo-rate level already merged by the feature factory.",
        )
    else:
        register_signal(
            "rbi_rate_chg",
            pd.Series(np.nan, index=out.index, dtype=float),
            source="missing:rbi_repo_rate_level",
            status="missing",
            notes="Repo-rate level is unavailable in the built panel.",
        )

    us10y_exact = merged.get(f"diff_20d_{EXACT_PLAN_SYMBOLS['us_10y']}")
    if us10y_exact is not None and _numeric(us10y_exact, len(merged)).notna().any():
        register_signal(
            "us_10y_4w",
            _numeric(us10y_exact, len(merged)) / 10.0,
            source=f"cross_asset:{EXACT_PLAN_SYMBOLS['us_10y']}",
            status="exact",
            notes="20 trading-day US 10Y yield level change from ^TNX, converted from CBOE tenth-percent units and shifted one week before merge.",
        )
    else:
        register_signal(
            "us_10y_4w",
            pd.Series(np.nan, index=out.index, dtype=float),
            source="missing:us_10y_series",
            status="missing",
            notes="No US 10Y source is staged locally.",
        )

    if "india_vix" in weekly_panel.columns:
        vix_panel = (
            weekly_panel[["date", "india_vix"]]
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date", kind="mergesort")
            .reset_index(drop=True)
        )
        vix_panel["vix_india_4w"] = pd.to_numeric(vix_panel["india_vix"], errors="coerce").pct_change(4)
        register_signal(
            "vix_india_4w",
            out.merge(vix_panel[["date", "vix_india_4w"]], on="date", how="left")["vix_india_4w"],
            source="feature_factory:india_vix",
            status="exact",
            notes="One-week-lagged four-week change in the merged India VIX level.",
        )
    elif allow_proxies:
        vix_proxy = _load_vix_proxy_weekly(runtime_root)
        register_signal(
            "vix_india_4w",
            out.merge(vix_proxy, on="date", how="left")["vix_india_4w"],
            source="proxy:data/processed/regime/india_vix_proxy.parquet",
            status="proxy",
            notes="Exact India VIX history is unavailable locally; the staged proxy series is used.",
        )
    else:
        register_signal(
            "vix_india_4w",
            pd.Series(np.nan, index=out.index, dtype=float),
            source="missing:india_vix",
            status="proxy_blocked",
            notes="Exact India VIX history is unavailable locally and proxy usage is disabled.",
        )

    dxy = _numeric(out.get("dxy_4w_return"), len(out))
    inr_vol = _numeric(out.get("inrusd_vol_4w"), len(out))
    register_signal(
        "fii_proxy",
        inr_vol * dxy,
        source="derived:inrusd_vol_4w*dxy_4w_return",
        status="derived",
        notes="Composite FII stress proxy from INR volatility and DXY change.",
    )

    commodity_inputs = []
    for col in [
        "crude_4w_return",
        "gold_4w_return",
        "steel_4w_return",
        "copper_4w_return",
        "coal_4w_return",
    ]:
        if col in out.columns:
            commodity_inputs.append(_numeric(out[col], len(out)))
    if commodity_inputs:
        commodity_frame = pd.concat(commodity_inputs, axis=1)
        basket = commodity_frame.mean(axis=1, skipna=True)
    else:
        basket = pd.Series(np.nan, index=out.index, dtype=float)
    register_signal(
        "commodity_basket",
        basket,
        source="derived:equal_weight_available_commodity_signals",
        status="derived",
        notes="Seed composite only. Recompute IC-weighted basket on Kaggle from the frozen primitive signals.",
    )

    signal_cols = [col for col in out.columns if col not in {"date"}]
    if signal_cols:
        out[signal_cols] = out[signal_cols].shift(1)
    return out, audit_rows


def _merge_plan_signals(
    weekly_panel: pd.DataFrame,
    *,
    raw_bundle_dir: Path,
    runtime_root: Path,
    allow_proxies: bool,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    signal_block, audit_rows = _build_plan_signal_block(
        weekly_panel,
        raw_bundle_dir=raw_bundle_dir,
        runtime_root=runtime_root,
        allow_proxies=allow_proxies,
    )
    merged = weekly_panel.merge(signal_block, on="date", how="left", sort=False)

    oil_sensitivity = _numeric(merged.get("oil_sensitivity_score"), len(merged))
    fx_sensitivity = _numeric(merged.get("fx_sensitivity_score"), len(merged))
    international_revenue = _numeric(merged.get("international_revenue_proxy"), len(merged))
    effective_fx_sensitivity = np.where(np.isfinite(fx_sensitivity) & (np.abs(fx_sensitivity) > 0), fx_sensitivity, international_revenue)
    merged["stock_x_crude"] = oil_sensitivity * _numeric(merged.get("crude_4w_return"), len(merged))
    merged["stock_x_inrusd"] = pd.Series(effective_fx_sensitivity, index=merged.index, dtype=float) * _numeric(
        merged.get("inrusd_4w_return"), len(merged)
    )
    return merged, audit_rows


def _summarize_signal_audit(
    weekly_panel: pd.DataFrame,
    audit_rows: list[dict[str, Any]],
    *,
    strict_plan_signals: bool,
    min_exact_signal_coverage_pct: float,
) -> dict[str, Any]:
    rows = []
    blocking: list[str] = []
    warnings: list[str] = []
    low_coverage: list[str] = []

    for row in audit_rows:
        signal = str(row["signal"])
        work = dict(row)
        series = _numeric(weekly_panel.get(signal), len(weekly_panel))
        if "date" in weekly_panel.columns and signal in weekly_panel.columns:
            per_date = (
                weekly_panel[["date", signal]]
                .drop_duplicates(subset=["date"], keep="last")
                .sort_values("date", kind="mergesort")
            )
            date_series = _numeric(per_date.get(signal), len(per_date))
            work["date_coverage_pct"] = float(date_series.notna().mean() * 100.0) if len(date_series) else 0.0
        work["panel_coverage_pct"] = float(series.notna().mean() * 100.0) if len(series) else 0.0
        status = str(work.get("status", "unknown"))
        if status in {"missing", "proxy_blocked"}:
            blocking.append(signal)
        elif status == "proxy":
            warnings.append(signal)
        elif status in {"benchmark", "hybrid"}:
            warnings.append(signal)
        if status in {"exact", "benchmark", "hybrid"} and float(work["panel_coverage_pct"]) < float(
            min_exact_signal_coverage_pct
        ):
            low_coverage.append(signal)
        rows.append(work)

    if strict_plan_signals:
        blocking.extend(low_coverage)
    else:
        warnings.extend(low_coverage)

    return {
        "generated_at": now_utc_iso(),
        "strict_plan_signals": bool(strict_plan_signals),
        "blocking_signals": sorted(dict.fromkeys(blocking)),
        "warning_signals": sorted(dict.fromkeys(warnings)),
        "low_coverage_signals": sorted(dict.fromkeys(low_coverage)),
        "min_exact_signal_coverage_pct": float(min_exact_signal_coverage_pct),
        "signals": rows,
    }


def _validation_window(
    *,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    warmup_days: int,
    forward_buffer_days: int,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    validation_end = data_end
    validation_start = max(data_start, data_end - pd.Timedelta(days=max(540, warmup_days + 180)))
    return validation_start, _normalize_ts(validation_end + pd.Timedelta(days=max(0, forward_buffer_days)))


def _validate_signal_contract(
    *,
    runtime_root: Path,
    raw_bundle_dir: Path,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    warmup_days: int,
    forward_buffer_days: int,
    max_tickers: int,
    max_rows: int,
    duckdb_threads: int,
    duckdb_memory_limit_mb: int,
    allow_proxies: bool,
    strict_plan_signals: bool,
    min_exact_signal_coverage_pct: float,
) -> dict[str, Any]:
    progress = StepProgress("Validation", 7)
    validation_start, validation_build_end = _validation_window(
        data_start=data_start,
        data_end=data_end,
        warmup_days=warmup_days,
        forward_buffer_days=forward_buffer_days,
    )
    with progress.step(
        "Build daily research dataset "
        f"({validation_start.date().isoformat()} -> {validation_build_end.date().isoformat()})"
    ):
        panel, dataset_meta = _build_dataset_frame(
            runtime_root,
            start_date=validation_start,
            end_date=validation_build_end,
            max_tickers=max_tickers,
            max_rows=max_rows,
            duckdb_threads=duckdb_threads,
            duckdb_memory_limit_mb=duckdb_memory_limit_mb,
        )
    with progress.step("Normalize and sort daily panel"):
        panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
        panel["ticker"] = panel["ticker"].astype("string")
        panel = panel.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")
    with progress.step("Resample daily panel to weekly Friday cadence"):
        weekly_panel = resample_daily_panel_to_weekly(panel)
    with progress.step("Attach universe annotations"):
        weekly_panel = attach_universe_annotations(weekly_panel, runtime_root)
    with progress.step("Build market-cap fields"):
        weekly_panel = build_market_cap_fields(weekly_panel)
    with progress.step("Build and merge regime labels"):
        regimes_df = build_plan_regime_labels(weekly_panel, runtime_root)
        weekly_panel = merge_regimes_into_panel(weekly_panel, regimes_df)
    with progress.step("Merge plan signals and summarize audit"):
        weekly_panel, audit_rows = _merge_plan_signals(
            weekly_panel,
            raw_bundle_dir=raw_bundle_dir,
            runtime_root=runtime_root,
            allow_proxies=allow_proxies,
        )
        audit = _summarize_signal_audit(
            weekly_panel,
            audit_rows,
            strict_plan_signals=strict_plan_signals,
            min_exact_signal_coverage_pct=min_exact_signal_coverage_pct,
        )
    audit["validation_slice"] = {
        "start_date": validation_start.date().isoformat(),
        "end_date": validation_build_end.date().isoformat(),
    }
    audit["dataset_metadata"] = json_ready(dataset_meta)
    return audit


def _feature_name_manifest(feature_columns: Iterable[str]) -> list[dict[str, Any]]:
    """Names + inferred unit kind only.

    N8: the chunk builder cannot compute coverage (no merged data yet), so it
    must NOT emit a full feature_unit_registry from an empty frame — that would
    report coverage 0 / model_safe False for every column, which is misleading.
    The authoritative registry (with real coverage) is written by the merge step
    from the actual merged parquet. Here we emit only the name + unit kind.
    """
    names = [str(col) for col in feature_columns if str(col) not in {"date", "ticker", "target_weekly_return"}]
    return [{"feature": name, "unit_kind": infer_feature_unit_kind(name)} for name in sorted(dict.fromkeys(names))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a chunked local Northstar feature dataset.")
    parser.add_argument("--data-dir", type=Path, default=None, help="Repo root or raw-bundle root.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Where the chunked dataset bundle will be written.")
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--chunk-months", type=int, default=6)
    parser.add_argument("--warmup-days", type=int, default=420)
    parser.add_argument("--forward-buffer-days", type=int, default=10)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--duckdb-threads", type=int, default=1)
    parser.add_argument("--duckdb-memory-limit-mb", type=int, default=768)
    parser.add_argument("--max-tickers", type=int, default=0)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--rebuild-screener", choices=["auto", "true", "false"], default="auto")
    parser.add_argument("--allow-proxies", choices=["true", "false"], default="false")
    parser.add_argument("--strict-plan-signals", choices=["true", "false"], default="true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--preflight-validation",
        action="store_true",
        help="Run the pre-build trailing-window signal validation (redundant with per-chunk + per-era enforcement; off by default for full builds).",
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--min-exact-signal-coverage-pct", type=float, default=90.0)
    parser.add_argument("--train-weeks", type=int, default=104)
    parser.add_argument("--test-weeks", type=int, default=13)
    parser.add_argument("--step-weeks", type=int, default=13)
    parser.add_argument("--target-windows", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _configure_thread_limits(args.threads)

    # E.9: the warmup window must cover the longest rolling factor lookback, or
    # chunk-boundary rows silently get truncated rolling features that differ from
    # the direct (non-chunked) path. Gap9 academic factors default to a 252-day
    # (~365 calendar-day) beta/factor lookback; require ~1.45x + a margin so a
    # future increase to the factor lookback surfaces here instead of silently.
    _gap9_lookback_days = 252
    _required_warmup = int(1.45 * _gap9_lookback_days) + 30  # ~395
    if int(args.warmup_days) < _required_warmup:
        raise ValueError(
            f"warmup_days_too_small:{args.warmup_days}<{_required_warmup} "
            f"(must cover the {_gap9_lookback_days}-day factor lookback with margin; "
            f"raise --warmup-days or lower the factor lookback)"
        )

    bootstrap = StepProgress("Bootstrap", 5)
    with bootstrap.step("Resolve raw bundle directory"):
        raw_bundle_dir = resolve_raw_bundle_dir(args.data_dir)
    with bootstrap.step("Validate raw bundle support artifacts"):
        _validate_raw_bundle_support_artifacts(raw_bundle_dir)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with bootstrap.step("Prepare runtime project"):
        runtime_root = prepare_runtime_project(raw_bundle_dir, output_dir / "_runtime_root")
        (runtime_root / "config").mkdir(parents=True, exist_ok=True)
        (runtime_root / "config" / "research_policy.yaml").write_text(
            "# Runtime policy is encoded in chunk manifests for the chunked local builder.\n",
            encoding="utf-8",
        )
        # N1: any valuation_scores.parquet shipped in a raw bundle without a
        # post-N1-fix provenance marker was computed BEFORE the metadata-broadcast
        # leak fix and is poisoned (today's price/ROCE stamped into history).
        # A marker-attested cache (scripts/research/precompute_valuation_cache.py)
        # is trusted: recomputing valuations in-build costs ~116ms/ticker-date and
        # killed three 2026-07-16/17 Kaggle runs against the 12h session cap.
        # Only act when the runtime data tree is a real copy (Kaggle); when it is
        # a symlink to the live project tree, the file is managed there.
        runtime_data = runtime_root / "data"
        stale_cache = runtime_root / "data" / "processed" / "valuation_scores.parquet"
        cache_marker = stale_cache.with_name("valuation_scores.provenance.json")
        if not runtime_data.is_symlink() and stale_cache.exists():
            marker_ok = False
            if cache_marker.exists():
                try:
                    marker_ok = bool(json.loads(cache_marker.read_text()).get("post_n1_fix"))
                except Exception:
                    marker_ok = False
            if marker_ok:
                print("[bootstrap] trusted marker-attested valuation cache (post-N1-fix)", flush=True)
            else:
                stale_cache.rename(stale_cache.with_name("valuation_scores.pre_n1_fix.stale"))
                print("[bootstrap] quarantined stale valuation_scores.parquet (pre-N1-fix cache)", flush=True)

    with bootstrap.step("Validate screener rebuild state"):
        screener_rebuild = _maybe_rebuild_screener(runtime_root, args.rebuild_screener)
        write_json(output_dir / "screener_rebuild_validation.json", screener_rebuild)

    with bootstrap.step("Detect available price date bounds"):
        detected_start, detected_end = _detect_price_bounds(raw_bundle_dir)
    global_start = _normalize_ts(args.start_date) if args.start_date else detected_start
    global_end = _normalize_ts(args.end_date) if args.end_date else detected_end
    if global_end < global_start:
        raise ValueError(f"invalid_date_range:{global_start}>{global_end}")

    allow_proxies = _as_bool(args.allow_proxies, default=False)
    strict_plan_signals = _as_bool(args.strict_plan_signals, default=True)

    # G.3: the preflight validation rebuilds the trailing ~1.6 years of the
    # dataset before the main loop then discards it, and the chunk loop rebuilds
    # the same dates again. For a normal full build the per-chunk audits plus the
    # finalize-time per-era enforcement (E.1/E.2) already cover the signal
    # contract over the FULL range, so skip the redundant preflight by default.
    # --validate-only and --preflight-validation still run it.
    run_preflight = bool(args.validate_only or args.preflight_validation)
    if run_preflight:
        validation_audit = _validate_signal_contract(
            runtime_root=runtime_root,
            raw_bundle_dir=raw_bundle_dir,
            data_start=global_start,
            data_end=global_end,
            warmup_days=int(args.warmup_days),
            forward_buffer_days=int(args.forward_buffer_days),
            max_tickers=int(args.max_tickers),
            max_rows=int(args.max_rows),
            duckdb_threads=int(args.duckdb_threads),
            duckdb_memory_limit_mb=int(args.duckdb_memory_limit_mb),
            allow_proxies=allow_proxies,
            strict_plan_signals=strict_plan_signals,
            min_exact_signal_coverage_pct=float(args.min_exact_signal_coverage_pct),
        )
    else:
        validation_audit = {
            "generated_at": now_utc_iso(),
            "preflight_skipped": True,
            "note": "Full build: per-chunk audits + finalize per-era enforcement cover the signal contract.",
            "blocking_signals": [],
            "warning_signals": [],
        }
    write_json(output_dir / "plan_signal_audit.json", validation_audit)
    if args.validate_only:
        print(
            json_ready(
                {
                    "output_dir": str(output_dir),
                    "blocking_signals": validation_audit.get("blocking_signals", []),
                    "warning_signals": validation_audit.get("warning_signals", []),
                }
            )
        )
        return 0
    if run_preflight and strict_plan_signals and validation_audit.get("blocking_signals"):
        raise RuntimeError(
            "strict_plan_signal_validation_failed:"
            + ",".join(str(item) for item in validation_audit["blocking_signals"])
        )

    feature_chunk_dir = output_dir / "features_chunks"
    metadata_chunk_dir = output_dir / "metadata_chunks"
    regime_chunk_dir = output_dir / "regime_chunks"
    chunk_manifest_dir = output_dir / "chunk_manifests"
    for path in [feature_chunk_dir, metadata_chunk_dir, regime_chunk_dir, chunk_manifest_dir]:
        path.mkdir(parents=True, exist_ok=True)

    chunks = _build_chunks(
        global_start=global_start,
        global_end=global_end,
        chunk_months=int(args.chunk_months),
        warmup_days=int(args.warmup_days),
        forward_buffer_days=int(args.forward_buffer_days),
    )

    feature_union: list[str] = []
    metadata_union: list[str] = []
    regime_union: list[str] = []
    all_weekly_dates: list[pd.Timestamp] = []
    chunk_rows: list[dict[str, Any]] = []

    for chunk in chunks:
        feature_path = feature_chunk_dir / f"{chunk.slug}.parquet"
        metadata_path = metadata_chunk_dir / f"{chunk.slug}.parquet"
        regime_path = regime_chunk_dir / f"{chunk.slug}.parquet"
        chunk_manifest_path = chunk_manifest_dir / f"{chunk.slug}.json"

        if args.skip_existing and feature_path.exists() and metadata_path.exists() and regime_path.exists():
            chunk_rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "slug": chunk.slug,
                    "start_date": chunk.start_date.date().isoformat(),
                    "end_date": chunk.end_date.date().isoformat(),
                    "status": "skipped_existing",
                    "files": {
                        "features": str(feature_path),
                        "metadata": str(metadata_path),
                        "regimes": str(regime_path),
                    },
                }
            )
            continue

        chunk_progress = StepProgress(f"Chunk {chunk.chunk_id + 1}/{len(chunks)}", 8)
        with chunk_progress.step(
            "Build daily research dataset "
            f"({chunk.warmup_start_date.date().isoformat()} -> {chunk.build_end_date.date().isoformat()})"
        ):
            panel, dataset_meta = _build_dataset_frame(
                runtime_root,
                start_date=chunk.warmup_start_date,
                end_date=chunk.build_end_date,
                max_tickers=int(args.max_tickers),
                max_rows=int(args.max_rows),
                duckdb_threads=int(args.duckdb_threads),
                duckdb_memory_limit_mb=int(args.duckdb_memory_limit_mb),
            )
        with chunk_progress.step("Normalize and sort daily panel"):
            panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
            panel["ticker"] = panel["ticker"].astype("string")
            panel = panel.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")

        with chunk_progress.step("Resample daily panel to weekly Friday cadence"):
            weekly_panel = resample_daily_panel_to_weekly(panel)
        with chunk_progress.step("Attach universe annotations"):
            weekly_panel = attach_universe_annotations(weekly_panel, runtime_root)
        with chunk_progress.step("Build market-cap fields"):
            weekly_panel = build_market_cap_fields(weekly_panel)
        with chunk_progress.step("Build and merge regime labels"):
            regimes_df = build_plan_regime_labels(weekly_panel, runtime_root)
            weekly_panel = merge_regimes_into_panel(weekly_panel, regimes_df)
        with chunk_progress.step("Merge plan signals"):
            weekly_panel, signal_audit_rows = _merge_plan_signals(
                weekly_panel,
                raw_bundle_dir=raw_bundle_dir,
                runtime_root=runtime_root,
                allow_proxies=allow_proxies,
            )
        with chunk_progress.step("Trim chunk window, apply hygiene, and write parquet artifacts"):
            weekly_panel = _trim_chunk_window(weekly_panel, chunk)
            regimes_out = _trim_chunk_window(regimes_df, chunk)
            weekly_panel, feature_hygiene = _apply_feature_hygiene(weekly_panel)
            feature_cols = select_feature_columns(weekly_panel)
            features_df = cast_feature_frame(weekly_panel, feature_cols)
            metadata_df = cast_metadata_frame(weekly_panel)
            regimes_out = (
                regimes_out.drop_duplicates(subset=["date"], keep="last")
                .sort_values("date", kind="mergesort")
                .reset_index(drop=True)
            )

            features_df.to_parquet(feature_path, index=False)
            metadata_df.to_parquet(metadata_path, index=False)
            regimes_out.to_parquet(regime_path, index=False)

        for name in features_df.columns:
            if name not in feature_union:
                feature_union.append(str(name))
        for name in metadata_df.columns:
            if name not in metadata_union:
                metadata_union.append(str(name))
        for name in regimes_out.columns:
            if name not in regime_union:
                regime_union.append(str(name))

        all_weekly_dates.extend(pd.to_datetime(features_df["date"], errors="coerce").dropna().tolist())
        chunk_signal_audit = _summarize_signal_audit(
            weekly_panel,
            signal_audit_rows,
            strict_plan_signals=strict_plan_signals,
            min_exact_signal_coverage_pct=float(args.min_exact_signal_coverage_pct),
        )
        chunk_manifest = {
            "generated_at": now_utc_iso(),
            "chunk": asdict(chunk),
            "dataset_metadata": json_ready(dataset_meta),
            "feature_hygiene": json_ready(feature_hygiene),
            "rows": {
                "features": int(len(features_df)),
                "metadata": int(len(metadata_df)),
                "regimes": int(len(regimes_out)),
            },
            "features": {
                "count": int(max(0, len(feature_cols))),
                "files": {
                    "features": str(feature_path),
                    "metadata": str(metadata_path),
                    "regimes": str(regime_path),
                },
            },
            "signal_audit": chunk_signal_audit,
        }
        write_json(chunk_manifest_path, chunk_manifest)
        chunk_rows.append(
            {
                "chunk_id": chunk.chunk_id,
                "slug": chunk.slug,
                "start_date": chunk.start_date.date().isoformat(),
                "end_date": chunk.end_date.date().isoformat(),
                "feature_rows": int(len(features_df)),
                "metadata_rows": int(len(metadata_df)),
                "regime_rows": int(len(regimes_out)),
                "feature_count": int(len(feature_cols)),
                "blocking_signals": list(chunk_signal_audit.get("blocking_signals", []) or []),
                "warning_signals": list(chunk_signal_audit.get("warning_signals", []) or []),
                "low_coverage_signals": list(chunk_signal_audit.get("low_coverage_signals", []) or []),
                "files": {
                    "features": str(feature_path),
                    "metadata": str(metadata_path),
                    "regimes": str(regime_path),
                    "manifest": str(chunk_manifest_path),
                },
            }
        )

    finalization = StepProgress("Finalize", 4)
    weekly_dates = (
        pd.Series(pd.to_datetime(all_weekly_dates, errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    splits: list[dict[str, Any]] = []
    with finalization.step("Generate walk-forward splits"):
        if weekly_dates:
            split_config = _effective_split_config(
                weekly_dates,
                train_weeks=int(args.train_weeks),
                test_weeks=int(args.test_weeks),
                step_weeks=int(args.step_weeks),
                target_windows=int(args.target_windows),
                forward_buffer_days=int(args.forward_buffer_days),
                target_horizon_days=5,
            )
            splits = generate_anchored_weekly_splits(
                weekly_dates,
                train_weeks=int(split_config["train_weeks"]),
                test_weeks=int(split_config["test_weeks"]),
                step_weeks=int(split_config["step_weeks"]),
                target_windows=int(split_config["target_windows"]),
                forward_buffer_days=int(args.forward_buffer_days),
                target_horizon_days=5,
            )
        write_json(output_dir / "northstar_walk_forward_splits.json", splits)
    with finalization.step("Write feature name manifest"):
        # N8: names + unit kinds only. The coverage-bearing feature_unit_registry
        # is written by merge_chunked_feature_dataset.py from the merged data.
        write_json(output_dir / "feature_name_manifest.json", _feature_name_manifest(feature_union))
    canonical_feature_columns = _canonical_feature_column_order(feature_union)
    with finalization.step("Stabilize feature chunk schemas"):
        schema_stabilization_audit = _stabilize_feature_chunk_schemas(
            chunk_rows=chunk_rows,
            canonical_columns=canonical_feature_columns,
        )
    chunk_blocking_counts: dict[str, int] = {}
    chunk_warning_counts: dict[str, int] = {}
    chunk_low_coverage_counts: dict[str, int] = {}
    built_chunk_rows = [row for row in chunk_rows if row.get("feature_rows") is not None]
    n_built_chunks = int(len(built_chunk_rows))
    for row in chunk_rows:
        for signal in row.get("blocking_signals", []) or []:
            key = str(signal)
            chunk_blocking_counts[key] = int(chunk_blocking_counts.get(key, 0) + 1)
        for signal in row.get("warning_signals", []) or []:
            key = str(signal)
            chunk_warning_counts[key] = int(chunk_warning_counts.get(key, 0) + 1)
        for signal in row.get("low_coverage_signals", []) or []:
            key = str(signal)
            chunk_low_coverage_counts[key] = int(chunk_low_coverage_counts.get(key, 0) + 1)
    chunk_blocking_union = sorted(chunk_blocking_counts)
    chunk_warning_union = sorted(chunk_warning_counts)

    # E.1/E.2: the pre-build validation slice only ever sees the trailing ~1.6
    # years, so it structurally cannot catch "sparse for most of history, fine
    # recently". Enforce over the ACTUAL per-chunk audits, which span the full
    # date range. A signal that is blocking, or below the exact-coverage floor,
    # in more than a threshold fraction of built chunks fails the build (in
    # strict mode) instead of only living in individual chunk manifests.
    era_fault_fraction = 0.34
    if n_built_chunks > 0:
        era_faults: dict[str, dict[str, Any]] = {}
        for signal, count in {**chunk_blocking_counts, **chunk_low_coverage_counts}.items():
            blocking_n = int(chunk_blocking_counts.get(signal, 0))
            low_cov_n = int(chunk_low_coverage_counts.get(signal, 0))
            worst = max(blocking_n, low_cov_n)
            if worst > era_fault_fraction * n_built_chunks:
                era_faults[signal] = {
                    "blocking_chunks": blocking_n,
                    "low_coverage_chunks": low_cov_n,
                    "total_built_chunks": n_built_chunks,
                }
        if era_faults:
            message = "per_era_signal_coverage_failed:" + json.dumps(era_faults, sort_keys=True)
            if strict_plan_signals:
                raise RuntimeError(message)
            print(f"[build_chunks] WARNING {message}", flush=True)
    with finalization.step("Write master chunk manifest"):
        manifest = {
            "generated_at": now_utc_iso(),
            "builder": "build_local_feature_chunks.py",
            "universe_annotation_pit": "current_snapshot_static",
            "raw_bundle_dir": str(raw_bundle_dir),
            "runtime_root": str(runtime_root),
            "date_range": {
                "requested_start_date": global_start.date().isoformat(),
                "requested_end_date": global_end.date().isoformat(),
                "detected_data_start_date": detected_start.date().isoformat(),
                "detected_data_end_date": detected_end.date().isoformat(),
            },
            "engine_limits": {
                "max_threads": int(args.threads),
                "duckdb_threads": int(args.duckdb_threads),
                "duckdb_memory_limit_mb": int(args.duckdb_memory_limit_mb),
                "max_tickers": int(args.max_tickers),
                "max_rows": int(args.max_rows),
            },
            "chunk_policy": {
                "chunk_months": int(args.chunk_months),
                "warmup_days": int(args.warmup_days),
                "forward_buffer_days": int(args.forward_buffer_days),
                "allow_proxies": bool(allow_proxies),
                "strict_plan_signals": bool(strict_plan_signals),
                "min_exact_signal_coverage_pct": float(args.min_exact_signal_coverage_pct),
            },
            "feature_hygiene_policy": {
                "dropped_dead_features": sorted(DEAD_EXPORT_COLUMNS),
                "schema_default_fill_values": dict(sorted(SCHEMA_DEFAULT_FILL_VALUES.items())),
                "availability_flags": dict(sorted(SPARSE_FEATURE_AVAILABILITY_FLAGS.items())),
            },
            "plan_signal_audit": json_ready(validation_audit),
            "chunk_signal_audit_summary": {
                "blocking_signals": chunk_blocking_union,
                "warning_signals": chunk_warning_union,
                "blocking_signal_counts": dict(sorted(chunk_blocking_counts.items())),
                "warning_signal_counts": dict(sorted(chunk_warning_counts.items())),
            },
            "feature_columns": canonical_feature_columns,
            "metadata_columns": metadata_union,
            "regime_columns": regime_union,
            "schema_stabilization_audit": schema_stabilization_audit,
            "n_feature_chunks": int(sum(1 for row in chunk_rows if row.get("feature_rows") is not None)),
            "n_windows": int(len(splits)),
            "chunks": chunk_rows,
            "artifacts": {
                "feature_chunk_dir": str(feature_chunk_dir),
                "metadata_chunk_dir": str(metadata_chunk_dir),
                "regime_chunk_dir": str(regime_chunk_dir),
                "chunk_manifest_dir": str(chunk_manifest_dir),
                "splits": str(output_dir / "northstar_walk_forward_splits.json"),
                "feature_name_manifest": str(output_dir / "feature_name_manifest.json"),
                "plan_signal_audit": str(output_dir / "plan_signal_audit.json"),
            },
        }
        write_json(output_dir / "local_chunked_dataset_manifest.json", manifest)
    print(
        json_ready(
            {
                "output_dir": str(output_dir),
                "n_chunks": int(len(chunk_rows)),
                "n_feature_columns": int(max(0, len(feature_union) - 3)),
                "n_windows": int(len(splits)),
                "blocking_signals": chunk_blocking_union,
                "warning_signals": chunk_warning_union,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
