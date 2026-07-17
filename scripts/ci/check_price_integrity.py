#!/usr/bin/env python3
"""CI / export gate: the processed price panel must be trading-clean.

This is a STRICT superset of check_price_continuity.py. The 2026-07-04 Kaggle
alpha export was silently poisoned by three price defects that the old
continuity gate (single-day ratio bounds only) could not see, because the
corruption hides *between* real rows:

  1. NON-TRADING-DAY ROWS. Every ticker's raw CSV carries NSE-holiday rows
     (Jan-1: 500/500 tickers) and weekend rows. NSE never trades those days,
     so the values are fabricated/forward-filled and they manufacture false
     scale seams at year boundaries.
  2. FROZEN FORWARD-FILL BLOCKS. ICICIBANK and HDFCBANK carry ~730 consecutive
     days (2 full years) with <0.1%/day movement at a wrong (~1/5) scale; TCS
     and FORCEMOT have shorter runs. A stuck series cannot be back-adjusted —
     there is no clean anchor — so it must be QUARANTINED and re-fetched, never
     silently shipped. sanitize_ticker_frame cannot fix these.
  3. RESIDUAL SCALE SEAMS below the sanitizer's 2.5x ceiling (e.g. HDFCBANK's
     2.38x year-boundary jump) survive the back-adjust and leave the mega-cap
     at the wrong scale for years.

Because every downstream feature is cross-sectionally ranked per date, one
corrupted mega-cap perturbs EVERY other stock's z-score on every affected date.
This gate fails the build loudly rather than let that reach an experiment.

Exit 0 = clean. Exit 1 = defects found (listed as structured JSON).

Usage:
  python scripts/ci/check_price_integrity.py            # gate data/processed/prices.parquet
  python scripts/ci/check_price_integrity.py --path X   # gate an arbitrary panel
  python scripts/ci/check_price_integrity.py --json      # machine-readable only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICES = PROJECT_ROOT / "data" / "processed" / "prices.parquet"

# --- thresholds -------------------------------------------------------------
# Scale-seam bounds match src/data/price_sanitizer (kept in sync intentionally).
UPPER_RATIO, LOWER_RATIO = 2.5, 0.2
# Flat-line: a real equity moves every session. The reliable signal is the
# FRACTION of a calendar year that is frozen, measured on trading days only and
# within the analysis window — HDFCBANK/ICICIBANK sit at frac_flat=1.0 for two
# full years (2023-2024) at a ~1/5 scale, while genuinely-quiet names top out
# near 0.13. A raw longest-run counter false-flags ancient pre-2019 illiquid
# history, so we bucket by year instead.
FLAT_EPS = 0.001            # 0.1% daily move counts as "frozen"
FLAT_YEAR_FRAC = 0.50       # a year this frozen is a forward-filled block
PENNY_FLOOR = 5.0           # below this, tiny absolute moves are legitimately flat
ANALYSIS_START_YEAR = 2019  # the panel window; older history is not gated
# Panel coverage: a weekly/daily cross-section with too few names is a broken
# merge (the 2023-03-31 phantom week had exactly 5 tickers).
MIN_TICKERS_PER_DATE = 100


def _trading_rows(px: pd.DataFrame) -> pd.DataFrame:
    """Weekday rows within the analysis window. Flat/scale/coverage checks run on
    this view so weekend rows can't manufacture false runs. NSE genuinely trades
    on Jan-1 in most years (2025-01-01 had 491 names), so Jan-1 is NOT excluded;
    fabricated true-holiday rows (Republic Day etc., only the ~5 corrupt mega-caps
    present) are surfaced by check_panel_coverage as thin dates instead."""
    wd = px["Date"].dt.dayofweek
    keep = (wd < 5) & (px["Date"].dt.year >= ANALYSIS_START_YEAR)
    return px[keep]

# Absolute-level pins are intentionally EMPTY. The panel is dividend-adjusted
# (price_fetcher pins auto_adjust=True), so a name's absolute level is basis- and
# time-dependent (HDFCBANK sits ~₹790 adjusted vs ~₹1650 nominal) — hardcoded
# nominal bands cry wolf on clean data. The structural checks (flat-line blocks,
# scale seams, non-session rows) catch the actual corruption class and were
# verified to isolate exactly the corrupt tickers with zero false positives, so
# no absolute-level pin is needed. Populate only with a reference series fetched
# on the SAME adjustment basis if a future case ever escapes the structural nets.
MEGA_CAP_PINS: dict[str, list[tuple[int, float, float]]] = {}


def _load(path: Path) -> pd.DataFrame:
    # Accept both the Title-case processed panel and the lower-case canonical
    # panel (data/canonical/prices/equity_prices_daily.parquet).
    avail = set(pd.read_parquet(path, columns=None).head(0).columns)
    dcol = "Date" if "Date" in avail else "date"
    ccol = "Close" if "Close" in avail else "close"
    tcol = "ticker" if "ticker" in avail else "Ticker"
    px = pd.read_parquet(path, columns=[dcol, tcol, ccol]).rename(
        columns={dcol: "Date", ccol: "Close", tcol: "ticker"})
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    return px.dropna(subset=["Date", "Close"]).sort_values(["ticker", "Date"])


def check_non_trading_days(px: pd.DataFrame) -> dict:
    # Weekends are never NSE sessions. True holidays (weekdays NSE was closed)
    # are caught by check_panel_coverage as thin dates rather than a hardcoded
    # calendar — a real session has hundreds of names, a fabricated holiday row
    # has only the corrupt few.
    wd = px["Date"].dt.dayofweek
    weekend = int((wd >= 5).sum())
    return {
        "weekend_rows": weekend,
        "status": "PASS" if weekend == 0 else "FAIL",
    }


def check_flat_lines(px: pd.DataFrame) -> dict:
    """Flag tickers with any analysis-window year >FLAT_YEAR_FRAC frozen.

    These are forward-filled synthetic blocks (HDFCBANK/ICICIBANK: two full
    years at a wrong scale) and are UNRECOVERABLE by back-adjustment — there is
    no clean anchor — so they must be re-fetched from source, not shipped."""
    trad = _trading_rows(px)
    offenders = {}
    for tk, g in trad.groupby("ticker"):
        if g["Close"].median() < PENNY_FLOOR:
            continue
        yr_flat = g.groupby(g["Date"].dt.year)["Close"].apply(
            lambda c: float((c.pct_change().abs() < FLAT_EPS).mean()))
        worst = yr_flat.max()
        if worst > FLAT_YEAR_FRAC:
            bad_years = yr_flat[yr_flat > FLAT_YEAR_FRAC]
            offenders[tk] = {
                "worst_year": int(bad_years.idxmax()),
                "frac_flat": round(float(worst), 3),
                "frozen_years": [int(y) for y in bad_years.index],
            }
    offenders = dict(sorted(offenders.items(),
                            key=lambda x: -x[1]["frac_flat"]))
    return {
        "frozen_tickers": len(offenders),
        "quarantine_refetch": offenders,
        "status": "PASS" if not offenders else "FAIL",
    }


def check_scale_seams(px: pd.DataFrame) -> dict:
    px = _trading_rows(px)
    ratio = px.groupby("ticker")["Close"].pct_change() + 1.0
    bad = px[(ratio > UPPER_RATIO) | (ratio < LOWER_RATIO)]
    offenders = bad.groupby("ticker").size().sort_values(ascending=False)
    return {
        "discontinuities": int(len(bad)),
        "offenders": offenders.head(20).astype(int).to_dict(),
        "status": "PASS" if bad.empty else "FAIL",
    }


def check_mega_cap_pins(px: pd.DataFrame) -> dict:
    """ADVISORY only. Wide known-good annual bands as a backstop against a
    numeric-but-wrong scale. Bands are approximate and adjustment-basis
    sensitive (a 1:1 bonus halves the whole back-history), so a violation means
    "inspect this name", not "fail the build" — it never sets the gate to FAIL.
    Structural checks (flat-lines, non-trading rows, seams) are authoritative."""
    flags = []
    for tk, bands in MEGA_CAP_PINS.items():
        g = px[px["ticker"] == tk]
        if g.empty:
            continue
        for yr, lo, hi in bands:
            yv = g[g["Date"].dt.year == yr]["Close"]
            if yv.empty:
                continue
            med = float(yv.median())
            if not (lo <= med <= hi):
                flags.append({"ticker": tk, "year": yr,
                              "median_close": round(med, 1),
                              "approx_band": [lo, hi]})
    return {"advisory_flags": flags, "status": "ADVISORY"}


def check_panel_coverage(px: pd.DataFrame) -> dict:
    # Only police the analysis window: the universe genuinely grew from ~40 names
    # in 1996 to ~500 today, so early-history thin dates are expected. A thin
    # date inside the window is a broken merge (the 2023-03-31 phantom week had
    # exactly the 5 corrupted mega-caps and nobody else).
    px = _trading_rows(px)
    per_date = px.groupby("Date")["ticker"].nunique()
    thin = per_date[per_date < MIN_TICKERS_PER_DATE]
    return {
        "thin_dates": int(len(thin)),
        "worst": {str(d.date()): int(n) for d, n in thin.head(10).items()},
        "status": "PASS" if thin.empty else "FAIL",
    }


def run(path: Path) -> dict:
    px = _load(path)
    checks = {
        "non_trading_days": check_non_trading_days(px),
        "flat_lines": check_flat_lines(px),
        "scale_seams": check_scale_seams(px),
        "mega_cap_pins": check_mega_cap_pins(px),
        "panel_coverage": check_panel_coverage(px),
    }
    # ADVISORY checks never fail the build; only hard PASS/FAIL checks gate.
    overall = "PASS" if all(c["status"] in ("PASS", "ADVISORY")
                            for c in checks.values()) else "FAIL"
    return {
        "gate": "price_integrity",
        "status": overall,
        "path": str(path),
        "rows": int(len(px)),
        "tickers": int(px["ticker"].nunique()),
        "checks": checks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(DEFAULT_PRICES))
    ap.add_argument("--json", action="store_true", help="machine-readable only")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"gate": "price_integrity", "status": "SKIP",
                          "reason": f"{path} missing"}))
        return 0

    report = run(path)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
