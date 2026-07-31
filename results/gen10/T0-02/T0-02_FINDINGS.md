# T0-02 — Archive Sweep for the T0-01 Defect Class. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T0-01/T0-01_FINDINGS.md, GEN10_REMEDIATION_CHARTER.md s4/T0-02
Artifacts:    t0_02_data.json. Script: scripts/gen10/t0_02_pooled_se_sweep.py
```

**Outcome: the defect is contained, but it was hiding a second and more common problem — archived
"POSITIVE" verdicts with no significance test attached at all.** The Gen-2/3 DS battery is clean,
which protects the highest-value item in the whole remediation plan. AEP Paper C's four sub-question
verdicts turn out to rest on point estimates that were never tested; supplying the tests retires one
of them outright and downgrades two more.

---

## 1. Part A — the DS battery is clean

`scripts/gen23/deepsearch.py` computes a per-date Spearman IC series and then applies
`_hac_tstat` (Newey-West, Bartlett, 4 lags) over dates. That is the correct unit of inference.
Verified empirically rather than by reading the code — six DS signals recomputed through the Gen-10
inference layer:

| ID | column | archived t | Gen-10 t | IC | n dates | naive pooled t |
|---|---|---|---|---|---|---|
| DS-U-02 | `delivery_pct_4w_avg` | +4.06 | **+4.05** | +0.0250 | 338 | +4.54 |
| DS-U-01 | `mom_60d_cs_z` | +2.91 | **+2.83** | +0.0138 | 1,121 | +9.00 |
| DS-F1-05 | `dv_deliv_price` | +4.21 | **+4.17** | +0.0230 | 338 | +6.62 |
| DS-F5-01 | `rel_deliv_sector` | +4.93 | **+4.88** | +0.0262 | 338 | +7.22 |
| DS-U-04 | `rel_deliv_sector` | +4.93 | **+4.88** | +0.0262 | 338 | +7.22 |
| DS-F4-02 | `pa_mom_declpart` | +6.33 | **+6.29** | +0.0131 | 1,121 | +8.10 |

6/6 reproduce within 0.1 t-units. The `naive pooled t` column shows how much work the harness is
doing — for DS-U-01 the defective statistic would have reported +9.00 against a true +2.83.

**This matters for sequencing.** Plan item 2.4 (running the DS battery through the Gen-5 economic
gate) is the highest-value item in the remediation plan, and it now rests on verified statistics.
The DS battery's real problems are elsewhere and unaffected by this: no discovery/OOS split
(`"lockbox_used": false` on all 28 manifests), FDR at q=0.10 rather than 0.05, and duplicate specs.
Those are T1-04a's job.

**Also confirmed here: DS-F5-01 and DS-U-04 are the same test.** Identical column, identical IC to
seven decimal places, identical t. They are one signal registered twice, not two signals — which
means the 28-hypothesis BH-FDR denominator was also wrong.

## 2. Part B — AEP Paper C: the tests that were never run

### Q3 Sizing — archived ACCEPTED, "the most economically material result in this sub-study"

| | fixed | liquidity-scaled |
|---|---|---|
| Sharpe | 0.6918 | 0.7271 |
| annualised vol | 0.2492 | 0.1923 |
| annualised return | **17.24%** | **13.98%** |

Paired Jobson-Korkie/Memmel test (the streams are the same book at different exposure, so they are
highly correlated and an unpaired test would be wrong):

```
Sharpe difference  +0.0353   SE 0.0710   t = +0.50   p = 0.619
bootstrap 95% CI   [-0.156, +0.209]
MDE at 80% power   +0.1992 Sharpe  ->  the observed effect is 0.18x the detectable floor
return given up     3.26 %/yr
```

The archived write-up reports two point Sharpes and no test. **t = 0.50.**

**And it is not a liquidity rule.** `PERSISTENT_REGIMES = {"NORMAL_UP", "STRESS"}` — the sizing keys
off the market-regime label. No measurement of liquidity persistence enters the decision; M-02's
finding is used to *justify* which labels to pick, not to compute anything. De-gearing one regime at a
time shows the regime selection is close to arbitrary with respect to performance:

| de-gear only in… | Sharpe |
|---|---|
| **CRASH** | **0.8164** |
| **STRESS** | **0.7775** |
| RECOVERY | 0.6940 |
| STRONG_UP | 0.5941 |
| NORMAL_UP | 0.5030 |
| *bundled Q3 rule* | *0.7271* |
| *ungeared baseline* | *0.6918* |

Two single-regime rules beat the bundled rule, and **one of them is a regime Q3 deliberately holds at
full exposure** — Q3 keeps 100% in STRESS, while de-gearing STRESS alone scores 0.7775 against the
full rule's 0.7271. The rule is a crash-and-stress de-gearing idea with the wrong regimes selected,
wearing a liquidity label.

Finally, the construction charges nothing for the de-gearing: `weekly_ret` is gross `target_1w`, with
no turnover cost for halving and restoring the book at every regime flip and no cash yield on the
un-invested half. A cost-aware version is worse than what is shown.

**Q3 is retired.** It is Gen-5 F11 / G5-05A (regime-conditioned gross exposure timing) under another
name — already TERMINATED_BY_GATE with a realizable estimate three times larger than this one, and
already retired in the remediation plan's own §5 as a capital-scale-independent skill failure.

### Q1 / Q4 Execution — archived POSITIVE (modest)

The cost series is already per-date, so the defect class does not apply; the problem is again that no
test was computed.

| capital | persistent | other | difference | **t (HAC)** |
|---|---|---|---|---|
| ₹100cr | 3.64 bps (n=638) | 3.89 bps (n=393) | −0.26 bps | **−1.75** |
| ₹500cr | 3.90 bps (n=638) | 4.20 bps (n=393) | −0.31 bps | **−1.75** |

The direction is consistent and reproduces the archived means exactly, but **|t| = 1.75 does not clear
the programme's own |t| ≥ 2 bar.** Verdict downgraded from POSITIVE to **directional, not
significant**.

This has a direct consequence for the remediation plan's Tier 2, which recommends folding Q1/Q2/Q4
"directly into the cost model / trading rules (e.g. prefer liquidity-persistent names when a trade can
go either way)." That would encode a t = −1.75 effect worth a quarter of a basis point as a standing
trading rule. **Not supported.**

### Q2 Universe — not recomputed
Q2 is a per-name correlation (−0.119, n=517) reported without a standard error. Names are not
independent — they share a market factor — so a naive t ≈ 2.7 overstates it, but by how much was not
computed here. **Flagged NO-TEST and left open**; it is a Tier-2 descriptive item, not on the Tier-1
path, and it is recorded as unresolved rather than silently reclassified.

## 3. Part C — classification of every archived verdict in scope

| archived result | class | note |
|---|---|---|
| AEP Paper B Sub-study 2a/2b | **DEFECTIVE** | pooled stock-week SE; both verdicts changed — T0-01 |
| AEP Paper B Sub-study 1 (Prototype 1) | CLEAN | alternate-split replication counting, not a pooled t; rejection stands |
| AEP Paper C Q1/Q4 | **NO-TEST** | two means, no test; supplied here — t = −1.75, downgraded |
| AEP Paper C Q2 | **NO-TEST** | name-level correlation, no SE; left open |
| AEP Paper C Q3 | **NO-TEST** | two point Sharpes, no test; supplied here — t = +0.50, retired |
| AEP Paper C Sub-studies 2+3 | CLEAN | clean null on matched Sharpes; a bad SE does not manufacture a null |
| AEP Paper D resolutions | CLEAN (multiplicity gap) | MI vs permutation null on non-overlapping windows; m=5 uncorrected — T1-07 |
| AEP Paper A redundancy | CLEAN | time-series MI with permutation nulls; not stock-week pooled |
| Gen-2/3 DS battery (28 items) | CLEAN | per-date IC then NW HAC; verified empirically |

## 4. Findings

**G10-F04 — the pooled stock-week SE defect is confined to AEP Paper B Sub-study 2.** Every other
archived result in scope either uses the correct per-date unit of inference or, in Paper C's case,
uses no inference at all. The Gen-2/3 DS battery is verified clean, which protects the remediation
plan's highest-value item.

**G10-F05 — the more common failure in the AEP papers is not a wrong test but a missing one.** Three
of Paper C's four sub-questions were given verdicts (ACCEPTED / POSITIVE) on the strength of point
estimates with no standard error. Supplying the tests retires Q3 (t = +0.50) and downgrades Q1/Q4
(t = −1.75) to directional-not-significant. A "POSITIVE (modest)" label should never have been
issuable without a test attached.

**G10-F06 — AEP Paper C Q3 is Gen-5 G5-05A rediscovered under a liquidity label, and its regime
selection is wrong on its own terms.** Not significant (t = 0.50, 0.18× its own detection floor),
costs 3.26 %/yr of return, keys off regime labels rather than any liquidity measurement, charges
nothing for the exposure switching, and is beaten by de-gearing in either CRASH alone (0.816) or
STRESS alone (0.778) — the latter being a regime Q3 holds at full exposure. **Retired.**

## 5. Errata required against the permanent record

1. **`results/AEP_PAPER_C/PAPER_C_ADAPTIVE_PORTFOLIO_MANAGEMENT.md`** — Q3's ACCEPTED verdict
   withdrawn; Q1/Q4 downgraded to directional-not-significant; Q2 flagged untested.
2. **`archive/11_registries/FINDINGS_REGISTRY.csv`, finding #43** ("liquidity-conditional sizing real
   but robustness-untested") — the effect is not established at all, not merely untested for
   robustness.
3. **`AEP_PROTOTYPE_REGISTRY.md`, Prototype 3** — Q3 sub-variant re-derived to REJECTED.
4. **`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §8d.**
5. **`Northstar_Remediation_Priority_Plan.md` §2.6** (Tier-1 item) and its Tier-2 row recommending
   Q1/Q2/Q4 be folded into the cost model — both void.

## 6. Threats to validity

- The Jobson-Korkie statistic assumes normal, i.i.d. returns. Momentum-book weekly returns are
  neither; both violations widen the interval, so t = 0.50 is if anything generous.
- The Q1/Q4 difference test combines two independently-estimated HAC standard errors rather than
  testing a single paired series, because the two arms are disjoint sets of dates. This is
  conservative in neither direction specifically; the point estimate reproduces the archive exactly.
- Part A verifies six of the 28 DS items, chosen to span the families (unconditional, divergence,
  sector-relative, path) and both history lengths (338 vs 1,121 dates). The remaining 22 use the
  identical `fast_ic` / `conditional_ic` / `failure_ic` code path.
- Q2 was not recomputed and is recorded as open.
