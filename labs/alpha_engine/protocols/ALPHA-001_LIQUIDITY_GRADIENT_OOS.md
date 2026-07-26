# ALPHA-001 — Liquidity-Gradient Out-of-Sample Test on a Fresh Holdout

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                alpha_engine
Depends On:         results/gen8/G9-01/G9-01_FINDINGS.md (the corrected liquidity-gradient finding),
                    labs/microstructure/results/MICRO-001/FINDINGS.md (rules out exit-fill realism
                    as a material confound), labs/microstructure/protocols/MICRO-002_DATA_ACQUISITION.md
                    (the ownership-mechanism question remains open and unresolved)
```

## 1. Why this proceeds despite MICRO-002 being blocked

The restructuring plan gates this test on 1a and 1b producing "a sharper mechanism story." 1b
(institutional ownership, MICRO-002) is blocked by a genuine data gap and remains unresolved. 1a
(MICRO-001) did sharpen the story in a real, if narrower, way: it **ruled out execution-realism at
delisting exits as a material confound** (modeled drag −0.015%/yr differential, two orders of
magnitude below the materiality bar). Combined with G9-01's own finding that sector composition is
also ruled out, **two of the plausible alternative explanations for the liquidity gradient are now
eliminated, even though the positive mechanism (why liquidity predicts receptivity) remains
unconfirmed.** This is enough to justify testing whether the *effect itself* replicates
out-of-sample — a narrower claim than confirming *why* it exists, and the two are appropriately kept
separate in this contract's conclusions.

## 2. Why this holdout is legitimate

The window tested here (2025-07-11 through 2026-07-10, 53 weeks) has not been inspected by any prior
liquidity-gradient analysis — G8-07, G8-11, G9-01, and G9-02 all restrict to `date < 2025-07-11`
throughout. It is a genuinely fresh window for *this* question. (It is the same calendar window
Gen-7's Lab 8 used as its cross-asset transmission lockbox — but that lockbox was opened for a
completely different hypothesis, external carrier-to-equity transmission, using none of the domestic
cross-sectional machinery this test uses. Reusing the calendar window for an unrelated domestic
question is not re-opening Gen-7's lockbox; it is a different experiment that happens to share a
time period.)

## 3. Research question

Does the liquidity-decile gradient in momentum's cross-sectional IC (G9-01: Spearman(decile, IC) =
−0.818, p=0.0038, least-liquid decile carrying 2.2× the IC of most-liquid) replicate directionally on
data none of this session's liquidity-gradient work has seen?

## 4. Pre-registered specification

**One signal, one comparison, chosen before looking at the fresh window:** `res_mom_52w_ex4w` —
Config-4's own top Shapley contributor and MSRP's highest-incremental-retention information
primitive, the single least arbitrary choice available, and specifically **not** re-selected from the
17-signal sweep that found the aggregate tier effect. Compare mean weekly cross-sectional Spearman IC
in liquidity decile 0 (least liquid) against decile 9 (most liquid), on the 53 post-lockbox weeks.

## 5. Power disclosure — computed BEFORE looking at the fresh window's results

```
POWER PRECHECK [ALPHA-001 liquidity-gradient OOS (53wk)] -- UNDERPOWERED
  sample size n                : 53
  meaningful effect (contract) : 0.24 (standardized, matching G9-01's decile-gradient magnitude)
  min detectable @ 80% power   : 0.377
  power AT the meaningful effect: 40.9%
  n required for meaningful effect: 135 (have 53)
```

**This is, numerically, close to Gen-7's own 51–53 week lockbox that the audit found had ~13% power
for a smaller effect — the same order-of-magnitude lesson recurring on a domestic question.** Per
Amendment-002/003 and this lab's own charter, this is disclosed *before* running the test, and the
outcome rule below is fixed in advance specifically because of this number, not fitted afterward.

## 6. Pre-committed outcome rule (fixed before any result is seen)

**Given 40.9% power, no outcome from this test alone can be classified VALIDATED or REJECTED.** The
test is run anyway — because directional information at 41% power is not zero information, and a
53-week check costs nothing to compute — but the verdict is fixed in advance:

- If the direction matches G9-01 (decile 0 IC > decile 9 IC): **INCONCLUSIVE — directionally
  consistent, underpowered to confirm.**
- If the direction reverses: **INCONCLUSIVE — directionally inconsistent, underpowered to refute
  either the original finding or this check.** Explicitly NOT treated as a rejection of G9-01, because
  a reversal at 41% power is exactly the kind of noise Gen-7's Oil sign-flip taught this programme to
  distrust (p=0.249 there, on a comparably-sized sample).
- **Neither outcome updates the master registry's confidence in G9-01 itself** — it stands on its own
  much larger, better-powered sample (810 weeks, sign test across 17 signals, p=0.00027).

## 7. Economic check (Alpha Engine charter requirement) — same power caveat applies

A long-decile-0/short-decile-9 spread, sized at ₹5cr (the capital level both Delivery and the
liquidity tilt independently point to), backtested on the same 53 weeks with the real cost model.
Reported for completeness per this lab's charter (statistical + economic + robustness, always), but
**the same 41%-power caveat applies to any Sharpe computed on 53 weeks** — this is a descriptive
readout, not a validation, and is not gated as pass/fail.

## 8. Exclusions

- Does not re-test the institutional-ownership mechanism (blocked, MICRO-002).
- Does not treat this window's result as informative about Delivery, which was tested separately and
  is gated by its own, unrelated 59-year data requirement (G8-09).
- Does not extend, shorten, or otherwise adjust the 53-week window based on what makes the result look
  better — the window is exactly the untouched calendar range as of this session's freeze date.
