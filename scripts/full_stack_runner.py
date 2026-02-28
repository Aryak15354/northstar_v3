#!/usr/bin/env python3
"""Run full research stack sequentially in isolated processes for 8GB-class hosts."""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.regime_map import get_regime, list_regimes


DEFAULT_PHASES = ["classical", "deep", "walkforward", "ensemble"]
CLASSICAL_MODELS = ["lightgbm", "xgboost", "catboost", "random_forest"]
DEEP_MODELS = ["lstm", "tcn", "transformer"]
ALL_MODELS = CLASSICAL_MODELS + DEEP_MODELS
ENSEMBLE_MODELS = ["lightgbm", "xgboost", "transformer"]


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out.get(key, {}), value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _parse_phases(value: str) -> List[str]:
    parts = [p.strip().lower() for p in str(value).split(",") if p.strip()]
    if not parts:
        return list(DEFAULT_PHASES)
    return parts


def _parse_horizons(value: str | None) -> List[int]:
    if value is None:
        return []
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    out: List[int] = []
    for p in parts:
        try:
            h = int(p)
        except Exception as exc:
            raise ValueError(f"invalid_target_horizon:{p}") from exc
        if h <= 0:
            raise ValueError(f"invalid_target_horizon:{p}")
        out.append(h)
    # De-duplicate while preserving order.
    dedup: List[int] = []
    seen = set()
    for h in out:
        if h in seen:
            continue
        seen.add(h)
        dedup.append(h)
    return dedup


def _phase_overrides(phase: str, args: argparse.Namespace, base_hr: Dict[str, Any]) -> Dict[str, Any]:
    phase = str(phase).strip().lower()
    model_cooldown = max(0.0, float(args.model_cooldown_seconds))
    base_windows = int(base_hr.get("training", {}).get("max_windows", 8))

    if phase == "classical":
        overrides = {
            "historical_research": {
                "enable_deep_models": False,
                "enabled_models": CLASSICAL_MODELS,
                "enable_ensemble": False,
                "autonomous_budget": {
                    "max_models_weekday": len(CLASSICAL_MODELS),
                    "max_models_weekend": len(CLASSICAL_MODELS),
                },
                "autonomous_exploration": {
                    "enabled": False,
                },
                "training": {
                    "max_windows": max(1, int(args.classical_windows)),
                },
                "model_cooldown_seconds": model_cooldown,
            }
        }
    elif phase == "deep":
        overrides = {
            "historical_research": {
                "enable_deep_models": True,
                "enabled_models": DEEP_MODELS,
                "enable_ensemble": False,
                "disable_ensemble_in_low_resource": True,
                "autonomous_budget": {
                    "max_models_weekday": len(DEEP_MODELS),
                    "max_models_weekend": len(DEEP_MODELS),
                    "model_priority": DEEP_MODELS + CLASSICAL_MODELS,
                },
                "autonomous_exploration": {
                    "enabled": False,
                },
                "training": {
                    "max_windows": max(1, int(args.deep_windows)),
                },
                "model_cooldown_seconds": model_cooldown,
            }
        }
    elif phase == "walkforward":
        overrides = {
            "historical_research": {
                "enable_deep_models": True,
                "enabled_models": ALL_MODELS,
                "enable_ensemble": False,
                "autonomous_budget": {
                    "max_models_weekday": len(ALL_MODELS),
                    "max_models_weekend": len(ALL_MODELS),
                    "model_priority": ALL_MODELS,
                },
                "autonomous_exploration": {
                    "enabled": False,
                },
                "training": {
                    "max_windows": max(1, int(args.walkforward_windows or base_windows)),
                    "start_window": max(0, int(args.walkforward_window_start)),
                },
                "model_cooldown_seconds": model_cooldown,
            }
        }
    elif phase == "ensemble":
        overrides = {
            "historical_research": {
                "enable_deep_models": True,
                "enabled_models": ENSEMBLE_MODELS,
                "enable_ensemble": True,
                "disable_ensemble_in_low_resource": False,
                "autonomous_budget": {
                    "max_models_weekday": len(ENSEMBLE_MODELS),
                    "max_models_weekend": len(ENSEMBLE_MODELS),
                    "model_priority": ENSEMBLE_MODELS,
                },
                "autonomous_exploration": {
                    "enabled": False,
                },
                "training": {
                    "max_windows": max(1, int(args.ensemble_windows)),
                },
                "model_cooldown_seconds": model_cooldown,
            }
        }
    elif phase == "exploration":
        variants = max(1, int(args.exploration_variants))
        overrides = {
            "historical_research": {
                "enable_deep_models": True,
                "enabled_models": ALL_MODELS,
                "enable_ensemble": False,
                "autonomous_budget": {
                    "max_models_weekday": len(ALL_MODELS),
                    "max_models_weekend": len(ALL_MODELS),
                    "model_priority": ALL_MODELS,
                },
                "autonomous_exploration": {
                    "enabled": True,
                    "variants_weekday": variants,
                    "variants_weekend": max(variants, 2),
                    "evaluation_max_windows": 1,
                },
                "training": {
                    "max_windows": max(1, int(args.exploration_windows)),
                },
                "model_cooldown_seconds": model_cooldown,
            }
        }
    else:
        raise ValueError(f"unknown_phase:{phase}")

    hr = overrides.setdefault("historical_research", {})
    budget = hr.setdefault("autonomous_budget", {})
    exploration = hr.setdefault("autonomous_exploration", {})
    model_params = hr.setdefault("model_params", {})

    if bool(args.enable_hyperopt):
        hr["enable_hyperopt"] = True
        hr["hyperopt_calls"] = max(5, int(args.hyperopt_calls))
        hr["hyperopt_max_windows"] = max(1, int(args.hyperopt_max_windows))
        # Keep parameter search operational on constrained hosts even when skopt
        # is not installed by allowing Bayesian optimizer fallback.
        hr["strict_bayesian_only"] = False

    if args.evaluation_max_windows is not None:
        exploration["evaluation_max_windows"] = max(1, int(args.evaluation_max_windows))

    if args.max_models_weekday is not None:
        budget["max_models_weekday"] = max(1, int(args.max_models_weekday))
    if args.max_models_weekend is not None:
        budget["max_models_weekend"] = max(1, int(args.max_models_weekend))

    if args.rf_estimators is not None:
        model_params.setdefault("random_forest", {})["n_estimators"] = max(50, int(args.rf_estimators))
    if args.lstm_epochs is not None:
        model_params.setdefault("lstm", {})["epochs"] = max(1, int(args.lstm_epochs))
    if args.tcn_epochs is not None:
        model_params.setdefault("tcn", {})["epochs"] = max(1, int(args.tcn_epochs))
    if args.transformer_epochs is not None:
        model_params.setdefault("transformer", {})["epochs"] = max(1, int(args.transformer_epochs))
    if args.transformer_d_model is not None:
        model_params.setdefault("transformer", {})["d_model"] = max(16, int(args.transformer_d_model))

    return overrides


def _collect_cycle_file(before: Sequence[str], after: Sequence[str]) -> str:
    before_set = set(before)
    new_files = [p for p in after if p not in before_set]
    if new_files:
        new_files.sort(key=lambda p: Path(p).stat().st_mtime)
        return new_files[-1]
    # Do not fall back to the latest existing cycle file because that can
    # silently report stale metrics when a cycle is skipped or fails early.
    return ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        return float(default)
    if x != x:  # NaN guard
        return float(default)
    return float(x)


def _load_cycle_payload(cycle_file: str) -> Dict[str, Any]:
    if not cycle_file:
        return {}
    p = Path(str(cycle_file))
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_cycle_metrics(cycle_file: str) -> Dict[str, Any]:
    payload = _load_cycle_payload(cycle_file)
    outputs = payload.get("outputs_generated")
    if not isinstance(outputs, list):
        outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        outputs = []

    model_rows: List[Dict[str, Any]] = []
    best_model = ""
    candidate_score = 0.0
    ic_diag: Dict[str, Any] = {}
    skipped = bool(payload.get("skipped", False))
    skip_reason = str(payload.get("skip_reason", "")).strip()

    for item in outputs:
        if not isinstance(item, dict):
            continue
        otype = str(item.get("type", "")).strip().lower()
        data = item.get("data")
        if not isinstance(data, dict):
            continue

        if otype == "model_validation":
            model = str(data.get("model", "")).strip()
            agg = data.get("aggregate_metrics")
            if model and isinstance(agg, dict):
                model_rows.append(
                    {
                        "model": model,
                        "ic": _safe_float(agg.get("ic_mean", 0.0)),
                        "sharpe": _safe_float(agg.get("avg_sharpe", 0.0)),
                        "dd": _safe_float(agg.get("avg_max_drawdown", 0.0)),
                        "windows": int(round(_safe_float(agg.get("windows", 0.0), default=0.0))),
                        "stability_score": _safe_float(agg.get("stability_score", 0.0)),
                        "avg_turnover": _safe_float(agg.get("avg_turnover", 0.0)),
                        "avg_overlap": _safe_float(agg.get("avg_overlap", 0.0)),
                        "median_holding_days": _safe_float(agg.get("median_holding_days", 0.0)),
                        "avg_assets_per_day": _safe_float(agg.get("avg_assets_per_day", 0.0)),
                        "avg_txn_cost_per_rebalance": _safe_float(agg.get("avg_txn_cost_per_rebalance", 0.0)),
                    }
                )
        elif otype == "model_promotion":
            best_model = str(data.get("best_model", "")).strip()
            score_obj = data.get("score", 0.0)
            if isinstance(score_obj, dict):
                candidate_score = _safe_float(score_obj.get("candidate_score", score_obj.get("raw_score", 0.0)))
            else:
                candidate_score = _safe_float(score_obj)
        elif otype == "ic_diagnostics":
            ic_diag = {
                "n_features_input": int(round(_safe_float(data.get("n_features_input", 0.0), default=0.0))),
                "n_features_selected": int(round(_safe_float(data.get("n_features_selected", 0.0), default=0.0))),
                "n_features_after_prune": int(round(_safe_float(data.get("n_features_after_prune", 0.0), default=0.0))),
                "top_features": list(data.get("top_features", [])),
                "decay_summary_selected_features": dict(data.get("decay_summary_selected_features", {}) or {}),
            }

    model_rows = sorted(
        model_rows,
        key=lambda x: (_safe_float(x.get("ic", 0.0)), _safe_float(x.get("sharpe", 0.0))),
        reverse=True,
    )
    return {
        "model_metrics": model_rows,
        "best_model": best_model,
        "candidate_score": candidate_score,
        "ic_diagnostics": ic_diag,
        "skipped": skipped,
        "skip_reason": skip_reason,
    }


def _print_run_horizon_summary(results: Sequence[Dict[str, Any]]) -> None:
    rows: List[Dict[str, Any]] = []
    for item in results:
        if int(item.get("return_code", 1)) != 0:
            continue
        phase = str(item.get("phase", "")).strip()
        horizon = item.get("target_horizon_days")
        regime = str(item.get("regime") or "all_data")
        cmet = item.get("cycle_metrics") if isinstance(item.get("cycle_metrics"), dict) else {}
        model_metrics = cmet.get("model_metrics") if isinstance(cmet.get("model_metrics"), list) else []
        if not model_metrics:
            continue
        top = sorted(
            [x for x in model_metrics if isinstance(x, dict)],
            key=lambda x: (_safe_float(x.get("ic", 0.0)), _safe_float(x.get("sharpe", 0.0))),
            reverse=True,
        )[0]
        rows.append(
            {
                "phase": phase,
                "horizon": horizon,
                "regime": regime,
                "model": str(top.get("model", "")),
                "ic": _safe_float(top.get("ic", 0.0)),
                "sharpe": _safe_float(top.get("sharpe", 0.0)),
                "dd": _safe_float(top.get("dd", 0.0)),
            }
        )
    if not rows:
        return
    rows = sorted(rows, key=lambda x: (x["ic"], x["sharpe"]), reverse=True)
    print("[full-stack] horizon sweep ranking (top by IC per run item)")
    for row in rows:
        print(
            "[full-stack] rank "
            f"phase={row['phase']} h={row['horizon']} regime={row['regime']} "
            f"model={row['model']} ic={row['ic']:.4f} sharpe={row['sharpe']:.4f} dd={row['dd']:.4f}"
        )


def _build_env(args: argparse.Namespace) -> Dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "LOKY_MAX_CPU_COUNT": str(max(1, int(args.max_cpu_cores))),
            "OMP_NUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "OPENBLAS_NUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "MKL_NUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "NUMEXPR_NUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "VECLIB_MAXIMUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "TORCH_NUM_THREADS": str(max(1, int(args.max_blas_threads))),
            "TORCH_NUM_INTEROP_THREADS": "1",
            "NORTHSTAR_LOW_RESOURCE_PROFILE": "1" if bool(args.keep_low_resource_profile) else "0",
            "NORTHSTAR_DISABLE_MPS": "0" if bool(args.enable_mps) else "1",
        }
    )
    return env


def _apply_global_dataset_overrides(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    sched = out.setdefault("scheduling", {})
    hr = out.setdefault("historical_research", {})
    ds = hr.setdefault("dataset", {})
    training = hr.setdefault("training", {})
    # Keep low-resource mode behavior consistent across controller + dataset manager.
    # The runner already exports NORTHSTAR_LOW_RESOURCE_PROFILE, so mirror that choice
    # into config to avoid hidden dataset caps when the env profile is disabled.
    low_resource_requested = bool(args.keep_low_resource_profile)
    hr["low_resource_mode"] = bool(low_resource_requested)
    ds["low_resource_mode"] = bool(low_resource_requested)
    if bool(args.run_during_market_hours):
        sched["run_during_market_hours"] = True
    if bool(args.production_100d):
        hr["enable_deep_models"] = False
        hr["enable_ensemble"] = False
        hr["enabled_models"] = ["lightgbm", "xgboost", "catboost"]
        hr.setdefault("autonomous_exploration", {})["enabled"] = False
        hr["candidate_acceptance_threshold"] = float(max(0.65, float(hr.get("candidate_acceptance_threshold", 0.65))))
        ds["target_market_residualize"] = True
        ds["target_residual_window_days"] = int(ds.get("target_residual_window_days", 252))
        ds["target_residual_min_obs"] = int(ds.get("target_residual_min_obs", 80))
        ic_cfg0 = hr.setdefault("ic_diagnostics", {})
        ic_cfg0["enabled"] = True
        ic_cfg0["prune_features"] = True
        ic_cfg0["horizons"] = [5, 10, 20, 40, 60, 80, 100]
        ic_cfg0["min_abs_ic"] = float(ic_cfg0.get("min_abs_ic", 0.015))
        ic_cfg0["min_sign_consistency"] = float(ic_cfg0.get("min_sign_consistency", 0.60))
        ic_cfg0["min_keep_features"] = int(ic_cfg0.get("min_keep_features", 15))
        ic_cfg0["max_keep_features"] = int(ic_cfg0.get("max_keep_features", 30))
        ic_cfg0["max_regimes_to_report"] = int(ic_cfg0.get("max_regimes_to_report", 4))
        ic_cfg0["min_regime_days"] = int(ic_cfg0.get("min_regime_days", 30))
        port0 = hr.setdefault("portfolio_construction", {})
        port0["long_short_quantile"] = float(port0.get("long_short_quantile", 0.15))
        port0["min_assets_per_day"] = int(port0.get("min_assets_per_day", 10))
        port0["max_weight_per_asset"] = float(port0.get("max_weight_per_asset", 0.08))
        port0["use_vol_scaling"] = True
        port0["rebalance_frequency_days"] = int(port0.get("rebalance_frequency_days", 5))
        gate0 = hr.setdefault("structural_promotion_gate", {})
        gate0["enabled"] = True
        gate0["min_peak_horizon"] = float(gate0.get("min_peak_horizon", 80))
        gate0["min_half_life_horizon"] = float(gate0.get("min_half_life_horizon", 80))
        gate0["min_monotonicity_score"] = float(gate0.get("min_monotonicity_score", 0.80))
        gate0["min_peak_ic"] = float(gate0.get("min_peak_ic", 0.05))

    if args.dataset_max_rows is not None:
        ds["max_rows"] = int(args.dataset_max_rows)
    if args.dataset_max_tickers is not None:
        ds["max_tickers"] = int(args.dataset_max_tickers)
    if args.dataset_lookback_days is not None:
        ds["lookback_days"] = int(args.dataset_lookback_days)
    if args.dataset_start_date is not None:
        ds["start_date"] = str(args.dataset_start_date)
    if args.dataset_end_date is not None:
        ds["end_date"] = str(args.dataset_end_date)
    if bool(args.target_market_residualize):
        ds["target_market_residualize"] = True
    if args.target_residual_window_days is not None:
        ds["target_residual_window_days"] = int(args.target_residual_window_days)
    if args.target_residual_min_obs is not None:
        ds["target_residual_min_obs"] = int(args.target_residual_min_obs)
    ic_cfg = hr.setdefault("ic_diagnostics", {})
    if bool(args.enable_ic_diagnostics):
        ic_cfg["enabled"] = True
    if bool(args.prune_features_by_ic):
        ic_cfg["prune_features"] = True
    if args.ic_min_abs is not None:
        ic_cfg["min_abs_ic"] = float(args.ic_min_abs)
    if args.ic_min_sign_consistency is not None:
        ic_cfg["min_sign_consistency"] = float(args.ic_min_sign_consistency)
    if args.ic_min_t_stat is not None:
        ic_cfg["min_t_stat"] = float(args.ic_min_t_stat)
    if args.ic_min_keep_features is not None:
        ic_cfg["min_keep_features"] = int(args.ic_min_keep_features)
    if args.ic_max_keep_features is not None:
        ic_cfg["max_keep_features"] = int(args.ic_max_keep_features)
    if args.ic_max_features_to_analyze is not None:
        ic_cfg["max_features_to_analyze"] = int(args.ic_max_features_to_analyze)
    if args.ic_max_regimes_to_report is not None:
        ic_cfg["max_regimes_to_report"] = int(args.ic_max_regimes_to_report)
    if args.ic_min_regime_days is not None:
        ic_cfg["min_regime_days"] = int(args.ic_min_regime_days)
    if args.ic_horizons is not None:
        ic_cfg["horizons"] = _parse_horizons(args.ic_horizons)

    port = hr.setdefault("portfolio_construction", {})
    if args.long_short_quantile is not None:
        port["long_short_quantile"] = float(args.long_short_quantile)
    if args.min_assets_per_day is not None:
        port["min_assets_per_day"] = int(args.min_assets_per_day)
    if args.max_weight_per_asset is not None:
        port["max_weight_per_asset"] = float(args.max_weight_per_asset)
    if bool(args.disable_vol_scaling):
        port["use_vol_scaling"] = False
    if args.rebalance_frequency_days is not None:
        port["rebalance_frequency_days"] = int(args.rebalance_frequency_days)
    if bool(args.sector_neutralize):
        port["sector_neutralize"] = True
    if args.max_sector_weight is not None:
        port["max_sector_weight"] = float(args.max_sector_weight)
    if args.transaction_cost_bps_per_side is not None:
        port["transaction_cost_bps_per_side"] = float(args.transaction_cost_bps_per_side)

    if args.train_end_date is not None:
        training["holdout_train_end_date"] = str(args.train_end_date)
    if args.test_start_date is not None:
        training["holdout_test_start_date"] = str(args.test_start_date)
    if args.test_end_date is not None:
        training["holdout_test_end_date"] = str(args.test_end_date)
    if args.holdout_valid_periods is not None:
        training["holdout_valid_periods"] = int(args.holdout_valid_periods)
    if args.holdout_min_train_periods is not None:
        training["holdout_min_train_periods"] = int(args.holdout_min_train_periods)

    gate = hr.setdefault("structural_promotion_gate", {})
    if bool(args.enable_structural_promotion_gate):
        gate["enabled"] = True
    if bool(args.disable_structural_promotion_gate):
        gate["enabled"] = False
    if args.promotion_min_peak_horizon is not None:
        gate["min_peak_horizon"] = float(args.promotion_min_peak_horizon)
    if args.promotion_min_half_life_horizon is not None:
        gate["min_half_life_horizon"] = float(args.promotion_min_half_life_horizon)
    if args.promotion_min_monotonicity is not None:
        gate["min_monotonicity_score"] = float(args.promotion_min_monotonicity)
    if args.promotion_min_peak_ic is not None:
        gate["min_peak_ic"] = float(args.promotion_min_peak_ic)
    return out


def _apply_regime_window(cfg: Dict[str, Any], *, start_date: str, end_date: str) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    ds = out.setdefault("historical_research", {}).setdefault("dataset", {})
    ds["start_date"] = str(start_date)
    ds["end_date"] = str(end_date)
    # Regime slices can be intentionally narrow; relax strict row gates for slice mode.
    mins = dict(ds.get("artifact_min_rows", {}) or {})
    mins["prices"] = min(int(mins.get("prices", 2000)), 40)
    mins["fundamentals"] = min(int(mins.get("fundamentals", 400)), 20)
    mins["macro"] = min(int(mins.get("macro", 200)), 20)
    mins["valuation_posterior"] = min(int(mins.get("valuation_posterior", 400)), 20)
    mins["sentiment_company"] = min(int(mins.get("sentiment_company", 100)), 10)
    mins["sentiment_market"] = min(int(mins.get("sentiment_market", 5)), 2)
    ds["artifact_min_rows"] = mins
    ds["strict_required_artifacts"] = ["prices"]
    return out


def _load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_yaml_mapping:{path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequential full-stack research runner with process isolation.")
    parser.add_argument("--base-config", type=Path, default=PROJECT_ROOT / "config/research_policy.yaml")
    parser.add_argument(
        "--production-100d",
        action="store_true",
        help="Apply 100-day production profile defaults (residualized target, weekly rebalance, structural promotion gate).",
    )
    parser.add_argument("--phases", default="classical,deep,walkforward,ensemble")
    parser.add_argument(
        "--run-during-market-hours",
        action="store_true",
        help="Override scheduling guard and allow research runs during market hours.",
    )
    parser.add_argument(
        "--target-horizons",
        default=None,
        help="Comma-separated forecast horizons in days (e.g. 5,20,60). Default uses base config horizon.",
    )
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--cooldown-seconds", type=float, default=15.0)
    parser.add_argument("--model-cooldown-seconds", type=float, default=6.0)
    parser.add_argument("--classical-windows", type=int, default=4)
    parser.add_argument("--deep-windows", type=int, default=3)
    parser.add_argument("--walkforward-windows", type=int, default=8)
    parser.add_argument("--walkforward-window-start", type=int, default=0)
    parser.add_argument("--ensemble-windows", type=int, default=2)
    parser.add_argument("--exploration-windows", type=int, default=2)
    parser.add_argument("--exploration-variants", type=int, default=1)
    parser.add_argument("--dataset-max-rows", type=int, default=None)
    parser.add_argument("--dataset-max-tickers", type=int, default=None)
    parser.add_argument("--dataset-lookback-days", type=int, default=None)
    parser.add_argument("--dataset-start-date", type=str, default=None)
    parser.add_argument("--dataset-end-date", type=str, default=None)
    parser.add_argument("--target-market-residualize", action="store_true")
    parser.add_argument("--target-residual-window-days", type=int, default=None)
    parser.add_argument("--target-residual-min-obs", type=int, default=None)
    parser.add_argument("--train-end-date", type=str, default=None)
    parser.add_argument("--test-start-date", type=str, default=None)
    parser.add_argument("--test-end-date", type=str, default=None)
    parser.add_argument("--holdout-valid-periods", type=int, default=None)
    parser.add_argument("--holdout-min-train-periods", type=int, default=None)
    parser.add_argument("--enable-ic-diagnostics", action="store_true")
    parser.add_argument("--prune-features-by-ic", action="store_true")
    parser.add_argument("--ic-min-abs", type=float, default=None)
    parser.add_argument("--ic-min-sign-consistency", type=float, default=None)
    parser.add_argument("--ic-min-t-stat", type=float, default=None)
    parser.add_argument("--ic-min-keep-features", type=int, default=None)
    parser.add_argument("--ic-max-keep-features", type=int, default=None)
    parser.add_argument("--ic-max-features-to-analyze", type=int, default=None)
    parser.add_argument("--ic-max-regimes-to-report", type=int, default=None)
    parser.add_argument("--ic-min-regime-days", type=int, default=None)
    parser.add_argument(
        "--ic-horizons",
        default=None,
        help="Comma-separated IC diagnostic horizons in days (e.g. 5,10,20).",
    )
    parser.add_argument("--long-short-quantile", type=float, default=None)
    parser.add_argument("--min-assets-per-day", type=int, default=None)
    parser.add_argument("--max-weight-per-asset", type=float, default=None)
    parser.add_argument("--rebalance-frequency-days", type=int, default=None)
    parser.add_argument("--sector-neutralize", action="store_true")
    parser.add_argument("--max-sector-weight", type=float, default=None)
    parser.add_argument("--transaction-cost-bps-per-side", type=float, default=None)
    parser.add_argument("--disable-vol-scaling", action="store_true")
    parser.add_argument("--enable-structural-promotion-gate", action="store_true")
    parser.add_argument("--disable-structural-promotion-gate", action="store_true")
    parser.add_argument("--promotion-min-peak-horizon", type=float, default=None)
    parser.add_argument("--promotion-min-half-life-horizon", type=float, default=None)
    parser.add_argument("--promotion-min-monotonicity", type=float, default=None)
    parser.add_argument("--promotion-min-peak-ic", type=float, default=None)
    parser.add_argument("--max-cpu-cores", type=int, default=1)
    parser.add_argument("--max-blas-threads", type=int, default=1)
    parser.add_argument("--enable-hyperopt", action="store_true")
    parser.add_argument("--hyperopt-calls", type=int, default=8)
    parser.add_argument("--hyperopt-max-windows", type=int, default=1)
    parser.add_argument("--evaluation-max-windows", type=int, default=None)
    parser.add_argument("--max-models-weekday", type=int, default=None)
    parser.add_argument("--max-models-weekend", type=int, default=None)
    parser.add_argument("--rf-estimators", type=int, default=None)
    parser.add_argument("--lstm-epochs", type=int, default=None)
    parser.add_argument("--tcn-epochs", type=int, default=None)
    parser.add_argument("--transformer-epochs", type=int, default=None)
    parser.add_argument("--transformer-d-model", type=int, default=None)
    parser.add_argument("--enable-mps", action="store_true")
    parser.add_argument("--keep-low-resource-profile", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--keep-temp-configs", action="store_true")
    parser.add_argument("--regime", type=str, default=None)
    parser.add_argument("--all-regimes", action="store_true")
    args = parser.parse_args()
    if bool(args.enable_structural_promotion_gate) and bool(args.disable_structural_promotion_gate):
        raise ValueError("conflicting_structural_gate_flags")

    base_path = Path(args.base_config)
    if not base_path.is_absolute():
        base_path = (PROJECT_ROOT / base_path).resolve()
    if not base_path.exists():
        raise FileNotFoundError(f"base_config_missing:{base_path}")

    phase_list = _parse_phases(args.phases)
    horizon_list = _parse_horizons(args.target_horizons)
    base_cfg = _load_yaml(base_path)
    base_cfg = _apply_global_dataset_overrides(base_cfg, args)

    regimes_to_run = []
    if args.all_regimes:
        regimes_to_run = list_regimes()
    elif args.regime:
        regime = get_regime(args.regime)
        if regime is None:
            raise ValueError(f"unknown_regime:{args.regime}")
        regimes_to_run = [regime]
    else:
        regimes_to_run = [None]

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = PROJECT_ROOT / "data/research/full_stack_runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "base_config": str(base_path),
        "phases": phase_list,
        "target_horizons": horizon_list if horizon_list else [base_cfg.get("historical_research", {}).get("dataset", {}).get("target_horizon_days", 5)],
        "regime_mode": "all" if args.all_regimes else ("single" if args.regime else "none"),
        "results": [],
    }

    env = _build_env(args)
    runner = PROJECT_ROOT / "scripts/run_research_worker.py"

    horizons_to_run = horizon_list if horizon_list else [None]
    for horizon_days in horizons_to_run:
        for regime in regimes_to_run:
            for phase in phase_list:
                before_cycles = glob.glob(str(PROJECT_ROOT / "data/research/research_cycle_*.json"))
                phase_cfg = copy.deepcopy(base_cfg)
                if regime is not None:
                    phase_cfg = _apply_regime_window(
                        phase_cfg,
                        start_date=regime.start_date,
                        end_date=regime.end_date,
                    )
                if horizon_days is not None:
                    phase_cfg.setdefault("historical_research", {}).setdefault("dataset", {})["target_horizon_days"] = int(horizon_days)
                phase_cfg = _deep_merge(
                    phase_cfg,
                    _phase_overrides(
                        phase=phase,
                        args=args,
                        base_hr=dict(phase_cfg.get("historical_research", {})),
                    ),
                )

                h_tag = f"h{int(horizon_days)}d_" if horizon_days is not None else ""
                tmp_path = Path(tempfile.gettempdir()) / f"northstar_full_stack_{run_ts}_{h_tag}{phase}.yaml"
                if regime is not None:
                    tmp_path = Path(tempfile.gettempdir()) / f"northstar_full_stack_{run_ts}_{h_tag}{regime.name}_{phase}.yaml"
                tmp_path.write_text(yaml.safe_dump(phase_cfg, sort_keys=False))

                t0 = time.time()
                cmd = [
                    sys.executable,
                    str(runner),
                    "--once",
                    "--config",
                    str(tmp_path),
                    "--log-level",
                    str(args.log_level),
                ]
                horizon_label = (
                    str(horizon_days)
                    if horizon_days is not None
                    else str(
                        phase_cfg.get("historical_research", {})
                        .get("dataset", {})
                        .get("target_horizon_days", "default")
                    )
                )
                print(
                    f"[full-stack] phase={phase} horizon_days={horizon_label} "
                    f"regime={regime.name if regime else 'all_data'} config={tmp_path}"
                )
                proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, check=False)
                elapsed = float(time.time() - t0)

                after_cycles = glob.glob(str(PROJECT_ROOT / "data/research/research_cycle_*.json"))
                cycle_file = _collect_cycle_file(before_cycles, after_cycles)
                cycle_metrics = _extract_cycle_metrics(cycle_file)
                item = {
                    "phase": phase,
                    "target_horizon_days": int(horizon_days) if horizon_days is not None else None,
                    "regime": regime.name if regime else None,
                    "start_date": regime.start_date if regime else None,
                    "end_date": regime.end_date if regime else None,
                    "return_code": int(proc.returncode),
                    "duration_seconds": elapsed,
                    "cycle_file": cycle_file,
                    "cycle_metrics": cycle_metrics,
                }
                summary["results"].append(item)

                model_metrics = list(cycle_metrics.get("model_metrics", []))
                for row in model_metrics:
                    print(
                        "[full-stack] metrics "
                        f"h={horizon_label} phase={phase} regime={regime.name if regime else 'all_data'} "
                        f"model={row.get('model')} ic={_safe_float(row.get('ic')):.4f} "
                        f"sharpe={_safe_float(row.get('sharpe')):.4f} dd={_safe_float(row.get('dd')):.4f} "
                        f"turnover={_safe_float(row.get('avg_turnover')):.4f} "
                        f"hold_days={_safe_float(row.get('median_holding_days')):.2f}"
                    )

                best_model = str(cycle_metrics.get("best_model", "")).strip()
                if best_model:
                    print(
                        "[full-stack] decision "
                        f"h={horizon_label} phase={phase} regime={regime.name if regime else 'all_data'} "
                        f"best_model={best_model} score={_safe_float(cycle_metrics.get('candidate_score')):.4f}"
                    )

                if bool(cycle_metrics.get("skipped", False)):
                    print(
                        "[full-stack] skipped "
                        f"h={horizon_label} phase={phase} regime={regime.name if regime else 'all_data'} "
                        f"reason={str(cycle_metrics.get('skip_reason', '') or 'unspecified')}"
                    )

                if not cycle_file:
                    print(
                        "[full-stack] warning "
                        f"h={horizon_label} phase={phase} regime={regime.name if regime else 'all_data'} "
                        "no_new_cycle_artifact"
                    )

                ic_diag = cycle_metrics.get("ic_diagnostics", {})
                if isinstance(ic_diag, dict) and int(ic_diag.get("n_features_after_prune", 0)) > 0:
                    print(
                        "[full-stack] ic-gate "
                        f"h={horizon_label} phase={phase} regime={regime.name if regime else 'all_data'} "
                        f"features={int(ic_diag.get('n_features_after_prune', 0))}/"
                        f"{int(ic_diag.get('n_features_input', 0))}"
                    )

                if not args.keep_temp_configs:
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                if proc.returncode != 0 and not args.continue_on_error:
                    summary["failed"] = True
                    summary["failed_phase"] = phase
                    summary["failed_regime"] = regime.name if regime else None
                    summary["failed_target_horizon_days"] = int(horizon_days) if horizon_days is not None else None
                    summary["completed_at"] = datetime.now().isoformat()
                    out_path = run_dir / f"full_stack_run_{run_ts}.json"
                    out_path.write_text(json.dumps(summary, indent=2))
                    print(f"[full-stack] failed phase={phase} rc={proc.returncode} summary={out_path}")
                    return int(proc.returncode)

                if args.cooldown_seconds > 0:
                    time.sleep(float(args.cooldown_seconds))

    summary["completed_at"] = datetime.now().isoformat()
    summary["failed"] = False
    _print_run_horizon_summary(summary.get("results", []))
    out_path = run_dir / f"full_stack_run_{run_ts}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"[full-stack] completed summary={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
