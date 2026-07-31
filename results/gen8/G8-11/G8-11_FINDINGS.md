> ## ⚠ CORRECTION — date-coverage confound (2026-07-31, Gen-10 T1-11)
>
> **Each tier's Sharpe was measured on its own date set.** `backtest` computes
> `r = s_net[pre].dropna()` per config x tier, and the tiers do not cover the same weeks:
>
> | universe | n_weeks |
> |---|---|
> | ALL / FNO_LARGE / SMALL_ADV_Q1 | 1,070 |
> | **NON_FNO_TAIL** | **712** |
>
> The NON_FNO_TAIL book only exists from 2010 — the panel's cross-section is too thin before then for
> a non-F&O tail to clear a 30-name floor. The excluded 2005–13 weeks are systematically worse
> (ALL tier: Sharpe **+0.58** on excluded weeks vs **+1.01** on the common window), so a tier measured
> only on the later window receives a free ~+0.43 Sharpe.
>
> **SMALL_ADV_Q1's +0.222 lead is like-for-like and stands. NON_FNO_TAIL's +0.296 lead does not.**
> On a common date set the lead halves to +0.207 and becomes fragile (bootstrap CI includes zero),
> while SMALL_ADV_Q1's rises to +0.496 (t = 3.51). **The ordering reverses.**
>
> The liquidity story is not damaged — it is strengthened and **relocated**: the edge sits at the
> small/illiquid extreme of a continuous gradient, not at the discrete F&O boundary. G9-01's gradient
> (Spearman −0.818) is unaffected, since its deciles all exist every week.
>
> **Recommended fix:** re-run `g8_07_capital_scale_sweep.py` with a common-date restriction across all
> four tiers and all three configs, net of cost. Evidence: `results/gen10/T1-11/`.
>
> ### ✅ SETTLED 2026-07-31 by T1-13 (common dates x 3 configs x NET of cost)
>
> The re-run prescribed above has been done. It reproduces this document's native leads almost exactly
> (+0.299 / +0.228 / −0.153 against the published +0.296 / +0.222 / −0.153), which validates it, and
> then corrects them:
>
> | tier | published (native) | **common index, net of cost** |
> |---|---|---|
> | NON_FNO_TAIL | +0.296 | **+0.042** — ~86% was the coverage gap |
> | SMALL_ADV_Q1 | +0.222 | **+0.279** — survives, incl. the cost test meant to break it |
> | FNO_LARGE | −0.153 | −0.272 |
>
> **And a third fact:** under `config4_secbal40_short` — the certified production config — BOTH tiers
> are negative (−0.284 and −0.013). The advantage exists only in the two long-only configs. The
> F&O-only short leg cannot hedge a long book drawn from a disjoint non-F&O universe, so the tier
> effect and the short leg are structurally incompatible. "3/3 configs won" becomes 2/3, and the
> failing config is the deployed one.
>
> Evidence: `results/gen10/T1-13/`.
>
> ### This document's central claim — revised twice, final
>
> G8-11 **moved** G8-07's finding from the micro-cap tier to the non-F&O tail ("CORRECTED — non-F&O
> tail is the real source"; "non-F&O beats all in 16/17 signals") and concluded the bottom ADV quintile
> "is not an advantage at all", losing to the full universe by −0.096 on average.
>
> **This document has its own version of the index-alignment defect, distinct from G8-07's.**
> `backtest` never skips a date — it records `port = 0.0` whenever the tier is too thin to hold
> anything, gating only the rebalance on `len(gg) >= 40`. So every tier reports 1,070 weeks, which
> reads as clean coverage and is not:
>
> | tier | weeks the tier held nothing |
> |---|---|
> | ALL / FNO_LARGE | 0 / 1,070 |
> | **NON_FNO_TAIL** | **447 / 1,070 (41.8%)** |
> | SMALL_ADV_Q1 | 296 / 1,070 (27.7%) |
>
> NON_FNO_TAIL's median name count is **0.0 for every year 2005-09 and 2013** — `fno_ok` is
> `adv_rank <= 190` and the early panel has fewer than 190 names, so the non-F&O tail is **empty by
> construction**. The 16/17 sign test is computed over Sharpes in which the winning tier spent two
> fifths of the sample not trading.
>
> **Direction of the bias (stated backwards on first writing, corrected by T1-14):** zero-padding
> scales Sharpe by **√(n/(n+k))** — zeros shrink the mean linearly and the standard deviation only as
> a square root — so a filled tier is **diluted, not flattered**. Re-running this document's own
> battery with empty weeks EXCLUDED therefore *raises* both thin tiers:
>
> | tier | as published (zero-filled) | **empty weeks excluded** | sign test |
> |---|---|---|---|
> | FNO_LARGE | 0 / 17 | **0 / 17** | p = 0.00002 |
> | NON_FNO_TAIL | 16 / 17 | **15 / 17** | p = 0.00235 |
> | **SMALL_ADV_Q1** | 5 / 17 | **15 / 17** | p = 0.00235 |
>
> **This document's non-F&O finding SURVIVES its own correction almost intact (16 → 15 of 17).** What
> does not survive is the companion claim: once its 185 empty weeks stop being scored as zeros, the
> micro-cap tier goes from 5/17 to 15/17 and **ties** the tier this document elevated above it.
>
> **Final reading.** The ranking dispute between the two small tiers is unanswerable on this evidence
> and, more usefully, unimportant. What survives every correction across G8-07, G8-11, T1-11, T1-13 and
> T1-14 is the **monotone size gradient**: large caps lose 0/17, both smaller tiers win 15/17. The
> mechanism is a continuous size/ADV constraint — capital and impact cost — not a discrete
> F&O-eligibility discontinuity. That is consistent with G9-01 (Spearman −0.818, verified clean in
> T1-12), and it is long-only: the effect is absent from the certified `config4_secbal40_short` book
> (T1-13, T1-14).
>
> Evidence: `results/gen10/T1-11/`, `T1-13/`, `T1-14/`.

---

# G8-11 — Small-Capital Deep Dive: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         results/gen8/G8-07/G8-07_FINDINGS.md, results/gen8/G8-12/G8-12_FINDINGS.md,
                    results/gen8/G8-08/CONFIG4_RECERTIFICATION_2026_07_26.md (the 0.8105 benchmark)
Related Papers:     Gen-8, task C (deep dive)
```

**Outcome: the tier effect is now established at p = 0.00027 — and it is NOT what G8-07 suggested.**
The advantage belongs to the **non-F&O tail**, not to micro-caps. The bottom ADV quintile is, on
average, *worse* than the full universe. **408 backtests: 17 signals × 4 tiers × 6 capital levels.**

Artifacts: `g8_11_deep_dive.csv`, `g8_11_data.json`. Script: `scripts/gen8/g8_11_smallcap_deep_dive.py`.

---

## 1. A finding that shaped the design, established before running anything

**All 55 REJECTED entries in `results/ARP_MASTER_ALPHA_REGISTRY.csv` were rejected for cause R1 —
weak or absent information — and not one has |t| > 2.** The strongest is IC 0.021 at t = 1.21.

Capital scale can only rescue a strategy that **has** signal and loses it to cost. It cannot
manufacture signal that was never there. **Re-running those 55 across a capital ladder would have been
theatre**, so this instead tests every canonical signal the panel carries — momentum, reversal,
volatility, liquidity, skew, volume, beta — as a standalone portfolio, with directions fixed from the
research record rather than fitted.

## 2. The tier main effect — 16 of 17 signals

Mean Sharpe across capital levels, by universe tier:

| signal | ALL | FNO_LARGE | **NON_FNO** | SMALL_Q1 | **NONFNO−ALL** | SMALL−ALL |
|---|---|---|---|---|---|---|
| res_mom_52w_ex4w | +0.592 | +0.471 | **+1.064** | +0.988 | **+0.472** | +0.395 |
| high_52w_prox | +0.730 | +0.581 | **+1.063** | +0.779 | **+0.333** | +0.049 |
| sharpe_mom_26w | +0.750 | +0.605 | **+1.076** | +0.630 | **+0.325** | −0.120 |
| ret_1w | +0.137 | +0.052 | +0.454 | −0.096 | +0.318 | −0.233 |
| ret_13w | +0.609 | +0.443 | +0.903 | +0.560 | +0.293 | −0.049 |
| ret_52w_ex4w | +0.554 | +0.433 | +0.832 | +0.593 | +0.277 | +0.039 |
| ret_4w | +0.032 | −0.054 | +0.281 | +0.069 | +0.250 | +0.037 |
| consistency_mom_26w | +0.625 | +0.497 | +0.874 | +0.577 | +0.249 | −0.048 |
| ret_26w | +0.645 | +0.484 | +0.886 | +0.493 | +0.241 | −0.152 |
| idio_vol_13w | +0.479 | +0.398 | +0.719 | +0.495 | +0.240 | +0.016 |
| vol_52w | +0.726 | +0.668 | +0.946 | +0.431 | +0.221 | −0.295 |
| abnormal_volume_4w | +0.445 | +0.299 | +0.644 | +0.186 | +0.199 | −0.259 |
| skew_26w | +0.263 | +0.194 | +0.458 | +0.027 | +0.195 | −0.236 |
| vol_13w | +0.553 | +0.473 | +0.715 | +0.385 | +0.162 | −0.168 |
| beta_104w | +0.686 | +0.654 | +0.768 | +0.657 | +0.083 | −0.029 |
| max5_4w | +0.306 | +0.275 | +0.307 | +0.237 | +0.001 | −0.069 |
| amihud_13w | +0.528 | +0.275 | +0.434 | +0.025 | **−0.095** | −0.503 |

| Tier | beats ALL in | mean Δ |
|---|---|---|
| **NON_FNO_TAIL** | **16 / 17** | **+0.221** |
| SMALL_ADV_Q1 | 5 / 17 | **−0.096** |
| FNO_LARGE | **0 / 17** | −0.112 |

**Sign test on the non-F&O effect: p = 0.00027.**

## 3. The correction to G8-07

G8-07 tested 3 momentum configurations and reported both NON_FNO_TAIL (+0.296) and SMALL_ADV_Q1
(+0.222) as beating the full universe. **Across 17 signals that does not hold for micro-caps.**

- **Non-F&O tail: real, systematic, highly significant** (16/17, p = 0.00027).
- **Bottom ADV quintile: not an advantage at all** — it *loses* to the full universe on average
  (−0.096) and wins for only 5 of 17 signals.

**The effect is "outside the F&O large-cap universe", not "as small as possible."** There is an
interior optimum: past the liquid mega-caps, but not down into the micro-cap tail where costs,
truncation exposure (G8-12: 22.3% of names later truncated vs 17.2% for non-F&O) and thin
cross-sections take over.

G8-07's micro-cap number was driven by 3 correlated momentum variants; widening to 17 signals shows it
does not generalise. **This is the earlier result being corrected by more evidence, not confirmed.**

## 4. Capital rescue — real, and mechanistic

Sharpe at ₹1cr minus Sharpe at ₹500cr, best tier per signal:

| signal | rescue | | signal | rescue |
|---|---|---|---|---|
| **ret_1w** | **+0.417** | | vol_13w / idio_vol_13w | +0.221 |
| **abnormal_volume_4w** | **+0.376** | | sharpe_mom_26w | +0.175 |
| **max5_4w** | **+0.376** | | ret_26w | +0.165 |
| **ret_4w** | **+0.352** | | consistency_mom_26w | +0.142 |
| ret_13w | +0.243 | | res_mom_52w_ex4w | +0.111 |
| high_52w_prox | +0.234 | | amihud_13w | +0.049 |

**Every signal improves as capital falls, and the ordering is mechanistically coherent**: the biggest
gains go to **short-horizon, high-turnover** signals — 1-week reversal, volume surprise, lottery-demand,
4-week reversal. Those are precisely the strategies that square-root impact cost destroys at scale, so
they are precisely the ones small capital rescues. Long-horizon momentum, which trades slowly, gains
least (+0.111).

**This is the clean answer to the question asked**: the strategies that "come back" at small capital
are the fast ones, and the mechanism is turnover × impact, not a small-cap risk premium.

## 5. What does NOT survive: individual signals against the book

Five signal × tier combinations beat the certified book (0.8105) by more than Gen-5's +0.15 bar at
≤₹10cr — led by `high_52w_prox` and `sharpe_mom_26w` on the non-F&O tail at Sharpe ≈ 1.118.

**But BH correction across the 17-signal family gives 0 survivors at q < 0.05** (best q = 0.66).
SE(Sharpe) at 1,070 weeks is **0.254**, so a single strategy needs to beat the book by ~0.5 Sharpe to
certify individually, and none does.

**The two results are consistent, and the distinction matters:**
- The **tier effect** is a systematic shift measured across 16 independent signals → **highly
  significant** (p = 0.00027).
- Any **individual signal's** Sharpe is estimated with SE 0.254 on 21 years → **not significant**.

**So: "trade this signal on the non-F&O tail at ₹1–10cr" is not certified. "The non-F&O tail is a
better universe than the full panel, for essentially any signal" is.**

## 6. Findings

**G8-F27 — the non-F&O tail is a systematically better universe, at p = 0.00027.** It beats the full
panel for 16 of 17 canonical signals, mean +0.221 Sharpe, while the F&O large-cap tier loses for
17 of 17 (−0.112). This is the strongest statistical result in Gen-8 and one of the strongest in the
programme, because it rests on a sign test across largely independent signals rather than on a single
Sharpe estimate.

**G8-F28 — micro-caps are NOT the answer, correcting G8-07.** The bottom ADV quintile underperforms the
full universe on average (−0.096, 5/17). The advantage lives *outside F&O*, not at the smallest
extreme. G8-07's micro-cap figure was an artifact of testing only 3 correlated momentum variants.

**G8-F29 — capital rescue is real and its mechanism is turnover.** Every signal improves as capital
falls; the gain is largest for short-horizon high-turnover signals (ret_1w +0.417, abnormal_volume_4w
+0.376) and smallest for slow momentum (+0.111). **The programme's previously rejected fast signals
are the natural candidates for a small book** — not because they were mis-rejected, but because they
were tested at a capital scale that guaranteed cost would dominate.

**G8-F30 — no individual strategy certifies against the book, and the reason is estimation noise, not
weak performance.** SE(Sharpe) = 0.254 at 21 years means ~0.5 Sharpe of outperformance is needed for
individual significance. This is the same power wall Gen-7 and Gen-8 keep meeting, in portfolio form.

## 7. Threats to validity

- **In-sample, pre-lockbox.** No out-of-sample test. The tier hypothesis has never been tested on
  held-out data — and unlike Gen-7's spent lockbox, a fresh holdout is legitimate here.
- **Truncation exposure differs by tier** (G8-12): the non-F&O tail is the *least* exposed of the small
  tiers (2.5% of rows from later-truncated names vs 8.0% for micro-caps), which supports rather than
  undermines G8-F27 — but the bias is not zero.
- **Signal directions were fixed from the research record, not fitted.** Had they been fitted, the
  entire exercise would be circular. Two directions (`amihud_13w`, `abnormal_volume_4w`) are less
  firmly documented than the rest.
- **Long-only top-quintile portfolios**, monthly rebalance, trade bands — one construction, applied
  uniformly for comparability. A different construction could change levels, though the tier effect is
  a within-construction comparison and should be robust to it.
- **The non-F&O tail cannot absorb institutional capital** (G8-07/G8-F19: tradeable to ~₹10cr). This is
  a finding about a small book, and is not portable to the ₹100cr+ regime the frozen book targets.
