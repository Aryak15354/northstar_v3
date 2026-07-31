# T1-13 — Tier Sweep: Common Dates × 3 Configs × Net of Cost. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T1-11 (which raised it), results/gen8/G8-07, G8-11
Artifacts:    t1_13_data.json. Script: scripts/gen10/t1_13_tier_sweep_common_dates_net.py
```

**Outcome: T1-11's reversal holds net of cost, and is larger than T1-11 could see. G8-07's non-F&O
lead is almost entirely a date artifact (+0.299 → +0.042). And a third fact neither experiment was
looking for: the tier advantage does not exist in the certified production config at all — it is a
long-only phenomenon.**

---

## 1. Correctness gate

This re-uses G8-07's own `CONFIGS`, `apply_tier`, book rules and cost model verbatim; only the
evaluation index changes. On native date sets it reproduces G8-07's published leads:

| tier | G8-07 published | T1-13 native (₹10cr) |
|---|---|---|
| NON_FNO_TAIL | +0.296 | **+0.299** |
| SMALL_ADV_Q1 | +0.222 | **+0.228** |
| FNO_LARGE | −0.153 | **−0.153** |

Tier week counts reproduce exactly too: ALL / FNO_LARGE / SMALL_ADV_Q1 = 1,070, **NON_FNO_TAIL = 712**.

**Method note.** `backtest` is stateful — `lbook`/`sbook` evolve across dates and the rebalance fires
on `i % 4 == 0` — so filtering *input* dates would change the strategy, not the evaluation window.
Each (config, tier) therefore runs over the full panel exactly as G8-07 runs it, and only the
resulting net-return **series** is restricted to the common index (Rule 6).

## 2. The correction

Mean tier lead vs ALL, averaged across the three configs, net of cost:

| capital | tier | lead (native) | **lead (common)** | configs won |
|---|---|---|---|---|
| ₹1cr | NON_FNO_TAIL | +0.303 | **+0.049** | 2/3 |
| | SMALL_ADV_Q1 | +0.235 | **+0.299** | 3/3 |
| **₹10cr** | **NON_FNO_TAIL** | **+0.299** | **+0.042** | 2/3 |
| | **SMALL_ADV_Q1** | **+0.228** | **+0.279** | 2/3 |
| ₹100cr | NON_FNO_TAIL | +0.292 | **+0.029** | 2/3 |
| | SMALL_ADV_Q1 | +0.214 | **+0.227** | 2/3 |
| all | FNO_LARGE | −0.153 | **−0.272** | 0/3 |

**NON_FNO_TAIL's lead is ~86% date artifact** — it collapses to +0.04, effectively nothing.
**SMALL_ADV_Q1's lead is not** — it *rises* on the common index and is stable across capital.

Cost was the specific worry, because it penalises the least liquid tier hardest — i.e. works against
SMALL_ADV_Q1. It does bite (its lead decays +0.299 → +0.279 → +0.227 from ₹1cr to ₹100cr) but it does
not overturn anything. **T1-11's reversal survives the test designed to break it.**

## 3. The finding neither experiment was looking for

Per-config significance on the common index at ₹10cr, paired vs ALL:

| config | tier | Δ Sharpe | t | bootstrap 95% CI |
|---|---|---|---|---|
| **config4_secbal40_short** *(the certified book)* | NON_FNO_TAIL | **−0.284** | −1.65 | [−0.654, +0.089] |
| **config4_secbal40_short** | SMALL_ADV_Q1 | **−0.013** | −0.07 | [−0.440, +0.440] |
| longonly_Q5_bands | NON_FNO_TAIL | +0.207 | +2.00 | [−0.006, +0.449] — fragile |
| longonly_Q5_bands | SMALL_ADV_Q1 | +0.376 | +2.72 | [+0.103, +0.676] |
| longonly_secbal40 | NON_FNO_TAIL | +0.203 | +2.24 | [+0.026, +0.406] |
| longonly_secbal40 | SMALL_ADV_Q1 | **+0.475** | **+4.18** | **[+0.198, +0.800]** |

**In `config4_secbal40_short` — the certified production configuration — both tiers are negative.**
The entire tier advantage lives in the two long-only configs.

G8-07 reported "3 / 3 configs won" for both tiers. On a common index that becomes 2/3, and **the
config that fails is the one that is actually deployed.**

The mechanism is economically sensible: `short_q1` selects from `fno_ok` names only. In an
`ALL`-universe book the long and short legs draw from overlapping universes and the short leg hedges
what the long leg owns. In a NON_FNO_TAIL or SMALL_ADV_Q1 book the long leg is by construction
*disjoint* from the short leg's universe — so the short leg stops being a hedge and becomes an
uncorrelated drag. **The tier effect and the F&O short leg are structurally incompatible.**


## 3b. G8-11 — a second, more severe version of the same defect

**I nearly retracted §4's claim about G8-11 and would have been wrong to.** G8-11's own output reports
**all four tiers at 1,070 weeks**, which looks like clean, like-for-like coverage. It is not. Checking
the mechanism rather than trusting the column:

`g8_11_smallcap_deep_dive.backtest` **never skips a date.** It records
`port = float(r.mean()) if len(r) else 0.0` for every week, and gates only the *rebalance* on
`len(gg) >= 40`. So when a tier is too thin to form a book, the week is not excluded — it is recorded
as a **0.0% return**.

How often does that happen?

| tier | weeks below the 40-name rebalance threshold | last such week |
|---|---|---|
| ALL | 0 / 1,070 | — |
| FNO_LARGE | 0 / 1,070 | — |
| **NON_FNO_TAIL** | **447 / 1,070 (41.8%)** | 2014-05-09 |
| SMALL_ADV_Q1 | 296 / 1,070 (27.7%) | 2013-12-20 |

NON_FNO_TAIL's median name count by year is **0.0 for every year from 2005 to 2009, and again in
2013** — `fno_ok` is `adv_rank <= 190`, and the early panel has fewer than 190 names, so *every* name
is F&O-eligible and the non-F&O tail is empty by construction.

**This is worse than truncation.** Truncation removes hard weeks from the comparison; zero-fill
*credits the tier with a flat, risk-free 0.0% return through them* — including the whole of 2008.
A book sitting at zero through the GFC while `ALL` takes the drawdown will show a materially better
Sharpe, and 41.8% of NON_FNO_TAIL's sample is exactly that.

So G8-11's 16/17 sign test (p = 0.00027) is computed over Sharpes in which the winning tier spent two
fifths of the sample not trading. **Equal `n_weeks` is not evidence of equal coverage when empty
groups are filled rather than skipped** — which is now Rule 6c.

## 4. Findings

**G10-F38 — G8-07's non-F&O tier lead does not survive a common-date, net-of-cost, three-config
re-run.** +0.299 native → **+0.042** common. Roughly 86% of it was the 358-week coverage gap.

**G10-F38b — G8-11's independent evidence for the same tier is compromised by a different mechanism.**
Its uniform 1,070-week coverage is produced by recording `0.0` for weeks in which the tier cannot form
a book, not by the tier actually trading. **41.8% of NON_FNO_TAIL's sample is synthetic zeros**,
including all of 2005-09 and 2013 when the tier is *empty by construction*. Its 16/17 sign test at
p = 0.00027 rests on that. G8-11's correction of G8-07 is therefore **not supported either** — but for
a reason unrelated to G8-07's, and one that flatters the tier more, not less.

**G10-F39 — the micro-cap tier lead does survive, including the cost test designed to break it.**
+0.228 native → **+0.279** common at ₹10cr, decaying gracefully to +0.227 at ₹100cr, with the strongest
single cell at t = +4.18 and a bootstrap CI excluding zero. T1-11's reversal is confirmed at three
capital levels and on the full config set.

**G10-F40 — the tier advantage is a long-only phenomenon and is absent from the certified book.**
Both tiers are negative under `config4_secbal40_short` (−0.284 and −0.013). The F&O-only short leg
cannot hedge a long book drawn from a disjoint non-F&O universe. **Any proposal to tilt the certified
book toward small/illiquid names must drop or redesign the short leg first** — which makes it a
different strategy, not a tilt.

## 5. What is now settled, and what is not

**Settled:** the mechanism is a continuous size/ADV gradient, not a discrete F&O boundary. This is
consistent with G9-01 (Spearman −0.818, verified clean in T1-12) and inconsistent with G8-11's
framing. The binding constraint is capital/impact cost, not shortability.

**Not settled:** whether the micro-cap tilt is *deployable*. G10-F40 says it is not deployable in the
current book without redesigning the short leg, and G8-F19 already put the tradeable ceiling at
₹1–10cr. Those two together make it a small-capital, long-only proposition — which is a real thing,
but not an improvement to Config-4.

## 6. Threats to validity

- **The common index is 712 weeks starting 2008-01-04**, set by when NON_FNO_TAIL first reaches 20
  names. All corrected numbers describe that window. It is shared by every tier, which is the point,
  but no tier is characterised on 2005–07 here.
- **The comparison is restricted by the weakest tier.** If NON_FNO_TAIL were dropped, the common index
  for the remaining three would be 1,070 weeks and SMALL_ADV_Q1's lead should be re-read on that
  longer window before being acted on.
- **`SHORT_COST_WK = 0.0008` is a flat borrow assumption** inherited from G8-07. Real borrow on
  small-caps is worse and more variable, which would deepen G10-F40 rather than soften it.
- Lockbox (post 2025-07-11) is excluded throughout, as in G8-07.
