# MICRO-002 — Historical Institutional Ownership 2010–2022: Data Acquisition Assessment

```
Version:            v1.0
Status:             Frozen (assessment complete; acquisition path pending user decision)
Freeze Date:        2026-07-26
Owner:              Aryak
Lab:                Microstructure
Depends On:         results/gen8/G9-02/G9-02_FINDINGS.md (the gap this assesses),
                    data/canonical/fundamentals/shareholding_quarterly.parquet
```

**This is a data-acquisition task, not a modeling task, per this lab's charter. No simulation was
built around the gap.** The finding below is more precise than G9-02's own characterization of the
problem, and it changes what the right next step is.

---

## 1. What actually exists locally — checked directly, not assumed

`data/canonical/fundamentals/shareholding_quarterly.parquet`: 7,531 rows, 2016-02-14 through
2026-05-15. On its face this looks like it already reaches back to 2016. It does not, in the sense
that matters for G9-02's regression.

| Period | Distinct tickers/year | `record_origin` |
|---|---|---|
| 2016 | 86 | **100% `delisted_screener`** |
| 2017 | 93 | 100% `delisted_screener` |
| 2018 | 91 | 100% `delisted_screener` |
| 2019 | 63 | `delisted_screener` + some `active_screener` |
| 2020 | 54 | mixed |
| 2021 | 39 | 100% `delisted_screener` |
| 2022 | 21 | 100% `delisted_screener` |
| **2023** | **506** | **100% `active_screener`** |
| 2024 | 517 | `active_screener` |
| 2025 | 537 | `active_screener` |

**The pre-2023 records are not a sparse version of the same coverage — they are a different
collection entirely: a side artifact of the delisted-company price backfill effort, scraped for a
small, unsystematic set of already-delisted names, not for the live tradeable universe.** Systematic,
near-full-universe shareholding coverage (500+ of ~779 tickers per year) begins precisely in 2023,
which is when `active_screener` scraping infrastructure was built and run. There is no partial,
extendable signal sitting in the existing data between 2010 and 2022 for the active universe — the
gap is total, not thin.

**This sharpens G9-02's finding.** G9-02 found the joint liquidity/ownership regression collapses to
112 weeks, all 2023–2025. This assessment establishes *why*, precisely: it is not that older records
exist but fail some other filter — the active-universe records simply do not exist before 2023.

## 2. Local investigation of alternative already-on-disk sources

Checked and ruled out before considering external acquisition:
- `data/raw/vendors/nse_filings/` (370 tickers) — investor presentations and earnings transcripts
  only. No shareholding-pattern (Regulation 31) filings.
- `data/raw/vendors/nse_xbrl/` (20,062 files) — financial statement XBRL, not shareholding pattern.
- `scripts/backfill_nse_corporate_filings.py` — backfills promoter pledges and announcements only;
  never touched shareholding pattern disclosures.
- No other local archive of quarterly shareholding data was found.

## 3. The three sourcing options, assessed concretely

### Option 1 — Screener.in paid/historical export tier

The existing `active_screener` scrape (2023+) matches exactly the depth Screener.in's **free** tier
typically exposes on a company's live shareholding page (roughly the trailing 8–12 quarters). This is
consistent with the observed cutover. **A paid Screener.in subscription may expose a longer history
per company**, but this cannot be verified without an actual account — I cannot check a paywalled
tier's contents, and I will not attempt to log in or provide payment details, per standing policy.
**This is the cheapest option if it works, and the only way to know is for the user to check what
their (or a paid) Screener.in account actually shows for a sample company's shareholding history.**

### Option 2 — BSE/NSE corporate-filings archives (Regulation 31 disclosures)

Real, public, and technically feasible: quarterly shareholding pattern is a mandatory regulatory
disclosure, filed per-company per-quarter, and both exchanges maintain searchable filing archives.
**Scale: ~779 tickers × ~48 quarters (2010–2022) ≈ 37,000 individual filing lookups**, each requiring
locating the correct filing (PDF or XBRL) and parsing the shareholding table out of it — format has
almost certainly changed across 12+ years, so this is not a single fixed parser.

**This was not attempted in this session.** Bulk-scraping an exchange's own regulatory archive at
this volume is a real-world action with actual footprint on a third party — request volume, possible
rate limits, and terms-of-service considerations — and per this repository's own standing safety
practice for consequential external actions, this needs your explicit go-ahead before any code hits
those servers, not an autonomous decision on my part.

### Option 3 — Commercial vendor (Ace Equity, Capitaline, Bloomberg)

Per the restructuring prompt's own explicit instruction: **flagging this to you directly rather than
assuming it's unavailable.** These vendors package exactly this series (historical shareholding
pattern, point-in-time) cleanly, and if you have institutional access to any of them, this is very
likely the fastest and most reliable path — a single bulk export rather than 37,000 scraped filings.
I have no way to check whether you have such access; only you can answer that.

## 4. Recommendation

**Priority order given the assessment above: Option 3 (if you have vendor access) > Option 1 (cheap
to check, ask about it first) > Option 2 (real, but the largest undertaking, and needs your
authorization before any scraping begins given the volume and third-party footprint involved).**

No acquisition was performed in this session. This document is the honest coverage assessment and
sourcing plan the restructuring prompt asked for; the next action is yours.

## 5. Update, 2026-07-26 (same day) — Option 2 authorized, scraper built, not yet executed

The user authorized Option 2 (BSE/NSE Regulation-31 archive scraping) with guardrails: throttled,
robots.txt-respecting, cache-before-parse, resumable, and a re-run of section 1's diagnostic once
data lands. **Before building anything, a fresh local-data check was run first** (per the user's own
request, in case a prior BSE/NSE backfill existed that this document's section 2 missed) — an
Explore-agent sweep of the whole repo, including `git log --all`, confirmed no additional
shareholding-pattern archive exists; `data/raw/exchanges/{bse,nse}/` (checked directly this time, not
just `nse_filings`/`nse_xbrl`) has pledge/bulk-deals/announcements/credit-ratings data, never
shareholding pattern. Section 2's conclusion stands, now on a broader check.

**Built**: `scripts/microstructure/bse_nse_shareholding_scraper/` — a full resumable scraper (rate
limiter, robots.txt hard gate, raw-response cache written before any parsing, atomic resumable
checkpoint, per-exchange fetchers, a schema-matching parser with 17 passing unit tests against
synthetic fixtures). Universe derived from `panel_a_weekly.parquet` itself (532 tickers, not the
~779 estimate this document's section 3 used for scale — that was a rough estimate, this is the real,
verified count), 2010-2022 quarters. Full details and the exact runbook are in that directory's
`README.md`.

**Not yet executed at volume, and not a silent gap**: this environment's browsing tool is
policy-blocked from `bseindia.com`/`nseindia.com`, but with the user's explicit go-ahead, a real
2-request live verification WAS run from this sandbox's Bash (`requests`, not the blocked browsing
tool). The result changes this document's conclusion materially — see section 6.

## 6. Live verification result, 2026-07-26 — the gap is NOT resolved by this approach as scoped

**NSE — confirmed working, but confirmed shallow.** `/api/corporate-share-holdings-master` returned a
real filing for RELIANCE (promoter 50.49%, public 49.51%, genuine submission date) — this is real
data, not a guess; captured as a ground-truth test fixture in the scraper's `test_parse.py`. **But a
request spanning 2010-2022 returned only 6 records, all from late-2021 onward; a 2015-2016 window
returned zero records.** This endpoint has the same kind of recent-only ceiling already documented in
section 3, Option 1 for Screener.in's free tier — it is a different vendor with the same limitation,
not a solution to the 2010-2022 gap. It also only reports promoter/public percentages, not the
FII/DII/govt breakdown this document's target schema wants; each record links to its full XBRL
filing, which likely has that detail — parsing it is a real, undone follow-up task.

**BSE — confirmed wrong, not merely unverified.** The endpoint guessed by analogy to this repo's own
working `ConsolidatePledge` pattern (`ddlqtrid`) 301-redirects to a generic BSE sales/contact page,
not shareholding data. The real BSE shareholding-pattern endpoint has not been found, and finding it
needs a live browser session with dev-tools network inspection on bseindia.com — not available in
this sandbox.

**Updated, honest conclusion**: neither exchange's public API, as currently understood, reaches the
2010-2022 institutional-ownership gap. The most promising undone leads are (a) parsing the XBRL
filing archive linked from each NSE summary record, if NSE's own filing index reaches back further
than the summary API's ~2-year window, and (b) finding BSE's real endpoint via a live browser session
outside this sandbox. **Option 2 (BSE/NSE scraping) is not closed as a direction, but is not the quick
win it looked like on paper** — this document and `scripts/microstructure/bse_nse_shareholding_scraper/
README.md` should both be updated again if either lead is pursued further. Until then, the 2010-2022
gap remains open exactly as characterized in sections 1-3 above.
