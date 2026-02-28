"""Family-level alpha aggregation with IC-aware pruning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd

from .family_registry import build_feature_family_map


def _safe_spearman(a: pd.Series, b: pd.Series) -> float:
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


def _daily_rank_ic(
    frame: pd.DataFrame,
    *,
    feature_col: str,
    target_col: str,
    date_col: str,
    min_obs_per_day: int,
) -> pd.Series:
    cols = [date_col, feature_col, target_col]
    if not set(cols).issubset(frame.columns):
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
    return pd.Series([x[1] for x in out], index=idx, dtype=float).sort_index()


def _summarize_ic(ic_series: pd.Series) -> Dict[str, float]:
    x = pd.to_numeric(ic_series, errors="coerce").dropna()
    n = int(len(x))
    if n == 0:
        return {
            "n_days": 0.0,
            "mean_ic": 0.0,
            "std_ic": 0.0,
            "ic_t_stat": 0.0,
            "sign_consistency": 0.0,
            "ir": 0.0,
            "stability_score": 0.0,
        }
    mean_ic = float(x.mean())
    std_ic = float(x.std(ddof=1)) if n > 1 else 0.0
    t_stat = float(mean_ic / (std_ic / np.sqrt(float(n)) + 1e-12)) if n > 2 else 0.0
    positive_rate = float((x > 0.0).mean())
    negative_rate = float((x < 0.0).mean())
    sign_consistency = float(max(positive_rate, negative_rate))
    ir = float(mean_ic / (std_ic + 1e-12))
    stability = float(mean_ic * sign_consistency / (std_ic + 1e-12))
    return {
        "n_days": float(n),
        "mean_ic": mean_ic,
        "std_ic": std_ic,
        "ic_t_stat": t_stat,
        "sign_consistency": sign_consistency,
        "ir": ir,
        "stability_score": stability,
    }


def _group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 6.0) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce")
    mu = v.groupby(groups, sort=False).transform("mean")
    sd = v.groupby(groups, sort=False).transform("std")
    z = (v - mu) / (sd + 1e-12)
    if np.isfinite(clip_abs) and clip_abs > 0:
        z = z.clip(lower=-float(clip_abs), upper=float(clip_abs))
    return z.fillna(0.0).astype(float)


def _pairwise_corr_prune(
    frame: pd.DataFrame,
    *,
    features: Sequence[str],
    score_by_feature: Mapping[str, float],
    corr_threshold: float,
) -> Tuple[List[str], Dict[str, List[str]]]:
    if len(features) <= 1:
        return list(features), {}

    f = [str(x) for x in features if str(x) in frame.columns]
    if len(f) <= 1:
        return f, {}

    score = {str(k): float(v) for k, v in score_by_feature.items()}
    ordered = sorted(
        f,
        key=lambda x: abs(float(score.get(x, 0.0))),
        reverse=True,
    )
    corr = frame[ordered].replace([np.inf, -np.inf], np.nan).corr(method="spearman", min_periods=20)
    corr = corr.where(np.isfinite(corr), np.nan)

    keep: List[str] = []
    dropped_by: Dict[str, List[str]] = {}
    thr = float(max(0.0, corr_threshold))
    for feat in ordered:
        drop = False
        for kept in keep:
            c = corr.loc[feat, kept] if feat in corr.index and kept in corr.columns else np.nan
            if pd.notna(c) and abs(float(c)) >= thr:
                dropped_by.setdefault(kept, []).append(feat)
                drop = True
                break
        if not drop:
            keep.append(feat)
    return keep, dropped_by


def _daily_long_short_returns(
    frame: pd.DataFrame,
    *,
    score_col: str,
    target_col: str,
    date_col: str,
    long_short_quantile: float,
    min_assets_per_day: int,
) -> pd.Series:
    cols = [date_col, score_col, target_col]
    if not set(cols).issubset(frame.columns):
        return pd.Series(dtype=float)
    sub = frame[cols].dropna()
    if sub.empty:
        return pd.Series(dtype=float)

    q = float(np.clip(long_short_quantile, 0.01, 0.49))
    out: List[Tuple[pd.Timestamp, float]] = []
    for dt, g in sub.groupby(date_col, sort=False):
        n = int(len(g))
        if n < int(max(min_assets_per_day, 8)):
            continue
        k = int(max(1, np.floor(n * q)))
        if n < int(2 * k + 2):
            continue
        long_leg = g.nlargest(k, score_col)[target_col]
        short_leg = g.nsmallest(k, score_col)[target_col]
        if long_leg.empty or short_leg.empty:
            continue
        out.append((pd.Timestamp(dt), float(long_leg.mean() - short_leg.mean())))
    if not out:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex([x[0] for x in out])
    return pd.Series([x[1] for x in out], index=idx, dtype=float).sort_index()


def _daily_signal_turnover(
    frame: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    score_col: str,
) -> pd.Series:
    cols = [date_col, ticker_col, score_col]
    if not set(cols).issubset(frame.columns):
        return pd.Series(dtype=float)
    x = frame[cols].dropna().copy()
    if x.empty:
        return pd.Series(dtype=float)
    x = x.sort_values([ticker_col, date_col])
    x["turn"] = x.groupby(ticker_col, sort=False)[score_col].diff().abs()
    out = x.groupby(date_col, sort=False)["turn"].mean()
    return pd.to_numeric(out, errors="coerce").fillna(0.0).astype(float)


def build_family_factor_table(
    frame: pd.DataFrame,
    *,
    feature_cols: Sequence[str],
    feature_family_map: Mapping[str, str] | None = None,
    date_col: str = "date",
    ticker_col: str = "ticker",
    target_col: str = "forward_return_5d",
    min_obs_per_day: int = 25,
    min_abs_ic: float = 0.01,
    min_sign_consistency: float = 0.55,
    min_t_stat: float = 0.0,
    corr_prune_threshold: float = 0.85,
    min_features_per_family: int = 1,
    max_features_per_family: int = 25,
    long_short_quantile: float = 0.20,
    min_assets_per_day: int = 12,
) -> Dict[str, Any]:
    """Build family-level factor table with IC/stability-aware feature pruning."""
    if frame is None or frame.empty:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "empty_frame",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "feature_stats": [],
            "family_feature_weights": {},
            "family_stats": {},
        }
    required = {date_col, ticker_col, target_col}
    if not required.issubset(frame.columns):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "missing_required_columns",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "feature_stats": [],
            "family_feature_weights": {},
            "family_stats": {},
        }

    work = frame.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col]).sort_values([date_col, ticker_col])
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce")

    features = [str(c) for c in feature_cols if str(c) in work.columns]
    if not features:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_features",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "feature_stats": [],
            "family_feature_weights": {},
            "family_stats": {},
        }

    work.loc[:, features] = (
        work[features]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )

    fmap = (
        {str(k): str(v) for k, v in feature_family_map.items()}
        if feature_family_map is not None
        else build_feature_family_map(features)
    )
    family_to_features: Dict[str, List[str]] = {}
    for feat in features:
        family = str(fmap.get(feat, "other"))
        family_to_features.setdefault(family, []).append(feat)

    feature_stats: List[Dict[str, Any]] = []
    family_feature_weights: Dict[str, Dict[str, float]] = {}
    family_stats: Dict[str, Dict[str, Any]] = {}
    family_score_cols: Dict[str, pd.Series] = {}
    family_ic_series: Dict[str, pd.Series] = {}
    family_ret_series: Dict[str, pd.Series] = {}
    family_turnover: Dict[str, float] = {}

    for family, fam_feats in sorted(family_to_features.items(), key=lambda x: x[0]):
        per_feature: List[Dict[str, Any]] = []
        for feat in fam_feats:
            ic_daily = _daily_rank_ic(
                work,
                feature_col=feat,
                target_col=target_col,
                date_col=date_col,
                min_obs_per_day=int(min_obs_per_day),
            )
            summary = _summarize_ic(ic_daily)
            row = {"family": family, "feature": feat, **summary}
            keep = True
            reasons: List[str] = []
            mean_ic = float(summary.get("mean_ic", 0.0))
            sign_cons = float(summary.get("sign_consistency", 0.0))
            t_stat = float(summary.get("ic_t_stat", 0.0))
            if abs(mean_ic) < float(min_abs_ic):
                keep = False
                reasons.append("low_abs_ic")
            if sign_cons < float(min_sign_consistency):
                keep = False
                reasons.append("unstable_sign")
            if float(min_t_stat) > 0.0 and abs(t_stat) < float(min_t_stat):
                keep = False
                reasons.append("low_t_stat")
            row["keep_base"] = bool(keep)
            row["drop_reasons"] = reasons
            per_feature.append(row)
            feature_stats.append(dict(row))

        if not per_feature:
            continue
        ranked = sorted(
            per_feature,
            key=lambda x: abs(float(x.get("stability_score", 0.0)))
            + abs(float(x.get("mean_ic", 0.0))),
            reverse=True,
        )

        selected = [str(x["feature"]) for x in ranked if bool(x.get("keep_base", False))]
        min_keep = max(1, int(min_features_per_family))
        if len(selected) < min_keep:
            selected = [str(x["feature"]) for x in ranked[: min(min_keep, len(ranked))]]

        score_by_feature = {
            str(x["feature"]): float(
                abs(float(x.get("stability_score", 0.0)))
                + abs(float(x.get("ir", 0.0)))
                + abs(float(x.get("mean_ic", 0.0)))
            )
            for x in ranked
        }
        selected, dropped_by = _pairwise_corr_prune(
            work,
            features=selected,
            score_by_feature=score_by_feature,
            corr_threshold=float(corr_prune_threshold),
        )

        max_keep = int(max_features_per_family)
        if max_keep > 0:
            selected = selected[:max_keep]
        if len(selected) < min_keep:
            add_pool = [str(x["feature"]) for x in ranked if str(x["feature"]) not in set(selected)]
            selected = (selected + add_pool)[:min_keep]

        chosen_stats = {str(x["feature"]): x for x in ranked if str(x["feature"]) in set(selected)}
        raw_w: Dict[str, float] = {}
        for feat in selected:
            fs = chosen_stats.get(feat, {})
            mean_ic = float(fs.get("mean_ic", 0.0))
            orient = 1.0 if mean_ic >= 0.0 else -1.0
            strength = float(
                abs(float(fs.get("stability_score", 0.0)))
                + abs(float(fs.get("ir", 0.0)))
                + abs(mean_ic)
            )
            if strength <= 1e-12:
                strength = 1.0
            raw_w[feat] = orient * strength
        denom = float(sum(abs(v) for v in raw_w.values()))
        if denom <= 1e-12:
            weights = {k: float(1.0 / max(1, len(raw_w))) for k in raw_w}
        else:
            weights = {k: float(v / denom) for k, v in raw_w.items()}
        family_feature_weights[family] = weights

        score = pd.Series(0.0, index=work.index, dtype=float)
        for feat, w in weights.items():
            score = score + pd.to_numeric(work[feat], errors="coerce").fillna(0.0) * float(w)
        score = _group_zscore(score, work[date_col], clip_abs=6.0)
        fam_col = f"family_{family}"
        family_score_cols[fam_col] = score

        work_tmp = work[[date_col, ticker_col, target_col]].copy()
        work_tmp[fam_col] = score.values
        fam_ic = _daily_rank_ic(
            work_tmp,
            feature_col=fam_col,
            target_col=target_col,
            date_col=date_col,
            min_obs_per_day=int(min_obs_per_day),
        )
        fam_ret = _daily_long_short_returns(
            work_tmp,
            score_col=fam_col,
            target_col=target_col,
            date_col=date_col,
            long_short_quantile=float(long_short_quantile),
            min_assets_per_day=int(min_assets_per_day),
        )
        fam_turn = _daily_signal_turnover(
            work_tmp,
            date_col=date_col,
            ticker_col=ticker_col,
            score_col=fam_col,
        )
        family_ic_series[family] = fam_ic
        family_ret_series[family] = fam_ret
        family_turnover[family] = float(pd.to_numeric(fam_turn, errors="coerce").mean()) if not fam_turn.empty else 0.0
        fam_sum = _summarize_ic(fam_ic)
        family_stats[family] = {
            "n_features_input": int(len(fam_feats)),
            "n_features_selected": int(len(selected)),
            "selected_features": list(selected),
            "dropped_by_correlation": {k: list(v) for k, v in dropped_by.items()},
            "mean_feature_ic": float(
                np.mean([float(chosen_stats.get(f, {}).get("mean_ic", 0.0)) for f in selected])
            )
            if selected
            else 0.0,
            "family_ic_summary": fam_sum,
            "avg_signal_turnover": float(family_turnover[family]),
        }

    if not family_score_cols:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_family_scores",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "feature_stats": feature_stats,
            "family_feature_weights": family_feature_weights,
            "family_stats": family_stats,
        }

    family_scores = work[[date_col, ticker_col, target_col]].copy()
    for col, s in family_score_cols.items():
        family_scores[col] = pd.to_numeric(s, errors="coerce").astype(float)

    family_returns = pd.DataFrame(family_ret_series).sort_index() if family_ret_series else pd.DataFrame()
    family_ic_daily = pd.DataFrame(family_ic_series).sort_index() if family_ic_series else pd.DataFrame()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "feature_family_map": fmap,
        "feature_stats": feature_stats,
        "family_feature_weights": family_feature_weights,
        "family_stats": family_stats,
        "family_scores": family_scores,
        "family_returns": family_returns,
        "family_ic_daily": family_ic_daily,
        "family_turnover": family_turnover,
    }


def apply_family_feature_weights(
    frame: pd.DataFrame,
    *,
    family_feature_weights: Mapping[str, Mapping[str, float]],
    date_col: str = "date",
    ticker_col: str = "ticker",
    target_col: str = "forward_return_5d",
    min_obs_per_day: int = 25,
    long_short_quantile: float = 0.20,
    min_assets_per_day: int = 12,
) -> Dict[str, Any]:
    """Apply prefit family feature weights to a new slice (typically OOS test data)."""
    if frame is None or frame.empty:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "empty_frame",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "family_turnover": {},
            "family_feature_weights": {},
            "family_stats": {},
        }

    required = {date_col, ticker_col, target_col}
    if not required.issubset(frame.columns):
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "missing_required_columns",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "family_turnover": {},
            "family_feature_weights": {},
            "family_stats": {},
        }

    if not family_feature_weights:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_family_weights",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "family_turnover": {},
            "family_feature_weights": {},
            "family_stats": {},
        }

    work = frame.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col]).sort_values([date_col, ticker_col])
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce")

    available_features = sorted(
        {
            str(feat)
            for fam_weights in family_feature_weights.values()
            for feat in (fam_weights or {}).keys()
            if str(feat) in work.columns
        }
    )
    if not available_features:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_weight_features_in_frame",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "family_turnover": {},
            "family_feature_weights": {},
            "family_stats": {},
        }

    work.loc[:, available_features] = (
        work[available_features]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )

    family_score_cols: Dict[str, pd.Series] = {}
    family_ic_series: Dict[str, pd.Series] = {}
    family_ret_series: Dict[str, pd.Series] = {}
    family_turnover: Dict[str, float] = {}
    family_stats: Dict[str, Dict[str, Any]] = {}
    used_weights: Dict[str, Dict[str, float]] = {}

    for family, weights_map in sorted(family_feature_weights.items(), key=lambda x: str(x[0])):
        raw = {str(k): float(v) for k, v in dict(weights_map or {}).items() if str(k) in work.columns}
        raw = {k: v for k, v in raw.items() if np.isfinite(v) and abs(float(v)) > 1e-12}
        if not raw:
            continue
        gross = float(sum(abs(v) for v in raw.values()))
        if gross <= 1e-12:
            continue
        norm_w = {k: float(v / gross) for k, v in raw.items()}
        used_weights[str(family)] = norm_w

        score = pd.Series(0.0, index=work.index, dtype=float)
        for feat, w in norm_w.items():
            score = score + pd.to_numeric(work[feat], errors="coerce").fillna(0.0) * float(w)
        score = _group_zscore(score, work[date_col], clip_abs=6.0)

        fam = str(family)
        fam_col = f"family_{fam}"
        family_score_cols[fam_col] = score

        work_tmp = work[[date_col, ticker_col, target_col]].copy()
        work_tmp[fam_col] = score.values

        fam_ic = _daily_rank_ic(
            work_tmp,
            feature_col=fam_col,
            target_col=target_col,
            date_col=date_col,
            min_obs_per_day=int(min_obs_per_day),
        )
        fam_ret = _daily_long_short_returns(
            work_tmp,
            score_col=fam_col,
            target_col=target_col,
            date_col=date_col,
            long_short_quantile=float(long_short_quantile),
            min_assets_per_day=int(min_assets_per_day),
        )
        fam_turn = _daily_signal_turnover(
            work_tmp,
            date_col=date_col,
            ticker_col=ticker_col,
            score_col=fam_col,
        )

        family_ic_series[fam] = fam_ic
        family_ret_series[fam] = fam_ret
        family_turnover[fam] = float(pd.to_numeric(fam_turn, errors="coerce").mean()) if not fam_turn.empty else 0.0
        family_stats[fam] = {
            "n_features_input": int(len(weights_map or {})),
            "n_features_selected": int(len(norm_w)),
            "selected_features": sorted(list(norm_w.keys())),
            "dropped_by_correlation": {},
            "mean_feature_ic": 0.0,
            "family_ic_summary": _summarize_ic(fam_ic),
            "avg_signal_turnover": float(family_turnover[fam]),
        }

    if not family_score_cols:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_family_scores",
            "family_scores": pd.DataFrame(),
            "family_returns": pd.DataFrame(),
            "family_ic_daily": pd.DataFrame(),
            "family_turnover": {},
            "family_feature_weights": {},
            "family_stats": {},
        }

    family_scores = work[[date_col, ticker_col, target_col]].copy()
    for col, s in family_score_cols.items():
        family_scores[col] = pd.to_numeric(s, errors="coerce").astype(float)

    family_returns = pd.DataFrame(family_ret_series).sort_index().fillna(0.0) if family_ret_series else pd.DataFrame()
    family_ic_daily = pd.DataFrame(family_ic_series).sort_index().fillna(0.0) if family_ic_series else pd.DataFrame()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "family_scores": family_scores,
        "family_returns": family_returns,
        "family_ic_daily": family_ic_daily,
        "family_turnover": family_turnover,
        "family_feature_weights": used_weights,
        "family_stats": family_stats,
    }
