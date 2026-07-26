#!/usr/bin/env python3
"""MICRO-002 backfill: BSE + NSE shareholding-pattern scrape, 2010-2022.

**READ THIS BEFORE RUNNING THE FULL BACKFILL.** This environment could not verify the BSE/NSE
endpoints live (both domains are blocked by this sandbox's browsing policy) -- run `--verify` first,
in whatever environment actually executes this, and inspect the raw cached output before committing
to the ~37,000-request full run. See README.md for the full workflow.

Usage:
  # 1. Confirm the endpoints actually work and look right, on ONE ticker/quarter each:
  python3 run_scrape.py --verify

  # 2. Small-scale test (a handful of tickers, recent quarters only -- fast, cheap sanity check):
  python3 run_scrape.py --source both --limit-tickers 5 --start 2021-01-01 --end 2022-12-31

  # 3. The real thing, resumable (safe to Ctrl-C and re-run; already-done work is skipped):
  python3 run_scrape.py --source both --qps 1.5 --workers 4
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cache
import fetch_bse
import fetch_nse
import robots_check
from checkpoint import Checkpoint
from quarters import quarter_list
from rate_limiter import CircuitBreaker, RateLimiter
from universe import build_universe

REPO = Path(__file__).resolve().parents[3]
CHECKPOINT_PATH = REPO / "data/raw/exchanges/shareholding_pattern_scrape/_checkpoint.csv"


def run_verify() -> int:
    """Fetch exactly one real (ticker, quarter) from each source and print the raw response --
    no caching, no checkpoint writes. This is the gate before anything else runs."""
    print("=" * 100)
    print("VERIFY MODE -- one request per source, raw output printed for manual inspection")
    print("=" * 100)

    print("\n--- robots.txt check ---")
    try:
        robots_check.assert_allowed_or_raise()
    except PermissionError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    u = build_universe()
    sample = u[u["bse_code"].notna()].iloc[0]
    qs = quarter_list()
    recent_q = qs[-1]  # most recent quarter -- easiest to cross-check against known-good data

    print(f"\n--- NSE: {sample['nse_symbol']}, window around {recent_q.availability_date.date()} ---")
    try:
        session = fetch_nse.make_session()
        from_d, to_d = fetch_nse.date_window_for_quarter(recent_q.quarter_end, recent_q.availability_date)
        raw = fetch_nse.fetch_one(session, sample["nse_symbol"], from_d, to_d)
        print(f"  {len(raw)} bytes received. First 500 chars:\n  {raw[:500]!r}")
    except Exception as exc:
        print(f"  FAILED: {exc}")

    print(f"\n--- BSE: scripcode {sample['bse_code']} ---")
    try:
        session = fetch_bse.make_session()
        qtr_raw, blocked = fetch_bse.fetch_available_quarters(session, sample["bse_code"])
        print(f"  ddlqtrid response: blocked={blocked}, "
              f"{len(qtr_raw) if qtr_raw else 0} bytes: {qtr_raw[:500] if qtr_raw else None!r}")
    except Exception as exc:
        print(f"  FAILED: {exc}")

    print("\n" + "=" * 100)
    print("If either response above doesn't look like real shareholding-pattern data (percentages by")
    print("promoter/FII/DII/public), the endpoint in fetch_nse.py or fetch_bse.py needs correcting --")
    print("do NOT proceed to the full run until this looks right.")
    print("=" * 100)
    return 0


def _do_nse(symbol: str, quarter, ckpt: Checkpoint, limiter: RateLimiter, breaker: CircuitBreaker,
           session) -> None:
    if not ckpt.should_attempt("nse", symbol, quarter.label):
        return
    if cache.is_cached("nse", symbol, quarter.label):
        ckpt.record("nse", symbol, quarter.label, "done", "already cached")
        return
    limiter.acquire()
    try:
        from_d, to_d = fetch_nse.date_window_for_quarter(quarter.quarter_end, quarter.availability_date)
        raw = fetch_nse.fetch_one(session, symbol, from_d, to_d)
        if not raw or len(raw) < 10:
            ckpt.record("nse", symbol, quarter.label, "empty", "empty response")
            return
        cache.write_raw("nse", symbol, quarter.label, raw,
                        meta=dict(from_date=from_d, to_date=to_d))
        ckpt.record("nse", symbol, quarter.label, "done")
        breaker.record_success()
    except Exception as exc:
        tripped = breaker.record_failure()
        ckpt.record("nse", symbol, quarter.label, "failed", str(exc)[:200])
        if tripped:
            raise RuntimeError(f"NSE circuit breaker tripped after repeated failures: {exc}") from exc


def _do_bse(bse_code: str, quarter, ckpt: Checkpoint, limiter: RateLimiter, breaker: CircuitBreaker,
           session) -> None:
    if not ckpt.should_attempt("bse", bse_code, quarter.label):
        return
    if cache.is_cached("bse", bse_code, quarter.label) or cache.is_cached("bse", bse_code, quarter.label, ext="csv"):
        ckpt.record("bse", bse_code, quarter.label, "done", "already cached")
        return
    limiter.acquire()
    try:
        # BSE needs a qtrid, not a calendar quarter directly -- cache the ddlqtrid lookup per
        # scripcode once (not per quarter) to avoid redundant requests.
        qtr_cache_label = "_qtrid_list"
        if not cache.is_cached("bse", bse_code, qtr_cache_label):
            qtr_raw, blocked = fetch_bse.fetch_available_quarters(session, bse_code)
            if qtr_raw:
                cache.write_raw("bse", bse_code, qtr_cache_label, qtr_raw)
            if blocked and not qtr_raw:
                raise RuntimeError("blocked fetching quarter-id list")
        # NOTE: mapping quarter.label -> the right qtrid requires parsing the cached qtrid-list
        # response (format not confirmed live -- see parse.py's disclosure). This fetch attempts the
        # quarter label directly as a qtrid fallback; correct once a real response shape is seen.
        raw, blocked, shape = fetch_bse.fetch_shareholding(session, bse_code, quarter.label)
        if not raw or len(raw) < 10:
            ckpt.record("bse", bse_code, quarter.label, "empty", "empty response")
            return
        cache.write_raw("bse", bse_code, quarter.label, raw, ext=("csv" if shape == "csv" else "json"))
        ckpt.record("bse", bse_code, quarter.label, "done")
        breaker.record_success()
    except Exception as exc:
        tripped = breaker.record_failure()
        ckpt.record("bse", bse_code, quarter.label, "failed", str(exc)[:200])
        if tripped:
            raise RuntimeError(f"BSE circuit breaker tripped after repeated failures: {exc}") from exc


def run_full(source: str, qps: float, workers: int, start: str, end: str,
            limit_tickers: int, max_consec_fail: int) -> int:
    print("=" * 100)
    print(f"MICRO-002 BACKFILL -- source={source} qps={qps} workers={workers} range={start}..{end}")
    print("=" * 100)

    print("\n--- robots.txt check (hard gate, re-checked every run) ---")
    robots_check.assert_allowed_or_raise()

    universe = build_universe(start=start, end=end)
    if limit_tickers:
        universe = universe.head(limit_tickers)
    quarters = quarter_list(start=start, end=end)
    print(f"universe: {len(universe)} tickers, {len(quarters)} quarters "
         f"({len(universe) * len(quarters):,} units of work per source)")

    ckpt = Checkpoint(CHECKPOINT_PATH)
    limiter = RateLimiter(qps=qps)
    breaker = CircuitBreaker(max_consecutive_failures=max_consec_fail)

    t0 = time.time()
    n_done = 0

    def work_items():
        for _, row in universe.iterrows():
            for q in quarters:
                if source in ("nse", "both"):
                    yield ("nse", row["nse_symbol"], q)
                if source in ("bse", "both") and row["bse_code"]:
                    yield ("bse", row["bse_code"], q)

    items = list(work_items())
    print(f"total fetch units: {len(items):,}\n")

    nse_session = fetch_nse.make_session()
    bse_session = fetch_bse.make_session()

    def _run_one(item):
        src, ident, q = item
        if src == "nse":
            _do_nse(ident, q, ckpt, limiter, breaker, nse_session)
        else:
            _do_bse(ident, q, ckpt, limiter, breaker, bse_session)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_one, it): it for it in items}
        for fut in as_completed(futures):
            n_done += 1
            try:
                fut.result()
            except RuntimeError as exc:
                print(f"\n[CIRCUIT BREAKER TRIPPED] {exc}")
                print("Stopping -- re-run this command later to resume (already-done work is cached "
                     "and will be skipped).")
                pool.shutdown(cancel_futures=True)
                break
            if n_done % 100 == 0:
                elapsed = time.time() - t0
                rate = n_done / elapsed if elapsed else 0
                summary = ckpt.summary()
                print(f"[{n_done}/{len(items)}] {rate:.2f} req/s | "
                     f"done={summary.get('done', 0)} empty={summary.get('empty', 0)} "
                     f"failed={summary.get('failed', 0)}", flush=True)

    print("\n" + "=" * 100)
    print("FINAL SUMMARY:", ckpt.summary())
    print("=" * 100)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="One request per source, print raw output, exit.")
    ap.add_argument("--source", choices=["nse", "bse", "both"], default="both")
    ap.add_argument("--qps", type=float, default=1.5, help="Combined requests/second across all workers.")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default="2022-12-31")
    ap.add_argument("--limit-tickers", type=int, default=0, help="Cap universe size, for a test run.")
    ap.add_argument("--max-consec-fail", type=int, default=8,
                    help="Trip the circuit breaker after this many consecutive failures.")
    args = ap.parse_args()

    if args.verify:
        return run_verify()
    return run_full(args.source, args.qps, args.workers, args.start, args.end,
                    args.limit_tickers, args.max_consec_fail)


if __name__ == "__main__":
    raise SystemExit(main())
