# T1-09 — DS Momentum-Quality and Cross-Factor Clusters. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T0-03 (composition artifact), results/gen10/T1-04a (cluster procedure),
              GEN10_REMEDIATION_CHARTER.md s4/T1-09
Artifacts:    t1_09_data.json. Script: scripts/gen10/t1_09_ds_momentum_and_crossfactor.py
```

**Outcome: nothing promotes.** The cross-factor item with the largest t-statistic in the entire deep
search (DS-F2-03, t = −8.91) is retired on cost before Stage 1, its turnover landing within 2% of the
Gen-1 reversal signal that was killed for exactly this reason. The momentum-quality cluster loses
30–40% of its headline ICs to the composition artifact and then fails out of sample. One item
survives the letter of the Stage-1 rule while failing multiplicity and showing nothing at all in
discovery.

---

## 1. DS-F2-03 — retired on cost, before Stage 1

The charter pre-registered running Stage 4 first for this item, because it is a reversal × illiquidity
interaction and Gen-1 killed that family twice:

- **A04** — 1-week reversal: real IC (t = −6.82), dead at **4187%/yr** turnover.
- **A15/A19** — momentum × illiquidity: *"edge sits exactly where impact cost kills it."*

Turnover of a top-quintile long book on DS-F2-03:

| | annualised two-way turnover |
|---|---|
| **DS-F2-03** | **4091%/yr** (0.393/week) |
| A04 reference | 4187%/yr |
| control: `mom_60d_cs_z` | 2236%/yr |

**A 2% match to A04.** The control shows the measurement discriminates — a slow signal on the same
panel turns over at roughly half the rate. DS-F2-03 is the same trade as A04 wearing an interaction
label, and it is retired without running the remaining stages, exactly as pre-registered.

This is the single largest |t| in the whole 28-item deep search. It was never a candidate; it was a
transaction-cost machine that the discovery pass had no cost model to see.

## 2. Composition correction (T0-03), applied before Stage 1

T1-04a established that delivery signals are immune to the universe-composition artifact because
their coverage sits inside the liquid universe. These signals are broad-coverage, so the correction
was applied before any Stage-1 decision:

| ID | share of pooled IC that is between-group composition |
|---|---|
| **DS-F4-01** | **+40%** |
| **DS-U-01** | **+36%** |
| **DS-F4-02** | **+30%** |
| DS-F2-04 | +7% |
| DS-F2-06 | −5% |

T0-03 predicted this from coverage alone, and the prediction holds: the three broad price-momentum
signals lose a third or more of their headline IC, while the two conditional tests — which gate on a
tercile and so already sit inside a narrower slice — are clean.

**Three of the six "statistically real" signals in this cluster were between a third and two-fifths
artifact before any out-of-sample question was asked.**

## 3. Stage 1 — corrected ICs across the split

Windows: DISCOVERY 2005-01-07…2017-12-29 (678w), OOS 2018-01-05…2025-07-04 (392w),
LOCKBOX 2025-07-11…2026-06-26 (51w). All t-statistics below are composition-corrected.

| ID | cluster | archived t | full (pooled) | full | DISC | **OOS** | LOCK | verdict |
|---|---|---|---|---|---|---|---|---|
| DS-F4-01 | momentum-quality | +3.06 | +2.99 | +1.96 | +1.29 | **+1.36** | +1.15 | KILL |
| DS-F4-02 | momentum-quality | +6.33 | +6.29 | +4.52 | +4.30 | **+1.73** | +1.06 | KILL |
| DS-U-01 | momentum-quality | +2.91 | +2.83 | +1.99 | +1.33 | **+1.40** | +1.06 | KILL |
| DS-F2-06 | momentum-quality | +3.38 | +3.34 | +3.54 | +3.25 | **+1.32** | +1.16 | KILL |
| DS-F2-03 | cross-factor | −8.91 | — | — | — | — | — | RETIRED (cost) |
| DS-F2-04 | cross-factor | +2.20 | +2.22 | +2.16 | +0.03 | **+2.31** | +0.75 | survives |

**DS-F4-02 is the instructive case.** The remediation plan singled it out as its second-priority
candidate — *"t=6.33 in particular is a candidate veto/overlay on the existing momentum book"*. It
loses 30% to composition (6.29 → 4.52), holds up strongly in discovery (+4.30), and then falls to
**+1.73 out of sample**. A veto overlay built on it would have been built on a discovery-window
artifact.

**Multiplicity:** BY at q=0.05 across the five tested items — **0 of 5 pass**. DS-F2-04's OOS p =
0.0212 is the best and does not clear.

## 4. DS-F2-04 — survives the letter of the rule, promotes nothing

DS-F2-04 ("value works when price is weak") satisfies the pre-registered Stage-1 rule: OOS |t| = 2.31
and no sign flip. But two things disqualify it from promotion:

1. **It fails the pre-registered BY correction** (p = 0.0212).
2. **Discovery t = +0.03.** The signal is entirely absent across 678 weeks of discovery and appears
   only in the 392-week OOS window. That is the opposite of what a real effect looks like — selection
   normally makes discovery *stronger* than OOS, not invisible. Either a genuine post-2018 regime
   effect or noise, and 392 weeks cannot separate those.

Recorded as **UNRESOLVED**, not promoted. Its archived t of +2.20 was the weakest of the cross-factor
pair, and it remains marginal after everything.

## 5. Findings

**G10-F20 — DS-F2-03, the largest |t| in the deep search, is A04 rediscovered.** Top-quintile turnover
of 4091%/yr against A04's 4187%/yr, with a 2236%/yr control demonstrating the measurement
discriminates. Retired on cost before any statistical stage, per pre-registration. **A large t-stat on
a fast-turnover signal is a cost problem presented as a discovery.**

**G10-F21 — the momentum-quality cluster is 30–40% composition artifact and then fails out of
sample.** After correction, all four items fall below |t| = 2 on the OOS window, including DS-F4-02
which the remediation plan ranked as its strongest overlay candidate (archived +6.33 → OOS +1.73).

**G10-F22 — the deep search's out-of-sample survival rate is now measurable, and it is low.** Across
T1-04a and T1-09, 14 deduped DS items have faced a genuine split. One survives its rule while failing
multiplicity; three survived in T1-04a and proved to be one already-deployed signal; the rest died.
**Zero new deployable alpha from 28 catalogued RESEARCH_SIGNAL items.** Combined with DS-F3-04's
earlier collapse, RESEARCH_SIGNAL as issued by the deep search does not predict out-of-sample
survival — it predicts a full-sample fit.

## 6. Consequences for the remediation plan

- **Item 2.4 is closed in full** (delivery cluster in T1-04a, these two clusters here). It was the
  plan's highest-value item — "~15 statistically real signals… reuses infra you already built" — and
  the infrastructure claim was right while the value claim was not.
- **The plan's own cautions were correct and load-bearing.** It flagged DS-F2-03 for exactly this
  reason ("run Stage 4 before getting attached to the effect size; if it shares reversal's turnover
  profile, it's dead for the same structural reason regardless of statistical strength"). That
  instruction was followed and it was right to the second decimal place.
- **What the plan could not have anticipated** is the composition artifact, which is what actually
  killed the momentum-quality cluster. That came out of T0-03 and did not exist as a concept in the
  plan.

## 7. Threats to validity

- **The composition correction is a two-group split** (in PANEL-A / not). A finer split by ADV decile
  would attribute more and could push the corrected t-statistics lower still — the correction is a
  lower bound on the artifact, so the kills are conservative in the right direction.
- **Conditional tests (DS-F2-06, DS-F2-04) reproduce `deepsearch.conditional_ic`'s tercile gating at
  0.66/0.34.** A different gate is untested. Both were fixed in advance.
- **The turnover measure is name churn in a top-quintile book**, not a full cost model with per-name
  ADV and impact. It is the same measure A04's 4187%/yr refers to, which is what makes the comparison
  meaningful; an absolute cost figure would need the capacity-ladder machinery used in T1-06.
- **The discovery window (2005–2017) contains fewer names per date** than the OOS window, since the
  panel grows over time. This weakens discovery-window power somewhat and could contribute to
  DS-F2-04's discovery t of +0.03 — though not plausibly all of a gap from 0.03 to 2.31.
