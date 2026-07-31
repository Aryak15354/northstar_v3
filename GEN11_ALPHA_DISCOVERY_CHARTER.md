# Gen-11 — Alpha Discovery: Charter and Standing Gate

```
Version:   v1.0
Status:    OPEN
Opened:    2026-07-31
Owner:     Aryak
Mandate:   Find deployable alpha OTHER THAN MOMENTUM.
Binding:   RESEARCH_INFERENCE_STANDARD.md (six rules) — all of it, without exception.
```

## 1. Why this can be opened at all

Gen-10 closed with: *the binding constraint is estimation, not information* — and one explicit
exception. The ceiling it measured (**attainable IC +0.141**, book captures 20%) was computed on the
**15-feature price basis only**. Gen-10's own threat-to-validity says so:

> *"The ceiling is basis-specific. It bounds what these 15 features can deliver, not what any data
> could. A genuinely new data source is the one route Pillar 5 does not close."*

The enriched panel carries **603 columns** across macro, credit, fundamentals, earnings, sentiment,
events/flows and microstructure. Most were tested **individually** across Gen-1/2/3 and rejected. None
was ever tested for **incremental ceiling over the price basis**. Those are different questions: a
family can contain no standalone signal and still raise the joint ceiling.

Gen-11 therefore starts by **mapping where information lives**, not by proposing a strategy.

## 2. What "alpha other than momentum" means operationally

A candidate must clear a definition, not just a t-statistic. **Every candidate is orthogonalised
against the deployed momentum composite, per date, in rank space, before it is scored.** A signal
whose incremental IC over momentum is zero is momentum, whatever it is called. This is the lesson of
T1-04a, where three "new" delivery signals turned out to be one already-deployed signal (incremental
t 0.27–0.61 against the incumbent).

## 3. The standing adversarial gate — pre-registered, applied to every candidate

A candidate is **REJECTED** the moment it fails any stage. No stage may be re-run with a changed
specification to rescue a failure; a changed specification is a new candidate with a new multiplicity
count.

| # | gate | kill condition |
|---|---|---|
| **A0** | **Coverage honesty** | fewer than 150 usable dates, or coverage straddling two universes without the composition correction (T0-03) |
| **A1** | **Incremental over momentum** | \|t\| < 2 on the momentum-orthogonalised signal (Rule 1: per-date IC, NW + bootstrap) |
| **A2** | **Out-of-sample split** | OOS \|t\| < 2, or sign flip vs discovery. Discovery/OOS/lockbox fixed before running |
| **A3** | **Multiplicity** | not BY-clean across every candidate tried in the same family, counting abandoned variants (Rule 4) |
| **A4** | **Not a rediscovery** | rank-correlation ≥ 0.7 with any already-catalogued signal, or an incremental t < 2 against it |
| **A5** | **Turnover / cost** | net-of-cost Sharpe contribution ≤ 0 through `IndianEquityCostModel`, or turnover in A04's band (~4000 %/yr) |
| **A6** | **Economic story** | no stateable mechanism. A signal that works for no reason is a fit until proven otherwise |
| **A7** | **Portfolio contribution** | fails to improve the book at the portfolio level, paired, with a CI excluding zero (Gen-5 F08) |

**A1 before everything else.** It is the cheapest and it is the one that defines the mandate.

## 4. Standing cautions inherited from Gen-10

- **Composition artifact (T0-03).** Any IC on a pooled multi-universe cross-section reports its
  within-group value alongside. Cost the momentum-quality cluster 30–40% of its headline.
- **Index alignment (Rule 6).** Cross-group comparisons on an explicitly common index; equal *n* is
  not equal coverage.
- **Full-sample fitting.** `RESEARCH_SIGNAL` as issued by the Gen-2/3 deep search did not predict
  out-of-sample survival in a single case out of 14.
- **Turnover masquerading as signal.** The largest |t| in the entire deep search (−8.91) was a
  4091 %/yr transaction-cost machine.
- **Measure a bias, never reason about it.** Gen-10 got the direction of the zero-fill bias backwards
  by arguing from intuition; the arithmetic took two lines.

## 5. Sequence

1. **E1 — Ceiling decomposition.** Where does information live? Incremental attainable ceiling of each
   feature family over the price basis, measured against a permutation null, on matched dates.
   *Descriptive. No strategy proposed. Its output decides everything after it.*
2. **E2+** — construct and gate candidates in whichever family E1 identifies, in descending order of
   incremental ceiling. Stop when a family's ceiling is exhausted or its candidates die at A1/A2.

## 6. Kill condition for the programme

If E1 shows **no family with a materially positive incremental ceiling**, Gen-11 closes immediately
with that as its finding, and Gen-10's closing statement stands unamended. That is a real possible
outcome and it is cheaper to accept than to work around.
