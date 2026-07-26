#!/usr/bin/env python3
"""Check robots.txt for both exchanges before any scraping begins. Hard-fails (refuses to proceed)
if the specific paths this scraper hits are disallowed for a generic user-agent -- this check runs
every time `run_scrape.py` starts, not just once, since robots.txt can change.
"""
from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass

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


def check_domain(base_url: str, paths: list[str]) -> RobotsResult:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(base_url.rstrip("/") + "/robots.txt")
    try:
        rp.read()
        fetched_ok = True
    except Exception as exc:
        # robots.txt unreachable: fail closed, do not assume permission.
        return RobotsResult(domain=base_url, fetched_ok=False, all_allowed=False,
                            per_path={p: False for p in paths})

    per_path = {p: rp.can_fetch(USER_AGENT, base_url.rstrip("/") + p) for p in paths}
    return RobotsResult(domain=base_url, fetched_ok=fetched_ok,
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
            problems.append(f"{r.domain}: robots.txt could not be fetched -- failing closed, "
                           f"not assuming permission")
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
