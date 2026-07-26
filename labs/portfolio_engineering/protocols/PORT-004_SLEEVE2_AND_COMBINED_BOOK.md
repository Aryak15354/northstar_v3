# PORT-004 — Vol-Targeting and Drawdown De-Gross Overlays, Extended to Sleeve-2 and the Combined Book

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                portfolio_engineering
Depends On:         labs/portfolio_engineering/results/PORT-001-002-003/FINDINGS.md (the same two
                    overlay mechanisms, validated on Sleeve-1 alone), results/FROZEN_SPEC.md
                    (Sleeve-2's exact construction: 13w lookback, top-2/bottom-2, monthly rebalance)
```

## Why this is a fresh experiment, not a re-fit

`PORT-001` and `PORT-002` validated vol-targeting and drawdown de-gross overlays against Sleeve-1
(Config-4+G-05) alone — 80% of the book — and explicitly disclosed Sleeve-2 as out of scope, since
its own backtest apparatus hadn't been reused that session. This experiment closes exactly that gap,
using the **same two overlay mechanisms, unchanged**, applied to two bases never tested before:
Sleeve-2 alone, and the full 80/20 combined book. No new overlay logic is introduced.

## Pre-registered specification

**Sleeve-2 construction**: reused verbatim from `scripts/kaggle/plan_2026_05_18_production/
run_sector_cert_signal.py`'s own `rot(piv, lookback=13, k=2, rebal=4)` — the exact parameters
`FROZEN_SPEC.md` documents (13-week lookback, top-2 long/bottom-2 short by sector momentum, monthly
rebalance). Not re-tuned.

**Combined book**: `0.8 * Sleeve-1 + 0.2 * Sleeve-2` weekly returns, aligned on date intersection —
`FROZEN_SPEC.md`'s own documented allocation, unchanged.

**Overlays, both unchanged from PORT-001/PORT-002**:
1. Vol-targeting: `L(t) = target_vol / trailing_13w_vol(t)`, clipped `[0.5x, 1.5x]`, `target_vol` =
   pre-lockbox realized vol of the base series being overlaid (Sleeve-2 alone, or the combined book —
   each gets its own target, not Sleeve-1's), reset only at each base's own monthly rebalance dates,
   PIT-safe (trailing window strictly through *t*-1, the exact leakage fix already applied in
   PORT-001/002).
2. Drawdown de-gross: trigger at -15% running-peak drawdown, de-gross to 0.5x, restore at -5%,
   identical thresholds to PORT-002, fixed before running.

**Gates, identical to PORT-001/002**: vol-targeting passes if pre-lockbox Sharpe delta >= +0.15
(Gen-5 bar); de-gross passes if maxDD improves >2pp for <3pp CAGR cost. Applied independently to each
of the two new bases (Sleeve-2 alone, combined book) — four sub-results in total, each closed on its
own terms, not averaged together.

## Why the full window, not a fresh holdout

Same reasoning as PORT-001/002: these are mechanical sizing transformations of an already-frozen
signal's realized returns, not a new predictive claim, so no OOS protection is being spent.
Pre-lockbox is the gate, per the same convention; lockbox is reported as context only.

## Exclusions

- No change to Sleeve-2's own signal, universe, or rebalance cadence.
- Does not re-litigate Sleeve-1's own PORT-001/002 results, which stand independently.
- Does not test a THIRD overlay (execution-schedule refinement, PORT-003) on these bases — that
  overlay is about trade notional at scale, not applicable to a description-level analysis here
  without rebuilding Sleeve-2's own per-name trade list, which is out of scope for this contract.
