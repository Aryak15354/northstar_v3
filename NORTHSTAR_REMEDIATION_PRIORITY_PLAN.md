# Northstar — Remediation & Re-Discovery Priority Plan

**Compiled:** 2026-07-30
**Source:** Master Hypothesis & Results Ledger (2026-07-28), Gen-1→9 + AEP/ARP/MSRP registries
**Purpose:** Of ~460 catalogued hypotheses across Gen-1 through MSRP, this plan identifies the subset that is *not* actually closed — signal that's underpowered, blocked on data, near a significance threshold, never pushed through an economic gate, or explicitly flagged as an open question — and gives you a concrete, sequenced way to run each one properly.

**Revision note (v2):** the first pass of this document was built by reading through the ledger narratively and prioritizing by payoff. This version follows a second, mechanical pass — every individual ID across all three source documents was extracted and checked line-by-line against what the first pass covered — specifically to catch anything the narrative read skipped. That pass added one new Tier-1 item (2.8), about a dozen Tier-2 refinements, one Tier-3 addition, a new section on data I genuinely can't verify from what I was given (Section 6), and several footnotes in the "retired" list confirming specific items were seen and deliberately excluded rather than missed. Everything new is marked inline.

---

# ⚠ STATUS: TIER 1 EXECUTED IN FULL — 2026-07-31

**Every Tier-1 item in this plan has been run.** Fifteen experiments (Gen-10 Remediation Programme):
**zero new deployable alpha, eight corrected verdicts, three permanent closures.** The certified book
is unchanged. Evidence: `results/gen10/GEN10_SYNTHESIS.md`; narrative in `MONOGRAPH.md` Part IX.

**Read this before acting on anything below.** The analysis in this document was directionally sound
and its sequencing advice paid off, but four Tier-1 items rested on premises that did not survive
testing, and the plan's headline #1 is now closed negative.

| plan item | outcome |
|---|---|
| **2.1** Delivery sleeve integration *(headline #1)* | **CLOSED, NEGATIVE.** See the correction at §1 and §2.1 |
| **2.2** Delivery regime dependency | **CLOSED.** Not regime-conditional (RISK_ON−RISK_OFF t = +1.49). A static weight is correct |
| **2.3** Universe-rule fix + survivorship rebuild | **REPLACED.** Its source (G8-12) says the rule is the strategy's own stop, not a bug. The exit-realism sweep it actually prescribed was run instead: the lead survives to a −45% gap-down exit |
| **2.4** DS-battery economic gate | **CLOSED, NOTHING PROMOTES.** 14 deduped items given their first-ever OOS split. 3 "survivors" are one already-deployed signal. DS-F2-03 (largest \|t\| in the battery) is Gen-1's A04 at 4091%/yr turnover |
| **2.5** Paper B Sub-study 2a | **PREMISE VOID, THEN CLOSED.** 2b did *not* confirm cleanly — its verdict rests on a pooled stock-week SE and reverses out of sample. 2a was the stronger role and closes on its own |
| **2.6** Paper C Q3 robustness | **RETIRED, NOT PROMOTED.** Never tested at all: paired **t = +0.50**, 0.18× its own detection floor. Not a liquidity rule, and Gen-5 G5-05A rediscovered |
| **2.7** Gen-7 CAIT redesign | **RUN. NULL at adequate power.** 0/15 survivors, max \|r\| = 0.014 vs a 0.11 floor. Cross-asset transmission retired permanently |
| **2.8** Paper D monthly | **RETIRED.** Fails correction for the five resolutions it was selected from. "RISING" is a curve-shape label, not a trend |
| **§6** un-enumerated registry buckets | **RESOLVED.** 16 of 17 rows were already covered by this plan; the one omission (G2-B03b) is logged. Nothing promising was hidden |

**What this plan got right and should be reused:** the four-fate taxonomy; pre-registering the kill
criterion; the sleeve-vs-overlay distinction at 2.1 (a genuine gap in the record); running 2.2 before
2.1; and above all the caution on **DS-F2-03** — "run Stage 4 before getting attached to the effect
size" was right to the second decimal place (4091%/yr vs A04's 4187%/yr).

**Six rules were adopted in response:** `RESEARCH_INFERENCE_STANDARD.md`.

---

## 0. How to read this document

Every experiment in the ledger got a verdict, but "verdict" and "closed" are not the same thing. Roughly four things happened to the ~460 hypotheses:

1. **Genuinely tested and killed** (REJECTED, |t|<2, no construction error, no data gate) — nothing left to do. ~230 of these.
2. **Genuinely tested and confirmed as economic laws or portfolio components** — already in the book or in the permanent findings registry. Not this document's concern.
3. **Statistically detected but never economically tested** — RESEARCH_SIGNAL, INCONCLUSIVE, near-miss, or explicitly flagged OPEN QUESTION. This is where the unexploited value is.
4. **Never run at all** — REGISTERED/PENDING, BLOCKED_DATA, DEFERRED. Some of these are just waiting on data you can now get; some need live capital and aren't backtestable; some were correctly never run and should stay that way.

This document is entirely about buckets 3 and 4. I've sorted them into three tiers by (expected payoff) × (tractability with data/tools you already have), then given you a run-book for each Tier-1 item and lighter guidance for Tier 2/3. Section 5 is the explicit "let go" list — read it once so you know what was considered and consciously excluded, then don't re-litigate it. Section 6 covers a couple of things I flagged during a follow-up audit that I genuinely can't resolve from the source material I was given.

**One meta-point before the tiers:** the single biggest pattern in this ledger is that Gen-2/3's "deep-search factor battery" (DS-F1 through DS-U, ~28 items) produced a pile of statistically real RESEARCH_SIGNAL findings that **never went through the same 4-stage economic gate** that Gen-5 applied to portfolio levers (statistical → ceiling → realizable-skill-with-CI → net-of-cost). That gate is the thing that turned "looks good" into "TERMINATED_BY_GATE" for three Gen-5 levers and into "CONFIRMED, deployable" for Delivery. Applying it retroactively to the DS-battery is probably the highest-value single project in this whole plan, because you already have the harness — you built it for Gen-5.

---

## 1. Headline recommendation — if you only do five things

| # | Item | Why it's alive | Effort |
|---|---|---|---|
| 1 | ~~**Delivery × frozen book portfolio integration**~~ **CLOSED, NEGATIVE (T1-06)** | **The premise was wrong.** corr 0.14 is *signal* orthogonality — the realised correlation of the two long-only sleeves' **returns is 0.842**. Two long-only Indian equity books share market beta whatever their signals do, so there was never meaningful diversification to harvest. With that gone the case rests on Delivery's higher standalone Sharpe: **+0.335, t = +1.60** — not significant on 338 weeks. At the lower bound of its own CI the optimal sleeve weight is **0% at every capital band**; bootstrap `w*` swings 49%→100% across resamples. Sleeves *are* cleanly separable (15.7% name overlap), so this is not a collision problem — it is a correlation-and-power problem. **Both integration architectures are now closed** (overlay: G8-09, 59 years needed; sleeve: T1-06). Delivery is a confirmed-real, cost-surviving, capacity-characterised signal **with no known way into the book.** | — |
| 2 | **Run the DS-battery through the Gen-5 economic gate**, starting with the delivery-family and momentum-quality clusters | ~15 statistically real signals (some with |t| up to 8.9) sitting untested since Gen-2/3. Reuses infra you already built. | Medium (per signal: low) |
| 3 | **Fix the universe-inclusion rule per G8-12 and rebuild the survivorship-complete panel** | This is a data-integrity issue underneath your *entire* certified alpha stack (C04/C05/C07), and G8-12 already diagnosed the exact mechanism (217/327 delisted names never enter by rule). Diagnosed bugs are the cheapest wins in research. | Medium |
| 4 | **Re-run AEP Paper B Sub-study 2a ("Confirms" role)** | Missed its own bar by a hair (t=1.97–1.91 vs required 2.0) while its sibling Sub-study 2b confirmed cleanly (t=2.03–2.25). Classic near-miss — worth a proper power check before letting it go. | Low |
| 5 | **Redesign Gen-7/CAIT using the G8-10 fix (stock-level receiver, reduced multiplicity)** | Cross-asset transmission was never proven *absent* — it was proven *underpowered* (detection threshold above all candidate effect sizes). G8-10 found the exact fix (stock-level gives 4–10x the effective independent series vs sector-level) but it was never applied to a full re-run. | Medium-high |

Everything below expands on these five plus the rest of the Tier 1/2/3 lists.

---

## 2. Tier 1 — pursue now (clear next step, reuses existing infra, real payoff if it works)

### 2.1 Delivery Alpha — Portfolio Integration with the Frozen Book

> **⚠ CLOSED NEGATIVE, 2026-07-31 (`results/gen10/T1-06/`).** Run as specified below except for three
> corrections. (a) **Step 2's premise is void** — 0.14 is signal orthogonality; realised sleeve-return
> correlation is **0.842**, so an inverse-vol or risk-parity blend has almost nothing to diversify.
> (b) **Step 1 must not mix eras** — Config-4's 0.8105/0.8471 are full-history; on the matched
> delivery window the same book scores 1.604, and mixing the two manufactures an improvement.
> (c) **Step 5's pre-registered test is unreachable** — its unpaired MDE is ~8× its own bar, which is
> the same wall G8-09 hit. Re-run as a *sizing* question instead: at the lower bound of Sleeve B's own
> Sharpe CI the optimal weight is **0% at every capital band**. Step 3's name-collision check was run
> first and passed (15.7% overlap) — that instruction was correct and worth keeping.


**Source:** ARP Delivery Dossier — "Portfolio integration: does Delivery combine well with the frozen momentum+sector book? OPEN QUESTION — not yet tested." Also G8-09 (Gen8/9): "Delivery overlay improves the actual certified Config-4 book — UNRESOLVED / do-not-integrate, best contribution +0.066 Sharpe, needs 59yr to resolve."

**Why these two results aren't actually a contradiction, and why that matters:** G8-09 tested Delivery as an *overlay/veto* on the existing momentum book and found the improvement (+0.066 Sharpe) can't be statistically distinguished from noise without 59 years of data. But the ARP dossier's capacity-ladder work tested Delivery as a **standalone sleeve** (correctness gate: CONTROL 0.698 vs ADD_nonfno_tail net Sharpe 0.767 @20bps; capacity ladder peaking ~0.792 @₹5–10cr, degrading gracefully to 0.660 @₹500cr) — and that version has never been combined with the book at the *portfolio* level (i.e., as its own capital allocation, not as a conditioning overlay on momentum's picks). Those are two different integration architectures, and only one of them (the overlay) has been shown to be underpowered. The sleeve-level combination is untested, not disproven.

**Run plan:**
1. **Construct the combined book explicitly as two independently-sized sleeves**, not a signal overlay: Sleeve A = frozen Config-4 (recertified Sharpe 0.8105, or 0.8471 with the G-05 crash overlay — use the *recertified* number from `G4_00B_PROVENANCE_AUDIT.md`, not the pre-correction 0.9235 figure that turned out to be survivorship-inflated). Sleeve B = Delivery non-F&O tail construction from `ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md`, sized at whatever capital band you're targeting (peak efficiency is ₹5–10cr; if your working AUM assumption is different, pull the number off the capacity ladder for that band).
2. **Weight the blend using the known correlation.** corr=0.14 between Delivery and momentum is close enough to orthogonal that a simple inverse-vol or risk-parity blend should get you most of the diversification benefit without a full mean-variance optimization — start there before reaching for anything more complex; if the simple blend clears the bar you don't need to build machinery you'd otherwise have to validate separately.
3. **Check for a name-collision effect before anything else.** Delivery is a non-F&O tail signal; momentum's frozen book pulls from the full universe. Quantify how much overlap exists in simultaneous holdings — if it's near zero, the diversification math is clean; if it's material, you need to handle position netting explicitly or you'll double-count capacity at the position level, not just the sleeve level.
4. **Reuse the existing cost model.** `IndianEquityCostModel` and the G5-D01/D02 findings (slippage dominates fees, growing from 58.5%→84.1% of cost as AUM scales ₹100cr→₹2500cr) apply directly — run the combined book through the same capacity ladder (₹5L → ₹500cr) that was used for Delivery alone, this time measuring the *combined* net Sharpe at each band, not just Delivery's.
5. **Pre-register the success/kill criterion before running it**, the same discipline every Gen-5 lever used: e.g. "combined book's net Sharpe at the target capital band must exceed frozen-momentum-alone's net Sharpe by a CI that excludes zero in the lockbox window." If you don't pre-register this, a positive-looking result here is just as easy to overfit to as any Gen-2/3 DS-battery signal was.
6. **Hold out the same lockbox year(s)** used to validate Config-4 originally — don't let this test see data the frozen book's own certification used for tuning.

**What "done" looks like:** either a portfolio construction doc analogous to `CONFIG4_HOLDINGS_AND_REPRO_BREAK.md` showing the combined holdings and the lockbox-verified Sharpe improvement, or a clean negative result you can retire (in which case log it back into the ledger as a proper NSR-EXP entry — don't let this live only in your head).

### 2.2 Delivery Alpha — Regime Dependency

> **⚠ CLOSED 2026-07-31 (T1-06).** Not regime-conditional: RISK_ON−RISK_OFF IC difference t = +1.49. A **static** sleeve weight is correct. Note the design change forced by data — in the delivery era RECOVERY has 15 weeks and CRASH 29, both under MSRP's own MIN_N=30, so the five-state test this section specifies is not runnable; it was collapsed to two states. Step 0 (check G8-03 first) and step 3 (build the non-overlap check in from the start) were both good calls and were followed.

**Source:** ARP Delivery Dossier — "Regime dependency: is the signal regime-conditional? OPEN QUESTION — no MSRP-style test run yet."

**Why this is worth doing right after 2.1, not instead of it:** if Delivery turns out to be regime-locked (the way liquidity memory in M-02 was found to be locked specifically to NORMAL_UP/STRESS regimes), that changes how you should size Sleeve B in 2.1 — you'd want a regime-conditional allocation rather than a static one, and it's much cheaper to build that in from the start than to retrofit it after 2.1 is "done."

**Run plan:**
0. **[Added on audit] Check G8-03 before trusting the toolkit.** Gen-8/9's own re-check of MSRP's feature basis found "9/12 exceeds, 3 within" some rolling-window-memory threshold — i.e., a partial audit flag on the same MSRP infrastructure this plan wants to reuse, and it's not clear from the source ledger whether that flag touches M-02/M-04/M-05 specifically or only the Information-pillar features. Confirm which of the 12 features are implicated before leaning on the Memory-pillar tests below — if Delivery's regime-lock result comes back positive, you want to know it isn't inheriting the same artifact that M-01→M-01B and G6-00→G6-00B both had to catch and correct once already.
1. Apply the full MSRP Memory-pillar methodology — not just M-01B/M-02/M-04, but also **M-03** (does the state dwell-time exceed AR(1)-implied persistence?) and **M-05** (Interaction Persistence Hypothesis — does the signal's memory only emerge conditional on trend state?) — to the Delivery signal instead of the six original primitives.
2. Specifically test: does Delivery's IC (baseline 0.0318, t 8.02 unconditional) hold uniformly across the regime states MSRP already built (NORMAL_UP / STRESS / CRASH / RECOVERY), or is it concentrated the way liquidity memory was?
3. Use M-01/M-01B's own history as a cautionary template — M-01's first pass falsely found "long memory everywhere" due to a rolling-window overlap artifact, caught and corrected in M-01B. Build the non-overlapping/differenced check in from the start rather than as an afterthought.
4. If regime-locked, feed the result directly into the sizing rule for 2.1.
5. **[Added on audit]** M-05's finding — that consistency_mom_26w's memory is near-absent unconditionally and only emerges conditional on trend state — is worth testing on Delivery specifically because it's the same shape of question 2.5 below is wrestling with (why did "Confirms" narrowly fail while "Warns" passed). If Delivery turns out to have the same trend-state-conditional memory structure, that's a second, independent data point for whether trend-state conditioning is a genuinely load-bearing construct in this dataset or a coincidence specific to consistency_mom_26w.

### 2.3 Universe-Inclusion Rule Fix + Survivorship-Complete Rebuild

> **⚠ REPLACED 2026-07-31 (T1-08).** This item prescribes the opposite of its own source. G8-12 concluded the universe rule is **the strategy's own stop-loss, not a bug** — rebuilding the panel to hold names through delisting would model a book nobody would trade. G8-12 §6 named the actual remaining task (a realistic gap-down exit), which was run instead: the tier lead survives to a **−45% gap-down**, and G8-12's 0 to −2.29%/yr bound is confirmed by direct simulation. Step 4's instruction to expect a confirmatory outcome was also the wrong discipline for a pre-registration.

**Source:** C05 (Gen-1, DATA-BLOCKED — "34/409 delistings; bias likely conservative") and G8-12 (Gen8/9 — "small-cap advantage is a survivorship artifact fixable by backfill: REJECTED — real bias is universe-rule truncation; 217/327 delisted names never enter panel by rule").

**Why this matters more than its tier ranking might suggest:** this isn't a new-alpha hunt, it's a foundation check. C04 (Q1 short-leg alpha, certified at +9.5%/yr proxy, +6.3%/yr F&O-only) and C07 (RECOVERY phase diagnosis) both sit on top of a panel that G8-12 has already shown has a *specific, mechanical* construction bug — not missing data, a rule that excludes names before they delist. That's the cheapest kind of bug to fix because you don't need new data acquisition, you need a rule change plus a rebuild.

**Run plan:**
1. Locate the exact universe-construction rule referenced in G8-12's finding (likely a liquidity/listing-age/index-membership filter that's evaluated at portfolio-construction time using *current* status rather than point-in-time status — that's the classic mechanism behind this kind of bug).
2. Rewrite the rule so a name that meets universe criteria at time t stays eligible through its delisting, rather than being silently dropped from the panel once its liquidity/membership status changes.
3. Rebuild the panel and re-run C04, C05, and C07 exactly as originally specified (don't respecify anything else at the same time, or you won't know whether a changed result came from the rule fix or from something else).
4. Because C05's own note says the expected bias direction is "conservative" (i.e., the current numbers likely *understate* the real edge), a rebuild that shows the edge holding or strengthening is the expected/confirmatory outcome — a rebuild that shows the edge weakening materially would itself be an important (if unwelcome) finding, and should be treated as such rather than debugged away.
5. This also directly informs G9-02 (institutional-ownership explanation for the liquidity-IC gradient), which is currently blocked by an FII data coverage cutover in 2023 — a corrected panel won't fix the data-coverage problem, but it will remove one confound from that investigation.

### 2.4 Deep-Search Factor Battery — Retroactive Economic Gate

> **⚠ CLOSED, NOTHING PROMOTES 2026-07-31 (T1-04a, T1-09).** The premise was exactly right — no DS item had ever been evaluated out of sample (`"lockbox_used": false` on all 28). Given that split, 14 deduped items produced **zero new alpha**: 3 "survivors" are one already-deployed signal (pairwise ρ 0.72–0.92, incremental t 0.27–0.61), and DS-F2-03 is Gen-1's A04 at **4091%/yr turnover vs A04's 4187%/yr**. Two pairs were duplicate registrations (DS-U-04 ≡ DS-F5-01, DS-U-03 ≡ DS-F4-01), so the 28-item FDR denominator was wrong. Broad-coverage ICs were additionally inflated 30–40% by a universe-composition artifact.

**Source:** Gen-2/3 §2a (DS-F1 through DS-U), ~28 items, mostly RESEARCH_SIGNAL. Per the ledger's own note in `MASTER_EXPERIMENT_CATALOGUE.csv`, RESEARCH_SIGNAL is explicitly "not a rejection... no alpha/portfolio/economic-law content identified [yet]" — meaning these cleared a statistical significance bar in a discovery pass and then nothing else happened to them.

**The gate you already have, restated for reuse:**
- **Stage 1 — Statistical robustness.** Re-verify the original t-stat isn't a full-sample artifact (this is exactly what killed DS-F3-04, "volume surge predicts momentum-long failure," whose full-sample t=-4.4 collapsed to t=-0.06 in a genuine discovery/OOS split — and killed MOM-DET-COMPOSITE the same way). Split into alternate windows the way AEP Paper B did (2/5 alternate splits is the bar Prototype 1 failed).
- **Stage 2 — Ceiling estimate.** What's the best-case Sharpe/IC if you had perfect timing on this signal, the way Gen-5 computed oracle ceilings for its levers?
- **Stage 3 — Realizable skill with CI.** What's the *actual* achievable improvement with a realistic model, and does its confidence interval exclude the "no better than doing nothing" case? This is the exact test that terminated G5-05A/05B/04C despite decent-looking ceilings.
- **Stage 4 — Net-of-cost, at capital scale.** Turnover and cost profile, run through `IndianEquityCostModel` the way Delivery's capacity ladder was built.

**Prioritization within the battery — group by mechanism, not by ID, and run the highest-confidence cluster first:**

| Cluster | IDs | Signal strength | Why prioritize/deprioritize |
|---|---|---|---|
| **Delivery-family extensions** | DS-F1-01 (t=-1.88, weakest of the group — include but expect it to be the first casualty at Stage 1), DS-F1-04 (t=-2.95), DS-F1-05 (t=4.21), DS-F1-06 (t=3.46), DS-F3-01 (t=2.34), DS-F3-02 (t=3.02), DS-F5-01 (t=4.93), DS-U-02 (t=4.06), DS-U-04 (t=4.93) | Strong, and consistent | **Highest priority.** These extend a mechanism you've *already* proven deployable (Delivery/G2-E03). Consolidate F5-01 and U-04 first — "stock delivery relative to sector" and "unconditional sector-relative delivery" are likely the same underlying construct measured twice; check for redundancy before treating them as two signals. Feed survivors into an enhanced Delivery composite and re-run through the capacity ladder from 2.1/2.2. |
| **Momentum-quality overlays** | DS-F4-01 (t=3.06, smooth vs jumpy momentum), DS-F4-02 (t=6.33, declining participation = vulnerable), DS-F2-06 (t=3.38, momentum stronger in low-vol names), DS-U-01 (t=2.91), DS-U-03 (t=3.06) | Strong | **Second priority.** DS-F4-02 in particular (t=6.33) is a candidate veto/overlay on the existing momentum book, structurally similar to how the Delivery overlay (G2-E03-OVERLAY) was found to improve net Sharpe 0.70→0.77 *without* concentrating the book. Test it the same way — as a veto/confirm construction on top of frozen momentum, not as a standalone strategy — before assuming it needs its own capital allocation. |
| **Cross-factor conditioning** | DS-F2-03 (t=-8.91, reversal stronger after liquidity shocks), DS-F2-04 (t=2.20, value works when price weak) | Very strong (F2-03) but flagged for caution | **Third priority, caution flagged.** DS-F2-03 has the single largest t-stat in the whole battery, which should make you *more* suspicious, not less — Gen-1's A04 already showed 1-week reversal has a real IC (t=-6.82) that dies at 4187%/yr turnover, and DS-F2-03 is a reversal-family signal. Run Stage 4 (turnover/cost) *before* getting attached to the effect size; if it shares reversal's turnover profile, it's dead for the same structural reason regardless of statistical strength. |

**Practical sequencing:** don't try to run all ~15 through all 4 stages before drawing conclusions on any of them. Take the Delivery-family cluster through Stage 1–4 fully, since it's most likely to actually convert; use what you learn there (what construction choices mattered, what killed candidates at which stage) to make the other two clusters faster.

### 2.5 AEP Paper B, Sub-study 2a ("Confirms" role) — Near-Miss Re-Test

> **⚠ PREMISE VOID, THEN CLOSED 2026-07-31 (T0-01, T1-05″).** This item assumes 2b confirmed cleanly
> and asks why 2a nearly failed. **2b did not confirm** — its t-statistics pool ~62,000 stock-weeks as
> independent; corrected, it is t = +0.57 and all four lockbox horizons are negative. 2a was the
> *stronger* role (corrected t = +2.52 at 4w) and then closed on its own: eight further tests using 33%
> and 100% of the cross-section all agree in sign, none reaches |t| = 2, and settling it by waiting
> needs 9.7 more years. Step 3's instinct (condition on trend state) was good — test 2a is *already*
> trend-conditional by construction, which is plausibly why it is the role that held up.


**Source:** consistency_mom_26w as a conditional signal was tested for four candidate roles. 2b (Warns) confirmed cleanly (t=2.25/2.03/2.07 across horizons). 2a (Confirms) missed by a hair: t=1.97–1.91, just under the |t|≥2 bar, across the same horizons. For completeness, the other two roles were also tested and cleanly rejected — 2c (Delays): stable, non-asymmetric cross-correlation; 2d (Accelerates-exits): t=0.79, n.s. — so this is genuinely a 1-of-4 pattern, not a coin flip you're re-litigating.

**Run plan:**
1. **Do a power calculation before re-running anything.** You have the effect size (implied by t≈1.9–2.0 at your current n_dates). Compute how many additional weeks of data would be needed to push the CI to exclude the null at the same effect size, assuming it's real and not sampling noise. If that number is small (a few months of additional walk-forward data you'll accumulate naturally), the right move is simply to re-check at a scheduled future date — not to re-run immediately with the same n and hope for a different draw.
2. **In parallel, investigate the mechanical difference between 2a and 2b.** Confirms and Warns are presumably scored from the same underlying signal with different thresholds/logic; 2b's clean confirmation and 2a's near-miss suggests the *threshold*, not the underlying signal, might be miscalibrated. Try 2–3 alternate threshold specifications (pre-registered, not tuned to the answer) before concluding 2a is genuinely weaker than 2b rather than just less cleanly specified.
3. **[Added on audit] Specifically try conditioning "Confirms" on trend state.** MSRP's M-05 (Interaction Persistence Hypothesis) found that this exact signal's *memory* is near-absent unconditionally and only shows up once you condition on trend state. If "Confirms" was originally specified unconditionally, that's a plausible, specific reason it fell just short while "Warns" (which may implicitly already carry a trend-conditional flavor) passed — worth testing as your first alternate specification in step 2, not a generic threshold tweak.
4. Treat this as a single pre-registered re-test, not an open-ended search — if the alternate specifications don't clear the bar either, let it go and don't return to it until the natural data-accumulation trigger from step 1 fires.

### 2.6 AEP Paper C, Prototype 3 (Liquidity-Persistence Sizing, Q3) — Robustness Confirmation

> **⚠ RETIRED, NOT PROMOTED 2026-07-31 (T0-02).** Q3 was never "one robustness check away" — **it was never tested at all.** Supplying the test: paired **t = +0.50**, p = 0.62, effect **0.18× its own 80%-power detection floor**, costing **3.26%/yr** of return. It is also not a liquidity rule (it keys off regime labels; no liquidity-persistence measurement enters the decision), its regime selection is wrong on its own terms (de-gearing in CRASH alone scores 0.816 and STRESS alone 0.778, both beating the bundled 0.727 — and STRESS is held at *full* exposure), and it is **Gen-5 G5-05A rediscovered**, already TERMINATED_BY_GATE at 3× the effect size.

**Source:** "Q3 Sizing: Scaling exposure by liquidity-persistence improves risk-adjusted return? ACCEPTED (robustness untested). Sharpe 0.692→0.727, vol -23%."

**Why this is cheap and worth doing before almost anything else in this document:** it's already a positive, economically meaningful result (a 5% Sharpe improvement with a 23% vol reduction is not a marginal effect) sitting one robustness check away from being promotable to an actual Portfolio Component. The test harness for this already exists — it's the same 2/5-alternate-split validation that Prototype 1 failed and that's used throughout AEP.

**Run plan:**
1. Apply the identical alternate-split robustness test (5 splits, need to clear at least the same bar the programme uses elsewhere — Prototype 1 failed at "2/5 alt splits," so the implicit bar is passing at least 3–4 of 5) to the Q3 liquidity-sizing rule specifically, holding everything else about Paper C's Q1/Q2/Q4 findings fixed.
2. If it passes: promote from "AEP research finding" to an actual sizing rule applied in the frozen book's next revision, and log the promotion the same way G2-E03 was promoted to Deployable Alpha in ARP.
3. If it fails: retire it alongside Prototype 1 (same failure mode — a real full-sample effect that doesn't survive alternate splits) and don't revisit.

### 2.7 Gen-7 (CAIT) Redesign Using the G8-10 Fix

> **✅ RUN 2026-07-31 (T1-10) — NULL at adequate power.** Design instincts here were right (cut multiplicity, economically-motivated carriers, fix the FDR resolution). The one gap was that G8-10 required a **beta control** be settled before any code: Gen-7's effects hit 41/42 sector cells equally, which reads as market beta. Receivers were therefore beta-residualised and channel specificity tested rather than assumed. Result: **0/15 survivors, largest |r| = 0.014 against the pre-registered 0.11 floor, zero effects classified as beta.** Cross-asset transmission retired permanently; H-A2/A3/A4 close with H-A1. One caveat: US 10Y was untestable on 440 weeks, so the duration/rates channel remains formally uncovered.

**Source:** H-A1 (cross-asset transmission) was "NOT SUPPORTED" but the ledger is explicit that absence was never actually established — G7-F02: "does zero survivors prove absence? REJECTED (unresolved, underpowered)"; G7-F04: lockbox power only ~13%, all 6 candidate CIs include zero; G7-F08: detecting the candidate effect size at 80% power needs ~34 years of weekly data, you have 21. G8-10 (Gen8/9) then found the actual fix: "a stock-level receiver universe fixes Gen-7's power problem — stock-level: 12.2 effective independent series, 4–10x the required n" (vs. sector-level, which is what the original 310-pair test used).

**Why this is worth a real re-run rather than being filed under "wait for more data":** G8-02 (the direct Gen-7 rerun at reduced multiplicity m=31) is close — 67.5% power at r=0.11, needs n=1312, you have n=1070 — but closing that gap by *waiting* means ~4.6 more years of weekly data. G8-10's stock-level fix gets you a materially larger effective sample size *now*, without waiting.

**Run plan:**
1. Re-specify the receiver side of the transmission tests at the individual-stock level (using the 500-equity universe) rather than the 42-sector-cell level used in the original 310-pair test.
2. Reduce the carrier universe from the original exhaustive 310 pairs to a pre-registered, economically-motivated subset — G7-F06 already showed that cutting multiplicity from m=310 to m=31 alone raises power from 31%→60% at r=0.11; combining that cut with the stock-level fix should compound. Pick the ~20–30 carriers with the clearest fundamental transmission channel to Indian equities (crude oil for energy/paint/tyre names, USDINR for importers/exporters, US 10Y for financials/duration-sensitive sectors) rather than testing every commodity/FX cross against every sector blindly — this also sidesteps G7-F07's finding that any detected association hit 41/42 sector cells roughly equally (i.e., wasn't channel-specific), which is itself a symptom of an underpowered, over-broad original design.
3. Apply the BH/BY FDR correction discipline the original used — but fix it first, don't just reuse it as-is: G7-F03 found the original permutation-based correction had a p-floor "an order of magnitude coarser than needed," which is a resolution problem independent of the multiplicity/granularity issues G7-F06/G8-10 addressed. Increase the permutation count enough to give the p-floor the resolution the corrected, lower-multiplicity test actually needs, or this redesign inherits a second bug on top of the two it's fixing.
4. Pre-register the effect-size floor you're testing for (r≈0.11, per G7-F04/G8-02's own framing) so a null result here is informative and closes the question, rather than inviting a third re-run.
5. If this redesign still produces zero survivors at adequate power, that's a *real* negative result (properly powered, not the underpowered non-result Gen-7 produced) — and at that point cross-asset transmission should move from "unresolved" to "let go" for good.
6. **[Added on audit]** If it instead *does* turn up a survivor, remember that H-A2 (is transmission lagged?), H-A3 (is it stable through time?), and H-A4 (is it directional?) were never independently disproven — they were marked UNTESTABLE/UNCHANGED/WITHDRAWN purely because H-A1 (does transmission exist at all) was unresolved. A confirmed H-A1 makes all three live questions again, not settled ones.

### 2.8 [Added on audit] AEP Paper D / Prototype 4 — Monthly-Resolution Near-Miss

> **⚠ RETIRED 2026-07-31 (T1-07).** The suspicion was right, the stated reason was not. **"RISING" is a pre-registered curve-shape label** (any resolution ≥3× weekly), computed once on the full sample — it never meant the margin was widening with more data. The decisive problem is multiplicity: monthly p ≈ **0.038** against a Bonferroni threshold of **0.010** at m = 5, failing BH and BY too. Monthly is simply where *n* is still large enough to keep the null tight while aggregation has lifted MI. Gen-5's F17 was never a resolution artifact and is now settled across all five cadences.

**Source:** Gen-5's F17 asked whether weekly state carries information about the correct action and found it doesn't (normalized MI 0.003–0.012, near noise). AEP Paper D then re-asked the same question at five different decision-time resolutions. Weekly, biweekly, and 6-week all failed cleanly; quarterly's initially-dramatic result turned out to be a small-sample artifact (n=82) once corrected. But **monthly narrowly passed**: nMI 0.0263 vs. a null of 0.0245 — "ACCEPTED (barely) — RISING."

**Why this belongs next to 2.5, not in Tier 2:** it's the same shape of finding — a real, pre-registered, properly-corrected test that landed just past its own bar rather than well past it — and it's cheap to follow up because the resolution-study harness already exists (it's what produced all five results in the first place).

**Run plan:**
1. Before doing anything else, check whether "RISING" in the verdict means the margin (0.0263 vs. 0.0245) has been getting wider as more data comes in, or whether it was computed once on the full sample. If it's a single full-sample computation, treat it with the same skepticism as any other single point estimate — that's exactly the pattern that made DS-F3-04 and MOM-DET-COMPOSITE look real in-sample and evaporate out-of-sample.
2. Re-run the monthly-resolution test on a genuine train/discovery/lockbox split, the same discipline used everywhere else in the programme, rather than relying on the single pooled number in the table.
3. If it survives a proper OOS split, the natural next question is *why* monthly specifically — is there an economic story (e.g., monthly lines up with some natural decision cadence, like position-review timing) or is it just the resolution that happened to land closest to the noise floor by chance among five tried? A finding with an economic story behind it is worth more than one that's simply "the best of five resolutions tried."
4. If it doesn't survive a proper split, retire it alongside weekly/biweekly/6-week and treat F17's original weekly-null as the settled answer across all resolutions.

---

## 3. Tier 2 — pursue opportunistically (real but smaller, or gated on time passing)

These are worth doing, but either the expected payoff is smaller, the fix is less certain, or the right move is literally "wait for more data" rather than "do more work now." I've included a trigger condition for each so you know when to revisit rather than checking in on all of them constantly.

| Item | Source | Status | Trigger to re-run |
|---|---|---|---|
| **G5-08A/B/C/D** — confidence-weighting, risk parity, covariance shrinkage, no-trade regions | Gen-5, REGISTERED → PENDING, never run | Legitimate unexplored portfolio-construction ideas that don't require new alpha, just better use of what you have. **[Audit caveat]** the granular per-experiment notes claim these were "superseded by renamed successors (G5-08B/C → G5-D01/D02)," but the main ledger's own Gen-5 section lists them as simply never-run, and thematically G5-08B/C (risk parity, covariance shrinkage) don't obviously map onto G5-D01/D02 (slippage cost, execution delay) — those look like different topics entirely, not a rename. Resolve this inconsistency before spending time here: check the actual `results/gen5/` folder for whether G5-08B/C code exists standalone, rather than trusting either summary blindly. | Any time — these are ready to run now, just deprioritized behind Tier 1, pending the caveat above |
| **G5-09** — temporal model of state | Gen-5, REGISTERED → PENDING | Same as above | Any time |
| **G5-06A (dispersion/vol-timing)** | Gen-5, INCONCLUSIVE → REDESIGN | Diagnosed as a wrong-signed proxy construction error, not an information absence | Fix the proxy sign/construction, then re-run once — if it still fails Stage 1, let go for good |
| **G5-06B (vol-targeting)** | Gen-5, INCONCLUSIVE → REDESIGN | Diagnosed as regime instability (reverses post-2015), not construction | Only worth revisiting with an explicitly regime-conditional design, not a redo of the same static rule |
| **G4-GATE-02** | Gen-2/3, RESEARCH_SIGNAL, "worth one review pass" per its own notes | Real weak signal (t=3.79) but net-negative at 2x leverage; ambiguous between "too small" and "portfolio-component-only" | Test explicitly as a portfolio component (combined with existing sleeves) rather than standalone before retiring |
| **G2-D01a (SUE drift)**, t=2.09 | Gen-2/3, INCONCLUSIVE | Right at the edge, **but temper expectations**: SUE/PEAD has now been independently tested null across at least eight other framings in this ledger — A10, E01, E02, E10, and the Ledger-level rev_sue/eps_sue/combined_sue all failed, plus G2-D01b/c also failed. One t=2.09 among that many independent looks at the same underlying idea is close to what you'd expect from chance alone, not strong evidence the ninth framing is the one that's real | Worth the re-test once more quarters of earnings data accumulate, but go in expecting it to join the rest, not expecting a breakthrough |
| **G2-D02a/b (ROE inflection, operating margin improvement)** | Gen-2/3, INCONCLUSIVE, IC 0.066/0.045 (large ICs, no reported t) | Large point estimates, likely thin-sample | Compute the actual t-stat/CI properly before treating as promising — may already resolve the ambiguity without new data |
| **G3-T4 (INR depreciation, exporters/importers)** | Gen-3, INCONCLUSIVE | Importer leg wrong-signed (construction issue), exporter leg alone correctly signed (t=2.06) | Redesign as an exporter-only long overlay, drop the importer leg entirely rather than trying to fix its sign |
| **[Added on audit] G3-T5 (analyst disagreement flags momentum failures)**, t=2.28, and **G2-A03/G2-A0c (abnormal news intensity / narrative momentum of info flow)**, t=2.29/2.28 | Gen-2/3, all INCONCLUSIVE | Three separate, narrowly-above-2.0 signals about *when momentum or information is unreliable* — thematically close to consistency_mom_26w's "Warns" role (2.5) and to A11's sentiment work, which is known to be sparse before 2024 | Check sample size/n_dates on all three before getting interested — if any of them shares the sentiment cluster's thin-history problem, treat it like A11 (wait for data) rather than like a genuine near-miss worth an immediate re-test |
| **G8-05 (options PCR, bulk deals)** | Gen8/9, NEGATIVE EVIDENCE but "PCR IC real (+0.0093) but below materiality bar" | Real, just small | Only worth another look if you find a way to combine it with another small-but-real signal (blending sub-materiality signals can sometimes clear a materiality bar that none clears alone) — don't re-run it alone expecting a different answer, and see the amihud/vol_52w row below for a similar-sized candidate to blend it with |
| **[Added on audit] amihud_13w (t=2.96) and vol_52w (t=-2.02)** | Gen-1 Ledger, both labeled WEAK | Both clear the *statistical* bar (t>2, FDR pass) — amihud_13w even has perfect monotonicity (1.0) — but fall just short of the |IC|≥0.02 promotion threshold (0.0185 and 0.0174 respectively). Same "significant but too small" pattern as accruals_ratio (t=-2.71, IC=-0.0143), which is a third candidate for this cluster. amihud in particular is a liquidity-based signal, which puts it in the same conceptual family as the now-confirmed liquidity gradient (G9-01, Spearman(decile,IC)=-0.818, p=0.0038) behind Delivery's edge | Test whether amihud_13w + vol_52w + accruals_ratio combined (or amihud blended with G8-05's PCR signal above) clears the materiality bar as a small composite even though none does alone — this is a cheap check since all three series already exist |
| **[Added on audit] MOM60 vs. ret_13w — reconcile before trusting either** | MOM60 (Gen-2/3, RESEARCH_SIGNAL, t=3.36) appears to be the same 3-month-momentum construct as ret_13w (Gen-1 Ledger, NOISE, t=1.17) | A momentum-family variant that tested significant in one generation and noise in another, on what should be a near-identical signal, is either a genuine methodology difference worth understanding (different universe, window, or ex-window handling between the two harnesses) or a red flag that one of the two runs has a bug | Before doing anything else with MOM60, diff the exact construction against ret_13w's — this is a quick reconciliation, not a new experiment, and momentum is your one flagship edge so any genuinely-confirmed additional momentum variant is worth having |
| **[Added on audit] RESMOM20** | Gen-2/3, INCONCLUSIVE — non-deployable, t=-5.97 | Explicitly retained as a conditioning feature only, not a standalone strategy — but a t-stat that large is worth using *somewhere*. The ledger's own note says "review whether small-capital construction changes this (unlikely, per its own classification)" | Test it as an additional conditioning/veto input in the same role Delivery and consistency_mom_26w already play (2.1/2.5), rather than trying again as a standalone sleeve, which its own classification already rules out |
| **A11 (FinBERT sentiment), A12 (banking credit depth), A14 (promoter-holding changes)** | Gen-1, RESEARCH (deferred)/thin | Explicitly thin-sample, deferred pending more history (40, sparse-since-2018, and 99 weeks respectively). **[Audit refinement]** within the sentiment cluster specifically, sent_momentum_score (IC 0.0151, t=1.35, n=40) is the only one of four Ledger-level sentiment signals with a non-trivial point estimate — the other three (signed intensity, raw FinBERT score, composite score) all sit at t between -0.15 and -0.11, essentially pure noise regardless of sample size | Set a calendar trigger (e.g., re-test annually) rather than re-running now with the same thin sample — and when you do, prioritize re-testing sent_momentum_score specifically, not the sentiment family broadly |
| **[Added on audit] Q1 short-leg's non-F&O concentration** | Gen-1, C04 — "63% of alpha non-F&O" (buried inside an already-CERTIFIED finding, not a rejection) | **[Corrected 2026-07-31]** The G8-07→G8-11→G9-01 chain was *not* settled: G8-07 compared tiers over different date sets (NON_FNO_TAIL 712 weeks vs 1,070), and G8-11's "correction" zero-filled 41.8% of its winning tier's sample. Measured cleanly, **`SMALL_ADV_Q1` is a strict subset of `NON_FNO_TAIL` from 2015 onward (100% containment)** — F&O eligibility is itself liquidity-gated, so these were never two tiers to choose between but one gradient cut at two points. Large caps lose 0/17 signals; both smaller tiers win 15/17. **G9-01's gradient stands, verified clean** (Spearman −0.818, identical on a common cell set). So the liquidity-gradient phenomenon is real and this row's instinct is right — but the mechanism is a continuous size/ADV constraint, not a discrete F&O boundary, and it is **long-only**: the effect is absent from the certified book, whose F&O-only short leg cannot hedge a disjoint non-F&O long book | Once the capacity-ladder/liquidity-gradient tooling from 2.1 and 2.3 exists, point it at the Q1 short-leg's non-F&O names too and see if the same careful capital-scaling work that made Delivery deployable does anything useful here — this is a "reuse the tool you're about to build anyway" item, not a new research thread |
| **[Added on audit] Paper C, Q1/Q2/Q4 (execution cost, universe, capacity)** | AEP, all "POSITIVE (modest)" — e.g. Q1: 3.90bps vs. 4.20bps in persistent-liquidity regimes, ~7% reduction | These are small, already-resolved, positive findings — not open questions | No further testing needed; fold directly into the cost model / trading rules (e.g., prefer liquidity-persistent names when a trade can go either way) the same way G5-D01/D02 already are |
| **piotroski_fscore, roe (Ledger)** | Gen-1, UNTESTED (n<60) | roe is close (n=58, t=1.82); piotroski has huge effect (t=3.38) but n=5 | roe: near-term re-test once n clears 60. piotroski: needs much more history before the huge effect size is trustworthy — don't act on t=3.38 at n=5 |
| **Accruals data-hygiene fix** | Gen-1, archive CSV corrupted by unescaped quote | Already resolved in this document — Document 3 (Ledger.csv) gives the clean row: IC=-0.0143, t=-2.71, FDR-pass=True, but |IC| below the 0.02 promotion threshold, so WEAK stands | No further action needed on the verdict — just propagate the clean row back into `MASTER_EXPERIMENT_CATALOGUE.csv` to close the data-quality flag |
| **MSRP frontier pillars (Geometry, Networks, Economic Limits)** | MSRP, never opened per 2026-07-25 scope decision | Genuinely unexplored — three of five pillars never run | Long-horizon exploratory thread; don't let this compete with Tier 1 for near-term time, but worth scoping once Tier 1 is through |

---

## 4. Tier 3 — data-gated or long-horizon (don't spend active time here yet)

These share one property: the blocker isn't methodology, it's data you don't currently have, or time that hasn't passed yet. Revisit only when the specific blocker clears.

- **A5_BORROW_CAPACITY** (Gen-5, BLOCKED_DATA) — no borrow availability/fee/utilization dataset exists in the repo. Only actionable if you find a source for Indian securities-lending data (likely to require a paid feed or broker relationship — check whether Upstox or another broker integration exposes anything here before assuming it needs a new vendor).
- **G5-08A_EXECUTION_ENGINE** (Gen-5, BLOCKED_DATA) — needs intraday data; the whole repo is weekly-resolution. Gen-8's G8-06 already tested whether daily resolution recovers information weekly discards and found weekly beats daily for both signals tested — so don't assume finer resolution is automatically valuable even if you do acquire it later.
- **Analyst-revision family, R01–R08** (Gen-1, DATA-BLOCKED, supersedes E11) — needs a point-in-time consensus-estimate feed; 0/448 relevant columns exist. This is probably the most expensive data gap in the whole programme to close (PIT analyst data is rarely free) — worth keeping on a wishlist but not worth active effort until/unless a source appears.
- **G9-02** (institutional ownership explaining the liquidity-IC gradient) — blocked by a hard FII-coverage data cutover in 2023. The 2.3 fix (survivorship rebuild) removes one confound but doesn't solve the coverage gap itself; you'd need either a pre-2023-compatible proxy or a different institutional-ownership data source.
- **Calendar seasonality (A17)** — deliberately never searched due to snooping risk. If you ever do test this, it needs the strictest possible pre-registration (specify the exact calendar effect and window *before* looking at any data) — this is the one place in the whole ledger where "just try it and see" is actively dangerous rather than merely low-value.
- **G5-08E/F, G5-09A/B (operational robustness, shadow portfolio, live walk-forward)** — DEFERRED because they require live deployment or are already implicit in the backtest discipline. Not applicable until you're actually running capital.
- **[Added on audit] E09** (Alpha Registry, "large surprise + muted price reaction → drift") — UNTESTED with n_dates=13, the same thin-sample situation as piotroski_fscore (n=5). Needs a lot more history before it's worth a real look; not actionable now.

---

## 5. Explicitly retired — do not revisit

Documenting this so it's clear these were considered and consciously excluded, not overlooked.

- **Gen-6 representation learning (G6-01/01B/01C, sequence + self-supervised families)** — decisively closed. G6-00B showed the underlying "temporal structure" was 71% a rolling-window artifact (predictive-info R² collapsed 0.964→0.0134), and G8-01/01B independently re-confirmed at 198x scale that the Gen-6 result was an artifact (i.i.d. returns through the identical pipeline scored *higher* than real data). This isn't underpowered, it's actively disconfirmed.
- **Most Gen-2/3 single-factor REJECTED items** (the bulk of G2-A/B/C/D/E and all of G3-T1/T2) — |t| below 2 with no construction error and no data-thinness flag. Real absence-of-information results, not underpowered ones.
- **Gen-5 dynamic-timing levers** (short-budget G5-05B/F10, gross-exposure G5-05A/F11, sector-reallocation G5-04C/F12) — all three TERMINATED_BY_GATE, and the ledger is explicit that this is a **capital-scale-independent skill failure** (verified against `GEN5_NEGATIVE_RESULTS.md`, no capacity mention in the actual failure explanation). Recovering at smaller capital does not change an oracle/economic-gate failure — these are closed regardless of what capital band you eventually deploy at.
- **Gen-4 certified price-state model, as an *integrated* addition to Config-4** — confirmed no incremental value in the certified 2022–26 window (t≈0.49, down from a full-window t≈4.5 that was period-dependent). Note the nuance: this kills *integration into Config-4 specifically*, not necessarily the standalone model as its own future sleeve — but that's speculative enough (a fourth capital allocation on top of momentum, sector rotation, and Delivery) that it doesn't make Tier 2 on its own merits right now.
- **AEP Prototype 1 (vol-regime momentum sizing) and Prototypes 6/7 (adaptive holding/rebalancing)** — clean nulls or failed robustness (2/5 alt splits), not thin-sample or construction-error cases.
- **G2-I01 (macro-defined regime vs. simple price-only crash rule)** — the simple rule outperforms it (catches 28% of worst weeks vs. 15.9%), so there's no case for the more complex macro version even though it cleared a "RESEARCH_SIGNAL (descriptive)" label.
- **Paper C sub-studies 2 and 3 (memory-conditional holding period / rebalancing)** — clean null (0.705 vs. 0.704 Sharpe), independent of the Q3 sizing result in section 2.6.
- **Paper E (confidence-based allocation)** — correctly deferred by its own pre-registered readiness rule (needs ≥2 of 3 input papers validated; currently only Paper A qualifies). This isn't a re-run candidate, it's a downstream consequence — if 2.6/Tier-2 work eventually validates Paper C more fully, Paper E becomes reachable on its own; don't try to build it early.
- **[Added on audit] A05 (low-vol premium) and A15/A19 (momentum×illiquidity, "untradeable")** — A05 is a weaker, redundant version of A06/G-05, which already does the crash-hedge job and is already deployed; nothing is lost by leaving A05 dead. A15/A19 are worth an explicit note *because* they sound adjacent to Delivery: both concentrate in illiquid/thin names, but they are not the same finding. A15/A19's edge is a momentum-illiquidity interaction that was tested and found not to survive transaction costs. Delivery is an independent signal that *was* shown to survive costs, via its own capacity ladder. Sounding similar isn't the same as being the same mechanism — A15/A19 stay retired.
- **[Added on audit] A25 (3-state HMM vs. simple trailing-return crash rule)** — the Gen-1 version of the same finding as G2-I01 above (simple price-only rule beats the fancier regime model at both generations, independently). Two confirmations of the same null, not two separate open questions.
- **[Added on audit] G2-C05, G2-G03 (momentum's conditional behavior across banking-credit and GDP-deceleration macro states), and the broader Gen-5 "EXPAND"-tagged diagnostic cluster (G5-10/11/12/13, G5-07A/B, PAPER2_5_M1–M5, G5-D01/D02)** — these were reviewed and are consciously treated as background/context throughout this document, not overlooked gaps. They're descriptive findings that get folded into "economic laws" and inform *how* to build the items above (e.g., the cost-model figures in 2.1, the capacity-ladder logic in 2.1/2.3) — they aren't standalone tradeable strategies in their own right, so they don't get their own tier entry.
- **[Added on audit] The RECOVERY-phase short-book weakness** — C07 diagnosed it, F04/F07 confirmed it's specifically a sub-phase effect (junk-bounce squeezes shorts near recovery), F09 flagged the short book as the highest-priority lever partly because of it, F15 showed richer transition-aware state raises the relevant ceiling substantially (+0.015→+0.165), and G5-05B then tested a dynamic short-budget lever *using that richer state* and still failed the Stage-4 realizable-skill gate. This thread is fully traced end-to-end and properly closed — it isn't sitting half-finished the way Gen-7 or the DS-battery are.
- **[Added on audit] G8-04 (momentum's cross-sectional IC is regime-dependent by volatility)** — independently reconfirms AEP Prototype 1's rejection (vol-regime momentum sizing doesn't generalize) from a different angle. Consistent with, not in tension with, Prototype 1 staying retired.

---

## 6. [Added on audit] Known limits of this audit — verify before trusting

Two things surfaced in the cross-check that aren't research findings, they're gaps in what I was actually given to work with. Flagging them explicitly rather than silently working around them:

- **ARP's own bucket counts don't add up.** The 141-row `ARP_MASTER_ALPHA_REGISTRY.csv` is summarized as "70 Permanent Dead End, 46 N/A/descriptive, 13 research-incomplete, 3 Deployable Alpha, 2 Portfolio Component, 2 Execution Improvement, 4 flagged for review, 6 Gen-6 representation findings." Those eight numbers sum to 146, not 141 — a 5-row discrepancy in the source document's own arithmetic. I can't resolve this from what I have; it's worth a direct look at the raw CSV.
- **The "13 research-incomplete" and "4 flagged for review" buckets inside that same registry are never individually enumerated anywhere in the materials I was given** — only their counts. I can identify G4-GATE-02 as almost certainly one of the "4 flagged for review" from its own explicit note ("worth one review pass"), but I have no visibility into the other ~16 rows across those two buckets. Everything in this plan is built from Document 1's narrative ledger and Document 2's NSR-EXP catalogue (which stops at AEP and doesn't include ARP's own row-level detail), so there is a real chance something genuinely promising is sitting in one of those two un-enumerated buckets that this plan simply can't see. **Recommended follow-up:** pull `ARP_MASTER_ALPHA_REGISTRY.csv` directly and diff its "research-incomplete" and "flagged for review" rows against everything above — that's the one part of this audit I can't do without the actual file.

---

## 7. A note on sequencing given limited hands-on time

Everything in Tier 1 is designed to be runnable as unattended batch jobs (backtests, re-specifications, robustness splits) rather than requiring long stretches of continuous attention — the actual thinking-heavy part of each item is in the pre-registration step (deciding the test *before* running it), which is a short, focused task, followed by a longer unattended compute step, followed by a short review. That structure is worth preserving deliberately: write the pre-registration and kick off the run in one sitting, let it run unattended, review results in a separate short sitting. It's the same discipline the programme has already used everywhere else (walk-forward gates, lockbox holdouts) — the only change here is applying it retroactively to work that never got the treatment.

Suggested order, roughly by (payoff × how self-contained the task is):

1. **2.3** (universe rule fix) — do this first since it underlies the integrity of everything else, including 2.1.
2. **2.1 + 2.2** (Delivery integration + regime test) — run together since 2.2's output feeds 2.1's sizing.
3. **2.4, Delivery-family cluster only** — extends what 2.1/2.2 just taught you about Delivery's behavior.
4. **2.6** (Prototype 3 robustness) — cheapest, fastest, already-positive result.
5. **2.5 and 2.8 together** (Sub-study 2a and Paper D near-misses) — same shape of task (power check + one bounded, properly-split re-test), cheap enough to batch.
6. **2.4, remaining clusters** and **2.7** (Gen-7 redesign) — the two most compute/design-heavy items, once the faster wins are banked.
7. **Tier 2**, opportunistically, as time allows or triggers fire. Pull `ARP_MASTER_ALPHA_REGISTRY.csv` directly at some point in this window too (Section 6) — it's a quick check that might resurface something this plan couldn't see.
