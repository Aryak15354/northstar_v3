#!/usr/bin/env python3
"""Run a cheap W09/W10 regression check for the inference-time centering fix."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.research.run_day2_clean_baseline import (
    DEFAULT_COMPARE_AGAINST,
    Day2CleanBaselineRunner,
    RequestedConfig,
)


DEFAULT_PRIOR_DAY2_DIR = (
    PROJECT_ROOT
    / "data/results/research/experiments/week_2026_03_22/day2_clean_baseline/20260323_005917_clean_standard_baseline"
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default))


def _build_config(args: argparse.Namespace) -> RequestedConfig:
    return RequestedConfig(
        validation_type="institutional_complete",
        n_windows=10,
        train_weeks=104,
        test_weeks=13,
        purge_gap_weeks=1,
        embargo_weeks=2,
        step_size_weeks=13,
        universe="nifty_500",
        min_universe_size=100,
        min_factor_coverage=0.25,
        model="certified_production",
        model_path=str(args.model_path),
        target_horizon_days=5,
        target_type="cross_sectional_rank",
        winsorize_low=0.01,
        winsorize_high=0.99,
        portfolio_size=20,
        long_only=True,
        max_position_weight=0.10,
        min_position_weight=0.01,
        turnover_constraint=0.60,
        use_config_capital_structure=True,
        governor_config_path=str(args.governor_config_path),
        regime="STANDARD",
        large_cap_bps=15.0,
        mid_cap_bps=20.0,
        small_cap_bps=30.0,
        large_cap_threshold_crore=10000.0,
        mid_cap_threshold_crore=2000.0,
        output_dir=str(args.output_dir),
        compare_against=str(args.compare_against),
        allow_regime_bundle_fallback=bool(args.allow_regime_bundle_fallback),
        certified_model_path=str(args.certified_model_path) if args.certified_model_path else None,
        preflight_only=False,
        low_resource_mode=str(args.low_resource_mode),
        duckdb_threads=int(args.duckdb_threads),
        duckdb_memory_limit_mb=int(args.duckdb_memory_limit_mb),
        calibration_stride_weeks=int(args.calibration_stride_weeks),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the centering patch on the dead W09/W10 windows.")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2b_centering_patch"),
        help="Experiment root for the centering diagnostic.",
    )
    parser.add_argument(
        "--prior-day2-dir",
        default=str(DEFAULT_PRIOR_DAY2_DIR),
        help="Prior Day 2 experiment directory to compare against.",
    )
    parser.add_argument(
        "--compare-against",
        default=str(DEFAULT_COMPARE_AGAINST),
        help="Institutional baseline report path.",
    )
    parser.add_argument(
        "--window-ids",
        default="W09,W10",
        help="Comma-separated window ids to rerun with the centering fix active.",
    )
    parser.add_argument(
        "--governor-config-path",
        default="config/portfolio_governor_config.yaml",
    )
    parser.add_argument(
        "--model-path",
        default="data/model_registry",
    )
    parser.add_argument(
        "--certified-model-path",
        default=None,
    )
    parser.add_argument(
        "--allow-regime-bundle-fallback",
        action="store_true",
        help="Allow the same fallback used by the current Day 2 runner when production metadata is incomplete.",
    )
    parser.add_argument("--duckdb-threads", type=int, default=1)
    parser.add_argument("--duckdb-memory-limit-mb", type=int, default=512)
    parser.add_argument("--low-resource-mode", default="on", choices=["on", "off", "auto"])
    parser.add_argument("--calibration-stride-weeks", type=int, default=4)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    cfg = _build_config(args)
    runner = Day2CleanBaselineRunner(cfg)

    requested_window_ids = {
        token.strip().upper()
        for token in str(args.window_ids).split(",")
        if token.strip()
    }
    if not requested_window_ids:
        raise ValueError("day2b_missing_window_ids")

    selected_windows = [window for window in runner.windows if window.window_id.upper() in requested_window_ids]
    if not selected_windows:
        raise ValueError(f"day2b_no_matching_windows:{sorted(requested_window_ids)}")
    runner.windows = selected_windows

    print(f"Experiment directory: {runner.experiment_dir}")
    print(f"Selected windows: {', '.join(window.window_id for window in runner.windows)}")
    print(f"Resolved model source: {runner.model_resolution.source}")
    print("Running centering regression diagnostic on the selected dead windows only")

    preflight = runner.run_preflight()
    if not preflight.get("ready_for_overnight", False):
        raise RuntimeError("day2b_preflight_failed")

    summary = runner.run_full()

    prior_dir = Path(args.prior_day2_dir).expanduser().resolve()
    prior_windows_path = prior_dir / "window_results.parquet"
    prior_df = pd.read_parquet(prior_windows_path)
    new_df = pd.read_parquet(runner.experiment_dir / "window_results.parquet")

    prior_df["window_id"] = prior_df["window_id"].astype(str)
    new_df["window_id"] = new_df["window_id"].astype(str)

    merged = prior_df.merge(
        new_df,
        on="window_id",
        suffixes=("_prior", "_patched"),
        how="inner",
    )
    merged = merged[merged["window_id"].isin([window.window_id for window in runner.windows])].copy()
    if merged.empty:
        raise RuntimeError("day2b_empty_comparison")

    merged["exposure_change"] = pd.to_numeric(merged["mean_exposure_patched"], errors="coerce").fillna(0.0) - pd.to_numeric(
        merged["mean_exposure_prior"], errors="coerce"
    ).fillna(0.0)
    merged["return_change"] = pd.to_numeric(merged["total_return_patched"], errors="coerce").fillna(0.0) - pd.to_numeric(
        merged["total_return_prior"], errors="coerce"
    ).fillna(0.0)
    merged["sharpe_change"] = pd.to_numeric(merged["sharpe_patched"], errors="coerce").fillna(0.0) - pd.to_numeric(
        merged["sharpe_prior"], errors="coerce"
    ).fillna(0.0)

    min_window_exposure = float(pd.to_numeric(merged["mean_exposure_patched"], errors="coerce").fillna(0.0).min())
    pass_threshold = 15.0
    verdict = "centering_patch_restored_dead_windows" if min_window_exposure > pass_threshold else "investigate_low_vol_further"

    comparison_payload = {
        "requested_window_ids": sorted(requested_window_ids),
        "prior_day2_dir": str(prior_dir),
        "patched_experiment_dir": str(runner.experiment_dir),
        "resolved_model": asdict(runner.model_resolution),
        "summary": summary,
        "window_comparison": merged[
            [
                "window_id",
                "total_return_prior",
                "total_return_patched",
                "return_change",
                "sharpe_prior",
                "sharpe_patched",
                "sharpe_change",
                "mean_exposure_prior",
                "mean_exposure_patched",
                "exposure_change",
                "violations_prior",
                "violations_patched",
            ]
        ].to_dict("records"),
        "min_window_exposure_patched": min_window_exposure,
        "pass_threshold_exposure": pass_threshold,
        "verdict": verdict,
    }
    _write_json(runner.experiment_dir / "comparison.json", comparison_payload)

    lines = [
        "# Day 2B Centering Patch Diagnostic",
        "",
        f"- Prior Day 2 Dir: `{prior_dir}`",
        f"- Patched Experiment Dir: `{runner.experiment_dir}`",
        f"- Selected Windows: `{', '.join(sorted(requested_window_ids))}`",
        f"- Verdict: `{verdict}`",
        "",
        "| Window | Prior Exposure | Patched Exposure | Change | Prior Sharpe | Patched Sharpe | Prior Return | Patched Return |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in comparison_payload["window_comparison"]:
        lines.append(
            "| {window_id} | {mean_exposure_prior:.2f}% | {mean_exposure_patched:.2f}% | {exposure_change:.2f}% | "
            "{sharpe_prior:.2f} | {sharpe_patched:.2f} | {total_return_prior:.2f}% | {total_return_patched:.2f}% |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            f"- Minimum patched window exposure: `{min_window_exposure:.2f}%`",
            f"- Pass threshold: `{pass_threshold:.2f}%`",
            "",
        ]
    )
    (runner.experiment_dir / "comparison.md").write_text("\n".join(lines))

    print(f"Summary JSON: {runner.experiment_dir / 'summary.json'}")
    print(f"Comparison JSON: {runner.experiment_dir / 'comparison.json'}")
    print(f"Comparison MD:   {runner.experiment_dir / 'comparison.md'}")
    print(f"Verdict: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
