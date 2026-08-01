# E8 — Institutional Ownership Change ("Institutional Sentiment"). Findings

```
Version:   v1.0
Status:    Frozen — concept tests as a coin flip; AMFI build NOT recommended
Freeze:    2026-07-31
Proposal:  monthly AMFI/MF portfolio disclosures as a PIT proxy for analyst consensus
Method:    tested the concept on quarterly ownership data ALREADY in the panel, before
           committing to the acquisition build
```

**Outcome: the concept is a coin flip on data already held, and one factual premise behind the
proposal is wrong.** The AMFI build is a large project (40+ AMC sites, heterogeneous monthly
filings) whose prior is now poor. One corner of the idea remains genuinely untested.

---

## 1. First, a concern that turned out to be unfounded

The panel's `screener_*` ownership columns were suspect: this repo's own dataset audit found
Screener metadata being *broadcast* into history, which poisoned the `val_*` family. If these
were constants, Gen-1's rejections of them (A13, G2-D05a) would have tested nothing.

**They are genuine time series.** ~12 distinct values per name, quarterly steps, with
`screener_dii_pct` running **2016-07 → 2026-06 (418 weeks)**. Example, RELIANCE FII%:
22.49 → 22.60 → 22.06 → 21.30 → 19.07 → 18.65 → 19.09. Real, moving data. The prior
rejections stand on real evidence.

## 2. The concept, tested at the observation level

The proposal is *change* in institutional ownership, not level. A first pass got only 14 usable
weeks because the quarterly data is forward-filled weekly and `.diff()` is zero except on step
dates — a construction error. Corrected to differencing at the **distinct-observation** level,
then forward-filling the realised change:

| candidate | weeks | share-positive | NW t | resid IC | resid t | verdict |
|---|---|---|---|---|---|---|
| `screener_dii_pct_qchg` | 150 | **51.3%** | −0.46 | +0.0035 | +0.68 | coin flip |
| `screener_fii_pct_qchg` | 150 | 46.7% | −0.47 | +0.0009 | +0.17 | borderline |
| `screener_institutional_pct_qchg` | 150 | **48.7%** | −0.65 | +0.0021 | +0.43 | coin flip |
| `screener_promoter_pct_qchg` | 150 | 49.3% | +0.43 | +0.0073 | +1.35 | coin flip |

Reference: **delivery 62.2%**, **momentum 60.5%** (both real); **futures OI 50.0%** (dead).

**All four sit where futures OI died.** This is the same class of result — and futures OI had a
genuine +0.0266 incremental ceiling behind it, which these do not.

This corroborates rather than duplicates the existing record: Gen-1 **A13** (FII flow following,
L/S −3.7%/yr, Sharpe −0.63), **G2-D05a** (rising FII ownership, t = −1.91) and **G2-D05b**
(rising promoter holding, t = 0.70) all rejected the same family by different routes.

## 3. The freshness test — the fair version of the objection

A legitimate objection to §2: forward-filling means most weeks carry a *stale* change. If the
effect lives in the days after disclosure, the test dilutes it — and that would be the argument
for monthly data, which delivers 3× more fresh events.

| feature | weeks since disclosure | weeks | stock-weeks | resid IC | resid t |
|---|---|---|---|---|---|
| `screener_dii_pct` | fresh (0–2) | 33 | — | **too few to test** | — |
| | mid (3–8) | 66 | 31,889 | +0.0012 | +0.17 |
| | stale (>8) | 59 | 27,077 | +0.0072 | +0.56 |
| `screener_institutional_pct` | fresh (0–2) | 33 | — | **too few to test** | — |
| | mid (3–8) | 66 | 31,751 | +0.0122 | +1.54 |
| | stale (>8) | 51 | 25,906 | +0.0058 | +0.85 |

**The freshest window genuinely cannot be tested at quarterly frequency** — 33 weeks is below
the floor. That is the one honest gap, and it is exactly what monthly data would fill.

Against it: a quarterly signal decays over ~13 weeks, so a strong post-disclosure drift should
still be visible in the 3–8 week window. It is not (t = 0.17, +1.54 on ~32,000 stock-weeks).

## 4. A factual correction to the proposal

> *"Libraries like `yfinance` ... can access historical institutional holding percentages."*

**Not for Indian equities.** Tested directly:

```
RELIANCE.NS    institutional_holders  EMPTY    mutualfund_holders  EMPTY
INFY.NS        institutional_holders  EMPTY    mutualfund_holders  EMPTY
TATAMOTORS.NS  institutional_holders  EMPTY    mutualfund_holders  EMPTY
major_holders  -> 4 rows, no date column: a current snapshot, no history
```

There is no shortcut. The AMFI route would have to be built from scratch.

## 5. What the AMFI build would actually cost

The proposal's regulatory premise is correct — SEBI mandates **monthly** portfolio disclosure by
AMCs, and that is genuinely PIT if the publication lag is respected (disclosures land ~10 days
after month-end; using the as-of date rather than the publication date would reintroduce
look-ahead).

But there is no consolidated feed. AMFI publishes NAV and AUM, not stock-level holdings. Those
sit on **40+ individual AMC websites**, as heterogeneous XLS/PDF, monthly, with no schema
stability. That is a multi-week engineering project with ongoing maintenance.

**And it would buy a genuinely different measurement** — rupee holdings per scheme, hence real
net flows rather than % of shares outstanding. That distinction is real and I do not dismiss it.
The problem is that the quantity it proxies tests at 51.3% on ten years of quarterly data.

## 6. Findings

**G11-F10 — institutional ownership change is a coin flip on the data already held.** Four
constructions, 150 weeks, share-positive 46.7–51.3%, all resid |t| < 1.4. Corroborates A13,
G2-D05a and G2-D05b by a fourth independent route.

**G11-F11 — `yfinance` does not carry Indian institutional or mutual-fund holdings.**
`institutional_holders` and `mutualfund_holders` return empty frames; `major_holders` is an
undated snapshot. Any MF-ownership panel must be built from AMC filings directly.

**G11-F12 — the post-disclosure freshness window is untestable at quarterly frequency and is
the one live corner of this idea.** 33 weeks is below the floor. The adjacent 3–8 week window,
where a quarterly effect should still be visible, shows nothing.

## 7. Recommendation, and what would change it

**Do not build the AMFI pipeline on current evidence.** Weeks of scraping 40+ heterogeneous
sources to measure a quantity whose quarterly proxy is a coin flip, in a programme where the
last 27 experiments have all failed out of sample.

**What would change my mind:** evidence that the effect is concentrated in the first 1–2 weeks
after disclosure. That is untestable here, but it is testable cheaply on a *narrow* slice —
pick the ~40 largest AMCs' single most recent monthly filing, build one cross-section, and
check whether the freshest signal separates. One month of data, one afternoon, instead of a
full historical pipeline. If that cross-section is flat, the idea is closed for good.
