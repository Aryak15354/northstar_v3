#!/usr/bin/env python3
"""Backfill NSE corporate-announcement history over explicit date windows.

The live scraper (``scrape_nse_announcements.py``) only fetches rolling recent
windows (1D..1Y), so ``announcements_all`` starts in Feb 2026. The NSE
announcements API actually serves history back years (verified: a single week of
Jul-2019 returns ~1,600 rows), so this script sweeps the range in fixed windows
and writes raw CSVs in the exact format ``parse_nse_announcements_csv`` consumes.
Run the canonicalizer afterwards to merge them into the processed artifact.

The raw window CSVs double as the attachment index used by the Phase 4 document
layer (each row carries the ``ATTACHMENT`` PDF URL).

    python scripts/backfill_nse_announcements_history.py --start 2019-01-01 --end 2026-07-11
    python scripts/canonicalize_alternative_data.py
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_csv_scraper_common import create_nse_session, nse_request  # noqa: E402
from scripts.nse_corporate_filings_processors import RAW_ANNOUNCEMENTS_DIR  # noqa: E402

API_URL = "https://www.nseindia.com/api/corporate-announcements"
NSE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"

EXPORT_COLUMNS = [
    "SYMBOL", "COMPANY NAME", "SUBJECT", "DETAILS",
    "BROADCAST DATE/TIME", "RECEIPT", "DISSEMINATION", "DIFFERENCE", "ATTACHMENT",
]


def _to_export_frame(payload: list) -> pd.DataFrame:
    frame = pd.DataFrame(payload)
    if frame.empty:
        return pd.DataFrame(columns=EXPORT_COLUMNS)
    empty = pd.Series("", index=frame.index, dtype=object)
    return pd.DataFrame({
        "SYMBOL": frame.get("symbol", empty),
        "COMPANY NAME": frame.get("sm_name", empty),
        "SUBJECT": frame.get("desc", empty),
        "DETAILS": frame.get("attchmntText", empty),
        "BROADCAST DATE/TIME": frame.get("an_dt", empty),
        "RECEIPT": frame.get("an_dt", empty),
        "DISSEMINATION": frame.get("exchdisstime", empty),
        "DIFFERENCE": frame.get("difference", empty),
        "ATTACHMENT": frame.get("attchmntFile", empty),
    })


def _windows(start: date, end: date, window_days: int):
    cur = start
    step = timedelta(days=window_days)
    while cur <= end:
        w_end = min(cur + step - timedelta(days=1), end)
        yield cur, w_end
        cur = w_end + timedelta(days=1)


def backfill(start: date, end: date, window_days: int, resume: bool,
             delay: tuple[float, float]) -> dict:
    RAW_ANNOUNCEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    session = create_nse_session(referer=NSE_URL)
    total_rows = 0
    fetched = skipped = failed = 0
    windows = list(_windows(start, end, window_days))
    for i, (w_start, w_end) in enumerate(windows, 1):
        f_from = w_start.strftime("%d-%m-%Y")
        f_to = w_end.strftime("%d-%m-%Y")
        out = RAW_ANNOUNCEMENTS_DIR / f"backfill_announcements_{w_start:%Y%m%d}_{w_end:%Y%m%d}.csv"
        if resume and out.exists() and out.stat().st_size > 0:
            skipped += 1
            continue
        try:
            resp = nse_request(
                session, API_URL,
                params={"index": "equities", "from_date": f_from, "to_date": f_to, "reqXbrl": "false"},
                referer=NSE_URL, timeout=(30, 180), max_attempts=4,
            )
            payload = resp.json()
            if not isinstance(payload, list):
                raise RuntimeError(f"unexpected payload type {type(payload).__name__}")
            frame = _to_export_frame(payload)
            frame.to_csv(out, index=False)
            total_rows += len(frame)
            fetched += 1
            print(f"[ann-backfill] ({i}/{len(windows)}) {f_from}..{f_to} rows={len(frame)} cumulative={total_rows}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[ann-backfill] ({i}/{len(windows)}) {f_from}..{f_to} FAILED: {exc}")
        time.sleep(random.uniform(*delay))
    summary = {"windows": len(windows), "fetched": fetched, "skipped": skipped,
               "failed": failed, "rows": total_rows}
    print(f"[ann-backfill] done: {summary}")
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill NSE announcements over explicit windows.")
    p.add_argument("--start", type=str, default="2019-01-01")
    p.add_argument("--end", type=str, default=date.today().isoformat())
    p.add_argument("--window-days", type=int, default=7)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=1.0)
    p.add_argument("--delay-max", type=float, default=2.5)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    backfill(
        date.fromisoformat(args.start),
        date.fromisoformat(args.end),
        int(args.window_days),
        bool(args.resume),
        (float(args.delay_min), float(args.delay_max)),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
