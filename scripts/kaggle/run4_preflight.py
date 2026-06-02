#!/usr/bin/env python3
"""Preflight checks before spending Kaggle GPU time on Northstar Run 4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", required=True)
    parser.add_argument("--sequence-dir", required=True)
    parser.add_argument("--code-dir", required=True)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()

    feature_dir = Path(args.feature_dir)
    sequence_dir = Path(args.sequence_dir)
    code_dir = Path(args.code_dir)
    failures: list[str] = []

    checks = {
        "feature_parquet": feature_dir / "northstar_features.parquet",
        "walk_forward_splits": feature_dir / "northstar_walk_forward_splits.json",
        "regime_labels": feature_dir / "northstar_regime_labels.parquet",
        "sequence_splits": sequence_dir / "sequence_walk_forward_splits.json",
        "sequence_manifest": sequence_dir / "sequence_export_manifest.json",
        "sequence_shards": sequence_dir / "sequence_shards",
        "common_py": code_dir / "plan_2026_05_18_production" / "common.py",
        "experiments_py": code_dir / "plan_2026_05_18_production" / "experiments.py",
        "run_all": code_dir / "run_all_northstar_experiments.sh",
        "sequence_runner": code_dir / "sequence_experiments" / "run_sequence_experiment.py",
    }
    for name, path in checks.items():
        if not path.exists():
            failures.append(f"missing:{name}:{path}")

    if not failures:
        common_text = checks["common_py"].read_text(encoding="utf-8")
        experiments_text = checks["experiments_py"].read_text(encoding="utf-8")
        run_all_text = checks["run_all"].read_text(encoding="utf-8")
        required_markers = {
            "fixed_iterations": common_text,
            "grow_policy\": \"Depthwise": experiments_text,
            "EXP-09_run4b_depthwise_min_leaf_sweep": run_all_text,
            "RUN_EXTRA_DIAGNOSTICS": run_all_text,
        }
        for marker, text in required_markers.items():
            if marker not in text:
                failures.append(f"stale_code_marker_missing:{marker}")

    cuda_available = None
    if args.require_cuda:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            if not cuda_available:
                failures.append("cuda_not_available")
        except Exception as exc:
            failures.append(f"torch_cuda_check_failed:{exc}")

    report = {
        "status": "fail" if failures else "ok",
        "failures": failures,
        "feature_dir": str(feature_dir),
        "sequence_dir": str(sequence_dir),
        "code_dir": str(code_dir),
        "cuda_available": cuda_available,
    }
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
