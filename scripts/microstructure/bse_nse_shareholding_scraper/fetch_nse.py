#!/usr/bin/env python3
"""NSE shareholding-pattern fetcher.

Reuses `scripts/nse_csv_scraper_common.py` verbatim (create_nse_session, bootstrap_nse_session,
nse_request) -- this is the already-working session/cookie/retry infrastructure this repo's other
NSE scrapers (fetch_nse_microstructure.py, scrape_nse_*.py) rely on, not reinvented here.

ENDPOINT STATUS, updated 2026-07-26 after a live check from this sandbox's Bash (the interactive
browsing tool is policy-blocked from nseindia.com, but a plain `requests`/`curl` call was not):
**CONFIRMED WORKING.** A real request for RELIANCE returned a genuine filing record (promoter 50.49%,
public 49.51%, real submission date) -- see `test_parse.py::test_parse_nse_json_real_verified_payload`
for the exact captured fixture.

**CONFIRMED LIMITATION, load-bearing for MICRO-002's actual goal**: this endpoint only serves
recent history. A request spanning 2010-2022 for RELIANCE returned just 6 records, all from
late-2021 onward; a 2015-2016 window returned zero. **This endpoint alone does not reach the
2010-2022 gap** -- it appears to have the same kind of recent-only ceiling already documented for
Screener.in's free tier (`MICRO-002_DATA_ACQUISITION.md` section 3, Option 1), just via a different
vendor. Whether NSE exposes a genuinely deeper historical archive through some other endpoint is an
open question this session did not resolve (further guessing against live NSE infrastructure without
a browser session to observe real network calls was judged not worth the additional requests).

**Also confirmed**: this summary record has `promoter_pct`/`public_pct` only -- no FII/DII/govt
breakdown. Each record includes an `xbrl` URL to the full regulatory filing, which likely does have
that breakdown; parsing it is a real follow-up task, not built here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nse_csv_scraper_common import bootstrap_nse_session, create_nse_session, nse_request  # noqa: E402

NSE_REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern"
NSE_API = "https://www.nseindia.com/api/corporate-share-holdings-master"


def make_session():
    s = create_nse_session(referer=NSE_REFERER)
    bootstrap_nse_session(s, referer=NSE_REFERER)
    return s


def fetch_one(session, symbol: str, from_date: str, to_date: str, *, max_attempts: int = 4) -> bytes:
    """from_date/to_date: 'DD-MM-YYYY' (NSE's own date format convention on this API family).
    Returns raw response bytes -- caller writes to cache before parsing."""
    params = {"index": "equities", "symbol": symbol, "from_date": from_date, "to_date": to_date}
    r = nse_request(session, NSE_API, params=params, referer=NSE_REFERER, max_attempts=max_attempts)
    return r.content


def date_window_for_quarter(quarter_end, availability_date, pad_days: int = 30) -> tuple[str, str]:
    """A window around the filing's availability date -- NSE's API is date-range based, not a single
    as-of date, so pad on both sides to be sure the actual filing falls inside the window even if the
    company filed a few days early or the deadline estimate is slightly off."""
    start = availability_date - pd.Timedelta(days=pad_days)
    end = availability_date + pd.Timedelta(days=pad_days)
    return start.strftime("%d-%m-%Y"), end.strftime("%d-%m-%Y")
