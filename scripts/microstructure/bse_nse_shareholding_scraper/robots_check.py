#!/usr/bin/env python3
"""Check robots.txt for both exchanges before any scraping begins. Hard-fails (refuses to proceed)
if the specific paths this scraper hits are disallowed for a generic user-agent -- this check runs
every time `run_scrape.py` starts, not just once, since robots.txt can change.

QUIRK CONFIRMED 2026-07-26: a plain fetch of `bseindia.com/robots.txt` (and `api.bseindia.com`'s,
which 301-redirects to an unrelated page) returns the site's Angular SPA shell -- real HTML, not
robots.txt directives (BSE's server 200s/redirects any unmatched path to the front end rather than
404ing). Using `urllib.robotparser` naively here would silently parse that HTML as if it were
robots.txt, producing meaningless results in either direction. This module fetches the raw response
itself first and checks Content-Type before handing anything to the parser, so a non-text/plain
response is reported honestly as "no real robots.txt found" (and fails closed) rather than silently
misinterpreted.
"""
from __future__ import annotations

import io
import urllib.robotparser
from dataclasses import dataclass

import requests

USER_AGENT = "Mozilla/5.0 (compatible; research-data-collection)"

# The actual paths this scraper requests. Update this list if a fetcher's URL changes.
BSE_PATHS = [
    "/BseIndiaAPI/api/ShareholdingPattern/w",
    "/BseIndiaAPI/api/ddlqtrid/w",
    "/BseIndiaAPI/api/DwnldExcel_Shp/w",
]
NSE_PATHS = [
    "/api/corporate-share-holdings-master",
    "/companies-listing/corporate-filings-shareholding-pattern",
]


@dataclass
class RobotsResult:
    domain: str
    fetched_ok: bool
    all_allowed: bool
    per_path: dict[str, bool]
    note: str = ""


def check_domain(base_url: str, paths: list[str], *, timeout: int = 15) -> RobotsResult:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        r = requests.get(robots_url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    except Exception as exc:
        return RobotsResult(domain=base_url, fetched_ok=False, all_allowed=False,
                            per_path={p: False for p in paths},
                            note=f"request failed: {exc}")

    content_type = r.headers.get("Content-Type", "").lower()
    if "text/plain" not in content_type or r.history:
        # Real robots.txt is served as text/plain and shouldn't redirect. A different content-type
        # (or a redirect having occurred, per r.history) means this is not a genuine robots.txt --
        # most likely an SPA/catch-all response. Fail closed and say so honestly, rather than
        # feeding arbitrary HTML into a parser that will produce a meaningless allow/disallow.
        return RobotsResult(
            domain=base_url, fetched_ok=False, all_allowed=False,
            per_path={p: False for p in paths},
            note=(f"response at {robots_url} was not a real robots.txt (content-type={content_type!r}, "
                 f"redirected={bool(r.history)}) -- likely an SPA catch-all, not a genuine policy. "
                 f"Failing closed rather than guessing."))

    rp = urllib.robotparser.RobotFileParser()
    rp.parse(io.StringIO(r.text).readlines())
    per_path = {p: rp.can_fetch(USER_AGENT, base_url.rstrip("/") + p) for p in paths}
    return RobotsResult(domain=base_url, fetched_ok=True,
                        all_allowed=all(per_path.values()), per_path=per_path)


def check_all() -> tuple[RobotsResult, RobotsResult]:
    bse = check_domain("https://www.bseindia.com", BSE_PATHS)
    bse_api = check_domain("https://api.bseindia.com", BSE_PATHS)
    nse = check_domain("https://www.nseindia.com", NSE_PATHS)
    # BSE's data actually lives on api.bseindia.com; report both, gate on the api host since that's
    # the one actually requested.
    return bse_api, nse


def assert_allowed_or_raise() -> None:
    bse_api, nse = check_all()
    problems = []
    for r in (bse_api, nse):
        if not r.fetched_ok:
            problems.append(f"{r.domain}: {r.note or 'robots.txt could not be fetched'} -- "
                           f"failing closed, not assuming permission")
        elif not r.all_allowed:
            disallowed = [p for p, ok in r.per_path.items() if not ok]
            problems.append(f"{r.domain}: robots.txt disallows: {disallowed}")
    if problems:
        raise PermissionError(
            "Refusing to scrape -- robots.txt check failed:\n  " + "\n  ".join(problems) +
            "\nThis is a hard gate, not a warning. If robots.txt has changed to explicitly permit "
            "these paths, re-run this check; do not bypass it in code.")
    print("[robots_check] PASS -- both hosts' robots.txt permit every path this scraper requests")


if __name__ == "__main__":
    assert_allowed_or_raise()
