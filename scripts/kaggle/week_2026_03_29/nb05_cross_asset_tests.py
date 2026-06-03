#!/usr/bin/env python3
"""NB-05: cross-asset signal tests for forex and commodities."""

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
    json_ready,
    load_export_artifacts,
    load_export_manifest,
    make_run_dir,
    resolve_export_dir,
    resolve_raw_bundle_from_export,
    safe_spearman,
    write_json,
)


LAGS = [0, 1, 2, 3, 4, 6, 8, 13]
SIGNAL_TARGET_SECTORS = {
    "oil_sector_impact": {"Energy", "Oil & Gas", "Auto", "FMCG", "Consumer"},
    "steel_margin_factor": {"Capital Goods", "Infrastructure", "Real Estate", "Metals"},
    "copper_activity_signal": {"Capital Goods", "Power", "Consumer Durables", "Electricals"},
    "inr_revenue_factor": {"Information Technology", "Healthcare", "Pharma", "Chemicals"},
    "gold_consumption_drag": {"FMCG", "Consumer Discretionary", "Consumer"},
    "dxy_fii_proxy": {"Financial Services", "Information Technology", "FMCG"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-05 cross-asset tests.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _load_cross_asset_weekly(raw_bundle_dir: Path) -> pd.DataFrame:
    path = raw_bundle_dir / "data" / "canonical" / "macro" / "cross_asset_prices_daily.parquet"
    panel = pd.read_parquet(path)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel = panel.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"], kind="mergesort")

    close = pd.to_numeric(panel["close"], errors="coerce")
    panel["ret_5d"] = close.groupby(panel["symbol"], sort=False).pct_change(5)
    panel["ret_21d"] = close.groupby(panel["symbol"], sort=False).pct_change(21)
    panel["vol_21d"] = close.groupby(panel["symbol"], sort=False).pct_change().rolling(21).std().reset_index(level=0, drop=True)
    panel["week_end"] = panel["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    weekly = panel.groupby(["symbol", "week_end"], sort=True, as_index=False).tail(1).copy()
    weekly = weekly.rename(columns={"date": "week_source_date", "week_end": "date"})
    wide = weekly.pivot(index="date", columns="symbol", values=["ret_5d", "ret_21d", "vol_21d"])
    wide.columns = [f"{outer}_{inner}" for outer, inner in wide.columns.to_flat_index()]
    wide = wide.reset_index().sort_values("date", kind="mergesort")

    if "ret_5d_USDINR=X" in wide.columns:
        wide["inr_5d_return"] = wide["ret_5d_USDINR=X"]
        wide["inr_21d_return"] = wide.get("ret_21d_USDINR=X")
        wide["inr_vol_21d"] = wide.get("vol_21d_USDINR=X")
    if "ret_5d_CL=F" in wide.columns:
        wide["brent_5d_return"] = wide["ret_5d_CL=F"]
        wide["brent_21d_return"] = wide.get("ret_21d_CL=F")
    if "ret_5d_GC=F" in wide.columns:
        wide["gold_5d_return"] = wide["ret_5d_GC=F"]
        wide["gold_21d_return"] = wide.get("ret_21d_GC=F")
    if "ret_5d_HG=F" in wide.columns:
        wide["copper_5d_return"] = wide["ret_5d_HG=F"]
        wide["copper_21d_return"] = wide.get("ret_21d_HG=F")
    if "ret_5d_EURUSD=X" in wide.columns:
        wide["dxy_proxy_5d_return"] = -pd.to_numeric(wide["ret_5d_EURUSD=X"], errors="coerce")
    else:
        wide["dxy_proxy_5d_return"] = np.nan
    if "ret_21d_HG=F" in wide.columns:
        wide["steel_proxy_21d_return"] = wide["ret_21d_HG=F"]
        wide["steel_proxy_source"] = "copper_fallback"
    else:
        wide["steel_proxy_21d_return"] = np.nan
        wide["steel_proxy_source"] = "unavailable"
    return wide


def _ic_summary(frame: pd.DataFrame, signal_col: str) -> dict[str, float]:
    values: list[float] = []
    for _, group in frame.groupby("date", sort=True):
        local = group[[signal_col, "target_weekly_return"]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(local) < 8:
            continue
        corr = safe_spearman(local[signal_col].to_numpy(dtype=float), local["target_weekly_return"].to_numpy(dtype=float))
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


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb05_cross_asset_tests")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_bundle_dir = resolve_raw_bundle_from_export(export_artifacts.export_dir, args.data_dir)
    features_df, _, regimes_df, metadata_df = load_export_artifacts(export_artifacts.export_dir)
    merged = features_df.merge(metadata_df, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    merged = merged.merge(regimes_df[["date", "plan_regime_id"]], on="date", how="left", sort=False)
    if "plan_regime_id" not in merged.columns:
        for candidate in ("plan_regime_id_x", "plan_regime_id_y"):
            if candidate in merged.columns:
                merged["plan_regime_id"] = merged[candidate]
                break
        if "plan_regime_id" not in merged.columns:
            merged["plan_regime_id"] = pd.Series(pd.NA, index=merged.index, dtype="string")

    weekly_macro = _load_cross_asset_weekly(raw_bundle_dir)
    weekly_macro.to_parquet(output_dir / "cross_asset_weekly_panel.parquet", index=False)

    lag_rows: list[dict[str, Any]] = []
    best_by_signal: dict[str, dict[str, Any]] = {}

    for lag in LAGS:
        shifted = weekly_macro.copy()
        lagged_cols = [col for col in shifted.columns if col != "date" and col != "steel_proxy_source"]
        for column in lagged_cols:
            shifted[column] = pd.to_numeric(shifted[column], errors="coerce").shift(int(lag))
        frame = merged.merge(shifted, on="date", how="left", sort=False)

        frame["inr_revenue_factor"] = pd.to_numeric(frame.get("inr_21d_return"), errors="coerce") * pd.to_numeric(frame.get("international_revenue_proxy"), errors="coerce")
        frame["oil_sector_impact"] = pd.to_numeric(frame.get("brent_21d_return"), errors="coerce") * pd.to_numeric(frame.get("oil_sensitivity_score"), errors="coerce")
        frame["steel_margin_factor"] = pd.to_numeric(frame.get("steel_proxy_21d_return"), errors="coerce") * pd.to_numeric(frame.get("steel_sensitivity_score"), errors="coerce")
        frame["copper_activity_signal"] = pd.to_numeric(frame.get("copper_21d_return"), errors="coerce") * pd.to_numeric(frame.get("copper_sensitivity_score"), errors="coerce")
        frame["gold_consumption_drag"] = pd.to_numeric(frame.get("gold_21d_return"), errors="coerce") * (-pd.to_numeric(frame.get("gold_sensitivity_score"), errors="coerce"))
        frame["dxy_fii_proxy"] = pd.to_numeric(frame.get("dxy_proxy_5d_return"), errors="coerce") * (pd.to_numeric(frame.get("fii_pct"), errors="coerce") / 100.0)

        candidate_signals = [
            "inr_5d_return",
            "inr_21d_return",
            "inr_vol_21d",
            "brent_5d_return",
            "brent_21d_return",
            "gold_5d_return",
            "gold_21d_return",
            "copper_5d_return",
            "copper_21d_return",
            "dxy_proxy_5d_return",
            "inr_revenue_factor",
            "oil_sector_impact",
            "steel_margin_factor",
            "copper_activity_signal",
            "gold_consumption_drag",
            "dxy_fii_proxy",
        ]
        for signal in candidate_signals:
            if signal not in frame.columns:
                continue
            overall = _ic_summary(frame, signal)
            sector_col = frame.get("broad_sector", frame.get("sector_group", pd.Series("UNKNOWN", index=frame.index))).astype("string")
            frame["sector_group"] = sector_col.fillna("UNKNOWN")
            target_sectors = SIGNAL_TARGET_SECTORS.get(signal, set())
            sector_subset = frame[frame["sector_group"].isin(target_sectors)].copy() if target_sectors else frame.copy()
            regime_subset = frame[frame["plan_regime_id"].isin(["R4", "R7", "R9"])].copy()
            sector_stats = _ic_summary(sector_subset, signal) if not sector_subset.empty else {"mean_ic": float("nan"), "ic_ir": float("nan"), "hit_rate": float("nan"), "n_dates": 0.0}
            regime_stats = _ic_summary(regime_subset, signal) if not regime_subset.empty else {"mean_ic": float("nan"), "ic_ir": float("nan"), "hit_rate": float("nan"), "n_dates": 0.0}
            row = {
                "signal": signal,
                "lag_weeks": lag,
                "overall_mean_ic": overall["mean_ic"],
                "overall_ic_ir": overall["ic_ir"],
                "sector_mean_ic": sector_stats["mean_ic"],
                "sector_ic_ir": sector_stats["ic_ir"],
                "stress_regime_mean_ic": regime_stats["mean_ic"],
                "stress_regime_ic_ir": regime_stats["ic_ir"],
            }
            lag_rows.append(row)
            incumbent = best_by_signal.get(signal)
            if incumbent is None or (np.isfinite(row["overall_ic_ir"]) and row["overall_ic_ir"] > incumbent.get("overall_ic_ir", float("-inf"))):
                best_by_signal[signal] = row

    lag_table = pd.DataFrame(lag_rows).sort_values(["signal", "overall_ic_ir"], ascending=[True, False])
    lag_table.to_parquet(output_dir / "cross_asset_lag_table.parquet", index=False)
    lag_table.to_csv(output_dir / "cross_asset_lag_table.csv", index=False)

    promoted = [
        signal
        for signal, row in best_by_signal.items()
        if np.isfinite(row["overall_mean_ic"]) and abs(float(row["overall_mean_ic"])) > 0.015 and np.isfinite(row["overall_ic_ir"]) and float(row["overall_ic_ir"]) > 0.30
    ]
    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "raw_bundle_dir": str(raw_bundle_dir),
        "signals": best_by_signal,
        "promoted_signals": promoted,
        "notes": {
            "dxy_proxy": "Derived from negative EURUSD return when direct DXY history is unavailable.",
            "steel_proxy": "Uses copper 21d return as a fallback steel-margin proxy because no direct HRC series is staged yet.",
        },
    }
    write_json(output_dir / "cross_asset_results.json", payload)
    print(json_ready({"promoted_signals": promoted, "signal_count": len(best_by_signal)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
