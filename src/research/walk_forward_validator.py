"""Walk-forward validation metrics for research models."""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd


EPS = 1e-12
MAX_ABS_PERIOD_RETURN = 1.0
MIN_PERIOD_RETURN = -0.999


def _max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    safe = np.asarray(returns, dtype=float).reshape(-1)
    safe = np.nan_to_num(
        safe,
        nan=0.0,
        posinf=MAX_ABS_PERIOD_RETURN,
        neginf=MIN_PERIOD_RETURN,
    )
    safe = np.clip(safe, MIN_PERIOD_RETURN, MAX_ABS_PERIOD_RETURN)
    curve = np.cumprod(1.0 + safe)
    peaks = np.maximum.accumulate(curve)
    dd = (curve / np.maximum(peaks, EPS)) - 1.0
    return float(abs(np.min(dd)))


def _safe_spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 8 or len(b) < 8:
        return 0.0
    if float(np.std(a)) <= EPS or float(np.std(b)) <= EPS:
        return 0.0
    sa = pd.Series(a)
    sb = pd.Series(b)
    val = sa.corr(sb, method="spearman")
    return float(val) if np.isfinite(val) else 0.0


def _cap_and_renormalize(weights: np.ndarray, cap: float) -> np.ndarray:
    w = np.asarray(weights, dtype=float).reshape(-1)
    if len(w) == 0:
        return w
    cap_v = float(max(1e-6, cap))
    w = np.clip(w, 0.0, cap_v)
    total = float(np.sum(w))
    if total <= EPS:
        return np.zeros_like(w, dtype=float)
    return w / total


def _apply_sector_caps(
    *,
    tickers: list[str],
    weights: np.ndarray,
    sectors_by_ticker: Dict[str, str],
    max_sector_weight: float,
) -> np.ndarray:
    """Cap sector concentration on one leg and renormalize weights."""
    w = np.asarray(weights, dtype=float).reshape(-1)
    if len(w) == 0 or len(tickers) != len(w):
        return w
    cap_v = float(min(1.0, max(1e-6, max_sector_weight)))
    if cap_v >= 0.999:
        return _cap_and_renormalize(w, cap=1.0)

    out = np.clip(w, 0.0, np.inf)
    # Iterative projection is robust enough for small cross-sections.
    for _ in range(8):
        total = float(np.sum(out))
        if total <= EPS:
            return np.zeros_like(out, dtype=float)
        out = out / total
        sector_totals: Dict[str, float] = {}
        for i, tk in enumerate(tickers):
            sec = str(sectors_by_ticker.get(str(tk), "UNKNOWN"))
            sector_totals[sec] = float(sector_totals.get(sec, 0.0) + float(out[i]))
        overflow = False
        for sec, sec_w in sector_totals.items():
            if sec_w <= cap_v + 1e-12:
                continue
            overflow = True
            scale = cap_v / max(sec_w, EPS)
            for i, tk in enumerate(tickers):
                if str(sectors_by_ticker.get(str(tk), "UNKNOWN")) == sec:
                    out[i] *= scale
        if not overflow:
            break
    total = float(np.sum(out))
    return out / total if total > EPS else np.zeros_like(out, dtype=float)


def _weighted_leg_return(group: pd.DataFrame, weights_by_ticker: Dict[str, float]) -> float:
    if group.empty or not weights_by_ticker:
        return 0.0
    tickers = group["ticker"].astype(str).to_numpy()
    y = group["y_true"].to_numpy(dtype=float)
    w = np.asarray([float(weights_by_ticker.get(str(t), 0.0)) for t in tickers], dtype=float)
    mask = w > EPS
    if int(mask.sum()) <= 0:
        return 0.0
    w = w[mask]
    y = y[mask]
    total = float(np.sum(w))
    if total <= EPS:
        return 0.0
    w = w / total
    return float(np.dot(w, y))


def build_cross_sectional_portfolio_returns(
    *,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    dates: Sequence | np.ndarray,
    tickers: Sequence | np.ndarray | None = None,
    sectors: Sequence | np.ndarray | None = None,
    vol: np.ndarray | None = None,
    long_short_quantile: float = 0.20,
    min_assets_per_day: int = 8,
    max_weight_per_asset: float = 0.10,
    use_vol_scaling: bool = True,
    rebalance_frequency_days: int = 1,
    sector_neutralize: bool = False,
    max_sector_weight: float = 1.0,
    transaction_cost_bps_per_side: float = 0.0,
    return_diagnostics: bool = False,
) -> np.ndarray | Dict[str, Any]:
    """Build daily long/short portfolio returns from cross-sectional predictions."""
    y_t = np.asarray(y_true, dtype=float).reshape(-1)
    y_p = np.asarray(y_pred, dtype=float).reshape(-1)
    d = pd.to_datetime(pd.Series(dates), errors="coerce")
    n = int(min(len(y_t), len(y_p), len(d)))
    if n <= 0:
        return np.asarray([], dtype=float)

    y_t = np.nan_to_num(y_t[:n], nan=0.0, posinf=0.0, neginf=0.0)
    y_p = np.nan_to_num(y_p[:n], nan=0.0, posinf=0.0, neginf=0.0)
    d = d.iloc[:n]
    if tickers is None:
        ticker_arr = np.asarray([f"asset_{i}" for i in range(n)], dtype=object)
    else:
        ticker_arr = np.asarray(tickers).reshape(-1)
        if len(ticker_arr) < n:
            pad = np.asarray([f"asset_{i}" for i in range(len(ticker_arr), n)], dtype=object)
            ticker_arr = np.concatenate([ticker_arr, pad], axis=0)
        ticker_arr = ticker_arr[:n]

    if sectors is None:
        sector_arr = np.asarray(["UNKNOWN"] * n, dtype=object)
    else:
        sector_arr = np.asarray(sectors).reshape(-1)
        if len(sector_arr) < n:
            pad = np.asarray(["UNKNOWN"] * (n - len(sector_arr)), dtype=object)
            sector_arr = np.concatenate([sector_arr, pad], axis=0)
        sector_arr = pd.Series(sector_arr[:n], dtype="string").fillna("UNKNOWN").astype(str).to_numpy(dtype=object)

    if vol is None:
        vol_arr = np.full(n, np.nan, dtype=float)
    else:
        vol_arr = np.asarray(vol, dtype=float).reshape(-1)
        if len(vol_arr) < n:
            pad = np.full(n - len(vol_arr), np.nan, dtype=float)
            vol_arr = np.concatenate([vol_arr, pad], axis=0)
        vol_arr = vol_arr[:n]

    q = float(min(0.49, max(0.05, long_short_quantile)))
    min_assets = max(4, int(min_assets_per_day))
    max_w = float(min(0.50, max(0.01, max_weight_per_asset)))
    rebalance_every = max(1, int(rebalance_frequency_days))
    max_sector_w = float(min(1.0, max(1e-3, max_sector_weight)))
    txn_cost_side = float(max(0.0, transaction_cost_bps_per_side)) / 10_000.0

    work = pd.DataFrame(
        {
            "date": d,
            "ticker": pd.Series(ticker_arr, dtype="string").fillna("").astype(str),
            "sector": pd.Series(sector_arr, dtype="string").fillna("UNKNOWN").astype(str),
            "y_true": np.clip(y_t, -MAX_ABS_PERIOD_RETURN, MAX_ABS_PERIOD_RETURN),
            "y_pred": y_p,
            "vol": np.abs(vol_arr),
        }
    ).dropna(subset=["date"])
    if work.empty:
        empty = np.asarray([], dtype=float)
        if not return_diagnostics:
            return empty
        return {
            "returns": empty,
            "portfolio_days": 0.0,
            "rebalance_count": 0.0,
            "avg_turnover": 0.0,
            "median_turnover": 0.0,
            "avg_overlap": 0.0,
            "median_holding_days": 0.0,
            "avg_assets_per_day": 0.0,
            "avg_selected_assets": 0.0,
            "avg_txn_cost_per_rebalance": 0.0,
        }

    daily_returns: list[float] = []
    long_weights_by_ticker: Dict[str, float] = {}
    short_weights_by_ticker: Dict[str, float] = {}
    prev_combined_weights: Dict[str, float] = {}
    prev_names: set[str] = set()
    hold_counters: Dict[str, int] = {}
    completed_holds: list[int] = []
    rebalance_turnovers: list[float] = []
    rebalance_overlaps: list[float] = []
    rebalance_costs: list[float] = []
    assets_per_day: list[int] = []
    selected_assets_per_rebalance: list[int] = []
    day_counter = 0
    for _, g in work.groupby("date", sort=True):
        assets_per_day.append(int(len(g)))
        if len(g) < min_assets:
            continue

        do_rebalance = (day_counter % rebalance_every == 0) or (not long_weights_by_ticker) or (not short_weights_by_ticker)
        day_counter += 1
        tx_cost = 0.0

        if do_rebalance:
            # Rank-based buckets are more stable than raw-score thresholds.
            p_rank = g["y_pred"].rank(method="average", pct=True)
            long_mask = p_rank >= (1.0 - q)
            short_mask = p_rank <= q
            if int(long_mask.sum()) < 1 or int(short_mask.sum()) < 1:
                continue

            if use_vol_scaling and g["vol"].notna().any():
                inv_vol = 1.0 / np.clip(g["vol"].to_numpy(dtype=float), 1e-4, np.inf)
            else:
                inv_vol = np.ones(len(g), dtype=float)

            long_df = g.loc[long_mask, ["ticker", "sector"]].copy()
            short_df = g.loc[short_mask, ["ticker", "sector"]].copy()
            long_tickers = long_df["ticker"].astype(str).tolist()
            short_tickers = short_df["ticker"].astype(str).tolist()
            long_sec_map = {str(t): str(s) for t, s in zip(long_df["ticker"], long_df["sector"])}
            short_sec_map = {str(t): str(s) for t, s in zip(short_df["ticker"], short_df["sector"])}

            if bool(sector_neutralize):
                long_secs = {str(s) for s in long_df["sector"].astype(str).tolist()}
                short_secs = {str(s) for s in short_df["sector"].astype(str).tolist()}
                common_secs = sorted(s for s in long_secs.intersection(short_secs) if s)
                if not common_secs:
                    continue
                sec_alloc = 1.0 / float(len(common_secs))
                long_weights_by_ticker = {}
                short_weights_by_ticker = {}
                for sec in common_secs:
                    lm = long_df["sector"].astype(str).eq(sec).to_numpy()
                    sm = short_df["sector"].astype(str).eq(sec).to_numpy()
                    if int(lm.sum()) <= 0 or int(sm.sum()) <= 0:
                        continue
                    lw = _cap_and_renormalize(inv_vol[long_mask.to_numpy()][lm], cap=max_w) * sec_alloc
                    sw = _cap_and_renormalize(inv_vol[short_mask.to_numpy()][sm], cap=max_w) * sec_alloc
                    for tk, w in zip(np.asarray(long_tickers, dtype=object)[lm].tolist(), lw.tolist()):
                        long_weights_by_ticker[str(tk)] = float(long_weights_by_ticker.get(str(tk), 0.0) + float(w))
                    for tk, w in zip(np.asarray(short_tickers, dtype=object)[sm].tolist(), sw.tolist()):
                        short_weights_by_ticker[str(tk)] = float(short_weights_by_ticker.get(str(tk), 0.0) + float(w))
                if not long_weights_by_ticker or not short_weights_by_ticker:
                    continue
                # Final per-leg cap and renormalization.
                lt = list(long_weights_by_ticker.keys())
                st = list(short_weights_by_ticker.keys())
                lw = _apply_sector_caps(
                    tickers=lt,
                    weights=np.asarray([long_weights_by_ticker[t] for t in lt], dtype=float),
                    sectors_by_ticker=long_sec_map,
                    max_sector_weight=max_sector_w,
                )
                sw = _apply_sector_caps(
                    tickers=st,
                    weights=np.asarray([short_weights_by_ticker[t] for t in st], dtype=float),
                    sectors_by_ticker=short_sec_map,
                    max_sector_weight=max_sector_w,
                )
                long_weights_by_ticker = {str(t): float(w) for t, w in zip(lt, lw.tolist())}
                short_weights_by_ticker = {str(t): float(w) for t, w in zip(st, sw.tolist())}
            else:
                long_w = _cap_and_renormalize(inv_vol[long_mask.to_numpy()], cap=max_w)
                short_w = _cap_and_renormalize(inv_vol[short_mask.to_numpy()], cap=max_w)
                if len(long_w) == 0 or len(short_w) == 0:
                    continue
                long_w = _apply_sector_caps(
                    tickers=long_tickers,
                    weights=long_w,
                    sectors_by_ticker=long_sec_map,
                    max_sector_weight=max_sector_w,
                )
                short_w = _apply_sector_caps(
                    tickers=short_tickers,
                    weights=short_w,
                    sectors_by_ticker=short_sec_map,
                    max_sector_weight=max_sector_w,
                )
                long_weights_by_ticker = {str(tk): float(w) for tk, w in zip(long_tickers, long_w)}
                short_weights_by_ticker = {str(tk): float(w) for tk, w in zip(short_tickers, short_w)}

            selected_assets_per_rebalance.append(int(len(long_weights_by_ticker) + len(short_weights_by_ticker)))

            combined_weights: Dict[str, float] = {}
            for tk, w in long_weights_by_ticker.items():
                combined_weights[str(tk)] = float(combined_weights.get(str(tk), 0.0) + 0.5 * float(w))
            for tk, w in short_weights_by_ticker.items():
                combined_weights[str(tk)] = float(combined_weights.get(str(tk), 0.0) - 0.5 * float(w))

            if prev_combined_weights:
                all_tickers = set(prev_combined_weights.keys()).union(set(combined_weights.keys()))
                turnover = float(sum(abs(float(combined_weights.get(t, 0.0)) - float(prev_combined_weights.get(t, 0.0))) for t in all_tickers))
                rebalance_turnovers.append(turnover)
                if txn_cost_side > 0.0:
                    tx_cost = float(turnover * txn_cost_side)
                curr_names = set(long_weights_by_ticker.keys()).union(set(short_weights_by_ticker.keys()))
                overlap = float(len(curr_names.intersection(prev_names)) / max(1, len(prev_names)))
                rebalance_overlaps.append(overlap)
                prev_names = curr_names
            else:
                prev_names = set(long_weights_by_ticker.keys()).union(set(short_weights_by_ticker.keys()))
            prev_combined_weights = combined_weights
            rebalance_costs.append(float(tx_cost))

        long_ret = _weighted_leg_return(g, long_weights_by_ticker)
        short_ret = _weighted_leg_return(g, short_weights_by_ticker)
        # 50/50 dollar-neutral long-short basket.
        day_ret = 0.5 * long_ret - 0.5 * short_ret - float(tx_cost)
        if np.isfinite(day_ret):
            daily_returns.append(float(np.clip(day_ret, MIN_PERIOD_RETURN, MAX_ABS_PERIOD_RETURN)))

        active_names = set(long_weights_by_ticker.keys()).union(set(short_weights_by_ticker.keys()))
        for tk in active_names:
            hold_counters[str(tk)] = int(hold_counters.get(str(tk), 0) + 1)
        for tk in list(hold_counters.keys()):
            if tk not in active_names:
                completed_holds.append(int(hold_counters.get(tk, 0)))
                hold_counters.pop(tk, None)

    for tk, days in hold_counters.items():
        if int(days) > 0:
            completed_holds.append(int(days))

    rets = np.asarray(daily_returns, dtype=float)
    if not return_diagnostics:
        return rets
    return {
        "returns": rets,
        "portfolio_days": float(len(rets)),
        "rebalance_count": float(len(rebalance_costs)),
        "avg_turnover": float(np.mean(rebalance_turnovers)) if rebalance_turnovers else 0.0,
        "median_turnover": float(np.median(rebalance_turnovers)) if rebalance_turnovers else 0.0,
        "avg_overlap": float(np.mean(rebalance_overlaps)) if rebalance_overlaps else 0.0,
        "median_holding_days": float(np.median(completed_holds)) if completed_holds else 0.0,
        "avg_assets_per_day": float(np.mean(assets_per_day)) if assets_per_day else 0.0,
        "avg_selected_assets": float(np.mean(selected_assets_per_rebalance)) if selected_assets_per_rebalance else 0.0,
        "avg_txn_cost_per_rebalance": float(np.mean(rebalance_costs)) if rebalance_costs else 0.0,
    }


def _decile_monotonicity(pred: np.ndarray, realized: np.ndarray) -> Dict[str, float]:
    if len(pred) < 40:
        return {"top_bottom_spread": 0.0, "slope": 0.0, "monotonic_pass": 0.0}

    f = pd.DataFrame({"p": pred, "r": realized}).dropna()
    if len(f) < 40:
        return {"top_bottom_spread": 0.0, "slope": 0.0, "monotonic_pass": 0.0}

    try:
        f["d"] = pd.qcut(f["p"].rank(method="first"), 10, labels=False, duplicates="drop")
    except Exception:
        return {"top_bottom_spread": 0.0, "slope": 0.0, "monotonic_pass": 0.0}

    agg = f.groupby("d", as_index=False)["r"].mean().sort_values("d")
    if len(agg) < 4:
        return {"top_bottom_spread": 0.0, "slope": 0.0, "monotonic_pass": 0.0}

    x = agg["d"].to_numpy(dtype=float)
    y = agg["r"].to_numpy(dtype=float)
    slope = float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else 0.0
    spread = float(y[-1] - y[0])
    monotonic = 1.0 if slope > 0.0 and spread > 0.0 else 0.0
    return {
        "top_bottom_spread": spread,
        "slope": slope,
        "monotonic_pass": monotonic,
    }


def compute_window_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    dates: Sequence | np.ndarray | None = None,
    tickers: Sequence | np.ndarray | None = None,
    sectors: Sequence | np.ndarray | None = None,
    vol: np.ndarray | None = None,
    long_short_quantile: float = 0.20,
    min_assets_per_day: int = 8,
    max_weight_per_asset: float = 0.10,
    use_vol_scaling: bool = True,
    rebalance_frequency_days: int = 1,
    sector_neutralize: bool = False,
    max_sector_weight: float = 1.0,
    transaction_cost_bps_per_side: float = 0.0,
) -> Dict[str, float]:
    """Compute return/risk + predictive diagnostics for one test window."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = min(len(y_true), len(y_pred))
    if n == 0:
        return {
            "n_obs": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "hit_rate": 0.0,
            "ic": 0.0,
            "ic_abs": 0.0,
            "top_bottom_spread": 0.0,
            "decile_slope": 0.0,
            "decile_monotonic_pass": 0.0,
            "prediction_dispersion": 0.0,
            "avg_turnover": 0.0,
            "median_turnover": 0.0,
            "avg_overlap": 0.0,
            "median_holding_days": 0.0,
            "avg_assets_per_day": 0.0,
            "avg_selected_assets": 0.0,
            "avg_txn_cost_per_rebalance": 0.0,
            "rebalance_count": 0.0,
        }

    y_true = y_true[:n]
    y_pred = y_pred[:n]
    y_true = np.nan_to_num(y_true, nan=0.0, posinf=0.0, neginf=0.0)
    y_pred = np.nan_to_num(y_pred, nan=0.0, posinf=0.0, neginf=0.0)

    signal = np.tanh(np.clip(y_pred, -20.0, 20.0))
    realized = np.clip(y_true, -MAX_ABS_PERIOD_RETURN, MAX_ABS_PERIOD_RETURN)
    strat_ret = np.asarray([], dtype=float)
    port_diag: Dict[str, Any] = {}
    if dates is not None:
        built = build_cross_sectional_portfolio_returns(
            y_true=realized,
            y_pred=y_pred,
            dates=dates,
            tickers=tickers,
            sectors=sectors,
            vol=vol,
            long_short_quantile=long_short_quantile,
            min_assets_per_day=min_assets_per_day,
            max_weight_per_asset=max_weight_per_asset,
            use_vol_scaling=use_vol_scaling,
            rebalance_frequency_days=rebalance_frequency_days,
            sector_neutralize=sector_neutralize,
            max_sector_weight=max_sector_weight,
            transaction_cost_bps_per_side=transaction_cost_bps_per_side,
            return_diagnostics=True,
        )
        if isinstance(built, dict):
            port_diag = dict(built)
            strat_ret = np.asarray(port_diag.get("returns", np.asarray([], dtype=float)), dtype=float)
        else:
            strat_ret = np.asarray(built, dtype=float)
    if len(strat_ret) == 0:
        strat_ret = signal * realized

    mean = float(np.mean(strat_ret))
    vol = float(np.std(strat_ret))
    downside = np.asarray([x for x in strat_ret if x < 0.0], dtype=float)
    downside_vol = float(np.std(downside)) if len(downside) else 0.0

    sharpe = mean / (vol + EPS)
    sortino = mean / (downside_vol + EPS)
    max_dd = _max_drawdown(strat_ret)
    ann = mean * 252.0
    calmar = ann / (max_dd + EPS)

    hit = float(np.mean(np.sign(signal) == np.sign(y_true)))
    ic = _safe_spearman(y_pred, y_true)
    dec = _decile_monotonicity(y_pred, y_true)

    return {
        "n_obs": float(n),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown": float(max_dd),
        "calmar": float(calmar),
        "hit_rate": hit,
        "ic": ic,
        "ic_abs": float(abs(ic)),
        "top_bottom_spread": float(dec["top_bottom_spread"]),
        "decile_slope": float(dec["slope"]),
        "decile_monotonic_pass": float(dec["monotonic_pass"]),
        "prediction_dispersion": float(np.std(y_pred)),
        "portfolio_days": float(len(strat_ret)),
        "avg_turnover": float(port_diag.get("avg_turnover", 0.0)),
        "median_turnover": float(port_diag.get("median_turnover", 0.0)),
        "avg_overlap": float(port_diag.get("avg_overlap", 0.0)),
        "median_holding_days": float(port_diag.get("median_holding_days", 0.0)),
        "avg_assets_per_day": float(port_diag.get("avg_assets_per_day", 0.0)),
        "avg_selected_assets": float(port_diag.get("avg_selected_assets", 0.0)),
        "avg_txn_cost_per_rebalance": float(port_diag.get("avg_txn_cost_per_rebalance", 0.0)),
        "rebalance_count": float(port_diag.get("rebalance_count", 0.0)),
    }


def aggregate_metrics(window_metrics: list[Dict[str, float]]) -> Dict[str, float]:
    if not window_metrics:
        return {
            "windows": 0.0,
            "avg_sharpe": 0.0,
            "avg_sortino": 0.0,
            "avg_max_drawdown": 0.0,
            "avg_calmar": 0.0,
            "avg_hit_rate": 0.0,
            "ic_mean": 0.0,
            "ic_std": 0.0,
            "top_bottom_spread_mean": 0.0,
            "monotonic_pass_rate": 0.0,
            "stability_score": 0.0,
            "avg_turnover": 0.0,
            "avg_overlap": 0.0,
            "median_holding_days": 0.0,
            "avg_assets_per_day": 0.0,
            "avg_selected_assets": 0.0,
            "avg_txn_cost_per_rebalance": 0.0,
            "avg_rebalance_count": 0.0,
        }

    df = pd.DataFrame(window_metrics)
    ic_mean = float(df["ic"].mean())
    ic_std = float(df["ic"].std()) if len(df) > 1 else 0.0
    monotonic_rate = float(df["decile_monotonic_pass"].mean())
    sharpe_mean = float(df["sharpe"].mean())
    sharpe_std = float(df["sharpe"].std()) if len(df) > 1 else 0.0

    # Stability rewards consistent Sharpe and monotonic cross-sectional behavior.
    stability = float((1.0 / (1.0 + abs(sharpe_std))) * (0.5 + 0.5 * monotonic_rate))

    return {
        "windows": float(len(df)),
        "avg_sharpe": sharpe_mean,
        "avg_sortino": float(df["sortino"].mean()),
        "avg_max_drawdown": float(df["max_drawdown"].mean()),
        "avg_calmar": float(df["calmar"].mean()),
        "avg_hit_rate": float(df["hit_rate"].mean()),
        "ic_mean": ic_mean,
        "ic_std": ic_std,
        "top_bottom_spread_mean": float(df["top_bottom_spread"].mean()),
        "monotonic_pass_rate": monotonic_rate,
        "stability_score": stability,
        "avg_turnover": float(df.get("avg_turnover", pd.Series([0.0])).mean()),
        "avg_overlap": float(df.get("avg_overlap", pd.Series([0.0])).mean()),
        "median_holding_days": float(df.get("median_holding_days", pd.Series([0.0])).median()),
        "avg_assets_per_day": float(df.get("avg_assets_per_day", pd.Series([0.0])).mean()),
        "avg_selected_assets": float(df.get("avg_selected_assets", pd.Series([0.0])).mean()),
        "avg_txn_cost_per_rebalance": float(df.get("avg_txn_cost_per_rebalance", pd.Series([0.0])).mean()),
        "avg_rebalance_count": float(df.get("rebalance_count", pd.Series([0.0])).mean()),
    }
