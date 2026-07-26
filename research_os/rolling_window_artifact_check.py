#!/usr/bin/env python3
"""Mandatory artifact check for any persistence / memory / autocorrelation claim.

Fixes defect **1e** in `GEN8_RESEARCH_CHARTER.md` §3.1. Implements the **Rolling-Window Persistence
Principle** named in `MSRP_CHARTER.md` as executable infrastructure rather than as a habit — and, in
the course of building it, found and corrected a limitation in the principle's own standard remedy
(see "A correction to the inherited method", below).

--------------------------------------------------------------------------------------------------
Why this exists: the same failure, four times, in two programmes
--------------------------------------------------------------------------------------------------
1. **Gen-6 G6-00 -> G6-00B.** R0's two apparently-positive metrics were construction artifacts;
   first-differencing collapsed predictive-information R^2 from 0.964 to 0.0134 (71x), ACF
   significance 35/35 -> 17/35.
2. **MSRP M-01 -> M-01B.** All six primitives classified "M4 Long Memory", including `beta_104w`,
   whose own window is 104 weeks.
3. **MSRP M-02 -> M-02(corrected).** A fixed effect-size band at regime-level sample sizes made all
   six primitives falsely register regime-locked.
4. **Gen-7 Paper A TD-014.** A broken one-year-window check in Laboratory 2, self-caught.

--------------------------------------------------------------------------------------------------
The mechanism, stated exactly
--------------------------------------------------------------------------------------------------
For i.i.d. `x_t` and a rolling mean `y_t = mean(x_{t-W+1..t})`, adjacent values share `W-1` of `W`
inputs, so

    corr(y_t, y_{t+k}) = 1 - k/W    for 0 <= k < W,    0 otherwise.

This holds when the underlying data has **no memory at all**. A 52-week feature shows ACF ~0.98 at
lag 1 and ~0.5 at lag 26 regardless of what the market does. Reporting that as "long memory" reports
the window length.

--------------------------------------------------------------------------------------------------
A correction to the inherited method (found while building this module, 2026-07-26)
--------------------------------------------------------------------------------------------------
Gen-6 and MSRP both corrected for this artifact by **first-differencing** and re-testing. Direct
simulation shows first-differencing is **not a discriminator** — it removes genuine persistence just
as thoroughly as mechanical persistence:

    AR(1), phi=0.90 (genuinely persistent)  -> differenced ACF(1) = -0.042, band ±0.057, NOT significant
    AR(1), phi=0.99 (extremely persistent)  -> differenced ACF(1) = -0.042, band ±0.057, NOT significant

Differencing an AR(1) gives ACF(1) = -(1-phi)/2, which tends to 0 as persistence *increases*. So
"does not survive differencing" is **not** evidence of an artifact. Differencing is a valid
**one-way conservative screen**: what survives it is real; what fails it is unclassified.

This does not overturn any MSRP or Gen-6 conclusion — their claims were about persistence out to lags
comparable with the window, where the level-ACF comparison does the work — but it does mean the
differencing test cannot carry a verdict on its own, and this module therefore does not let it.

--------------------------------------------------------------------------------------------------
What the check does
--------------------------------------------------------------------------------------------------
  A. **Differencing screen** (the Gen-6/MSRP correction). Reported, never decisive, for the reason
     above.
  B. **Calibrated construction null** — the primary discriminator. Simulate many replicates of
     `rolling_mean(i.i.d. noise, W)` at the *same length n*, take the per-lag upper percentile of
     their ACF, and ask whether the observed ACF exceeds it. This is a real null model rather than
     the closed-form envelope, which is optimistic at long lags in finite samples (at n=1200, W=52:
     closed form gives 0.500 at lag 26, the simulated null gives 0.572).
  C. **Non-overlapping resample** — keep every W-th observation so no two share an input window.
     Persistence surviving here is construction-independent by definition, at the cost of a much
     smaller sample, so **its power is reported alongside it**: a null from test C on a short series
     is UNRESOLVED, not negative. Amendments 002/003 apply to artifact checks too.

--------------------------------------------------------------------------------------------------
Known limitation, stated rather than discovered later
--------------------------------------------------------------------------------------------------
The sample ACF of a **near-unit-root** series is biased downward at finite n. At n=1200 an AR(1)
with phi=0.995 lands on either side of the width-52 construction null depending on the draw
(measured: EXCEEDS on one seed, WITHIN on another). The check is therefore **conservative** in that
region — it can return WITHIN for a series that is genuinely persistent. That is the safe direction
of error for an artifact screen, but it means a WITHIN verdict on a highly persistent candidate
should be reported as UNRESOLVED, which is exactly what charter §6 requires anyway. A true random
walk is detected reliably; the ambiguous band is roughly 0.99 < phi < 1.0 at this sample size.

Verdicts are deliberately phrased as what the evidence discriminates, not as "genuine" vs "fake":

  EXCEEDS_CONSTRUCTION   -- persistence beyond what the window alone mechanically produces
  WITHIN_CONSTRUCTION    -- indistinguishable from the window's own persistence; the claim is not
                            supported by this evidence (which is not the same as "no memory exists")
  NO_PERSISTENCE         -- no significant autocorrelation even on levels


---
RESEARCH OS lineage: forked from scripts/gen8/lib/rolling_window_artifact_check.py (2026-07-26). Per GEN8_RESEARCH_CHARTER.md section 11's own inheritance contract, this becomes the canonical shared copy for all four Northstar Institute labs. scripts/gen8/lib/rolling_window_artifact_check.py is UNCHANGED and remains the historical Gen-8 record -- this is a fork, not a move, per the never-silently-rewrite-history discipline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
from scipy import stats

EXCEEDS = "EXCEEDS_CONSTRUCTION"
WITHIN = "WITHIN_CONSTRUCTION"
NONE = "NO_PERSISTENCE"


class RollingWindowArtifactError(RuntimeError):
    """A persistence/memory claim is not distinguishable from the feature's own window construction."""


def acf(x: np.ndarray, max_lag: int) -> np.ndarray:
    """Sample autocorrelation at lags 1..max_lag (mean-removed, consistent normalisation)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n <= max_lag + 2:
        raise ValueError(f"series too short: n={n} for max_lag={max_lag}")
    xd = x - x.mean()
    denom = float(xd @ xd)
    if denom == 0:
        return np.zeros(max_lag)
    return np.array([float(xd[k:] @ xd[:-k]) / denom for k in range(1, max_lag + 1)])


def acf_significance_band(n: int, alpha: float = 0.05) -> float:
    """Two-sided significance band for a white-noise null: ``z_{1-a/2}/sqrt(n)``."""
    return float(stats.norm.ppf(1 - alpha / 2) / np.sqrt(n))


def construction_envelope(window: int, max_lag: int) -> np.ndarray:
    """Closed-form ACF of a width-W rolling mean on i.i.d. input: ``max(0, 1 - k/W)``.

    Kept for reference and for the module's demonstration; the *calibrated* null below is what the
    verdict uses, because the closed form is optimistic at long lags in finite samples.
    """
    k = np.arange(1, max_lag + 1, dtype=float)
    return np.maximum(0.0, 1.0 - k / float(window))


def calibrated_construction_null(n: int, window: int, max_lag: int, n_sim: int = 400,
                                 pct: float = 95.0, seed: int = 42) -> np.ndarray:
    """Per-lag upper percentile of the ACF of ``rolling_mean(i.i.d. noise, window)`` at length ``n``.

    This is the mechanical persistence the construction produces on data with no memory at all —
    the honest null for "does this feature have memory beyond its own window".
    """
    rng = np.random.default_rng(seed)
    kernel = np.ones(window) / window
    out = np.empty((n_sim, max_lag))
    for i in range(n_sim):
        raw = rng.standard_normal(n + window)
        rolled = np.convolve(raw, kernel, mode="valid")[:n]
        out[i] = acf(rolled, max_lag)
    return np.percentile(out, pct, axis=0)


def non_overlapping_resample(x: np.ndarray, window: int) -> np.ndarray:
    """Keep every ``window``-th observation, so no two retained points share an input window."""
    x = np.asarray(x, dtype=float)
    return x[:: max(int(window), 1)]


@dataclass
class ArtifactReport:
    name: str
    window: int
    n: int
    max_lag: int
    alpha: float
    acf_levels: list[float]
    acf_differenced: list[float]
    construction_null_p95: list[float]
    closed_form_envelope: list[float]
    significance_band_levels: float
    n_sig_levels: int
    n_sig_differenced: int
    differencing_threshold: float
    n_lags_exceeding_null: int
    max_excess_over_null: float
    lag_of_max_excess: int
    acf_nonoverlap_lag1: float
    n_nonoverlap: int
    nonoverlap_band: float
    nonoverlap_power_at_02: float
    survives_differencing: bool
    exceeds_construction: bool
    survives_nonoverlap: bool
    verdict: str
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"ROLLING-WINDOW ARTIFACT CHECK [{self.name}] -- {self.verdict}",
            f"  feature window W             : {self.window} periods",
            f"  series length n              : {self.n:,}   (lags examined: 1..{self.max_lag})",
            f"  A. differencing screen       : {self.n_sig_levels}/{self.max_lag} lags significant on "
            f"levels -> {self.n_sig_differenced}/{self.max_lag} on first differences "
            f"(needs >{self.differencing_threshold:.1f} to beat chance; "
            f"{'survives' if self.survives_differencing else 'does not survive'}) "
            f"[one-way screen only; see module docstring]",
            f"  B. calibrated construction null (PRIMARY): observed ACF exceeds the width-{self.window} "
            f"mechanical null at {self.n_lags_exceeding_null}/{self.max_lag} lags; "
            f"max excess {self.max_excess_over_null:+.3f} at lag {self.lag_of_max_excess}",
            f"  C. non-overlapping resample  : n={self.n_nonoverlap} retained, band ±"
            f"{self.nonoverlap_band:.3f}, lag-1 ACF {self.acf_nonoverlap_lag1:+.3f} "
            f"({'survives' if self.survives_nonoverlap else 'does not survive'}); power to detect "
            f"ACF=0.2 here is {self.nonoverlap_power_at_02:.0%}",
        ]
        lines += [f"  note: {x}" for x in self.notes]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


def rolling_window_artifact_check(series, window: int, name: str = "series",
                                  max_lag: int | None = None, alpha: float = 0.05,
                                  n_sim: int = 400, seed: int = 42,
                                  verbose: bool = True) -> ArtifactReport:
    """Run all three artifact tests on a claimed persistence result.

    Parameters
    ----------
    series : the feature time series whose autocorrelation/persistence is being claimed.
    window : the feature's own construction window in periods (e.g. 52 for `vol_52w`). **Required** —
        it is the single most diagnostic input and defaulting it would defeat test B. For a feature
        that is *not* built from a rolling window, pass the horizon the persistence claim is about;
        the check then asks whether the persistence exceeds that horizon's mechanical equivalent.
    """
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    if max_lag is None:
        max_lag = int(window)
    max_lag = int(min(max_lag, n // 4))
    if max_lag < 1:
        raise ValueError(f"series too short (n={n}) to examine any lag")

    a_lev = acf(x, max_lag)
    dx = np.diff(x)
    a_dif = acf(dx, max_lag)
    env_closed = construction_envelope(window, max_lag)
    null_p95 = calibrated_construction_null(n, window, max_lag, n_sim=n_sim, seed=seed)

    band_lev = acf_significance_band(n, alpha)
    band_dif = acf_significance_band(len(dx), alpha)
    n_sig_lev = int(np.sum(np.abs(a_lev) > band_lev))
    n_sig_dif = int(np.sum(np.abs(a_dif) > band_dif))

    excess = a_lev - null_p95
    n_exceed = int(np.sum(excess > 0))
    i_max = int(np.argmax(excess))

    xs = non_overlapping_resample(x, window)
    n_no = len(xs)
    if n_no > 8:
        a_no = acf(xs, max_lag=max(1, min(4, n_no // 4)))
        band_no = acf_significance_band(n_no, alpha)
        survives_no = bool(abs(a_no[0]) > band_no)
        lam = abs(np.arctanh(0.2)) * np.sqrt(max(n_no - 3, 1))
        z_a = stats.norm.ppf(1 - alpha / 2)
        power_no = float(stats.norm.sf(z_a - lam) + stats.norm.cdf(-z_a - lam))
        a_no_1 = float(a_no[0])
    else:
        a_no_1, band_no, survives_no, power_no = float("nan"), float("nan"), False, 0.0

    # The differencing screen must clear the false positives testing `max_lag` lags at `alpha`
    # generates by chance alone: expected alpha*max_lag, sd sqrt(max_lag*alpha*(1-alpha)). Using
    # "any significant lag" here would fire on ~93% of pure white-noise series at max_lag=52.
    exp_fp = alpha * max_lag
    sd_fp = float(np.sqrt(max_lag * alpha * (1 - alpha)))
    diff_threshold = exp_fp + 2.0 * sd_fp
    survives_diff = bool(n_sig_dif > diff_threshold)
    exceeds = bool(n_exceed > 0)

    if n_sig_lev == 0:
        verdict = NONE
    elif exceeds:
        verdict = EXCEEDS
    else:
        verdict = WITHIN

    notes: list[str] = []
    if verdict == WITHIN:
        notes.append(
            f"the observed ACF never exceeds what a width-{window} rolling mean of i.i.d. noise "
            f"produces at this length. Any 'memory' claim from this series is a claim about the "
            f"window, not the data. This does NOT establish that no memory exists — it establishes "
            f"that this evidence cannot show it (charter §6: UNRESOLVED, not NEGATIVE EVIDENCE).")
    if verdict == EXCEEDS:
        notes.append(
            f"persistence beyond construction confirmed at {n_exceed} lag(s), strongest at lag "
            f"{i_max + 1} (+{excess[i_max]:.3f} over the mechanical null). Report the excess, not "
            f"the raw ACF, as the effect size.")
    if not survives_diff and verdict == EXCEEDS:
        notes.append(
            "failed the differencing screen while exceeding the construction null — expected for a "
            "highly persistent level series, since differencing an AR(1) gives ACF(1)=-(1-phi)/2, "
            "which vanishes as persistence rises. Not a contradiction; see module docstring.")
    if n_no <= 30:
        notes.append(f"test C retained only {n_no} observations; a null from it is UNRESOLVED, not "
                     f"negative (power to detect ACF=0.2 is {power_no:.0%}).")
    if max_lag < window:
        notes.append(f"max_lag={max_lag} was capped below W={window} by series length (n={n}); the "
                     f"lags where the construction null is weakest were not examined.")

    rep = ArtifactReport(
        name=name, window=int(window), n=int(n), max_lag=int(max_lag), alpha=float(alpha),
        acf_levels=[float(v) for v in a_lev], acf_differenced=[float(v) for v in a_dif],
        construction_null_p95=[float(v) for v in null_p95],
        closed_form_envelope=[float(v) for v in env_closed],
        significance_band_levels=float(band_lev),
        n_sig_levels=n_sig_lev, n_sig_differenced=n_sig_dif,
        differencing_threshold=float(diff_threshold),
        n_lags_exceeding_null=n_exceed, max_excess_over_null=float(excess[i_max]),
        lag_of_max_excess=int(i_max + 1),
        acf_nonoverlap_lag1=a_no_1, n_nonoverlap=int(n_no), nonoverlap_band=float(band_no),
        nonoverlap_power_at_02=float(power_no),
        survives_differencing=survives_diff, exceeds_construction=exceeds,
        survives_nonoverlap=survives_no, verdict=verdict, notes=notes)
    if verbose:
        print(rep.summary())
    return rep


def assert_not_artifact(series, window: int, name: str = "series", **kw) -> ArtifactReport:
    """**Hard gate.** Raise unless the persistence claim exceeds its own construction null.

    Per charter Standing Rule 4, any autocorrelation/persistence/memory claim involving a windowed
    feature must pass this before it may be reported. A failure is a finding to report, not an error
    to suppress — catch it, record the verdict, classify the claim UNRESOLVED, and move on.
    """
    rep = rolling_window_artifact_check(series, window, name, **kw)
    if rep.verdict != EXCEEDS:
        raise RollingWindowArtifactError(
            rep.summary()
            + f"\n\n  A width-{window} rolling mean shows ACF ~ 1-k/W on i.i.d. input. The observed "
              f"ACF does not exceed the calibrated version of that null, so the persistence claim is "
              f"not supported by this evidence. Same failure mode as Gen-6 R0/R0B, MSRP M-01/M-01B "
              f"and MSRP M-02. Classify UNRESOLVED and report the construction null alongside the "
              f"observed ACF — do not report the raw ACF as a memory finding."
        )
    return rep


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    n = 1200
    print("=" * 96)
    print("CASE 1 -- rolling 52-period mean of PURE WHITE NOISE (no memory whatsoever)")
    print("         expected: WITHIN_CONSTRUCTION")
    print("=" * 96)
    raw = rng.standard_normal(n + 52)
    rolling_window_artifact_check(np.convolve(raw, np.ones(52) / 52, "valid")[:n],
                                  window=52, name="rolling_mean_of_noise")

    print("\n" + "=" * 96)
    print("CASE 2 -- rolling 52-period mean of a GENUINELY PERSISTENT underlying (AR(1) phi=0.98)")
    print("         expected: EXCEEDS_CONSTRUCTION")
    print("=" * 96)
    u = np.zeros(n + 52)
    for t in range(1, n + 52):
        u[t] = 0.98 * u[t - 1] + rng.standard_normal()
    rolling_window_artifact_check(np.convolve(u, np.ones(52) / 52, "valid")[:n],
                                  window=52, name="rolling_mean_of_persistent")

    print("\n" + "=" * 96)
    print("CASE 3 -- moderately persistent AR(1) phi=0.90, persistence claim made at horizon 52")
    print("         expected: WITHIN_CONSTRUCTION -- phi=0.90 dies out well inside 52 periods, so a")
    print("         'long memory to 52' claim about it is NOT supported, and that is the right answer")
    print("=" * 96)
    ar = np.zeros(n)
    for t in range(1, n):
        ar[t] = 0.90 * ar[t - 1] + rng.standard_normal()
    rolling_window_artifact_check(ar, window=52, name="ar1_phi0.90")

    print("\n" + "=" * 96)
    print("CASE 4 -- the differencing screen's blind spot, demonstrated: AR(1) phi=0.99 is extremely")
    print("         persistent, yet its differenced ACF(1) is -(1-phi)/2 ~ -0.005, insignificant.")
    print("         Verdict must still be EXCEEDS_CONSTRUCTION, from test B, not test A.")
    print("=" * 96)
    ar99 = np.zeros(n)
    for t in range(1, n):
        ar99[t] = 0.99 * ar99[t - 1] + rng.standard_normal()
    rolling_window_artifact_check(ar99, window=52, name="ar1_phi0.99")
