# PORT-001 / PORT-002 / PORT-003 — First Portfolio Engineering Workstreams on the Frozen Book

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                portfolio_engineering
Depends On:         results/FROZEN_SPEC.md (the book this overlays), results/gen8/G8-08/
                    CONFIG4_RECERTIFICATION_2026_07_26.md (Sharpe 0.8471, maxDD -47.76%),
                    results/gen8/G8-09/g8_09_capital_ladder.csv (the slippage-share curve)
```

**Portfolio Engineering has done nothing across nine generations of this programme.** These three are
its first real workstreams: sizing/hedge/execution rules layered on top of the already-frozen,
already-validated Config-4 + G-05 signal — **never a new predictive signal**, per this lab's absolute
charter prohibition (`labs/portfolio_engineering/charter/CHARTER.md`).

## Scope decision, disclosed up front

All three overlays are tested against **Sleeve-1 (Config-4 + G-05) alone — 80% of the frozen book's
capital** — reusing `run_final_portfolio_matrix.py`'s own recertified backtest apparatus
(`long_secbal`, `short_q1`, `build_regimes`, ratio 0.5, exactly the configuration
`CONFIG4_RECERTIFICATION_2026_07_26.md` re-verified). Sleeve-2 (sector rotation, 20%) is not
replicated here: its own charter framing is "drawdown reduction more than return" (`FROZEN_SPEC.md`),
its backtest apparatus was not reused this session, and re-deriving it would be a second, separate
undertaking. This is a real scope limitation, stated honestly rather than silently treating Sleeve-1
results as if they were book-level.

## Why the full 2005–2026 window is used, not a fresh holdout

None of these three overlays discovers or claims a new return-predicting relationship — each is a
mechanical, pre-specified transformation of an *already-frozen* signal's realized return stream
(trailing realized volatility, trailing drawdown, execution scheduling of already-decided trades).
There is no OOS protection to spend here in the sense the lockbox exists for, because nothing about
future returns is being fitted — the same logic already used for `MICRO-001`'s modeled exit-fill
drag. All three are evaluated pre-lockbox and lockbox-inclusive, both reported separately.

---

## PORT-001 — Volatility-targeting overlay (sizing only)

**Rule.** At each of the signal's own monthly rebalance dates, compute trailing 13-week annualized
realized volatility of the Config-4+G-05 net weekly return series, `vol_trail(t)`. Set leverage
`L(t) = target_vol / vol_trail(t)`, clipped to `[0.5x, 1.5x]` (bounds fixed in this contract, not
tuned after seeing results). `target_vol` is the realized annualized vol of the **pre-lockbox**
baseline series, computed once, held fixed. Leverage is held constant between rebalances, matching the
signal's own cadence — no new trading frequency is introduced.

**Cost treatment.** Each leverage change at a rebalance date incurs an approximate incremental cost of
`|L(t) - L(t-1)| x 3bps` of gross notional (a conservative, disclosed approximation for the
additional financing/rebalancing turnover a leverage change requires — not a full notional-level
reconstruction, since the overlay changes aggregate exposure rather than the underlying name list).

**Gate.** Economic improvement bar: Sharpe delta >= +0.15 (Gen-5's own economic bar, used consistently
across this programme), evaluated pre-lockbox; lockbox reported as context only, not for selection.

## PORT-002 — Drawdown-triggered de-gross overlay (a tail-risk sizing rule, not an options hedge)

**Why not a literal options hedge.** A real protective-put backtest would need two decades of
historical NIFTY/stock index-options pricing; the options data on disk (`data/options/`) is recent
(2025-2026 live/complete chains), not a multi-decade series. Rather than simulate around that gap,
this is built as the honest, currently-buildable substitute: a systematic **net-exposure reduction**
triggered by realized drawdown — a sizing rule, squarely within this lab's charter.

**Rule.** At each monthly rebalance date, compute running-peak drawdown of the cumulative baseline
return series through that date. If drawdown <= -15% (roughly one-third of the documented -47.76%
historical maxDD — chosen to intervene before a stress period fully develops, fixed before running),
apply a 0.5x de-gross multiplier until drawdown recovers to >= -5% (hysteresis band, fixed in advance
to avoid whipsaw), then restore to 1.0x.

**Cost treatment.** Same incremental-cost approximation as PORT-001, applied to the de-gross/re-gross
transitions.

**Gate.** Primary metric is maxDD reduction (GFC 2008 and COVID 2020 windows specifically, per
`run_final_portfolio_matrix.py`'s own `metrics()` convention), reported alongside the CAGR/Sharpe cost
of holding the hedge — this overlay is expected to cost some return in exchange for a shallower tail,
and is judged on whether that trade is favorable, not on Sharpe improvement alone.

## PORT-003 — Execution-schedule refinement at scale (given the 58.5%→84.1% slippage-cost curve)

**Rule.** At ₹2,500cr (the upper end of `G8-09`'s documented capital ladder, where slippage dominates
total cost), compare two execution schemes for every monthly rebalance's traded names, using the real
`IndianEquityCostModel`: **(a) single-shot** — full per-name notional executed in one fill; **(b)
5-day staggered** — each name's notional split into 5 equal tranches, each incurring its own full
statutory cost (brokerage/STT/stamp/GST) plus slippage at 1/5th the notional. This is a genuine
trade-off, not a free lunch: splitting lowers sqrt-impact per tranche but repeats fixed per-trade
costs five times over — the pre-registered question is which effect dominates at this capital level,
reusing the exact traded-name/ADV history from the Config-4+G-05 backtest (not synthetic).

**Gate.** Total cost (statutory + slippage) under scheme (b) vs (a), reported as an annualized bps
difference, plus the recomputed slippage-share-of-total-cost at ₹2,500cr under both schemes.

## Exclusions (all three)

- No change to the underlying signal, universe, or rebalance cadence — `FROZEN_SPEC.md`'s own
  binding language ("No discretionary overrides. No parameter tuning.") applies to everything these
  overlays sit on top of.
- Sleeve-2 (sector rotation) is out of scope for this contract (see scope decision above).
- PORT-002 is evaluated as a sizing rule; no options-pricing claim is made anywhere in this document.
