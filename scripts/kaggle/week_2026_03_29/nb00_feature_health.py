#!/usr/bin/env python3
"""NB-00: feature health audit and tier classification for the weekly sprint."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    PLAN_BULL_REGIMES,
    PLAN_CRASH_REGIMES,
    compute_window_feature_ic,
    derive_size_rank,
    json_ready,
    load_export_artifacts,
    make_run_dir,
    mean_ic_summary,
    read_json,
    resolve_export_dir,
    safe_spearman,
    select_feature_columns,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-00 feature health checks.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--feature-limit", type=int, default=0, help="Optional feature cap for smoke/debug runs.")
    parser.add_argument("--sample-corr-dates", type=int, default=24)
    return parser.parse_args()


def _regime_ic_by_feature(
    features_df: pd.DataFrame,
    regimes_df: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    merged = features_df.merge(
        regimes_df[["date", "plan_regime_id"]],
        on="date",
        how="left",
        sort=False,
    )
    rows: list[dict[str, Any]] = []
    for feature in feature_cols:
        for bucket_name, bucket_ids in {
            "bull": PLAN_BULL_REGIMES,
            "crash": PLAN_CRASH_REGIMES,
        }.items():
            bucket = merged[merged["plan_regime_id"].isin(bucket_ids)].copy()
            values: list[float] = []
            for _, group in bucket.groupby("date", sort=True):
                local = group[[feature, "target_weekly_return"]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(local) < 8:
                    continue
                corr = safe_spearman(local[feature].to_numpy(dtype=float), local["target_weekly_return"].to_numpy(dtype=float))
                if pd.notna(corr):
                    values.append(float(corr))
            rows.append(
                {
                    "feature": feature,
                    "bucket": bucket_name,
                    "mean_ic": float(np.mean(values)) if values else float("nan"),
                    "n_dates": int(len(values)),
                }
            )
    return pd.DataFrame(rows)


def _mean_size_corr(features_df: pd.DataFrame, metadata_df: pd.DataFrame, feature: str) -> float:
    size_rank = derive_size_rank(metadata_df)
    if size_rank.empty or float(size_rank.notna().mean()) <= 0.0:
        return float("nan")
    size_meta = metadata_df[["date", "ticker"]].copy()
    size_meta["market_cap_rank"] = size_rank
    merged = features_df[["date", "ticker", feature]].merge(
        size_meta,
        on=["date", "ticker"],
        how="inner",
        sort=False,
    )
    corrs: list[float] = []
    for _, group in merged.groupby("date", sort=True):
        local = group[[feature, "market_cap_rank"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 8:
            continue
        corr = safe_spearman(local[feature].to_numpy(dtype=float), local["market_cap_rank"].to_numpy(dtype=float))
        if pd.notna(corr):
            corrs.append(float(corr))
    return float(np.nanmean(corrs)) if corrs else float("nan")


def _pairwise_redundancy(features_df: pd.DataFrame, feature_cols: list[str], sample_corr_dates: int) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(features_df["date"], errors="coerce").dropna().unique().tolist())
    if not dates:
        return pd.DataFrame(columns=["left_feature", "right_feature", "mean_abs_corr"])
    step = max(1, int(math.ceil(len(dates) / max(1, sample_corr_dates))))
    sampled = {pd.Timestamp(value).normalize() for value in dates[::step]}
    corr_accumulator: dict[tuple[str, str], list[float]] = {}
    for _, group in features_df[features_df["date"].isin(sampled)].groupby("date", sort=True):
        local = group[feature_cols].replace([np.inf, -np.inf], np.nan)
        if local.shape[0] < 8:
            continue
        corr = local.corr(method="spearman")
        if corr.empty:
            continue
        for left_index, left_feature in enumerate(feature_cols):
            for right_feature in feature_cols[left_index + 1 :]:
                value = corr.loc[left_feature, right_feature]
                if pd.notna(value):
                    corr_accumulator.setdefault((left_feature, right_feature), []).append(abs(float(value)))
    rows = [
        {
            "left_feature": left_feature,
            "right_feature": right_feature,
            "mean_abs_corr": float(np.mean(values)),
        }
        for (left_feature, right_feature), values in corr_accumulator.items()
        if values
    ]
    return pd.DataFrame(rows).sort_values("mean_abs_corr", ascending=False).reset_index(drop=True)


def _tier_for_row(row: pd.Series) -> str:
    if bool(row["noise_flag"]):
        return "NOISE"
    if (
        abs(float(row["mean_ic"])) > 0.020
        and abs(float(row["ic_tstat"])) > 2.0
        and float(row["sign_stability"]) > 0.60
        and not bool(row["decay_alert"])
        and float(row["coverage"]) > 0.80
    ):
        return "TIER_1"
    if bool(row["regime_dependent_flag"]):
        return "TIER_3"
    if bool(row["experimental_flag"]):
        return "TIER_4"
    return "TIER_2"


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb00_feature_health")
    output_dir.mkdir(parents=True, exist_ok=True)

    features_df, splits, regimes_df, metadata_df = load_export_artifacts(export_artifacts.export_dir)
    feature_cols = select_feature_columns(features_df)
    if args.feature_limit > 0:
        feature_cols = feature_cols[: int(args.feature_limit)]

    window_ic = compute_window_feature_ic(features_df, splits, feature_cols)
    regime_ic = _regime_ic_by_feature(features_df, regimes_df, feature_cols)
    redundancy = _pairwise_redundancy(features_df, feature_cols, int(args.sample_corr_dates))
    redundancy.to_parquet(output_dir / "feature_redundancy_table.parquet", index=False)
    window_ic.to_parquet(output_dir / "feature_window_ic.parquet", index=False)
    regime_ic.to_parquet(output_dir / "feature_regime_ic.parquet", index=False)

    regime_pivot = regime_ic.pivot(index="feature", columns="bucket", values="mean_ic") if not regime_ic.empty else pd.DataFrame()
    mean_ic_lookup = (
        window_ic.groupby("feature", as_index=True)["mean_ic"]
        .apply(lambda series: float(np.nanmean(pd.to_numeric(series, errors="coerce"))))
        .to_dict()
    )
    drop_candidates: dict[str, str] = {}
    for _, row in redundancy[redundancy["mean_abs_corr"] > 0.85].iterrows():
        left = str(row["left_feature"])
        right = str(row["right_feature"])
        left_ic = abs(float(mean_ic_lookup.get(left, 0.0) or 0.0))
        right_ic = abs(float(mean_ic_lookup.get(right, 0.0) or 0.0))
        if left_ic >= right_ic:
            drop_candidates[right] = left
        else:
            drop_candidates[left] = right

    rows: list[dict[str, Any]] = []
    for feature in feature_cols:
        feature_windows = window_ic.loc[window_ic["feature"] == feature, "mean_ic"].astype(float).tolist()
        summary = mean_ic_summary(feature_windows)
        mean_ic = float(summary["mean_ic"])
        mean_sign = math.copysign(1.0, mean_ic) if np.isfinite(mean_ic) and abs(mean_ic) > 1e-12 else 0.0
        sign_stability = float(
            np.mean([math.copysign(1.0, value) == mean_sign for value in feature_windows if np.isfinite(value)])
        ) if feature_windows and mean_sign != 0.0 else float("nan")
        first_half = feature_windows[:8]
        second_half = feature_windows[-8:]
        first_abs = float(np.nanmean(np.abs(first_half))) if first_half else float("nan")
        second_abs = float(np.nanmean(np.abs(second_half))) if second_half else float("nan")
        decay_ratio = second_abs / first_abs if np.isfinite(first_abs) and first_abs > 1e-12 else float("nan")
        coverage = float(pd.to_numeric(features_df[feature], errors="coerce").notna().mean())
        size_corr = _mean_size_corr(features_df, metadata_df, feature)
        bull_ic = float(regime_pivot.loc[feature, "bull"]) if feature in regime_pivot.index and "bull" in regime_pivot.columns else float("nan")
        crash_ic = float(regime_pivot.loc[feature, "crash"]) if feature in regime_pivot.index and "crash" in regime_pivot.columns else float("nan")
        regime_dependent = bool(np.isfinite(bull_ic) and np.isfinite(crash_ic) and abs(bull_ic) > 0.030 and abs(crash_ic) < 0.005)
        noise_flag = bool(
            abs(mean_ic) < 0.010
            or abs(float(summary["ic_tstat"])) < 1.5
            or (np.isfinite(sign_stability) and sign_stability < 0.55)
            or coverage < 0.70
        )
        experimental_flag = feature.startswith(
            (
                "macro_linkage",
                "oil_",
                "steel_",
                "copper_",
                "inr_",
                "dxy_",
                "gold_",
                "fx_",
            )
        )
        row = {
            "feature": feature,
            **summary,
            "sign_stability": sign_stability,
            "decay_ratio_last8_vs_prior8": decay_ratio,
            "decay_alert": bool(np.isfinite(decay_ratio) and decay_ratio < 0.60),
            "coverage": coverage,
            "size_corr_mean": size_corr,
            "size_proxy_flag": bool(np.isfinite(size_corr) and abs(size_corr) > 0.40),
            "bull_ic": bull_ic,
            "crash_ic": crash_ic,
            "regime_dependent_flag": regime_dependent,
            "noise_flag": noise_flag,
            "experimental_flag": experimental_flag,
            "redundant_with": drop_candidates.get(feature),
            "redundant_flag": feature in drop_candidates,
        }
        row["tier"] = _tier_for_row(pd.Series(row))
        rows.append(row)

    health = pd.DataFrame(rows).sort_values(["tier", "mean_ic"], key=lambda series: series.abs() if series.name == "mean_ic" else series, ascending=[True, False]).reset_index(drop=True)
    health.to_parquet(output_dir / "feature_health_table.parquet", index=False)
    health.to_csv(output_dir / "feature_health_table.csv", index=False)

    tier_lists = {
        tier: health.loc[health["tier"] == tier, "feature"].astype(str).tolist()
        for tier in ["TIER_1", "TIER_2", "TIER_3", "TIER_4", "NOISE"]
    }
    screener_registry_path = export_artifacts.export_dir / "screener_metric_unit_registry.json"
    screener_registry = read_json(screener_registry_path) if screener_registry_path.exists() else []
    report = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "summary": {
            "feature_count": int(len(feature_cols)),
            "window_count": int(len(splits)),
            "tier_counts": {tier: len(values) for tier, values in tier_lists.items()},
            "redundant_feature_count": int(health["redundant_flag"].sum()),
            "size_proxy_count": int(health["size_proxy_flag"].sum()),
            "decaying_count": int(health["decay_alert"].sum()),
        },
        "tier_lists": tier_lists,
        "sets": {
            "noise_set": health.loc[health["noise_flag"], "feature"].astype(str).tolist(),
            "unstable_set": health.loc[health["sign_stability"] < 0.55, "feature"].astype(str).tolist(),
            "decaying_set": health.loc[health["decay_alert"], "feature"].astype(str).tolist(),
            "size_proxy_set": health.loc[health["size_proxy_flag"], "feature"].astype(str).tolist(),
            "redundant_set": health.loc[health["redundant_flag"], "feature"].astype(str).tolist(),
            "sparse_set": health.loc[health["coverage"] < 0.70, "feature"].astype(str).tolist(),
            "regime_dependent_set": health.loc[health["regime_dependent_flag"], "feature"].astype(str).tolist(),
        },
        "screener_unit_summary": {
            "metrics_total": len(screener_registry),
            "unit_counts": (
                pd.DataFrame(screener_registry)["unit_kind"].value_counts().to_dict()
                if screener_registry
                else {}
            ),
        },
    }
    write_json(output_dir / "feature_health_report.json", report)
    print(json_ready(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
