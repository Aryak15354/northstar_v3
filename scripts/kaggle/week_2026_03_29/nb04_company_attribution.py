#!/usr/bin/env python3
"""NB-04: company- and cluster-level factor attribution."""

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
    derive_size_rank,
    json_ready,
    load_export_artifacts,
    make_run_dir,
    resolve_export_dir,
    safe_spearman,
    write_json,
)


FACTOR_CANDIDATES = {
    "eps_sue_decay": ["eps_sue_decay", "eps_sue"],
    "eps_revision_accel": ["eps_revision_accel", "combined_revision_score_cs_z", "combined_revision_score"],
    "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank", "earnings_quality_ratio"],
    "agreement_score": ["agreement_score_cs_z", "agreement_score_cs_rank", "agreement_score"],
    "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank", "accruals_ratio"],
    "sector_quality_composite": ["sector_quality_composite_cs_rank", "sector_quality_composite"],
    "macro_linkage_score": ["macro_linkage_score"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-04 company factor attribution.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _resolve_factor(available: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _ic_by_group(frame: pd.DataFrame, factor_col: str, group_col: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_name, subset in frame.groupby(group_col, dropna=False):
        date_ics: list[float] = []
        n_tickers = int(subset["ticker"].astype(str).nunique())
        if n_tickers < 8:
            continue
        for _, group in subset.groupby("date", sort=True):
            local = group[[factor_col, "target_weekly_return"]].replace([np.inf, -np.inf], np.nan).dropna()
            if len(local) < 6:
                continue
            corr = safe_spearman(local[factor_col].to_numpy(dtype=float), local["target_weekly_return"].to_numpy(dtype=float))
            if pd.notna(corr):
                date_ics.append(float(corr))
        if not date_ics:
            continue
        mean_ic = float(np.mean(date_ics))
        std = float(np.std(date_ics, ddof=1)) if len(date_ics) > 1 else float("nan")
        rows.append(
            {
                "group": str(group_name),
                "factor": factor_col,
                "mean_ic": mean_ic,
                "ic_ir": mean_ic / std if np.isfinite(std) and std > 0 else float("nan"),
                "n_dates": int(len(date_ics)),
                "n_tickers": n_tickers,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb04_company_attribution")
    output_dir.mkdir(parents=True, exist_ok=True)

    features_df, _, _, metadata_df = load_export_artifacts(export_artifacts.export_dir)
    available = list(features_df.columns)
    factors = {
        alias_name: resolved
        for alias_name, candidates in FACTOR_CANDIDATES.items()
        for resolved in [_resolve_factor(available, candidates)]
        if resolved is not None
    }
    merged = features_df.merge(metadata_df, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    merged["market_cap_rank"] = derive_size_rank(merged)
    for factor_col in list(factors.values()):
        if factor_col in merged.columns:
            continue
        left = merged.get(f"{factor_col}_x")
        right = merged.get(f"{factor_col}_y")
        if left is not None or right is not None:
            base = left if left is not None else pd.Series(np.nan, index=merged.index, dtype=float)
            fallback = right if right is not None else pd.Series(np.nan, index=merged.index, dtype=float)
            merged[factor_col] = pd.to_numeric(base, errors="coerce").where(pd.to_numeric(base, errors="coerce").notna(), pd.to_numeric(fallback, errors="coerce"))

    merged["sector_group"] = (
        merged.get("broad_sector", merged.get("sector", pd.Series("UNKNOWN", index=merged.index)))
        .astype("string")
        .fillna("UNKNOWN")
    )
    merged["market_cap_quintile"] = pd.cut(
        pd.to_numeric(merged["market_cap_rank"], errors="coerce"),
        bins=[-np.inf, 0.20, 0.40, 0.60, 0.80, np.inf],
        labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
    ).astype("string")

    if "eps_revision_accel" in features_df.columns:
        accel = pd.to_numeric(features_df["eps_revision_accel"], errors="coerce")
        merged["revision_cohort"] = (
            accel.groupby(features_df["date"], sort=False)
            .transform(lambda series: pd.qcut(series.rank(method="first"), q=[0.0, 0.2, 0.8, 1.0], labels=["low_revision", "stable", "high_revision"], duplicates="drop"))
            .astype("string")
        )
    else:
        merged["revision_cohort"] = "stable"

    if "fii_pct" in merged.columns:
        fii_pct = pd.to_numeric(merged["fii_pct"], errors="coerce")
    else:
        fii_pct = pd.Series(np.nan, index=merged.index, dtype=float)
    merged["fii_bracket"] = pd.cut(
        fii_pct,
        bins=[-np.inf, 5.0, 15.0, np.inf],
        labels=["low_fii", "mid_fii", "high_fii"],
    ).astype("string")
    merged["business_cycle_bucket"] = merged.get("business_cycle_bucket", pd.Series("mixed", index=merged.index)).astype("string")
    merged["conglomerate_bucket"] = merged.get("conglomerate_group", pd.Series("", index=merged.index)).astype("string").map(
        lambda value: "independent" if not str(value).strip() else str(value).strip()
    )
    merged["mnc_bucket"] = merged.get("international_brand_mnc_subsidiary", pd.Series("", index=merged.index)).astype("string").map(
        lambda value: "mnc" if "yes" in str(value).lower() else "domestic"
    )

    dimensions = [
        "sector_group",
        "market_cap_quintile",
        "revision_cohort",
        "fii_bracket",
        "business_cycle_bucket",
        "conglomerate_bucket",
        "mnc_bucket",
    ]
    tables: list[pd.DataFrame] = []
    summary: dict[str, Any] = {}
    for label, factor_col in factors.items():
        factor_rows: list[dict[str, Any]] = []
        for dimension in dimensions:
            table = _ic_by_group(merged[[dimension, "date", "ticker", factor_col, "target_weekly_return"]].copy(), factor_col, dimension)
            if table.empty:
                continue
            table["dimension"] = dimension
            table["factor_alias"] = label
            factor_rows.extend(table.to_dict("records"))
            tables.append(table.assign(dimension=dimension, factor_alias=label))
        factor_frame = pd.DataFrame(factor_rows).sort_values("mean_ic", ascending=False) if factor_rows else pd.DataFrame()
        summary[label] = {
            "feature": factor_col,
            "top_clusters": factor_frame.head(5).to_dict("records") if not factor_frame.empty else [],
            "bottom_clusters": factor_frame.tail(5).to_dict("records") if not factor_frame.empty else [],
        }

    all_tables = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if not all_tables.empty:
        all_tables.to_parquet(output_dir / "company_factor_attribution.parquet", index=False)
        all_tables.to_csv(output_dir / "company_factor_attribution.csv", index=False)

    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "factors": summary,
    }
    write_json(output_dir / "company_factor_map.json", payload)
    print(json_ready({"factor_count": len(summary), "dimensions": dimensions}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
