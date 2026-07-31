> ## ⚠ CORRECTION — date-coverage confound (2026-07-31, Gen-10 T1-11)
>
> **Each tier's Sharpe was measured on its own date set.** `backtest` computes
> `r = s_net[pre].dropna()` per config x tier, and the tiers do not cover the same weeks:
>
> | universe | n_weeks |
> |---|---|
> | ALL / FNO_LARGE / SMALL_ADV_Q1 | 1,070 |
> | **NON_FNO_TAIL** | **712** |
>
> The NON_FNO_TAIL book only exists from 2010 — the panel's cross-section is too thin before then for
> a non-F&O tail to clear a 30-name floor. The excluded 2005–13 weeks are systematically worse
> (ALL tier: Sharpe **+0.58** on excluded weeks vs **+1.01** on the common window), so a tier measured
> only on the later window receives a free ~+0.43 Sharpe.
>
> **SMALL_ADV_Q1's +0.222 lead is like-for-like and stands. NON_FNO_TAIL's +0.296 lead does not.**
> On a common date set the lead halves to +0.207 and becomes fragile (bootstrap CI includes zero),
> while SMALL_ADV_Q1's rises to +0.496 (t = 3.51). **The ordering reverses.**
>
> The liquidity story is not damaged — it is strengthened and **relocated**: the edge sits at the
> small/illiquid extreme of a continuous gradient, not at the discrete F&O boundary. G9-01's gradient
> (Spearman −0.818) is unaffected, since its deciles all exist every week.
>
> **Recommended fix:** re-run `g8_07_capital_scale_sweep.py` with a common-date restriction across all
> four tiers and all three configs, net of cost. Evidence: `results/gen10/T1-11/`.

---

# G8-07 / G8-07B — Capital Scale × Universe Tier: Findings

```
Version:            v1.0
Status:             Frozen
Freeze Date:        2026-07-26
Owner:              Aryak
Depends On:         results/gen8/G8-08/CONFIG4_RECERTIFICATION_2026_07_26.md (the benchmark),
                    src/pnl/indian_cost_model.py, results/ARP_DELIVERY/ (the precedent)
Related Papers:     Gen-8, task C
```

**Outcome: a coherent, economically large LEAD — not a validated finding.** Smaller universes at
smaller capital beat the certified book by more than Gen-5's economic bar, consistently across every
strategy tested. It does not reach statistical significance, and one specific data limitation blocks
resolution.

Artifacts: `g8_07_capital_sweep.csv` (96 cells), `g8_07_data.json`, `g8_07b_stress.json`.
Scripts: `scripts/gen8/g8_07_capital_scale_sweep.py`, `g8_07b_smallcap_stress.py`.

---

## 1. Correctness gate — passed before any new number was reported

Reproducing the certified Config-4 at ₹100cr / ALL universe: **0.81045** against the certified
**0.8105**. A new implementation compared against old numbers is not evidence; this one reproduces.

## 2. The result

Mean Sharpe by universe tier, averaged across capital levels (pre-lockbox, real cost model):

| config | ALL | FNO_LARGE | **NON_FNO_TAIL** | **SMALL_ADV_Q1** |
|---|---|---|---|---|
| config4_secbal40_short | 0.836 | 0.621 | **0.967** | 0.919 |
| longonly_Q5_bands | 0.688 | 0.562 | **1.107** | 0.981 |
| longonly_secbal40 | 0.627 | 0.511 | **0.967** | 0.919 |

| Tier vs ALL | per-config deltas | mean | configs won |
|---|---|---|---|
| FNO_LARGE (large caps) | −0.215, −0.127, −0.116 | **−0.153** | 0 / 3 |
| **NON_FNO_TAIL** | +0.131, +0.418, +0.340 | **+0.296** | **3 / 3** |
| **SMALL_ADV_Q1** | +0.082, +0.292, +0.291 | **+0.222** | **3 / 3** |

**The ordering is monotone in size and consistent in every configuration: smaller is better, larger
is worse.** This is not a lucky maximum from a search — it is a systematic main effect, and the
large-cap tier underperforms by almost exactly as much as the small-cap tier outperforms.

**Capital sensitivity is mild and gracefully degrading**, matching ARP's Delivery finding. Example
(`longonly_secbal40`, NON_FNO_TAIL): Sharpe 0.989 at ₹1cr → 0.982 at ₹10cr → 0.965 at ₹50cr → 0.899
at ₹500cr. The book does not fall off a cliff; it erodes.

**Four combinations beat the certified reference (0.8105) by more than Gen-5's +0.15 bar.**

## 3. Three adversarial attacks (G8-07B)

### Attack 1 — Survivorship. Partially survived, with a caveat that matters.

| config × tier | full universe | survivors only | inflation | 2014+ only |
|---|---|---|---|---|
| longonly_Q5 × NON_FNO_TAIL | 1.139 | 1.243 | +0.104 | **1.360** |
| longonly_Q5 × SMALL_ADV_Q1 | 1.020 | 0.911 | **−0.109** | **1.586** |
| config4 × NON_FNO_TAIL | 0.989 | 1.180 | **+0.191** | 1.306 |
| config4 × ALL (reference) | 0.875 | 1.007 | +0.132 | 1.397 |

The reported figures are the **full-universe** ones, i.e. already survivorship-adjusted to the extent
the panel's 110 delisted names allow. `config4 × NON_FNO_TAIL` is *more* survivorship-sensitive than
the ALL tier (+0.191 vs +0.132), which is the expected direction and a real caution. The small-cap
tier is not systematically worse, and one cell is *negatively* sensitive.

**The binding limitation is not what the panel contains but what it lacks.** The panel manifest states
plainly: *"Archive holds today's ~591 tickers + 91 delisted … 2005-2013 cross-section is ~120-190
names and tilted toward survivors. Upgrade path: full NSE bhavcopy history acquisition."* Roughly 110
delisted names over 21 years is far fewer than actually delisted, and the missing ones concentrate in
exactly this tail. **This result cannot be cleared until delisted coverage is complete.**

The 2014+ figures are *higher*, not lower — which argues against a pre-2014 survivorship artifact, but
is confounded with the 2014–2025 Indian small-cap bull market and cannot be read as robustness.

### Attack 2 — Multiplicity. My first test was mis-specified; disclosed and corrected.

The initial null assumed **96 independent searches** and returned p = 1.00 ("does not survive"). That
null is wrong: the 96 cells are 3 configs × 4 tiers × 8 capital levels, and Sharpe barely moves with
capital, so the cells are nearly perfectly correlated — nothing close to 96 independent bets. Testing
the *maximum* of a correlated family against an independent-max null over-corrects by roughly two
orders of magnitude.

**Corrected test — the tier main effect rather than the selected maximum:** observed
NON_FNO_TAIL − ALL = **+0.296**, null SD **0.207**, i.e. **≈1.4σ, p ≈ 0.15**.

**Honest reading: directionally systematic (3/3 configs, monotone across tiers), economically large,
and not statistically significant.** Twenty-one years of one market's weekly data is not enough to
resolve a Sharpe difference of this size — the same power wall Gen-7 and Gen-8 keep hitting.

### Attack 3 — Tradeability. This is the real operating constraint.

Median participation as % of ADV:

| tier | ₹0.1cr | ₹1cr | ₹10cr | ₹50cr |
|---|---|---|---|---|
| NON_FNO_TAIL | 0.03% | 0.31% | 3.07% (OK) | 15.4% (**strained**) |
| SMALL_ADV_Q1 | 0.13% | 1.26% | 12.6% (**strained**) | 62.9% (**untradeable**) |

**The small-cap edge is real capital-constrained, not merely capital-preferred.** It is comfortably
tradeable to about **₹10cr** in the non-F&O tail and about **₹1–5cr** in the bottom ADV quintile.
Above that the backtest holds positions an actual order could not fill, and the reported Sharpe
becomes fictional regardless of its statistical status.

## 4. Findings

**G8-F17 — the user's hypothesis is directionally confirmed: momentum works better in smaller names,
and the effect is systematic, not selected.** Non-F&O tail beats the full universe by +0.296 mean
Sharpe and the bottom ADV quintile by +0.222, in 3 of 3 configurations, while the large-cap F&O tier
*underperforms* by −0.153. The monotone ordering across four tiers is the strongest part of the
evidence.

**G8-F18 — and it is a lead, not a finding, for two identified reasons.** (a) At ≈1.4σ it does not
clear statistical significance on 21 years of data. (b) The panel's delisted coverage (~110 names) is
acknowledged incomplete precisely in the small-cap tail where the effect lives, so the residual
survivorship risk is unquantified rather than small. **Neither reason is unfixable**, and the second
has a stated upgrade path.

**G8-F19 — capacity, not alpha, is the binding constraint on the small-cap tier.** The strategy is
tradeable to ~₹10cr (non-F&O) or ~₹1–5cr (micro), and untradeable at institutional scale. This is the
same structural fact ARP found for Delivery — whose net Sharpe also peaked at ₹5–10cr — reached
independently by a different route. **Two of this programme's three most promising leads now point at
the same capital range**, which is itself the most actionable pattern in the Gen-8 results.

## 5. What would resolve it

1. **Complete the delisted-name backfill** from the full NSE bhavcopy history (the panel manifest's own
   stated upgrade path, and the archive is already on disk — `data/raw/fo_bhav/` and
   `data/raw/delisted_bhav/`). This is the single highest-value data task remaining and it removes the
   unquantified risk rather than bounding it.
2. **Pre-register a single tier × capital combination** and test it out-of-sample. The lockbox for the
   frozen book is spent, but the tier hypothesis has never been tested on held-out data, so a fresh
   holdout is legitimate here in a way it is not for Gen-7.
3. **Model impact properly at 3–15% ADV participation**, where the square-root model is least reliable.

## 6. Threats to validity

- **Universe tiers were defined by me, after seeing Gen-8's earlier results.** The tier definitions
  (F&O eligibility, ADV quintile) are standard and pre-specified in the script, but this was not a
  pre-registered contract — it is exploratory by construction and is labelled as such.
- **Pre-lockbox, in-sample.** No out-of-sample test was run.
- **Costs use the repo's own model**, whose square-root impact term is least trustworthy exactly where
  this result lives.
- **The short leg is F&O-only by construction**, so `config4` in the NON_FNO_TAIL tier is long-tail /
  short-large — a structurally different book from the certified one, not merely a filtered version.
