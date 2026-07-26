# MICRO-001 — Realistic Exit-Fill Model: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Microstructure
Depends On:         labs/microstructure/protocols/MICRO-001_EXIT_FILL_MODEL.md (frozen contract)
Verdict:            REJECTED (materiality hypothesis) — recorded in
                    research_os/MASTER_EXPERIMENT_REGISTRY.csv
```

**Outcome: the exit-fill drag is real and statistically distinguishable from zero, but two orders of
magnitude smaller than the crude bound it replaces — good news for the liquidity-gradient lead, not
bad.**

Artifacts: `micro001_data.json`, `micro001_breach_events.csv`. Script:
`labs/microstructure/protocols/run_micro001_exit_fill.py`. False-start artifacts preserved unedited at
`false_start_2026-07-26/` (never deleted, per every lab's inherited never-silently-rewrite-history
discipline).

---

## 1. A self-caught unit bug, disclosed before any verdict was trusted (P6)

The first run of this simulation produced a mean drag of **exactly −20.0000%** across all 89 breach
events, with a bootstrap 95% CI that was a **point mass** at the same value — zero variance across
2,000 resamples of 89 independent events. That is not a finding; it is the signature of a simulation
where nothing is actually varying, and it was treated as such rather than reported.

**Root cause:** `adv_13w` in the panel is already denominated in raw INR — verified directly (the
panel-wide minimum is exactly `1.00049e7`, matching the documented universe floor of "13-week median
traded value ≥ ₹1cr" to five significant figures). The first version of the script multiplied this
value by a further `1e7`, as if it were expressed in crore. That inflated every simulated position by
roughly **ten million times**, so the 5%-of-daily-volume unwind cap could never sell a meaningful
fraction of any position within the 20-day horizon — every single event hit the day-20 liquidity
discount at 100% unliquidated, producing the flat, suspicious −20% (the discount rate itself, applied
uniformly) with no cross-event variation whatsoever.

**Caught by the symptom, not by re-reading the code line by line**: a real market simulation across
89 independent, heterogeneous historical events producing *zero* variance is itself the tell. Fixed
by removing the erroneous `* 1e7`; the false-start output is kept on disk, not deleted.

## 2. The corrected result

| | |
|---|---|
| Breach-event population | 102 tickers (all non-quarantined, all with a documented post-breach daily tail) |
| Simulated unwinds | 89 (13 excluded: no post-breach tail or zero ADV at breach) |
| Mean per-position drag | **−0.431%** |
| Median per-position drag | **−0.136%** |
| Bootstrap 95% CI (2,000 draws) | **[−0.930%, −0.132%]** — excludes zero |
| Mean days to unwind (of a 20-day max) | **6.1** |
| Mean unliquidated fraction at day 20 | **1.5%** |

The unwind dynamics are now realistic: most positions liquidate within about a week, and only a small
residual (1.5%) hits the day-20 liquidity-discount floor — a plausible picture of what actually
happens when a name's liquidity degrades, rather than the false start's "nothing ever sells" artifact.

## 3. Annualized, per-tier, against G8-12's own exposure shares

| Tier | Exposure to later-truncated names (G8-12) | Modeled annualized drag |
|---|---|---|
| ALL | 4.5% | −0.019%/yr |
| FNO_LARGE | 5.5% | −0.024%/yr |
| NON_FNO_TAIL | 2.5% | −0.011%/yr |
| **SMALL_ADV_Q1** | **8.0%** | **−0.034%/yr** |

**SMALL_ADV_Q1 − ALL differential: −0.015%/yr.**

## 4. Gates and verdict

| Gate | Result |
|---|---|
| Direction (drag < 0) | **PASS** |
| Bootstrap CI excludes zero | **PASS** |
| Tier concentration (small-liquidity tier more exposed) | **PASS** |
| Materiality (\|differential\| > 0.5%/yr) | **FAIL** |

**Verdict: REJECTED** — specifically, the hypothesis that exit-fill realism is a *material* driver of
the G8-07/G8-11 tier effect. This is a precise distinction, not a downgrade to INCONCLUSIVE: the
effect is real and powered (the bootstrap CI excludes zero cleanly), it is simply too small to matter.
Reporting this as INCONCLUSIVE — as an earlier draft of this script's verdict logic would have — would
have conflated "real but negligible" with "we couldn't tell," which is exactly the distinction
`research_os/verdict_schema.py` exists to prevent. Caught and corrected before this document was
written, disclosed here rather than silently fixed.

## 5. What this means for the liquidity-gradient lead (G8-07/G8-11/G9-01)

**G8-12's bound (0 to −2.29%/yr) is superseded by a modeled figure roughly two orders of magnitude
smaller (−0.015%/yr differential).** The delisting-exit realism question that G8-12 flagged as the
gate between "a promising lead" and "a testable finding" turns out, once modeled rather than bounded,
to be a real but economically negligible drag. **The tier effect discovered in G8-07/G8-11
(non-F&O tail beating the full universe by +0.296 mean Sharpe, sign test p=0.00027 across 17 signals)
is not meaningfully explained away by execution realism at delisting exits.**

This does not validate the tier effect itself — that remains gated on the institutional-ownership
mechanism question (G9-02, still blocked by the 2010–2022 data gap; see MICRO-002) — but it removes
one of the two concerns G8-12 raised, cleanly and in the favorable direction.

## 6. Threats to validity

- **Position sizing convention.** Each simulated position is set to 10% of the name's own last-
  qualifying ADV — a reasonable single-name exposure convention, but not derived from an actual
  book's specific position-sizing rule. A book that sizes positions very differently (e.g., equal-
  weight across a fixed name count regardless of that name's own liquidity) would see a different
  drag.
- **The day-20 liquidity discount (20%) is a stated assumption**, not derived from data — chosen to
  be a real cost rather than a silent zero, per the contract's own requirement, but its exact size is
  not empirically calibrated. Given only 1.5% of positions hit this floor on average, its precise
  value has limited leverage over the headline result.
- **The 89-event sample excludes 13 tickers** with no post-breach tail or zero ADV at breach — these
  are disclosed as excluded, not folded in as zero-drag by assumption.
- **Single-day traded value is used as the ADV proxy for slippage** during the unwind, which may
  understate slippage on days immediately following breach if that day's volume is itself an outlier
  (e.g., a one-day volume spike from panic selling) rather than representative of sustainable daily
  liquidity.
- **No bid-ask spread data exists in this repository** for these names; slippage is entirely the
  existing √-impact cost model, an approximation this whole programme already relies on elsewhere.
