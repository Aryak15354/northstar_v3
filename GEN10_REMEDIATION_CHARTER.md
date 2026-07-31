# Gen-10 — Remediation & Re-Discovery Programme: Charter and Pre-Registration

```
Version:      v1.0
Status:       OPEN
Opened:       2026-07-31
Owner:        Aryak
Source plan:  Northstar_Remediation_Priority_Plan.md (v2, 2026-07-30)
Review:       REMEDIATION_PLAN_FEASIBILITY_REVIEW.md (2026-07-31)
Supersedes:   nothing. Extends Gen-8/9 (RRD) into the plan's Tier-1 backlog.
```

## 1. Why this programme exists

The plan identified ~460 catalogued hypotheses of which a subset was never genuinely closed:
statistically detected but never economically gated, blocked on data, or sitting just under a
significance bar. Gen-10 runs that Tier-1 backlog.

The feasibility review changed the running order. Two Tier-1 items (2.5, 2.6) turned out to rest on
statistics that do not survive correction, one (2.3) prescribed the opposite of its own source
finding, and two (2.1, 2.2) are bounded by a data window the plan never accounted for. Gen-10
therefore opens with an **inference-integrity tier** before running any new experiment, because the
Tier-0 findings re-rank the rest.

## 2. Standing methodological law (binding on every Gen-10 experiment)

**G10-L01 — One date is one observation.** No hypothesis test may treat pooled stock-weeks as
independent. Every test collapses to a per-date series before inference. Violating this is what
produced AEP Paper B's Sub-study 2b verdict.

**G10-L02 — Overlap must be declared.** Any test using h-period forward returns declares `overlap=h`
so the Newey-West bandwidth floor covers the induced MA(h-1) structure.

**G10-L03 — Two estimators, or it is fragile.** Every headline number carries both a Newey-West HAC
test and a stationary block-bootstrap interval. Where they disagree about significance, the result is
reported as FRAGILE. Neither may be selected after the fact.

**G10-L04 — Power before result.** Every comparison states its minimum detectable effect *before*
running. A design whose MDE exceeds its own bar is reported as underpowered and is not run to
completion. (G7-F02, G8-09 s2.)

**G10-L05 — Paired where paired applies.** Sharpe comparisons between streams on the same dates use
the Jobson-Korkie/Memmel paired statistic. Two independent Sharpe SEs are never used for correlated
streams.

**G10-L06 — Matched windows.** No comparison may mix statistics estimated on different date ranges.
Delivery-dependent work is bounded to 2020+ and says so in every headline number.

**G10-L07 — Multiplicity is counted across everything tried**, including variants abandoned mid-run
and resolutions/specifications selected from. Correlated families use Benjamini-Yekutieli, not
Benjamini-Hochberg.

All are enforced in code by `src/research/gen10/inference.py` rather than by convention.

## 3. Data limits, stated up front

| Constraint | Effect |
|---|---|
| `delivery_pct` 2020-01-03 → 2026-06-26, 339 weeks; `delivery_pct_z52` 320 weeks from 2020-05-15 | Bounds items 2.1, 2.2, and the 2.4 delivery cluster. Excludes the COVID crash from the z52 construction. |
| Regime cells in the delivery era: CRASH 29w, RECOVERY 15w | Below MSRP's own `MIN_N=30`. 2.2 collapses to two states. |
| `^TNX`, `DX-Y.NYB` begin 2018-01-02 (~420 weeks) vs crude/USDINR (1,070) | Carrier budget for 2.7 must be weighted to long-history symbols. |
| Delisted archive ends 2024-07-29; 56 of 327 names quarantined | Bounds 2.3'. |
| No PIT analyst consensus, no borrow data, no intraday | R01–R08, A5, G5-08A_EXECUTION_ENGINE stay closed. |

## 4. Pre-registered contracts

Each contract states the kill criterion **before** the run. A result that meets neither the promote
nor the kill condition is recorded as UNRESOLVED with its MDE, not re-specified until it resolves.

### T0-01 — AEP Paper B Sub-study 2, standard-error correction
- **Question.** Do the four candidate roles for `consistency_mom_26w` survive date-clustered inference?
- **Design.** Re-run all four sub-studies (2a Confirms, 2b Warns, 2c Delays, 2d Accelerates-exits)
  through `date_clustered_group_diff` at horizons 1/4/8/13w, reporting the naive pooled t alongside.
- **Promote.** Any role with |t| ≥ 2 under NW *and* a bootstrap CI excluding zero *and* an effect
  monotone in horizon → carried to T1-05 for the economic gate.
- **Kill.** Any role whose corrected |t| < 2 at every horizon → retired, erratum issued.
- **Multiplicity.** m=4 roles × 4 horizons declared; BY correction applied to the promote decision.

### T0-02 — Pooled-SE sweep across AEP Papers C/D and the Gen-2/3 DS battery
- **Question.** How many other archived verdicts rest on the same defect?
- **Design.** Recompute each archived t-statistic on per-date series. No new hypotheses.
- **Output.** A table of `verdict_before` / `verdict_after`. Any verdict that flips triggers an erratum.

### T0-03 — Momentum harness reconciliation
- **Question.** `mom_60d_cs_z` and `ret_13w` have per-date Spearman 0.969 but carry three different
  verdicts (NOISE t=1.17, RESEARCH_SIGNAL t=2.91, RESEARCH_SIGNAL t=3.36). Which harness is right?
- **Design.** Hold the signal fixed; vary one harness axis at a time (target definition, universe,
  IC method, window) and attribute the t-gap to specific axes.
- **Kill/Promote.** Not a promote/kill item — it is a measurement-validity item. Output is a stated
  rule for which harness is authoritative for cross-generation comparison.

### T1-04a — DS-battery delivery cluster through the Gen-5 economic gate
- **Universe of tests.** DS-F1-01/04/05/06, DS-F3-01/02, DS-F5-01, DS-U-02/04, deduped against
  DS-F5-01 ≡ DS-U-04 and against the already-promoted G2-E03/E03b.
- **Stage 1.** Discovery/OOS split — the first any DS item has ever had. Kill if the OOS |t| < 2 or
  the sign flips.
- **Stage 2.** Oracle ceiling. Kill if the perfect-signal ceiling fails the +0.15 Sharpe bar (the bar
  G8-09 used).
- **Stage 3.** Realizable skill with CI. Kill if the CI includes zero.
- **Stage 4.** Net-of-cost on the real `IndianEquityCostModel` capacity ladder.
- **Multiplicity.** Declared across the full deduped cluster, BY-corrected.

### T1-05 — Corrected Paper B role, economic gate
- Conditional on T0-01 promoting a role. Same four stages. Kill conditions identical.

### T1-06 — Delivery sleeve integration (2.1') and regime dependency (2.2')
- **2.2' first**, because its output sizes 2.1'. Two-state regime collapse
  (NORMAL_UP+STRONG_UP vs STRESS+CRASH+RECOVERY), both sides clearing MIN_N=30.
- **2.1' is a sizing question, not a significance question.** Pre-registered: *what Sleeve-B weight
  maximises blended Sharpe when Sleeve B's Sharpe is set to the lower bound of its own 320-week CI,
  and does that weight remain strictly positive across the whole capacity ladder?*
- **Promote.** Optimal weight > 0 at the CI lower bound across the ₹5L–₹100cr band.
- **Kill.** Optimal weight collapses to 0 at the lower bound, or name-overlap makes the sleeves
  non-separable.
- The unpaired blend-vs-momentum significance test is reported as **descriptive only**, with its MDE
  stated, because G8-09 already established that design cannot resolve at this n.
- All numbers on the matched 2020–2026 window. Config-4's full-history Sharpe is not used.

### T1-07 — Paper D multiplicity correction (2.8')
- **Design.** Apply BY across the five resolutions monthly was selected from. No re-run unless it
  survives.
- **Kill.** Monthly fails the corrected threshold → retired; F17's weekly null becomes the settled
  answer at all resolutions.

### T1-08 — Exit-realism sweep (2.3', replacing the plan's universe-rule rewrite)
- **Rationale for the substitution.** G8-12 established the universe rule is the strategy's own stop,
  not a bug, and that the remaining task is execution realism. Rebuilding the panel to hold names to
  delisting would model a book that would not be traded.
- **Design.** Charge a gap-down exit when a name leaves the universe on a price/liquidity failure.
  Sweep the exit assumption clean-fill → −10% → −20% → −35% → −50%.
- **Output.** The exit assumption at which G8-07's +0.222 to +0.296 Sharpe tier lead stops being a lead.

### T1-09 — DS momentum-quality and cross-factor clusters
- As T1-04a. **DS-F2-03 runs Stage 4 first**: it is a reversal × illiquidity interaction, and Gen-1
  killed that family twice (A04 on turnover, A15/A19 on impact cost). Pre-registered: if its turnover
  profile matches A04's, it is retired without running Stages 2–3.

### T1-10 — Gen-7 CAIT redesign
- Blocked until a contract resolving G8-10 §4's three points is written: pooled-vs-per-stock,
  date-clustered SEs, and whether broad market-beta transmission counts as an answer.
- **Pre-registered beta control.** Receivers residualised against the market before testing. A carrier
  hitting all receiver groups roughly equally is scored as beta, not transmission.
- **Effect floor** r ≈ 0.11 per G7-F04/G8-02. A properly-powered null closes the question permanently.

## 5. Retired at open (do not run)

- **Plan item 2.6 (AEP Paper C Q3 liquidity-persistence sizing).** Sharpe delta +0.035, paired
  t = 0.50. The rule keys off market-regime labels, not liquidity persistence. Its entire effect is
  CRASH de-gearing, and de-gearing only in CRASH scores 0.816 against the bundled rule's 0.727 while
  STRONG_UP de-gearing is destructive (0.594). It is Gen-5 F11 / G5-05A under another name, already
  TERMINATED_BY_GATE at three times this effect size, and it charges no cost for the exposure
  switching. Recorded, closed. See T0-02 for the formal write-up.
- **Plan item 2.3 as written** (universe-rule rewrite + panel rebuild) — replaced by T1-08.
- **Plan Section 6** — both gaps resolved in the feasibility review; 16 of the 17 un-enumerated
  registry rows were already covered by the plan. The one omission, G2-B03b (order-win announcements),
  is logged to Tier 3.

## 6. Definition of done

Gen-10 closes when every T-item above is either promoted with a dossier, killed with a recorded
negative, or marked UNRESOLVED with its MDE stated. "Ran out of time" is not a verdict.
