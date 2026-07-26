#!/usr/bin/env python3
"""Mandatory power pre-flight for any test that functions as a gate.

Fixes defects **1b** (power disclosure) and **1c** (holdout sizing) in `GEN8_RESEARCH_CHARTER.md` §3.1,
implementing **Amendment-002** (`docs/GEN7_CHARTER_AMENDMENTS.md`) as executable infrastructure rather
than as a discipline someone has to remember.

--------------------------------------------------------------------------------------------------
The bug, precisely
--------------------------------------------------------------------------------------------------
Gen-7's Laboratory 8 adjudicated effects of |r| ~ 0.10-0.14 with a **51-53 week** lockbox, using sign
agreement alone — no CI, no significance test, no power analysis. At n=52 the Fisher-z standard error
is 0.143, i.e. **larger than every effect being tested**. The minimum detectable effect at 80% power
was |r| = 0.377, a 2.6x gap. All six lockbox CIs contained zero; 3-of-6 sign agreement is exactly the
binomial expectation under "none of these are real" (p = 1.000).

The test was ~87% likely to be uninformative before it was run, and that fact was computable in
advance from n alone — no data required.

--------------------------------------------------------------------------------------------------
What this module enforces
--------------------------------------------------------------------------------------------------
Before an experiment computes anything it will report, it calls `power_precheck(...)` with:

  * the actual sample size and test design,
  * the **meaningful effect size** the scientific question cares about, stated in the contract.

The precheck computes the minimum detectable effect at 80% power and the finest resolvable statistic,
prints them, and **raises `UnderpoweredGateError`** if the design cannot detect the effect that
matters. Proceeding anyway requires an explicit `allow_underpowered=True` (wired to the
`--i-understand-this-is-underpowered` CLI flag), which is recorded in the returned report and must be
carried into the findings document — there is no silent path.

For model classes where no closed form exists (G8-01's GRU/LSTM/autoencoder), `simulation_power`
estimates power by injecting a known effect and measuring the recovery rate. That is also the
executable form of **Amendment-003**: a procedure not shown capable of returning a positive cannot be
cited as evidence of a negative.

--------------------------------------------------------------------------------------------------
Holdout sizing (defect 1c)
--------------------------------------------------------------------------------------------------
`required_n_for_correlation(r, ...)` answers "how long must the holdout be?" *before* one is carved
out. `recommend_validation_design(...)` turns that into a decision: when the available data cannot
support an adequately powered single holdout, it says so and recommends rolling-origin
cross-validation instead — which is the honest response, rather than running the underpowered lockbox
and treating its output as a verdict.


---
RESEARCH OS lineage: forked from scripts/gen8/lib/power_precheck.py (2026-07-26). Per GEN8_RESEARCH_CHARTER.md section 11's own inheritance contract, this becomes the canonical shared copy for all four Northstar Institute labs. scripts/gen8/lib/power_precheck.py is UNCHANGED and remains the historical Gen-8 record -- this is a fork, not a move, per the never-silently-rewrite-history discipline."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Callable, Sequence

import numpy as np
from scipy import stats


class UnderpoweredGateError(RuntimeError):
    """A gate's minimum detectable effect exceeds the effect it is supposed to adjudicate."""


# ---------------------------------------------------------------------------------------------
# Closed-form power for a correlation (Fisher z)
# ---------------------------------------------------------------------------------------------
def fisher_z_se(n: int) -> float:
    """Standard error of the Fisher z transform of a correlation: ``1/sqrt(n-3)``."""
    if n <= 3:
        raise ValueError(f"n must be > 3 for the Fisher-z approximation, got {n}")
    return 1.0 / math.sqrt(n - 3)


def min_detectable_correlation(n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest |r| detectable at the given power and two-sided alpha, at sample size n."""
    z_a = stats.norm.ppf(1.0 - alpha / 2.0)
    z_b = stats.norm.ppf(power)
    return float(np.tanh((z_a + z_b) * fisher_z_se(n)))


def power_for_correlation(r: float, n: int, alpha: float = 0.05) -> float:
    """Power to detect a true correlation ``r`` at sample size ``n``, two-sided.

    **This is an upper bound, not an estimate**, for any test applied to serially dependent data.
    The Fisher-z form assumes i.i.d. observations; a Newey-West HAC or block-bootstrap test on the
    same n has a larger effective standard error and therefore less power. Cross-check against
    Gen-7's RA-006, which simulated the actual estimator on the actual series: at r=0.11 and n=1017
    it reports 31% (m=310) and 60% (m=31), where this closed form gives 39.9% and 64.2%. The
    direction and the size of the multiplicity gain agree; the levels differ by roughly the
    efficiency the HAC estimator gives up to serial dependence.

    Consequence for use: closed-form power is fine for *rejecting* a design (if the optimistic bound
    is already below target, the real design certainly is). Claiming a design is adequately powered
    on a marginal closed-form number is not — use `simulation_power` against the actual detector.
    """
    if n <= 3:
        return 0.0
    z_a = stats.norm.ppf(1.0 - alpha / 2.0)
    lam = abs(np.arctanh(r)) / fisher_z_se(n)
    return float(stats.norm.sf(z_a - lam) + stats.norm.cdf(-z_a - lam))


def required_n_for_correlation(r: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Sample size needed to detect ``r`` at the given power. The holdout-sizing calculation (1c)."""
    if r == 0:
        return int(np.inf) if False else 10 ** 12  # a zero effect is never detectable
    z_a = stats.norm.ppf(1.0 - alpha / 2.0)
    z_b = stats.norm.ppf(power)
    return int(math.ceil(3.0 + ((z_a + z_b) / abs(np.arctanh(r))) ** 2))


def multiplicity_adjusted_alpha(alpha: float, m: int, method: str = "BH") -> float:
    """The effective per-test alpha a family of ``m`` tests faces at rank 1.

    Using the rank-1 threshold is conservative for BH (a survivor at a lower rank faces a looser
    bound), and is the right number for a *power* calculation: it is the bar a single pre-registered
    candidate has to clear when it is the only real effect present, which is the case power analysis
    should be planned against.
    """
    from .valid_pvalue import strictest_threshold  # local import keeps the modules independent
    return float(strictest_threshold(m, alpha, method))


# ---------------------------------------------------------------------------------------------
# Simulation-based power, for designs with no closed form (Amendment-003 in executable form)
# ---------------------------------------------------------------------------------------------
def simulation_power(detector: Callable[[np.ndarray, np.ndarray], bool],
                     generator: Callable[[float, np.random.Generator], tuple],
                     effect_size: float, n_sims: int = 200, seed: int = 42) -> dict:
    """Estimate power by injecting a known effect and counting how often the detector fires.

    ``generator(effect_size, rng) -> (X, y)`` synthesises data carrying the stated effect;
    ``detector(X, y) -> bool`` is the experiment's own decision procedure, unmodified.

    Returns the recovery rate plus a Wilson 95% interval. Run at ``effect_size=0`` this is a
    false-positive-rate calibration instead; both are required before a null may be reported.
    """
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_sims):
        X, y = generator(effect_size, rng)
        hits += bool(detector(X, y))
    p = hits / n_sims
    z = 1.959963984540054
    denom = 1 + z ** 2 / n_sims
    centre = (p + z ** 2 / (2 * n_sims)) / denom
    half = z * math.sqrt(p * (1 - p) / n_sims + z ** 2 / (4 * n_sims ** 2)) / denom
    return dict(effect_size=float(effect_size), n_sims=int(n_sims), n_detected=int(hits),
                power=float(p), ci95=(float(max(0.0, centre - half)), float(min(1.0, centre + half))),
                seed=int(seed))


def power_curve(detector, generator, effect_sizes: Sequence[float], n_sims: int = 200,
                seed: int = 42) -> list[dict]:
    """`simulation_power` across a grid — the shape RA-006 used to overturn Gen-7's own conclusion."""
    return [simulation_power(detector, generator, e, n_sims, seed + i)
            for i, e in enumerate(effect_sizes)]


# ---------------------------------------------------------------------------------------------
# The precheck itself
# ---------------------------------------------------------------------------------------------
@dataclass
class PowerReport:
    experiment: str
    test_design: str
    n: int
    alpha_nominal: float
    m_tests: int
    alpha_effective: float
    target_power: float
    meaningful_effect: float
    min_detectable_effect: float
    power_at_meaningful_effect: float
    finest_resolvable_statistic: float
    required_n_for_meaningful_effect: int
    adequately_powered: bool
    proceeded_underpowered: bool = False
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        verdict = ("ADEQUATELY POWERED" if self.adequately_powered
                   else ("UNDERPOWERED (proceeding under explicit override)"
                         if self.proceeded_underpowered else "UNDERPOWERED"))
        lines = [
            f"POWER PRECHECK [{self.experiment}] -- {verdict}",
            f"  design                       : {self.test_design}",
            f"  sample size n                : {self.n:,}",
            f"  simultaneous tests m         : {self.m_tests}",
            f"  alpha (nominal / effective)  : {self.alpha_nominal:.4g} / {self.alpha_effective:.4g}",
            f"  meaningful effect (contract) : {self.meaningful_effect:.4f}",
            f"  min detectable @ {self.target_power:.0%} power  : {self.min_detectable_effect:.4f}",
            f"  power AT the meaningful effect: {self.power_at_meaningful_effect:.1%}",
            f"  finest resolvable statistic  : {self.finest_resolvable_statistic:.3e}",
            f"  n required for meaningful eff: {self.required_n_for_meaningful_effect:,} "
            f"(have {self.n:,})",
        ]
        lines += [f"  note: {x}" for x in self.notes]
        return "\n".join(lines)


def power_precheck(experiment: str,
                   n: int,
                   meaningful_effect: float,
                   m_tests: int = 1,
                   alpha: float = 0.05,
                   target_power: float = 0.80,
                   correction: str = "BH",
                   test_design: str = "two-sided correlation test (Fisher z)",
                   finest_resolvable_statistic: float | None = None,
                   allow_underpowered: bool = False,
                   verbose: bool = True) -> PowerReport:
    """**Mandatory pre-flight.** Call before computing anything the experiment will report.

    Raises `UnderpoweredGateError` when the design's minimum detectable effect exceeds the
    contract's stated meaningful effect, unless ``allow_underpowered=True`` — which every Gen-8
    experiment wires to an explicit `--i-understand-this-is-underpowered` flag and which is recorded
    in the returned report, in the experiment's JSON output, and in its findings document.
    """
    alpha_eff = multiplicity_adjusted_alpha(alpha, m_tests, correction) if m_tests > 1 else alpha
    mde = min_detectable_correlation(n, alpha_eff, target_power)
    pwr = power_for_correlation(meaningful_effect, n, alpha_eff)
    req_n = required_n_for_correlation(meaningful_effect, alpha_eff, target_power)
    if finest_resolvable_statistic is None:
        finest_resolvable_statistic = fisher_z_se(n)

    rep = PowerReport(
        experiment=experiment, test_design=test_design, n=int(n), alpha_nominal=float(alpha),
        m_tests=int(m_tests), alpha_effective=float(alpha_eff), target_power=float(target_power),
        meaningful_effect=float(meaningful_effect), min_detectable_effect=float(mde),
        power_at_meaningful_effect=float(pwr),
        finest_resolvable_statistic=float(finest_resolvable_statistic),
        required_n_for_meaningful_effect=int(req_n),
        adequately_powered=bool(mde <= abs(meaningful_effect)),
    )
    if m_tests > 1:
        rep.notes.append(
            f"multiplicity reduction is usually the cheapest power gain available: at n={n}, going "
            f"from m={m_tests} to m=1 moves power at the meaningful effect from "
            f"{pwr:.1%} to {power_for_correlation(meaningful_effect, n, alpha):.1%} "
            f"with no new data (Gen-7 G7-F06)."
        )
    if verbose:
        print(rep.summary())

    if not rep.adequately_powered:
        if not allow_underpowered:
            raise UnderpoweredGateError(
                rep.summary()
                + f"\n\n  This gate cannot adjudicate its own question: it can only detect effects of "
                  f"|{mde:.3f}| or larger, while the question is about |{meaningful_effect:.3f}|.\n"
                  f"  Per Amendment-002, a gate whose minimum detectable effect exceeds the effect "
                  f"under test must not be reported as adjudicating, in either direction.\n"
                  f"  Options: (a) redesign — reduce m, pool observations, or change the statistic; "
                  f"(b) obtain n >= {req_n:,}; (c) switch to a validation design that uses all the "
                  f"data (see recommend_validation_design); or (d) pass "
                  f"allow_underpowered=True / --i-understand-this-is-underpowered, in which case the "
                  f"result is classified UNRESOLVED, never NEGATIVE EVIDENCE."
            )
        rep.proceeded_underpowered = True
        rep.notes.append("PROCEEDED UNDERPOWERED under explicit override; any null from this gate is "
                         "classified UNRESOLVED, not NEGATIVE EVIDENCE (charter §6).")
        if verbose:
            print("  !! proceeding UNDERPOWERED under explicit override -- outcome will be UNRESOLVED")
    return rep


# ---------------------------------------------------------------------------------------------
# Holdout sizing / validation-design decision (defect 1c)
# ---------------------------------------------------------------------------------------------
@dataclass
class ValidationDesignRecommendation:
    n_total: int
    meaningful_effect: float
    required_holdout_n: int
    max_holdout_available: int
    single_holdout_viable: bool
    recommended_design: str
    rationale: str

    def summary(self) -> str:
        return (f"VALIDATION DESIGN: {self.recommended_design}\n"
                f"  effect to adjudicate         : |r| = {self.meaningful_effect:.4f}\n"
                f"  holdout n required @80% power: {self.required_holdout_n:,}\n"
                f"  holdout n actually available : {self.max_holdout_available:,}\n"
                f"  single fixed holdout viable  : {self.single_holdout_viable}\n"
                f"  rationale: {self.rationale}")


def recommend_validation_design(n_total: int, meaningful_effect: float, alpha: float = 0.05,
                                target_power: float = 0.80, min_train_fraction: float = 0.60,
                                verbose: bool = True) -> ValidationDesignRecommendation:
    """Decide between a single fixed holdout and rolling-origin CV, *before* carving out a holdout.

    A single holdout is recommended only if enough observations can be reserved to detect the effect
    that matters while leaving ``min_train_fraction`` of the sample for discovery. Otherwise the
    honest move is a design that uses every observation for validation at some point.
    """
    req = required_n_for_correlation(meaningful_effect, alpha, target_power)
    max_holdout = int(math.floor(n_total * (1.0 - min_train_fraction)))
    viable = req <= max_holdout
    if viable:
        design = f"single fixed holdout of {req:,} observations (lockbox), opened exactly once"
        rationale = (f"{max_holdout:,} observations can be reserved while keeping "
                     f"{min_train_fraction:.0%} for discovery, and {req:,} are needed to detect "
                     f"|r|={meaningful_effect:.3f} at {target_power:.0%} power.")
    else:
        design = "rolling-origin cross-validation (expanding window, no single fixed lockbox)"
        rationale = (
            f"detecting |r|={meaningful_effect:.3f} at {target_power:.0%} power needs {req:,} "
            f"holdout observations, but only {max_holdout:,} can be reserved from n={n_total:,} "
            f"while keeping {min_train_fraction:.0%} for discovery. A fixed holdout of "
            f"{max_holdout:,} would have {power_for_correlation(meaningful_effect, max(max_holdout, 4), alpha):.0%} "
            f"power — it would not adjudicate, and reporting it as if it had is exactly Gen-7's "
            f"CRITICAL-2. Rolling-origin CV uses every observation out-of-sample at some origin, at "
            f"the cost of overlapping evaluation windows, which must be accounted for when combining "
            f"fold statistics (do not treat folds as independent)."
        )
    rec = ValidationDesignRecommendation(
        n_total=int(n_total), meaningful_effect=float(meaningful_effect),
        required_holdout_n=int(req), max_holdout_available=int(max_holdout),
        single_holdout_viable=bool(viable), recommended_design=design, rationale=rationale)
    if verbose:
        print(rec.summary())
    return rec


def add_underpowered_flag(parser):
    """Attach the standard override flag to an experiment's argparse parser."""
    parser.add_argument("--i-understand-this-is-underpowered", action="store_true",
                        dest="allow_underpowered",
                        help="proceed past the power precheck; the result is then classified "
                             "UNRESOLVED, never NEGATIVE EVIDENCE, and the override is logged")
    return parser


if __name__ == "__main__":
    print("Gen-7 Laboratory 8's lockbox, as it was run:")
    power_precheck("gen7-lab8-lockbox (retrospective)", n=52, meaningful_effect=0.11, m_tests=1,
                   test_design="sign agreement on a 52-week holdout correlation",
                   allow_underpowered=True)
    print("\nGen-7 Lab 2's discovery scan, as it was run (m=310):")
    power_precheck("gen7-lab2-discovery (retrospective)", n=1017, meaningful_effect=0.11, m_tests=310,
                   allow_underpowered=True)
    print("\nSame data, one pre-registered lag per carrier (m=31) -- the G7-F06 gain:")
    power_precheck("gen8-g8-02 (m=31)", n=1017, meaningful_effect=0.11, m_tests=31,
                   allow_underpowered=True)
    print()
    recommend_validation_design(n_total=1070, meaningful_effect=0.11)
