# T1-06 — Delivery: Regime Dependency and Sleeve Integration. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md (open questions 1 and 2),
              results/gen8/G8-09 (the overlay version), GEN10_REMEDIATION_CHARTER.md s4/T1-06
Artifacts:    t1_06_data.json. Script: scripts/gen10/t1_06_delivery_sleeve_and_regime.py
```

**Outcome: both of ARP's open questions are answered, and the answer to the second one is no.**
Delivery is **not** regime-conditional (a static weight is correct). As a separate sleeve it is
genuinely separable from the momentum book, but **at the lower bound of its own confidence interval
the optimal allocation is zero at every capital band** — so it does not promote. Two premises the
remediation plan built on turned out to be wrong: the sleeves are 0.84 correlated, not 0.14, and the
diversification case they were supposed to support does not exist.

---

## 1. Part 1 (2.2') — is Delivery regime-conditional?

Regime cells in the delivery era, using the repo's own PIT `build_regimes`:

| regime | weeks | |
|---|---|---|
| NORMAL_UP | 150 | |
| STRESS | 70 | |
| STRONG_UP | 65 | |
| CRASH | 38 | |
| RECOVERY | **15** | **below MSRP's MIN_N = 30** |

RECOVERY fails MSRP's own gate. Testing five states here would repeat M-02A's documented false
positive, where a fixed effect-size band at small regime samples flagged all six primitives as
regime-locked. The pre-registered fallback — a two-state collapse — was used.

| state | weeks | IC | t | bootstrap 95% CI |
|---|---|---|---|---|
| RISK_ON (NORMAL_UP + STRONG_UP) | 215 | +0.0327 | **+4.20** | [+0.0161, +0.0490] |
| RISK_OFF (STRESS + CRASH + RECOVERY) | 123 | +0.0110 | +0.89 | [−0.0119, +0.0340] |

It is tempting to read that as "delivery works in risk-on and not in risk-off". **That reading is
wrong, and it is exactly the error M-02A made.** The hypothesis is about the *difference*, and the
difference must be tested directly:

```
RISK_ON - RISK_OFF = +0.0217   SE 0.0146   t = +1.49
```

**Not significant.** Delivery is **not** established as regime-conditional. Two cells with different
individual significance are not a difference; the RISK_OFF cell simply has fewer weeks and a wider
interval.

**Sizing implication for 2.1': a static Sleeve-B weight is the correct choice.** The plan anticipated
that a regime-locked result would call for a regime-conditional allocation, and was right to run this
first — the answer just came back static.

## 2. Part 2 (2.1') — sleeve integration

### 2.1 Name overlap — the sleeves are separable

| | |
|---|---|
| Sleeve A (momentum, top 20%) | 86 names/week |
| Sleeve B (non-F&O delivery, top 10%) | 30 names/week |
| shared | **4.7/week — 15.7% of Sleeve B** |
| Jaccard | 0.044 |

Below the 25% pre-registered threshold. **No material position-level double-counting**; the two
sleeves can be sized independently. This was the plan's step 3 and running it first was correct.

### 2.2 The correlation premise is wrong

| | |
|---|---|
| Sleeve A Sharpe | **+1.604** ± 0.397 (95% CI [+0.83, +2.38]) |
| Sleeve B Sharpe | **+1.939** ± 0.399 (95% CI [+1.16, +2.72]) |
| **sleeve return correlation** | **+0.842** |
| n | 338 weeks |

The ARP dossier's **0.14 is signal orthogonality** — the correlation of the delivery ranking with the
momentum ranking. The remediation plan's step 2 reads it as sleeve-return correlation and concludes
"close enough to orthogonal that a simple inverse-vol or risk-parity blend should get you most of the
diversification benefit". **Two long-only Indian equity books share market beta whatever their signals
do.** The realised sleeve correlation is 0.842, and at that level there is very little diversification
to harvest.

So any blended improvement must come from Sleeve B's higher standalone Sharpe, not from
diversification. Is that advantage real?

```
Sleeve B - Sleeve A:  +0.335 Sharpe   SE 0.209   t = +1.60   p = 0.109
                      bootstrap 95% CI [-0.081, +0.791]
```

**Not significant.** The entire case for the sleeve rests on a Sharpe difference that cannot be
distinguished from zero on the available history.

### 2.3 The significance test the plan wanted — and why it was pre-registered as descriptive

At a naive w = 20%: blend vs momentum-alone = +0.109 Sharpe, paired t = +2.33.

That looks like a pass, and it is reported **descriptively only**, because the design's own power says
it means little: the minimum detectable Sharpe difference at 80% power is **+1.573 unpaired** — the
design the plan's step 5 specified. G8-09 reached the same conclusion by the same arithmetic and
switched to a paired design; the paired MDE here is degenerate because the blend contains Sleeve A,
so the two streams are nested and the comparison is close to self-referential. A "significant"
improvement from adding 20% of a sleeve to itself is not evidence of anything.

### 2.4 The pre-registered question — optimal weight under uncertainty

| Sleeve B assumed at | standalone Sharpe | w* | blended Sharpe | gain |
|---|---|---|---|---|
| point estimate | +1.939 | **100%** (corner) | +1.940 | +0.335 |
| **CI lower bound** | **+1.157** | **0%** | +1.604 | **0.000** |

At the point estimate the optimum is a corner — put everything in Sleeve B — which is a symptom of
Sharpe-maximisation with two correlated streams, not a recommendation. At Sleeve B's CI lower bound
the optimum is zero.

A bootstrap over jointly-resampled weekly returns shows how little the data pins this down:

```
w* distribution:  5% -> 49% | 25% -> 82% | median -> 100% | 75% -> 100% | 95% -> 100%
P(w* = 0)    =  0.4%
P(w* >= 50%) = 94.7%
P(w* = 100%) = 57.9%
```

The two views disagree, and the disagreement is informative rather than a problem to resolve. The
bootstrap resamples symmetrically and mostly wants a large allocation; the pre-registered CI-lower-bound
stress is deliberately **asymmetric** — it penalises Sleeve B while holding Sleeve A at its point
estimate — and wants none. That asymmetry is a genuine limitation of the rule as written, and it is
recorded rather than argued around, because the rule was fixed before the run.

What both agree on: **338 weeks cannot size this sleeve.** The range of defensible allocations spans
0% to 100%.

### 2.5 The one robust conclusion — capacity

| capital | Sleeve A net Sharpe | Sleeve B net Sharpe | w* (point est) | w* (CI lower) |
|---|---|---|---|---|
| ₹5L | 1.408 | 1.641 | 95% | 0% |
| ₹1cr | 1.404 | 1.569 | 83% | 0% |
| ₹5cr | 1.389 | 1.400 | 53% | 0% |
| ₹10cr | 1.367 | 1.269 | 29% | 0% |
| ₹25cr | 1.321 | 1.013 | **0%** | 0% |
| ₹100cr | 1.185 | 0.382 | 0% | 0% |
| ₹500cr | 0.824 | **−0.648** | 0% | 0% |

Independent of the sizing debate, the optimal weight **declines monotonically with capital and reaches
zero by ₹25cr** even on the most favourable assumption. Sleeve B's net Sharpe turns negative above
~₹100cr. This reproduces ARP's capacity ladder and G8-09's ₹5–10cr peak by a third independent route,
which is the most trustworthy part of this result.

## 3. Verdict

**DO NOT PROMOTE**, per the pre-registered rule: the optimal weight at Sleeve B's CI lower bound is
zero at every capital band.

## 4. Findings

**G10-F16 — Delivery is not regime-conditional.** The RISK_ON minus RISK_OFF IC difference is +0.0217
with t = +1.49. ARP's open question 2 is answered: a static sleeve weight is correct, and no
regime-conditional sizing rule is justified. Testing the two cells separately (t = 4.20 vs 0.89) and
concluding "regime-locked" would be M-02A's error repeated.

**G10-F17 — signal orthogonality is not sleeve-return orthogonality.** Delivery's 0.14 correlation
with momentum is a ranking correlation; the two long-only sleeves' *returns* correlate at 0.842. The
diversification case for a two-sleeve book does not survive the distinction. Any future
multi-sleeve proposal in this programme must quote realised sleeve-return correlation, never signal
correlation.

**G10-F18 — the sleeve's case rests on a Sharpe advantage that is not significant.** Sleeve B beats
Sleeve A by +0.335 Sharpe with t = +1.60 on 338 weeks. With sleeve correlation at 0.842 there is
almost no diversification to fall back on, so the allocation stands or falls on that difference, and
it does not stand.

**G10-F19 — ARP's open question 1 is answered in the negative, and by a different route than
G8-09.** G8-09 showed the delivery *overlay* does not improve the certified book and cannot be shown
to. This shows the *sleeve* formulation — the architecture G8-09 explicitly left untested — does not
promote either, for a different reason: not that its contribution is too small to detect, but that
its optimal size is indistinguishable from zero once its own estimation error is taken seriously.
**Both integration architectures are now closed.**

## 5. Consequences for the remediation plan

- **Item 2.1 is closed.** Its central insight — that sleeve-level and overlay-level integration are
  different architectures and only the overlay had been tested — was correct and is confirmed by
  G8-09 §7. The sleeve architecture has now been tested and does not promote.
- **Item 2.1's step 2 was based on a misreading** of what the 0.14 correlation refers to. This is
  worth recording because the same number appears in the ARP dossier, the handbook and the plan.
- **Item 2.2 is closed** with a clean negative, and its output did what the plan intended: it sized
  2.1 (statically).
- The plan's step 1 instruction to use Config-4's recertified Sharpe (0.8105/0.8471) alongside
  delivery-era numbers was avoided. On the matched window Sleeve A scores 1.604 — the delivery era is
  a much stronger period for this book, and mixing eras would have manufactured an improvement.

## 6. Threats to validity

- **338 weeks, one market era.** Every delivery result carries this. It is the binding constraint on
  the sizing question, not a side note.
- **The pre-registered CI-lower-bound rule is asymmetric** — it stresses Sleeve B and not Sleeve A.
  A symmetric version (both at their lower bounds) or a Bayesian shrinkage approach would be a better
  rule. It was fixed before the run and is reported as written; the bootstrap in §2.4 is the
  symmetric counterpart and is reported alongside.
- **Sleeve A is a momentum-quintile proxy, not the full certified Config-4** (no sector balancing, no
  0.5× F&O short, no G-05 crash overlay). It matches the construction ARP's own correctness gate used,
  so the comparison is internally consistent, but a full-book version could behave differently. G8-09
  ran the full book and reached a compatible conclusion.
- **Equal-weighting within each sleeve.** Alternative weightings inside Sleeve B are untested.
- The bootstrap uses an expected block length of n^(1/3) ≈ 7 weeks. Longer blocks widen the w*
  distribution further, which strengthens rather than weakens the "cannot size this" conclusion.
