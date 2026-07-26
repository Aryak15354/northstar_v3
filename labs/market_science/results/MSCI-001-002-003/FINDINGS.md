# MSCI-001 / MSCI-002 / MSCI-003 — Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Market Science
Verdict:            INCONCLUSIVE (all three, fixed by a pre-registered power gate)
```

Artifacts: `msci_001_002_003_data.json`. Script: `labs/market_science/protocols/run_msci_001_002_003.py`.
Panel: `data/kaggle_upload/panel_a_weekly.parquet`, 317,199 rows, 1,123 weeks (2005-01-07 to
2026-07-10).

---

## The gate that decided all three verdicts, stated once

Every predictor here is a **trailing rolling-window quantity computed on overlapping weekly data**,
so a naive `n = number of weeks` overstates statistical power enormously — adjacent weeks share
most of their construction window. The pre-registered design (see contract §"Shared methodology")
therefore sizes power off `n_eff = floor(weeks / 13)` — the number of **non-overlapping quarters**
available — a conservative but transparent discounting.

At `n_eff ≈ 80` and a pre-registered meaningful effect of `|r| = 0.15`, power is **~26%** for all
three tests; **347 non-overlapping quarters (≈67 years) would be needed for 80% power at this effect
size.** This was computed before any result was examined (`research_os.power_precheck`, run first in
the script for each hypothesis), and the contract's outcome rule is mechanical: **an underpowered
design cannot close VALIDATED or REJECTED, regardless of the point estimate.** All three therefore
close **INCONCLUSIVE** — this is a disclosed limitation of quarter-scale forecasting on ~20 years of
weekly Indian equity data, not evidence against any of the three hypotheses.

## Results, reported honestly by hypothesis

| | Pearson r | NW t | NW p | perm p | direction vs. hypothesis |
|---|---|---|---|---|---|
| **MSCI-001** (stability → future IC) | **−0.227** | −3.08 | 0.0021 | 0.031 | **reversed** |
| **MSCI-002** (interaction complexity → decay) | −0.052 | −0.58 | 0.559 | 0.520 | matches, but ≈0 |
| **MSCI-003** (redundancy → crowding) | −0.189 | −2.00 | 0.046 | 0.066 | matches |

All three passed `rolling_window_artifact_check` at "EXCEEDS_CONSTRUCTION" — the predictor's
persistence is not purely a construction artifact of its own window (see caveat below) — so the
underlying signal in each predictor series is real; it is the *forecasting relationship to future IC*
that is underpowered to adjudicate.

**MSCI-001 is the one worth flagging for a future session, explicitly as an exploratory observation,
not a finding.** The pre-registered hypothesis was that *higher* trailing rank-stability of
`res_mom_52w_ex4w` predicts *higher* forward IC. The observed relationship is the opposite sign and
the strongest of the three (NW p=0.002, permutation p=0.031 — nominally "significant" on both, and
only closes INCONCLUSIVE because the pre-registered power gate is mechanical regardless of p-value).
A plausible reading, stated as speculation and not investigated further here: when a signal's
cross-sectional ranking is *unusually stable* week-to-week, that may itself indicate a period where
little genuine cross-sectional dispersion is being resolved (a "quiet," low-information regime) —
the reverse of what the pre-registered hypothesis assumed. This is exactly the kind of result the
charter says to report honestly rather than force into the hypothesized direction.

**MSCI-002 is a clean null**, not merely underpowered — the point estimate itself is near zero
(r=−0.05). The interaction-complexity measure trialed here shows no detectable relationship to
`res_mom_52w_ex4w`'s own subsequent IC at any power level tested.

**MSCI-003 is the closest to a positive result of the three** — direction matches the crowding
hypothesis, NW p clears 0.05, but the permutation p (0.066) — the more conservative test, since it
respects the predictor's own autocorrelation structure via circular block resampling — does not. This
is the one most worth revisiting first if/when more data accrues.

## The rolling-window artifact check caveat (Gen-8 correction), applied here

All three predictors legitimately exceed their own construction null (`EXCEEDS_CONSTRUCTION`), which
means the persistence in the predictor series is not simply an artifact of its rolling window. This
check says nothing about the *predictive* relationship tested above — it only clears the predictor
series itself of being pure construction noise. Per the Gen-8 correction, the differencing screen
component is a one-way conservative filter (a highly persistent, genuine AR process can legitimately
fail it), so the construction-null component (test B) is treated as primary throughout, exactly as
specified in the contract.

## What would resolve these

Roughly 67 years of non-overlapping quarterly data are needed at this effect size and horizon — not
achievable by waiting. Two honest paths forward, neither pursued here (out of scope for this
contract, which was to run the pre-registered test, not redesign it after seeing it was underpowered):

1. **Shorten the forecast horizon** (K=13 was chosen for one pre-registered reason: a quarter is
   economically meaningful; a shorter horizon, e.g. K=4, would roughly triple `n_eff` at the cost of a
   noisier, less economically meaningful outcome — a real trade-off, not a free lunch).
2. **Pool across more signals** (rather than one hypothesis on one signal), which raises `m_tests` and
   requires the multiplicity correction in `research_os.valid_pvalue` — a different, larger pre-
   registered design, not a re-run of this one.

Both are legitimate directions for a future MSCI experiment; neither is implied to already be
promising by the numbers above.
