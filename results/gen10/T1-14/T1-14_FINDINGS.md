# T1-14 — Full-Window Tier Check and the G8-11 Re-run. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T1-13 (whose §3b this CORRECTS), results/gen8/G8-07, G8-11
Artifacts:    t1_14_data.json. Script: scripts/gen10/t1_14_tier_full_window_and_g811_rerun.py
```

**Outcome: the tier question resolves, and it resolves against my own T1-13 reasoning.** Zero-fill
does not flatter a thin tier — it *dilutes* it, by exactly √(n/(n+k)). Correcting G8-11 therefore
**raises** both thin tiers rather than deflating the favoured one, and the effect is to put
`SMALL_ADV_Q1` and `NON_FNO_TAIL` at parity (both 15/17, both p = 0.00235) rather than to choose
between them. The durable finding is simpler than the dispute it came out of: **large caps
underperform, both smaller tiers outperform, and which of the two leads was never the interesting
question.**

---

## 1. Correction to T1-13 §3b — I had the sign of the zero-fill bias backwards

T1-13 §3b argued that G8-11's zero-fill was "worse than truncation" because a tier sitting flat at
0.0% through the GFC would show "a materially better Sharpe" than one taking the drawdown. **That is
wrong, and it is wrong arithmetically, not just empirically.**

Padding a return series of *n* observations (mean μ, sd σ) with *k* exact zeros gives
mean → μ·n/(n+k) and sd → σ·√(n/(n+k)), so

```
Sharpe_padded  ≈  Sharpe_true × √(n / (n+k))
```

Zeros shrink the mean linearly and the standard deviation only as a square root, so **the Sharpe is
always diluted toward zero.** Verified numerically against the closed form:

| zeros added | n | Sharpe | predicted |
|---|---|---|---|
| 0 | 600 | 0.5586 | 0.5586 |
| 100 | 700 | 0.5170 | 0.5172 |
| 270 | 870 | 0.4636 | 0.4639 |
| 447 | 1047 | 0.4225 | 0.4229 |

The defect in G8-11 is real; **its direction is the opposite of what I claimed.** It *understated*
every tier that spends weeks unable to trade — which is precisely the thin ones.

## 2. Part B — G8-11 re-run with empty weeks excluded

Correctness gate first: reproducing G8-11's method verbatim (zero-filled) gives **NON_FNO_TAIL
16/17**, matching its published 16/17 exactly. `SMALL_ADV_Q1` reproduces at 7/17 against a published
5/17 — the small gap is capital level (₹10cr here vs. G8-11's average over six levels).

| tier | mean Sharpe, zero-filled | mean Sharpe, excluded | Δ | mean empty weeks |
|---|---|---|---|---|
| ALL | 0.5108 | 0.5124 | +0.002 | 5 |
| FNO_LARGE | 0.4003 | 0.4018 | +0.002 | 5 |
| **NON_FNO_TAIL** | 0.7476 | **0.8678** | **+0.120** | **270** |
| **SMALL_ADV_Q1** | 0.4773 | **0.5276** | **+0.050** | **185** |

Both thin tiers rise once their non-trading weeks stop being counted as flat returns. The two liquid
tiers, which are essentially never empty, do not move.

**The headline — tier beats ALL in how many of 17 signals:**

| tier | zero-filled | **excluded** | sign test (excluded) |
|---|---|---|---|
| FNO_LARGE | 0 / 17 | **0 / 17** | p = 0.00002 |
| NON_FNO_TAIL | 16 / 17 | **15 / 17** | p = 0.00235 |
| **SMALL_ADV_Q1** | 7 / 17 | **15 / 17** | **p = 0.00235** |

**G8-11's central claim is half right.** The non-F&O tail's advantage is real and survives the fix
almost unchanged (16→15 of 17). But its companion claim — that the bottom ADV quintile "is not an
advantage at all" and "*loses* to the full universe on average (−0.096)" — **does not survive**. Once
its 185 empty weeks stop being scored as zeros, `SMALL_ADV_Q1` goes from 7/17 to **15/17**, tying the
tier G8-11 elevated above it.

## 3. Part A — the full 1,070-week window

T1-13's common index was 712 weeks, bounded by the weakest tier. Dropping `NON_FNO_TAIL`, the other
three have 1,070 weeks each — and per Rule 6 "same count" was verified to be "same dates" rather than
assumed. It is: all three indices are **identical**, in all three configs.

| config | FNO_LARGE lead | SMALL_ADV_Q1 lead | SMALL t | bootstrap 95% CI |
|---|---|---|---|---|
| config4_secbal40_short *(certified)* | −0.2155 | **+0.0725** | +0.48 | [−0.260, +0.424] |
| longonly_Q5_bands | −0.1268 | **+0.3072** | +2.84 | [+0.095, +0.536] |
| longonly_secbal40 | −0.1160 | **+0.3040** | +3.81 | [+0.110, +0.537] |
| **mean** | **−0.1528** | **+0.2279** | | |

**SMALL_ADV_Q1's lead holds on the longer window** (+0.228 against +0.279 on the 712-week index),
significant with bootstrap CIs excluding zero in both long-only configs — and **absent in the
certified config** (t = +0.48), confirming T1-13's G10-F40 on a window 50% longer.

## 4. Findings

**G10-F41 — zero-fill dilutes, it does not flatter. T1-13 §3b is corrected.** Padding with zeros
scales Sharpe by √(n/(n+k)). G8-11's defect understated its thin tiers rather than inflating them, and
my reasoning about the GFC was backwards.

**G10-F42 — G8-11's non-F&O finding survives its own correction; its micro-cap dismissal does not.**
With empty weeks excluded, NON_FNO_TAIL is 15/17 (p = 0.00235) and SMALL_ADV_Q1 is **also 15/17
(p = 0.00235)**, against G8-11's published 5/17 and its claim that the tier "loses to the full
universe on average."

**G10-F43 — the tier question resolves as a monotone size effect, not a contest between two tiers.**
Large caps lose in 0 of 17 signals (p = 0.00002); both smaller tiers win in 15 of 17. Every
generation that looked at this — G8-07, G8-11, T1-11, T1-13 — was arguing about *which* small tier
leads, on evidence that could not support the distinction because each analysis compared groups over
different observation sets. **What all of them agree on, and what survives every correction, is the
gradient itself**, which is exactly what G9-01 measured directly (Spearman −0.818, verified clean in
T1-12).

**G10-F44 — the certified book remains the exception.** SMALL_ADV_Q1's lead is +0.0725 with t = +0.48
under `config4_secbal40_short` on 1,070 weeks, against +0.30 (t = 2.8–3.8) in both long-only configs.
The F&O-only short leg cannot hedge a long book drawn from a disjoint universe. Confirmed on the
longer window.

## 5. What the tier story now is

Stated once, cleanly, after four experiments across three generations:

- **The edge is a continuous size/liquidity gradient.** Smaller is better, monotonically, and the
  binding constraint is capital and impact cost rather than F&O shortability.
- **Both sub-large tiers carry it**, at statistically indistinguishable strength. The
  non-F&O-vs-micro-cap dispute was an artifact of three different mismatched-observation-set defects,
  and is now closed as unanswerable *and unimportant*.
- **It is long-only.** It does not exist in the certified book, and adding it requires redesigning the
  short leg — a different strategy, not a tilt.
- **It is capacity-bound** to roughly ₹1–10cr (G8-F19), which is where every promising lead in this
  programme has converged.

## 6. Threats to validity

- **Part B is at ₹10cr only**, where G8-11 averaged six capital levels; that is why its zero-filled
  reproduction gives 7/17 for SMALL_ADV_Q1 against a published 5/17. The *direction and size* of the
  zero-fill correction (7 → 15) is far larger than that gap, but the absolute counts are not directly
  comparable to G8-11's table.
- **Excluding empty weeks changes what is being measured**, from "the tier's return including periods
  it could not trade" to "the tier's return when it can trade." The second is the right quantity for a
  tier comparison and the wrong one for a deployable-strategy return series — a book that cannot
  trade for 270 weeks is not a book. That constraint is real and is the capacity story, not the alpha
  story.
- The 17 signals are correlated (four are momentum variants), so a sign test at m = 17 overstates
  independence. It overstates it identically for every tier, so the *comparison* stands even though
  the p-values are optimistic in absolute terms.
- Part A's window is 1,070 weeks and its date sets are verified identical; Part B's are per-signal and
  per-tier, compared pairwise on shared dates.
