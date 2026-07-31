# Gen-7 (CAIT) — Status and Findings

```
Version:      v1.0
Status:       Frozen (generation ACTIVE but discovery arc halted)
              -> SUPERSEDED 2026-07-31: the arc is now CLOSED, see the banner below
Freeze Date:  2026-07-25
Scope:        Paper A (executed, audited, re-analysed) + Paper B Laboratory 1 (executed, suspended)
```

> ## ✅ RESOLVED — H-A1 answered at adequate power (2026-07-31, Gen-10 T1-10)
>
> Gen-7 could never establish whether zero survivors meant *absence* or *insufficient power*
> (G7-F02, G7-F04 at 13% power, G7-F08 needing ~34 years against 21 available). G8-02 narrowed it
> (67.5% power, n = 1312 needed vs 1070 available) and G8-10 identified the one untried remedy —
> a stock-level receiver universe supplying 12.2 effective independent series against sectors' 1.49 —
> while declining to run it until a contract resolved three questions in advance.
>
> **That contract was written and frozen** (`docs/gen10_protocols/T1-10_CAIT_REDESIGN_CONTRACT.md`),
> resolving all three: pooled estimation with one coefficient per carrier-lag; date-clustered SEs
> throughout; and — the substantive one — **broad market-beta transmission was ruled in advance not to
> count as an answer**, so receivers are beta-residualised and channel specificity is tested rather
> than assumed.
>
> **Result: 0 of 15 survivors. Largest |r| on any channel group = 0.0138, against a pre-registered
> floor of r = 0.11.** Zero effects classified as beta, so the null is not residualisation eating a
> real broad effect. 491-stock receiver universe, Fama-MacBeth over ~1,000 dates with genuine
> cross-sectional identification.
>
> | hypothesis | was | now |
> |---|---|---|
> | **H-A1** transmission exists | NOT SUPPORTED (underpowered, unresolved) | **NOT SUPPORTED, at adequate power — RETIRED** |
> | H-A2 lagged | UNTESTABLE | **closed with H-A1** |
> | H-A3 stable through time | UNCHANGED/MOOT | **closed with H-A1** |
> | H-A4 directional | WITHDRAWN | **closed with H-A1** |
>
> **This does not invite a fourth re-run.** One channel remains formally uncovered: US 10Y was
> untestable (440 weeks of history against the others' 1,067), so the duration/discount-rate channel
> needs longer rates history rather than a better design.
>
> Evidence: `results/gen10/T1-10/`. Gen-7 is not in Archive v1.0, so this is applied here directly
> rather than by addendum.

Gen-7's equivalent of `GEN5_MASTER_FINDINGS.md` / `results/msrp/PHASE1_SYNTHESIS_FROZEN.md`. Read this
first for "what does Gen-7 actually know."

**Companion documents, in reading order:**
1. This document — the findings.
2. `PAPER_A_REVISED_VERDICT.md` (v2.0) — authoritative scientific conclusions and hypothesis verdicts.
3. `GEN6_GEN7_INDEPENDENT_AUDIT_2026_07_25.md` — the audit that overturned Paper A, with reproduction
   commands for every finding.
4. `paper_a_reanalysis/` — RA-001–RA-006: the corrected science and its independent verification.
5. `PAPER_A_VERDICT.md` / `PAPER_A_POSTMORTEM.md` — the **original** execution, preserved unedited as
   history per P5. Superseded on statistics, still the record of what was actually run.
6. `../../GEN7_RESEARCH_CHARTER.md` + `../../docs/GEN7_CHARTER_AMENDMENTS.md` — governance, incl.
   Amendments 002/003 which this generation's failures produced.

---

## One-paragraph summary

Gen-7 asked whether information is detectable while still travelling between asset classes, before it is
reflected in Indian equities. Paper A scanned 31 non-equity carriers × 10 weekly lags (310 tests) against
the aggregate Indian equity return and originally reported six FDR survivors and three lockbox-validated
Transmission Objects. An independent audit found both headline procedures invalid. **Corrected
re-analysis finds no detectable transmission at the required evidentiary standard — and also finds the
design was never powered to detect effects of the size present. The question is UNRESOLVED, not answered.
Gen-7 has produced no validated scientific object.** Its durable contribution is methodological.

---

## Permanent findings (G7-F01 … G7-F08)

| ID | Finding | Confidence | Evidence |
|---|---|---|---|
| **G7-F01** | **No cross-asset transmission is detectable between the 31 tested carriers and the aggregate Indian equity return at q<0.05.** Zero of 310 carrier-lag pairs survive Benjamini-Hochberg *or* Benjamini-Yekutieli under a calibrated HAC test. Best BH q-value across the entire family: 0.847. | High (verified) | RA-001, RA-005 |
| **G7-F02** | **That null is UNRESOLVED, not an absence.** The design's 80%-power detection threshold is \|r\|=0.154; all six candidate effects lie at \|r\|=0.102–0.144, entirely below it. Mean power at the observed effect sizes: 40%. | High | RA-006 |
| **G7-F03** | **A permutation p-value floored at exactly 0.0 makes an FDR correction uninterpretable.** With 500 draws the finest resolvable p-value (1/501) is an order of magnitude coarser than the BH rank-1 threshold (0.05/310). The procedure could not have produced a legitimate survivor at any observation. | High | RA-001, audit CRITICAL-1 |
| **G7-F04** | **A 53-week holdout cannot adjudicate effects of \|r\|≈0.1.** Power ~13%; minimum detectable effect 2.6× larger than anything present; all six lockbox CIs include zero; five of six include their own pre-lockbox value; 3-of-6 sign agreement is exactly the chance expectation (binomial p=1.000). | High | RA-003, audit CRITICAL-2 |
| **G7-F05** | **Procedural rigor does not substitute for statistical power.** Paper A honoured every process discipline it claimed — untouched holdout, verified no look-ahead, correct ladder ordering, honest sequencing — and still learned nothing, because two gates were not powered to filter. | High | audit; Charter §3.1 (rewritten) |
| **G7-F06** | **Reducing multiplicity is the cheapest available power gain.** Pre-registering one lag per carrier (m=31 rather than 310) raises power at r=0.11 from **31% → 60%** on the existing data, with no new data at all. | Moderate-High | RA-006 supplement |
| **G7-F07** | **Whatever weak association exists is broad, not channel-specific.** Effects hit essentially all sectors roughly equally (41/42 cells); Crude Oil's strongest sector was Materials, not Energy. Consistent with broad market-beta / EM-risk-sentiment exposure rather than named mechanistic pathways. Survives the re-analysis unchanged and is *strengthened* by it. | Moderate | Lab 5 |
| **G7-F08** | **Weekly resolution is a hard ceiling for this question.** No daily equity-grade data exists in-repo for these carriers; lag=0 is PIT-illegal for non-India carriers. Detecting r=0.11 at 80% power with m=310 would need ~34 years of history against the 21 available. | High | Lab 1 (TD-001/002), RA-006 |

## Rejected / withdrawn claims from Paper A v1.0

| Original claim | Status now |
|---|---|
| "6 of 310 survive BH-FDR correction" | **Withdrawn** — artifact of a p-value floored at 0.0. Corrected: 0. |
| "3 of 6 survive a true out-of-sample lockbox" | **Withdrawn** — the holdout had no power to decide. |
| "Crude Oil was decisively killed by the lockbox" | **Withdrawn** — Oil's lockbox CI contains its own pre-lockbox value; the change is not significant (p=0.249). |
| "USD/KRW is a structurally peripheral node with no redundancy edges" | **False** — Lab 3's own data shows every node has ≥1 redundancy edge. |
| "Transfer entropy positive for all 6 candidates" | **No evidential weight** — plug-in TE is positively biased and no null model was run. |
| H-A1 ACCEPTED (transmission exists) | **UNRESOLVED** |
| H-A4 ACCEPTED (transmission is directional) | **Withdrawn** — measured only on pathways that are not established. |

## Object registry state

| Object | Status | Note |
|---|---|---|
| TO-001 (USD/KRW, lag 1) | **INCONCLUSIVE** | demoted from VALID |
| TO-002 (USD/MXN, lag 2) | **INCONCLUSIVE** | demoted from VALID |
| TO-003 (USD/MXN, lag 1) | **INCONCLUSIVE** | demoted from VALID |
| Crude Oil / AUD-USD / USD-BRL | **INCONCLUSIVE** | not refuted either |
| NW-001 (Paper B) | **SUSPENDED** | structurally sound graph over unvalidated edges |

**INCONCLUSIVE, not INVALID** throughout — the evidence does not support detection, and never had the
power to establish absence. Claiming refutation would repeat the same overreach in the opposite direction.

## Methodological contributions (the generation's real output)

1. **Amendment-002 — power disclosure is a precondition for a gate.** Any gate must publish, before
   running, the effect size it can detect at 80% and the smallest statistic it can resolve. A gate whose
   minimum detectable effect exceeds the effect under test adjudicates nothing, in either direction.
2. **Amendment-003 — detection capability must be demonstrated before a null is reported.** Synthetic
   corruption for audits; injected known effects for discovery pipelines.
3. **A reusable verified statistical core** — `scripts/gen7/reanalysis/ra001_corrected_discovery.py`
   provides a Newey-West HAC correlation test and a circular-block-bootstrap null, both independently
   verified (RA-005, 22/22 against SciPy, the BH-1995 published example, and closed-form AR(1) results).
4. **A worked example of self-correction at generation scale** — five defects found, fixed, re-run and
   re-verified in one session, including two corrections to the audit's *own* claims.

## What is still sound from Paper A

- No look-ahead bias (`ret_1w` verified trailing; lag ≥ 1 with W-FRI alignment is PIT-clean).
- Lockbox *discipline* was honoured — Labs 2–6 never touched the holdout. The failure was power, not
  contamination.
- Lab 1's trusted weekly carrier dataset reproduces exactly from raw sources (deviation 0.00e+00).
- Lab 5's breadth finding (G7-F07).
- Paper B Laboratory 1's execution — and TS-105 in particular, which independently reached this
  re-analysis's conclusion by a different route, before the audit began.

## Open decision

Laboratory 2 is blocked. Three options, in the revised verdict's order of honesty: **(1)** record the
discovery question as UNRESOLVED with stated power requirements — recommended; **(2)** redesign for power
(multiplicity reduction first, then a sector- or stock-level receiver universe) and re-run; **(3)**
re-scope Paper B to *candidate* objects — defensible but low-value, since TS-105 already showed a
3-object network cannot support structural inference.

**No option is "proceed as planned."**
