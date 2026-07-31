# T1-05″ — Paper B 2a With a Full-Cross-Section Estimator. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T0-01 (which left 2a unresolved and named this as the only route)
Artifacts:    t1_05_data.json. Script: scripts/gen10/t1_05_full_cross_section.py
```

**Outcome: the more efficient estimator does not rescue 2a — it weakens it. 2a is closed.**

---

## 1. The question

T0-01 left Sub-study 2a ("Confirms") unresolved: corrected t = +2.52 at 4w with a monotone,
consistently-signed effect, failing the pre-registered BY correction, and needing 9.7 more years to
settle by waiting. T0-01 named one remaining route — a more efficient estimator, since the original
design discards most of each week's cross-section.

Quantified: the original compares extreme consistency terciles **within** the top trend tercile, using
**~22%** of each week's names. Two estimators that use more:

- **E1 — conditional IC** (33% of names): per-date Spearman IC of consistency vs forward return
  within the High-Trend tercile. Uses every High-Trend name rather than the extremes.
- **E2 — Fama-MacBeth** (100%): per-date OLS of forward return on trend rank, consistency rank, and
  their interaction. The interaction coefficient is "Confirms" as a continuous effect.

## 2. Results — discovery window, 1,032 dates

| estimator | horizon | estimate | t | p | bootstrap 95% CI |
|---|---|---|---|---|---|
| E1 conditional IC | 1w | +0.00597 | 1.19 | 0.233 | [−0.0036, +0.0156] |
| **E1 conditional IC** | **4w** | **+0.01677** | **1.88** | **0.060** | [−0.0007, +0.0350] |
| E1 conditional IC | 8w | +0.01675 | 1.52 | 0.130 | [−0.0044, +0.0388] |
| E1 conditional IC | 13w | +0.01882 | 1.36 | 0.174 | [−0.0088, +0.0462] |
| E2 Fama-MacBeth | 1w | +0.00037 | 0.20 | 0.842 | [−0.0033, +0.0041] |
| E2 Fama-MacBeth | 4w | +0.00681 | 1.05 | 0.295 | [−0.0066, +0.0200] |
| E2 Fama-MacBeth | 8w | +0.01561 | 1.39 | 0.166 | [−0.0080, +0.0382] |
| E2 Fama-MacBeth | 13w | +0.01841 | 1.12 | 0.265 | [−0.0144, +0.0520] |

**Every one of the eight is positive** — the effect's sign is stable across estimators and horizons.
**None reaches |t| = 2**, and every bootstrap interval includes zero.

**The efficient estimators are weaker, not stronger** (best t = 1.88 vs T0-01's 2.52). That is
informative rather than disappointing: if the relationship were a clean monotone one, using the whole
cross-section would *tighten* the estimate. Diluting it instead points to an effect concentrated in
the tails of the consistency distribution — a weak or non-monotone relationship rather than a
tradeable ranking signal.

## 3. Multiplicity, stated honestly

This is a **second look at data already tested in T0-01**. The honest family is T0-01's 9 tests plus
these 8 = **17**. Nothing clears BY at either m = 8 or m = 17; the best p is 0.060.

## 4. Lockbox — 53 weeks, never seen by Paper B

| estimator | 4w | 8w |
|---|---|---|
| E1 conditional IC | +0.0305 (t = 1.16) | +0.0340 (t = 0.76) |
| E2 Fama-MacBeth | **−0.0129** (t = −1.32) | **−0.0236** (t = −1.14) |

The two estimators **disagree in sign** out of sample. T0-01's lockbox showed the tercile-contrast
version replicating in direction; the continuous version does not. Neither is significant on 49
dates, but the disagreement removes the one piece of supporting evidence 2a had.

## 5. Verdict — closed

**2a is closed as a documented near-effect.** Two independent designs on the same 985 weeks — an
extreme-tercile contrast and a full-cross-section regression — both find a consistently-signed effect
that will not clear a correction for the number of looks taken at it, and the two disagree out of
sample.

**Further estimators on this data would be a search, not a test.** Seventeen looks have now been
taken at one question. The pre-registered discipline that made T0-01 worth doing is the same
discipline that says to stop here.

## 6. Findings

**G10-F26 — Paper B Sub-study 2a is closed as unresolved.** Eight additional tests using 33% and 100%
of the cross-section (against the original's 22%) all agree in sign and none reaches |t| = 2; the
best is 1.88. Nothing clears BY at m = 8 or m = 17.

**G10-F27 — the effect, if real, lives in the tails of the consistency distribution.** A more
efficient estimator producing a *weaker* result is the signature of a non-monotone or
tail-concentrated relationship, not a linear ranking effect. That is worth recording because it also
explains why the original tercile-contrast design found the most: it was, accidentally, the best
estimator for the shape of whatever is there.

**G10-F28 — Prototype 2 (Conditional Momentum Confirmation) closes with no confirmed role.** 2b
retired in T0-01 (sign-flipped out of sample), 2c and 2d rejected there, and 2a closed here. All four
candidate roles for `consistency_mom_26w` as a conditional signal are now closed.

## 7. Threats to validity

- **E2 assumes a linear interaction in rank space.** A genuinely non-monotone effect — which §6
  suggests — is one this estimator is poorly suited to, so its weakness is partly expected and should
  not be read as independent disconfirmation. E1, which is rank-based and makes no linearity
  assumption, is the more informative of the two and it also fails.
- **The lockbox is 49 usable dates** and cannot confirm or refute anything; it is used only for sign
  agreement, and it is the *disagreement* between estimators that is reported, not either level.
- **The m = 17 family counts tests, not independent questions.** Horizons within an estimator are
  nested and correlated, so BY at m = 17 is conservative. 2a does not clear the more generous m = 8
  either, so the choice does not drive the verdict.
