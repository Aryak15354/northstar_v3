from __future__ import annotations

import gc
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # noqa: BLE001
    torch = None
    nn = None

try:
    from catboost import CatBoostRanker, Pool
except Exception:  # noqa: BLE001
    CatBoostRanker = None
    Pool = None


PLAN_PAYLOAD = __PLAN_PAYLOAD__
MAJOR_EVENTS_RECORDS = __MAJOR_EVENTS_RECORDS__

DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
}

REQUIRED_EXPORT_FILES = (
    "northstar_features.parquet",
    "northstar_metadata.parquet",
    "northstar_regime_labels.parquet",
    "northstar_walk_forward_splits.json",
)


@dataclass(frozen=True)
class PlanInfo:
    plan_id: str
    version: str
    source_doc: str
    master_notebook: str
    dataset_contract: dict[str, Any]
    anchor_factors: tuple[str, ...]
    cross_asset_signals: tuple[str, ...]
    sector_conditional_features: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentSpec:
    exp_id: str
    title: str
    family: str
    priority: int
    dependencies: tuple[str, ...]
    hypothesis: str
    outputs: tuple[str, ...]
    params: dict[str, Any]


@dataclass(frozen=True)
class PlanDataset:
    export_dir: Path
    features: pd.DataFrame
    metadata: pd.DataFrame
    regimes: pd.DataFrame
    splits: list[dict[str, Any]]
    merged: pd.DataFrame


@dataclass(frozen=True)
class ExperimentPaths:
    experiment_root: Path
    artifacts_dir: Path
    summary_path: Path
    narrative_path: Path


def load_plan_info() -> PlanInfo:
    plan = dict(PLAN_PAYLOAD.get("plan") or {})
    return PlanInfo(
        plan_id=str(plan.get("plan_id") or ""),
        version=str(plan.get("version") or "v1"),
        source_doc=str(plan.get("source_doc") or ""),
        master_notebook=str(plan.get("master_notebook") or ""),
        dataset_contract=dict(plan.get("dataset_contract") or {}),
        anchor_factors=tuple(str(value) for value in list(plan.get("anchor_factors") or [])),
        cross_asset_signals=tuple(str(value) for value in list(plan.get("cross_asset_signals") or [])),
        sector_conditional_features=tuple(str(value) for value in list(plan.get("sector_conditional_features") or [])),
    )


def load_experiment_catalog() -> dict[str, ExperimentSpec]:
    payload = dict(PLAN_PAYLOAD.get("experiments") or {})
    catalog: dict[str, ExperimentSpec] = {}
    for exp_id, raw in payload.items():
        data = dict(raw or {})
        catalog[str(exp_id)] = ExperimentSpec(
            exp_id=str(exp_id),
            title=str(data.get("title") or ""),
            family=str(data.get("family") or ""),
            priority=int(data.get("priority") or 0),
            dependencies=tuple(str(value) for value in list(data.get("dependencies") or [])),
            hypothesis=str(data.get("hypothesis") or ""),
            outputs=tuple(str(value) for value in list(data.get("outputs") or [])),
            params=dict(data.get("params") or {}),
        )
    return dict(sorted(catalog.items(), key=lambda item: (item[1].priority, item[0])))


def get_experiment_spec(exp_id: str) -> ExperimentSpec:
    catalog = load_experiment_catalog()
    if exp_id not in catalog:
        raise KeyError(f"unknown_experiment:{exp_id}")
    return catalog[exp_id]


def normalize_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def slugify(value: Any) -> str:
    clean = normalize_label(value).replace(" ", "_")
    return clean or "unknown"


def json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): json_ready(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_ready(value) for value in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        if not np.isfinite(value):
            return None
        return value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Series):
        return {str(key): json_ready(value) for key, value in obj.to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    return obj


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(json_ready(payload), indent=2) + "\n", encoding="utf-8")


def write_table(path: Path, frame: pd.DataFrame) -> None:
    ensure_parent(path)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def write_narrative(
    path: Path,
    *,
    exp_id: str,
    title: str,
    hypothesis: str,
    metrics: dict[str, Any],
    extra_notes: Sequence[str] | None = None,
) -> None:
    lines = [
        f"# {exp_id} - {title}",
        "",
        f"Hypothesis: {hypothesis}",
        "",
        "Observed metrics:",
    ]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    if extra_notes:
        lines.append("")
        lines.append("Notes:")
        for note in extra_notes:
            lines.append(f"- {note}")
    ensure_parent(path)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def make_experiment_paths(output_root: str | Path, exp_id: str, version: str = "v1") -> ExperimentPaths:
    root = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}"
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return ExperimentPaths(
        experiment_root=root,
        artifacts_dir=artifacts,
        summary_path=root / "summary.json",
        narrative_path=root / "economic_narrative.md",
    )


def load_summary_if_exists(output_root: str | Path, exp_id: str, version: str = "v1") -> dict[str, Any] | None:
    path = make_experiment_paths(output_root, exp_id, version).summary_path
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if np.isfinite(numeric) else default


def pick_best_candidate(candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    def key_fn(row: dict[str, Any]) -> tuple[float, float, float, float]:
        ratio = _safe_float(row.get("mean_train_test_ratio"), default=float("inf"))
        ic = _safe_float(row.get("mean_test_ic"), default=float("-inf"))
        ic_ir = _safe_float(row.get("ic_ir"), default=float("-inf"))
        gate = 1.0 if np.isfinite(ratio) and ratio < 2.5 and np.isfinite(ic) and ic > 0.020 else 0.0
        return (gate, ic, -ratio if np.isfinite(ratio) else float("-inf"), ic_ir)

    return sorted(candidates, key=key_fn, reverse=True)[0]


def _is_valid_export_dir(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED_EXPORT_FILES)


def resolve_export_dir(candidates: Sequence[str | Path] | None = None) -> Path:
    probes: list[Path] = []
    for value in list(candidates or []):
        probes.append(Path(value).expanduser())

    kaggle_root = Path("/kaggle/input")
    if kaggle_root.exists():
        probes.append(kaggle_root)
        probes.extend(sorted(path for path in kaggle_root.iterdir() if path.is_dir()))
        for parent in sorted(path for path in kaggle_root.iterdir() if path.is_dir()):
            probes.extend(sorted(path for path in parent.iterdir() if path.is_dir()))

    probes.extend(
        [
            Path.cwd(),
            Path.cwd() / "tmp" / "northstar_v3_chunk_build_robust_merged",
            Path("/kaggle/working"),
        ]
    )

    checked: list[str] = []
    seen: set[str] = set()
    for candidate in probes:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if _is_valid_export_dir(candidate):
            return candidate.resolve()
        checked.append(str(candidate))
        if candidate.exists() and candidate.is_dir():
            for inner in sorted(path for path in candidate.iterdir() if path.is_dir()):
                inner_key = str(inner.resolve())
                if inner_key in seen:
                    continue
                seen.add(inner_key)
                if _is_valid_export_dir(inner):
                    return inner.resolve()
                checked.append(str(inner))
    raise FileNotFoundError(
        "Unable to resolve the feature export directory. Checked:\n- " + "\n- ".join(checked[:40])
    )


def _drop_dead_features(frame: pd.DataFrame) -> pd.DataFrame:
    dead_cols = [col for col in frame.columns if str(col).startswith("earnings_quality_ratio")]
    if dead_cols:
        return frame.drop(columns=dead_cols, errors="ignore")
    return frame


def load_plan_dataset(export_dir: str | Path) -> PlanDataset:
    export_root = resolve_export_dir([export_dir])
    features = pd.read_parquet(export_root / "northstar_features.parquet")
    metadata = pd.read_parquet(export_root / "northstar_metadata.parquet")
    regimes = pd.read_parquet(export_root / "northstar_regime_labels.parquet")
    splits = json.loads((export_root / "northstar_walk_forward_splits.json").read_text())

    features = _drop_dead_features(features)
    features["date"] = pd.to_datetime(features["date"], errors="coerce").dt.normalize()
    features["ticker"] = features["ticker"].astype("string")

    metadata["date"] = pd.to_datetime(metadata["date"], errors="coerce").dt.normalize()
    metadata["ticker"] = metadata["ticker"].astype("string")

    regimes["date"] = pd.to_datetime(regimes["date"], errors="coerce").dt.normalize()

    merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "__meta"))
    duplicate_cols = [col for col in merged.columns if col.endswith("__meta")]
    if duplicate_cols:
        merged = merged.drop(columns=duplicate_cols)
    regime_cols = [col for col in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if col in regimes.columns]
    if regime_cols:
        merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
    return PlanDataset(
        export_dir=export_root,
        features=features,
        metadata=metadata,
        regimes=regimes,
        splits=list(splits),
        merged=merged,
    )


def validate_dataset_contract(dataset: PlanDataset, export_dir: str | Path | None = None) -> dict[str, Any]:
    export_root = resolve_export_dir([export_dir]) if export_dir is not None else dataset.export_dir
    required_flags = [
        "pledge_pct_available",
        "rating_numeric_available",
        "days_since_earnings_available",
        "sector_dummy__NA_",
    ]
    missing_flags = [column for column in required_flags if column not in dataset.features.columns]
    dead_columns = [column for column in dataset.features.columns if column.startswith("earnings_quality_ratio")]
    audit_path = export_root / "plan_signal_audit.json"
    audit_payload = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    return {
        "missing_required_flags": missing_flags,
        "dead_earnings_quality_columns": dead_columns,
        "target_last_column": bool(dataset.features.columns[-1] == "target_weekly_return"),
        "blocking_signals": list(audit_payload.get("blocking_signals", []) or []),
        "warning_signals": list(audit_payload.get("warning_signals", []) or []),
    }


def feature_names_for_frame(features_df: pd.DataFrame) -> list[str]:
    exclude = {"date", "ticker", "target_weekly_return", "forward_return_5d"}
    numeric = set(features_df.select_dtypes(include=[np.number]).columns)
    names = [
        column
        for column in features_df.columns
        if column in numeric and column not in exclude and not str(column).endswith("__realized")
    ]
    return [name for name in names if not str(name).startswith("earnings_quality_ratio")]


def generate_anchored_weekly_splits(
    weekly_dates: Sequence[Any],
    *,
    anchor_start: str = "2019-01-01",
    train_weeks: int = 104,
    test_weeks: int = 13,
    step_weeks: int = 13,
    target_windows: int | None = None,
) -> list[dict[str, Any]]:
    dates = sorted({pd.Timestamp(value).normalize() for value in weekly_dates if pd.notna(value)})
    anchor = pd.Timestamp(anchor_start).normalize()
    dates = [date for date in dates if date >= anchor]
    if len(dates) < train_weeks + test_weeks:
        return []
    splits: list[dict[str, Any]] = []
    window_id = 1
    for test_start_idx in range(train_weeks, len(dates) - test_weeks + 1, step_weeks):
        train_slice = dates[test_start_idx - train_weeks : test_start_idx]
        test_slice = dates[test_start_idx : test_start_idx + test_weeks]
        splits.append(
            {
                "window_id": window_id,
                "train_start": str(train_slice[0].date()),
                "train_end": str(train_slice[-1].date()),
                "test_start": str(test_slice[0].date()),
                "test_end": str(test_slice[-1].date()),
            }
        )
        window_id += 1
        if target_windows and len(splits) >= int(target_windows):
            break
    return splits


def _safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    left_arr = np.asarray(left, dtype=float)
    right_arr = np.asarray(right, dtype=float)
    mask = np.isfinite(left_arr) & np.isfinite(right_arr)
    if int(mask.sum()) < 5:
        return 0.0
    corr, _ = spearmanr(left_arr[mask], right_arr[mask])
    return float(corr) if np.isfinite(corr) else 0.0


def compute_ic_series(
    frame: pd.DataFrame,
    feature: str,
    *,
    target_col: str = "target_weekly_return",
    min_obs: int = 10,
) -> pd.Series:
    rows: list[dict[str, Any]] = []
    for date_value, group in frame.groupby("date", sort=True):
        local = group[[feature, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < min_obs:
            continue
        corr = _safe_spearman(local[feature].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
        if np.isfinite(corr):
            rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(corr)})
    if not rows:
        return pd.Series(dtype="float64")
    return pd.Series([row["ic"] for row in rows], index=pd.Index([row["date"] for row in rows], name="date"), dtype="float64")


def summarize_ic_series(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {"n_dates": 0, "mean_ic": float("nan"), "ic_ir": float("nan"), "ic_tstat": float("nan"), "hit_rate": float("nan")}
    mean_ic = float(clean.mean())
    std = float(clean.std(ddof=1)) if len(clean) > 1 else float("nan")
    ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
    ic_tstat = mean_ic / (std / math.sqrt(len(clean))) if np.isfinite(std) and std > 0 else float("nan")
    return {
        "n_dates": int(len(clean)),
        "mean_ic": mean_ic,
        "ic_ir": ic_ir,
        "ic_tstat": ic_tstat,
        "hit_rate": float((clean >= 0).mean()) if mean_ic >= 0 else float((clean <= 0).mean()),
    }


def resolve_sector_tickers(dataset: PlanDataset, sector_name: str) -> list[str]:
    target = normalize_label(sector_name)
    frame = dataset.metadata.copy()
    sector_cols = [col for col in ["broad_sector", "sector", "subsector"] if col in frame.columns]
    mask = pd.Series(False, index=frame.index)
    for column in sector_cols:
        normalized = frame[column].astype("string").fillna("").map(normalize_label)
        mask = mask | normalized.eq(target) | normalized.str.contains(target, regex=False)
    return sorted(frame.loc[mask, "ticker"].astype(str).dropna().unique().tolist())


def augment_sector_conditionals(
    dataset: PlanDataset,
    *,
    base_features: Sequence[str],
    sectors: Sequence[str],
) -> tuple[pd.DataFrame, list[str]]:
    frame = dataset.features.copy()
    meta_cols = [col for col in ["date", "ticker", "broad_sector", "sector"] if col in dataset.metadata.columns]
    meta = dataset.metadata[meta_cols].copy()
    sector_col = "broad_sector" if "broad_sector" in meta.columns else "sector"
    meta[sector_col] = meta[sector_col].astype("string").fillna("Other")
    merged = frame.merge(meta, on=["date", "ticker"], how="left", sort=False)
    added: list[str] = []
    for sector_name in sectors:
        indicator_name = f"plan_sector_is_{slugify(sector_name)}"
        merged[indicator_name] = merged[sector_col].astype("string").fillna("").map(
            lambda value: 1.0 if normalize_label(value) == normalize_label(sector_name) else 0.0
        )
        added.append(indicator_name)
        for feature in base_features:
            if feature not in merged.columns:
                continue
            interaction_name = f"{feature}__{slugify(sector_name)}"
            merged[interaction_name] = pd.to_numeric(merged[feature], errors="coerce").fillna(0.0) * pd.to_numeric(
                merged[indicator_name], errors="coerce"
            ).fillna(0.0)
            added.append(interaction_name)
    return merged.drop(columns=[sector_col], errors="ignore"), added


def dominant_regime(regimes_df: pd.DataFrame, split: dict[str, Any]) -> str:
    test_start = pd.Timestamp(split["test_start"]).normalize()
    test_end = pd.Timestamp(split["test_end"]).normalize()
    window = regimes_df.loc[regimes_df["date"].between(test_start, test_end)].copy()
    label_col = "regime" if "regime" in window.columns else "plan_regime_label"
    if window.empty or label_col not in window.columns:
        return "unknown"
    counts = window[label_col].astype("string").fillna("unknown").value_counts()
    return str(counts.index[0]) if not counts.empty else "unknown"


def to_group_relevance_labels(y_values: Sequence[float], group_sizes: Sequence[int], max_relevance: int = 30) -> np.ndarray:
    y_arr = np.asarray(y_values, dtype=float).reshape(-1)
    labels = np.zeros(len(y_arr), dtype=np.int32)
    cursor = 0
    for group_size in group_sizes:
        size = int(group_size)
        if size <= 0:
            continue
        window = y_arr[cursor : cursor + size]
        if size == 1:
            labels[cursor] = 0
            cursor += size
            continue
        order = np.argsort(np.argsort(window, kind="mergesort"), kind="mergesort")
        if size - 1 <= max_relevance:
            labels[cursor : cursor + size] = np.minimum(order, max_relevance).astype(np.int32)
        else:
            scaled = np.floor(order.astype(float) * float(max_relevance) / float(size - 1))
            labels[cursor : cursor + size] = np.clip(scaled, 0, max_relevance).astype(np.int32)
        cursor += size
    return labels.astype(np.int32)


def _split_train_validation_by_groups(
    x_train: np.ndarray,
    y_train: np.ndarray,
    group_sizes: Sequence[int],
    val_fraction: float = 0.10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[int], list[int]]:
    groups = [int(size) for size in group_sizes if int(size) > 0]
    if len(groups) < 3:
        return x_train, x_train[:0], y_train, y_train[:0], groups, []
    n_val_groups = max(1, int(round(len(groups) * float(val_fraction))))
    n_val_groups = min(n_val_groups, len(groups) - 1)
    train_groups = groups[:-n_val_groups]
    val_groups = groups[-n_val_groups:]
    cut = int(sum(train_groups))
    return (
        x_train[:cut],
        x_train[cut:],
        y_train[:cut],
        y_train[cut:],
        train_groups,
        val_groups,
    )


def get_window_arrays(
    features_df: pd.DataFrame,
    split: dict[str, Any],
    feature_names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    train_start = pd.Timestamp(split["train_start"]).normalize()
    train_end = pd.Timestamp(split["train_end"]).normalize()
    test_start = pd.Timestamp(split["test_start"]).normalize()
    test_end = pd.Timestamp(split["test_end"]).normalize()

    train_df = features_df.loc[features_df["date"].between(train_start, train_end)].copy()
    test_df = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
    train_df = train_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
    test_df = test_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
    if train_df.empty or test_df.empty:
        raise ValueError(
            f"Window {split.get('window_id', '?')} has empty train/test slice "
            f"(train={len(train_df)}, test={len(test_df)})"
        )

    use_features = [name for name in feature_names if name in train_df.columns and name in test_df.columns]
    train_features = train_df[use_features].replace([np.inf, -np.inf], np.nan)
    test_features = test_df[use_features].replace([np.inf, -np.inf], np.nan)
    medians = train_features.median(axis=0, numeric_only=True).fillna(0.0)
    train_features = train_features.fillna(medians)
    test_features = test_features.fillna(medians)

    scaler = StandardScaler()
    x_train = scaler.fit_transform(train_features.to_numpy(dtype=np.float32)).astype(np.float32)
    x_test = scaler.transform(test_features.to_numpy(dtype=np.float32)).astype(np.float32)
    y_train = train_df["target_weekly_return"].to_numpy(dtype=np.float32)
    y_test = test_df["target_weekly_return"].to_numpy(dtype=np.float32)
    context = {
        "feature_names": use_features,
        "train_group_sizes": train_df.groupby("date", sort=False).size().tolist(),
        "test_group_sizes": test_df.groupby("date", sort=False).size().tolist(),
        "train_dates": train_df["date"].to_numpy(),
        "test_dates": test_df["date"].to_numpy(),
    }
    return x_train, y_train, x_test, y_test, context


def compute_window_metrics(
    y_train: np.ndarray,
    pred_train: np.ndarray,
    y_test: np.ndarray,
    pred_test: np.ndarray,
    *,
    split: dict[str, Any],
    regime: str,
) -> dict[str, Any]:
    train_ic = _safe_spearman(y_train, pred_train)
    test_ic = _safe_spearman(y_test, pred_test)
    ratio = abs(train_ic) / max(abs(test_ic), 1e-6)
    hit_rate = float(np.mean(np.sign(np.asarray(pred_test, dtype=float)) == np.sign(np.asarray(y_test, dtype=float))))
    n = len(y_test)
    q_size = max(1, n // 5)
    sorted_idx = np.argsort(np.asarray(pred_test, dtype=float))
    bottom_ret = float(np.mean(np.asarray(y_test, dtype=float)[sorted_idx[:q_size]]))
    top_ret = float(np.mean(np.asarray(y_test, dtype=float)[sorted_idx[-q_size:]]))
    return {
        "window_id": int(split.get("window_id", 0)),
        "train_start": str(split.get("train_start")),
        "train_end": str(split.get("train_end")),
        "test_start": str(split.get("test_start")),
        "test_end": str(split.get("test_end")),
        "regime": regime,
        "train_ic": round(float(train_ic), 6),
        "test_ic": round(float(test_ic), 6),
        "train_test_ratio": round(float(ratio), 4),
        "hit_rate": round(float(hit_rate), 4),
        "top_quintile_return": round(float(top_ret), 6),
        "bottom_quintile_return": round(float(bottom_ret), 6),
        "quintile_spread": round(float(top_ret - bottom_ret), 6),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }


def summarize_windows(windows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in windows if "error" not in row]
    if len(valid) < 1:
        return {
            "mean_test_ic": float("nan"),
            "std_test_ic": float("nan"),
            "ic_ir": float("nan"),
            "mean_train_test_ratio": float("nan"),
            "mean_hit_rate": float("nan"),
            "mean_quintile_spread": float("nan"),
            "windows_completed": 0,
            "windows_failed": len(windows),
            "verdict": "INSUFFICIENT_DATA",
        }
    frame = pd.DataFrame(valid)
    mean_test_ic = float(pd.to_numeric(frame["test_ic"], errors="coerce").mean())
    std_test_ic = float(pd.to_numeric(frame["test_ic"], errors="coerce").std(ddof=1)) if len(frame) > 1 else float("nan")
    ic_ir = mean_test_ic / std_test_ic if np.isfinite(std_test_ic) and abs(std_test_ic) > 1e-12 else float("nan")
    mean_ratio = float(pd.to_numeric(frame["train_test_ratio"], errors="coerce").mean())
    mean_hit = float(pd.to_numeric(frame["hit_rate"], errors="coerce").mean())
    mean_spread = float(pd.to_numeric(frame["quintile_spread"], errors="coerce").mean())
    verdict = "QUALIFIED" if np.isfinite(mean_test_ic) and mean_test_ic > 0.015 and mean_ratio < 2.5 and mean_hit > 0.51 else "NOT_QUALIFIED"
    return {
        "mean_test_ic": mean_test_ic,
        "std_test_ic": std_test_ic,
        "ic_ir": ic_ir,
        "mean_train_test_ratio": mean_ratio,
        "mean_hit_rate": mean_hit,
        "mean_quintile_spread": mean_spread,
        "windows_completed": int(len(valid)),
        "windows_failed": int(len(windows) - len(valid)),
        "verdict": verdict,
    }


def run_catboost_walkforward(
    *,
    features_df: pd.DataFrame,
    regimes_df: pd.DataFrame,
    splits: Sequence[dict[str, Any]],
    feature_names: Sequence[str],
    params: dict[str, Any],
    max_splits: int | None = None,
) -> dict[str, Any]:
    if CatBoostRanker is None or Pool is None:
        raise RuntimeError("catboost is not available in this notebook environment.")
    windows: list[dict[str, Any]] = []
    active_splits = list(splits[: max_splits]) if max_splits else list(splits)
    for index, raw_split in enumerate(active_splits, start=1):
        split = dict(raw_split)
        split["window_id"] = int(split.get("window_id", index))
        regime = dominant_regime(regimes_df, split)
        try:
            x_train, y_train, x_test, y_test, context = get_window_arrays(features_df, split, feature_names)
            x_fit, x_val, y_fit, y_val, fit_groups, val_groups = _split_train_validation_by_groups(
                x_train,
                y_train,
                context["train_group_sizes"],
            )
            y_fit_rank = to_group_relevance_labels(y_fit, fit_groups)
            train_pool = Pool(x_fit, y_fit_rank, group_id=np.repeat(np.arange(len(fit_groups)), fit_groups))
            model = CatBoostRanker(
                iterations=int(params.get("iterations", 800)),
                depth=int(params.get("depth", 4)),
                learning_rate=float(params.get("learning_rate", 0.02)),
                l2_leaf_reg=float(params.get("l2_leaf_reg", 15.0)),
                min_data_in_leaf=int(params.get("min_data_in_leaf", 40)),
                loss_function=str(params.get("loss_function", "YetiRank")),
                eval_metric=str(params.get("eval_metric", "NDCG")),
                boosting_type=str(params.get("boosting_type", "Ordered")),
                od_type="Iter",
                od_wait=int(params.get("od_wait", 30)),
                verbose=int(params.get("verbose", 0)),
                random_seed=42,
                task_type="GPU" if (CatBoostRanker is not None and torch is not None and torch.cuda.is_available()) else "CPU",
            )
            fit_kwargs: dict[str, Any] = {}
            if len(y_val):
                y_val_rank = to_group_relevance_labels(y_val, val_groups)
                fit_kwargs["eval_set"] = Pool(x_val, y_val_rank, group_id=np.repeat(np.arange(len(val_groups)), val_groups))
                fit_kwargs["use_best_model"] = True
            model.fit(train_pool, **fit_kwargs)
            train_preds = model.predict(x_train)
            test_preds = model.predict(x_test)
            windows.append(
                compute_window_metrics(
                    y_train,
                    np.asarray(train_preds, dtype=float),
                    y_test,
                    np.asarray(test_preds, dtype=float),
                    split=split,
                    regime=regime,
                )
            )
        except Exception as exc:  # noqa: BLE001
            windows.append(
                {
                    "window_id": int(split.get("window_id", index)),
                    "train_start": str(split.get("train_start")),
                    "train_end": str(split.get("train_end")),
                    "test_start": str(split.get("test_start")),
                    "test_end": str(split.get("test_end")),
                    "regime": regime,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    summary = summarize_windows(windows)
    return {"model_name": "CatBoost", "params": dict(params), "windows": windows, "summary": summary}


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


def _make_pairwise_ranking_loss(margin: float = 0.005):
    def ranking_loss(scores, targets):
        n = len(scores)
        if n < 2:
            return nn.functional.mse_loss(scores, targets)
        s_i = scores.unsqueeze(1).expand(n, n)
        s_j = scores.unsqueeze(0).expand(n, n)
        t_i = targets.unsqueeze(1).expand(n, n)
        t_j = targets.unsqueeze(0).expand(n, n)
        should_be_higher = (t_i > t_j).float()
        pair_loss = torch.relu(margin - (s_i - s_j)) * should_be_higher
        n_pairs = should_be_higher.sum().clamp(min=1)
        return pair_loss.sum() / n_pairs

    return ranking_loss


def _reshape_feature_sequence(x_values: np.ndarray, lookback_weeks: int) -> tuple[np.ndarray, int]:
    n_samples, n_features = x_values.shape
    step_dim = int(np.ceil(n_features / lookback_weeks))
    padded_dim = lookback_weeks * step_dim
    pad_width = padded_dim - n_features
    x_arr = np.asarray(x_values, dtype=np.float32)
    if pad_width > 0:
        x_arr = np.pad(x_arr, ((0, 0), (0, pad_width)), mode="constant")
    return x_arr.reshape(n_samples, lookback_weeks, step_dim).astype(np.float32), n_features


class LSTMRanker(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 32, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, max(8, hidden_size // 2)),
            nn.GELU(),
            nn.Linear(max(8, hidden_size // 2), 1),
        )

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.head(h_n[-1]).squeeze(-1)


class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x):
        return x[:, :, :-self.chomp_size] if self.chomp_size > 0 else x


class TemporalBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation),
            Chomp1d(padding),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(out_channels, out_channels, kernel_size, padding=padding, dilation=dilation),
            Chomp1d(padding),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, x):
        return self.net(x) + self.downsample(x)


class TCNRanker(nn.Module):
    def __init__(
        self,
        input_size: int,
        num_channels: Sequence[int] = (32, 32, 64),
        kernel_size: int = 3,
        dilations: Sequence[int] = (1, 2, 4, 8),
        dropout: float = 0.2,
    ):
        super().__init__()
        channels = [input_size] + list(num_channels)
        blocks = []
        for idx, dilation in enumerate(dilations):
            in_channels = channels[min(idx, len(channels) - 1)]
            out_channels = channels[min(idx + 1, len(channels) - 1)]
            blocks.append(TemporalBlock(in_channels, out_channels, kernel_size, dilation, dropout))
        self.network = nn.Sequential(*blocks)
        self.head = nn.Sequential(
            nn.LayerNorm(channels[-1]),
            nn.Dropout(dropout),
            nn.Linear(channels[-1], 1),
        )

    def forward(self, x):
        y = self.network(x.transpose(1, 2))
        pooled = y.mean(dim=-1)
        return self.head(pooled).squeeze(-1)


def _train_sequence_model(
    model_cls,
    *,
    x_train: np.ndarray,
    y_train: np.ndarray,
    lookback_weeks: int,
    device: str,
    model_kwargs: dict[str, Any],
    max_epochs: int,
    patience: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> tuple[Any, np.ndarray]:
    x_seq, _ = _reshape_feature_sequence(x_train, lookback_weeks)
    split_idx = max(int(len(x_seq) * 0.9), 1)
    x_fit = torch.tensor(x_seq[:split_idx], dtype=torch.float32, device=device)
    y_fit = torch.tensor(y_train[:split_idx], dtype=torch.float32, device=device)
    x_val = torch.tensor(x_seq[split_idx:], dtype=torch.float32, device=device) if split_idx < len(x_seq) else x_fit[:0]
    y_val = torch.tensor(y_train[split_idx:], dtype=torch.float32, device=device) if split_idx < len(x_seq) else y_fit[:0]

    model = model_cls(input_size=x_seq.shape[2], **model_kwargs).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    loss_fn = _make_pairwise_ranking_loss()
    best_loss = float("inf")
    best_state = None
    patience_counter = 0
    batch_size = min(int(batch_size), len(x_fit))

    for _ in range(int(max_epochs)):
        perm = torch.randperm(len(x_fit), device=device)
        model.train()
        for start in range(0, len(x_fit), batch_size):
            idx = perm[start : start + batch_size]
            xb = x_fit[idx]
            yb = y_fit[idx]
            optimizer.zero_grad(set_to_none=True)
            preds = model(xb)
            loss = loss_fn(preds, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            eval_x = x_val if len(x_val) else x_fit
            eval_y = y_val if len(y_val) else y_fit
            eval_loss = float(loss_fn(model(eval_x), eval_y).item())
        if eval_loss < best_loss - 1e-4:
            best_loss = eval_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= int(patience):
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, x_seq


def run_sequence_walkforward(
    *,
    model_name: str,
    model_cls,
    model_kwargs: dict[str, Any],
    features_df: pd.DataFrame,
    regimes_df: pd.DataFrame,
    splits: Sequence[dict[str, Any]],
    feature_names: Sequence[str],
    max_splits: int | None = None,
    lookback_weeks: int = 12,
    max_epochs: int = 8,
    patience: int = 3,
    batch_size: int = 128,
    learning_rate: float = 0.001,
    weight_decay: float = 1e-4,
    seeds: Sequence[int] = (42,),
) -> dict[str, Any]:
    if torch is None or nn is None:
        return {
            "model_name": model_name,
            "windows": [{"window_id": 0, "error": "torch unavailable"}],
            "summary": summarize_windows([]),
        }
    device = "cuda" if torch.cuda.is_available() else "cpu"
    active_splits = list(splits[: max_splits]) if max_splits else list(splits)
    windows: list[dict[str, Any]] = []
    for index, raw_split in enumerate(active_splits, start=1):
        split = dict(raw_split)
        split["window_id"] = int(split.get("window_id", index))
        regime = dominant_regime(regimes_df, split)
        try:
            x_train, y_train, x_test, y_test, _ = get_window_arrays(features_df, split, feature_names)
            all_train: list[np.ndarray] = []
            all_test: list[np.ndarray] = []
            x_test_seq, _ = _reshape_feature_sequence(x_test, lookback_weeks)
            x_test_tensor = torch.tensor(x_test_seq, dtype=torch.float32, device=device)
            for seed in list(seeds):
                _set_seed(int(seed))
                model, x_train_seq = _train_sequence_model(
                    model_cls,
                    x_train=x_train,
                    y_train=y_train,
                    lookback_weeks=lookback_weeks,
                    device=device,
                    model_kwargs=model_kwargs,
                    max_epochs=max_epochs,
                    patience=patience,
                    batch_size=batch_size,
                    learning_rate=learning_rate,
                    weight_decay=weight_decay,
                )
                model.eval()
                x_train_tensor = torch.tensor(x_train_seq, dtype=torch.float32, device=device)
                with torch.no_grad():
                    train_preds = model(x_train_tensor).detach().cpu().numpy()
                    test_preds = model(x_test_tensor).detach().cpu().numpy()
                all_train.append(np.asarray(train_preds, dtype=float))
                all_test.append(np.asarray(test_preds, dtype=float))
                del model, x_train_tensor
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            windows.append(
                compute_window_metrics(
                    y_train,
                    np.mean(np.vstack(all_train), axis=0),
                    y_test,
                    np.mean(np.vstack(all_test), axis=0),
                    split=split,
                    regime=regime,
                )
            )
        except Exception as exc:  # noqa: BLE001
            windows.append(
                {
                    "window_id": int(split.get("window_id", index)),
                    "train_start": str(split.get("train_start")),
                    "train_end": str(split.get("train_end")),
                    "test_start": str(split.get("test_start")),
                    "test_end": str(split.get("test_end")),
                    "regime": regime,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {"model_name": model_name, "windows": windows, "summary": summarize_windows(windows)}


def _best_ratio_params(
    output_root: str | Path,
    version: str,
    *,
    manual_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(DEFAULT_CATBOOST_PARAMS)
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        payload = load_summary_if_exists(output_root, exp_id, version)
        best = dict((payload or {}).get("best_candidate") or {})
        values = dict(best.get("params") or {})
        if values:
            params.update(values)
            break
    if manual_override:
        params.update(dict(manual_override))
    return params


def _candidate_table(candidates: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in candidates:
        merged = dict(row)
        params = dict(merged.pop("params", {}))
        for key, value in params.items():
            merged[f"param_{key}"] = value
        rows.append(merged)
    return pd.DataFrame(rows)


def run_ratio_experiment(
    exp_id: str,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str = "full",
    max_splits: int | None = None,
    version: str = "v1",
    manual_upstream_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = get_experiment_spec(exp_id)
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []
    base_feature_names = feature_names_for_frame(dataset.features)

    if spec.exp_id == "EXP-09":
        base_params = dict(DEFAULT_CATBOOST_PARAMS)
        base_params.update(dict(spec.params.get("base_catboost") or {}))
        for depth in list(spec.params.get("depth_grid") or []):
            for od_wait in list(spec.params.get("early_stopping_rounds") or []):
                params = {**base_params, "depth": int(depth), "od_wait": int(od_wait)}
                state = run_catboost_walkforward(
                    features_df=dataset.features,
                    regimes_df=dataset.regimes,
                    splits=dataset.splits,
                    feature_names=base_feature_names,
                    params=params,
                    max_splits=max_splits,
                )
                summary = dict(state.get("summary") or {})
                candidates.append(
                    {
                        "params": dict(params),
                        "mean_test_ic": summary.get("mean_test_ic"),
                        "ic_ir": summary.get("ic_ir"),
                        "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                        "mean_hit_rate": summary.get("mean_hit_rate"),
                        "windows_completed": summary.get("windows_completed"),
                    }
                )
        notes.append("Standalone notebook run: no external code dataset is required.")

    elif spec.exp_id == "EXP-10":
        upstream = _best_ratio_params(output_root, version, manual_override=manual_upstream_params)
        for l2_leaf_reg in list(spec.params.get("l2_leaf_reg_grid") or []):
            params = {**upstream, "l2_leaf_reg": float(l2_leaf_reg)}
            state = run_catboost_walkforward(
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=dataset.splits,
                feature_names=base_feature_names,
                params=params,
                max_splits=max_splits,
            )
            summary = dict(state.get("summary") or {})
            candidates.append(
                {
                    "params": dict(params),
                    "mean_test_ic": summary.get("mean_test_ic"),
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "mean_hit_rate": summary.get("mean_hit_rate"),
                    "windows_completed": summary.get("windows_completed"),
                }
            )
        notes.append("When no prior EXP-09 summary exists, this notebook falls back to the default CatBoost baseline.")

    elif spec.exp_id == "EXP-11":
        upstream = _best_ratio_params(output_root, version, manual_override=manual_upstream_params)
        for boosting_type in list(spec.params.get("boosting_types") or []):
            params = {**upstream, "boosting_type": str(boosting_type)}
            state = run_catboost_walkforward(
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=dataset.splits,
                feature_names=base_feature_names,
                params=params,
                max_splits=max_splits,
            )
            summary = dict(state.get("summary") or {})
            candidates.append(
                {
                    "params": dict(params),
                    "mean_test_ic": summary.get("mean_test_ic"),
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "mean_hit_rate": summary.get("mean_hit_rate"),
                    "windows_completed": summary.get("windows_completed"),
                }
            )
        notes.append("Only the CatBoost boosting type changes in this comparison.")

    elif spec.exp_id == "EXP-12":
        upstream = _best_ratio_params(output_root, version, manual_override=manual_upstream_params)
        weekly_dates = pd.to_datetime(dataset.features["date"], errors="coerce").dropna().sort_values().unique().tolist()
        for years in list(spec.params.get("train_window_years") or []):
            custom_splits = generate_anchored_weekly_splits(
                weekly_dates,
                anchor_start="2019-01-01",
                train_weeks=int(years) * 52,
                test_weeks=int(spec.params.get("test_window_weeks") or 26),
                step_weeks=int(spec.params.get("step_weeks") or 26),
                target_windows=0,
            )
            state = run_catboost_walkforward(
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=custom_splits,
                feature_names=base_feature_names,
                params=upstream,
                max_splits=max_splits,
            )
            summary = dict(state.get("summary") or {})
            params = {**dict(upstream), "train_window_years": int(years)}
            candidates.append(
                {
                    "params": params,
                    "mean_test_ic": summary.get("mean_test_ic"),
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "mean_hit_rate": summary.get("mean_hit_rate"),
                    "windows_completed": summary.get("windows_completed"),
                    "split_count": len(custom_splits),
                }
            )
        notes.append("EXP-12 rebuilds the walk-forward windows directly inside the notebook.")

    else:
        raise KeyError(f"unsupported_ratio_experiment:{exp_id}")

    table = _candidate_table(candidates)
    write_table(paths.experiment_root / "candidate_table.csv", table)
    best = pick_best_candidate(candidates) or {}
    payload = {
        "exp_id": spec.exp_id,
        "title": spec.title,
        "family": spec.family,
        "hypothesis": spec.hypothesis,
        "candidate_count": len(candidates),
        "best_candidate": best,
        "candidates": candidates,
    }
    write_json(paths.summary_path, payload)
    write_narrative(
        paths.narrative_path,
        exp_id=spec.exp_id,
        title=spec.title,
        hypothesis=spec.hypothesis,
        metrics={
            "candidate_count": len(candidates),
            "best_mean_test_ic": best.get("mean_test_ic"),
            "best_ic_ir": best.get("ic_ir"),
            "best_mean_train_test_ratio": best.get("mean_train_test_ratio"),
            "best_params": best.get("params"),
        },
        extra_notes=notes,
    )
    return payload


def run_sector_experiment(
    exp_id: str,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str = "full",
    max_splits: int | None = None,
    version: str = "v1",
    best_params_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = get_experiment_spec(exp_id)
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    best_params = _best_ratio_params(output_root, version, manual_override=best_params_override)

    if spec.exp_id in {"EXP-13", "EXP-14", "EXP-15"}:
        sector_name = str(spec.params.get("sector_name") or "")
        tickers = resolve_sector_tickers(dataset, sector_name)
        features = dataset.features.loc[dataset.features["ticker"].astype(str).isin(set(tickers))].copy()
        state = run_catboost_walkforward(
            features_df=features,
            regimes_df=dataset.regimes,
            splits=dataset.splits,
            feature_names=feature_names_for_frame(features),
            params=best_params,
            max_splits=max_splits,
        )
        summary = dict(state.get("summary") or {})
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "sector_name": sector_name,
            "n_tickers": len(tickers),
            "tickers": tickers,
            "best_params": best_params,
            "catboost_summary": summary,
        }
        write_json(paths.experiment_root / "sector_subset_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "sector_name": sector_name,
                "n_tickers": len(tickers),
                "mean_test_ic": summary.get("mean_test_ic"),
                "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
            },
            extra_notes=[
                "This self-contained notebook resolves sector membership from northstar_metadata.parquet.",
                "If no prior ratio summary exists, it falls back to the default CatBoost baseline.",
            ],
        )
        return payload

    if spec.exp_id == "EXP-16":
        plan = load_plan_info()
        feature_frame, added_features = augment_sector_conditionals(
            dataset,
            base_features=plan.sector_conditional_features,
            sectors=list(spec.params.get("sectors") or []),
        )
        state = run_catboost_walkforward(
            features_df=feature_frame,
            regimes_df=dataset.regimes,
            splits=dataset.splits,
            feature_names=feature_names_for_frame(feature_frame),
            params=best_params,
            max_splits=max_splits,
        )
        summary = dict(state.get("summary") or {})
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "best_params": best_params,
            "added_feature_count": len(added_features),
            "added_features": added_features,
            "catboost_summary": summary,
        }
        write_json(paths.experiment_root / "augmented_feature_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "added_feature_count": len(added_features),
                "mean_test_ic": summary.get("mean_test_ic"),
                "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
            },
            extra_notes=["This run creates explicit sector indicators and sector-conditional feature interactions inside the notebook."],
        )
        return payload

    raise KeyError(f"unsupported_sector_experiment:{exp_id}")


def load_major_events() -> pd.DataFrame:
    frame = pd.DataFrame(MAJOR_EVENTS_RECORDS)
    for column in ["start_date", "end_date"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    return frame.sort_values(["start_date", "event_id"], kind="mergesort").reset_index(drop=True)


def select_high_risk_events(events_df: pd.DataFrame, dataset: PlanDataset, top_n: int = 5) -> pd.DataFrame:
    min_date = pd.to_datetime(dataset.features["date"], errors="coerce").dropna().min()
    max_date = pd.to_datetime(dataset.features["date"], errors="coerce").dropna().max()
    frame = events_df.loc[(events_df["end_date"] >= min_date) & (events_df["start_date"] <= max_date)].copy()
    collapse_rank = frame["model_collapse_risk"].astype("string").fillna("").map(
        lambda value: 2 if "EXTREME" in str(value).upper() else 1 if "HIGH" in str(value).upper() else 0
    )
    frame["_collapse_rank"] = collapse_rank
    frame = frame.sort_values(
        ["_collapse_rank", "severity_score_1_10", "start_date"],
        ascending=[False, False, True],
        kind="mergesort",
    )
    return frame.head(int(top_n)).drop(columns=["_collapse_rank"])


def build_event_split(dataset: PlanDataset, *, start_date: Any, end_date: Any, train_weeks: int = 104) -> list[dict[str, Any]]:
    dates = sorted(pd.to_datetime(dataset.features["date"], errors="coerce").dropna().dt.normalize().unique().tolist())
    test_dates = [date for date in dates if pd.Timestamp(start_date) <= pd.Timestamp(date) <= pd.Timestamp(end_date)]
    if not test_dates:
        raise ValueError(f"event_has_no_weekly_rows:{start_date}:{end_date}")
    test_start = pd.Timestamp(min(test_dates)).normalize()
    test_end = pd.Timestamp(max(test_dates)).normalize()
    prior_dates = [date for date in dates if pd.Timestamp(date) < test_start]
    if not prior_dates:
        raise ValueError(f"event_has_no_training_history:{start_date}:{end_date}")
    train_slice = prior_dates[-int(train_weeks) :] if len(prior_dates) > int(train_weeks) else prior_dates
    return [
        {
            "window_id": 1,
            "train_start": str(pd.Timestamp(train_slice[0]).date()),
            "train_end": str(pd.Timestamp(train_slice[-1]).date()),
            "test_start": str(test_start.date()),
            "test_end": str(test_end.date()),
        }
    ]


def run_regime_experiment(
    exp_id: str,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str = "full",
    max_splits: int | None = None,
    version: str = "v1",
    best_params_override: dict[str, Any] | None = None,
    run_sequence_models: bool = True,
) -> dict[str, Any]:
    spec = get_experiment_spec(exp_id)
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    events_df = load_major_events()

    if spec.exp_id == "EXP-17":
        plan = load_plan_info()
        rows: list[dict[str, Any]] = []
        for event in events_df.to_dict(orient="records"):
            event_frame = dataset.merged.loc[
                dataset.merged["date"].between(pd.Timestamp(event["start_date"]), pd.Timestamp(event["end_date"]))
            ].copy()
            if event_frame.empty:
                continue
            for factor in list(plan.anchor_factors):
                if factor not in event_frame.columns:
                    continue
                summary = summarize_ic_series(compute_ic_series(event_frame, factor))
                rows.append(
                    {
                        "event_id": event["event_id"],
                        "event_name": event["event_name"],
                        "factor": factor,
                        "mean_ic": summary["mean_ic"],
                        "ic_ir": summary["ic_ir"],
                        "ic_tstat": summary["ic_tstat"],
                        "n_dates": summary["n_dates"],
                        "severity_score_1_10": event.get("severity_score_1_10"),
                        "model_collapse_risk": event.get("model_collapse_risk"),
                    }
                )
        table = pd.DataFrame(rows)
        write_table(paths.experiment_root / "factor_event_heatmap.csv", table)
        write_table(paths.experiment_root / "factor_event_heatmap.parquet", table)
        blind_spots = (
            table.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort")
            .head(10)
            .to_dict(orient="records")
            if not table.empty
            else []
        )
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "event_count": int(table["event_id"].nunique()) if not table.empty else 0,
            "factor_count": int(table["factor"].nunique()) if not table.empty else 0,
            "blind_spots": blind_spots,
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "event_count": payload["event_count"],
                "factor_count": payload["factor_count"],
                "weakest_factor_event_cells": len(blind_spots),
            },
            extra_notes=["This self-contained notebook embeds the canonical major-event table."],
        )
        return payload

    if spec.exp_id == "EXP-18":
        params = _best_ratio_params(output_root, version, manual_override=best_params_override)
        risky = select_high_risk_events(events_df, dataset, top_n=int(spec.params.get("top_n_high_risk_events") or 5))
        rows: list[dict[str, Any]] = []
        for event in risky.to_dict(orient="records"):
            split = build_event_split(
                dataset,
                start_date=event["start_date"],
                end_date=event["end_date"],
                train_weeks=int(spec.params.get("train_window_weeks") or 104),
            )
            min_date = split[0]["train_start"]
            max_date = split[0]["test_end"]
            features = dataset.features.loc[dataset.features["date"].between(pd.Timestamp(min_date), pd.Timestamp(max_date))].copy()
            state = run_catboost_walkforward(
                features_df=features,
                regimes_df=dataset.regimes,
                splits=split,
                feature_names=feature_names_for_frame(features),
                params=params,
                max_splits=1,
            )
            summary = dict(state.get("summary") or {})
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_name": event["event_name"],
                    "severity_score_1_10": event.get("severity_score_1_10"),
                    "model_collapse_risk": event.get("model_collapse_risk"),
                    "mean_test_ic": summary.get("mean_test_ic"),
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "windows_completed": summary.get("windows_completed"),
                }
            )
        table = pd.DataFrame(rows)
        write_table(paths.experiment_root / "event_collapse_table.csv", table)
        worst = (
            table.sort_values(["mean_test_ic", "mean_train_test_ratio"], ascending=[True, False], kind="mergesort")
            .head(3)
            .to_dict(orient="records")
            if not table.empty
            else []
        )
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "events_tested": int(len(table)),
            "worst_events": worst,
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "events_tested": len(table),
                "worst_event_mean_test_ic": worst[0]["mean_test_ic"] if worst else None,
            },
            extra_notes=["Each event run creates a single chronological train/test split ending exactly before the event starts."],
        )
        return payload

    if spec.exp_id == "EXP-19":
        params = _best_ratio_params(output_root, version, manual_override=best_params_override)
        states: dict[str, dict[str, Any]] = {
            "CatBoost": run_catboost_walkforward(
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=dataset.splits,
                feature_names=feature_names_for_frame(dataset.features),
                params=params,
                max_splits=max_splits,
            )
        }
        if run_sequence_models:
            states["LSTM"] = run_sequence_walkforward(
                model_name="LSTM",
                model_cls=LSTMRanker,
                model_kwargs={"hidden_size": 32, "num_layers": 2, "dropout": 0.2},
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=dataset.splits,
                feature_names=feature_names_for_frame(dataset.features),
                max_splits=max_splits,
                lookback_weeks=12,
                max_epochs=8,
                patience=3,
                seeds=(42,),
            )
            states["TCN"] = run_sequence_walkforward(
                model_name="TCN",
                model_cls=TCNRanker,
                model_kwargs={"num_channels": (32, 32, 64), "kernel_size": 3, "dilations": (1, 2, 4, 8), "dropout": 0.2},
                features_df=dataset.features,
                regimes_df=dataset.regimes,
                splits=dataset.splits,
                feature_names=feature_names_for_frame(dataset.features),
                max_splits=max_splits,
                lookback_weeks=26,
                max_epochs=8,
                patience=3,
                seeds=(42,),
            )

        rows: list[dict[str, Any]] = []
        for model_name, state in states.items():
            frame = pd.DataFrame([row for row in state.get("windows", []) if "error" not in row])
            if frame.empty:
                continue
            grouped = (
                frame.groupby("regime", as_index=False)
                .agg(mean_test_ic=("test_ic", "mean"), mean_ratio=("train_test_ratio", "mean"), n_windows=("window_id", "count"))
            )
            for row in grouped.to_dict(orient="records"):
                rows.append({"model": model_name, **row})

        routing_table = pd.DataFrame(rows).sort_values(["regime", "mean_test_ic"], ascending=[True, False], kind="mergesort")
        write_table(paths.experiment_root / "routing_table.csv", routing_table)
        routing_rows: list[dict[str, Any]] = []
        if not routing_table.empty:
            for regime_name, group in routing_table.groupby("regime", sort=True):
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
        routed_mean_ic = float(pd.DataFrame(routing_rows)["selected_mean_test_ic"].mean()) if routing_rows else float("nan")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "candidate_models": list(states.keys()),
            "routed_mean_ic": routed_mean_ic,
            "routing_rows": routing_rows,
            "model_summaries": {name: state.get("summary") for name, state in states.items()},
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "candidate_models": list(states.keys()),
                "regime_count": int(pd.DataFrame(routing_rows)["regime"].nunique()) if routing_rows else 0,
                "routed_mean_ic": routed_mean_ic,
            },
            extra_notes=[
                "The routing policy chooses the model with the highest observed mean test IC inside each regime.",
                "Sequence models are trained directly inside the notebook with lightweight PyTorch heads.",
            ],
        )
        return payload

    raise KeyError(f"unsupported_regime_experiment:{exp_id}")
