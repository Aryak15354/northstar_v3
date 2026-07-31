# GEN-10 ADDENDUM 001 — `consistency_mom_26w`'s conditional role

```
Addendum:        GEN10_ADDENDUM_001
Issued:          2026-07-31
Author:          Aryak (Gen-10 Remediation Programme)
Addresses:       NSR-FIND-000042 (AEP-04)
Archive version: v1.0 (unmodified)
Evidence:        results/gen10/T0-01/T0-01_FINDINGS.md, results/gen10/T1-05/T1-05_FINDINGS.md
Mechanism:       archive/GEN7_INTERFACE_RULE.md — addendum, not edit
```

## 1. The archived finding

**NSR-FIND-000042 (AEP-04)** — Economic Law, Moderate confidence, traces to AEP-PAPER-B:

> *"consistency_mom_26w's conditional role does not cleanly resolve; tension between MI and
> return-spread methodologies."*

The archive is **not** altered. What follows is what Gen-10 found and how it differs.

## 2. What Gen-10 found

The finding's *statement* survives — the role still does not cleanly resolve. **Its evidence base is
inverted.**

AEP Paper B Sub-study 2 computed its t-statistics by pooling ~62,000 stock-weeks as independent
observations. They are not: forward returns over h weeks overlap by construction, and stocks within a
week share a market factor. The effective sample is ~1,030 dates.

Recomputed on the per-date difference series with Newey-West standard errors and a stationary block
bootstrap (naive column reproduces the archived numbers exactly, confirming the reproduction is
faithful and inference is the only thing that changed):

| role | horizon | archived t (pooled) | corrected t | effect |
|---|---|---|---|---|
| **2b "Warns"** | 4w | **+2.25 (CONFIRMED)** | **+0.57** | +0.13% |
| 2b "Warns" | 8w | +2.03 | −0.17 | −0.06% |
| 2b "Warns" | 13w | +2.07 | −0.46 | −0.24% |
| **2a "Confirms"** | 4w | +1.52 | **+2.52** | +0.65% |
| 2a "Confirms" | 8w | +1.97 (near-miss) | +2.21 | +1.04% |

- **2b, the role AEP recorded as CONFIRMED, is retired.** Its economic effect is ±0.03–0.24% with a
  sign that changes across horizons, and on 53 weeks of lockbox data that Paper B truncated away and
  never used, all four horizons come back **negative**.
- **2a, recorded as a near-miss, is the only coherent role of the four** — monotone +0.12% → +1.36%
  across horizons, consistently signed, bootstrap CI excluding zero at two horizons, and direction
  replicated on the unseen lockbox.

## 3. And 2a does not promote either

A follow-up (T1-05″) tested whether a more efficient estimator resolves 2a on existing data. The
original design uses ~22% of each week's cross-section; two replacements use 33% and 100%. All eight
tests agree in sign; **none reaches |t| = 2** (best 1.88), none clears Benjamini-Yekutieli at m = 8 or
at the honest m = 17 that counts T0-01's earlier looks, and the two estimators **disagree in sign** on
the lockbox.

Settling 2a by accumulating data would need |t| ≥ 3.10, i.e. n = 1,487 dates against 985 — **502 more
weeks, 9.7 more years.** It is closed as a documented near-effect.

## 4. Net effect on the archived record

| archived element | status after this addendum |
|---|---|
| NSR-FIND-000042 statement ("does not cleanly resolve") | **stands** |
| its stated cause (a confirmed role vs a near-miss) | **superseded** — no role confirmed; the near-miss was the stronger of the two |
| confidence: Moderate | **appropriate, arguably now High** — four roles closed on two independent designs |
| Prototype 2 (Conditional Momentum Confirmation), MODIFIED | **re-derived: no confirmed role.** 2b retired, 2c/2d rejected, 2a closed |

**Live (non-archive) documents updated to match:** `results/AEP_PAPER_B/`,
`results/AEP_PROTOTYPE_REGISTRY.md`, `results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §8c.

## 5. Why this is recorded rather than quietly fixed

The archive represents what was believed on the evidence available at freeze time. Paper B's
conclusion was reasonable given its own statistic; the statistic was wrong. Recording that as an
addendum keeps both facts — what was concluded, and why it changed — which is the point of the
interface rule.
