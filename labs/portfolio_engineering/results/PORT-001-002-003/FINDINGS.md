# PORT-001 / PORT-002 / PORT-003 — Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Portfolio Engineering
Verdict:            VALIDATED (all three, against the pre-registered gates — see caveats below)
```

Artifacts: `port_001_002_003_data.json`. Script:
`labs/portfolio_engineering/protocols/run_port_001_002_003.py`. Baseline: Config-4 + G-05
(Sleeve-1, 80% of the frozen book), reusing `run_final_portfolio_matrix.py`'s recertified apparatus,
2005-01-07 to 2026-07-10 (1,123 weeks). Pre-lockbox baseline reproduces the recertified numbers
(`CONFIG4_RECERTIFICATION_2026_07_26.md`) closely: CAGR +11.8%, Sharpe +0.947, maxDD −45.4%.

**Scope, restated from the contract**: all three test Sleeve-1 alone (80% of the book), not the full
two-sleeve book — Sleeve-2 (sector rotation)'s own backtest apparatus was not reused this session.

---

## Two bugs caught and fixed before these numbers were reported

**1. A one-week look-ahead leak in PORT-001 and PORT-002.** The first pass computed trailing
volatility as `base.rolling(13).std()` and drawdown as `cumsum()` evaluated directly at each
rebalance date — both windows include that date's own not-yet-realized return, so the leverage
decision for week *t* was partly informed by week *t*'s own outcome. **Fixed** by shifting both
series one period (`base.shift(1)...`) so the decision at *t* only ever sees data through *t*−1. This
mattered: PORT-001's pre-lockbox Sharpe delta fell from +0.272 (leaky) to **+0.179** (fixed); PORT-002's
maxDD improvement fell from +14.0pp to **+11.4pp**. Both survive the fix; neither would have been
caught without checking.

**2. Short-leg notional overstated 2x in PORT-003's first pass.** The initial cost calculation gave
the short leg the same full `fund_inr` notional per name as the long leg, ignoring Config-4's own
0.5x short-sizing ratio. **Fixed** by scaling the short leg's per-name notional by 0.5x, matching the
book's actual construction. Absolute cost levels fell substantially (single-shot: 1,675 → **948
bps/yr**); the qualitative conclusion (staggered execution roughly halves total cost) was unaffected.

---

## PORT-001 — Volatility-targeting overlay

| | pre-lockbox Sharpe | pre-lockbox maxDD | lockbox-context Sharpe |
|---|---|---|---|
| Baseline | +0.947 | −45.4% | −0.079 |
| **+ vol-targeting overlay** | **+1.126** | **−30.5%** | **−0.340** |

Sharpe delta **+0.179**, clears the pre-registered Gen-5 bar (+0.15). MaxDD improves by 14.9
percentage points. **Verdict per the pre-registered gate (pre-lockbox only): VALIDATED.**

**Caveat that must travel with this result.** In the lockbox-context window, the overlay makes
performance *worse* (−0.079 → −0.340), not better. The mechanism: vol-targeting delevers during
*high-volatility* stress (2008, 2020 — both crash episodes the pre-lockbox sample is dominated by,
where lower exposure genuinely helped) but **levers up during low-volatility periods regardless of
their sign** — and the lockbox window has apparently been a low-vol, negative-drift stretch, where
the overlay's leverage-up response amplified a loss rather than protecting against one. The contract
fixed lockbox as context, not a gate, specifically so this kind of post-hoc information wouldn't
change the verdict — but it is reported here in full because a future session sizing this overlay for
live capital needs to know its known failure mode, not just its historical Sharpe.

## PORT-002 — Drawdown-triggered de-gross overlay

| | pre-lockbox CAGR | Sharpe | maxDD | GFC dd | COVID dd |
|---|---|---|---|---|---|
| Baseline | +11.8% | +0.947 | −45.4% | −43.8% | −11.2% |
| **+ de-gross overlay** | +11.0% | +0.996 | **−34.0%** | **−32.1%** | −11.2% |

MaxDD improves 11.4 percentage points (concentrated entirely in the GFC window — COVID's drawdown was
too shallow/fast to trigger the −15% threshold before it recovered) for a CAGR cost of 0.8 points.
**Verdict: VALIDATED** — the trade is favorable by the pre-registered criteria (>2pp maxDD gain for
<3pp CAGR cost). This is a genuine tail-risk reduction, not merely a relabeling of PORT-001's effect:
the trigger is drawdown-based, not vol-based, and its improvement is concentrated in a different part
of history (GFC specifically) than PORT-001's broader vol-driven adjustment.

## PORT-003 — Execution-schedule refinement at ₹2,500cr

| | total cost |
|---|---|
| Single-shot execution | 948.3 bps/yr |
| **5-day staggered execution** | **528.9 bps/yr** |
| Difference | **−419.4 bps/yr** |

Staggering cuts annual cost by more than half at this capital level (281 rebalance events, 11,932
name-trades over the full history). This confirms the trade-off stated in the contract resolves in
favor of splitting: sqrt-impact reduction from smaller per-tranche notional dominates the repeated
fixed statutory costs of five separate fills, by a wide margin at ₹2,500cr. **Verdict: VALIDATED.**

**Caveat.** This model assumes each of the 5 daily tranches gets the same ADV-relative impact
function as a same-day fill — it does not model intraday adverse selection, information leakage
across a multi-day execution window, or the possibility that ADV itself reacts to a visible large
order being worked over several days. All of these would work against staggering, not for it, so
528.9 bps/yr should be read as a **best-case** estimate of the staggered scheme's cost, not a
guaranteed achievable number.

## What Alpha Engine's ALPHA-002 means for how these are used

`ALPHA-002` found Delivery and the liquidity-decile gradient substantially overlap as mechanisms. That
finding is about which *signals* to size, not about these three overlays (a leverage rule, a drawdown
rule, and an execution schedule apply identically regardless of which underlying signal generates the
long/short book) — no interaction between that finding and these three is implied or tested here.
