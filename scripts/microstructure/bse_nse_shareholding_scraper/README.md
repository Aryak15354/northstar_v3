# MICRO-002 — BSE/NSE Shareholding-Pattern Backfill Scraper

Built 2026-07-26, per the user's explicit go-ahead on `labs/microstructure/protocols/
MICRO-002_DATA_ACQUISITION.md`'s Option 2 (BSE/NSE Regulation-31 archive scraping), with the
guardrails the user specified: throttled/rate-limited, robots.txt-respecting, raw-response caching
before parsing, resumable/incremental logging, and a re-run of the MICRO-002 diagnostic once the data
lands.

**Local-data check done first, per the user's request**: an Explore-agent sweep of the whole repo
(directory names, script docstrings, `git log --all`) confirmed no BSE/NSE Regulation-31
shareholding-pattern archive exists locally beyond what `MICRO-002_DATA_ACQUISITION.md` already
found. `data/raw/exchanges/{bse,nse}/` has pledge/bulk-deals/announcements/credit-ratings data — real,
but not shareholding pattern. This scraper is a genuine data-acquisition task, not redundant with
anything already on disk.

## Verified live 2026-07-26 — read this before running anything

The interactive browsing tool in this session is blocked from `bseindia.com`/`nseindia.com` by
environment policy, but a plain `requests`/`curl` call from the same sandbox's Bash was not — so a
real, live 2-request verification WAS run here (with the user's explicit go-ahead), and the results
are concrete, not guesses:

**NSE — CONFIRMED WORKING, but with a real, load-bearing limitation.** `/api/corporate-share-
holdings-master` returned a genuine filing for RELIANCE (promoter 50.49%, public 49.51%, real
submission date) — captured as ground truth in
`test_parse.py::test_parse_nse_json_real_verified_payload`. **But a request spanning 2010-2022
returned only 6 records, all from late-2021 onward; a 2015-2016 window returned zero.** This endpoint
does not reach the 2010-2022 gap by itself — it has the same kind of recent-only ceiling already
documented for Screener.in's free tier, just from a different vendor. It also only returns
promoter/public percentages, not the FII/DII/govt breakdown; each record's `xbrl` URL points to the
full filing, which likely has that breakdown — parsing it is a real follow-up task, not built here.

**BSE — CONFIRMED WRONG.** The guessed `ddlqtrid` endpoint 301-redirects to a generic BSE sales
page (`/members/showinterest.aspx`), not shareholding data. `bseindia.com/robots.txt` also returns
the site's Angular SPA shell (HTML, not real robots.txt directives) — `robots_check.py` now detects
this via Content-Type and fails closed honestly rather than misparsing it, but the underlying problem
is that **the real BSE endpoint has not been found.** Finding it needs an actual browser session on
BSE's live shareholding-pattern page with dev-tools network inspection, which this sandbox cannot do.

**Bottom line: this scrape, as currently scoped, does not solve MICRO-002's 2010-2022 gap.** The
honest state of play is: NSE gives a working but shallow (recent-only) source; BSE's real endpoint is
still unknown; and the deeper regulatory archive (XBRL filings, or a genuinely historical NSE/BSE
endpoint) has not been located. See `labs/microstructure/protocols/MICRO-002_DATA_ACQUISITION.md`
section 6 for the full, current recommendation.

**Still run `--verify` first if anything here changes** (a fixed BSE endpoint, or evidence of a
deeper NSE archive): it does exactly two requests and prints the raw response for inspection before
any volume is sent. If a response doesn't look like real promoter/FII/DII/public percentages:
1. Fix the URL/params in `fetch_bse.py` or `fetch_nse.py` — nothing else needs to change.
2. Update `_CATEGORY_KEYWORDS` in `parse.py` if BSE's real field/category labels differ from the
   still-unverified guesses there (see that file's own disclosure comment).
3. Re-run `python3 test_parse.py` (19 tests, network-free, includes the one real ground-truth
   fixture) — add a new test using any new real payload shape you capture.

## The guardrails, and where each one lives

| Guardrail (as specified) | Where it's implemented |
|---|---|
| Throttle/rate-limit | `rate_limiter.py` — thread-safe token bucket, shared across all workers so `--qps` is a hard combined ceiling regardless of `--workers` |
| Respect robots.txt / ToS | `robots_check.py` — hard gate, runs at the start of every invocation (not just once), fails closed if robots.txt can't be fetched. **Caveat observed this session**: a plain fetch of `bseindia.com/robots.txt` returned the site's SPA shell HTML, not robots.txt content — some sites 404-catch-all to their front end. Confirm `robots_check.py`'s output looks like a real robots.txt parse before trusting the PASS, and check both domains' actual `robots.txt` content manually once. |
| Cache raw responses before parsing | `cache.py` — every fetch writes raw bytes to `data/raw/exchanges/shareholding_pattern_scrape/{source}/{ticker_or_code}/{quarter}.{json,csv}` atomically (write-tmp-then-replace) *before* `parse.py` ever runs. A parser bug or a wrong keyword guess never requires re-scraping — `python3 parse.py nse` re-runs any time, free. |
| Resumable, incremental logging | `checkpoint.py` — one row per (source, identifier, quarter) with status `done`/`empty`/`failed` and a retry count, atomic writes. Progress prints every 100 requests. Ctrl-C and re-run `run_scrape.py` any time; already-`done`/`empty` units are skipped, `failed` units retry up to `--max-consec-fail`-independent per-unit cap (3, in `checkpoint.should_attempt`). |
| Re-run MICRO-002 diagnostic once data lands | See "After the scrape" below. |

## Running it for real

```bash
# small, cheap sanity check first — a handful of tickers, only the most recent 2 years
python3 run_scrape.py --source both --limit-tickers 5 --start 2021-01-01 --end 2022-12-31

# the actual backfill, resumable
python3 run_scrape.py --source both --qps 1.5 --workers 4 --start 2010-01-01 --end 2022-12-31
```

**Universe**: 532 tickers, derived entirely from `data/kaggle_upload/panel_a_weekly.parquet` (the
panel itself, not a stale universe snapshot — two other candidate sources,
`data/reference/nse_universe_history.parquet` and `data/universe/universe_snapshots.parquet`, were
checked and rejected because both only cover 2021+, which would have silently under-covered exactly
the delisted names this scrape exists to reach). Run `python3 universe.py` to regenerate
`universe_targets.csv` and see the current coverage numbers. **BSE-code coverage is 83% (442/532)** —
real, not a bug: BSE codes for delisted names come from local Screener-derived metadata that itself
only has partial coverage. **NSE-path coverage is 100% of the universe** (needs only a symbol, no
code) — prioritize the NSE path if BSE coverage gaps matter for your timeline.

**Quarters**: 2010-2022, quarter-end dates with an `availability_date` estimate of quarter-end + 21
days (SEBI LODR Regulation 31(1)(b)'s filing deadline) — a documented assumption, not a measured
filing date; replace it with the real filing timestamp once you've seen what a real response contains.

**Expected runtime**: at `--qps 1.5`, ~37,000 requests (532 tickers × 48 quarters, roughly — BSE path
is smaller given 83% code coverage) is on the order of 7 hours for one source, run both sources
concurrently or back-to-back. `--workers` only hides per-request latency; it does not raise the
combined rate past `--qps`.

**BSE quarter-ID mapping — a known gap, disclosed, not silently worked around**: BSE's shareholding
pattern API needs a `qtrid`, not a calendar quarter, and the mapping between them is company-specific
(fetched via the `ddlqtrid` endpoint, cached once per company in `_qtrid_list.json`). `fetch_bse.py`'s
`_do_bse` currently tries the calendar `quarter.label` directly as a fallback `qtrid` value, which is
almost certainly wrong once you see a real `ddlqtrid` response — **this is the first thing to fix
after `--verify`**: parse the cached `_qtrid_list.json` for each company and map calendar quarters to
the real `qtrid` values before the full BSE run, rather than relying on the current placeholder.

## After the scrape

```bash
# parse whatever's cached so far into the canonical schema (network-free, re-runnable any time)
python3 parse.py nse > /tmp/nse_parsed_preview.txt
python3 parse.py bse > /tmp/bse_parsed_preview.txt
```
`build_normalized_table(source)` in `parse.py` returns a DataFrame with the same columns as
`data/canonical/fundamentals/shareholding_quarterly.parquet` (`promoter_pct`, `fii_pct`, `dii_pct`,
`public_pct`, `govt_pct`, `n_shareholders`) plus `record_origin="{source}_scrape"` — merge into the
canonical parquet by `(ticker, quarter)`, keeping `record_origin` so provenance is never silently
lost (per this whole programme's never-silently-rewrite-history discipline).

**Then, per the user's own instruction: re-run MICRO-002's diagnostic** (the coverage-by-year table
in `labs/microstructure/protocols/MICRO-002_DATA_ACQUISITION.md` section 1) against the merged data,
to confirm the 2010-2022 cutover is actually resolved before any ALPHA/MSCI work that depends on it
(`ALPHA-002`, `MICRO-002` itself) treats the gap as closed. If real coverage lands meaningfully below
532×48 (rate limits, missing quarters, endpoint gaps for older filings), report the actual achieved
coverage honestly rather than treating a partial backfill as a full resolution — the same standard
every other closed experiment this session was held to.

## Files

- `universe.py` — target list (network-free, from local data)
- `quarters.py` — quarter list + availability-date estimate
- `rate_limiter.py` — token-bucket throttle + circuit breaker
- `robots_check.py` — hard gate, checked every run
- `cache.py` — raw-response disk cache (write-before-parse)
- `checkpoint.py` — resumable per-unit progress manifest
- `fetch_nse.py` / `fetch_bse.py` — per-exchange fetchers (endpoint URLs need live verification)
- `parse.py` — cache → canonical schema (network-free, keyword-matching logic unit-tested)
- `test_parse.py` — 19 tests (incl. one real ground-truth NSE fixture), run with `python3 test_parse.py`
- `run_scrape.py` — CLI: `--verify`, then small `--limit-tickers` test, then the full run
