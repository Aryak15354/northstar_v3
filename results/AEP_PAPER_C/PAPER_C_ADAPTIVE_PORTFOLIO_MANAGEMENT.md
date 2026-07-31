> ## ⚠ CORRECTION — Sub-study 1 (2026-07-31, Gen-10 T0-02)
>
> **Q1, Q3 and Q4 were given verdicts with no significance test attached.** Supplying them:
>
> | | archived | corrected |
> |---|---|---|
> | **Q3 Sizing** | **ACCEPTED** — "the most economically material result in this sub-study", Sharpe 0.692 → 0.727, vol −23% | **REJECTED** — paired **t = +0.50**, p = 0.62, bootstrap CI [−0.156, +0.209]; the effect is **0.18× its own 80%-power detection floor**, and it gives up **3.26 %/yr** of return |
> | **Q1 / Q4 Execution** | POSITIVE (modest) | **directional, not significant** — t = −1.75 at both ₹100cr and ₹500cr |
> | **Q2 Universe** | POSITIVE (modest) | **untested** — a name-level correlation with no SE; not recomputed, left open |
>
> Three further problems with Q3, each independently disqualifying:
> 1. **It is not a liquidity rule.** `PERSISTENT_REGIMES = {"NORMAL_UP","STRESS"}` — the sizing keys
>    off the market-regime label; no liquidity-persistence measurement enters the decision.
> 2. **The regime selection is wrong on its own terms.** De-gearing in CRASH alone scores 0.8164 and
>    in STRESS alone 0.7775, both beating the bundled rule's 0.7271 — and STRESS is a regime the rule
>    holds at *full* exposure.
> 3. **It charges nothing for the de-gearing** — gross returns, no turnover cost at regime flips, no
>    cash yield on the un-invested half.
>
> Q3 is also **Gen-5 F11 / G5-05A rediscovered** (regime-conditioned gross exposure), already
> TERMINATED_BY_GATE at three times this effect size.
>
> **Practical consequence:** the recommendation to prefer liquidity-persistent names when a trade can
> go either way would encode a t = −1.75 effect worth a quarter of a basis point. Not supported.
>
> **Sub-studies 2+3 are unaffected** — a clean null is not manufactured by a missing standard error.
>
> Evidence: `results/gen10/T0-02/`. Archive addendum: `archive_addenda/GEN10_ADDENDUM_002.md`
> (NSR-FIND-000043). Original text below left intact.

---

# Paper C — Adaptive Portfolio Management: FINDINGS (FROZEN v1.0)

Per `docs/aep_protocols/PAPER-C_RESEARCH_CONTRACT.md`. Entirely Branch 2 — every result below is judged
on cost/turnover/capacity/risk, never on raw predictive improvement, per the standing constraint.
`scripts/aep/paper_c_adaptive_portfolio.py`, `results/AEP_PAPER_C/liquidity_substudy_data.json`.

## Sub-study 1 — Liquidity State Dynamics (4 independently-reported questions)

**Q1 Execution — MODEST, DIRECTIONALLY POSITIVE.** Average round-trip trade cost on the momentum book
(Rs500cr, real `IndianEquityCostModel`) is lower in persistent-liquidity regimes (NORMAL_UP/STRESS,
3.90bps) than in others (4.20bps) — a ~7% relative reduction, real but small in absolute terms
(n=638 vs 393 weeks).

**Q2 Universe — MODEST, DIRECTIONALLY CONSISTENT.** Per-name liquidity-persistence (lag-1 autocorrelation
of differenced `amihud_13w`) correlates negatively with realized round-trip cost (corr=−0.119, n=517
names) — names with more persistent liquidity are modestly cheaper to trade, consistent with Q1's
regime-level finding at the individual-name level.

**Q3 Sizing — REAL, MEANINGFUL.** Scaling book exposure by liquidity-persistence state (100% in
NORMAL_UP/STRESS, 50% otherwise) improves net Sharpe from 0.692 to 0.727 (~5% relative improvement)
**while reducing annualized volatility by ~23%** (0.249 → 0.192) — the most economically material result
in this sub-study. This is a genuine risk-adjusted improvement, not merely a return/vol trade-off (Sharpe
improved, not just vol shrank proportionally with return).

**Q4 Capacity — CONFIRMS Q1's direction, stable across capital scale.** The persistent-vs-other cost gap
holds at both tested NAV levels (Rs100cr: 3.64 vs 3.89bps; Rs500cr: 3.90 vs 4.20bps) — the
regime-conditional execution advantage is not an artifact of one specific capital level.

**Sub-study 1 verdict: Q1/Q2/Q4 real but modest (execution-level, single-digit-bps effects); Q3
meaningful (portfolio-level, ~5% Sharpe / 23% vol effect).** All four questions answered independently as
required; none forced to agree with the others.

## Sub-studies 2+3 — Adaptive Holding Period + Adaptive Rebalancing (joint): NULL RESULT

**Design:** compared Config-4's fixed weekly rebalance against a memory-conditional variant (rebalance
every 2 weeks specifically when `vol_52w` is in its Low state — the long-trend-memory regime per M-01B/
M-04 — and every week otherwise).

**Result: essentially no difference** (fixed weekly Sharpe 0.705 vs. memory-conditional 0.704; vol
0.251 vs 0.252). **A clean, informative negative result** — the pre-registered null hypothesis (holding
period has no measurable effect once cost is properly accounted for, matching Gen-5 F23's finding that
0–3wk execution delay was largely irrelevant given the book's already-low turnover) is **not rejected**.
This is consistent, not contradictory, with M-01B/M-04's memory findings: those establish that certain
primitives' *information* persists longer, but this result shows that exploiting that persistence via
*rebalance cadence specifically* does not translate into a measurable portfolio-level benefit for this
book — the effect, if any, is too small to distinguish from noise at this book's existing turnover level.

## Combined Paper C conclusion
**Two of six sub-questions (Q3 Sizing, and Q1/Q2/Q4 collectively as one directionally-consistent
execution finding) show real, actionable results; the Holding/Rebalancing joint study is a clean null.**
Per the standing portfolio-level constraint (Gen-5 F08), Q3's result is the strongest candidate for
further engineering — a liquidity-regime-conditional exposure-scaling rule, analogous in spirit to Paper
B's volatility-sizing idea but with a materially more robust initial result (no Phase B/C robustness
testing has been run on Q3 yet — that would be the natural next step before treating this as engineerable,
mirroring Paper B Sub-study 1's discipline exactly).

## What Paper E should take from this
Paper E (Confidence Engine) should treat Q3's liquidity-scaling result as a candidate input, explicitly
UNTESTED for robustness (no sensitivity/definition-robustness pass has been run, unlike Paper B's
Sub-study 1) — do not treat it as more validated than Paper B's rejected volatility-sizing idea just
because its initial result looked stronger; the difference in validation depth, not just point-estimate
size, must be tracked.

---
**Paper C is FROZEN as of this document. Verdict: MODIFIED (Q3 real but robustness-untested; Q1/Q2/Q4
real but modest; Holding/Rebalancing REJECTED as a joint study — clean null).**
