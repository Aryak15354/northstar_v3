# T1-07 — AEP Paper D: Multiplicity Across Resolutions. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/AEP_PAPER_D/resolution_curve.json, GEN10_REMEDIATION_CHARTER.md s4/T1-07
Artifacts:    t1_07_data.json. Script: scripts/gen10/t1_07_paper_d_multiplicity.py
```

**Outcome: monthly does not survive correction for the five resolutions it was selected from.
RETIRED.** Gen-5 F17's weekly null is now the settled answer at every decision cadence tested.

---

## 1. What was archived

Paper D asked whether market state carries information about the correct portfolio action, at five
decision-time resolutions. Monthly cleared its own permutation null and was recorded
**ACCEPTED (barely) — RISING**. No correction was applied across the five resolutions.

| resolution | n_obs | MI | null mean | null p95 | archived |
|---|---|---|---|---|---|
| weekly | 1,070 | 0.00272 | 0.00247 | 0.00583 | rejected |
| biweekly | 535 | 0.00709 | 0.00511 | 0.01126 | rejected |
| **monthly** | **267** | **0.02577** | 0.01071 | **0.02454** | **ACCEPTED** |
| 6-week | 178 | 0.00282 | 0.01500 | 0.03739 | rejected |
| quarterly | 82 | 0.05921 | 0.04080 | 0.09101 | rejected |

## 2. Correction

The archive stores each null's mean and 95th percentile rather than the draws, so p-values were
reconstructed with an exponential-tail fit anchored so that the stored p95 maps to exactly p = 0.05.
Monthly's reconstructed p ≈ **0.0384**.

| resolution | p | archived | Bonferroni | BH q=.05 | BY q=.05 |
|---|---|---|---|---|---|
| weekly | 0.804 | ✗ | ✗ | ✗ | ✗ |
| biweekly | 0.381 | ✗ | ✗ | ✗ | ✗ |
| **monthly** | **0.038** | **✓** | **✗** | **✗** | **✗** |
| 6-week | 1.000 | ✗ | ✗ | ✗ | ✗ |
| quarterly | 0.333 | ✗ | ✗ | ✗ | ✗ |

**Monthly fails all three corrections.** The Bonferroni threshold at m=5 is 0.0100 against p ≈ 0.0384.

## 3. Why monthly and not another resolution

Monthly clears its own null by **5.0%** — 0.02577 against 0.02454. And the null band widens sharply
as the number of non-overlapping windows falls:

```
weekly     n=1070   null p95 = 0.00583
biweekly   n= 535   null p95 = 0.01126
monthly    n= 267   null p95 = 0.02454
6week      n= 178   null p95 = 0.03739
quarterly  n=  82   null p95 = 0.09101
```

Aggregating to longer windows raises measured MI; shrinking n widens the null. Monthly is the point
where n is still large enough to keep the null tight while aggregation has lifted MI. **That is a
property of the null's shape across resolutions, not evidence of an economic decision cadence.**

This also explains the archived "RISING" label, which the remediation plan read as a possible
strengthening-over-time signal. It is not: `_summary.classification` is a pre-registered label for the
*curve shape* across resolutions (any resolution ≥ 3× weekly), computed once on the full sample. The
plan's step 1 for this item ("check whether RISING means the margin has been getting wider as more
data comes in") is answered — it does not.

## 4. Findings

**G10-F14 — AEP Paper D's monthly result does not survive correction for the five resolutions it was
selected from.** p ≈ 0.0384 against a Bonferroni threshold of 0.0100, and it fails BH and BY as well.
It cleared its own null by 5%, and it is the resolution structurally most able to do so.

**G10-F15 — Gen-5 F17 is now settled at every resolution tested.** Market state carries no usable
information about the correct portfolio action at weekly, biweekly, monthly, 6-week or quarterly
cadence. F17's original weekly finding (normalized MI 0.003–0.012, near noise) was not a
resolution artifact, which is exactly what Paper D was commissioned to check. It answered the
question — the answer is just the same one.

## 5. Errata

1. **`results/AEP_PAPER_D/PAPER_D_DECISION_RESOLUTION_STUDY.md`** — monthly's ACCEPTED verdict
   withdrawn; Paper D's overall verdict moves from MODIFIED to REJECTED across all resolutions.
2. **`archive/11_registries/FINDINGS_REGISTRY.csv`, finding #45** ("Narrow RISING signal at monthly
   resolution only; quarterly was bias") — the monthly half is withdrawn; the quarterly half
   (small-sample artifact at n=82) stands.
3. **`AEP_PROTOTYPE_REGISTRY.md`, Prototype 4** — MODIFIED re-derived to REJECTED.
4. **`Northstar_Remediation_Priority_Plan.md` §2.8** — closed; the plan was right to be suspicious,
   for a different reason than it gave.

## 6. Threats to validity

- **The p-values are reconstructed, not stored.** The exponential-tail fit is anchored exactly at the
  stored p95 → p = 0.05, so the reconstruction is exact at the one point that matters most, but the
  tail shape between anchor points is an assumption. Monthly would need p ≤ 0.0100 to survive
  Bonferroni; recovering that from a reconstructed 0.0384 would require the true null to be far more
  right-skewed than an exponential. Re-running `paper_d_resolution_study.py` with the permutation
  draws retained would settle it exactly, and is worth doing if this verdict is ever contested.
- **m = 5 is the honest multiplicity** — five resolutions were pre-registered and all five were run.
  It does not count the Gen-5 F17 weekly test that preceded them, which would make the correction
  stricter, not looser.
- No new data was used and no experiment was re-run; this is a correction to the arithmetic of an
  existing result.
