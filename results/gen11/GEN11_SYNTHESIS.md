# Gen-11 — Alpha Discovery: Synthesis

```
Version:    v1.0
Status:     CLOSED — five experiments, zero surviving candidates, one reusable method
Freeze:     2026-07-31
Owner:      Aryak
Charter:    GEN11_ALPHA_DISCOVERY_CHARTER.md
Mandate:    find deployable alpha OTHER THAN MOMENTUM
```

**Outcome: no new alpha. But Gen-11 produced the cheap pre-test this programme has been
missing for ten generations, and it validates itself against the two signals already known
to be real.**

---

## 1. What was run

| id | question | outcome |
|---|---|---|
| **E1** | Does any feature family raise the joint ceiling above the price basis? | **microstructure +0.0340**, liquidity_exposure +0.0137, rest ≈0 or negative |
| **E2** | Is that ceiling a rediscovery of deployed delivery? | **No — futures OI adds +0.0121 over delivery.** Market-level control returns exactly +0.0000 |
| **E3** | Do OI constructions survive the adversarial gate? | **0/5 die at A1.** Best resid t = +1.30 |
| **E4** | Why did a real ceiling produce no realizable signal? | **Sign instability.** Built a screen from it |
| **E5** | Do the screen's non-momentum survivors gate? | **0/3.** Their effect is pre-2020 and has decayed |

## 2. The finding that matters: a positive ceiling is nowhere near sufficient

E2 measured a genuine +0.0266 incremental ceiling for futures OI, and the method was validated
in the same run — **date-constant market-level columns returned exactly +0.0000**, as they must.
Yet E3's five pre-registered OI constructions all died at the first gate.

The diagnostic resolves it. Per-date OI coefficient, controlling for momentum, 856 weeks:

```
mean +0.000142     t = 1.17        not significant
share positive          51.1%      a coin flip
|mean| / std            0.037      27x more noise than signal
lag-1 autocorrelation  -0.082      no week-to-week persistence
weekly refit buys       20.8x      the fixed-rule coefficient
```

**The oracle earns its ceiling by refitting a sign-unstable coefficient every week, with
foresight. A deployable rule must commit to one sign, and that sign is right 51% of the time.**

This sharpens Gen-10's closing statement from a claim into a mechanism. "The binding constraint
is estimation, not information" is now measurable per feature: it is the **sign stability** of
the per-date relationship.

## 3. The deliverable: a sign-stability screen

If realizability is sign stability, that is far cheaper to measure than a ceiling and should be
run *before* constructing candidates. E4 does it: per date, regress forward return on
[momentum, feature]; record the share of weeks the feature's coefficient is positive.

**It validates against known ground truth** — which is why it is worth keeping:

| feature | share positive | t | known status |
|---|---|---|---|
| `delivery_pct_z52` | **62.2%** | +4.75 | **the one validated non-momentum signal** — ranks #1 of 25 |
| `delivery_pct_4w_avg` | 61.8% | +3.37 | same family |
| `mom_60d_cs_z` | **60.5%** | +5.65 | **momentum, the certified edge** — positive control |
| `fut_oi_chg_4w_pct` | **50.0%** | +2.07 | rejected by G2-E02, and by E3 |
| `stock_x_crude` | 49.1% | −0.06 | cross-asset, closed by T1-10 |
| `eps_sue_cs_z` | 52.1% | +0.74 | rejected by A10/E01/E02 and six other framings |

The screen ranks **delivery first and momentum third out of 25 features**, and puts futures OI
at a literal coin flip. It recovers this programme's ten-generation ground truth from one cheap
statistic. **Cost: minutes. It would have made E3 unnecessary.**

## 4. Why the three survivors died — and the correction inside it

E4 surfaced three CAPTURABLE features that are neither momentum nor delivery, two of which
Gen-1 had rejected raw (`screener_roce` IC −0.0182, `operating_margin` IC −0.0072):

| candidate | full-history t | OOS t | **on the 2020+ window** |
|---|---|---|---|
| `macro_linkage_score` | +12.26 | +3.62 | **+2.02** |
| `operating_margin_cs_z` | +6.46 | +2.05 | **+0.86** |
| `screener_roce_cs_z` | +7.05 | +2.08 | **+0.42** |

All three survived A2 and A3 (BY-clean at the honest m = 25, since they were *chosen* from a
25-feature screen). All three died at A4.

**But the first A4 run attributed the kill to the wrong cause.** It removed delivery on the
320-week overlap window and reported the collapse as a delivery rediscovery. Re-checking on the
same window *without* removing delivery shows the effect is already gone (+2.02 / +0.86 / +0.42
vs +1.56 / +0.42 / +0.20). **The window is doing the killing, not delivery** — the same
index-alignment error class Gen-10 corrected five times, appearing a sixth.

The corrected reading is more interesting than the original: **these are real historical effects
that have decayed.** Quality and margin signals, conditional on momentum, worked strongly before
2019 and are near-zero since. That independently reproduces Gen-1's A08 verdict — *"REJECT
(regime): wrong sign in the 2019-2025 growth regime"* — from a completely different method.
**Gen-1 was right, and the screen picked up the pre-2019 era by averaging over full history.**

## 5. Findings

**G11-F01 — a positive incremental ceiling is necessary but nowhere near sufficient.** Futures
OI raises the attainable ceiling by +0.0266 and yields nothing realizable, because its per-date
coefficient is positive 51.1% of weeks with no persistence (lag-1 −0.08). The oracle's advantage
over a fixed rule is 20.8×, and it is entirely foresight.

**G11-F02 — realizability is sign stability, and it is cheap to measure.** The screen ranks
delivery #1 and momentum #3 of 25 features, and futures OI at a coin flip. It recovers the
programme's known ground truth from one statistic in minutes.

**G11-F03 — futures open interest carries no capturable cross-sectional information.** Five
pre-registered constructions, all dead at gate A1 (best resid t = +1.30). This confirms G2-E01
(t = −0.27) and G2-E02 (t = −0.03) by a different route and explains *why* the ceiling
suggested otherwise.

**G11-F04 — quality and margin signals are real pre-2019 and dead since.** `screener_roce_cs_z`
and `operating_margin_cs_z`, conditional on momentum, run t ≈ +6.5 to +7.0 on full history and
+0.42 to +0.86 on 2020+. Gen-1's regime-based rejection is independently confirmed.

**G11-F05 — the sixth appearance of the index-alignment error class, inside Gen-11's own
gate.** E5's A4 attributed a kill to delivery when the window was responsible. The verdict was
unchanged; the stated cause was wrong. Rule 6 exists for exactly this and it still had to be
caught by hand.

## 6. Verdict on the mandate

**No deployable alpha other than momentum was found.** Gen-10's closing statement stands, now
with a mechanism attached: the constraint is estimation, and specifically it is that the
relationships outside momentum and delivery **do not hold their sign**.

The one route Gen-10 named — a genuinely new data source — is untouched by this and remains the
only open direction. Gen-11 adds a way to triage such a source cheaply: **run the sign-stability
screen before building anything.** A feature at 50% is unreachable no matter how good its
ceiling looks.
