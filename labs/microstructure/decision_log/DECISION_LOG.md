# Microstructure Lab — Decision Log

Append-only.

---

## 2026-07-26 — Experiments closed this session

- **MICRO-001** (`labs/microstructure/results/MICRO-001/FINDINGS.md`) — modeled realistic exit-fill
  unwind for the liquidity-gradient tilt, replacing G8-12's crude 0-to−2.29%/yr bound with a point
  estimate + CI from real historical volume/price behavior. A real, self-caught unit-conversion bug
  (10,000,000x notional inflation) was found and fixed before reporting; the false-start outputs are
  preserved in `results/MICRO-001/false_start_2026-07-26/`, not deleted. Closed **REJECTED**
  (materiality hypothesis specifically): modeled drag differential is −0.015%/yr, two orders of
  magnitude below the materiality bar — execution-realism at delisting exits is ruled out as a
  material confound on the liquidity gradient.
- **MICRO-002** (`labs/microstructure/protocols/MICRO-002_DATA_ACQUISITION.md`) — assessed historical
  institutional-ownership coverage 2010-2022. Found the gap is total (not thin): pre-2023 records are
  a side artifact of the delisted-backfill effort, not systematic coverage. Three sourcing options
  documented (Screener.in paid tier, BSE/NSE Regulation-31 archive scraping ~37,000 lookups,
  commercial vendor) with an explicit recommendation ordering. Closed **INCONCLUSIVE** — genuine data
  gap, no acquisition attempted without the user's explicit go-ahead (particularly for the archive-
  scraping option, given its third-party footprint).

## 2026-07-26 (same day) — MICRO-002 update: Option 2 authorized, scraper built

The user authorized BSE/NSE Regulation-31 archive scraping (Option 2) with guardrails (throttled,
robots.txt-respecting, cache-before-parse, resumable, re-diagnose after). A fresh, broader local-data
sweep (requested by the user, in case a prior BSE/NSE backfill had been missed) confirmed the gap is
real — no shareholding-pattern archive exists locally beyond what was already found. Built
`scripts/microstructure/bse_nse_shareholding_scraper/` (rate limiter, robots.txt gate, raw-response
cache, resumable checkpoint, 17 passing parser unit tests). **Not yet executed**: this session's
browsing tool is policy-blocked from both exchange domains, so the exact endpoint URLs are
best-effort and need live verification (`run_scrape.py --verify`) before any real volume is sent —
see `MICRO-002_DATA_ACQUISITION.md` section 5 and the scraper's own `README.md` for the full status
and runbook.

## 2026-07-26 (same day) — live verification run, gap NOT resolved

With the user's go-ahead, a real 2-request verification ran from this sandbox's Bash (the browsing
tool itself stays policy-blocked from both domains). Result: **NSE's endpoint is confirmed working
but confirmed shallow** (a 2010-2022 request for RELIANCE returned only 6 records, all from
late-2021+; a 2015-2016 window returned zero) — the same recent-only ceiling as Screener.in's free
tier, from a different vendor. **BSE's guessed endpoint is confirmed wrong** (301-redirects to a
sales page, not shareholding data); the real endpoint needs a live browser session this sandbox
cannot provide. See `MICRO-002_DATA_ACQUISITION.md` section 6 for full detail.

**Updated conclusion: this scraping approach, as built, does not close the 2010-2022 gap.** The two
undone leads worth a future look: parsing the XBRL filing archive linked from each NSE record (if
NSE's own filing index reaches back further than the summary API), and finding BSE's real endpoint
via a browser session outside this sandbox. Neither was pursued further this session.

## Open item carried forward

The 2010-2022 institutional-ownership gap remains open. `ALPHA-002` and any future experiment should
continue to treat it as unresolved — do not assume a future scraper run has closed it without
re-running section 1's coverage diagnostic against real landed data first.
