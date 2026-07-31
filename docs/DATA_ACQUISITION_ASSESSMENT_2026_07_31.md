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
| 3. PIT analyst consensus | **not obtainable free** | — | do not attempt |
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

## 3. PIT analyst consensus — not obtainable free, do not attempt

Gen-1's R01–R08 family was already marked DATA-BLOCKED with "0/448 relevant columns", and that
verdict stands. Point-in-time consensus estimates are the core product of Refinitiv/I-B-E-S,
Bloomberg and FactSet, and are priced accordingly.

**Why the free workarounds fail:**
- Screener.in / Trendlyne / Tickertape surface *current* consensus, not point-in-time. Using
  today's consensus as history is exactly the look-ahead bug that poisoned the `val_*` family
  (see `reports/dataset_creation/`, "current-day Screener metadata broadcast into history").
  **Scraping these to build a PIT series would reintroduce a bug you already fixed.**
- Their terms of service also generally prohibit systematic scraping. I am not going to
  recommend building on that.

**Action: leave closed.** This is the one gap where the honest answer is that the data costs
money and there is no sound free substitute.

---

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
