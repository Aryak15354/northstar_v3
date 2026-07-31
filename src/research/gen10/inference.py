#!/usr/bin/env python3
"""Gen-10 shared inference layer.

Exists because of G10-F01: several AEP-era results computed t-statistics by pooling
stock-weeks as though they were independent observations. They are not — h-week forward
returns overlap, and stocks within a week share a market factor. The repo already knew
this (G8-10 s4.2 demands date-clustered SEs; G9-02 s1 documents catching the same error
in its own v1) but the discipline was applied per-script rather than centrally.

Every Gen-10 experiment routes its inference through this module so the correction is
structural rather than remembered.

Design rules
------------
1. Cross-sectional dependence is handled by COLLAPSING TO A PER-DATE SERIES first.
   Never test on pooled stock-weeks. One date = one observation.
2. Serial dependence (from overlapping h-period forward returns, and from genuine
   autocorrelation) is handled by Newey-West with a Bartlett kernel. For an h-period
   overlapping return the MA order is h-1, so the lag floor is h-1.
3. Every headline number carries a second opinion from a stationary block bootstrap,
   which makes no parametric assumption. If NW and bootstrap disagree materially, the
   result is reported as fragile rather than picking the friendlier one.
4. Sharpe differences between two return streams on the SAME dates use the paired
   Jobson-Korkie/Memmel statistic, never two independent Sharpe SEs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict, field
from typing import Sequence

ANN_WEEKLY = np.sqrt(52.0)


# --------------------------------------------------------------------------------------
# results container
# --------------------------------------------------------------------------------------
@dataclass
class TestResult:
    """One hypothesis test. `n` is ALWAYS the effective (per-date) sample, never stock-weeks."""
    estimate: float
    se: float
    t: float
    p: float
    n: int
    nw_lags: int
    boot_ci_lo: float | None = None
    boot_ci_hi: float | None = None
    boot_p: float | None = None
    n_pooled: int | None = None          # for transparency vs the old, wrong statistic
    t_naive_pooled: float | None = None  # the number the defective design would have given
    label: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def fragile(self) -> bool:
        """NW and bootstrap disagree about crossing |t|>=2 / CI-excludes-zero."""
        if self.boot_ci_lo is None:
            return False
        nw_sig = abs(self.t) >= 2.0
        bs_sig = (self.boot_ci_lo > 0) or (self.boot_ci_hi < 0)
        return nw_sig != bs_sig

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fragile"] = self.fragile
        return d

    def __str__(self) -> str:
        s = (f"{self.label:<28s} est={self.estimate:+.6f} se={self.se:.6f} "
             f"t={self.t:+.2f} p={self.p:.4f} n={self.n}")
        if self.boot_ci_lo is not None:
            s += f" boot95=[{self.boot_ci_lo:+.6f},{self.boot_ci_hi:+.6f}]"
        if self.t_naive_pooled is not None:
            s += f"  (naive-pooled t={self.t_naive_pooled:+.2f}, n={self.n_pooled})"
        if self.fragile:
            s += "  [FRAGILE: NW/bootstrap disagree]"
        return s


# --------------------------------------------------------------------------------------
# core estimators
# --------------------------------------------------------------------------------------
def newey_west_lags(n: int, overlap: int = 1) -> int:
    """Bartlett bandwidth. Floor of `overlap - 1` covers MA structure induced by using
    overlapping k-period returns; the 4*(n/100)^(2/9) term is the standard automatic rule."""
    auto = int(np.floor(4.0 * (max(n, 2) / 100.0) ** (2.0 / 9.0)))
    return int(max(overlap - 1, auto, 1))


def nw_mean_test(x: Sequence[float], overlap: int = 1, lags: int | None = None,
                 label: str = "", n_boot: int = 5000, seed: int = 20260731) -> TestResult:
    """Test H0: mean(x) == 0 with a Newey-West HAC standard error, plus a stationary
    block-bootstrap CI as an independent second opinion.

    `x` MUST already be a per-date series (one observation per decision date).
    """
    from scipy import stats

    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    n = a.size
    if n < 10:
        return TestResult(np.nan, np.nan, np.nan, np.nan, n, 0, label=label,
                          notes=["n<10, not tested"])

    m = float(a.mean())
    e = a - m
    L = int(lags) if lags is not None else newey_west_lags(n, overlap)
    L = min(L, n - 2)
    s = float(e @ e) / n
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)           # Bartlett
        s += 2.0 * w * float(e[l:] @ e[:-l]) / n
    s = max(s, 1e-30)
    se = float(np.sqrt(s / n))
    t = m / se
    p = float(2.0 * stats.t.sf(abs(t), df=max(n - 1, 1)))

    lo, hi, bp = stationary_bootstrap_mean_ci(a, overlap=overlap, n_boot=n_boot, seed=seed)
    return TestResult(estimate=m, se=se, t=float(t), p=p, n=n, nw_lags=L,
                      boot_ci_lo=lo, boot_ci_hi=hi, boot_p=bp, label=label)


def stationary_bootstrap_mean_ci(x: Sequence[float], overlap: int = 1, n_boot: int = 5000,
                                 alpha: float = 0.05, seed: int = 20260731
                                 ) -> tuple[float, float, float]:
    """Politis-Romano stationary bootstrap CI for the mean. Expected block length is tied
    to the dependence horizon so overlap-induced autocorrelation is resampled intact."""
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    n = a.size
    if n < 10:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    exp_block = max(float(overlap), n ** (1.0 / 3.0))
    p_restart = 1.0 / exp_block

    idx = rng.integers(0, n, size=(n_boot, n))
    cont = rng.random((n_boot, n)) > p_restart
    # walk forward: where cont, index = prev+1 (mod n); else fresh draw
    for j in range(1, n):
        idx[:, j] = np.where(cont[:, j], (idx[:, j - 1] + 1) % n, idx[:, j])
    means = a[idx].mean(axis=1)

    lo = float(np.quantile(means, alpha / 2.0))
    hi = float(np.quantile(means, 1.0 - alpha / 2.0))
    centered = means - means.mean()
    bp = float((np.abs(centered) >= abs(a.mean())).mean())
    return lo, hi, bp


# --------------------------------------------------------------------------------------
# the specific shape that broke AEP Paper B
# --------------------------------------------------------------------------------------
def date_clustered_group_diff(df: pd.DataFrame, date_col: str, value_col: str,
                              hi_mask: pd.Series, lo_mask: pd.Series, overlap: int = 1,
                              label: str = "", min_per_side: int = 5,
                              seed: int = 20260731) -> TestResult:
    """Mean(value | hi) - Mean(value | lo), tested correctly.

    Collapses to one difference per date FIRST (killing cross-sectional dependence), then
    applies NW over dates (killing overlap-induced serial dependence). Also reports the
    naive pooled two-sample t the defective design produced, so the two are comparable
    side by side in the output rather than in a reader's memory.
    """
    d = df[[date_col, value_col]].copy()
    d["_hi"] = hi_mask.reindex(df.index).fillna(False).to_numpy()
    d["_lo"] = lo_mask.reindex(df.index).fillna(False).to_numpy()
    d = d[d[value_col].notna()]

    hi = d[d["_hi"]]
    lo = d[d["_lo"]]

    # --- the wrong statistic, computed for transparency only ---
    a, b = hi[value_col].to_numpy(), lo[value_col].to_numpy()
    t_naive = np.nan
    if a.size > 1 and b.size > 1:
        se_naive = np.sqrt(a.var(ddof=1) / a.size + b.var(ddof=1) / b.size)
        if se_naive > 0:
            t_naive = float((a.mean() - b.mean()) / se_naive)

    # --- the right statistic ---
    g_hi = hi.groupby(date_col)[value_col].agg(["mean", "size"])
    g_lo = lo.groupby(date_col)[value_col].agg(["mean", "size"])
    j = g_hi.join(g_lo, how="inner", lsuffix="_hi", rsuffix="_lo")
    j = j[(j["size_hi"] >= min_per_side) & (j["size_lo"] >= min_per_side)]
    diff = (j["mean_hi"] - j["mean_lo"]).sort_index()

    res = nw_mean_test(diff.to_numpy(), overlap=overlap, label=label, seed=seed)
    res.n_pooled = int(a.size + b.size)
    res.t_naive_pooled = t_naive
    return res


def per_date_ic(df: pd.DataFrame, date_col: str, signal_col: str, target_col: str,
                method: str = "spearman", min_pairs: int = 30) -> pd.Series:
    """Cross-sectional IC per date. The unit of inference for anything signal-shaped."""
    def _ic(g):
        s = g[[signal_col, target_col]].dropna()
        if len(s) < min_pairs:
            return np.nan
        if s[signal_col].nunique() < 3 or s[target_col].nunique() < 3:
            return np.nan
        return s[signal_col].corr(s[target_col], method=method)
    g = df.groupby(date_col, sort=True)
    try:                                     # pandas >= 2.2 keeps grouping cols unless told
        return g.apply(_ic, include_groups=False).dropna()
    except TypeError:
        return g.apply(_ic).dropna()


def ic_test(df: pd.DataFrame, date_col: str, signal_col: str, target_col: str,
            overlap: int = 1, method: str = "spearman", min_pairs: int = 30,
            label: str = "", seed: int = 20260731) -> tuple[TestResult, pd.Series]:
    ic = per_date_ic(df, date_col, signal_col, target_col, method=method, min_pairs=min_pairs)
    return nw_mean_test(ic.to_numpy(), overlap=overlap, label=label or signal_col, seed=seed), ic


# --------------------------------------------------------------------------------------
# Sharpe comparisons
# --------------------------------------------------------------------------------------
def sharpe(returns: Sequence[float], ann: float = ANN_WEEKLY) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    sd = r.std(ddof=1)
    return float(r.mean() / sd * ann) if sd > 0 else np.nan


def sharpe_se(returns: Sequence[float], ann: float = ANN_WEEKLY) -> float:
    """Lo (2002) SE for an annualised Sharpe under i.i.d. returns. This is an OPTIMISTIC
    bound: real return series are autocorrelated and fat-tailed, both of which widen it."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < 10:
        return np.nan
    s = sharpe(r, ann=1.0)
    return float(np.sqrt((1.0 + 0.5 * s * s) / n) * ann)


def paired_sharpe_diff(ra: Sequence[float], rb: Sequence[float], ann: float = ANN_WEEKLY,
                       label: str = "", n_boot: int = 5000, seed: int = 20260731) -> TestResult:
    """Jobson-Korkie with Memmel's correction: SR(b) - SR(a) for two return streams
    observed on the SAME dates. Using two independent Sharpe SEs here badly overstates
    the standard error when the streams are correlated (which sleeves and overlays always
    are) and is the reason G8-09 switched to a paired design."""
    from scipy import stats

    a = np.asarray(ra, dtype=float)
    b = np.asarray(rb, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = a.size
    if n < 20:
        return TestResult(np.nan, np.nan, np.nan, np.nan, n, 0, label=label,
                          notes=["n<20, not tested"])

    sa, sb = sharpe(a, ann=1.0), sharpe(b, ann=1.0)
    rho = float(np.corrcoef(a, b)[0, 1])
    var = (2.0 - 2.0 * rho + 0.5 * (sa ** 2 + sb ** 2)
           - rho * sa * sb * (1.0 + rho)) / n
    diff = sb - sa
    # The Jobson-Korkie/Memmel expansion is only valid away from rho=1. As rho -> 1 the
    # analytic variance goes to zero and can turn negative, producing an absurd t. When
    # that happens (nested/overlapping streams, e.g. a book vs a blend containing it),
    # fall back to the bootstrap SE, which stays well defined.
    analytic_ok = var > 0
    se = float(np.sqrt(var)) if analytic_ok else np.nan

    # bootstrap the paired difference for a distribution-free second opinion
    rng = np.random.default_rng(seed)
    exp_block = max(1.0, n ** (1.0 / 3.0))
    p_restart = 1.0 / exp_block
    idx = rng.integers(0, n, size=(n_boot, n))
    cont = rng.random((n_boot, n)) > p_restart
    for j in range(1, n):
        idx[:, j] = np.where(cont[:, j], (idx[:, j - 1] + 1) % n, idx[:, j])
    A, B = a[idx], b[idx]
    with np.errstate(invalid="ignore", divide="ignore"):
        sA = A.mean(axis=1) / A.std(axis=1, ddof=1)
        sB = B.mean(axis=1) / B.std(axis=1, ddof=1)
    d_boot = (sB - sA) * ann
    lo = float(np.nanquantile(d_boot, 0.025))
    hi = float(np.nanquantile(d_boot, 0.975))

    notes = [f"corr(a,b)={rho:.3f}; SR_a={sa*ann:.4f} SR_b={sb*ann:.4f}"]
    if not analytic_ok:
        se = float(np.nanstd(d_boot, ddof=1)) / ann          # store in per-period units
        notes.append(f"analytic JK variance non-positive at rho={rho:.4f}; "
                     "bootstrap SE substituted")
    t = (diff * ann) / (se * ann) if se and np.isfinite(se) and se > 0 else np.nan
    p = float(2.0 * stats.norm.sf(abs(t))) if np.isfinite(t) else np.nan

    res = TestResult(estimate=float(diff * ann), se=float(se * ann), t=float(t), p=p,
                     n=n, nw_lags=0, boot_ci_lo=lo, boot_ci_hi=hi, label=label)
    res.notes.extend(notes)
    return res


def min_detectable_sharpe_diff(returns: Sequence[float], paired_corr: float | None = None,
                               power: float = 0.80, alpha: float = 0.05,
                               ann: float = ANN_WEEKLY) -> float:
    """Smallest Sharpe difference detectable at the given power. Run this BEFORE a test,
    not after: it is what turns 'we found nothing' into 'this design could not have found
    anything'. G7-F02/G8-09's central lesson."""
    from scipy import stats
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = r.size
    if n < 20:
        return np.nan
    s = sharpe(r, ann=1.0)
    if paired_corr is None:
        var = 2.0 * (1.0 + 0.5 * s * s) / n            # unpaired, two independent Sharpes
    else:
        rho = float(paired_corr)
        var = (2.0 - 2.0 * rho + 0.5 * (s ** 2 + s ** 2) - rho * s * s * (1.0 + rho)) / n
    se = np.sqrt(max(var, 1e-30))
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * se * ann)


# --------------------------------------------------------------------------------------
# multiplicity
# --------------------------------------------------------------------------------------
def benjamini_hochberg(pvals: Sequence[float], q: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    n = p.size
    order = np.argsort(p)
    thresh = (np.arange(1, n + 1) / n) * q
    passed = p[order] <= thresh
    out = np.zeros(n, dtype=bool)
    if passed.any():
        kmax = np.max(np.where(passed)[0])
        out[order[: kmax + 1]] = True
    return out


def benjamini_yekutieli(pvals: Sequence[float], q: float = 0.05) -> np.ndarray:
    """BH under arbitrary dependence. Correct choice when tested signals are correlated —
    which duplicated / same-family signals always are."""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    c = np.sum(1.0 / np.arange(1, n + 1))
    return benjamini_hochberg(p, q=q / c)


def bonferroni(pvals: Sequence[float], alpha: float = 0.05) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    return p <= (alpha / max(p.size, 1))


# --------------------------------------------------------------------------------------
def _selftest() -> None:
    """Sanity: on i.i.d. noise the corrected test must be calibrated, and on an overlapping
    series the naive pooled t must be visibly inflated relative to it."""
    rng = np.random.default_rng(7)
    # 1. calibration of nw_mean_test under the null
    rejects = 0
    for i in range(300):
        x = rng.normal(size=400)
        r = nw_mean_test(x, overlap=1, n_boot=200, seed=i)
        rejects += abs(r.t) >= 1.96
    rate = rejects / 300
    assert 0.02 < rate < 0.10, f"null rejection rate {rate:.3f} not near 0.05"

    # 2. overlapping data: naive iid SE understates, NW corrects toward truth
    z = rng.normal(size=2000)
    ov = pd.Series(z).rolling(8).sum().dropna().to_numpy()
    naive_t = ov.mean() / (ov.std(ddof=1) / np.sqrt(ov.size))
    nw_t = nw_mean_test(ov, overlap=8, n_boot=200).t
    assert abs(nw_t) < abs(naive_t) * 1.05, "NW should not exceed the naive t on overlapping data"

    # 3. paired sharpe: identical streams -> zero difference
    a = rng.normal(0.002, 0.02, size=500)
    r = paired_sharpe_diff(a, a, n_boot=200)
    assert abs(r.estimate) < 1e-9

    # 4. BY is stricter than BH
    p = rng.random(20) * 0.05
    assert benjamini_yekutieli(p, 0.05).sum() <= benjamini_hochberg(p, 0.05).sum()

    print(f"inference selftest OK (null rejection rate {rate:.3f}, "
          f"naive_t={naive_t:+.2f} vs nw_t={nw_t:+.2f})")


if __name__ == "__main__":
    _selftest()
