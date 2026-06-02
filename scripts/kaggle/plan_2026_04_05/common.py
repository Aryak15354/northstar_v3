"""Shared runtime helpers for the compendium-aligned experiment suite."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint" / "shared"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    derive_size_rank,
    generate_anchored_weekly_splits,
    json_ready,
    load_export_artifacts,
    read_json,
    resolve_export_dir,
    safe_spearman,
    subset_feature_export,
    write_json,
)


def _load_shared_module(module_name: str):
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        module_path = SHARED_DIR / f"{module_name}.py"
        if not module_path.exists():
            raise FileNotFoundError(f"missing_shared_kaggle_module:{module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable_to_load_shared_kaggle_module:{module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


_track_a_runner = _load_shared_module("track_a_runner")
_track_b_runner = _load_shared_module("track_b_runner")
TrackARunConfig = _track_a_runner.TrackARunConfig
TrackARunner = _track_a_runner.TrackARunner
TrackBRunConfig = _track_b_runner.TrackBRunConfig
TrackBRunner = _track_b_runner.TrackBRunner


class ConfigurableTrackARunner(TrackARunner):
    def __init__(self, config: TrackARunConfig | None = None, *, tree_overrides: dict[str, Any] | None = None):
        self.tree_overrides = dict(tree_overrides or {})
        super().__init__(config=config)

    def _tree_configs(self):  # type: ignore[override]
        xgb_config, lightgbm_config, catboost_config = super()._tree_configs()
        catboost_config.update(self.tree_overrides)
        return xgb_config, lightgbm_config, catboost_config


class ConfigurableTrackBRunner(TrackBRunner):
    def __init__(self, config: TrackBRunConfig | None = None, *, frontier_overrides: dict[str, dict[str, Any]] | None = None):
        self.frontier_overrides = {str(key): dict(value) for key, value in dict(frontier_overrides or {}).items()}
        super().__init__(config=config)

    def _frontier_configs(self):  # type: ignore[override]
        tft_config, itr_config = super()._frontier_configs()
        mapping = {"tft": tft_config, "itransformer": itr_config}
        for name, overrides in self.frontier_overrides.items():
            if name in mapping:
                mapping[name].update(overrides)
        return mapping["tft"], mapping["itransformer"]


@dataclass(frozen=True)
class ExperimentPaths:
    experiment_root: Path
    artifacts_dir: Path
    summary_path: Path
    narrative_path: Path


@dataclass(frozen=True)
class PlanDataset:
    export_dir: Path
    features: pd.DataFrame
    splits: list[dict[str, Any]]
    regimes: pd.DataFrame
    metadata: pd.DataFrame
    merged: pd.DataFrame


def normalize_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def slugify(value: Any) -> str:
    clean = normalize_label(value).replace(" ", "_")
    return clean or "unknown"


def load_plan_dataset(export_dir: str | Path) -> PlanDataset:
    artifacts = resolve_export_dir(export_dir)
    features, splits, regimes, metadata = load_export_artifacts(artifacts.export_dir)
    merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    regime_cols = [col for col in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if col in regimes.columns]
    if regime_cols:
        merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
    for base_name in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id"]:
        if base_name in merged.columns:
            continue
        left_name = f"{base_name}_x"
        right_name = f"{base_name}_y"
        if left_name in merged.columns and right_name in merged.columns:
            merged[base_name] = merged[left_name].where(pd.Series(merged[left_name]).notna(), merged[right_name])
        elif left_name in merged.columns:
            merged[base_name] = merged[left_name]
        elif right_name in merged.columns:
            merged[base_name] = merged[right_name]
    return PlanDataset(
        export_dir=artifacts.export_dir,
        features=features,
        splits=list(splits),
        regimes=regimes,
        metadata=metadata,
        merged=merged,
    )


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


def resolve_feature(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lookup = {str(column): str(column) for column in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def compute_ic_series(frame: pd.DataFrame, feature: str, target_col: str = "target_weekly_return", min_obs: int = 8) -> pd.Series:
    if feature not in frame.columns or target_col not in frame.columns:
        return pd.Series(dtype="float64")
    rows: list[dict[str, Any]] = []
    for date_value, group in frame.groupby("date", sort=True):
        local = group[[feature, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < min_obs:
            continue
        corr = safe_spearman(
            local[feature].to_numpy(dtype=float),
            local[target_col].to_numpy(dtype=float),
        )
        if np.isfinite(corr):
            rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(corr)})
    if not rows:
        return pd.Series(dtype="float64")
    series = pd.Series(
        [row["ic"] for row in rows],
        index=pd.Index([row["date"] for row in rows], name="date"),
        dtype="float64",
    )
    return series.sort_index()


def summarize_ic_series(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {
            "n_dates": 0,
            "mean_ic": float("nan"),
            "ic_ir": float("nan"),
            "ic_tstat": float("nan"),
            "hit_rate": float("nan"),
            "sign_stability": float("nan"),
            "recent8_mean_ic": float("nan"),
            "prior8_mean_ic": float("nan"),
        }
    mean_ic = float(clean.mean())
    std = float(clean.std(ddof=1)) if len(clean) > 1 else float("nan")
    ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
    ic_tstat = mean_ic / (std / math.sqrt(len(clean))) if np.isfinite(std) and std > 0 else float("nan")
    pos_rate = float((clean > 0).mean())
    neg_rate = float((clean < 0).mean())
    recent = clean.tail(8)
    prior = clean.iloc[-16:-8] if len(clean) >= 16 else pd.Series(dtype="float64")
    return {
        "n_dates": int(len(clean)),
        "mean_ic": mean_ic,
        "ic_ir": ic_ir,
        "ic_tstat": ic_tstat,
        "hit_rate": float((clean >= 0).mean()) if mean_ic >= 0 else float((clean <= 0).mean()),
        "sign_stability": max(pos_rate, neg_rate),
        "recent8_mean_ic": float(recent.mean()) if not recent.empty else float("nan"),
        "prior8_mean_ic": float(prior.mean()) if not prior.empty else float("nan"),
    }


def market_cap_correlation(frame: pd.DataFrame, feature: str) -> float:
    candidate = "market_cap"
    if candidate not in frame.columns:
        candidate = "market_cap_rank" if "market_cap_rank" in frame.columns else ""
    if not candidate or feature not in frame.columns:
        return float("nan")
    values: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        local = group[[feature, candidate]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 8:
            continue
        corr = safe_spearman(local[feature].to_numpy(dtype=float), local[candidate].to_numpy(dtype=float))
        if np.isfinite(corr):
            values.append(abs(float(corr)))
    return float(np.mean(values)) if values else float("nan")


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
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def run_five_test_battery(frame: pd.DataFrame, feature: str, *, narrative: str) -> dict[str, Any]:
    ic_series = compute_ic_series(frame, feature)
    summary = summarize_ic_series(ic_series)
    recent = float(summary.get("recent8_mean_ic", float("nan")))
    prior = float(summary.get("prior8_mean_ic", float("nan")))
    decay_ratio = abs(recent) / abs(prior) if np.isfinite(prior) and abs(prior) > 1e-12 else float("nan")
    market_corr = market_cap_correlation(frame, feature)
    tests = {
        "T1": bool(np.isfinite(summary["ic_tstat"]) and float(summary["ic_tstat"]) > 1.96),
        "T2": bool(np.isfinite(summary["sign_stability"]) and float(summary["sign_stability"]) > 0.60),
        "T3": bool(np.isfinite(decay_ratio) and decay_ratio > 0.60),
        "T4": bool(np.isfinite(market_corr) and market_corr < 0.40),
        "T5": bool(len(str(narrative or "").strip()) >= 30),
    }
    return {
        "feature": feature,
        "tests": tests,
        "all_pass": bool(all(tests.values())),
        "mean_ic": summary["mean_ic"],
        "ic_ir": summary["ic_ir"],
        "ic_tstat": summary["ic_tstat"],
        "sign_stability": summary["sign_stability"],
        "decay_ratio": decay_ratio,
        "market_cap_spearman_abs": market_corr,
        "n_dates": summary["n_dates"],
    }


def resolve_sector_tickers(dataset: PlanDataset, sector_name: str) -> list[str]:
    target = normalize_label(sector_name)
    frame = dataset.metadata.copy()
    sector_cols = [col for col in ["broad_sector", "sector", "subsector"] if col in frame.columns]
    mask = pd.Series(False, index=frame.index)
    for col in sector_cols:
        normalized = frame[col].astype("string").fillna("").map(normalize_label)
        mask = mask | normalized.eq(target) | normalized.str.contains(target, regex=False)
    return sorted(frame.loc[mask, "ticker"].astype(str).dropna().unique().tolist())


def top_large_cap_tickers(dataset: PlanDataset, top_n: int) -> list[str]:
    rank_frame = dataset.metadata[["ticker"]].copy()
    rank_frame["size_rank"] = derive_size_rank(dataset.metadata)
    medians = rank_frame.groupby("ticker", as_index=True)["size_rank"].median().sort_values(ascending=False)
    return medians.head(int(top_n)).index.astype(str).tolist()


def augment_sector_conditionals(
    dataset: PlanDataset,
    *,
    base_features: Sequence[str],
    sectors: Sequence[str],
) -> tuple[pd.DataFrame, list[str]]:
    frame = dataset.features.copy()
    meta = dataset.metadata[["date", "ticker", "broad_sector"]].copy()
    meta["broad_sector"] = meta["broad_sector"].astype("string").fillna("Other")
    merged = frame.merge(meta, on=["date", "ticker"], how="left", sort=False)
    added: list[str] = []
    for sector_name in sectors:
        indicator_name = f"plan_sector_is_{slugify(sector_name)}"
        merged[indicator_name] = merged["broad_sector"].astype("string").fillna("").map(
            lambda value: 1.0 if normalize_label(value) == normalize_label(sector_name) else 0.0
        )
        added.append(indicator_name)
        for feature in base_features:
            if feature not in merged.columns:
                continue
            interaction_name = f"{feature}__{slugify(sector_name)}"
            merged[interaction_name] = pd.to_numeric(merged[feature], errors="coerce") * pd.to_numeric(
                merged[indicator_name],
                errors="coerce",
            )
            added.append(interaction_name)
    return merged.drop(columns=["broad_sector"], errors="ignore"), added


def load_major_events() -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "canonical" / "reference" / "regimes" / "nse_regime_events_major.parquet"
    frame = pd.read_parquet(path)
    for column in ["start_date", "end_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    return frame.sort_values(["start_date", "event_id"], kind="mergesort").reset_index(drop=True)


def select_high_risk_events(events_df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    frame = events_df.copy()
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
    train_end = pd.Timestamp(prior_dates[-1]).normalize()
    train_slice = prior_dates[-int(train_weeks) :] if len(prior_dates) > int(train_weeks) else prior_dates
    train_start = pd.Timestamp(train_slice[0]).normalize()
    return [
        {
            "window_id": 1,
            "train_start": str(train_start.date()),
            "train_end": str(train_end.date()),
            "test_start": str(test_start.date()),
            "test_end": str(test_end.date()),
        }
    ]


def prepare_subset_export(
    *,
    dataset: PlanDataset,
    output_dir: Path,
    selected_features: Sequence[str] | None = None,
    feature_frame: pd.DataFrame | None = None,
    splits_override: Sequence[dict[str, Any]] | None = None,
    ticker_mask: Sequence[str] | None = None,
    date_min: str | None = None,
    date_max: str | None = None,
    manifest_updates: dict[str, Any] | None = None,
) -> Path:
    subset_feature_export(
        source_dir=dataset.export_dir,
        output_dir=output_dir,
        selected_features=selected_features,
        feature_frame=feature_frame,
        splits_override=splits_override,
        ticker_mask=ticker_mask,
        date_min=date_min,
        date_max=date_max,
        manifest_updates=manifest_updates,
    )
    return output_dir


def run_track_a_model(
    *,
    data_dir: Path,
    output_dir: Path,
    profile: str,
    max_splits: int | None,
    model_filter: Sequence[str],
    tree_overrides: dict[str, Any] | None = None,
    resume_from_checkpoint: bool = True,
) -> dict[str, Any]:
    cfg = TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        run_profile=profile,
        max_splits=max_splits,
        model_filter=list(model_filter),
        continue_on_error=False,
        resume_from_checkpoint=resume_from_checkpoint,
        skip_days=set(),
    )
    runner = ConfigurableTrackARunner(cfg, tree_overrides=tree_overrides)
    return runner.run()


def run_track_b_model(
    *,
    data_dir: Path,
    output_dir: Path,
    profile: str,
    max_splits: int | None,
    model_filter: Sequence[str],
    frontier_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = TrackBRunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        run_profile=profile,
        max_splits=max_splits,
        model_filter=list(model_filter),
        continue_on_error=False,
        resume_from_checkpoint=True,
        skip_days=set(),
    )
    runner = ConfigurableTrackBRunner(cfg, frontier_overrides=frontier_overrides)
    return runner.run()


def load_summary_if_exists(output_root: str | Path, exp_id: str, version: str = "v1") -> dict[str, Any] | None:
    path = make_experiment_paths(output_root, exp_id, version).summary_path
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def pick_best_candidate(candidates: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    def key_fn(row: dict[str, Any]) -> tuple[float, float, float]:
        ratio = float(row.get("mean_train_test_ratio", float("inf")))
        ic = float(row.get("mean_test_ic", row.get("mean_ic", float("-inf"))))
        ic_ir = float(row.get("ic_ir", float("-inf")))
        gate = 1.0 if np.isfinite(ratio) and ratio < 2.5 and np.isfinite(ic) and ic > 0.020 else 0.0
        return (gate, ic, -ratio if np.isfinite(ratio) else float("-inf"), ic_ir)

    return sorted(candidates, key=key_fn, reverse=True)[0]


def extract_model_windows(state: dict[str, Any], model_name: str) -> list[dict[str, Any]]:
    payload = dict((state.get("all_model_results") or {}).get(model_name) or {})
    return list(payload.get("windows") or [])


def write_table(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def summarize_model_state(state: dict[str, Any], model_name: str) -> dict[str, Any]:
    summary = dict((state.get("all_summaries") or {}).get(model_name) or {})
    summary["model"] = model_name
    summary["windows_completed"] = int(summary.get("windows_completed") or 0)
    return summary


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_manifest(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}
