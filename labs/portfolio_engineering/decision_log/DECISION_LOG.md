# Portfolio Engineering Lab — Decision Log

Append-only. This lab did nothing across nine prior generations of this programme — this is its
first entry.

---

## 2026-07-26 — Experiments closed this session

- **PORT-001** (`labs/portfolio_engineering/results/PORT-001-002-003/FINDINGS.md`) — volatility-
  targeting leverage overlay on Config-4+G-05 (sizing only). A self-caught one-week look-ahead leak
  (trailing vol included the current week's own return) was found and fixed before reporting; the
  effect survived the fix at a reduced magnitude. Closed **VALIDATED** against the pre-registered
  pre-lockbox gate (Sharpe delta +0.179 vs. +0.15 bar). **Carries a real caveat**: the overlay
  underperforms in the lockbox-context window, because it levers up in any low-volatility period
  regardless of sign — read the findings doc's caveat section before sizing this for live capital.
- **PORT-002** — drawdown-triggered de-gross overlay (a sizing rule, not an options hedge — no
  sufficient historical index-options depth exists to backtest a real protective-put strategy over
  2005-2026). Same look-ahead bug, same fix. Closed **VALIDATED**: maxDD improves 11.4 points
  (concentrated in the GFC window) for a 0.8-point CAGR cost.
- **PORT-003** — execution-schedule refinement (1-day vs. 5-day staggered fills) at ₹2,500cr. A
  second self-caught bug (short leg given 2x its real notional in the first pass) was found and
  fixed. Closed **VALIDATED**: staggering roughly halves total annual cost (948 → 529 bps/yr) at this
  capital level. Carries a disclosed caveat that the cost model does not capture intraday adverse
  selection or information leakage from working a multi-day order.

## 2026-07-26 (same day) — PORT-004 closed: Sleeve-2 and combined-book extension

Closes the Sleeve-2 gap flagged in PORT-001/002/003. Same two overlay mechanisms, unchanged, applied
to two new bases. **Genuinely mixed result, four sub-tests**: vol-targeting REJECTED on both Sleeve-2
alone (+0.064 Sharpe delta, below the +0.15 bar) and the combined book (+0.135, close but still
below) — PORT-001's Sleeve-1 vol-targeting result does not generalize. Drawdown de-gross VALIDATED on
both: a marginal result on Sleeve-2 alone (+2.2pp maxDD for +1.7pp CAGR cost), and the **strongest
result in this whole overlay programme** on the combined book (+9.2pp maxDD improvement for only
+0.4pp CAGR cost, concentrated in the GFC window). Closed INCONCLUSIVE at the registry level (a
summary label for a mixed result, not a null finding) — see the findings doc for the four sub-results.

**Practical takeaway for a future capital-allocation decision**: the combined-book drawdown de-gross
overlay is the standout candidate across all of Portfolio Engineering's work this session.
Vol-targeting stays validated for Sleeve-1 alone only; it should not be assumed to extend without
further, Sleeve-2-specific calibration work (not attempted here).

## Cross-referenced finding (not owned here, not duplicated)

`ALPHA-002` (Alpha Engine, joint) found Delivery and the liquidity-decile gradient collapse into
substantially one mechanism. **Implication for this lab, stated once, here**: a future capital
allocation should not size Delivery and the liquidity tilt as independent, diversifying ₹5–10cr
sleeves — the evidence says they occupy the same ground. No sizing decision has been made on this
yet; it is recorded here so a future session doesn't re-litigate it as new information.

## Scope note carried forward

All three experiments above test Sleeve-1 (Config-4+G-05, 80% of the book) alone. Sleeve-2 (sector
rotation)'s own overlay behavior is untested — its backtest apparatus was not reused this session.
