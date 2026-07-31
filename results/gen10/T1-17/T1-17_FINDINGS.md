# T1-17 — G5-08A/B/C/D and G5-09: The Construction Branch. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   docs/GEN5_DECISION_LOG.md (the sequencing rule this overrides)
Artifacts:    t1_17_data.json. Script: scripts/gen10/t1_17_g508_construction_battery.py
```

**Outcome: 0 of 5 promote. Gen-5's sequencing rule is vindicated — but not trivially.** Two arms
(risk parity, covariance shrinkage) are the **first construction-side items in this programme to clear
statistical significance at all**, and they fail only on the economic bar. That distinction is worth
recording precisely rather than filing under "nothing worked."

---

## 1. Why these were never run

Gen-5 did not skip this branch for data or time. Its own frozen sequencing rule shut it
(`docs/GEN5_DECISION_LOG.md`, 2026-07-24):

> *"Per the frozen sequencing rule, Paper 2's construction branch (G5-08A–D) does NOT open — it
> required a cleared B1 gate, which none produced."*

All three B1 levers were TERMINATED_BY_GATE, so the branch stayed shut. **Running it overrides that
discipline, on explicit instruction, and the prior going in was low** — Gen-10's own T1-06 (any
long-only sleeve added to a long-only book hits a ~0.84 correlation wall) and T1-15 (the small-cap
tiers are one nested signal) both pointed the same way. A low prior is a reason to pre-register a hard
kill criterion, not a reason to skip.

## 2. Results

Identical holdings, identical dates, only weights differ (Rule 6). Net of the real cost model.
Book: top-quintile composite, monthly rebalance, 1,068 weeks, ~56 names.

| arm | Sharpe | Δ vs EW | t | bootstrap 95% CI | cost | verdict |
|---|---|---|---|---|---|---|
| **EW** *(benchmark)* | +0.6767 | — | — | — | 2.27 bps | — |
| G5-08A confidence-weighting | +0.6397 | **−0.037** | −1.04 | [−0.127, +0.053] | 5.38 bps | KILL |
| **G5-08B risk parity** | +0.7374 | **+0.061** | **+4.24** | **[+0.001, +0.121]** | 3.40 bps | KILL |
| **G5-08C covariance shrinkage** | +0.7395 | **+0.063** | **+5.80** | **[+0.008, +0.119]** | 3.24 bps | KILL |
| G5-08D no-trade regions | +0.6757 | −0.001 | −0.45 | [−0.006, +0.003] | 2.23 bps | KILL |
| G5-09 temporal state model | — | +0.110 | +1.54 | [−0.060, +0.299] | — | KILL |

**Pre-registered rule: promote requires Δ ≥ +0.15 (Gen-5's own bar) AND a bootstrap CI excluding zero
AND BY-clean at m = 5. 0/5 clear it.**

## 3. What the two survivors actually show

G5-08B and G5-08C are **statistically real**: t = +4.24 and +5.80, BY-clean, bootstrap CIs excluding
zero. They are also **economically small**: +0.061 and +0.063 Sharpe against a +0.15 bar, and their
bootstrap lower bounds are **+0.001 and +0.008** — the intervals essentially touch zero even though
the NW t-statistics look emphatic. That gap between a t of 5.8 and a CI lower bound of 0.008 is
exactly what Rule 3's two-estimator requirement exists to surface.

Both are variants of the same idea — down-weight volatile names — which is why they land within 0.002
Sharpe of each other. This is one finding, not two.

**Confidence weighting (G5-08A) is the interesting failure.** Weighting by composite strength is the
most intuitive construction idea in the set and it is the only arm that goes *backwards* (−0.037),
while tripling turnover cost (5.38 vs 2.27 bps). Concentrating into the strongest-ranked names buys
nothing and pays for the privilege — consistent with Gen-5 F01 (the momentum composite is a redundant
4-way ensemble, so the top of its ranking is not meaningfully "more signal").

**No-trade regions (G5-08D) do nothing** (−0.001, cost 2.23 vs 2.27 bps). That is the expected result
and worth stating: the book already has trade-band hysteresis from **A21** (enter 60th / keep 40th
percentile, turnover 308%→151%/yr, already deployed). G5-08D re-proposes a mechanism the book already
has, so finding no incremental value confirms A21 is doing its job rather than revealing a gap.

## 4. On the bar

The +0.15 gate was set for **dynamic timing levers** — designs that estimate a new state and act on
it, carrying new failure modes. G5-08B/C are **static reweightings** with no new state estimation and
~1 bp of extra cost. Whether a static construction change should face the same bar as a dynamic
overlay is a **governance question this experiment cannot settle**, and it is raised here only because
the honest answer to "did anything work" is "two things are real and small, and the bar they failed
was written for a different kind of intervention."

**The pre-registered verdict stands: KILL.** Recording the nuance is not the same as promoting on it,
and the bootstrap lower bounds above are the reason not to.

## 5. Findings

**G10-F50 — the construction branch produces no promotable result, and Gen-5's sequencing rule was
sound.** 0 of 5 arms clear a pre-registered bar of Δ ≥ +0.15 with a CI excluding zero. The branch was
closed for the right reason.

**G10-F51 — inverse-volatility weighting is a real but sub-gate improvement.** Risk parity (+0.061,
t = 4.24) and covariance shrinkage (+0.063, t = 5.80) are the first construction-side items in this
programme to clear statistical significance, and they are one finding, not two. Their bootstrap CI
lower bounds (+0.001, +0.008) show the effect is far weaker than the t-statistics suggest.

**G10-F52 — confidence weighting is actively harmful.** Weighting by composite strength costs −0.037
Sharpe and triples turnover cost. This is Gen-5 F01 in portfolio-construction form: if the composite
is a redundant ensemble, the top of its ranking carries no extra information to concentrate into.

**G10-F53 — no-trade regions add nothing because the book already has them.** A21's trade bands are
deployed; G5-08D re-proposes the same mechanism and finds −0.001. A confirmation, not a gap.

## 6. Threats to validity

- **G5-08C is implemented as a shrunk-diagonal covariance** (per-name vol shrunk 50% toward its
  cross-sectional mean, inverse-variance weights), not a full Ledoit-Wolf estimate on a sample
  covariance matrix. With ~56 names and weekly data a full covariance is badly conditioned; the
  diagonal case is what a shrinkage optimizer collapses toward here. A full-covariance version could
  differ, and its near-identity with G5-08B suggests the diagonal is carrying the effect.
- **G5-09 is one temporal specification** — exposure halved when trailing 13-week market vol is rising
  over 4 weeks. Gen-5 F17 already established that weekly state carries near-zero information about
  the correct action, and T1-07 settled that across five cadences; this tests trajectory rather than
  level, and finds +0.110 with a CI spanning zero.
- The book is a Config-4 *proxy* (top-quintile composite, no sector balancing, no short leg, no G-05
  overlay). Weight-scheme effects should transfer, but absolute Sharpes are not the certified book's.
- All arms share one holdings path, so this isolates weighting cleanly and says nothing about
  selection.
