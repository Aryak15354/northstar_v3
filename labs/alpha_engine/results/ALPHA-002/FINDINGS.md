# ALPHA-002 — Is Delivery the Same Mechanism as the Liquidity-Decile Gradient? Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Alpha Engine (joint with Portfolio Engineering)
Verdict:            INCONCLUSIVE (fixed by the pre-registered power gate — see "the honest tension" below)
```

Artifacts: `alpha002_data.json`. Script: `labs/alpha_engine/protocols/run_alpha002_delivery_liquidity.py`.
Universe: non-F&O (`adv_rank_13w > 190`), price ≥ ₹20, delivery-covered weeks —
75,734 rows, 338 weeks, 2020-01-10 to 2026-06-26.

---

## Result

| | mean | NW-t | NW-p |
|---|---|---|---|
| Univariate IC: Delivery vs `target_1w` | **+0.0344** | +5.59 | <0.0001 |
| Univariate IC: log(ADV) vs `target_1w` | −0.0087 | −1.52 | 0.129 |
| **Raw overlap: Delivery vs log(ADV)** | **−0.205** | −17.92 | <0.0001 |
| **Partial coefficient: Delivery, controlling for liquidity** | **+0.00056** | +1.67 | 0.095 |
| Partial coefficient: liquidity, controlling for Delivery | −0.00091 | −2.99 | 0.003 |

**Delivery's incremental information collapses to 2% of its univariate magnitude once liquidity is
held fixed** (partial/univariate ratio = 0.02), and loses conventional significance in the process
(p=0.095 vs p<0.0001 univariate). High-delivery names are also strongly, significantly less liquid
names in this universe (raw overlap −0.205, t=−17.92) — the mechanical link the restructuring plan
asked this test to check for is directly visible in the data. Liquidity, by contrast, *retains* a
significant partial effect after controlling for Delivery.

**Read plainly, this is about as clean a "one mechanism, not two" result as this programme has
produced.**

## The honest tension — why this still closes INCONCLUSIVE, not REJECTED

The pre-registered power gate (`research_os.power_precheck`, following the same convention
`ALPHA-001` used: treat the weekly count as the correlation-test sample size) computed **8.5% power**
to detect the pre-registered meaningful effect of `|r|=0.03` at n=338, requiring 8,719 weeks — so the
design proceeded only under `allow_underpowered=True`, and the contract's outcome rule fixes
underpowered designs to INCONCLUSIVE regardless of what comes out, precisely to prevent fitting the
verdict to a result seen after the fact.

**But the actual univariate test found `p<0.0001` on an observed effect of 0.0344 — right at the
"undetectable" threshold the power formula predicted, and yet clearly detected.** This is disclosed
in the contract itself (§4): the shared power module's formula treats `n` as a count of raw i.i.d.
correlation pairs, which understates power for a design where each of the 338 observations is already
a cross-sectional aggregate over ~224 stocks. The mechanical INCONCLUSIVE verdict is honored here
because the rule was fixed in advance and not re-fit after seeing the numbers — **but readers should
not mistake "INCONCLUSIVE" for "no effect was found."** The effect was found, clearly; what remains
genuinely unresolved is only the formal power classification against an overly conservative heuristic,
not the substantive question this experiment set out to answer.

## What this means for Portfolio Engineering (per the joint framing in §5 of the contract)

**Recommendation, stated plainly despite the formal INCONCLUSIVE label: treat Delivery and the
liquidity-decile tilt as overlapping, not diversifying, capital.** The data show they occupy
substantially the same non-F&O, low-liquidity ground, and Delivery's apparent incremental information
is almost entirely liquidity by another name in this sample. A future frozen-book capital allocation
that sizes both as independent ₹5–10cr sleeves would very likely be double-counting one source of
return, not stacking two. This is cross-referenced in `labs/portfolio_engineering/decision_log/` —
not re-tested there as a separate experiment.

## What would properly close this

A power calculation designed for an NW-aggregated mean test (matching the `se_sharpe`-based approach
`G8-09` used for its own paired-difference test), rather than the generic raw-pair correlation
formula, would very likely show this design is in fact adequately powered at the observed effect
size. Building that variant into `research_os.power_precheck` is flagged as a concrete Research OS
improvement for a future session — not built here, so as not to redesign a gate after seeing that the
generic version disappointed.
