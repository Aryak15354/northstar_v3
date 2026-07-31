# Caveats on `deepsearch_summary.csv`

**Added 2026-07-31 by Gen-10.** Read this before using any number in that file. The CSV is left
unmodified — it is a faithful record of what the deep search computed.

## 1. Every row is full-sample

All 28 manifests carry `"lockbox_used": false`, and `deepsearch.fast_ic` runs across all dates. **No
row in that file has ever been evaluated out of sample**, with the single exception of DS-F3-04, which
was later split and collapsed from t = −4.4 to t = −0.06.

Gen-10 split 14 deduped items. Out-of-sample outcomes:

| survived | died |
|---|---|
| DS-F1-05, DS-F5-01, DS-U-02 — **and all three are one signal**, already deployed as G2-E03b | DS-F1-01, DS-F1-04, DS-F1-06, DS-F3-01, DS-F3-02, DS-F4-01, DS-F4-02, DS-F2-06, DS-U-01 |
| DS-F2-04 survives the rule, fails multiplicity, and shows **nothing in discovery** (t = +0.03) | DS-F2-03 — retired on transaction cost before Stage 1 |

**Net new deployable alpha from the battery: zero.**

## 2. Two rows are duplicate registrations

Verified identical to seven decimal places:

- `DS-U-04` ≡ `DS-F5-01` — both `rel_deliv_sector`
- `DS-U-03` ≡ `DS-F4-01` — both `pa_mom_smooth`

**The `bh_thr` column is therefore computed against a denominator of 28 when the true number of
distinct tests is 26**, and correlated duplicates inflate the apparent survivor count. Any re-use of
the FDR column should recompute it.

## 3. The `ic` column is not comparable to PANEL-A ICs

These ICs are measured on the broad enriched panel (~450 names/date). PANEL-A carries ~266. Pooling
two groups of stocks that differ systematically on both signal and forward return manufactures rank
correlation that exists in neither group — the pooled IC exceeds the IC of *either* group alone.

Composition share of the archived IC, measured directly:

| signal | share that is between-group composition |
|---|---|
| DS-F4-01 `pa_mom_smooth` | **+40%** |
| DS-U-01 `mom_60d_cs_z` | **+36%** |
| DS-F4-02 `pa_mom_declpart` | **+30%** |
| DS-F2-04 | +7% |
| DS-F2-06 | −5% |
| DS-U-02, DS-F5-01 (delivery) | **≈ 0** |

The artifact is coverage-dependent: signals straddling both universes are exposed, signals confined to
the liquid universe are not. **Delivery's numbers stand unchanged; the broad price signals' do not.**

## 4. `DS-F2-03`'s t = −8.91 is a cost profile, not a signal

The largest |t| in the file. Its top-quintile book turns over at **4091 %/yr**, against Gen-1 A04's
**4187 %/yr** — the reversal trade A04 already killed for exactly this reason (a 2236 %/yr control on
the same panel confirms the measurement discriminates). It is A04 wearing an interaction label.

---

Evidence: `results/gen10/T0-03/`, `results/gen10/T1-04a/`, `results/gen10/T1-09/`.
Archive addendum: `archive_addenda/GEN10_ADDENDUM_004.md`.
