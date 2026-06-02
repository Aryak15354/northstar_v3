"""EXP-20 through EXP-23: model-redemption campaign runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    make_experiment_paths,
    prepare_subset_export,
    run_track_a_model,
    run_track_b_model,
    summarize_model_state,
    top_large_cap_tickers,
    write_json,
    write_narrative,
)


def _resolve_requested_features(columns: list[str], requested: list[str]) -> tuple[list[str], list[str]]:
    resolved: list[str] = []
    missing: list[str] = []
    present = set(map(str, columns))
    for name in requested:
        if str(name) in present:
            resolved.append(str(name))
        else:
            missing.append(str(name))
    return sorted(dict.fromkeys(resolved)), missing


def _macro_feature_candidates(columns: list[str]) -> list[str]:
    keep = []
    for column in columns:
        lower = str(column).lower()
        if lower.startswith(("macro_", "rbi_", "yield_curve", "cpi_", "gst_", "power_", "inrusd_", "crude_", "gold_", "copper_", "steel_", "coal_", "dxy_", "fii_", "vix_", "us_10y_", "commodity_")):
            keep.append(str(column))
    return sorted(dict.fromkeys(keep))


def _sector_rotation_features(columns: list[str]) -> list[str]:
    keep = []
    for column in columns:
        lower = str(column).lower()
        if "sector" in lower or lower.startswith(("mom_", "res_mom_", "price_to_sma20", "vol_z20", "ret_20d", "ret_5d", "nifty_")):
            keep.append(str(column))
    return sorted(dict.fromkeys(keep))


def run_redemption_experiment(
    spec: ExperimentSpec,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str,
    max_splits: int | None,
    version: str = "v1",
) -> dict[str, Any]:
    paths = make_experiment_paths(output_root, spec.exp_id, version)

    if spec.exp_id == "EXP-20":
        top_n = int(spec.params.get("top_n_tickers") or 150)
        tickers = top_large_cap_tickers(dataset, top_n)
        architecture = dict(spec.params.get("architecture") or {})
        export_dir = paths.artifacts_dir / "large_cap_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            ticker_mask=tickers,
            manifest_updates={"plan_experiment": spec.exp_id, "top_n_tickers": top_n},
        )
        state = run_track_a_model(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "lstm_run",
            profile=profile,
            max_splits=max_splits,
            model_filter=[str(spec.params.get("model") or "lstm")],
        )
        summary = summarize_model_state(state, "LSTM")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "top_n_tickers": top_n,
            "subset_tickers": tickers,
            "architecture": architecture,
            "favorable_events": list(spec.params.get("favorable_events") or []),
            "dataset_execution_mode": "weekly_proxy_large_cap_subset",
            "dataset_gaps": [
                "Current export is weekly and cannot recreate the compendium's daily 60-day temporal sequences exactly.",
            ],
            "pass_gates": {
                "ic": spec.params.get("pass_ic_gate"),
                "ratio": spec.params.get("pass_ratio_gate"),
                "hit_rate": spec.params.get("pass_hit_rate_gate"),
            },
            "model_summary": summary,
        }
        write_json(paths.experiment_root / "subset_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "top_n_tickers": top_n,
                "mean_test_ic": summary.get("mean_test_ic"),
                "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
            },
            extra_notes=["The v1 redemption pass restricts LSTM to the top large-cap names by median market-cap rank across the export."],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    if spec.exp_id == "EXP-21":
        requested_observed = [str(value) for value in list(spec.params.get("observed_inputs") or [])]
        requested_future = [str(value) for value in list(spec.params.get("known_future_inputs") or [])]
        exact_requested, missing_requested = _resolve_requested_features(list(dataset.features.columns), requested_observed + requested_future)
        macro_features = sorted(dict.fromkeys([*exact_requested, *_macro_feature_candidates(list(dataset.features.columns))]))
        export_dir = paths.artifacts_dir / "macro_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            selected_features=macro_features,
            manifest_updates={"plan_experiment": spec.exp_id, "macro_feature_count": len(macro_features)},
        )
        frontier_overrides = {}
        state = run_track_b_model(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "tft_run",
            profile=profile,
            max_splits=max_splits,
            model_filter=[str(spec.params.get("model") or "tft")],
            frontier_overrides=frontier_overrides or None,
        )
        summary = summarize_model_state(state, "TFT")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "macro_feature_count": len(macro_features),
            "macro_features": macro_features,
            "requested_observed_inputs": requested_observed,
            "requested_known_future_inputs": requested_future,
            "missing_requested_inputs": missing_requested,
            "output_probabilities": list(spec.params.get("output_probabilities") or []),
            "dataset_execution_mode": "weekly_stock_attached_macro_proxy",
            "dataset_gaps": [
                "The current export is not the compendium's standalone 2010-2025 macro panel.",
                "Known-future covariates are represented only if matching weekly proxy columns exist in the export.",
            ],
            "pass_gates": {
                "incremental_ic": spec.params.get("incremental_ic_gate"),
                "val_loss": spec.params.get("val_loss_gate"),
                "epoch_cap": spec.params.get("convergence_epoch_cap"),
            },
            "model_summary": summary,
        }
        write_json(paths.experiment_root / "macro_embedding_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "macro_feature_count": len(macro_features),
                "mean_test_ic": summary.get("mean_test_ic"),
                "ic_ir": summary.get("ic_ir"),
            },
            extra_notes=[
                "The v1 run uses the TFT notebook stack as a macro distillation engine over the macro and exact cross-asset feature subset.",
                "The output is still evaluated through the existing Track B ranking machinery so we can compare it consistently.",
            ],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    if spec.exp_id == "EXP-22":
        selected = _sector_rotation_features(list(dataset.features.columns))
        export_dir = paths.artifacts_dir / "sector_rotation_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            selected_features=selected,
            manifest_updates={"plan_experiment": spec.exp_id, "feature_count": len(selected)},
        )
        state = run_track_a_model(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "tcn_run",
            profile=profile,
            max_splits=max_splits,
            model_filter=[str(spec.params.get("model") or "tcn")],
        )
        summary = summarize_model_state(state, "TCN")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "feature_count": len(selected),
            "selected_features": selected,
            "architecture": {
                "sector_count": spec.params.get("sector_count"),
                "lookback_weeks": spec.params.get("lookback_weeks"),
                "forecast_horizon_weeks": spec.params.get("forecast_horizon_weeks"),
                "kernel_size": spec.params.get("kernel_size"),
                "layers": spec.params.get("layers"),
                "dilations": list(spec.params.get("dilations") or []),
            },
            "output_feature_name": spec.params.get("output_feature_name"),
            "dataset_execution_mode": "weekly_sector_rotation_proxy",
            "pass_gates": {
                "standalone_ic": spec.params.get("standalone_ic_gate"),
                "incremental_ic": spec.params.get("incremental_ic_gate"),
            },
            "model_summary": summary,
        }
        write_json(paths.experiment_root / "subset_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "feature_count": len(selected),
                "mean_test_ic": summary.get("mean_test_ic"),
                "ic_ir": summary.get("ic_ir"),
            },
            extra_notes=["The TCN subset emphasizes sector-relative momentum and broad sector identity features to match the rotation hypothesis."],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    if spec.exp_id == "EXP-23":
        requested_candidates = [str(value) for value in list(spec.params.get("feature_candidates") or [])]
        candidates, missing_candidates = _resolve_requested_features(list(dataset.features.columns), requested_candidates)
        sector_dummies = [col for col in dataset.features.columns if str(col).startswith("sector_dummy_")]
        intended_channel_count = int(spec.params.get("intended_channel_count") or 45)
        channels = sorted(dict.fromkeys([*candidates, *sector_dummies]))[:intended_channel_count]
        export_dir = paths.artifacts_dir / "itransformer_export"
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            selected_features=channels,
            manifest_updates={"plan_experiment": spec.exp_id, "channel_count": len(channels)},
        )
        state = run_track_b_model(
            data_dir=export_dir,
            output_dir=paths.artifacts_dir / "itransformer_run",
            profile=profile,
            max_splits=max_splits,
            model_filter=[str(spec.params.get("model") or "itransformer")],
        )
        summary = summarize_model_state(state, "iTransformer")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "channel_count": len(channels),
            "channels": channels,
            "requested_channel_candidates": requested_candidates,
            "missing_requested_candidates": missing_candidates,
            "section_header_channel_count": spec.params.get("section_header_channel_count"),
            "intended_channel_count": intended_channel_count,
            "output_feature_name": spec.params.get("output_feature_name"),
            "dataset_execution_mode": "weekly_cross_asset_channel_proxy",
            "pass_gates": {
                "oom_resolved_required": spec.params.get("oom_resolved_required"),
                "derived_signal_ic": spec.params.get("derived_signal_ic_gate"),
            },
            "model_summary": summary,
        }
        write_json(paths.experiment_root / "channel_manifest.json", payload)
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "channel_count": len(channels),
                "mean_test_ic": summary.get("mean_test_ic"),
                "ic_ir": summary.get("ic_ir"),
            },
            extra_notes=["The v1 channel set is constrained to 60 channels to stay aligned with the compendium's cross-asset attention experiment while remaining practical for repeated tuning."],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    raise KeyError(f"unsupported_redemption_experiment:{spec.exp_id}")
