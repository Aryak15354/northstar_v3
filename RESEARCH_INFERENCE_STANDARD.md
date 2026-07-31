# Northstar Research Inference Standard v1.0

```
Status:    ADOPTED 2026-07-31
Supersedes: nothing. Extends GEN2_GEN3_RESEARCH_CONSTITUTION.yaml, GEN5_RESEARCH_CONSTITUTION.yaml
            and the per-generation charters with rules that apply to ALL of them.
Origin:     Gen-10 Remediation Programme. Every rule below exists because its violation was found
            in this repository and changed a verdict. None is precautionary.
Enforcement: src/research/gen10/inference.py makes rules 1-3 structural rather than remembered.
```

Six rules (one with three corollaries). Each is followed by the specific incident that motivated it, so nobody has to take them
on trust.

---

## Rule 1 — One date is one observation

**No hypothesis test may treat pooled stock-weeks as independent.** Collapse to a per-date series
before inference. Declare the overlap of any *h*-period forward return so the HAC bandwidth covers the
induced MA(*h*−1) structure.

> **Why.** AEP Paper B Sub-study 2 computed `se = sqrt(var(hi)/n_hi + var(lo)/n_lo)` over ~62,000
> stock-weeks. Corrected to ~1,030 dates, its **CONFIRMED** result became t = +0.57 with a sign that
> reverses out of sample, and its recorded **near-miss** became the stronger of the two. On lockbox
> data the same defective statistic would have "significantly confirmed" the exact opposite of the
> archived conclusion. — `archive_addenda/GEN10_ADDENDUM_001.md`

## Rule 2 — No verdict without a test

**ACCEPTED, POSITIVE, CONFIRMED and REAL may not be issued from a point estimate.** Every verdict
carries an interval. Every comparison states its minimum detectable effect **before** the run — a
design whose MDE exceeds its own bar is reported as underpowered, not run to a conclusion.

> **Why.** AEP Paper C gave verdicts to three of four sub-questions with no standard error anywhere.
> Supplying the tests: Q3 "ACCEPTED — the most economically material result" is t = +0.50 at 0.18× its
> own detection floor while giving up 3.26 %/yr of return; Q1/Q4 "POSITIVE" is t = −1.75. This was the
> **most common** defect Gen-10 found — more common than a wrong test.
> — `archive_addenda/GEN10_ADDENDUM_002.md`

## Rule 3 — Two estimators, or it is fragile

**Every headline number carries a HAC test and a distribution-free bootstrap interval.** Where they
disagree about significance, the result is reported **FRAGILE**. Neither may be selected after seeing
which is friendlier.

> **Why.** The NON_FNO_TAIL tier lead crosses |t| = 2 under Newey-West while its bootstrap interval
> includes zero. Reporting either alone would have been defensible and misleading.
> — `results/gen10/T1-08/`

## Rule 4 — Multiplicity counts everything tried

**Including specifications abandoned mid-run, resolutions selected from, and earlier looks at the same
question.** Correlated families use Benjamini-Yekutieli, not Benjamini-Hochberg.

> **Why.** AEP Paper D's monthly result cleared its own null by 5% and was recorded ACCEPTED; across
> the five resolutions it was selected from, p ≈ 0.038 against a Bonferroni threshold of 0.010. And
> Gen-10's own T1-05″ counted its 8 new tests against a family of 17 because T0-01 had already spent 9
> looks on the same question — which is why 2a was closed rather than promoted.
> — `archive_addenda/GEN10_ADDENDUM_003.md`

## Rule 5 — No comparison without provenance

**Every ledger row carries four fields: target horizon, target relativity, universe/panel, window.**
No two ICs are comparable unless all four match. **Any IC measured on a pooled multi-universe
cross-section must report its within-group value alongside the pooled one.**

> **Why.** `ret_13w`, `MOM60` and `DS-U-01` are one signal (per-date Spearman 0.969) carrying three
> archived verdicts. The cause was not harness configuration — it was the panel. Pooling two groups of
> stocks that differ systematically on both signal and forward return produced a cross-sectional IC
> *exceeding the IC of either group alone*; **36%** of the disputed number was composition. The
> artifact is coverage-dependent and therefore predictable: it cost the momentum-quality signals
> 30–40% and delivery ~0%. — `archive_addenda/GEN10_ADDENDUM_004.md`

### 5b — Corollary for panel designs

A **stock-level receiver is only a stock-level receiver if the regressor varies within a date.**
Averaging a group's returns and regressing on a date-constant shock reproduces a *group-level* design
under a stock-level label, and forfeits the power the stock dimension was supposed to buy.

> **Why.** G8-10 justified the Gen-7 redesign on 12.2 effective independent series from a stock-level
> receiver universe. A first implementation collapsed each sector group to a per-date mean — which is
> the sector-level design G8-10 measured at 1.49 series and called a false remedy. Only interacting
> the shock with each stock's own rolling exposure realises the gain. — `results/gen10/T1-10/`

## Rule 6 — Cross-group comparisons run on an explicitly common index

**Any Sharpe, IC or mean compared across groups must be computed on an explicitly constructed common
index.** A per-group `dropna()`, `continue`-on-empty, or minimum-count filter applied *before* a
cross-group comparison is **banned without a reconciliation step** that either restricts all groups to
the shared index or reports the coverage difference alongside the result.

> **Why.** This is the fifth appearance of one defect class — an implicit assumption that two things
> share an index, breaking silently. It has now shown up as pooled stock-weeks (Rule 1), pooled
> multi-universe cross-sections (Rule 5), mismatched estimation eras (T1-06's Sharpe-baseline trap),
> and twice as per-group date sets:
>
> `g8_07_capital_scale_sweep.backtest` computes `r = s_net[pre].dropna()` per config × tier, giving
> **NON_FNO_TAIL 712 weeks against every other tier's 1,070.** The excluded weeks are harder for
> *everyone* (ALL scores **+0.58** there vs **+1.01** on the common window), so the short-window tier
> collected a free ~+0.43 Sharpe. On common dates its lead halves and loses significance while
> SMALL_ADV_Q1's rises to t = 3.51 — **the ordering reverses, and G8-11's correction of G8-07 does not
> survive.** — `results/gen10/T1-11/`
>
> The precedent for elevating a twice-seen bug to standing law is the **Rolling-Window Persistence
> Principle** (M-01→M-01B, G6-00→G6-00B). This one has been seen five times.

### 6b — Latent compliance is not compliance

Code that is correct **because of its current data** rather than because of its structure must still
carry the reconciliation step.

> **Why.** `scripts/arp/delivery_capacity_recovery.py` compares CONTROL and ADD Sharpes with no
> reconciliation, and is clean only because both selectors happen to run on the same filtered frame
> and `s_add` is a superset of `s_control` — 338/338 identical dates. Change the delivery threshold,
> add a minimum-names floor, or alter the momentum cut, and it silently acquires G8-07's defect. That
> is exactly how G8-07 acquired it: nothing in the code is wrong until the data shifts under it.
> — `results/gen10/T1-12/`

### 6c — Equal n is not equal coverage

**A group that cannot form a book must be excluded, not filled.** Recording a synthetic value (0.0, the
market return, the previous value) for a period in which a group has no position makes coverage look
uniform while crediting that group with a return it never earned. Report the count of filled periods
per group, always.

> **Why.** `g8_11_smallcap_deep_dive.backtest` records `port = 0.0` whenever a tier is too thin to hold
> anything, and gates only the rebalance. Every tier therefore reports **1,070 weeks**, which reads as
> clean like-for-like coverage. In fact **41.8% of NON_FNO_TAIL's sample is synthetic zeros** — the
> tier's median name count is *0.0* for every year 2005-09 and 2013, because `fno_ok` is
> `adv_rank <= 190` and the early panel has fewer than 190 names, so the non-F&O tail is empty by
> construction. The tier sits flat at 0.0% through the entire GFC while `ALL` takes the drawdown.
>
> **This is worse than truncation.** Truncation removes hard periods from a comparison; zero-fill
> awards the favoured group a risk-free return through them. I nearly retracted a correct finding on
> the strength of that uniform `n_weeks` column. — `results/gen10/T1-13/` §3b

**Audit outcome (T1-12):** Delivery is clean on all three of its load-bearing artifacts, and G9-01's
liquidity gradient is identical to three decimals on a common cell set (−0.818, p = 0.0038). The
defect bites in exactly one place, and it is now recorded there.

---

## How to comply

```python
from src.research.gen10.inference import (
    nw_mean_test,               # Rule 1 + 3: HAC on a per-date series, bootstrap included
    date_clustered_group_diff,  # Rule 1: group contrasts, reports the naive t alongside
    ic_test, per_date_ic,       # Rule 1: cross-sectional IC as the unit of inference
    paired_sharpe_diff,         # Rule 2: correlated return streams, never two independent SEs
    min_detectable_sharpe_diff, # Rule 2: state the MDE before running
    benjamini_yekutieli,        # Rule 4: correlated families
)
```

**Rule 6 has no helper yet** — it is a review check. Before any cross-group comparison, print the
per-group index length. If they differ, either restrict to the intersection or say so in the output.
Three lines, and it would have caught G8-07.

`TestResult.fragile` implements Rule 3. `python src/research/gen10/inference.py` runs the calibration
self-test.

## What these rules do not do

They do not make results correct — T0-01 through T1-12 produced no new alpha and these rules would not
have found any. What they do is stop a full-sample fit, a missing standard error, an uncorrected
selection, a universe artifact, or a misaligned index from entering the permanent record as a finding.
**All six had already happened**, and the sixth had happened five times.
