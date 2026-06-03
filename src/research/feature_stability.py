"""Feature-importance stability diagnostics for walk-forward research runs."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


_EPS = 1e-12


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not np.isfinite(out):
        return None
    return float(out)


def map_feature_importance_names(
    feature_importance: Mapping[str, Any] | None,
    feature_names: Sequence[str] | None = None,
) -> dict[str, float]:
    """Map adapter-native feature keys like f0/f1 back to dataset feature names."""
    out: dict[str, float] = {}
    names = [str(x) for x in list(feature_names or [])]
    for raw_name, raw_score in dict(feature_importance or {}).items():
        score = _safe_float(raw_score)
        if score is None:
            continue
        name = str(raw_name)
        match = re.fullmatch(r"f(\d+)", name)
        if match and names:
            idx = int(match.group(1))
            if 0 <= idx < len(names):
                name = names[idx]
        out[name] = float(out.get(name, 0.0) + score)
    return out


def _window_label(window: Mapping[str, Any], index: int) -> str:
    test_start = str(window.get("test_start", "") or "").strip()
    test_end = str(window.get("test_end", "") or "").strip()
    if test_start or test_end:
        return f"W{index:02d}:{test_start[:10]}->{test_end[:10]}"
    return f"W{index:02d}"


def _importance_frame(windows: Sequence[Mapping[str, Any]]) -> tuple[pd.DataFrame, list[str], int]:
    cols: dict[str, pd.Series] = {}
    total_windows = int(len(windows))
    for index, window in enumerate(windows, start=1):
        fi = dict(window.get("feature_importance", {}) or {})
        if not fi:
            continue
        cols[_window_label(window, index)] = pd.Series(fi, dtype=float)
    if not cols:
        return pd.DataFrame(dtype=float), [], total_windows
    frame = pd.DataFrame(cols).fillna(0.0)
    frame = frame.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame, list(frame.columns), total_windows


def _safe_spearman(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float).reshape(-1)
    y = np.asarray(b, dtype=float).reshape(-1)
    if len(x) != len(y) or len(x) == 0:
        return float("nan")
    x_const = bool(np.allclose(x, x[0], equal_nan=True))
    y_const = bool(np.allclose(y, y[0], equal_nan=True))
    if x_const and y_const:
        return 1.0 if np.allclose(x, y, equal_nan=True) else 0.0
    if x_const or y_const:
        return 0.0
    xr = pd.Series(x).rank(method="average")
    yr = pd.Series(y).rank(method="average")
    corr = xr.corr(yr)
    return 0.0 if corr is None or not np.isfinite(float(corr)) else float(corr)


def _top_feature_rows(series: pd.Series, top_k: int) -> list[dict[str, Any]]:
    if series.empty:
        return []
    ranked = series.sort_values(ascending=False).head(max(1, int(top_k)))
    return [
        {
            "feature": str(name),
            "importance": float(value),
        }
        for name, value in ranked.items()
    ]


def compute_feature_stability_report(
    windows: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 15,
) -> dict[str, Any]:
    """Compute cross-window stability diagnostics from per-window importance vectors."""
    imp_df, labels, total_windows = _importance_frame(windows)
    analyzed_windows = int(len(labels))
    if total_windows <= 0:
        return {
            "status": "no_windows",
            "windows_total": 0,
            "windows_with_feature_importance": 0,
            "required_rerun": False,
        }
    if analyzed_windows == 0:
        return {
            "status": "missing_window_feature_importance",
            "windows_total": total_windows,
            "windows_with_feature_importance": 0,
            "required_rerun": True,
            "reason": "This run does not contain per-window feature importance vectors.",
        }
    if analyzed_windows < 2:
        return {
            "status": "insufficient_windows",
            "windows_total": total_windows,
            "windows_with_feature_importance": analyzed_windows,
            "required_rerun": False,
            "reason": "Need at least two windows with feature importance to measure stability.",
        }

    corr_matrix = pd.DataFrame(
        np.eye(analyzed_windows, dtype=float),
        index=labels,
        columns=labels,
    )
    pairwise_rows: list[dict[str, Any]] = []
    jaccard_vals: list[float] = []
    top_sets: dict[str, set[str]] = {}

    for label in labels:
        top_sets[label] = set(imp_df[label].sort_values(ascending=False).head(max(1, int(top_k))).index.astype(str))

    for i, left in enumerate(labels):
        for j in range(i + 1, analyzed_windows):
            right = labels[j]
            corr = _safe_spearman(imp_df[left].to_numpy(dtype=float), imp_df[right].to_numpy(dtype=float))
            corr_matrix.loc[left, right] = corr
            corr_matrix.loc[right, left] = corr
            inter = len(top_sets[left].intersection(top_sets[right]))
            union = len(top_sets[left].union(top_sets[right]))
            jaccard = float(inter / union) if union > 0 else 1.0
            jaccard_vals.append(jaccard)
            pairwise_rows.append(
                {
                    "window_a": left,
                    "window_b": right,
                    "spearman_rank_correlation": corr,
                    "top_feature_jaccard": jaccard,
                }
            )

    pairwise_corrs = np.asarray([row["spearman_rank_correlation"] for row in pairwise_rows], dtype=float)
    mean_corr = float(np.nanmean(pairwise_corrs)) if len(pairwise_corrs) else 1.0
    median_corr = float(np.nanmedian(pairwise_corrs)) if len(pairwise_corrs) else 1.0
    min_corr = float(np.nanmin(pairwise_corrs)) if len(pairwise_corrs) else 1.0
    max_corr = float(np.nanmax(pairwise_corrs)) if len(pairwise_corrs) else 1.0
    mean_jaccard = float(np.mean(jaccard_vals)) if jaccard_vals else 1.0

    mean_importance = imp_df.mean(axis=1)
    std_importance = imp_df.std(axis=1)
    denom = mean_importance.abs().copy()
    cv = (std_importance / denom.clip(lower=_EPS)).replace([np.inf, -np.inf], np.inf)
    zero_mean = denom <= _EPS
    cv.loc[zero_mean & (std_importance <= _EPS)] = 0.0
    cv.loc[zero_mean & (std_importance > _EPS)] = np.inf

    if mean_corr >= 0.70:
        stability_band = "stable"
        next_action = "Proceed to Track B hyperparameter tuning."
    elif mean_corr >= 0.40:
        stability_band = "mixed"
        next_action = "Mixed signal. Pair targeted tuning with a feature audit."
    else:
        stability_band = "unstable"
        next_action = "Feature-side issue likely dominates. Audit features before more tuning."

    per_window_top_features = {
        label: _top_feature_rows(imp_df[label], top_k=top_k)
        for label in labels
    }
    top_features_by_mean_importance = [
        {
            "feature": str(name),
            "mean_importance": float(mean_importance.loc[name]),
            "window_nonzero_frac": float((imp_df.loc[name] > 0.0).mean()),
        }
        for name in mean_importance.sort_values(ascending=False).head(max(1, int(top_k))).index
    ]
    most_unstable_features = [
        {
            "feature": str(name),
            "importance_cv": float(cv.loc[name]) if np.isfinite(float(cv.loc[name])) else float("inf"),
            "mean_importance": float(mean_importance.loc[name]),
            "std_importance": float(std_importance.loc[name]),
            "window_nonzero_frac": float((imp_df.loc[name] > 0.0).mean()),
        }
        for name in cv.sort_values(ascending=False).head(max(1, int(top_k))).index
    ]

    return {
        "status": "ok",
        "windows_total": total_windows,
        "windows_with_feature_importance": analyzed_windows,
        "n_features": int(imp_df.shape[0]),
        "mean_pairwise_rank_correlation": mean_corr,
        "median_pairwise_rank_correlation": median_corr,
        "min_pairwise_rank_correlation": min_corr,
        "max_pairwise_rank_correlation": max_corr,
        "mean_top_feature_jaccard": mean_jaccard,
        "stability_band": stability_band,
        "next_action": next_action,
        "pairwise_rank_correlation_matrix": {
            "labels": labels,
            "matrix": [[float(x) for x in row] for row in corr_matrix.to_numpy(dtype=float)],
        },
        "pairwise_window_stats": pairwise_rows,
        "top_features_by_mean_importance": top_features_by_mean_importance,
        "most_unstable_features": most_unstable_features,
        "per_window_top_features": per_window_top_features,
    }
