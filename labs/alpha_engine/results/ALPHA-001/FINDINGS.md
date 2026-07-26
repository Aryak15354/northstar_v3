# ALPHA-001 — Liquidity-Gradient OOS Test: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Alpha Engine
Verdict:            INCONCLUSIVE (fixed in advance by the power computation)
```

**Outcome: directionally consistent, and correctly not claimed as more than that.**

Artifacts: `alpha001_data.json`. Script: `labs/alpha_engine/protocols/run_alpha001_oos.py`.

---

## Result

On the 53-week window strictly after Gen-7's cross-asset lockbox boundary (2025-07-11 to
2026-07-10) — untouched by every prior liquidity-gradient analysis this session —
`res_mom_52w_ex4w`'s cross-sectional IC:

| | mean IC | NW-t |
|---|---|---|
| Decile 0 (least liquid) | **+0.03006** | +1.19 |
| Decile 9 (most liquid) | +0.02595 | +1.23 |

**Direction matches G9-01** (decile 0 > decile 9). A descriptive long-low-liquidity/short-high-
liquidity spread at ₹5cr shows mean +0.131%/week, annualized Sharpe +0.34 over the same 53 weeks.

## Why this is not reported as a validation

The contract fixed the outcome rule **before** this script ran, because the power computation
(40.9% at n=53) was done first: no result from a 53-week window can be called VALIDATED regardless
of direction. This is the same lesson Gen-7 learned the hard way — a small holdout that happens to
point the right way is not evidence, it is one noisy draw. The Sharpe readout is explicitly
descriptive, not gated, for the same reason.

**Verdict: INCONCLUSIVE.** G9-01's own finding is unaffected by this either way — it stands on its
much larger, better-powered sample (810 weeks, sign test across 17 signals, p=0.00027). This test
adds one consistent-but-underpowered data point; it neither strengthens nor weakens that result on
its own terms, and is reported as exactly that.

## What would resolve it

Roughly 135 weeks are needed for 80% power at this effect size — about 2.6 years. The honest path is
to let this window accumulate rather than force a verdict now; a future lab session revisiting this
in 2027–2028 would have a properly powered fresh test available.
