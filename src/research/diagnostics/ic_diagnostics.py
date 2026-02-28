"""Cross-sectional Information Coefficient diagnostics and feature gating."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple
import json
import re

import numpy as np
import pandas as pd


_TARGET_HORIZON_RE = re.compile(r"forward_return_(\d+)d")


def _safe_spearman(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 3 or len(b) < 3:
        return 0.0
    aa = pd.to_numeric(a, errors="coerce")
    bb = pd.to_numeric(b, errors="coerce")
    mask = aa.notna() & bb.notna()
    if int(mask.sum()) < 3:
        return 0.0
    aa = aa[mask]
    bb = bb[mask]
    if float(aa.std()) <= 1e-12 or float(bb.std()) <= 1e-12:
        return 0.0
    val = aa.corr(bb, method="spearman")
    return float(val) if np.isfinite(val) else 0.0


def _daily_ic(
    frame: pd.DataFrame,
    *,
    feature_col: str,
    target_col: str,
    date_col: str,
    min_obs_per_day: int,
) -> pd.Series:
    cols = [date_col, feature_col, target_col]
    if not set(cols).issubset(set(frame.columns)):
        return pd.Series(dtype=float)
    sub = frame[cols].dropna()
    if sub.empty:
        return pd.Series(dtype=float)
    out: List[Tuple[pd.Timestamp, float]] = []
    for dt, g in sub.groupby(date_col, sort=False):
        if len(g) < int(min_obs_per_day):
            continue
        ic = _safe_spearman(g[feature_col], g[target_col])
        if np.isfinite(ic):
            out.append((pd.Timestamp(dt), float(ic)))
    if not out:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex([x[0] for x in out])
    vals = [x[1] for x in out]
    return pd.Series(vals, index=idx, dtype=float).sort_index()


def _summarize_ic(ic_series: pd.Series) -> Dict[str, float]:
    if ic_series is None or ic_series.empty:
        return {
            "n_days": 0.0,
            "mean_ic": 0.0,
            "std_ic": 0.0,
            "ic_t_stat": 0.0,
            "positive_rate": 0.0,
            "negative_rate": 0.0,
            "sign_consistency": 0.0,
        }
    x = pd.to_numeric(ic_series, errors="coerce").dropna()
    n = int(len(x))
    if n == 0:
        return {
            "n_days": 0.0,
            "mean_ic": 0.0,
            "std_ic": 0.0,
            "ic_t_stat": 0.0,
            "positive_rate": 0.0,
            "negative_rate": 0.0,
            "sign_consistency": 0.0,
        }
    mean_ic = float(x.mean())
    std_ic = float(x.std(ddof=1)) if n > 1 else 0.0
    t_stat = float(mean_ic / (std_ic / np.sqrt(float(n)) + 1e-12)) if n > 2 else 0.0
    positive_rate = float((x > 0.0).mean())
    negative_rate = float((x < 0.0).mean())
    sign_consistency = float(max(positive_rate, negative_rate))
    return {
        "n_days": float(n),
        "mean_ic": mean_ic,
        "std_ic": std_ic,
        "ic_t_stat": t_stat,
        "positive_rate": positive_rate,
        "negative_rate": negative_rate,
        "sign_consistency": sign_consistency,
    }


def _normalize_horizons(horizons: Iterable[int] | None) -> List[int]:
    if horizons is None:
        return []
    out: List[int] = []
    seen = set()
    for h in horizons:
        try:
            hv = int(h)
        except Exception:
            continue
        if hv <= 0 or hv in seen:
            continue
        seen.add(hv)
        out.append(hv)
    return out


def _infer_base_horizon(target_col: str, default: int = 5) -> int:
    m = _TARGET_HORIZON_RE.search(str(target_col))
    if not m:
        return int(default)
    try:
        return max(1, int(m.group(1)))
    except Exception:
        return int(default)


def _ensure_forward_horizon_targets(
    frame: pd.DataFrame,
    *,
    horizons: Sequence[int],
    ticker_col: str = "ticker",
    price_col: str = "close",
) -> Tuple[pd.DataFrame, Dict[int, str]]:
    out = frame.copy()
    mapping: Dict[int, str] = {}
    if ticker_col not in out.columns or price_col not in out.columns:
        return out, mapping
    p = pd.to_numeric(out[price_col], errors="coerce")
    out[price_col] = p
    grouped = out.groupby(ticker_col, sort=False)[price_col]
    for h in horizons:
        col = f"forward_return_{int(h)}d_diag"
        out[col] = grouped.shift(-int(h)) / (out[price_col] + 1e-12) - 1.0
        mapping[int(h)] = col
    return out, mapping


def _date_regime_map(frame: pd.DataFrame, *, date_col: str, regime_col: str) -> pd.Series:
    if date_col not in frame.columns or regime_col not in frame.columns:
        return pd.Series(dtype=object)

    def _mode_or_unknown(x: pd.Series) -> str:
        s = x.astype("string")
        s = s[s.notna()].str.strip()
        s = s[(s != "") & (s.str.lower() != "nan")]
        if len(s) == 0:
            return "unknown"
        vc = s.value_counts()
        return str(vc.index[0]) if not vc.empty else "unknown"

    out = frame[[date_col, regime_col]].dropna(subset=[date_col]).copy()
    if out.empty:
        return pd.Series(dtype=object)
    m = out.groupby(date_col, sort=False)[regime_col].agg(_mode_or_unknown)
    return m.astype(str)


def _aggregate_decay_curves(
    feature_stats: Sequence[Dict[str, Any]],
    *,
    horizons: Sequence[int],
) -> Dict[str, float]:
    curve: Dict[str, float] = {}
    for h in horizons:
        key = str(int(h))
        vals: List[float] = []
        for row in feature_stats:
            d = row.get("ic_decay", {})
            if not isinstance(d, dict):
                continue
            if key not in d:
                continue
            try:
                v = float(d.get(key, 0.0))
            except Exception:
                continue
            if np.isfinite(v):
                vals.append(v)
        curve[key] = float(np.mean(vals)) if vals else 0.0
    return curve


def _summarize_decay_curve(curve: Dict[str, float]) -> Dict[str, float]:
    if not curve:
        return {
            "peak_horizon": 0.0,
            "peak_ic": 0.0,
            "half_life_horizon": 0.0,
            "signed_area": 0.0,
            "abs_area": 0.0,
            "monotonicity_score": 0.0,
            "sign_flip_count": 0.0,
        }
    items: List[Tuple[int, float]] = []
    for k, v in curve.items():
        try:
            h = int(k)
            x = float(v)
        except Exception:
            continue
        if h <= 0 or not np.isfinite(x):
            continue
        items.append((h, x))
    if not items:
        return {
            "peak_horizon": 0.0,
            "peak_ic": 0.0,
            "half_life_horizon": 0.0,
            "signed_area": 0.0,
            "abs_area": 0.0,
            "monotonicity_score": 0.0,
            "sign_flip_count": 0.0,
        }
    items = sorted(items, key=lambda x: x[0])
    horizons = np.asarray([x[0] for x in items], dtype=float)
    vals = np.asarray([x[1] for x in items], dtype=float)
    abs_vals = np.abs(vals)
    peak_idx = int(np.argmax(abs_vals))
    peak_h = float(horizons[peak_idx])
    peak_ic = float(vals[peak_idx])
    half_thresh = 0.5 * float(abs_vals[peak_idx])
    half_h = float(horizons[-1])
    for j in range(peak_idx, len(horizons)):
        if float(abs_vals[j]) <= half_thresh:
            half_h = float(horizons[j])
            break
    signed_area = float(np.trapezoid(vals, horizons)) if len(horizons) > 1 else float(vals[0])
    abs_area = float(np.trapezoid(abs_vals, horizons)) if len(horizons) > 1 else float(abs_vals[0])

    sign_nonzero = [int(np.sign(v)) for v in vals if abs(v) > 1e-12]
    sign_flips = 0
    for i in range(1, len(sign_nonzero)):
        if sign_nonzero[i] != sign_nonzero[i - 1]:
            sign_flips += 1

    up = 1.0
    down = 1.0
    if peak_idx > 0:
        up_diffs = np.diff(abs_vals[: peak_idx + 1])
        up = float(np.mean(up_diffs >= -1e-12)) if len(up_diffs) else 1.0
    if peak_idx < len(abs_vals) - 1:
        down_diffs = np.diff(abs_vals[peak_idx:])
        down = float(np.mean(down_diffs <= 1e-12)) if len(down_diffs) else 1.0
    mono = float(0.5 * (up + down))

    return {
        "peak_horizon": peak_h,
        "peak_ic": peak_ic,
        "half_life_horizon": half_h,
        "signed_area": signed_area,
        "abs_area": abs_area,
        "monotonicity_score": mono,
        "sign_flip_count": float(sign_flips),
    }


def _regime_decay_for_features(
    frame: pd.DataFrame,
    *,
    features: Sequence[str],
    regime_by_date: pd.Series,
    date_col: str,
    horizon_targets: Dict[int, str],
    horizons: Sequence[int],
    min_obs_per_day: int,
    max_regimes_to_report: int,
    min_regime_days: int,
) -> Dict[str, Dict[str, float]]:
    if frame.empty or not features or regime_by_date.empty:
        return {}
    reg_counts = regime_by_date.value_counts()
    regimes = [str(r) for r, c in reg_counts.items() if int(c) >= int(min_regime_days)]
    if int(max_regimes_to_report) > 0:
        regimes = regimes[: int(max_regimes_to_report)]
    if not regimes:
        return {}

    out: Dict[str, Dict[str, float]] = {}
    for reg in regimes:
        reg_dates = set(regime_by_date.index[regime_by_date.eq(reg)].tolist())
        curve: Dict[str, float] = {}
        for h in horizons:
            h_col = horizon_targets.get(int(h), "")
            if not h_col or h_col not in frame.columns:
                continue
            vals: List[float] = []
            for f in features:
                ic = _daily_ic(
                    frame,
                    feature_col=str(f),
                    target_col=h_col,
                    date_col=date_col,
                    min_obs_per_day=int(min_obs_per_day),
                )
                if ic.empty:
                    continue
                ic = ic[ic.index.isin(reg_dates)]
                if ic.empty:
                    continue
                vals.append(float(pd.to_numeric(ic, errors="coerce").mean()))
            curve[str(int(h))] = float(np.mean(vals)) if vals else 0.0
        out[reg] = curve
    return out


def compute_feature_ic_diagnostics(
    frame: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    target_col: str = "forward_return_5d",
    date_col: str = "date",
    ticker_col: str = "ticker",
    regime_col: str = "regime",
    horizons: Sequence[int] | None = None,
    min_obs_per_day: int = 25,
    min_abs_ic: float = 0.01,
    min_sign_consistency: float = 0.55,
    min_t_stat: float = 0.0,
    min_keep_features: int = 15,
    max_keep_features: int = 40,
    max_features_to_analyze: int = 0,
    max_regimes_to_report: int = 4,
    min_regime_days: int = 30,
) -> Dict[str, Any]:
    """Compute per-feature IC diagnostics and a deterministic keep/drop decision."""
    if frame is None or frame.empty:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "empty_frame",
            "feature_stats": [],
            "selected_features": [],
            "dropped_features": [],
        }
    if date_col not in frame.columns:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "missing_date_column",
            "feature_stats": [],
            "selected_features": [],
            "dropped_features": [],
        }

    work = frame.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col]).sort_values([date_col, ticker_col] if ticker_col in work.columns else [date_col])

    base_horizon = _infer_base_horizon(target_col, default=5)
    h_list = _normalize_horizons(horizons)
    if base_horizon not in h_list:
        h_list = [base_horizon] + h_list
    work, horizon_targets = _ensure_forward_horizon_targets(
        work,
        horizons=h_list,
        ticker_col=ticker_col,
        price_col="close",
    )
    base_target = str(target_col)
    if base_target not in work.columns:
        base_target = horizon_targets.get(base_horizon, "")
    if not base_target or base_target not in work.columns:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "missing_target_column",
            "feature_stats": [],
            "selected_features": [],
            "dropped_features": [],
        }

    features = [str(f) for f in feature_cols if str(f) in work.columns]
    if int(max_features_to_analyze) > 0 and len(features) > int(max_features_to_analyze):
        features = features[: int(max_features_to_analyze)]
    if not features:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_features",
            "feature_stats": [],
            "selected_features": [],
            "dropped_features": [],
        }

    regime_by_date = _date_regime_map(work, date_col=date_col, regime_col=regime_col)
    feature_stats: List[Dict[str, Any]] = []
    for fname in features:
        ic = _daily_ic(
            work,
            feature_col=fname,
            target_col=base_target,
            date_col=date_col,
            min_obs_per_day=int(min_obs_per_day),
        )
        summary = _summarize_ic(ic)
        if int(summary.get("n_days", 0.0)) <= 0:
            continue

        decay: Dict[str, float] = {}
        for h in h_list:
            h_col = horizon_targets.get(int(h), "")
            if not h_col or h_col not in work.columns:
                continue
            h_ic = _daily_ic(
                work,
                feature_col=fname,
                target_col=h_col,
                date_col=date_col,
                min_obs_per_day=int(min_obs_per_day),
            )
            decay[str(int(h))] = float(pd.to_numeric(h_ic, errors="coerce").mean()) if not h_ic.empty else 0.0

        regime_ic: Dict[str, float] = {}
        if not regime_by_date.empty and not ic.empty:
            ic_df = pd.DataFrame({"ic": pd.to_numeric(ic, errors="coerce")}).dropna()
            ic_df = ic_df.join(regime_by_date.rename("regime"), how="left")
            for reg, g in ic_df.groupby("regime", sort=False):
                regime_ic[str(reg)] = float(pd.to_numeric(g["ic"], errors="coerce").mean())

        mean_ic = float(summary.get("mean_ic", 0.0))
        sign_consistency = float(summary.get("sign_consistency", 0.0))
        t_stat = float(summary.get("ic_t_stat", 0.0))
        keep = True
        drop_reasons: List[str] = []
        if abs(mean_ic) < float(min_abs_ic):
            keep = False
            drop_reasons.append("low_abs_ic")
        if sign_consistency < float(min_sign_consistency):
            keep = False
            drop_reasons.append("unstable_sign")
        if float(min_t_stat) > 0.0 and abs(t_stat) < float(min_t_stat):
            keep = False
            drop_reasons.append("low_t_stat")

        feature_stats.append(
            {
                "feature": fname,
                **summary,
                "ic_decay": decay,
                "regime_ic": regime_ic,
                "keep": bool(keep),
                "drop_reasons": drop_reasons,
            }
        )

    feature_stats = sorted(feature_stats, key=lambda x: abs(float(x.get("mean_ic", 0.0))), reverse=True)
    selected = [str(x["feature"]) for x in feature_stats if bool(x.get("keep", False))]
    min_keep = max(1, int(min_keep_features))
    if len(selected) < min_keep and feature_stats:
        selected = [str(x["feature"]) for x in feature_stats[:min(min_keep, len(feature_stats))]]

    max_keep = int(max_keep_features)
    if max_keep > 0:
        selected = selected[:max_keep]
    selected_set = set(selected)
    dropped = [str(x["feature"]) for x in feature_stats if str(x["feature"]) not in selected_set]

    selected_stats = [x for x in feature_stats if str(x["feature"]) in selected_set]
    mean_ic_selected = (
        float(np.mean([float(x.get("mean_ic", 0.0)) for x in selected_stats])) if selected_stats else 0.0
    )
    mean_ic_all = float(np.mean([float(x.get("mean_ic", 0.0)) for x in feature_stats])) if feature_stats else 0.0
    all_curve = _aggregate_decay_curves(feature_stats, horizons=h_list)
    selected_curve = _aggregate_decay_curves(selected_stats, horizons=h_list)
    all_curve_summary = _summarize_decay_curve(all_curve)
    selected_curve_summary = _summarize_decay_curve(selected_curve)
    regime_decay_selected = _regime_decay_for_features(
        work,
        features=list(selected_set),
        regime_by_date=regime_by_date,
        date_col=date_col,
        horizon_targets=horizon_targets,
        horizons=h_list,
        min_obs_per_day=int(min_obs_per_day),
        max_regimes_to_report=int(max_regimes_to_report),
        min_regime_days=int(min_regime_days),
    )
    regime_decay_selected_summary = {
        reg: _summarize_decay_curve(curve) for reg, curve in regime_decay_selected.items()
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "base_target_col": str(base_target),
        "base_target_requested": str(target_col),
        "horizons": [int(h) for h in h_list],
        "thresholds": {
            "min_abs_ic": float(min_abs_ic),
            "min_sign_consistency": float(min_sign_consistency),
            "min_t_stat": float(min_t_stat),
            "min_keep_features": int(min_keep),
            "max_keep_features": int(max_keep),
            "min_obs_per_day": int(min_obs_per_day),
        },
        "n_features_input": int(len(features)),
        "n_features_evaluated": int(len(feature_stats)),
        "n_features_selected": int(len(selected)),
        "n_features_dropped": int(len(dropped)),
        "mean_ic_all_features": mean_ic_all,
        "mean_ic_selected_features": mean_ic_selected,
        "ic_decay_all_features": all_curve,
        "ic_decay_selected_features": selected_curve,
        "decay_summary_all_features": all_curve_summary,
        "decay_summary_selected_features": selected_curve_summary,
        "regime_ic_decay_selected_features": regime_decay_selected,
        "regime_decay_summary_selected_features": regime_decay_selected_summary,
        "feature_stats": feature_stats,
        "selected_features": selected,
        "dropped_features": dropped,
        "top_features": selected[: min(20, len(selected))],
    }


def write_ic_report(report: Dict[str, Any], path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2))
    return str(p)
