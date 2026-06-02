"""EXP-13 through EXP-16: sector-specific and sector-conditional campaigns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec, load_plan_info
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    augment_sector_conditionals,
    json_ready,
    load_summary_if_exists,
    make_experiment_paths,
    pick_best_candidate,
    prepare_subset_export,
    resolve_sector_tickers,
    run_track_a_model,
    summarize_model_state,
    write_json,
    write_narrative,
)


DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
}


def _best_catboost_params(output_root: str | Path, version: str) -> dict[str, Any]:
    params = dict(DEFAULT_CATBOOST_PARAMS)
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        payload = load_summary_if_exists(output_root, exp_id, version)
        best = dict((payload or {}).get("best_candidate") or {})
        values = dict(best.get("params") or {})
        if values:
            params.update(values)
            break
    return params


def _resolved_best_catboost_params(
    output_root: str | Path,
    version: str,
    best_params_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = _best_catboost_params(output_root, version)
    if best_params_override:
        params.update(dict(best_params_override))
    return params


def _run_sector_catboost(
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
    return summarize_model_state(state, "CatBoost")


def run_sector_experiment(
    spec: ExperimentSpec,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str,
    max_splits: int | None,
    version: str = "v1",
    best_params_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    best_params = _resolved_best_catboost_params(output_root, version, best_params_override)

    if spec.exp_id in {"EXP-13", "EXP-14", "EXP-15"}:
        sector_name = str(spec.params.get("sector_name") or "")
        tickers = resolve_sector_tickers(dataset, sector_name)
        export_dir = paths.artifacts_dir / "sector_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            ticker_mask=tickers,
            manifest_updates={"plan_experiment": spec.exp_id, "sector_name": sector_name, "n_tickers": len(tickers)},
        )
        summary = _run_sector_catboost(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "catboost_run",
            profile=profile,
            max_splits=max_splits,
            params=best_params,
        )
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
                "The sector subset is created from the canonical metadata attached to the Kaggle export.",
                "This run inherits the best broad-universe CatBoost settings available from the ratio campaign.",
            ],
        )
        print(json.dumps(json_ready({"exp_id": spec.exp_id, "sector_name": sector_name, "summary": summary}), indent=2))
        return payload

    if spec.exp_id == "EXP-16":
        plan = load_plan_info()
        sectors = list(spec.params.get("sectors") or [])
        feature_frame, added_features = augment_sector_conditionals(
            dataset,
            base_features=plan.sector_conditional_features,
            sectors=sectors,
        )
        export_dir = paths.artifacts_dir / "sector_blend_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            feature_frame=feature_frame,
            manifest_updates={
                "plan_experiment": spec.exp_id,
                "added_feature_count": len(added_features),
                "sector_count": len(sectors),
            },
        )
        summary = _run_sector_catboost(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "catboost_run",
            profile=profile,
            max_splits=max_splits,
            params=best_params,
        )
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
            extra_notes=[
                "The v1 implementation uses explicit sector identity indicators and numeric sector-conditional interactions.",
                "This keeps the model contract compatible with the existing Track A runner while matching the compendium's sector-blend intent.",
            ],
        )
        print(json.dumps(json_ready({"exp_id": spec.exp_id, "added_feature_count": len(added_features)}), indent=2))
        return payload

    raise KeyError(f"unsupported_sector_experiment:{spec.exp_id}")
