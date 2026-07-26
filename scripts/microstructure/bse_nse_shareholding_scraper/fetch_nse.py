#!/usr/bin/env python3
"""NSE shareholding-pattern fetcher.

Reuses `scripts/nse_csv_scraper_common.py` verbatim (create_nse_session, bootstrap_nse_session,
nse_request) -- this is the already-working session/cookie/retry infrastructure this repo's other
NSE scrapers (fetch_nse_microstructure.py, scrape_nse_*.py) rely on, not reinvented here.

ENDPOINT DISCLOSURE: this environment's browsing policy blocks nseindia.com, so the exact URL/params
below could not be verified against a live response in this session. `/api/corporate-share-holdings-
master` is the endpoint NSE's own "Corporate filings > Shareholding Pattern" page calls, per its
publicly observable structure -- but **run `run_scrape.py --verify` first** and inspect the raw cached
response for one ticker before committing to the full backfill. If the shape differs, only this file
needs to change; nothing downstream does (the parser and cache are endpoint-agnostic).
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
