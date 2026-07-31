# T1-10 — Gen-7 CAIT Redesign. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Contract:     docs/gen10_protocols/T1-10_CAIT_REDESIGN_CONTRACT.md (frozen before results)
Discharges:   G8-10 s6 ("write the contract"), G8-10 s4 points 1-3
Artifacts:    t1_10_data.json. Script: scripts/gen10/t1_10_cait_redesign.py
```

**Outcome: clean null at adequate power, with the beta confound removed by design. Cross-asset
transmission into Indian equities is retired.** This is the properly-powered negative that Gen-7 and
G8-02 could not produce — not another underpowered non-result.

---

## 1. What was different this time

| | Gen-7 / G8-02 | T1-10 |
|---|---|---|
| receivers | 1 aggregate / 42 sector cells | **491 stocks**, beta-residualised |
| identification | shock constant within date | **shock × per-stock rolling exposure** |
| multiplicity | 310 pairs, then 31 | **18 declared** (15 testable) |
| inference | permutation with a coarse p-floor | date-clustered NW + block bootstrap |
| beta confound | not addressed | **residualised out, and channel specificity tested** |

**The identification change is the one that mattered.** A first implementation regressed each sector
group's per-date mean residual return on the lagged shock. That looked like a stock-level design but
was not one: with the shock constant within a date, the stock dimension contributes nothing to
identification and the estimator collapses to a *sector-level* receiver — exactly the design G8-10
measured at 1.49 effective series and called "a false remedy… Gen-7's mistake in a milder form."

The corrected estimator interacts the shock with each stock's own rolling 104-week carrier exposure,
so the regressor varies across stocks within a date. That is what makes the 491-stock receiver
universe do any work, and it is the estimator G8-10's power argument assumes. Both were run; both are
null, and the corrected one produces effect sizes an order of magnitude smaller.

## 2. Results — 15 testable carrier-lag pairs

| carrier | lag | channel r | channel t | other r | other t | class |
|---|---|---|---|---|---|---|
| Crude oil | 1 / 2 / 4 | 0.006 / 0.011 / 0.010 | 0.47 / 1.86 / −1.66 | ~0.00 | 1.27 / 1.38 / −1.25 | null |
| Copper | 1 / 2 / 4 | 0.013 / 0.003 / 0.014 | 1.36 / −0.69 / 1.11 | ~0.00 | 0.37 / 0.18 / −0.35 | null |
| Gold | 1 / 2 / 4 | −0.007 / 0.000 / −0.002 | 0.61 / −0.47 / −0.12 | ~0.00 | 0.29 / −0.49 / −1.68 | null |
| USD/INR | 1 / 2 / 4 | 0.002 / −0.002 / −0.007 | 1.14 / −1.73 / −0.21 | ~0.00 | −0.22 / −1.83 / −0.07 | null |
| DXY | 1 / 2 / 4 | −0.004 / **−0.011** / −0.005 | −0.56 / **−2.51** / −1.16 | ~0.00 | 1.12 / −0.99 / −0.03 | 1 candidate |
| US 10Y | — | — | — | — | — | **not testable** |

- **BY-clean at m = 15: 0.**
- **Largest |r| on any channel group: 0.0138**, against the pre-registered floor of **r = 0.11**.
  Not one test reaches even an eighth of the effect size the design was built to detect.
- **DXY at lag 2** is nominally channel-specific (t = −2.51 on IT + Materials, t = −0.99 elsewhere)
  but fails BY and carries r = −0.011. It is recorded and it is not a survivor.
- **Zero tests classified BETA.** Nothing was significant on both the channel group and its
  complement — so the null is not being produced by residualisation eating a real broad effect.

**US 10Y could not be tested.** With 440 weeks of history, a 104-week rolling exposure requiring 52
minimum periods, plus the lag, it fell below the 100-date minimum. This is a data limitation, stated
rather than worked around, and it is why m dropped from 18 declared to 15 tested.

## 3. Why this is a real null and not another underpowered one

Gen-7's problem was never the answer, it was that the design could not have found an answer. G7-F02
put the detection threshold at |r| = 0.154 with all six candidates below it; G7-F04 put lockbox power
at 13%; G7-F08 said detecting r = 0.11 at 80% power needed ~34 years against 21 available.

This design does not have that problem, and the reason is visible in the numbers rather than asserted:
the largest effect anywhere is r = 0.0138. The question is no longer whether the design could see
r = 0.11 — nothing is remotely near it. With Fama-MacBeth over ~1,000 dates and genuine
cross-sectional identification, an effect of the pre-registered size would have been unmissable.

## 4. Findings

**G10-F29 — cross-asset transmission into Indian equity idiosyncratic returns is null at adequate
power, and the question is retired.** 15 channel-specific carrier-lag tests on a 491-stock
beta-residualised receiver universe, date-clustered inference, BY at m = 15: zero survivors, largest
|r| = 0.0138 against a pre-registered floor of 0.11, zero effects classified as beta. Per the frozen
contract §3 and G8-10 §6, this does not invite a fourth re-run.

**G10-F29b — [added 2026-07-31] the null is now complete.** T1-16 covered the one channel this
experiment could not test and retired its one surviving candidate. There is no uncovered carrier
channel and no outstanding candidate.

**G10-F30 — H-A2, H-A3 and H-A4 stay closed.** They were marked UNTESTABLE/UNCHANGED/WITHDRAWN only
because H-A1 was unresolved. H-A1 is now resolved negative, so they close with it rather than becoming
live again.

**G10-F31 — a stock-level receiver is only a stock-level receiver if the regressor varies within a
date.** Averaging beta-residualised returns within a sector group and regressing on a date-constant
shock reproduces the sector-level design under a stock-level label. The distinction is worth recording
because G8-10's power argument (12.2 effective independent series) is only available to the
interaction form, and a reader could implement the collapsed version believing it delivers the gain.

## 5. Consequences

- **Plan item 2.7 is complete.** Its design instincts were right — reduce multiplicity, pick
  economically-motivated carriers, fix the FDR resolution — and its one gap was that it never stated
  a beta control, which G8-10 said was the point that had to be settled first.
- **Gen-7 (CAIT), Paper A closes properly.** H-A1 moves from "unresolved, underpowered" to
  "tested at adequate power, not supported."
- **G8-10's request is discharged.** The contract it asked for exists and has been executed.

## 6. Threats to validity

- ~~**US 10Y untested**, and DXY tested on 440 weeks against the others' 1,067. The duration/discount-rate
  channel is therefore not covered by this null. That channel remains formally open, and closing it
  needs a longer rates history rather than a better design.~~
  **[CORRECTED 2026-07-31 by T1-16 — this diagnosis was wrong.]** `^TNX` yields **zero** usable dates at
  a 104w, 52w *or* 26w exposure window, so history length was never the binding constraint. The actual
  blocker is the receiver: **`Real Estate` has a median of 10 names per date and never reaches 15** in
  1,123 weeks, so a cross-sectional regression inside it could not run at any history length. Widening
  the receiver to Real Estate + Industrials makes it testable, and it is **null** (best |t| = 1.45, no
  complement separation). **The duration/rates channel is covered, not open.**
- **[Added by T1-16]** This experiment's one "channel-specific candidate" — DXY at lag 2, t = −2.51 —
  is a window artifact: it swings −3.07 → −0.80 → −0.51 across 104w/52w/26w exposure windows.
  **Retired**, which makes this null cleaner rather than weaker.
- **Beta-residualisation removes genuine market-level transmission along with the confound.** That was
  decided in contract §1 point 3 before any result — market-level effects were ruled not to count as
  an answer. A reader who rejects that decision should reject this design's scope, not its result.
- **Rolling exposures are estimated on 104 weeks with a 52-week minimum**, so early history is
  dropped and exposures are noisy for names with short listings. Noisy exposures attenuate the
  interaction toward zero, which biases toward the null — the direction that should be flagged given
  the verdict. Against that: the attenuation would have to be roughly eightfold to hide an r = 0.11.
- **Six carriers and three lags is a deliberate narrowing** from 310 pairs. A channel outside this set
  is untested, by design and per G7-F06's multiplicity finding.
