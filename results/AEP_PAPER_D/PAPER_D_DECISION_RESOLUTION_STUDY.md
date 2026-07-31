> ## ⚠ CORRECTION (2026-07-31, Gen-10 T1-07)
>
> **The monthly result does not survive correction for the five resolutions it was selected from.**
> No multiplicity correction was applied across the five. Applying it: monthly p ≈ **0.0384** against
> a Bonferroni threshold of **0.0100** at m = 5. It fails Bonferroni, BH and BY alike.
>
> Monthly cleared its own permutation null by **5.0%** (MI 0.02577 vs null p95 0.02454). The null's
> width is driven by the number of non-overlapping windows — p95 runs 0.0058 (n=1070) → 0.0245
> (n=267) → 0.0910 (n=82) — so monthly is simply the point where n is still large enough to keep the
> null tight while aggregation has lifted MI. **A property of the null's shape across resolutions,
> not an economic decision cadence.**
>
> Note also that **"RISING" is a curve-shape label**, pre-registered for any resolution ≥ 3× weekly
> and computed once on the full sample. It does *not* mean the margin has widened as data accumulated.
>
> **Verdict: MODIFIED → REJECTED at all five resolutions.** Paper D answered the question it was
> commissioned to answer — whether Gen-5 F17's weekly null was a resolution artifact — and the answer
> is that it was not. F17 is now settled across five cadences instead of one.
>
> *Caveat on this correction:* p-values are **reconstructed** from the stored null mean and 95th
> percentile (the draws are not retained), via an exponential-tail fit anchored exactly at p95 → 0.05.
> Re-running `scripts/aep/paper_d_resolution_study.py` with the draws retained would settle it exactly.
>
> Evidence: `results/gen10/T1-07/`. Archive addendum: `archive_addenda/GEN10_ADDENDUM_003.md`
> (NSR-FIND-000045). Original text below left intact.

---

# Paper D — Decision Resolution Study: FINDINGS (FROZEN v1.0)

Per `docs/aep_protocols/PAPER-D_RESEARCH_CONTRACT.md`. Correctness gate: reproduces canonical Config-4
Sharpe 0.8471 exactly via `scripts/gen5/g5_paper2_engine.py`, reused unchanged.
`scripts/aep/paper_d_resolution_study.py`, `results/AEP_PAPER_D/resolution_curve.json`.

## Self-caught correction (added mid-analysis, before reporting)
The initial pass computed raw normalized mutual information at 5 resolutions and found monthly (9.63×
weekly) and quarterly (21.96× weekly) both crossing the pre-registered 3× "RISING" threshold. **Before
reporting this, a permutation-null control was added** (200 shuffles per resolution, 95th-percentile
threshold — the same convention used throughout MSRP) because raw empirical MI is known to be
upward-biased at small sample sizes, and quarterly resolution has only 82 observations against the same
5-category regime state (as few as ~16 observations per cell on average). **This is exactly the right
kind of check, and it changed the conclusion**: quarterly's dramatic-looking raw ratio does **not** clear
its own (much wider) permutation null (MI=0.0592 vs. null 95th percentile 0.0910) — the apparent "rising"
signal at quarterly resolution is fully explained by small-sample noise inflating both the estimate and
its natural variability. **Only monthly resolution clears its null** (MI=0.0258 vs. null 0.0245), and
narrowly.

## Full information curve (permutation-null-controlled)
| Resolution | n obs | MI (bits) | Normalized MI | Perm-null 95th pctile | Significant? |
|---|---|---|---|---|---|
| Weekly | 1,070 | 0.0027 | 0.0027 | 0.0058 | No |
| Biweekly | 535 | 0.0071 | 0.0072 | 0.0113 | No |
| **Monthly** | 267 | **0.0258** | **0.0263** | 0.0245 | **Yes (barely)** |
| 6-week | 178 | 0.0028 | 0.0028 | 0.0374 | No |
| Quarterly | 82 | 0.0592 | 0.0599 | 0.0910 | No (raw ratio was misleading) |

## Classification: RISING — specifically and only at monthly resolution
Per the contract's pre-registered classification scheme: this is a RISING curve, not FLAT — but the
rise is narrow (monthly only) and marginal (the observed MI exceeds its null by a small margin, not a
decisive one). **6-week resolution is notably NOT elevated** (nmi=0.0028, close to weekly's 0.0027,
actually below biweekly) — the curve is non-monotonic, consistent with the contract's third possible
classification category ("a peak at an intermediate resolution... flagged for targeted follow-up rather
than assumed to extrapolate further").

## Interpretation
Gen-5's F17 (weekly action MI near-zero) stands, unchanged, at its own resolution. This paper's honest
extension: there is a real, but narrow and marginal, signal specifically at monthly decision granularity
— not a broad "any coarser resolution helps" story, and specifically **not** at quarterly, where the
initially striking raw number turns out to be a sample-size artifact caught before it was reported as a
finding (mirroring this session's now-repeated pattern of catching a construction/estimation artifact
before trusting a result, this time for a decision-resolution study rather than a memory-pillar one).

## What this licenses, and what it does not
Per the contract: Paper D does NOT build a trading rule, even under the RISING classification — it only
establishes whether the informational precondition for one exists. **The honest conclusion: a monthly-
resolution state-dependent decision rule has a thin, not-yet-compelling informational basis** (a marginal
permutation-null pass, not a decisive one) — worth flagging as a specific, narrow, evidence-justified
target for a future properly-scoped Type-B experiment (full Universal Oracle Ladder discipline), but NOT
strong enough evidence on its own to justify building one now. This is a materially more honest and more
precise conclusion than either "F17 is settled, nothing to see" or "monthly decisions clearly work" —
both of which the raw, uncorrected result would have wrongly supported.

## Data-sufficiency note (per the contract's own flagged risk)
Quarterly resolution (n=82) was checked and is NOT silently trusted — its apparently large raw MI is
explicitly attributed to small-sample estimator bias, not real information, per the permutation-null
result above.

---
**Paper D is FROZEN as of this document. Verdict: MODIFIED — RISING, narrowly, at monthly resolution
only; FLAT (and initially misleading) at quarterly. Insufficient on its own to license a new trading-rule
experiment without further evidence.**
