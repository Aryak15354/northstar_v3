# E6/E7 — The IV Surface Through the Gate. Findings

```
Version:   v1.0
Status:    Frozen — 0/7 features promote
Freeze:    2026-07-31
Charter:   GEN11_ALPHA_DISCOVERY_CHARTER.md (gates A0-A7)
Data:      data/processed/iv_surface_weekly.parquet, joined to PANEL-A
           94,688 stock-weeks | 797 weeks (2010-12 .. 2026-07) | 308 names
```

**Outcome: the first genuinely new data source this programme has added produces no
capturable cross-sectional signal. Both A1 survivors die out of sample.** The screen's value
is confirmed again — it flagged 3 of 7 as coin flips before any effort was spent on them.

---

## 1. The screen (E6)

Per-date coefficient on the feature, controlling for momentum; `share_positive` is the
fraction of weeks that coefficient is positive. Reference points: **delivery 62.2%** and
**momentum 60.5%** (both real), **futures OI 50.0%** (dead).

| feature | weeks | share+ | NW t | verdict |
|---|---|---|---|---|
| `pcr_oi` | 716 | **56.4%** | +3.06 | CAPTURABLE |
| `iv_atm` | 716 | 47.5% | −2.15 | borderline |
| `vrp` | 716 | 46.6% | −1.45 | borderline |
| `iv_rank_52w` | 685 | 46.6% | +1.00 | borderline |
| `iv_skew_25d` | 688 | 52.0% | +1.60 | coin flip |
| `iv_term_slope` | 518 | 48.1% | −0.33 | coin flip |
| `oi_concentration` | 716 | 48.5% | −0.63 | coin flip |

**The two features with the strongest external priors — the variance risk premium and 25-delta
skew — are the ones that fail hardest.** VRP sits at 46.6% and skew at 52.0%, both effectively
coin flips. Whatever makes them work in US equity research does not survive in this
cross-section.

## 2. Gate A1 and A3

| feature | raw IC | raw t | resid IC (over momentum) | resid t | BY at m=7 |
|---|---|---|---|---|---|
| `iv_atm` | −0.0258 | −3.07 | **−0.0237** | **−3.18** | clean |
| `pcr_oi` | +0.0175 | +4.18 | **+0.0151** | **+3.76** | clean |
| `vrp` | −0.0138 | −2.65 | −0.0116 | −2.33 | not clean |
| `iv_rank_52w` | −0.0047 | −0.96 | −0.0041 | −0.86 | not clean |

Two survivors, both with bootstrap CIs excluding zero and neither flagged fragile.

## 3. A2 — and both die

Windows fixed before running: DISCOVERY ≤ 2019-12-31 (474 weeks), OOS → 2025-07-11
(289 weeks), LOCKBOX after (34 weeks, too short to test).

| feature | DISCOVERY t | **OOS t** | verdict |
|---|---|---|---|
| `iv_atm` | −3.02 | **−1.03** | **KILL** |
| `pcr_oi` | +3.09 | **+1.36** | **KILL** |

No sign flips — the direction holds. The magnitude does not. On 289 out-of-sample weeks
neither reaches |t| = 2.

## 4. A4 — run anyway, and it says something worth keeping

A2 already decided the verdict, but the rediscovery gate was completed because each survivor
had a specific named suspect.

**`iv_atm` is NOT the low-volatility anomaly in disguise.** That was the obvious hypothesis —
implied and realised vol correlate at **0.600**, and "low vol → higher returns" is A05/A06
territory. It survives the control:

```
momentum only                    t = -3.18
+ realised vol                   t = -3.25   (102% of t retained)
+ realised vol + vol_52w         t = -3.03   ( 95%)
+ realised vol + vol_52w + beta  t = -2.37   ( 75%)
```

Implied vol carries information that realised vol, 52-week vol and beta jointly do not. That
is a real and slightly surprising result — it just is not stable enough out of sample to trade.

**`pcr_oi` is partly, but not wholly, a rediscovery.** It retains 62–67% of its t after
delivery and futures OI are removed (t = +3.76 → +2.33). G8-05 found index-level PCR at
IC +0.0093, "real but below the materiality bar"; this per-stock version behaves the same way —
real, small, and not out-of-sample robust.

## 5. Findings

**G11-F06 — the options IV surface carries no capturable cross-sectional signal beyond
momentum.** 0 of 7 declared features promote. Two clear A1 and A3 with |t| > 3 in discovery;
both fall below |t| = 2 out of sample across 289 weeks.

**G11-F07 — the two features with the strongest external priors fail hardest.** The variance
risk premium (46.6% share-positive) and 25-delta skew (52.0%) are coin flips on this
cross-section. A prior imported from another market is not evidence about this one.

**G11-F08 — implied volatility is not a restatement of realised volatility.** `iv_atm` retains
75–102% of its momentum-orthogonalised t after realised vol, 52-week vol and beta are stripped
(corr(IV, RV) = 0.600). The information is distinct; it is simply not stable.

**G11-F09 — the screen paid for itself a second time.** It flagged skew, term slope and OI
concentration as coin flips before any construction effort, and correctly ranked `pcr_oi`
highest of the seven — which was indeed the one that went furthest through the gate.

## 6. What this does not claim

- **Only the linear cross-sectional use is tested.** IV surfaces are used elsewhere for
  event timing (around earnings), for options overlays, and for position sizing. None of that
  is tested here and none is refuted.
- **The dataset stands regardless.** 112,706 rows over 16.5 years is a real asset; this
  experiment tested one use of it.
- **The lockbox (34 weeks) was too short to test** and is untouched.
