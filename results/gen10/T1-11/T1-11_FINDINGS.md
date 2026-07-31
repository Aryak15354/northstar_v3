# T1-11 — Tier Comparison on Common Dates. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen8/G8-07 (the lead), G8-11 (the correction being checked),
              results/gen10/T1-08 (which raised the doubt)
Artifacts:    t1_11_data.json. Script: scripts/gen10/t1_11_tier_common_dates.py
```

**Outcome: G8-11's correction of G8-07 does not survive a common-date comparison, and the ordering
reverses.** The underlying liquidity story is not damaged — if anything it is strengthened — but it
**relocates** from the F&O boundary to the micro-cap tier, which is where G8-07 originally put it
before G8-11 moved it.

---

## 1. The defect

`g8_07_capital_scale_sweep.backtest` computes `r = s_net[pre].dropna()` per config × tier and reports
that tier's Sharpe. Each tier is therefore measured on whatever dates it happened to have a book. From
G8-07's own output:

| universe | n_weeks | mean Sharpe |
|---|---|---|
| ALL | 1,070 | 0.717 |
| FNO_LARGE | 1,070 | 0.565 |
| SMALL_ADV_Q1 | 1,070 | 0.939 |
| **NON_FNO_TAIL** | **712** | **1.014** |

**SMALL_ADV_Q1's +0.222 lead is like-for-like. NON_FNO_TAIL's +0.296 lead is not** — it compares 712
weeks against 1,070.

## 2. Why that matters here specifically

The NON_FNO_TAIL book only exists from **2010-01-15** — before then the panel's cross-section is too
thin for a non-F&O tail to clear a 30-name floor. The weeks it excludes are almost entirely 2005–2013,
and they are **systematically worse**:

| ALL tier measured on… | Sharpe | annual return |
|---|---|---|
| the common weeks (2010+) | **+1.0057** | +20.95% |
| the excluded weeks (mostly 2005–13) | **+0.5788** | +15.20% |

Any tier measured only on the post-2010 window receives a **free ~+0.43 Sharpe** relative to ALL
measured across everything. That is the entire mechanism.

## 3. The leads, corrected

| tier | native Sharpe | common Sharpe | lead (native) | **lead (common)** | t | |
|---|---|---|---|---|---|---|
| FNO_LARGE | 0.6976 | 0.8028 | −0.1093 | **−0.2029** | −3.22 | significant |
| **NON_FNO_TAIL** | 1.2129 | 1.2129 | +0.4060 | **+0.2072** | +2.25 | **FRAGILE** — bootstrap CI [−0.008, +0.441] includes zero |
| **SMALL_ADV_Q1** | 0.9537 | 1.5020 | +0.1468 | **+0.4963** | +3.51 | significant, CI [+0.186, +0.836] |

**The ordering reverses.** On its native date set NON_FNO_TAIL looks like the strongest tier; on a
common date set SMALL_ADV_Q1 leads it more than two to one, and NON_FNO_TAIL's lead is fragile.

This reproduces T1-08's result by a different construction (four-factor momentum composite here vs a
single residual-momentum book there), which is the most trustworthy part of it.

## 4. What this does and does not overturn

**Does not overturn — the liquidity story itself.** G9-01's gradient (Spearman(decile, IC) = −0.818,
p = 0.0038) measures IC across liquidity deciles that all exist in every week, so it is not exposed to
this defect. And the corrected result **strengthens** the direction: the smallest, least liquid tier is
now the clear leader rather than the runner-up. Smaller is still better.

**Does overturn — G8-11's specific correction.** G8-11 concluded *"CORRECTED — non-F&O tail is the real
source"* of G8-07's advantage, moving it away from the micro-cap tier, and reported *"non-F&O beats all
in 16/17 signals"*. The tier it moved the finding **to** is the one measured on a different, later,
easier window. On common dates the micro-cap tier leads.

**Practical consequence.** The F&O boundary was being treated as the meaningful discontinuity — a
discrete, institutional, shortability-driven story. The corrected picture is a **continuous size /
liquidity gradient**, with the extreme of the gradient carrying the edge. That is a different
mechanism, and it points at different implementation constraints: ADV-driven capacity limits rather
than F&O eligibility.

## 5. Findings

**G10-F32 — G8-07's NON_FNO_TAIL lead is roughly half date-coverage artifact.** +0.406 native →
+0.207 on common dates, and fragile at that. The tier's book only exists from 2010, and the excluded
2005–13 weeks score +0.58 Sharpe against the common window's +1.01.

**G10-F33 — G8-11's correction of G8-07 does not survive, and the ordering reverses.** On a common
date set SMALL_ADV_Q1 leads ALL by +0.496 (t = 3.51, bootstrap CI excludes zero) against
NON_FNO_TAIL's +0.207 (fragile). The advantage sits at the small/illiquid extreme, not at the F&O
boundary. G9-01's liquidity gradient is unaffected and is consistent with the corrected reading.

**G10-F34 — this is the fifth instance of one defect class.** Comparing statistics computed over
different observation sets: pooled stock-weeks (T0-01), pooled multi-universe cross-sections (T0-03),
tier-native date sets (T1-08, here), and mismatched estimation eras (T1-06's Sharpe-baseline trap).
Rule 5 of the inference standard exists for this, and it now covers dates as well as universes.

## 6. Threats to validity

- **This is not a re-run of G8-07.** One config (four-factor momentum composite, top-quintile
  long-only, gross) against G8-07's three configs through the full cost model. Native Sharpes
  therefore differ from G8-07's (e.g. SMALL_ADV_Q1 964 weeks here vs 1,070 there, so its native lead
  reads +0.147 rather than +0.222). **The common-date comparison is the claim**; the absolute levels
  are not.
- **A definitive fix is to re-run `g8_07_capital_scale_sweep.py` with a common-date restriction**
  across all four tiers and all three configs. That is the recommended follow-up and is mechanical.
- The common window is 645 weeks and begins in 2010, so all corrected numbers describe the post-GFC
  era. That is a restriction shared by every tier equally, which is the point, but it does mean none
  of these tiers is characterised across 2005–09.
- Costs are not modelled here. G8-07's cost model would lower all tiers, and most for the least liquid
  — which would work against SMALL_ADV_Q1, the tier this finding elevates. **The corrected ordering is
  therefore a gross-return statement and should be re-checked net of cost before it is acted on.**
