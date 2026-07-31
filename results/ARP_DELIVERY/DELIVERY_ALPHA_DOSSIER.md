# Delivery Family — Alpha Dossier (ARP Stage 3/4/9)

**Status: RECOVERED, VALIDATED at realistic personal/boutique capital.** The one confirmed ARP recovery
candidate (`ARP_STAGE1_CENSUS_AND_FINDINGS.md`), now backtested for real at small-capital scale rather
than asserted from the original 2026-07 institutional-scale certification alone.

## Scientific rationale
Delivery percentage (`delivery_pct_z52` / `delivery_pct_4w_avg`) predicts forward returns, momentum-
orthogonally (correlation with the momentum book: 0.14). True-OOS 2024–26 IC +0.033 (t=2.94), survives
ten adversarial certification tests (breadth, sector-neutrality, liquidity/ownership controls, leave-
one-year-out, parameter-plateau) — see `results/gen23/DELIVERY_CERTIFICATION.md`.

## Original discovery and supporting experiments
`G2-E03` (Gen-2, discovery) → `G2-E03b` (post-discovery smoothing transformation) → `G2-E03-OVERLAY`
(decisive long-only overlay test, `scripts/gen23/exp_delivery_overlay.py`) → **this dossier**
(`scripts/arp/delivery_capacity_recovery.py`, 2026-07-25), which reproduces the overlay test exactly as
a correctness gate, then extends it to a real small-capital cost ladder.

## Why it was never deployed (the capacity/liquidity casualty)
The entire tradable edge concentrates in non-F&O, non-shortable names (IC 0.033, t=5.2 there; dead in
F&O names, t=1.0). A market-neutral book requiring F&O shortability cannot access it. The `ADD_nonfno_tail`
construction (momentum longs + a high-delivery non-F&O tail) sidesteps this: it is long-only, requires no
shorting, and improves the book without concentrating capacity (117 names vs. 48–64 for the
VETO/CONFIRM alternatives).

## Correctness gate (2026-07-25, reproduced fresh)
| Construction | Gross Sharpe | Net Sharpe @20bps | Turnover | Avg names |
|---|---|---|---|---|
| CONTROL (momentum-only) | 0.911 | **0.698** | 0.201 | ~96 |
| ADD_nonfno_tail | 1.004 | **0.767** | 0.211 | **117** |

Matches `DELIVERY_CERTIFICATION.md`'s stated 0.70/0.77 exactly — the engine is faithful, reproduced
independently rather than merely cited.

## Capacity curve (NEW — real `IndianEquityCostModel` per-trade cost, not a flat-bps proxy, at 13
realistic capital levels from ₹5 lakh to ₹500 crore)
| Capital | CONTROL net Sharpe | ADD net Sharpe | ADD median %ADV per trade |
|---|---|---|---|
| ₹5L | 0.702 | 0.771 | 0.00% |
| ₹10L | 0.701 | 0.770 | 0.00% |
| ₹25L | 0.700 | 0.769 | 0.01% |
| ₹50L | 0.699 | 0.767 | 0.01% |
| ₹1cr | 0.711 | 0.774 | 0.01% |
| ₹2cr | 0.720 | 0.788 | 0.02% |
| **₹5cr** | **0.723** | **0.792** | 0.05% |
| ₹10cr | 0.720 | 0.789 | 0.11% |
| ₹25cr | 0.711 | 0.778 | 0.27% |
| ₹50cr | 0.699 | 0.764 | 0.54% |
| ₹100cr | 0.683 | 0.745 | 1.08% |
| ₹250cr | 0.649 | 0.705 | 2.71% |
| ₹500cr | 0.611 | 0.660 | 5.41% |

**Interpretation — a genuinely non-obvious result:** net Sharpe does NOT monotonically decrease with
capital. It is roughly flat from ₹5L–₹50L (statutory/brokerage costs dominate, at their full proportional
rate below the ₹20 brokerage cap's notional threshold), **rises to a peak around ₹5–10cr** (large enough
trades now benefit from the brokerage cap, while market impact is still negligible), then **degrades
materially above ₹100cr** as market impact (participation vs. ADV) starts to dominate — fully consistent
with Gen-5's own F19/F22 findings (capacity not binding at moderate AUM; slippage, not statutory fees,
dominates cost at scale) now confirmed on this specific alpha via real, independently-computed costs,
not assumed.

**Practical implication:** the Delivery family (`ADD_nonfno_tail` construction) is deployable across the
ENTIRE personal-to-boutique capital range this dossier tested (₹5L–₹100cr), with its best risk-adjusted
efficiency specifically in the ₹2–25cr band — not a niche-tiny-capital-only opportunity as the founding
ARP hypothesis might have suggested, but genuinely usable well beyond retail scale, degrading gracefully
(not collapsing) even out to ₹500cr.

## Turnover profile
Low (0.201–0.211 weekly turnover, ~44-week-scale realized holding, consistent with Config-4's own
low-turnover character per Gen-5 F03/F23) — the overlay does not materially increase the book's turnover
burden.

## Market dependency / regime dependency
Not tested in this dossier — the underlying certification (`DELIVERY_CERTIFICATION.md`) found the effect
robust across leave-one-year-out (t=3.3–4.3 for every excluded year) and across mid/large caps (t=4.4/2.1
respectively), but no MSRP-style regime-conditional test has been run on this specific signal. Flagged as
an open question, not assumed resolved.

## Interaction effects
Momentum-orthogonal (correlation 0.14) — genuinely diversifying, not redundant, per the original
certification. Portfolio-level integration with the frozen Gen-5 momentum + sector-rotation book (per
Gen-5 F08's standing rule: evaluate at the portfolio level, never standalone) is the next open item —
not yet executed in this dossier.

## Implementation complexity
Low — the `ADD_nonfno_tail` construction is a straightforward long-only overlay (add a non-F&O,
high-delivery tail to the existing momentum long book), no new data source required (delivery data
already flows through the existing pipeline), no shorting infrastructure needed.

## Recommended deployment capital
₹5 lakh through ₹100 crore, with peak risk-adjusted efficiency around ₹2–25 crore. Above ₹250cr,
degradation is material but not collapse (net Sharpe still 0.61–0.66 at ₹500cr) — a genuine, gradual
capacity frontier, not a cliff.

## Confidence
High for the signal's existence and the overlay construction's correctness (independently reproduced).
Moderate for the specific capacity numbers above ₹100cr (extrapolated from a relatively short OOS window,
2024–26, ~2 years — the original certification's own disclosed limitation).

## Open questions

> **[G10 2026-07-31] Questions 1 and 2 are now ANSWERED — both negative.** See
> `results/gen10/T1-06/`. Question 3 is moot: AEP Papers B and C did not mature (see
> `archive_addenda/GEN10_ADDENDUM_001.md` and `002`).

1. ~~Portfolio-level integration with the frozen Gen-5 book~~ — **ANSWERED: does not promote.**
   Tested as an independently-sized sleeve (the architecture G8-09 explicitly left untested when it
   closed the *overlay* version). At Sleeve B's own CI lower bound the optimal weight is **zero at
   every capital band**; on the point estimate it declines monotonically with capital and reaches zero
   by ₹25cr. **Both integration architectures are now closed.**
2. ~~Regime-conditional robustness~~ — **ANSWERED: not regime-conditional.** RISK_ON minus RISK_OFF
   IC difference = +0.0217, **t = +1.49**. The individual cells (t = 4.20 vs 0.89) must not be read as
   a difference — that is the error M-02A made. A **static** sleeve weight is correct.
3. The `MARKET_STATE_SPECIFICATION_v1.md` dimensions were not used to condition this analysis —
   **moot**, since the Papers B/C relationships this depended on did not survive re-testing.

> **⚠ CORRECTION to this dossier's "Interaction effects" section.** It reports Delivery as
> "momentum-orthogonal (correlation 0.14) — genuinely diversifying". **That 0.14 is *signal*
> orthogonality — the correlation of the delivery ranking with the momentum ranking.** The realised
> correlation of the two long-only *sleeves' returns* is **+0.842**: two long-only Indian equity books
> share market beta whatever their signals do. There is very little diversification to harvest, so the
> blend's case rests entirely on Sleeve B's higher standalone Sharpe — which is **not significant**
> (+0.335, t = +1.60 on 338 weeks). Downstream documents quoting the 0.14 as a diversification
> argument (incl. `NORTHSTAR_HANDBOOK.md` and the remediation plan) inherit this error.

**What still stands:** the signal's existence, the `ADD_nonfno_tail` construction's correctness, and
the capacity curve — Gen-10 reproduced the ₹5–10cr peak by a third independent route. Delivery remains
a validated, capacity-bound signal. What is closed is the claim that adding it to the book helps.

## Candidate verdict
**RECOVER, CONFIRMED at real cost, deployable ₹5L–₹100cr+.** This is ARP's first (and per Stage 1's
census, only) fully validated recovery. Recommend: portfolio-level integration test against the frozen
Gen-5 book as the next concrete step (open question 1), before calling ARP's Delivery recovery fully
complete per `ARP_CHARTER.md`'s Stage 9 (Alpha Dossier) and Stage 10 (Final Deployable Portfolio)
requirements.
