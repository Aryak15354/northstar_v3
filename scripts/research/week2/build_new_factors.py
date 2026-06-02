#!/usr/bin/env python3
"""
Builds Northstar week-2 research factors on the Mac-side Kaggle export.

This script:
1. Loads the existing Kaggle export from ~/Desktop/northstar_kaggle_data
2. Adds four new factor groups
3. Validates that the new factors do not introduce lookahead bias
4. Prints factor IC diagnostics
5. Writes the augmented parquet plus metadata to ~/Desktop/northstar_kaggle_data_v2
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ConstantInputWarning, spearmanr


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = Path.home() / "Desktop" / "northstar_kaggle_data"
OUTPUT_DIR = Path.home() / "Desktop" / "northstar_kaggle_data_v2"
INPUT_PARQUET = INPUT_DIR / "northstar_features.parquet"
OUTPUT_PARQUET = OUTPUT_DIR / "northstar_features_v2.parquet"
OUTPUT_METADATA = OUTPUT_DIR / "northstar_factor_metadata_v2.json"
SUPPORT_FILES = (
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
)
EPSILON = 0.001
DEFAULT_EXPECTED_MIN_TICKERS = 500
DEFAULT_EXPECTED_START_DATE = "2019-01-01"

EXPECTED_IC_HINTS = {
    "eps_revision_accel": 0.012,
    "eps_revision_direction": 0.008,
    "combined_revision_score": 0.014,
    "combined_revision_score_cs_z": 0.015,
    "combined_revision_score_cs_rank": 0.015,
    "roe_within_sector_cs_rank": 0.010,
    "roe_within_sector_cs_z": 0.009,
    "earnings_quality_within_sector_cs_rank": 0.010,
    "earnings_quality_within_sector_cs_z": 0.009,
    "sector_quality_composite": 0.012,
    "sector_quality_composite_cs_rank": 0.012,
    "mom_20d_vol_adj": 0.007,
    "mom_60d_vol_adj": 0.006,
    "ret_5d_vol_adj": 0.005,
    "mom_20d_vol_adj_sector_rel": 0.008,
    "mom_20d_vol_adj_cs_rank": 0.008,
    "mom_20d_vol_adj_cs_z": 0.008,
    "pledge_short_signal": 0.008,
    "pledge_bulk_stress": 0.010,
    "pledge_bulk_stress_cs_z": 0.010,
    "smart_money_consensus": 0.011,
    "smart_money_consensus_cs_z": 0.011,
}

SUMMARY_COLUMNS = [
    "eps_revision_accel",
    "eps_revision_direction",
    "combined_revision_score_cs_z",
    "roe_within_sector_cs_rank",
    "sector_quality_composite_cs_rank",
    "mom_20d_vol_adj_cs_rank",
    "pledge_short_signal",
    "smart_money_consensus_cs_z",
]


@dataclass
class FactorIC:
    mean_ic: float
    t_stat: float
    hit_rate: float
    n_dates: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build week-2 research factors on the Kaggle export.")
    parser.add_argument("--input-parquet", type=Path, default=INPUT_PARQUET)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--expected-min-tickers", type=int, default=DEFAULT_EXPECTED_MIN_TICKERS)
    parser.add_argument("--expected-start-date", type=str, default=DEFAULT_EXPECTED_START_DATE)
    parser.add_argument(
        "--fail-on-coverage",
        action="store_true",
        help="Exit non-zero when the source export does not satisfy the expected universe/date coverage.",
    )
    return parser.parse_args()


def pct_rank(series: pd.Series) -> pd.Series:
    """Stable 0-1 percentile rank within a group."""

    out = pd.Series(np.nan, index=series.index, dtype=float)
    valid = series.notna()
    n_valid = int(valid.sum())
    if n_valid == 0:
        return out
    if n_valid == 1:
        out.loc[valid] = 0.5
        return out

    ranks = series.loc[valid].rank(method="average")
    out.loc[valid] = (ranks - 1.0) / float(n_valid - 1)
    return out


def zscore_group(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score with safe handling for tiny groups."""

    out = pd.Series(np.nan, index=series.index, dtype=float)
    valid = series.notna()
    if int(valid.sum()) == 0:
        return out

    values = pd.to_numeric(series.loc[valid], errors="coerce").astype(float)
    mean_val = float(values.mean())
    std_val = float(values.std(ddof=0))
    if not np.isfinite(std_val) or std_val < 1e-12:
        out.loc[valid] = 0.0
        return out

    out.loc[valid] = ((values - mean_val) / std_val).clip(-8.0, 8.0)
    return out


def group_rank(df: pd.DataFrame, value_col: str, group_cols: list[str], min_size: int = 1) -> pd.Series:
    counts = df.groupby(group_cols, sort=False)[value_col].transform(lambda s: s.notna().sum())
    enough = counts >= int(min_size)
    out = pd.Series(np.nan, index=df.index, dtype=float)
    if bool(enough.any()):
        out.loc[enough] = (
            df.loc[enough]
            .groupby(group_cols, sort=False)[value_col]
            .transform(pct_rank)
            .astype(float)
        )
    return out


def group_zscore(df: pd.DataFrame, value_col: str, group_cols: list[str], min_size: int = 1) -> pd.Series:
    counts = df.groupby(group_cols, sort=False)[value_col].transform(lambda s: s.notna().sum())
    enough = counts >= int(min_size)
    out = pd.Series(np.nan, index=df.index, dtype=float)
    if bool(enough.any()):
        out.loc[enough] = (
            df.loc[enough]
            .groupby(group_cols, sort=False)[value_col]
            .transform(zscore_group)
            .astype(float)
        )
    return out


def mean_of_available(columns: list[pd.Series]) -> pd.Series:
    return pd.concat(columns, axis=1).mean(axis=1, skipna=True)


def infer_sector_labels(df: pd.DataFrame) -> pd.Series:
    if "sector" in df.columns:
        return df["sector"].astype("string").fillna("UNKNOWN")

    sector_dummy_cols = [c for c in df.columns if c.startswith("sector_dummy_")]
    if not sector_dummy_cols:
        return pd.Series("UNKNOWN", index=df.index, dtype="string")

    dummy_frame = df[sector_dummy_cols].fillna(0.0).astype(float)
    values = dummy_frame.to_numpy(dtype=float)
    if values.size == 0:
        return pd.Series("UNKNOWN", index=df.index, dtype="string")

    max_idx = values.argmax(axis=1)
    max_val = values.max(axis=1)
    clean_names = np.asarray(
        [c.replace("sector_dummy_", "").replace("_", " ") for c in sector_dummy_cols],
        dtype=object,
    )
    labels = np.full(len(df), "UNKNOWN", dtype=object)
    has_signal = max_val > 0
    labels[has_signal] = clean_names[max_idx[has_signal]]
    return pd.Series(labels, index=df.index, dtype="string")


def first_available(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    series = pd.Series(np.nan, index=df.index, dtype=float)
    for col in candidates:
        if col in df.columns:
            current = pd.to_numeric(df[col], errors="coerce")
            series = series.where(series.notna(), current)
    return series


def ensure_rank(df: pd.DataFrame, raw_col: str, rank_col: str) -> pd.Series:
    if rank_col in df.columns:
        return pd.to_numeric(df[rank_col], errors="coerce")
    if raw_col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return df.groupby("date", sort=False)[raw_col].transform(pct_rank)


def sparse_event_projection(
    series: pd.Series,
    *,
    lag_events: int = 4,
    std_window: int = 8,
    sign_window: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """
    Builds quarterly-like event features from a sparse, forward-carried factor series.

    The export is daily, but earnings surprise values arrive on event dates and are often
    carried forward or sparsely populated. We therefore:
    1. keep only non-null observations,
    2. collapse consecutive duplicate values so one earnings print counts as one event,
    3. compute lag/std/sign metrics on the event series,
    4. forward-fill the event-level outputs back to daily rows.
    """

    full_index = series.index
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        empty = pd.Series(np.nan, index=full_index, dtype=float)
        return empty, empty

    is_new_event = values.ne(values.shift())
    event_values = values.loc[is_new_event].astype(float)
    if event_values.empty:
        empty = pd.Series(np.nan, index=full_index, dtype=float)
        return empty, empty

    lagged = event_values.shift(lag_events)
    rolling_std = event_values.rolling(std_window, min_periods=4).std()
    accel_events = (event_values - lagged) / rolling_std.replace(0.0, np.nan)
    direction_events = event_values.rolling(sign_window, min_periods=sign_window).apply(
        lambda x: 1.0 if float(np.sum(np.asarray(x) > 0.0)) >= 2.0 else -1.0,
        raw=True,
    )

    accel = pd.Series(np.nan, index=full_index, dtype=float)
    direction = pd.Series(np.nan, index=full_index, dtype=float)
    accel.loc[event_values.index] = accel_events.to_numpy(dtype=float)
    direction.loc[event_values.index] = direction_events.to_numpy(dtype=float)

    accel = accel.ffill()
    direction = direction.ffill()

    valid_mask = series.notna()
    accel.loc[~valid_mask] = np.nan
    direction.loc[~valid_mask] = np.nan
    return accel, direction


def compute_factor_ic(df: pd.DataFrame, factor_col: str, target_col: str) -> FactorIC:
    ics: list[float] = []
    for _, group in df.groupby("date", sort=True):
        local = group[[factor_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 10:
            continue
        x = local[factor_col].to_numpy(dtype=float)
        y = local[target_col].to_numpy(dtype=float)
        if np.nanstd(x) <= 1e-12 or np.nanstd(y) <= 1e-12:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=ConstantInputWarning)
            corr, _ = spearmanr(x, y)
        if np.isfinite(corr):
            ics.append(float(corr))

    if not ics:
        return FactorIC(mean_ic=float("nan"), t_stat=float("nan"), hit_rate=float("nan"), n_dates=0)

    arr = np.asarray(ics, dtype=float)
    mean_ic = float(arr.mean())
    std_ic = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    stderr = std_ic / math.sqrt(len(arr)) if len(arr) > 1 else 0.0
    t_stat = float(mean_ic / stderr) if abs(stderr) > 1e-12 else float("nan")
    hit_rate = float(np.mean(arr > 0.0))
    return FactorIC(mean_ic=mean_ic, t_stat=t_stat, hit_rate=hit_rate, n_dates=int(len(arr)))


def build_eps_revision_factors(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    eps_signal = first_available(work, ["eps_sue", "eps_sue_decay"])
    rev_signal = first_available(work, ["rev_sue", "rev_sue_decay"])

    work["__eps_signal"] = eps_signal
    work["__rev_signal"] = rev_signal

    work["__eps_revision_accel_raw"] = (
        work.groupby("ticker", sort=False)["__eps_signal"]
        .transform(lambda s: sparse_event_projection(s)[0])
        .astype(float)
    )
    work["eps_revision_direction"] = (
        work.groupby("ticker", sort=False)["__eps_signal"]
        .transform(lambda s: sparse_event_projection(s)[1])
        .astype(float)
    )
    work["__rev_revision_accel_raw"] = (
        work.groupby("ticker", sort=False)["__rev_signal"]
        .transform(lambda s: sparse_event_projection(s)[0])
        .astype(float)
    )

    work["eps_revision_accel"] = group_zscore(work, "__eps_revision_accel_raw", ["date"])

    eps_revision_composite = mean_of_available(
        [
            work["__eps_revision_accel_raw"],
            work["eps_revision_direction"],
            work["__eps_signal"],
        ]
    )
    rev_revision_composite = mean_of_available(
        [
            work["__rev_revision_accel_raw"],
            work["__rev_signal"],
        ]
    )
    work["combined_revision_score"] = 0.6 * eps_revision_composite + 0.4 * rev_revision_composite
    work["combined_revision_score_cs_z"] = group_zscore(work, "combined_revision_score", ["date"])
    work["combined_revision_score_cs_rank"] = group_rank(work, "combined_revision_score", ["date"])

    return work.drop(columns=["__eps_signal", "__rev_signal", "__eps_revision_accel_raw", "__rev_revision_accel_raw"])


def build_sector_relative_quality(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["__sector_label"] = infer_sector_labels(work)

    work["roe_within_sector_cs_rank"] = group_rank(work, "roe", ["date", "__sector_label"], min_size=5)
    work["roe_within_sector_cs_z"] = group_zscore(work, "roe", ["date", "__sector_label"], min_size=5)
    work["earnings_quality_within_sector_cs_rank"] = group_rank(
        work,
        "earnings_quality_ratio",
        ["date", "__sector_label"],
        min_size=5,
    )
    work["earnings_quality_within_sector_cs_z"] = group_zscore(
        work,
        "earnings_quality_ratio",
        ["date", "__sector_label"],
        min_size=5,
    )

    composite_raw = mean_of_available(
        [
            work["roe_within_sector_cs_rank"],
            work["earnings_quality_within_sector_cs_rank"],
        ]
    )
    work["sector_quality_composite"] = group_zscore(
        pd.DataFrame({"date": work["date"], "__composite": composite_raw}),
        "__composite",
        ["date"],
    )
    work["sector_quality_composite_cs_rank"] = group_rank(
        pd.DataFrame({"date": work["date"], "__composite": composite_raw}),
        "__composite",
        ["date"],
    )

    return work.drop(columns=["__sector_label"])


def build_vol_adjusted_momentum(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["__sector_label"] = infer_sector_labels(work)

    mom_20d = first_available(work, ["mom_20d", "ret_20d"])
    mom_60d = first_available(work, ["mom_60d", "ret_60d"])
    ret_5d = first_available(work, ["ret_5d"])
    vol_20d = first_available(work, ["vol_20d"])
    vol_60d = first_available(work, ["vol_60d"])

    work["mom_20d_vol_adj"] = mom_20d / (vol_20d.abs() + EPSILON)
    work["mom_60d_vol_adj"] = mom_60d / (vol_60d.abs() + EPSILON)
    work["ret_5d_vol_adj"] = ret_5d / (vol_20d.abs() + EPSILON)

    sector_median = work.groupby(["date", "__sector_label"], sort=False)["mom_20d_vol_adj"].transform("median")
    work["mom_20d_vol_adj_sector_rel"] = work["mom_20d_vol_adj"] - sector_median
    work["mom_20d_vol_adj_cs_rank"] = group_rank(work, "mom_20d_vol_adj", ["date"])
    work["mom_20d_vol_adj_cs_z"] = group_zscore(work, "mom_20d_vol_adj", ["date"])

    return work.drop(columns=["__sector_label"])


def build_pledge_and_smart_money(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    pledge_rank = ensure_rank(work, "pledge_pct", "pledge_pct_cs_rank")
    bulk_21_rank = ensure_rank(work, "bulk_net_volume_21d", "bulk_net_volume_21d_cs_rank")
    inst_rank = ensure_rank(work, "bulk_net_institutional_21d", "bulk_net_institutional_21d_cs_rank")
    fii_rank = ensure_rank(work, "screener_fii_change_1q", "screener_fii_change_1q_cs_rank")

    work["pledge_short_signal"] = -pledge_rank
    bulk_is_selling = pd.to_numeric(work.get("bulk_net_volume_21d"), errors="coerce") < 0.0
    work["pledge_bulk_stress"] = np.where(
        bulk_is_selling,
        work["pledge_short_signal"].fillna(0.0) * (-bulk_21_rank.fillna(0.0)),
        0.0,
    )
    work["pledge_bulk_stress_cs_z"] = group_zscore(work, "pledge_bulk_stress", ["date"])

    inst_center = (inst_rank - 0.5) * 2.0
    fii_center = (fii_rank - 0.5) * 2.0
    same_direction = np.sign(inst_center) == np.sign(fii_center)
    agreement_strength = np.abs(inst_center * fii_center)
    work["smart_money_consensus"] = np.where(
        same_direction,
        np.sign(inst_center + fii_center) * agreement_strength,
        -agreement_strength,
    )
    work["smart_money_consensus_cs_z"] = group_zscore(work, "smart_money_consensus", ["date"])

    return work


def apply_all_factor_groups(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    original_columns = list(df.columns)
    work = (
        df.copy()
        .assign(date=pd.to_datetime(df["date"], errors="coerce"))
        .sort_values(["ticker", "date"], kind="mergesort")
        .reset_index(drop=False)
        .rename(columns={"index": "__original_index"})
    )

    work = build_eps_revision_factors(work)
    work = build_sector_relative_quality(work)
    work = build_vol_adjusted_momentum(work)
    work = build_pledge_and_smart_money(work)

    new_columns = [c for c in work.columns if c not in original_columns and not c.startswith("__")]
    work = (
        work.sort_values("__original_index", kind="mergesort")
        .drop(columns=[c for c in work.columns if c.startswith("__")], errors="ignore")
        .reset_index(drop=True)
    )
    return work, new_columns


def validate_no_lookahead(base_df: pd.DataFrame, full_df: pd.DataFrame, new_columns: list[str]) -> dict[str, Any]:
    unique_dates = sorted(pd.to_datetime(base_df["date"], errors="coerce").dropna().unique())
    if len(unique_dates) < 6:
        sample_dates = unique_dates
    else:
        usable = unique_dates[4:]
        stride = max(1, len(usable) // 6)
        sample_dates = usable[::stride][:6]

    failures: list[dict[str, Any]] = []
    for date_value in sample_dates:
        prefix = base_df.loc[pd.to_datetime(base_df["date"], errors="coerce") <= pd.Timestamp(date_value)].copy()
        rebuilt_prefix, _ = apply_all_factor_groups(prefix)
        full_slice = full_df.loc[pd.to_datetime(full_df["date"], errors="coerce") == pd.Timestamp(date_value), ["date", "ticker"] + new_columns]
        prefix_slice = rebuilt_prefix.loc[pd.to_datetime(rebuilt_prefix["date"], errors="coerce") == pd.Timestamp(date_value), ["date", "ticker"] + new_columns]
        merged = full_slice.merge(prefix_slice, on=["date", "ticker"], how="outer", suffixes=("_full", "_prefix"))

        for col in new_columns:
            left = pd.to_numeric(merged[f"{col}_full"], errors="coerce")
            right = pd.to_numeric(merged[f"{col}_prefix"], errors="coerce")
            mismatch = left.isna() ^ right.isna()
            if bool(mismatch.any()):
                failures.append(
                    {
                        "date": str(pd.Timestamp(date_value).date()),
                        "column": col,
                        "reason": "nan_mismatch",
                    }
                )
                continue
            diff_arr = np.abs(left.to_numpy(dtype=float) - right.to_numpy(dtype=float))
            finite_mask = np.isfinite(diff_arr)
            if not bool(finite_mask.any()):
                continue
            diff = float(diff_arr[finite_mask].max())
            if np.isfinite(diff) and diff > 1e-10:
                failures.append(
                    {
                        "date": str(pd.Timestamp(date_value).date()),
                        "column": col,
                        "reason": "value_mismatch",
                        "max_abs_diff": float(diff),
                    }
                )

    return {
        "passed": not failures,
        "checked_dates": [str(pd.Timestamp(x).date()) for x in sample_dates],
        "failures": failures[:50],
        "failure_count": len(failures),
    }


def audit_dataset_coverage(
    df: pd.DataFrame,
    *,
    expected_min_tickers: int,
    expected_start_date: str,
) -> dict[str, Any]:
    date_series = pd.to_datetime(df["date"], errors="coerce")
    ticker_count = int(df["ticker"].astype(str).nunique())
    date_min = pd.Timestamp(date_series.min()).normalize() if date_series.notna().any() else None
    date_max = pd.Timestamp(date_series.max()).normalize() if date_series.notna().any() else None
    expected_start = pd.Timestamp(expected_start_date).normalize()
    coverage_ok = bool(
        ticker_count >= int(expected_min_tickers)
        and date_min is not None
        and date_min <= expected_start
    )
    return {
        "rows": int(len(df)),
        "tickers": ticker_count,
        "date_min": str(date_min.date()) if date_min is not None else None,
        "date_max": str(date_max.date()) if date_max is not None else None,
        "expected_min_tickers": int(expected_min_tickers),
        "expected_start_date": str(expected_start.date()),
        "coverage_ok": coverage_ok,
        "coverage_note": (
            "source export meets the requested 500-name / 2019-start standard"
            if coverage_ok
            else "source export is below the requested 500-name / 2019-start standard"
        ),
    }


def audit_support_splits(
    output_dir: Path,
    dataset_start: pd.Timestamp,
    dataset_end: pd.Timestamp,
) -> dict[str, Any]:
    splits_path = output_dir / "northstar_walk_forward_splits.json"
    if not splits_path.exists():
        return {"present": False, "coverage_ok": False, "note": "walk-forward splits file missing"}

    try:
        splits = json.loads(splits_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"present": True, "coverage_ok": False, "note": f"failed to parse split file: {exc}"}

    if not splits:
        return {"present": True, "coverage_ok": False, "note": "split file is empty"}

    split_min = min(pd.Timestamp(split["train_start"]) for split in splits).normalize()
    split_max = max(pd.Timestamp(split["test_end"]) for split in splits).normalize()
    dataset_start = pd.Timestamp(dataset_start).normalize()
    dataset_end = pd.Timestamp(dataset_end).normalize()
    warmup_days = int((split_min - dataset_start).days)
    split_ok = split_min >= dataset_start and split_max <= dataset_end
    return {
        "present": True,
        "n_splits": int(len(splits)),
        "first_train_start": str(split_min.date()),
        "last_test_end": str(split_max.date()),
        "dataset_start": str(dataset_start.date()),
        "dataset_end": str(dataset_end.date()),
        "warmup_days": warmup_days,
        "coverage_ok": split_ok,
        "note": (
            "walk-forward splits fit within the dataset history"
            if split_ok
            else "walk-forward splits fall outside the dataset coverage"
        ),
    }


def audit_power_features(df: pd.DataFrame) -> dict[str, Any]:
    power_cols = [col for col in df.columns if "power" in col.lower()]
    if not power_cols:
        return {"columns": [], "nonzero_columns": [], "coverage_ok": False, "note": "no power features present"}

    nonzero_columns: list[str] = []
    zero_columns: list[str] = []
    for col in power_cols:
        values = pd.to_numeric(df[col], errors="coerce")
        magnitude = float(values.abs().sum(skipna=True))
        if np.isfinite(magnitude) and magnitude > 1e-8:
            nonzero_columns.append(col)
        else:
            zero_columns.append(col)

    return {
        "columns": power_cols,
        "nonzero_columns": nonzero_columns,
        "zero_columns": zero_columns,
        "coverage_ok": bool(nonzero_columns),
        "note": (
            "power features contain non-zero signal columns"
            if nonzero_columns
            else "all power features are zero or missing"
        ),
    }


def build_factor_metadata(
    new_columns: list[str],
    ic_summary: dict[str, FactorIC],
    validation: dict[str, Any],
    dataset_audit: dict[str, Any],
    split_audit: dict[str, Any],
    power_audit: dict[str, Any],
    ready_for_kaggle: bool,
    source_parquet: Path,
    output_parquet: Path,
) -> dict[str, Any]:
    derivations = {
        "eps_revision": "Ticker-level lagged earnings/revenue surprise acceleration and sign consistency, then cross-sectionally normalized per date.",
        "sector_quality": "ROE and earnings quality ranked within same-date sector peer groups (min 5 names), then blended back into universe-wide cross-sectional scores.",
        "vol_adjusted_momentum": "Momentum divided by realized volatility with sector-relative adjustment to stabilize momentum across volatility regimes.",
        "pledge_smart_money": "Pledge sign-correction, pledge x institutional selling stress, and FII/institutional agreement consensus signal.",
    }
    group_map = {
        "eps_revision_accel": "eps_revision",
        "eps_revision_direction": "eps_revision",
        "combined_revision_score": "eps_revision",
        "combined_revision_score_cs_z": "eps_revision",
        "combined_revision_score_cs_rank": "eps_revision",
        "roe_within_sector_cs_rank": "sector_quality",
        "roe_within_sector_cs_z": "sector_quality",
        "earnings_quality_within_sector_cs_rank": "sector_quality",
        "earnings_quality_within_sector_cs_z": "sector_quality",
        "sector_quality_composite": "sector_quality",
        "sector_quality_composite_cs_rank": "sector_quality",
        "mom_20d_vol_adj": "vol_adjusted_momentum",
        "mom_60d_vol_adj": "vol_adjusted_momentum",
        "ret_5d_vol_adj": "vol_adjusted_momentum",
        "mom_20d_vol_adj_sector_rel": "vol_adjusted_momentum",
        "mom_20d_vol_adj_cs_rank": "vol_adjusted_momentum",
        "mom_20d_vol_adj_cs_z": "vol_adjusted_momentum",
        "pledge_short_signal": "pledge_smart_money",
        "pledge_bulk_stress": "pledge_smart_money",
        "pledge_bulk_stress_cs_z": "pledge_smart_money",
        "smart_money_consensus": "pledge_smart_money",
        "smart_money_consensus_cs_z": "pledge_smart_money",
    }

    columns_payload: dict[str, Any] = {}
    for col in new_columns:
        ic_stats = ic_summary.get(col, FactorIC(float("nan"), float("nan"), float("nan"), 0))
        columns_payload[col] = {
            "factor_group": group_map.get(col, "unknown"),
            "derivation": derivations.get(group_map.get(col, "unknown"), ""),
            "expected_ic": EXPECTED_IC_HINTS.get(col),
            "observed_ic": None if not np.isfinite(ic_stats.mean_ic) else ic_stats.mean_ic,
            "observed_t_stat": None if not np.isfinite(ic_stats.t_stat) else ic_stats.t_stat,
        }

    return {
        "version": "week2_v2",
        "source_parquet": str(source_parquet),
        "output_parquet": str(output_parquet),
        "new_columns": new_columns,
        "column_metadata": columns_payload,
        "dataset_audit": dataset_audit,
        "split_audit": split_audit,
        "power_audit": power_audit,
        "lookahead_validation": validation,
        "ready_for_kaggle": bool(ready_for_kaggle),
    }


def copy_support_files(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in SUPPORT_FILES:
        src = input_dir / name
        if src.exists():
            shutil.copy2(src, output_dir / name)


def format_ic_line(name: str, stats: FactorIC) -> str:
    ic_text = f"{stats.mean_ic:.4f}" if np.isfinite(stats.mean_ic) else "nan"
    t_text = f"{stats.t_stat:.2f}" if np.isfinite(stats.t_stat) else "nan"
    return f"  {name:<30} IC={ic_text}  t={t_text}"


def main() -> None:
    args = parse_args()
    input_parquet = Path(args.input_parquet).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_parquet = output_dir / OUTPUT_PARQUET.name
    output_metadata = output_dir / OUTPUT_METADATA.name
    input_dir = input_parquet.parent

    if not input_parquet.exists():
        raise FileNotFoundError(f"Missing input export: {input_parquet}")

    output_dir.mkdir(parents=True, exist_ok=True)
    copy_support_files(input_dir, output_dir)

    base_df = pd.read_parquet(input_parquet)
    base_df["date"] = pd.to_datetime(base_df["date"], errors="coerce")
    base_df = base_df.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

    enriched_df, new_columns = apply_all_factor_groups(base_df)
    target_col = "target_weekly_return" if "target_weekly_return" in enriched_df.columns else "forward_return_5d"
    validation = validate_no_lookahead(base_df, enriched_df, new_columns)
    dataset_audit = audit_dataset_coverage(
        enriched_df,
        expected_min_tickers=args.expected_min_tickers,
        expected_start_date=args.expected_start_date,
    )
    split_audit = audit_support_splits(
        output_dir,
        dataset_start=pd.Timestamp(enriched_df["date"].min()),
        dataset_end=pd.Timestamp(enriched_df["date"].max()),
    )
    power_audit = audit_power_features(enriched_df)

    ic_summary = {col: compute_factor_ic(enriched_df, col, target_col) for col in new_columns}
    ready = bool(
        validation["passed"]
        and output_dir.exists()
        and dataset_audit["coverage_ok"]
        and split_audit["coverage_ok"]
        and power_audit["coverage_ok"]
    )
    metadata = build_factor_metadata(
        new_columns,
        ic_summary,
        validation,
        dataset_audit,
        split_audit,
        power_audit,
        ready,
        input_parquet,
        output_parquet,
    )

    enriched_df.to_parquet(output_parquet, index=False)
    output_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("FACTOR BUILD COMPLETE")
    print(f"  New factors added: {len(new_columns)}")
    print(f"  Rows: {len(enriched_df)}")
    print(f"  Date range: {enriched_df['date'].min().date()} to {enriched_df['date'].max().date()}")
    print(f"  Tickers: {dataset_audit['tickers']}")
    print(f"  Coverage target: >={dataset_audit['expected_min_tickers']} names from {dataset_audit['expected_start_date']}")
    print("")
    print("New factor IC summary:")
    for name in SUMMARY_COLUMNS:
        print(format_ic_line(name, ic_summary.get(name, FactorIC(float('nan'), float('nan'), float('nan'), 0))))
    print("")
    print("Dataset audit:")
    print(f"  Universe coverage: {'OK' if dataset_audit['coverage_ok'] else 'FAIL'} — {dataset_audit['coverage_note']}")
    print(f"  Split coverage:    {'OK' if split_audit['coverage_ok'] else 'FAIL'} — {split_audit['note']}")
    print(f"  Power features:    {'OK' if power_audit['coverage_ok'] else 'FAIL'} — {power_audit['note']}")
    if args.fail_on_coverage and not ready:
        raise SystemExit("Coverage/readiness checks failed. Refusing to mark this export ready for Kaggle.")
    print(f"Ready for Kaggle upload: {'YES' if ready else 'NO'}")


if __name__ == "__main__":
    main()
