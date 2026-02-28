#!/usr/bin/env python3
"""
Offline walk-forward validation harness for AlphaOS stability proof.

Design goals:
- No dependency on live broker auth tokens.
- Frozen-parameter style replay over crisis windows.
- Emit governance metrics: drawdown, fallback frequency, survival-core activity.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.bayesian_kelly_allocator import BayesianKellyAllocator
from src.models.regime_probability_engine import DEFAULT_STATES, RegimeProbabilityEngine, train_hmm_em
from src.risk.survival_core_mode import SurvivalCoreMode


@dataclass
class WindowSpec:
    name: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str


DEFAULT_WINDOWS = [
    WindowSpec("wf_2008", "2003-01-01", "2007-12-31", "2008-01-01", "2008-12-31"),
    WindowSpec("wf_2018", "2013-01-01", "2017-12-31", "2018-01-01", "2018-12-31"),
    WindowSpec("wf_2020", "2015-01-01", "2019-12-31", "2020-01-01", "2020-12-31"),
    WindowSpec("wf_2022", "2017-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
]


def _load_alpha_os_cfg() -> Dict[str, Any]:
    cfg_path = PROJECT_ROOT / "config/options_trading.yaml"
    if not cfg_path.exists():
        return {}
    try:
        payload = yaml.safe_load(cfg_path.read_text()) or {}
        return payload.get("alpha_os", {}) if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_features(path: Optional[Path]) -> pd.DataFrame:
    candidates = [
        path if path is not None else None,
        PROJECT_ROOT / "data/processed/regime_hmm_training_features.parquet",
        PROJECT_ROOT / "data/processed/market_state.parquet",
    ]
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        df = pd.read_parquet(candidate)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return pd.DataFrame()


def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    date_col = None
    for col in ["date", "timestamp", "Date"]:
        if col in out.columns:
            date_col = col
            break
    if date_col is None:
        raise ValueError("No date/timestamp column found in input data.")
    out["date"] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Keep numeric columns only for HMM features, preserve daily_return if present.
    num_cols = list(out.select_dtypes(include=[np.number]).columns)
    if "daily_return" not in num_cols:
        # Proxy from first available return-like field.
        for candidate in ["return", "ret", "pnl_return", "portfolio_return"]:
            if candidate in out.columns:
                out["daily_return"] = pd.to_numeric(out[candidate], errors="coerce")
                break
    if "daily_return" not in out.columns:
        out["daily_return"] = 0.0
    out["daily_return"] = pd.to_numeric(out["daily_return"], errors="coerce").fillna(0.0).clip(-0.25, 0.25)

    for col in ["iv_rank", "iv_percentile", "volatility_20d", "volatility_5d", "stress_score", "risk_on_probability"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.infer_objects(copy=False)
    numeric_cols = out.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        out[numeric_cols] = out[numeric_cols].interpolate(limit_direction="both").ffill().bfill()
    return out


def _feature_columns(df: pd.DataFrame) -> List[str]:
    preferred = [
        "iv_percentile",
        "iv_rank",
        "volatility_20d",
        "volatility_5d",
        "stress_score",
        "risk_on_probability",
    ]
    cols = [c for c in preferred if c in df.columns]
    if len(cols) >= 4:
        return cols
    numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c not in {"daily_return"}]
    return numeric[:8]


def _window_row_counts(df: pd.DataFrame, window: WindowSpec) -> Tuple[int, int]:
    train = df[(df["date"] >= pd.Timestamp(window.train_start)) & (df["date"] <= pd.Timestamp(window.train_end))]
    test = df[(df["date"] >= pd.Timestamp(window.test_start)) & (df["date"] <= pd.Timestamp(window.test_end))]
    return int(len(train)), int(len(test))


def _adaptive_windows(df: pd.DataFrame) -> List[WindowSpec]:
    if df.empty:
        return []
    ordered = df.sort_values("date").reset_index(drop=True)
    n = len(ordered)
    if n < 20:
        return []

    def _idx_date(i: int) -> str:
        i = max(0, min(n - 1, i))
        return str(pd.Timestamp(ordered.loc[i, "date"]).date())

    windows: List[WindowSpec] = []
    if n >= 180:
        train_end_1 = int(n * 0.60)
        test_end_1 = int(n * 0.80)
        train_end_2 = int(n * 0.75)
        windows.append(
            WindowSpec(
                name="wf_adaptive_1",
                train_start=_idx_date(0),
                train_end=_idx_date(train_end_1 - 1),
                test_start=_idx_date(train_end_1),
                test_end=_idx_date(test_end_1 - 1),
            )
        )
        windows.append(
            WindowSpec(
                name="wf_adaptive_2",
                train_start=_idx_date(0),
                train_end=_idx_date(train_end_2 - 1),
                test_start=_idx_date(train_end_2),
                test_end=_idx_date(n - 1),
            )
        )
    else:
        split = int(n * 0.70)
        windows.append(
            WindowSpec(
                name="wf_adaptive_single",
                train_start=_idx_date(0),
                train_end=_idx_date(split - 1),
                test_start=_idx_date(split),
                test_end=_idx_date(n - 1),
            )
        )
    return windows


def _select_windows(df: pd.DataFrame) -> List[WindowSpec]:
    min_train_rows = 30
    min_test_rows = 10
    selected: List[WindowSpec] = []
    for window in DEFAULT_WINDOWS:
        tr, te = _window_row_counts(df, window)
        if tr >= min_train_rows and te >= min_test_rows:
            selected.append(window)
    if selected:
        return selected
    adaptive = _adaptive_windows(df)
    return adaptive if adaptive else list(DEFAULT_WINDOWS)


def _run_window(df: pd.DataFrame, window: WindowSpec, feature_cols: Sequence[str], smoothing: float) -> Dict[str, Any]:
    train = df[(df["date"] >= pd.Timestamp(window.train_start)) & (df["date"] <= pd.Timestamp(window.train_end))].copy()
    test = df[(df["date"] >= pd.Timestamp(window.test_start)) & (df["date"] <= pd.Timestamp(window.test_end))].copy()
    if train.empty or test.empty:
        return {
            "window": asdict(window),
            "status": "skipped",
            "reason": "insufficient_rows",
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
        }

    train_x = train[list(feature_cols)].to_numpy(dtype=float)
    model, train_diag = train_hmm_em(
        features=train_x,
        states=DEFAULT_STATES,
        smoothing=float(smoothing),
        feature_names=list(feature_cols),
    )
    engine = RegimeProbabilityEngine(model_path="unused")
    engine._model = model  # offline in-memory frozen model for this walk-forward split

    allocator = BayesianKellyAllocator()
    survival_core = SurvivalCoreMode()

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    fallback_count = 0
    survival_days = 0
    halted_cycles = 0
    prev_probs = None
    daily_rows: List[Dict[str, Any]] = []

    for _, row in test.iterrows():
        x = row[list(feature_cols)].to_numpy(dtype=float)
        regime = engine.predict(x, prev_probs=prev_probs)
        raw_probs = regime.get("probabilities", {}) if isinstance(regime.get("probabilities"), dict) else {}
        probs_vec = np.asarray([float(raw_probs.get(s, 0.0) or 0.0) for s in DEFAULT_STATES], dtype=float)
        probs_vec = np.nan_to_num(probs_vec, nan=0.0, posinf=0.0, neginf=0.0)
        if float(probs_vec.sum()) <= 1e-12:
            probs_vec = np.ones(len(DEFAULT_STATES), dtype=float) / float(len(DEFAULT_STATES))
        else:
            probs_vec = np.clip(probs_vec, 1e-12, None)
            probs_vec = probs_vec / probs_vec.sum()
        probs = {s: float(probs_vec[i]) for i, s in enumerate(DEFAULT_STATES)}
        prev_probs = [float(probs[s]) for s in DEFAULT_STATES]

        crisis = float(probs.get("CRISIS", 0.0))
        high_vol = float(probs.get("HIGH_VOL", 0.0))
        low_vol = float(probs.get("LOW_VOL", 0.0))
        transition = float(probs.get("TRANSITION", 0.0))
        base_ret = float(row.get("daily_return", 0.0) or 0.0)
        vol_proxy = max(0.02, abs(float(row.get("volatility_20d", 0.05) or 0.05)))
        drawdown = max(0.0, (peak - equity) / max(peak, 1e-8))

        posteriors = {
            "short_vol": {
                "posterior_mean": float(0.012 + 0.010 * low_vol - 0.040 * crisis - 0.010 * high_vol),
                "posterior_variance": float(0.03 + 0.06 * crisis),
                "volatility": float(0.08 + 0.90 * vol_proxy),
                "adjusted_sharpe": 0.0,
                "credibility": float(max(0.05, 0.9 - crisis)),
                "convexity_score": float(0.15 + crisis),
                "liquidity_score": float(min(1.0, 0.2 + high_vol + crisis)),
            },
            "long_vol": {
                "posterior_mean": float(-0.004 + 0.030 * crisis + 0.006 * transition),
                "posterior_variance": float(0.02 + 0.04 * high_vol),
                "volatility": float(0.10 + 0.70 * vol_proxy),
                "adjusted_sharpe": 0.0,
                "credibility": float(min(0.95, 0.35 + crisis + 0.3 * high_vol)),
                "convexity_score": float(0.05),
                "liquidity_score": float(0.25 + 0.2 * high_vol),
            },
        }
        alloc = allocator.allocate(
            regime_probs=probs,
            strategy_posteriors=posteriors,
            current_drawdown=drawdown,
            model_confidence=float(regime.get("confidence", 0.5) or 0.5),
            hard_limits={"gross_cap": 1.0, "net_cap": 0.6},
            soft_limits={
                "vol_target": 0.18,
                "cvar_target": 0.24,
                "drawdown_probability_max": 0.25,
                "liquidity_penalty_max": 0.70,
                "convexity_preference_max": 0.80,
            },
        )
        weights = dict(alloc.get("weights", {}) or {})
        if bool(alloc.get("used_fallback", False)):
            fallback_count += 1

        survival_state = survival_core.evaluate(
            crisis_probability=crisis,
            convexity_score=float(posteriors["short_vol"]["convexity_score"] * abs(weights.get("short_vol", 0.0))),
            drawdown=drawdown,
            entropy=float(-np.sum(np.asarray(list(probs.values()), dtype=float) * np.log(np.asarray(list(probs.values()), dtype=float) + 1e-12))),
            n_states=4,
        )
        if bool(survival_state.get("active", False)):
            survival_days += 1
        weights, _ = survival_core.apply_overrides(
            weights=weights,
            strategy_metadata={
                "short_vol": {"is_short_convexity": True, "convexity_score": 0.4},
                "long_vol": {"is_short_convexity": False, "convexity_score": 0.05},
            },
            allowed_gross_cap=1.0,
        )

        # Proxy PnL model.
        short_ret = base_ret - 0.9 * max(0.0, crisis - 0.25)
        long_ret = -0.25 * base_ret + 0.6 * max(0.0, crisis - 0.2)
        portfolio_ret = float(weights.get("short_vol", 0.0)) * short_ret + float(weights.get("long_vol", 0.0)) * long_ret

        # Never halt replay on numerical issues.
        if not np.isfinite(portfolio_ret):
            halted_cycles += 1
            portfolio_ret = 0.0
        equity *= float(1.0 + portfolio_ret)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / max(peak, 1e-8))

        daily_rows.append(
            {
                "date": str(pd.Timestamp(row["date"]).date()),
                "equity": float(equity),
                "drawdown": float((peak - equity) / max(peak, 1e-8)),
                "fallback_used": bool(alloc.get("used_fallback", False)),
                "survival_active": bool(survival_state.get("active", False)),
                "crisis_probability": float(crisis),
            }
        )

    fallback_rate = float(fallback_count / max(1, len(test)))
    return {
        "window": asdict(window),
        "status": "ok",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "max_drawdown": float(max_dd),
        "final_equity_multiple": float(equity),
        "fallback_rate": fallback_rate,
        "survival_core_activation_rate": float(survival_days / max(1, len(test))),
        "halted_cycles": int(halted_cycles),
        "training_diagnostics": train_diag,
        "daily": daily_rows[-400:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline walk-forward validation for AlphaOS.")
    parser.add_argument("--features", type=str, default="", help="Optional parquet path for historical features.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "data/validation/walk_forward_results.json"),
        help="Output JSON path.",
    )
    args = parser.parse_args()

    alpha_cfg = _load_alpha_os_cfg()
    smoothing = float(alpha_cfg.get("hmm_transition_smoothing", 0.02) or 0.02)
    features_df = _load_features(Path(args.features) if args.features else None)
    if features_df.empty:
        raise SystemExit("No features available for walk-forward validation.")
    frame = _prepare_frame(features_df)
    cols = _feature_columns(frame)
    if len(cols) < 3:
        raise SystemExit("Insufficient numeric feature columns for HMM walk-forward.")

    selected_windows = _select_windows(frame)
    results = []
    for window in selected_windows:
        results.append(_run_window(frame, window, cols, smoothing=smoothing))

    summary_rows = [r for r in results if r.get("status") == "ok"]
    overall = {
        "windows_run": len(results),
        "windows_ok": len(summary_rows),
        "max_drawdown_worst": float(max((r.get("max_drawdown", 0.0) for r in summary_rows), default=0.0)),
        "fallback_rate_worst": float(max((r.get("fallback_rate", 0.0) for r in summary_rows), default=0.0)),
        "survival_activation_worst": float(max((r.get("survival_core_activation_rate", 0.0) for r in summary_rows), default=0.0)),
        "halted_cycles_total": int(sum(int(r.get("halted_cycles", 0) or 0) for r in summary_rows)),
    }
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_columns": cols,
        "windows_selected": [asdict(w) for w in selected_windows],
        "overall": overall,
        "windows": results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"output": str(out_path), "overall": overall}, indent=2))


if __name__ == "__main__":
    main()
