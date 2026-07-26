# MSCI-001 / MSCI-002 / MSCI-003 — Evolving MSRP from Descriptive to Predictive Science

```
Version:            v1.0
Status:             Frozen (pre-registration — written before any result-producing code runs)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                market_science
Depends On:         results/msrp/PHASE1_SYNTHESIS_FROZEN.md (the information hierarchy),
                    results/msrp/M-01..M-05 (the memory findings these hypotheses build on),
                    docs/FIELD_REPORT_2026_07_26.md section 2a's explicit reframing
```

**A real methodological escalation, not a follow-on script to a frozen result.** MSRP's Phase 1/2
answered *descriptive* questions: does information exist, how is it organized, does it persist. These
three hypotheses ask *predictive* questions: does a structural property, measured only from trailing
data, forecast a future, out-of-sample outcome. Each is pre-registered, walk-forward, and validated by
permutation-null and replication — **never by Sharpe or any portfolio metric**, per this lab's
absolute charter prohibition. A result here that looks tradeable is handed to Alpha Engine as a fresh
hypothesis, never validated as a finding of this lab.

---

## Shared methodology

**Walk-forward, PIT-safe throughout.** Every predictor below is computed at week *t* using only data
through *t*; it is then tested against realized outcomes over `(t, t+K]`, never overlapping with its
own construction window in a way that would leak.

**Validation, all three hypotheses:**
1. Newey-West HAC test of the correlation between the trailing predictor and the forward outcome.
2. A circular block-bootstrap permutation null (valid `(1+k)/(N+1)` p-value, per
   `research_os.valid_pvalue`) — never a floored `k/N` estimator.
3. Power precheck (`research_os.power_precheck`) run and logged before results are examined.
4. Where the predictor involves a rolling window: `research_os.rolling_window_artifact_check`, with
   the Gen-8 caveat stated inline — the calibrated construction null is the primary discriminator, not
   differencing alone.

**Pre-registered forecast horizon: K = 13 weeks** for all three (roughly one quarter — long enough to
be economically meaningful, short enough that the full sample supports many non-overlapping-ish
observations; chosen once, before any hypothesis-specific tuning).

---

## MSCI-001 — Does primitive stability predict future IC?

**Hypothesis.** `res_mom_52w_ex4w`'s trailing cross-sectional rank-stability (how much the relative
ranking of stocks by this signal persists week to week, computed over a trailing 52-week window)
predicts the signal's own forward-realized cross-sectional IC over the next 13 weeks.

**H-MSCI-001-1:** Higher trailing rank-stability predicts higher forward IC (a stable ranking reflects
a genuine, persistent economic ordering rather than noise). *H₀: no correlation.*

**Predictor construction:** trailing 52-week mean of the week-over-week Spearman rank correlation of
`res_mom_52w_ex4w` across the same cross-section, computed strictly from data through week *t*.

**Outcome:** forward-realized weekly cross-sectional Spearman IC of `res_mom_52w_ex4w` vs.
`target_1w`, averaged over `(t, t+13]`.

## MSCI-002 — Does interaction complexity predict factor decay?

**Hypothesis.** The trailing interaction strength between `res_mom_52w_ex4w` and
`consistency_mom_26w` (the confirmed Interaction Persistence primitive, I-05/M-05) predicts a
*decline* in `res_mom_52w_ex4w`'s own forward IC — a crowding/complexity-precedes-decay story.

**H-MSCI-002-1 (primary):** Higher trailing interaction strength predicts *lower* forward IC of
`res_mom_52w_ex4w` over the next 13 weeks. *H₀: no correlation.*

**Predictor construction:** trailing 104-week incremental Spearman-rank contribution of
`consistency_mom_26w` over `res_mom_52w_ex4w` alone in predicting `target_1w` (the same incremental-
information logic MSRP's I-04/I-05 used, computed on a rolling trailing basis rather than the full
sample) — never using data beyond week *t*.

## MSCI-003 — Does structural redundancy forecast crowding?

**Hypothesis.** Rising trailing structural redundancy between the momentum family
(`res_mom_52w_ex4w`, `ret_52w_ex4w`, `sharpe_mom_26w`, `consistency_mom_26w`) and the volatility
family (`vol_13w`, `vol_52w`, `beta_104w`, `idio_vol_13w`) precedes a period of lower realized
momentum-composite IC — the direct forecasting version of MSRP's own structural-redundancy metric.

**H-MSCI-003-1:** Higher trailing cross-family redundancy predicts *lower* forward IC of the momentum
composite over the next 13 weeks. *H₀: no correlation.*

**Predictor construction:** trailing 52-week mean pairwise absolute correlation between the two
families' cross-sectionally z-scored values, computed strictly from data through week *t*.

---

## Exclusions (all three)

- No portfolio, no Sharpe, no economic claim of any kind — a positive predictive finding here is
  handed to Alpha Engine as a fresh, separately pre-registered hypothesis, never validated as a
  trading signal by this lab.
- Single pre-registered horizon (K=13) — no scan across horizons; a horizon scan would be a separate,
  explicitly exploratory follow-up.
- No claim about causality — these are pure forecasting/correlation tests of structural properties.

## Outcome classification

Each of the three closes independently with one of the four schema verdicts, per its own gates stated
in the execution script. A result classified VALIDATED here means "this structural property has
demonstrated, walk-forward, out-of-sample predictive power over a market-science quantity (future
IC)" — nothing more, and specifically not "this is tradeable."
