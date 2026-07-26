# MSCI-004 — Volatility-Regime Stability and Future IC: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Market Science
Verdict:            INCONCLUSIVE (underpowered; point estimate also opposite the primary hypothesis)
```

Artifacts: `msci004_data.json`. Script: `labs/market_science/protocols/run_msci_004.py`.

---

## Result

| | value |
|---|---|
| Joined series | 1,078 weeks (2005-09-30 to 2026-05-22) |
| Pearson r | **+0.069** |
| NW t / p | +0.78 / 0.438 |
| Permutation p | 0.512 |
| Power at meaningful effect (\|r\|=0.15) | 26.9% (n_eff=82, needs 347) |
| Direction vs. primary hypothesis (r<0) | **not supported** (r is positive, near zero) |

**Verdict: INCONCLUSIVE** by the pre-registered power gate — but unlike `MSCI-001`, this is not a
case of "a real-looking effect closed INCONCLUSIVE on a technicality." The point estimate itself is
small, positive (opposite the pre-registered direction), and nowhere near significant on either test.

## What this means for the MSCI-001 reversed-sign lead

`MSCI-001` found that higher trailing rank-stability of `res_mom_52w_ex4w` predicts *lower* forward
IC of that same signal — a real, if underpowered-by-formal-gate, surprise (NW p=0.002, permutation
p=0.031). This experiment tested whether the same pattern replicates using a **completely
independent construction of "stability"** — trailing stability of the market's own volatility-regime
classification (CRASH/STRESS/NORMAL_UP/STRONG_UP/RECOVERY), rather than the signal's own rank
stability.

**It does not replicate.** The regime-stability predictor shows no meaningful relationship to
`res_mom_52w_ex4w`'s forward IC in either direction. This is a useful, honest negative: it suggests
MSCI-001's finding is more likely a property specific to how `res_mom_52w_ex4w`'s own cross-sectional
ranking behaves, not a general "quiet markets carry less resolved information" phenomenon that would
show up under any reasonable operationalization of "stability." The MSCI-001 lead is not
strengthened by this test, and should not be treated as a broader regularity without further,
differently-constructed replication attempts.

## Rolling-window artifact check

The regime-stability predictor series fails the differencing screen (5/52 lags, below the ~5.7
chance threshold) but also barely exceeds its own construction null (1/52 lags, max excess ~0.000 —
essentially at the boundary of noise). Per the Gen-8 caveat, this is not a contradiction (a highly
persistent series legitimately fails differencing), but combined with the near-zero excess over the
construction null, there is little evidence this predictor series carries information beyond what a
52-week rolling window of similarly-persistent regime labels would produce mechanically.

## What would resolve this

As with MSCI-001/002/003, roughly 347 non-overlapping quarters are needed for adequate power at this
effect size — far beyond available history. Given the point estimate itself is weak and wrong-signed
here, further data accrual is a lower priority than for MSCI-001's own (stronger, correctly-signed)
result.
