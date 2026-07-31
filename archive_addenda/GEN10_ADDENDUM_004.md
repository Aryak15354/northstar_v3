# GEN-10 ADDENDUM 004 — The deep-search battery: out-of-sample survival and a measurement artifact

```
Addendum:        GEN10_ADDENDUM_004
Issued:          2026-07-31
Author:          Aryak (Gen-10 Remediation Programme)
Addresses:       NSR-EXP-000001, -000004, -000005, -000006, -000009, -000010, -000012,
                 -000013, -000014, -000018, -000019, -000020, -000025, -000026, -000027,
                 -000028  (the deep-search battery, DS-F1-01 through DS-U-04)
Archive version: v1.0 (unmodified)
Evidence:        results/gen10/T0-03, T1-04a, T1-09 FINDINGS.md
Mechanism:       archive/GEN7_INTERFACE_RULE.md — addendum, not edit
```

## 1. What the archive records

Sixteen deep-search experiments carry permanent IDs, most with status **RESEARCH_SIGNAL** and the
registry's own note that this is *"not a rejection… no alpha/portfolio/economic-law content identified
[yet]"*. The archive is **not** altered; their status at freeze time was correct given the evidence
then available.

## 2. Two facts that were not visible at freeze time

### (a) None of them had ever been evaluated out of sample

Every manifest in `scripts/gen23/deepsearch.py` carries `"lockbox_used": false`, and `fast_ic` runs
across the full sample. Significance was BH-FDR at **q = 0.10**. The one item later given a genuine
split — DS-F3-04 — collapsed from t = −4.4 to t = −0.06.

Gen-10 ran that split for fourteen deduped items:

| ID | archived t | out-of-sample | outcome |
|---|---|---|---|
| NSR-EXP-000001 DS-F1-01 | −1.88 | −1.28 | killed |
| NSR-EXP-000004 DS-F1-04 | −2.95 | −1.85 | killed |
| NSR-EXP-000006 DS-F1-06 | +3.46 | +0.42 | killed |
| NSR-EXP-000013 DS-F3-01 | +2.34 | +1.91 | killed |
| NSR-EXP-000014 DS-F3-02 | +3.02 | +1.76 | killed |
| NSR-EXP-000018 DS-F4-01 | +3.06 | +1.36 | killed |
| **NSR-EXP-000019 DS-F4-02** | **+6.33** | **+1.73** | **killed** |
| NSR-EXP-000012 DS-F2-06 | +3.38 | +1.32 | killed |
| NSR-EXP-000025 DS-U-01 | +2.91 | +1.40 | killed |
| **NSR-EXP-000009 DS-F2-03** | **−8.91** | — | **retired on cost before Stage 1** |
| NSR-EXP-000010 DS-F2-04 | +2.20 | +2.31 | survives rule, fails multiplicity |
| NSR-EXP-000005 DS-F1-05 | +4.21 | +2.92 | survives — but see §3 |
| NSR-EXP-000020 DS-F5-01 | +4.93 | +3.92 | survives — but see §3 |
| NSR-EXP-000026 DS-U-02 | +4.06 | +3.07 | survives — is the already-promoted G2-E03b |

**DS-F2-03 (NSR-EXP-000009)**, the largest |t| in the entire battery, is Gen-1's already-killed
reversal trade under an interaction label: top-quintile turnover **4091%/yr against A04's 4187%/yr**,
with a 2236%/yr control confirming the measurement discriminates. Retired on transaction cost before
any statistical stage.

### (b) Duplicate registrations

Two pairs are **the same specification registered twice**, verified identical to seven decimal places:

- **NSR-EXP-000028 (DS-U-04) ≡ NSR-EXP-000020 (DS-F5-01)** — both `rel_deliv_sector`, IC and t identical.
- **NSR-EXP-000027 (DS-U-03) ≡ NSR-EXP-000018 (DS-F4-01)** — both `pa_mom_smooth`.

The permanent IDs remain assigned and are never reused (per `HOW_TO_CITE_THIS_ARCHIVE.md`); this
records that they denote one test each, not two. It also means **the 28-hypothesis BH-FDR denominator
was wrong**, and correlated duplicates inflated the apparent survivor count.

## 3. The three survivors are one signal, already deployed

DS-F1-05, DS-F5-01 and DS-U-02 are all built from `delivery_pct_4w_avg`. Pairwise per-date Spearman
0.72–0.92. Orthogonalised against DS-U-02 — which *is* G2-E03b, already certified and promoted through
ARP — the challengers retain **16%** and **9%** of their t-statistics (3.92 → 0.61, 2.92 → 0.27).
Neither cleanly subsumes the other in reverse.

This is Gen-5 **F01** again (momentum's four members individually significant, jointly redundant,
leave-one-out ≈ 0), now demonstrated for the delivery family.

## 4. A measurement artifact affecting the broad-coverage members

A cross-sectional IC is **not comparable across universes of different breadth.** The enriched panel
used by the deep search pools two groups of stocks that differ systematically on both the signal
(mean +0.054 vs −0.125) and the forward return (+0.0035 vs +0.0017). The pooled IC therefore exceeds
the IC of *either group alone*:

```
union, as measured                       IC = +0.0138
union, restricted to the liquid universe IC = +0.0086
union, the extra names only              IC = +0.0050
union, between-group variation removed   IC = +0.0089   ->  36% was composition
```

The artifact is **coverage-dependent**, and therefore predictable:

| signal | composition share of the archived IC |
|---|---|
| DS-F4-01 | **+40%** |
| DS-U-01 | **+36%** |
| DS-F4-02 | **+30%** |
| DS-F2-04 | +7% |
| DS-F2-06 | −5% |
| DS-U-02, DS-F5-01 (delivery) | **≈ 0** — coverage is 94% inside the liquid universe |

Broad price signals are exposed; narrow microstructure signals are not. The delivery family's
archived numbers stand unchanged.

## 5. Net effect on the archived record

| archived element | status after this addendum |
|---|---|
| the 16 experiments' RESEARCH_SIGNAL status at freeze time | **stands** — correct on the evidence then available |
| RESEARCH_SIGNAL as a predictor of deployability | **superseded** — it predicts full-sample fit, not out-of-sample survival |
| NSR-EXP-000028 / -000027 as distinct experiments | **duplicates** of -000020 / -000018 |
| the archived ICs of the broad-coverage members | **inflated 30–40%** by universe composition |
| the archived ICs of the delivery members | **unchanged** |
| DS-F2-03's t = −8.91 | **economically void** — a transaction-cost profile, not a signal |

**Net new deployable alpha from the battery: zero.**

**Live documents updated to match:** `results/gen23/deepsearch_summary.csv`,
`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §2a.

## 6. Threats to validity of this addendum

- The composition correction uses a two-group split. A finer split by ADV decile would attribute more,
  so the shares above are lower bounds and the kills are conservative in the right direction.
- The delivery cluster's out-of-sample window is 79 weeks and its lockbox 51; the five kills there
  should be read as "did not replicate in 2024–25" rather than "does not exist". The momentum-quality
  cluster had 392 out-of-sample weeks and carries no such caveat.
- Six of the sixteen were re-verified against their archived t-statistics and reproduced within 0.1
  t-units, confirming the archived numbers themselves are sound; the remaining ten use the identical
  code path.
