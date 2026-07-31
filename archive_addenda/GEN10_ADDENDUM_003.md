# GEN-10 ADDENDUM 003 — The monthly-resolution signal does not survive multiplicity

```
Addendum:        GEN10_ADDENDUM_003
Issued:          2026-07-31
Author:          Aryak (Gen-10 Remediation Programme)
Addresses:       NSR-FIND-000045 (AEP-07)
Archive version: v1.0 (unmodified)
Evidence:        results/gen10/T1-07/T1-07_FINDINGS.md
Mechanism:       archive/GEN7_INTERFACE_RULE.md — addendum, not edit
```

## 1. The archived finding

**NSR-FIND-000045 (AEP-07)** — Economic Law, Moderate confidence, traces to AEP-PAPER-D:

> *"Narrow, marginal RISING signal at monthly decision resolution only (quarterly was small-sample
> bias)."*

The archive is **not** altered.

## 2. What Gen-10 found

Paper D tested five decision-time resolutions. Monthly cleared its own permutation null by **5.0%**
(MI 0.02577 vs null p95 0.02454) and was recorded ACCEPTED. **No correction was applied across the
five resolutions it was selected from.**

Applying it (p-values reconstructed from the stored null mean and p95 with an exponential-tail fit
anchored exactly at p95 → p = 0.05):

| resolution | n_obs | p | archived | Bonferroni | BH q=.05 | BY q=.05 |
|---|---|---|---|---|---|---|
| weekly | 1,070 | 0.804 | ✗ | ✗ | ✗ | ✗ |
| biweekly | 535 | 0.381 | ✗ | ✗ | ✗ | ✗ |
| **monthly** | 267 | **0.038** | **✓** | **✗** | **✗** | **✗** |
| 6-week | 178 | 1.000 | ✗ | ✗ | ✗ | ✗ |
| quarterly | 82 | 0.333 | ✗ | ✗ | ✗ | ✗ |

**Monthly fails all three.** The Bonferroni threshold at m = 5 is 0.0100 against p ≈ 0.0384.

## 3. Why monthly and not another resolution

The permutation null's width is driven by the number of non-overlapping windows:

```
weekly     n=1070   null p95 = 0.00583
biweekly   n= 535   null p95 = 0.01126
monthly    n= 267   null p95 = 0.02454
6week      n= 178   null p95 = 0.03739
quarterly  n=  82   null p95 = 0.09101
```

Aggregating to longer windows raises measured MI; shrinking n widens the null. Monthly is the single
point where n is still large enough to keep the null tight while aggregation has lifted MI. **That is
a property of the null's shape across resolutions, not an economic decision cadence.**

The archived "RISING" label is also easily misread, and was: `_summary.classification` is a
pre-registered label for the *curve shape* across resolutions (any resolution ≥ 3× weekly), computed
once on the full sample. It does not mean the margin has been widening as data accumulates.

## 4. What this settles

Paper D existed to check whether Gen-5 **F17** ("regime state predicts weekly correct action",
REJECTED, normalized MI 0.003–0.012, near noise) was a resolution artifact. It answered the question.
The answer is the same one:

**Market state carries no usable information about the correct portfolio action at weekly, biweekly,
monthly, 6-week or quarterly cadence.** F17 was not a resolution artifact.

## 5. Net effect on the archived record

| archived element | status after this addendum |
|---|---|
| NSR-FIND-000045, monthly half ("narrow, marginal RISING signal") | **withdrawn** — fails Bonferroni, BH and BY at m = 5 |
| NSR-FIND-000045, quarterly half ("quarterly was small-sample bias") | **stands** |
| Prototype 4 (Resolution Study), MODIFIED | **re-derived: REJECTED at all resolutions** |
| Paper D overall verdict, MODIFIED | **REJECTED** |
| Gen-5 F17 | **strengthened** — now settled across five cadences rather than one |

**Live documents updated to match:** `results/AEP_PAPER_D/`, `results/AEP_PROTOTYPE_REGISTRY.md`,
`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §8e.

## 6. Threat to validity of this addendum

The p-values are **reconstructed**, not stored — the archive keeps each null's mean and 95th
percentile, not the draws. The exponential-tail fit is exact at the anchor that matters (p95 → 0.05),
but the tail shape between anchors is an assumption. Monthly would need p ≤ 0.0100 to survive
Bonferroni; recovering that from a reconstructed 0.0384 would require the true null to be far more
right-skewed than exponential. **Re-running `scripts/aep/paper_d_resolution_study.py` with the
permutation draws retained would settle it exactly**, and should be done if this addendum is ever
contested.
