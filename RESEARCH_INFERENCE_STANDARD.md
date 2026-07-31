# Northstar Research Inference Standard v1.0

```
Status:    ADOPTED 2026-07-31
Supersedes: nothing. Extends GEN2_GEN3_RESEARCH_CONSTITUTION.yaml, GEN5_RESEARCH_CONSTITUTION.yaml
            and the per-generation charters with rules that apply to ALL of them.
Origin:     Gen-10 Remediation Programme. Every rule below exists because its violation was found
            in this repository and changed a verdict. None is precautionary.
Enforcement: src/research/gen10/inference.py makes rules 1-3 structural rather than remembered.
```

Five rules. Each is followed by the specific incident that motivated it, so nobody has to take them
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

`TestResult.fragile` implements Rule 3. `python src/research/gen10/inference.py` runs the calibration
self-test.

## What these rules do not do

They do not make results correct — T0-01 through T1-10 produced no new alpha and these rules would not
have found any. What they do is stop a full-sample fit, a missing standard error, an uncorrected
selection, or a universe artifact from entering the permanent record as a finding. Four of those five
things had already happened.
