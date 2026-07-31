> ## ⚠ VERDICTS RE-DERIVED (2026-07-31, Gen-10)
>
> Three prototypes' outcomes change once the Papers that tested them are corrected:
>
> | prototype | archived outcome | re-derived |
> |---|---|---|
> | **2 — Conditional Momentum Confirmation** | MODIFIED (Paper B Sub-study 2) | **no role confirmed.** 2b retired (its CONFIRMED verdict rests on a pooled stock-week SE and reverses out of sample), 2c/2d rejected, 2a closed as a documented near-effect |
> | **3 — Liquidity Persistence** | MODIFIED; "Q3 sizing real" | **Q3 REJECTED** — paired t = +0.50, 0.18× its own detection floor; also not a liquidity rule, and a rediscovery of Gen-5 G5-05A |
> | **4 — Resolution Study** | MODIFIED; "only monthly clears, narrowly" | **REJECTED at all five resolutions** — monthly fails correction for the five it was selected from |
>
> Prototypes 1, 5, 6, 7 and 8 are unaffected. Prototype 8 (Confidence Engine) was already DEFERRED
> pending ≥2 of 3 validated input papers; after these corrections **Paper A remains the only one that
> qualifies**, so it stays deferred and is now further from reachable, not closer.
>
> Evidence: `results/gen10/GEN10_SYNTHESIS.md`. Addenda: `archive_addenda/GEN10_ADDENDUM_001..003.md`.

---

# AEP Prototype Registry

**These are engineering hypotheses, not experiments — none has a research contract or a backtest yet.**
Per `AEP_CHARTER.md` rule 2, none is evidence; each needs its own pre-registered design before any code
runs. This registry exists to organize *which* hypothesis to design first and *what depends on what* —
the deliverable requested before jumping into Stage 2/backtesting, not a substitute for it.

## Branch and stream summary
| # | Prototype | Branch | Stream | Depends on |
|---|---|---|---|---|
| 1 | Low-Volatility Momentum Sizing | 1 (Direct Alpha) | Adaptive Alpha Engine | M-04, F15 |
| 2 | Conditional Momentum Confirmation | 1 (Direct Alpha) | Adaptive Alpha Engine | I-05, M-05 |
| 3 | Liquidity Persistence (4 sub-variants) | 2 (Portfolio) | Adaptive Execution Engine | M-02, M-03 |
| 4 | Resolution Study (was "Monthly State Decisions") | 1 (Direct Alpha) | Adaptive Alpha Engine | F17 |
| 5 | Composite State Machine | Foundational | Adaptive Market State Engine | I-01, I-03B, M-01B, M-02, M-04, M-05 |
| 6 | Adaptive Holding Period | 2 (Portfolio) | Adaptive Portfolio Engine | M-01B, M-02, M-03 |
| 7 | Adaptive Rebalancing | 2 (Portfolio) | Adaptive Portfolio Engine | M-02, M-03 |
| 8 | Confidence Engine | 1/2 boundary | Adaptive Portfolio Engine (consumes Alpha Engine output) | Prototypes 1, 2, 5, plus M-02 |

**Sequencing implication of the dependency structure:** Prototype 5 (Composite State Machine) is
foundational to Prototype 8 (Confidence Engine) — the Confidence Engine cannot be meaningfully designed
until the state vector it consumes exists. Prototypes 1, 2, 3, 4 can proceed independently and in
parallel; 6 and 7 depend on the same MSRP Memory-pillar evidence (M-01B/M-02/M-03) as 3, so should be
designed together rather than as three unrelated efforts even though they answer different questions.

---

## Prototype 1 — Low-Volatility Momentum Sizing (Branch 1, Direct Alpha)
**Base finding:** MSRP M-04 (trend memory is longer in Low-Vol than High-Vol `vol_52w` states — opposite
the naive prior) + Gen-5 F15 (richer state materially raises decision-value ceilings, within tested
bounds). **This is expanded into a 5-phase programme, not a single backtest:**
- **Phase A — Replication.** Reproduce M-04's Low-Vol/High-Vol memory-duration split exactly, as a
  correctness gate before anything else (same discipline as every prior generation's reproduction check).
- **Phase B — Sensitivity.** M-04 used a median (50%) split. Retest at 25/33/40/60/75% splits — if the
  Low-Vol/High-Vol duration gap collapses away from the median, the effect is fragile, not robust, and
  the prototype should not proceed to Phase D.
- **Phase C — Definition robustness.** Retest with `vol_13w`, `idio_vol_13w`, `beta_104w`, and a combined
  volatility state (e.g. first principal component of the volatility family, per MSRP I-03B's confirmed
  coherent family) in place of `vol_52w`. Survival across definitions is required before trusting this as
  a general "volatility regime" effect rather than a `vol_52w`-specific artifact.
- **Phase D — Engineering.** Only after B/C survive: design the actual sizing rule — binary (e.g. 100%
  exposure in Low-Vol, 50% in High-Vol) vs. continuous (position size as a smooth function of the
  volatility state). Pre-register both before comparing.
- **Phase E — Economic interpretation.** Why would this be true? Candidate hypothesis for the pre-
  registered write-up (not yet tested): information arrives faster / gets priced in faster during
  high-volatility periods, so trends decay faster — worth stating explicitly as a falsifiable economic
  mechanism, not just an empirical pattern, before calling this a finding rather than a correlation.

## Prototype 2 — Conditional Momentum Confirmation (Branch 1, Direct Alpha)
**Base finding:** MSRP I-05 (consistency_mom_26w: Dead standalone, 2nd-largest incremental MI in the
Greedy Basis) + M-05 (Interaction Persistence Hypothesis confirmed for memory). **The conceptual shift
this prototype represents is significant and worth stating explicitly: `consistency_mom_26w` moves from
"bad factor" to "good conditional factor"** — not a marginal refinement, a different scientific object.
**Research question reframed:** not "does it predict?" (already answered: no, standalone) but **"when
does it predict, and what does it do when it does?"** Candidate roles to investigate, not yet
distinguished by any evidence collected so far:
- **Confirms** a trend signal (increases confidence/sizing when both agree).
- **Warns** (flags trends likely to fail, independent of confirming good ones).
- **Delays** (a lagging indicator that shifts entry timing rather than screening).
- **Accelerates exits** (a signal about when to leave a position, not whether to enter one).
Engineering surface once the role is determined: entry filter, exit filter, position-sizing multiplier,
holding-period modifier, or a standalone confirmation/confidence score. **This is plausibly a full paper
on its own**, not a quick prototype — the base evidence (I-05, M-05) is strong, but which of the four
candidate roles is correct is completely undetermined and needs its own dedicated design, not assumed.

## Prototype 3 — Liquidity Persistence (Branch 2, Portfolio/Execution) — FOUR separate sub-variants,
not one
**Base finding:** MSRP M-02 (`amihud_13w` regime-locked in NORMAL_UP/STRESS) + M-03 (state-lifetime
confirmation). Originally proposed as a single execution-timing rule; **correctly identified as
conflating four genuinely different questions that need four separate designs:**
1. **Execution** — when should a trade be placed, given the current liquidity-persistence regime?
2. **Universe** — should names with unstable (non-regime-locked) liquidity be excluded or down-weighted
   from the tradable universe entirely, independent of timing?
3. **Sizing** — should position size increase specifically when liquidity persistence is high (a
   different mechanism from Prototype 1's volatility-based sizing)?
4. **Capacity** — can more capital be deployed specifically during persistent-liquidity regimes, i.e. is
   the Capacity Ladder (ARP Stage 4) itself regime-conditional rather than a fixed curve?
These do not have to reach the same conclusion — e.g. Execution and Capacity could both be regime-
conditional while Universe and Sizing are not. Each needs its own evidence before being folded together.

## Prototype 4 — Resolution Study (Branch 1, Direct Alpha) — was "Monthly State Decisions," reframed
**Base finding:** Gen-5 F17 (near-zero MI between hand-engineered state and the *weekly* correct action —
explicitly scoped, multi-week/continuous granularity never tested). **Correctly identified as the riskiest
prototype in this registry**, because Gen-5 already spent real effort failing at weekly timing (G5-05A/
05B/04C) — reopening any state-dependent-decision question needs a strong, specific justification per the
standing burden-of-proof principle, not just "try a different number." **Redesigned as a Resolution
Study, not a single monthly retest**: compute the state→action information curve across weekly, biweekly,
monthly, 6-week, and quarterly decision granularity, and let the curve itself indicate whether there is a
resolution at which real information exists — rather than picking "monthly" a priori and testing only
that. If the information curve is flat (near-zero at every resolution), this closes the question
permanently and more decisively than F17 alone did; if it rises at some resolution, that becomes the
justified, evidence-driven target for any further design.

## Prototype 5 — Composite State Machine (Foundational, feeds all other streams)
**Not derived from a single MSRP experiment — a synthesis across nearly all of them:** I-01 (volatility
dominates raw information), I-03B (volatility family coherent, momentum superfamily is not), M-01B
(primitive-specific memory), M-02 (regime-locked liquidity), M-04 (volatility-state modulates trend
memory), M-05 (interaction-conditional memory). **The observation motivating this prototype:** the
program has independently discovered a volatility state, a trend state, a liquidity state, a consistency
state, a transition state (Gen-5 G5-12A), a memory state, and an interaction state — all measured
separately, never combined. **Proposal:** build a single Market State Vector (e.g. `STATE = {macro_regime,
vol_state, liquidity_persistence_state, trend_memory_state, consistency_state}` rather than the single
categorical `regime` label Gen-5 always conditioned on) and condition future prototypes on the full
vector rather than one dimension at a time. This is explicitly what MSRP's own trajectory (Information →
Memory, with Geometry/Networks still unopened) was heading toward, and it directly extends Gen-5's F15
finding that richer state raises ceilings — this prototype IS the richer state, assembled from parts that
already exist but have never been combined. **This is foundational, not a quick add-on**: Prototype 8
(Confidence Engine) cannot be properly designed without this existing first.

## Prototype 6 — Adaptive Holding Period (Branch 2, Portfolio Engineering)
**Base finding:** MSRP M-01/M-02/M-03 (memory pillar, in full) — memory determines how long a signal's
information should be trusted. **Direct engineering consequence, never previously considered:** Config-4
uses a fixed rebalance/holding structure (Gen-5 F03/G5-10: ~44-week realized average holding via trade
band) regardless of which primitive is driving a given position. Proposal: primitives with longer measured
memory (e.g. `vol_52w`) could justify holding related positions longer before re-evaluation; primitives
with short/reversal-type memory (`ret_4w`) might justify faster turnover on the positions they drive.
This is a genuinely new idea with no prior Gen-5 test — Gen-5's holding-period findings (F03) were about
the AGGREGATE book's realized holding period, never about VARYING it by which signal is currently
dominant.

## Prototype 7 — Adaptive Rebalancing (Branch 2, Portfolio Engineering)
**Base finding:** MSRP M-02/M-03 (regime-locked memory, state-lifetime). **Proposal:** rebalance cadence
itself becomes state-dependent — slower rebalancing when the dominant driving primitive is in a
persistent-memory regime (e.g. `vol_52w` in NORMAL_UP/STRESS), faster when a reversal-type signal
(`ret_4w`) is active. Closely related to Prototype 6 (both derive from the same M-02/M-03 evidence) and
should be designed as one combined holding-period/rebalancing study, not two independent ones, to avoid
double-counting the same underlying evidence as two "wins."

## Prototype 8 — Confidence Engine (Branch 1/2 boundary — consumes Alpha Engine output, feeds Portfolio
Engine)
**Not derived from a single finding — the capstone synthesis of Prototypes 1, 2, and 5.** Proposal:
replace a binary buy/no-buy signal with a continuous confidence score,
`confidence = f(volatility_state, trend_memory, interaction/consistency_state, liquidity_state, regime)`,
and size positions by confidence rather than by a fixed rule. **Explicitly the most architecturally
ambitious item in this registry** — it presupposes Prototype 5 (the state vector to condition on) and
ideally Prototypes 1 and 2 (specific, validated conditional relationships to combine) already exist in
validated form. Attempting the Confidence Engine before its dependencies are designed and tested would be
building on hypotheses, not evidence — explicitly out of sequence per the dependency map, not to be
started first regardless of how appealing it is as an end state.

---

## What this registry does NOT do
Provide evidence for any of the 8 prototypes above — every one remains an untested hypothesis. Decide
sequencing beyond the dependency constraints noted (Prototype 5 before Prototype 8; Prototypes 6/7 studied
together). Replace the pre-registered research contract each prototype needs before any backtest is run.
