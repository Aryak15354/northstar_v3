#!/usr/bin/env python3
"""Valid permutation p-values and resolution-gated multiplicity correction.

Fixes defect **1a** (and supports **1d**) in `GEN8_RESEARCH_CHARTER.md` §3.1, traced to CRITICAL-1 in
`results/gen7/GEN6_GEN7_INDEPENDENT_AUDIT_2026_07_25.md`.

--------------------------------------------------------------------------------------------------
The bug, precisely
--------------------------------------------------------------------------------------------------
`scripts/gen7/lab2_pairwise_discovery.py` computed the permutation p-value as

    p = 1 - mean(|null| < |observed|)          # == k/N

which returns **exactly 0.0** whenever the observed statistic beats every draw. Zero is not a valid
p-value: the permutation distribution includes the observed value itself, so the smallest honest
statement a permutation test can make is "at most 1 in N+1".

Two consequences, and the second is the one that actually destroyed Paper A's headline claim:

1. The six tests reporting p=0.0 were *precisely* the six "BH-FDR survivors."
2. With N=500 draws the finest resolvable p-value is 1/501 = 1.996e-3, while BH at rank 1 with m=310
   and q=0.05 requires p <= 1.61e-4. **The design could not have produced a legitimate survivor at any
   observation whatsoever** — the correction was uninterpretable before a single number was computed.

Fixing (1) alone would have been worse than useless: it turns a false positive into a confident false
negative. The resolution gate below is the part that matters.

--------------------------------------------------------------------------------------------------
The fix
--------------------------------------------------------------------------------------------------
* `permutation_pvalue(k, n_perm)` -> `(1 + k) / (n_perm + 1)`, floored at `1/(n_perm+1)`, never 0.
* `required_n_perm(m, q, ...)` derives the draw count the *specific* family needs — this is why
  10,000 is not hardcoded anywhere in this module. For m tests under BH at rank 1 the strictest
  threshold is `q/m`, so bare resolvability needs `N >= m/q - 1` (~20m at q=0.05) and the
  order-of-magnitude margin this library requires by default needs `N >= 10m/q - 1` (~200m at q=0.05).
* `assert_permutation_resolution(...)` **raises** `InsufficientResolutionError`. It is a hard gate,
  not a warning and not a comment — Gen-7's failure was precisely that nothing stopped an
  unresolvable correction from being run and reported.

`bh_step_up` / `by_step_up` are carried over from `scripts/gen7/reanalysis/ra001_corrected_discovery.py`,
which RA-005 verified 22/22 against SciPy's own FDR implementation (to 1e-12 across 200 random families)
and against the Benjamini-Hochberg (1995) published worked example. They are re-homed here rather than
re-derived, so the verified implementation is the one every Gen-8 experiment actually calls.


---
RESEARCH OS lineage: forked from scripts/gen8/lib/valid_pvalue.py (2026-07-26). Per GEN8_RESEARCH_CHARTER.md section 11's own inheritance contract, this becomes the canonical shared copy for all four Northstar Institute labs. scripts/gen8/lib/valid_pvalue.py is UNCHANGED and remains the historical Gen-8 record -- this is a fork, not a move, per the never-silently-rewrite-history discipline."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


class InsufficientResolutionError(RuntimeError):
    """A permutation design cannot resolve the multiplicity threshold it will be corrected against."""


class InvalidPValueError(ValueError):
    """A p-value of exactly 0 (or outside (0, 1]) was produced or supplied."""


# ---------------------------------------------------------------------------------------------
# Core p-value
# ---------------------------------------------------------------------------------------------
def permutation_pvalue(n_ge: int, n_perm: int) -> float:
    """The statistically valid permutation p-value: ``(1 + k) / (N + 1)``.

    Parameters
    ----------
    n_ge : number of null draws with |statistic| >= |observed statistic|.
    n_perm : number of null draws.

    The observed value is counted as one realization under the null, which is what makes the
    estimator valid (and gives it a hard floor of ``1/(N+1)``). The invalid form ``k/N`` returns 0
    when ``k == 0``.
    """
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1, got {n_perm}")
    if not (0 <= n_ge <= n_perm):
        raise ValueError(f"n_ge must lie in [0, n_perm], got n_ge={n_ge}, n_perm={n_perm}")
    return (1.0 + float(n_ge)) / (float(n_perm) + 1.0)


def invalid_permutation_pvalue_DO_NOT_USE(n_ge: int, n_perm: int) -> float:
    """The **defective** estimator ``k/N``, retained solely so tests can demonstrate the failure.

    Never call this in an experiment. It exists because `GEN8_RESEARCH_CHARTER.md` §10 requires every
    remediation module to carry a unit test in which the old code gives a demonstrably wrong answer,
    and that test needs the old code to be runnable.
    """
    return float(n_ge) / float(n_perm)


def finest_resolvable_pvalue(n_perm: int) -> float:
    """Smallest p-value a permutation test with ``n_perm`` draws can ever report: ``1/(N+1)``."""
    return 1.0 / (float(n_perm) + 1.0)


def validate_pvalues(pvals) -> np.ndarray:
    """Reject a p-value vector containing exactly 0 (or values outside (0, 1]).

    Amendment-002 corollary 2: *"A p-value of exactly 0 is never valid output."* This guards the
    boundary where a p-value enters a correction from anywhere — including from a legacy artifact.
    """
    p = np.asarray(pvals, dtype=float)
    if p.size == 0:
        raise InvalidPValueError("empty p-value vector")
    if not np.all(np.isfinite(p)):
        raise InvalidPValueError("p-value vector contains non-finite entries")
    bad_zero = int(np.sum(p <= 0.0))
    if bad_zero:
        raise InvalidPValueError(
            f"{bad_zero} p-value(s) are <= 0. A p-value of exactly 0 is never valid output "
            f"(Amendment-002 corollary 2). If these came from a permutation test, recompute with "
            f"permutation_pvalue((1+k)/(N+1))."
        )
    if int(np.sum(p > 1.0)):
        raise InvalidPValueError("p-value vector contains entries > 1")
    return p


# ---------------------------------------------------------------------------------------------
# Resolution gate  (the part that actually mattered in CRITICAL-1)
# ---------------------------------------------------------------------------------------------
def strictest_threshold(m: int, q: float = 0.05, method: str = "BH") -> float:
    """The smallest p-value that could ever be rejected by the correction, i.e. its rank-1 threshold.

    BH rank 1: ``q/m``.  BY rank 1: ``q / (m * H(m))`` where ``H(m)`` is the m-th harmonic number.
    """
    if m < 1:
        raise ValueError(f"m must be >= 1, got {m}")
    method = method.upper()
    if method == "BH":
        return q / m
    if method == "BY":
        return q / (m * float(np.sum(1.0 / np.arange(1, m + 1))))
    if method in ("BONFERRONI", "BONF"):
        return q / m
    raise ValueError(f"unknown method {method!r}; use 'BH', 'BY' or 'Bonferroni'")


def required_n_perm(m: int, q: float = 0.05, method: str = "BH", margin: float = 10.0) -> int:
    """Draws needed so the finest resolvable p-value clears the family's strictest threshold.

    ``margin=1`` gives bare resolvability (``1/(N+1) <= q/m``, i.e. ``N >= m/q - 1``, ~20m at q=0.05).
    ``margin=10`` (the default, and what this library enforces) puts the floor a full order of
    magnitude below the threshold, so a survivor is resolved rather than merely touching the bound.

    Note this is a function of the *actual* m and q of the experiment. Hardcoding 10,000 is only
    correct for m up to 50 at q=0.05 with margin 10 — it is far too few for a 310-test family and
    wastefully many for a 6-test one.
    """
    thr = strictest_threshold(m, q, method)
    return int(np.ceil(margin / thr - 1.0))


@dataclass
class ResolutionReport:
    m: int
    q: float
    method: str
    n_perm: int
    strictest_threshold: float
    finest_resolvable_p: float
    margin_achieved: float
    required_n_perm_bare: int
    required_n_perm_with_margin: int
    sufficient: bool

    def summary(self) -> str:
        verdict = "SUFFICIENT" if self.sufficient else "INSUFFICIENT"
        return (
            f"[{verdict}] permutation resolution: N={self.n_perm:,} draws give a finest resolvable "
            f"p-value of {self.finest_resolvable_p:.3e}; {self.method} at rank 1 with m={self.m} and "
            f"q={self.q} requires p <= {self.strictest_threshold:.3e} "
            f"(margin achieved {self.margin_achieved:.2f}x). "
            f"Bare resolvability needs N >= {self.required_n_perm_bare:,}; "
            f"an order-of-magnitude margin needs N >= {self.required_n_perm_with_margin:,}."
        )


def check_permutation_resolution(n_perm: int, m: int, q: float = 0.05, method: str = "BH",
                                 margin: float = 10.0) -> ResolutionReport:
    """Non-raising form: report whether ``n_perm`` can resolve the correction that will be applied."""
    thr = strictest_threshold(m, q, method)
    finest = finest_resolvable_pvalue(n_perm)
    return ResolutionReport(
        m=int(m), q=float(q), method=method.upper(), n_perm=int(n_perm),
        strictest_threshold=float(thr), finest_resolvable_p=float(finest),
        margin_achieved=float(thr / finest) if finest > 0 else float("inf"),
        required_n_perm_bare=required_n_perm(m, q, method, margin=1.0),
        required_n_perm_with_margin=required_n_perm(m, q, method, margin=margin),
        sufficient=bool(finest * margin <= thr),
    )


def assert_permutation_resolution(n_perm: int, m: int, q: float = 0.05, method: str = "BH",
                                  margin: float = 10.0, verbose: bool = True) -> ResolutionReport:
    """**Hard gate.** Raise `InsufficientResolutionError` unless ``n_perm`` can resolve the threshold.

    Call this *before* running the permutations, not after — the point is to stop an uninterpretable
    design from consuming compute and then being reported as if it had adjudicated something.
    """
    rep = check_permutation_resolution(n_perm, m, q, method, margin)
    if verbose:
        print(rep.summary())
    if not rep.sufficient:
        raise InsufficientResolutionError(
            rep.summary()
            + f"\n  This is the exact failure mode of Gen-7 Lab 2 (audit CRITICAL-1): N=500 draws "
              f"against m=310, q=0.05 -> floor 1.996e-03 vs threshold 1.613e-04. The correction "
              f"could not produce a legitimate survivor at any observation. "
              f"\n  Remedies: raise n_perm to >= {rep.required_n_perm_with_margin:,}; reduce m by "
              f"pre-registering one test per hypothesis (defect 1d); or use a test with continuous "
              f"p-values (e.g. the Newey-West HAC test in scripts/gen7/reanalysis/"
              f"ra001_corrected_discovery.py) instead of a permutation screen."
        )
    return rep


# ---------------------------------------------------------------------------------------------
# Multiplicity correction
# (carried over verbatim from RA-001, verified 22/22 by RA-005 against SciPy and BH-1995)
# ---------------------------------------------------------------------------------------------
def bh_step_up(pvals, q: float = 0.05):
    """Benjamini-Hochberg step-up. Returns ``(reject_bool_vector, qvalue_vector)``."""
    p = validate_pvalues(pvals)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    below = ranked <= q * np.arange(1, m + 1) / m
    reject = np.zeros(m, dtype=bool)
    if below.any():
        kmax = np.where(below)[0].max()
        reject[order[: kmax + 1]] = True
    adj = np.minimum.accumulate((ranked * m / np.arange(1, m + 1))[::-1])[::-1]
    qvals = np.empty(m)
    qvals[order] = np.clip(adj, 0, 1)
    return reject, qvals


def by_step_up(pvals, q: float = 0.05):
    """Benjamini-Yekutieli — valid under **arbitrary** dependence. Returns ``(reject, c_m)``.

    Amendment-002 corollary 3: where the family is dependent (a shared response series, overlapping
    predictors), BY must be reported alongside BH. Every Gen-8 family that screens one response
    against many predictors is dependent by construction, so this is the default, not the exception.
    """
    p = validate_pvalues(pvals)
    m = len(p)
    c_m = float(np.sum(1.0 / np.arange(1, m + 1)))
    return bh_step_up(p, q / c_m)[0], c_m


def correct_and_report(pvals, q: float = 0.05, labels=None) -> dict:
    """Apply BH and BY together and return one machine-readable record. The standard Gen-8 call."""
    p = validate_pvalues(pvals)
    rej_bh, qv = bh_step_up(p, q)
    rej_by, c_m = by_step_up(p, q)
    out = dict(
        m=int(len(p)), q=float(q),
        n_reject_bh=int(rej_bh.sum()), n_reject_by=int(rej_by.sum()),
        by_constant=float(c_m),
        best_q_bh=float(np.min(qv)),
        strictest_threshold_bh=float(strictest_threshold(len(p), q, "BH")),
        strictest_threshold_by=float(strictest_threshold(len(p), q, "BY")),
        min_pvalue=float(np.min(p)),
    )
    if labels is not None:
        lab = list(labels)
        out["survivors_bh"] = [lab[i] for i in np.where(rej_bh)[0]]
        out["survivors_by"] = [lab[i] for i in np.where(rej_by)[0]]
    return out


if __name__ == "__main__":  # a runnable demonstration of the Gen-7 failure and its fix
    print("Gen-7 Lab 2 as it was run:  m=310, q=0.05, N=500 draws")
    rep = check_permutation_resolution(n_perm=500, m=310, q=0.05)
    print(" ", rep.summary())
    print("\nSame family, resolvable design:")
    print(" ", check_permutation_resolution(n_perm=required_n_perm(310, 0.05), m=310, q=0.05).summary())
    print("\nAfter multiplicity reduction to one lag per carrier (m=31):")
    print(" ", check_permutation_resolution(n_perm=required_n_perm(31, 0.05), m=31, q=0.05).summary())
    print("\nInvalid vs valid p-value when the observed statistic beats all 500 draws:")
    print(f"  k/N        = {invalid_permutation_pvalue_DO_NOT_USE(0, 500):.6f}   <- not a p-value")
    print(f"  (1+k)/(N+1)= {permutation_pvalue(0, 500):.6f}")
    print("\nmachine-readable report:", asdict(rep))
