# T1-18 — MSRP's Three Unopened Pillars. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   MSRP_CHARTER.md (the opening rules), results/gen10/T1-10 + T1-16 (Networks' gate)
Artifacts:    t1_18_data.json. Script: scripts/gen10/t1_18_msrp_pillars.py
```

**Outcome: Economic Limits run, Geometry run, Networks assessed and NOT opened.** The charter treats
these three asymmetrically and so does this. The headline number is uncomfortable and is reported as
such: the deployed book captures only **20%** of the attainable ceiling in its own feature basis —
but every Gen-10 attempt to claim that headroom failed, which relocates the binding constraint from
information to estimation.

---

## 1. Pillar 5 — Economic Limits (charter: "runs regardless")

Per date, fit the best possible linear combination of the 15-feature basis to *that date's own
realised* forward returns. That oracle cannot exist, so its IC bounds what any model could extract
from these features.

**The correction that matters.** An in-sample fit of *k* regressors on *n* points buys IC from
overfitting alone. A first pass subtracted an analytic √(k/n) term — **that is not valid in IC
space**, so it was replaced with a measured permutation null: the same design matrix, refit on a
*shuffled* target.

| | IC |
|---|---|
| oracle, in-sample best combination | **+0.3534** |
| oracle on a **shuffled** target — what overfitting alone buys | **+0.2128** |
| **attainable ceiling** (excess over shuffled) | **+0.1407**  (t = +32.3, boot95 [+0.131, +0.151]) |
| **deployed** momentum composite | **+0.0284**  (t = +4.97) |

**60% of the raw oracle was overfitting.** Measuring that rather than approximating it is the whole
result — an analytic correction would have put the ceiling at +0.114 and the capture rate at 25%.

**Capture rate: 20%.**

**How to read that, in both directions.** Nominally there is 5× headroom in this feature basis. But
Gen-10 spent fourteen experiments trying to claim exactly that headroom — the DS battery (14 deduped
items, first-ever OOS split, zero new alpha), the construction branch (0/5 promote), conditional
momentum (closed), liquidity sizing (t = 0.50) — and **every attempt failed out of sample.** The
ceiling is an *in-sample* bound computed with perfect foresight of each week's returns; the gap
between it and the deployed book is not a list of unclaimed opportunities, it is the price of not
having foresight. **The binding constraint is estimation, not information.**

That is a more useful statement than either "there's lots left" or "we're near the limit", and it is
the first quantified version of it this programme has.

## 2. Pillar 3 — Geometry

Effective dimensionality = participation ratio of the correlation matrix eigenvalues,
(ΣΛ)² / ΣΛ² — the same statistic G8-10 used for receiver independence. Computed per era, on levels
**and on first differences**, because every feature is a rolling-window construct and MSRP law
requires the differenced check as a first step, not an afterthought.

| era | eff-dim (levels) | PC1 | eff-dim (differenced) | PC1 |
|---|---|---|---|---|
| 2005–2009 | 6.21 | 29% | 7.34 | 27% |
| 2010–2014 | 6.03 | 30% | 7.42 | 26% |
| 2015–2019 | 5.86 | 30% | 7.18 | 27% |
| 2020–2025 | 6.06 | 30% | 7.21 | 27% |
| **mean** | **6.04** (range 0.35) | | **7.29** (range 0.24) | |

**Two findings.**

**The shape is stable.** Effective dimension varies by **0.35** across four eras on a 15-dimensional
space — including the GFC, demonetisation, COVID and the 2022 rate cycle. PC1 holds at 29–30%
throughout. Whatever else changes about this market, the *shape* of its state space does not.

**Differencing raises effective dimension by +1.25** (6.04 → 7.29). This is the Rolling-Window
Persistence Principle appearing a third time, in a new place and with the opposite sign to its
previous appearances: overlapping windows do not only manufacture *persistence* (M-01, G6-00), they
also manufacture apparent *common structure*, making the state space look ~17% lower-dimensional than
it is. Levels understate dimensionality.

## 3. Pillar 4 — Networks: assessed, NOT opened

The charter gates this one: *"Only if 1–3 show exploitable structure worth propagating across
assets."* Three independent reasons it does not open:

1. **Its core question is already answered, negatively.** "How information flows between sectors,
   assets and macro variables" is what Gen-7 CAIT asked. T1-10 closed it at adequate power (0/15
   survivors, max |r| = 0.014 against a 0.11 floor, beta confound removed by design); T1-16 covered
   its one uncovered channel and retired its one surviving candidate. Opening Networks would re-ask a
   question now answered twice.
2. **The macro arm is answered too.** Gen-2/3's five-wave programme tested 155 domestic indicators
   across credit, rates, fiscal, real-economy and valuation channels: no tradeable signal beyond
   price/sector/delivery.
3. **The gate's premise fails on Pillar 5's own terms.** Networks exists to propagate exploitable
   structure across assets. Pillar 5 shows the constraint is estimation rather than information — so
   there is no identified structure waiting to be propagated, only a ceiling nobody can reach.

**VERDICT: DO NOT OPEN.** This is the charter's own conditional rule applied, not a scope cut.

## 4. Findings

**G10-F54 — the attainable predictability ceiling in the 15-feature basis is IC +0.141, and the
deployed book captures 20% of it.** Measured against a permutation null rather than an analytic
correction: **60% of the raw oracle (+0.353) is overfitting**, visible only because the null was
measured. The remaining gap is the cost of lacking foresight, not a list of unclaimed opportunities —
Gen-10 tried to claim it fourteen times and failed every time.

**G10-F55 — the market's state space has a stable shape.** Effective dimension 6.04 on levels, range
**0.35** across four eras spanning the GFC, COVID and the 2022 rate cycle; PC1 constant at 29–30%.
MSRP Pillar 3's core question is answered: the shape does not change.

**G10-F56 — rolling windows manufacture apparent common structure, not just apparent persistence.**
Differencing *raises* effective dimension by +1.25 (6.04 → 7.29), so levels understate
dimensionality by ~17%. A third appearance of the Rolling-Window Persistence Principle, with the
opposite sign to M-01 and G6-00 — worth recording because a reader who knows the principle as
"windows create spurious persistence" would predict the wrong direction here.

**G10-F57 — MSRP Pillar 4 (Networks) does not open, by its own charter gate.** Its question has been
answered negatively twice (Gen-7/T1-10/T1-16 for cross-asset, Gen-2/3 waves for macro), and Pillar 5
shows nothing identified is waiting to be propagated.

## 5. Threats to validity

- **The oracle is linear.** A non-linear oracle would sit higher, so +0.141 is a *linear* ceiling and
  the true capture rate is an over-estimate. Against that: Gen-6 and G8-01/01B tested non-linear
  representations at 198× scale and found no positive evidence, so the linear bound is unlikely to be
  far off in practice.
- **The permutation null uses 3 draws per date** across 1,033 dates (≈3,100 fits). More draws would
  tighten the per-date estimate; the aggregate is already very tight (boot95 [+0.131, +0.151]).
- **The ceiling is basis-specific.** It bounds what these 15 features can deliver, not what any data
  could. A genuinely new data source is outside this bound — which is the one route Pillar 5 does not
  close.
- **Effective dimensionality is a second-moment statistic.** A state space can have stable covariance
  geometry while its higher moments or its conditional structure shift. Geometry's question as the
  charter poses it ("what shape, and does it change") is answered at the level the statistic measures.
