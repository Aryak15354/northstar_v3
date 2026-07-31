# Research Programme Status — Continuity Document

**Purpose: if this session ended and a new one started with zero prior context, this document alone
should make the full state of the research programme reconstructable.** Originally written 2026-07-24;
last updated **2026-07-31** (Gen-10 remediation; see the section immediately below). Previously updated 2026-07-28 after ALL FIVE WAVES of the new Gen-2/3 macro-data acquisition (two
spreadsheets, 155 domestic indicators) were built, verified, and run to completion. Read this
top-to-bottom; every claim is sourced to a file that still exists.

---

## READ FIRST: Gen-10 Remediation — eight verdicts corrected (2026-07-31)

**A successor generation re-tested this record rather than extending it. Parts of what is written
below and in the frozen volumes are wrong.** Thirteen experiments, **zero new deployable alpha, eight
corrected verdicts, three permanent closures.** The certified book is unchanged.

**Start here:** [`results/gen10/GEN10_SYNTHESIS.md`](../results/gen10/GEN10_SYNTHESIS.md), then
`MONOGRAPH.md` Part IX for the narrative and `RESEARCH_INFERENCE_STANDARD.md` for the six rules
adopted in response.

What changed, in one table:

| area | corrected to |
|---|---|
| **AEP Papers B, C, D** | all three → **REJECTED**. Paper B's CONFIRMED role rests on a pooled stock-week SE and reverses out of sample; Paper C's Q3 is **t = 0.50** with no test ever computed and is Gen-5 G5-05A rediscovered; Paper D's monthly fails correction for the five resolutions it was selected from. **Zero AEP papers now carry a positive engineering result.** |
| **Gen-7 (CAIT)** | **CLOSED, negative, at adequate power.** 0/15 survivors, max \|r\| = 0.014 against a 0.11 floor, beta confound removed by design. H-A2/A3/A4 close with it. |
| **Delivery** | signal **stands**; **both integration architectures closed** (overlay G8-09, sleeve Gen-10 T1-06). Not a production strategy. Its 0.14 correlation with momentum is *signal* orthogonality — the sleeves' **returns correlate at 0.842**. |
| **Universe tiers (G8-07/G8-11)** | resolves as a **monotone size gradient**, not a contest between tiers. Large caps lose **0/17** signals (p=0.00002); both smaller tiers win **15/17** (p=0.00235 each). G8-07's non-F&O lead was ~86% a date artifact; G8-11's zero-fill understated the micro-cap tier (5/17 → 15/17 when corrected). Mechanism is capital/impact cost, not F&O shortability. **Long-only — absent from the certified book.** G9-01 unaffected, verified. |
| **Deep-search battery** | all 28 items were full-sample (`"lockbox_used": false`). 14 given a first out-of-sample split → **zero new alpha**. Its largest \|t\| (DS-F2-03, −8.91) is Gen-1's already-killed reversal trade at 4091 %/yr turnover. |
| **Production strategies** | **2 → 1** (frozen momentum + sector rotation). |

**Binding on all future work:** every experiment routes inference through
`src/research/gen10/inference.py`. Six rules in `RESEARCH_INFERENCE_STANDARD.md`, each carrying the
incident that motivated it.

**The one lesson worth carrying:** the sharpest error in the whole record sat inside a finding that
already carried a *"corrected"* label. **A finding that has been corrected once is not thereby more
trustworthy than one that never has.**

**The backlog is now empty.** Everything listed as open on 2026-07-31 was subsequently run:

| was open | outcome |
|---|---|
| G5-08A/B/C/D + G5-09 (never run) | **0/5 promote** (T1-17). Gen-5's sequencing rule vindicated. Risk parity / shrinkage are real but sub-gate (+0.06 vs a +0.15 bar) |
| MSRP's three unopened pillars | **Geometry + Economic Limits run; Networks does not open** by its own charter gate (T1-18) |
| Paper C Q2 | **CLEARS its bar** — the one Gen-10 revision that goes upward (T1-15) |
| G2-B03b | **REJECTED**, wrong-signed, 46–59% composition artifact (T1-16) |
| duration/rates channel | **Covered and null.** Its blocker was receiver size (Real Estate: 10 names/date), not history length — correcting T1-10's own diagnosis (T1-16) |
| SMALL_ADV_Q1 on the longer window | **Holds** at +0.228 across 1,070 weeks, identical date index verified (T1-14) |

**The closing statement:** the attainable ceiling in the 15-feature basis is IC **+0.141**; the
deployed book captures **20%** of it. Nominally 5× headroom — but eighteen experiments tried to claim
it and none survived out of sample. **The binding constraint is estimation, not information.** A
genuinely new data source is the one route that bound does not close.


---

## New: Gen-2/3 macro-data programme — ALL 5 WAVES COMPLETE (2026-07-28)

**`MACRO_DATA_EXPERIMENTATION_PLAN.md`'s full 5-wave plan is now closed.** 17 experiments
registered (`A23-RETEST`, `G2-C01–C05`, `G2-F01–F04`, `G2-G01–G05`, `G2-H01`, `G2-I01`), none
reaching VALIDATED_ALPHA or DEPLOYABLE_SLEEVE, three legitimate DESCRIPTIVE_FINDING nulls
(G2-C05, G2-G03, G2-I01), one INCONCLUSIVE (G2-C03), the rest REJECTED. **The honest headline:**
155 domestic macro indicators across credit, rates, fiscal, real-economy, and valuation channels,
tested with real statistical power, add no tradeable signal beyond what this programme already
knew from price/sector/delivery data — a complete, decisive answer, not a shortfall. START HERE
for this thread: `docs/gen23_protocols/WAVE5_MACRO_REGIME.md`'s closing section links all six
wave documents.


`MACRO_DATA_EXPERIMENTATION_PLAN.md` (repo root) lays out a 5-wave plan to test 155 domestic macro
indicators against the existing Gen-2 constitution (`GEN2_GEN3_RESEARCH_CONSTITUTION.yaml`) — reusing
the G2-C family and adding new G2-F/G/H families.

- **Wave 0 (PIT foundation)** — done: `docs/gen23_protocols/WAVE0_PIT_FOUNDATION.md`, built by
  `scripts/gen23/build_macro_pit_dataset.py`, consumed via `src/research/gen23/macro_loader.py`, data
  in `data/macro/gen23/`.
- **Wave 1 (Credit Transmission — A23-RETEST + G2-C01–C05, 6 hypotheses)** — done, all six
  pre-registered, certified, run, recorded (`results/gen23/experiments/{A23-RETEST,G2-C01..C05}/`):
  `docs/gen23_protocols/WAVE1_CREDIT_TRANSMISSION.md`. **None of the six reached RESEARCH_SIGNAL** —
  A23-RETEST REJECTED with real statistical power (full 2005-2026 vs. the original's thin 2019-25
  data), closing the credit-transmission-via-sector-tilt question rather than leaving it open. G2-C05
  produced a legitimate null (momentum's IC doesn't meaningfully depend on banking-system state).
  Required building `src/research/gen23/macro_timeseries_harness.py` (a new time-series evaluation
  module) since these are national broadcast series, not cross-sectional signals. Two things were
  caught and fixed before any verdict was drawn: a self-canceling "sign-flip" placebo bug, and a
  data-quality finding (isolated ~2x doubling artifacts in the M3/credit-to-commercial-sector series).
- **Wave 2 (Monetary Policy & Rate Regime — G2-F01–F04, 4 hypotheses)** — done, all four
  pre-registered, certified, run, recorded (`results/gen23/experiments/G2-F0{1,2,3,4}/`):
  `docs/gen23_protocols/WAVE2_MONETARY_POLICY.md`. **All four REJECTED** — real policy rate,
  term-structure slope, rate-cycle phase (vs. a Sleeve-2-proxy rotation book), and T-bill spread
  dislocation (incl. a G-01-style crash-catch diagnostic, 1.29x lift vs. G-01's own 28% catch rate)
  all carry no detectable weekly market-timing signal, despite this being the plan's own "safest
  family to build" (100%-complete, zero-revision-risk series). A real MHT-accounting bug was caught
  and fixed this Wave (hardcoded `hypotheses_searched=6` leaking from Wave 1's runner into Wave 2's
  calls, corrected in the registry before this doc was written).
- **Wave 3 (Fiscal & Real-Economy Impulse — G2-G01–G05, 5 hypotheses)** — done, all five
  pre-registered, certified, run, recorded (`results/gen23/experiments/G2-G0{1..5}/`):
  `docs/gen23_protocols/WAVE3_FISCAL_REAL_ECONOMY.md`. **Four REJECTED, one DESCRIPTIVE_FINDING** —
  fiscal-deficit trajectory, GDP acceleration, WPI-CPI wedge, and HPI acceleration all carry no
  detectable signal; G2-G03 (a macro-level retest of E07/E08's "momentum dominates fundamentals")
  found momentum's IC is directionally *strongest* during GDP deceleration, not weakest, though not
  individually significant. Every result in this Wave is mechanically capped `CERTIFIED-BOUNDED`
  (a new `_apply_revision_ceiling` enforcement added this Wave, since `fiscal_deficit_cga`,
  `gdp_quarterly`, and `wpi_all` are all `revision_prone` per Wave 0) — this is now a structural
  property of the pipeline, not something to remember by hand.
- **Wave 4 (Market-Cap-to-GDP Valuation Regime — G2-H01, bonus, 1 hypothesis)** — done, pre-
  registered, certified, run, recorded (`results/gen23/experiments/G2-H01/`):
  `docs/gen23_protocols/WAVE4_MARKET_CAP_TO_GDP.md`. **REJECTED (CERTIFIED-BOUNDED)** — India's
  "Buffett Indicator" (BSE market cap / annualized GDP) carries no significant weekly market-
  timing signal (HAC-t=+1.38). The secondary G2-H02 diagnostic (does it add crash-catch
  information beyond G-05's actual price-only rule) showed a +6.8pp lift, disclosed with its own
  honest limitation (an OR-combination diagnostic that can only help or tie by construction, not
  a rigorous incremental-value test) — reported, not chased, per the plan's own framing for this
  explicitly bonus/one-test wave.
- **Wave 5 (Macro-Conditioned Regime Definition — G2-I01, 1 consolidated test of 3 candidates)**
  — done, pre-registered, certified, run, recorded (`results/gen23/experiments/G2-I01/`):
  `docs/gen23_protocols/WAVE5_MACRO_REGIME.md`. **DESCRIPTIVE_FINDING (nuanced null)** — tested
  credit-impulse state, rate-cycle phase, and term-structure inversion against G-01's own crash-
  catch reference points (3% HMM, 28% simple price rule). Credit-impulse state caught 15.9% of
  worst-decile weeks (1.59x its own baseline, beats the HMM) but none of the three candidates beat
  the simple price rule. Per the plan's own section 7, this null is exactly as valuable a finding
  as a positive result — it closes off "maybe a smarter macro regime detector would help G-05" as
  a category, with actual evidence rather than assumption.

This is a separate, additive thread; it does not change any verdict below. The macro-data
programme's own closing synthesis is at the end of `docs/gen23_protocols/WAVE5_MACRO_REGIME.md`.

---

## Gen-7 is active but its discovery arc is HALTED (read this first if you're picking this up fresh)

**Gen-7 — Cross-Asset Information Transmission Programme (CAIT)** — `GEN7_RESEARCH_CHARTER.md` (v1.0,
Frozen 2026-07-25), `docs/GEN7_DECISION_LOG.md`, `docs/GEN7_CHARTER_AMENDMENTS.md`. Founding Research
Programme, parent: None. Explicitly independent of Archive v1.0 — inherits no hypotheses from Gen-1
through AEP, only engineering standards. Central question: can information be detected while still
travelling through financial markets, before it is fully reflected in Indian equities. Standing rule: no
equity-derived feature may be an explanatory variable during discovery.

**START HERE: `results/gen7/GEN7_STATUS_AND_FINDINGS.md`** — Gen-7's synthesis document (G7-F01…F08).

### Current state, in one paragraph
Paper A ran fully (8 laboratories, TD-001…TD-075) and originally reported 6 FDR survivors and 3
lockbox-validated Transmission Objects. **An independent audit on 2026-07-25 found both headline
procedures invalid, and corrected re-analysis overturned the conclusions.** There is **no validated
scientific object in Gen-7**. Paper B's Laboratory 1 executed correctly (TS-101–106) and promoted
`NW-001`, which is now **SUSPENDED** because its edges were demoted. **Laboratory 2 is blocked.**

### What went wrong, and what the corrected answer is
- **CRITICAL-1.** Lab 2's permutation p-value was floored at exactly 0.0 (valid form is `(1+k)/(N+1)`).
  The "6 BH-FDR survivors" were exactly the 6 tests reporting p=0.0. With 500 draws the finest resolvable
  p-value (1/501) is an order of magnitude coarser than the BH rank-1 threshold (0.05/310) — the design
  could not have produced a legitimate survivor. **Corrected: 0 of 310 survive BH *or* BY.**
- **CRITICAL-2.** The 53-week lockbox had ~13% power and a minimum detectable effect 2.6× larger than
  anything present. All six lockbox CIs include zero; five include their own pre-lockbox value; 3-of-6
  sign agreement is exactly the chance expectation (binomial p=1.000). **Crude Oil's "decisive" sign
  flip is not a significant change (p=0.249)** — the Charter's own founding-proof narrative, since
  rewritten (§3.1).
- **And the null is UNRESOLVED, not an absence.** The design's 80%-power threshold is |r|=0.154 while all
  candidate effects sit at 0.102–0.144; mean power 40%. This falsified the re-analysis's *own* first
  recommendation ("close on a clean, well-powered negative result") — disclosed, not silently revised.
- Also fixed: two incompatible TC-numbering conventions across the corpus; a false "no redundancy edges"
  claim contradicted by Lab 3's own data; transfer entropy reported with no null model; an MI estimator
  that floored to 0.0 and whose failures were used downstream as negatives.

### Verification status
`RA-005` independently verified all four foundations — **22/22 checks** against external references
(SciPy's own FDR implementation, the Benjamini-Hochberg 1995 published worked example, closed-form AR(1)
long-run variance, an end-to-end raw-data rebuild matching Lab 1 to 0.00e+00, and a positive control
proving the pipeline detects injected effects at r≥0.15).

### The one concrete gain
Pre-registering **one lag per carrier (m=31 instead of 310)** raises power at r=0.11 from **31% → 60% on
the existing data with no new data at all** — the single actionable methodological result of the whole
re-analysis. More data alone is not viable: r=0.11 at 80% power with m=310 needs ~34 years against the
21 available, and the lockbox is spent.

### Governance changes adopted
- **Amendment-002** — power disclosure is a precondition for a gate: every gate must publish its 80%
  minimum detectable effect and its finest resolvable statistic *before* running.
- **Amendment-003** — detection capability must be demonstrated before any null is reported.

### The exact next action
**A decision, not an experiment.** Choose between: (1) record the discovery question as UNRESOLVED with
stated power requirements (recommended); (2) redesign for power — multiplicity reduction first, then a
sector- or stock-level receiver universe — and re-run; (3) re-scope Paper B to *candidate* objects
(low value; TS-105 already showed a 3-object network cannot support structural inference).
**"Proceed as planned" is not among them.**

**`archive/` was NOT touched by any of this** — per `GEN7_INTERFACE_RULE.md`.

---

## Gen-1 → AEP: FROZEN, archived, historical evidence only (unchanged since 2026-07-25, read below for
detail)

**THE GEN-1 THROUGH AEP RESEARCH PROGRAMME IS FORMALLY FROZEN AND ARCHIVED, as of 2026-07-25** (Gen-7,
above, is a new and separate active programme, not a continuation of this one). Gen-1 through AEP are
all closed. Three top-level deliverables now exist and are the fastest way to get oriented, in this
order:

1. **`MONOGRAPH.md` (Volume I)** — the full research narrative, Gen-2 through AEP, 7 parts, fully cited.
   Read this for *why* things happened in the order they did.
2. **`PROGRAMME_VALIDATION.md`** — the quantitative meta-validation. 141 experiments/analyses catalogued
   across the whole programme (70 permanently retired, 35 not-a-rejection, 29 economic-law content, 3
   deployable-alpha registry rows behind 1 real discovery). **13 distinct self-caught methodological
   corrections** enumerated across all 6 generations (never found by external review — every one caught
   by the programme applying its own stated discipline to its own results). **~46 total permanent
   findings.** The closure chain's honest headline: 8 AEP engineering hypotheses were catalogued, 4 papers
   were actually executed, and **zero cleared the bar for a validated, production-ready engineering
   rule** — reported plainly, not softened. **Two production strategies exist**, and neither came from
   AEP's engineering layer: the frozen momentum+sector-rotation book (pre-dates AEP) and the Delivery
   overlay (recovered via ARP). Ends with an explicit recommendation to freeze the programme.
3. **`NORTHSTAR_HANDBOOK.md` (Volume II)** — the operations manual, no research narrative. Frozen
   portfolio spec, the Delivery overlay's operating summary (recovered but NOT yet portfolio-integrated —
   still the one open item), risk architecture, capacity curves, execution rules, rebalancing, a
   maintenance schedule, and an operating-procedures section for common future situations (a sleeve
   underperforming, someone proposing a new dynamic-timing overlay, "just one more experiment"). This is
   what someone would actually use to run the strategy.

**What this means going forward:** per `PROGRAMME_VALIDATION.md`'s own recommendation, no further
iteration on the existing Gen-2→AEP architecture is warranted — the next advance needs new evidence or a
genuinely new research question, not another paper, prototype, or experiment on the same material. If a
future session is asked to "continue the research," the correct response is to read the three documents
above first and ask what NEW question is being posed, not to resume Papers B/C/D-style engineering on
what's already been tested and found wanting.

**Nothing in this entire programme has ever been committed to git.** All work is in the working tree.
Ask before any git action.

### How the programme got here (chronological summary — full detail in Parts 1-6 below)
- **Gen-5: CLOSED, v1.0** (content label, not a git tag). `GEN5_FINAL_RELEASE.md`.
- **Gen-6: Paper 1 CLOSED (final).** Three representation-learning families rejected; a formal Interim
  Review declined the final transformer budget. `results/gen6/PAPER1_INTERIM_REVIEW.md`.
- **MSRP: Phase 1 FROZEN v1.1, Phase 2 (Memory) FROZEN as of M-05.** `results/msrp/PHASE1_SYNTHESIS_FROZEN.md`.
- **ARP: Stage 1 census complete, Delivery family RECOVERED AND VALIDATED for real** (correctness gate
  reproduces the original certification exactly; a real-cost capacity ladder across 13 levels, ₹5L–₹500cr,
  found net Sharpe peaks ~₹5–10cr and degrades gracefully, not a cliff, to ₹500cr). `results/ARP_DELIVERY/`.
- **AEP: 5 Papers (A-E) all executed/deferred and frozen.** Paper A (Market State Ontology) ACCEPTED, with
  a genuine new computation (redundancy analysis across 7 state dimensions) that independently
  cross-validated an MSRP finding via a different method. Papers B, C, D all MODIFIED — each produced a
  real, honestly-reported negative or partial result after catching its own methodological problem first
  (a wrong-series bug in Paper B, a small-sample MI-estimator bias in Paper D). Paper E was correctly
  DEFERRED without writing any code, because its own pre-registered readiness rule wasn't met.
  `results/AEP_SYNTHESIS_FROZEN.md`.
- **`MONOGRAPH.md`, `PROGRAMME_VALIDATION.md`, `NORTHSTAR_HANDBOOK.md` written and frozen 2026-07-25** —
  the three closing deliverables described above.

---

## Part 1 — Gen-5 (Config-4 portfolio-state research). CLOSED.

**What it was:** research into whether Config-4 (the frozen momentum+shorts+G-05 strategy, canonical
Sharpe 0.8471, panel `d858fb42`, commit `516c2df`) could be improved via dynamic portfolio-state levers.

**How it ended:** Five B1 candidates tested under the Universal Oracle Ladder (short budget, gross
exposure, sleeve allocation, vol target, opportunity forecasting). Three (G5-05B, G5-05A, G5-04C)
reached the economic gate and failed it — ceilings clustered tightly at +0.153–0.165 Sharpe, all
collapsing under realistic skill degradation. Two (G5-06A, G5-06B) failed at the descriptive stage.
Paper 2.5 (meta-experiments M1–M5) explained *why*: mostly a fundamental information limit (near-zero
mutual information between hand-engineered state and weekly action), not tooling — validated by exact
exhaustive search (M5) proving the ceilings were true global optima, not optimizer artifacts. Paper 3A
(capacity) and partial 3B (cost/execution) extended the economic picture. A full closeout was executed:
audits, manifests, due diligence, retrospective, final release.

**Key permanent findings (F01–F23), governance rules, and the full experiment ledger:**
- `GEN5_MASTER_FINDINGS.md` — 23 numbered findings, each with confidence/limitations.
- `GEN5_PROGRAMME_FREEZE.md` — frozen permanent findings, terminated levers, open questions.
- `GEN5_RETROSPECTIVE.md`, `GEN5_DUE_DILIGENCE.md`, `GEN5_FINAL_RELEASE.md` (v1.0 counts/closeout).
- `docs/GEN5_DECISION_LOG.md` — the full chronological decision record (largest single log in the repo).
- `results/MASTER_EXPERIMENT_INDEX.csv`, `results/gen23/registry.jsonl` — the Gen-2 through Gen-5
  experiment registry (append-only; includes a documented ID-collision correction, G5-08B/C → G5-D01/D02).
- `GEN5_RESEARCH_CONSTITUTION.yaml` — the full rule set (Oracle Ladder O1–O7, Universal Oracle Ladder
  Framework U1–U6, burden-of-proof principle, portfolio-as-unit-of-analysis).

**Why Gen-5 ended and Gen-6 began:** the research object changed from "can Config-4 be improved" to "does
representation learning find information beyond what Gen-5's hand-engineered ontology already captures"
— licensed by Paper 2.5's own finding (M2: richer hand-engineered state moved ceilings materially, but
only within a bounded band).

---

## Part 2 — Gen-6 (representation learning). Paper 1 CLOSED.

**Charter:** `GEN6_RESEARCH_CHARTER.md`. Central question: can a *learned* representation beat the Gen-5
ontology, under the same Oracle Ladder discipline extended with a new Stage −1 (Representation)?
Five planned papers, each with a hard stop; only Paper 1 (Learning Economic State Representations) ran.

**The Representation Ladder (R0→R4)** governed Paper 1 — see the charter for the full stage table.

**What happened, in order** (full detail in `docs/GEN6_DECISION_LOG.md`, ledger in
`results/GEN6_EXPERIMENT_INDEX.csv`):
1. **G6-00 (Stage R0A):** dataset-feasibility check, score +2 of 5 pre-registered metrics → INCONCLUSIVE.
2. **G6-00B (Stage R0B):** independent review suspected the two passing metrics (ACF, predictive-info R²)
   were construction artifacts (rolling-window overlap). Corrected on first differences: predictive-info
   R² **collapsed 0.964→0.0134 (71×)** — confirmed artifact. ACF survived, reduced but real (100%→48.6%
   pairs), cross-validated by non-overlapping resampling. Score +1 → still INCONCLUSIVE, but decisive and
   far more honest. **Stage R0 formally frozen** (`results/gen6/G6-00/STAGE_R0_FREEZE.md`), authorizing
   exactly one minimal G6-01 pilot.
3. **G6-01 (GRU, sequence family, architecture 1/2):** mechanically PARTIAL, but both the GRU (R²=−0.034)
   and its Ridge baseline (R²=−0.102) had **negative absolute out-of-sample R²** — the "pass" was
   relative only. **Reclassified "NO POSITIVE EVIDENCE"** on independent review. This produced a
   **permanent charter principle**: relative improvement alone is insufficient; every future gate
   requires both relative AND absolute competence, defined in advance.
4. **G6-01B (LSTM, sequence family, architecture 2/2, corrected criteria):** relative PASS, stability
   PASS, but absolute competence still FAILS (R²=−0.011). **Sequence family REJECTED** (2-architecture
   budget exhausted).
5. **Budget rule made asymmetric** after this: sequence=2 (used), self-supervised=1, transformer=1
   (self-supervised authorized first — it attacks the representation question more directly).
6. **G6-01C (Autoencoder, self-supervised family, 1/1):** failed even more decisively — reconstruction R²
   (0.092) was *worse* than 5-component linear PCA (0.119). **Self-supervised family REJECTED.**
7. **Paper 1 Interim Review** (`results/gen6/PAPER1_INTERIM_REVIEW.md`, unscheduled, evidence-triggered):
   weighed both sides of "should we spend the final transformer budget," estimated posterior ≈15–20% that
   PatchTST reverses the conclusion, **recommended declining it**. **User accepted this recommendation.**
8. **PAPER 1 CLOSED, FINAL.** Conclusion: *"Across three conceptually distinct representation-learning
   approaches ... no positive evidence was found that learned representations extract economically
   meaningful information beyond the validated engineered ontology, under the current data, task, and
   evaluation framework."* Papers 2–5 do not open (gated on Paper 1 passing, which it did not).

**Why Gen-6 ended and MSRP began:** repeated model-first failures suggested the more productive question
was not "can a model solve this" but "what does the market's information structure actually look like."

---

## Part 3 — MSRP (Market Structure Research Programme). CLOSED (Phase 1 + Phase 2 both frozen; Geometry/Networks/Economic Limits pillars never opened).

**Charter:** `MSRP_CHARTER.md`. Core philosophy: `Question → Measurement → Conclusion → Economic
interpretation`, **no experiment trains a predictive model**. Five pillars: Information, Memory,
Geometry, Networks, Economic Limits. Governance retained from Gen-5/6 (contracts, pre-registration,
four-outcome classification: POSITIVE EVIDENCE / NEGATIVE EVIDENCE / INCONCLUSIVE / METHODOLOGICAL
FAILURE).

**Full decision record:** `docs/MSRP_DECISION_LOG.md`. Ledger: `results/MSRP_EXPERIMENT_INDEX.csv`.

### Phase 1 (Information) — COMPLETE, FROZEN v1.1
Eight experiments (I-01, I-02, I-03, I-03B, I-04A, I-04B, I-05, I-06), synthesized in
`results/msrp/PHASE1_SYNTHESIS_FROZEN.md` (six chapters). **Verdict: POSITIVE EVIDENCE, High Confidence.**

**The central finding:** within the engineered ontology tested, predictive information organizes
hierarchically (Features → Families → Behavioral Classes → Primitives → Structural Basis), dominated by
a **Persistent Volatility Regime** that seven independent measurements all converge on, and a
behaviorally-heterogeneous momentum superfamily. `res_mom_52w_ex4w` (Config-4's top Shapley contributor
in Gen-5) independently confirmed as carrying genuinely distinct information (69% incremental retention
against the volatility family) — **two unrelated methodologies (Gen-5 portfolio Shapley, MSRP mutual
information) converged on the same conclusion.**

**Permanent concepts adopted:**
- **Structural redundancy vs. behavioral coherence** are orthogonal (`MSRP_CHARTER.md`) — every future
  clustering experiment must report both separately.
- **Information Primitive**, formally defined in `MSRP_CHARTER.md`.
- **Three working sets** for all future phases (`results/msrp/PHASE1_WORKING_SETS.md`): Full Ontology
  (18 features), Information Basis (12, the "Greedy/Practical" basis — NOT "minimal," precision-corrected
  in v1.1), Core Primitives (6, with `consistency_mom_26w` and `sharpe_mom_26w` flagged Fading per I-06).

### Phase 2 (Memory) — FROZEN (M-01B through M-05 complete; M-06 folded into synthesis rather than run)

**M-01/M-01B (Memory Characterization).** Raw M-01 run classified all six primitives as "M4 Long Memory"
(significant autocorrelation to 52 weeks) — including `beta_104w`, whose own window is 104 weeks, an
immediate red flag. Diagnosed as the **same construction artifact** Gen-6's R0/R0B caught. Corrected via
**M-01B** (first-differenced series + a pre-registered effect-size band): most "memory" evaporated.
**M-01B FORMALLY ACCEPTED** (independent review, High confidence) — M-01 relabeled `M-01A — Initial
Measurement`, M-01B = `Artefact-Corrected Measurement`, this two-stage pattern now recognized as healthy
recurring MSRP behavior. **Biggest result: falsifies "long lookback windows imply genuine long memory."**
Before M-02, the framework itself was tightened (all in `MSRP_CHARTER.md`): **Rolling-Window Persistence
Principle** named permanent law; **5 Methodological Safeguards** added; memory taxonomy revised to two
independent axes (**Duration** M1–M5 × **Behavior** B1 Persistence/B2 Reversal/B3 Oscillatory/B4
Lag-Specific/B5 Interaction-Driven); `vol_52w`'s "annual mean-reversion" claim **formally withdrawn**
(coincides with its own native window, cause unresolved) and weakened; **Interaction Persistence
Hypothesis** named for `consistency_mom_26w`'s recurring Dead→Interaction→Fading→thin narrative, to be
tested directly by M-05. Full write-up: `results/msrp/M-01/M01_MEMORY_CHARACTERIZATION.md`.

**M-02 (Regime-Dependent Memory Characterization)** ran with the tightened framework from the outset
(2-axis taxonomy, differencing correction, not retrofitted). **Self-caught a THIRD mid-run artifact**
(M-02A→M-02, third occurrence this session after Gen-6 R0/R0B and MSRP M-01/M-01B): M-01B's fixed
effect-size band alone was meaningless at regime-level sample sizes (n as low as 30–63), making all six
primitives falsely register "regime-locked." Corrected to require joint statistical-AND-economic
significance (n-adjusted). **Corrected result: POSITIVE EVIDENCE (candidate, awaiting independent
review) — 4 of 6 primitives genuinely regime-locked, 2 are informative negatives.** Strongest finding:
`amihud_13w` (Liquidity) is unconditionally memoryless but shows genuine memory specifically in
NORMAL_UP/STRESS regimes — regime-pooling in M-01B was diluting a real signal to invisibility.
`beta_104w` and `ret_4w` are cleanly NOT regime-locked (real negative results). Full write-up:
`results/msrp/M-02/M02_REGIME_DEPENDENT_MEMORY.md`.

**M-03 (Primitive Persistence — State Lifetime)** ran and required **two failed null designs** before a
third worked (a genuine design failure, not a threshold miscalibration): an unbounded-random-walk null
(M-03A) was systematically too persistent; a level-block-shuffle null (M-03B) systematically destroyed
persistence via artificial discontinuities. Adopted an AR(1)-matched null (tests state-locking beyond
simple linear mean-reversion). **Result: POSITIVE EVIDENCE (candidate) — `vol_52w` (99th percentile) and
`amihud_13w` (100th percentile) genuinely exceed AR(1)-predicted dwell time; 4 of 6 primitives are
ordinary.** `vol_52w` is now confirmed "special" by three independent MSRP measures (ACF-memory,
regime-locked memory, state-lifetime). `amihud_13w`'s result independently confirms M-02's regime-locked
finding via a completely different methodology. Full write-up:
`results/msrp/M-03/M03_PRIMITIVE_PERSISTENCE.md`.

**M-04 (Cross-Primitive Memory)** tested whether `vol_52w`'s state modulates the other 5 primitives'
memory (scoped to one conditioning primitive — the best-evidenced one — not all 30 pairs, per
burden-of-proof discipline). **Pre-registered directional hypothesis FALSIFIED**: predicted
`res_mom_52w_ex4w` memory would be stronger in High-Vol; observed the opposite (M4 Low-Vol vs M2
High-Vol) — trend persists more in calm periods. 4 of 5 targets show genuine modulation; only
`consistency_mom_26w` doesn't (sharpening M-05's design). Full write-up:
`results/msrp/M-04/M04_CROSS_PRIMITIVE_MEMORY.md`.

**M-05 (Interaction Memory)** directly tested the Interaction Persistence Hypothesis for the memory
dimension. **Pre-registered hypothesis CONFIRMED**: `consistency_mom_26w`'s memory (thin unconditionally)
emerges conditional on `res_mom_52w_ex4w`'s state (M4/M3 by state) — extending I-05's cross-sectional
confirmation to memory via an independent methodology. Secondary/exploratory direction found an
asymmetric coupling: `res_mom_52w_ex4w`'s memory also depends on `consistency_mom_26w`'s state (M4→M1),
establishing Residual Trend's memory as genuinely state-dependent, not fixed. Full write-up:
`results/msrp/M-05/M05_INTERACTION_MEMORY.md`.

**PHASE 2 (MEMORY) NOW FROZEN.** M-05 was the last experiment authorized under the 2026-07-25 scope
discipline. **M-06 (Memory Stability) folds into the Phase 2 synthesis rather than running as a
standalone experiment.** Next MSRP action: write the Phase 2 synthesis (mirroring
`PHASE1_SYNTHESIS_FROZEN.md`'s precedent), then the full pivot to Track A (Research Atlas + monograph).

**Outstanding, not yet done:** the 12-feature basis ACF robustness check from the raw M-01 run also needs
the differencing correction — flagged, not yet executed, and now deferred to the Phase 2 synthesis
write-up or later, not a blocking item.

---

## STRATEGIC SCOPE DISCIPLINE (adopted 2026-07-25 during MSRP, now the standing rule for the whole
programme, honored all the way through AEP's freeze)
Independent review of the three-programme arc concluded **the bottleneck was no longer lack of
experiments — it was turning results into knowledge.** Standing rule: **every proposed experiment must
justify why it answers a genuinely new scientific question, not merely that it is possible to run.** This
rule governed every subsequent decision in the programme: MSRP's Memory phase froze after M-05 rather
than running an M-06; AEP's Paper E was deferred rather than built on hope; and the final
`PROGRAMME_VALIDATION.md` explicitly recommends freezing the entire programme now, for the same reason —
not because ideas ran out, but because continuing would be iteration for its own sake, not new science.

## The exact next action
**There is no pending research action.** The programme is frozen. If a future session is asked to
continue, the first move is to read `MONOGRAPH.md`, `PROGRAMME_VALIDATION.md`, and
`NORTHSTAR_HANDBOOK.md`, then determine whether the user is posing a genuinely new question (which
would justify new work) or asking to resume the existing architecture (which the programme's own
standing discipline says not to do without new evidence). The one still-open, non-research item flagged
throughout is the **Delivery overlay's portfolio-level integration test** against the full frozen
two-sleeve book (`NORTHSTAR_HANDBOOK.md` Section 2, `results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md`) —
an implementation task, not a new research question, and the most natural next action if any is taken.

## How every governance layer nests (for a fast mental model)
```
GEN5_RESEARCH_CONSTITUTION.yaml (Gen-5 law: Oracle Ladder, burden-of-proof, portfolio-as-unit)
   -> superseded in spirit by GEN6_RESEARCH_CHARTER.md (Gen-6: Representation Ladder, extends Gen-5's O-rules)
        -> superseded in spirit by MSRP_CHARTER.md (MSRP: no predictive models, Information Primitive,
                                                     structural-redundancy-vs-behavioral-coherence)
             -> ARP_CHARTER.md (ARP: forensic close-out, NOT a research generation -- reuses Gen-5's
                                Oracle Ladder + burden-of-proof discipline but applies them backward,
                                to the existing archive, not forward to new experiments)
             -> AEP_CHARTER.md (AEP: parallel to ARP, not sequential -- mines economic KNOWLEDGE rather
                                than strategy VERDICTS; shares the 5-bucket classification with ARP)
                     -> AEP_MASTER_RESEARCH_PLAN.md (frozen constitutional document once AEP's own
                                architecture was settled -- no further AEP redesign without new evidence)
                             -> MONOGRAPH.md + PROGRAMME_VALIDATION.md + NORTHSTAR_HANDBOOK.md
                                (the three closing deliverables -- narrative, quantitative validation,
                                and pure operations, deliberately kept as separate documents)
```
Each charter *extends* rather than deletes the previous one's governance philosophy (pre-registration,
four/five-outcome classification, freeze discipline, never-silently-rewrite-history). Decision logs are
per-programme (`GEN5_DECISION_LOG.md`, `GEN6_DECISION_LOG.md`, `MSRP_DECISION_LOG.md`, `ARP_DECISION_LOG.md`,
`AEP_DECISION_LOG.md`) and are the authoritative chronological record within each; this document is the
cross-programme index.

## File map (everything referenced above, one place)
```
MONOGRAPH.md, PROGRAMME_VALIDATION.md, NORTHSTAR_HANDBOOK.md   <- START HERE: the three closing deliverables
GEN5_RESEARCH_CONSTITUTION.yaml, GEN6_RESEARCH_CHARTER.md, MSRP_CHARTER.md, ARP_CHARTER.md, AEP_CHARTER.md,
  AEP_MASTER_RESEARCH_PLAN.md   <- the governing "laws"
docs/GEN5_DECISION_LOG.md, docs/GEN6_DECISION_LOG.md, docs/MSRP_DECISION_LOG.md, docs/ARP_DECISION_LOG.md, docs/AEP_DECISION_LOG.md   <- decision records
docs/gen5_protocols/, docs/gen6_protocols/, docs/msrp_protocols/, docs/aep_protocols/   <- per-experiment/paper research contracts (AEP: Papers A-E, all frozen)
results/MASTER_EXPERIMENT_INDEX.csv (gen2-5), results/GEN6_EXPERIMENT_INDEX.csv, results/MSRP_EXPERIMENT_INDEX.csv
results/ARP_MASTER_ALPHA_REGISTRY.csv, results/ARP_STAGE1_CENSUS_AND_FINDINGS.md   <- ARP Stage 1
results/ARP_DELIVERY/   <- ARP's recovered, validated Delivery family (dossier + real capacity ladder data)
results/AEP_DISCOVERY_CENSUS.csv, results/AEP_STAGE1_DISCOVERY_CENSUS.md, scripts/arp/, scripts/aep/   <- AEP census + all paper scripts
results/AEP_PROTOTYPE_REGISTRY.md, results/AEP_DEPENDENCY_MAP.md   <- AEP background (superseded as planning unit by Papers A-E, kept for history)
results/AEP_PAPER_A/, results/AEP_PAPER_B/, results/AEP_PAPER_C/, results/AEP_PAPER_D/   <- AEP's per-paper frozen findings + raw data
results/AEP_SYNTHESIS_FROZEN.md   <- AEP's own closing synthesis (all 5 papers' verdicts)
MARKET_STATE_SPECIFICATION_v1.md   <- Paper A's implementation-ready deliverable, reusable independent of AEP's engineering outcomes
results/gen5/, results/gen6/, results/msrp/   <- per-experiment data + write-ups
GEN7_RESEARCH_CHARTER.md, docs/GEN7_DECISION_LOG.md, docs/GEN7_CHARTER_AMENDMENTS.md   <- Gen-7 governance
docs/gen7_protocols/PAPER-A_RESEARCH_CONTRACT.md, docs/gen7_protocols/PAPER-B_LAB1_SPECIFICATION.md
results/gen7/GEN7_STATUS_AND_FINDINGS.md   <- START HERE for Gen-7 (G7-F01..F08)
results/gen7/GEN6_GEN7_INDEPENDENT_AUDIT_2026_07_25.md   <- the audit that overturned Paper A
results/gen7/PAPER_A_REVISED_VERDICT.md    <- authoritative Paper A conclusions (v2.0)
results/gen7/PAPER_A_VERDICT.md, PAPER_A_POSTMORTEM.md   <- original, preserved unedited as history
results/gen7/paper_a_reanalysis/   <- RA-001..RA-006 corrected science + verification
results/gen7/lab1..lab8/, results/gen7/lab1_paperB/   <- per-laboratory data + write-ups
scripts/gen7/, scripts/gen7/reanalysis/   <- all Gen-7 code
scripts/gen5/, scripts/gen6/, scripts/msrp/   <- all engines/experiment code
GEN5_MASTER_FINDINGS.md, GEN5_PROGRAMME_FREEZE.md, GEN5_FINAL_RELEASE.md, GEN5_RETROSPECTIVE.md,
  GEN5_DUE_DILIGENCE.md, GEN5_DATASET_MANIFEST.md, GEN5_SCRIPT_MANIFEST.md, GEN5_REPRODUCTION_GUIDE.md,
  GEN5_OPERATIONS_MANUAL.md, GEN5_RESEARCH_ATLAS.md, GEN5_OPEN_QUESTIONS.md   <- Gen-5 closeout package
  (all under results/gen5/, written during the WP1-WP8 closeout)
results/gen6/PAPER1_INTERIM_REVIEW.md, results/gen6/G6-00/STAGE_R0_FREEZE.md   <- Gen-6 key artifacts
results/msrp/PHASE1_SYNTHESIS_FROZEN.md, results/msrp/PHASE1_WORKING_SETS.md,
  results/msrp/INFORMATION_MAP.md, results/msrp/I04_I05_INCREMENTAL_AND_BASIS.md   <- MSRP Phase 1 package
```
