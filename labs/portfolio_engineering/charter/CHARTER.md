# CHARTER — Portfolio Engineering Lab (Programme D)

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         docs/FIELD_REPORT_2026_07_26.md, NORTHSTAR_HANDBOOK.md (the frozen book this lab
                    works on), results/gen8/G8-08/CONFIG4_RECERTIFICATION_2026_07_26.md (the
                    corrected benchmark: Sharpe 0.8471, maxDD -46.3%)
Related Registries: research_os/MASTER_EXPERIMENT_REGISTRY.csv (PORT-NNN)
```

## Objective

**Extract more from signals this programme has already validated — never discover new ones.** This
lab has done no work across nine prior generations, and the field report is explicit that this is a
real gap: "most quant firms spend more effort here than factor discovery." Sizing, risk overlay, and
execution-schedule questions on the *existing* frozen momentum + sector-rotation book, and on any
signal Alpha Engine or Microstructure has already validated and handed off — never a candidate signal
of this lab's own invention.

## Scope

Dynamic leverage / volatility targeting, tail-hedge overlay design, execution-schedule refinement,
capital allocation across already-validated sleeves, drawdown-control mechanisms. All work operates on
the frozen book's **existing** signal set (Config-4's four momentum sub-signals, the sector-rotation
signal, and — pending Section 2b's joint test — Delivery and/or the liquidity gradient once handed off
as validated inputs). This lab never runs a discovery pipeline of its own.

## What this lab is explicitly NOT allowed to do

- **Introduce a new predictive signal under the guise of an allocation rule.** A volatility-targeting
  overlay that conditions sizing on a *new* engineered state variable this lab invented is not sizing
  — it is an undisclosed discovery pipeline, and it is exactly the mistake Gen-5 spent an entire
  generation testing and rejecting (three state-dependent timing levers, all TERMINATED_BY_GATE after
  passing their descriptive stage and failing the economic gate). Any state variable this lab
  conditions on must already be validated by Alpha Engine, Market Science, or a prior generation — cite
  the validating document in the pre-registration, or the workstream does not proceed.
- **Re-litigate Gen-5's three terminated timing levers** (short-budget timing, gross-exposure timing,
  sector-sleeve reallocation) without new, specific evidence per the burden-of-proof principle
  (`NORTHSTAR_HANDBOOK.md` §8's own explicit operating procedure for this exact situation). A
  volatility-targeting overlay is not automatically the same as Gen-5's gross-exposure timing lever —
  but the pre-registration must state explicitly why it differs (state, action, or horizon), not
  merely re-implement the same idea with a new name.
- **Claim a sizing/hedging improvement without simulating it against the same realistic cost model and
  the same pre-lockbox/lockbox discipline as the rest of this programme.** `src/pnl/
  indian_cost_model.IndianEquityCostModel` is the only cost model to use; a flat-bps proxy is a
  first-pass sanity check only, never a final claim, per the Handbook's own standing rule.
- **Touch the frozen book's signal definition, universe rules, or rebalance cadence.** Per
  `results/FROZEN_SPEC.md`: "No discretionary overrides. No parameter tuning." This lab may propose an
  *overlay* (a layer on top) — it may not modify the frozen specification itself. Any parameter change
  to the frozen spec requires full re-certification with a fresh lockbox, which is outside this lab's
  charter to authorize alone.

## Validation standard

**Simulation / stress-test standard.**

1. Backtest the overlay against the corrected, re-certified benchmark (Sharpe 0.8471, maxDD −46.3%,
   `results/gen8/G8-08/`) — never against the superseded, survivorship-inflated 0.9235.
2. Real per-trade cost model at the capital level actually being claimed, participation vs. ADV capped
   at 5% per the existing Sleeve-1 convention.
3. Stress-test across at least the documented historical drawdown episodes (GFC, COVID, and the
   book's own pre-lockbox −46.3% maxDD window) — an overlay that only helps in the average case and
   not in the specific episodes it is meant to protect against has not demonstrated its purpose.
4. Report the overlay's own capacity/cost profile if it changes turnover — an overlay that improves
   risk-adjusted return at ₹100cr but degrades capacity at ₹5,000cr must say so.

## Inherited governance (binding, not optional)

Same five items as every lab (pre-registration, power disclosure, rolling-window check with the
Gen-8 caveat, never-silently-rewrite-history, honest negative/inconclusive reporting) — shared text
in `labs/alpha_engine/charter/CHARTER.md`.

## Experiment ID convention

`PORT-NNN`, assigned once, in order, by `research_os/experiment_registry.py`.
