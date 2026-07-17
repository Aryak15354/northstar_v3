"""Harness v3 — the statistics/evaluation constitution for Master Plan v3.0 (D-06).

Implements Part I of the master experimentation plan as importable, tested code:

- Lockbox guard (I.5): refuses configs without a lockbox and raises if any loaded
  date crosses it.
- Per-date NaN-preserving Spearman IC (I.3): < min_pairs valid pairs -> NaN, never 0.
- HAC / Newey-West t-stat on IC series (I.3) with lag = h_weeks - 1.
- Stationary block bootstrap CI (I.3): block = 26w, 2000 resamples.
- CPCV splitter (I.5): contiguous date groups, purge + embargo, capped combos.
- Walk-forward splitter (I.5): expanding origin, purge between train/test.
- PBO via CSCV (I.5) and Deflated Sharpe Ratio (I.5).
- Benjamini-Hochberg FDR (I.3) and |rho|>0.90 dedupe clustering (I.3).
- Multi-horizon target derivation from weekly closes (I.2): target_{h}w emitted
  at experiment time from the metadata close series; tgt flavors (mkt/sec/beta/z).
- Cost block (I.6): imported from the paper-portfolio cost parameters — single
  source of truth; do not re-type numbers here.

Anti-patterns enforced here (Appendix D): no zero-fill of missing IC (D3), no
date-constant series in cross-sectional IC (D2 — raises), tripwire on |IC| > 0.15
(D12), NaN preserved everywhere.
"""

from __future__ import annotations

import itertools
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.panel_math import group_zscore  # noqa: E402


# ---------------------------------------------------------------------------
# Lockbox (I.5)
# ---------------------------------------------------------------------------

LOCKBOX_START = pd.Timestamp("2025-07-11")  # rows with date >= this are locked


class LockboxViolation(RuntimeError):
    pass


def assert_lockbox(config: dict[str, Any]) -> pd.Timestamp:
    """Every experiment config MUST declare lockbox_start; refuse otherwise."""
    raw = config.get("lockbox_start")
    if not raw:
        raise LockboxViolation("config_missing_lockbox_start: every Track B-P config must declare it")
    ts = pd.Timestamp(raw)
    if ts != LOCKBOX_START:
        raise LockboxViolation(f"nonstandard_lockbox_start:{ts.date()} != {LOCKBOX_START.date()}")
    return ts


def enforce_lockbox(frame: pd.DataFrame, config: dict[str, Any], *, date_col: str = "date") -> pd.DataFrame:
    """Physically exclude lockbox rows. FINAL-02 is the only caller allowed to
    pass config['final_02_unlock']=True (audited by the ledger)."""
    ts = assert_lockbox(config)
    if bool(config.get("final_02_unlock", False)):
        return frame
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    if bool((dates >= ts).any()):
        frame = frame.loc[dates < ts].copy()
    # hard invariant, not a filter that can silently no-op:
    remaining = pd.to_datetime(frame[date_col], errors="coerce")
    if bool((remaining >= ts).any()):
        raise LockboxViolation("lockbox_rows_survived_filter")
    return frame


# ---------------------------------------------------------------------------
# Per-date NaN-preserving Spearman IC (I.3, anti-pattern D2/D3/D12)
# ---------------------------------------------------------------------------

TRIPWIRE_ABS_IC = 0.15  # any single-signal |mean IC| above this halts for review


class LeakTripwire(RuntimeError):
    pass


def per_date_spearman_ic(
    signal: pd.Series,
    target: pd.Series,
    dates: pd.Series,
    *,
    min_pairs: int = 30,
) -> pd.Series:
    """Cross-sectional Spearman per date. Dates with < min_pairs valid pairs or a
    date-constant signal yield NaN (never 0). Raises if the signal is constant on
    EVERY date — that is a date-level (macro) series, which has no cross-section
    (anti-pattern D2)."""
    s = pd.to_numeric(signal, errors="coerce")
    t = pd.to_numeric(target, errors="coerce")
    d = pd.to_datetime(dates, errors="coerce")
    work = pd.DataFrame({"s": s, "t": t, "d": d}).dropna(subset=["d"])

    out: dict[pd.Timestamp, float] = {}
    n_constant = 0
    n_dates = 0
    for date, grp in work.groupby("d", sort=True):
        n_dates += 1
        pair = grp[["s", "t"]].dropna()
        if len(pair) < int(min_pairs):
            out[date] = np.nan
            continue
        if pair["s"].nunique() <= 1:
            n_constant += 1
            out[date] = np.nan
            continue
        rs = pair["s"].rank(method="average")
        rt = pair["t"].rank(method="average")
        rs = (rs - rs.mean()) / (rs.std(ddof=0) + 1e-12)
        rt = (rt - rt.mean()) / (rt.std(ddof=0) + 1e-12)
        out[date] = float((rs * rt).mean())
    if n_dates > 0 and n_constant == n_dates:
        raise ValueError("date_constant_signal_has_no_cross_section (anti-pattern D2: macro series?)")
    return pd.Series(out, dtype=float).sort_index()


def ic_summary(ic_series: pd.Series, *, h_weeks: int = 4, tripwire: bool = True) -> dict[str, Any]:
    """Mean IC + HAC t + bootstrap CI + annualized ICIR + n_dates."""
    ic = pd.to_numeric(ic_series, errors="coerce").dropna()
    n = int(len(ic))
    if n == 0:
        return {"mean_ic": np.nan, "hac_t": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                "icir_ann": np.nan, "n_dates": 0}
    mean = float(ic.mean())
    if tripwire and abs(mean) > TRIPWIRE_ABS_IC and n >= 20:
        raise LeakTripwire(f"abs_mean_ic_{mean:.3f}_exceeds_{TRIPWIRE_ABS_IC}: assume leak until proven otherwise")
    lag = max(0, int(h_weeks) - 1)
    t = hac_tstat(ic.to_numpy(), lag=lag)
    lo, hi = block_bootstrap_ci(ic.to_numpy(), block_len=26, n_boot=2000, alpha=0.05, seed=42)
    std = float(ic.std(ddof=1)) if n > 1 else np.nan
    icir = mean / std * math.sqrt(52.0) if std and std > 0 else np.nan
    return {"mean_ic": mean, "hac_t": float(t), "ci_lo": float(lo), "ci_hi": float(hi),
            "icir_ann": float(icir) if np.isfinite(icir) else np.nan, "n_dates": n}


# ---------------------------------------------------------------------------
# HAC / Newey-West t-stat (I.3)
# ---------------------------------------------------------------------------

def hac_tstat(x: np.ndarray, *, lag: int) -> float:
    """t-stat of mean(x) with Newey-West (Bartlett kernel) long-run variance."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.nan
    demeaned = x - x.mean()
    gamma0 = float(np.dot(demeaned, demeaned)) / n
    lrv = gamma0
    L = min(int(lag), n - 1)
    for k in range(1, L + 1):
        w = 1.0 - k / (L + 1.0)
        gamma_k = float(np.dot(demeaned[k:], demeaned[:-k])) / n
        lrv += 2.0 * w * gamma_k
    if lrv <= 0:
        lrv = gamma0  # degenerate; fall back to iid variance
    se = math.sqrt(lrv / n)
    return float(x.mean() / se) if se > 0 else np.nan


# ---------------------------------------------------------------------------
# Stationary block bootstrap CI (I.3)
# ---------------------------------------------------------------------------

def block_bootstrap_ci(
    x: np.ndarray,
    *,
    block_len: int = 26,
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Politis-Romano stationary bootstrap CI for the mean (geometric blocks with
    expected length block_len, circular wrap)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 5:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    p = 1.0 / float(max(1, block_len))
    means = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.empty(n, dtype=int)
        pos = rng.integers(0, n)
        for i in range(n):
            idx[i] = pos
            if rng.random() < p:
                pos = rng.integers(0, n)
            else:
                pos = (pos + 1) % n
        means[b] = x[idx].mean()
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))


# ---------------------------------------------------------------------------
# Splitters (I.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Split:
    train_dates: tuple  # sorted tuple of Timestamps
    test_dates: tuple


def walk_forward_splits(
    dates: Sequence[pd.Timestamp],
    *,
    first_train_end: str | pd.Timestamp,
    test_weeks: int = 26,
    step_weeks: int = 26,
    purge_weeks: int = 4,
    embargo_weeks: int = 4,
) -> list[Split]:
    """Expanding-origin walk-forward. Purge = gap between train end and test
    start; embargo applies to any subsequent refit (encoded by stepping)."""
    ds = sorted(pd.to_datetime(pd.Series(list(dates)).dropna().unique()))
    ds = [pd.Timestamp(d) for d in ds]
    first_end = pd.Timestamp(first_train_end)
    splits: list[Split] = []
    i_end = max(i for i, d in enumerate(ds) if d <= first_end) if any(d <= first_end for d in ds) else None
    if i_end is None:
        return splits
    while True:
        test_start_idx = i_end + 1 + purge_weeks
        test_end_idx = test_start_idx + test_weeks - 1
        if test_end_idx >= len(ds):
            break
        train = tuple(ds[: i_end + 1])
        test = tuple(ds[test_start_idx : test_end_idx + 1])
        splits.append(Split(train_dates=train, test_dates=test))
        i_end += step_weeks
    return splits


def cpcv_splits(
    train_dates: Sequence[pd.Timestamp],
    *,
    n_groups: int = 8,
    n_test_groups: int = 2,
    max_combos: int = 16,
    purge_weeks: int = 4,
    embargo_weeks: int = 4,
    seed: int = 42,
) -> list[Split]:
    """Combinatorial purged CV inside a training span: contiguous date groups,
    choose n_test_groups as validation, purge+embargo around each validation
    group, cap combinations at max_combos (seeded choice)."""
    ds = sorted(pd.to_datetime(pd.Series(list(train_dates)).dropna().unique()))
    ds = [pd.Timestamp(d) for d in ds]
    n = len(ds)
    if n < n_groups * 2:
        return []
    bounds = np.linspace(0, n, n_groups + 1, dtype=int)
    groups = [list(range(bounds[g], bounds[g + 1])) for g in range(n_groups)]
    combos = list(itertools.combinations(range(n_groups), n_test_groups))
    if len(combos) > max_combos:
        rng = np.random.default_rng(seed)
        pick = rng.choice(len(combos), size=max_combos, replace=False)
        combos = [combos[i] for i in sorted(pick)]
    out: list[Split] = []
    for combo in combos:
        val_idx = sorted(i for g in combo for i in groups[g])
        val_set = set(val_idx)
        # purge+embargo: drop train dates within purge_weeks before or
        # embargo_weeks after any validation date-index
        excluded = set()
        for i in val_idx:
            for j in range(i - purge_weeks, i + embargo_weeks + 1):
                excluded.add(j)
        train_idx = [i for i in range(n) if i not in val_set and i not in excluded]
        if not train_idx:
            continue
        out.append(Split(
            train_dates=tuple(ds[i] for i in train_idx),
            test_dates=tuple(ds[i] for i in val_idx),
        ))
    return out


# ---------------------------------------------------------------------------
# PBO via CSCV (I.5)
# ---------------------------------------------------------------------------

def probability_of_backtest_overfitting(
    config_by_window: pd.DataFrame,
    *,
    n_partitions: int = 16,
    seed: int = 42,
) -> float:
    """CSCV PBO. Input: rows = evaluation windows (chronological), columns =
    configs, values = the metric (e.g. window IC). Returns P(the config chosen
    in-sample ranks below median out-of-sample)."""
    M = config_by_window.to_numpy(dtype=float)
    n_windows, n_configs = M.shape
    if n_windows < 4 or n_configs < 2:
        return np.nan
    S = min(int(n_partitions), n_windows - (n_windows % 2 or 0)) or 2
    S = S if S % 2 == 0 else S - 1
    S = max(2, min(S, n_windows))
    bounds = np.linspace(0, n_windows, S + 1, dtype=int)
    blocks = [list(range(bounds[i], bounds[i + 1])) for i in range(S)]
    combos = list(itertools.combinations(range(S), S // 2))
    if len(combos) > 128:
        rng = np.random.default_rng(seed)
        pick = rng.choice(len(combos), size=128, replace=False)
        combos = [combos[i] for i in sorted(pick)]
    n_overfit = 0
    n_total = 0
    for combo in combos:
        is_idx = [i for b in combo for i in blocks[b]]
        oos_idx = [i for b in range(S) if b not in combo for i in blocks[b]]
        is_perf = np.nanmean(M[is_idx], axis=0)
        oos_perf = np.nanmean(M[oos_idx], axis=0)
        if np.all(~np.isfinite(is_perf)) or np.all(~np.isfinite(oos_perf)):
            continue
        best = int(np.nanargmax(is_perf))
        # rank of chosen config OOS (0 = worst)
        rank = float((oos_perf < oos_perf[best]).sum()) / max(1, n_configs - 1)
        n_total += 1
        if rank < 0.5:
            n_overfit += 1
    return float(n_overfit / n_total) if n_total else np.nan


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (I.5)
# ---------------------------------------------------------------------------

def deflated_sharpe_ratio(
    returns: np.ndarray,
    *,
    n_trials: int,
    periods_per_year: int = 52,
) -> float:
    """Bailey & Lopez de Prado DSR: probability the observed Sharpe exceeds the
    expected max Sharpe of n_trials random strategies. Returns P in [0,1]."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 20 or n_trials < 1:
        return np.nan
    sr = r.mean() / (r.std(ddof=1) + 1e-12)  # per-period Sharpe
    from scipy.stats import skew, kurtosis, norm
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))
    # expected max SR of n_trials iid trials (Euler-Mascheroni approx)
    e = 0.5772156649
    z1 = norm.ppf(1 - 1.0 / max(2, n_trials))
    z2 = norm.ppf(1 - 1.0 / (max(2, n_trials) * math.e))
    sr0 = math.sqrt(1.0 / max(1, n - 1)) * ((1 - e) * z1 + e * z2)
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4.0 * sr * sr))
    z = (sr - sr0) * math.sqrt(n - 1) / denom
    return float(norm.cdf(z))


# ---------------------------------------------------------------------------
# BH-FDR + dedupe clustering (I.3)
# ---------------------------------------------------------------------------

def benjamini_hochberg(pvals: Sequence[float], *, q: float = 0.10) -> list[bool]:
    """Returns pass/fail per p-value at FDR level q. NaN p-values fail."""
    p = np.asarray([np.nan if v is None else float(v) for v in pvals], dtype=float)
    n = int(np.isfinite(p).sum())
    passed = [False] * len(p)
    if n == 0:
        return passed
    order = np.argsort(np.where(np.isfinite(p), p, np.inf))
    thresh_rank = -1
    for rank, idx in enumerate(order[:n], start=1):
        if p[idx] <= q * rank / n:
            thresh_rank = rank
    for rank, idx in enumerate(order[:n], start=1):
        if rank <= thresh_rank:
            passed[idx] = True
    return passed


def dedupe_clusters(
    signal_frame: pd.DataFrame,
    *,
    threshold: float = 0.90,
    coverage: pd.Series | None = None,
) -> dict[str, str]:
    """Cluster signals at |Spearman rho| > threshold over common dates; return
    {signal -> representative}. Representative = highest coverage (or first)."""
    cols = list(signal_frame.columns)
    if len(cols) <= 1:
        return {c: c for c in cols}
    corr = signal_frame.rank().corr(method="pearson")  # spearman via ranks, faster
    parent = {c: c for c in cols}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.at[a, b]
            if np.isfinite(r) and abs(r) > threshold:
                parent[find(a)] = find(b)
    clusters: dict[str, list[str]] = {}
    for c in cols:
        clusters.setdefault(find(c), []).append(c)
    rep_map: dict[str, str] = {}
    for members in clusters.values():
        if coverage is not None:
            rep = max(members, key=lambda m: float(coverage.get(m, 0.0)))
        else:
            rep = members[0]
        for m in members:
            rep_map[m] = rep
    return rep_map


# ---------------------------------------------------------------------------
# Targets (I.2) — derived at experiment time, never stored
# ---------------------------------------------------------------------------

TARGET_HORIZONS_W = (1, 2, 4, 8, 13)


def derive_forward_targets(
    weekly_close: pd.DataFrame,
    *,
    horizons_w: Sequence[int] = TARGET_HORIZONS_W,
    date_col: str = "date",
    ticker_col: str = "ticker",
    close_col: str = "close",
) -> pd.DataFrame:
    """target_{h}w = forward log return over h weeks from Friday close t to t+h.
    Input: long frame of (date, ticker, close) on the weekly Friday grid.
    Missing future closes stay NaN (suspension/delisting edge weeks are NOT
    zero-filled — anti-pattern D3)."""
    work = weekly_close[[date_col, ticker_col, close_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()
    work = work.dropna(subset=[date_col, ticker_col])
    work = work.sort_values([ticker_col, date_col], kind="mergesort")
    close = pd.to_numeric(work[close_col], errors="coerce")
    close = close.where(close > 0)
    logc = np.log(close)
    g = logc.groupby(work[ticker_col], sort=False)
    for h in horizons_w:
        work[f"target_{h}w"] = (g.shift(-int(h)) - logc).astype(float)
    return work.drop(columns=[close_col])


def derive_target_flavors(
    panel: pd.DataFrame,
    *,
    horizon_w: int = 4,
    date_col: str = "date",
    sector_col: str | None = "sector",
    mktcap_col: str | None = "market_cap",
    winsor_z: float = 3.0,
) -> pd.DataFrame:
    """tgt_mkt / tgt_sec / tgt_z for one horizon. tgt_z winsorized PER DATE at
    ±winsor_z (never full-sample — playbook N6)."""
    tcol = f"target_{horizon_w}w"
    if tcol not in panel.columns:
        raise KeyError(f"missing_{tcol}: run derive_forward_targets first")
    out = panel.copy()
    t = pd.to_numeric(out[tcol], errors="coerce")
    d = pd.to_datetime(out[date_col], errors="coerce")
    # market-excess (cap-weighted if caps available, else equal-weight)
    if mktcap_col and mktcap_col in out.columns:
        w = pd.to_numeric(out[mktcap_col], errors="coerce").clip(lower=0)
        num = (t * w).groupby(d).transform("sum")
        den = w.where(t.notna()).groupby(d).transform("sum")
        mkt_mean = num / den.replace(0.0, np.nan)
    else:
        mkt_mean = t.groupby(d).transform("mean")
    out[f"tgt_mkt_{horizon_w}w"] = (t - mkt_mean).astype(float)
    if sector_col and sector_col in out.columns:
        key = pd.MultiIndex.from_arrays([d, out[sector_col].astype("string").fillna("UNKNOWN")])
        sec_mean = t.groupby(key).transform("mean")
        out[f"tgt_sec_{horizon_w}w"] = (t - sec_mean).astype(float)
    z = group_zscore(t, d, clip_abs=float(winsor_z))
    out[f"tgt_z_{horizon_w}w"] = z
    return out


# ---------------------------------------------------------------------------
# Cost block (I.6) — single source of truth
# ---------------------------------------------------------------------------

def load_cost_model(config: dict[str, Any] | None = None):
    """Return the paper fund's IndianEquityCostModel — the single source of
    truth for brokerage/STT/stamp/GST/slippage/impact. Experiments call its
    methods (e.g. slippage_bps_for(order_value, adv)); never re-type numbers."""
    from src.pnl.indian_cost_model import IndianEquityCostModel
    return IndianEquityCostModel(dict(config or {}))
