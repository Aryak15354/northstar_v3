#!/usr/bin/env python3
"""Validate a Northstar V3 sequence export before running temporal models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float):
        return None if not np.isfinite(obj) else obj
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence-dir", default="/kaggle/working/northstar_v3_sequence_export")
    parser.add_argument("--min-samples", type=int, default=50_000)
    parser.add_argument("--max-shards-check", type=int, default=5)
    args = parser.parse_args()

    seq_dir = Path(args.sequence_dir)
    required = [
        "sample_index.parquet",
        "static_features.parquet",
        "sequence_feature_registry.json",
        "sequence_export_manifest.json",
        "sequence_walk_forward_splits.json",
    ]
    missing = [name for name in required if not (seq_dir / name).exists()]
    shard_dir = seq_dir / "sequence_shards"
    shards = sorted(shard_dir.glob("seq_shard_*.npz"))
    if not shards:
        missing.append("sequence_shards/seq_shard_*.npz")

    report: dict[str, Any] = {"sequence_dir": str(seq_dir), "missing_files": missing}
    if missing:
        print(json.dumps(report, indent=2))
        return 2

    sample_index = pd.read_parquet(seq_dir / "sample_index.parquet")
    static = pd.read_parquet(seq_dir / "static_features.parquet")
    registry = json.loads((seq_dir / "sequence_feature_registry.json").read_text())
    manifest = json.loads((seq_dir / "sequence_export_manifest.json").read_text())
    splits = json.loads((seq_dir / "sequence_walk_forward_splits.json").read_text()).get("windows", [])

    shard_rows = 0
    shapes = []
    finite_rates = []
    mask_rates = []
    target_stats = []
    sample_ids = set()
    for shard in shards[: args.max_shards_check]:
        payload = np.load(shard)
        X = payload["X_temporal"]
        M = payload["X_mask"]
        y = payload["y"]
        ids = payload["sample_id"]
        shapes.append(list(X.shape))
        shard_rows += int(len(y))
        finite_rates.append(float(np.isfinite(X).mean()))
        mask_rates.append(float(M.mean()))
        target_stats.extend(y[np.isfinite(y)].astype(float).tolist())
        sample_ids.update(int(x) for x in ids.tolist())
        if X.shape != M.shape:
            report["shape_error"] = f"{shard.name}: X shape {X.shape} != mask shape {M.shape}"
            print(json.dumps(json_safe(report), indent=2))
            return 2

    duplicate_samples = int(sample_index.duplicated("sample_id").sum())
    split_counts = [
        {
            "window_id": w.get("window_id"),
            "train_samples": int(w.get("train_samples", 0)),
            "test_samples": int(w.get("test_samples", 0)),
        }
        for w in splits
    ]
    arr = np.asarray(target_stats, dtype=float)
    report.update(
        {
            "status": "ok",
            "samples": int(len(sample_index)),
            "tickers": int(sample_index["ticker"].nunique()),
            "date_min": str(pd.to_datetime(sample_index["date"]).min().date()),
            "date_max": str(pd.to_datetime(sample_index["date"]).max().date()),
            "static_shape": list(static.shape),
            "temporal_feature_count": int(len(registry.get("temporal_features", []))),
            "static_feature_count": int(manifest.get("static_feature_count", static.shape[1] - 3)),
            "shard_count": int(len(shards)),
            "checked_shard_shapes": shapes,
            "checked_finite_rate": float(np.mean(finite_rates)) if finite_rates else None,
            "checked_observed_mask_rate": float(np.mean(mask_rates)) if mask_rates else None,
            "target_mean_checked": float(arr.mean()) if arr.size else None,
            "target_std_checked": float(arr.std()) if arr.size else None,
            "duplicate_sample_ids": duplicate_samples,
            "split_windows": int(len(splits)),
            "first_split_counts": split_counts[:5],
            "passes_min_samples": bool(len(sample_index) >= args.min_samples),
            "feature_groups": {k: len(v) for k, v in registry.get("groups", {}).items()},
        }
    )
    out = seq_dir / "sequence_validation_report.json"
    out.write_text(json.dumps(json_safe(report), indent=2), encoding="utf-8")
    print(json.dumps(json_safe(report), indent=2))
    return 0 if report["passes_min_samples"] and duplicate_samples == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
