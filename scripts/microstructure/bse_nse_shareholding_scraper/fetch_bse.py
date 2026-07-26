#!/usr/bin/env python3
"""BSE shareholding-pattern fetcher.

Mirrors the proven dual-path resilience pattern already working in this repo's
`scripts/scrape_bse_promoter_pledge.py` (same `api.bseindia.com` host, same header set, same
retry/backoff-on-403/429 logic) rather than inventing a new one: primary JSON API, CSV-download
fallback if the JSON path comes back empty.

ENDPOINT STATUS, updated 2026-07-26 after a live check from this sandbox's Bash (the interactive
browsing tool is policy-blocked from bseindia.com, but a plain `requests`/`curl` call was not):
**CONFIRMED WRONG.** `ddlqtrid`, guessed by analogy to the working `ConsolidatePledge` pattern,
returns an HTTP 301 redirect to `https://www.bseindia.com/members/showinterest.aspx` -- a generic
sales/contact page, not shareholding data. This is not a permissions issue (see robots_check.py's own
disclosure below) -- the path itself does not resolve to real data on BSE's current infrastructure.
`www.bseindia.com/robots.txt` also returned the site's Angular SPA shell (HTML, not robots.txt
directives), which is a separate, real quirk worth knowing about but not the cause of the wrong
endpoint.

**The real BSE shareholding-pattern endpoint has NOT been found.** Discovering it needs an actual
browser session on bseindia.com's live shareholding-pattern page with dev-tools network inspection --
this sandbox cannot do that (the browsing tool is domain-blocked) and guessing further via blind
curl probes against BSE's live infrastructure was judged not worth the additional requests. **Do not
run the BSE path until this is fixed** -- `run_scrape.py --verify` will keep failing at the robots.txt
gate (which is, correctly, refusing to proceed against paths that don't resolve to real data) until a
real endpoint replaces the guess below.
"""
from __future__ import annotations

import time

import requests

QTR_LIST_URL = "https://api.bseindia.com/BseIndiaAPI/api/ddlqtrid/w?scripcode={code}"
SHP_URL = "https://api.bseindia.com/BseIndiaAPI/api/ShareholdingPattern/w?scripcode={code}&qtrid={qtrid}"
CSV_FALLBACK_URL = "https://api.bseindia.com/BseIndiaAPI/api/DwnldExcel_Shp/w?scripcode={code}&qtrid={qtrid}&flag=ShP"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.bseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get_with_backoff(session: requests.Session, url: str, *, retries: int = 6,
                      timeout: int = 45) -> tuple[requests.Response | None, bool]:
    """Returns (response_or_none, was_blocked). Mirrors scrape_bse_promoter_pledge.py's `_safe_get`."""
    backoff = 1.0
    blocked = False
    for _ in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code in {403, 429}:
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if r.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if "access denied" in (r.text or "")[:300].lower():
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            return r, blocked
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return None, blocked


def fetch_available_quarters(session: requests.Session, bse_code: str) -> tuple[bytes | None, bool]:
    """Raw response listing this company's available filed quarter IDs -- caller writes to cache,
    then the parser extracts {qtrid: quarter_desc} pairs from it."""
    r, blocked = _get_with_backoff(session, QTR_LIST_URL.format(code=bse_code))
    return (r.content if r is not None else None), blocked


def fetch_shareholding(session: requests.Session, bse_code: str, qtrid: str
                       ) -> tuple[bytes | None, bool, str]:
    """Returns (raw_bytes_or_none, was_blocked, source_path) where source_path is 'json' or 'csv' --
    the parser needs to know which shape it's looking at."""
    r, blocked = _get_with_backoff(session, SHP_URL.format(code=bse_code, qtrid=qtrid))
    if r is not None and r.content and len(r.content) > 20:
        return r.content, blocked, "json"
    # fallback, same resilience pattern as the working pledge scraper
    r2, blocked2 = _get_with_backoff(session, CSV_FALLBACK_URL.format(code=bse_code, qtrid=qtrid), retries=4)
    if r2 is not None and r2.content:
        return r2.content, (blocked or blocked2), "csv"
    return None, (blocked or blocked2), "json"
