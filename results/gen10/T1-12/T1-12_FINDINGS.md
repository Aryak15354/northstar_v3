# T1-12 — Index-Alignment Audit of the Load-Bearing Findings

```
Version:      v1.0
Status:       Frozen
Freeze Date:  2026-07-31
Owner:        Aryak
Motivation:   T1-11 was the fifth appearance of one defect class. Delivery is the second
              most load-bearing finding in the programme after momentum, so the question
              is whether the defect is sitting in the artifact we can least afford it in.
Scope:        A targeted audit, not a new experiment. No hypothesis is tested.
```

**Outcome: Delivery is clean on all three of its load-bearing artifacts, and G9-01's liquidity
gradient is clean to three decimal places. The defect bites in exactly one place — G8-07/G8-11 —
which T1-11 already found.** One structural vulnerability is recorded that does not currently bite.

---

## 1. What was audited and why

The defect class: **comparing statistics computed over different observation sets.** Five prior
appearances — pooled stock-weeks (T0-01), pooled multi-universe cross-sections (T0-03), tier-native
date sets (T1-08, T1-11), mismatched estimation eras (T1-06). The common mechanism is an implicit
assumption that two things share an index, breaking silently.

Delivery is now the programme's second most load-bearing finding. It rests on three artifacts.

## 2. Results

| artifact | mechanism present? | does it bite? | evidence |
|---|---|---|---|
| **ARP capacity ladder** `scripts/arp/delivery_capacity_recovery.py` | **yes, structurally** — `port_returns` skips dates where a selector returns empty, then `metrics()` computes each Sharpe on its own index, with **no reconciliation** | **no** | CONTROL and ADD have **identical** date sets: 130/130 (OOS), **338/338** (full window). Native and common-date deltas are identical to 4 dp (+0.1037) |
| **G8-09 book integration** `scripts/gen8/g8_09_delivery_book_integration.py` | **no** — explicitly `common = base.index.intersection(over.index)` before differencing (lines 190, 212) | n/a | correct by construction |
| **G9-01 liquidity gradient** `scripts/gen8/g9_01_*.py` | **yes, structurally** — decile ICs averaged over whatever `(date, signal)` cells cleared `MIN_NAMES = 25` | **no** | see below |

### G9-01 in detail — the finding I previously asserted was unaffected

I claimed in T1-11 that G9-01 was not exposed because its deciles exist every week. That was an
assertion; here it is tested.

Coverage is near-symmetric by construction (deciles are equal-sized `qcut` buckets):

```
decile   n_dates   mean names
  0        604       34.66
  ...      591-604   34.2-34.9
  9        604       34.85
```

**94.0%** of `(date, signal)` cells are complete across all ten deciles. Recomputing the gradient on
the identical cell set for every decile:

| | Spearman(decile, mean IC) | p |
|---|---|---|
| archived (each decile on its own cells) | **−0.818** | 0.0038 |
| **common-cell (identical set for every decile)** | **−0.818** | **0.0038** |

Identical to three decimals; individual decile means move by ≤0.0013. **G9-01 stands, verified rather
than asserted.**

## 3. The structural vulnerability worth recording

`delivery_capacity_recovery.py` is clean **because of its data, not because of its code.** Both
selectors run on a frame already filtered to `delivery_pct_4w_avg.notna()`, the momentum top-quintile
is never empty, and `s_add` is a superset of `s_control`. Change any one of those — a stricter
delivery threshold, a minimum-names floor, a different momentum cut — and CONTROL and ADD acquire
different date sets silently, with `metrics()` happily reporting two Sharpes measured over different
weeks.

That is precisely how G8-07 acquired its defect: nothing in the code is wrong until the data shifts
under it. **Recorded as a latent defect, not an active one.**

## 4. Findings

**G10-F35 — the Delivery finding is not contaminated by the index-alignment defect.** All three
load-bearing artifacts check out: the capacity ladder has identical date sets (338/338), G8-09
intersects explicitly, and neither result changes.

**G10-F36 — G9-01's liquidity gradient is verified, not merely assumed, unaffected.** Recomputed on a
common cell set the Spearman is identical to three decimals (−0.818, p=0.0038). The corrected tier
picture from T1-11 is therefore *consistent* with G9-01 rather than in tension with it: a continuous
gradient across liquidity deciles sits more comfortably with a continuous size/ADV story than with a
discrete F&O-boundary one.

**G10-F37 — the capacity ladder carries a latent version of the defect.** It is correct today for
reasons that live in the data rather than the code. Rule 6 exists to convert that from luck into
guarantee.

## 5. Threats to validity

- This audits three artifacts, chosen because they carry the Delivery and liquidity findings. It is
  not a sweep of every comparison in the repository.
- The capacity ladder was checked on the OOS and full-delivery windows as the script itself uses them.
  A different capital band or construction was not re-derived.
- G9-01's Q2 arm (tercile × F&O designation) shows genuinely asymmetric coverage — `0|FNO` has 72
  dates against `0|NON`'s 810 — which is expected, since a low-ADV F&O name is rare by definition.
  That arm was **not** re-derived here; only the headline decile gradient was. If the Q2 conclusion is
  ever load-bearing, it should get the same treatment.
