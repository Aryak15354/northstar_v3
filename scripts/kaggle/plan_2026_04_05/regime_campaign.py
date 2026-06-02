"""EXP-17 through EXP-19: regime and event-focused campaign runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec, load_plan_info
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    build_event_split,
    compute_ic_series,
    extract_model_windows,
    generate_anchored_weekly_splits,
    json_ready,
    load_major_events,
    load_summary_if_exists,
    make_experiment_paths,
    pick_best_candidate,
    prepare_subset_export,
    run_track_a_model,
    select_high_risk_events,
    summarize_ic_series,
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


def _event_factor_table(dataset: PlanDataset, factors: list[str], events_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events_df.to_dict(orient="records"):
        event_frame = dataset.merged[
            dataset.merged["date"].between(pd.Timestamp(event["start_date"]), pd.Timestamp(event["end_date"]))
        ].copy()
        for factor in factors:
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
    return pd.DataFrame(rows)


def _run_event_catboost(
    *,
    dataset: PlanDataset,
    output_dir: Path,
    profile: str,
    max_splits: int | None,
    params: dict[str, Any],
    event_row: dict[str, Any],
    train_window_weeks: int,
) -> dict[str, Any]:
    split = build_event_split(
        dataset,
        start_date=event_row["start_date"],
        end_date=event_row["end_date"],
        train_weeks=train_window_weeks,
    )
    export_dir = output_dir / "event_export"
    prepare_subset_export(
        dataset=dataset,
        output_dir=export_dir,
        date_min=split[0]["train_start"],
        date_max=split[0]["test_end"],
        splits_override=split,
        manifest_updates={"event_id": event_row["event_id"], "plan_experiment": "EXP-18"},
    )
    state = run_track_a_model(
        data_dir=export_dir,
        output_dir=output_dir / "catboost_run",
        profile=profile,
        max_splits=max_splits,
        model_filter=["catboost"],
        tree_overrides=params,
    )
    summary = summarize_model_state(state, "CatBoost")
    return {
        "event_id": event_row["event_id"],
        "event_name": event_row["event_name"],
        "severity_score_1_10": event_row.get("severity_score_1_10"),
        "model_collapse_risk": event_row.get("model_collapse_risk"),
        "mean_test_ic": summary.get("mean_test_ic"),
        "ic_ir": summary.get("ic_ir"),
        "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
        "windows_completed": summary.get("windows_completed"),
        "train_window_weeks": train_window_weeks,
        "output_dir": str(output_dir),
    }


def _regime_table_from_windows(windows: list[dict[str, Any]], model_name: str) -> pd.DataFrame:
    rows = []
    for row in windows:
        if "error" in row:
            continue
        rows.append(
            {
                "model": model_name,
                "window_id": row.get("window_id"),
                "regime": row.get("regime", "UNKNOWN"),
                "test_ic": row.get("test_ic"),
                "train_test_ratio": row.get("train_test_ratio"),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["model", "regime", "test_ic", "train_test_ratio"])
    frame = pd.DataFrame(rows)
    return (
        frame.groupby(["model", "regime"], as_index=False)
        .agg(mean_test_ic=("test_ic", "mean"), mean_ratio=("train_test_ratio", "mean"), n_windows=("window_id", "count"))
        .sort_values(["regime", "mean_test_ic"], ascending=[True, False], kind="mergesort")
    )


def _router_date_frame(
    dataset: PlanDataset,
    *,
    currency_vix_threshold: float = 25.0,
    currency_inrusd_threshold: float = -0.03,
    macro_bear_drawdown_threshold: float = -0.10,
    macro_bear_drawdown_weeks: int = 8,
) -> pd.DataFrame:
    columns = [
        "date",
        "plan_regime_id",
        "plan_regime_label",
        "vix_india_4w",
        "inrusd_4w_return",
        "nifty_close",
        "nifty_sma_200",
    ]
    available = [column for column in columns if column in dataset.merged.columns]
    frame = dataset.merged[available].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.sort_values("date", kind="mergesort").drop_duplicates("date", keep="last")
    frame["vix_india_4w"] = pd.to_numeric(frame.get("vix_india_4w"), errors="coerce")
    frame["inrusd_4w_return"] = pd.to_numeric(frame.get("inrusd_4w_return"), errors="coerce")
    frame["nifty_close"] = pd.to_numeric(frame.get("nifty_close"), errors="coerce")
    frame["nifty_sma_200"] = pd.to_numeric(frame.get("nifty_sma_200"), errors="coerce")
    frame["rolling_peak_drawdown"] = frame["nifty_close"].rolling(max(1, int(macro_bear_drawdown_weeks)), min_periods=1).max()
    frame["market_drawdown_weeks"] = frame["nifty_close"] / frame["rolling_peak_drawdown"] - 1.0
    frame["rule_currency_crisis"] = frame["vix_india_4w"].gt(float(currency_vix_threshold)) & frame["inrusd_4w_return"].lt(float(currency_inrusd_threshold))
    below_trend = frame["nifty_close"].lt(frame["nifty_sma_200"] * 0.90)
    stress_regimes = frame.get("plan_regime_id", pd.Series("", index=frame.index)).astype("string").isin(["R4", "R8", "R9"])
    drawdown_break = pd.to_numeric(frame["market_drawdown_weeks"], errors="coerce").le(float(macro_bear_drawdown_threshold))
    frame["rule_macro_bear"] = (~frame["rule_currency_crisis"]) & (stress_regimes | drawdown_break | below_trend)
    frame["router_bucket"] = np.select(
        [frame["rule_currency_crisis"], frame["rule_macro_bear"]],
        ["currency_crisis", "macro_bear"],
        default="non_crisis",
    )
    return frame


def _router_bucket_for_window(router_frame: pd.DataFrame, test_start: Any, test_end: Any) -> str:
    start = pd.Timestamp(test_start)
    end = pd.Timestamp(test_end)
    window = router_frame.loc[router_frame["date"].between(start, end)].copy()
    if window.empty:
        return "unknown"
    counts = window["router_bucket"].astype("string").value_counts()
    return str(counts.index[0]) if not counts.empty else "unknown"


def _window_metric_summary(windows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in windows if "error" not in row and pd.notna(row.get("test_ic"))]
    if not rows:
        return {
            "windows_completed": 0,
            "mean_test_ic": float("nan"),
            "ic_ir": float("nan"),
            "mean_ratio": float("nan"),
        }
    ic = pd.to_numeric(pd.Series([row.get("test_ic") for row in rows]), errors="coerce").dropna()
    ratio = pd.to_numeric(pd.Series([row.get("train_test_ratio") for row in rows]), errors="coerce").dropna()
    mean_ic = float(ic.mean()) if not ic.empty else float("nan")
    std_ic = float(ic.std(ddof=1)) if len(ic) > 1 else float("nan")
    return {
        "windows_completed": int(len(rows)),
        "mean_test_ic": mean_ic,
        "ic_ir": mean_ic / std_ic if np.isfinite(std_ic) and std_ic > 0 else float("nan"),
        "mean_ratio": float(ratio.mean()) if not ratio.empty else float("nan"),
    }


def run_regime_experiment(
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
    events_df = load_major_events()

    if spec.exp_id == "EXP-17":
        plan = load_plan_info()
        table = _event_factor_table(dataset, list(plan.anchor_factors), events_df)
        heatmap = table.pivot(index="event_id", columns="factor", values="mean_ic").reset_index()
        write_table(paths.experiment_root / "factor_event_heatmap.csv", table)
        write_table(paths.experiment_root / "factor_event_heatmap.parquet", table)
        survival_threshold = float(spec.params.get("survival_min_ic") or 0.020)
        survival_min_windows = int(spec.params.get("survival_min_windows") or 15)
        breakout_threshold = float(spec.params.get("breakout_min_ic") or 0.040)
        breakout_min_windows = int(spec.params.get("breakout_min_windows") or 18)
        factor_survival = []
        if not table.empty:
            scored = table.copy()
            scored["survival_hit"] = pd.to_numeric(scored["mean_ic"], errors="coerce").gt(survival_threshold)
            scored["breakout_hit"] = pd.to_numeric(scored["mean_ic"], errors="coerce").gt(breakout_threshold)
            factor_survival = (
                scored.groupby("factor", as_index=False)
                .agg(
                    windows_over_survival=("survival_hit", "sum"),
                    windows_over_breakout=("breakout_hit", "sum"),
                )
                .sort_values("factor", kind="mergesort")
                .to_dict(orient="records")
            )
        surviving_factors = [
            row["factor"]
            for row in factor_survival
            if int(row["windows_over_survival"]) >= survival_min_windows
        ]
        breakout_factors = [
            row["factor"]
            for row in factor_survival
            if int(row["windows_over_breakout"]) >= breakout_min_windows
        ]
        blind_spots = (
            table.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort")
            .head(10)
            .to_dict(orient="records")
        )
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "event_count": int(events_df["event_id"].nunique()),
            "factor_count": int(table["factor"].nunique()) if not table.empty else 0,
            "survival_threshold": survival_threshold,
            "survival_min_windows": survival_min_windows,
            "surviving_factors": surviving_factors,
            "breakout_threshold": breakout_threshold,
            "breakout_min_windows": breakout_min_windows,
            "breakout_factors": breakout_factors,
            "factor_survival_table": factor_survival,
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
                "surviving_factors": surviving_factors,
                "breakout_factors": breakout_factors,
                "weakest_factor_event_cells": len(blind_spots),
            },
            extra_notes=["The v1 heat map uses the canonical 22-event major-regime table under data/canonical/reference/regimes/."],
        )
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    if spec.exp_id == "EXP-18":
        params = _resolved_best_catboost_params(output_root, version, best_params_override)
        baseline = load_summary_if_exists(output_root, "EXP-12", version) or load_summary_if_exists(output_root, "EXP-11", version) or {}
        baseline_ic = float(((baseline.get("best_candidate") or {}).get("mean_test_ic")) or np.nan)
        risky = select_high_risk_events(events_df, top_n=int(spec.params.get("top_n_high_risk_events") or 5))
        rows = []
        for event_row in risky.to_dict(orient="records"):
            rows.append(
                _run_event_catboost(
                    dataset=dataset,
                    output_dir=paths.artifacts_dir / str(event_row["event_id"]).lower(),
                    profile=profile,
                    max_splits=max_splits,
                    params=params,
                    event_row=event_row,
                    train_window_weeks=int(spec.params.get("train_window_weeks") or 104),
                )
            )
        table = pd.DataFrame(rows)
        if not table.empty and np.isfinite(baseline_ic):
            table["collapse_vs_baseline"] = pd.to_numeric(table["mean_test_ic"], errors="coerce") / baseline_ic
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
            "baseline_mean_test_ic": baseline_ic,
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
                "baseline_mean_test_ic": baseline_ic,
                "worst_event_mean_test_ic": worst[0]["mean_test_ic"] if worst else None,
            },
            extra_notes=["Each event run creates a single chronological train/test split ending exactly before the event starts."],
        )
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    if spec.exp_id == "EXP-19":
        params = _resolved_best_catboost_params(output_root, version, best_params_override)
        currency_vix_threshold = float(spec.params.get("currency_crisis_vix_threshold") or 25.0)
        currency_inrusd_threshold = float(spec.params.get("currency_crisis_inrusd_4w_threshold") or -0.03)
        macro_bear_drawdown_threshold = float(spec.params.get("macro_bear_drawdown_threshold") or -0.10)
        macro_bear_drawdown_weeks = int(spec.params.get("macro_bear_drawdown_weeks") or 8)
        universal_state = run_track_a_model(
            data_dir=dataset.export_dir,
            output_dir=paths.artifacts_dir / "universal_catboost",
            profile=profile,
            max_splits=max_splits,
            model_filter=["catboost"],
            tree_overrides=params,
        )
        universal_windows = extract_model_windows(universal_state, "CatBoost")
        router_frame = _router_date_frame(
            dataset,
            currency_vix_threshold=currency_vix_threshold,
            currency_inrusd_threshold=currency_inrusd_threshold,
            macro_bear_drawdown_threshold=macro_bear_drawdown_threshold,
            macro_bear_drawdown_weeks=macro_bear_drawdown_weeks,
        )
        universal_rows: list[dict[str, Any]] = []
        for row in universal_windows:
            if "error" in row:
                continue
            universal_rows.append(
                {
                    "variant": "universal_catboost",
                    "router_bucket": _router_bucket_for_window(router_frame, row.get("test_start"), row.get("test_end")),
                    "window_id": int(row.get("window_id", 0) or 0),
                    "test_ic": row.get("test_ic"),
                    "train_test_ratio": row.get("train_test_ratio"),
                    "regime": row.get("regime", "unknown"),
                }
            )

        specialized_rows: list[dict[str, Any]] = []
        bucket_records: list[dict[str, Any]] = []
        bucket_train_weeks = int(spec.params.get("bucket_train_weeks") or 52)
        bucket_test_weeks = int(spec.params.get("bucket_test_weeks") or 13)
        bucket_step_weeks = int(spec.params.get("bucket_step_weeks") or 13)
        all_features = [column for column in dataset.features.columns if column not in {"date", "ticker", "target_weekly_return"}]
        for bucket_name in ["non_crisis", "macro_bear", "currency_crisis"]:
            bucket_dates = router_frame.loc[router_frame["router_bucket"] == bucket_name, "date"].dropna().sort_values().tolist()
            if len(bucket_dates) < bucket_train_weeks + bucket_test_weeks:
                bucket_records.append(
                    {
                        "router_bucket": bucket_name,
                        "variant": "bucket_catboost",
                        "status": "SKIPPED",
                        "date_count": int(len(bucket_dates)),
                    }
                )
                continue
            splits = generate_anchored_weekly_splits(
                bucket_dates,
                anchor_start=str(pd.Timestamp(bucket_dates[0]).date()),
                train_weeks=bucket_train_weeks,
                test_weeks=bucket_test_weeks,
                step_weeks=bucket_step_weeks,
                target_windows=20,
            )
            bucket_export = paths.artifacts_dir / f"{bucket_name}_export"
            prepare_subset_export(
                dataset=dataset,
                output_dir=bucket_export,
                feature_frame=dataset.features[dataset.features["date"].isin(bucket_dates)].copy(),
                regime_frame=dataset.regimes[dataset.regimes["date"].isin(bucket_dates)].copy(),
                splits_override=splits,
                manifest_updates={"plan_experiment": spec.exp_id, "router_bucket": bucket_name},
            )
            bucket_state = run_track_a_model(
                data_dir=bucket_export,
                output_dir=paths.artifacts_dir / f"{bucket_name}_catboost",
                profile=profile,
                max_splits=max_splits,
                model_filter=["catboost"],
                tree_overrides=params,
            )
            bucket_windows = extract_model_windows(bucket_state, "CatBoost")
            bucket_summary = _window_metric_summary(bucket_windows)
            bucket_summary.update(
                {
                    "router_bucket": bucket_name,
                    "variant": "bucket_catboost",
                    "status": "RUN",
                    "date_count": int(len(bucket_dates)),
                }
            )
            bucket_records.append(bucket_summary)
            for row in bucket_windows:
                if "error" in row:
                    continue
                specialized_rows.append(
                    {
                        "variant": "bucket_catboost",
                        "router_bucket": bucket_name,
                        "window_id": int(row.get("window_id", 0) or 0),
                        "test_ic": row.get("test_ic"),
                        "train_test_ratio": row.get("train_test_ratio"),
                        "regime": row.get("regime", "unknown"),
                    }
                )

        universal_table = pd.DataFrame(universal_rows)
        if not universal_table.empty:
            universal_bucket_table = (
                universal_table.groupby("router_bucket", as_index=False)
                .agg(
                    universal_mean_test_ic=("test_ic", "mean"),
                    universal_mean_ratio=("train_test_ratio", "mean"),
                    universal_windows=("window_id", "count"),
                )
                .sort_values("router_bucket", kind="mergesort")
            )
        else:
            universal_bucket_table = pd.DataFrame(columns=["router_bucket", "universal_mean_test_ic", "universal_mean_ratio", "universal_windows"])

        routing = pd.DataFrame(bucket_records).merge(universal_bucket_table, on="router_bucket", how="left", sort=False)
        if not routing.empty:
            routing["ic_improvement_vs_universal"] = (
                pd.to_numeric(routing.get("mean_test_ic"), errors="coerce")
                - pd.to_numeric(routing.get("universal_mean_test_ic"), errors="coerce")
            )
            routing["ratio_improvement_vs_universal"] = (
                pd.to_numeric(routing.get("universal_mean_ratio"), errors="coerce")
                - pd.to_numeric(routing.get("mean_ratio"), errors="coerce")
            )
        routed_summary = _window_metric_summary(specialized_rows)
        universal_summary = _window_metric_summary(universal_rows)
        write_table(paths.experiment_root / "routing_table.csv", routing)
        write_table(paths.experiment_root / "routing_windows.csv", pd.DataFrame([*universal_rows, *specialized_rows]))
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "candidate_models": ["universal_catboost", "non_crisis_catboost", "macro_bear_catboost", "currency_crisis_catboost"],
            "router_rules": {
                "currency_crisis": f"vix_india_4w > {currency_vix_threshold} and inrusd_4w_return < {currency_inrusd_threshold}",
                "macro_bear": f"8-week market drawdown <= {macro_bear_drawdown_threshold} or plan_regime_id in {{R4,R8,R9}} or nifty_close < 0.9 * nifty_sma_200",
                "non_crisis": "otherwise",
            },
            "routed_mean_ic": routed_summary["mean_test_ic"],
            "routed_ic_ir": routed_summary["ic_ir"],
            "universal_mean_ic": universal_summary["mean_test_ic"],
            "universal_ic_ir": universal_summary["ic_ir"],
            "ic_ir_improvement_vs_universal": float(routed_summary["ic_ir"]) - float(universal_summary["ic_ir"]),
            "inference_center_outputs_required": bool(spec.params.get("inference_center_outputs", True)),
            "routing_rows": routing.to_dict(orient="records"),
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "candidate_models": payload["candidate_models"],
                "router_bucket_count": int(routing["router_bucket"].nunique()) if not routing.empty and "router_bucket" in routing.columns else 0,
                "routed_mean_ic": payload["routed_mean_ic"],
                "universal_mean_ic": payload["universal_mean_ic"],
                "ic_ir_improvement_vs_universal": payload["ic_ir_improvement_vs_universal"],
            },
            extra_notes=[
                "This run now matches the compendium intent: separate CatBoost models are trained for non-crisis, macro-bear, and currency-crisis buckets.",
                "Inference-time cross-sectional centering remains an explicit deployment requirement and is recorded in the summary so the old routing bug is not forgotten.",
            ],
        )
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    raise KeyError(f"unsupported_regime_experiment:{spec.exp_id}")
