#!/usr/bin/env python3
"""Run the compendium-aligned v1 experiment suite against the Kaggle-ready export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_05.catalog import get_experiment_spec, load_experiment_catalog, load_plan_info, ordered_experiment_ids
from scripts.kaggle.plan_2026_04_05.common import json_ready, load_plan_dataset
from scripts.kaggle.plan_2026_04_05.model_redemption import run_redemption_experiment
from scripts.kaggle.plan_2026_04_05.ratio_campaign import run_ratio_experiment
from scripts.kaggle.plan_2026_04_05.regime_campaign import run_regime_experiment
from scripts.kaggle.plan_2026_04_05.sector_campaign import run_sector_experiment
from scripts.kaggle.plan_2026_04_05.signal_expansion import run_signal_experiment
from scripts.kaggle.plan_2026_04_05.signal_verification import run_verification_experiment


DEFAULT_EXPORT_DIR = PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_augmented_20260408"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "runs" / "compendium_plan_v1"
FAMILY_RUNNERS = {
    "ratio": run_ratio_experiment,
    "sector": run_sector_experiment,
    "regime": run_regime_experiment,
    "redemption": run_redemption_experiment,
    "signal": run_signal_experiment,
    "verification": run_verification_experiment,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the compendium-aligned Northstar experiment suite.")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--exp-id", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def _resolve_selection(exp_ids: list[str] | None) -> list[str]:
    if exp_ids:
        return [str(exp_id) for exp_id in exp_ids]
    return ordered_experiment_ids()


def run_suite(
    *,
    export_dir: Path,
    output_root: Path,
    exp_ids: list[str] | None,
    profile: str,
    max_splits: int | None,
    version: str = "v1",
) -> dict[str, Any]:
    dataset = load_plan_dataset(export_dir)
    selected = _resolve_selection(exp_ids)
    output_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for exp_id in selected:
        spec = get_experiment_spec(exp_id)
        runner = FAMILY_RUNNERS[spec.family]
        print(f"[plan-suite] running {exp_id} - {spec.title}", flush=True)
        results[exp_id] = runner(
            spec,
            dataset=dataset,
            output_root=output_root,
            profile=profile,
            max_splits=max_splits,
            version=version,
        )
    payload = {
        "plan_id": load_plan_info().plan_id,
        "version": version,
        "export_dir": str(export_dir),
        "output_root": str(output_root),
        "experiments": results,
    }
    (output_root / "suite_summary.json").write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    catalog = load_experiment_catalog()
    if args.list:
        listing = {
            exp_id: {
                "title": spec.title,
                "family": spec.family,
                "priority": spec.priority,
                "dependencies": list(spec.dependencies),
            }
            for exp_id, spec in catalog.items()
        }
        print(json.dumps(listing, indent=2))
        return 0

    selected = args.exp_id if args.exp_id else (ordered_experiment_ids() if args.all or not args.exp_id else [])
    payload = run_suite(
        export_dir=args.export_dir,
        output_root=args.output_root,
        exp_ids=selected,
        profile=args.profile,
        max_splits=args.max_splits,
        version=args.version,
    )
    print(json.dumps(json_ready(payload), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
