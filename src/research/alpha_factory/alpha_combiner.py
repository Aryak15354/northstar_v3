"""Covariance-aware family blending and production monitoring helpers."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

import numpy as np
import pandas as pd


def robust_ledoit_wolf_cov(
    returns: np.ndarray,
    *,
    shrinkage: float | None = None,
    eigen_floor: float = 1e-4,
    ridge: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """
    Robust covariance estimation with scaled-identity shrinkage.

    Σ_shrunk = (1-λ)Σ + λμI, where μ = trace(Σ)/N
    """
    x = np.asarray(returns, dtype=float)
    if x.ndim != 2 or x.shape[1] <= 0:
        cov = np.eye(1, dtype=float) * float(max(1e-10, eigen_floor))
        eig = np.asarray([float(max(1e-10, eigen_floor))], dtype=float)
        return cov, eig, 1.0, float(0.60 if shrinkage is None else np.clip(shrinkage, 0.0, 1.0))

    sample_cov = np.cov(x, rowvar=False)
    if np.ndim(sample_cov) == 0:
        sample_cov = np.asarray([[float(sample_cov)]], dtype=float)
    sample_cov = np.asarray(sample_cov, dtype=float)
    sample_cov = np.nan_to_num(sample_cov, nan=0.0, posinf=0.0, neginf=0.0)
    sample_cov = 0.5 * (sample_cov + sample_cov.T)

    n = int(sample_cov.shape[0])
    mu = float(np.trace(sample_cov) / max(1, n))
    identity_target = np.eye(n, dtype=float) * mu

    if shrinkage is None:
        beta = float(np.linalg.norm(sample_cov - identity_target, ord="fro") ** 2)
        alpha = float(np.linalg.norm(sample_cov, ord="fro") ** 2)
        if alpha <= 1e-12:
            lam = 0.60
        else:
            lam = float(np.clip(beta / (alpha + 1e-12), 0.20, 0.60))
    else:
        lam = float(np.clip(shrinkage, 0.0, 1.0))

    shrunk = (1.0 - lam) * sample_cov + lam * identity_target
    shrunk = np.nan_to_num(shrunk, nan=0.0, posinf=0.0, neginf=0.0)
    shrunk = 0.5 * (shrunk + shrunk.T)
    if ridge > 0.0:
        shrunk = shrunk + np.eye(n, dtype=float) * float(ridge)

    floor = float(max(1e-10, eigen_floor))
    try:
        eigvals, eigvecs = np.linalg.eigh(shrunk)
        eigvals = np.clip(eigvals, floor, None)
        shrunk = eigvecs @ np.diag(eigvals) @ eigvecs.T
        shrunk = 0.5 * (shrunk + shrunk.T)
        cond = float(np.max(eigvals) / max(float(np.min(eigvals)), 1e-12))
    except Exception:
        eigvals = np.full(n, floor, dtype=float)
        shrunk = np.eye(n, dtype=float) * floor
        cond = np.inf
    return shrunk, eigvals, cond, lam


def stable_inverse(cov: np.ndarray, *, rcond: float = 1e-5) -> np.ndarray:
    """Numerically stable inverse proxy for near-singular covariance matrices."""
    return np.linalg.pinv(np.asarray(cov, dtype=float), rcond=float(max(1e-12, rcond)))


def compute_weights(mu_vector: np.ndarray, cov: np.ndarray, *, rcond: float = 1e-5) -> np.ndarray:
    """Compute normalized Σ⁻¹μ weights."""
    inv_cov = stable_inverse(cov, rcond=rcond)
    raw_w = np.asarray(inv_cov @ np.asarray(mu_vector, dtype=float), dtype=float)
    gross = float(np.abs(raw_w).sum())
    if gross > 1e-8:
        raw_w = raw_w / gross
    return raw_w


def _normalize_weights(
    raw: np.ndarray,
    *,
    long_only: bool,
    target_gross: float,
    max_abs_weight: float,
) -> np.ndarray:
    w = np.asarray(raw, dtype=float).copy()
    if long_only:
        w = np.clip(w, 0.0, None)
    if float(max_abs_weight) > 0:
        w = np.clip(w, -float(max_abs_weight), float(max_abs_weight))
    gross = float(np.abs(w).sum())
    if gross <= 1e-12:
        w = np.ones_like(w, dtype=float)
        if long_only:
            w = np.clip(w, 0.0, None)
        gross = float(np.abs(w).sum())
    scale = float(max(1e-12, target_gross)) / max(gross, 1e-12)
    return w * scale


def optimize_family_blend(
    family_returns: pd.DataFrame,
    *,
    expected_returns: Mapping[str, float] | pd.Series | None = None,
    family_turnover: Mapping[str, float] | None = None,
    previous_weights: Mapping[str, float] | None = None,
    lookback_periods: int = 756,
    shrinkage: float | None = None,
    eigen_floor: float = 1e-4,
    ridge: float = 1e-6,
    transaction_cost_penalty: float = 0.0,
    allocation_turnover_cap: float = 0.20,
    long_only: bool = False,
    max_abs_weight: float = 0.60,
    target_gross: float = 1.0,
    target_annual_vol: float | None = None,
    periods_per_year: int = 252,
    min_history: int = 40,
    non_overlap_stride: int = 1,
) -> Dict[str, Any]:
    """Compute Σ⁻¹μ family weights with shrinkage, turnover governance, and vol targeting."""
    if family_returns is None or family_returns.empty:
        return {
            "status": "empty_returns",
            "weights": {},
            "vol_target_scale": 1.0,
            "diagnostics": {},
        }

    returns = family_returns.copy()
    if not isinstance(returns.index, pd.DatetimeIndex):
        returns.index = pd.to_datetime(returns.index, errors="coerce")
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
    if returns.empty:
        return {
            "status": "empty_after_clean",
            "weights": {},
            "vol_target_scale": 1.0,
            "diagnostics": {},
        }

    keep_cols = [c for c in returns.columns if int(returns[c].notna().sum()) >= int(min_history)]
    returns = returns[keep_cols].dropna(axis=0, how="any")
    if returns.empty or returns.shape[1] == 0:
        return {
            "status": "insufficient_history",
            "weights": {},
            "vol_target_scale": 1.0,
            "diagnostics": {},
        }

    if int(lookback_periods) > 0:
        returns = returns.tail(int(lookback_periods))
    cols = list(returns.columns)
    n = len(cols)
    if n == 0:
        return {
            "status": "no_columns",
            "weights": {},
            "vol_target_scale": 1.0,
            "diagnostics": {},
        }

    if expected_returns is None:
        mu = returns.mean().to_numpy(dtype=float)
    else:
        if isinstance(expected_returns, pd.Series):
            mu = np.asarray([float(expected_returns.get(c, 0.0)) for c in cols], dtype=float)
        else:
            mu = np.asarray([float((expected_returns or {}).get(c, 0.0)) for c in cols], dtype=float)
    mu = np.nan_to_num(mu, nan=0.0, posinf=0.0, neginf=0.0)

    tc = float(max(0.0, transaction_cost_penalty))
    if tc > 0.0 and family_turnover:
        to = np.asarray([float((family_turnover or {}).get(c, 0.0)) for c in cols], dtype=float)
        mu = mu - tc * to

    returns_mat = returns.to_numpy(dtype=float)
    cov, eigvals, cond, used_shrinkage = robust_ledoit_wolf_cov(
        returns_mat,
        shrinkage=shrinkage,
        eigen_floor=float(eigen_floor),
        ridge=float(ridge),
    )
    adaptive_shrinkage_applied = False
    if cond > 10000.0:
        # Escalate shrinkage into institutional stability band when needed.
        forced = float(np.clip(max(0.65, used_shrinkage), 0.60, 0.70))
        if forced > used_shrinkage + 1e-12:
            cov, eigvals, cond, used_shrinkage = robust_ledoit_wolf_cov(
                returns_mat,
                shrinkage=forced,
                eigen_floor=float(eigen_floor),
                ridge=float(ridge),
            )
            adaptive_shrinkage_applied = True

    try:
        raw = compute_weights(mu, cov, rcond=1e-5)
    except Exception:
        raw = mu.copy()

    if float(np.abs(raw).sum()) <= 1e-12:
        raw = np.ones(n, dtype=float)

    weights_vec = _normalize_weights(
        raw,
        long_only=bool(long_only),
        target_gross=float(target_gross),
        max_abs_weight=float(max_abs_weight),
    )

    # One-way allocation turnover cap.
    all_keys = sorted(set(cols) | set((previous_weights or {}).keys()))
    prev_vec = np.asarray([float((previous_weights or {}).get(k, 0.0)) for k in all_keys], dtype=float)
    new_map = {c: float(weights_vec[i]) for i, c in enumerate(cols)}
    new_vec = np.asarray([float(new_map.get(k, 0.0)) for k in all_keys], dtype=float)
    turnover = 0.5 * float(np.abs(new_vec - prev_vec).sum())
    cap = float(max(0.0, allocation_turnover_cap))
    if cap > 0.0 and turnover > cap and turnover > 1e-12:
        blend = cap / turnover
        new_vec = prev_vec + blend * (new_vec - prev_vec)
        gross = float(np.abs(new_vec).sum())
        if gross > 1e-12:
            new_vec = new_vec / gross * float(max(1e-12, target_gross))
        turnover = 0.5 * float(np.abs(new_vec - prev_vec).sum())
    final_weights = {k: float(v) for k, v in zip(all_keys, new_vec) if abs(float(v)) > 1e-10}

    aligned_vec = np.asarray([float(final_weights.get(c, 0.0)) for c in cols], dtype=float)
    combined = returns.to_numpy(dtype=float) @ aligned_vec
    realized_vol = float(np.std(combined, ddof=1)) if len(combined) > 1 else 0.0
    realized_ann_vol = realized_vol * np.sqrt(float(max(1, periods_per_year)))
    realized_ann_return = float(np.mean(combined)) * float(max(1, periods_per_year))
    sharpe_like = float(realized_ann_return / (realized_ann_vol + 1e-12))
    non_overlap_stride = int(max(1, non_overlap_stride))
    non_overlap_count = 0
    non_overlap_ann_return = 0.0
    non_overlap_ann_vol = 0.0
    non_overlap_sharpe_like = 0.0
    if non_overlap_stride > 1 and len(combined) >= 3:
        ppy_non = float(max(1.0, float(periods_per_year) / float(non_overlap_stride)))
        nr: List[float] = []
        nv: List[float] = []
        ns: List[float] = []
        for off in range(non_overlap_stride):
            sub = np.asarray(combined[off::non_overlap_stride], dtype=float)
            if len(sub) < 3:
                continue
            v = float(np.std(sub, ddof=1))
            ar = float(np.mean(sub)) * ppy_non
            av = v * np.sqrt(ppy_non)
            sr = float(ar / (av + 1e-12))
            nr.append(ar)
            nv.append(av)
            ns.append(sr)
        if ns:
            non_overlap_count = int(len(ns))
            non_overlap_ann_return = float(np.mean(nr))
            non_overlap_ann_vol = float(np.mean(nv))
            non_overlap_sharpe_like = float(np.mean(ns))

    vol_target_scale = 1.0
    if target_annual_vol is not None and float(target_annual_vol) > 0.0 and realized_ann_vol > 1e-12:
        vol_target_scale = float(target_annual_vol) / realized_ann_vol

    return {
        "status": "ok",
        "weights": {k: float(v) for k, v in sorted(final_weights.items(), key=lambda x: x[0])},
        "vol_target_scale": float(vol_target_scale),
        "diagnostics": {
            "n_families": int(n),
            "lookback_rows": int(len(returns)),
            "expected_returns": {c: float(mu[i]) for i, c in enumerate(cols)},
            "covariance_condition_number": float(cond),
            "covariance_min_eigenvalue": float(np.min(eigvals)) if len(eigvals) else 0.0,
            "shrinkage_requested": None if shrinkage is None else float(shrinkage),
            "shrinkage_used": float(used_shrinkage),
            "adaptive_shrinkage_applied": bool(adaptive_shrinkage_applied),
            "covariance_target_condition_max": 5000.0,
            "covariance_target_min_eigenvalue": float(max(1e-4, float(eigen_floor))),
            "covariance_condition_breach": bool(cond > 5000.0),
            "covariance_eigen_breach": bool(
                (float(np.min(eigvals)) if len(eigvals) else 0.0) < float(max(1e-4, float(eigen_floor)))
            ),
            "estimated_turnover": float(turnover),
            "turnover_cap": float(cap),
            "realized_annual_return": float(realized_ann_return),
            "realized_annual_vol": float(realized_ann_vol),
            "realized_sharpe_like": float(sharpe_like),
            "non_overlap_stride": int(non_overlap_stride),
            "non_overlap_offsets_used": int(non_overlap_count),
            "non_overlap_annual_return": float(non_overlap_ann_return),
            "non_overlap_annual_vol": float(non_overlap_ann_vol),
            "non_overlap_sharpe_like": float(non_overlap_sharpe_like),
        },
    }


def estimate_stacked_ic(
    base_ic: float,
    n_signals: int,
    avg_pairwise_corr: float,
) -> float:
    """Approximate combined IC from many weakly-correlated signals."""
    n = int(max(1, n_signals))
    rho = float(np.clip(avg_pairwise_corr, -0.99, 0.99))
    denom = np.sqrt(max(1e-12, 1.0 + (n - 1.0) * rho))
    return float(float(base_ic) * np.sqrt(float(n)) / denom)


def simulate_signal_stacking(
    *,
    base_ic: float = 0.02,
    n_signals: int = 200,
    corr_grid: Iterable[float] = (0.05, 0.10, 0.20),
) -> Dict[str, Any]:
    scenarios: List[Dict[str, float]] = []
    for rho in corr_grid:
        ic_comb = estimate_stacked_ic(base_ic=float(base_ic), n_signals=int(n_signals), avg_pairwise_corr=float(rho))
        scenarios.append(
            {
                "avg_pairwise_corr": float(rho),
                "combined_ic": float(ic_comb),
            }
        )
    return {
        "base_ic": float(base_ic),
        "n_signals": int(n_signals),
        "scenarios": scenarios,
    }


def compute_live_monitoring_metrics(
    family_returns: pd.DataFrame,
    *,
    family_ic_daily: pd.DataFrame | None = None,
    lookback_periods: int = 60,
    corr_lookback_periods: int = 60,
    periods_per_year: int = 252,
) -> Dict[str, Any]:
    """Build production monitoring metrics for family-level alpha health."""
    if family_returns is None or family_returns.empty:
        return {"status": "empty_returns", "alerts": []}

    rets = family_returns.copy()
    if not isinstance(rets.index, pd.DatetimeIndex):
        rets.index = pd.to_datetime(rets.index, errors="coerce")
    rets = rets.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
    rets = rets.dropna(axis=0, how="any")
    if rets.empty:
        return {"status": "empty_after_clean", "alerts": []}

    lb = int(max(20, lookback_periods))
    cb = int(max(20, corr_lookback_periods))
    tail = rets.tail(lb)
    recent_corr = rets.tail(cb).corr()
    full_corr = rets.corr()

    def _offdiag_median_abs(corr_df: pd.DataFrame) -> float:
        if corr_df is None or corr_df.empty or corr_df.shape[0] < 2:
            return 0.0
        mat = np.asarray(corr_df, dtype=float)
        mask = ~np.eye(mat.shape[0], dtype=bool)
        vals = np.abs(mat[mask])
        vals = vals[np.isfinite(vals)]
        return float(np.median(vals)) if len(vals) else 0.0

    med_abs_recent_corr = _offdiag_median_abs(recent_corr)
    med_abs_full_corr = _offdiag_median_abs(full_corr)
    corr_drift = 0.0
    if not recent_corr.empty and not full_corr.empty:
        cols = [c for c in recent_corr.columns if c in full_corr.columns]
        if cols:
            diff = recent_corr.loc[cols, cols] - full_corr.loc[cols, cols]
            mat = np.asarray(diff, dtype=float)
            mask = ~np.eye(mat.shape[0], dtype=bool)
            vals = np.abs(mat[mask])
            vals = vals[np.isfinite(vals)]
            corr_drift = float(np.mean(vals)) if len(vals) else 0.0

    family_health: Dict[str, Dict[str, float]] = {}
    alerts: list[str] = []
    for col in tail.columns:
        s = pd.to_numeric(tail[col], errors="coerce").dropna()
        if s.empty:
            continue
        ann_ret = float(s.mean()) * float(max(1, periods_per_year))
        ann_vol = float(s.std(ddof=1)) * np.sqrt(float(max(1, periods_per_year))) if len(s) > 1 else 0.0
        sharpe = float(ann_ret / (ann_vol + 1e-12))
        hit = float((s > 0).mean())
        neg_streak = 0
        run = 0
        for v in s.iloc[::-1]:
            if float(v) < 0.0:
                run += 1
                neg_streak = max(neg_streak, run)
            else:
                break
        family_health[col] = {
            "annual_return": ann_ret,
            "annual_vol": ann_vol,
            "sharpe_like": sharpe,
            "hit_rate": hit,
            "recent_negative_streak": float(neg_streak),
        }
        if sharpe < 0.0 and neg_streak >= 20:
            alerts.append(f"{col}: negative_performance_streak")

    if med_abs_recent_corr > 0.60:
        alerts.append("diversification_collapse_risk")

    ic_summary: Dict[str, Dict[str, float]] = {}
    if isinstance(family_ic_daily, pd.DataFrame) and not family_ic_daily.empty:
        ic_tail = family_ic_daily.tail(lb)
        for col in ic_tail.columns:
            s = pd.to_numeric(ic_tail[col], errors="coerce").dropna()
            if s.empty:
                continue
            n = len(s)
            mean_ic = float(s.mean())
            std_ic = float(s.std(ddof=1)) if n > 1 else 0.0
            t_stat = float(mean_ic / (std_ic / np.sqrt(float(n)) + 1e-12)) if n > 2 else 0.0
            pos = float((s > 0.0).mean())
            ic_summary[col] = {
                "mean_ic": mean_ic,
                "std_ic": std_ic,
                "t_stat": t_stat,
                "positive_rate": pos,
            }
            if mean_ic < 0.0 and t_stat < 0.0:
                alerts.append(f"{col}: ic_degradation")

    eq = rets.mean(axis=1)
    wealth = (1.0 + eq).cumprod()
    run_max = wealth.cummax()
    drawdown = wealth / (run_max + 1e-12) - 1.0
    trough_idx = int(np.argmin(drawdown.values)) if len(drawdown) else 0
    trough_date = drawdown.index[trough_idx] if len(drawdown) else None
    peak_date = None
    drawdown_contrib: Dict[str, float] = {}
    if trough_date is not None:
        peak_slice = wealth.iloc[: trough_idx + 1]
        if len(peak_slice):
            peak_date = peak_slice.index[int(np.argmax(peak_slice.values))]
        if peak_date is not None and peak_date <= trough_date:
            window = rets.loc[(rets.index >= peak_date) & (rets.index <= trough_date)]
            if not window.empty:
                gross = float(np.abs(window.sum(axis=0)).sum())
                if gross <= 1e-12:
                    gross = 1.0
                drawdown_contrib = {
                    str(c): float(window[c].sum() / gross) for c in window.columns
                }

    return {
        "status": "ok",
        "alerts": sorted(set(alerts)),
        "family_health": family_health,
        "ic_health": ic_summary,
        "correlation_drift": {
            "median_abs_corr_recent": float(med_abs_recent_corr),
            "median_abs_corr_full": float(med_abs_full_corr),
            "mean_abs_corr_shift": float(corr_drift),
        },
        "drawdown_decomposition": {
            "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
            "peak_date": str(peak_date) if peak_date is not None else None,
            "trough_date": str(trough_date) if trough_date is not None else None,
            "family_contributions": drawdown_contrib,
        },
    }
