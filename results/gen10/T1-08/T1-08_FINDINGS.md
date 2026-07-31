# T1-08 — Exit Realism. Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Replaces:     Northstar_Remediation_Priority_Plan.md item 2.3 (universe-rule rewrite + rebuild)
Depends On:   results/gen8/G8-12 (which named this as the actual remaining task),
              results/gen8/G8-07 (the lead being stressed), GEN10_REMEDIATION_CHARTER.md s4/T1-08
Artifacts:    t1_08_data.json. Script: scripts/gen10/t1_08_exit_realism.py
```

**Outcome: the small-cap lead survives realistic exit assumptions, and a date-coverage correction
changes which tier is actually leading.** G8-12's bound is confirmed by direct simulation. But the
correction needed to make the tiers comparable also puts G8-11's conclusion — that the non-F&O tail
rather than the micro-cap tier is the source — in question.

---

## 1. Why this replaces plan item 2.3

The remediation plan proposed rewriting the universe-inclusion rule so names stay eligible through
delisting, rebuilding the panel, and re-running C04/C05/C07. G8-12 had already rejected that reading:

> *"The universe rules are the strategy's own rules… Dropping it is not the backtest hiding a loss —
> it is the backtest executing a stop that the strategy actually has."*

Holding names below ₹20 with no liquidity all the way to zero models a book nobody would trade.
G8-12 named the real task instead (§6.1): charge a realistic gap-down when a name leaves the universe
on a price or liquidity failure. That is what this does.

## 2. Failure exits

A failure exit is a (date, ticker) where the name is held at *t*, absent at *t+1*, and its last
observation shows it failing the universe rule on price or liquidity — not simply reaching the end of
the data.

| tier | failure-exit rows | share of tier rows |
|---|---|---|
| ALL | 711 | 0.244% |
| FNO_LARGE | 403 | 0.209% |
| NON_FNO_TAIL | 308 | 0.314% |
| **SMALL_ADV_Q1** | 408 | **0.696%** |

The exposure ordering reproduces G8-12 §3 independently: the illiquid tier sits closest to the
universe boundary and is dropped roughly 3× as often as the large-cap tier.

## 3. A correction that had to come first

Each tier book exists on a different number of dates — the ≥30-name floor bites hardest on the small
tiers:

```
ALL = 1032 weeks | FNO_LARGE = 1032 | NON_FNO_TAIL = 643 | SMALL_ADV_Q1 = 869
```

**Comparing Sharpes across different date sets compares periods, not tiers.** All results below use
the common 643-week set. This matters: on the tier-native date sets NON_FNO_TAIL leads ALL by +0.573;
on the common set the same comparison is **+0.204**. Two-thirds of the apparent lead was a period
effect.

## 4. The sweep

Top-quintile residual-momentum long book within each tier, charging the stated gap on the exit week
of any holding that leaves the universe on a failure. Common 643-week date set.

| gap on exit | ALL | FNO_LARGE | NON_FNO_TAIL | SMALL_ADV_Q1 |
|---|---|---|---|---|
| clean fill | 1.0607 | 0.8316 | 1.2650 | 1.5156 |
| −10% | 1.0483 | 0.8277 | 1.2379 | 1.4925 |
| −20% | 1.0107 | 0.8147 | 1.1472 | 1.4020 |
| −35% | 0.9542 | 0.7951 | 1.0090 | 1.2617 |
| −50% | 0.8976 | 0.7752 | 0.8712 | 1.1194 |

**Tier lead vs ALL:**

| gap on exit | NON_FNO_TAIL | SMALL_ADV_Q1 | FNO_LARGE |
|---|---|---|---|
| clean fill | +0.2044 | **+0.4550** | −0.2290 |
| −10% | +0.1896 | +0.4442 | −0.2206 |
| −20% | +0.1365 | +0.3913 | −0.1960 |
| −35% | +0.0548 | +0.3075 | −0.1591 |
| −50% | **−0.0265** | **+0.2217** | −0.1224 |

**Break-even exit assumption:**

- **NON_FNO_TAIL** — lead reaches zero at a **−45.1%** gap-down exit.
- **SMALL_ADV_Q1** — lead survives the entire sweep; still +0.222 at −50%.

A −45% gap-down on every failing exit is far harsher than any realistic fill. G8-12's honest range
(0 to −2.29%/yr drag) is confirmed here by direct simulation rather than by applying a median decline
uniformly to each tier's share of truncated rows.

## 5. Statistical significance — the leads are weaker than the point estimates suggest

| comparison | Sharpe difference | t | bootstrap 95% CI | |
|---|---|---|---|---|
| NON_FNO_TAIL vs ALL, clean fill | +0.204 | +2.07 | [−0.049, +0.470] | **FRAGILE** |
| **SMALL_ADV_Q1 vs ALL, clean fill** | **+0.455** | **+3.13** | **[+0.120, +0.821]** | significant |
| NON_FNO_TAIL vs ALL, −50% | −0.026 | −0.23 | [−0.328, +0.279] | gone |
| SMALL_ADV_Q1 vs ALL, −50% | +0.222 | +1.43 | [−0.156, +0.635] | not significant |

The NON_FNO_TAIL lead is **fragile even at clean fill** — the Newey-West t crosses 2 while the
bootstrap interval includes zero, which is precisely the disagreement G10-L03 requires be reported
rather than resolved by picking the friendlier estimator.

## 6. Findings

**G10-F23 — the small-cap lead survives exit realism.** Break-even requires a −45% gap-down on every
failure exit for NON_FNO_TAIL, and SMALL_ADV_Q1's lead survives −50% intact. Exit realism is
**not** what threatens this lead, and G8-12's 0 to −2.29%/yr bound is confirmed by direct simulation.
The plan's item 2.3 would have spent a panel rebuild on a non-problem.

**G10-F24 — two-thirds of the NON_FNO_TAIL lead is a date-coverage artifact.** Measured on its native
643-week date set the tier leads ALL by +0.573; measured against ALL on the same 643 weeks it leads by
+0.204. Tier books do not exist on the same dates, and Sharpe comparisons across different date sets
compare periods. This is the same class of error as T0-03's composition artifact: an apparently clean
comparison confounded by which observations each arm actually contains.

**G10-F25 — the tier ordering may be the reverse of G8-11's.** On the common date set SMALL_ADV_Q1
leads by +0.455 (t = 3.13, bootstrap CI excludes zero) while NON_FNO_TAIL leads by +0.204 (fragile).
G8-11 concluded the opposite — that the non-F&O tail, not the micro-cap tier, is the real source, and
"non-F&O beats all in 16/17 signals". **This is flagged as a discrepancy, not a refutation:** the
construction here is one config (top-quintile residual momentum, no cost model) against G8-07/G8-11's
three configs with the full cost model. The specific thing worth re-checking is whether G8-07's tier
comparison used common dates.

## 7. Consequences

- **Plan item 2.3 is closed**, having been replaced. No panel rebuild is needed and none should be
  done: the universe rule is the strategy's stop, and the exit assumption it implies costs far less
  than the lead is worth.
- **G8-07's lead is not threatened by survivorship or exit realism** — but it remains what G8-F18
  called it, a lead rather than a finding, and this adds a second reason: on common dates the
  NON_FNO_TAIL version of it is fragile.
- **A follow-up is warranted on G8-07/G8-11**: re-run their tier comparison on a common date set. If
  the ordering flips there too, G8-11's correction of G8-07 needs revisiting.

## 8. Threats to validity

- **One configuration, no cost model.** G8-07 averaged three configs through the real
  `IndianEquityCostModel`; this uses a single top-quintile momentum book on gross returns. It is the
  right construction for isolating the *exit* assumption (which is what was asked) and the wrong one
  for restating G8-07's absolute numbers. The §6 discrepancy is reported with that caveat attached.
- **The common date set is 643 weeks and skews later**, because the panel's cross-section grows over
  time and the small tiers only clear the 30-name floor in later years. The correction removes a
  period confound between tiers but introduces a period restriction common to all of them.
- **The gap is charged on the exit week's return only.** A real forced exit from a collapsing illiquid
  name might take several weeks and incur impact on each. The −50% single-week charge is intended to
  bracket that; it is a bound, not a simulation of the liquidation path.
- **Failure exits are identified from the panel's own thresholds** (ADV < ₹1cr, close < ₹25, or the
  delisted flag). Names that leave for benign reasons — index reconstitution, a data gap — are
  excluded, but the classification is heuristic and 711 exits is a small population.
