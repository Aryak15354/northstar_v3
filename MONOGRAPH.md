# The Evolution of the Northstar Research Programme

**Volume I. Frozen 2026-07-25.** This is the permanent scientific record of a single, continuous research
programme spanning Gen-2 through the Alpha Engineering Programme (AEP) — roughly six generations of work
unified by one discipline: pre-registration before code, correctness gates before trust, honest reporting
of negative results, and never silently rewriting history. This document does not repeat every number
from every experiment (those live in their own frozen records, cited throughout); it tells the story of
what the programme learned, in the order it learned it, and why each pivot happened.

---

## ADDENDUM (added 2026-07-25, after the original freeze — Part I below is unedited, per this
programme's own never-silently-rewrite-history rule)

**Archival work following this volume's original freeze identified an earlier phase this monograph did
not name: Gen-1, a Foundational Discovery Phase (dated 2026-07-16 through 2026-07-18), predating Part I
below.** Full detail: `ARCHIVE_DESIGN_REVIEW.md` Section 12b. In brief: before the Gen-2/3 registry
convention (`G2-`/`G3-` IDs) existed, an earlier research phase — using its own panel-based `F`-track
convention and a `LEDGER.csv` verdict scheme (`results/LEDGER.csv`, `results/RESEARCH_LOG.md`, and the
`f/`, `g/`, `m/`, `p/`, `cycle2/`–`cycle8/`, `newalpha/`, `trackx/`, `deepdive/` directories under
`results/`) — ran the factor search that discovered momentum as the one robust single-stock edge, tested
and rejected value/quality/accruals/sentiment/credit, and **produced `results/FROZEN_SPEC.md` — the exact
two-sleeve momentum-plus-sector-rotation benchmark every generation from Gen-4 onward treats as its
foundational, unquestioned reference point.** Every later generation cites Config-4 and the frozen
two-sleeve spec as a given; Gen-1 is where that given came from. A separate, earlier draft of the Gen-2
registry system also lives in this cluster (`results/alpha_registry/registry.jsonl`, timestamped one day
before the authoritative `results/gen23/registry.jsonl` version this monograph's Part I actually
describes) — a superseded pilot run, not a second independent research thread, noted here for
completeness but not itself a scientific finding.

This does not change any conclusion in Parts I–VII below — it adds one generation's worth of prior
context that this volume's original write-up, produced from the same-session working memory that had
already moved past Gen-1's chronological point, did not have in view. Read Part I's "the programme began
as a factor-search exercise" as picking up mid-story; Gen-1 is where the story actually starts.

---

## Part I — Genesis: What Predicts Returns? (Gen-2/Gen-3)

The programme began as a factor-search exercise: pre-register hypotheses, test them under a strict
multiple-hypothesis-testing discipline, keep only what survives. Of ~120 catalogued Gen-2/3 experiments
(`results/MASTER_EXPERIMENT_INDEX.csv`), the overwhelming majority were rejected for the ordinary reason —
no measurable information, confirmed by the framework working exactly as designed.

Two discoveries survived and mattered permanently. **Momentum** emerged as the durable, redundant,
four-way-measured signal that would anchor every subsequent generation. **Delivery percentage** emerged
as a second, independent, momentum-orthogonal signal (correlation 0.14) — real (true-OOS IC +0.033,
t=2.94, surviving ten adversarial certification tests) but structurally hard to deploy: its entire
tradable edge lives in non-F&O, non-shortable names (`results/gen23/DELIVERY_CERTIFICATION.md`). This
single fact — that Delivery was real but *inaccessible* under the deployment assumptions used to test
it — would not be resolved for another four generations, until the Alpha Recovery Programme (Part VI).

The methodological lesson banked here, still cited in every later generation: **high IC is not the same
as harvestable alpha.** The IC → monotonicity → turnover → capacity → cost chain has to be run every
time, not assumed. A second lesson, equally durable: null results must be checked for construction
artifacts before being trusted — Gen-3's first "null" FX-competitiveness test turned out to be a
broadcast-column bug, not a real absence of effect. This habit — suspect a clean result until it survives
a deliberate attempt to break it — becomes the programme's signature by Gen-5 and is still active,
unchanged, in AEP's final papers.

## Part II — Engineering: Building a Deployable Book (Gen-4)

Gen-4 asked whether cross-sectional information existed beyond momentum, sector, and delivery. The answer
was a clean, disciplined **no** — the "Gen-4 gate" closed with two important self-caught false positives
along the way (price-feature contamination in an early non-price test; pooled walk-forward inflation in a
capacity estimate), both corrected before being reported as findings, not after. This closure licensed
the frozen two-sleeve strategy — momentum (Config-4) plus sector rotation — that becomes the
programme's canonical, unit-of-measurement benchmark for every generation that follows.

## Part III — Economic Validation: When Do Strategies Work? (Gen-5)

Gen-5 is the programme's methodological center of gravity. Its central invention, the **Universal Oracle
Ladder**, formalized a discipline every later generation inherits: never trust a perfect-foresight number;
always report the realizable value after simulated forecast-skill degradation; gate promotion on a
pre-registered economic threshold (+0.15 realizable Sharpe), not a statistically-significant-but-tiny
number.

Gen-5's 23 permanent findings (`results/gen5/GEN5_MASTER_FINDINGS.md`) established Config-4's true
architecture: **momentum is the redundant, robust return engine; the short book is risk control, not
alpha, and its economic value is expressed as covariance reduction with momentum (F08) — not standalone
return.** Every dynamic-timing lever tested against this architecture (short-budget timing, gross-exposure
timing, sector-sleeve reallocation) passed its descriptive Stage-1 test and then **failed the same
economic gate** — not because the underlying economic facts were wrong, but because the realizable skill
needed to exploit them, after honest degradation, fell short of the threshold. Paper 2.5's meta-analysis
(M1–M5) explained why: near-zero mutual information between hand-engineered state and the correct weekly
action (F17) — a fundamental information limit, not a search failure (confirmed by exact exhaustive
search, F18).

Gen-5 closed with a full, disciplined audit — including catching and fixing a real registry ID collision
(G5-08B/C) during its own closeout, exactly the kind of self-inspection a genuine forensic close-out is
supposed to perform. Frozen v1.0, not committed to git without explicit request.

## Part IV — The Limits of Representation Learning (Gen-6)

Licensed by Gen-5's own finding that richer hand-engineered state helped (within bounds, F15), Gen-6
asked whether a *learned* representation could do better. Three architecture families — GRU/LSTM
(sequence), Autoencoder (self-supervised), and a declined PatchTST attempt (transformer, after a formal
interim review weighed both sides and estimated only 15–20% odds of reversing the conclusion) — were
tested under a purpose-built Representation Ladder. **All three found no positive evidence.**

The programme's single most important methodological catch of this era happened here: **the R0 dataset-
feasibility check's two apparently-positive metrics (near-perfect autocorrelation, R²=0.964) were almost
entirely a rolling-window construction artifact.** First-differencing collapsed the predictive-info R² by
71× (0.964→0.0134). This is the first appearance of what becomes a named, standing principle
(`MSRP_CHARTER.md`'s Rolling-Window Persistence Principle): *features built from overlapping rolling
windows inherit mechanical persistence from their own construction, and any temporal-structure claim must
survive a differencing or non-overlap transformation before being trusted.* This exact mechanism recurs —
and is caught again — in MSRP's Memory pillar (Part V) and in AEP's Paper D (Part VI).

A second permanent principle: relative improvement over a baseline is not sufficient; a model must also
clear an absolute-competence bar. G6-01's GRU pilot was mechanically "PARTIAL" until independent review
noticed both the GRU and its Ridge baseline had *negative* absolute out-of-sample R² — meaning the model
had merely overfit less badly, not learned anything real. Reclassified honestly, via addendum, not silent
edit.

Gen-6 closed itself, choosing not to spend its final transformer budget after an honest weighing of the
evidence — a complete scientific outcome per its own charter, not a failure.

## Part V — Market Structure: What Is the Market's Internal Structure? (MSRP)

Three consecutive representation-learning failures suggested a different question was more productive:
not "can a model solve this" but "what does the market's information structure actually look like."
MSRP is measurement-only by charter — no predictive models, ever.

**Phase 1 (Information)** found the market's predictable structure, within the engineered ontology
studied, organizes hierarchically: a **Persistent Volatility Regime** (structurally redundant and
behaviorally coherent — seven independent measurements converge on it) and a **behaviorally heterogeneous
momentum superfamily** (correlated but not coherent — `res_mom_52w_ex4w` is delayed and behaviorally
distinct from its own family members, independently confirming Gen-5's F01 via mutual information rather
than Shapley decomposition — two unrelated methodologies, same answer). Eighteen features compress to a
twelve-feature Greedy Information Basis, with a genuine, non-additive interaction effect
(`consistency_mom_26w`, dead standalone, second-largest incremental contributor once combined with
others) that becomes the programme's central interaction case study for the rest of the arc.

**Phase 2 (Memory)** is where the programme's self-correcting discipline is most visible in a single
thread. M-01's raw run classified *every* primitive as long-memory — including `beta_104w`, whose own
window is 104 weeks, an immediate red flag, self-caught before being reported. The corrected version
(M-01B) reversed most classifications: only `vol_52w` shows genuine memory, `ret_4w` shows classic
short-term reversal, `beta_104w` is effectively memoryless. M-02 found liquidity's memory is
**regime-locked** (real specifically in NORMAL_UP/STRESS, invisible when regimes are pooled — a second,
independent demonstration that averaging across states can hide a real, state-specific effect). M-03
required **two rejected null designs** before a properly-specified one (an AR(1)-matched null) confirmed
`vol_52w` and `amihud_13w` as genuinely persistent beyond simple linear smoothing. M-04 and M-05
established that `res_mom_52w_ex4w`'s own memory is **doubly conditional** — on volatility state (M-04,
falsifying the naive prior that trends persist *more* in volatile periods, not less) and on
`consistency_mom_26w`'s state (M-05, confirming the Interaction Persistence Hypothesis for the memory
dimension, not just the cross-sectional-information dimension I-05 established).

Phase 2 froze after M-05 by explicit, disciplined choice — not because ideas ran out, but because the
governing question (does memory itself have structure) had been answered, and continuing (an M-06, an
M-07) would have been experimentation for its own sake, not new science.

## Part VI — Recovery and Engineering: Making the Archive Useful (ARP + AEP)

Before the final synthesis, the programme conducted one last forensic pass, split into two genuinely
different questions sharing the same evidence base.

**ARP (Alpha Recovery Programme)** asked whether any prior rejection was actually a capacity/liquidity
casualty rather than a genuine failure. The founding hypothesis — that Gen-5's institutional-scale Oracle
Ladder had wrongly buried strategies that would work at smaller capital — was tested against the actual
141-entry archive and found **largely false**: Gen-5's real terminations (G5-05A/05B/04C) were Universal
Oracle Ladder economic-gate failures (insufficient realizable skill), a capital-scale-*independent*
finding, verified directly against the source document rather than assumed. **But the hypothesis held,
decisively, for the one case flagged all the way back in Part I**: the Delivery signal. Recovered and
validated for real — reproduction gate passed exactly against the 2026 certification, then extended with
a real per-trade cost model across thirteen capital levels from ₹5 lakh to ₹500 crore. The result was
genuinely non-obvious: net Sharpe **peaks around ₹5–10 crore**, not at the smallest capital tested, and
degrades gracefully rather than collapsing even at ₹500 crore (`results/ARP_DELIVERY/`).

**AEP (Alpha Engineering Programme)** asked a different question: what permanent economic knowledge did
the whole archive produce, independent of whether it was ever framed as a strategy? Its five papers
(A–E) form the programme's final, and most methodologically self-critical, chapter:

- **Paper A (Market State Ontology, ACCEPTED)** assembled seven state dimensions MSRP had measured
  separately into one specified, evidence-traced vector (`MARKET_STATE_SPECIFICATION_v1.md`) — including
  a real new computation (pairwise redundancy across the states' own time series) that independently
  reproduced I-04B's finding that `res_mom_52w_ex4w` is the ontology's most information-independent
  dimension, via a completely different method.
- **Paper B (Conditional Alpha, MODIFIED)** attempted to turn M-04's volatility-conditional finding and
  I-05/M-05's interaction finding into engineerable rules, and largely could not: the volatility-sizing
  idea failed its own pre-registered sensitivity and definition-robustness tests; the four candidate
  roles for `consistency_mom_26w` did not cleanly resolve, surfacing a genuine, unresolved tension between
  two different measurement methodologies (incremental mutual information versus direct return spread).
- **Paper C (Adaptive Portfolio Management, MODIFIED)** found a real, meaningful liquidity-conditional
  sizing effect (Sharpe 0.692→0.727) — flagged, correctly, as not yet validated to the same depth as
  Paper B's rejected idea, precisely to avoid trusting a bigger number just because it looked bigger — and
  a clean null on memory-conditional holding period and rebalancing.
- **Paper D (Decision Resolution Study, MODIFIED)** reused Gen-5's own information-theoretic engine at
  five decision resolutions and **caught its own artifact mid-analysis**: a dramatic-looking
  quarterly-resolution result was entirely small-sample estimator bias, invisible until a permutation-null
  control (built in response to recognizing the risk, not after being told) revealed only a narrow, marginal
  signal survives at monthly resolution.
- **Paper E (Confidence-Based Portfolio Allocation) was correctly DEFERRED** — its own pre-registered
  readiness rule required two of three input papers to be validated, and only one was. Refusing to build
  an impressive-looking architecture on unvalidated inputs is the same discipline the programme applied to
  itself one level up (Paper A was deliberately built as ontology before machine, not the reverse) —
  applied here to Paper E's own capstone ambition, and honored even when it meant not building the most
  exciting deliverable in the registry.

**AEP's real finding is not any single engineered rule — it is that MSRP's own robustness discipline,
applied one level up (from "is this a real measurement" to "is this a robust engineering input"), catches
real gaps.** Most candidates did not survive that harder bar on first attempt. This is reported as a
complete, valuable scientific outcome, not a shortfall — precisely the same stance the programme took
toward Gen-6's negative representation-learning results four generations earlier.

## Part VII — General Theory: What the Whole Arc Says

Read end to end, six generations converge on a small number of durable, cross-validated truths:

1. **Momentum is the one robust, deployable edge this programme found**, redundantly measured, requiring
   risk-management architecture (a short book, a crash overlay) rather than more alpha, to be
   institutionally deployable.
2. **The market has real, measurable internal structure** — a persistent volatility regime, a
   behaviorally heterogeneous momentum family, genuine (if narrow) memory, and real interaction effects —
   but that structure resists conversion into engineered decision rules more often than it yields to it.
   Both facts are permanent findings, not a contradiction: **a phenomenon can be real at the specification
   it was measured, and not generalize into a robust engineering input**, and telling the two apart
   requires deliberately trying to break every promising result before trusting it.
3. **Every methodological advance in this programme came from a self-caught correction, not an external
   audit** — the broadcast-column bug (Gen-3), the negative-oracle-ceiling bug (Gen-5), the registry ID
   collision (Gen-5), the rolling-window construction artifact (Gen-6, then twice more in MSRP), the
   flawed null designs (MSRP M-03), the wrong-series threshold bug (AEP Paper B), the small-sample MI bias
   (AEP Paper D). **A research programme's real discipline is measured by what it catches in itself, not
   by what it never gets wrong.**
4. **Capacity and liquidity, not raw predictive skill, buried the programme's one other real discovery**
   (Delivery) for four generations — a distinct failure mode from "no information," worth its own
   forensic pass precisely because it does not show up as a low t-stat.
5. **Knowing when to stop is itself a research skill.** Phase 2 froze after M-05, not because ideas ran
   out. Paper E deferred rather than building on hope. Gen-6 declined its own final budget after an honest
   weighing of costs and benefits. None of these stops were forced by running out of options — each was a
   disciplined choice to treat "we could keep going" and "we should keep going" as different questions.

---

## Part VIII — Gen-7: When Rigor Is Not Enough (added as a dated addendum, 2026-07-25)

**This Part was added after Volume I's original freeze.** Parts I–VII above are unedited, per this
programme's never-silently-rewrite-history rule. Gen-7 is a *separate, independent* research programme —
a new branch, not a continuation of Gen-1→AEP — but its outcome speaks so directly to Part VII's General
Theory that leaving it unrecorded here would make this volume misleading rather than merely incomplete.

Gen-7 (CAIT) broke the equity anchor every prior generation shared. Instead of asking what predicts
Indian equity returns, it asked whether information is *detectable in transit* between asset classes
before equities reflect it — a change of causal direction, not a variation on the prior question. Paper A
scanned 31 non-equity carriers across 10 weekly lags (310 tests) and reported, in its original verdict,
six multiple-testing-corrected survivors narrowing to three lockbox-validated Transmission Objects, all
emerging-market FX. Its most quoted moment was Crude Oil — the strongest candidate through seven of eight
laboratories — sign-flipping at the holdout and being rejected. That was written up as the ladder working
exactly as designed, and the generation's charter enshrined it as a founding proof.

**An independent audit found that neither headline claim survives contact with its own data.** The
permutation p-value had been computed in a form that returns exactly zero when an observed correlation
beats every draw; the six "FDR survivors" were precisely the six tests reporting p = 0. With only 500
permutations, the finest resolvable p-value is an order of magnitude coarser than the correction's own
rank-1 threshold — the procedure could not have produced a legitimate survivor at any observation.
Recomputed with a valid p-value and a calibrated heteroskedasticity- and autocorrelation-robust test,
**zero of 310 pairs survive, under both Benjamini-Hochberg and the dependence-robust
Benjamini-Yekutieli.** And the 53-week holdout that had "adjudicated" the promotions carried roughly 13%
power against a minimum detectable effect 2.6× larger than anything present: every lockbox confidence
interval included zero, five of six included their own pre-lockbox value, and the celebrated Oil sign-flip
turned out not to be a statistically significant change at all (p = 0.249). Three of six sign-agreements
is exactly what chance predicts.

Then the correction corrected itself. The first draft of the revised verdict recommended closing Gen-7's
discovery arc on "a clean, well-powered negative result" — until a positive control, injected on the
principle that a pipeline reporting no survivors must first be shown capable of reporting survivors,
revealed that the design detects an effect of 0.15 but misses one of 0.10. A full power curve put the
80%-power threshold at |r| = 0.154 while all six real candidates sat between 0.102 and 0.144, with mean
power of 40%. **The negative result was not well-powered either.** The honest verdict is neither
"transmission exists" nor "transmission does not exist" but *unresolved* — and that second self-correction
was disclosed rather than quietly folded in, exactly as Part VII's third truth would demand.

What Gen-7 adds to the General Theory is a genuinely new proposition, and an uncomfortable one:

> **Procedural rigor does not substitute for statistical power. A generation can honour every discipline
> it claims — pre-registration, an untouched holdout, verified freedom from look-ahead, correct ladder
> ordering, honest sequencing — and still learn nothing, because the gates it built were not powered to
> filter.**

Every prior generation's failures were failures of *ambition* meeting reality: momentum was real and
everything else mostly was not; learned representations found nothing beyond the engineered ontology;
dynamic-timing levers were real economically and unexploitable after honest degradation. Gen-7's failure
is different in kind. Its process was sound and its answer was empty, and the emptiness looked like a
finding for as long as nobody asked what the tests could detect. Part VII's third truth — that a
programme's discipline is measured by what it catches in itself — held once more, but only just, and only
because the audit asked a question none of the eight original laboratories had: *what effect size could
this have found?*

The practical residue is two standing amendments, now binding: every gate must publish its minimum
detectable effect **before** it runs, and any reported null must first demonstrate the procedure's own
detection capability. The one actionable gain from the entire re-analysis is that cutting multiplicity —
pre-registering a single lag per carrier rather than testing ten — raises power at the relevant effect
size from 31% to 60% **on the existing data, with no new data at all.** Gen-7 produced no validated
scientific object. It produced a sharper rule for what counts as evidence, which on this programme's own
stated values is not the lesser outcome.

Full record: `results/gen7/GEN7_STATUS_AND_FINDINGS.md` (findings G7-F01–F08),
`results/gen7/GEN6_GEN7_INDEPENDENT_AUDIT_2026_07_25.md` (the audit),
`results/gen7/PAPER_A_REVISED_VERDICT.md` (authoritative conclusions),
`results/gen7/paper_a_reanalysis/` (RA-001–RA-006, including the independent verification suite).

---

## Part IX — Gen-10: What the Record Got Wrong (added as a dated addendum, 2026-07-31)

*Parts I–VIII above are unedited, per this programme's never-silently-rewrite-history rule. This part
records what a successor generation found when it re-tested the record rather than extending it.*

Gen-10 set out to run the Tier-1 backlog of `Northstar_Remediation_Priority_Plan.md` — the ~460
catalogued hypotheses' residue of "statistically real but never economically gated" findings. It ran
thirteen experiments and produced **zero new deployable alpha, eight corrected verdicts, and three
permanent closures.** The certified book is unchanged.

That outcome is not the interesting part. The interesting part is *why* the backlog produced nothing:
**a meaningful share of it was never statistically real.** Not overfitted, not fragile — measured
wrongly, in ways that survived a freeze, an archive, a citation guide and this monograph.

### The four things that were wrong

**1. The unit of inference.** AEP Paper B computed t-statistics by pooling ~62,000 stock-weeks as
independent observations. Forward returns over *h* weeks overlap by construction and stocks within a
week share a market factor; the effective sample is ~1,030 dates. Corrected, Paper B's **CONFIRMED**
role (2b "Warns") becomes t = +0.57 with a sign that reverses on 53 weeks of lockbox data the paper had
truncated away and never used — while its recorded *near-miss* (2a "Confirms") becomes the stronger of
the two, and then closes on its own after eight further tests. **No role for `consistency_mom_26w`
survives.** Part VI describes this as "a genuine, unresolved tension between two measurement
methodologies." It was not a tension between methodologies. One of them had the wrong standard error.

**2. Verdicts issued without tests.** AEP Paper C gave ACCEPTED and POSITIVE verdicts to three of four
sub-questions on the strength of point estimates with **no standard error anywhere**. Supplying them:
Q3 — the one Part VI calls "a real, meaningful liquidity-conditional sizing effect" — is **paired
t = +0.50**, 0.18× its own 80%-power detection floor, and costs 3.26 %/yr of return. It is also not a
liquidity rule (it keys off regime labels; no liquidity-persistence measurement enters the decision),
its regime selection is wrong on its own terms (de-gearing in CRASH alone, or STRESS alone, both beat
the bundled rule — and STRESS is a regime the rule holds at full exposure), and it is **Gen-5's own
G5-05A rediscovered**, already TERMINATED_BY_GATE at three times the effect size. Q1/Q4 fall to
t = −1.75.

**3. Multiplicity not counted.** AEP Paper D's monthly result cleared its own permutation null by
5.0% and was recorded ACCEPTED. Across the five resolutions it was selected from, p ≈ 0.038 against a
Bonferroni threshold of 0.010 — it fails Bonferroni, BH and BY alike. Monthly is simply the resolution
where *n* is still large enough to keep the null tight while aggregation has lifted the measured MI: a
property of the null's shape, not an economic cadence. Gen-5's **F17 was never a resolution artifact**,
and is now settled across five cadences instead of one.

**4. Comparisons across different observation sets — five times.** This is the one that generalises
furthest, and it is the reason Gen-10 exists as more than a cleanup.

- Pooled stock-weeks (above).
- **Pooled universes.** `ret_13w`, `MOM60` and `DS-U-01` are one signal — per-date Spearman **0.969** —
  carrying three different archived verdicts. The cause is neither the signal nor the harness
  configuration: it is the *panel*. The enriched panel pools two groups of stocks differing
  systematically on both signal and forward return, so its cross-sectional IC (+0.0138) **exceeds the
  IC of either group alone** (+0.0086, +0.0050). **36%** of the disputed number was composition, not
  information. The artifact is coverage-dependent and therefore predictable — it cost the broad
  momentum signals 30–40% and the delivery family ~0%, exactly as forecast before those tests ran.
- **Truncated date sets.** G8-07 measured `NON_FNO_TAIL` on **712 weeks** against every other tier's
  1,070, because `backtest` skips a date when a tier is too thin. The excluded weeks are harder for
  everyone (`ALL` scores +0.58 there against +1.01 on the common window), so the short-window tier
  collected a free ~+0.43 Sharpe. Net of cost, across all three configs, on a common index: its lead
  collapses from **+0.299 to +0.042**.
- **Zero-filled date sets.** G8-11 — which *corrected* G8-07 by moving the finding to that same tier —
  reports all four tiers at 1,070 weeks, which reads as clean coverage. It is not: `backtest` never
  skips a date, recording `port = 0.0` whenever a tier cannot form a book. **41.8% of NON_FNO_TAIL's
  sample is synthetic zeros**, the tier being *empty by construction* through 2005–09 and 2013 (the
  early panel has fewer than 190 names, so nothing is outside the F&O universe). The tier sits flat at
  0% through the whole GFC while `ALL` takes the drawdown. **Zero-fill is worse than truncation:** it
  awards the favoured group a risk-free return through the hardest periods rather than merely omitting
  them.
- **Mismatched estimation eras**, in Gen-10's own first attempt at a Delivery sleeve comparison.

Six rules were adopted in response (`RESEARCH_INFERENCE_STANDARD.md`), each carrying the incident that
motivated it. The precedent is this programme's own: the Rolling-Window Persistence Principle was
elevated to charter law on its *second* appearance. This one had appeared five times.

### What this changes in Parts I–VIII

| claim | status |
|---|---|
| Part VI: AEP Paper B's four roles "did not cleanly resolve," a methodological tension | **superseded** — one role was a bad standard error; none survives |
| Part VI: Paper C found "a real, meaningful liquidity-conditional sizing effect" | **withdrawn** — t = 0.50, and not a liquidity rule |
| Part VI: Paper D found "a narrow, marginal signal survives at monthly resolution" | **withdrawn** — fails correction for the five resolutions tried |
| Part VI: Delivery "recovered and validated for real," capacity peak ₹5–10cr | **stands** — reproduced by a third independent route. But see below |
| Part VIII: Gen-7's transmission question left open, underpowered | **closed** — 0/15 survivors at adequate power, max \|r\| = 0.014 against a 0.11 floor, beta confound removed by design |
| Part VII §1: momentum is the one robust deployable edge | **stands, reinforced** — 14 deep-search items faced their first out-of-sample split and produced nothing |
| Part VII §2: real structure resists conversion into engineered rules | **stands, reinforced** |
| Part VII §4: capacity buried Delivery, the programme's one other real discovery | **amended** — see below |
| Part VII §3: every methodological advance came from a self-caught correction | **amended** — see below |

**On Part VII §4.** Delivery remains a validated signal, and Gen-10 reproduced its capacity curve
independently. What changed is that **both** integration architectures are now closed: G8-09 showed the
overlay does not improve the certified book and cannot be shown to; Gen-10 showed the independently
sized *sleeve* — the architecture G8-09 explicitly left untested — does not promote either, because at
the lower bound of its own confidence interval the optimal allocation is zero at every capital band. A
premise underlying the sleeve case also turned out to be a misreading the programme repeated in three
documents: Delivery's **0.14 correlation with momentum is signal orthogonality**, ranking against
ranking. The realised correlation of the two long-only sleeves' *returns* is **0.842** — two long-only
Indian equity books share market beta whatever their signals do. There was never much diversification
to harvest. So the honest amendment: capacity did bury a real signal, and the signal is real, and it
still has no deployment.

**On Part VII §3, which needs the most honest amendment.** The claim was: *"Every methodological
advance in this programme came from a self-caught correction, not an external audit."* Gen-10 is
internal in the sense that matters least — same repository, same author — and external in the sense
that matters most: **a different generation, deliberately re-testing predecessors rather than extending
them.** Every defect above survived its own generation's review, a programme freeze, an archive
build with permanent IDs and checksums, a citation guide, and this monograph's own composition. Some
sat in the record for months and were cited downstream as established.

The amended version: *a programme catches its own errors only for as long as something keeps
re-testing it. Freezing a record protects it from silent revision; it does not make it true.* The
Rolling-Window Persistence Principle was caught twice by the generations that made it. The
index-alignment defect took five appearances and a dedicated remediation generation. **The difference
between those two is not diligence — it is that one produced a visibly wrong number and the other
produced a plausible one.**

### What Gen-10 confirms rather than corrects

Three checks came back clean, and they matter more than the corrections because they bound the damage:

- **The Gen-2/3 deep-search battery is statistically sound** — six signals recomputed independently,
  6/6 within 0.1 t-units of their archived values. Its problem was never the statistic; it was that no
  item had ever been evaluated out of sample (`"lockbox_used": false` on all 28). Given that split,
  fourteen deduped items produced no new alpha, three "survivors" proved to be one already-deployed
  signal, and the battery's largest |t| — DS-F2-03 at −8.91 — turned out to be Gen-1's already-killed
  reversal trade wearing an interaction label, at **4091 %/yr turnover against A04's 4187 %/yr**.
- **Delivery's own artifacts are clean**, checked specifically because it is the second most
  load-bearing finding in the programme: identical date sets (338/338), explicit intersection in G8-09.
- **G9-01's liquidity gradient is clean**, recomputed on a common cell set: Spearman **−0.818,
  p = 0.0038**, identical to three decimals. It was previously asserted unaffected; it is now verified.
  And it is the piece that survives the tier correction intact — a *continuous* gradient across
  liquidity deciles always sat oddly beside a *discrete* F&O-boundary story, and fits a continuous
  size/ADV-constraint story better. The mechanism relocates from shortability to capital and impact
  cost. That is a real update, not a downgrade.

One genuinely new result came out of the re-testing, and it is a constraint rather than an
opportunity: **the small/illiquid tier advantage does not exist in the certified production book.**
Under `config4_secbal40_short` both tiers are *negative*. The F&O-only short leg cannot hedge a long
book drawn from a disjoint non-F&O universe, so it stops being a hedge and becomes an uncorrelated
drag. Any small-cap tilt of Config-4 must redesign the short leg first — which makes it a different
strategy, not a tilt.

### The lesson Part VII did not have

Part VII §5 said knowing when to stop is a research skill, and cited three disciplined stops. Gen-10
adds the complement, which is less comfortable: **knowing when to go back.** The programme's instinct
after MSRP was to synthesise rather than run more experiments, and that instinct was right — but the
thing most worth doing was neither synthesis nor new discovery. It was re-testing findings that already
carried a "corrected" label. G8-11's correction of G8-07 is the sharpest case: it *felt* checked,
because someone had already checked it, and it was the single most wrong thing in the record.

**A finding that has been corrected once is not thereby more trustworthy than one that never has.**

Full record: `results/gen10/GEN10_SYNTHESIS.md` (findings G10-F01–F40), `GEN10_REMEDIATION_CHARTER.md`
(the pre-registrations, written before results), `RESEARCH_INFERENCE_STANDARD.md` (the six rules),
`archive_addenda/GEN10_ADDENDUM_001–004.md` (corrections against permanent IDs, Archive v1.0 unmodified
per `archive/GEN7_INTERFACE_RULE.md`), and `REMEDIATION_PLAN_FEASIBILITY_REVIEW.md` (the review that
re-ordered the plan before any of it was run).

---

## Appendix — Where every claim in this volume is sourced
`GEN5_RESEARCH_CONSTITUTION.yaml`, `GEN6_RESEARCH_CHARTER.md`, `MSRP_CHARTER.md`, `ARP_CHARTER.md`,
`AEP_CHARTER.md`, `AEP_MASTER_RESEARCH_PLAN.md` (the five governing documents); `docs/GEN5_DECISION_LOG.md`,
`docs/GEN6_DECISION_LOG.md`, `docs/MSRP_DECISION_LOG.md`, `docs/ARP_DECISION_LOG.md`,
`docs/AEP_DECISION_LOG.md` (the chronological decision records); `results/MASTER_EXPERIMENT_INDEX.csv`,
`results/GEN6_EXPERIMENT_INDEX.csv`, `results/MSRP_EXPERIMENT_INDEX.csv`,
`results/ARP_MASTER_ALPHA_REGISTRY.csv`, `results/AEP_DISCOVERY_CENSUS.csv` (the machine-readable
ledgers); `results/gen5/GEN5_MASTER_FINDINGS.md`, `results/msrp/PHASE1_SYNTHESIS_FROZEN.md`,
`results/AEP_SYNTHESIS_FROZEN.md`, `results/ARP_STAGE1_CENSUS_AND_FINDINGS.md`,
`results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md` (the frozen synthesis documents this volume draws from
directly). `docs/RESEARCH_PROGRAMME_STATUS.md` remains the live cross-programme index for anyone
continuing this work after this volume is read.

---

**Volume I's Parts I–VII are frozen as of 2026-07-25; Part VIII was appended the same day as a dated addendum, and Part IX on 2026-07-31 — both unedited above.**

**Parts I–VIII contain claims that Part IX corrects. They are deliberately left as written.** Read Part IX before relying on any AEP result, on Gen-7's status, or on the universe-tier story.

**Volume I is frozen as of 2026-07-25. Nothing in this research programme has been committed to git
without explicit request — this remains a working-tree record until the user decides otherwise.**
