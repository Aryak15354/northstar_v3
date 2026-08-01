# Free Data Sourcing Assessment — the four gaps Gen-11 named

```
Date:     2026-07-31
Context:  Gen-11 closed with "a genuinely new data source is the only open direction",
          naming four: options-implied vol surface, intraday microstructure,
          PIT analyst consensus, supply-chain/shipping.
Constraint: no paid data.
```

## Headline: one of the four is already on your disk, unused

| gap | verdict | cost | effort |
|---|---|---|---|
| **1. Options-implied vol surface** | **ALREADY HAVE IT — 2.0 GB, 2010–2026** | ₹0 | **build a feature extractor, no acquisition** |
| 2. Intraday microstructure | partially obtainable, **forward-only** | ₹0 | medium; no free deep history exists |
| 3. PIT analyst consensus | ~~not obtainable free~~ **CORRECTED — obtainable, 92% coverage, forward-only** | ₹0 | **collector built and running** |
| 4. Supply-chain / shipping | obtainable free, but **low prior** | ₹0 | low effort, low expected value |

---

## 1. Options-implied vol surface — you already have 17 years of it

`data/raw/fo_bhav/` holds the **complete NSE F&O bhavcopy archive: 4,075 files, 2.0 GB,
2010 → 2026**, every trading day. This is the full options chain, not a summary.

**Verified working end-to-end** (2026-07-16, computed live):

```
20,859 liquid contracts that day, 215 underlyings
IV solved for 503/529 contracts on a 3-name test

  HDFCBANK  spot  808.3   ATM IV 24.6%   skew +2.6%   term 28.6% -> 25.1% -> 25.5%
  INFY      spot 1082.2   ATM IV 33.1%   skew +5.0%   term 38.9% -> 34.7% -> 32.8%
  RELIANCE  spot 1296.0   ATM IV 25.3%   skew -1.5%   term 31.1% -> 26.2% -> 24.8%
```

Fields present: `StrkPric`, `XpryDt`, `OptnTp` (CE/PE), `SttlmPric`, `OpnIntrst`,
`ChngInOpnIntrst`, `TtlTradgVol`, and from 2025 also `UndrlygPric`.

**Two format eras**, both usable:
- **2010–2024**: 16 columns, `STRIKE_PR` / `OPTION_TYP`, **no underlying price** — join spot
  from `data/raw/prices_daily/` (5,528 files already on disk).
- **2025–2026**: 34 columns, `StrkPric` / `OptnTp`, `UndrlygPric` included.

### Why this is a genuinely new information source, not a repeat

Gen-11 killed **futures** open interest (`fut_oi_*`, share-positive 50.0%). This is different
data answering a different question. Futures OI is positioning. The **options surface is the
market's risk-neutral forward distribution** — level, asymmetry and term structure of expected
volatility. Nothing in the 603-column panel encodes it.

Derivable stock-level weekly features, none of which exist in the panel today:

| feature | what it means |
|---|---|
| ATM IV | forward expected volatility |
| **IV − realised vol (variance risk premium)** | what people pay for insurance vs what it costs |
| **25-delta skew** (OTM put IV − OTM call IV) | crash-fear asymmetry; the classic equity signal |
| term-structure slope | near vs far expected vol; stress indicator when inverted |
| put/call OI and volume ratio | positioning (`G8-05` found PCR IC +0.0093, real but sub-materiality — **at index level only**; this is per-stock) |
| IV rank / IV percentile vs own 52w | rich/cheap vol |
| OI-weighted strike dispersion | disagreement about where price ends up |

**The variance risk premium and skew are the two with the strongest priors** — both are
well-documented cross-sectional equity predictors internationally, and neither has ever been
tested here.

**Action: no acquisition needed. Build the extractor.** ~1,100 weekly snapshots to match the
panel's frequency.

---

## 2. Intraday microstructure — forward-only, and be honest about that

**Free deep history does not exist.** NSE does not publish historical tick or minute data for
free; vendors who have it charge for it. Anyone offering "free NSE historical intraday" is
either redistributing in breach of NSE's terms or serving reconstructed/unreliable data.

**What you can do free, going forward:**
- **Upstox API** — already integrated (`src/options/upstox_adapter.py`, `.env.options`, and a
  verified working live path). Intraday candles are available within its rate limits. This
  accrues history from the day you start; it does not backfill.
- **NSE daily deliverable-position data** — already on disk (`data/raw/delivery/`, 1,686 files).
  This is the *daily* residue of intraday behaviour and is the closest free proxy you have.
- **Participant-wise OI** — already on disk (`data/raw/participant_oi/`, 1,608 files). Note
  Gen-11 established these are **date-constant** (market-level), so they cannot generate
  cross-sectional IC. Useful only as a regime/timing input.

**Honest assessment:** starting a forward collection now yields a usable sample in 2–3 years.
That is a real option but not a near-term one. **Do not prioritise this above §1.**

---

## 3. PIT analyst consensus — I WAS WRONG. Corrected 2026-07-31.

**My original verdict here was "not obtainable free — do not attempt". That was asserted from
priors, not measured, and it is wrong.** Yahoo Finance (via `yfinance`) carries analyst data
for Indian equities, and coverage on the live 493-name universe is **455/493 = 92%**.

### What is and is not point-in-time — the distinction that actually matters

**NOT PIT** (today's values only; writing them backwards is the `val_*` look-ahead bug):
`numberOfAnalystOpinions`, `targetMedianPrice`, `recommendationKey`, estimate *levels*.

**GENUINELY PIT-USABLE as of the collection date:**
- **`eps_revisions`** — counts of analysts revising up/down over the trailing 7 and 30 days.
  A *change* measure: "how many revised up in the last 30 days, as of today" is a legitimate
  as-of-today feature. **This is exactly the analyst-revision-breadth construct Gen-1's
  R01–R08 family wanted and was blocked on ("0/448 relevant columns").**
- **`eps_trend`** — the consensus EPS estimate as it stood 7/30/60/90 days ago. A real, short
  backward window; differences give revision *magnitude*.

**NOT AVAILABLE for Indian names:** `upgrades_downgrades` returns an empty frame — there is no
dated broker-action history. That part of my original assessment stands.

### The binding constraint is history, not access

**You cannot backfill.** Each weekly run appends one dated snapshot carrying a 90-day internal
lookback. A usable PIT panel accrues *forward* from the first run. The 90-day window is a head
start, not a substitute for waiting. At weekly frequency, ~30 snapshots (7 months) before the
sign-stability screen has anything to chew on.

### First snapshot — collected 2026-07-31

`data/processed/analyst_consensus/consensus_2026W31.parquet`, 493 rows, **92% coverage**:

```
target_upside          455 non-null   median +13.1%
rec_bull_share         455 non-null   median  74.1%   <- sell-side optimism, as expected
eps_rev_mag_30d        196 non-null   median  +0.79%
eps_rev_net_30d        339 non-null   median   0.00
```

### A construction flaw the first snapshot exposed

The obvious breadth ratio `(up − dn)/(up + dn)` is **degenerate for thinly-covered names**.
Most Indian stocks get at most one revision a month, so it collapses to exactly ±1 — of 146
names with any revision, **90 were −1.0 and 49 were +1.0**, only 4 distinct values in total.
It carries almost no cross-sectional gradation.

Fixed to `eps_rev_net_scaled_30d` = (up − dn) / n_analysts, which separates "1 of 2 analysts
cut" from "1 of 30 analysts cut" — **66 distinct values instead of 4**. The raw counts were
stored, so the existing snapshot was recomputed without re-fetching.

### On the other sources you listed

Trendlyne, Moneycontrol, MarketScreener and Investing.com sit behind Cloudflare and
JavaScript-rendered tables, and their terms prohibit systematic scraping. I have not built
against them and would not — `yfinance` reaches a public endpoint through a standard library
and gets 92% coverage, so the ToS-violating route buys nothing. FMP's free tier (250 calls/day)
would need two days per 493-name snapshot and its India coverage is thinner than Yahoo's.

**Action: run `scripts/gen11/collect_analyst_consensus.py` weekly.** It is idempotent per ISO
week and never overwrites a snapshot.

## 4. Supply-chain / shipping — free, but the prior is poor

Genuinely free and legitimate:
- **UN Comtrade API** — bilateral trade flows, free tier, registration only.
- **India DGCI&S / Ministry of Commerce** — monthly commodity-level import/export, free.
- **Ministry of Ports, Shipping & Waterways** — monthly major-port cargo traffic, free.
- **World Bank Pink Sheet** — commodity prices; **already wired**
  (`scripts/fetch_worldbank_pinksheet.py`).
- **FRED** — freight/shipping series; **already wired** (`scripts/fetch_fred_series.py`).

**But the prior is low, and the evidence is yours.** Gen-2/3's five-wave macro programme tested
**155 domestic macro indicators** across credit, rates, fiscal, real-economy and valuation and
found *no tradeable signal beyond price/sector/delivery*. Shipping data is more macro of the
same kind: **monthly, national, and not cross-sectional.** Gen-11's screen explains why that
class fails — a national monthly series broadcast across stocks is near date-constant, and
date-constant features cannot generate cross-sectional IC (E2's control returned exactly
+0.0000).

**Action: skip unless you want a market-timing overlay rather than stock selection.**

---

## Recommendation

**Do §1 and nothing else.** It is free, already downloaded, stock-level, forward-looking,
17 years deep, ~215 underlyings per day, and completely untested in this programme. The other
three are respectively slow, impossible-free, and low-prior.

**Then triage it with Gen-11's screen before building any strategy** — the sign-stability test
takes minutes and correctly ranked delivery #1 and momentum #3 of 25 features. If ATM IV, skew
and the variance risk premium come back near 50% share-positive, stop there and the answer is
cheap. If any lands where delivery did (62%), it goes through the full A0–A7 gate.

## A note on scraping generally

Everything recommended above is either **already on your disk**, an **official government or
exchange publication**, or an **API you already hold credentials for**. I have not recommended
scraping any site whose terms prohibit it, and I would not — the two places where scraping is
the only route (§3's consensus vendors) are also the two where it would breach terms *and*
reintroduce a look-ahead bug you have already fixed once.

---

## BUILT — 2026-07-31

The §1 recommendation is done. `data/processed/iv_surface_weekly.parquet`:

```
112,706 rows | 847 weeks | 427 underlyings | 2010-01-08 .. 2026-07-17
median 141 names/week (212 in the recent era)

  iv_atm            100% coverage   median 31.7%
  iv_skew_25d        94%            median +2.2%   <- correctly signed: equity put skew
  iv_term_slope      64%            median +2.9%
  pcr_oi            100%            median 0.554
  pcr_vol           100%            median 0.429
  oi_concentration  100%            median 0.106
```

Sanity checks that passed without being tuned for: median skew is **positive** (equity options
carry put skew, as they must); IV spikes in the right places (Sept 2011 Euro crisis 39.7%,
March 2021 45.5%) and troughs in calm markets (Dec 2025 20.1%).

**Not yet tested for signal.** Next step is Gen-11's sign-stability screen, then the A0–A7 gate
if anything clears. `vrp` (IV − trailing realised vol) still needs the realised-vol join from
PANEL-A and is the feature with the strongest external prior.
