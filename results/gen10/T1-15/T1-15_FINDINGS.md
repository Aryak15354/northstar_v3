# T1-15 — Tier Constituent Overlap, and Paper C Q2. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Depends On:   results/gen10/T1-14 (the tie this explains), results/gen10/T0-02 (Q2 left open)
```

**Outcome: the 15/17 tie needs no explanation — `SMALL_ADV_Q1` is a strict subset of
`NON_FNO_TAIL` in every year from 2015 on. And Paper C Q2, the one sub-question T0-02 left
untested, does clear its bar.**

---

## 1. The tier "tie" is a nesting, not a coincidence

T1-14 found NON_FNO_TAIL and SMALL_ADV_Q1 both at 15/17 signals, p = 0.00235 each, and read that
as a monotone gradient rather than a contest. That reading is now mechanical rather than
inferential. F&O eligibility in India is itself liquidity-gated (`fno_ok` is `adv_rank <= 190`), so
the two tier definitions are not independent partitions of the universe:

| | |
|---|---|
| mean Jaccard(NON_FNO_TAIL, SMALL_ADV_Q1) | **0.506** |
| mean share of SMALL_ADV_Q1 that is **also** non-F&O | **87.2%** |
| mean share of NON_FNO_TAIL that is also bottom-ADV | 63.4% |
| mean tier sizes | NON_FNO 122 names, SMALL_Q1 63 names |

Share of SMALL_ADV_Q1 sitting inside NON_FNO_TAIL, by year:

```
2007  20.3%   2011  55.7%   2015-2025  100.0%  (every year)
2008  31.9%   2012  34.8%
2009  32.6%   2013  34.5%
2010  90.5%   2014  80.2%
```

**From 2015 onward the containment is total: SMALL_ADV_Q1 is the bottom half of NON_FNO_TAIL.**
The pre-2014 figures are low for the reason T1-13 already documented — the early panel has fewer
than 190 names, so almost nothing is outside the F&O universe and NON_FNO_TAIL is near-empty.

**Consequence.** These were never two tiers to choose between. They are one liquidity gradient cut
at two points, the tighter cut nested inside the looser one. Four analyses across three generations
(G8-07, G8-11, T1-11, T1-13) argued about which of them "really" carries the edge; the question was
malformed. It also means a dedicated construction effort aimed at this tier would be **chasing one
signal, not diversifying across two** — which is directly relevant to whether G5-08 is worth opening.

## 2. Paper C Q2 — the last untested sub-question

T0-02 classified Q2 as NO-TEST and explicitly left it open rather than silently reclassifying it.
Supplying the test now. The archived result is a per-name correlation between liquidity persistence
(ADV autocorrelation) and trading cost, `corr = -0.119, n = 517`, with no standard error.

Rebuilt (n = 344 names clearing a 60-observation floor; the count differs from 517 because the
original's per-name filter is looser):

```
corr = -0.1370
naive t, treating names as independent   = -2.56
bootstrap over names, 95% CI             = [-0.2871, -0.0183]   excludes zero
```

**Q2 clears its bar**, and unlike Q1/Q3/Q4 it does so on a test rather than a point estimate. The
sign is as claimed: higher liquidity persistence associates with lower trading cost.

Two caveats keep this modest. The effect is small (r ≈ −0.14, ~2% of variance), and names are not
independent — they share a market factor — so even the bootstrap-over-names CI is optimistic. It is
a real, weak, correctly-signed association, not a trading rule.

**This is also the one place where a Gen-10 correction goes in the archive's favour.** T0-02 retired
Q3 and downgraded Q1/Q4; Q2 survives. Worth stating plainly, because a remediation programme that
only ever finds things worse than reported should be suspected of looking for that answer.

## 3. Findings

**G10-F45 — `SMALL_ADV_Q1` is a strict subset of `NON_FNO_TAIL` from 2015 onward (100% containment,
87.2% on average across the full sample).** The two tiers are one gradient cut at two points. The
non-F&O-vs-micro-cap dispute was malformed, and its resolution as a "tie" in T1-14 is a nesting
artifact rather than a finding requiring explanation.

**G10-F46 — AEP Paper C Q2 clears its bar.** corr = −0.137, bootstrap-over-names 95% CI
[−0.287, −0.018], excluding zero. Small and correctly signed. Q2 is the only Paper C sub-question to
survive Gen-10, and the only Gen-10 result that revises an archived verdict *upward*.

## 4. Threats to validity

- The overlap is measured on `load_panel()`'s universe with its `close >= 20` filter and pre-lockbox
  window, matching every tier experiment in this programme.
- Q2's rebuild uses a fixed ₹500cr book and a 100-name position count to derive per-name cost, which
  reproduces the archived correlation's sign and rough magnitude (−0.137 vs −0.119) but not its
  exact `n`. The conclusion is not sensitive to that gap; the CI is wide either way.
- Bootstrapping over names treats names as exchangeable, which understates dependence from shared
  sector and market exposure. The true interval is wider than reported.
