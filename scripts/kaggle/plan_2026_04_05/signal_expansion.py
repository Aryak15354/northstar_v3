"""EXP-24 and EXP-25: signal discovery and validation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec, load_plan_info
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    compute_ic_series,
    json_ready,
    load_major_events,
    make_experiment_paths,
    run_five_test_battery,
    summarize_ic_series,
    write_json,
    write_narrative,
    write_table,
)


def _signal_sector_stats(frame: pd.DataFrame, signal: str, target_sectors: list[str]) -> dict[str, Any]:
    if "broad_sector" not in frame.columns or not target_sectors:
        return {"mean_ic": float("nan"), "ic_ir": float("nan"), "n_dates": 0}
    subset = frame[frame["broad_sector"].astype("string").isin(list(target_sectors))].copy()
    summary = summarize_ic_series(compute_ic_series(subset, signal))
    return summary


def _normalize_group_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _ccms_size_bucket(group_size: int) -> str:
    if int(group_size) >= 10:
        return "10_plus"
    if int(group_size) >= 7:
        return "7_to_9"
    if int(group_size) >= 5:
        return "5_to_6"
    if int(group_size) >= 4:
        return "4_only"
    return "2_to_3"


def run_signal_experiment(
    spec: ExperimentSpec,
    *,
    dataset: PlanDataset,
    output_root: str | Path,
    profile: str,
    max_splits: int | None,
    version: str = "v1",
) -> dict[str, Any]:
    del profile, max_splits
    paths = make_experiment_paths(output_root, spec.exp_id, version)
    plan = load_plan_info()

    if spec.exp_id == "EXP-24":
        rows = []
        stress = dataset.merged[dataset.merged["plan_regime_id"].isin(["R4", "R7", "R8", "R9"])].copy()
        for signal in plan.cross_asset_signals:
            if signal not in dataset.merged.columns:
                continue
            overall = summarize_ic_series(compute_ic_series(dataset.merged, signal))
            stress_stats = summarize_ic_series(compute_ic_series(stress, signal))
            sector_stats = _signal_sector_stats(
                dataset.merged,
                signal,
                list((spec.params.get("targeted_sectors") or {}).get(signal) or []),
            )
            rows.append(
                {
                    "signal": signal,
                    "overall_mean_ic": overall["mean_ic"],
                    "overall_ic_ir": overall["ic_ir"],
                    "overall_ic_tstat": overall["ic_tstat"],
                    "stress_mean_ic": stress_stats["mean_ic"],
                    "stress_ic_ir": stress_stats["ic_ir"],
                    "sector_mean_ic": sector_stats["mean_ic"],
                    "sector_ic_ir": sector_stats["ic_ir"],
                    "n_dates": overall["n_dates"],
                }
            )
        table = pd.DataFrame(rows).sort_values(["overall_ic_ir", "overall_mean_ic"], ascending=[False, False], kind="mergesort")
        write_table(paths.experiment_root / "signal_ic_battery.csv", table)
        standalone_ic_gate = float(spec.params.get("standalone_ic_gate") or 0.015)
        promoted = (
            table[
                (pd.to_numeric(table["overall_mean_ic"], errors="coerce").abs() > standalone_ic_gate)
                & (pd.to_numeric(table["overall_ic_ir"], errors="coerce") > 0.30)
            ]["signal"]
            .astype(str)
            .tolist()
            if not table.empty
            else []
        )
        interaction_rows = []
        interaction_map = {
            "stock_x_crude": "crude_4w_return",
            "stock_x_inrusd": "inrusd_4w_return",
        }
        for interaction_signal, raw_signal in interaction_map.items():
            if table.empty:
                continue
            interaction_row = table.loc[table["signal"].astype(str) == interaction_signal]
            raw_row = table.loc[table["signal"].astype(str) == raw_signal]
            if interaction_row.empty or raw_row.empty:
                continue
            interaction_rows.append(
                {
                    "interaction_signal": interaction_signal,
                    "raw_signal": raw_signal,
                    "interaction_mean_ic": float(pd.to_numeric(interaction_row["overall_mean_ic"], errors="coerce").iloc[0]),
                    "raw_mean_ic": float(pd.to_numeric(raw_row["overall_mean_ic"], errors="coerce").iloc[0]),
                    "interaction_outperforms_raw": bool(
                        pd.to_numeric(interaction_row["overall_mean_ic"], errors="coerce").iloc[0]
                        > pd.to_numeric(raw_row["overall_mean_ic"], errors="coerce").iloc[0]
                    ),
                }
            )
        interaction_outperformance = all(row["interaction_outperforms_raw"] for row in interaction_rows) if interaction_rows else False
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "signal_count": int(len(table)),
            "promoted_signals": promoted,
            "interaction_signal_comparison": interaction_rows,
            "interaction_outperformance": interaction_outperformance,
            "standalone_ic_gate": standalone_ic_gate,
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={"signal_count": len(table), "promoted_signals": promoted},
            extra_notes=[
                "This battery uses the exact Friday-aligned cross-asset signals embedded in the verified Kaggle dataset, not proxy rebuilds from raw daily data.",
                "Interaction-vs-raw signal comparisons are written explicitly so the compendium hypothesis can be judged directly instead of inferred from the table.",
            ],
        )
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    if spec.exp_id == "EXP-25":
        frame = dataset.merged.copy()
        frame["conglomerate_group"] = frame.get("conglomerate_group", pd.Series("", index=frame.index)).astype("string")
        frame["broad_sector"] = frame.get("broad_sector", pd.Series("Other", index=frame.index)).astype("string")
        frame["ret_20d"] = pd.to_numeric(frame.get("ret_20d"), errors="coerce")
        weight_col = "market_cap" if "market_cap" in frame.columns else None
        min_group_size = int(spec.params.get("min_group_size") or 2)

        group_counts = frame.groupby(["date", "conglomerate_group"], as_index=False)["ticker"].count().rename(columns={"ticker": "group_size"})
        frame = frame.merge(group_counts, on=["date", "conglomerate_group"], how="left", sort=False)
        frame = frame[frame["group_size"] >= min_group_size].copy()

        if weight_col is not None:
            frame[weight_col] = pd.to_numeric(frame[weight_col], errors="coerce").clip(lower=0.0)
            frame["_ccms_weighted_ret"] = frame["ret_20d"] * frame[weight_col]
            peer_weighted_sum = frame.groupby(["date", "conglomerate_group"], sort=False)["_ccms_weighted_ret"].transform("sum")
            peer_weight_sum = frame.groupby(["date", "conglomerate_group"], sort=False)[weight_col].transform("sum")
            frame["ccms_peer_ret_4w"] = (peer_weighted_sum - frame["_ccms_weighted_ret"]) / (peer_weight_sum - frame[weight_col]).replace(0, np.nan)
            frame = frame.drop(columns=["_ccms_weighted_ret"])
        else:
            peer_sum = frame.groupby(["date", "conglomerate_group"], sort=False)["ret_20d"].transform("sum")
            peer_count = frame.groupby(["date", "conglomerate_group"], sort=False)["ret_20d"].transform("count")
            frame["ccms_peer_ret_4w"] = (peer_sum - frame["ret_20d"]) / (peer_count - 1).replace(0, np.nan)
        sector_mean = frame.groupby(["date", "broad_sector"], sort=False)["ret_20d"].transform("mean")
        frame["ccms_signal"] = frame["ccms_peer_ret_4w"] - sector_mean
        ccms_frame = frame[["date", "ticker", "target_weekly_return", "conglomerate_group", "group_size", "ccms_signal"]].copy()
        ccms_frame.to_parquet(paths.experiment_root / "ccms_feature_frame.parquet", index=False)
        group_sizes = (
            ccms_frame.groupby("conglomerate_group", as_index=False)["ticker"]
            .nunique()
            .rename(columns={"ticker": "member_count"})
        )
        group_sizes["size_bucket"] = group_sizes["member_count"].map(_ccms_size_bucket)
        ccms_frame = ccms_frame.merge(group_sizes, on="conglomerate_group", how="left", sort=False)

        narrative = (
            "CCMS tests whether lagged peer moves inside a business group carry information beyond normal sector momentum. "
            "A positive result would support keeping explicit conglomerate structure in the research stack."
        )
        battery = run_five_test_battery(ccms_frame, "ccms_signal", narrative=narrative)
        size_rows = []
        for size_bucket, bucket_frame in ccms_frame.groupby("size_bucket", sort=False):
            summary = summarize_ic_series(compute_ic_series(bucket_frame, "ccms_signal"))
            size_rows.append(
                {
                    "size_bucket": str(size_bucket),
                    "mean_ic": summary["mean_ic"],
                    "ic_ir": summary["ic_ir"],
                    "n_dates": summary["n_dates"],
                    "group_count": int(bucket_frame["conglomerate_group"].nunique()),
                    "member_count_total": int(bucket_frame["ticker"].nunique()),
                }
            )
        size_table = pd.DataFrame(size_rows).sort_values("size_bucket", kind="mergesort")
        write_table(paths.experiment_root / "ccms_size_dependency.csv", size_table)

        events = load_major_events()
        adani_groups = [
            str(value)
            for value in ccms_frame["conglomerate_group"].dropna().astype(str).unique().tolist()
            if "adani" in _normalize_group_name(value)
        ]
        adani_event = events.loc[events["event_id"].astype(str) == "E017"].copy()
        adani_summary = {"mean_ic": float("nan"), "ic_ir": float("nan"), "n_dates": 0}
        if adani_groups and not adani_event.empty:
            event_row = adani_event.iloc[0]
            adani_frame = ccms_frame[
                ccms_frame["conglomerate_group"].astype("string").isin(adani_groups)
                & ccms_frame["date"].between(pd.Timestamp(event_row["start_date"]), pd.Timestamp(event_row["end_date"]))
            ].copy()
            adani_summary = summarize_ic_series(compute_ic_series(adani_frame, "ccms_signal"))

        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "rows": int(len(ccms_frame)),
            "groups": int(ccms_frame["conglomerate_group"].nunique()),
            "battery": battery,
            "adani_crisis_mean_ic": adani_summary["mean_ic"],
            "adani_crisis_ic_ir": adani_summary["ic_ir"],
            "pass_gates": {
                "overall_ic": spec.params.get("overall_ic_gate"),
                "adani_ic": spec.params.get("adani_ic_gate"),
            },
            "size_dependency_rows": size_rows,
            "peer_weight_mode": "market_cap_weighted" if weight_col is not None else "equal_weight_dataset_gap",
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "groups": payload["groups"],
                "rows": payload["rows"],
                "all_pass": battery["all_pass"],
                "mean_ic": battery["mean_ic"],
                "adani_crisis_mean_ic": adani_summary["mean_ic"],
            },
            extra_notes=[
                "The v1 CCMS signal removes same-sector average 4-week momentum before running the factor tests.",
                "If market_cap is absent from the export, the peer basket falls back to equal weighting and records that as a dataset gap.",
                "This run now also writes a size-dependency table and the Adani crisis check described in the compendium.",
            ],
        )
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    raise KeyError(f"unsupported_signal_experiment:{spec.exp_id}")
