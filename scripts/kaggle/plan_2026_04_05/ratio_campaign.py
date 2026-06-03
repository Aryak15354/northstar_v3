"""EXP-09 through EXP-12: CatBoost ratio and configuration campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    generate_anchored_weekly_splits,
    json_ready,
    load_summary_if_exists,
    make_experiment_paths,
    pick_best_candidate,
    prepare_subset_export,
    run_track_a_model,
    summarize_model_state,
    write_json,
    write_narrative,
    write_table,
)


DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
}


def _best_upstream_params(
    output_root: str | Path,
    version: str,
    manual_upstream_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = dict(DEFAULT_CATBOOST_PARAMS)
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        payload = load_summary_if_exists(output_root, exp_id, version)
        candidate = dict((payload or {}).get("best_candidate") or {})
        candidate_params = dict(candidate.get("params") or {})
        if candidate_params:
            params.update(candidate_params)
            break
    if manual_upstream_params:
        params.update(dict(manual_upstream_params))
    return params


def _run_catboost_candidate(
    *,
    data_dir: Path,
    output_dir: Path,
    profile: str,
    max_splits: int | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    state = run_track_a_model(
        data_dir=data_dir,
        output_dir=output_dir,
        profile=profile,
        max_splits=max_splits,
        model_filter=["catboost"],
        tree_overrides=params,
    )
    summary = summarize_model_state(state, "CatBoost")
    return {
        "params": dict(params),
        "mean_test_ic": summary.get("mean_test_ic"),
        "ic_ir": summary.get("ic_ir"),
        "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
        "mean_hit_rate": summary.get("mean_hit_rate"),
        "windows_completed": summary.get("windows_completed"),
        "output_dir": str(output_dir),
    }


def _candidate_table(candidates: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in candidates:
        merged = dict(row)
        params = dict(merged.pop("params", {}))
        for key, value in params.items():
            merged[f"param_{key}"] = value
        rows.append(merged)
    return pd.DataFrame(rows)


def _write_summary(
    *,
    spec: ExperimentSpec,
    paths,
    candidates: list[dict[str, Any]],
    extra_notes: list[str],
) -> dict[str, Any]:
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
    metrics = {
        "candidate_count": len(candidates),
        "best_mean_test_ic": best.get("mean_test_ic"),
        "best_ic_ir": best.get("ic_ir"),
        "best_mean_train_test_ratio": best.get("mean_train_test_ratio"),
        "best_params": best.get("params"),
    }
    write_narrative(
        paths.narrative_path,
        exp_id=spec.exp_id,
        title=spec.title,
        hypothesis=spec.hypothesis,
        metrics=metrics,
        extra_notes=extra_notes,
    )
    return payload


def run_ratio_experiment(
    spec: ExperimentSpec,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str,
    max_splits: int | None,
    version: str = "v1",
    manual_upstream_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []

    if spec.exp_id == "EXP-09":
        base = dict(DEFAULT_CATBOOST_PARAMS)
        base.update(dict(spec.params.get("base_catboost") or {}))
        for depth in list(spec.params.get("depth_grid") or []):
            for od_wait in list(spec.params.get("early_stopping_rounds") or []):
                params = {**base, "depth": int(depth), "od_wait": int(od_wait)}
                candidate_dir = paths.artifacts_dir / f"depth_{depth}_odwait_{od_wait}"
                candidates.append(
                    _run_catboost_candidate(
                        data_dir=dataset.export_dir,
                        output_dir=candidate_dir,
                        profile=profile,
                        max_splits=max_splits,
                        params=params,
                    )
                )
        notes.append("This campaign is the first ratio gate in the compendium and uses chronological validation inside Track A.")

    elif spec.exp_id == "EXP-10":
        upstream = _best_upstream_params(output_root, version, manual_upstream_params=manual_upstream_params)
        for l2_leaf_reg in list(spec.params.get("l2_leaf_reg_grid") or []):
            params = {**upstream, "l2_leaf_reg": float(l2_leaf_reg)}
            candidate_dir = paths.artifacts_dir / f"l2_{str(l2_leaf_reg).replace('.', '_')}"
            candidates.append(
                _run_catboost_candidate(
                    data_dir=dataset.export_dir,
                    output_dir=candidate_dir,
                    profile=profile,
                    max_splits=max_splits,
                    params=params,
                )
            )
        notes.append("The sweep reuses the best available depth and early-stopping settings from the prior ratio campaign if they already exist.")

    elif spec.exp_id == "EXP-11":
        upstream = _best_upstream_params(output_root, version, manual_upstream_params=manual_upstream_params)
        for boosting_type in list(spec.params.get("boosting_types") or []):
            params = {**upstream, "boosting_type": str(boosting_type)}
            candidate_dir = paths.artifacts_dir / f"boosting_{str(boosting_type).lower()}"
            candidates.append(
                _run_catboost_candidate(
                    data_dir=dataset.export_dir,
                    output_dir=candidate_dir,
                    profile=profile,
                    max_splits=max_splits,
                    params=params,
                )
            )
        notes.append("Only the CatBoost boosting type changes in this comparison; all other parameters inherit from the best upstream ratio configuration.")

    elif spec.exp_id == "EXP-12":
        upstream = _best_upstream_params(output_root, version, manual_upstream_params=manual_upstream_params)
        weekly_dates = pd.to_datetime(dataset.features["date"], errors="coerce").dropna().sort_values().unique().tolist()
        for years in list(spec.params.get("train_window_years") or []):
            train_weeks = int(years) * 52
            splits = generate_anchored_weekly_splits(
                weekly_dates,
                anchor_start="2019-01-01",
                train_weeks=train_weeks,
                test_weeks=int(spec.params.get("test_window_weeks") or 26),
                step_weeks=int(spec.params.get("step_weeks") or 26),
                target_windows=0,
            )
            export_dir = paths.artifacts_dir / f"window_{years}yr_export"
            prepare_subset_export(
                dataset=dataset,
                output_dir=export_dir,
                splits_override=splits,
                manifest_updates={
                    "plan_experiment": spec.exp_id,
                    "train_window_years": int(years),
                    "test_window_weeks": int(spec.params.get("test_window_weeks") or 26),
                },
            )
            params = dict(upstream)
            candidate = _run_catboost_candidate(
                data_dir=export_dir,
                output_dir=paths.artifacts_dir / f"window_{years}yr_results",
                profile=profile,
                max_splits=max_splits,
                params=params,
            )
            candidate["params"] = {**candidate["params"], "train_window_years": int(years)}
            candidate["split_count"] = len(splits)
            candidate["subset_export_dir"] = str(export_dir)
            candidates.append(candidate)
        notes.append("EXP-12 rebuilds the walk-forward windows to use a fixed 6-month test horizon, as specified in the compendium.")

    else:
        raise KeyError(f"unsupported_ratio_experiment:{spec.exp_id}")

    table = _candidate_table(candidates)
    write_table(paths.experiment_root / "candidate_table.csv", table)
    summary = _write_summary(spec=spec, paths=paths, candidates=candidates, extra_notes=notes)
    print(json.dumps(json_ready({"exp_id": spec.exp_id, "best_candidate": summary.get("best_candidate")}), indent=2))
    return summary
