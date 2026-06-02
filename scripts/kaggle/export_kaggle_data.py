#!/usr/bin/env python3
"""Export Northstar V4 validation artifacts for Kaggle."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors.gap9_academic_factors import Gap9AcademicFactors
from src.research.feature_factory import FeatureFactory
from src.research.dataset_manager import DatasetManager

DEFAULT_PRIMARY_SNAPSHOT = PROJECT_ROOT / "data/results/research/snapshots/2026/03/research_snapshot_20260326.parquet"
DAY3B_SUMMARY = PROJECT_ROOT / (
    "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization/"
    "20260325_204512_day3_model_comparison/summary.json"
)
DAY3B_EXPERIMENT_DIR = DAY3B_SUMMARY.parent
REGIME_LABELS_PATH = PROJECT_ROOT / "data/processed/regime_labels.parquet"
REGIME_FALLBACK_PATHS = [
    PROJECT_ROOT / "data/processed/intelligent_market_state.parquet",
    PROJECT_ROOT / "data/processed/market_state.parquet",
    PROJECT_ROOT / "data/canonical/macro/macro_regime_features.parquet",
]
MACRO_NEW_COLUMNS = [
    "rbi_repo_rate_level",
    "rbi_repo_rate_ts_z",
    "rbi_repo_rate_change_13w",
    "yield_curve_slope",
    "yield_curve_slope_ts_z",
    "cpi_surprise",
    "cpi_surprise_ts_z",
]
ALL_NEW_COLUMNS = Gap9AcademicFactors.OUTPUT_COLUMNS + MACRO_NEW_COLUMNS
NON_FEATURE_COLUMNS = {
    "date",
    "ticker",
    "close",
    "volume",
    "regime",
    "macro_regime",
    "regime_name",
    "valuation_regime",
    "forward_return_5d",
    "target_weekly_return",
    "fundamental_date",
    "availability_date",
    "availability_date_x",
    "availability_date_y",
    "screener_availability_date",
    "screener_shareholding_availability_date",
    "trade_date",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Kaggle-ready Northstar V4 validation data.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--config", default=PROJECT_ROOT / "config/research_policy.yaml", type=Path)
    parser.add_argument("--lookback-days", default=520, type=int)
    parser.add_argument("--start-date", default=None, type=str)
    parser.add_argument("--end-date", default=None, type=str)
    parser.add_argument("--sentiment-mode", choices=["full", "reduced"], default="reduced")
    parser.add_argument("--source-mode", choices=["auto", "snapshot", "raw"], default="auto")
    parser.add_argument("--snapshot-path", default=None, type=Path)
    parser.add_argument("--max-tickers", default=0, type=int)
    parser.add_argument("--max-rows", default=0, type=int)
    parser.add_argument("--low-resource-mode", choices=["auto", "true", "false"], default="false")
    parser.add_argument("--min-auto-tickers", default=200, type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _load_dataset_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    dataset_cfg = copy.deepcopy(payload.get("historical_research", {}).get("dataset", {}))
    if not isinstance(dataset_cfg, dict):
        raise ValueError("historical_research.dataset config missing or invalid")
    dataset_cfg["policy_config_path"] = str(config_path)
    dataset_cfg["use_gap9_academic_factors"] = True
    dataset_cfg["use_macro_features"] = True
    return dataset_cfg


def _read_snapshot(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"snapshot_not_found:{path}")
    frame = pd.read_parquet(path)
    if "date" not in frame.columns and "Date" in frame.columns:
        frame = frame.rename(columns={"Date": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["ticker"] = frame["ticker"].astype("string")
    frame = frame.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")
    return frame.reset_index(drop=True)


def _seed_window_source(summary_path: Path) -> list[dict[str, Any]]:
    seed_paths = sorted((summary_path.parent / "seed_results").glob("*.json"))
    for path in seed_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        full_result = payload.get("full_result", {})
        windows = full_result.get("windows", [])
        if isinstance(windows, list) and windows:
            out: list[dict[str, Any]] = []
            for idx, window in enumerate(windows, start=1):
                out.append(
                    {
                        "window_id": idx,
                        "train_start": str(window["train_start"])[:10],
                        "train_end": str(window["train_end"])[:10],
                        "test_start": str(window["test_start"])[:10],
                        "test_end": str(window["test_end"])[:10],
                    }
                )
            return out
    raise RuntimeError(f"unable_to_extract_windows_from_seed_results:{summary_path.parent}")


def _combine_snapshot_history(primary_path: Path, required_start: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    primary = _read_snapshot(primary_path)
    sources = [str(primary_path.relative_to(PROJECT_ROOT))]
    if primary.empty or primary["date"].min() <= required_start:
        return primary, sources

    snapshot_root = primary_path.parent
    candidates = sorted(snapshot_root.glob("research_snapshot_*.parquet"))
    older = [path for path in candidates if path.name < primary_path.name]
    older.sort(reverse=True)

    combined = primary.copy()
    for path in older:
        previous = _read_snapshot(path)
        if set(previous.columns) != set(primary.columns):
            continue
        prior_slice = previous.loc[previous["date"] < combined["date"].min()].copy()
        if prior_slice.empty:
            continue
        combined = pd.concat([prior_slice, combined], ignore_index=True)
        sources.append(str(path.relative_to(PROJECT_ROOT)))
        combined = (
            combined.sort_values(["date", "ticker"], kind="mergesort")
            .drop_duplicates(subset=["date", "ticker"], keep="last")
            .reset_index(drop=True)
        )
        if combined["date"].min() <= required_start:
            break
    return combined, sources


def _snapshot_stats(path: Path) -> dict[str, Any]:
    frame = pd.read_parquet(path, columns=["date", "ticker"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "ticker"])
    by_date = frame.groupby("date")["ticker"].nunique() if not frame.empty else pd.Series(dtype=int)
    return {
        "path": path,
        "n_rows": int(len(frame)),
        "n_tickers": int(frame["ticker"].astype("string").nunique()) if not frame.empty else 0,
        "date_min": frame["date"].min() if not frame.empty else pd.NaT,
        "date_max": frame["date"].max() if not frame.empty else pd.NaT,
        "daily_min_tickers": int(by_date.min()) if not by_date.empty else 0,
        "daily_max_tickers": int(by_date.max()) if not by_date.empty else 0,
    }


def _resolve_snapshot_path(args: argparse.Namespace) -> Path:
    if args.snapshot_path is not None:
        return args.snapshot_path.expanduser().resolve()
    if DEFAULT_PRIMARY_SNAPSHOT.exists():
        return DEFAULT_PRIMARY_SNAPSHOT
    snapshot_root = PROJECT_ROOT / "data/results/research/snapshots"
    candidates = sorted(snapshot_root.glob("**/research_snapshot_*.parquet"))
    if not candidates:
        raise FileNotFoundError("no_research_snapshot_found")
    return candidates[-1]


def _prepare_feature_panel_from_snapshot(
    args: argparse.Namespace,
    *,
    required_start: pd.Timestamp,
    snapshot_path: Path,
) -> tuple[pd.DataFrame, list[str]]:
    dataset_cfg = _load_dataset_config(args.config.resolve())
    dataset_cfg["sentiment_feature_mode"] = str(args.sentiment_mode)
    dataset_cfg["lookback_days"] = int(max(1, args.lookback_days))

    factory = FeatureFactory(
        target_horizon_days=int(dataset_cfg.get("target_horizon_days", 5) or 5),
        config=dataset_cfg,
    )
    panel, sources = _combine_snapshot_history(snapshot_path, required_start=required_start)
    panel = panel.drop(columns=ALL_NEW_COLUMNS, errors="ignore")
    panel = factory._merge_rbi_dbie_macro_features(panel)
    panel = factory._gap9_academic_block.transform(panel)
    panel = factory.apply_sentiment_feature_mode(panel)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel = panel.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")

    max_date = panel["date"].max()
    lookback_cutoff = max_date - pd.Timedelta(days=int(max(1, args.lookback_days)))
    effective_cutoff = min(lookback_cutoff, required_start)
    panel = panel.loc[panel["date"] >= effective_cutoff].copy()

    panel = _attach_target_weekly_return(panel)
    return panel.reset_index(drop=True), sources


def _attach_target_weekly_return(
    panel: pd.DataFrame,
    *,
    target_col_hint: str | None = None,
) -> pd.DataFrame:
    out = panel.copy()
    target = None
    for column in [target_col_hint, "target_weekly_return", "forward_return_5d", "forward_return"]:
        if column and column in out.columns:
            target = pd.to_numeric(out[column], errors="coerce")
            break
    if target is None and "ret_5d" in out.columns and "ticker" in out.columns:
        target = (
            pd.to_numeric(out["ret_5d"], errors="coerce")
            .groupby(out["ticker"], sort=False)
            .shift(-5)
        )
    if target is None:
        target = pd.Series(np.nan, index=out.index, dtype="float32")
    out["target_weekly_return"] = pd.to_numeric(target, errors="coerce").astype("float32")
    return out


def _prepare_feature_panel_from_raw(
    args: argparse.Namespace,
    *,
    required_start: pd.Timestamp,
) -> tuple[pd.DataFrame, list[str]]:
    dataset_cfg = _load_dataset_config(args.config.resolve())
    dataset_cfg["sentiment_feature_mode"] = str(args.sentiment_mode)
    dataset_cfg["lookback_days"] = int(max(1, args.lookback_days))
    dataset_cfg["use_gap9_academic_factors"] = True
    dataset_cfg["use_macro_features"] = True
    dataset_cfg["write_snapshot"] = False
    dataset_cfg["low_resource_mode"] = (
        str(args.low_resource_mode).strip().lower()
        if str(args.low_resource_mode).strip().lower() in {"true", "false", "auto"}
        else "false"
    )
    requested_tickers = int(args.max_tickers)
    if requested_tickers > 0:
        dataset_cfg["universe_size"] = max(int(dataset_cfg.get("universe_size", 0) or 0), requested_tickers)
    if int(args.max_tickers) >= 0:
        dataset_cfg["max_tickers"] = int(args.max_tickers)
    if int(args.max_rows) >= 0:
        dataset_cfg["max_rows"] = int(args.max_rows)
    if args.end_date:
        dataset_cfg["end_date"] = str(pd.Timestamp(args.end_date).date())
    # Kaggle export should preserve the full feature surface for downstream
    # notebook-side pruning rather than fail on the research laptop budget gate.
    dataset_cfg["feature_budget_enforce"] = False
    dataset_cfg["feature_correlation_enforce"] = False
    dataset_cfg["feature_correlation_skip"] = True
    dataset_cfg["feature_budget"] = max(
        int(dataset_cfg.get("feature_budget", 0) or 0),
        512,
        requested_tickers if requested_tickers > 0 else 0,
    )

    # Give rolling features enough warmup while ensuring the walk-forward train_start is available.
    warmup_days = max(365, int(args.lookback_days) + 180)
    if args.start_date:
        dataset_cfg["start_date"] = str(pd.Timestamp(args.start_date).date())
        dataset_cfg["lookback_days"] = 0
    else:
        dataset_cfg["start_date"] = str((required_start - pd.Timedelta(days=warmup_days)).date())

    manager = DatasetManager(project_root=PROJECT_ROOT, config=dataset_cfg)
    dataset = manager.build_research_dataset()
    panel = dataset.frame.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce")
    panel = panel.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")

    print(
        "[raw-build] dataset_ready "
        f"n_tickers={dataset.metadata.get('n_tickers')} "
        f"n_rows={dataset.metadata.get('n_rows')} "
        f"date_range={dataset.metadata.get('start_date')}..{dataset.metadata.get('end_date')} "
        f"low_resource={dataset.metadata.get('low_resource_mode_effective')}"
    )

    panel = _attach_target_weekly_return(
        panel,
        target_col_hint=str(dataset.metadata.get("target_col", "") or ""),
    )

    source_label = (
        "raw_build:"
        f"n_tickers={dataset.metadata.get('n_tickers')}|"
        f"n_rows={dataset.metadata.get('n_rows')}|"
        f"low_resource={dataset.metadata.get('low_resource_mode_effective')}"
    )
    return panel.reset_index(drop=True), [source_label]


def _prepare_feature_panel(
    args: argparse.Namespace,
    *,
    required_start: pd.Timestamp,
) -> tuple[pd.DataFrame, list[str]]:
    snapshot_path = _resolve_snapshot_path(args)
    snapshot_stats = _snapshot_stats(snapshot_path)

    use_raw = False
    if args.source_mode == "raw":
        use_raw = True
    elif args.source_mode == "snapshot":
        use_raw = False
    else:
        # Auto mode: avoid exporting obviously clipped low-resource snapshots.
        suspicious_row_cap = snapshot_stats["n_rows"] in {90000, 120000}
        too_few_tickers = snapshot_stats["n_tickers"] < int(max(1, args.min_auto_tickers))
        use_raw = suspicious_row_cap or too_few_tickers

    if use_raw:
        print(
            "[export] source_mode=raw "
            f"snapshot_reference={snapshot_path.name} "
            f"snapshot_tickers={snapshot_stats['n_tickers']} "
            f"snapshot_rows={snapshot_stats['n_rows']} "
            "rebuilding_from_raw=yes"
        )
        return _prepare_feature_panel_from_raw(args, required_start=required_start)

    print(
        f"[export] source_mode=snapshot path={snapshot_path.name} "
        f"tickers={snapshot_stats['n_tickers']} rows={snapshot_stats['n_rows']}"
    )
    return _prepare_feature_panel_from_snapshot(args, required_start=required_start, snapshot_path=snapshot_path)


def _select_feature_columns(panel: pd.DataFrame) -> list[str]:
    feature_cols: list[str] = []
    for column in panel.columns:
        name = str(column)
        if name in NON_FEATURE_COLUMNS:
            continue
        if name.startswith("forward_return_") or name.startswith("target_") or name.endswith("__realized"):
            continue
        if name.endswith("_raw") or "_raw_" in name or name.startswith("screener_raw_"):
            continue
        series = panel[column]
        if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
            continue
        if pd.api.types.is_numeric_dtype(series) or str(series.dtype) in {"bool", "boolean"}:
            feature_cols.append(name)
    return feature_cols


def _cast_feature_frame(panel: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = panel[["date", "ticker"] + feature_cols + ["target_weekly_return"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["ticker"] = out["ticker"].astype("string")
    numeric_cols = feature_cols + ["target_weekly_return"]
    for column in numeric_cols:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float32")
    return out


def _split_regime_components(regime_value: Any) -> tuple[str, str, str]:
    text = str(regime_value or "").strip()
    if not text:
        return "unknown", "unknown", "unknown"
    pieces = text.split("|")
    if len(pieces) >= 3:
        return pieces[0], pieces[1], pieces[2]
    return (
        pieces[0] if len(pieces) >= 1 else "unknown",
        pieces[1] if len(pieces) >= 2 else "unknown",
        "unknown",
    )


def _load_optional_market_metrics() -> pd.DataFrame:
    for path in REGIME_FALLBACK_PATHS[:2]:
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        work = frame.copy()
        if "date" not in work.columns and "Date" in work.columns:
            work["date"] = work["Date"]
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        work = work.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        if work.empty:
            continue
        merged = pd.DataFrame({"date": work["date"]}).drop_duplicates()
        if "regime_modifier" in work.columns:
            merged["regime_modifier"] = pd.to_numeric(work["regime_modifier"], errors="coerce")
        else:
            merged["regime_modifier"] = np.nan
        if "risk_on_probability" in work.columns:
            merged["macro_risk_on"] = pd.to_numeric(work["risk_on_probability"], errors="coerce")
        elif "risk_on" in work.columns:
            merged["macro_risk_on"] = pd.to_numeric(work["risk_on"], errors="coerce")
        else:
            merged["macro_risk_on"] = np.nan
        if "stress_level" in work.columns:
            merged["macro_stress_level"] = pd.to_numeric(work["stress_level"], errors="coerce")
        elif "stress_score" in work.columns:
            merged["macro_stress_level"] = pd.to_numeric(work["stress_score"], errors="coerce")
        else:
            merged["macro_stress_level"] = np.nan
        merged = merged.groupby("date", as_index=False).last()
        return merged
    return pd.DataFrame(
        columns=["date", "regime_modifier", "macro_risk_on", "macro_stress_level"]
    )


def _load_regime_labels() -> pd.DataFrame:
    optional_metrics = _load_optional_market_metrics()

    if REGIME_LABELS_PATH.exists():
        frame = pd.read_parquet(REGIME_LABELS_PATH)
        work = frame.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        work = work.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        work["regime"] = work["regime"].astype("string")
        work["vol_regime"] = work.get("vol_label", pd.Series(index=work.index, dtype="string")).astype("string")
        work["trend_regime"] = work.get("trend_label", pd.Series(index=work.index, dtype="string")).astype("string")
        work["cycle_regime"] = work.get("macro_label", pd.Series(index=work.index, dtype="string")).astype("string")
    else:
        work = pd.DataFrame()
        for path in REGIME_FALLBACK_PATHS:
            if not path.exists():
                continue
            frame = pd.read_parquet(path)
            if frame.empty:
                continue
            candidate = frame.copy()
            if "date" not in candidate.columns and "Date" in candidate.columns:
                candidate["date"] = candidate["Date"]
            candidate["date"] = pd.to_datetime(candidate["date"], errors="coerce").dt.normalize()
            candidate = candidate.dropna(subset=["date"]).sort_values("date", kind="mergesort")
            if candidate.empty:
                continue
            if "regime" not in candidate.columns:
                if "macro_regime_label" in candidate.columns:
                    candidate["regime"] = candidate["macro_regime_label"].astype("string")
                else:
                    candidate["regime"] = "unknown"
            components = candidate["regime"].map(_split_regime_components)
            candidate["vol_regime"] = components.map(lambda x: x[0]).astype("string")
            candidate["trend_regime"] = components.map(lambda x: x[1]).astype("string")
            candidate["cycle_regime"] = components.map(lambda x: x[2]).astype("string")
            work = candidate
            break
        if work.empty:
            raise FileNotFoundError("no_regime_label_source_found")

    work = work[["date", "regime", "vol_regime", "trend_regime", "cycle_regime"]].copy()
    for column in ["regime", "vol_regime", "trend_regime", "cycle_regime"]:
        work[column] = work[column].fillna("unknown").astype("string")
    if optional_metrics.empty:
        work["regime_modifier"] = np.nan
        work["macro_risk_on"] = np.nan
        work["macro_stress_level"] = np.nan
    else:
        work = work.merge(optional_metrics, on="date", how="left")
        for column in ["regime_modifier", "macro_risk_on", "macro_stress_level"]:
            if column not in work.columns:
                work[column] = np.nan
    return work.sort_values("date", kind="mergesort").reset_index(drop=True)


def _dominant_regime(regime_df: pd.DataFrame, test_start: str, test_end: str) -> str:
    if regime_df.empty:
        return "unknown"
    start = pd.Timestamp(test_start).normalize()
    end = pd.Timestamp(test_end).normalize()
    mask = regime_df["date"].between(start, end)
    if not bool(mask.any()):
        return "unknown"
    counts = regime_df.loc[mask, "regime"].astype("string").fillna("unknown").value_counts()
    return str(counts.index[0]) if not counts.empty else "unknown"


def _extract_walk_forward_splits(regime_df: pd.DataFrame) -> list[dict[str, Any]]:
    windows = _seed_window_source(DAY3B_SUMMARY)
    splits: list[dict[str, Any]] = []
    for window in windows:
        splits.append(
            {
                "window_id": int(window["window_id"]),
                "train_start": str(window["train_start"]),
                "train_end": str(window["train_end"]),
                "test_start": str(window["test_start"]),
                "test_end": str(window["test_end"]),
                "regime": _dominant_regime(regime_df, window["test_start"], window["test_end"]),
            }
        )
    return splits


def _generate_walk_forward_splits(
    panel_dates: pd.Series,
    regime_df: pd.DataFrame,
    *,
    target_windows: int = 20,
    train_periods: int = 252,
    test_periods: int = 63,
    step_periods: int = 63,
) -> list[dict[str, Any]]:
    unique_dates = (
        pd.Series(pd.to_datetime(panel_dates, errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    n_dates = len(unique_dates)
    if n_dates < train_periods + test_periods:
        raise ValueError(f"not_enough_dates_for_walk_forward:{n_dates}<{train_periods + test_periods}")

    windows: list[dict[str, Any]] = []
    for test_start_idx in range(train_periods, n_dates - test_periods + 1, step_periods):
        train_start_idx = max(0, test_start_idx - train_periods)
        train_end_idx = test_start_idx - 1
        test_end_idx = min(n_dates - 1, test_start_idx + test_periods - 1)
        windows.append(
            {
                "window_id": len(windows) + 1,
                "train_start": str(pd.Timestamp(unique_dates[train_start_idx]).date()),
                "train_end": str(pd.Timestamp(unique_dates[train_end_idx]).date()),
                "test_start": str(pd.Timestamp(unique_dates[test_start_idx]).date()),
                "test_end": str(pd.Timestamp(unique_dates[test_end_idx]).date()),
            }
        )

    if target_windows > 0 and len(windows) > target_windows:
        windows = windows[-target_windows:]

    splits: list[dict[str, Any]] = []
    for idx, window in enumerate(windows, start=1):
        splits.append(
            {
                "window_id": idx,
                "train_start": window["train_start"],
                "train_end": window["train_end"],
                "test_start": window["test_start"],
                "test_end": window["test_end"],
                "regime": _dominant_regime(regime_df, window["test_start"], window["test_end"]),
            }
        )
    return splits


def _resolve_walk_forward_splits(
    regime_df: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    prefer_dynamic: bool = False,
) -> list[dict[str, Any]]:
    seed_splits = _extract_walk_forward_splits(regime_df)
    panel_dates = pd.to_datetime(panel["date"], errors="coerce")
    panel_min = pd.Timestamp(panel_dates.min()).normalize()
    panel_max = pd.Timestamp(panel_dates.max()).normalize()
    seed_min = min(pd.Timestamp(split["train_start"]) for split in seed_splits).normalize()
    seed_max = max(pd.Timestamp(split["test_end"]) for split in seed_splits).normalize()

    if prefer_dynamic or panel_min > seed_min or panel_max < seed_max:
        print(
            "[export] regenerating walk-forward splits "
            f"for panel_range={panel_min.date()}..{panel_max.date()} "
            f"(seed_range={seed_min.date()}..{seed_max.date()})"
        )
        return _generate_walk_forward_splits(panel_dates, regime_df, target_windows=len(seed_splits))

    return seed_splits


def _file_size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024.0 * 1024.0), 2)


def _write_atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp.{int(time.time())}")
    frame.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)


def _write_atomic_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp.{int(time.time())}")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _print_feature_summary(path: Path, frame: pd.DataFrame, feature_cols: list[str]) -> None:
    date_min = pd.to_datetime(frame["date"], errors="coerce").min()
    date_max = pd.to_datetime(frame["date"], errors="coerce").max()
    print(path.name)
    print(f"  rows: {len(frame)}")
    print(f"  tickers: {frame['ticker'].nunique()}")
    print(f"  date_range: {date_min:%Y-%m-%d} to {date_max:%Y-%m-%d}")
    print(f"  feature_cols: {len(feature_cols)}")
    print(f"  target_non_null_pct: {frame['target_weekly_return'].notna().mean() * 100.0:.2f}%")
    if path.exists():
        print(f"  file_size_mb: {_file_size_mb(path)}")


def _print_split_summary(path: Path, splits: list[dict[str, Any]]) -> None:
    starts = [pd.Timestamp(split["train_start"]) for split in splits]
    ends = [pd.Timestamp(split["test_end"]) for split in splits]
    print(path.name)
    print(f"  windows: {len(splits)}")
    print(f"  earliest_train_start: {min(starts):%Y-%m-%d}")
    print(f"  latest_test_end: {max(ends):%Y-%m-%d}")
    print(f"  total_span_days: {(max(ends) - min(starts)).days}")


def _print_regime_summary(path: Path, regime_df: pd.DataFrame) -> None:
    counts = regime_df["regime"].astype("string").fillna("unknown").value_counts().to_dict()
    date_min = regime_df["date"].min()
    date_max = regime_df["date"].max()
    print(path.name)
    print(f"  rows: {len(regime_df)}")
    print(f"  date_range: {date_min:%Y-%m-%d} to {date_max:%Y-%m-%d}")
    print(f"  unique_regimes: {regime_df['regime'].nunique()}")
    print(f"  regime_distribution: {counts}")


def _json_ready(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, )):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    return value


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    existing_features_path = output_dir / "northstar_features.parquet"
    if existing_features_path.exists():
        mtime = datetime.fromtimestamp(existing_features_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(
            "[export] existing_artifact_detected "
            f"path={existing_features_path} "
            f"mtime={mtime} "
            "note=old_files_remain_until_new_export_finishes"
        )
    regime_df = _load_regime_labels()
    seed_splits = _extract_walk_forward_splits(regime_df)
    earliest_required_start = min(pd.Timestamp(split["train_start"]) for split in seed_splits)

    panel, sources = _prepare_feature_panel(args, required_start=earliest_required_start)
    splits = _resolve_walk_forward_splits(
        regime_df,
        panel,
        prefer_dynamic=bool(args.start_date),
    )
    feature_cols = _select_feature_columns(panel)
    features_df = _cast_feature_frame(panel, feature_cols)
    features_path = output_dir / "northstar_features.parquet"
    splits_path = output_dir / "northstar_walk_forward_splits.json"
    regime_path = output_dir / "northstar_regime_labels.parquet"
    manifest_path = output_dir / "northstar_export_manifest.json"

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic_parquet(features_df, features_path)
        _write_atomic_text(splits_path, json.dumps(_json_ready(splits), indent=2))
        _write_atomic_parquet(regime_df, regime_path)

        manifest = {
            "exported_at": datetime.now().isoformat(),
            "source_mode": str(args.source_mode),
            "sources": _json_ready(sources),
            "n_rows": int(len(features_df)),
            "n_tickers": int(features_df["ticker"].nunique()),
            "date_min": str(pd.to_datetime(features_df["date"], errors="coerce").min()),
            "date_max": str(pd.to_datetime(features_df["date"], errors="coerce").max()),
            "n_features": int(len(feature_cols)),
            "target_non_null_pct": float(features_df["target_weekly_return"].notna().mean()),
        }
        _write_atomic_text(manifest_path, json.dumps(_json_ready(manifest), indent=2))

    _print_feature_summary(features_path, features_df, feature_cols)
    _print_split_summary(splits_path, splits)
    _print_regime_summary(regime_path, regime_df)

    source_tickers = panel["ticker"].nunique()
    min_ticker_floor = min(100, int(source_tickers))
    gap9_columns = Gap9AcademicFactors.OUTPUT_COLUMNS
    assert features_df["target_weekly_return"].notna().mean() > 0.70, "Target coverage too low"
    assert len(splits) >= 8, "Too few walk-forward windows"
    assert features_df["ticker"].nunique() >= min_ticker_floor, "Too few tickers after export"
    assert all(column in features_df.columns for column in gap9_columns), "Gap 9 features missing"
    assert features_df.select_dtypes("float64").shape[1] == 0, "float64 columns found, should all be float32"

    total_size_mb = 0.0
    if not args.dry_run:
        total_size_mb = round(
            _file_size_mb(features_path)
            + _file_size_mb(splits_path)
            + _file_size_mb(regime_path)
            + _file_size_mb(manifest_path),
            2,
        )

    print("EXPORT COMPLETE")
    print(f"  output_dir: {output_dir}")
    print(f"  total_size_mb: {total_size_mb if not args.dry_run else 'dry-run'}")
    print("  ready_for_kaggle_upload: YES")
    print(f"  source_snapshots: {sources}")
    print(f"  final_tickers: {features_df['ticker'].nunique()}")
    print(f"  final_rows: {len(features_df)}")
    print(f"  final_date_range: {pd.to_datetime(features_df['date'], errors='coerce').min():%Y-%m-%d} to {pd.to_datetime(features_df['date'], errors='coerce').max():%Y-%m-%d}")
    if not args.dry_run:
        print(f"  manifest: {manifest_path}")
    if args.dry_run:
        print("  note: dry-run mode did not write files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
