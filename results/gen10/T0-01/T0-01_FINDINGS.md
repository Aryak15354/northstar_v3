# T0-01 — AEP Paper B Sub-study 2: Standard-Error Correction. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/AEP_PAPER_B/, scripts/aep/paper_b_substudy2_conditional_activation.py,
              GEN10_REMEDIATION_CHARTER.md s4/T0-01 (pre-registration)
Artifacts:    t0_01_data.json. Script: scripts/gen10/t0_01_paper_b_se_correction.py
```

**Outcome: the two headline results of AEP Paper B Sub-study 2 swap places.** The role that was
CONFIRMED (2b "Warns") is retired — it fails under correct inference and sign-flips out of sample.
The role recorded as a near-miss (2a "Confirms") is the only coherent effect of the four, but it does
**not** clear the multiplicity correction this experiment pre-registered, and the lockbox is too short
to adjudicate it. Verdict: **2b RETIRED, 2a UNRESOLVED.**

---

## 1. The defect

`scripts/aep/paper_b_substudy2_conditional_activation.py` tests each role with

```python
se = sqrt(hi.var()/len(hi) + lo.var()/len(lo))    # len(hi)+len(lo) ~ 62,000 stock-weeks
```

Those observations are not independent, twice over:

- **Overlap.** `fwd_ret_8w` at week *t* and week *t+1* share seven of their eight weeks. The series
  is MA(h−1) by construction.
- **Cross-sectional dependence.** All stocks in a week share a market factor. A week is closer to one
  observation than to 500.

Effective sample is ~1,030 dates, not ~62,000 stock-weeks. The repo already knew this — `G8-10 §4.2`
demands date-clustered SEs by name, and `G9-02 §1` documents catching the identical error in its own
v1 and discarding the result rather than reporting it. Paper B shipped with it.

## 2. Corrected results — discovery window (2005-09-30 → 2025-07-04, 1,032 dates)

Per-date difference series, Newey-West with Bartlett kernel and bandwidth floor h−1, plus a
stationary block bootstrap as an independent second opinion. The naive column reproduces the archived
numbers exactly, which confirms the reproduction is faithful and the only change is inference.

### 2a "Confirms" — High-Trend × [High-Consistency vs Low-Consistency]

| horizon | effect | naive pooled t | **corrected t** | bootstrap 95% CI |
|---|---|---|---|---|
| 1w | +0.118% | −0.37 | +1.61 | [−0.010%, +0.258%] |
| **4w** | **+0.650%** | +1.52 | **+2.52** | **[+0.141%, +1.172%]** |
| **8w** | **+1.038%** | +1.97 ← archived | **+2.21** | **[+0.124%, +1.993%]** |
| 13w | +1.355% | +1.91 ← archived | +1.84 | [−0.023%, +2.835%] |

Sign stable, monotone increasing in horizon, bootstrap CI excludes zero at 4w and 8w.

### 2b "Warns" — Low-Trend × [High-Consistency vs Low-Consistency]

| horizon | effect | naive pooled t | **corrected t** | bootstrap 95% CI |
|---|---|---|---|---|
| 1w | +0.033% | +1.49 | +0.48 | [−0.098%, +0.162%] |
| 4w | +0.129% | +2.25 ← archived | +0.57 | [−0.273%, +0.544%] |
| 8w | −0.063% | +2.03 ← archived | −0.17 | [−0.761%, +0.609%] |
| 13w | −0.236% | +2.07 ← archived | −0.46 | [−1.190%, +0.696%] |

**Read the effect column, not the t column.** 2b's economic effect is ±0.03–0.24% and changes sign
across horizons. 2a's runs +0.12% → +1.36%, consistently signed and monotone. 2b was never a real
effect; a bad standard error made a tiny, sign-unstable difference look significant.

### 2c "Delays" and 2d "Accelerates-exits"
Both remain rejected, and the correction does not rescue either. 2c's lead/lag cross-correlation is
flat at −0.17 to −0.18 across lags −4…+4 (no asymmetry, as originally found). 2d corrects from a naive
t=+0.79 to t=+1.11 on 453 dates, bootstrap CI [−0.213%, +0.756%] — still nothing.

## 3. Lockbox — 53 weeks Paper B truncated away and never saw

Paper B cut its sample at `LOCK = 2025-07-11`. PANEL-A runs to 2026-07-10. Those 53 weeks are genuine
untouched out-of-sample data, and they were simply never used.

| role | 4w | 8w | 13w | direction vs discovery |
|---|---|---|---|---|
| **2a Confirms** | +0.613% (t=1.34) | +1.743% (t=1.49) | +2.862% (t=1.34) | **same sign, same monotone shape, larger magnitude** |
| **2b Warns** | −0.931% (t=−1.65) | −1.154% (t=−1.40) | −1.602% (t=−1.42) | **sign-flipped against the archived positive claim** |

Pre-registered power check (G10-L04), run before reading the t-statistics:

| horizon | discovery effect | lockbox n | lockbox MDE | adequately powered? |
|---|---|---|---|---|
| 1w | +0.118% | 52 | 0.308% | no |
| 4w | +0.650% | 49 | 0.900% | no |
| 8w | +1.038% | 45 | 2.297% | no |
| 13w | +1.355% | 40 | 4.201% | no |

**The lockbox cannot confirm 2a** — its minimum detectable effect is 1.4–3.1× the effect being looked
for at every horizon. What it *can* do is check direction, and there 2a replicates cleanly while 2b
reverses.

A note on how badly the pooled statistic misleads: on the same lockbox data the naive design reports
2b at t = −2.75 / −2.36 / −3.08. Used as archived, it would now "significantly confirm" the exact
opposite of what Paper B concluded. The defective estimator manufactures significance in whichever
direction the sample happens to lean.

## 4. Multiplicity — and the honest consequence for 2a

The charter pre-registered a Benjamini-Yekutieli correction over the declared test family. Nine
significance tests were run (2 roles × 4 horizons + the exit test). **Nothing clears it, including 2a**
(2a_4w p=0.0119; BY rank-1 threshold p ≤ 0.00196).

This is not a formality to argue around after the fact. Under the rule written before the run, 2a is
**UNRESOLVED**, not promoted. Recording it that way is the whole point of pre-registering.

For completeness, and without changing the verdict: 2a fails BY under every multiplicity accounting
tried, including the more generous m=4 "one test per pre-registered role" version (threshold 0.006 vs
p=0.0119). It clears plain BH at m=4 (threshold 0.0125), and nothing else.

**What would settle it.** At the observed effect size, reaching the BY threshold needs |t| ≥ 3.10,
i.e. n = 1,487 dates against 985 available — **502 more weeks, 9.7 more years.** Waiting is not a
route. The only way to resolve this on existing data is a more efficient estimator: the current design
compares extreme terciles and discards the middle third of the cross-section every week. A full
cross-sectional specification would use all of it. That is a legitimate design improvement rather than
a search for a friendlier answer, but it is a **new** test and must be pre-registered as one.

## 5. Findings

**G10-F01 — AEP Paper B Sub-study 2b's CONFIRMED verdict does not survive date-clustered inference,
and reverses out of sample.** Corrected t = +0.57 at best against an archived +2.25, effect size
±0.03–0.24% with unstable sign, and all four lockbox horizons negative. **Retired.**

**G10-F02 — Sub-study 2a is the only coherent role of the four, and remains unresolved.** Corrected
t = +2.52 at 4w (archived reading: a near-miss at +1.52), monotone +0.12% → +1.36% across horizons,
bootstrap CI excluding zero at two horizons, direction and shape replicated on 53 unseen weeks. It
fails the pre-registered multiplicity correction and cannot be settled by waiting. **Unresolved —
strongest surviving candidate, not an established effect.**

**G10-F03 — the pooled stock-week standard error is an active defect class in this repository, not a
one-off.** It produced a false positive (2b), masked a real candidate (2a), and on lockbox data would
have produced a confident false positive in the opposite direction. Every Gen-10 experiment routes
inference through `src/research/gen10/inference.py`, which makes per-date collapsing structural. T0-02
sweeps the rest of the archive for the same defect.

## 6. Errata required against the permanent record

1. **`results/AEP_PAPER_B/`** — Sub-study 2b's CONFIRMED verdict is withdrawn; 2a's near-miss framing
   is superseded.
2. **`archive/11_registries/FINDINGS_REGISTRY.csv`, finding #42** ("consistency_mom_26w's conditional
   role doesn't cleanly resolve") — the *statement* survives, but its evidence base is now inverted:
   it is unresolved because 2a cannot clear multiplicity, not because no role confirmed while another
   nearly did.
3. **`AEP_PROTOTYPE_REGISTRY.md`, Prototype 2** (Conditional Momentum Confirmation) — MODIFIED verdict
   re-derived: no role is confirmed; one role (Confirms) is an unresolved candidate.
4. **`results/MASTER_HYPOTHESIS_AND_RESULTS_LEDGER_2026_07_28.md` §8c** — the Sub-study 2a/2b rows.
5. **`Northstar_Remediation_Priority_Plan.md` §2.5** — the item's premise ("2b confirmed cleanly, so
   why did 2a nearly fail?") is void.

## 7. Consequences for the rest of Tier 1

- Plan item **2.5's run plan is void**. Its steps 1 (power calculation on 2a) and 2 (recalibrate 2a's
  threshold because 2b passed cleanly) both follow from the inverted premise. Step 3 (condition on
  trend state per M-05) is moot — test 2a is *already* trend-conditional by construction, comparing
  consistency terciles **within** the High-Trend tercile, which is a plausible reason it is the role
  that holds up.
- Task #5 (`2.5'`: take 2a to the economic gate) is **not** unblocked. Under the pre-registered rule
  2a is unresolved, and running a four-stage economic gate on an unresolved statistical effect would
  invert the programme's own evidence ladder. It is re-scoped to: pre-register and run the
  full-cross-section estimator first; gate only if that resolves.

## 8. Threats to validity

- The Newey-West bandwidth uses a floor of h−1 plus the standard automatic rule. A longer bandwidth
  widens SEs slightly; it does not close a gap between t=+2.25 and t=+0.57.
- The block bootstrap uses an expected block length of max(h, n^(1/3)). Longer blocks widen intervals
  further, which if anything strengthens the retirement of 2b.
- Tercile boundaries, horizons and the lockbox date are inherited unchanged from the original so that
  inference is the single varying factor. A different tercile cut is untested here.
- The lockbox is 53 weeks in one market environment. Its value is directional replication, not
  confirmation, and it is reported that way.
- `min_per_side=5` names per date is imposed for stability; the original had no such filter. It
  removes a handful of thin early dates and does not drive any verdict.
