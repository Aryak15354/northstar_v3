#!/usr/bin/env python3
"""Repair the Northstar V3 feature export for Kaggle experiment runs.

This script is intentionally conservative: it fixes known hard data defects
without deleting sparse macro/regime columns that later experiments may need.
Model-facing scripts should still choose their feature policy from the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_robust_20260405"
DEFAULT_OUTPUT = PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_fixed_20260518"
TARGET_COL = "target_weekly_return"
TARGET_CLIP = 0.15
NON_FEATURE_COLS = {"date", "ticker", TARGET_COL}

PROMPT_KNOWN_NULL_COLS = [
    "accruals_ratio",
    "asset_turnover",
    "cash_conversion",
    "debt_to_equity",
    "ebitda_margin",
    "interest_coverage",
    "operating_margin",
    "roe",
    "piotroski_fscore",
    "screener_roe",
    "screener_roce",
    "screener_debt_to_equity",
    "screener_current_ratio",
    "screener_pe",
    "screener_pb",
    "gst_collection_yoy",
    "gst_ewaybill_growth",
    "gst_filing_rate",
    "promoter_pledge_ratio",
]

PROXY_COLS = {
    "coal_4w_return": "hybrid proxy from API2 coal futures plus official FRED coal benchmark fallback; treat IC as indicative",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _copy_sidecars(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.name in {"northstar_features.parquet", "northstar_metadata.parquet", "dataset-metadata.json"}:
            continue
        if path.is_file():
            shutil.copy2(path, output / path.name)


def _repair_features(features: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    audit: dict[str, Any] = {
        "raw_shape": [int(features.shape[0]), int(features.shape[1])],
        "raw_target_null_rows": int(features[TARGET_COL].isna().sum()),
    }
    df = features.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

    duplicate_rows = int(df.duplicated(["date", "ticker"]).sum())
    if duplicate_rows:
        df = df.drop_duplicates(["date", "ticker"], keep="last").reset_index(drop=True)
    audit["duplicate_rows_dropped"] = duplicate_rows

    pre_min = float(pd.to_numeric(df[TARGET_COL], errors="coerce").min())
    pre_max = float(pd.to_numeric(df[TARGET_COL], errors="coerce").max())
    clip_mask = pd.to_numeric(df[TARGET_COL], errors="coerce").abs() > TARGET_CLIP
    df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce").clip(-TARGET_CLIP, TARGET_CLIP)
    audit["target_pre_clip_min"] = pre_min
    audit["target_pre_clip_max"] = pre_max
    audit["target_clip_abs"] = TARGET_CLIP
    audit["target_rows_clipped"] = int(clip_mask.sum())

    null_target_rows = int(df[TARGET_COL].isna().sum())
    null_target_dates = [
        str(pd.Timestamp(value).date())
        for value in sorted(df.loc[df[TARGET_COL].isna(), "date"].dropna().unique())
    ]
    df = df[df[TARGET_COL].notna()].copy()
    audit["target_null_rows_dropped"] = null_target_rows
    audit["target_null_dates_dropped_or_partially_thinned"] = null_target_dates

    all_null_cols = [c for c in df.columns if c not in NON_FEATURE_COLS and df[c].isna().all()]
    known_null_present = [c for c in PROMPT_KNOWN_NULL_COLS if c in df.columns]
    drop_null_cols = sorted(set(all_null_cols) | set(known_null_present))
    df = df.drop(columns=drop_null_cols, errors="ignore")
    audit["all_null_or_prompt_null_cols_dropped"] = drop_null_cols

    numeric_cols = [
        c
        for c in df.columns
        if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    nunique = df[numeric_cols].nunique(dropna=True)
    constant_cols = sorted(nunique[nunique <= 1].index.astype(str).tolist())
    df = df.drop(columns=constant_cols, errors="ignore")
    audit["constant_numeric_cols_dropped"] = constant_cols

    feature_cols = [
        c
        for c in df.columns
        if c not in NON_FEATURE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    null_rates = df[feature_cols].isna().mean().sort_values(ascending=False)
    sparse_cols = null_rates[null_rates > 0.95].index.astype(str).tolist()
    safe_feature_cols = [c for c in feature_cols if c not in set(sparse_cols)]

    ordered_cols = ["date", "ticker"] + sorted(feature_cols) + [TARGET_COL]
    df = df[ordered_cols].sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
    audit["post_repair_shape"] = [int(df.shape[0]), int(df.shape[1])]
    audit["post_repair_date_min"] = str(df["date"].min().date())
    audit["post_repair_date_max"] = str(df["date"].max().date())
    audit["post_repair_ticker_count"] = int(df["ticker"].nunique())
    audit["model_feature_count"] = int(len(feature_cols))
    audit["safe_feature_count_null_le_95pct"] = int(len(safe_feature_cols))
    audit["sparse_cols_above_95pct_null"] = sparse_cols
    audit["sparse_col_null_rates"] = {c: float(null_rates[c]) for c in sparse_cols}
    return df, audit, safe_feature_cols


def _repair_metadata(metadata: pd.DataFrame, valid_keys: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    meta = metadata.copy()
    meta["date"] = pd.to_datetime(meta["date"], errors="coerce").dt.normalize()
    before_missing_sector = int(meta.get("sector", pd.Series(index=meta.index, dtype="object")).isna().sum())
    sector_like = ["sector", "broad_sector", "subsector"]
    for col in sector_like:
        if col in meta.columns:
            meta[col] = meta[col].fillna("Unknown").astype(str)
    filtered = valid_keys.merge(meta, on=["date", "ticker"], how="left", sort=False)
    for col in sector_like:
        if col in filtered.columns:
            filtered[col] = filtered[col].fillna("Unknown").astype(str)
    filtered = filtered.drop_duplicates(["date", "ticker"], keep="last").sort_values(["date", "ticker"], kind="mergesort")
    audit = {
        "raw_metadata_rows": int(len(metadata)),
        "metadata_rows_after_key_alignment": int(len(filtered)),
        "raw_missing_sector_rows": before_missing_sector,
        "post_missing_sector_rows": int(filtered["sector"].isna().sum()) if "sector" in filtered.columns else None,
        "unknown_sector_rows": int((filtered["sector"] == "Unknown").sum()) if "sector" in filtered.columns else None,
        "unknown_sector_tickers": int(filtered.loc[filtered["sector"] == "Unknown", "ticker"].nunique()) if "sector" in filtered.columns else None,
    }
    return filtered.reset_index(drop=True), audit


def _repair_splits(splits: list[dict[str, Any]], features: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    max_date = pd.Timestamp(features["date"].max()).normalize()
    min_date = pd.Timestamp(features["date"].min()).normalize()
    repaired: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for split in splits:
        row = dict(split)
        train_start = max(pd.Timestamp(row["train_start"]).normalize(), min_date)
        train_end = min(pd.Timestamp(row["train_end"]).normalize(), max_date)
        test_start = max(pd.Timestamp(row["test_start"]).normalize(), min_date)
        test_end = min(pd.Timestamp(row["test_end"]).normalize(), max_date)
        row.update(
            {
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
            }
        )
        train_rows = int(((features["date"] >= train_start) & (features["date"] <= train_end)).sum())
        test_rows = int(((features["date"] >= test_start) & (features["date"] <= test_end)).sum())
        row["train_rows"] = train_rows
        row["test_rows"] = test_rows
        repaired.append(row)
        audit_rows.append(
            {
                "window_id": int(row.get("window_id", len(repaired))),
                "train_rows": train_rows,
                "test_rows": test_rows,
                "test_dates": int(features.loc[(features["date"] >= test_start) & (features["date"] <= test_end), "date"].nunique()),
            }
        )
    return repaired, audit_rows


def repair_export(source: Path, output: Path) -> dict[str, Any]:
    if not source.exists():
        raise FileNotFoundError(f"source export does not exist: {source}")
    if output.exists():
        shutil.rmtree(output)
    _copy_sidecars(source, output)

    features_raw = pd.read_parquet(source / "northstar_features.parquet")
    metadata_raw = pd.read_parquet(source / "northstar_metadata.parquet")
    features, feature_audit, safe_feature_cols = _repair_features(features_raw)
    metadata, metadata_audit = _repair_metadata(metadata_raw, features[["date", "ticker"]])

    regimes = pd.read_parquet(source / "northstar_regime_labels.parquet")
    regimes["date"] = pd.to_datetime(regimes["date"], errors="coerce").dt.normalize()
    regimes = regimes[regimes["date"].isin(set(features["date"].unique()))].sort_values("date", kind="mergesort")

    splits_raw = json.loads((source / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))
    splits, split_audit = _repair_splits(list(splits_raw), features)

    features.to_parquet(output / "northstar_features.parquet", index=False)
    model_ready_cols = ["date", "ticker"] + safe_feature_cols + [TARGET_COL]
    features[model_ready_cols].to_parquet(output / "northstar_features_model_ready.parquet", index=False)
    metadata.to_parquet(output / "northstar_metadata.parquet", index=False)
    regimes.to_parquet(output / "northstar_regime_labels.parquet", index=False)
    _write_json(output / "northstar_walk_forward_splits.json", {"windows": splits})
    (output / "northstar_walk_forward_splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")

    manifest = _read_json(source / "weekly_export_manifest.json")
    manifest.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "builder": "repair_northstar_feature_export.py",
            "source_export": str(source),
            "features_rows": int(len(features)),
            "metadata_rows": int(len(metadata)),
            "feature_count": int(features.shape[1] - 3),
            "model_ready_feature_count": int(len(safe_feature_cols)),
            "ticker_count": int(features["ticker"].nunique()),
            "date_min": str(features["date"].min().date()),
            "date_max": str(features["date"].max().date()),
            "target_non_null_pct": float(features[TARGET_COL].notna().mean()),
            "target_clip_abs": TARGET_CLIP,
            "n_windows": len(splits),
            "repair_audit_path": "northstar_dataset_repair_audit.json",
            "feature_manifest_path": "northstar_feature_manifest.json",
        }
    )
    _write_json(output / "weekly_export_manifest.json", manifest)

    dataset_metadata = _read_json(source / "dataset-metadata.json")
    dataset_metadata.update(
        {
            "title": "Northstar V3 Feature Export Fixed",
            "id": "aryakghoshal/northstar-v3-feature-export-fixed",
            "licenses": dataset_metadata.get("licenses") or [{"name": "other"}],
            "isPrivate": True,
        }
    )
    _write_json(output / "dataset-metadata.json", dataset_metadata)

    feature_cols = [c for c in features.columns if c not in NON_FEATURE_COLS]
    sparse_cols = list(feature_audit["sparse_cols_above_95pct_null"])
    feature_manifest = {
        "target_col": TARGET_COL,
        "target_horizon_days": 5,
        "target_policy": f"winsorized at +/-{TARGET_CLIP} weekly return",
        "known_null_cols": PROMPT_KNOWN_NULL_COLS,
        "physically_dropped_null_or_prompt_cols": feature_audit["all_null_or_prompt_null_cols_dropped"],
        "physically_dropped_constant_cols": feature_audit["constant_numeric_cols_dropped"],
        "proxy_cols": PROXY_COLS,
        "known_sparse_cols_above_95pct_null": sparse_cols,
        "safe_model_feature_cols": safe_feature_cols,
        "full_numeric_feature_cols": feature_cols,
        "model_ready_parquet": "northstar_features_model_ready.parquet",
        "universe_note": "578 tickers including historical constituents/delisted names; do not force-filter to 493.",
        "row_count": int(len(features)),
        "date_range": f"{features['date'].min().date()} to {features['date'].max().date()}",
        "walk_forward_windows": len(splits),
        "sector_policy": "metadata sector/broad_sector/subsector nulls filled with Unknown",
        "experiment_feature_policy": {
            "EXP-09_to_EXP-16": "Use safe_model_feature_cols or northstar_features_model_ready.parquet.",
            "EXP-17_to_EXP-19": "May use full_numeric_feature_cols; CatBoost can consume sparse NaNs.",
            "EXP-20_to_EXP-23": "Use safe_model_feature_cols unless the script explicitly logs sparse handling.",
            "EXP-24_to_EXP-27": "Use available listed signals/factors only; never crash on missing columns.",
        },
    }
    _write_json(output / "northstar_feature_manifest.json", feature_manifest)

    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_export": str(source),
        "output_export": str(output),
        "feature_repair": feature_audit,
        "metadata_repair": metadata_audit,
        "split_audit": split_audit,
        "files": {
            name: {
                "bytes": (output / name).stat().st_size,
                "sha256": _sha256(output / name),
            }
            for name in [
                "northstar_features.parquet",
                "northstar_features_model_ready.parquet",
                "northstar_metadata.parquet",
                "northstar_regime_labels.parquet",
                "northstar_walk_forward_splits.json",
                "northstar_feature_manifest.json",
                "weekly_export_manifest.json",
                "dataset-metadata.json",
            ]
            if (output / name).exists()
        },
    }
    _write_json(output / "northstar_dataset_repair_audit.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audit = repair_export(args.source.expanduser().resolve(), args.output.expanduser().resolve())
    print(json.dumps(_json_safe(audit["feature_repair"]), indent=2))
    print(f"\nRepaired export written to: {args.output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
