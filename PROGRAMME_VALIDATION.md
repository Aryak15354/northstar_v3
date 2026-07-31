# Programme Validation Report

> ## ⚠ AMENDED 2026-07-31 by Gen-10 — read this before using any number below
>
> A successor generation re-tested this record rather than extending it, and **eight verdicts changed.**
> Numbers in §1 and §3–§5 that depend on AEP Papers B/C/D, on Gen-7's status, or on the universe-tier
> story are superseded. The §2 self-caught-corrections count is **13 → 21**, and its framing needs the
> amendment in §2b.
>
> This report is left as written. Corrections are recorded here and in
> `results/gen10/GEN10_SYNTHESIS.md`; the monograph carries the narrative version as Part IX.


**Quantitative meta-validation of the entire Northstar research programme, Gen-2 through AEP.** This is
not another experiment — it answers three separate questions the monograph's own reader would otherwise
have to reconstruct by hand: was the programme disciplined, what did it permanently produce, and what is
actually ready to run. Every number below is sourced to a specific ledger or decision log, not estimated.

---

## 1. Research quality

| Metric | Count | Source |
|---|---|---|
| Total catalogued experiments/analyses | **141** | `results/ARP_MASTER_ALPHA_REGISTRY.csv` (Gen-2/3/4/5: 120, Gen-6: 6, MSRP: 15) |
| Permanently retired (no information, overfit, wrong-signed, methodological failure, representation-learning failure) | **70** | Same, `bucket = Permanent Dead End` |
| Not a rejection at all (descriptive/EXPAND findings, superseded-never-run placeholders, MSRP measurements) | **35** | Same, `bucket = N/A` |
| Positive economic-law content (feeds AEP, not itself a strategy) | **29** | Same, `bucket = Economic Law` — see `results/AEP_DISCOVERY_CENSUS.csv` for the 26-item curated version |
| Deployable alpha (recovered, validated) | **3 registry rows, 1 underlying discovery** — **[G10]** the *signal* stands and its capacity curve reproduced independently, but **both integration architectures are now closed** (overlay: G8-09; sleeve: Gen-10 T1-06). A validated signal with no deployment | Delivery family (`G2-E03`, `G2-E03b`, `G2-E03-OVERLAY`); `results/gen10/T1-06/` |
| Portfolio component (risk/covariance overlays) | **2** | `bucket = Portfolio Component` |
| Execution improvement | **2** | `bucket = Execution Improvement` |
| AEP papers opened | **5** (A–E) | `AEP_MASTER_RESEARCH_PLAN.md` |
| AEP papers Accepted | **1** (Paper A) | `results/AEP_SYNTHESIS_FROZEN.md` |
| AEP papers Modified | ~~**3** (Papers B, C, D)~~ → **0**. **[G10]** B, C and D are all re-derived to REJECTED: Paper B's confirmed role rests on a pooled stock-week SE and reverses out of sample; Paper C's Q3 is t=0.50 with no test ever computed; Paper D's monthly fails correction for the five resolutions it was selected from | `results/gen10/`, `archive_addenda/GEN10_ADDENDUM_001–003.md` |
| AEP papers Deferred (correctly, without attempting code) | **1** (Paper E) | Same |
| AEP engineering hypotheses catalogued | **8** (original prototype registry, later reorganized into Papers A–E) | `results/AEP_PROTOTYPE_REGISTRY.md` |
| Independently reproduced correctness gates (exact canonical-value match before trusting a new result) | **≥9** distinct instances across the programme | Gen-5 (canonical Sharpe 0.8471, multiple scripts), Gen-6 (Stage R0 reproduction), MSRP (I-01/I-03 baselines), ARP (`exp_delivery_overlay.py` reproduced exactly, net Sharpe 0.698/0.767 vs certified 0.70/0.77), AEP Paper D (Gen-5 M4 engine reproduced exactly, Sharpe 0.8471) |

## 2. Methodology — self-caught corrections

**A research programme's discipline is measured by what it catches in itself, not by what it never gets
wrong** (`MONOGRAPH.md` Part VII). Every item below was found and fixed by the programme itself, before
external review, and disclosed rather than silently corrected:

| # | Correction | Generation | What was wrong | Resolution |
|---|---|---|---|---|
| 1 | Broadcast-column bug | Gen-3 | A "null" FX-competitiveness result was actually a data bug, not an absence of effect | Rebuilt as rolling-beta × shock; honest null confirmed only after the rebuild |
| 2 | Price-feature contamination | Gen-4 | An early non-price test leaked price information | Caught and corrected before the Gen-4 gate closed |
| 3 | Pooled walk-forward inflation | Gen-4 | A capacity estimate was inflated by pooling across folds incorrectly | Caught and corrected before the Gen-4 gate closed |
| 4 | Negative-oracle-ceiling bug | Gen-5 (G5-05B) | Mean-P&L-sign oracle produced an impossible negative ceiling | Rebuilt as coordinate-ascent optimizing true portfolio Sharpe |
| 5 | Registry ID collision | Gen-5 (G5-08B/C) | New Paper-3B experiments reused already-registered IDs | AUDIT_CORRECTION event; re-registered as G5-D01/D02 |
| 6 | Rolling-window construction artifact (1st occurrence) | Gen-6 (R0/R0B) | Near-perfect ACF/SNR were 71% mechanical window overlap | First-differencing correction; named a standing principle |
| 7 | Relative-vs-absolute competence conflation | Gen-6 (G6-01) | GRU "beat" Ridge only because both had negative absolute R² | Reclassified NO_POSITIVE_EVIDENCE; permanent charter principle added |
| 8 | Rolling-window construction artifact (2nd occurrence) | MSRP (M-01/M-01B) | All 6 primitives misclassified long-memory, incl. `beta_104w` at its own window | First-differenced + effect-size-banded correction (M-01B) |
| 9 | Small-sample joint-significance failure | MSRP (M-02A/M-02) | Econ-only threshold meaningless at regime-level n=30–472 | Corrected to joint statistical+economic significance |
| 10 | Null design failure #1 | MSRP (M-03A) | Cumsum-of-shuffled-diffs null was an unbounded random walk, systematically too persistent | Rejected, retained for audit |
| 11 | Null design failure #2 | MSRP (M-03B) | Block-shuffled-levels null created artificial discontinuities, destroyed all persistence | Rejected, retained for audit; AR(1)-matched null adopted as the 3rd, correct design |
| 12 | Wrong-series threshold bug | AEP (Paper B Sub-study 1) | Split threshold computed on the target-reindexed series, not the full conditioning series | Fixed before the Phase A correctness gate was allowed to pass |
| 13 | Small-sample MI estimator bias | AEP (Paper D) | Raw quarterly-resolution MI looked dramatically "rising" | Permutation-null control added *before* reporting; revealed the result was entirely bias |

**13 distinct self-caught corrections across 6 generations.** None required external review to surface —
every one was found by the programme applying its own stated discipline to its own results.

## 2b. [G10 2026-07-31] Eight more corrections, and an amendment to what "self-caught" means

Gen-10 adds eight corrections to the table above, taking the total to **21**:

| # | Correction | Generation | What was wrong |
|---|---|---|---|
| 14 | Pooled stock-week standard errors | AEP (Paper B Sub-study 2) | ~62,000 overlapping, cross-sectionally dependent observations treated as independent; the CONFIRMED role reverses out of sample |
| 15 | Verdicts issued without any test | AEP (Paper C Q1/Q3/Q4) | ACCEPTED and POSITIVE awarded to point estimates with no standard error; Q3 is t = +0.50 |
| 16 | Multiplicity uncounted across selected resolutions | AEP (Paper D) | Monthly clears its own null by 5% but fails Bonferroni/BH/BY at m = 5 |
| 17 | Universe-composition artifact in pooled ICs | Gen-2/3 (deep search) | A pooled cross-sectional IC exceeded the IC of either constituent group; 36% was composition |
| 18 | Truncated per-tier date sets | Gen-8 (G8-07) | `NON_FNO_TAIL` measured on 712 weeks against every other tier's 1,070 |
| 19 | Zero-filled per-tier date sets | Gen-8/9 (G8-11) | 41.8% of a tier's sample is synthetic 0.0% returns for weeks it was empty by construction. Correcting it moves the micro-cap tier 5/17 → 15/17, tying the tier G8-11 elevated. **(Gen-10's own first reading of this bias had its direction backwards; corrected by T1-14 — zero-fill dilutes Sharpe by √(n/(n+k)), it does not inflate it.)** |
| 20 | Full-sample evaluation mistaken for evidence | Gen-2/3 (all 28 DS items) | `"lockbox_used": false` throughout; 14 items given a first split produced no new alpha |
| 21 | Signal orthogonality read as sleeve-return orthogonality | ARP / handbook / plan | Delivery's 0.14 is a ranking correlation; the sleeves' returns correlate at 0.842 |

**The amendment matters more than the count.** §2 above claims *"None required external review to
surface."* That remains literally true — Gen-10 is the same repository and the same author. But every
one of items 14–21 **survived its own generation's review, a programme freeze, an archive build with
permanent IDs and checksums, a citation guide, and the monograph's composition.** Several were cited
downstream as established for months.

The honest version: **a programme catches its own errors only for as long as something keeps re-testing
it.** Freezing a record protects it from silent revision; it does not make it true. The
Rolling-Window Persistence Principle (items 6 and 8) was caught twice by the generations that made it,
because it produced a visibly impossible number. The index-alignment defect (items 14, 17, 18, 19) took
five appearances and a dedicated remediation generation, because it produced plausible ones.

**Corollary, and the single most useful thing Gen-10 learned:** the sharpest error in the record was
inside a finding that already carried a *"corrected"* label — G8-11's correction of G8-07. It felt
checked because someone had checked it. **A finding that has been corrected once is not thereby more
trustworthy than one that never has.**

## 3. Deliverables — what is now permanent record

| Category | Count | Examples |
|---|---|---|
| Permanent findings, Gen-5 | **23** (F01–F23) | `results/gen5/GEN5_MASTER_FINDINGS.md` |
| Permanent findings, Gen-6 | **3** | R0/R0B artifact-corrected feasibility; sequence-family rejection; self-supervised-family rejection |
| Permanent findings, MSRP | **~11** | Persistent Volatility Regime; momentum-superfamily heterogeneity; Interaction Persistence Hypothesis (confirmed twice, I-05+M-05); regime-locked liquidity memory (M-02); doubly-conditional trend memory (M-04+M-05); state-lifetime beyond AR(1) (M-03); Greedy Information Basis (12 features) |
| Permanent findings, ARP | **1** | Delivery capacity curve peaks ~₹5–10cr, degrades gracefully to ₹500cr — not the monotonic-decay shape assumed |
| Permanent findings, AEP | **~8** | Market State Ontology (7 dimensions, no redundant pairs); volatility-sizing does not generalize past its original spec; liquidity-sizing real but unvalidated; monthly-resolution signal narrow and marginal; AEP's own meta-finding (robustness discipline catches engineering gaps) |
| **Total permanent findings** | **~46** | Sum of the above |
| Permanent economic laws (AEP bucket) | **29** registry entries / **26** curated discoveries | `results/AEP_DISCOVERY_CENSUS.csv` |
| Permanent portfolio rules | **2** (short book = covariance reduction not alpha; G-05 = bottom-of-drawdown protection) | Gen-5 F02/F08, F05 |
| Permanent execution rules | **2** (slippage dominates cost at scale, not statutory fees; low-turnover book robust to 0–3wk delay) | Gen-5 F22/F23 |
| Permanent negative knowledge | **≥10 named, citable negative results** | 3 TERMINATED_BY_GATE levers (F10–F12); 3 Gen-6 representation-learning rejections; Paper B's 2 sub-studies; Paper C's holding/rebalancing null; Paper E's deferral |

## 4. Overall statistics — the closure chain

```
Experiments/analyses catalogued           141
        |
        v
Permanently retired (dead end)             70    (50% of all catalogued work)
        |
Not a rejection (descriptive/N-A)          35    (25%)
        |
Positive economic-law content              29    (21%)  --> feeds AEP
        |
        v
AEP engineering hypotheses                  8    (from the 29 above, curated to 8 testable ideas)
        |
        v
AEP papers executed                         4    (A, B, C, D -- Paper E correctly deferred)
        |
        v
Validated engineering rules ready for production        0
        |
        v
Production strategies                       2 -> 1  [G10]
                                                 (frozen momentum + sector-rotation book.
                                                  The Delivery overlay is NOT a production
                                                  strategy: G8-09 = do-not-integrate, and
                                                  Gen-10 T1-06 closed the sleeve architecture
                                                  too. Validated signal, no deployment.)
```

**The honest number in the middle of this chain is zero** — no AEP engineering rule (volatility sizing,
consistency-conditional filtering, liquidity sizing, monthly-resolution timing) cleared the bar for
production readiness. ~~This is not a shortfall to explain away: Paper C's Q3 liquidity-sizing result is
real and promising but explicitly flagged as robustness-untested~~ **[G10 2026-07-31]** — Q3 is not
real. It was never tested at all: paired **t = +0.50**, 0.18x its own detection floor, it keys off
regime labels rather than any liquidity measurement, and it is Gen-5's G5-05A rediscovered. The zero
in this chain was correct, and is now *more* robustly correct than when it was written — it no longer
has a promising near-miss sitting behind it.

**[G10] One production strategy exists**, not two — the frozen momentum + sector-rotation book. The
Delivery overlay was counted here as the second on the strength of ARP's standalone validation; G8-09
subsequently found it does not improve the certified book and cannot be shown to, and Gen-10 T1-06
closed the independently-sized sleeve architecture as well. Delivery is a validated signal with no
deployment. Neither figure comes from AEP's engineering layer.

## 5. Reproduction and strengthening/weakening ledger

| Direction | Count | Examples |
|---|---|---|
| Findings strengthened by independent replication | **≥5** | Gen-5 F01 confirmed by MSRP I-04B (different methodology, same conclusion); Gen-5's canonical Sharpe reproduced exactly in 4+ separate scripts across generations; MSRP's `vol_52w` "specialness" confirmed by 3 independent measures (M-01B, M-02, M-03); AEP Paper A's redundancy analysis independently reproduces I-04B via a completely different computation |
| Findings weakened/narrowed on closer testing | **≥4** | MSRP's raw M-01 (all primitives "long memory") narrowed by M-01B; Gen-6's G6-01 "PARTIAL" narrowed to NO_POSITIVE_EVIDENCE; AEP Paper D's raw "RISING at monthly+quarterly" narrowed to "RISING, monthly only, marginally"; AEP Paper B Sub-study 1's M-04 finding shown NOT to generalize beyond its original specification |

---

## What this report does NOT claim
That the programme found more alpha than it did (it found two production strategies: momentum+sector
rotation and Delivery). That AEP's engineering layer is ready to deploy (it is not — zero validated
rules). That negative results are failures (13 self-caught corrections and ~10 named negative results are
treated here, as throughout the programme, as complete scientific outcomes).

## Recommendation

> **[G10 2026-07-31] Amended.** The recommendation below was right about *new discovery* and wrong
> about what remained. Gen-10 ran thirteen experiments on this record and found zero new alpha —
> exactly as this section predicted — while correcting eight verdicts. **The debt was never in the
> unexplored space; it was in the record itself.**
>
> The amended rule: freezing is correct for *discovery*, and is not a substitute for **periodic
> re-testing of what is already believed** — particularly anything already carrying a "corrected"
> label. See `RESEARCH_INFERENCE_STANDARD.md` for the six rules adopted in response, and Part IX of
> the monograph for why five appearances of one defect class were needed before it was named.

**Freeze the research programme.** Per the closure chain above, further iteration on the same
architecture (a Paper F, an M-06, another AEP prototype) would not be justified by the evidence — the
programme's own burden-of-proof principle, applied to itself: the next advance should come from new
evidence or a genuinely new research question, not from continuing to work the same material. See
`NORTHSTAR_HANDBOOK.md` (Volume II) for what is actually ready to run.

---
**Frozen 2026-07-25, alongside `MONOGRAPH.md` (Volume I) and `NORTHSTAR_HANDBOOK.md` (Volume II).**
