# Gen-10 — Remediation Programme: Synthesis

```
Version:      v1.0
Status:       Tier 0 + Tier 1 COMPLETE (13 experiments); record propagated 2026-07-31
Freeze Date:  2026-07-31
Owner:        Aryak
Charter:      GEN10_REMEDIATION_CHARTER.md
Source plan:  Northstar_Remediation_Priority_Plan.md (v2, 2026-07-30)
Review:       REMEDIATION_PLAN_FEASIBILITY_REVIEW.md
```

Thirteen experiments. **Zero new deployable alpha. Eight verdicts corrected. Three questions
permanently closed.** The programme's certified state is unchanged: momentum remains the only
scalable stock-selection edge, sector rotation the modest diversifier, delivery a validated but
capacity-bound signal that does not improve the book in either integration architecture.

---

## 1. Results table

| ID | question | verdict |
|---|---|---|
| **T0-01** | Do `consistency_mom_26w`'s four roles survive date-clustered inference? | **2b RETIRED** (was CONFIRMED); 2a unresolved |
| **T0-02** | How far does the pooled-SE defect spread? | Confined to Paper B; **Paper C Q3 retired**, Q1/Q4 downgraded |
| **T0-03** | Why do three harnesses disagree on one momentum signal? | **36% of the disputed IC is a composition artifact** |
| **T1-04a** | DS delivery cluster through the economic gate | **One signal, already deployed.** 5 of 8 die at first OOS split |
| **T1-05″** | Can a better estimator rescue Paper B 2a? | **No — closed.** Efficient estimators are weaker |
| **T1-06** | Delivery regime dependency + sleeve integration | **Not regime-conditional; sleeve does not promote** |
| **T1-07** | Paper D monthly, corrected for multiplicity | **RETIRED.** F17's null now settled at all resolutions |
| **T1-08** | Exit realism on the small-cap lead | **Lead survives** to −45%; but 2/3 of one lead is a date artifact |
| **T1-09** | DS momentum-quality + cross-factor clusters | **Nothing promotes.** Largest deep-search t is A04 rediscovered |
| **T1-10** | Gen-7 CAIT redesign at adequate power | **NULL. Cross-asset transmission retired permanently** |
| **T1-11** | Is G8-07's tier lead a date-coverage artifact? | **Yes. Ordering reverses on common dates** |
| **T1-12** | Is the same defect in Delivery / G9-01? | **No — both clean, verified.** One latent vulnerability recorded |
| **T1-13** | Tier sweep: common dates x 3 configs x net of cost | **Reversal holds. Non-F&O lead ~86% artifact. Tier effect absent from the certified book** |

## 2. The five findings that generalise

### G10-A — the unit of inference was wrong in places, and it changed answers

AEP Paper B computed t-statistics by pooling ~62,000 stock-weeks as independent. Corrected to
date-clustered inference, its **CONFIRMED** result (2b) becomes t = 0.57 with a sign that flips out of
sample, and its **near-miss** (2a) becomes the stronger of the two. The repo already knew this error
class — G8-10 §4.2 demands date-clustered SEs, G9-02 §1 documents catching it internally — but the
discipline lived per-script. It is now structural: `src/research/gen10/inference.py` makes per-date
collapsing the only path, and every Gen-10 result routes through it.

**T0-02 bounded the damage:** the Gen-2/3 DS battery is clean (verified on six signals, 6/6 reproduce
within 0.1 t-units), and so are Papers A and D. The defect was one paper.

### G10-B — a more common failure than a wrong test is no test at all

Paper C issued ACCEPTED and POSITIVE verdicts on point estimates with no standard errors. Supplying
them retired Q3 (paired t = **0.50**, effect 0.18× its own detection floor, costing 3.26%/yr of
return) and downgraded Q1/Q4 to directional-not-significant (t = −1.75). Q3 also turned out not to be
a liquidity rule at all — it keys off regime labels, and de-gearing in CRASH alone (0.816) beats the
bundled rule (0.727) while the rule holds STRESS at full exposure when de-gearing STRESS alone scores
0.778.

### G10-C — cross-sectional IC is not comparable across universes

The `ret_13w` / `MOM60` / `DS-U-01` disagreement is not a harness-configuration difference. Running
the deepsearch configuration on PANEL-A gives t = +0.91 against an archived +2.91. **The panel is the
axis**, and the mechanism is composition: the enriched panel pools two groups of stocks differing
systematically on both signal (+0.054 vs −0.125) and forward return (+0.0035 vs +0.0017), so the
pooled IC (+0.0138) exceeds the IC of *either group alone* (+0.0086, +0.0050). Removing between-group
variation leaves +0.0089 — **36% of the headline was composition.**

The artifact is coverage-dependent, which made it predictive: delivery signals (94% inside the liquid
universe) are immune and were verified so before T1-04a ran; the broad momentum signals in T1-09 carry
**30–40%**, exactly as forecast.

### G10-D — RESEARCH_SIGNAL does not predict out-of-sample survival

All 28 deep-search items were evaluated full-sample (`"lockbox_used": false`). Across T1-04a and
T1-09, **14 deduped items faced a genuine split for the first time**:

- 5 delivery items died; 3 survived and proved to be one already-deployed signal (pairwise ρ 0.72–0.92,
  incremental t 0.27–0.61 against the incumbent);
- 4 momentum-quality items died after composition correction, including DS-F4-02 — the plan's
  strongest overlay candidate — falling from an archived +6.33 to an OOS +1.73;
- DS-F2-03, the **largest |t| in the entire deep search (−8.91)**, was retired on cost before Stage 1:
  its turnover is **4091%/yr against A04's 4187%/yr**, with a 2236%/yr control showing the measurement
  discriminates. It is Gen-1's already-killed reversal trade wearing an interaction label.

**Zero new deployable alpha from 28 catalogued RESEARCH_SIGNAL items.**

### G10-E — the same defect keeps appearing as "compared over different observation sets"

Five instances, one shape: pooled stock-weeks treated as independent (T0-01), pooled multi-universe
cross-sections (T0-03), tier-native date sets (T1-08 and T1-11), and mismatched estimation eras
(T1-06's Sharpe-baseline trap). T1-11 is the sharpest: G8-07 measured `NON_FNO_TAIL` on **712 weeks**
against every other tier's **1,070**, and the 358 excluded weeks score **+0.58** Sharpe against the
common window's **+1.01**. Half that tier's lead was the window. **G8-11's correction of G8-07 —
moving the finding from the micro-cap tier to the non-F&O tail — does not survive, and the ordering
reverses.** The liquidity story is strengthened but relocates from a discrete F&O boundary to the
extreme of a continuous size gradient.

**T1-13 then settled it net of cost, and found the defect twice more.** Reproducing G8-07's published
leads almost exactly (+0.299 / +0.228 / −0.153 vs +0.296 / +0.222 / −0.153) validates the re-run; on a
common index across all three configs, net of cost, NON_FNO_TAIL's lead collapses to **+0.042** while
SMALL_ADV_Q1 holds at **+0.279**. And **G8-11 has the same defect in a worse form**: it reports all
four tiers at 1,070 weeks, but records `port = 0.0` whenever a tier is too thin to trade — **41.8% of
NON_FNO_TAIL's sample is synthetic zeros**, the tier being *empty by construction* through 2005-09 and
2013. Zero-fill awards the favoured group a risk-free return through the GFC rather than merely
omitting it. Both G8-07's truncation and G8-11's zero-fill flatter the same tier.

**A separate result nobody was looking for:** under `config4_secbal40_short` — the certified
production config — **both tiers are negative** (−0.284, −0.013). The F&O-only short leg cannot hedge
a long book drawn from a disjoint non-F&O universe, so the tier effect and the short leg are
structurally incompatible. Any small-cap tilt of the certified book must redesign the short leg first,
which makes it a different strategy rather than a tilt.

## 3. Corrections against the permanent record (all applied — see §3b)

| document | correction |
|---|---|
| `results/AEP_PAPER_B/` | Sub-study 2b CONFIRMED withdrawn; 2a closed unresolved |
| `results/AEP_PAPER_C/` | Q3 ACCEPTED withdrawn; Q1/Q4 downgraded; Q2 flagged untested |
| `results/AEP_PAPER_D/` | monthly ACCEPTED withdrawn; Paper D → REJECTED at all resolutions |
| `FINDINGS_REGISTRY.csv` #42 | evidence base inverted (2a is the candidate, not 2b) |
| `FINDINGS_REGISTRY.csv` #43 | liquidity-conditional sizing is not established, not merely untested |
| `FINDINGS_REGISTRY.csv` #45 | monthly half withdrawn; quarterly half stands |
| `AEP_PROTOTYPE_REGISTRY.md` | Prototype 2 → no confirmed role; Prototype 3 Q3 → REJECTED; Prototype 4 → REJECTED |
| `MASTER_..._LEDGER_2026_07_28.md` | §8c, §8d, §8e; and §1b/§2e merge `ret_13w`/`MOM60`/`DS-U-01` |
| `results/LEDGER.csv`, `MASTER_EXPERIMENT_INDEX.csv` | add the four provenance fields (G10-F rule below) |
| `results/gen23/deepsearch_summary.csv` | flag broad-universe ICs as not PANEL-A-comparable |
| `results/gen7/GEN7_STATUS_AND_FINDINGS.md` | H-A1 resolved negative at power; H-A2/A3/A4 close with it |
| `results/gen8/G8-07`, `G8-11` | tier Sharpes compared across different date sets; G8-11's correction reverses |
| `results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md` | both open questions answered; the 0.14 correlation is signal, not sleeve-return |
| `NORTHSTAR_HANDBOOK.md` | do-not-integrate Delivery; the liquidity-sizing "lead" is not a lead |

## 3b. Record propagation — DONE 2026-07-31

Archive v1.0 was **not modified**, per `archive/GEN7_INTERFACE_RULE.md`. Corrections were issued as
`archive_addenda/GEN10_ADDENDUM_001..004.md` (indexed in `archive_addenda/README.md`), citing the
permanent IDs affected — NSR-FIND-000042/043/045 and sixteen NSR-EXP deep-search IDs.

Live documents were annotated in place with correction banners, originals left readable:
`results/AEP_PAPER_{B,C,D}/`, `AEP_PROTOTYPE_REGISTRY.md`, the master ledger (banner + 12 row edits +
a DS-battery note), `results/gen7/GEN7_STATUS_AND_FINDINGS.md`, `results/gen8/G8-07` and `G8-11`,
`results/ARP_DELIVERY/DELIVERY_ALPHA_DOSSIER.md`, `NORTHSTAR_HANDBOOK.md`, and a new
`results/gen23/DEEPSEARCH_SUMMARY_CAVEATS.md`. `results/LEDGER.csv` gained the four provenance fields.

The five rules below are adopted as `RESEARCH_INFERENCE_STANDARD.md`.

## 4. Constitutional additions (ADOPTED)

1. **One date is one observation.** No test may treat pooled stock-weeks as independent.
2. **No verdict without a test.** POSITIVE / ACCEPTED may not be issued from point estimates.
3. **Four provenance fields on every ledger row** — target horizon, target relativity, universe/panel,
   window. No cross-generation comparison without them.
4. **Pooled multi-universe ICs must report their within-group value** alongside the pooled one.
5. **A stock-level receiver requires within-date regressor variation** (T1-10 / G10-F31).

## 5. What the source plan got right

Its central thesis was correct: the RESEARCH_SIGNAL bucket had never been through the economic gate,
and that was the right place to look. Its taxonomy, its insistence on pre-registration, its explicit
retired list, and its working rhythm all held up. Three specific calls were load-bearing:

- **DS-F2-03's caution** — "run Stage 4 before getting attached to the effect size" — was right to the
  second decimal place.
- **The sleeve-vs-overlay distinction in 2.1** was a genuine gap in the record, confirmed by G8-09 §7.
- **Running 2.2 before 2.1** was correct sequencing; its output did size 2.1 (statically).

Where it went wrong it went wrong on premises, not method: 2b had not confirmed cleanly (T0-01), Q3
was not a promotable positive (T0-02), 2.3's source said the opposite of what the plan read (T1-08),
and the 0.14 correlation underpinning the whole diversification case for 2.1 is **signal**
orthogonality, not sleeve-return orthogonality — the realised sleeve correlation is **0.842** (T1-06).

## 6. What is genuinely still open

- **Paper C Q2** — never recomputed; a name-level correlation with no SE. Tier 2, small.
- **G2-B03b** (order-win announcements) — the one registry row the plan missed. Tier 3.
- **The duration/rates channel in T1-10** — US 10Y was untestable on 440 weeks. Needs longer history,
  not a better design.
- **G8-07/G8-11's tier ordering** — T1-08 found SMALL_ADV_Q1 leading NON_FNO_TAIL on common dates,
  the reverse of G8-11. Different construction, so flagged as a discrepancy to check, not a refutation.
- **G5-08A/B/C/D and G5-09** — genuinely never run; the rename question is resolved (the original Risk
  Parity / Shrinkage registrations are unrun; the scripts that exist are the D01/D02 work).
- **MSRP's three unopened pillars.**

## 7. The honest summary

Gen-10 found no new alpha and was not expected to. What it found is that a meaningful share of the
programme's "statistically real but untested" backlog was **not statistically real** — it was
full-sample fitting, missing standard errors, uncorrected multiplicity, and universe-composition
artifacts. Ten experiments produced six corrections to the permanent record and three permanent
closures, and left the certified book exactly where it was.

That is the correct outcome for a remediation programme, and it is worth more than a marginal signal
would have been.
