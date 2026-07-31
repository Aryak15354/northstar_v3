# Feasibility Review — Northstar Remediation & Re-Discovery Priority Plan (v2, 2026-07-30)

**Reviewed:** 2026-07-31
**Method:** every Tier-1 item traced to its source finding, its data, and its script. Two items
(2.5, 2.6) were re-run rather than read, because their verdicts turned on statistics the source
documents did not report.

---

## 0. Verdict

**The plan is directionally right and structurally sound, and it is not yet safe to execute.**

Its central thesis — that the ledger's "RESEARCH_SIGNAL / INCONCLUSIVE / near-miss" bucket was never
put through the Gen-5 economic gate, and that this is where the unexploited value is — is correct and
well-argued. Its taxonomy (four fates, three tiers), its insistence on pre-registration, and its
explicit "retired" list are all good discipline.

But four of its eight Tier-1 items have problems that would waste the run if executed as written:

| Item | Problem | Severity |
|---|---|---|
| **2.5** AEP Paper B 2a/2b | The two results are **reversed** under correct standard errors. Re-ran it: the "clean confirmation" (2b) is noise (t=0.17–0.22, sign flips); the "near-miss" (2a) is the real effect (t=2.07 @4w). The plan's entire framing of this item is backwards. | **Fatal as written** |
| **2.6** AEP Paper C Q3 | Not a promotable finding. Re-ran it: Sharpe delta +0.035, **t = 0.50**. And the rule is a crash-de-gearing rule wearing a liquidity costume — de-gearing *only* in CRASH scores 0.816 vs the full rule's 0.727. This is Gen-5 F11 / G5-05A, already TERMINATED_BY_GATE. | **Fatal as written** |
| **2.3** Universe-rule fix | Prescribes the opposite of what its own source says. G8-12 concluded the universe rule is **not a bug** — it is the strategy's own stop-loss — and that the remaining task is execution realism, not a rule rewrite + panel rebuild. | **Fatal as written** |
| **2.1 / 2.2** Delivery | Feasible, but bounded by a data limit the plan never mentions: **delivery data is 2020+ only, 320–339 weeks.** 2.2's regime cells fall below MSRP's own MIN_N=30. 2.1's pre-registered success criterion is arithmetically unreachable on that sample, for the same reason G8-09 was unresolvable. | **Needs redesign, not abandonment** |

The remaining four Tier-1 items (2.4, 2.7, 2.8) survive review with amendments. Section 6's two
"unresolvable" gaps are both fully resolvable and I resolved them below — with the reassuring answer
that nothing promising was hiding there.

**Bottom line: fix 2.3/2.5/2.6, rescope 2.1/2.2, add the cross-cutting inference audit in §2, and the
plan is good. Ship it in the corrected order in §7.**

---

## 1. Infrastructure and data inventory (what actually exists)

Verified present and runnable. This part of the plan's optimism is justified.

| Need | Status | Location |
|---|---|---|
| DS-battery harness | ✅ Complete, all 28 IDs pre-registered in code | `scripts/gen23/deepsearch.py` |
| Gen-5 economic gate (oracle ceiling → realizable-with-CI) | ✅ | `scripts/gen5/g5_paper2_engine.py`, `g5_02_realizable_ceiling.py` |
| Capacity ladder + real cost model | ✅ | `scripts/arp/delivery_capacity_recovery.py`, `src/pnl/indian_cost_model.py` |
| AEP Paper B/C/D harnesses | ✅ | `scripts/aep/paper_{b,c,d}_*.py` |
| MSRP Memory-pillar methodology | ✅ | `scripts/msrp/m0*.py` |
| Config-4 reconstruction | ✅ | `scripts/gen4/reconstruct_config4.py` |
| Regime labels (5-state, PIT) | ✅ | `build_regimes()` in `run_g02_regime.py` |
| PANEL-A (price, 2005–2026) | ✅ 317,199 rows, 614 tickers, 1,123 weeks | `data/kaggle_upload/panel_a_weekly.parquet` |
| Enriched panel (603 cols, 2005–2026) | ✅ 500,976 rows | `tmp/kaggle_uploads/panel_enriched/` |
| Delisted price history | ✅ 327 names, 2000–2024-07 | `data/processed/delisted_prices_merged.parquet` |
| Cross-asset carriers | ✅ 33 symbols | `.../cross_asset_prices_daily.parquet` |

### The one data fact that reshapes Tier 1

```
delivery_pct       : 146,730 rows | 2020-01-03 → 2026-06-26 | 339 weeks | 539 tickers
delivery_pct_z52   : 136,488 rows | 2020-05-15 → 2026-06-26 | 320 weeks
```

**Every Delivery-dependent item in the plan — 2.1, 2.2, and the entire "highest priority" DS cluster in
2.4 — rests on ~6.2 years of one market era.** The manifest states it plainly:
`"delivery/participant/index are 2020+"`. The plan cites Delivery's headline stats (IC 0.0318, t=8.02,
capacity ladder to ₹500cr) without ever noting they are all measured on this window. G8-09 did note it,
and it is why G8-09 came out UNRESOLVED.

Also material: **`^TNX` (US 10Y) and `DX-Y.NYB` (DXY) start 2018-01-02** — only 2,139 daily obs (~420
weeks), against 1,070 weeks for crude/USDINR. The plan's suggested Gen-7 carrier set names US 10Y as a
headline channel; it carries 40% of the history the others do.

---

## 2. The cross-cutting defect the plan does not see

This is the most important thing in this review, and it is a *class* of error, not a single item.

**Several AEP-era results compute t-statistics by pooling stock-weeks as if independent.** They are not
— forward returns over h weeks overlap, and stocks within a week share a market factor. The correct
statistic is on the per-date difference series with Newey-West/date-clustered SEs.

The repo already knows this. `G8-10 §4.2` demands date-clustered SEs by name. `G9-02 §1` documents
catching exactly this error in its own v1 and discarding the result. But **AEP Paper B shipped with it**,
and its conclusion is in the permanent findings registry.

I re-ran Paper B Sub-study 2 both ways. The naive column reproduces the archived numbers exactly, which
confirms the reproduction is faithful:

```
                 pooled stock-weeks        date-clustered (Newey-West, lag=h)
                 n≈62,000                  n_dates≈1,030
2a CONFIRMS   1w   t = -0.37                diff +0.105%   t = +1.50
              4w   t = +1.52                diff +0.510%   t = +2.07
              8w   t = +1.97  ← archived    diff +0.937%   t = +1.91
             13w   t = +1.91  ← archived    diff +1.188%   t = +1.49

2b WARNS      1w   t = +1.49                diff +0.016%   t = +0.22
              4w   t = +2.25  ← archived    diff +0.040%   t = +0.17
              8w   t = +2.03  ← archived    diff -0.212%   t = -0.48
             13w   t = +2.07  ← archived    diff -0.298%   t = -0.47
```

**Read the effect-size column, not just the t-column.** 2b's economic effect is ±0.02–0.30% and changes
sign across horizons — it is noise that a bad SE made look significant. 2a's is +0.11% → +1.19%,
monotonically increasing with horizon, consistently signed — the shape a real conditional effect has.

**Consequences:**
- AEP Paper B Sub-study 2b's **CONFIRMED** verdict does not survive. Permanent finding #42 and
  Prototype 2's MODIFIED status both need re-derivation.
- The plan's 2.5 is built on the premise "2b passed cleanly, so why did its sibling 2a nearly fail?"
  That premise is false, and every step of its run plan follows from it.

**Recommended addition — Tier 0, do before anything else (½ day):**
Audit every t-statistic in AEP Papers B/C/D and the Gen-2/3 DS battery for pooled-stock-week SEs.
Recompute on per-date series with NW SEs. This is mechanical, cheap, and it changes which items in
Tier 1 are worth running at all. Two of eight already flipped.

---

## 3. Tier-1 items, one by one

### 2.1 Delivery × frozen book — portfolio integration
**Feasible: YES. As pre-registered: NO.** Three fixes needed.

The plan's core insight is right and confirmed by the source. G8-09 §7 says explicitly: *"No claim
about other portfolio constructions. A book built around Delivery — rather than one that adds it to a
momentum book — was not tested."* Sleeve-level ≠ overlay. Good catch.

**Fix 1 — the Sharpe numbers in step 1 are not comparable.** The plan instructs Sleeve A = Config-4 at
recertified Sharpe **0.8105/0.8471** and Sleeve B = Delivery at **0.767**, then asks whether the blend
beats momentum alone. But 0.8471 is a *full-history 2005–2026* number and Delivery only exists 2020+.
G8-09 measured the same book over the matched delivery era at **Sharpe 1.44**. Comparing 0.85 against
a blend built on a 1.44-era sleeve manufactures an improvement out of nothing. **Every number in this
test must come from the matched 2020–2026 window.**

**Fix 2 — the pre-registered criterion in step 5 is unreachable, and this is knowable in advance.**
On 288–320 weeks, SE(annualised Sharpe) ≈ 0.42–0.48. G8-09 computed the minimum detectable unpaired
Sharpe difference at **1.19 against a 0.15 bar — eight times the bar**, and correctly switched to a
paired design. The plan's step 5 ("net Sharpe must exceed frozen-momentum-alone by a CI excluding
zero") is the unpaired design. **Run it as written and you will reproduce G8-09's UNRESOLVED and learn
nothing new.**

*What to pre-register instead:* the two-sleeve decision does not actually require a significance test on
the blend. It requires (a) Sleeve B is a validated standalone alpha — it is, ARP certified it across ten
adversarial tests; (b) the correlation is low — it is, 0.14; (c) a sizing rule robust to Sleeve B's own
Sharpe CI. So pre-register **a sizing question, not a significance question**: *"what Sleeve-B weight
maximises blended Sharpe when Sleeve B's Sharpe is set to the lower bound of its 288-week CI, and does
that weight stay positive across the whole capacity ladder?"* That is answerable on this data and it is
the question that actually gates deployment. Report the blend-vs-momentum comparison alongside as
descriptive, exactly as G8-09 did with its Sharpe column.

**Fix 3 — step 3's name-collision check is right and should be step 1.** `ADD_nonfno_tail` is 117 names
vs CONTROL's ~96, so ~21 net new names. If the sleeves are built independently at full size the overlap
will be much larger than that, and capacity double-counting is real. Run this first — it is cheap and it
determines whether the rest of the test is even coherent.

### 2.2 Delivery regime dependency
**Feasible: NO, as specified. Feasible in a reduced form.**

Regime week counts, computed on the actual delivery window using the repo's own PIT `build_regimes`:

```
                full history    delivery_pct era   delivery_z52 era
NORMAL_UP            492              153               145
STRESS               224               70                68
STRONG_UP            151               65                65
CRASH                188               38                29   ← below MIN_N
RECOVERY              68               15                15   ← far below MIN_N
```

`scripts/msrp/m02_regime_dependent_memory.py` sets `MIN_N = 30`. **CRASH (29) and RECOVERY (15) fail
that gate in the delivery era.** The z52 construction — the one G2-E03 actually uses — misses the
COVID crash entirely; it starts 2020-05-15, after the bottom.

Worse, MSRP has already been burned here: its own permanent methodological finding reads *"Fixed
effect-size band insufficient at small regime samples — M-02A initially falsely flagged all 6
primitives regime-locked."* Running M-02 on 15-week RECOVERY cells is that failure mode by construction.

*What to do instead:* collapse to a **two-state test** (NORMAL_UP+STRONG_UP = 218 weeks vs
STRESS+CRASH+RECOVERY = 112 weeks), which clears MIN_N on both sides, and pre-register that CRASH and
RECOVERY are **not separately testable on current data** — state it as a limit up front rather than
reporting a 15-week cell and letting a reader treat it as evidence.

The plan's step 0 (check G8-03 before trusting the MSRP toolkit) is a genuinely good addition. For the
record: G8-03's flag is `high_52w_prox` newly non-independent, 9/12 features exceeding the rolling-window
threshold. Delivery is not one of the 12, but the *regime labels* come from a 13-week rolling market
return — so the plan's instinct to build the non-overlapping check in from the start (step 3) is right
and should be mandatory, not optional.

The plan's step 5 (test M-05's trend-conditional structure on Delivery) is good and unaffected.

### 2.3 Universe-inclusion rule fix + survivorship rebuild
**Feasible: the task as written should not be run.** Its own source says so.

The plan reads G8-12 as "a diagnosed bug — cheapest kind of win." G8-12 explicitly rejects that reading:

> *"The universe rules are the strategy's own rules. A book that only trades names above ₹20 with ₹1cr
> ADV would sell a name that falls through those thresholds. Dropping it is not the backtest hiding a
> loss — it is the backtest executing a stop that the strategy actually has."*

And on the fix:

> *"This is a property of the universe definition. Fixing it requires changing what the panel is, not
> adding to it."*

The plan's step 2 — "rewrite the rule so a name stays eligible through its delisting" — would build a
panel modelling a strategy **you would not trade**: one that holds names below ₹20 with no liquidity all
the way to zero. It would import a median −93.9% tail into a backtest of a book that has a stop.

Two further errors in this item:
- The bound is **already computed**: 0 to −2.29%/yr differential against the small-cap tier. The plan
  treats it as unknown.
- Step 4 pre-frames the expected answer ("a rebuild that shows the edge holding or strengthening is the
  expected/confirmatory outcome"). That is the opposite of the pre-registration discipline the plan
  correctly demands everywhere else — and it points the wrong way: G8-12's direction is *negative* on the
  small-cap tier, not conservative.

*Replace 2.3 with G8-12 §6's actual recommendation, which is tractable and needs no new data:*
> **2.3′ — Exit-realism modelling.** Re-run the small-cap / non-F&O tier charging a **gap-down exit**
> when a name leaves the universe on a price or liquidity failure, instead of a clean fill at the last
> in-universe price. Data is present: `delisted_prices_merged.parquet`, 327 names, with
> `quarantine_discontinuity` flags (56 names quarantined — exclude and say so). Sweep the exit
> assumption from clean-fill to −20%/−50% gap and report where G8-07's +0.222 to +0.296 Sharpe lead
> stops being a lead. That is one parameter sweep and it settles the question.

This also means 2.3 **loses its "do this first, it underlies everything" status**. C04/C05/C07 do not
need a rebuild; they need the exit assumption stated. It drops out of the critical path.

### 2.4 DS-battery retroactive economic gate
**Feasible: YES. The single best item in the plan.** Three amendments.

The premise is fully confirmed by reading `deepsearch.py`. The manifest for every one of the 28 IDs
carries `"lockbox_used": False`, the significance is BH-FDR at **q=0.10** (not 0.05), and `fast_ic()`
runs on the full sample. **No DS item has ever seen a discovery/OOS split.** That is precisely why
DS-F3-04 collapsed from t=−4.4 to t=−0.06 the moment one was applied, and it is the strongest argument
in the whole document.

**Amendment 1 — the "~15 signals" count is inflated by literal duplicates.** From the BUDGET list:
- `DS-F5-01` and `DS-U-04` are **the same spec**: `rel_deliv_sector`, both `type="signal"`. Identical
  code path, identical t=4.93. Not two signals measured twice — one signal registered twice.
- `DS-F4-01` and `DS-U-03` are **the same spec**: `pa_mom_smooth`, both t=3.06.
- `DS-U-02` (`delivery_pct_4w_avg`) is G2-E03b, already promoted.
- `DS-U-01` (`mom_60d_cs_z`) is MOM60, already in the ledger separately.

So the delivery cluster's nine IDs cover roughly six distinct constructs, and the momentum-quality
cluster's five cover three. Dedupe before Stage 1 or you will spend the budget twice on the same test —
and note that the duplication also means **the BH-FDR denominator of 28 was wrong**; correlated
duplicates inflate the apparent survivor count.

**Amendment 2 — the delivery cluster inherits the 2020+ limit.** Its Stage-4 capacity work will be run
on the same 320 weeks as 2.1. Fine, but pre-register it as a bounded result.

**Amendment 3 — the plan's caution on DS-F2-03 is correct and should be stronger.** t=−8.91 on
`res_mom_20d_cs_z × amihud_illiquidity_cs_z` is a reversal × illiquidity interaction. Gen-1 tested that
family **twice** and killed it both times: A04 (reversal, real IC, dies at 4187%/yr turnover) and
**A15/A19 (momentum × illiquidity, REJECT — "edge sits exactly where impact cost kills it")**. Run
Stage 4 first for this one, as the plan says — and pre-register that if its turnover profile matches
A04's, it is retired without running Stages 2–3.

The plan's sequencing advice (take the delivery cluster through all four stages first, then use what
you learn) is right. Keep it.

### 2.5 AEP Paper B Sub-study 2a
**Feasible: YES, and it is more valuable than the plan thinks — but the run plan is wrong end-to-end.**

Per §2, the two results are reversed. Therefore:
- **Step 1 (power calculation on 2a) is unnecessary.** At 4w, 2a is already t=2.07 with correct SEs on
  1,028 dates. It does not need more data; it needed a correct standard error.
- **Step 2 (threshold recalibration, on the theory that 2b's clean pass shows 2a is mis-specified) is
  built on a false premise.** 2b did not cleanly pass.
- **Step 3 (condition Confirms on trend state, per M-05) is good** — and note that test 2a *is already*
  a trend-conditional test (it compares High-Cons vs Low-Cons **within the High-Trend tercile**). So
  M-05's interaction structure is already present in the design, which is a reasonable explanation for
  why 2a is the one that holds up.

*Replace the run plan with:*
1. Re-run `paper_b_substudy2_conditional_activation.py` with date-clustered/NW SEs (one function
   change). Publish the corrected table for all four sub-studies 2a–2d.
2. Issue an erratum against AEP Paper B and permanent finding #42; re-derive Prototype 2's verdict.
3. Take 2a (4w and 8w horizons) into the Gen-5 economic gate as a genuine conditional-momentum
   candidate — Stage 2 ceiling, Stage 3 realizable-with-CI, Stage 4 net-of-cost. Effect size at 4w is
   +0.51% over 4 weeks between High-Cons and Low-Cons within High-Trend, which is economically
   material enough to be worth the gate.
4. Retire 2b.

This is now a **Tier-1 promotion candidate**, not a near-miss cleanup.

### 2.6 AEP Paper C Q3 (liquidity-persistence sizing)
**Feasible: YES to run, but the answer is already known and it is negative.** I ran it.

Reproducing `q3_sizing` exactly (100% exposure in NORMAL_UP/STRESS, 50% otherwise, 1,032 weeks):

```
fixed    Sharpe 0.6918   vol 0.2492   ann return 17.24%
scaled   Sharpe 0.7271   vol 0.1923   ann return 13.98%

Sharpe difference  +0.0353   Jobson-Korkie SE 0.0710   t = +0.50
```

**t = 0.50.** The archived writeup reports no statistical test at all — just two point Sharpes and the
phrase "the most economically material result in this sub-study." The plan then upgrades that to "a 5%
Sharpe improvement with a 23% vol reduction is not a marginal effect" and ranks it *"cheapest, fastest,
already-positive — worth doing before almost anything else in this document."* It is none of those
things. It is +0.5σ, and it costs **3.3 percentage points of annual return** to get there.

Three further problems, any one of which is disqualifying:

**(a) It is not a liquidity rule.** `PERSISTENT_REGIMES = {"NORMAL_UP", "STRESS"}` — the scaling is
driven by the market regime label, with M-02's liquidity-memory finding used only as *justification* for
which labels to pick. No liquidity-persistence measurement enters the sizing decision.

**(b) The entire effect is the CRASH de-gearing, and the rule is a worse crash rule than the obvious
one.** De-gearing in one regime at a time:

```
de-gear only in CRASH      Sharpe 0.8164   ← better than the full Q3 rule
de-gear only in RECOVERY   Sharpe 0.6940   ← ~nothing
de-gear only in STRONG_UP  Sharpe 0.5941   ← actively destructive
```

Q3 bundles a good crash rule with a bad STRONG_UP rule and reports the average as a discovery. And the
programme **already deploys a crash rule** — A20 / G-05, "KEEP (mandatory)."

**(c) It is Gen-5 F11 under another name.** "Regime-conditioned gross exposure timing beats static 1.0x"
is F11 / G5-05A, **TERMINATED_BY_GATE**, oracle ceiling +0.1554, realizable +0.1052 with a CI straddling
the gate. Q3's +0.035 is a third of the realizable estimate that already failed. The plan's own §5
retires this family as *"a capital-scale-independent skill failure... closed regardless of what capital
band you eventually deploy at"* — and then Tier 1 resurrects it under a different label.

**Also: it charges nothing for the de-gearing.** `weekly_ret` is gross `target_1w`; there is no turnover
cost for halving and restoring the book at every regime flip, and no cash yield credited on the
un-invested half. A cost-aware version is worse than what is shown.

*Recommendation:* **move 2.6 from Tier 1 to §5 (retired).** Log the t=0.50 and the regime decomposition
into the ledger so it stays closed. If any part is kept, it is only the observation that CRASH-only
de-gearing scores 0.816 — and that is A20, already deployed and already validated.

### 2.7 Gen-7 / CAIT redesign
**Feasible: YES, with the highest design cost of anything in the plan.** The plan is close but skips the
gate its own source put in front of it.

G8-10 §4 explicitly declines to run this until **three points are resolved in advance**, and says point
3 "should be settled before any code is written." The plan addresses one of them:

| G8-10's requirement | Plan's coverage |
|---|---|
| 1. Pooled panel (m=1) or per-stock tests? Power math assumes **pooling**; per-stock "destroys the gain immediately" | ❌ Not addressed. Steps 3's BH/BY framing implies per-test multiplicity, which is the design G8-10 rules out |
| 2. **Every SE must be date-clustered.** Effective n=12.2 is a variance argument, not a licence to treat 132×1,070 as independent | ❌ Not addressed |
| 3. Is stock-level transmission even the hypothesis? Gen-7 Lab 5 found effects hit **41/42 sector cells equally** — reads as market beta, not a channel. If it is pure beta, this detects something already understood | ⚠️ Partially. Step 2's channel-specific carrier pairing is a genuinely good answer in spirit, but it is never stated as a beta control |

*Amendments:*
- **Add a market-beta residualisation step.** Regress each stock's return on the market before testing
  transmission, and pre-register that a carrier hitting all receiver groups equally is scored as beta,
  not transmission. This is what actually discharges point 3, and step 2's channel design becomes the
  test of it rather than an assumption.
- **State the estimator explicitly:** pooled panel, one coefficient per carrier-lag, date-clustered SEs.
  Otherwise the power argument the whole redesign rests on does not apply.
- **Fix the carrier list for data availability.** `^TNX` and `DX-Y.NYB` begin 2018-01-02 (~420 weeks);
  crude (`CL=F`, 2000+), USDINR (2003+), copper/gold/steel-HRC vary. Weight the ~20–30 carrier budget
  toward the long-history symbols, and drop `USDCNH=X` (10 observations).
- Steps 3 (permutation resolution), 4 (pre-registered effect floor r≈0.11), 5 (a null here closes the
  question) and 6 (H-A2/3/4 become live again if a survivor appears) are all correct. Keep them.

### 2.8 AEP Paper D monthly near-miss
**Feasible: YES, cheap, and mostly resolvable without a re-run.**

Step 1's question is answerable now: **"RISING" does not mean the margin is widening over time.** It is
a pre-registered classification of the MI-vs-*resolution* curve shape (any resolution ≥3× weekly), from
`resolution_curve.json`'s `_summary.classification`, computed once on the full sample. So treat it with
exactly the skepticism the plan reserves for single point estimates — the plan's instinct is right, its
stated reason is not.

The stronger objection the plan misses: **monthly fails a multiplicity correction across the five
resolutions it was selected from.**

```
resolution   n_obs    MI       null 95th pct   significant
weekly       1070   0.00272      0.00583          no
biweekly      535   0.00709      0.01126          no
monthly       267   0.02577      0.02454         YES (margin +5%)
6week         178   0.00282      0.03739          no
quarterly      82   0.05921      0.09101          no
```

Monthly clears its own null by 5%. Five resolutions were tested; no correction was applied across them.
Bonferroni at m=5 requires roughly the 99th percentile of the null — monthly does not come close. And
the null band widens sharply as n falls (0.0058 → 0.0910), so monthly is simply the resolution where n
is still large enough for a tight null while aggregation lifts MI — a shape artifact, not an economic
cadence.

*Revised plan:* apply the multiplicity correction (30 minutes, no re-run). If it fails — it will —
retire monthly alongside the other four and record F17's weekly null as the settled answer across all
resolutions. Only if it somehow survives is the plan's step 2 (proper OOS split) worth the compute.
Step 3's demand for an economic story before believing it is good and should be kept as the standing bar.

---

## 4. Section 6 — resolved (both gaps close, nothing was hiding)

The plan flags these as things it "genuinely can't resolve." Both resolve from
`results/ARP_MASTER_ALPHA_REGISTRY.csv` directly.

**(a) The arithmetic discrepancy is in the ledger's prose, not the CSV.** The `bucket` column sums to
exactly 141:

```
Permanent Dead End                     70
N/A (not a rejection, ...)             35
Economic Law (see AEP_DISCOVERY_CENSUS) 29
Deployable Alpha                        3
Portfolio Component                     2
Execution Improvement                   2
                                      ---
                                      141
```

The ledger's summary sentence reports "46 N/A/descriptive" and lists "13 research-incomplete" and "4
flagged for review" — but those latter two are *different columns* (`rejection_cause == R13` and
`recover_flag == REVIEW`), overlapping the buckets rather than partitioning alongside them, and the "6
Gen-6" are already inside Permanent Dead End. **Nothing is missing; the prose double-counts. Fix the
ledger sentence.**

**(b) Both un-enumerated buckets, enumerated — and the plan already covers all of them.**

`recover_flag == REVIEW` (the "4 flagged for review"):

| ID | Status | Already in plan? |
|---|---|---|
| G4-GATE-02 | RESEARCH_SIGNAL, t=3.79 | ✅ Tier 2 (the plan correctly guessed this one) |
| RESMOM20 | INCONCLUSIVE, t=−5.97 | ✅ Tier 2 |
| A5_BORROW_CAPACITY | BLOCKED_DATA | ✅ Tier 3 |
| G5-08A_EXECUTION_ENGINE | BLOCKED_DATA | ✅ Tier 3 |

`rejection_cause == R13` (the "13 research-incomplete"): G2-A03, G2-A0c, **G2-B03b**, G2-D01a, G2-D02a,
G2-D02b, G3-T5, A5_BORROW_CAPACITY, G5-08A_EXECUTION_ENGINE, G5-08E, G5-08F, G5-09A, G5-09B.

**Twelve of thirteen are already in the plan.** The one genuine omission is **G2-B03b** (order-win
announcements → revenue visibility, INCONCLUSIVE, no t-stat recorded). `order_win_flag_30d`,
`order_win_count_90d_cs_z` and their cs-ranks exist in the enriched panel, so it is testable — but it
sits in the event-driven family where G2-B01n/B01p/B02a/B02b and Gen-1's A26 all failed cleanly. Add it
to Tier 3 with a one-line note, do not spend Tier-1 time on it.

**Section 6 can be deleted from the plan and replaced with this table.** Its worry — that something
promising was invisible — was reasonable and turns out to be unfounded.

---

## 5. Tier-2 items that resolve now (no experiment needed)

Three of the plan's Tier-2 "resolve this ambiguity before spending time" items are answerable from the
repo directly.

**G5-08B/C — the rename claim is TRUE; the plan's skepticism is wrong.** The plan doubts the "superseded
by renamed successors" note because risk-parity/covariance-shrinkage don't map onto slippage/execution-delay.
But `docs/GEN5_DECISION_LOG.md:509` records the audit correction verbatim: *"G5-08B and G5-08C were used
TWICE with different meanings."* The scripts that exist are `g5_08b_cost_attribution.py` and
`g5_08c_execution_drift.py` — i.e. the D01/D02 work. **The original Risk Parity / Shrinkage
registrations remain unrun.** So: G5-08A (confidence weighting), G5-08B (risk parity), G5-08C
(covariance shrinkage), G5-08D (no-trade regions) are all genuinely never-run, and the caveat resolves
in favour of running them. Note G5-08D (no-trade regions) is close to A21 trade-band hysteresis, already
KEEP — check for overlap before running that one.

**MOM60 vs ret_13w — same signal, ρ = 0.97. This is a real red flag.** Measured directly: mean per-date
Spearman between `mom_60d_cs_z` (enriched panel) and `ret_13w` (PANEL-A) over 316,122 overlapping rows
is **0.969** (median 0.974). They are the same construct. Yet the ledger carries three different
verdicts for it:

```
ret_13w   (Gen-1 LEDGER)      IC 0.0089   t = 1.17   NOISE
DS-U-01   (deepsearch)                    t = 2.91   RESEARCH_SIGNAL
MOM60     (exp_momentum_determinants)     t = 3.36   RESEARCH_SIGNAL
```

The plan is right that this needs reconciling and right that it is quick. The differences to diff are:
target (`target_weekly_return` 1w vs 4w sector-relative), universe (enriched 500,976 rows vs PANEL-A
317,199), and IC method. **But the finding is bigger than the plan frames it:** if three harnesses give
NOISE / SIGNAL / SIGNAL on a ρ=0.97-identical signal, that is a harness-comparability problem affecting
every cross-generation comparison in the ledger, not a curiosity about one momentum variant. Elevate to
Tier 1, alongside the §2 SE audit — they are the same kind of problem.

**amihud_13w + vol_52w + accruals_ratio blend (plan's added Tier-2 item).** Good idea, correctly
reasoned, all three series exist. One caution the plan misses: `vol_52w` is MSRP I-04A's *most redundant*
feature in its family (retains only 33.9% incremental MI), and amihud/vol are both in the volatility-
liquidity complex that I-03B found "redundant AND coherent." A blend of three signals from one coherent
family will not diversify the way a blend of three independent small signals would. Pair amihud with
G8-05's PCR instead — genuinely different mechanism — before pairing it with vol_52w.

---

## 6. What the plan gets right (do not change these)

- The four-fate taxonomy and the "verdict ≠ closed" framing. Correct and useful.
- **The core thesis of 2.4** — that the DS battery cleared a discovery bar and then nothing happened —
  is exactly right and is confirmed in the source code (`lockbox_used: False`, full-sample fast IC).
- **The sleeve-vs-overlay distinction in 2.1.** Confirmed verbatim by G8-09 §7.
- Pre-registering the kill criterion before every run.
- §5's retired list, which is well-reasoned. In particular the A15/A19-vs-Delivery discrimination
  ("sounding similar isn't the same as being the same mechanism") is a subtle and correct call.
- §7's working rhythm (pre-register in one sitting → unattended compute → short review sitting).
- The audit-added caution on DS-F2-03. Right instinct, and §3 above strengthens the case.

---

## 7. Corrected sequencing

**Tier 0 — inference integrity (½–1 day, do first; it re-ranks everything downstream)**
1. Recompute AEP Paper B 2a–2d with date-clustered SEs; issue the erratum. *(mostly done in this review
   — needs writing up into the archive.)*
2. Sweep AEP Papers C/D and the DS battery for the same pooled-stock-week SE pattern.
3. Reconcile the MOM60 / ret_13w / DS-U-01 harness discrepancy (ρ=0.97, three verdicts).

**Tier 1 — corrected**
4. **2.4, delivery cluster**, deduped (F5-01≡U-04, F4-01≡U-03), through Stages 1–4. Now the clear
   highest-value item. Stage 1 is the first OOS split these have ever seen.
5. **2.5′** — take the corrected 2a (t=2.07 @4w, +0.51% effect) into the Gen-5 economic gate as a
   promotion candidate. Retire 2b.
6. **2.1′ + 2.2′** together, on matched 2020–2026 windows, with the sizing-under-uncertainty
   pre-registration replacing the significance test, and 2.2 collapsed to two regime states.
7. **2.8′** — apply the m=5 multiplicity correction. Half an hour, likely closes the item.
8. **2.3′** — exit-realism sweep on the delisted panel. No longer blocking anything else.
9. **2.4, remaining clusters** (momentum-quality; then cross-factor with Stage 4 run first).
10. **2.7** — Gen-7 redesign, once G8-10's three points are written down as a contract.

**Moved out of Tier 1**
- **2.6 → retired.** t=0.50, it is the crash rule, and it is G5-05A which already failed its gate.
- **2.3 → 2.3′**, rescoped and de-prioritised (no longer the foundation item).

**Deleted**
- **Section 6** → replaced by §4 above. Nothing promising was hidden.

---

## 8. Honest limits of this review

- I re-ran two items (Paper B Sub-study 2; Paper C Q3) and reproduced their archived numbers exactly
  before correcting them, so the corrections rest on faithful reproductions. I did **not** re-run the
  DS battery, Gen-7, or the Gen-5 gate.
- The Newey-West correction in §2 uses the per-date mean difference series with lag = horizon. That is
  the standard treatment for overlap plus cross-sectional dependence, but it is one defensible choice
  among several; a two-way-clustered or block-bootstrap version could shift the numbers modestly. It
  would not close a gap between t=2.25 and t=0.17.
- The Jobson-Korkie SE in §3/2.6 assumes normal, i.i.d. weekly returns. Momentum-book returns are
  neither, and both violations widen the interval — so t=0.50 is if anything generous.
- Regime counts use the repo's own `build_regimes` on PANEL-A. A different regime definition would
  shift the cell sizes, but RECOVERY at 15 weeks has no plausible definition that reaches 30 inside a
  6-year window.
- I did not verify the Gen-7 permutation p-floor claim (G7-F03) or Gen-5's oracle ceilings independently.
