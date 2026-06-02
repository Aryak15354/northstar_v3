#!/usr/bin/env python3
"""Robust runtime for Northstar V3 Kaggle experiments EXP-09 through EXP-27."""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from scripts.kaggle.plan_2026_05_18_production.event_registry import EVENT_WINDOWS, is_event_window

try:
    from catboost import CatBoostRegressor, Pool
except Exception:  # pragma: no cover - Kaggle has CatBoost, local smoke may not.
    CatBoostRegressor = None
    Pool = None


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TARGET_COL = "target_weekly_return"
TARGET_CLIP = 0.15
NON_FEATURE_COLS = {"date", "ticker", TARGET_COL}
POST_INDAS_ANCHOR = pd.Timestamp("2021-04-01")
DEFAULT_ROLLING_TRAIN_WEEKS = 104
VALIDATION_WEEKS = 8
EXTENDED_VALIDATION_WEEKS = 12
MIN_TRAIN_ROWS = 25_000
ABSOLUTE_MIN_TRAIN_ROWS = 1_000
ABSOLUTE_MIN_TEST_ROWS = 100
MIN_VAL_TARGET_STD = 0.005
MIN_MODEL_TREES = 20
MIN_PRED_UNIQUE = 5
MIN_PRED_STD = 1e-7
RATIO_EPS = 0.002
RATIO_CAP = 10.0
FALLBACK_ITERATIONS = 400
FALLBACK_LEARNING_RATE = 0.005
_FEATURE_SCREEN_CACHE: dict[tuple[Any, ...], list[str]] = {}
KNOWN_NULL_COLS = [
    "accruals_ratio",
    "asset_turnover",
    "cash_conversion",
    "debt_to_equity",
    "ebitda_margin",
    "interest_coverage",
    "operating_margin",
    "roe",
    "piotroski_fscore",
    "screener_roe",
    "screener_roce",
    "screener_debt_to_equity",
    "screener_current_ratio",
    "screener_pe",
    "screener_pb",
    "gst_collection_yoy",
    "gst_ewaybill_growth",
    "gst_filing_rate",
    "promoter_pledge_ratio",
]
ANCHOR_FACTOR_ALIASES = {
    "eps_sue_decay": ["eps_sue_decay", "eps_sue_decay_cs_z", "eps_sue_decay_cs_rank"],
    "eps_revision_accel": ["eps_revision_accel", "combined_revision_score_cs_z"],
    "rev_sue_decay": ["rev_sue_decay", "rev_sue_decay_cs_z", "rev_sue_decay_cs_rank"],
    "agreement_score": ["agreement_score", "agreement_score_cs_z", "agreement_score_cs_rank"],
    "earnings_quality_ratio": ["earnings_quality_ratio", "earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"],
    "accruals_ratio": ["accruals_ratio", "accruals_ratio_cs_z", "accruals_ratio_cs_rank"],
}
COMMODITY_SIGNALS = [
    "inrusd_4w_return",
    "inrusd_vol_4w",
    "crude_4w_return",
    "crude_shock",
    "gold_4w_return",
    "steel_4w_return",
    "copper_4w_return",
    "coal_4w_return",
    "dxy_4w_return",
    "fii_proxy",
    "vix_india_4w",
    "rbi_rate_chg",
    "us_10y_4w",
    "commodity_basket",
    "stock_x_crude",
    "stock_x_inrusd",
]
FEATURE_FAMILY_PATTERNS = {
    "earnings_surprise": ["eps_sue", "rev_sue", "combined_sue", "eps_decay", "rev_decay"],
    "momentum": ["mom_60d", "mom_63d", "mom_20d", "res_mom"],
    "ownership_or_sentiment": [
        "screener_institutional_pct",
        "screener_promoter_change",
        "screener_dii_pct",
        "screener_free_float_pct",
        "sent_confirmation",
        "sent_sentiment_intensity",
        "sent_mispricing",
        "sent_event_shock_factor",
    ],
}


@dataclass
class DatasetBundle:
    data_dir: Path
    features: pd.DataFrame
    metadata: pd.DataFrame
    regimes: pd.DataFrame
    splits: list[dict[str, Any]]
    manifest: dict[str, Any]
    audit: dict[str, Any]
    feature_cols: list[str]


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return obj


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload


def add_runtime_event_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["post_indas_training_era"] = (date >= POST_INDAS_ANCHOR).astype("float32")
    out["budget_2024_event_dummy"] = ((date >= pd.Timestamp("2024-06-28")) & (date <= pd.Timestamp("2024-09-20"))).astype("float32")
    out["post_nifty_peak_correction_dummy"] = ((date >= pd.Timestamp("2024-12-27")) & (date <= pd.Timestamp("2025-06-20"))).astype("float32")
    out["structural_event_window_dummy"] = (
        ((date >= pd.Timestamp("2024-06-28")) & (date <= pd.Timestamp("2024-12-20")))
        | ((date >= pd.Timestamp("2024-12-27")) & (date <= pd.Timestamp("2025-06-20")))
    ).astype("float32")
    return out


def post_indas_rolling_splits(
    splits: list[dict[str, Any]],
    *,
    rolling_train_weeks: int = DEFAULT_ROLLING_TRAIN_WEEKS,
    anchor: pd.Timestamp = POST_INDAS_ANCHOR,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in splits:
        split = dict(raw)
        test_start = pd.Timestamp(split["test_start"])
        train_end = pd.Timestamp(split["train_end"])
        if train_end < anchor:
            continue
        rolling_start = test_start - pd.Timedelta(weeks=rolling_train_weeks)
        train_start = max(anchor, rolling_start)
        split["original_train_start"] = split.get("train_start")
        split["original_window_id"] = split.get("window_id")
        split["window_id"] = len(normalized) + 1
        split["train_start"] = str(train_start.date())
        split["train_policy"] = f"post_indas_rolling_{rolling_train_weeks}w"
        is_event, event_label = is_event_window(split["test_start"], split["test_end"])
        split["aggregate_excluded"] = bool(is_event)
        split["event_label"] = event_label
        normalized.append(split)
    return normalized


def resolve_data_dir(user_path: str | Path | None = None) -> Path:
    if user_path:
        path = Path(user_path).expanduser().resolve()
        if (path / "northstar_features.parquet").exists():
            return path
        raise FileNotFoundError(f"northstar_features.parquet not found in {path}")
    candidates = [
        Path("/kaggle/input/northstar-v3-feature-export-fixed"),
        Path("/kaggle/input/northstar-v3-feature-export-fixed-1"),
        Path("/kaggle/input/northstar-v3-feature-export"),
        PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_fixed_20260519",
        PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_fixed_20260518",
        PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_robust_20260405",
    ]
    for path in candidates:
        if (path / "northstar_features.parquet").exists():
            return path.resolve()
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for feature_path in sorted(kaggle_input.rglob("northstar_features.parquet")):
            return feature_path.parent.resolve()
    raise FileNotFoundError("Unable to resolve Northstar feature export directory.")


def load_and_fix_dataset(
    data_dir: str | Path,
    *,
    feature_policy: str = "safe",
    null_threshold: float = 0.95,
    verbose: bool = True,
) -> DatasetBundle:
    data_dir = Path(data_dir).expanduser().resolve()
    audit: dict[str, Any] = {}
    manifest = read_json(data_dir / "northstar_feature_manifest.json", {})
    feature_path = data_dir / "northstar_features.parquet"
    if feature_policy == "safe" and (data_dir / "northstar_features_model_ready.parquet").exists():
        feature_path = data_dir / "northstar_features_model_ready.parquet"

    print(f"\n{'=' * 65}")
    print("  NORTHSTAR DATASET LOADER")
    print(f"{'=' * 65}")
    print(f"  Data dir: {data_dir}")
    print(f"  Feature file: {feature_path.name}")
    df = pd.read_parquet(feature_path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
    print(f"  Shape  : {len(df):,} rows x {df.shape[1]} columns")
    print(f"  Tickers: {df['ticker'].nunique()}  |  Dates: {df['date'].min().date()} -> {df['date'].max().date()}")
    audit["raw_shape"] = [int(df.shape[0]), int(df.shape[1])]

    dupes = int(df.duplicated(["date", "ticker"]).sum())
    if dupes:
        print(f"  WARNING: dropping {dupes} duplicate (date, ticker) rows")
        df = df.drop_duplicates(["date", "ticker"], keep="last").reset_index(drop=True)
    audit["duplicate_rows_dropped"] = dupes

    if TARGET_COL not in df.columns:
        raise KeyError(f"{TARGET_COL} missing from feature file.")
    pre_min = float(pd.to_numeric(df[TARGET_COL], errors="coerce").min())
    pre_max = float(pd.to_numeric(df[TARGET_COL], errors="coerce").max())
    clip_mask = pd.to_numeric(df[TARGET_COL], errors="coerce").abs() > TARGET_CLIP
    df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce").clip(-TARGET_CLIP, TARGET_CLIP)
    audit["target_pre_clip_min"] = pre_min
    audit["target_pre_clip_max"] = pre_max
    audit["target_rows_clipped_runtime"] = int(clip_mask.sum())
    if clip_mask.any():
        print(f"  Target : runtime-clipped {int(clip_mask.sum())} rows at +/-{TARGET_CLIP}")
    null_targets = int(df[TARGET_COL].isna().sum())
    if null_targets:
        print(f"  WARNING: dropping {null_targets} rows with null target")
        df = df.dropna(subset=[TARGET_COL]).reset_index(drop=True)
    audit["target_null_rows_dropped_runtime"] = null_targets
    df = add_runtime_event_features(df)

    feature_candidates = [
        c for c in df.columns
        if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    known_null_present = [c for c in KNOWN_NULL_COLS if c in feature_candidates]
    feature_candidates = [c for c in feature_candidates if c not in set(known_null_present)]
    null_rates = df[feature_candidates].isna().mean()
    sparse_cols = null_rates[null_rates > null_threshold].index.astype(str).tolist()
    if feature_policy == "safe":
        feature_candidates = [c for c in feature_candidates if c not in set(sparse_cols)]
    nunique = df[feature_candidates].nunique(dropna=True)
    constant_cols = nunique[nunique <= 1].index.astype(str).tolist()
    feature_candidates = [c for c in feature_candidates if c not in set(constant_cols)]

    audit.update(
        {
            "known_null_cols_dropped_runtime": known_null_present,
            "sparse_cols_dropped_runtime": sparse_cols if feature_policy == "safe" else [],
            "sparse_cols_kept_runtime": sparse_cols if feature_policy != "safe" else [],
            "constant_cols_dropped_runtime": constant_cols,
            "feature_policy": feature_policy,
            "final_feature_count": int(len(feature_candidates)),
            "final_shape": [int(len(df)), int(len(feature_candidates) + 3)],
        }
    )
    print(f"  Feature policy: {feature_policy}")
    print(f"  Dropped known-null: {len(known_null_present)}")
    print(f"  Dropped/kept sparse >{null_threshold:.0%}: {len(sparse_cols)} / {0 if feature_policy == 'safe' else len(sparse_cols)}")
    print(f"  Dropped constants: {len(constant_cols)}")
    print(f"  Clean features: {len(feature_candidates)}")
    print(f"{'=' * 65}\n")

    metadata = pd.read_parquet(data_dir / "northstar_metadata.parquet")
    metadata["date"] = pd.to_datetime(metadata["date"], errors="coerce").dt.normalize()
    for col in ["sector", "broad_sector", "subsector"]:
        if col in metadata.columns:
            metadata[col] = metadata[col].fillna("Unknown").astype(str)
    regimes = pd.read_parquet(data_dir / "northstar_regime_labels.parquet")
    regimes["date"] = pd.to_datetime(regimes["date"], errors="coerce").dt.normalize()
    splits = read_json(data_dir / "northstar_walk_forward_splits.json", [])
    if isinstance(splits, dict):
        splits = list(splits.get("windows") or [])
    splits = post_indas_rolling_splits(list(splits))
    audit["training_window_policy"] = {
        "mode": "rolling",
        "anchor": str(POST_INDAS_ANCHOR.date()),
        "rolling_train_weeks": DEFAULT_ROLLING_TRAIN_WEEKS,
        "validation_weeks": VALIDATION_WEEKS,
        "extended_validation_weeks": EXTENDED_VALIDATION_WEEKS,
        "min_train_rows": MIN_TRAIN_ROWS,
        "event_registry": EVENT_WINDOWS,
    }
    print(f"  Loaded {len(splits)} walk-forward windows")
    print(f"  Train policy: post-Ind-AS rolling {DEFAULT_ROLLING_TRAIN_WEEKS}w, adaptive validation {VALIDATION_WEEKS}/{EXTENDED_VALIDATION_WEEKS}w")
    excluded = [int(s.get("window_id", idx + 1)) for idx, s in enumerate(splits) if s.get("aggregate_excluded")]
    print(f"  Aggregate-excluded event windows by date overlap: {excluded}")
    return DatasetBundle(data_dir, df, metadata, regimes, list(splits), manifest, audit, feature_candidates)


def _is_pre_normalized_feature(col: str) -> bool:
    lowered = col.lower()
    return lowered.endswith("_cs_z") or lowered.endswith("_cs_rank") or lowered.endswith("_cs_zscore")


def cross_sectional_normalize(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in feature_cols:
        if _is_pre_normalized_feature(col):
            continue
        values = pd.to_numeric(out[col], errors="coerce")
        means = values.groupby(out["date"]).transform("mean")
        stds = values.groupby(out["date"]).transform("std").replace(0.0, np.nan)
        out[col] = ((values - means) / (stds + 1e-8)).clip(-3.0, 3.0)
    return out


def apply_split(df: pd.DataFrame, split: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[(df["date"] >= pd.Timestamp(split["train_start"])) & (df["date"] <= pd.Timestamp(split["train_end"]))].copy()
    test = df[(df["date"] >= pd.Timestamp(split["test_start"])) & (df["date"] <= pd.Timestamp(split["test_end"]))].copy()
    train = train.dropna(subset=[TARGET_COL])
    test = test.dropna(subset=[TARGET_COL])
    return train, test


def compute_ic(predictions: np.ndarray, targets: np.ndarray) -> float:
    mask = np.isfinite(predictions) & np.isfinite(targets)
    if int(mask.sum()) < 10:
        return float("nan")
    pred = predictions[mask]
    targ = targets[mask]
    if np.unique(pred).size <= 1 or np.unique(targ).size <= 1:
        return float("nan")
    corr, _ = spearmanr(pred, targ)
    return float(corr) if np.isfinite(corr) else float("nan")


def ic_by_date(frame: pd.DataFrame, score_col: str, target_col: str = TARGET_COL, min_obs: int = 10) -> pd.Series:
    rows: list[tuple[pd.Timestamp, float]] = []
    for date_value, group in frame.groupby("date", sort=True):
        local = group[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < min_obs:
            continue
        ic = compute_ic(local[score_col].to_numpy(float), local[target_col].to_numpy(float))
        if np.isfinite(ic):
            rows.append((pd.Timestamp(date_value), ic))
    return pd.Series([v for _, v in rows], index=[d for d, _ in rows], dtype="float64")


def get_val_split(
    train_df: pd.DataFrame,
    date_col: str = "date",
    target_col: str = TARGET_COL,
    *,
    preferred_weeks: int = VALIDATION_WEEKS,
    extended_weeks: int = EXTENDED_VALIDATION_WEEKS,
) -> tuple[pd.DataFrame, pd.DataFrame | None, int, str]:
    """Use the shortest recent validation split with enough target dispersion."""
    all_dates = sorted(pd.to_datetime(train_df[date_col]).dropna().unique())
    if len(all_dates) < 10:
        return train_df.copy(), None, 0, "none_insufficient_dates"

    chosen: tuple[pd.DataFrame, pd.DataFrame | None, int, str] | None = None
    for val_weeks in [preferred_weeks, extended_weeks]:
        val_dates = max(1, val_weeks)
        split_idx = len(all_dates) - val_dates
        if split_idx < len(all_dates) * 0.5:
            break
        split_date = pd.Timestamp(all_dates[split_idx])
        fit_df = train_df[train_df[date_col] < split_date].copy()
        val_df = train_df[train_df[date_col] >= split_date].copy()
        if len(val_df) < 50 or len(fit_df) < 200:
            continue
        val_target_std = float(pd.to_numeric(val_df[target_col], errors="coerce").std())
        mode = "standard" if val_weeks == preferred_weeks else "extended"
        chosen = (fit_df, val_df, val_weeks, f"{mode}_target_std_{val_target_std:.6f}")
        if np.isfinite(val_target_std) and val_target_std >= MIN_VAL_TARGET_STD:
            return chosen

    if chosen is not None:
        return chosen
    return train_df.copy(), None, 0, "none_val_too_small"


def _feature_screen_stats(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    *,
    target_col: str = TARGET_COL,
    date_col: str = "date",
    min_feature_coverage: float = 0.10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dates = sorted(pd.to_datetime(train_df[date_col]).dropna().unique())
    for col in feature_cols:
        if col not in train_df.columns or not pd.api.types.is_numeric_dtype(train_df[col]):
            continue
        coverage = float(train_df[col].notna().mean())
        if coverage < min_feature_coverage:
            rows.append({"feature": col, "coverage": coverage, "n_dates": 0, "median_abs_ic": 0.0, "positive_ic_rate": 0.0})
            continue
        date_ics: list[float] = []
        for date_value in dates:
            local = train_df.loc[train_df[date_col] == date_value, [col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(local) < 10:
                continue
            ic = compute_ic(local[col].to_numpy(float), local[target_col].to_numpy(float))
            if np.isfinite(ic):
                date_ics.append(float(ic))
        arr = np.asarray(date_ics, dtype=float)
        rows.append(
            {
                "feature": col,
                "coverage": coverage,
                "n_dates": int(arr.size),
                "median_abs_ic": float(np.median(np.abs(arr))) if arr.size else 0.0,
                "positive_ic_rate": float((arr > 0).mean()) if arr.size else 0.0,
            }
        )
    rows.sort(key=lambda r: (-float(r["median_abs_ic"]), -float(r["positive_ic_rate"]), str(r["feature"])))
    return rows


def screen_features_by_ic(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    *,
    target_col: str = TARGET_COL,
    date_col: str = "date",
    min_median_abs_ic: float = 0.010,
    min_positive_ic_rate: float = 0.55,
    min_feature_coverage: float = 0.10,
    always_keep: list[str] | None = None,
    relaxed_fallback: bool = True,
) -> list[str]:
    """
    Window-local univariate IC screen.

    Keeps features with enough coverage, median absolute per-date IC, and sign stability.
    If fewer than 20 pass, falls back to the top 30 features from a relaxed screen.
    """
    always = [c for c in (always_keep or []) if c in feature_cols and c in train_df.columns]
    cache_key = (
        str(pd.to_datetime(train_df[date_col]).min().date()),
        str(pd.to_datetime(train_df[date_col]).max().date()),
        int(len(train_df)),
        tuple(feature_cols),
        tuple(always),
        float(min_median_abs_ic),
        float(min_positive_ic_rate),
        float(min_feature_coverage),
        bool(relaxed_fallback),
    )
    if cache_key in _FEATURE_SCREEN_CACHE:
        return list(_FEATURE_SCREEN_CACHE[cache_key])

    stats_rows = _feature_screen_stats(
        train_df,
        feature_cols,
        target_col=target_col,
        date_col=date_col,
        min_feature_coverage=min_feature_coverage,
    )
    passing = [
        r["feature"]
        for r in stats_rows
        if r["feature"] not in set(always)
        and int(r["n_dates"]) >= 5
        and float(r["coverage"]) >= min_feature_coverage
        and float(r["median_abs_ic"]) >= min_median_abs_ic
        and float(r["positive_ic_rate"]) >= min_positive_ic_rate
    ]
    if relaxed_fallback and len(always) + len(passing) < 20:
        relaxed = [
            r["feature"]
            for r in stats_rows
            if r["feature"] not in set(always)
            and int(r["n_dates"]) >= 5
            and float(r["coverage"]) >= min_feature_coverage
            and float(r["median_abs_ic"]) >= 0.005
            and float(r["positive_ic_rate"]) >= 0.50
        ]
        if len(always) + len(relaxed) < 20:
            relaxed = [r["feature"] for r in stats_rows if r["feature"] not in set(always) and int(r["n_dates"]) >= 5]
        passing = relaxed[:30]

    selected = list(dict.fromkeys(always + passing))
    _FEATURE_SCREEN_CACHE[cache_key] = selected
    return selected


def feature_family_coverage(features: list[str], family_patterns: dict[str, list[str]] | None = None) -> dict[str, Any]:
    patterns_by_family = family_patterns or FEATURE_FAMILY_PATTERNS
    lowered = {f: f.lower() for f in features}
    present: dict[str, list[str]] = {}
    missing: list[str] = []
    for family, patterns in patterns_by_family.items():
        hits = [name for name, low in lowered.items() if any(pattern in low for pattern in patterns)]
        present[family] = hits
        if not hits:
            missing.append(family)
    earnings_like = [
        name
        for name, low in lowered.items()
        if "sue" in low or "eps" in low or "rev" in low
    ]
    return {
        "family_hits": {k: len(v) for k, v in present.items()},
        "family_features": present,
        "missing_families": missing,
        "is_family_complete": len(missing) == 0,
        "earnings_feature_count": len(earnings_like),
        "earnings_features": earnings_like,
    }


def summarize_ic_values(values: Iterable[float]) -> dict[str, Any]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size == 0:
        return {"mean_ic": None, "ic_std": None, "ic_ir": None, "hit_rate": None, "n": 0}
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    mean = float(arr.mean())
    return {
        "mean_ic": mean,
        "ic_std": std,
        "ic_ir": float(mean / std) if std > 0 else None,
        "hit_rate": float((arr > 0).mean()),
        "n": int(arr.size),
    }


def prediction_diagnostics(predictions: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(predictions, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return {"prediction_std": None, "prediction_unique": 0, "prediction_degenerate": True}
    unique = int(pd.Series(finite).round(12).nunique())
    std = float(np.std(finite))
    return {
        "prediction_std": std,
        "prediction_unique": unique,
        "prediction_degenerate": bool(unique < MIN_PRED_UNIQUE or std < MIN_PRED_STD),
    }


def train_test_ratio(train_ic: float, test_ic: float) -> tuple[float, float, bool]:
    if not np.isfinite(train_ic) or not np.isfinite(test_ic):
        return float("nan"), float("nan"), False
    raw = float(abs(train_ic) / max(abs(test_ic), 1e-8))
    robust = float(min(abs(train_ic) / max(abs(test_ic), RATIO_EPS), RATIO_CAP))
    return raw, robust, bool(raw > RATIO_CAP)


def log_window_start(idx: int, total: int, split: dict[str, Any], train: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]) -> None:
    target_coverage = float(test[TARGET_COL].notna().mean()) if len(test) else 0.0
    feature_null_rate = float(test[feature_cols].isna().mean().mean()) if len(test) and feature_cols else 0.0
    print(f"\n{'-' * 65}")
    print(f"  WINDOW {idx + 1:02d}/{total}  Train: {split['train_start']} -> {split['train_end']}  Test: {split['test_start']} -> {split['test_end']}")
    print(f"  Train rows: {len(train):,}  |  Test rows: {len(test):,}  |  Features: {len(feature_cols)}")
    print(f"  Test target coverage: {target_coverage:.1%}  |  Feature null rate: {feature_null_rate:.1%}")
    if split.get("aggregate_excluded"):
        print(f"  Event window: {split.get('event_label')}  |  excluded from aggregate gates")
    if target_coverage < 0.85:
        print("  WARNING: low target coverage in test window; IC may be unreliable")
    print(f"{'-' * 65}")


def log_aggregate(exp_id: str, candidate: str, window_rows: list[dict[str, Any]]) -> dict[str, Any]:
    excluded_rows = [r for r in window_rows if r.get("aggregate_excluded")]
    skipped_rows = [r for r in window_rows if r.get("skipped")]
    valid_rows = [r for r in window_rows if not r.get("skipped") and not r.get("prediction_degenerate") and not r.get("aggregate_excluded")]
    train_ics = [float(r["train_ic"]) for r in valid_rows if np.isfinite(r.get("train_ic", np.nan))]
    test_ics = [float(r["test_ic"]) for r in valid_rows if np.isfinite(r.get("test_ic", np.nan))]
    raw_ratios = [float(r["ratio_raw"]) for r in valid_rows if np.isfinite(r.get("ratio_raw", np.nan))]
    robust_ratios = [float(r["ratio"]) for r in valid_rows if np.isfinite(r.get("ratio", np.nan))]
    test_summary = summarize_ic_values(test_ics)
    train_summary = summarize_ic_values(train_ics)
    mean_raw_ratio = float(np.mean(raw_ratios)) if raw_ratios else None
    mean_ratio = float(np.mean(robust_ratios)) if robust_ratios else None
    median_ratio = float(np.median(robust_ratios)) if robust_ratios else None
    degenerate_windows = [int(r["window_id"]) for r in window_rows if r.get("prediction_degenerate")]
    unstable_ratio_windows = [int(r["window_id"]) for r in window_rows if r.get("ratio_capped")]
    aggregate_excluded_windows = [{"window": int(r["window_id"]), "event": r.get("event_label")} for r in excluded_rows if not r.get("skipped")]
    skipped_windows = [{"window": int(r["window_id"]), "reason": r.get("skip_reason")} for r in skipped_rows]
    gate_ic = (test_summary["mean_ic"] or 0.0) >= 0.020
    gate_ratio = median_ratio is not None and median_ratio < 2.5
    gate_hit = (test_summary["hit_rate"] or 0.0) > 0.55
    gate_stability = len(degenerate_windows) == 0
    print(f"\n{'=' * 65}")
    print(f"  AGGREGATE - {exp_id} - {candidate}")
    print(f"  Mean train IC: {train_summary['mean_ic']}")
    print(f"  Mean test IC : {test_summary['mean_ic']}  [{'PASS' if gate_ic else 'FAIL'} IC >= 0.020]")
    print(f"  IC IR        : {test_summary['ic_ir']}")
    print(f"  Median ratio : {median_ratio}  [{'PASS' if gate_ratio else 'FAIL'} robust ratio < 2.5x]")
    print(f"  Mean ratio   : {mean_ratio}  | raw mean ratio: {mean_raw_ratio}")
    print(f"  Hit rate     : {test_summary['hit_rate']}  [{'PASS' if gate_hit else 'FAIL'} hit > 55%]")
    print(f"  Degenerate windows: {degenerate_windows or []}  [{'PASS' if gate_stability else 'FAIL'} stability]")
    print(f"  Skipped windows: {skipped_windows or []}")
    print(f"  Event-excluded windows: {aggregate_excluded_windows or []}")
    print(f"  Ratio-capped windows: {unstable_ratio_windows or []}")
    print(f"  Effective eval windows: {len(valid_rows)}")
    print(f"{'=' * 65}\n")
    return {
        "candidate": candidate,
        "mean_train_ic": train_summary["mean_ic"],
        "mean_test_ic": test_summary["mean_ic"],
        "ic_ir": test_summary["ic_ir"],
        "mean_train_test_ratio": mean_ratio,
        "median_train_test_ratio": median_ratio,
        "raw_mean_train_test_ratio": mean_raw_ratio,
        "mean_hit_rate": test_summary["hit_rate"],
        "windows_completed": int(len(window_rows)),
        "valid_windows_completed": int(len(valid_rows)),
        "aggregate_excluded_window_count": int(len(excluded_rows)),
        "aggregate_excluded_windows": aggregate_excluded_windows,
        "skipped_window_count": int(len(skipped_rows)),
        "skipped_windows": skipped_windows,
        "effective_eval_windows": int(len(valid_rows)),
        "degenerate_window_count": int(len(degenerate_windows)),
        "degenerate_windows": degenerate_windows,
        "ratio_capped_windows": unstable_ratio_windows,
        "gate_ic_pass": bool(gate_ic),
        "gate_ratio_pass": bool(gate_ratio),
        "gate_hit_pass": bool(gate_hit),
        "gate_stability_pass": bool(gate_stability),
    }


def build_catboost(**params: Any) -> Any:
    base = {
        "depth": 4,
        "learning_rate": 0.01,
        "iterations": 600,
        "l2_leaf_reg": 3.0,
        "min_data_in_leaf": 40,
        "boosting_type": "Ordered",
        "loss_function": "RMSE",
        "eval_metric": "RMSE",
        "random_seed": 42,
        "thread_count": -1,
        "verbose": False,
        "allow_writing_files": False,
        "od_type": "Iter",
        "od_wait": 40,
        "training_mode": "fixed_iterations",
    }
    base.update(params)
    training_mode = base.pop("training_mode", None)
    if CatBoostRegressor is not None:
        return CatBoostRegressor(**base)
    from sklearn.ensemble import HistGradientBoostingRegressor

    print("  WARNING: CatBoost unavailable; using sklearn HistGradientBoostingRegressor for smoke validation.")
    return HistGradientBoostingRegressor(max_iter=min(int(base.get("iterations", 200)), 200), learning_rate=float(base["learning_rate"]), random_state=int(base["random_seed"]))


def warmup_capacity_profile(train_rows: int, requested_min_rows: int) -> dict[str, Any]:
    """Return a conservative model profile for chronologically young windows.

    The early post-IndAS windows cannot have 25k rows by construction. Instead
    of skipping them, train a smaller model whose capacity is proportional to
    the rows that actually exist.
    """
    if train_rows >= requested_min_rows:
        return {
            "warmup_window": False,
            "capacity_tier": "production",
            "max_features": None,
            "param_overrides": {},
        }
    if train_rows < 8_000:
        return {
            "warmup_window": True,
            "capacity_tier": "warmup_tiny",
            "max_features": 20,
            "param_overrides": {"depth": 2, "iterations": 250, "min_data_in_leaf": 80, "learning_rate": 0.01},
        }
    if train_rows < 15_000:
        return {
            "warmup_window": True,
            "capacity_tier": "warmup_small",
            "max_features": 25,
            "param_overrides": {"depth": 3, "iterations": 300, "min_data_in_leaf": 90, "learning_rate": 0.01},
        }
    return {
        "warmup_window": True,
        "capacity_tier": "warmup_medium",
        "max_features": 35,
        "param_overrides": {"depth": 4, "iterations": 400, "min_data_in_leaf": 110, "learning_rate": 0.01},
    }


def cap_feature_list(selected: list[str], always_keep: list[str] | None, max_features: int | None) -> list[str]:
    if not max_features or len(selected) <= max_features:
        return selected
    always = [c for c in (always_keep or []) if c in selected]
    rest = [c for c in selected if c not in set(always)]
    return list(dict.fromkeys(always + rest[: max(0, max_features - len(always))]))


def _fit_catboost_with_guard(
    train: pd.DataFrame,
    fit: pd.DataFrame,
    val: pd.DataFrame | None,
    test: pd.DataFrame,
    cols: list[str],
    params: dict[str, Any],
) -> tuple[Any, np.ndarray, np.ndarray, int | None, str, dict[str, Any]]:
    if len(cols) == 0:
        print("  WARNING: IC screen returned 0 features - skipping window (no features to fit)")
        return None, np.asarray([], dtype=float), np.asarray([], dtype=float), 0, "skipped_zero_features", {
            "prediction_std": None,
            "prediction_unique": 0,
            "prediction_degenerate": True,
        }
    model = build_catboost(**params)
    if CatBoostRegressor is not None and isinstance(model, CatBoostRegressor):
        training_mode = str(params.get("training_mode", "fixed_iterations"))
        if training_mode == "fixed_iterations":
            fixed_params = dict(params)
            fixed_params.pop("od_wait", None)
            fixed_params.pop("od_type", None)
            fixed_params.pop("training_mode", None)
            model = build_catboost(**fixed_params)
            full_pool = Pool(train[cols], train[TARGET_COL])
            model.fit(full_pool)
            best_iteration = int(getattr(model, "tree_count_", fixed_params.get("iterations", 800)) or fixed_params.get("iterations", 800))
            train_pred = model.predict(train[cols])
            test_pred = model.predict(test[cols])
            test_diag = prediction_diagnostics(test_pred)
            if test_diag["prediction_degenerate"]:
                print(
                    "  WARNING: fixed-iteration CatBoost prediction dispersion is weak "
                    f"(pred_unique={test_diag['prediction_unique']}, pred_std={test_diag['prediction_std']})."
                )
            return model, train_pred, test_pred, best_iteration, f"catboost_primary_fixed_lr{float(fixed_params.get('learning_rate', 0.01)):.3g}_iter{best_iteration}", test_diag

        train_pool = Pool(fit[cols], fit[TARGET_COL])
        eval_pool = Pool(val[cols], val[TARGET_COL]) if val is not None else None
        model.fit(train_pool, eval_set=eval_pool, early_stopping_rounds=int(params.get("od_wait", 30)), use_best_model=eval_pool is not None)
        best_iteration = int(model.best_iteration_ or 0)
        train_pred = model.predict(train[cols])
        test_pred = model.predict(test[cols])
        test_diag = prediction_diagnostics(test_pred)
        if best_iteration < MIN_MODEL_TREES or test_diag["prediction_degenerate"]:
            print(
                "  WARNING: CatBoost selected a degenerate/too-small model "
                f"(best_iteration={best_iteration}, pred_unique={test_diag['prediction_unique']}); "
                f"retraining fixed {FALLBACK_ITERATIONS} trees at lr={FALLBACK_LEARNING_RATE}."
            )
            fallback_params = dict(params)
            fallback_params["iterations"] = int(FALLBACK_ITERATIONS)
            fallback_params["learning_rate"] = float(FALLBACK_LEARNING_RATE)
            fallback_params.pop("od_wait", None)
            fallback = build_catboost(**fallback_params)
            full_pool = Pool(train[cols], train[TARGET_COL])
            fallback.fit(full_pool)
            model = fallback
            best_iteration = int(getattr(model, "tree_count_", fallback_params["iterations"]) or fallback_params["iterations"])
            train_pred = model.predict(train[cols])
            test_pred = model.predict(test[cols])
            test_diag = prediction_diagnostics(test_pred)
            return model, train_pred, test_pred, best_iteration, "catboost_retrained_lr005_fixed400", test_diag
        return model, train_pred, test_pred, best_iteration, "catboost_best_model", test_diag

    X_fit = fit[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    model.fit(X_fit, fit[TARGET_COL])
    train_pred = model.predict(train[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0))
    test_pred = model.predict(test[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0))
    return model, train_pred, test_pred, None, "sklearn_fallback", prediction_diagnostics(test_pred)


def run_catboost_walkforward(
    bundle: DatasetBundle,
    *,
    exp_id: str,
    candidate: str,
    params: dict[str, Any],
    frame: pd.DataFrame | None = None,
    feature_cols: list[str] | None = None,
    always_keep_features: list[str] | None = None,
    use_ic_screen: bool = True,
    min_train_rows: int = MIN_TRAIN_ROWS,
    splits: list[dict[str, Any]] | None = None,
    max_windows: int | None = None,
    test_ic_floor: float | None = None,
    allow_warmup_windows: bool = True,
    ic_screen_min_median_abs_ic: float = 0.010,
    ic_screen_min_positive_ic_rate: float = 0.55,
    ic_screen_min_feature_coverage: float = 0.10,
    production_ic_screen_min_median_abs_ic: float | None = None,
    production_relaxed_feature_fallback: bool = True,
    require_multi_family_features: bool = False,
    feature_family_patterns: dict[str, list[str]] | None = None,
    earnings_starvation_min_features: int | None = None,
    earnings_starvation_hard_gate: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = frame.copy() if frame is not None else bundle.features.copy()
    cols = list(feature_cols or bundle.feature_cols)
    cols = [c for c in cols if c in data.columns and pd.api.types.is_numeric_dtype(data[c])]
    data = cross_sectional_normalize(data, cols)
    windows = list(splits or bundle.splits)
    if max_windows:
        windows = windows[:max_windows]
    window_rows: list[dict[str, Any]] = []
    for idx, split in enumerate(windows):
        train, test = apply_split(data, split)
        log_window_start(idx, len(windows), split, train, test, cols)
        window_id = int(split.get("window_id", idx + 1))
        base_skip = {
            "exp_id": exp_id,
            "candidate": candidate,
            "window_id": window_id,
            "train_start": split["train_start"],
            "train_end": split["train_end"],
            "test_start": split["test_start"],
            "test_end": split["test_end"],
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "aggregate_excluded": bool(split.get("aggregate_excluded", False)),
            "event_label": split.get("event_label"),
            "train_policy": split.get("train_policy"),
            "skipped": True,
            "train_ic": None,
            "test_ic": None,
            "ratio": None,
            "ratio_raw": None,
            "ratio_capped": False,
            "prediction_degenerate": False,
        }
        if len(train) < ABSOLUTE_MIN_TRAIN_ROWS or len(test) < ABSOLUTE_MIN_TEST_ROWS:
            reason = f"insufficient_rows_train_{len(train)}_test_{len(test)}"
            print(f"  SKIP: {reason}")
            window_rows.append({**base_skip, "skip_reason": reason, "feature_count": int(len(cols))})
            continue
        capacity = warmup_capacity_profile(len(train), min_train_rows)
        window_params = dict(params)
        if capacity["warmup_window"] and not allow_warmup_windows:
            reason = f"train_rows_{len(train)}_below_threshold_{min_train_rows}"
            print(f"  SKIP: train rows {len(train):,} < {min_train_rows:,} threshold")
            window_rows.append({**base_skip, "skip_reason": reason, "feature_count": int(len(cols))})
            continue
        if capacity["warmup_window"]:
            window_params.update(capacity["param_overrides"])
            print(
                f"  WARMUP: train rows {len(train):,} < {min_train_rows:,}; "
                f"using {capacity['capacity_tier']} profile "
                f"(depth={window_params.get('depth')}, iterations={window_params.get('iterations')}, "
                f"min_data_in_leaf={window_params.get('min_data_in_leaf')})"
            )

        fit, val, val_weeks, val_mode = get_val_split(train)
        min_fit_rows = max(200, int(window_params.get("min_data_in_leaf", 40)) * 8)
        if len(fit) < min_fit_rows:
            print(
                f"  WARMUP: validation split left fit={len(fit)} < {min_fit_rows}; "
                "training on full window without a validation holdout."
            )
            fit = train.copy()
            val = None
            val_weeks = 0
            val_mode = "none_full_window_warmup_fit"
        passing_cols = cols
        screen_min_abs_ic = ic_screen_min_median_abs_ic
        relaxed_fallback = True
        if not capacity["warmup_window"]:
            screen_min_abs_ic = production_ic_screen_min_median_abs_ic if production_ic_screen_min_median_abs_ic is not None else ic_screen_min_median_abs_ic
            relaxed_fallback = bool(production_relaxed_feature_fallback)
        if use_ic_screen:
            passing_cols = screen_features_by_ic(
                train,
                cols,
                target_col=TARGET_COL,
                date_col="date",
                min_median_abs_ic=screen_min_abs_ic,
                min_positive_ic_rate=ic_screen_min_positive_ic_rate,
                min_feature_coverage=ic_screen_min_feature_coverage,
                always_keep=always_keep_features,
                relaxed_fallback=relaxed_fallback,
            )
            if len(passing_cols) < 20:
                print(f"  WARNING: IC screen returned only {len(passing_cols)} features after fallback")
        passing_cols = cap_feature_list(passing_cols, always_keep_features, capacity.get("max_features"))
        family_diag = feature_family_coverage(passing_cols, feature_family_patterns)
        print(f"  -> features: {len(passing_cols)} / {len(cols)} passed IC screen")
        print(f"  -> feature families: {family_diag['family_hits']} missing={family_diag['missing_families']}")
        if earnings_starvation_min_features is not None and family_diag["earnings_feature_count"] < int(earnings_starvation_min_features):
            msg = (
                f"earnings_starved_{family_diag['earnings_feature_count']}"
                f"_below_{int(earnings_starvation_min_features)}"
            )
            print(f"  WARNING: {msg}; earnings-like features={family_diag['earnings_features']}")
            if earnings_starvation_hard_gate and not capacity["warmup_window"]:
                window_rows.append({
                    **base_skip,
                    "skip_reason": msg,
                    "feature_count": int(len(passing_cols)),
                    "feature_count_total": int(len(cols)),
                    "feature_screen_passed": int(len(passing_cols)),
                    "feature_screen_total": int(len(cols)),
                    "selected_features": passing_cols,
                    "feature_family_diagnostics": family_diag,
                    "val_weeks": int(val_weeks),
                    "val_mode": val_mode,
                })
                continue
        family_incomplete_excluded = bool(require_multi_family_features and not bool(family_diag["is_family_complete"]))
        if family_incomplete_excluded and capacity["warmup_window"]:
            print(
                "  GATE-DIAGNOSTIC: family-incomplete warmup window will be fit "
                "for coverage but excluded from aggregate gates."
            )
        if family_incomplete_excluded and not capacity["warmup_window"]:
            reason = "multi_family_incomplete_missing_" + "_".join(family_diag["missing_families"])
            print(f"  GATE: {reason}; no model fit for this production window.")
            window_rows.append({
                **base_skip,
                "skip_reason": reason,
                "feature_count": int(len(passing_cols)),
                "feature_count_total": int(len(cols)),
                "feature_screen_passed": int(len(passing_cols)),
                "feature_screen_total": int(len(cols)),
                "selected_features": passing_cols,
                "feature_family_diagnostics": family_diag,
                "val_weeks": int(val_weeks),
                "val_mode": val_mode,
            })
            continue
        print(f"  -> val_weeks: {val_weeks} ({val_mode})")
        if split.get("aggregate_excluded"):
            print(f"  -> event_window: {split.get('event_label')} | excluded from aggregate gates")
        if len(passing_cols) == 0:
            reason = "ic_screen_zero_features"
            print(f"  SKIP: {reason}")
            window_rows.append({
                **base_skip,
                "skip_reason": reason,
                "feature_count": 0,
                "feature_count_total": int(len(cols)),
                "feature_screen_passed": 0,
                "feature_screen_total": int(len(cols)),
                "selected_features": [],
                "feature_family_diagnostics": feature_family_coverage([], feature_family_patterns),
                "val_weeks": int(val_weeks),
                "val_mode": val_mode,
            })
            continue

        model, train_pred, test_pred, best_iteration, fit_mode, test_pred_diag = _fit_catboost_with_guard(train, fit, val, test, passing_cols, window_params)
        if model is None or fit_mode == "skipped_zero_features":
            reason = "ic_screen_zero_features"
            print(f"  SKIP: {reason}")
            window_rows.append({
                **base_skip,
                "skip_reason": reason,
                "feature_count": 0,
                "feature_count_total": int(len(cols)),
                "feature_screen_passed": 0,
                "feature_screen_total": int(len(cols)),
                "selected_features": [],
                "feature_family_diagnostics": feature_family_coverage([], feature_family_patterns),
                "val_weeks": int(val_weeks),
                "val_mode": val_mode,
            })
            continue
        train_scored = train[["date", "ticker", TARGET_COL]].copy()
        test_scored = test[["date", "ticker", TARGET_COL]].copy()
        train_scored["prediction"] = train_pred
        test_scored["prediction"] = test_pred
        train_ic = float(ic_by_date(train_scored, "prediction").mean())
        test_ic = float(ic_by_date(test_scored, "prediction").mean())
        ratio_raw, ratio, ratio_capped = train_test_ratio(train_ic, test_ic)
        floor_excluded = bool(
            test_ic_floor is not None
            and np.isfinite(test_ic)
            and test_ic < float(test_ic_floor)
            and not bool(split.get("aggregate_excluded", False))
        )
        aggregate_excluded = bool(split.get("aggregate_excluded", False) or floor_excluded or family_incomplete_excluded)
        event_label = split.get("event_label")
        if floor_excluded:
            event_label = f"test_ic_below_floor_{test_ic_floor}"
            print(f"  -> test_IC floor exclusion: {test_ic:+.4f} < {test_ic_floor:+.4f}")
        if family_incomplete_excluded:
            family_label = "family_incomplete_missing_" + "_".join(family_diag["missing_families"])
            event_label = family_label if not event_label else f"{event_label}|{family_label}"
        row = {
            "exp_id": exp_id,
            "candidate": candidate,
            "window_id": window_id,
            "train_start": split["train_start"],
            "train_end": split["train_end"],
            "test_start": split["test_start"],
            "test_end": split["test_end"],
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "aggregate_excluded": aggregate_excluded,
            "event_label": event_label,
            "test_ic_floor_excluded": floor_excluded,
            "train_policy": split.get("train_policy"),
            "warmup_window": bool(capacity["warmup_window"]),
            "capacity_tier": capacity["capacity_tier"],
            "requested_min_train_rows": int(min_train_rows),
            "skipped": False,
            "feature_count": int(len(passing_cols)),
            "feature_count_total": int(len(cols)),
            "feature_screen_passed": int(len(passing_cols)),
            "feature_screen_total": int(len(cols)),
            "selected_features": passing_cols,
            "feature_family_diagnostics": family_diag,
            "feature_family_complete": bool(family_diag["is_family_complete"]),
            "family_incomplete_excluded": bool(family_incomplete_excluded),
            "missing_feature_families": family_diag["missing_families"],
            "earnings_feature_count": int(family_diag["earnings_feature_count"]),
            "val_weeks": int(val_weeks),
            "val_mode": val_mode,
            "train_ic": train_ic,
            "test_ic": test_ic,
            "ratio": ratio,
            "ratio_raw": ratio_raw,
            "ratio_capped": ratio_capped,
            "best_iteration": best_iteration,
            "fit_mode": fit_mode,
            **test_pred_diag,
        }
        if row["prediction_degenerate"]:
            print(
                f"  WARNING: prediction dispersion remains weak "
                f"(std={row['prediction_std']}, unique={row['prediction_unique']})"
            )
        print(f"  [{candidate}] train_IC={train_ic:+.4f} test_IC={test_ic:+.4f} ratio={ratio:.2f}x raw={ratio_raw:.2f}x mode={fit_mode}")
        window_rows.append(row)
        gc.collect()
    summary = log_aggregate(exp_id, candidate, window_rows)
    return summary, window_rows


def save_results(exp_id: str, results: dict[str, Any], audit: dict[str, Any], feature_list: list[str], output_dir: str | Path | None = None) -> None:
    out = Path(output_dir or os.environ.get("NORTHSTAR_OUTPUT_DIR") or (Path("/kaggle/working") if Path("/kaggle/working").exists() else PROJECT_ROOT / "tmp" / "kaggle_results" / "production_runs"))
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "exp_id": exp_id,
        "run_datetime": datetime.now().isoformat(),
        "dataset_audit": audit,
        "feature_count": len(feature_list),
        **results,
    }
    stem = exp_id.lower().replace("-", "_")
    summary_path = out / f"{stem}_summary.json"
    summary_path.write_text(json.dumps(json_safe(payload), indent=2), encoding="utf-8")
    if results.get("window_results"):
        pd.DataFrame(results["window_results"]).to_csv(out / f"{stem}_windows.csv", index=False)
    if results.get("table_rows"):
        pd.DataFrame(results["table_rows"]).to_csv(out / f"{stem}_table.csv", index=False)
    print(f"  Results written to {summary_path}")


def parser_for(exp_id: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--feature-policy", choices=["safe", "full"], default="safe")
    return parser


def latest_metadata(bundle: DatasetBundle) -> pd.DataFrame:
    meta = bundle.metadata.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates("ticker", keep="last")
    for col in ["sector", "broad_sector", "subsector"]:
        if col in meta.columns:
            meta[col] = meta[col].fillna("Unknown").astype(str)
    return meta


def merge_metadata(bundle: DatasetBundle, frame: pd.DataFrame | None = None) -> pd.DataFrame:
    base = frame.copy() if frame is not None else bundle.features.copy()
    meta_cols = [c for c in bundle.metadata.columns if c not in set(base.columns) or c in {"date", "ticker"}]
    meta = bundle.metadata[meta_cols].drop_duplicates(["date", "ticker"])
    merged = base.merge(meta, on=["date", "ticker"], how="left", sort=False)
    if "sector" in merged.columns:
        merged["sector"] = merged["sector"].fillna("Unknown").astype(str)
    return merged


def merge_regimes(bundle: DatasetBundle, frame: pd.DataFrame | None = None) -> pd.DataFrame:
    base = frame.copy() if frame is not None else bundle.features.copy()
    regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id", "subtle_period_id"] if c in bundle.regimes.columns]
    return base.merge(bundle.regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)


def resolve_factor(df: pd.DataFrame, factor: str) -> str | None:
    for col in ANCHOR_FACTOR_ALIASES.get(factor, [factor]):
        if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().mean() > 0.05:
            return col
    return None


def run_factor_ic_table(bundle: DatasetBundle, factors: list[str], frame: pd.DataFrame | None = None) -> list[dict[str, Any]]:
    data = frame.copy() if frame is not None else bundle.features.copy()
    rows: list[dict[str, Any]] = []
    for factor in factors:
        col = resolve_factor(data, factor)
        if col is None:
            rows.append({"factor": factor, "resolved_col": None, "status": "missing"})
            continue
        series = ic_by_date(data.rename(columns={col: "score"}), "score")
        summary = summarize_ic_values(series.tolist())
        rows.append({"factor": factor, "resolved_col": col, "status": "ok", **summary})
    return rows
