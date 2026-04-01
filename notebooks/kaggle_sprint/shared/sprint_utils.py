"""Shared utilities for the Northstar Kaggle research sprint."""

from __future__ import annotations

import gc
import json
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn


FEATURE_EXPORT_CANDIDATES = (
    "northstar_features.parquet",
    "northstar_features_v2.parquet",
)
MODEL_FEATURE_MANIFEST = "northstar_model_feature_names.json"

REQUIRED_EXPORT_FILES = (
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
)

DEFAULT_PROTECTED_FEATURES = (
    "eps_sue_decay",
    "rev_sue_decay",
    "eps_sue",
    "agreement_score",
    "agreement_score_cs_rank",
    "agreement_score_cs_z",
    "earnings_quality_ratio",
    "earnings_quality_ratio_cs_rank",
    "earnings_quality_ratio_cs_z",
    "accruals_ratio",
    "cash_conversion",
    "posterior_gap",
    "roe_qoq_change",
    "piotroski_fscore",
    "rating_numeric_cs_z",
    "ret_5d",
    "ret_5d_cs_rank",
    "ret_5d_cs_z",
    "ret_5d_sector_rel",
)

DEFAULT_RAW_FINANCIAL_FEATURES = (
    "gross_profit",
    "inventory",
    "ebitda",
    "lease_liabilities",
    "net_income",
    "operating_income",
    "revenue",
    "interest_expense",
    "cost_of_revenue",
    "total_debt",
    "working_capital",
    "operating_cash_flow",
    "free_cash_flow",
    "receivables",
    "payables",
)

DEFAULT_REDUCED_EXCLUDE_REGEX = r"^(rbi_|yield_curve|gst_|power_|screener_)"

DEFAULT_ANCHOR_FEATURES = (
    "eps_sue_decay",
    "rev_sue_decay",
    "eps_sue",
    "rev_sue",
    "earnings_quality_ratio_cs_rank",
    "earnings_quality_ratio_cs_z",
    "agreement_score",
    "agreement_score_cs_rank",
    "agreement_score_cs_z",
    "accruals_ratio_cs_rank",
    "accruals_ratio_cs_z",
    "eps_revision_accel",
    "combined_revision_score_cs_z",
    "mom_20d_vol_adj_cs_rank",
    "sector_quality_composite_cs_rank",
    "bulk_net_institutional_21d_cs_rank",
    "bulk_net_fii_21d_cs_rank",
    "piotroski_fscore",
    "cash_conversion",
    "roe_qoq_change",
)

DEFAULT_HIGH_VOLATILITY_REGIMES = {
    "high_vol|uptrend|expansion",
    "high_vol|downtrend|expansion",
    "high_vol|uptrend|contraction",
    "high_vol|downtrend|contraction",
}


def _safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    left_arr = np.asarray(left, dtype=float)
    right_arr = np.asarray(right, dtype=float)
    mask = np.isfinite(left_arr) & np.isfinite(right_arr)
    if int(mask.sum()) < 5:
        return 0.0
    corr, _ = spearmanr(left_arr[mask], right_arr[mask])
    return float(corr) if np.isfinite(corr) else 0.0


def _make_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _make_serializable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(value) for value in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        value = float(obj)
        return None if np.isnan(value) or np.isinf(value) else value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Series):
        return {str(key): _make_serializable(value) for key, value in obj.to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, float):
        return None if np.isnan(obj) or np.isinf(obj) else obj
    return obj


def normalize_raw_financial_frames(
    train_features: pd.DataFrame,
    test_features: pd.DataFrame,
    *,
    raw_financial_features: list[str] | tuple[str, ...] | None = None,
    denominator_feature: str = "total_assets",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert absolute INR financial statement fields into scale-free ratios before scaling.

    This keeps raw statement size proxies from dominating the ranking models whenever
    the export contains a usable asset base column.
    """

    raw_features = list(raw_financial_features or DEFAULT_RAW_FINANCIAL_FEATURES)
    if denominator_feature not in train_features.columns or denominator_feature not in test_features.columns:
        return train_features, test_features

    train_out = train_features.copy()
    test_out = test_features.copy()

    denom_train = train_out[denominator_feature].astype(float).abs().replace([np.inf, -np.inf], np.nan)
    denom_test = test_out[denominator_feature].astype(float).abs().replace([np.inf, -np.inf], np.nan)

    fallback = float(denom_train.median(skipna=True))
    if not np.isfinite(fallback) or fallback <= 0.0:
        fallback = 1.0
    floor = max(fallback * 1e-4, 1.0)

    denom_train = denom_train.fillna(fallback).clip(lower=floor)
    denom_test = denom_test.fillna(fallback).clip(lower=floor)

    for feature in raw_features:
        if feature == denominator_feature:
            continue
        if feature not in train_out.columns or feature not in test_out.columns:
            continue
        train_out[feature] = train_out[feature].astype(float) / denom_train
        test_out[feature] = test_out[feature].astype(float) / denom_test

    return train_out, test_out


def build_xgb_groups(dates_array: np.ndarray) -> list[int]:
    """
    Builds group sizes for XGBRanker from an array of dates.
    Each unique date forms one group (one cross-section to rank within).

    CRITICAL: This is the fix for XGBoost ratio=30x.
    Prior code passed group=[len(y_train)] creating one massive group.
    This function creates per-date groups of 97-493 rows each.

    Args:
        dates_array: numpy array of date values (any comparable type)

    Returns:
        list of ints, one per unique date, summing to len(dates_array)

    Example:
        dates = ['2022-01-01'] * 97 + ['2022-01-08'] * 97
        groups = build_xgb_groups(dates)
        # groups = [97, 97]
    """

    safe_dates = np.asarray(dates_array).astype(str, copy=False).reshape(-1)
    if safe_dates.size == 0:
        return []

    groups: list[int] = []
    current = safe_dates[0]
    count = 1
    for value in safe_dates[1:]:
        if value == current:
            count += 1
        else:
            groups.append(int(count))
            current = value
            count = 1
    groups.append(int(count))
    return groups


def to_group_relevance(y_values, groups, levels: int = 5) -> np.ndarray:
    """
    Converts continuous labels into per-group integer relevance labels for ranking.

    XGBoost rankers require integer labels for evaluation datasets. Returning a
    stable int32 array here keeps train/eval label handling consistent across the
    notebooks and the shared smoke tests.
    """

    y_arr = np.asarray(y_values, dtype=float).reshape(-1)
    labels = np.zeros(len(y_arr), dtype=np.int32)
    cursor = 0
    for group_size in groups:
        size = int(group_size)
        if size <= 0:
            continue
        window = y_arr[cursor : cursor + size]
        if size == 1:
            labels[cursor] = 0
            cursor += 1
            continue
        order = np.argsort(np.argsort(window, kind="mergesort"), kind="mergesort")
        scaled = np.floor(order.astype(float) * float(levels - 1) / float(size - 1))
        labels[cursor : cursor + size] = scaled.astype(np.int32)
        cursor += size
    return labels.astype(np.int32)


def select_features_for_regime(
    X_train: np.ndarray,
    feature_names: list,
    regime: str,
    anchor_features: list,
    high_vol_regimes: set,
    min_anchor: int = 10,
) -> tuple[np.ndarray, list[str]]:
    """
    Returns (X_train_selected, selected_names) based on regime.

    In high-volatility regimes, prefer the anchor feature set if enough anchors
    are present and active. Otherwise fall back to all active features.
    """

    X_arr = np.asarray(X_train, dtype=np.float32)
    std = np.nanstd(X_arr, axis=0)
    means = np.nanmean(X_arr, axis=0)
    active_mask = np.isfinite(std) & ((std > 1e-6) | (np.abs(means) > 1e-6))
    active_indices = np.flatnonzero(active_mask).astype(int).tolist()
    if not active_indices:
        active_indices = list(range(X_arr.shape[1]))

    active_names = [feature_names[idx] for idx in active_indices]
    active_name_set = set(active_names)
    if str(regime) in set(high_vol_regimes):
        anchor_names = [name for name in anchor_features if name in active_name_set]
        if len(anchor_names) >= int(min_anchor):
            indices = [feature_names.index(name) for name in anchor_names]
            return X_arr[:, indices], anchor_names

    return X_arr[:, active_indices], active_names


def compute_regime_ic_breakdown(results: dict, regime_df: pd.DataFrame) -> dict:
    """
    Groups walk-forward window results by regime and computes mean IC per regime.

    Returns:
        {regime: {mean_ic, n_windows, best_window, worst_window}}
    """

    rows: list[dict[str, Any]] = []
    for window in results.get("windows", []):
        if "error" in window:
            continue
        regime = window.get("regime")
        if (regime is None or regime == "unknown") and regime_df is not None and not regime_df.empty:
            test_start = pd.Timestamp(window.get("test_start")) if window.get("test_start") else None
            test_end = pd.Timestamp(window.get("test_end")) if window.get("test_end") else None
            if test_start is not None and test_end is not None:
                window_regime = regime_df.loc[regime_df["date"].between(test_start, test_end)].copy()
                if not window_regime.empty and "regime" in window_regime.columns:
                    counts = window_regime["regime"].astype(str).value_counts()
                    regime = str(counts.index[0]) if not counts.empty else "unknown"
        rows.append(
            {
                "window_id": int(window.get("window_id", 0)),
                "regime": str(regime or "unknown"),
                "test_ic": float(window.get("test_ic", np.nan)),
            }
        )

    if not rows:
        return {}

    frame = pd.DataFrame(rows)
    output: dict[str, Any] = {}
    for regime, regime_frame in frame.groupby("regime", dropna=False):
        clean = regime_frame.dropna(subset=["test_ic"]).copy()
        if clean.empty:
            continue
        best_row = clean.loc[clean["test_ic"].idxmax()]
        worst_row = clean.loc[clean["test_ic"].idxmin()]
        output[str(regime if pd.notna(regime) else "unknown")] = {
            "mean_ic": float(clean["test_ic"].mean()),
            "n_windows": int(len(clean)),
            "best_window": {
                "window_id": int(best_row["window_id"]),
                "test_ic": float(best_row["test_ic"]),
            },
            "worst_window": {
                "window_id": int(worst_row["window_id"]),
                "test_ic": float(worst_row["test_ic"]),
            },
        }
    return output


def check_session_budget(
    session_start: float,
    model_name: str,
    estimated_minutes: float,
    limit_hours: float = 8.5,
) -> bool:
    """
    Returns True if enough session budget remains for the requested model run.
    """

    elapsed = max(0.0, time.time() - float(session_start))
    remaining_seconds = max(0.0, float(limit_hours) * 3600.0 - elapsed)
    needed_seconds = max(0.0, float(estimated_minutes) * 60.0)
    if remaining_seconds >= needed_seconds:
        return True
    print(
        f"WARNING: Skipping {model_name} because only {remaining_seconds / 60.0:.0f} "
        f"minutes remain in the session and the model needs about {estimated_minutes:.0f} minutes."
    )
    return False


def normalize_financial_features(
    X_train: np.ndarray,
    X_test: np.ndarray,
    feature_names: list[str],
    allow_skip_if_scaled: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Normalizes raw financial statement features by their cross-sectional median.
    Applied per window, fit on train only, applied to test.

    These raw INR features act as market cap proxies because larger companies
    have larger absolute financial values. Normalization converts them from
    size proxies to quality/scale indicators.

    RAW_FINANCIAL_FEATURES = features that are in absolute currency units.

    Returns:
        (X_train_normalized, X_test_normalized) - copies, not in-place
    """

    raw_financial_names = [
        "gross_profit",
        "inventory",
        "ebitda",
        "lease_liabilities",
        "net_income",
        "operating_income",
        "revenue",
        "interest_expense",
        "cost_of_revenue",
        "total_debt",
        "working_capital",
        "total_assets",
        "operating_cash_flow",
        "free_cash_flow",
        "receivables",
        "payables",
        "cash_and_equivalents",
        "equity",
        "shares_outstanding",
        "payables",
    ]

    X_tr = np.asarray(X_train, dtype=np.float32).copy()
    X_te = np.asarray(X_test, dtype=np.float32).copy()

    for feat_name in raw_financial_names:
        if feat_name not in feature_names:
            continue
        idx = feature_names.index(feat_name)
        median_val = float(np.nanmedian(np.abs(X_tr[:, idx])))
        col_std = float(np.nanstd(X_tr[:, idx]))
        if allow_skip_if_scaled and 0.4 <= col_std <= 2.5 and median_val <= 5.0:
            continue
        if np.isfinite(median_val) and median_val > 1.0:
            X_tr[:, idx] = X_tr[:, idx] / median_val
            X_te[:, idx] = X_te[:, idx] / median_val

    return X_tr, X_te


def listnet_loss(
    scores: torch.Tensor,
    targets: torch.Tensor,
    temperature: float = 0.5,
    top_k_fraction: float = 0.5,
) -> torch.Tensor:
    """
    ListNet ranking loss.

    Uses cross-entropy between softmax of predicted scores and softmax of targets.
    More stable than pairwise loss in low-dispersion regimes (bear markets)
    because it does not require pairwise differences to be non-zero.
    """

    scores = scores.reshape(-1)
    targets = targets.reshape(-1)
    n = len(scores)
    if n < 4:
        return nn.functional.mse_loss(scores, targets)

    k = max(4, int(n * top_k_fraction))
    top_idx = torch.topk(targets, k).indices
    scores_k = scores[top_idx]
    targets_k = targets[top_idx]

    targets_norm = (targets_k - targets_k.mean()) / (targets_k.std() + 1e-8)
    scores_norm = (scores_k - scores_k.mean()) / (scores_k.std() + 1e-8)

    p_targets = torch.softmax(targets_norm / temperature, dim=0)
    log_p_scores = torch.log_softmax(scores_norm / temperature, dim=0)

    return -torch.sum(p_targets * log_p_scores)


def top_ic_feature_names(
    ic_table: pd.DataFrame | None,
    available_feature_names: list[str],
    *,
    limit: int = 60,
    min_abs_ic: float = 0.0,
    exclude_regex: str | None = None,
) -> list[str]:
    """Build a reduced feature list ordered by absolute day-1 IC."""

    if ic_table is None or ic_table.empty:
        return []

    available = set(available_feature_names)
    table = ic_table.copy()
    if "feature" not in table.columns or "mean_ic" not in table.columns:
        return []
    table = table.loc[table["feature"].isin(available)].copy()
    if min_abs_ic > 0.0:
        table = table.loc[table["mean_ic"].abs() >= float(min_abs_ic)]
    if exclude_regex:
        table = table.loc[~table["feature"].astype(str).str.contains(exclude_regex, regex=True, na=False)]
    table = table.reindex(table["mean_ic"].abs().sort_values(ascending=False).index)

    chosen: list[str] = []
    for feature in table["feature"].astype(str):
        if feature not in chosen:
            chosen.append(feature)
        if len(chosen) >= int(limit):
            break
    return chosen


def select_feature_subset(
    x_train: np.ndarray,
    x_test: np.ndarray,
    feature_names: list[str],
    *,
    feature_mode: str = "full",
    reduced_feature_names: list[str] | None = None,
    protected_features: list[str] | tuple[str, ...] | None = None,
    exclude_regex: str | None = None,
    min_std: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray, list[int], list[str]]:
    """
    Apply dead-feature filtering and optional reduced/protected feature selection.
    """

    feature_mode_normalized = str(feature_mode or "full").strip().lower()
    reduced_names = set(reduced_feature_names or [])
    protected = set(protected_features or DEFAULT_PROTECTED_FEATURES)
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    std = np.nanstd(np.asarray(x_train, dtype=float), axis=0)
    active_mask = np.isfinite(std) & (std > float(min_std))
    keep_mask = active_mask.copy()

    if exclude_pattern is not None:
        excluded = np.asarray(
            [bool(exclude_pattern.search(str(feature))) for feature in feature_names],
            dtype=bool,
        )
        keep_mask &= ~excluded

    if feature_mode_normalized == "protected_only":
        protected_mask = np.asarray([feature in protected for feature in feature_names], dtype=bool)
        keep_mask &= protected_mask
    elif feature_mode_normalized == "reduced":
        if reduced_names:
            reduced_mask = np.asarray(
                [(feature in reduced_names) or (feature in protected) for feature in feature_names],
                dtype=bool,
            )
            keep_mask &= reduced_mask
    elif feature_mode_normalized not in {"full", "all"}:
        raise ValueError(f"Unknown feature_mode={feature_mode!r}")

    indices = np.flatnonzero(keep_mask).astype(int).tolist()
    if not indices:
        indices = np.flatnonzero(active_mask).astype(int).tolist()
    if not indices:
        indices = list(range(len(feature_names)))

    selected_names = [feature_names[idx] for idx in indices]
    return (
        np.asarray(x_train, dtype=np.float32)[:, indices],
        np.asarray(x_test, dtype=np.float32)[:, indices],
        indices,
        selected_names,
    )


def expand_feature_importance(importance: np.ndarray | list[float], selected_indices: list[int], total_features: int) -> np.ndarray:
    """Map an importance vector from a reduced feature set back to the full feature space."""

    full = np.zeros(int(total_features), dtype=float)
    arr = np.asarray(importance, dtype=float).reshape(-1)
    for local_idx, feature_idx in enumerate(selected_indices):
        if local_idx >= arr.size:
            break
        full[int(feature_idx)] = float(arr[local_idx])
    return full


def _resolve_feature_export(path: Path) -> Path | None:
    for filename in FEATURE_EXPORT_CANDIDATES:
        candidate = path / filename
        if candidate.exists():
            return candidate
    return None


def _looks_like_export_dir(path: Path) -> bool:
    return path.is_dir() and _resolve_feature_export(path) is not None and all(
        (path / filename).exists() for filename in REQUIRED_EXPORT_FILES
    )


def _resolve_data_dir(data_dir: Path | None) -> Path:
    if data_dir is not None:
        resolved = Path(data_dir)
        if _looks_like_export_dir(resolved):
            return resolved
        raise ValueError(f"Could not find required Northstar export files in {resolved}")

    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        exact = kaggle_input / "northstar-v4-validation-data"
        if _looks_like_export_dir(exact):
            return exact
        for candidate in sorted(kaggle_input.iterdir()):
            if _looks_like_export_dir(candidate):
                return candidate
        for feature_name in FEATURE_EXPORT_CANDIDATES:
            for candidate in sorted(kaggle_input.rglob(feature_name)):
                if _looks_like_export_dir(candidate.parent):
                    return candidate.parent

    for candidate in [
        Path.cwd(),
        Path.cwd() / "northstar_kaggle_data",
        Path.home() / "Desktop" / "northstar_kaggle_data",
    ]:
        if _looks_like_export_dir(candidate):
            return candidate

    raise ValueError("Cannot resolve Northstar Kaggle export directory.")


def get_window_data(
    features_df: pd.DataFrame,
    split: dict[str, Any],
    feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (X_train, y_train, X_test, y_test, train_dates, test_dates).

    - Date filtering by train_start/train_end/test_start/test_end
    - NaN imputation: median per column, fit on train only
    - StandardScaler: fit on train only, applied to test
    - Financial normalization: fit on train only, applied to test
    - Target: target_weekly_return
    """

    train_start = pd.Timestamp(split["train_start"])
    train_end = pd.Timestamp(split["train_end"])
    test_start = pd.Timestamp(split["test_start"])
    test_end = pd.Timestamp(split["test_end"])

    train_df = features_df.loc[features_df["date"].between(train_start, train_end)].copy()
    test_df = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
    train_df = train_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
    test_df = test_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")

    if train_df.empty or test_df.empty:
        raise ValueError(
            f"Window {split.get('window_id', '?')} has empty train/test slice "
            f"(train={len(train_df)}, test={len(test_df)})"
        )

    train_features = train_df[feature_names].replace([np.inf, -np.inf], np.nan)
    test_features = test_df[feature_names].replace([np.inf, -np.inf], np.nan)
    medians = train_features.median(axis=0, numeric_only=True).fillna(0.0)
    train_features = train_features.fillna(medians)
    test_features = test_features.fillna(medians)

    X_train_raw = train_features.to_numpy(dtype=np.float32)
    X_test_raw = test_features.to_numpy(dtype=np.float32)
    X_train_raw, X_test_raw = normalize_financial_features(X_train_raw, X_test_raw, feature_names)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
    X_test = scaler.transform(X_test_raw).astype(np.float32)
    y_train = train_df["target_weekly_return"].to_numpy(dtype=np.float32)
    y_test = test_df["target_weekly_return"].to_numpy(dtype=np.float32)
    train_dates = train_df["date"].to_numpy()
    test_dates = test_df["date"].to_numpy()

    return X_train, y_train, X_test, y_test, train_dates, test_dates


class SprintDataLoader:
    """
    Loads and prepares the Northstar feature matrix for the full sprint.
    Handles the fact that the Kaggle dataset has 97 tickers and 20 windows
    anchored from 2022-04-18 to 2023-10-27.
    """

    def __init__(self):
        self.last_window_context: dict[str, Any] = {}
        self._features_df: pd.DataFrame | None = None
        self._model_feature_names: list[str] = []

    def load(self, data_dir: Path | None) -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
        """
        Returns (features_df, splits, regime_df).
        Prints:
            rows, tickers, date_range, feature_count, target_coverage, n_windows
        """

        resolved_dir = _resolve_data_dir(data_dir)
        feature_path = _resolve_feature_export(resolved_dir)
        if feature_path is None:
            raise ValueError(f"Cannot resolve a supported feature export in {resolved_dir}")

        features_df = pd.read_parquet(feature_path)
        features_df["date"] = pd.to_datetime(features_df["date"], errors="coerce")
        features_df["ticker"] = features_df["ticker"].astype("string")
        features_df = features_df.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
        manifest_path = resolved_dir / MODEL_FEATURE_MANIFEST
        if manifest_path.exists():
            try:
                requested = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                requested = []
            requested_set = {str(value) for value in requested}
            self._model_feature_names = [
                column for column in features_df.columns if column in requested_set
            ]
        else:
            self._model_feature_names = self._infer_model_feature_names(features_df)

        metadata_path = resolved_dir / "northstar_metadata.parquet"
        if metadata_path.exists():
            metadata_df = pd.read_parquet(metadata_path)
            metadata_df["date"] = pd.to_datetime(metadata_df["date"], errors="coerce")
            metadata_df["ticker"] = metadata_df["ticker"].astype("string")
            metadata_cols = [col for col in metadata_df.columns if col not in {"date", "ticker"}]
            if metadata_cols:
                features_df = features_df.merge(
                    metadata_df[["date", "ticker"] + metadata_cols],
                    on=["date", "ticker"],
                    how="left",
                    suffixes=("", "__meta"),
                )
                duplicate_meta_cols = [col for col in features_df.columns if col.endswith("__meta")]
                if duplicate_meta_cols:
                    features_df = features_df.drop(columns=duplicate_meta_cols)
        features_df.attrs["model_feature_names"] = list(self._model_feature_names)

        with (resolved_dir / "northstar_walk_forward_splits.json").open("r", encoding="utf-8") as handle:
            splits = json.load(handle)

        regime_df = pd.read_parquet(resolved_dir / "northstar_regime_labels.parquet")
        regime_df["date"] = pd.to_datetime(regime_df["date"], errors="coerce")
        if "regime" not in regime_df.columns:
            vol = regime_df.get("vol_regime", "unknown")
            trend = regime_df.get("trend_regime", "unknown")
            cycle = regime_df.get("cycle_regime", "unknown")
            regime_df["regime"] = (
                vol.astype(str) + "|" + trend.astype(str) + "|" + cycle.astype(str)
            )

        self._features_df = features_df
        feature_names = self.get_feature_names(features_df)
        print(
            "Loaded Northstar sprint data:\n"
            f"  rows:            {len(features_df):,}\n"
            f"  tickers:         {features_df['ticker'].nunique():,}\n"
            f"  date_range:      {features_df['date'].min().date()} to {features_df['date'].max().date()}\n"
            f"  feature_count:   {len(feature_names):,}\n"
            f"  target_coverage: {features_df['target_weekly_return'].notna().mean() * 100.0:.2f}%\n"
            f"  n_windows:       {len(splits):,}"
        )
        return features_df, splits, regime_df

    def get_window_arrays(
        self,
        features_df,
        split: dict,
        feature_names: list[str],
        config: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns (X_train, y_train, X_test, y_test).
        - Date filtering by train_start/train_end/test_start/test_end
        - NaN imputation: median per column, fit on train only
        - StandardScaler: fit on train only, applied to test
        - Target: target_weekly_return column
        - Prints: train/test rows, target coverage
        """

        cfg = dict(config or {})
        if bool(cfg.get("normalize_raw_financials", False)):
            train_start = pd.Timestamp(split["train_start"])
            train_end = pd.Timestamp(split["train_end"])
            test_start = pd.Timestamp(split["test_start"])
            test_end = pd.Timestamp(split["test_end"])

            train_df = features_df.loc[features_df["date"].between(train_start, train_end)].copy()
            test_df = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
            train_df = train_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
            test_df = test_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")

            if train_df.empty or test_df.empty:
                raise ValueError(
                    f"Window {split.get('window_id', '?')} has empty train/test slice "
                    f"(train={len(train_df)}, test={len(test_df)})"
                )

            train_features = train_df[feature_names].replace([np.inf, -np.inf], np.nan)
            test_features = test_df[feature_names].replace([np.inf, -np.inf], np.nan)
            train_features, test_features = normalize_raw_financial_frames(
                train_features,
                test_features,
                raw_financial_features=cfg.get("raw_financial_features"),
                denominator_feature=str(cfg.get("financial_denominator_feature", "total_assets")),
            )
            medians = train_features.median(axis=0, numeric_only=True).fillna(0.0)
            train_features = train_features.fillna(medians)
            test_features = test_features.fillna(medians)
            scaler = StandardScaler()
            x_train = scaler.fit_transform(train_features.to_numpy(dtype=np.float32)).astype(np.float32)
            x_test = scaler.transform(test_features.to_numpy(dtype=np.float32)).astype(np.float32)
            y_train = train_df["target_weekly_return"].to_numpy(dtype=np.float32)
            y_test = test_df["target_weekly_return"].to_numpy(dtype=np.float32)
            train_dates = train_df["date"].to_numpy()
            test_dates = test_df["date"].to_numpy()
        else:
            x_train, y_train, x_test, y_test, train_dates, test_dates = get_window_data(
                features_df,
                split,
                feature_names,
            )
            train_start = pd.Timestamp(split["train_start"])
            train_end = pd.Timestamp(split["train_end"])
            test_start = pd.Timestamp(split["test_start"])
            test_end = pd.Timestamp(split["test_end"])
            train_df = features_df.loc[features_df["date"].between(train_start, train_end)].copy()
            test_df = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
            train_df = train_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
            test_df = test_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")

        train_counts = train_df.groupby("date", sort=False).size().tolist()
        test_counts = test_df.groupby("date", sort=False).size().tolist()
        self.last_window_context = {
            "train_dates": train_dates,
            "test_dates": test_dates,
            "train_tickers": train_df["ticker"].astype(str).to_numpy(),
            "test_tickers": test_df["ticker"].astype(str).to_numpy(),
            "train_group_sizes": train_counts,
            "test_group_sizes": test_counts,
            "train_df": train_df[["date", "ticker", "target_weekly_return"]].copy(),
            "test_df": test_df[["date", "ticker", "target_weekly_return"]].copy(),
        }

        print(
            f"Window {split.get('window_id', '?')}: "
            f"train rows={len(train_df):,} "
            f"test rows={len(test_df):,} "
            f"target coverage={test_df['target_weekly_return'].notna().mean() * 100.0:.2f}%"
        )
        return x_train, y_train, x_test, y_test

    def get_window_data(
        self,
        features_df: pd.DataFrame,
        split: dict[str, Any],
        feature_names: list[str],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Class wrapper around the standalone get_window_data helper."""

        return get_window_data(features_df, split, feature_names)

    def get_feature_names(self, features_df) -> list[str]:
        """
        Returns numeric feature columns excluding:
        date, ticker, target_weekly_return, forward_return_5d,
        any column ending in __realized
        """

        stored = list(features_df.attrs.get("model_feature_names") or [])
        if stored:
            return stored
        return self._infer_model_feature_names(features_df)

    @staticmethod
    def _infer_model_feature_names(features_df) -> list[str]:
        exclude = {"date", "ticker", "target_weekly_return", "forward_return_5d"}
        numeric = set(features_df.select_dtypes(include=[np.number]).columns)
        return [
            column
            for column in features_df.columns
            if column in numeric and column not in exclude and not column.endswith("__realized")
        ]

    def get_regime_for_window(self, regime_df, split: dict) -> str:
        """
        Returns dominant regime string during test window.
        Falls back to 'unknown' if no regime data for that period.
        """

        test_start = pd.Timestamp(split["test_start"])
        test_end = pd.Timestamp(split["test_end"])
        window_regime = regime_df.loc[regime_df["date"].between(test_start, test_end)].copy()
        if window_regime.empty:
            return "unknown"
        if "regime" in window_regime.columns:
            counts = window_regime["regime"].astype(str).value_counts()
            return str(counts.index[0]) if not counts.empty else "unknown"
        return "unknown"


class SprintWalkForward:
    """
    Unified walk-forward engine used by both tracks.
    Handles tree models and neural network models with the same interface.
    """

    GATE_IC = 0.015
    GATE_RATIO = 2.5
    GATE_HIT = 0.51

    CATBOOST_BASELINE = {
        "mean_test_ic": 0.0277,
        "mean_train_test_ratio": 6.9908,
        "mean_hit_rate": 0.5126,
        "feature_stability_corr": 0.7799,
    }

    @staticmethod
    def _checkpoint_path(output_dir: Path, model_name: str) -> Path:
        return output_dir / f"{model_name.lower().replace(' ', '_')}_checkpoint.json"

    def load_checkpoint(self, output_dir: Path, model_name: str) -> dict[str, Any]:
        """Loads a saved walk-forward checkpoint if present."""

        checkpoint_path = self._checkpoint_path(Path(output_dir), model_name)
        if not checkpoint_path.exists():
            return {}
        try:
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def run(self, model_name, model_factory, features_df, splits, regime_df, feature_names, config) -> dict:
        """
        model_factory signature:
            (X_train, y_train, X_test, feature_names, config)
            -> (train_preds, test_preds, importance_vec_or_None)

        Runs all windows. Checkpoints after each.
        On exception: records error, continues to next window.

        Returns full results dict with:
        - windows: list of per-window metrics
        - feature_importances: {window_id: array}
        - model_name, config
        """

        loader = SprintDataLoader()
        output_dir = Path(config.get("output_dir", "/kaggle/working" if Path("/kaggle").exists() else "./kaggle_results"))
        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self._checkpoint_path(output_dir, model_name)
        force_rerun_windows = {
            int(window_id)
            for window_id in config.get("force_rerun_window_ids", [])
            if str(window_id).strip()
        }

        results: dict[str, Any] = {}
        if checkpoint_path.exists() and bool(config.get("resume_from_checkpoint", True)):
            results = self.load_checkpoint(output_dir, model_name)
            if results:
                results.setdefault("model_name", model_name)
                results.setdefault("model", model_name)
                results.setdefault("config", dict(config))
                results.setdefault("windows_total", len(splits))
                results.setdefault("feature_names", list(feature_names))
                results.setdefault("feature_importances", {})
                results.setdefault("windows", [])
                results.setdefault("run_started_at", datetime.now(timezone.utc).isoformat())
                print(
                    f"Resuming {model_name} from checkpoint with "
                    f"{len(results.get('windows', []))} recorded windows"
                )

        if not results:
            results = {
                "model_name": model_name,
                "model": model_name,
                "config": dict(config),
                "windows_total": len(splits),
                "feature_names": list(feature_names),
                "feature_importances": {},
                "windows": [],
                "run_started_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            retained_windows = []
            for window in results.get("windows", []):
                window_id = window.get("window_id")
                if window_id is None:
                    continue
                if "error" in window:
                    continue
                if int(window_id) in force_rerun_windows:
                    continue
                retained_windows.append(window)
            results["windows"] = retained_windows
            results["feature_importances"] = {
                str(window_id): value
                for window_id, value in results.get("feature_importances", {}).items()
                if int(window_id) not in force_rerun_windows
            }

        completed_window_ids = {
            int(window.get("window_id"))
            for window in results.get("windows", [])
            if (
                window.get("window_id") is not None
                and "error" not in window
                and int(window.get("window_id")) not in force_rerun_windows
            )
        }

        for index, raw_split in enumerate(splits, start=1):
            split = dict(raw_split)
            split["window_id"] = int(split.get("window_id", index))
            split["regime"] = split.get("regime") or loader.get_regime_for_window(regime_df, split)
            if split["window_id"] in completed_window_ids:
                print(f"{split['window_id']:02d} | resume skip")
                continue
            try:
                x_train, y_train, x_test, y_test = loader.get_window_arrays(features_df, split, feature_names, config=config)
                run_config = dict(config)
                run_config["window_id"] = split["window_id"]
                run_config["window_regime"] = split["regime"]
                run_config["window_context"] = loader.last_window_context
                train_preds, test_preds, importance = model_factory(x_train, y_train, x_test, feature_names, run_config)

                metrics = self._compute_metrics(y_train, train_preds, y_test, test_preds, split)
                window_record = {
                    **metrics,
                    "train_start": split.get("train_start"),
                    "train_end": split.get("train_end"),
                    "test_start": split.get("test_start"),
                    "test_end": split.get("test_end"),
                    "n_train": int(len(y_train)),
                    "n_test": int(len(y_test)),
                    "y_train": np.asarray(y_train, dtype=float),
                    "train_preds": np.asarray(train_preds, dtype=float),
                    "test_preds": np.asarray(test_preds, dtype=float),
                    "y_test": np.asarray(y_test, dtype=float),
                }
                results["windows"].append(window_record)

                if importance is not None:
                    arr = np.asarray(importance, dtype=float).reshape(-1)
                    if arr.size == len(feature_names):
                        results["feature_importances"][str(split["window_id"])] = arr

                print(
                    f"{split['window_id']:02d} | "
                    f"train_ic={metrics['train_ic']:.4f} | "
                    f"test_ic={metrics['test_ic']:.4f} | "
                    f"ratio={metrics['train_test_ratio']:.2f} | "
                    f"hit_rate={metrics['hit_rate']:.4f}"
                )
                if float(metrics["test_ic"]) < -0.02:
                    print(
                        f"  WARNING: Large negative IC in window {split['window_id']} "
                        f"({split['regime']}) — IC={metrics['test_ic']:.4f}. "
                        "Consider regime-specific feature selection for this window."
                    )
            except Exception as exc:  # noqa: BLE001
                error_payload = {
                    "window_id": split["window_id"],
                    "train_start": split.get("train_start"),
                    "train_end": split.get("train_end"),
                    "test_start": split.get("test_start"),
                    "test_end": split.get("test_end"),
                    "regime": split.get("regime", "unknown"),
                    "error": str(exc),
                }
                results["windows"].append(error_payload)
                print(f"WARNING window {split['window_id']}: {exc}")

            checkpoint = {
                "model_name": model_name,
                "model": model_name,
                "config": dict(config),
                "windows_completed": len([window for window in results["windows"] if "error" not in window]),
                "windows_total": len(splits),
                "feature_names": list(feature_names),
                "feature_importances": results.get("feature_importances", {}),
                "windows": results["windows"],
                "run_started_at": results.get("run_started_at"),
                "checkpoint_updated_at": datetime.now(timezone.utc).isoformat(),
            }
            checkpoint_path.write_text(json.dumps(_make_serializable(checkpoint), indent=2), encoding="utf-8")

            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception:  # noqa: BLE001
                    pass
            gc.collect()

        results["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        return results

    def _compute_metrics(self, y_train, pred_train, y_test, pred_test, split) -> dict:
        """
        Computes via Spearman:
        train_ic, test_ic, train_test_ratio, hit_rate,
        top_quintile_return, bottom_quintile_return, quintile_spread,
        window_id, test_start, regime
        """

        y_train_arr = np.asarray(y_train, dtype=float)
        pred_train_arr = np.asarray(pred_train, dtype=float)
        y_test_arr = np.asarray(y_test, dtype=float)
        pred_test_arr = np.asarray(pred_test, dtype=float)

        train_ic = _safe_spearman(y_train_arr, pred_train_arr)
        test_ic = _safe_spearman(y_test_arr, pred_test_arr)
        ratio = abs(train_ic) / max(abs(test_ic), 1e-6)
        hit_rate = float(np.mean(np.sign(pred_test_arr) == np.sign(y_test_arr)))

        n = len(y_test_arr)
        q_size = max(1, n // 5)
        sorted_idx = np.argsort(pred_test_arr)
        bottom_ret = float(np.mean(y_test_arr[sorted_idx[:q_size]]))
        top_ret = float(np.mean(y_test_arr[sorted_idx[-q_size:]]))
        quintile_spread = top_ret - bottom_ret

        return {
            "window_id": int(split.get("window_id", 0)),
            "test_start": split.get("test_start", ""),
            "train_ic": round(train_ic, 6),
            "test_ic": round(test_ic, 6),
            "train_test_ratio": round(ratio, 4),
            "hit_rate": round(hit_rate, 4),
            "top_quintile_return": round(top_ret, 6),
            "bottom_quintile_return": round(bottom_ret, 6),
            "quintile_spread": round(quintile_spread, 6),
            "regime": split.get("regime", "unknown"),
        }

    def summarize(self, results: dict) -> dict:
        """
        From valid windows (no error key):
        mean_test_ic, std_test_ic, ic_ir, mean_train_test_ratio,
        mean_hit_rate, mean_quintile_spread,
        windows_completed, windows_total, windows_failed,
        passed_viability_filter (bool),
        verdict: QUALIFIED / NOT_QUALIFIED / INSUFFICIENT_DATA
        """

        windows = results.get("windows", [])
        valid_windows = [window for window in windows if "error" not in window]
        windows_total = int(results.get("windows_total", len(windows)))
        windows_completed = len(valid_windows)
        windows_failed = len(windows) - windows_completed

        if windows_completed < 3:
            return {
                "mean_test_ic": float("nan"),
                "std_test_ic": float("nan"),
                "ic_ir": float("nan"),
                "mean_train_test_ratio": float("nan"),
                "mean_hit_rate": float("nan"),
                "mean_quintile_spread": float("nan"),
                "windows_completed": windows_completed,
                "windows_total": windows_total,
                "windows_failed": windows_failed,
                "passed_viability_filter": False,
                "verdict": "INSUFFICIENT_DATA",
            }

        frame = pd.DataFrame(valid_windows)
        mean_test_ic = float(pd.to_numeric(frame["test_ic"], errors="coerce").mean())
        std_test_ic = float(pd.to_numeric(frame["test_ic"], errors="coerce").std(ddof=1)) if len(frame) > 1 else 0.0
        ic_ir = float(mean_test_ic / std_test_ic) if abs(std_test_ic) > 1e-12 else 0.0
        mean_ratio = float(pd.to_numeric(frame["train_test_ratio"], errors="coerce").mean())
        mean_hit = float(pd.to_numeric(frame["hit_rate"], errors="coerce").mean())
        mean_spread = float(pd.to_numeric(frame.get("quintile_spread"), errors="coerce").mean())

        passed = bool(
            mean_test_ic > self.GATE_IC
            and mean_ratio < self.GATE_RATIO
            and mean_hit > self.GATE_HIT
        )

        return {
            "mean_test_ic": mean_test_ic,
            "std_test_ic": std_test_ic,
            "ic_ir": ic_ir,
            "mean_train_test_ratio": mean_ratio,
            "mean_hit_rate": mean_hit,
            "mean_quintile_spread": mean_spread,
            "windows_completed": windows_completed,
            "windows_total": windows_total,
            "windows_failed": windows_failed,
            "passed_viability_filter": passed,
            "verdict": "QUALIFIED" if passed else "NOT_QUALIFIED",
        }

    def regime_breakdown(self, results: dict) -> dict:
        """
        Mean test IC grouped by regime string.
        Returns {regime: mean_ic} dict.
        """

        breakdown = compute_regime_ic_breakdown(results, pd.DataFrame())
        return {regime: float(values["mean_ic"]) for regime, values in breakdown.items()}

    def feature_stability(self, results: dict, feature_names: list[str]) -> dict:
        """
        Pairwise Spearman of importance vectors across windows.
        Returns:
        mean_pairwise_correlation, band (stable/cautious/unstable),
        top_stable_features (list), top_unstable_features (list),
        mean_importance_by_feature (dict),
        top_features_by_mean_importance (list)
        """

        feature_importances = results.get("feature_importances", {})
        cleaned: list[np.ndarray] = []
        for value in feature_importances.values():
            arr = np.asarray(value, dtype=float).reshape(-1)
            if arr.size == len(feature_names):
                cleaned.append(np.abs(arr))

        if not cleaned:
            return {
                "windows_used": 0,
                "mean_pairwise_correlation": float("nan"),
                "band": "unknown",
                "top_stable_features": [],
                "top_unstable_features": [],
                "mean_importance_by_feature": {},
                "top_features_by_mean_importance": [],
            }

        correlations: list[float] = []
        for left_idx in range(len(cleaned)):
            for right_idx in range(left_idx + 1, len(cleaned)):
                corr = _safe_spearman(cleaned[left_idx], cleaned[right_idx])
                if np.isfinite(corr):
                    correlations.append(float(corr))

        mean_corr = float(np.mean(correlations)) if correlations else float("nan")
        if np.isfinite(mean_corr) and mean_corr >= 0.70:
            band = "stable"
        elif np.isfinite(mean_corr) and mean_corr >= 0.40:
            band = "cautious"
        else:
            band = "unstable" if np.isfinite(mean_corr) else "unknown"

        stacked = np.vstack(cleaned)
        mean_importance = np.nanmean(stacked, axis=0)
        std_importance = np.nanstd(stacked, axis=0)
        cv = std_importance / np.where(np.abs(mean_importance) > 1e-12, np.abs(mean_importance), 1e-12)

        unstable_sorted = sorted(zip(feature_names, cv), key=lambda item: (-item[1], item[0]))
        stable_sorted = sorted(zip(feature_names, cv), key=lambda item: (item[1], item[0]))
        importance_sorted = sorted(zip(feature_names, mean_importance), key=lambda item: (-item[1], item[0]))

        return {
            "windows_used": len(cleaned),
            "mean_pairwise_correlation": mean_corr,
            "band": band,
            "top_stable_features": [name for name, _ in stable_sorted[:15]],
            "top_unstable_features": [name for name, _ in unstable_sorted[:15]],
            "mean_importance_by_feature": OrderedDict((name, float(score)) for name, score in importance_sorted),
            "top_features_by_mean_importance": [name for name, _ in importance_sorted[:25]],
            "top_stable_feature_cvs": OrderedDict((name, float(score)) for name, score in stable_sorted[:15]),
            "top_unstable_feature_cvs": OrderedDict((name, float(score)) for name, score in unstable_sorted[:15]),
        }

    def compare_to_catboost_baseline(self, summary: dict) -> dict:
        """
        Returns ic_improvement_pct, ratio_improvement_pct,
        hit_improvement_pct, qualifies_vs_baseline
        """

        base = self.CATBOOST_BASELINE
        mean_ic = float(summary.get("mean_test_ic", np.nan))
        mean_ratio = float(summary.get("mean_train_test_ratio", np.nan))
        mean_hit = float(summary.get("mean_hit_rate", np.nan))
        return {
            "ic_improvement_pct": ((mean_ic - base["mean_test_ic"]) / abs(base["mean_test_ic"])) * 100.0 if np.isfinite(mean_ic) else float("nan"),
            "ratio_improvement_pct": ((base["mean_train_test_ratio"] - mean_ratio) / abs(base["mean_train_test_ratio"])) * 100.0 if np.isfinite(mean_ratio) else float("nan"),
            "hit_improvement_pct": ((mean_hit - base["mean_hit_rate"]) / abs(base["mean_hit_rate"])) * 100.0 if np.isfinite(mean_hit) else float("nan"),
            "qualifies_vs_baseline": bool(
                summary.get("passed_viability_filter", False)
                and np.isfinite(mean_ic)
                and np.isfinite(mean_ratio)
                and np.isfinite(mean_hit)
                and mean_ic >= base["mean_test_ic"]
                and mean_ratio < base["mean_train_test_ratio"]
                and mean_hit >= base["mean_hit_rate"]
            ),
        }


class FactorICAnalyzer:
    """
    Day 1 / Day 5 equivalent: computes per-feature IC against forward returns.
    Works on the Kaggle feature matrix, no external data needed.
    """

    @staticmethod
    def _date_level_ics(df: pd.DataFrame, feature: str, target_col: str) -> np.ndarray:
        values: list[float] = []
        for _, group in df.groupby("date", sort=True):
            local = group[[feature, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(local) < 10:
                continue
            corr = _safe_spearman(local[feature].to_numpy(), local[target_col].to_numpy())
            if np.isfinite(corr):
                values.append(float(corr))
        return np.asarray(values, dtype=float)

    def compute_ic_table(
        self,
        features_df,
        feature_names,
        target_col="target_weekly_return",
        progress_label: str | None = None,
        progress_every: int = 25,
    ) -> pd.DataFrame:
        """
        For each feature: mean IC, IC t-stat, hit rate, IC IR.
        Uses Spearman correlation per date cross-section, then averages.
        Returns DataFrame sorted by abs(mean_ic) descending.
        """

        rows: list[dict[str, Any]] = []
        base = features_df[["date", target_col] + list(feature_names)].copy()
        total_features = len(feature_names)
        for index, feature in enumerate(feature_names, start=1):
            date_ics = self._date_level_ics(base, feature, target_col)
            if len(date_ics) == 0:
                rows.append(
                    {
                        "feature": feature,
                        "mean_ic": 0.0,
                        "ic_tstat": 0.0,
                        "hit_rate": 0.0,
                        "ic_ir": 0.0,
                        "n_dates": 0,
                    }
                )
                continue
            mean_ic = float(np.mean(date_ics))
            std_ic = float(np.std(date_ics, ddof=1)) if len(date_ics) > 1 else 0.0
            stderr = std_ic / np.sqrt(len(date_ics)) if len(date_ics) > 1 else 0.0
            ic_tstat = float(mean_ic / stderr) if abs(stderr) > 1e-12 else 0.0
            ic_ir = float(mean_ic / std_ic) if abs(std_ic) > 1e-12 else 0.0
            rows.append(
                {
                    "feature": feature,
                    "mean_ic": mean_ic,
                    "ic_tstat": ic_tstat,
                    "hit_rate": float(np.mean(date_ics > 0)),
                    "ic_ir": ic_ir,
                    "n_dates": int(len(date_ics)),
                }
            )
            if progress_label and (
                index == 1
                or index == total_features
                or (progress_every > 0 and index % progress_every == 0)
            ):
                print(
                    f"{progress_label}: processed {index}/{total_features} features",
                    flush=True,
                )
        frame = pd.DataFrame(rows)
        return frame.sort_values(["mean_ic"], key=lambda col: col.abs(), ascending=False).reset_index(drop=True)

    def top_factors(self, ic_table, n=20) -> pd.DataFrame:
        """Top N factors by absolute mean IC."""

        return ic_table.reindex(ic_table["mean_ic"].abs().sort_values(ascending=False).index).head(n).reset_index(drop=True)

    def decay_check(
        self,
        features_df,
        feature_names,
        split_date: str,
        *,
        min_abs_first_half_ic: float = 0.005,
    ) -> pd.DataFrame:
        """
        Computes IC in first half vs second half of history.
        decay_ratio = ic_second_half / ic_first_half.
        Flag decay_alert only when the feature had real first-half signal and
        its second-half absolute IC fell below half of that strength.
        """

        split_ts = pd.Timestamp(split_date)
        first_half = features_df.loc[features_df["date"] < split_ts].copy()
        second_half = features_df.loc[features_df["date"] >= split_ts].copy()
        rows: list[dict[str, Any]] = []
        for feature in feature_names:
            first_ics = self._date_level_ics(first_half[["date", feature, "target_weekly_return"]], feature, "target_weekly_return")
            second_ics = self._date_level_ics(second_half[["date", feature, "target_weekly_return"]], feature, "target_weekly_return")
            ic_first = float(np.mean(first_ics)) if len(first_ics) else 0.0
            ic_second = float(np.mean(second_ics)) if len(second_ics) else 0.0
            has_signal = bool(np.isfinite(ic_first) and abs(ic_first) >= float(min_abs_first_half_ic))
            if has_signal and abs(ic_first) > 1e-12:
                decay_ratio = ic_second / ic_first
                abs_decay_ratio = abs(ic_second) / abs(ic_first)
            else:
                decay_ratio = float("nan")
                abs_decay_ratio = float("nan")
            rows.append(
                {
                    "feature": feature,
                    "ic_first_half": ic_first,
                    "ic_second_half": ic_second,
                    "decay_ratio": decay_ratio,
                    "abs_decay_ratio": abs_decay_ratio,
                    "decay_alert": bool(has_signal and np.isfinite(abs_decay_ratio) and abs_decay_ratio < 0.5),
                }
            )
        return pd.DataFrame(rows).sort_values(
            ["decay_alert", "abs_decay_ratio"],
            ascending=[False, True],
            na_position="last",
        ).reset_index(drop=True)


class RegimeConditionalIC:
    """Day 4 equivalent: IC broken down by regime period."""

    REGIME_PERIODS = {
        "bear_2022": ("2022-01-01", "2022-12-31"),
        "bull_2023": ("2023-01-01", "2023-10-31"),
    }

    def compute(self, features_df, feature_names, regime_df) -> dict:
        """
        For each regime period: mean IC of each feature.
        Returns {regime: ic_series} dict.
        """

        analyzer = FactorICAnalyzer()
        output: dict[str, pd.Series] = {}
        for regime_name, (start, end) in self.REGIME_PERIODS.items():
            subset = features_df.loc[features_df["date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
            if subset.empty:
                output[regime_name] = pd.Series(dtype=float)
                continue
            ic_table = analyzer.compute_ic_table(subset, feature_names)
            output[regime_name] = ic_table.set_index("feature")["mean_ic"].sort_values(key=lambda col: col.abs(), ascending=False)
        return output

    def model_regime_breakdown(self, walk_forward_results: dict) -> pd.DataFrame:
        """
        Takes walk-forward results dict.
        Returns DataFrame: regime × model IC matrix.
        """

        rows: list[dict[str, Any]] = []
        for model_name, result in walk_forward_results.items():
            for window in result.get("windows", []):
                if "error" in window:
                    continue
                rows.append(
                    {
                        "model": model_name,
                        "regime": window.get("regime", "unknown"),
                        "test_ic": window.get("test_ic", np.nan),
                    }
                )
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        return frame.pivot_table(index="regime", columns="model", values="test_ic", aggfunc="mean").sort_index()


class SectorICAnalyzer:
    """
    Day 4 equivalent: IC broken down by sector.
    Uses sector column if present in features_df, else skips gracefully.
    """

    @staticmethod
    def _resolve_sector_column(features_df: pd.DataFrame, requested: str) -> str | None:
        if requested in features_df.columns:
            return requested
        for candidate in ("broad_sector", "sector_group", "sector"):
            if candidate in features_df.columns:
                return candidate
        return None

    def compute(self, features_df, feature_names, sector_col="sector") -> pd.DataFrame:
        """
        Per sector: mean IC, IC hit rate, n_stocks.
        Skips sectors with fewer than 10 stocks.
        Returns DataFrame sorted by mean_ic descending.
        """

        resolved_sector_col = self._resolve_sector_column(features_df, sector_col)
        if resolved_sector_col is None:
            return pd.DataFrame(columns=["sector", "mean_ic", "hit_rate", "n_stocks"])

        numeric_features = [feature for feature in feature_names if feature in features_df.columns]
        if not numeric_features:
            return pd.DataFrame(columns=["sector", "mean_ic", "hit_rate", "n_stocks"])

        analyzer = FactorICAnalyzer()
        rows: list[dict[str, Any]] = []
        for sector, sector_df in features_df.groupby(resolved_sector_col):
            if sector_df["ticker"].nunique() < 10:
                continue
            composite_name = "__sector_composite__"
            working = sector_df.copy()
            working[composite_name] = working[numeric_features[: min(25, len(numeric_features))]].mean(axis=1)
            ic_table = analyzer.compute_ic_table(working[["date", "ticker", "target_weekly_return", composite_name]], [composite_name])
            row = ic_table.iloc[0]
            rows.append(
                {
                    "sector": sector,
                    "mean_ic": float(row["mean_ic"]),
                    "hit_rate": float(row["hit_rate"]),
                    "n_stocks": int(sector_df["ticker"].nunique()),
                }
            )
        if not rows:
            return pd.DataFrame(columns=["sector", "mean_ic", "hit_rate", "n_stocks"])
        return pd.DataFrame(rows).sort_values("mean_ic", ascending=False).reset_index(drop=True)


class EnsembleBuilder:
    """Day 6 equivalent: IC-weighted ensemble of multiple model predictions."""

    def build(self, model_predictions: dict, ic_history: dict, lookback=10) -> np.ndarray:
        """
        model_predictions: {model_name: array of test predictions}
        ic_history: {model_name: list of past window ICs}
        lookback: how many past windows to use for weights

        Returns IC-weighted ensemble prediction array.
        Clips weights to (0.10, 0.90) so no single model dominates.
        """

        model_names = list(model_predictions.keys())
        if not model_names:
            raise ValueError("No model predictions provided to ensemble builder.")

        raw_weights = []
        for model_name in model_names:
            history = np.asarray(ic_history.get(model_name, [])[-lookback:], dtype=float)
            history = history[np.isfinite(history)]
            score = float(np.mean(history)) if history.size else 1.0
            raw_weights.append(max(score, 0.01))

        raw = np.asarray(raw_weights, dtype=float)
        raw = raw / raw.sum()
        clipped = np.clip(raw, 0.10, 0.90)
        weights = clipped / clipped.sum()

        prediction_stack = np.vstack([np.asarray(model_predictions[name], dtype=float) for name in model_names])
        return np.average(prediction_stack, axis=0, weights=weights)

    def evaluate_gain(
        self,
        ensemble_preds,
        individual_results: dict,
        y_test: np.ndarray,
        *,
        ensemble_ratio: float | None = None,
        individual_ratios: dict | None = None,
    ) -> dict:
        """
        Returns ensemble-vs-best gain metrics and an inclusion verdict.
        """

        ensemble_ic = _safe_spearman(np.asarray(ensemble_preds, dtype=float), np.asarray(y_test, dtype=float))
        individual_ics = {
            model_name: _safe_spearman(np.asarray(preds, dtype=float), np.asarray(y_test, dtype=float))
            for model_name, preds in individual_results.items()
        }
        best_individual_ic = max(individual_ics.values()) if individual_ics else float("nan")
        ic_gain = ensemble_ic - best_individual_ic if np.isfinite(best_individual_ic) else float("nan")
        payload = {
            "ensemble_ic": float(ensemble_ic),
            "best_individual_ic": float(best_individual_ic),
            "ic_gain": float(ic_gain),
            "passes_min_parity": bool(np.isfinite(ic_gain) and ic_gain > -0.003),
        }
        if individual_ics:
            best_model_name = max(individual_ics, key=individual_ics.get)
            payload["best_individual_model"] = str(best_model_name)
        if ensemble_ratio is not None and individual_ratios:
            best_ratio = float(individual_ratios.get(payload.get("best_individual_model"), np.nan))
            ratio_cost = float(ensemble_ratio) / max(best_ratio, 1.0) if np.isfinite(best_ratio) else float("nan")
            if np.isfinite(ic_gain) and ic_gain > 0.001 and np.isfinite(ratio_cost) and ratio_cost < 1.5:
                verdict = "BEATS best individual — include in final"
            elif np.isfinite(ic_gain) and ic_gain > 0.001 and np.isfinite(ratio_cost) and ratio_cost >= 1.5:
                verdict = f"IC gain +{ic_gain:.4f} but ratio worsened {ratio_cost:.1f}x — DO NOT USE"
            else:
                verdict = "Does not beat best individual seed"
            payload.update(
                {
                    "ensemble_ratio": float(ensemble_ratio),
                    "best_individual_ratio": best_ratio,
                    "ratio_cost": ratio_cost,
                    "verdict": verdict,
                }
            )
        return payload


class PromotionVerdict:
    """Day 7 equivalent: generates the final research verdict."""

    VERDICT_A_CRITERIA = {
        "min_factors_ic_above_030": 2,
        "min_model_ic_ir": 0.5,
        "min_train_test_ratio_below": 2.5,
        "min_regime_coverage": 0.67,
    }

    VERDICT_B_CRITERIA = {
        "min_factors_ic_above_020": 1,
        "min_model_ic_ir": 0.3,
        "min_train_test_ratio_below": 2.5,
    }

    def compute(self, ic_table, best_model_summary, stability, regime_breakdown, ensemble_gain, track_name) -> dict:
        """
        Returns:
        verdict: A / B / C
        verdict_label: PROMOTE / PROMOTE_LIMITED / DO_NOT_PROMOTE
        evidence: dict of all supporting metrics
        recommendation: plain English string
        open_questions: list of strings
        """

        strong_factors = int((ic_table["mean_ic"].abs() > 0.030).sum())
        moderate_factors = int((ic_table["mean_ic"].abs() > 0.020).sum())
        ic_ir = float(best_model_summary.get("ic_ir", np.nan))
        ratio = float(best_model_summary.get("mean_train_test_ratio", np.nan))
        hit = float(best_model_summary.get("mean_hit_rate", np.nan))
        stability_corr = float(stability.get("mean_pairwise_correlation", np.nan))
        positive_regimes = sum(1 for value in regime_breakdown.values() if value > 0)
        total_regimes = len(regime_breakdown)
        regime_coverage = float(positive_regimes / total_regimes) if total_regimes else 0.0
        ensemble_parity = bool(ensemble_gain.get("passes_min_parity")) if ensemble_gain else False

        verdict = "C"
        verdict_label = "DO_NOT_PROMOTE"
        recommendation = (
            "Do not promote this track yet. Keep the current production stance, redesign the weak factors, "
            "and re-run the walk-forward after the next factor iteration."
        )

        if (
            strong_factors >= self.VERDICT_A_CRITERIA["min_factors_ic_above_030"]
            and ic_ir >= self.VERDICT_A_CRITERIA["min_model_ic_ir"]
            and ratio < self.VERDICT_A_CRITERIA["min_train_test_ratio_below"]
            and regime_coverage >= self.VERDICT_A_CRITERIA["min_regime_coverage"]
        ):
            verdict = "A"
            verdict_label = "PROMOTE"
            recommendation = (
                "Promote the best model from this track into the next certification cycle with STANDARD capital "
                "structure, 40-60% target deployment, and weekly rebalancing."
            )
        elif (
            moderate_factors >= self.VERDICT_B_CRITERIA["min_factors_ic_above_020"]
            and ic_ir >= self.VERDICT_B_CRITERIA["min_model_ic_ir"]
            and ratio < self.VERDICT_B_CRITERIA["min_train_test_ratio_below"]
        ):
            verdict = "B"
            verdict_label = "PROMOTE_LIMITED"
            recommendation = (
                "Promote at limited scale under a CAUTIOUS regime, keep deployment nearer 20-30%, and continue "
                "India-specific factor research before the next freeze review."
            )

        open_questions: list[str] = []
        if strong_factors < 2:
            open_questions.append("Need more factors with sustained IC above 0.030.")
        if ic_ir < 0.5:
            open_questions.append("Model IC IR is still below the strong-promotion threshold.")
        if ratio >= 2.5:
            open_questions.append("Train/test ratio is still too high and suggests overfitting.")
        if total_regimes and regime_coverage < 0.67:
            open_questions.append("Regime coverage is still too narrow for a broad live promotion.")
        if not ensemble_parity:
            open_questions.append("The ensemble does not yet beat or match the best single model reliably.")
        if stability_corr < 0.40:
            open_questions.append("Feature-importance stability remains weak across windows.")
        if not open_questions:
            open_questions = [
                "Monitor live slippage versus the research assumptions.",
                "Recheck factor behavior after the next major macro regime shift.",
                "Prepare the re-certification run for the week of April 12.",
            ]

        evidence = {
            "track_name": track_name,
            "factors_above_030": strong_factors,
            "factors_above_020": moderate_factors,
            "best_model_mean_test_ic": float(best_model_summary.get("mean_test_ic", np.nan)),
            "best_model_ic_ir": ic_ir,
            "best_model_ratio": ratio,
            "best_model_hit_rate": hit,
            "stability_corr": stability_corr,
            "regime_coverage": regime_coverage,
            "positive_regimes": positive_regimes,
            "total_regimes": total_regimes,
            "ensemble_ic_gain": None if not ensemble_gain else ensemble_gain.get("ic_gain"),
            "ensemble_passes_parity": ensemble_parity,
        }

        return {
            "verdict": verdict,
            "verdict_label": verdict_label,
            "evidence": evidence,
            "recommendation": recommendation,
            "open_questions": open_questions,
        }

    def format_memo(self, verdict_dict, track_name) -> str:
        """
        Returns formatted markdown promotion memo string.
        Follows the template from the weekly research plan PDF exactly.
        """

        evidence = verdict_dict.get("evidence", {})
        verdict_code = str(verdict_dict.get("verdict") or "C")
        is_b_band = verdict_code == "B" or verdict_code.startswith("B_")
        target_regime = "STANDARD" if verdict_code == "A" else "CAUTIOUS" if is_b_band else "HOLD"
        target_equity = "40-60%" if verdict_code == "A" else "20-30%" if is_b_band else "0-20%"
        return "\n".join(
            [
                "# Research Verdict - Week of 2026-03-22",
                f"## Verdict: {verdict_dict.get('verdict', 'C')}",
                "## Evidence Summary",
                "### Factor IC Results",
                "| Metric | Value |",
                "|---|---|",
                f"| Factors with |IC| > 0.030 | {evidence.get('factors_above_030', 0)} |",
                f"| Factors with |IC| > 0.020 | {evidence.get('factors_above_020', 0)} |",
                "### Model Comparison",
                "| Metric | Value |",
                "|---|---|",
                f"| Best model mean IC | {evidence.get('best_model_mean_test_ic')} |",
                f"| Best model IC IR | {evidence.get('best_model_ic_ir')} |",
                f"| Train/Test ratio | {evidence.get('best_model_ratio')} |",
                f"| Hit rate | {evidence.get('best_model_hit_rate')} |",
                "### Deployment Root Cause",
                "The prior 4.84% exposure failure was treated this week as a research diagnosis problem rather than a live deployment action.",
                f"Post-sprint recommendation for {track_name}: {verdict_dict.get('recommendation', '')}",
                "### India-Specific Findings",
                "- Earnings quality sign should be checked against the day-5 output.",
                "- Interaction factors should be compared against their standalone components.",
                "- Power-consumption lag should be reviewed for sector-specific lead structure.",
                "## Recommendation",
                verdict_dict.get("recommendation", ""),
                "## Parameters for Live Run (if Verdict A or B)",
                f"- Capital structure regime: {target_regime}",
                f"- Target equity deployment: {target_equity}",
                "- Portfolio size: 20 stocks",
                "- Rebalancing frequency: weekly",
                "- Maximum position size: 10%",
                "- Transaction cost budget per week: 15-30 bps one-way by cap bucket",
                "## Open Questions for Next Research Cycle",
            ]
            + [f"{idx}. {question}" for idx, question in enumerate(verdict_dict.get("open_questions", []), start=1)]
            + [
                "## Freeze Review Note",
                "This memo is prepared for the April 17 freeze review.",
                "Current freeze expires: 2026-04-19.",
            ]
        )


class ResultsSaver:
    """Serializes all results safely to JSON."""

    def load_combined(self, output_dir: Path, track_name: str) -> dict[str, Any]:
        """Loads the combined JSON file if present, else returns an empty dict."""

        combined_path = Path(output_dir) / f"{track_name}_full_results.json"
        if not combined_path.exists():
            return {}
        try:
            return json.loads(combined_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def load_day(self, output_dir: Path, track_name: str, day_key: str) -> Any:
        """Loads a single saved day payload if present."""

        combined = self.load_combined(output_dir, track_name)
        if day_key in combined:
            return combined[day_key]
        day_path = Path(output_dir) / f"{track_name}_{day_key}.json"
        if not day_path.exists():
            return None
        try:
            return json.loads(day_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def save_all(self, output_dir: Path, track_name: str, day_results: dict):
        """
        Saves one JSON per day: track_a_day1.json, track_a_day2.json, etc.
        Converts all numpy types. Handles NaN/Inf -> None.
        Also saves full combined results as track_a_full_results.json.
        """

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        combined_path = output_dir / f"{track_name}_full_results.json"
        existing: dict[str, Any] = {}
        if combined_path.exists():
            try:
                existing = json.loads(combined_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}

        for key, value in day_results.items():
            existing[key] = _make_serializable(value)
            day_path = output_dir / f"{track_name}_{key}.json"
            day_path.write_text(json.dumps(existing[key], indent=2), encoding="utf-8")

        existing["last_updated_at"] = datetime.now(timezone.utc).isoformat()
        combined_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def save_model_result(
        self,
        output_dir: Path,
        model_name: str,
        results: dict[str, Any],
        summary: dict[str, Any],
        stability: dict[str, Any],
        baseline_comparison: dict[str, Any] | None = None,
    ) -> Path:
        """Saves a single model payload in the same shape as the frontier Kaggle artifacts."""

        payload = {
            "model": model_name,
            "summary": _make_serializable(summary),
            "stability": _make_serializable(stability),
            "windows": _make_serializable(results.get("windows", [])),
            "baseline_comparison": _make_serializable(baseline_comparison or {}),
            "config": _make_serializable(results.get("config", {})),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_count": int(len(results.get("feature_names", []))),
        }
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{model_name}_final.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path

    def print_progress_banner(self, day: int, label: str, elapsed_minutes: float):
        """Prints a clean separator line with day number, label, elapsed time."""

        print("\n" + "=" * 72)
        print(f"DAY {day} - {label} - elapsed {elapsed_minutes:.1f} min")
        print("=" * 72)
