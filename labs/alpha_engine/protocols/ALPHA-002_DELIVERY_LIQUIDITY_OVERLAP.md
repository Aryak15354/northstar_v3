# ALPHA-002 — Is Delivery the Same Mechanism as the Liquidity-Decile Gradient?

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                alpha_engine (joint with portfolio_engineering — see §5)
Depends On:         results/gen8/G9-01/G9-01_FINDINGS.md (liquidity-decile IC gradient),
                    results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md (Delivery's standalone validation),
                    results/gen8/G8-09/G8-09_FINDINGS.md (Delivery's portfolio-level capacity ladder)
```

## 1. The coincidence this resolves

Two independently-run capacity analyses converged on the same capital band without ever being
compared directly: Delivery's overlay Sharpe peaks around ₹5–10cr (G8-09's capital ladder), and the
liquidity-decile momentum tilt peaks around ₹1–10cr (G8-12's capacity bound). Both signals are also
constructed on **overlapping ground** — Delivery is defined on the non-F&O universe (G8-09 §s_add),
and the liquidity-decile gradient's strongest effect is concentrated in the low-ADV, non-F&O tail
(G9-01). **Neither prior analysis asked whether Delivery's own predictive power is just the liquidity
gradient wearing a different name.** This experiment asks that question directly.

## 2. Research question

Does `delivery_pct_4w_avg`'s cross-sectional information about `target_1w`, within the non-F&O
universe, survive controlling for `adv_13w` (the same liquidity measure driving G9-01's gradient)? If
Delivery's incremental information collapses to (statistically indistinguishable from) zero once
liquidity is held fixed, Delivery and the liquidity gradient are evidence of **one** mechanism, not
two independent edges — and the restructuring plan is explicit that this must be reported as such,
not preserved as two separate "edges" if the evidence says otherwise.

## 3. Pre-registered specification

Universe: non-F&O tickers (`adv_rank_13w > 190`, exactly `run_final_portfolio_matrix.py`'s own
`fno_ok` definition — and per G9-01, the definition the "non-F&O" tier actually was throughout this
programme), price >= ₹20, restricted to weeks with non-null `delivery_pct_4w_avg` (2020-01-10 through
2026-06-26, 338 weeks — the full systematic coverage window, per G8-09's own established start date;
see §6 for why the full window, not a holdout, is used here).

Each week *t*, cross-sectionally:
1. **Univariate IC** of `delivery_pct_4w_avg` vs `target_1w` (Spearman).
2. **Univariate IC** of `adv_13w` vs `target_1w` (Spearman) — the liquidity control on its own.
3. **Raw overlap**: Spearman correlation between `delivery_pct_4w_avg` and `adv_13w` themselves — the
   most literal test of "are high-delivery names just low-liquidity names."
4. **Multivariate (partial) regression**: `target_1w ~ z(delivery_pct_4w_avg) + z(log(adv_13w))`,
   OLS, cross-sectional, each week. Delivery's **partial** coefficient is the quantity of interest —
   this is what "incremental IC, controlling for liquidity" means operationally.

All four series (weekly univariate ICs, weekly overlap correlation, weekly partial coefficients) are
aggregated across the 338 weeks with a Newey-West HAC mean test (non-overlapping weekly cross-
sections, so autocorrelation here is expected to be far milder than the rolling-window MSCI designs —
still tested formally, not assumed away).

## 4. Power disclosure — computed before running

```
n = 338 weekly cross-sections (independent weekly draws, not an overlapping rolling window)
meaningful effect (contract): |r| = 0.03  (matching G9-01's own decile-level IC magnitudes —
                                            the smallest effect this programme has treated as real)
```
Run via `research_os.power_precheck` before results are examined; reported in the findings alongside
the actual numbers, per this lab's binding reporting discipline. **Disclosed in advance:** the shared
module's power formula treats `n` as the count of raw i.i.d. correlation pairs, whereas this design's
338 observations are each themselves a cross-sectional statistic aggregated over ~224 stocks/week —
the same convention `ALPHA-001` already used (treating "n weeks" as the correlation-power sample
size). This is a conservative heuristic, not a literal model of the actual NW mean-test, and is
expected to show as formally underpowered for a |r|=0.03 effect regardless of what the real test
finds — the script proceeds under `allow_underpowered=True` per programme convention, and the
resulting classification is fixed by the same INCONCLUSIVE-if-underpowered rule used throughout this
programme, not loosened after seeing the number.

## 5. Why this is a joint Alpha Engine / Portfolio Engineering question

**Alpha Engine** owns the mechanism-overlap question itself (is this one edge or two) — registered
here as an Alpha Engine experiment because it's fundamentally asking whether a claimed source of
return is genuinely distinct. **Portfolio Engineering** is the direct consumer of the answer: if the
two collapse into one mechanism, the frozen book must not size Delivery and the liquidity tilt as if
they were diversifying, independent bets in the same capital band — that would double-count one
source of return. This finding is cross-referenced in Portfolio Engineering's decision log rather than
duplicated as a second experiment there, per this programme's cross-lab discipline.

## 6. Why the full 338-week window is used, not a fresh holdout

This is a **mechanism/overlap diagnostic** between two already-known, already-partially-validated
signals — it is not a discovery pipeline testing a new hypothesis for the first time, and it produces
no new tradeable claim on its own (a "these are the same thing" finding does not need OOS protection
the way a new predictive claim would). Using the full window is analogous to G9-02's own joint
mechanism regression, which likewise used its full available joint-coverage window rather than
carving out a holdout. No lockbox is spent by this test.

## 7. Outcome classification

- If Delivery's partial coefficient (controlling for liquidity) remains statistically significant
  (NW p < 0.05) **and** retains most of its univariate magnitude (partial/univariate ratio >= 0.5):
  **VALIDATED** — Delivery and the liquidity gradient are separable mechanisms.
- If Delivery's partial coefficient loses significance, or its magnitude collapses below half its
  univariate value: **REJECTED (as separable)** — reported explicitly as "Delivery and the liquidity
  gradient collapse into one explanatory variable," per the restructuring plan's own framing.
- If underpowered at the pre-registered effect size: **INCONCLUSIVE**, per this programme's standard
  gate.

## 8. Exclusions

- Does not re-test Delivery's standalone validation (ARP's own certification stands regardless).
- Does not re-test the portfolio-level integration question (G8-09, already closed UNRESOLVED at book
  level for unrelated reasons — insufficient history, not mechanism overlap).
- Single pre-registered specification (one control variable, one universe, one window) — no scan
  across alternative liquidity measures or delivery windows.
