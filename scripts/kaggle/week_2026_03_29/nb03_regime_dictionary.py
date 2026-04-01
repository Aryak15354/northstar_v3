#!/usr/bin/env python3
"""NB-03: build the regime-conditional feature dictionary for the weekly sprint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    PLAN_REGIME_LABELS,
    json_ready,
    load_export_artifacts,
    make_run_dir,
    read_json,
    resolve_export_dir,
    select_feature_columns,
    write_json,
)


PLAN_TEMPLATE = {
    "R1": {
        "primary": ["eps_sue_decay", "eps_revision_accel", "earnings_quality_ratio", "agreement_score"],
        "secondary": ["mom_20d_vol_adj", "sector_quality_composite", "roe_qoq_change", "macro_linkage_score"],
        "gate": ["accruals_ratio", "credit_stress_flag"],
    },
    "R2": {
        "primary": ["eps_sue_decay", "eps_revision_accel", "rev_sue_decay"],
        "secondary": ["mom_20d_vol_adj", "agreement_score", "macro_linkage_score"],
        "gate": ["momentum_raw", "ret_20d_raw"],
    },
    "R3": {
        "primary": ["accruals_ratio", "earnings_quality_ratio", "eps_sue_decay"],
        "secondary": ["credit_stress_flag", "pledge_short_signal", "bulk_distribution_breadth"],
        "gate": ["eps_revision_accel", "mom_20d_vol_adj"],
    },
    "R4": {
        "primary": ["earnings_quality_ratio", "accruals_ratio", "credit_stress_flag"],
        "secondary": ["dxy_fii_proxy", "promoter_pledge_change", "macro_linkage_score"],
        "gate": ["mom_20d_vol_adj", "eps_revision_accel", "rev_sue_decay"],
    },
    "R5": {
        "primary": ["eps_sue_decay", "rev_sue_decay", "agreement_score"],
        "secondary": ["macro_linkage_score", "val_discount_to_fair_pct", "sector_quality_composite"],
        "gate": ["accruals_ratio"],
    },
    "R6": {
        "primary": ["earnings_quality_ratio", "eps_sue_decay", "agreement_score"],
        "secondary": ["sector_quality_composite", "macro_linkage_score"],
        "gate": ["mom_20d_vol_adj", "eps_revision_accel"],
    },
    "R7": {
        "primary": ["eps_sue_decay", "earnings_quality_ratio", "inr_revenue_factor"],
        "secondary": ["dxy_fii_proxy", "fx_sensitivity_score", "rate_sensitivity_score"],
        "gate": ["rate_sensitive_raw", "mom_20d_vol_adj"],
    },
    "R8": {
        "primary": ["earnings_quality_ratio", "accruals_ratio", "macro_linkage_score"],
        "secondary": ["sector_quality_composite", "gold_consumption_drag"],
        "gate": ["political_narrative_raw"],
    },
    "R9": {
        "primary": ["earnings_quality_ratio", "macro_linkage_score", "inr_revenue_factor"],
        "secondary": ["dxy_fii_proxy", "oil_sector_impact", "copper_activity_signal"],
        "gate": ["india_domestic_raw", "policy_beta"],
    },
}

FEATURE_ALIASES = {
    "eps_sue_decay": ["eps_sue_decay", "eps_sue"],
    "eps_revision_accel": ["eps_revision_accel", "combined_revision_score_cs_z", "combined_revision_score"],
    "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank", "earnings_quality_ratio"],
    "agreement_score": ["agreement_score_cs_z", "agreement_score_cs_rank", "agreement_score"],
    "mom_20d_vol_adj": ["mom_20d_vol_adj_cs_rank", "mom_20d_vol_adj_cs_z", "mom_20d_vol_adj"],
    "sector_quality_composite": ["sector_quality_composite_cs_rank", "sector_quality_composite_cs_z", "sector_quality_composite"],
    "roe_qoq_change": ["roe_qoq_change"],
    "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank", "accruals_ratio"],
    "credit_stress_flag": ["rating_numeric_cs_z", "val_debt_safety_score_zscore", "posterior_variance"],
    "pledge_short_signal": ["pledge_short_signal", "promoter_pledge_change_90d"],
    "bulk_distribution_breadth": ["bulk_distribution_breadth", "bulk_net_institutional_21d_cs_rank"],
    "rev_sue_decay": ["rev_sue_decay", "rev_sue"],
    "promoter_pledge_change": ["promoter_pledge_change_90d", "pledge_short_signal"],
    "val_discount_to_fair_pct": ["val_discount_to_fair_pct_zscore", "val_discount_to_fair_pct"],
    "inr_revenue_factor": ["inr_revenue_factor"],
    "dxy_fii_proxy": ["dxy_fii_proxy"],
    "fx_sensitivity_score": ["fx_sensitivity_score"],
    "rate_sensitivity_score": ["rate_sensitivity_score"],
    "gold_consumption_drag": ["gold_consumption_drag"],
    "oil_sector_impact": ["oil_sector_impact"],
    "copper_activity_signal": ["copper_activity_signal"],
    "macro_linkage_score": ["macro_linkage_score"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-03 regime feature dictionary.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--nb00-report", type=Path, default=None)
    parser.add_argument("--nb05-results", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _resolve_alias(feature_cols: list[str], key: str) -> str | None:
    for candidate in FEATURE_ALIASES.get(key, [key]):
        if candidate in feature_cols:
            return candidate
    return None


def _date_level_ic(frame: pd.DataFrame, feature: str) -> dict[str, float]:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        local = group[[feature, "target_weekly_return"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 8:
            continue
        corr = local[feature].corr(local["target_weekly_return"], method="spearman")
        if pd.notna(corr):
            values.append(float(corr))
    if not values:
        return {"mean_ic": float("nan"), "ic_ir": float("nan"), "n_dates": 0.0}
    mean_ic = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if len(values) > 1 else float("nan")
    return {
        "mean_ic": mean_ic,
        "ic_ir": mean_ic / std if np.isfinite(std) and std > 0 else float("nan"),
        "n_dates": float(len(values)),
    }


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb03_regime_dictionary")
    output_dir.mkdir(parents=True, exist_ok=True)

    features_df, _, regimes_df, _ = load_export_artifacts(export_artifacts.export_dir)
    feature_cols = select_feature_columns(features_df)
    report_path = args.nb00_report or (export_artifacts.export_dir / "feature_health_report.json")
    feature_report = read_json(report_path) if report_path.exists() else {}
    tier_lists = dict(feature_report.get("tier_lists") or {})
    eligible = list(
        dict.fromkeys(
            [
                *(tier_lists.get("TIER_1") or []),
                *(tier_lists.get("TIER_2") or []),
                *(tier_lists.get("TIER_3") or []),
            ]
        )
    )
    eligible = [feature for feature in eligible if feature in feature_cols] or feature_cols

    nb05_path = args.nb05_results or (export_artifacts.export_dir / "cross_asset_results.json")
    nb05_payload = read_json(nb05_path) if nb05_path.exists() else {}
    promoted_cross_asset = list(nb05_payload.get("promoted_signals") or [])

    merged = features_df.merge(
        regimes_df[["date", "plan_regime_id", "plan_regime_label"]],
        on="date",
        how="left",
        sort=False,
    )
    regime_ic_rows: list[dict[str, Any]] = []
    regime_dict: dict[str, Any] = {}

    for regime_id, regime_label in PLAN_REGIME_LABELS.items():
        subset = merged[merged["plan_regime_id"] == regime_id].copy()
        empirical_rows: list[dict[str, Any]] = []
        for feature in eligible:
            stats = _date_level_ic(subset, feature)
            empirical_rows.append({"feature": feature, **stats})
        empirical = pd.DataFrame(empirical_rows).sort_values("mean_ic", ascending=False)
        empirical["abs_mean_ic"] = empirical["mean_ic"].abs()
        empirical = empirical.sort_values(["abs_mean_ic", "mean_ic"], ascending=[False, False]).reset_index(drop=True)
        regime_ic_rows.extend([{"regime_id": regime_id, "regime_label": regime_label, **row} for row in empirical.to_dict("records")])

        template = PLAN_TEMPLATE.get(regime_id, {"primary": [], "secondary": [], "gate": []})
        manual_primary = [_resolve_alias(feature_cols, name) for name in template["primary"]]
        manual_secondary = [_resolve_alias(feature_cols, name) for name in template["secondary"]]
        manual_gate = [_resolve_alias(feature_cols, name) for name in template["gate"]]
        manual_primary = [item for item in manual_primary if item]
        manual_secondary = [item for item in manual_secondary if item]
        manual_gate = [item for item in manual_gate if item]

        empirical_top = empirical.loc[empirical["mean_ic"] > 0.0, "feature"].astype(str).head(10).tolist()
        empirical_bottom = empirical.loc[empirical["mean_ic"] < 0.0, "feature"].astype(str).head(10).tolist()

        extra_cross_asset = [
            signal
            for signal in promoted_cross_asset
            if (regime_id in {"R4", "R7", "R9"} and any(token in signal for token in ["inr", "dxy", "oil", "copper", "gold"]))
            or (regime_id in {"R2", "R5"} and any(token in signal for token in ["oil", "copper"]))
        ]

        selected_primary = list(dict.fromkeys(manual_primary + empirical_top[:4]))
        selected_secondary = list(dict.fromkeys(manual_secondary + empirical_top[4:10] + extra_cross_asset))
        gated = list(dict.fromkeys(manual_gate + empirical_bottom))

        regime_dict[regime_id] = {
            "label": regime_label,
            "selected_primary": selected_primary,
            "selected_secondary": selected_secondary,
            "gated_features": gated,
            "manual_template": template,
            "empirical_top": empirical_top[:12],
            "empirical_bottom": empirical_bottom[:12],
            "cross_asset_promoted": extra_cross_asset,
        }

    regime_ic_table = pd.DataFrame(regime_ic_rows)
    if not regime_ic_table.empty:
        regime_ic_table.to_parquet(output_dir / "regime_feature_ic_table.parquet", index=False)
    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "eligible_feature_count": len(eligible),
        "regimes": regime_dict,
        "promoted_cross_asset": promoted_cross_asset,
    }
    write_json(output_dir / "regime_feature_dict.json", payload)
    print(json_ready({"regimes": {k: {"primary": v["selected_primary"][:4], "secondary": v["selected_secondary"][:4]} for k, v in regime_dict.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
