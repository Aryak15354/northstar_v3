#!/usr/bin/env python3
"""Run a focused regime-conditional IC audit for one research model."""

from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.research.research_controller import ResearchController
from src.research.external_data_interfaces import audit_external_data_interfaces
from src.research.regime_engine import RegimeEngine


def _load_cfg(path: Path) -> Dict[str, Any]:
    return dict(yaml.safe_load(path.read_text()) or {})


def _normalize_policy_cfg(raw_cfg: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalize policy shape to the controller contract (historical_research payload)."""
    cfg = dict(raw_cfg or {})
    if isinstance(cfg.get("historical_research"), dict):
        hr = copy.deepcopy(dict(cfg.get("historical_research", {})))
        if "low_resource_mode" in cfg and "low_resource_mode" not in hr:
            hr["low_resource_mode"] = cfg.get("low_resource_mode")
        source = "historical_research"
        return hr, {"config_shape": source}
    return copy.deepcopy(cfg), {"config_shape": "top_level"}


def _set_single_core_caps(max_cores: int, max_blas_threads: int) -> None:
    c = max(1, int(max_cores))
    b = max(1, int(max_blas_threads))
    os.environ["LOKY_MAX_CPU_COUNT"] = str(c)
    os.environ["OMP_NUM_THREADS"] = str(b)
    os.environ["OPENBLAS_NUM_THREADS"] = str(b)
    os.environ["MKL_NUM_THREADS"] = str(b)
    os.environ["NUMEXPR_NUM_THREADS"] = str(b)


def _apply_overrides(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    out = copy.deepcopy(dict(cfg))
    out.setdefault("runtime_policy", {})["pause_scheduled_until_burn_in"] = False
    # Default diagnostics mode: disable low-resource clamps unless explicitly enabled.
    if bool(args.allow_low_resource_profile):
        out["low_resource_mode"] = "auto"
    else:
        out["low_resource_mode"] = "disabled"

    training = out.setdefault("training", {})
    if args.max_windows is not None:
        training["max_windows"] = int(args.max_windows)
    if args.start_window is not None:
        training["start_window"] = int(args.start_window)
    if args.train_periods is not None:
        training["train_periods"] = int(args.train_periods)
    if args.valid_periods is not None:
        training["valid_periods"] = int(args.valid_periods)
    if args.test_periods is not None:
        training["test_periods"] = int(args.test_periods)
    if args.step_periods is not None:
        training["step_periods"] = int(args.step_periods)
    if args.min_tickers_per_date is not None:
        training["min_tickers_per_date"] = int(args.min_tickers_per_date)
    if args.holdout_train_end_date:
        training["holdout_train_end_date"] = str(args.holdout_train_end_date).strip()
    if args.holdout_test_start_date:
        training["holdout_test_start_date"] = str(args.holdout_test_start_date).strip()
    if args.holdout_test_end_date:
        training["holdout_test_end_date"] = str(args.holdout_test_end_date).strip()
    if args.holdout_valid_periods is not None:
        training["holdout_valid_periods"] = int(args.holdout_valid_periods)
    if args.holdout_min_train_periods is not None:
        training["holdout_min_train_periods"] = int(args.holdout_min_train_periods)

    dataset = out.setdefault("dataset", {})
    if bool(args.allow_low_resource_profile):
        dataset["low_resource_mode"] = "auto"
    else:
        dataset["low_resource_mode"] = "disabled"
    if args.target_horizon_days is not None:
        dataset["target_horizon_days"] = int(args.target_horizon_days)
    if args.dataset_max_rows is not None:
        dataset["max_rows"] = int(args.dataset_max_rows)
    if args.dataset_max_tickers is not None:
        dataset["max_tickers"] = int(args.dataset_max_tickers)
    if args.dataset_lookback_days is not None:
        dataset["lookback_days"] = int(args.dataset_lookback_days)
    if args.target_mode:
        dataset["target_mode"] = str(args.target_mode).strip().lower()
    if bool(args.target_sector_residualize):
        dataset["target_sector_residualize"] = True
    if bool(args.target_market_residualize):
        dataset["target_market_residualize"] = True
    if bool(args.target_cross_sectional_zscore):
        dataset["target_cross_sectional_zscore"] = True
    if bool(args.feature_cross_sectional_zscore):
        dataset["feature_cross_sectional_zscore"] = True
    if bool(args.disable_macro_features):
        dataset["enable_macro_features"] = False
    if bool(args.enable_macro_features):
        dataset["enable_macro_features"] = True

    icd = out.setdefault("ic_diagnostics", {})
    icd["enabled"] = True
    icd["scope_mode"] = "train_only"
    if args.ic_min_abs is not None:
        icd["min_abs_ic"] = float(args.ic_min_abs)
    if args.ic_min_sign_consistency is not None:
        icd["min_sign_consistency"] = float(args.ic_min_sign_consistency)
    if args.prune_features_by_ic:
        icd["prune_features"] = True
    if args.max_keep_features is not None:
        icd["max_keep_features"] = int(args.max_keep_features)

    pc = out.setdefault("portfolio_construction", {})
    if args.transaction_cost_bps is not None:
        pc["transaction_cost_bps_per_side"] = float(args.transaction_cost_bps)
    if args.rebalance_frequency_days is not None:
        pc["rebalance_frequency_days"] = int(args.rebalance_frequency_days)
    if args.label_embargo_periods is not None:
        pc["label_embargo_periods"] = int(args.label_embargo_periods)
    if args.long_short_quantile is not None:
        pc["long_short_quantile"] = float(args.long_short_quantile)
    if args.max_weight_per_asset is not None:
        pc["max_weight_per_asset"] = float(args.max_weight_per_asset)
    if args.portfolio_mode:
        pc["portfolio_mode"] = str(args.portfolio_mode).strip().lower()
    if args.prediction_transform:
        pc["prediction_transform"] = str(args.prediction_transform).strip().lower()
    if args.prediction_rank_power is not None:
        pc["prediction_rank_power"] = float(args.prediction_rank_power)
    if args.prediction_tanh_scale is not None:
        pc["prediction_tanh_scale"] = float(args.prediction_tanh_scale)
    if bool(args.prediction_sector_neutralize):
        pc["prediction_sector_neutralize"] = True
    if args.prediction_neutralize_factors:
        pc["prediction_neutralize_factors"] = _parse_csv_list(args.prediction_neutralize_factors)
    if bool(args.no_use_vol_scaling):
        pc["use_vol_scaling"] = False
    elif bool(args.use_vol_scaling):
        pc["use_vol_scaling"] = True
    if bool(args.sector_neutralize):
        pc["sector_neutralize"] = True
    if args.max_sector_weight is not None:
        pc["max_sector_weight"] = float(args.max_sector_weight)
    if args.regime_exposure_scale:
        pc["regime_exposure_scales"] = _parse_regime_scale_map(args.regime_exposure_scale)

    return out


def _select_model(controller: ResearchController, model_name: str) -> Tuple[str, Dict[str, Any]]:
    want = controller._normalize_model_name(model_name)  # pylint: disable=protected-access
    specs = dict(controller._model_specs())  # pylint: disable=protected-access
    if want in specs:
        return want, dict(specs[want] or {})
    # Fallback to first configured model.
    for name, params in controller._model_specs():  # pylint: disable=protected-access
        return str(name), dict(params or {})
    raise ValueError("No model specs available in configuration.")


def _usable_regime_values(series: pd.Series) -> list[str]:
    vals = (
        series.astype("string")
        .fillna("")
        .str.strip()
        .replace({"<NA>": "", "nan": "", "None": "", "unknown": ""})
    )
    out = sorted([str(x) for x in vals.unique().tolist() if str(x)])
    return out


def _ensure_regime_column(dataset: Any, regime_col: str = "regime") -> str:
    """Return a regime column with at least 2 usable states; derive if needed."""
    frame = dataset.frame.copy()
    if regime_col in frame.columns:
        usable = _usable_regime_values(frame[regime_col])
        if len(usable) >= 2:
            dataset.frame = frame
            return regime_col

    if "date" not in frame.columns:
        dataset.frame = frame
        return regime_col

    d = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.assign(date=d).dropna(subset=["date"]).copy()
    if frame.empty:
        dataset.frame = frame
        return regime_col
    engine = RegimeEngine(
        {
            "regime_labels_path": str(
                dataset.metadata.get("regime_labels_path", "data/processed/regime_labels.parquet")
            )
        }
    )
    start = pd.to_datetime(frame["date"], errors="coerce").min()
    end = pd.to_datetime(frame["date"], errors="coerce").max()
    reg_series = engine.get_regime_series(start, end)

    if reg_series.empty:
        close_col = next((c for c in ["close", "Close", "adj_close", "Adj Close"] if c in frame.columns), None)
        prices_for_engine = frame[["date"]].copy()
        if "ticker" in frame.columns:
            prices_for_engine["ticker"] = frame["ticker"].astype(str)
        if close_col is not None:
            prices_for_engine["Close"] = pd.to_numeric(frame[close_col], errors="coerce")
        else:
            proxy = pd.to_numeric(frame.get("vol_20d"), errors="coerce").fillna(method="ffill").fillna(0.0)
            prices_for_engine["Close"] = (100.0 + proxy.rank(method="first")).to_numpy()
        try:
            _ = engine.build_historical_regimes(prices_df=prices_for_engine, macro_df=None)
            reg_series = engine.get_regime_series(start, end)
        except Exception:
            reg_series = pd.Series(dtype=object)

    if reg_series.empty:
        frame["regime_audit"] = "unknown"
        dataset.frame = frame
        return "regime_audit"

    reg_map = pd.Series(reg_series.astype(str).to_numpy(), index=pd.DatetimeIndex(reg_series.index).normalize())
    frame["regime_audit"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize().map(reg_map).fillna("unknown").astype(str)
    dataset.frame = frame
    return "regime_audit"


def _parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    out = []
    for part in str(raw).split(","):
        s = str(part).strip()
        if s:
            out.append(s)
    return out


def _parse_regime_scale_map(raw: str | None) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not raw:
        return out
    for part in str(raw).split(","):
        token = str(part).strip()
        if not token or ":" not in token:
            continue
        k, v = token.split(":", 1)
        key = str(k).strip()
        if not key:
            continue
        try:
            out[key] = float(v)
        except Exception:
            continue
    return out


def _parse_patterns(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [str(x).strip() for x in str(raw).split(",") if str(x).strip()]


def _canonical_sector_token(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    s = " ".join(s.split())
    alias = {
        "it": "information technology",
        "technology": "information technology",
        "tech": "information technology",
        "information technology": "information technology",
    }
    return alias.get(s, s)


def _apply_sector_filter(dataset: Any, sector_filters: List[str]) -> None:
    if not sector_filters or dataset.frame.empty:
        return
    sector_col = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in dataset.frame.columns), None)
    if sector_col is None:
        return
    wanted = {_canonical_sector_token(x) for x in sector_filters}
    sec_token = dataset.frame[sector_col].astype(str).map(_canonical_sector_token)
    keep = sec_token.isin(wanted)
    dataset.frame = dataset.frame.loc[keep].copy()
    _rebuild_xy(dataset)


def _rebuild_xy(dataset: Any) -> None:
    feat_names = [str(f) for f in list(dataset.feature_names or []) if str(f) in dataset.frame.columns]
    if feat_names:
        dataset.feature_names = feat_names
        dataset.X = dataset.frame[feat_names].to_numpy(dtype=float)
    target_col = str(dataset.metadata.get("target_col", "forward_return_5d"))
    if target_col in dataset.frame.columns:
        dataset.y = pd.to_numeric(dataset.frame[target_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    dataset.metadata["n_rows"] = int(len(dataset.frame))
    dataset.metadata["n_features"] = int(len(dataset.feature_names or []))


def _apply_feature_name_filter(dataset: Any, include_patterns: List[str], exclude_patterns: List[str]) -> None:
    feats = [str(f) for f in list(dataset.feature_names or [])]
    if not feats:
        return
    inc = [p.lower() for p in include_patterns]
    exc = [p.lower() for p in exclude_patterns]
    keep: List[str] = []
    for f in feats:
        fl = f.lower()
        if inc and not any(p in fl for p in inc):
            continue
        if exc and any(p in fl for p in exc):
            continue
        if f in dataset.frame.columns:
            keep.append(f)
    if keep:
        dataset.feature_names = keep
        dataset.X = dataset.frame[keep].to_numpy(dtype=float)
        dataset.metadata["n_features"] = int(len(keep))


def _apply_liquidity_bucket_filter(dataset: Any, *, bucket: str, liquidity_col: str = "") -> None:
    b = str(bucket or "all").strip().lower()
    if b not in {"top", "mid", "bottom"}:
        return
    frame = dataset.frame
    if frame.empty or "date" not in frame.columns:
        return
    candidate_cols = [str(liquidity_col).strip()] if str(liquidity_col).strip() else []
    candidate_cols += ["liquidity", "avg_dollar_volume_20d", "dollar_volume_20d", "dollar_volume", "adv_20d", "volume"]
    col = next((c for c in candidate_cols if c in frame.columns), None)
    if col is None:
        return
    v = pd.to_numeric(frame[col], errors="coerce")
    d = pd.to_datetime(frame["date"], errors="coerce")
    r = v.groupby(d, sort=False).rank(method="average", pct=True)
    if b == "top":
        keep = r >= 0.7
    elif b == "bottom":
        keep = r <= 0.3
    else:
        keep = (r > 0.3) & (r < 0.7)
    dataset.frame = frame.loc[keep.fillna(False)].copy()
    _rebuild_xy(dataset)


def _apply_dispersion_bucket_filter(dataset: Any, *, bucket: str, dispersion_col: str = "ret_1d") -> None:
    b = str(bucket or "all").strip().lower()
    if b not in {"high", "low"}:
        return
    frame = dataset.frame
    if frame.empty or "date" not in frame.columns:
        return
    col = str(dispersion_col or "ret_1d").strip()
    if col not in frame.columns:
        return
    d = pd.to_datetime(frame["date"], errors="coerce")
    x = pd.to_numeric(frame[col], errors="coerce")
    daily = x.groupby(d, sort=False).std()
    med = float(pd.to_numeric(daily, errors="coerce").median()) if len(daily) else 0.0
    if b == "high":
        keep_dates = set(daily[daily >= med].index.tolist())
    else:
        keep_dates = set(daily[daily <= med].index.tolist())
    keep = d.isin(list(keep_dates))
    dataset.frame = frame.loc[keep.fillna(False)].copy()
    _rebuild_xy(dataset)


def main() -> int:
    ap = argparse.ArgumentParser(description="Focused regime IC split diagnostics")
    ap.add_argument("--base-config", required=True, help="Path to research policy YAML")
    ap.add_argument("--model", default="xgboost", help="Model name")
    ap.add_argument("--max-windows", type=int, default=3)
    ap.add_argument("--start-window", type=int, default=None)
    ap.add_argument("--target-horizon-days", type=int)
    ap.add_argument("--train-periods", type=int)
    ap.add_argument("--valid-periods", type=int)
    ap.add_argument("--test-periods", type=int)
    ap.add_argument("--step-periods", type=int)
    ap.add_argument("--min-tickers-per-date", type=int, default=None)
    ap.add_argument("--holdout-train-end-date", type=str, default="")
    ap.add_argument("--holdout-test-start-date", type=str, default="")
    ap.add_argument("--holdout-test-end-date", type=str, default="")
    ap.add_argument("--holdout-valid-periods", type=int, default=None)
    ap.add_argument("--holdout-min-train-periods", type=int, default=None)
    ap.add_argument("--dataset-max-rows", type=int, default=120000)
    ap.add_argument("--dataset-max-tickers", type=int, default=120)
    ap.add_argument("--dataset-lookback-days", type=int, default=2200)
    ap.add_argument("--allow-low-resource-profile", action="store_true")
    ap.add_argument("--disable-macro-features", action="store_true")
    ap.add_argument("--enable-macro-features", action="store_true")
    ap.add_argument("--target-mode", type=str, default="")
    ap.add_argument("--target-sector-residualize", action="store_true")
    ap.add_argument("--target-market-residualize", action="store_true")
    ap.add_argument("--target-cross-sectional-zscore", action="store_true")
    ap.add_argument("--feature-cross-sectional-zscore", action="store_true")
    ap.add_argument("--max-cpu-cores", type=int, default=1)
    ap.add_argument("--max-blas-threads", type=int, default=1)
    ap.add_argument("--prune-features-by-ic", action="store_true")
    ap.add_argument("--ic-min-abs", type=float, default=0.01)
    ap.add_argument("--ic-min-sign-consistency", type=float, default=0.55)
    ap.add_argument("--max-keep-features", type=int, default=None)
    ap.add_argument("--transaction-cost-bps", type=float, default=25.0)
    ap.add_argument("--rebalance-frequency-days", type=int, default=5)
    ap.add_argument("--label-embargo-periods", type=int, default=5)
    ap.add_argument("--long-short-quantile", type=float, default=None)
    ap.add_argument("--max-weight-per-asset", type=float, default=None)
    ap.add_argument("--use-vol-scaling", action="store_true")
    ap.add_argument("--no-use-vol-scaling", action="store_true")
    ap.add_argument("--prediction-transform", type=str, default="", choices=["raw", "zscore", "rank", "rank_power", "tanh"])
    ap.add_argument("--prediction-rank-power", type=float, default=None)
    ap.add_argument("--prediction-tanh-scale", type=float, default=None)
    ap.add_argument("--prediction-sector-neutralize", action="store_true")
    ap.add_argument("--prediction-neutralize-factors", type=str, default="")
    ap.add_argument(
        "--portfolio-mode",
        type=str,
        choices=["long_short", "long_only", "short_only"],
        default="long_short",
    )
    ap.add_argument("--sector-neutralize", action="store_true")
    ap.add_argument("--max-sector-weight", type=float, default=0.35)
    ap.add_argument("--active-regime", type=str, default="")
    ap.add_argument("--regime-scale", type=str, default="", help="CSV map e.g. high_vol|downtrend:1.3,default:1.0")
    ap.add_argument(
        "--regime-exposure-scale",
        type=str,
        default="",
        help="CSV map e.g. low_vol|downtrend:0.05,default:1.0 (applies to portfolio weights)",
    )
    ap.add_argument(
        "--invert-regimes",
        type=str,
        default="",
        help="Comma-separated regime names to invert signal in",
    )
    ap.add_argument("--sector-filter", type=str, default="", help="Comma-separated sector names to keep")
    ap.add_argument("--feature-include-patterns", type=str, default="", help="CSV substring filters for feature names")
    ap.add_argument("--feature-exclude-patterns", type=str, default="", help="CSV substring excludes for feature names")
    ap.add_argument("--liquidity-bucket", type=str, choices=["all", "top", "mid", "bottom"], default="all")
    ap.add_argument("--liquidity-col", type=str, default="")
    ap.add_argument("--dispersion-bucket", type=str, choices=["all", "high", "low"], default="all")
    ap.add_argument("--dispersion-col", type=str, default="ret_1d")
    ap.add_argument(
        "--output-json",
        default="data/results/research/reports/regime_ic_split_latest.json",
        help="Where to store structured output JSON",
    )
    args = ap.parse_args()

    _set_single_core_caps(args.max_cpu_cores, args.max_blas_threads)

    raw_cfg = _load_cfg(Path(args.base_config))
    cfg, cfg_meta = _normalize_policy_cfg(raw_cfg)
    cfg = _apply_overrides(cfg, args)
    req_training_cfg = dict(cfg.get("training", {}))
    req_windows = int(req_training_cfg.get("max_windows", 0) or 0)
    controller = ResearchController(config=cfg, project_root=REPO_ROOT)
    holdout_requested = bool(
        str(args.holdout_train_end_date or "").strip()
        or str(args.holdout_test_start_date or "").strip()
        or str(args.holdout_test_end_date or "").strip()
    )
    if holdout_requested:
        # Ensure holdout params are present on the pipeline even if config layers drop them.
        h_train = str(args.holdout_train_end_date or "").strip()
        h_test_start = str(args.holdout_test_start_date or "").strip()
        h_test_end = str(args.holdout_test_end_date or "").strip()
        if h_train:
            controller.pipeline.holdout_train_end_date = h_train
        if h_test_start:
            controller.pipeline.holdout_test_start_date = h_test_start
        if h_test_end:
            controller.pipeline.holdout_test_end_date = h_test_end
        if args.holdout_valid_periods is not None:
            controller.pipeline.holdout_valid_periods = int(args.holdout_valid_periods)
        if args.holdout_min_train_periods is not None:
            controller.pipeline.holdout_min_train_periods = int(args.holdout_min_train_periods)
        print(
            "[regime-ic] holdout_requested "
            f"train_end={controller.pipeline.holdout_train_end_date} "
            f"test_start={controller.pipeline.holdout_test_start_date} "
            f"test_end={controller.pipeline.holdout_test_end_date}"
        )
    eff_windows = int(getattr(controller.pipeline, "max_windows", 0) or 0)
    if req_windows > 0 and eff_windows != req_windows:
        print(f"[regime-ic][warn] requested_max_windows={req_windows} effective_max_windows={eff_windows}")

    dataset = controller.dataset_manager.build_research_dataset()
    dataset_rows = int(len(dataset.frame))
    dataset_tickers = int(dataset.frame["ticker"].astype(str).nunique()) if "ticker" in dataset.frame.columns else 0
    dataset_dates = int(pd.to_datetime(dataset.frame.get("date"), errors="coerce").dropna().nunique()) if "date" in dataset.frame.columns else 0
    sample_tickers = (
        sorted(dataset.frame["ticker"].astype(str).dropna().unique().tolist())[:10]
        if "ticker" in dataset.frame.columns
        else []
    )
    print(
        "[regime-ic] dataset_summary "
        f"config_shape={cfg_meta.get('config_shape')} rows={dataset_rows} "
        f"tickers={dataset_tickers} unique_dates={dataset_dates} "
        f"effective_max_tickers={dataset.metadata.get('effective_max_tickers', dataset.metadata.get('max_tickers'))} "
        f"effective_max_rows={dataset.metadata.get('effective_max_rows', dataset.metadata.get('max_rows'))} "
        f"low_resource_mode_effective={dataset.metadata.get('low_resource_mode_effective')}"
    )
    if sample_tickers:
        print(f"[regime-ic] sample_tickers={sample_tickers}")

    sector_col0 = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in dataset.frame.columns), None)
    if sector_col0 is not None and not dataset.frame.empty:
        labels = sorted(dataset.frame[sector_col0].astype(str).fillna("").str.strip().replace({"<NA>": ""}).unique().tolist())
        print(f"[regime-ic] sector_column={sector_col0} unique_sector_labels={labels}")

    _apply_feature_name_filter(
        dataset,
        include_patterns=_parse_patterns(args.feature_include_patterns),
        exclude_patterns=_parse_patterns(args.feature_exclude_patterns),
    )
    sector_filters = [s.lower() for s in _parse_csv_list(args.sector_filter)]
    _apply_sector_filter(dataset, sector_filters)
    _apply_liquidity_bucket_filter(dataset, bucket=str(args.liquidity_bucket), liquidity_col=str(args.liquidity_col))
    _apply_dispersion_bucket_filter(dataset, bucket=str(args.dispersion_bucket), dispersion_col=str(args.dispersion_col))

    dataset, ic_payload = controller._run_ic_diagnostics_gate(dataset)  # pylint: disable=protected-access
    date_count = int(pd.to_datetime(dataset.frame.get("date"), errors="coerce").dropna().nunique()) if "date" in dataset.frame.columns else 0
    min_tickers_per_date = int(
        req_training_cfg.get(
            "min_tickers_per_date",
            getattr(controller.pipeline, "min_tickers_per_date", 50),
        )
        or 50
    )
    n_valid_dates = int(date_count)
    n_full_dates = 0
    if {"date", "ticker"}.issubset(set(dataset.frame.columns)):
        dts = pd.to_datetime(dataset.frame["date"], errors="coerce")
        counts = dataset.frame.assign(__date=dts).dropna(subset=["__date"]).groupby("__date", sort=True)["ticker"].nunique()
        if not counts.empty:
            n_valid_dates = int((counts >= max(1, min_tickers_per_date)).sum())
            n_full_dates = int((counts >= max(1, dataset_tickers)).sum()) if dataset_tickers > 0 else 0
    print(
        f"[universe] dates with {min_tickers_per_date}+ tickers: {n_valid_dates}, "
        f"dates with all tickers: {n_full_dates}"
    )
    tr_cfg = dict(cfg.get("training", {}) or {})
    tr_days = int(tr_cfg.get("train_periods", 0) or 0)
    va_days = int(tr_cfg.get("valid_periods", 0) or 0)
    te_days = int(tr_cfg.get("test_periods", 0) or 0)
    st_days = max(1, int(tr_cfg.get("step_periods", 1) or 1))
    min_required = tr_days + va_days + te_days
    if n_valid_dates >= min_required and min_required > 0:
        theoretical_max_windows = 1 + int((n_valid_dates - min_required) // st_days)
    else:
        theoretical_max_windows = 0
    print(
        "[regime-ic] date_coverage "
        f"unique_dates={date_count} valid_dates={n_valid_dates} min_required={min_required} "
        f"theoretical_max_windows={theoretical_max_windows}"
    )
    regime_col = _ensure_regime_column(dataset, regime_col="regime")

    model_name, model_params = _select_model(controller, args.model)
    model = controller._build_model(model_name, model_params)  # pylint: disable=protected-access
    regime_policy = {
        "active_regimes": _parse_csv_list(args.active_regime),
        "invert_regimes": _parse_csv_list(args.invert_regimes),
        "regime_scales": _parse_regime_scale_map(args.regime_scale),
    }
    payload = controller.pipeline.run(model, dataset, regime_col=regime_col, regime_policy=regime_policy)

    agg = dict(payload.get("aggregate_metrics", {}) or {})
    regime_metrics = dict(payload.get("regime_metrics", {}) or {})

    rows = []
    for regime, m in regime_metrics.items():
        mm = dict(m or {})
        rows.append(
            {
                "regime": str(regime),
                "ic": float(mm.get("ic_mean", 0.0) or 0.0),
                "n_obs": int(round(float(mm.get("total_n_obs", 0.0) or 0.0))),
                "windows": int(round(float(mm.get("windows", 0.0) or 0.0))),
                "avg_sharpe": float(mm.get("avg_sharpe", 0.0) or 0.0),
                "avg_max_drawdown": float(mm.get("avg_max_drawdown", 0.0) or 0.0),
            }
        )
    rows = sorted(rows, key=lambda x: x["ic"], reverse=True)

    print(f"[regime-ic] model={model_name} windows={int(round(float(agg.get('windows', 0.0) or 0.0)))}")
    print(f"[regime-ic] global_ic={float(agg.get('ic_mean', 0.0) or 0.0):.4f} global_sharpe={float(agg.get('avg_sharpe', 0.0) or 0.0):.4f}")
    print("")
    print("| Regime | IC | N obs | Windows | Avg Sharpe | Avg MaxDD |")
    print("|---|---:|---:|---:|---:|---:|")
    if rows:
        for r in rows:
            print(
                f"| {r['regime']} | {r['ic']:.4f} | {r['n_obs']} | {r['windows']} | "
                f"{r['avg_sharpe']:.4f} | {r['avg_max_drawdown']:.4f} |"
            )
    else:
        print("| (none) | 0.0000 | 0 | 0 | 0.0000 | 0.0000 |")

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model_name,
        "model_params": model_params,
        "config_shape": str(cfg_meta.get("config_shape", "unknown")),
        "regime_col_used": str(regime_col),
        "regime_policy": regime_policy,
        "aggregate_metrics": agg,
        "regime_rows": rows,
        "ic_diagnostics": dict(ic_payload or {}),
        "selected_features": list((ic_payload or {}).get("selected_features", []) or []),
        "dataset_rows": int(dataset.metadata.get("n_rows", 0) or 0),
        "dataset_features": int(dataset.metadata.get("n_features_after_ic_prune", dataset.metadata.get("n_features", 0)) or 0),
        "dataset_tickers": int(dataset.frame["ticker"].astype(str).nunique()) if "ticker" in dataset.frame.columns else 0,
        "dataset_unique_dates": int(pd.to_datetime(dataset.frame.get("date"), errors="coerce").dropna().nunique()) if "date" in dataset.frame.columns else 0,
        "dataset_start_date": str(dataset.frame["date"].min()) if "date" in dataset.frame.columns and not dataset.frame.empty else None,
        "dataset_end_date": str(dataset.frame["date"].max()) if "date" in dataset.frame.columns and not dataset.frame.empty else None,
        "dataset_metadata": {
            "effective_max_tickers": dataset.metadata.get("effective_max_tickers", dataset.metadata.get("max_tickers")),
            "effective_max_rows": dataset.metadata.get("effective_max_rows", dataset.metadata.get("max_rows")),
            "low_resource_mode_effective": dataset.metadata.get("low_resource_mode_effective"),
            "macro_features_enabled": dataset.metadata.get("macro_features_enabled"),
            "min_tickers_per_date": int(min_tickers_per_date),
            "n_dates_min_tickers": int(n_valid_dates),
            "n_dates_all_tickers": int(n_full_dates),
        },
        "data_integrity": {
            "pit_fundamentals_enabled": bool(dataset.metadata.get("pit_fundamentals_enabled", True)),
            "pit_fundamental_lag_days": int(dataset.metadata.get("pit_fundamental_lag_days", 60) or 60),
            "pit_use_announcement_dates": bool(dataset.metadata.get("pit_use_announcement_dates", True)),
            "pit_no_future_leak": bool(dataset.metadata.get("pit_no_future_leak", True)),
        },
        "feature_importance": dict(payload.get("feature_importance", {}) or {}),
        "external_data_audit": audit_external_data_interfaces(project_root=REPO_ROOT, cfg=cfg),
        "split_mode": str(payload.get("split_mode", "rolling")),
        "holdout_train_end_date": payload.get("holdout_train_end_date"),
        "holdout_test_start_date": payload.get("holdout_test_start_date"),
        "holdout_test_end_date": payload.get("holdout_test_end_date"),
    }
    if holdout_requested and str(out.get("split_mode", "")).strip().lower() != "fixed_holdout":
        raise ValueError(
            "run_regime_ic_split_holdout_not_applied:"
            f"requested_train_end={args.holdout_train_end_date or 'NA'}:"
            f"requested_test_start={args.holdout_test_start_date or 'NA'}:"
            f"requested_test_end={args.holdout_test_end_date or 'NA'}:"
            f"actual_split_mode={out.get('split_mode')}"
        )
    out_path = Path(args.output_json)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n[regime-ic] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
