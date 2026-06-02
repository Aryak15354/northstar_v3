"""EXP-26 and EXP-27: formal verification battery runners."""

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
    make_experiment_paths,
    resolve_feature,
    run_five_test_battery,
    summarize_ic_series,
    write_json,
    write_narrative,
    write_table,
)
from scripts.kaggle.week_2026_03_29.common import derive_size_rank


COMPENDIUM_DOC_FACTOR_ALIASES: dict[str, list[str]] = {
    "eps_sue_decay": ["eps_sue_decay_cs_z", "eps_sue_decay_cs_rank"],
    "eps_revision_accel": ["combined_revision_score_cs_z"],
    "rev_sue_decay": ["rev_sue_decay_cs_z", "rev_sue_decay_cs_rank"],
    "agreement_score": ["agreement_score_cs_z", "agreement_score_cs_rank"],
    "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"],
    "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank"],
}


def _resolve_factor(columns: list[str], factor_label: str, aliases: dict[str, list[str]]) -> str | None:
    candidates = [str(factor_label), *[str(value) for value in list(aliases.get(factor_label) or [])]]
    return resolve_feature(columns, candidates)


def _window_summary_from_frame(frame: pd.DataFrame, feature: str) -> dict[str, Any]:
    return summarize_ic_series(compute_ic_series(frame, feature))


def _bucket_summary_rows(
    frame: pd.DataFrame,
    *,
    feature: str,
    label_col: str,
    label_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    work = frame.copy()
    work[label_col] = work[label_col].astype("string").fillna("unknown")
    grouped = work.groupby(label_col, sort=False)
    for label, group in grouped:
        summary = _window_summary_from_frame(group, feature)
        rows.append({"segment": str(label), **summary})
    if label_order:
        order = {value: idx for idx, value in enumerate(label_order)}
        rows.sort(key=lambda row: order.get(str(row["segment"]), len(order)))
    return rows


def _tier_label(row: pd.Series) -> str:
    if bool(row.get("all_pass")):
        return "Tier 1"
    if bool(row.get("T1")) and bool(row.get("T2")) and not bool(row.get("T3")) and bool(row.get("T4")) and bool(row.get("T5")):
        return "Tier 2"
    return "Review / Reject"


def run_verification_experiment(
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

    if spec.exp_id == "EXP-26":
        plan = load_plan_info()
        requested_factors = list(spec.params.get("anchor_factors") or COMPENDIUM_DOC_FACTOR_ALIASES.keys() or plan.anchor_factors)
        aliases = {
            str(key): [str(value) for value in list(values or [])]
            for key, values in dict(spec.params.get("factor_aliases") or COMPENDIUM_DOC_FACTOR_ALIASES).items()
        }
        rows = []
        missing_factors: list[str] = []
        for factor in requested_factors:
            resolved = _resolve_factor(list(dataset.merged.columns), str(factor), aliases)
            if resolved is None:
                missing_factors.append(str(factor))
                continue
            narrative = (
                f"{factor} is treated as an anchor factor in the compendium and must survive the full five-test battery "
                "before it remains in the production research shortlist."
            )
            battery = run_five_test_battery(dataset.merged, resolved, narrative=narrative)
            rows.append(
                {
                    "factor": factor,
                    "resolved_feature": resolved,
                    "all_pass": battery["all_pass"],
                    "mean_ic": battery["mean_ic"],
                    "ic_ir": battery["ic_ir"],
                    "ic_tstat": battery["ic_tstat"],
                    "sign_stability": battery["sign_stability"],
                    "decay_ratio": battery["decay_ratio"],
                    "market_cap_spearman_abs": battery["market_cap_spearman_abs"],
                    "T1": battery["tests"]["T1"],
                    "T2": battery["tests"]["T2"],
                    "T3": battery["tests"]["T3"],
                    "T4": battery["tests"]["T4"],
                    "T5": battery["tests"]["T5"],
                }
            )
        table = pd.DataFrame(rows).sort_values(["all_pass", "mean_ic"], ascending=[False, False], kind="mergesort")
        write_table(paths.experiment_root / "five_test_battery.csv", table)
        pre_period = list(spec.params.get("ind_as_pre_period") or [2015, 2017])
        post_period = list(spec.params.get("ind_as_post_period") or [2018, 2025])
        ind_as_available = bool(pd.to_datetime(dataset.merged["date"], errors="coerce").min() < pd.Timestamp(f"{int(pre_period[1])}-12-31"))
        discontinuity_rows: list[dict[str, Any]] = []
        if ind_as_available:
            pre_start = pd.Timestamp(f"{int(pre_period[0])}-01-01")
            pre_end = pd.Timestamp(f"{int(pre_period[1])}-12-31")
            post_start = pd.Timestamp(f"{int(post_period[0])}-01-01")
            post_end = pd.Timestamp(f"{int(post_period[1])}-12-31")
            for factor in requested_factors:
                resolved = _resolve_factor(list(dataset.merged.columns), str(factor), aliases)
                if resolved is None:
                    continue
                pre_summary = summarize_ic_series(compute_ic_series(dataset.merged[dataset.merged["date"].between(pre_start, pre_end)], resolved))
                post_summary = summarize_ic_series(compute_ic_series(dataset.merged[dataset.merged["date"].between(post_start, post_end)], resolved))
                discontinuity_rows.append(
                    {
                        "factor": str(factor),
                        "resolved_feature": resolved,
                        "pre_ind_as_mean_ic": pre_summary["mean_ic"],
                        "post_ind_as_mean_ic": post_summary["mean_ic"],
                        "pre_ind_as_ic_ir": pre_summary["ic_ir"],
                        "post_ind_as_ic_ir": post_summary["ic_ir"],
                    }
                )
        discontinuity_table = pd.DataFrame(discontinuity_rows)
        write_table(paths.experiment_root / "ind_as_discontinuity.csv", discontinuity_table)
        tier_rows = []
        if not table.empty:
            tier_table = table.copy()
            tier_table["tier"] = tier_table.apply(_tier_label, axis=1)
            tier_rows = tier_table[["factor", "resolved_feature", "tier", "all_pass", "T1", "T2", "T3", "T4", "T5"]].to_dict(orient="records")
            write_json(paths.experiment_root / "factor_tier_classification.json", {"factors": tier_rows})
        else:
            write_json(paths.experiment_root / "factor_tier_classification.json", {"factors": []})
        downgraded = table.loc[~table["all_pass"], "factor"].astype(str).tolist() if not table.empty else []
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "factor_count": int(len(table)),
            "downgraded_factors": downgraded,
            "missing_anchor_factors": missing_factors,
            "requested_anchor_factors": requested_factors,
            "factor_tiers": tier_rows,
            "ind_as_history_available": ind_as_available,
            "status": "ok" if len(table) and not missing_factors else "partial_dataset_gap" if len(table) else "dataset_gap",
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "factor_count": len(table),
                "downgraded_factors": downgraded,
                "missing_anchor_factors": missing_factors,
            },
            extra_notes=[
                "T3 is implemented exactly as a recent-8 versus prior-8 decay test on weekly IC series.",
                "This section uses the compendium document's six-factor battery and resolves aliases explicitly against the export schema.",
                "Missing factors are recorded as dataset gaps instead of being silently proxied.",
                "The Ind-AS discontinuity table is written separately; on the current 2019+ export it will usually be marked as a historical dataset gap.",
            ],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    if spec.exp_id == "EXP-27":
        aliases = {
            str(key): [str(value) for value in list(values or [])]
            for key, values in dict(spec.params.get("factor_aliases") or COMPENDIUM_DOC_FACTOR_ALIASES).items()
        }
        requested_candidates = list(spec.params.get("feature_candidates") or ["accruals_ratio", "earnings_quality_ratio"])
        feature = None
        resolved_label = None
        for candidate in requested_candidates:
            resolved = _resolve_factor(list(dataset.merged.columns), str(candidate), aliases)
            if resolved is not None:
                feature = resolved
                resolved_label = str(candidate)
                break
        if feature is None:
            fallback = resolve_feature(
                list(dataset.merged.columns),
                ["accruals_ratio_cs_z", "accruals_ratio_cs_rank", "accruals_ratio"],
            )
            payload = {
                "exp_id": spec.exp_id,
                "title": spec.title,
                "status": "dataset_gap",
                "missing_feature_candidates": list(spec.params.get("feature_candidates") or []),
                "proxy_feature": fallback,
            }
            if fallback is not None:
                proxy_summary = summarize_ic_series(compute_ic_series(dataset.merged, fallback))
                payload["proxy_feature_summary"] = proxy_summary
            write_json(paths.summary_path, payload)
            write_narrative(
                paths.narrative_path,
                exp_id=spec.exp_id,
                title=spec.title,
                hypothesis=spec.hypothesis,
                metrics={
                    "status": "dataset_gap",
                    "missing_feature_candidates": list(spec.params.get("feature_candidates") or []),
                    "proxy_feature": fallback,
                },
                extra_notes=[
                    "The current export does not contain the compendium's earnings-quality feature family, so EXP-27 cannot be run exactly as written.",
                    "Any proxy summary is reported only as a supplemental diagnostic, not as a substitute pass/fail result.",
                ],
            )
            print(json.dumps(payload, indent=2, default=str))
            return payload
        narrative = (
            "India earnings quality is expected to retain a positive sign through regimes and over time because accrual discipline, "
            "cash conversion, and accounting quality should matter persistently in the local market."
        )
        overall = run_five_test_battery(dataset.merged, feature, narrative=narrative)
        work = dataset.merged.copy()
        market_cap_series = work["market_cap"] if "market_cap" in work.columns else pd.Series(np.nan, index=work.index)
        market_cap_base = pd.to_numeric(market_cap_series, errors="coerce")
        if market_cap_base.notna().any():
            work["market_cap_proxy"] = market_cap_base
            market_cap_source = "market_cap"
        else:
            work["market_cap_proxy"] = derive_size_rank(work)
            market_cap_source = "size_rank_proxy"
        work["market_cap_quintile"] = (
            pd.to_numeric(work["market_cap_proxy"], errors="coerce")
            .groupby(pd.to_datetime(work["date"], errors="coerce"))
            .transform(
                lambda series: pd.qcut(series.rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
                if series.notna().sum() >= 5
                else pd.Series(index=series.index, dtype="object")
            )
            .astype("string")
        )
        retail_col = "retail_ownership_pct" if "retail_ownership_pct" in work.columns else None
        if retail_col is not None:
            work["retail_ownership_quintile"] = (
                pd.to_numeric(work[retail_col], errors="coerce")
                .groupby(pd.to_datetime(work["date"], errors="coerce"))
                .transform(
                    lambda series: pd.qcut(series.rank(method="first"), 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"], duplicates="drop")
                    if series.notna().sum() >= 5
                    else pd.Series(index=series.index, dtype="object")
                )
                .astype("string")
            )
        regime_groups = {
            str(label): list(values)
            for label, values in dict(spec.params.get("regime_bucket_groups") or {}).items()
        }
        work["regime_bucket"] = "other"
        for label, regime_ids in regime_groups.items():
            mask = work["plan_regime_id"].isin(list(regime_ids))
            work.loc[mask, "regime_bucket"] = label
        work["time_bucket"] = np.where(
            pd.to_datetime(work["date"], errors="coerce") < pd.Timestamp("2017-01-01"),
            "pre_2017",
            "post_2017",
        )
        rows = [{"segment": "overall", **_window_summary_from_frame(work, feature)}]
        rows.extend(
            {"segment": f"market_cap_{row['segment']}", **{key: value for key, value in row.items() if key != "segment"}}
            for row in _bucket_summary_rows(
                work.dropna(subset=["market_cap_quintile"]),
                feature=feature,
                label_col="market_cap_quintile",
                label_order=["Q1", "Q2", "Q3", "Q4", "Q5"],
            )
        )
        if retail_col is not None:
            rows.extend(
                {"segment": f"retail_{row['segment']}", **{key: value for key, value in row.items() if key != "segment"}}
                for row in _bucket_summary_rows(
                    work.dropna(subset=["retail_ownership_quintile"]),
                    feature=feature,
                    label_col="retail_ownership_quintile",
                    label_order=["Q1", "Q2", "Q3", "Q4", "Q5"],
                )
            )
        rows.extend(
            {"segment": f"time_{row['segment']}", **{key: value for key, value in row.items() if key != "segment"}}
            for row in _bucket_summary_rows(
                work,
                feature=feature,
                label_col="time_bucket",
                label_order=["pre_2017", "post_2017"],
            )
        )
        rows.extend(
            {"segment": f"regime_{row['segment']}", **{key: value for key, value in row.items() if key != "segment"}}
            for row in _bucket_summary_rows(
                work,
                feature=feature,
                label_col="regime_bucket",
                label_order=["bull_recovery", "stress", "other"],
            )
        )
        table = pd.DataFrame(rows)
        write_table(paths.experiment_root / "earnings_quality_validation.csv", table)
        stress_ic = (
            float(table.loc[table["segment"] == "regime_stress", "mean_ic"].iloc[0])
            if "regime_stress" in table["segment"].tolist()
            else float("nan")
        )
        q1_ic = float(table.loc[table["segment"] == "market_cap_Q1", "mean_ic"].iloc[0]) if "market_cap_Q1" in table["segment"].tolist() else float("nan")
        q5_ic = float(table.loc[table["segment"] == "market_cap_Q5", "mean_ic"].iloc[0]) if "market_cap_Q5" in table["segment"].tolist() else float("nan")
        payload = {
            "exp_id": spec.exp_id,
            "title": spec.title,
            "feature_label": resolved_label,
            "feature": feature,
            "overall_battery": overall,
            "stress_mean_ic": stress_ic,
            "small_cap_proxy_mean_ic": q1_ic,
            "large_cap_proxy_mean_ic": q5_ic,
            "sign_preserved_in_stress": bool(np.isfinite(stress_ic) and stress_ic > 0.0),
            "market_cap_quintile_source": market_cap_source,
            "retail_ownership_available": bool(retail_col is not None),
            "pre_2017_history_available": bool(pd.to_datetime(work["date"], errors="coerce").min() < pd.Timestamp("2017-01-01")),
        }
        write_json(paths.summary_path, payload)
        write_narrative(
            paths.narrative_path,
            exp_id=spec.exp_id,
            title=spec.title,
            hypothesis=spec.hypothesis,
            metrics={
                "feature": feature,
                "all_pass": overall["all_pass"],
                "overall_mean_ic": overall["mean_ic"],
                "stress_mean_ic": stress_ic,
            },
            extra_notes=[
                "The deep validation now reports the compendium's main segment cuts: market-cap buckets, retail-ownership buckets when available, regime buckets, and time buckets.",
                "Retail-ownership and pre-2017 Ind-AS tests are recorded as dataset gaps on the current 2019+ feature export.",
            ],
        )
        print(json.dumps(payload, indent=2, default=str))
        return payload

    raise KeyError(f"unsupported_verification_experiment:{spec.exp_id}")
