# T1-10 — Gen-7 CAIT Redesign: Pre-Registered Contract

```
Version:      v1.0
Status:       FROZEN BEFORE RESULTS
Written:      2026-07-31
Owner:        Aryak
Discharges:   results/gen8/G8-10_RECEIVER_UNIVERSE_FEASIBILITY.md s4 (three points that
              G8-10 required be resolved in advance) and s6 (the contract it asked for)
```

G8-10 ended with: *"Do not run it yet, and do not close the question. Write
`G8-11_STOCK_LEVEL_RECEIVER.md` as a pre-registered contract resolving §4's three points — in
particular deciding, before any test, whether detecting broad market-beta transmission would count as
an answer at all."* This is that contract. It is frozen before any result is computed.

---

## 1. The three points G8-10 required be settled

### Point 1 — pooled or per-stock?

**Resolved: POOLED, one coefficient per carrier-lag.**

G8-10's power calculation explicitly assumes pooling: *"the power calculation above assumes pooling
with date-clustered standard errors; per-stock testing would destroy the gain immediately."*
Per-stock testing would give m = 31 × 132 tests and multiply the multiplicity by two orders of
magnitude, discarding exactly the advantage the stock-level receiver was supposed to buy.

Estimator: for each carrier `c` and lag `L`, a single pooled coefficient from regressing
beta-residualised stock returns on the lagged carrier shock, across all receiver stocks and dates.

### Point 2 — inference under cross-sectional dependence

**Resolved: DATE-CLUSTERED, always.**

G8-10: *"Effective n of 12.2 is a variance argument, not a licence to treat 132 × 1,070 observations
as independent. Every SE must be date-clustered."* This is also Gen-10's standing law G10-L01, and
T0-01 showed what happens when it is ignored — a false positive that reversed out of sample.

Implementation: collapse to a per-date coefficient (Fama-MacBeth), then Newey-West over dates with a
bandwidth floor of the shock horizon. Reported alongside a stationary block bootstrap (G10-L03).

### Point 3 — would broad market-beta transmission count as an answer?

**Resolved: NO. It would not.**

This is the substantive point and G8-10 said it should be settled before any code is written.

Gen-7's Lab 5 (G7-F07) found that any detected association hit **41 of 42 sector cells roughly
equally**. An effect that reaches every receiver equally is not transmission through a named economic
channel — it is the Indian market moving with global risk appetite, which is already understood,
already priced, and not actionable as a cross-sectional signal. Detecting it with more power would be
detecting something the programme already knows.

Two consequences, both binding:

1. **Receivers are residualised against the market before testing.** Each stock's weekly return has
   its exposure to the equal-weight universe return removed. What remains is the idiosyncratic
   component, which is where a channel-specific effect would have to live.
2. **Channel specificity is tested, not assumed.** Every carrier is tested against BOTH its
   economically-motivated receiver group AND all other sectors. A carrier that moves both is scored
   as **beta, not transmission**, and does not count as a survivor regardless of significance.

**If the only thing found is a broad effect, the question is retired on scientific grounds rather
than power grounds** — which G8-10 identified as the cleaner ending.

## 2. Design

**Receivers.** Individual stocks in PANEL-A, weekly, beta-residualised against the equal-weight
universe return using a 104-week rolling beta. Grouped by sector for the channel test.

**Carriers.** A pre-registered, economically-motivated subset rather than the original exhaustive 310
pairs. G7-F06 showed cutting multiplicity from m = 310 to m = 31 raises power from 31% to 60% at
r = 0.11 with no new data. Carriers are weighted toward long history: `^TNX` and `DX-Y.NYB` begin
2018-01-02 (~420 weeks) against crude and USD/INR at 1,070, so short-history carriers are included
only where the channel is strong enough to justify the power cost. `USDCNH=X` (10 observations) is
excluded outright.

| carrier | channel | receiver group |
|---|---|---|
| `CL=F` crude | input cost / margin | Energy, Materials |
| `HG=F` copper | industrial demand | Materials, Industrials |
| `GC=F` gold | risk appetite / safe haven | Consumer Goods |
| `USDINR=X` | exporter revenue / importer cost | Information Technology |
| `^TNX` US 10Y | duration / discount rate | Real Estate |
| `DX-Y.NYB` DXY | EM flow | Information Technology, Materials |

**Lags.** 1, 2, 4 weeks. Multiplicity m = 6 carriers × 3 lags = **18**, declared in advance.

**Shock definition.** 4-week log return of the carrier, as-of Friday, matching Gen-7's construction.

**Effect-size floor.** r ≈ 0.11, per G7-F04 and G8-02's own framing. A properly-powered null at this
floor closes the question permanently.

**FDR.** Benjamini-Yekutieli across the 18 tests. BY rather than BH because carriers are correlated
(crude, copper and DXY all load on global risk). G7-F03 found the original permutation-based
correction had a p-floor an order of magnitude too coarse; this design uses analytic p-values from
date-clustered Newey-West statistics, which do not have a permutation floor at all.

## 3. Pre-registered decision rule

**SURVIVOR** requires all four:
1. |t| ≥ 2 on the channel receiver group under date-clustered Newey-West;
2. bootstrap 95% CI excludes zero;
3. BY-clean at m = 18;
4. **channel-specific** — the effect on the channel group must materially exceed the effect on
   non-channel sectors. Operationally: |t| on the channel group ≥ 2 **and** |t| on the complement
   < 2, or the two coefficients differ by more than their combined standard error.

**BETA, NOT TRANSMISSION** — significant on both the channel group and its complement. Does not
count as a survivor. Recorded separately.

**NULL** — no survivors at adequate power. Per §1 point 3 and G8-10 §6, **this retires the
cross-asset transmission question permanently.** It does not invite a fourth re-run.

## 4. What this design does not claim

- It does not test the original 310 pairs and cannot resurrect any of them individually.
- Beta-residualisation removes any genuine market-level transmission along with the beta confound.
  That is deliberate: §1 point 3 decided market-level effects do not count as an answer. A reader who
  disagrees with that decision should reject this design's scope, not its result.
- Power is bought by pooling. A carrier whose effect is real for a handful of stocks and absent for
  the rest of its sector group will be missed.
