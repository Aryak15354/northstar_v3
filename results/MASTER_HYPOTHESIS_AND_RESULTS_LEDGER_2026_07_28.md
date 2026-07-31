> ## ⚠ SUPERSEDED IN PLACES BY GEN-10 (2026-07-31)
>
> The Gen-10 Remediation Programme re-tested this ledger's Tier-1 open items and **corrected six
> verdicts and closed three questions.** Rows affected are marked **[G10]** inline below. Full
> evidence: [`results/gen10/GEN10_SYNTHESIS.md`](gen10/GEN10_SYNTHESIS.md); archive addenda in
> [`archive_addenda/`](../archive_addenda/).
>
> | § | what changed |
> |---|---|
> | §8c Paper B | **2b "Warns" CONFIRMED → RETIRED** (pooled stock-week SE; reverses out of sample). 2a was the stronger role and is now closed. **No role confirmed.** |
> | §8d Paper C | **Q3 ACCEPTED → REJECTED** (paired t = 0.50). Q1/Q4 → directional, not significant. Q2 flagged untested. |
> | §8e Paper D | **Monthly ACCEPTED → REJECTED** (fails correction for the five resolutions it was selected from). F17 now settled at all cadences. |
> | §2a DS battery | 14 items given their first out-of-sample split: **zero new deployable alpha.** Two duplicate registrations; broad-coverage ICs inflated 30–40% by a universe-composition artifact. |
> | §1b / §2e | `ret_13w`, `MOM60` and `DS-U-01` are **one signal** (per-date Spearman 0.969) under three configurations, not three findings. |
> | §6 Gen-7 | **H-A1 resolved NEGATIVE at adequate power.** Cross-asset transmission retired; H-A2/A3/A4 close with it. |
> | §9 ARP | Delivery's two open questions answered: **not regime-conditional**, and the sleeve architecture **does not promote**. |
>
> **Three verdict-vocabulary cautions this ledger's own §"How to read this" should now carry:**
> RESEARCH_SIGNAL predicts full-sample fit, not out-of-sample survival; ACCEPTED was in places issued
> from point estimates with no test; and no two ICs are comparable unless target horizon, target
> relativity, universe/panel and window all match.

---

# Northstar Research Programme — Master Hypothesis & Results Ledger

**Compiled:** 2026-07-28
**Purpose:** Every research hypothesis tested across the Northstar V3 programme (Gen-1 → Gen-9, plus AEP/ARP/MSRP), with its verdict and supporting stat, in one place. Extracted directly from the underlying registries — not re-derived or summarized from narrative docs.

## How to read this

- **Verdict vocabulary is inherited from each generation's own registry** and isn't fully standardized: REJECTED/FAILED_SIGN/NOISE (no info), RESEARCH_SIGNAL (statistically real, not necessarily deployable), VALIDATED/ACCEPTED/POSITIVE_EVIDENCE (cleared the bar), INCONCLUSIVE (didn't clear either way), TERMINATED_BY_GATE (failed a pre-registered economic/skill gate after passing earlier stages), BLOCKED_DATA (never testable — no dataset exists), DEFERRED (deliberately not run), REGISTERED/PENDING (pre-registered, never executed).
- **Deduplication note:** ARP's master registry (141 rows) mostly *re-classifies* Gen-2/3/4/5/6/MSRP experiments already listed in their own sections below — those are not repeated a second time under ARP; only ARP's genuinely new output (the recovered Delivery alpha dossier) is broken out separately. AEP's "Discovery Census" restates Gen-5's F01–F23 findings verbatim as its evidence base — those appear once, under Gen-5.
- **Data-quality flag:** the permanent archive's `MASTER_EXPERIMENT_CATALOGUE.csv` (`archive/11_registries/`) has its `question`/`hypothesis` columns filled with a placeholder string ("see per-generation decision log") for all but a few rows — the actual hypothesis wording used below for those IDs was reconstructed from the per-generation source registries (Alpha Registry, Master Index, F-registries), not copied verbatim from the archive CSV. One row (**NSR-EXP-000174**, `accruals_ratio`) is corrupted in that source file by an unescaped quote character that broke column alignment; treat its stats as unreliable and check `results/LEDGER.csv` directly if needed.
- **Archive scope:** the permanent NSR-EXP/NSR-FIND registry (181 experiments, 46 findings) covers Gen-1 through AEP only, frozen 2026-07-25. **Gen-7, Gen-8/9, and ARP are not yet in the permanent archive** — they're presented here from their own live registries.

---

## Topline counts

| Programme | Hypotheses tested | Rough verdict mix |
|---|---|---|
| Gen-1 (Foundational Discovery) | 44 (Alpha Registry) + 35 (Ledger, signal-level, overlapping concepts) | 7 VALIDATED, ~9 FAILED_SIGN, ~7 NOISE, 3 CORE, 1 DIVERSIFIER, rest REJECT/RESEARCH/UNTESTED |
| Gen-2/3 (Info Transmission) | 139 unique experiment IDs | ~85 REJECTED, ~30 RESEARCH_SIGNAL, ~15 INCONCLUSIVE, 1 deployable (delivery) |
| Gen-4 (Engineering/Audit) | 3 registered + ~8 unregistered narrative artifacts | Certified one new price-state alpha standalone; failed to integrate into the live book |
| Gen-5 (Portfolio-State Action) | 23 findings (F01–F23) + ~30 lever/paper experiments | Momentum architecture validated; every dynamic-timing lever (short-budget, gross-exposure, sector-reallocation) TERMINATED_BY_GATE |
| Gen-6 (Representation Learning) | 7 experiments | 0/3 architecture families (sequence, self-supervised, feasibility) showed positive evidence |
| Gen-7 (CAIT — cross-asset transmission) | ~40 carrier-lag pathway tests + 8 methodological findings | 0/310 pairs survive correction; all "successes" downgraded to INCONCLUSIVE on independent audit |
| Gen-8/9 (Remediation & Re-Discovery) | ~20 experiments | Confirmed Gen-6/7 were underpowered, not "true negatives"; found a real liquidity-IC gradient (non-F&O tail) |
| AEP (Alpha Engineering) | 26 discovery-census items (= Gen-5 restated) + 8 prototypes + 4 Papers (A–D) + Paper E deferred | Paper A Accepted, B/C/D Modified, E Deferred |
| ARP (Alpha Recovery) | 141 re-classified + 4 new (Delivery dossier) | Recovered 1 deployable alpha family (Delivery, capacity-bound) |
| MSRP (Market Structure) | 10 experiments (Information + Memory pillars only; Geometry/Networks/Economic Limits never opened) | 2 POSITIVE_EVIDENCE synthesis freezes, individual results mostly POSITIVE_EVIDENCE/DESCRIPTIVE |

**Certified state as of 2026-07-28:** momentum (`res_mom_52w_ex4w` + composite) is the only certified scalable stock-selection edge. Sector rotation is a certified modest diversifier. Delivery% is a validated, momentum-orthogonal, capacity-bound signal. Short-term reversal and cross-asset transmission are statistically detectable in places but economically inaccessible or unconfirmed on independent replication. Essentially every macro/credit/rates/fiscal/housing hypothesis tested has been rejected as a direct stock-selection signal.

---

## 1. Gen-1 — Foundational Discovery

### 1a. Alpha Registry (`results/ALPHA_REGISTRY.md`/`.csv`) — permanent record, 44 entries

| ID | Hypothesis | Verdict | Key stat / reason |
|---|---|---|---|
| A01 | Residual momentum (52w ex 4w) predicts 4w sector-relative returns | CORE | IC 0.046, HAC-t 5.83, ICIR 2.21; lockbox IC +0.062 |
| A02 | 12-1 price momentum (`ret_52w_ex4w`) | CORE | IC 0.039, ICIR 1.72; must-beat baseline |
| A03 | Sharpe-momentum 26w + consistency-momentum 26w composite | CORE | validated Phase-1; EW composite beats all reweightings |
| A04 | Short-term reversal (1w/4w) — losers bounce | REJECT | IC -0.028, t -6.82 but net Sharpe -5.0 at 4187%/yr turnover |
| A05 | Low-volatility premium is long-leg deployable in India | REJECT (regime-conditional) | monotonicity 0.4; only +0.019 IC in CRASH regime |
| A06 | Low-beta/BAB as crash hedge | CONDITIONAL | IC +0.038 in CRASH vs negative elsewhere; powers G-05 |
| A07 | Value composite predicts returns | REJECT (regime) | IC ~0/wrong sign 2019-2025 |
| A08 | ROCE quality predicts returns | REJECT (regime) | wrong sign in 2019-2025 growth regime |
| A09 | Accruals as diversifying sleeve | REJECT (artifact) | Sharpe 1.19 but orthog t 1.94; Sharpe 2.46→-0.15 by subperiod |
| A10 | SUE/PEAD multi-week drift (calendar-gridded) | REJECT (this window) | eps_sue t 1.14; IC decays 4→13w, no PEAD pattern |
| A11 | FinBERT news sentiment predicts returns | RESEARCH (deferred) | only 40 dense weeks (2024+) |
| A12 | Banking credit depth signals | RESEARCH (deferred) | 2018+ too sparse |
| A13 | FII flow following | REJECT | L/S -3.7%/yr Sharpe -0.63 |
| A14 | Promoter-holding changes | RESEARCH (thin) | 99 weeks only, Sharpe 0.50 |
| A15 | Momentum × illiquidity interaction harvestable | REJECT (untradeable) | edge sits exactly where impact cost kills it |
| A16 | Sector rotation (13w, top-2/bottom-2 of 7) | DIVERSIFIER | net Sharpe 0.56; all validation gates pass |
| A17 | Calendar seasonality | REJECT (snooping risk) | deliberately not searched |
| A18 | Ridge regression on 15 price features vs EW composite | REJECT | OOS IC 0.044 < composite 0.049 |
| A19 | LightGBM on price features vs EW composite | REJECT (net-of-cost) | IC 0.056 but 2.3x turnover; edge is illiquid-momentum |
| A20 | G-05 crash overlay (rotate long leg to low-beta in CRASH) | KEEP (mandatory) | Sharpe 0.94→0.98; +2.2pp/20y concentrated in crises |
| A21 | Trade-band hysteresis (enter 60th/keep 40th pctile) | KEEP | turnover 308→151%/yr; IR 0.63→0.84 |
| A22 | Targeted 0.5x Q1-short (F&O) vs blunt NIFTY hedge | KEEP (core of Config-4) | 12.3% CAGR Sharpe 0.86 vs 6.7% |
| E01 | Announcement-anchored sector-std SUE predicts 4-13w returns | REJECT (this window) | rev_sue 13w t -2.04, wrong sign |
| E02 | PEAD in event-time (not calendar-gridded) | REJECT (this window) | no significant drift; 2-4w bucket t 0.88 |
| E03 | EPS/net-profit growth acceleration | REJECT (this window) | ortho-IC +0.0155 @4w, t 1.28 < 2.0 |
| E04 | Revenue growth acceleration | REJECT (this window) | ortho-IC +0.009 @4w, t 1.63 |
| E05 | Operating-margin trajectory | REJECT (this window) | t 1.4-1.7; suggestive not significant |
| E06 | ROCE trajectory improvement | REJECT (this window) | wrong sign, 13w t -2.24 |
| E07 | Improving fundamentals + weak momentum → positive alpha | REJECT (this window) | underperforms -3.4%/yr; worst cell |
| E08 | Deteriorating fundamentals + strong momentum → negative alpha | REJECT (this window) | outperforms +6.9%/yr; momentum dominates |
| E09 | Large surprise + muted price reaction → drift | UNTESTED (thin) | n_dates 13 < 60 |
| E10 | Cash-backed surprise beats raw surprise | REJECT (this window) | opposite of hypothesis |
| E11 | Analyst estimate/target revisions predict returns | UNTESTED (no data) | no PIT analyst data anywhere |
| E12 | Composite expectations score (E01-E10 survivors) | NOT BUILT | no component cleared gates |
| C04 | Q1 short-leg selection alpha genuine & executable | CERTIFIED-BOUNDED | proxy +9.5%/yr; F&O-only +6.3%/yr; 63% of alpha non-F&O |
| C05 | Survivorship-corrected rebuild leaves edge intact | DATA-BLOCKED | 34/409 delistings; bias likely conservative |
| C07 | RECOVERY is frozen book's structural weak spot | DIAGNOSED | post-recovery Q1 beats Q5 +10.6%/yr; no spec change |
| C08 | Execution rules recover cost w/o changing exposure | REJECT (no free lunch) | no rule wins under strict exposure-preserving gate |
| R01–R08 | Analyst-revision family (breadth/magnitude/accel/disagreement/etc.) | DATA-BLOCKED | supersedes E11; no PIT consensus feed (0/448 cols) |
| A23 | Macro transmission predicts cross-sectional/sector returns | REJECT (this window) | sector-tilt net Sharpe -0.30 |
| A24 | Regime-conditional value/reversal hedges momentum in crashes | REJECT (disproved) | reversal +0.50 corr to momentum in-crash, not a hedge |
| A25 | 3-state HMM regime vs simple trailing-return crash rule | REJECT (simple adequate) | HMM catches 3% of worst weeks vs 28% for simple rule |
| A26 | Event drift (bulk-deal pressure + insider flags) as idio sleeve | REJECT (this window) | bulk_net_pressure incr-IC -0.017, t -1.5 |
| A27 | Macro-state conditioning improves price-feature LightGBM | REJECT (this window) | OOS IC 0.0384→0.0359; adds noise |

### 1b. Ledger (`results/LEDGER.csv`) — signal-level verdicts, 35 rows

| Signal | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| val_roce_5yr_avg_zscore | ROCE 5yr value predicts returns | FAILED_SIGN | IC -0.0222, t -1.89 |
| ret_4w | 1-month return predicts returns | FAILED_SIGN | IC -0.0186, t -2.91 |
| screener_roce | ROCE predicts returns | FAILED_SIGN | IC -0.0182, t -1.65 |
| val_earnings_quality_score_zscore | Earnings-quality value score | FAILED_SIGN | IC -0.0095, t -0.97 |
| val_composite_score_zscore | Composite value score | FAILED_SIGN | IC -0.0089, t -0.76 |
| rev_sue | Revenue SUE | FAILED_SIGN | IC -0.0075, t -0.76 |
| operating_margin | Operating margin level | FAILED_SIGN | IC -0.0072, t -0.90 |
| skew_26w | 26w return skew ("lottery" effect) | FAILED_SIGN | IC 0.0025, t 0.59 |
| combined_sue | Combined SUE | FAILED_SIGN | IC -0.0007, t -0.08 |
| screener_promoter_change_1q | Promoter buying (1q change) | NOISE | IC 0.0124, t 1.30 |
| ret_13w | 3-month momentum | NOISE **[G10]** | IC 0.0089, t 1.17 — same signal as MOM60/DS-U-01 (per-date Spearman 0.969); the differing verdicts are panel+target, not signal |
| eps_sue | EPS SUE | NOISE | IC 0.0088, t 1.14 |
| screener_fii_change_1q | FII ownership change (1q) | NOISE | IC 0.0071, t 0.68 |
| val_discount_to_fair_pct_zscore | Discount-to-fair value | NOISE | IC 0.0034, t 0.53 |
| val_margin_of_safety_zscore | Margin of safety | NOISE | IC 0.0034, t 0.52 |
| combined_revision_score | Analyst revision score | NOISE | IC 0.0031, t 0.36 |
| bulk_net_pressure_21d | Bulk-deal net pressure | NOISE | IC 0.0018, t 0.46 |
| piotroski_fscore | Piotroski F-score quality | UNTESTED (n<60) | IC 0.0652, t 3.38, n=5 |
| roe | ROE level | UNTESTED (n<60) | IC 0.0195, t 1.82, n=58 |
| sent_momentum_score | Sentiment momentum | UNTESTED (n<60) | IC 0.0151, t 1.35, n=40 |
| sent_signed_sentiment_intensity | Signed sentiment intensity | UNTESTED (n<60) | IC -0.001, t -0.15 |
| sent_sentiment_score | FinBERT sentiment score | UNTESTED (n<60) | IC -0.0007, t -0.11 |
| sent_northstar_score | Sentiment composite score | UNTESTED (n<60) | IC -0.0007, t -0.11 |
| **res_mom_52w_ex4w** | Residual momentum | **VALIDATED** | IC 0.0459, t 5.83 |
| **ret_52w_ex4w** | 12-1 classic momentum | **VALIDATED** | IC 0.0387, t 4.64 |
| **sharpe_mom_26w** | Sharpe-scaled momentum | **VALIDATED** | IC 0.0284, t 3.67 |
| **consistency_mom_26w** | Momentum consistency | **VALIDATED** | IC 0.0249, t 3.88 |
| **ret_26w** | 6-month momentum | **VALIDATED** | IC 0.0238, t 3.02 |
| ret_1w | 1-week short-term reversal | VALIDATED (short leg) | IC -0.0278, t -6.82 |
| beta_104w | Beta / BAB | VALIDATED (short leg) | IC -0.0224, t -2.17 |
| amihud_13w | Amihud illiquidity premium | WEAK | IC 0.0185, t 2.96 |
| vol_52w | 52w realized vol (low-vol) | WEAK | IC -0.0174, t -2.02 |
| accruals_ratio | Accruals (exploratory) | WEAK — **⚠ corrupted in archive CSV**, verify here | IC -0.0143, t -2.71 |
| vol_13w | 13w realized vol (low-vol) | WEAK | IC -0.014, t -1.89 |
| cash_conversion | Cash conversion quality | WEAK | IC 0.0086, t 1.73 |

---

## 2. Gen-2/3 — Domestic & Global Information Transmission

139 unique experiment IDs across `results/MASTER_EXPERIMENT_INDEX.csv` and `results/gen23/registry.jsonl`. Governed by `GEN2_GEN3_RESEARCH_CONSTITUTION.yaml`.

### 2a. Deep-search factor battery (DS-)

> **[G10] All 28 items were evaluated FULL-SAMPLE** (`"lockbox_used": false`). Gen-10 gave 14 deduped
> items their first out-of-sample split: **5 delivery items died; 3 survived and proved to be one
> already-deployed signal** (pairwise rho 0.72–0.92, incremental t 0.27–0.61 vs the incumbent G2-E03b);
> **4 momentum-quality items died** after correction, incl. DS-F4-02 (+6.33 → OOS +1.73); **DS-F2-03,
> the largest |t| here, was retired on cost** — turnover 4091%/yr vs A04's 4187%/yr. **Net new
> deployable alpha: zero.** DS-U-04 ≡ DS-F5-01 and DS-U-03 ≡ DS-F4-01 are duplicate registrations, so
> the 28-item FDR denominator was wrong. Broad-coverage ICs below are inflated 30–40% by a
> universe-composition artifact (delivery signals are immune). See `archive_addenda/GEN10_ADDENDUM_004.md`.


| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| DS-F1-01 | Delivery×momentum: delivery confirms/vetoes momentum longs | RESEARCH_SIGNAL | t -1.88 |
| DS-F1-02 | Delivery×OI build: conviction + positioning | REJECTED | t 1.47 |
| DS-F1-03 | Abnormal delivery during volume surge | REJECTED | t 0.51 |
| DS-F1-04 | Delivery confirmation during price breakout | RESEARCH_SIGNAL | t -2.95 |
| DS-F1-05 | Delivery-price divergence (accumulation) | RESEARCH_SIGNAL | t 4.21 |
| DS-F1-06 | Delivery jump above own trend | RESEARCH_SIGNAL | t 3.46 |
| DS-F2-01 | Momentum works better when delivery-confirmed | REJECTED | t 0.42 |
| DS-F2-02 | Momentum IC in LOW delivery state | REJECTED | t 0.49 |
| DS-F2-03 | Reversal stronger after liquidity shocks | RESEARCH_SIGNAL | t -8.91 |
| DS-F2-04 | Value works when price weak (disagreement) | RESEARCH_SIGNAL | t 2.20 |
| DS-F2-05 | Sentiment predicts only around attention spikes | REJECTED | t 1.82 |
| DS-F2-06 | Momentum stronger in low-volatility names | RESEARCH_SIGNAL | t 3.38 |
| DS-F3-01 | Delivery predicts which momentum longs succeed | RESEARCH_SIGNAL | t 2.34 |
| DS-F3-02 | Delivery-vs-history predicts momentum-long success | RESEARCH_SIGNAL | t 3.02 |
| DS-F3-03 | OI build predicts momentum-long success | REJECTED | t -1.21 |
| DS-F3-04 | Volume surge predicts momentum-long failure (exhaustion) | **OVERTURNED on OOS** | full-sample t -4.4 → discovery t -0.06 |
| DS-F3-05 | Delivery-price divergence predicts momentum-long success | REJECTED | t 1.63 |
| DS-F4-01 | Smooth (risk-adjusted) momentum beats jumpy momentum | RESEARCH_SIGNAL | t 3.06 |
| DS-F4-02 | Momentum with declining participation = vulnerable | RESEARCH_SIGNAL | t 6.33 |
| DS-F5-01 | Stock delivery relative to sector | RESEARCH_SIGNAL | t 4.93 |
| DS-F5-02 | Earnings surprise relative to sector peers | REJECTED | t 1.73 |
| DS-F5-03 | Momentum relative to sector | REJECTED | t -0.91 |
| DS-F6-01 | Exporter sectors × INR depreciation | REJECTED | no t-stat |
| DS-F6-02 | Metals/Mining × copper shock | REJECTED | no t-stat |
| DS-U-01 | Unconditional 3m momentum (reference) | RESEARCH_SIGNAL | t 2.91 |
| DS-U-02 | Unconditional delivery | RESEARCH_SIGNAL | t 4.06 |
| DS-U-03 | Unconditional smooth momentum | RESEARCH_SIGNAL | t 3.06 |
| DS-U-04 | Unconditional sector-relative delivery | RESEARCH_SIGNAL | t 4.93 |

### 2b. Wave-1/2 primitive battery (sentiment, events, credit, fundamentals, microstructure)

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| G2-A01 | Sentiment surprise vs trailing-normal | REJECTED | t 0.35 |
| G2-A02 | Sentiment trajectory (acceleration) | REJECTED | t -1.61 |
| G2-A03 | Abnormal news intensity marks new info | INCONCLUSIVE | t 2.29 |
| G2-A06 | Composite novelty-adjusted sentiment | REJECTED | t 0.79 |
| G2-A0b | Sentiment level baseline | REJECTED | t 0.20 |
| G2-A0c | Narrative momentum of info flow | INCONCLUSIVE | t 2.28 |
| G2-B01n | Negative-event drift | REJECTED | t 0.36 |
| G2-B01p | Positive-event drift | REJECTED | t 0.36 |
| G2-B02a | Bulk-deal net buying pressure | REJECTED | t 0.82 |
| G2-B02b | Sustained bulk-deal net volume | REJECTED | t 0.57 |
| G2-B03a | Insider buying signals undervaluation | REJECTED | no t-stat |
| G2-B03b | Order-win announcements → revenue visibility | INCONCLUSIVE | no t-stat |
| G2-B04 | Credit-rating level/upgrade → lower risk premium | REJECTED | no t-stat |
| G2-C01 | Accelerating credit deployment (personal/housing) predicts bank/NBFC returns | REJECTED | t -0.53 |
| G2-C02 | Credit impulse as market-wide timing signal | REJECTED | t 0.15 |
| G2-C03 | Credit-equity disagreement signals reversal | INCONCLUSIVE | t -1.01 |
| G2-C04 | Credit-deposit ratio drives bank-sector returns | REJECTED | t -0.59 |
| G2-C04a | Rising GNPA → weak bank returns | REJECTED | t -0.40 |
| G2-C04b | Stronger CET1 buffer → resilience | REJECTED | t 1.21 |
| G2-C05 | Momentum behaves differently across banking-system macro states | RESEARCH_SIGNAL (descriptive) | tercile IC spread 0.0114 |
| G2-D01a | SUE drift | INCONCLUSIVE | t 2.09 |
| G2-D01b | Acceleration in analyst EPS revisions | REJECTED | t 1.57 |
| G2-D01c | Composite earnings-revision breadth | REJECTED | t 1.60 |
| G2-D02a | Improving profitability (ROE inflection) | INCONCLUSIVE | IC 0.0660 |
| G2-D02b | Operating-margin improvement | INCONCLUSIVE | IC 0.0454 |
| G2-D03a | Accruals anomaly | REJECTED | t 0.96 |
| G2-D03b | Higher earnings quality → reliable returns | REJECTED | t 1.98 |
| G2-D04a | Cheaper vs fair value → higher forward return | REJECTED | t 0.93 |
| G2-D04b | Composite valuation attractiveness | REJECTED | t 1.92 |
| G2-D05a | Rising FII ownership → smart-money accumulation | REJECTED | t -1.91 |
| G2-D05b | Rising promoter holding → insider conviction | REJECTED | t 0.70 |
| G2-D05c | High promoter pledge → financial stress | REJECTED | t 0.60 |
| G2-E01 | Abnormally high F&O OI vs own history | REJECTED | t -0.27 |
| G2-E02 | 4-week OI build → continuation | REJECTED | t -0.03 |
| **G2-E03** | **High delivery% vs own history = conviction/informed accumulation** | **RESEARCH_SIGNAL → Deployable Alpha (recovered by ARP)** | IC 0.0318, t 8.02; capacity-bound to non-F&O names |
| G2-E03-OVERLAY | Delivery as long-only overlay/veto on frozen momentum book | KEEP_AS_FEATURE | Sharpe 0.70→0.77 @20bps, non-concentrating |
| G2-E03b | Sustained high delivery over 4 weeks | DEPLOYABLE_SLEEVE | IC 0.0250, t 4.06 |

### 2c. Macro/rates/fiscal batch (added 2026-07-28, in `registry.jsonl` only, not yet in Master Index CSV)

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| A23-RETEST | Sector returns lag domestic credit/GDP conditions (retest w/ 2005-2026 series) | REJECTED | t -1.41 |
| G2-F01 | Negative/falling real policy rate signals accommodative, bullish conditions | REJECTED | t -1.20 |
| G2-F02 | Term-structure slope is a business-cycle timing indicator | REJECTED | t 1.11 |
| G2-F03 | Sector leadership rotates with monetary-policy cycle | REJECTED | t 0.28 |
| G2-F04 | T-bill curve dislocation is an early-warning funding-stress signal | REJECTED | t 0.14 |
| G2-G01 | Widening fiscal deficit trajectory is a headwind | REJECTED | t 0.90 |
| G2-G02 | GDP growth acceleration is a timing signal | REJECTED | t 0.76 |
| G2-G03 | Retest of "momentum dominates fundamentals" using GDP deceleration | RESEARCH_SIGNAL (descriptive) | tercile IC spread 0.015 |
| G2-G04 | Widening WPI-CPI wedge is a margin-compression headwind | REJECTED | t -0.74 |
| G2-G05 | Accelerating house-price growth is a tailwind for realty/HFC/cement | REJECTED | t 0.86 |
| G2-H01 | India's "Buffett Indicator" signals aggregate overvaluation | REJECTED | t 1.38 |
| G2-I01 | Macro-defined regime beats G-01's price-only crash-catch rule | RESEARCH_SIGNAL (descriptive) | catches 15.9% of worst weeks vs simple rule's 28% |

### 2d. Cross-asset transmission battery (G3-)

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| G3-A02a | Stock crude-exposure × crude move → response | REJECTED | no t-stat |
| G3-A02b | Stock INR-exposure × INR move → response | REJECTED | no t-stat |
| G3-T1 (composite/copper/crude/dxy/gold/natgas/steel/us10y/usdinr) | Historical asset-beta × contemporaneous shock predicts return, 9 assets | REJECTED (all 9) | \|t\| 0.06–1.63, none significant |
| G3-T2 (same 8 assets) | Acceleration of asset-sensitivity × shock predicts return | REJECTED (all 8) | \|t\| 0.14–1.50, none significant |
| G3-T4 | INR depreciation helps exporters, hurts importers | INCONCLUSIVE — rejected as strategy | Importer leg wrong-signed (t +3.30); exporter leg alone correct (t +2.06) |
| G3-T5 | Analyst disagreement flags momentum failures via cross-asset transmission | INCONCLUSIVE | t 2.28 |

### 2e. Gen-4 gate items (registered under Gen-2/3 tag `gen2x3`) and momentum reference

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| G4-02A | Certified price-state model adds incremental value inside frozen Config-4 | REJECTED (no incremental value) | t 0.49, 2022-26 window |
| G4-GATE-01 | Non-price info predicts returns beyond momentum/sector/delivery | RESEARCH_SIGNAL → SUPERSEDED | price features leaked into "non-price" test |
| G4-GATE-02 | Corrected non-price-only gate re-test | RESEARCH_SIGNAL (weak, not promotable) | t 3.79 but net-negative @2x cost |
| MOM-DET-COMPOSITE | Composite of validated momentum determinants | RESEARCH_SIGNAL → **OVERTURNED on OOS** | true-OOS t -1.26 (n.s.) |
| MOM20 | 1-month price momentum | REJECTED | t -0.68 |
| MOM60 | 3-month price momentum | **[G10] = ret_13w** | t 3.36 on the broad enriched panel; ~36% of that IC is a universe-composition artifact; PANEL-A gives t=0.91 |
| RESMOM20 | Residual (idiosyncratic) 20d momentum | INCONCLUSIVE — non-deployable | t -5.97; conditioning feature only |

---

## 3. Gen-4 — Engineering / Formalization / Audit

Mostly a repair-and-formalize phase, not a hypothesis-generation phase. Only 3 items got permanent archive IDs (NSR-EXP-000082/083/084, listed in §2e above under `gen2x3`). The rest were narrative artifacts in `results/gen4/`, never assigned permanent IDs:

| Artifact | What it tested | Result |
|---|---|---|
| `G4_00B_PROVENANCE_AUDIT.md` | Reconciles a reproducibility break in the certified Config-4 baseline | Drift explained: stored Sharpe 0.9235 was survivorship-inflated; re-certified panel gives Sharpe 0.8105 (0.8471 with G-05 crash overlay) |
| `CONFIG4_HOLDINGS_AND_REPRO_BREAK.md` | Recovers exact historical Config-4 holdings, confirms the break above | Holdings reconstructed bit-for-bit |
| `G4_01_PRICE_DECOMPOSITION.md` / `G4_01B_05_FINDINGS.md` | Certifies a new price-state model (momentum+reversal+vol+path, 81 features) as a candidate 3rd alpha | **CERTIFIED standalone**: 5/5 folds positive (mean IC +0.027), liquidity-neutral, net Sharpe +0.96 @2x cost, +0.51 @3x cost |
| `G4_04A_FINDINGS.md` | Studies the price-state signal's decay and stabilization | Alpha front-loaded in week 1 (earlier "slow decay" was an accounting artifact); weekly EWMA smoothing (α=0.33) beats 4-week-rebalance workaround |
| `G4_STABILIZATION_PLATEAU.md` | Is the signal's turnover problem estimator noise or genuine instability? | Seed bagging does NOT stabilize rankings; temporal smoothing does — EWMA α=0.33 adopted |
| `G4_02A_AUDIT.md` / `G4_02A_INTEGRATION_RESULT.md` | Does the certified price-state model add value integrated into the actual frozen Config-4 book? | **NO INCREMENTAL VALUE** — looks good full-window (t≈4.5) but vanishes in the certified 2022-26 window (t≈0.49); period-dependent, fails promotion bar |

**Bottom line:** Gen-4 discovered and certified a genuinely new standalone alpha (price-state model) but it added nothing once integrated into the live book — nothing from Gen-4 was promoted to production.

---

## 4. Gen-5 — Portfolio-State Action Research

Governed by `GEN5_RESEARCH_CONSTITUTION.yaml`. Shifted the research object from stock-alpha to portfolio-level action/lever design.

### 4a. Diagnostic findings (F01–F23)

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| F01 | Momentum composite is 4 independent alpha sources | REJECTED (redundant) | Shapley 19–31% each but LOO≈0; single feature (0.863) ≈ full composite (0.847) |
| F02 | Short leg generates positive expected return | REJECTED (risk control, not alpha) | Long-only Sharpe -0.206 vs canonical; short leg halves vol, cuts maxDD 24pts |
| F03 | Config-4 is statically miscalibrated | REJECTED (near-optimal) | Gross Sharpe-invariant 0.8-1.2x; static calibration accepted |
| F04 | Short book protects against crash bottoms | REJECTED (reframed to transition protection) | STRESS +14.5bps/wk but CRASH -12.6bps/wk (junk bounce squeezes shorts) |
| F05 | G-05 crash overlay earns its complexity | **ACCEPTED** | +0.037 Sharpe, ~0 return cost |
| F06 | Regime labels carry real temporal structure | **ACCEPTED** | χ²=2275.2, p≈0 |
| F07 | Short P&L is uniform within STRESS | REJECTED (sub-phases exist) | +53.5bps entering → +27.1 persisting → +0.4 pre-CRASH → -36.1 pre-RECOVERY |
| F08 | Short book's value is standalone utility | REJECTED (covariance effect) | corr(momentum,short)=-0.88 |
| F09 | Short book is the highest-priority lever | ACCEPTED (synthesis) | Convergent evidence F02/F03/F04/F07/F08 |
| F10 | Dynamic short budget beats static 0.5 ratio | **TERMINATED_BY_GATE** | ceiling +0.1645; realizable +0.0344, CI [-0.105,+0.167] |
| F11 | Regime-conditioned gross exposure timing beats static 1.0x | **TERMINATED_BY_GATE** | ceiling +0.1554; realizable +0.1052, CI straddles gate |
| F12 | Sector-rotation sleeve reallocation beats frozen 80/20 | **TERMINATED_BY_GATE** | ceiling +0.1530; realizable +0.1000, CI dips negative |
| F13 | Trailing vol/dispersion predict forward book performance | REJECTED (premise fails) | vol-target reverses post-2015; dispersion proxy wrong-signed |
| F14 | Discrete action-grid coarseness caused lever failures | REJECTED | 11-level vs 5-level: ceiling gain only +0.0006 |
| F15 | Richer hand-engineered state raises ceilings | ACCEPTED (scoped) | short-budget ceiling +0.015→+0.165 with transition-level state |
| F16 | Combining levers (gross+short) is super-additive | REJECTED | joint ceiling +0.157 vs naive sum +0.171 |
| F17 | Regime state predicts weekly correct action | REJECTED | normalized MI 0.003-0.012 — near noise |
| F18 | Reported ceilings are optimizer artifacts | REJECTED | exact exhaustive search matches ceilings exactly |
| F19 | Config-4's capacity is currently binding | REJECTED (not binding) | 50%-of-ceiling break bracketed ₹5000-10,000cr |
| F20 | Capacity ceiling is stable through history | REJECTED (time-varying) | Median ADV ~₹9.6cr (2008) → ~₹68.2cr (2024-25), ~7x growth |
| F21 | Splitting into liquidity tiers adds value | REJECTED | every tier Sharpe 0.47-0.61 underperforms combined 0.847 |
| F22 | Statutory fees dominate transaction cost at scale | REJECTED (slippage dominates) | slippage 58.5%→84.1% of cost, ₹100cr→₹2500cr |
| F23 | Execution delay materially hurts a low-turnover book | REJECTED | 0-3wk delay within ~4% of no-delay |

### 4b. Action/lever + capacity/execution experiments

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| G5-05A | Dynamic gross-exposure timing | TERMINATED_BY_GATE | see F11 |
| G5-05B | Short-budget dynamic timing | TERMINATED_BY_GATE | see F10 |
| G5-04C | Sector-sleeve reallocation | TERMINATED_BY_GATE | see F12 |
| G5-06A | Dispersion-forecast vol-timing | INCONCLUSIVE → REDESIGN | Stage1 fail, wrong-signed proxy |
| G5-06B | Vol-targeting | INCONCLUSIVE → REDESIGN | Stage1 fail, post-2015 reversal |
| G5-07A | Capacity characterization | RESEARCH_SIGNAL → EXPAND | see F19/F20 |
| G5-07B | Liquidity-tiered sub-strategies | RESEARCH_SIGNAL → EXPAND | see F21 |
| G5-08A/B/C/D | Confidence-weighting / risk parity / covariance shrinkage / no-trade regions | REGISTERED → PENDING | never run |
| G5-09 | Temporal model of state adds value | REGISTERED → PENDING | never run |
| G5-X1 / G5-X1B | Permanent state DB/dashboard infra, state-variable ontology registry | REGISTERED → PENDING | foundational infra, not a test |
| PAPER2_5_M1 | Action-space (short-budget grid) resolution is the bottleneck | REJECTED (not the bottleneck) | 5→11 levels gains only +0.0006 |
| PAPER2_5_M2 | State resolution matters materially | ACCEPTED | raises short ceiling 0.015→0.165 |
| PAPER2_5_M3 | Joint gross+short lever interaction is super-additive | REJECTED | see F16 |
| PAPER2_5_M4 | State predicts weekly correct action | REJECTED | see F17 |
| PAPER2_5_M5 | Oracle ceilings are the true optimum, not artifact | ACCEPTED | see F18 |
| A5_BORROW_CAPACITY | Borrow-capacity constrains short-leg | BLOCKED_DATA | no such dataset exists |
| G5-08A_EXECUTION_ENGINE | VWAP/TWAP order-splitting comparison | BLOCKED_DATA | needs intraday data (repo is weekly-only) |
| G5-08E_FAILURE_RECOVERY | Broker-outage/partial-fill resilience | DEFERRED | operational, not backtest |
| G5-08F_OPERATIONAL_ROBUSTNESS | Corporate-action/holiday/suspension stress-test | DEFERRED | already covered by PIT pipeline |
| G5-09A_WALKFORWARD | Confirmatory walk-forward check | DEFERRED | already implicit in every backtest |
| G5-09B_SHADOW_PORTFOLIO | Live shadow-portfolio validation | DEFERRED | needs 6-12mo live deployment |
| G5-D01 | Slippage dominates cost, not fees | ACCEPTED | see F22 |
| G5-D02 | 0-3wk execution delay has no material effect | ACCEPTED | see F23 |

---

## 5. Gen-6 — Representation Learning

Question: can learned representations beat Gen-5's hand-engineered ontology? Governed by `GEN6_RESEARCH_CHARTER.md`.

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| G6-00 | Raw dataset has genuine exploitable temporal structure | INCONCLUSIVE | score +2/5; suspected artifact |
| G6-00B | Structure survives differencing/non-overlapping resampling | **INCONCLUSIVE (decisive)** | predictive-info R² collapsed 0.964→0.0134 (71x) |
| G6-01 | GRU sequence model beats linear baseline | NO_POSITIVE_EVIDENCE | absolute OOS R² negative (both GRU and Ridge) |
| G6-01B | LSTM sequence model beats linear baseline | NO_POSITIVE_EVIDENCE — sequence family rejected | absolute R² still negative (-0.0109) |
| G6-01C | Self-supervised autoencoder learns useful representation | NO_POSITIVE_EVIDENCE | AE reconstruction R²=0.0921 worse than linear PCA (0.1190) |
| PAPER1_INTERIM_REVIEW | Is running the final transformer budget still justified? | DECLINED — Paper 1 closed | no positive evidence across 3 families; pivoted to MSRP |

---

## 6. Gen-7 (CAIT) — Cross-Asset Information Transmission

Governed by `GEN7_RESEARCH_CHARTER.md`. Tested whether price moves in global commodities/FX/rates transmit (with a lag) into Indian equity sector returns.

### 6a. Core hypotheses (Paper A)

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| H-A1 | Cross-asset transmission into Indian equities exists | **[G10] NOT SUPPORTED, now at adequate power — RETIRED** | Gen-10 T1-10: 491-stock beta-residualised receivers, 0/15 survivors, max \|r\|=0.014 vs a 0.11 floor |
| H-A2 | Transmission is delayed (lagged) | UNTESTABLE | no detected transmission to characterize |
| H-A3 | Transmission is stable through time | UNCHANGED/MOOT | window instability real, but no established effect |
| H-A4 | Transmission is directional | WITHDRAWN | measured only on pathways never established as real |

### 6b. Per-carrier pathway tests — all rejected in Lab 2 screen, or downgraded from earlier "valid" status on independent audit

| Carrier(s) | Verdict | Note |
|---|---|---|
| TO-001/002/003 (USD/KRW, USD/MXN ×2) | INCONCLUSIVE (was VALID) | Lockbox CIs all include 0; OOS power only 11-18% |
| Crude Oil, AUD/USD, USD/BRL (passed Labs 1-7) | INCONCLUSIVE (was REJECTED via sign-flip on OOS) | lockbox power only 13%, none of the sign flips significant |
| Natural Gas, RBOB Gasoline, Heating Oil, Gold, Silver, Copper, Steel(HRC), Corn, Soybeans, Wheat, Cotton, MTF(steel proxy) — all lags | REJECTED (Lab 2 screen) | none clear permutation-null + effect-size band |
| USD/INR, EUR/INR, DXY, EUR/USD, GBP/USD, USD/JPY, NZD/USD, USD/CAD, USD/CHF, USD/SGD, USD/ZAR, USD/MXN(lag12), USD/IDR, USD/KRW(lag2), USD/CNY, US 10Y Yield — all lags | REJECTED (Lab 2 screen / BH-FDR) | none survive multiple-testing correction |
| NW-001 (Paper B, 3-object transmission network) | SUSPENDED (was PROMOTE_WITH_LIMITATIONS) | graph structurally sound but its edges (TO-001-003) demoted to INCONCLUSIVE |

### 6c. Permanent methodological findings

| ID | Question | Verdict | Key stat |
|---|---|---|---|
| G7-F01 | Any carrier-lag pair detectable at q<0.05? | REJECTED | 0/310 survive BH or BY |
| G7-F02 | Does zero survivors prove absence? | REJECTED (unresolved, underpowered) | detection threshold \|r\|=0.154; all 6 candidates below it |
| G7-F03 | Was the permutation-based FDR correction valid? | REJECTED | p-floor an order of magnitude coarser than needed |
| G7-F04 | Can the 53-week lockbox adjudicate r≈0.1 effects? | REJECTED | power ~13%; all 6 CIs include zero |
| G7-F05 | Does procedural rigor substitute for statistical power? | REJECTED | every discipline honoured; still uninformative |
| G7-F06 | Does reducing multiplicity (m=310→31) raise power? | **ACCEPTED** | power at r=0.11 rises 31%→60% with no new data |
| G7-F07 | Is any detected weak association channel-specific? | REJECTED (broad, not specific) | effects hit 41/42 sector cells roughly equally |
| G7-F08 | Is weekly resolution sufficient for this question? | REJECTED (hard ceiling) | detecting r=0.11 at 80% power needs ~34yr; only 21yr available |

---

## 7. Gen-8/Gen-9 (RRD) — Remediation, Re-runs, Discovery

Governed by `GEN8_RESEARCH_CHARTER.md`. An independent audit found Gen-6/7 negative results came from underpowered procedures; Gen-8 fixes the procedures and re-runs.

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| EV-000 | Execution environment correctly configured | PASS | 14/14 checks |
| G8-P1 | Remediation library (6 defect fixes) is correct | PASS | 19/19 unit tests |
| G8-01 | Nonlinear/sequence representation beats linear baseline (Gen-6 re-run, 198x scale) | NEGATIVE EVIDENCE | best ΔR² +0.00033; GRU/LSTM significantly worse |
| G8-01B | Was the Gen-6 result a real learning signal? | ARTIFACT CONFIRMED | i.i.d. returns through identical pipeline score higher than real data |
| G8-02 | Cross-asset transmission detectable at m=31 (Gen-7 re-run) | UNRESOLVED | 0 BH/BY survivors; power 67.5% at r=0.11 but needs n=1312, have 1070 |
| G8-03 | MSRP's 12-feature basis has rolling-window memory (re-check) | 9/12 exceeds, 3 within | `high_52w_prox` newly flagged non-independent |
| G8-04 | Momentum's cross-sectional IC is regime-dependent (vol regime) | POSITIVE (descriptive), economic gate FAILED | LOW_VOL IC +0.0433 vs HIGH_VOL +0.0118; oracle Sharpe ceiling negative |
| G8-05 | Non-price signals (options PCR, bulk deals) are orthogonal, material alpha | NEGATIVE EVIDENCE | PCR IC real (+0.0093) but below materiality bar |
| G8-06 | Daily resolution recovers info weekly aggregation discards | NEGATIVE EVIDENCE | weekly beats daily for both signals tested |
| G8-07 | Momentum works better in smaller/less-liquid universe tiers | Directional lead, not significant | non-F&O tail +0.296 Sharpe, only ≈1.4σ |
| G8-08 | Config-4's 2026-07-18 certification (Sharpe 0.9235) reproducible | Corrected — was survivorship-inflated | recertified 0.8105/0.8471 |
| G8-09 | Delivery overlay improves the actual certified Config-4 book | UNRESOLVED / do-not-integrate | best contribution +0.066 Sharpe, needs 59yr to resolve |
| G8-10 | A stock-level receiver universe fixes Gen-7's power problem | Stock-level real, sector-level useless | stock-level: 12.2 effective independent series, 4-10x the required n |
| G8-11 | Micro-cap tier is the source of G8-07's advantage | CORRECTED — non-F&O tail is the real source | non-F&O beats all in 16/17 signals |
| G8-12 | Small-cap advantage is a survivorship artifact fixable by backfill | REJECTED — real bias is universe-rule truncation | 217/327 delisted names never enter panel by rule |
| G9-01 | Non-F&O advantage is a discrete F&O/liquidity boundary effect | Liquidity gradient CONFIRMED; sector ruled out | Spearman(decile,IC)=-0.818, p=0.0038 |
| G9-02 | Institutional ownership/size explain the liquidity-IC gradient | UNRESOLVED (blocked by data coverage) | FII coverage has a hard 2023 scrape cutover |

---

## 8. AEP — Alpha Engineering Programme

Mines permanent economic knowledge from the whole programme rather than testing new strategies. `AEP_CHARTER.md`; CLOSED 2026-07-25.

### 8a. Prototype registry (`AEP_PROTOTYPE_REGISTRY.md`) — 8 pre-registered engineering hypotheses, tested via Papers B–E below

| ID | Hypothesis | Verdict (as tested) | Key stat |
|---|---|---|---|
| Prototype 1 | Low-Volatility Momentum Sizing | REJECTED for engineering (Paper B Sub-study 1) | fails at 2/5 alternate splits |
| Prototype 2 | Conditional Momentum Confirmation (consistency_mom_26w as gate) | MODIFIED (Paper B Sub-study 2) | no candidate role cleanly confirmed |
| Prototype 3 | Liquidity Persistence (4 sub-variants) | MODIFIED (Paper C Sub-study 1) | Q3 sizing real; Q1/Q2/Q4 real but modest |
| Prototype 4 | Resolution Study (state-dependent decisions at other granularities) | MODIFIED (Paper D) | only monthly clears, narrowly |
| Prototype 5 | Composite State Machine (unify all state dims) | ACCEPTED as spec (Paper A) | 7-dim MarketState v1, no dimension redundant |
| Prototype 6 | Adaptive Holding Period | REJECTED (Paper C Sub-study 2) | clean null: 0.705 vs 0.704 Sharpe |
| Prototype 7 | Adaptive Rebalancing | REJECTED (Paper C Sub-study 3) | same clean null |
| Prototype 8 | Confidence Engine (combine 1,2,5) | DEFERRED (Paper E) | dependencies not validated |

### 8b. Paper A — Market State Ontology

| Test | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| A1-A3 | 7 distinct state dimensions exist and interact as specified | **ACCEPTED** | full evidence trail; TrendMemoryState confirmed doubly-conditional |
| A4 | Any dimension redundant (should merge)? | REJECTED (no merge justified) | strongest pair MI=0.138, well short of threshold |
| A5 | Formal v1 spec | ACCEPTED, frozen | `MARKET_STATE_SPECIFICATION_v1.md` |

### 8c. Paper B — Conditional Alpha

| Test | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| Sub-study 1 | Does vol-regime momentum-sizing (M-04) generalize to an engineerable rule? | REJECTED for engineering | fails at 2/5 alt splits; direction replicates only 2/4 alt vol definitions |
| Sub-study 2a (Confirms) | Does consistency_mom_26w confirm trend signals? | **[G10] CLOSED** (was near-miss) | corrected t=+2.52 @4w — the strongest role — but fails multiplicity; closed T1-05″ |
| Sub-study 2b (Warns) | Does it act as an independent warning flag? | **[G10] RETIRED** (was CONFIRMED) | pooled stock-week SE; corrected t=+0.57, all 4 lockbox horizons negative |
| Sub-study 2c (Delays) | Does it act as a lead/lag delay indicator? | REJECTED | stable, non-asymmetric cross-correlation |
| Sub-study 2d (Accelerates-exits) | Does it signal early exits? | REJECTED | t=0.79, n.s. |

### 8d. Paper C — Adaptive Portfolio Management

| Test | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| Q1 Execution | Trade cost lower in persistent-liquidity regimes? | **[G10] directional, not significant** | 3.90 vs 4.20bps but t=-1.75 |
| Q2 Universe | Liquidity-persistent names trade cheaper? | **[G10] UNTESTED** | corr=-0.119 with no SE; not recomputed |
| Q3 Sizing | Scaling exposure by liquidity-persistence improves risk-adj return? | **[G10] REJECTED** (was ACCEPTED) | paired t=+0.50; 0.18x its detection floor; not a liquidity rule; = G5-05A |
| Q4 Capacity | Does the execution advantage hold across capital scale? | **[G10] directional, not significant** | 3.64 vs 3.89bps, t=-1.75 |
| Sub-studies 2+3 | Memory-conditional holding/rebalancing improves the book? | **REJECTED** — clean null | Sharpe 0.705 vs 0.704 |

### 8e. Paper D — Decision Resolution Study

| Resolution | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| Weekly | State carries info about correct action | REJECTED | nMI 0.0027 vs null 0.0058 |
| Biweekly | Same | REJECTED | nMI 0.0072 vs null 0.0113 |
| Monthly | Same | **[G10] REJECTED** (was ACCEPTED) | p≈0.038 vs Bonferroni 0.010 at m=5; "RISING" is a curve-shape label |
| 6-week | Same | REJECTED | nMI 0.0028 vs null 0.0374 |
| Quarterly | Same (initial raw result looked dramatic) | REJECTED after correction | small-sample artifact, n=82 |

### 8f. Paper E — Confidence-Based Portfolio Allocation

| Test | Hypothesis | Verdict | Reason |
|---|---|---|---|
| Paper E | Build continuous confidence score combining A/B/C | **DEFERRED — never run** | fewer than 2 of 3 required input papers supplied validated relationships |

**AEP overall:** Paper A Accepted, Papers B/C/D Modified, Paper E correctly Deferred.

---

## 9. ARP — Alpha Recovery Programme

Forensic recovery of alphas rejected only for institutional-capacity reasons. `ARP_CHARTER.md`. 141 catalogued entries in `results/ARP_MASTER_ALPHA_REGISTRY.csv` — **the vast majority are re-classifications of Gen-2/3/4/5/6/MSRP experiments already listed in §1-§7 above** (bucket totals: 70 Permanent Dead End, 46 N/A/descriptive, 13 research-incomplete, 3 Deployable Alpha, 2 Portfolio Component, 2 Execution Improvement, 4 flagged for review, 6 Gen-6 representation findings). ARP's genuinely new output is the recovery dossier below.

### ARP Delivery Alpha Dossier (`results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md`)

| Test | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| Correctness gate | Does ADD_nonfno_tail reproduce the original G2-E03 overlay test exactly? | CONFIRMED | Net Sharpe @20bps: CONTROL 0.698, ADD_nonfno_tail 0.767 |
| Capacity ladder | Is Delivery deployable at realistic capital, degrading gracefully? | **RECOVERED, CONFIRMED** | peak Sharpe ~0.792 @₹5-10cr, degrades to 0.660 @₹500cr — not a cliff |
| Portfolio integration | Does Delivery combine well with the frozen momentum+sector book? | **[G10] ANSWERED — does not promote** | sleeve weight = 0 at B's CI lower bound; **realised sleeve corr 0.84**, the 0.14 is signal orthogonality |
| Regime dependency | Is the signal regime-conditional? | **[G10] ANSWERED — NO** | RISK_ON minus RISK_OFF IC difference t=+1.49; a static sleeve weight is correct |

---

## 10. MSRP — Market Structure Research Programme

Measures the market's internal structure (not predictive models) across 5 pillars. `MSRP_CHARTER.md`. **Only Information and Memory pillars were ever opened** — Geometry, Networks, and Economic Limits remain unopened per a 2026-07-25 scope-discipline decision.

### 10a. Pillar 1 — Information

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| I-01 | Do the 18 engineered features carry real predictive info (vs permutation null)? | **POSITIVE_EVIDENCE** | 56/90 (62.2%) feature-horizon pairs significant, above 30% bar |
| I-02 | How does each feature's info behave across horizons? | DESCRIPTIVE | 8 Persistent, 4 Delayed, 2 Immediate, 2 Dead, 2 Mixed |
| I-03 | Which features are pairwise-redundant? | DESCRIPTIVE | full 18×18 MI+correlation matrix built |
| I-03B | Do redundant features also share behavioral timing? | DESCRIPTIVE (key structural finding) | volatility family redundant AND coherent; momentum superfamily redundant but not coherent |
| I-04A | Within volatility family, does each feature add incremental info? | DESCRIPTIVE | vol_52w (highest raw MI) retains only 33.9% — most redundant in its family |
| I-04B | Does residual momentum retain info after conditioning on volatility (re-test of Gen-5 F01)? | **POSITIVE_EVIDENCE** | retains 69% raw MI — confirms Gen-5 F01 |
| I-05 | Minimal feature set spanning the information basis? | DESCRIPTIVE | 12 of 18 selected; consistency_mom_26w (Dead standalone) selected 2nd |
| I-06 | Is info content stable across 3 market eras incl. COVID? | **POSITIVE_EVIDENCE** (mixed) | volatility perfectly stable; 2 momentum features fading |
| PHASE1_SYNTHESIS | Overall coherent information structure? | **FROZEN v1.1, POSITIVE_EVIDENCE, High Confidence** | scoped to "the engineered ontology studied," not "the market" |

### 10b. Pillar 2 — Memory

| ID | Hypothesis | Verdict | Key stat |
|---|---|---|---|
| M-01 | Do all 6 primitives show long memory (raw run)? | SUPERSEDED_BY_M-01B (self-caught artifact) | all 6 falsely classified Long Memory — rolling-window overlap artifact |
| M-01B | Corrected: which primitives have genuine memory? | ACCEPTED, High confidence | beta_104w memoryless (corrected); vol_52w genuine memory; ret_4w reversal |
| M-02 | Is memory regime-dependent? | **POSITIVE_EVIDENCE** | 4/6 primitives regime-locked; amihud_13w strongest |
| M-03 | Does state dwell-time exceed AR(1)-implied persistence? | **POSITIVE_EVIDENCE** | vol_52w and amihud_13w exceed AR(1) |
| M-04 | Does high volatility strengthen trend memory (naive prior)? | **POSITIVE_EVIDENCE, prior FALSIFIED** | trend memory LONGER in Low-Vol, opposite of prediction |
| M-05 | Does consistency_mom_26w's memory emerge conditional on trend state (Interaction Persistence Hypothesis)? | **CONFIRMED** | memory near-absent unconditionally, emerges strongly conditional on trend state |

### 10c. Permanent methodological findings (decision-log level)

| Finding | Verdict | Note |
|---|---|---|
| Rolling-Window Persistence Principle | CONFIRMED, elevated to permanent charter law | recurred twice (Gen-6 R0/R0B, MSRP M-01/M-01B) |
| Structural redundancy ≠ behavioral coherence | orthogonal properties, formalized as standing requirement | I-03B |
| Fixed effect-size band insufficient at small regime samples | REJECTED, corrected to require joint stat+econ significance | M-02A initially falsely flagged all 6 primitives regime-locked |

---

## 11. Permanent Findings Registry (`archive/11_registries/FINDINGS_REGISTRY.csv`) — 46 synthesized laws

These are the compressed, cross-experiment "economic laws" the programme extracted, each traceable back to the experiments above (`NSR-FIND-000001` → `NSR-FIND-000046`). Categories: Economic Law (durable, general), Permanent Dead End (tested and closed), Portfolio Component (used in the live book), Deployable Alpha, Execution Improvement.

| # | Finding | Category |
|---|---|---|
| 1 | Momentum is a redundant 4-way ensemble | Economic Law |
| 2 | Short book is risk control, not alpha | Portfolio Component |
| 3 | Config-4 sits at a near locally-optimal static point | Economic Law |
| 4 | Short book = transition protection, not crash-bottom protection | Economic Law |
| 5 | G-05 overlay = cheap bottom-of-drawdown protection | Portfolio Component |
| 6 | Regime state machine is highly structured, not arbitrary | Economic Law |
| 7 | STRESS regime has distinct economic sub-phases | Economic Law |
| 8 | Short book's value is covariance reduction, not standalone utility | Economic Law |
| 9 | Every diagnostic converges on short book as the priority lever | Economic Law |
| 10-13 | Every dynamic-timing lever (short-budget, gross-exposure, sector-reallocation, vol/dispersion) fails its economic gate | Permanent Dead End |
| 14 | Action-space coarseness is not why any lever failed | Economic Law |
| 15 | Richer hand-engineered state materially raises ceilings (bounded) | Economic Law |
| 16 | Combining levers does not compound super-additively | Economic Law |
| 17 | Weekly action correctness carries near-zero information | Economic Law |
| 18 | Every Paper-2 ceiling is the global optimum, not an artifact | Economic Law |
| 19-20 | Config-4 not currently capacity-bound; capacity is time-varying (~7x growth since GFC) | Execution Improvement |
| 21 | Liquidity-tiered sub-strategies give up real diversification | Economic Law |
| 22 | Market-impact slippage dominates cost, not statutory fees | Execution Improvement |
| 23 | Low-turnover construction robust to modest execution delay | Execution Improvement |
| 24 | Rolling-window features manufactured 71% of apparent Gen-6 temporal structure | Permanent Dead End |
| 25-26 | Sequence family (GRU/LSTM) and self-supervised family (Autoencoder) both rejected | Permanent Dead End |
| 27 | Predictive info hierarchy: volatility dominant, momentum superfamily heterogeneous | Economic Law |
| 28 | Residual momentum retains 69% incremental MI after conditioning on volatility | Economic Law |
| 29 | 12-feature Greedy Information Basis; consistency_mom_26w is interaction-only | Economic Law |
| 30 | Volatility family stable across eras incl. COVID; 2 momentum features fading | Economic Law |
| 31 | Memory is primitive-specific, not universal | Economic Law |
| 32 | Liquidity memory regime-locked specifically in NORMAL_UP/STRESS | Economic Law |
| 33 | vol_52w and amihud_13w show state-locking beyond AR(1) | Economic Law |
| 34 | Trend memory doubly conditional on volatility AND consistency state | Economic Law |
| 35 | Interaction Persistence Hypothesis confirmed for memory | Economic Law |
| 36 | Rolling-Window Persistence Principle formalized (2nd independent occurrence) | Economic Law |
| 37 | Structural redundancy and behavioral coherence are orthogonal | Economic Law |
| 38 | Delivery capacity curve peaks ~₹5-10cr, degrades gracefully to ₹500cr | Deployable Alpha |
| 39-40 | Market State Ontology: 7 dimensions specified, none redundant; TrendMemoryState most independent | Economic Law |
| 41 | Vol-conditional momentum sizing does not generalize past its original spec | Permanent Dead End |
| 42 | consistency_mom_26w's conditional role doesn't cleanly resolve | Economic Law |
| 43 | Liquidity-conditional sizing real but robustness-untested | Economic Law |
| 44 | Memory-conditional holding/rebalancing: clean null | Permanent Dead End |
| 45 | Narrow RISING signal at monthly resolution only; quarterly was bias | Economic Law |
| 46 | AEP meta-finding: MSRP's robustness discipline, applied a level up, catches real engineering gaps | Economic Law |

*(Full statement text and traceability for each numbered finding is in `archive/11_registries/FINDINGS_REGISTRY.csv` and `archive/HOW_TO_CITE_THIS_ARCHIVE.md`, keyed by permanent ID `NSR-FIND-000001` through `NSR-FIND-000046`.)*

---

## Source files (for verification / re-extraction)

- Gen-1: `results/ALPHA_REGISTRY.md`/`.csv`, `results/LEDGER.csv`
- Gen-2/3: `results/MASTER_EXPERIMENT_INDEX.csv`, `results/gen23/registry.jsonl`, `docs/GEN2_GEN3_EXPERIMENTS_AND_RESULTS.md`
- Gen-4: `results/gen4/*.md`
- Gen-5: `results/gen5/` (per-experiment folders), `docs/GEN5_DECISION_LOG.md`
- Gen-6: `results/GEN6_EXPERIMENT_INDEX.csv`, `results/gen6/PAPER1_INTERIM_REVIEW.md`
- Gen-7: `results/gen7/NETWORK_REGISTRY.csv`, `FAILED_TRANSMISSION_REGISTRY.md`, `GEN7_STATUS_AND_FINDINGS.md`
- Gen-8/9: `results/gen8/GEN8_EXPERIMENT_REGISTRY.csv`, `GEN8_STATUS_AND_FINDINGS.md`
- AEP: `results/AEP_DISCOVERY_CENSUS.csv`, `AEP_PROTOTYPE_REGISTRY.md`, `AEP_SYNTHESIS_FROZEN.md`, `results/AEP_PAPER_A`–`D`
- ARP: `results/ARP_MASTER_ALPHA_REGISTRY.csv`, `results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md`
- MSRP: `results/MSRP_EXPERIMENT_INDEX.csv`, `docs/MSRP_DECISION_LOG.md`, `results/msrp/{I-01..I-06,M-01..M-05}/`
- Permanent archive: `archive/11_registries/MASTER_EXPERIMENT_CATALOGUE.csv`, `FINDINGS_REGISTRY.csv`, `PROVENANCE_MANIFEST.csv`, `finding_id_to_permanent_id.json`
