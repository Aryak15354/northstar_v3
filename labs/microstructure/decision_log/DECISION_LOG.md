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

## Open item carried forward

Whether to run the verification/full scrape from this sandbox (a plain `curl` reached `bseindia.com`
successfully, unlike the browsing tool) or entirely in a separate environment is still the user's
call, asked and pending as of this entry. Once real data lands, section 1's coverage diagnostic must
be re-run against it before `ALPHA-002` or any other experiment treats the ownership gap as resolved.
