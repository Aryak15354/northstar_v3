#!/usr/bin/env python3
"""
Builds the curated 60-feature week-2 dataset from the full feature matrix.

Selection criteria:
1. Keep features with mean absolute IC > 0.005 from prior unified-run JSON artifacts
2. Keep features with sign stability > 0.60 using prior decay alerts / decay tables
3. Keep features with stability CV < 1.2 across model importance rankings from saved model results
4. Always include PROTECTED_FEATURES
5. If raw and _cs_rank both pass, keep only _cs_rank
6. Cap at 60 features total, prioritized by mean absolute IC
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ConstantInputWarning, spearmanr


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = Path.home() / "Desktop" / "northstar_kaggle_data_v2"
SOURCE_PARQUET = INPUT_DIR / "northstar_features_v2.parquet"
OUTPUT_PARQUET = INPUT_DIR / "northstar_features_reduced.parquet"
OUTPUT_METADATA = INPUT_DIR / "northstar_features_reduced_metadata.json"

PROTECTED_FEATURES = [
    "eps_sue_decay",
    "rev_sue_decay",
    "eps_sue",
    "rev_sue",
    "earnings_quality_ratio_cs_rank",
    "earnings_quality_ratio_cs_z",
    "agreement_score",
    "agreement_score_cs_rank",
    "accruals_ratio_cs_rank",
    "accruals_ratio_cs_z",
    "roe_qoq_change",
    "piotroski_fscore",
    "cash_conversion",
    "posterior_gap",
    "bab_signal_cs_z",
    "amihud_illiquidity_cs_rank",
    "mom_20d_sector_ir",
    "ret_20d_sector_rel_cs_rank",
    "vol_20d_cs_z",
    "bulk_net_volume_5d_cs_rank",
]

MODEL_ARTIFACT_NAMES = {"XGBoost", "LightGBM", "CatBoost", "LSTM", "GRU", "PatchTST", "TFT", "iTransformer", "Transformer", "TCN"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the reduced 60-feature week-2 dataset.")
    parser.add_argument("--source-parquet", type=Path, default=SOURCE_PARQUET)
    parser.add_argument("--output-parquet", type=Path, default=OUTPUT_PARQUET)
    parser.add_argument("--ic-artifact", type=Path, default=None, help="Optional explicit IC JSON artifact path.")
    return parser.parse_args()


def discover_json_candidates() -> list[Path]:
    roots = [
        PROJECT_ROOT,
        PROJECT_ROOT / "tmp",
        PROJECT_ROOT / "data",
        Path.home() / "Desktop",
        Path.home() / "Downloads",
    ]
    patterns = [
        "*day1_ic_analysis.json",
        "*sprint_summary.json",
        "*full_results.json",
        "*_final.json",
    ]
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for path in root.rglob(pattern):
                if path.is_file():
                    found.add(path.resolve())
    return sorted(found)


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_ic_table(payload: dict[str, Any] | list[Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(payload, list):
        frame = pd.DataFrame(payload)
        if {"feature", "mean_ic"} <= set(frame.columns):
            return frame.copy(), {}
        return pd.DataFrame(), {}

    if "ic_table" in payload and isinstance(payload["ic_table"], list):
        return pd.DataFrame(payload["ic_table"]), payload

    day1 = payload.get("day1")
    if isinstance(day1, dict) and isinstance(day1.get("ic_table"), list):
        return pd.DataFrame(day1["ic_table"]), day1

    if isinstance(payload.get("day1_ic_table"), list):
        return pd.DataFrame(payload["day1_ic_table"]), payload

    return pd.DataFrame(), {}


def discover_ic_artifact(explicit_path: Path | None = None) -> tuple[Path, pd.DataFrame, dict[str, Any]]:
    if explicit_path is not None:
        payload = load_json(explicit_path)
        frame, meta = extract_ic_table(payload)
        if not frame.empty and {"feature", "mean_ic"} <= set(frame.columns):
            return explicit_path, frame, meta
        raise FileNotFoundError(f"Explicit IC artifact does not contain an ic_table: {explicit_path}")
    for path in discover_json_candidates():
        try:
            payload = load_json(path)
        except Exception:
            continue
        frame, meta = extract_ic_table(payload)
        if not frame.empty and {"feature", "mean_ic"} <= set(frame.columns):
            return path, frame, meta
    raise FileNotFoundError(
        "Could not find a unified-run IC artifact with an ic_table. "
        "Expected something like *_day1_ic_analysis.json or *_sprint_summary.json."
    )


def bootstrap_ic_artifact(
    features_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, pd.DataFrame, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "bootstrapped_day1_ic_analysis.json"

    target_col = "target_weekly_return" if "target_weekly_return" in features_df.columns else "forward_return_5d"
    if target_col not in features_df.columns:
        raise FileNotFoundError(
            "Could not find target_weekly_return or forward_return_5d in the source parquet."
        )

    work = features_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"]).sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

    feature_names = [
        col
        for col in work.select_dtypes(include=[np.number]).columns
        if col not in {"target_weekly_return", "forward_return_5d"}
        and col not in {"date", "ticker"}
        and not col.endswith("__realized")
    ]

    target_arr = pd.to_numeric(work[target_col], errors="coerce").to_numpy(dtype=float)
    grouped = [(pd.Timestamp(date), np.asarray(idx, dtype=int)) for date, idx in work.groupby("date", sort=True).indices.items()]
    ordered_dates = [date for date, _ in grouped]
    split_date = ordered_dates[len(ordered_dates) // 2] if ordered_dates else None

    ic_rows: list[dict[str, Any]] = []
    decay_rows: list[dict[str, Any]] = []

    for feature in feature_names:
        x_arr = pd.to_numeric(work[feature], errors="coerce").to_numpy(dtype=float)
        feat_ics: list[float] = []
        first_half: list[float] = []
        second_half: list[float] = []

        for date, idx in grouped:
            x = x_arr[idx]
            y = target_arr[idx]
            mask = np.isfinite(x) & np.isfinite(y)
            if int(mask.sum()) < 10:
                continue
            x_valid = x[mask]
            y_valid = y[mask]
            if np.nanstd(x_valid) <= 1e-12 or np.nanstd(y_valid) <= 1e-12:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=ConstantInputWarning)
                corr, _ = spearmanr(x_valid, y_valid)
            if not np.isfinite(corr):
                continue
            corr_f = float(corr)
            feat_ics.append(corr_f)
            if split_date is not None and date <= split_date:
                first_half.append(corr_f)
            else:
                second_half.append(corr_f)

        if not feat_ics:
            continue

        mean_ic = float(np.mean(feat_ics))
        std_ic = float(np.std(feat_ics, ddof=0))
        safe_std = std_ic + 1e-9
        ic_rows.append(
            {
                "feature": feature,
                "mean_ic": mean_ic,
                "std_ic": std_ic,
                "ic_ir": float(mean_ic / safe_std),
                "ic_tstat": float(mean_ic / (safe_std / np.sqrt(len(feat_ics)))),
                "hit_rate": float(np.mean(np.asarray(feat_ics) > 0)),
                "n_dates": int(len(feat_ics)),
            }
        )

        if first_half and second_half:
            ic_first = float(np.mean(first_half))
            ic_second = float(np.mean(second_half))
            decay_ratio = float(ic_second / (abs(ic_first) + 1e-9)) if abs(ic_first) > 1e-6 else 0.0
            decay_rows.append(
                {
                    "feature": feature,
                    "ic_first_half": ic_first,
                    "ic_second_half": ic_second,
                    "decay_ratio": decay_ratio,
                    "decay_alert": bool(decay_ratio < 0.5 or (ic_first * ic_second < 0.0)),
                }
            )

    ic_df = pd.DataFrame(ic_rows).sort_values("mean_ic", key=np.abs, ascending=False).reset_index(drop=True)
    decay_df = pd.DataFrame(decay_rows)
    alert_features = (
        decay_df.loc[decay_df["decay_alert"], "feature"].astype(str).tolist()
        if not decay_df.empty
        else []
    )

    payload = {
        "artifact_mode": "bootstrapped_from_source_parquet",
        "target_col": target_col,
        "split_date": str(split_date.date()) if split_date is not None else None,
        "ic_table": ic_df.to_dict("records"),
        "day1_decay": decay_df.to_dict("records"),
        "decay_alert_features": alert_features,
    }
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path, ic_df, payload


def discover_model_artifacts() -> list[Path]:
    model_paths: list[Path] = []
    for path in discover_json_candidates():
        if not path.name.endswith("_final.json"):
            continue
        try:
            payload = load_json(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("model", "")) not in MODEL_ARTIFACT_NAMES:
            continue
        stability = payload.get("stability", {})
        if isinstance(stability, dict) and isinstance(stability.get("mean_importance_by_feature"), dict):
            model_paths.append(path)
    return sorted(set(model_paths))


def build_sign_stability_map(ic_meta: dict[str, Any]) -> dict[str, float]:
    sign_map: dict[str, float] = {}

    decay_rows = ic_meta.get("day1_decay") or ic_meta.get("decay")
    if isinstance(decay_rows, list) and decay_rows:
        for row in decay_rows:
            if not isinstance(row, dict):
                continue
            feature = str(row.get("feature", ""))
            first = float(row.get("ic_first_half", np.nan))
            second = float(row.get("ic_second_half", np.nan))
            if not feature:
                continue
            stable = (
                np.isfinite(first)
                and np.isfinite(second)
                and first != 0.0
                and second != 0.0
                and math.copysign(1.0, first) == math.copysign(1.0, second)
            )
            sign_map[feature] = 1.0 if stable else 0.0

    alert_features = set(ic_meta.get("decay_alert_features") or [])
    for feature in alert_features:
        sign_map[str(feature)] = 0.0

    return sign_map


def build_importance_cv_map(model_artifacts: list[Path]) -> tuple[dict[str, float], dict[str, Any]]:
    if not model_artifacts:
        return {}, {"mode": "missing_model_artifacts", "models_used": []}

    model_frames: list[pd.Series] = []
    used_models: list[str] = []
    for path in model_artifacts:
        payload = load_json(path)
        stability = dict(payload.get("stability", {}) or {})
        mean_importance = stability.get("mean_importance_by_feature")
        if not isinstance(mean_importance, dict) or not mean_importance:
            continue
        series = pd.Series({str(k): abs(float(v)) for k, v in mean_importance.items()}, dtype=float)
        model_frames.append(series)
        used_models.append(str(payload.get("model", path.stem)))

    if not model_frames:
        return {}, {"mode": "missing_mean_importance", "models_used": used_models}

    imp_df = pd.concat(model_frames, axis=1).fillna(0.0)
    mean_vals = imp_df.mean(axis=1).abs()
    std_vals = imp_df.std(axis=1, ddof=0)
    cv = std_vals / mean_vals.replace(0.0, np.nan)
    cv = cv.replace([np.inf, -np.inf], np.nan)
    return cv.to_dict(), {"mode": "ok", "models_used": used_models}


def dedupe_raw_vs_rank(features: list[str]) -> list[str]:
    feature_set = set(features)
    drop_raw: set[str] = set()
    for feature in feature_set:
        if feature.endswith("_cs_rank"):
            raw_name = feature[: -len("_cs_rank")]
            if raw_name in feature_set and raw_name not in PROTECTED_FEATURES:
                drop_raw.add(raw_name)
    return [feature for feature in features if feature not in drop_raw]


def main() -> None:
    args = parse_args()
    source_parquet = Path(args.source_parquet).expanduser().resolve()
    output_parquet = Path(args.output_parquet).expanduser().resolve()
    output_metadata = output_parquet.with_name(OUTPUT_METADATA.name)

    if not source_parquet.exists():
        raise FileNotFoundError(
            f"Missing full week-2 parquet: {source_parquet}. Run build_new_factors.py first."
        )

    features_df = pd.read_parquet(source_parquet)
    try:
        ic_path, ic_table, ic_meta = discover_ic_artifact(args.ic_artifact)
    except FileNotFoundError:
        ic_path, ic_table, ic_meta = bootstrap_ic_artifact(features_df, output_parquet.parent)

    model_artifacts = discover_model_artifacts()
    sign_stability_map = build_sign_stability_map(ic_meta)
    importance_cv_map, cv_meta = build_importance_cv_map(model_artifacts)

    all_feature_names = [
        col
        for col in features_df.select_dtypes(include=[np.number]).columns
        if col not in {"target_weekly_return", "forward_return_5d"}
        and col not in {"date", "ticker"}
        and not col.endswith("__realized")
    ]

    ic_frame = ic_table.copy()
    ic_frame["feature"] = ic_frame["feature"].astype(str)
    ic_frame["mean_abs_ic"] = pd.to_numeric(ic_frame["mean_ic"], errors="coerce").abs()
    ic_map = dict(zip(ic_frame["feature"], ic_frame["mean_abs_ic"], strict=False))

    selection_frame = pd.DataFrame({"feature": all_feature_names})
    selection_frame["mean_abs_ic"] = selection_frame["feature"].map(ic_map).fillna(0.0)
    selection_frame["sign_stability"] = selection_frame["feature"].map(sign_stability_map).fillna(1.0)
    selection_frame["importance_cv"] = selection_frame["feature"].map(importance_cv_map).fillna(0.0)
    selection_frame["is_protected"] = selection_frame["feature"].isin(PROTECTED_FEATURES)

    stage1 = selection_frame.loc[(selection_frame["mean_abs_ic"] > 0.005) | selection_frame["is_protected"]].copy()
    stage2 = stage1.loc[(stage1["sign_stability"] > 0.60) | stage1["is_protected"]].copy()
    stage3 = stage2.loc[(stage2["importance_cv"] < 1.2) | stage2["is_protected"]].copy()

    ordered_candidates = (
        stage3.sort_values(["is_protected", "mean_abs_ic", "feature"], ascending=[False, False, True])["feature"].tolist()
    )
    ordered_candidates = dedupe_raw_vs_rank(ordered_candidates)

    protected_existing = [feature for feature in PROTECTED_FEATURES if feature in all_feature_names]
    missing_protected = [feature for feature in PROTECTED_FEATURES if feature not in all_feature_names]
    selected: list[str] = []
    for feature in protected_existing + ordered_candidates:
        if feature not in selected:
            selected.append(feature)
        if len(selected) >= 60:
            break

    if len(selected) < 60:
        fallback_pool = (
            selection_frame.sort_values(["mean_abs_ic", "feature"], ascending=[False, True])["feature"].tolist()
        )
        fallback_pool = dedupe_raw_vs_rank(fallback_pool)
        for feature in fallback_pool:
            if feature not in selected:
                selected.append(feature)
            if len(selected) >= 60:
                break

    selected = selected[:60]
    output_columns = ["date", "ticker"] + selected + ["target_weekly_return"]
    if "target_weekly_return" not in features_df.columns and "forward_return_5d" in features_df.columns:
        output_columns[-1] = "forward_return_5d"

    reduced_df = features_df[output_columns].copy()
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    reduced_df.to_parquet(output_parquet, index=False)

    metadata = {
        "source_full_parquet": str(source_parquet),
        "output_reduced_parquet": str(output_parquet),
        "ic_artifact": str(ic_path),
        "ic_artifact_mode": str(ic_meta.get("artifact_mode", "discovered")),
        "model_artifacts": [str(path) for path in model_artifacts],
        "selection_counts": {
            "all_numeric_features": int(len(all_feature_names)),
            "stage1_mean_abs_ic": int(len(stage1)),
            "stage2_sign_stability": int(len(stage2)),
            "stage3_importance_cv": int(len(stage3)),
            "selected_final": int(len(selected)),
        },
        "cv_metadata": cv_meta,
        "selected_features": selected,
        "protected_features_present": protected_existing,
        "protected_features_missing": missing_protected,
    }
    output_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("REDUCED FEATURE SET COMPLETE")
    print(f"  IC artifact: {ic_path}")
    print(f"  IC artifact mode: {ic_meta.get('artifact_mode', 'discovered')}")
    print(f"  Model artifacts used: {len(model_artifacts)}")
    print(f"  Selected features: {len(selected)}")
    print(f"  Protected features missing: {len(missing_protected)}")
    if missing_protected:
        print(f"    {missing_protected}")
    print(f"  Output: {output_parquet}")


if __name__ == "__main__":
    main()
