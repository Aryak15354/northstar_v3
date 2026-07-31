# T0-03 — Momentum Harness Reconciliation. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/LEDGER.csv, scripts/kaggle/plan_2026_05_18_production/run_phase1_battery.py,
              scripts/gen23/deepsearch.py, GEN10_REMEDIATION_CHARTER.md s4/T0-03
Artifacts:    t0_03_data.json. Script: scripts/gen10/t0_03_harness_reconciliation.py
```

**Outcome: the discrepancy is not a harness-configuration difference — it is a universe-composition
artifact, and 36% of the disputed IC is manufactured by pooling two systematically different groups of
stocks into one cross-section.** The good news is that the artifact is signal-specific and the delivery
cluster is immune, so the remediation plan's highest-value item is unaffected.

---

## 1. The discrepancy

`ret_13w` (PANEL-A) and `mom_60d_cs_z` (enriched panel) have a mean per-date Spearman of **0.9691**
(median 0.9743, min 0.7627, n=1,121). They are the same construct. Yet:

| source | signal | IC | t | verdict |
|---|---|---|---|---|
| Gen-1 LEDGER, F-01 battery | `ret_13w` | 0.0089 | 1.17 | **NOISE** |
| Gen-2/3 deepsearch, DS-U-01 | `mom_60d_cs_z` | 0.0138 | 2.91 | **RESEARCH_SIGNAL** |
| Gen-2/3 momentum determinants, MOM60 | `mom_60d_cs_z` | — | 3.36 | **RESEARCH_SIGNAL** |

## 2. The config axes do not explain it

Walking the five configuration differences one at a time, **all on PANEL-A** so the panel is held fixed:

| axis | LEDGER → deepsearch | IC | t | Δt |
|---|---|---|---|---|
| target horizon | 4w → 1w | −0.0042 | −0.92 | **−2.31** |
| target relativity | sector-rel → raw | +0.0243 | +2.56 | +1.17 |
| window | lockbox-excl → full | +0.0119 | +1.51 | +0.12 |
| target winsorization | none → clip 1/99 | +0.0116 | +1.42 | +0.03 |
| universe filter | close≥20 → none | +0.0113 | +1.39 | +0.00 |

Two axes matter individually and they pull in **opposite** directions. The net result is that the
deepsearch configuration, **run on PANEL-A, gives t = +0.91 — weaker than the LEDGER config's +1.39,
and nothing like the archived +2.91.** The configuration walk closes none of the gap.

Control: cross-sectional z-scoring changes the rank IC by 0.000000, as it must — it is monotone within
each date. `mom_60d_cs_z` vs `ret_13w` is not an axis at all.

## 3. The panel is the axis — and the mechanism is composition

| universe | IC | t | median names/date |
|---|---|---|---|
| enriched panel, FULL (as DS-U-01 ran) | **+0.0138** | +2.83 | 450 |
| enriched panel, restricted to PANEL-A's names | +0.0086 | +1.67 | 266 |
| enriched panel, ONLY the names PANEL-A lacks | +0.0050 | +0.83 | 181 |
| PANEL-A itself | +0.0047 | +0.91 | 266 |

**The union's IC exceeds both of its parts.** That is not possible for a genuine within-group effect,
and it is the signature of a composition artifact. Decomposing it by stripping between-group variation
(demeaning both signal and target within date × group, keeping only within-group ranking):

```
union, as measured                       IC = +0.0138
union, between-group variation removed   IC = +0.0089   (t = +1.99)
=> composition component                 IC = +0.0049   (36% of the headline IC)
```

The mechanism is visible directly in the group means:

| group | rows | mean signal | mean forward return |
|---|---|---|---|
| PANEL-A names | 316,143 | **+0.0537** | **+0.00346** |
| extra names | 175,533 | **−0.1246** | **+0.00172** |

The extra names are lower on the signal *and* lower on the realised return. Ranking the two groups
together produces positive rank correlation from the group difference alone — correlation that exists
in neither group separately. This is a Simpson-type composition effect, not information.

**Consequence:** a cross-sectional IC is not comparable across universes of different breadth. Adding a
systematically-different block of names mechanically moves the IC even when the signal has no
additional predictive content among them.

## 4. Does this contaminate the delivery cluster? No.

This is the question that gates T1-04a, so it was tested rather than assumed.

| signal | union IC | union t | within-group IC | within-group t | composition share |
|---|---|---|---|---|---|
| `delivery_pct_z52` | +0.0318 | +7.93 | +0.0321 | **+8.01** | **−1%** |
| `delivery_pct_4w_avg` | +0.0250 | +4.05 | +0.0279 | **+4.37** | **−11%** |
| `mom_60d_cs_z` (contrast) | +0.0138 | +2.83 | +0.0089 | +1.99 | **+36%** |

Both delivery signals *strengthen* slightly once between-group variation is removed. The reason is
coverage: delivery data sits **~94% inside PANEL-A's universe** (131,455 rows inside vs 5,011 outside
for `delivery_pct_z52`). There is no large second group to manufacture the artifact.

**The delivery cluster's archived t-statistics stand. T1-04a proceeds on them unchanged.**

The rule that falls out: a signal is exposed to this artifact in proportion to how evenly its coverage
straddles two systematically different universes. Broad-coverage price signals are exposed;
narrow-coverage microstructure signals are not.

## 5. Which harness is authoritative?

Neither is wrong — they measure different quantities — but the master ledger presents them side by
side as though comparable, and they are not.

For a **cross-sectional stock-selection claim**, the LEDGER / F-01 configuration is authoritative:

- A **sector-relative target** isolates stock selection from sector rotation, which is a separately
  certified sleeve (A16). A raw target rewards a signal for sector bets the book already runs
  elsewhere, double-counting the same exposure. This is why the relativity axis is worth +1.17 t-units
  — it is measuring something the book already owns.
- **Excluding the lockbox** is required by the programme's own holdout discipline.
- A **single stated universe** avoids the composition artifact of §3.

The deepsearch configuration is appropriate for **discovery breadth** — casting wide to find
candidates — and is not appropriate for promotion decisions. That is a defensible division of labour,
but it must be stated, because a discovery-configuration t-stat and a promotion-configuration t-stat
are different units.

## 6. Findings

**G10-F07 — `ret_13w` and `mom_60d_cs_z` are the same signal (per-date Spearman 0.969), and the three
archived verdicts differ because of the panel, not the signal or the harness configuration.** Running
the deepsearch configuration on PANEL-A yields t = +0.91, against an archived +2.91.

**G10-F08 — 36% of DS-U-01's headline IC is a universe-composition artifact.** The enriched panel
pools two groups of stocks that differ systematically on both the signal and the forward return; the
pooled cross-sectional IC (+0.0138) exceeds the IC of either group alone (+0.0086, +0.0050). Removing
between-group variation leaves +0.0089. Cross-sectional IC is not comparable across universes of
different breadth, and this affects every cross-generation IC comparison in the master ledger.

**G10-F09 — the artifact is coverage-dependent, and the delivery family is immune.** Signals whose
coverage straddles both universes are exposed; signals confined to the liquid universe are not.
`delivery_pct_z52` shows a −1% composition share (t = 7.93 → 8.01 when corrected). The remediation
plan's highest-value item is unaffected.

**G10-F10 — momentum's verdict is horizon-dependent in a way the ledger does not record.** At a
sector-relative 4-week target `ret_13w` gives t = +1.39; at a raw 1-week target on the same panel it
gives t = −0.92. Both are in the archive under the name "3-month momentum" with a single verdict
attached.

## 7. Proposed constitutional rule

> No signal may be compared across generations unless the comparison states **target horizon, target
> relativity, universe/panel, and window**. Ledger rows must carry those four fields. Any IC measured
> on a pooled multi-universe cross-section must report its within-group value alongside the pooled one.

This is cheap to enforce — all four fields are already known at run time in every harness — and it is
the minimum needed to make the master ledger's cross-generation table mean anything.

## 8. Errata required against the permanent record

1. **`results/LEDGER.csv` and `results/MASTER_EXPERIMENT_INDEX.csv`** — add the four provenance
   fields to every row.
2. **`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §1b and §2e** — `ret_13w` (NOISE),
   `MOM60` (RESEARCH_SIGNAL) and `DS-U-01` (RESEARCH_SIGNAL) are one signal under three
   configurations, not three findings. Merge with the configuration stated.
3. **`results/gen23/deepsearch_summary.csv`** — flag that ICs are measured on the broad enriched
   universe and are not comparable to PANEL-A numbers; the composition share should be reported per
   signal for the broad-coverage members of the battery.
4. **`Northstar_Remediation_Priority_Plan.md`** Tier-2 row "MOM60 vs ret_13w — reconcile before
   trusting either" — resolved here. The plan's framing ("either a genuine methodology difference or a
   bug") was right to flag it; the answer is neither, it is a universe artifact.

## 9. Threats to validity

- The between/within decomposition uses a two-group split (in PANEL-A / not in PANEL-A). A finer
  split — by ADV decile, say — would attribute the artifact more precisely and might raise the 36%
  figure. The two-group version is a lower bound.
- The residual gap between the enriched panel restricted to PANEL-A names (+0.0086) and PANEL-A itself
  (+0.0047) is not fully explained here. Swapping the target column accounts for a small part
  (+0.0086 → +0.0079); the remainder is row-level coverage differences between the two builds and is
  recorded as unresolved rather than attributed.
- The composition test demeans the target within group, which removes any genuine group-level return
  premium along with the artifact. If a real, tradeable group-level effect exists, this test is
  conservative against it. That is the right direction of conservatism for a *cross-sectional*
  stock-selection claim, but it would understate a long-short group-tilt strategy.
- MOM60's t = 3.36 comes from a third script (`exp_momentum_determinants.py`) with its own quintile
  construction; only DS-U-01 was reproduced directly. MOM60 uses the same enriched panel and is
  expected to carry the same artifact, but that was not separately verified.
