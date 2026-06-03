#!/usr/bin/env python3
"""NB-06: India-specific hypothesis battery for the weekly sprint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    load_export_artifacts,
    make_run_dir,
    resolve_export_dir,
    resolve_raw_bundle_from_export,
    safe_spearman,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-06 India-specific hypothesis battery.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _resolve_feature(available: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _window_summary(frame: pd.DataFrame, feature: str, target_col: str = "target_weekly_return") -> dict[str, float]:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        local = group[[feature, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 8:
            continue
        corr = safe_spearman(local[feature].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
        if pd.notna(corr):
            values.append(float(corr))
    if not values:
        return {"mean_ic": float("nan"), "ic_ir": float("nan"), "hit_rate": float("nan"), "n_dates": 0.0}
    mean_ic = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if len(values) > 1 else float("nan")
    return {
        "mean_ic": mean_ic,
        "ic_ir": mean_ic / std if np.isfinite(std) and std > 0 else float("nan"),
        "hit_rate": float(np.mean(np.asarray(values) > 0)),
        "n_dates": float(len(values)),
    }


def _regime_ic(frame: pd.DataFrame, feature: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for regime, subset in frame.groupby("plan_regime_id", dropna=False):
        stats = _window_summary(subset, feature)
        rows.append({"regime": str(regime), **stats})
    return pd.DataFrame(rows)


def _lagged_sector_test(
    frame: pd.DataFrame,
    macro_col: str,
    sector_col: str,
    target_sectors: set[str],
    max_lag: int = 13,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    working = frame.copy()
    macro_series = (
        working.groupby("date", as_index=False)[macro_col]
        .mean(numeric_only=True)
        .sort_values("date", kind="mergesort")
    )
    for lag in range(1, max_lag + 1):
        lagged = macro_series.copy()
        lagged[macro_col] = pd.to_numeric(lagged[macro_col], errors="coerce").shift(lag)
        merged = working.drop(columns=[macro_col], errors="ignore").merge(lagged, on="date", how="left", sort=False)
        subset = merged[merged[sector_col].isin(target_sectors)].copy()
        stats = _window_summary(subset, macro_col)
        rows.append({"lag_weeks": lag, **stats})
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb06_india_hypothesis_battery")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_bundle_dir = resolve_raw_bundle_from_export(export_artifacts.export_dir, args.data_dir)
    features_df, _, regimes_df, metadata_df = load_export_artifacts(export_artifacts.export_dir)
    available = list(features_df.columns)
    merged = features_df.merge(metadata_df, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    merged = merged.merge(regimes_df[["date", "plan_regime_id"]], on="date", how="left", sort=False)
    if "plan_regime_id" not in merged.columns:
        left = merged.get("plan_regime_id_x", pd.Series(pd.NA, index=merged.index, dtype="object"))
        right = merged.get("plan_regime_id_y", pd.Series(pd.NA, index=merged.index, dtype="object"))
        merged["plan_regime_id"] = left.where(left.notna(), right)

    broad_sector = merged.get("broad_sector", merged.get("sector", pd.Series("UNKNOWN", index=merged.index))).astype("string")
    merged["sector_group"] = broad_sector.fillna("UNKNOWN")
    merged["conglomerate_flag"] = merged.get("conglomerate_group", pd.Series("", index=merged.index)).astype("string").map(
        lambda value: 0 if not str(value).strip() else 1
    )

    results: dict[str, Any] = {}
    detail_tables: dict[str, pd.DataFrame] = {}

    accel = _resolve_feature(available, ["eps_revision_accel", "combined_revision_score_cs_z", "combined_revision_score"])
    velocity = _resolve_feature(available, ["eps_revision_velocity", "combined_revision_score_cs_rank"])
    level = _resolve_feature(available, ["eps_revision_level", "agreement_score_cs_z", "agreement_score"])
    h1_rows = []
    for label, feature in [("level", level), ("velocity", velocity), ("acceleration", accel)]:
        if feature is None:
            continue
        stats = _window_summary(merged, feature)
        h1_rows.append({"component": label, "feature": feature, **stats})
    h1_df = pd.DataFrame(h1_rows).sort_values("ic_ir", ascending=False) if h1_rows else pd.DataFrame()
    if not h1_df.empty:
        detail_tables["H01"] = h1_df
    ordering = h1_df["component"].tolist()
    results["H01"] = {
        "title": "Revision acceleration dominates revision level",
        "status": "confirmed" if ordering[:3] == ["acceleration", "velocity", "level"] else "refuted",
        "ordering": ordering,
        "evidence": h1_df.to_dict("records") if not h1_df.empty else [],
    }

    eq_feature = _resolve_feature(available, ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank", "earnings_quality_ratio"])
    if eq_feature is not None:
        eq_regime = _regime_ic(merged, eq_feature)
        detail_tables["H02"] = eq_regime
        positive_regimes = int((pd.to_numeric(eq_regime["mean_ic"], errors="coerce") > 0.010).sum())
        crash_negative = bool(
            eq_regime.loc[eq_regime["regime"].isin(["R4", "R9"]), "mean_ic"]
            .astype(float)
            .lt(0.0)
            .any()
        )
        results["H02"] = {
            "title": "India earnings quality sign stays positive across regimes",
            "status": "confirmed" if positive_regimes >= 7 and not crash_negative else "refuted",
            "feature": eq_feature,
            "positive_regimes": positive_regimes,
            "crash_negative": crash_negative,
            "evidence": eq_regime.to_dict("records"),
        }

    pledge = _resolve_feature(available, ["promoter_pledge_change_90d", "pledge_short_signal"])
    bulk = _resolve_feature(available, ["bulk_distribution_breadth", "bulk_net_institutional_21d_cs_rank"])
    if pledge is not None and bulk is not None:
        h3_frame = merged[["date", "ticker", "target_weekly_return", pledge, bulk]].copy()
        h3_frame["pledge_bulk_interaction"] = pd.to_numeric(h3_frame[pledge], errors="coerce") * pd.to_numeric(h3_frame[bulk], errors="coerce")
        h3_frame["pledge_bulk_sum"] = pd.to_numeric(h3_frame[pledge], errors="coerce") + pd.to_numeric(h3_frame[bulk], errors="coerce")
        h3_rows = []
        for label, feature in [
            ("pledge_alone", pledge),
            ("bulk_alone", bulk),
            ("interaction", "pledge_bulk_interaction"),
            ("sum_of_parts", "pledge_bulk_sum"),
        ]:
            stats = _window_summary(h3_frame, feature)
            h3_rows.append({"component": label, "feature": feature, **stats})
        h3_df = pd.DataFrame(h3_rows)
        detail_tables["H03"] = h3_df
        interaction_ic = float(h3_df.loc[h3_df["component"] == "interaction", "mean_ic"].iloc[0])
        sum_ic = float(h3_df.loc[h3_df["component"] == "sum_of_parts", "mean_ic"].iloc[0])
        results["H03"] = {
            "title": "Promoter pledge x bulk distribution is nonlinear",
            "status": "confirmed" if interaction_ic > 0.015 and interaction_ic > sum_ic + 0.005 else "refuted",
            "interaction_ic": interaction_ic,
            "sum_of_parts_ic": sum_ic,
            "evidence": h3_df.to_dict("records"),
        }

    fii_ownership = _resolve_feature(available, ["screener_fii_pct", "fii_pct", "screener_fii_pct_cs_rank"])
    fii_flow_proxy = _resolve_feature(available, ["screener_fii_change_1q", "fii_pct_change_1q"])
    if fii_ownership is not None and fii_flow_proxy is not None:
        h4 = merged[["date", "ticker", "plan_regime_id", "target_weekly_return", fii_ownership, fii_flow_proxy]].copy()
        h4["fii_ownership_flow_proxy"] = pd.to_numeric(h4[fii_ownership], errors="coerce") * pd.to_numeric(h4[fii_flow_proxy], errors="coerce")
        bull = _window_summary(h4[h4["plan_regime_id"] == "R1"], "fii_ownership_flow_proxy")
        stress = _window_summary(h4[h4["plan_regime_id"].isin(["R4", "R9"])], "fii_ownership_flow_proxy")
        results["H04"] = {
            "title": "FII ownership x FII flow proxy flips sign by regime",
            "status": "confirmed" if bull["mean_ic"] > 0.015 and stress["mean_ic"] < -0.010 else "refuted",
            "proxy_note": "Uses quarterly FII ownership change as the flow proxy because a direct daily FII net-flow series is not staged in the weekly export bundle.",
            "bull_regime": bull,
            "stress_regime": stress,
        }

    power_feature = _resolve_feature(available, ["power_mom_growth", "power_3m_trend", "power_yoy_growth"])
    if power_feature is not None:
        h5_df = _lagged_sector_test(
            merged,
            power_feature,
            "sector_group",
            {"Capital Goods", "Metals", "Construction", "Real Estate", "Infrastructure"},
        )
        detail_tables["H05"] = h5_df
        strong_lags = int(((pd.to_numeric(h5_df["mean_ic"], errors="coerce") > 0.015) & (pd.to_numeric(h5_df["ic_ir"], errors="coerce") > 0.30)).sum())
        best_row = h5_df.sort_values("ic_ir", ascending=False).head(1).to_dict("records")
        results["H05"] = {
            "title": "Power consumption lag predicts industrial sector returns",
            "status": "confirmed" if strong_lags >= 2 else "refuted",
            "feature": power_feature,
            "strong_lag_count": strong_lags,
            "best_lag": best_row[0] if best_row else {},
        }

    rbi_feature = _resolve_feature(available, ["rbi_repo_rate_change_13w", "rbi_repo_rate_level", "rbi_repo_rate_ts_z"])
    earnings_anchor = _resolve_feature(available, ["eps_sue_decay", "eps_sue", "eps_revision_accel"])
    if rbi_feature is not None and earnings_anchor is not None:
        h6 = merged[["date", "ticker", "target_weekly_return", rbi_feature, earnings_anchor]].copy()
        daily_rbi = h6.groupby("date", as_index=False)[rbi_feature].mean(numeric_only=True)
        threshold = float(pd.to_numeric(daily_rbi[rbi_feature], errors="coerce").abs().quantile(0.75))
        active_dates = set(daily_rbi.loc[pd.to_numeric(daily_rbi[rbi_feature], errors="coerce").abs() >= threshold, "date"].tolist())
        event_stats = _window_summary(h6[h6["date"].isin(active_dates)], earnings_anchor)
        quiet_stats = _window_summary(h6[~h6["date"].isin(active_dates)], earnings_anchor)
        ratio = float(event_stats["mean_ic"] / quiet_stats["mean_ic"]) if np.isfinite(quiet_stats["mean_ic"]) and abs(quiet_stats["mean_ic"]) > 1e-12 else float("nan")
        results["H06"] = {
            "title": "RBI-event IC is not more than 2x non-event IC",
            "status": "confirmed" if np.isfinite(ratio) and ratio < 1.5 else "refuted",
            "rate_feature": rbi_feature,
            "anchor_feature": earnings_anchor,
            "event_ic": event_stats,
            "quiet_ic": quiet_stats,
            "ratio": ratio,
        }

    earnings_calendar_path = raw_bundle_dir / "data" / "processed" / "alternative" / "earnings_dates_all.csv"
    if earnings_calendar_path.exists():
        earnings_dates = pd.read_csv(earnings_calendar_path)
        if {"ticker", "earnings_date"}.issubset(earnings_dates.columns):
            earnings_dates["ticker"] = earnings_dates["ticker"].astype("string")
            earnings_dates["earnings_date"] = pd.to_datetime(earnings_dates["earnings_date"], errors="coerce").dt.normalize()
            earnings_dates = earnings_dates.dropna(subset=["ticker", "earnings_date"])
            if not earnings_dates.empty:
                earnings_merge = merged[["date", "ticker", "target_weekly_return"]].copy()
                earnings_merge = earnings_merge.merge(earnings_dates, on="ticker", how="left", sort=False)
                earnings_merge["days_to_earnings"] = (earnings_merge["date"] - earnings_merge["earnings_date"]).dt.days.abs()
                earnings_weeks = set(earnings_merge.loc[earnings_merge["days_to_earnings"] <= 21, "date"].dropna().tolist())
                h7_rows = []
                for feature in [candidate for candidate in ["eps_sue_decay", "eps_revision_accel", "rev_sue_decay", "agreement_score_cs_z"] if candidate in available]:
                    event_stats = _window_summary(merged[merged["date"].isin(earnings_weeks)], feature)
                    quiet_stats = _window_summary(merged[~merged["date"].isin(earnings_weeks)], feature)
                    ratio = float(event_stats["mean_ic"] / quiet_stats["mean_ic"]) if np.isfinite(quiet_stats["mean_ic"]) and abs(quiet_stats["mean_ic"]) > 1e-12 else float("nan")
                    h7_rows.append(
                        {
                            "feature": feature,
                            "earnings_season_ic": event_stats["mean_ic"],
                            "quiet_ic": quiet_stats["mean_ic"],
                            "ratio": ratio,
                        }
                    )
                h7_df = pd.DataFrame(h7_rows)
                detail_tables["H07"] = h7_df
                strong = int((pd.to_numeric(h7_df["ratio"], errors="coerce") > 1.5).sum()) if not h7_df.empty else 0
                results["H07"] = {
                    "title": "Earnings-season IC is stronger than quiet-window IC",
                    "status": "confirmed" if strong >= 2 else "refuted",
                    "strong_factor_count": strong,
                    "evidence": h7_df.to_dict("records") if not h7_df.empty else [],
                }

    for factor_name, feature in {
        "earnings_quality_ratio": _resolve_feature(available, ["earnings_quality_ratio_cs_z", "earnings_quality_ratio"]),
        "accruals_ratio": _resolve_feature(available, ["accruals_ratio_cs_z", "accruals_ratio"]),
    }.items():
        if feature is None:
            continue
        conglomerate = _window_summary(merged[merged["conglomerate_flag"] == 1], feature)
        independent = _window_summary(merged[merged["conglomerate_flag"] == 0], feature)
        results.setdefault("H08_factors", []).append(
            {
                "factor": factor_name,
                "feature": feature,
                "conglomerate_ic": conglomerate["mean_ic"],
                "independent_ic": independent["mean_ic"],
                "difference": float(independent["mean_ic"] - conglomerate["mean_ic"]) if np.isfinite(independent["mean_ic"]) and np.isfinite(conglomerate["mean_ic"]) else float("nan"),
            }
        )
    if "H08_factors" in results:
        diffs = [row["difference"] for row in results["H08_factors"] if np.isfinite(row["difference"])]
        results["H08"] = {
            "title": "Conglomerate membership reduces earnings-quality factor IC",
            "status": "confirmed" if any(diff > 0.010 for diff in diffs) else "refuted",
            "evidence": list(results["H08_factors"]),
        }

    for key, table in detail_tables.items():
        if table.empty:
            continue
        table.to_parquet(output_dir / f"{key.lower()}_detail.parquet", index=False)
        table.to_csv(output_dir / f"{key.lower()}_detail.csv", index=False)

    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "raw_bundle_dir": str(raw_bundle_dir),
        "results": results,
    }
    write_json(output_dir / "india_hypothesis_results.json", payload)
    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
