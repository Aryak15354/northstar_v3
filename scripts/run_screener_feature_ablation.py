#!/usr/bin/env python3
"""Run baseline vs Screener feature ablation under fixed phase-1 settings."""

from __future__ import annotations

import argparse
import copy
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.research.research_controller import ResearchController


FUNDAMENTAL_BASE_FEATURES = {
    "revenue",
    "ebitda",
    "operating_income",
    "net_income",
    "equity",
    "total_assets",
    "total_debt",
    "operating_cash_flow",
    "free_cash_flow",
    "interest_expense",
    "shares_outstanding",
    "ni_margin",
    "debt_to_equity",
    "fcf_to_ocf",
    "roe",
    "operating_margin",
    "ebitda_margin",
    "accruals_ratio",
    "cash_conversion",
    "asset_turnover",
    "interest_coverage",
    "roe_qoq_change",
    "operating_margin_change",
}

REGIME_ORDER = [
    "high_vol|uptrend",
    "high_vol|downtrend",
    "low_vol|uptrend",
    "low_vol|downtrend",
]


def _load_cfg(path: Path) -> Dict[str, Any]:
    return dict(yaml.safe_load(path.read_text()) or {})


def _normalize_policy_cfg(raw_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(raw_cfg or {})
    if isinstance(cfg.get("historical_research"), dict):
        hr = copy.deepcopy(dict(cfg.get("historical_research", {})))
        if "low_resource_mode" in cfg and "low_resource_mode" not in hr:
            hr["low_resource_mode"] = cfg.get("low_resource_mode")
        return hr
    return copy.deepcopy(cfg)


def _set_single_core_caps(max_cores: int = 1, max_blas_threads: int = 1) -> None:
    c = max(1, int(max_cores))
    b = max(1, int(max_blas_threads))
    os.environ["LOKY_MAX_CPU_COUNT"] = str(c)
    os.environ["OMP_NUM_THREADS"] = str(b)
    os.environ["OPENBLAS_NUM_THREADS"] = str(b)
    os.environ["MKL_NUM_THREADS"] = str(b)
    os.environ["NUMEXPR_NUM_THREADS"] = str(b)
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", str(b))


def _apply_ablation_overrides(
    cfg: Dict[str, Any],
    *,
    use_screener: bool,
    max_tickers: int,
    lookback_days: int,
) -> Dict[str, Any]:
    out = copy.deepcopy(dict(cfg))
    out.setdefault("runtime_policy", {})["pause_scheduled_until_burn_in"] = False
    out["low_resource_mode"] = "disabled"
    out["use_screener_features"] = bool(use_screener)
    out["use_screener_extended_features"] = bool(use_screener)

    training = out.setdefault("training", {})
    training["max_windows"] = 8
    training["train_periods"] = 504
    training["valid_periods"] = 63
    training["test_periods"] = 63
    training["step_periods"] = 42

    dataset = out.setdefault("dataset", {})
    dataset["low_resource_mode"] = "disabled"
    dataset["max_tickers"] = int(max_tickers)
    dataset["lookback_days"] = int(lookback_days)
    dataset["target_horizon_days"] = 5
    dataset["enable_macro_features"] = False
    dataset["use_screener_features"] = bool(use_screener)
    dataset["use_screener_extended_features"] = bool(use_screener)
    dataset.setdefault("max_rows", 200000)

    # Keep explicit paths deterministic if present in parent config.
    if "screener_fundamentals_path" in out:
        dataset["screener_fundamentals_path"] = out["screener_fundamentals_path"]
    if "screener_shareholding_path" in out:
        dataset["screener_shareholding_path"] = out["screener_shareholding_path"]
    return out


def _select_model(controller: ResearchController, model_name: str) -> Tuple[str, Dict[str, Any]]:
    want = controller._normalize_model_name(model_name)  # pylint: disable=protected-access
    specs = dict(controller._model_specs())  # pylint: disable=protected-access
    if want in specs:
        return want, dict(specs[want] or {})
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
    return sorted([str(x) for x in vals.unique().tolist() if str(x)])


def _ensure_regime_column(dataset: Any, regime_col: str = "regime") -> str:
    frame = dataset.frame.copy()
    if regime_col in frame.columns:
        usable = _usable_regime_values(frame[regime_col])
        if len(usable) >= 2:
            dataset.frame = frame
            return regime_col

    if "date" not in frame.columns:
        dataset.frame = frame
        return regime_col

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).copy()
    if frame.empty:
        dataset.frame = frame
        return regime_col

    vol_cols = [c for c in ["vol_20d", "macro_volatility", "volatility"] if c in frame.columns]
    if vol_cols:
        vol_daily = pd.to_numeric(frame[vol_cols[0]], errors="coerce").groupby(frame["date"], sort=False).mean()
    else:
        vol_daily = pd.Series(0.0, index=sorted(frame["date"].unique()))
    vol_med = float(pd.to_numeric(vol_daily, errors="coerce").median()) if len(vol_daily) else 0.0
    vol_state = pd.Series(
        np.where(pd.to_numeric(vol_daily, errors="coerce").fillna(vol_med).to_numpy() >= vol_med, "high_vol", "low_vol"),
        index=vol_daily.index,
        dtype="object",
    )

    trend_cols = [c for c in ["mom_20d", "ret_20d", "macro_trend_score", "macro_regime_score"] if c in frame.columns]
    if trend_cols:
        trend_daily = pd.to_numeric(frame[trend_cols[0]], errors="coerce").groupby(frame["date"], sort=False).mean()
    else:
        trend_daily = pd.Series(0.0, index=vol_state.index)
    trend_state = pd.Series(
        np.where(pd.to_numeric(trend_daily, errors="coerce").fillna(0.0).to_numpy() >= 0.0, "uptrend", "downtrend"),
        index=trend_daily.index,
        dtype="object",
    )

    idx = sorted(set(vol_state.index).intersection(set(trend_state.index)))
    if not idx:
        frame["regime_audit"] = "unknown"
        dataset.frame = frame
        return "regime_audit"

    regime_daily = pd.Series(
        [f"{str(vol_state.loc[i])}|{str(trend_state.loc[i])}" for i in idx],
        index=pd.DatetimeIndex(idx),
        dtype="object",
    )
    frame["regime_audit"] = frame["date"].map(regime_daily).fillna("unknown").astype(str)
    dataset.frame = frame
    return "regime_audit"


def _is_fundamentals_only_feature(name: str) -> bool:
    s = str(name).strip().lower()
    if not s:
        return False
    if s.startswith("screener_"):
        return True
    for base in FUNDAMENTAL_BASE_FEATURES:
        if s == base or s.startswith(f"{base}_"):
            return True
    return False


def _apply_fundamentals_only_feature_filter(dataset: Any) -> None:
    names = [str(x) for x in list(dataset.feature_names or [])]
    if not names:
        raise ValueError("Dataset has no feature names")
    keep_idx = [i for i, name in enumerate(names) if _is_fundamentals_only_feature(name)]
    if not keep_idx:
        raise ValueError("No fundamentals-only features left after filtering")
    dataset.feature_names = [names[i] for i in keep_idx]
    dataset.X = np.asarray(dataset.X, dtype=float)[:, keep_idx]
    if isinstance(getattr(dataset, "metadata", None), dict):
        dataset.metadata["n_features"] = int(len(dataset.feature_names))
        dataset.metadata["feature_filter"] = "fundamentals_only_no_momentum_no_macro"


def _collect_regime_ic(regime_metrics: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for regime, payload in dict(regime_metrics or {}).items():
        m = dict(payload or {})
        out[str(regime)] = float(m.get("ic_mean", np.nan) or np.nan)
    return out


def _map_feature_importance(fi: Dict[str, Any], feature_names: Iterable[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    names = [str(x) for x in feature_names]
    for k, v in dict(fi or {}).items():
        try:
            score = float(v)
        except Exception:
            continue
        name = str(k)
        m = re.fullmatch(r"f(\d+)", name)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < len(names):
                name = names[idx]
        out[name] = float(out.get(name, 0.0) + score)
    return out


def _run_single_experiment(
    *,
    base_cfg: Dict[str, Any],
    use_screener: bool,
    max_tickers: int,
    lookback_days: int,
    model_name: str,
) -> Dict[str, Any]:
    cfg = _apply_ablation_overrides(
        base_cfg,
        use_screener=use_screener,
        max_tickers=max_tickers,
        lookback_days=lookback_days,
    )
    controller = ResearchController(config=cfg, project_root=REPO_ROOT)
    dataset = controller.dataset_manager.build_research_dataset()
    _apply_fundamentals_only_feature_filter(dataset)
    dataset, _ = controller._run_ic_diagnostics_gate(dataset)  # pylint: disable=protected-access
    regime_col = _ensure_regime_column(dataset, regime_col="regime")
    chosen_model, model_params = _select_model(controller, model_name)
    model = controller._build_model(chosen_model, model_params)  # pylint: disable=protected-access
    payload = controller.pipeline.run(model, dataset, regime_col=regime_col, regime_policy={})

    agg = dict(payload.get("aggregate_metrics", {}) or {})
    regime_ic = _collect_regime_ic(dict(payload.get("regime_metrics", {}) or {}))
    fi = _map_feature_importance(dict(payload.get("feature_importance", {}) or {}), dataset.feature_names)
    return {
        "aggregate_metrics": agg,
        "regime_ic": regime_ic,
        "feature_importance": fi,
        "status": str(payload.get("status", "")),
        "feature_count": int(len(dataset.feature_names)),
        "chosen_model": chosen_model,
    }


def _fmt4(v: Any) -> str:
    try:
        x = float(v)
    except Exception:
        return "nan"
    if np.isnan(x):
        return "nan"
    return f"{x:.4f}"


def _fmti(v: Any) -> str:
    try:
        return str(int(round(float(v))))
    except Exception:
        return "0"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run baseline vs Screener feature ablation")
    ap.add_argument("--base-config", default="config/research_policy.yaml")
    ap.add_argument("--model", default="xgboost")
    ap.add_argument("--max-tickers", type=int, default=150)
    ap.add_argument("--lookback-days", type=int, default=3650)
    ap.add_argument("--max-cpu-cores", type=int, default=1)
    ap.add_argument("--max-blas-threads", type=int, default=1)
    args = ap.parse_args()

    _set_single_core_caps(args.max_cpu_cores, args.max_blas_threads)
    raw_cfg = _load_cfg(REPO_ROOT / str(args.base_config))
    base_cfg = _normalize_policy_cfg(raw_cfg)

    start = time.time()
    baseline = _run_single_experiment(
        base_cfg=base_cfg,
        use_screener=False,
        max_tickers=int(args.max_tickers),
        lookback_days=int(args.lookback_days),
        model_name=str(args.model),
    )
    screener = _run_single_experiment(
        base_cfg=base_cfg,
        use_screener=True,
        max_tickers=int(args.max_tickers),
        lookback_days=int(args.lookback_days),
        model_name=str(args.model),
    )
    _elapsed = time.time() - start

    b_agg = dict(baseline.get("aggregate_metrics", {}) or {})
    s_agg = dict(screener.get("aggregate_metrics", {}) or {})

    print("=== Screener Feature Ablation ===")
    print("                    Baseline    Screener")
    print(f"Global IC:          {_fmt4(b_agg.get('ic_mean'))}      {_fmt4(s_agg.get('ic_mean'))}")
    print(f"Global Sharpe:      {_fmt4(b_agg.get('avg_sharpe'))}      {_fmt4(s_agg.get('avg_sharpe'))}")
    print(f"Windows:            {_fmti(b_agg.get('windows'))}           {_fmti(s_agg.get('windows'))}")
    print("")
    print("Regime breakdown:")
    print("                    Baseline IC    Screener IC")
    b_reg = dict(baseline.get("regime_ic", {}) or {})
    s_reg = dict(screener.get("regime_ic", {}) or {})
    for regime in REGIME_ORDER:
        print(f"{regime}:   {_fmt4(b_reg.get(regime, np.nan))}         {_fmt4(s_reg.get(regime, np.nan))}")
    print("")
    print("Top 5 features by importance (Screener run only):")
    top5 = sorted(
        dict(screener.get("feature_importance", {}) or {}).items(),
        key=lambda kv: float(kv[1]),
        reverse=True,
    )[:5]
    for name, score in top5:
        print(f"{name} : {_fmt4(score)}")
    if not top5:
        print("(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
