# MICRO-001 — Realistic Exit-Fill Model for the Liquidity-Gradient Tilt

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                microstructure
Depends On:         results/gen8/G8-12/G8-12_FINDINGS.md (the bound this tightens),
                    results/gen8/G8-11/G8-11_FINDINGS.md (the tier effect this bounds),
                    src/pnl/indian_cost_model.py, data/processed/delisted_prices_merged.parquet
```

## 1. Applicability check

G8-12 established a crude bound: a name falling out of the panel's universe (close < ₹20 or 13-week
ADV < ₹1cr) is dropped at its last in-universe price with zero modeled exit cost, and the true
unrecorded decline in the following window (median −93.9%, median 220 weeks) is *not* charged against
the strategy at all. G8-12 stated the honest range is 0 to −2.29%/yr differential drag on the small-
liquidity tier "depending on whether exits fill cleanly" — a bound, not a model. **This experiment
builds the model.** Checked directly: 102 delisted tickers have a documented gap between their last
panel-qualifying date and their last date in the merged source with usable (non-quarantined) daily
price/volume data — a median tail of 580 daily observations, more than enough to simulate a realistic
multi-day unwind.

## 2. Research question

When a name breaches the universe threshold (price or ADV), what is the realistic execution price a
strategy achieves unwinding its position over the following days — using the real, historically-
observed volume path — compared with the panel's implicit assumption of a costless exit at the last
in-universe close?

## 3. Hypotheses

- **H-MICRO-001-1.** The realistic unwind price is worse than the clean-fill assumption (the breach
  is a liquidity/price event by construction, so the following days' volume is already thin and the
  price already declining).
- **H-MICRO-001-2.** The drag is concentrated in the small-liquidity tiers (SMALL_ADV_Q1, NON_FNO_TAIL)
  identified in G8-07/G8-11 as carrying the most exposure to later-truncated names (8.0% and 2.5% of
  rows respectively, vs 4.5% for ALL).

## 4. Pre-registered specification

**One unwind rule, chosen before looking at any result:** on breach, liquidate the position over the
following trading days at a **5% daily-participation cap against that day's actual traded value** —
the identical convention already documented as Sleeve-1's binding execution rule
(`NORTHSTAR_HANDBOOK.md` §5: "cap at 5% of ADV per trade"). Not tuned; inherited from the existing
frozen book's own rule, so this experiment cannot be accused of picking a cap that flatters the
result.

**Execution price per day sold:** that day's actual historical close, minus slippage computed by the
real cost model (`IndianEquityCostModel.cost_breakdown("SELL", notional, adv_inr=...)`) at that day's
actual participation — i.e., the same cost model every other lab uses, applied to the *degraded*
post-breach liquidity, not the pre-breach ADV.

**Clean-fill comparator:** 100% of the position sold at the breach-day close, zero slippage — exactly
what the current panel-based backtests implicitly assume when a name simply disappears from next
week's universe.

**Horizon:** unwind over a maximum of 20 trading days; if the position cannot be fully liquidated
within 20 days at the 5% cap, the remainder is marked at the day-20 close with an additional
liquidity-discount penalty (stated explicitly, not hidden) rather than assumed to vanish.

## 5. Power disclosure

n = 102 breach events (all usable, non-quarantined tickers with a documented post-breach tail).
This is a **population, not a sample** — every currently-identifiable breach event in the merged
delisted-price source is included, so there is no separate discovery-vs-holdout split for this
specific descriptive question. Power is instead reported as the bootstrap confidence interval width
on the mean per-event drag across 102 events (`research_os.power_precheck.simulation_power`-style
resampling, 2,000 bootstrap draws) — if that interval is wide relative to the point estimate, the
result is reported as a wide-CI point estimate, not a false-precision single number.

## 6. Promotion / rejection gates

| Gate | Threshold |
|---|---|
| **Direction** | Mean realistic-unwind drag must be negative (worse than clean fill) for H-MICRO-001-1 to be supported |
| **Materiality** | A drag exceeding 0.5%/yr differential is considered material to the G8-07/11 tier finding; below that, report as "real but immaterial to the existing lead" |
| **Tier concentration** | H-MICRO-001-2 supported if SMALL_ADV_Q1's modeled drag exceeds ALL's by more than the G8-12 crude bound's own −2.29%/yr, i.e. the model must at minimum reproduce G8-12's directional finding, not merely assert a number |

## 7. Exclusions

- Does not model the 217 names in the merged source that never enter the panel's universe at all
  (delisted too early / too illiquid ever to qualify) — those never contribute a portfolio drag
  because no strategy following the universe rules would ever have held them.
- Does not model bid-ask spread directly (no quote data exists in this repository for these names);
  slippage is entirely the real cost model's √-impact term, which is a documented approximation, not
  a market-microstructure-order-book simulation.
- Does not re-open the 56 quarantined tickers (unresolved price discontinuities) — using them would
  risk modeling a data artifact as an execution cost.

## 8. Anticipated failure modes

1. **Thin post-breach volume makes the 5%-cap unwind take the full 20 days or longer** for the most
   illiquid names — handled explicitly via the day-20 liquidity-discount penalty (§4), not silently
   truncated.
2. **A small number of extreme events dominating the mean** — reported alongside the median and the
   bootstrap CI, not the mean alone.
3. **Corporate-action noise in the tail** (the same discontinuities `build_delisted_panel_merged.py`
   already flags) — mitigated by excluding quarantined tickers (§7); any residual large jump is
   flagged in the findings, not silently averaged in.

## 9. Outcome classification

- If the modeled drag is negative, material (>0.5%/yr), and concentrated in the small-liquidity
  tiers as G8-12 anticipated: **VALIDATED** — the crude bound is replaced with a real point estimate.
- If the modeled drag is negative but immaterial, or the CI is too wide to distinguish from zero:
  **INCONCLUSIVE** — states the CI and what further data/horizon would tighten it.
- If the sign is wrong (realistic unwind *better* than clean fill) or a modeling defect is found
  mid-run: **METHODOLOGICAL_FAILURE**, disclosed with the false start, per every lab's inherited
  honesty requirement.
