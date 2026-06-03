"""Self-contained runtime embedded into the Kaggle compendium notebooks."""

from __future__ import annotations

import json
import math
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from IPython.display import Markdown, display

warnings.filterwarnings("ignore")

try:
    from catboost import CatBoostRegressor
except Exception:  # pragma: no cover - Kaggle should have catboost
    CatBoostRegressor = None

try:
    from scipy.stats import spearmanr
except Exception:  # pragma: no cover - fallback below
    spearmanr = None

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - Kaggle should have torch
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

try:
    from sklearn.ensemble import HistGradientBoostingRegressor
except Exception:  # pragma: no cover
    HistGradientBoostingRegressor = None

try:
    from sklearn.neural_network import MLPRegressor
except Exception:  # pragma: no cover
    MLPRegressor = None


if torch is not None:
    try:
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    except Exception:
        pass


PLAN_INFO = dict((globals().get("PLAN_PAYLOAD") or {}).get("plan") or {})
EXPERIMENT_SPECS = dict((globals().get("PLAN_PAYLOAD") or {}).get("experiments") or {})
MAJOR_EVENTS_DF = pd.DataFrame(globals().get("MAJOR_EVENTS_PAYLOAD") or [])
for _date_col in ["start_date", "end_date"]:
    if _date_col in MAJOR_EVENTS_DF.columns:
        MAJOR_EVENTS_DF[_date_col] = pd.to_datetime(MAJOR_EVENTS_DF[_date_col], errors="coerce")


DEFAULT_EXPORT_DATASET_CANDIDATES = [
    "/kaggle/input/northstar-v3-feature-export",
    "/kaggle/input/northstar-v3-feature-export-1",
    "/kaggle/input/northstar-v3-feature-export-2",
]
REQUIRED_FLAG_COLUMNS = [
    "pledge_pct_available",
    "rating_numeric_available",
    "days_since_earnings_available",
    "sector_dummy__NA_",
]
CORE_EXTRA_FEATURES = [
    "accruals_ratio_cs_z",
    "agreement_score_cs_z",
    "amihud_illiquidity_cs_z",
    "bulk_net_pressure_21d_cs_z",
    "eps_sue_decay",
    "mom_20d_cs_z",
    "mom_20d_sector_rel_cs_z",
    "mom_60d_cs_z",
    "piotroski_fscore_cs_z",
    "price_to_sma20_cs_z",
    "res_mom_20d_cs_z",
    "ret_5d_cs_z",
    "ret_20d_cs_z",
    "rev_sue_decay",
    "turnover_ratio_20d_cs_z",
    "val_quality_composite_zscore",
    "vol_z20_cs_z",
]
NUMERIC_METADATA_FEATURES = [
    "close",
    "volume",
    "international_revenue_proxy",
    "macro_linkage_score",
    "oil_sensitivity_score",
    "steel_sensitivity_score",
    "copper_sensitivity_score",
    "gold_sensitivity_score",
    "fx_sensitivity_score",
    "rate_sensitivity_score",
]
SEQUENCE_EXTRA_FEATURES = [
    "eps_sue_decay",
    "rev_sue_decay",
    "agreement_score_cs_z",
    "piotroski_fscore_cs_z",
    "bulk_net_pressure_21d_cs_z",
    "ret_5d_cs_z",
    "ret_20d_cs_z",
    "mom_20d_cs_z",
    "mom_60d_cs_z",
    "mom_20d_sector_rel_cs_z",
    "res_mom_20d_cs_z",
    "price_to_sma20_cs_z",
    "vol_z20_cs_z",
    "inrusd_4w_return",
    "crude_4w_return",
    "gold_4w_return",
    "copper_4w_return",
    "steel_4w_return",
    "coal_4w_return",
    "dxy_4w_return",
    "vix_india_4w",
    "rbi_rate_chg",
    "us_10y_4w",
    "commodity_basket",
]
DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
    "iterations": 350,
    "learning_rate": 0.05,
}


@dataclass(frozen=True)
class PlanDataset:
    export_dir: Path
    features: pd.DataFrame
    metadata: pd.DataFrame
    regimes: pd.DataFrame
    splits: list[dict[str, Any]]
    merged: pd.DataFrame
    audit: dict[str, Any]
    manifest: dict[str, Any]
    merged_manifest: dict[str, Any]


def get_experiment_spec(exp_id: str) -> dict[str, Any]:
    if exp_id not in EXPERIMENT_SPECS:
        raise KeyError(f"unknown_experiment:{exp_id}")
    return dict(EXPERIMENT_SPECS[exp_id] or {})


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def slugify(value: Any) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean or "unknown"


def dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def write_json(path: str | Path, payload: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
    return output


def write_markdown(path: str | Path, text: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(text).strip() + "\n", encoding="utf-8")
    return output


def write_table(path: str | Path, frame: pd.DataFrame) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".parquet":
        frame.to_parquet(output, index=False)
    else:
        frame.to_csv(output, index=False)
    return output


def make_experiment_paths(output_root: str | Path, exp_id: str, version: str = "v1") -> dict[str, Path]:
    root = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}"
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return {
        "root": root,
        "artifacts": artifacts,
        "summary": root / "summary.json",
        "narrative": root / "economic_narrative.md",
    }


def _required_export_files() -> list[str]:
    contract = dict(PLAN_INFO.get("dataset_contract") or {})
    values = [str(value) for value in contract.values() if str(value or "").strip()]
    return values or [
        "northstar_features.parquet",
        "northstar_metadata.parquet",
        "northstar_regime_labels.parquet",
        "northstar_walk_forward_splits.json",
    ]


def _candidate_input_dirs() -> list[Path]:
    root = Path("/kaggle/input")
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def resolve_export_dir(
    candidates: Sequence[str] | None = None,
    export_dir_override: str | Path | None = None,
) -> Path:
    required = _required_export_files()
    probes: list[Path] = []
    if export_dir_override:
        probes.append(Path(export_dir_override).expanduser())
    probes.extend(Path(value) for value in (candidates or DEFAULT_EXPORT_DATASET_CANDIDATES))
    probes.extend(_candidate_input_dirs())
    checked: list[str] = []
    for candidate in probes:
        if not candidate.exists():
            checked.append(str(candidate))
            continue
        if all((candidate / filename).exists() for filename in required):
            return candidate
        checked.append(str(candidate))
    raise FileNotFoundError(
        "Unable to resolve the export dataset directory. Checked:\n- " + "\n- ".join(checked[:30])
    )


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_plan_dataset(export_dir: str | Path) -> PlanDataset:
    root = Path(export_dir).expanduser().resolve()
    features = pd.read_parquet(root / "northstar_features.parquet")
    metadata = pd.read_parquet(root / "northstar_metadata.parquet")
    regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
    splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))

    for frame in [features, metadata, regimes]:
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

    merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    regime_cols = [
        column
        for column in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id", "subtle_period_id"]
        if column in regimes.columns
    ]
    if regime_cols:
        merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
    for name in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id", "subtle_period_id"]:
        if name in merged.columns:
            continue
        left = f"{name}_x"
        right = f"{name}_y"
        if left in merged.columns or right in merged.columns:
            merged[name] = merged.get(left)
            if right in merged.columns:
                merged[name] = merged[name].where(pd.Series(merged[name]).notna(), merged[right])

    if "plan_regime_label" in merged.columns:
        merged["plan_regime_label"] = merged["plan_regime_label"].fillna("Unknown").astype(str)
    if "sector" in merged.columns:
        merged["sector"] = merged["sector"].fillna("Unknown").astype(str)

    return PlanDataset(
        export_dir=root,
        features=features,
        metadata=metadata,
        regimes=regimes,
        splits=list(splits),
        merged=merged,
        audit=_read_optional_json(root / "plan_signal_audit.json"),
        manifest=_read_optional_json(root / "weekly_export_manifest.json"),
        merged_manifest=_read_optional_json(root / "merged_chunk_export_manifest.json"),
    )


def validate_dataset_contract(dataset: PlanDataset) -> dict[str, Any]:
    required_columns = ["date", "ticker", "target_weekly_return"]
    missing_required = [column for column in required_columns if column not in dataset.features.columns]
    missing_flags = [column for column in REQUIRED_FLAG_COLUMNS if column not in dataset.features.columns]
    dead_columns = [column for column in dataset.features.columns if column.startswith("earnings_quality_ratio")]
    if missing_required:
        raise RuntimeError(f"Dataset is missing required columns: {missing_required}")
    if missing_flags:
        raise RuntimeError(f"Dataset is missing robust export flags: {missing_flags}")
    if dead_columns:
        raise RuntimeError(f"Dataset still contains removed dead columns: {dead_columns}")
    return {
        "features_rows": int(len(dataset.features)),
        "metadata_rows": int(len(dataset.metadata)),
        "feature_columns": int(dataset.features.shape[1]),
        "metadata_columns": int(dataset.metadata.shape[1]),
        "regime_rows": int(len(dataset.regimes)),
        "date_min": str(dataset.features["date"].min().date()),
        "date_max": str(dataset.features["date"].max().date()),
        "weekly_dates": int(dataset.features["date"].nunique()),
        "tickers": int(dataset.features["ticker"].nunique()),
        "walk_forward_windows": int(len(dataset.splits)),
        "target_last_column": bool(dataset.features.columns[-1] == "target_weekly_return"),
        "blocking_signals": list((dataset.audit or {}).get("blocking_signals") or []),
        "warning_signals": list((dataset.audit or {}).get("warning_signals") or []),
        "missing_anchor_factors": [
            factor for factor in list(PLAN_INFO.get("anchor_factors") or []) if factor not in dataset.merged.columns
        ],
    }


def display_dataset_report(exp_id: str, dataset: PlanDataset, contract: dict[str, Any]) -> None:
    spec = get_experiment_spec(exp_id)
    overview = pd.DataFrame(
        [
            {
                "plan_id": PLAN_INFO.get("plan_id"),
                "version": PLAN_INFO.get("version"),
                "exp_id": exp_id,
                "title": spec.get("title"),
                "features_rows": contract["features_rows"],
                "feature_columns": contract["feature_columns"],
                "tickers": contract["tickers"],
                "weekly_dates": contract["weekly_dates"],
                "walk_forward_windows": contract["walk_forward_windows"],
                "date_min": contract["date_min"],
                "date_max": contract["date_max"],
            }
        ]
    )
    display(overview)

    checks = pd.DataFrame(
        [
            {
                "target_last_column": contract["target_last_column"],
                "blocking_signals": ", ".join(contract["blocking_signals"]),
                "warning_signals": ", ".join(contract["warning_signals"]),
                "missing_anchor_factors": ", ".join(contract["missing_anchor_factors"]),
            }
        ]
    )
    display(checks)

    if dataset.audit:
        audit_row = {
            "audit_blocking": ", ".join(list(dataset.audit.get("blocking_signals") or [])),
            "audit_warning": ", ".join(list(dataset.audit.get("warning_signals") or [])),
        }
        display(pd.DataFrame([audit_row]))


def safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    if spearmanr is not None:
        try:
            corr = spearmanr(x, y, nan_policy="omit").correlation
            return float(corr) if corr is not None and np.isfinite(corr) else float("nan")
        except Exception:
            pass
    try:
        corr = pd.Series(x).corr(pd.Series(y), method="spearman")
    except Exception:
        return float("nan")
    return float(corr) if corr is not None and np.isfinite(corr) else float("nan")


def compute_ic_series(
    frame: pd.DataFrame,
    score_col: str = "prediction",
    target_col: str = "target_weekly_return",
    min_obs: int = 8,
) -> pd.Series:
    rows: list[dict[str, Any]] = []
    for date_value, group in frame.groupby("date", sort=True):
        local = group[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < min_obs:
            continue
        corr = safe_spearman(local[score_col].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
        if np.isfinite(corr):
            rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(corr)})
    if not rows:
        return pd.Series(dtype="float64")
    return pd.Series(
        [row["ic"] for row in rows],
        index=pd.Index([row["date"] for row in rows], name="date"),
        dtype="float64",
    ).sort_index()


def summarize_ic_series(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {
            "n_dates": 0,
            "mean_ic": float("nan"),
            "ic_ir": float("nan"),
            "ic_tstat": float("nan"),
            "hit_rate": float("nan"),
        }
    mean_ic = float(clean.mean())
    std = float(clean.std(ddof=1)) if len(clean) > 1 else float("nan")
    ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
    ic_tstat = mean_ic / (std / math.sqrt(len(clean))) if np.isfinite(std) and std > 0 else float("nan")
    hit_rate = float((clean >= 0).mean()) if mean_ic >= 0 else float((clean <= 0).mean())
    return {
        "n_dates": int(len(clean)),
        "mean_ic": mean_ic,
        "ic_ir": ic_ir,
        "ic_tstat": ic_tstat,
        "hit_rate": hit_rate,
    }


def summarize_window_results(windows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    clean = [dict(row) for row in windows if "error" not in row]
    if not clean:
        return {
            "windows_completed": 0,
            "mean_train_ic": float("nan"),
            "mean_test_ic": float("nan"),
            "ic_ir": float("nan"),
            "mean_train_test_ratio": float("nan"),
            "mean_hit_rate": float("nan"),
        }
    frame = pd.DataFrame(clean)
    mean_test = float(pd.to_numeric(frame["test_ic"], errors="coerce").mean())
    std_test = float(pd.to_numeric(frame["test_ic"], errors="coerce").std(ddof=1)) if len(frame) > 1 else float("nan")
    return {
        "windows_completed": int(len(frame)),
        "mean_train_ic": float(pd.to_numeric(frame["train_ic"], errors="coerce").mean()),
        "mean_test_ic": mean_test,
        "ic_ir": mean_test / std_test if np.isfinite(std_test) and std_test > 0 else float("nan"),
        "mean_train_test_ratio": float(pd.to_numeric(frame["train_test_ratio"], errors="coerce").mean()),
        "mean_hit_rate": float(pd.to_numeric(frame["hit_rate"], errors="coerce").mean()),
    }


def pick_best_candidate(candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    clean = [dict(item) for item in candidates if np.isfinite(float(item.get("mean_test_ic", np.nan)))]
    if not clean:
        return None
    clean.sort(
        key=lambda row: (
            float(row.get("mean_test_ic", float("-inf"))),
            float(row.get("ic_ir", float("-inf"))),
            -float(row.get("mean_train_test_ratio", float("inf"))),
        ),
        reverse=True,
    )
    best = clean[0]
    return best


def _numeric_feature_columns(frame: pd.DataFrame, columns: Sequence[str]) -> list[str]:
    chosen: list[str] = []
    for column in columns:
        if column not in frame.columns:
            continue
        if not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        chosen.append(str(column))
    return dedupe(chosen)


def default_catboost_feature_columns(dataset: PlanDataset) -> list[str]:
    feature_columns = [
        column
        for column in dataset.features.columns
        if column not in {"date", "ticker", "target_weekly_return"}
        and pd.api.types.is_numeric_dtype(dataset.features[column])
    ]
    metadata_columns = _numeric_feature_columns(dataset.metadata, NUMERIC_METADATA_FEATURES)
    merged = dedupe(list(feature_columns) + list(metadata_columns))
    return merged


def default_sequence_feature_columns(dataset: PlanDataset, limit: int = 20) -> list[str]:
    frame = dataset.merged
    candidates = dedupe(
        list(PLAN_INFO.get("anchor_factors") or [])
        + list(PLAN_INFO.get("cross_asset_signals") or [])
        + list(PLAN_INFO.get("sector_conditional_features") or [])
        + SEQUENCE_EXTRA_FEATURES
    )
    chosen = _numeric_feature_columns(frame, candidates)
    return chosen[:limit]


def _sanitize_feature_frame(frame: pd.DataFrame, feature_columns: Sequence[str]) -> pd.DataFrame:
    needed = ["date", "ticker", "target_weekly_return", "plan_regime_label", "sector"]
    cols = [column for column in needed if column in frame.columns] + [column for column in feature_columns if column in frame.columns]
    data = frame[cols].copy()
    for column in feature_columns:
        if column not in data.columns:
            continue
        data[column] = pd.to_numeric(data[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    data["target_weekly_return"] = (
        pd.to_numeric(data["target_weekly_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    )
    if "plan_regime_label" in data.columns:
        data["plan_regime_label"] = data["plan_regime_label"].fillna("Unknown").astype(str)
    if "sector" in data.columns:
        data["sector"] = data["sector"].fillna("Unknown").astype(str)
    return data.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


def generate_anchored_weekly_splits(
    weekly_dates: Sequence[pd.Timestamp],
    *,
    anchor_start: str = "2019-01-01",
    train_weeks: int = 104,
    test_weeks: int = 26,
    step_weeks: int = 26,
    target_windows: int = 0,
) -> list[dict[str, Any]]:
    dates = (
        pd.Series(pd.to_datetime(list(weekly_dates), errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    anchor = pd.Timestamp(anchor_start).normalize()
    dates = [pd.Timestamp(value).normalize() for value in dates if pd.Timestamp(value).normalize() >= anchor]
    if len(dates) < train_weeks + test_weeks:
        raise ValueError(f"insufficient_anchor_aligned_dates:{len(dates)}<{train_weeks + test_weeks}")

    windows: list[dict[str, Any]] = []
    for test_start_idx in range(train_weeks, len(dates) - test_weeks + 1, step_weeks):
        test_end_idx = test_start_idx + test_weeks - 1
        windows.append(
            {
                "window_id": len(windows) + 1,
                "train_start": str(dates[0].date()),
                "train_end": str(dates[test_start_idx - 1].date()),
                "test_start": str(dates[test_start_idx].date()),
                "test_end": str(dates[test_end_idx].date()),
            }
        )
    if target_windows > 0 and len(windows) > target_windows:
        windows = windows[-target_windows:]
        for idx, window in enumerate(windows, start=1):
            window["window_id"] = idx
    return windows


def _coerce_split_dates(split: dict[str, Any]) -> dict[str, pd.Timestamp]:
    return {
        "train_start": pd.Timestamp(split["train_start"]).normalize(),
        "train_end": pd.Timestamp(split["train_end"]).normalize(),
        "test_start": pd.Timestamp(split["test_start"]).normalize(),
        "test_end": pd.Timestamp(split["test_end"]).normalize(),
    }


def _train_valid_frames(train_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    unique_dates = sorted(pd.to_datetime(train_frame["date"]).dropna().unique().tolist())
    if len(unique_dates) < 12:
        return train_frame, None
    valid_dates = max(4, int(round(len(unique_dates) * 0.15)))
    valid_dates = min(valid_dates, len(unique_dates) - 4)
    if valid_dates <= 0:
        return train_frame, None
    cutoff = pd.Timestamp(unique_dates[-valid_dates]).normalize()
    fit_frame = train_frame[train_frame["date"] < cutoff].copy()
    valid_frame = train_frame[train_frame["date"] >= cutoff].copy()
    if fit_frame.empty or valid_frame.empty:
        return train_frame, None
    return fit_frame, valid_frame


def _build_catboost_model(params: dict[str, Any]):
    merged = dict(DEFAULT_CATBOOST_PARAMS)
    merged.update(dict(params or {}))
    if CatBoostRegressor is not None:
        return CatBoostRegressor(
            loss_function="RMSE",
            eval_metric="RMSE",
            random_seed=42,
            verbose=False,
            allow_writing_files=False,
            depth=int(merged.get("depth", 4)),
            l2_leaf_reg=float(merged.get("l2_leaf_reg", 15.0)),
            min_data_in_leaf=int(merged.get("min_data_in_leaf", 40)),
            od_type="Iter",
            od_wait=int(merged.get("od_wait", 30)),
            boosting_type=str(merged.get("boosting_type", "Ordered")),
            iterations=int(merged.get("iterations", 350)),
            learning_rate=float(merged.get("learning_rate", 0.05)),
        )
    if HistGradientBoostingRegressor is None:
        raise RuntimeError("Neither CatBoost nor sklearn HistGradientBoostingRegressor is available.")
    return HistGradientBoostingRegressor(
        learning_rate=float(merged.get("learning_rate", 0.05)),
        max_depth=int(merged.get("depth", 4)),
        max_iter=int(merged.get("iterations", 350)),
        random_state=42,
    )


def run_catboost_walkforward(
    frame: pd.DataFrame,
    splits: Sequence[dict[str, Any]],
    feature_columns: Sequence[str],
    *,
    params: dict[str, Any] | None = None,
    max_splits: int | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    data = _sanitize_feature_frame(frame, feature_columns)
    selected_splits = list(splits[:max_splits] if max_splits else splits)
    windows: list[dict[str, Any]] = []

    for split in selected_splits:
        window = dict(split)
        split_dates = _coerce_split_dates(split)
        train_frame = data[data["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
        test_frame = data[data["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
        if len(train_frame) < 1000 or len(test_frame) < 200:
            windows.append({**window, "error": "insufficient_rows"})
            continue

        fit_frame, valid_frame = _train_valid_frames(train_frame)
        X_fit = fit_frame[list(feature_columns)].to_numpy(dtype=np.float32)
        y_fit = fit_frame["target_weekly_return"].to_numpy(dtype=np.float32)
        X_train = train_frame[list(feature_columns)].to_numpy(dtype=np.float32)
        y_train = train_frame["target_weekly_return"].to_numpy(dtype=np.float32)
        X_test = test_frame[list(feature_columns)].to_numpy(dtype=np.float32)
        y_test = test_frame["target_weekly_return"].to_numpy(dtype=np.float32)

        model = _build_catboost_model(params or {})
        if valid_frame is not None and CatBoostRegressor is not None and isinstance(model, CatBoostRegressor):
            model.fit(
                X_fit,
                y_fit,
                eval_set=(
                    valid_frame[list(feature_columns)].to_numpy(dtype=np.float32),
                    valid_frame["target_weekly_return"].to_numpy(dtype=np.float32),
                ),
                use_best_model=True,
            )
        else:
            model.fit(X_fit, y_fit)

        train_scored = train_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
        test_scored = test_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
        train_scored["prediction"] = model.predict(X_train)
        test_scored["prediction"] = model.predict(X_test)

        train_summary = summarize_ic_series(compute_ic_series(train_scored))
        test_summary = summarize_ic_series(compute_ic_series(test_scored))
        train_ic = float(train_summary["mean_ic"])
        test_ic = float(test_summary["mean_ic"])
        ratio = abs(train_ic) / max(abs(test_ic), 1e-6) if np.isfinite(train_ic) else float("nan")
        regime = (
            test_scored["plan_regime_label"].mode(dropna=True).iloc[0]
            if "plan_regime_label" in test_scored.columns and not test_scored["plan_regime_label"].dropna().empty
            else "Unknown"
        )
        windows.append(
            {
                **window,
                "train_rows": int(len(train_frame)),
                "test_rows": int(len(test_frame)),
                "train_ic": train_ic,
                "test_ic": test_ic,
                "train_test_ratio": ratio,
                "hit_rate": float(test_summary["hit_rate"]),
                "regime": regime,
            }
        )

    summary = summarize_window_results(windows)
    state = {
        "model": "CatBoost",
        "feature_columns": list(feature_columns),
        "feature_count": len(feature_columns),
        "params": dict(DEFAULT_CATBOOST_PARAMS | dict(params or {})),
        "windows": windows,
        "summary": summary,
    }
    if output_dir:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        write_table(output / "window_metrics.csv", pd.DataFrame(windows))
        write_json(output / "summary.json", state)
    return state


def resolve_sector_tickers(dataset: PlanDataset, sector_name: str) -> list[str]:
    if "sector" not in dataset.metadata.columns:
        return []
    tickers = (
        dataset.metadata.loc[dataset.metadata["sector"].astype(str) == str(sector_name), "ticker"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return tickers


def augment_sector_conditionals(
    frame: pd.DataFrame,
    base_features: Sequence[str],
    sectors: Sequence[str],
) -> tuple[pd.DataFrame, list[str]]:
    augmented = frame.copy()
    added: list[str] = []
    if "sector" not in augmented.columns:
        return augmented, added
    for sector in sectors:
        slug = slugify(sector)
        indicator_name = f"sector_is__{slug}"
        augmented[indicator_name] = (augmented["sector"].astype(str) == str(sector)).astype("float32")
        added.append(indicator_name)
        for feature in base_features:
            if feature not in augmented.columns:
                continue
            interaction_name = f"{feature}__x__{slug}"
            augmented[interaction_name] = (
                pd.to_numeric(augmented[feature], errors="coerce").fillna(0.0) * augmented[indicator_name]
            ).astype("float32")
            added.append(interaction_name)
    return augmented, added


def overlapping_major_events(dataset: PlanDataset) -> pd.DataFrame:
    if MAJOR_EVENTS_DF.empty:
        return pd.DataFrame()
    date_min = pd.Timestamp(dataset.features["date"].min()).normalize()
    date_max = pd.Timestamp(dataset.features["date"].max()).normalize()
    events = MAJOR_EVENTS_DF.copy()
    events = events[events["end_date"].fillna(events["start_date"]) >= date_min]
    events = events[events["start_date"] <= date_max]
    return events.sort_values(["start_date", "event_id"], kind="mergesort").reset_index(drop=True)


def select_high_risk_events(events: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    if events.empty:
        return events

    def risk_score(row: pd.Series) -> float:
        label = str(row.get("model_collapse_risk") or "").upper()
        base = 0.0
        if "EXTREME" in label:
            base += 4.0
        elif "HIGH" in label:
            base += 3.0
        elif "MEDIUM" in label:
            base += 2.0
        elif "LOW" in label:
            base += 1.0
        severity = float(row.get("severity_score_1_10") or 0.0)
        return base + (severity / 10.0)

    ranked = events.copy()
    ranked["risk_score"] = ranked.apply(risk_score, axis=1)
    return ranked.sort_values(["risk_score", "severity_score_1_10"], ascending=[False, False], kind="mergesort").head(
        int(top_n)
    )


def build_event_split(dataset: PlanDataset, start_date: Any, end_date: Any, train_weeks: int = 104) -> list[dict[str, Any]]:
    weekly_dates = (
        pd.Series(pd.to_datetime(dataset.features["date"], errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    if not weekly_dates:
        return []
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    weekly = [pd.Timestamp(value).normalize() for value in weekly_dates]
    test_dates = [value for value in weekly if start <= value <= end]
    if len(test_dates) < 2:
        return []
    first_test = test_dates[0]
    first_idx = weekly.index(first_test)
    train_end_idx = first_idx - 1
    train_start_idx = max(0, train_end_idx - train_weeks + 1)
    if train_end_idx <= train_start_idx:
        return []
    return [
        {
            "window_id": 1,
            "train_start": str(weekly[train_start_idx].date()),
            "train_end": str(weekly[train_end_idx].date()),
            "test_start": str(test_dates[0].date()),
            "test_end": str(test_dates[-1].date()),
        }
    ]


def _best_ratio_params(
    output_root: str | Path,
    version: str,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(DEFAULT_CATBOOST_PARAMS)
    root = Path(output_root).expanduser().resolve()
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        path = root / f"{exp_id.lower().replace('-', '_')}_{version}" / "summary.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        best = dict((payload or {}).get("best_candidate") or {})
        best_params = dict(best.get("params") or {})
        if best_params:
            params.update(best_params)
            break
    if override:
        params.update(dict(override))
    return params


def _write_candidate_narrative(
    path: Path,
    *,
    exp_id: str,
    title: str,
    hypothesis: str,
    best_candidate: dict[str, Any] | None,
    notes: Sequence[str] | None = None,
) -> None:
    lines = [
        f"# {exp_id} - {title}",
        "",
        f"Hypothesis: {hypothesis}",
        "",
    ]
    if best_candidate:
        lines.extend(
            [
                "Best candidate:",
                f"- mean_test_ic: {best_candidate.get('mean_test_ic')}",
                f"- ic_ir: {best_candidate.get('ic_ir')}",
                f"- mean_train_test_ratio: {best_candidate.get('mean_train_test_ratio')}",
                f"- params: {best_candidate.get('params')}",
                "",
            ]
        )
    if notes:
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note}")
    write_markdown(path, "\n".join(lines))


def run_ratio_experiment(
    exp_id: str,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    version: str = "v1",
    max_splits: int | None = None,
    manual_upstream_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = get_experiment_spec(exp_id)
    paths = make_experiment_paths(output_root, exp_id, version)
    feature_columns = default_catboost_feature_columns(dataset)
    frame = dataset.merged
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []

    def _run_candidate(label: str, params: dict[str, Any], splits: Sequence[dict[str, Any]] | None = None) -> dict[str, Any]:
        state = run_catboost_walkforward(
            frame,
            splits or dataset.splits,
            feature_columns,
            params=params,
            max_splits=max_splits,
            output_dir=paths["artifacts"] / label,
        )
        summary = dict(state["summary"])
        return {
            "label": label,
            "params": dict(params),
            "mean_test_ic": summary.get("mean_test_ic"),
            "ic_ir": summary.get("ic_ir"),
            "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
            "mean_hit_rate": summary.get("mean_hit_rate"),
            "windows_completed": summary.get("windows_completed"),
            "output_dir": str(paths["artifacts"] / label),
        }

    if exp_id == "EXP-09":
        base = dict(DEFAULT_CATBOOST_PARAMS)
        base.update(dict((spec.get("params") or {}).get("base_catboost") or {}))
        for depth in list((spec.get("params") or {}).get("depth_grid") or []):
            for od_wait in list((spec.get("params") or {}).get("early_stopping_rounds") or []):
                params = {**base, "depth": int(depth), "od_wait": int(od_wait)}
                candidates.append(_run_candidate(f"depth_{depth}_odwait_{od_wait}", params))
        notes.append("This run compares CatBoost depth against early stopping on the robust merged export only.")

    elif exp_id == "EXP-10":
        upstream = _best_ratio_params(output_root, version, manual_upstream_params)
        for value in list((spec.get("params") or {}).get("l2_leaf_reg_grid") or []):
            params = {**upstream, "l2_leaf_reg": float(value)}
            candidates.append(_run_candidate(f"l2_{str(value).replace('.', '_')}", params))
        notes.append("The L2 sweep inherits the best available depth and stopping values from EXP-09 if present.")

    elif exp_id == "EXP-11":
        upstream = _best_ratio_params(output_root, version, manual_upstream_params)
        for boosting_type in list((spec.get("params") or {}).get("boosting_types") or []):
            params = {**upstream, "boosting_type": str(boosting_type)}
            candidates.append(_run_candidate(f"boosting_{str(boosting_type).lower()}", params))
        notes.append("Only the CatBoost boosting type changes in this comparison.")

    elif exp_id == "EXP-12":
        upstream = _best_ratio_params(output_root, version, manual_upstream_params)
        weekly_dates = pd.to_datetime(dataset.features["date"], errors="coerce").dropna().sort_values().unique().tolist()
        for years in list((spec.get("params") or {}).get("train_window_years") or []):
            splits = generate_anchored_weekly_splits(
                weekly_dates,
                anchor_start="2019-01-01",
                train_weeks=int(years) * 52,
                test_weeks=int((spec.get("params") or {}).get("test_window_weeks") or 26),
                step_weeks=int((spec.get("params") or {}).get("step_weeks") or 26),
                target_windows=0,
            )
            result = _run_candidate(f"window_{years}yr", upstream, splits=splits)
            result["params"] = {**result["params"], "train_window_years": int(years)}
            result["split_count"] = len(splits)
            candidates.append(result)
        notes.append("EXP-12 rebuilds the walk-forward windows with a fixed 6-month test horizon.")

    else:
        raise KeyError(f"unsupported_ratio_experiment:{exp_id}")

    candidate_table = pd.DataFrame(candidates)
    best_candidate = pick_best_candidate(candidates)
    payload = {
        "exp_id": exp_id,
        "title": spec.get("title"),
        "family": spec.get("family"),
        "hypothesis": spec.get("hypothesis"),
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "candidate_count": len(candidates),
        "best_candidate": best_candidate,
        "candidates": candidates,
    }
    write_table(paths["root"] / "candidate_table.csv", candidate_table)
    write_json(paths["summary"], payload)
    _write_candidate_narrative(
        paths["narrative"],
        exp_id=exp_id,
        title=str(spec.get("title") or ""),
        hypothesis=str(spec.get("hypothesis") or ""),
        best_candidate=best_candidate,
        notes=notes,
    )
    return payload


def _write_simple_narrative(path: Path, exp_id: str, title: str, hypothesis: str, metrics: dict[str, Any], notes: Sequence[str]) -> None:
    lines = [f"# {exp_id} - {title}", "", f"Hypothesis: {hypothesis}", "", "Observed metrics:"]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note}")
    write_markdown(path, "\n".join(lines))


def _regime_table_from_windows(windows: Sequence[dict[str, Any]], model_name: str) -> pd.DataFrame:
    clean = [row for row in windows if "error" not in row]
    if not clean:
        return pd.DataFrame(columns=["model", "regime", "mean_test_ic", "mean_ratio", "n_windows"])
    frame = pd.DataFrame(clean)
    return (
        frame.groupby("regime", as_index=False)
        .agg(mean_test_ic=("test_ic", "mean"), mean_ratio=("train_test_ratio", "mean"), n_windows=("window_id", "count"))
        .assign(model=model_name)
        .loc[:, ["model", "regime", "mean_test_ic", "mean_ratio", "n_windows"]]
    )


def run_sector_or_regime_experiment(
    exp_id: str,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    version: str = "v1",
    max_splits: int | None = None,
    best_ratio_params_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = get_experiment_spec(exp_id)
    paths = make_experiment_paths(output_root, exp_id, version)
    best_params = _best_ratio_params(output_root, version, best_ratio_params_override)
    feature_columns = default_catboost_feature_columns(dataset)

    if exp_id in {"EXP-13", "EXP-14", "EXP-15"}:
        sector_name = str((spec.get("params") or {}).get("sector_name") or "")
        tickers = resolve_sector_tickers(dataset, sector_name)
        subset = dataset.merged[dataset.merged["ticker"].isin(tickers)].copy()
        state = run_catboost_walkforward(
            subset,
            dataset.splits,
            feature_columns,
            params=best_params,
            max_splits=max_splits,
            output_dir=paths["artifacts"] / "catboost",
        )
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "sector_name": sector_name,
            "n_tickers": len(tickers),
            "tickers": tickers,
            "best_params": best_params,
            "feature_count": len(feature_columns),
            "catboost_summary": state["summary"],
        }
        write_json(paths["root"] / "sector_subset_manifest.json", payload)
        write_json(paths["summary"], payload)
        _write_simple_narrative(
            paths["narrative"],
            exp_id,
            str(spec.get("title") or ""),
            str(spec.get("hypothesis") or ""),
            {
                "sector_name": sector_name,
                "n_tickers": len(tickers),
                "mean_test_ic": state["summary"].get("mean_test_ic"),
                "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio"),
            },
            [
                "The subset is created directly from the sector labels stored in northstar_metadata.parquet.",
                "This run inherits the best broad-universe CatBoost settings found so far, unless you override them.",
            ],
        )
        return payload

    if exp_id == "EXP-16":
        sectors = list((spec.get("params") or {}).get("sectors") or [])
        augmented, added_features = augment_sector_conditionals(
            dataset.merged,
            base_features=list(PLAN_INFO.get("sector_conditional_features") or []),
            sectors=sectors,
        )
        all_features = dedupe(list(feature_columns) + [column for column in added_features if column in augmented.columns])
        state = run_catboost_walkforward(
            augmented,
            dataset.splits,
            all_features,
            params=best_params,
            max_splits=max_splits,
            output_dir=paths["artifacts"] / "catboost",
        )
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "best_params": best_params,
            "feature_count": len(all_features),
            "added_feature_count": len(added_features),
            "added_features": added_features,
            "catboost_summary": state["summary"],
        }
        write_json(paths["root"] / "augmented_feature_manifest.json", payload)
        write_json(paths["summary"], payload)
        _write_simple_narrative(
            paths["narrative"],
            exp_id,
            str(spec.get("title") or ""),
            str(spec.get("hypothesis") or ""),
            {
                "added_feature_count": len(added_features),
                "mean_test_ic": state["summary"].get("mean_test_ic"),
                "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio"),
            },
            [
                "The sector blend adds explicit sector identity flags plus sector-conditional interactions for the plan feature list.",
            ],
        )
        return payload

    if exp_id == "EXP-17":
        events = overlapping_major_events(dataset)
        available_anchors = [factor for factor in list(PLAN_INFO.get("anchor_factors") or []) if factor in dataset.merged.columns]
        rows: list[dict[str, Any]] = []
        for event in events.to_dict(orient="records"):
            event_frame = dataset.merged[
                dataset.merged["date"].between(pd.Timestamp(event["start_date"]), pd.Timestamp(event["end_date"]))
            ].copy()
            for factor in available_anchors:
                scored = event_frame[["date", "target_weekly_return", factor]].copy()
                scored = scored.rename(columns={factor: "prediction"})
                summary = summarize_ic_series(compute_ic_series(scored))
                rows.append(
                    {
                        "event_id": event.get("event_id"),
                        "event_name": event.get("event_name"),
                        "factor": factor,
                        "mean_ic": summary.get("mean_ic"),
                        "ic_ir": summary.get("ic_ir"),
                        "ic_tstat": summary.get("ic_tstat"),
                        "n_dates": summary.get("n_dates"),
                        "severity_score_1_10": event.get("severity_score_1_10"),
                        "model_collapse_risk": event.get("model_collapse_risk"),
                    }
                )
        table = pd.DataFrame(rows)
        blind_spots = (
            table.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort").head(10).to_dict(orient="records")
            if not table.empty
            else []
        )
        write_table(paths["root"] / "factor_event_heatmap.csv", table)
        write_table(paths["root"] / "factor_event_heatmap.parquet", table)
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "event_count": int(events["event_id"].nunique()) if not events.empty else 0,
            "factor_count": int(table["factor"].nunique()) if not table.empty else 0,
            "available_anchor_factors": available_anchors,
            "missing_anchor_factors": [
                factor for factor in list(PLAN_INFO.get("anchor_factors") or []) if factor not in available_anchors
            ],
            "blind_spots": blind_spots,
        }
        write_json(paths["summary"], payload)
        _write_simple_narrative(
            paths["narrative"],
            exp_id,
            str(spec.get("title") or ""),
            str(spec.get("hypothesis") or ""),
            {
                "event_count": payload["event_count"],
                "factor_count": payload["factor_count"],
                "missing_anchor_factors": ", ".join(payload["missing_anchor_factors"]),
            },
            [
                "The heat map is computed only on canonical major events that overlap the 2019-2026 export window.",
            ],
        )
        return payload

    if exp_id == "EXP-18":
        events = select_high_risk_events(
            overlapping_major_events(dataset),
            top_n=int((spec.get("params") or {}).get("top_n_high_risk_events") or 5),
        )
        baseline_path = Path(output_root).expanduser().resolve() / f"exp_12_{version}" / "summary.json"
        baseline_mean_test_ic = float("nan")
        if baseline_path.exists():
            baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_mean_test_ic = float(((baseline_payload.get("best_candidate") or {}).get("mean_test_ic")) or np.nan)
        rows: list[dict[str, Any]] = []
        for event in events.to_dict(orient="records"):
            split = build_event_split(
                dataset,
                event.get("start_date"),
                event.get("end_date"),
                train_weeks=int((spec.get("params") or {}).get("train_window_weeks") or 104),
            )
            if not split:
                rows.append(
                    {
                        "event_id": event.get("event_id"),
                        "event_name": event.get("event_name"),
                        "model_collapse_risk": event.get("model_collapse_risk"),
                        "severity_score_1_10": event.get("severity_score_1_10"),
                        "error": "insufficient_overlap",
                    }
                )
                continue
            state = run_catboost_walkforward(
                dataset.merged,
                split,
                feature_columns,
                params=best_params,
                max_splits=1,
                output_dir=paths["artifacts"] / str(event.get("event_id") or "event").lower(),
            )
            summary = dict(state["summary"])
            mean_test_ic = float(summary.get("mean_test_ic"))
            rows.append(
                {
                    "event_id": event.get("event_id"),
                    "event_name": event.get("event_name"),
                    "model_collapse_risk": event.get("model_collapse_risk"),
                    "severity_score_1_10": event.get("severity_score_1_10"),
                    "mean_test_ic": mean_test_ic,
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "collapse_vs_baseline": mean_test_ic / baseline_mean_test_ic
                    if np.isfinite(baseline_mean_test_ic) and baseline_mean_test_ic != 0
                    else float("nan"),
                }
            )
        table = pd.DataFrame(rows)
        write_table(paths["root"] / "event_collapse_table.csv", table)
        worst_events = (
            table[table["mean_test_ic"].notna()]
            .sort_values(["mean_test_ic", "mean_train_test_ratio"], ascending=[True, False], kind="mergesort")
            .head(3)
            .to_dict(orient="records")
            if not table.empty and "mean_test_ic" in table.columns
            else []
        )
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "baseline_mean_test_ic": baseline_mean_test_ic,
            "events_tested": int(len(table)),
            "worst_events": worst_events,
        }
        write_json(paths["summary"], payload)
        _write_simple_narrative(
            paths["narrative"],
            exp_id,
            str(spec.get("title") or ""),
            str(spec.get("hypothesis") or ""),
            {
                "events_tested": len(table),
                "baseline_mean_test_ic": baseline_mean_test_ic,
                "worst_event_mean_test_ic": worst_events[0]["mean_test_ic"] if worst_events else None,
            },
            [
                "Each event run trains on the preceding fixed history and tests only inside the selected event window.",
            ],
        )
        return payload

    if exp_id == "EXP-19":
        sequence_features = default_sequence_feature_columns(dataset)
        routing_catboost_features = dedupe(sequence_features + _numeric_feature_columns(dataset.metadata, NUMERIC_METADATA_FEATURES))
        catboost_state = run_catboost_walkforward(
            dataset.merged,
            dataset.splits,
            routing_catboost_features,
            params=best_params,
            max_splits=max_splits,
            output_dir=paths["artifacts"] / "catboost",
        )
        lstm_state = run_sequence_walkforward(
            dataset.merged,
            dataset.splits,
            sequence_features,
            model_name="LSTM",
            max_splits=max_splits,
            output_dir=paths["artifacts"] / "lstm",
        )
        tcn_state = run_sequence_walkforward(
            dataset.merged,
            dataset.splits,
            sequence_features,
            model_name="TCN",
            max_splits=max_splits,
            output_dir=paths["artifacts"] / "tcn",
        )
        regime_table = pd.concat(
            [
                _regime_table_from_windows(catboost_state.get("windows", []), "CatBoost"),
                _regime_table_from_windows(lstm_state.get("windows", []), "LSTM"),
                _regime_table_from_windows(tcn_state.get("windows", []), "TCN"),
            ],
            ignore_index=True,
        )
        routing_rows: list[dict[str, Any]] = []
        if not regime_table.empty:
            for regime_name, group in regime_table.groupby("regime", sort=True):
                best_row = group.sort_values(["mean_test_ic", "mean_ratio"], ascending=[False, True], kind="mergesort").iloc[0]
                routing_rows.append(
                    {
                        "regime": regime_name,
                        "selected_model": best_row["model"],
                        "selected_mean_test_ic": float(best_row["mean_test_ic"]),
                        "selected_mean_ratio": float(best_row["mean_ratio"]),
                        "n_windows": int(best_row["n_windows"]),
                    }
                )
        routing = pd.DataFrame(routing_rows)
        write_table(paths["root"] / "routing_table.csv", routing if not routing.empty else regime_table)
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "candidate_models": ["CatBoost", "LSTM", "TCN"],
            "routing_catboost_feature_count": len(routing_catboost_features),
            "routing_catboost_features": routing_catboost_features,
            "sequence_feature_count": len(sequence_features),
            "sequence_features": sequence_features,
            "routed_mean_ic": float(routing["selected_mean_test_ic"].mean()) if not routing.empty else float("nan"),
            "routing_rows": routing_rows,
            "model_summaries": {
                "CatBoost": catboost_state.get("summary"),
                "LSTM": lstm_state.get("summary"),
                "TCN": tcn_state.get("summary"),
            },
        }
        write_json(paths["summary"], payload)
        _write_simple_narrative(
            paths["narrative"],
            exp_id,
            str(spec.get("title") or ""),
            str(spec.get("hypothesis") or ""),
            {
                "routed_mean_ic": payload["routed_mean_ic"],
                "sequence_feature_count": len(sequence_features),
            },
            [
                "This notebook trains lightweight LSTM and TCN baselines directly inside Kaggle so routing can be tested without a separate code dataset.",
            ],
        )
        return payload

    raise KeyError(f"unsupported_sector_regime_experiment:{exp_id}")


class LSTMRegressor(nn.Module):
    def __init__(self, feature_count: int, hidden_size: int = 48):
        super().__init__()
        self.lstm = nn.LSTM(input_size=feature_count, hidden_size=hidden_size, batch_first=True, num_layers=1)
        self.dropout = nn.Dropout(0.1)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, inputs):  # type: ignore[override]
        output, _ = self.lstm(inputs)
        return self.head(self.dropout(output[:, -1, :])).squeeze(-1)


class TCNRegressor(nn.Module):
    def __init__(self, feature_count: int, hidden_size: int = 48):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(feature_count, hidden_size, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, inputs):  # type: ignore[override]
        channels = inputs.transpose(1, 2)
        hidden = self.network(channels).squeeze(-1)
        return self.head(hidden).squeeze(-1)


def _build_group_cache(frame: pd.DataFrame, feature_columns: Sequence[str]) -> dict[str, dict[str, Any]]:
    data = _sanitize_feature_frame(frame, feature_columns)
    groups: dict[str, dict[str, Any]] = {}
    for ticker, group in data.groupby("ticker", sort=False):
        ordered = group.sort_values("date", kind="mergesort").reset_index(drop=True)
        groups[str(ticker)] = {
            "dates": pd.to_datetime(ordered["date"], errors="coerce").to_numpy(),
            "target": ordered["target_weekly_return"].to_numpy(dtype=np.float32),
            "regime": ordered["plan_regime_label"].astype(str).to_numpy() if "plan_regime_label" in ordered.columns else None,
            "values": ordered[list(feature_columns)].to_numpy(dtype=np.float32),
        }
    return groups


def _sequence_samples_for_split(
    groups: dict[str, dict[str, Any]],
    split: dict[str, Any],
    seq_len: int,
    *,
    max_train_samples: int | None = None,
) -> dict[str, Any]:
    split_dates = _coerce_split_dates(split)
    train_x: list[np.ndarray] = []
    train_y: list[float] = []
    train_dates: list[pd.Timestamp] = []
    test_x: list[np.ndarray] = []
    test_y: list[float] = []
    test_dates: list[pd.Timestamp] = []
    test_regimes: list[str] = []

    for payload in groups.values():
        dates = payload["dates"]
        values = payload["values"]
        target = payload["target"]
        regimes = payload["regime"]
        for idx in range(seq_len - 1, len(dates)):
            date_value = pd.Timestamp(dates[idx]).normalize()
            sample = values[idx - seq_len + 1 : idx + 1]
            if date_value >= split_dates["train_start"] and date_value <= split_dates["train_end"]:
                train_x.append(sample)
                train_y.append(float(target[idx]))
                train_dates.append(date_value)
            elif date_value >= split_dates["test_start"] and date_value <= split_dates["test_end"]:
                test_x.append(sample)
                test_y.append(float(target[idx]))
                test_dates.append(date_value)
                test_regimes.append(str(regimes[idx]) if regimes is not None else "Unknown")

    if max_train_samples and len(train_x) > int(max_train_samples):
        rng = np.random.default_rng(42)
        keep = np.sort(rng.choice(len(train_x), size=int(max_train_samples), replace=False))
        train_x = [train_x[idx] for idx in keep]
        train_y = [train_y[idx] for idx in keep]
        train_dates = [train_dates[idx] for idx in keep]

    return {
        "train_x": np.asarray(train_x, dtype=np.float32),
        "train_y": np.asarray(train_y, dtype=np.float32),
        "train_dates": np.asarray(train_dates, dtype="datetime64[ns]"),
        "test_x": np.asarray(test_x, dtype=np.float32),
        "test_y": np.asarray(test_y, dtype=np.float32),
        "test_dates": np.asarray(test_dates, dtype="datetime64[ns]"),
        "test_regimes": np.asarray(test_regimes, dtype=object),
    }


def _fit_sequence_model(
    model_name: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    *,
    feature_count: int,
) -> tuple[Any, np.ndarray, np.ndarray]:
    if HistGradientBoostingRegressor is None:
        raise RuntimeError("sklearn_sequence_backend_unavailable")
    flat_train = train_x.reshape(len(train_x), -1).astype(np.float32, copy=False)
    mean = flat_train.mean(axis=0, keepdims=True)
    std = flat_train.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    scaled = (flat_train - mean) / std
    if model_name == "LSTM" and MLPRegressor is not None:
        model = MLPRegressor(
            hidden_layer_sizes=(96, 48),
            activation="relu",
            learning_rate_init=1e-3,
            max_iter=max(20, int(globals().get("SEQUENCE_EPOCHS", 4)) * 20),
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
        )
    else:
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=4,
            max_iter=max(100, int(globals().get("SEQUENCE_EPOCHS", 4)) * 40),
            random_state=42,
        )
    model.fit(scaled, train_y.astype(np.float32, copy=False))
    return model, mean.astype(np.float32), std.astype(np.float32)


def _fit_sequence_model_torch(
    model_name: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    *,
    feature_count: int,
) -> tuple[Any, np.ndarray, np.ndarray]:
    if torch is None or nn is None or DataLoader is None or TensorDataset is None:
        raise RuntimeError("torch_unavailable")
    if len(train_x) < 512:
        raise RuntimeError("insufficient_sequence_training_rows")

    train_x = train_x.astype(np.float32, copy=False)
    train_y = train_y.astype(np.float32, copy=False)
    order = np.argsort(np.arange(len(train_x)))
    train_x = train_x[order]
    train_y = train_y[order]

    split_idx = max(int(len(train_x) * 0.9), len(train_x) - 4096)
    split_idx = min(max(split_idx, 256), len(train_x) - 128)
    fit_x, valid_x = train_x[:split_idx], train_x[split_idx:]
    fit_y, valid_y = train_y[:split_idx], train_y[split_idx:]

    mean = fit_x.mean(axis=(0, 1), keepdims=True)
    std = fit_x.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    fit_x = (fit_x - mean) / std
    valid_x = (valid_x - mean) / std
    train_full_x = (train_x - mean) / std

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMRegressor(feature_count) if model_name == "LSTM" else TCNRegressor(feature_count)
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    fit_loader = DataLoader(
        TensorDataset(torch.from_numpy(fit_x), torch.from_numpy(fit_y)),
        batch_size=int(globals().get("SEQUENCE_BATCH_SIZE", 1024)),
        shuffle=True,
    )
    valid_inputs = torch.from_numpy(valid_x).to(device)
    valid_targets = torch.from_numpy(valid_y).to(device)

    best_loss = float("inf")
    best_state: dict[str, Any] | None = None
    patience = 0
    epochs = int(globals().get("SEQUENCE_EPOCHS", 4))
    for _epoch in range(max(1, epochs)):
        model.train()
        for batch_x, batch_y in fit_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            valid_loss = float(loss_fn(model(valid_inputs), valid_targets).item())
        if valid_loss < best_loss:
            best_loss = valid_loss
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
            if patience >= 2:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, mean.astype(np.float32), std.astype(np.float32)


def _predict_sequence_model(model: Any, x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict") and not hasattr(model, "parameters"):
        scaled = ((x.astype(np.float32, copy=False).reshape(len(x), -1) - mean) / std).astype(np.float32, copy=False)
        return np.asarray(model.predict(scaled), dtype=np.float32)
    if torch is None:
        return np.zeros(len(x), dtype=np.float32)
    device = next(model.parameters()).device
    scaled = ((x.astype(np.float32, copy=False) - mean) / std).astype(np.float32, copy=False)
    loader = DataLoader(torch.from_numpy(scaled), batch_size=int(globals().get("SEQUENCE_BATCH_SIZE", 1024)), shuffle=False)
    preds: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            if isinstance(batch, (list, tuple)):
                batch = batch[0]
            preds.append(model(batch.to(device)).detach().cpu().numpy())
    return np.concatenate(preds) if preds else np.zeros(len(x), dtype=np.float32)


def run_sequence_walkforward(
    frame: pd.DataFrame,
    splits: Sequence[dict[str, Any]],
    feature_columns: Sequence[str],
    *,
    model_name: str,
    max_splits: int | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    backend = str(globals().get("SEQUENCE_BACKEND", "torch" if Path("/kaggle").exists() else "sklearn")).strip().lower()
    if backend == "torch" and torch is None:
        backend = "sklearn"
    if backend not in {"torch", "sklearn"}:
        backend = "sklearn"

    if backend == "torch" and torch is None:
        state = {
            "model": model_name,
            "feature_columns": list(feature_columns),
            "windows": [],
            "summary": {"windows_completed": 0, "error": "torch_unavailable"},
        }
        if output_dir:
            write_json(Path(output_dir) / "summary.json", state)
        return state

    groups = _build_group_cache(frame, feature_columns)
    selected_splits = list(splits[:max_splits] if max_splits else splits)
    windows: list[dict[str, Any]] = []
    seq_len = int(globals().get("SEQUENCE_LENGTH", 8))
    max_train_samples = int(globals().get("SEQUENCE_MAX_TRAIN_SAMPLES", 60000))

    for split in selected_splits:
        bundle = _sequence_samples_for_split(groups, split, seq_len, max_train_samples=max_train_samples)
        if len(bundle["train_x"]) < 512 or len(bundle["test_x"]) < 128:
            windows.append({**dict(split), "error": "insufficient_sequence_rows"})
            continue
        try:
            fit_fn = _fit_sequence_model_torch if backend == "torch" else _fit_sequence_model
            model, mean, std = fit_fn(
                model_name,
                bundle["train_x"],
                bundle["train_y"],
                feature_count=len(feature_columns),
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            windows.append({**dict(split), "error": str(exc)})
            continue

        train_pred = _predict_sequence_model(model, bundle["train_x"], mean, std)
        test_pred = _predict_sequence_model(model, bundle["test_x"], mean, std)
        train_scored = pd.DataFrame(
            {
                "date": pd.to_datetime(bundle["train_dates"]),
                "target_weekly_return": bundle["train_y"],
                "prediction": train_pred,
            }
        )
        test_scored = pd.DataFrame(
            {
                "date": pd.to_datetime(bundle["test_dates"]),
                "target_weekly_return": bundle["test_y"],
                "prediction": test_pred,
                "plan_regime_label": bundle["test_regimes"],
            }
        )
        train_summary = summarize_ic_series(compute_ic_series(train_scored))
        test_summary = summarize_ic_series(compute_ic_series(test_scored))
        train_ic = float(train_summary["mean_ic"])
        test_ic = float(test_summary["mean_ic"])
        ratio = abs(train_ic) / max(abs(test_ic), 1e-6) if np.isfinite(train_ic) else float("nan")
        regime = (
            test_scored["plan_regime_label"].mode(dropna=True).iloc[0]
            if "plan_regime_label" in test_scored.columns and not test_scored["plan_regime_label"].dropna().empty
            else "Unknown"
        )
        windows.append(
            {
                **dict(split),
                "train_rows": int(len(bundle["train_x"])),
                "test_rows": int(len(bundle["test_x"])),
                "train_ic": train_ic,
                "test_ic": test_ic,
                "train_test_ratio": ratio,
                "hit_rate": float(test_summary["hit_rate"]),
                "regime": regime,
            }
        )

    summary = summarize_window_results(windows)
    state = {
        "model": model_name,
        "backend": backend,
        "feature_columns": list(feature_columns),
        "feature_count": len(feature_columns),
        "windows": windows,
        "summary": summary,
    }
    if output_dir:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        write_table(output / "window_metrics.csv", pd.DataFrame(windows))
        write_json(output / "summary.json", state)
    return state


def display_experiment_result(payload: dict[str, Any], show_top_rows: int = 12) -> None:
    display(Markdown(f"### {payload.get('exp_id')} - {payload.get('title')}"))
    for key in ["best_candidate", "catboost_summary", "model_summaries", "worst_events", "routing_rows"]:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, dict):
            display(pd.DataFrame([json_ready(value)]))
        elif isinstance(value, list):
            display(pd.DataFrame(json_ready(value)).head(show_top_rows))
    summary_path = Path(globals().get("OUTPUT_ROOT", "/kaggle/working/compendium_plan_v1")).expanduser().resolve()
    exp_root = summary_path / f"{str(payload.get('exp_id')).lower().replace('-', '_')}_{globals().get('VERSION', 'v1')}"
    if exp_root.exists():
        files = sorted(str(path.relative_to(exp_root)) for path in exp_root.rglob("*") if path.is_file())
        display(pd.DataFrame({"output_files": files[: max(show_top_rows, 20)]}))
