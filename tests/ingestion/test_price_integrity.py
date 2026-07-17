"""Regression tests for the price-integrity gate and the non-session-row drop.

These lock in the fixes for the corruption that silently poisoned the
2026-07-04 alpha export: fabricated NSE-holiday/weekend rows and forward-filled
frozen mega-cap blocks (HDFCBANK/ICICIBANK, two full years at ~1/5 scale).
Everything runs on synthetic data so it is independent of the live (currently
corrupt) prices.parquet.
"""

import numpy as np
import pandas as pd
import pytest

from scripts.ci.check_price_integrity import run as integrity_run
from src.processing.price_processor import drop_non_session_rows, trim_frozen_runs


def _clean_panel(n_tickers=120, start="2022-01-03", days=520, seed=0):
    """A well-formed daily panel: weekday sessions, all tickers present, prices
    that actually move every day."""
    rng = np.random.default_rng(seed)
    sessions = pd.bdate_range(start, periods=days)
    rows = []
    for t in range(n_tickers):
        px = 100.0 * np.cumprod(1 + rng.normal(0, 0.015, len(sessions)))
        rows.append(pd.DataFrame({"Date": sessions, "ticker": f"T{t:03d}.NS",
                                   "Close": px}))
    return pd.concat(rows, ignore_index=True)


def _write(tmp_path, df):
    p = tmp_path / "prices.parquet"
    df.to_parquet(p, index=False)
    return p


def test_clean_panel_passes(tmp_path):
    report = integrity_run(_write(tmp_path, _clean_panel()))
    assert report["status"] == "PASS", report["checks"]


def test_frozen_block_is_quarantined(tmp_path):
    df = _clean_panel()
    # Freeze one ticker for a full year at a wrong scale (the HDFCBANK pattern).
    frozen = df["ticker"] == "T000.NS"
    yr = frozen & (df["Date"].dt.year == 2023)
    df.loc[yr, "Close"] = 37.0 + np.linspace(0, 0.3, int(yr.sum()))  # <0.1%/day drift
    report = integrity_run(_write(tmp_path, df))
    assert report["status"] == "FAIL"
    assert report["checks"]["flat_lines"]["status"] == "FAIL"
    assert "T000.NS" in report["checks"]["flat_lines"]["quarantine_refetch"]


def test_weekend_rows_flagged(tmp_path):
    df = _clean_panel()
    sat = pd.DataFrame({"Date": [pd.Timestamp("2022-06-04")] * 3,  # a Saturday
                        "ticker": ["T000.NS", "T001.NS", "T002.NS"],
                        "Close": [101.0, 102.0, 103.0]})
    report = integrity_run(_write(tmp_path, pd.concat([df, sat], ignore_index=True)))
    assert report["checks"]["non_trading_days"]["status"] == "FAIL"
    assert report["checks"]["non_trading_days"]["weekend_rows"] == 3


def test_holiday_thin_date_flagged(tmp_path):
    df = _clean_panel()
    # Independence Day: NSE closed, but the corrupt feed fabricates rows for a
    # few mega-caps. Remove it from the dense base first so the injected rows are
    # genuinely the only ones on that date.
    hol_date = pd.Timestamp("2023-08-15")
    df = df[df["Date"] != hol_date]
    hol = pd.DataFrame({"Date": [hol_date] * 3,
                        "ticker": ["T000.NS", "T001.NS", "T002.NS"],
                        "Close": [50.0, 51.0, 52.0]})
    report = integrity_run(_write(tmp_path, pd.concat([df, hol], ignore_index=True)))
    assert report["checks"]["panel_coverage"]["status"] == "FAIL"


def test_drop_non_session_removes_weekend_and_holiday():
    df = _clean_panel(n_tickers=200)
    hol_date = pd.Timestamp("2023-08-15")
    df = df[df["Date"] != hol_date]  # NSE closed that day; base has no real rows
    # weekend rows (few tickers) + a fabricated thin holiday date (few tickers)
    junk = pd.DataFrame({
        "Date": [pd.Timestamp("2022-06-04")] * 3 + [hol_date] * 4,
        "ticker": [f"T{i:03d}.NS" for i in range(3)] + [f"T{i:03d}.NS" for i in range(4)],
        "Close": [1.0] * 7,
    })
    dirty = pd.concat([df, junk], ignore_index=True)
    cleaned, n_dropped = drop_non_session_rows(dirty)
    assert n_dropped == 7
    cleaned["Date"] = pd.to_datetime(cleaned["Date"])
    assert (cleaned["Date"].dt.dayofweek < 5).all()          # no weekends
    assert not (cleaned["Date"] == hol_date).any()            # holiday gone
    # real sessions untouched
    assert len(cleaned) == len(df)


def test_trim_drops_delisted_frozen_keeps_active_quiet():
    rng = np.random.default_rng(3)
    # ACTIVE name: real daily moves through 2026, one genuinely quiet 3-day patch
    ad = pd.bdate_range("2019-01-02", "2026-06-01")
    ac = 100 + np.cumsum(rng.normal(0, 0.6, len(ad)))
    ac[100:103] = ac[99]  # a 3-session quiet patch (< min_run) — must be kept
    active = pd.DataFrame({"date": ad, "ticker": "ACT.NS", "close": ac})
    # DELISTED name: forward-filled constant, series ends 2020 (< cutoff)
    dd = pd.bdate_range("2019-01-02", "2020-03-01")
    delisted = pd.DataFrame({"date": dd, "ticker": "DEAD.NS", "close": 50.0})

    out, n = trim_frozen_runs(pd.concat([active, delisted], ignore_index=True),
                              date_col="date", ticker_col="ticker")
    kept = out.groupby("ticker").size()
    assert kept["ACT.NS"] == len(active)            # active name fully preserved
    assert kept.get("DEAD.NS", 0) <= 1              # delisted frozen series removed


def test_drop_keeps_real_jan1_session():
    """NSE trades on Jan-1 in most years; a full-universe Jan-1 must survive."""
    # bdate_range already includes 2025-01-01 (a Wednesday), so the base panel
    # has a full-universe Jan-1 session; it must survive the drop untouched.
    df = _clean_panel(n_tickers=200, start="2024-12-02", days=40)
    n_jan1_in = int((df["Date"] == pd.Timestamp("2025-01-01")).sum())
    assert n_jan1_in == 200  # sanity: base has a real Jan-1 session
    cleaned, _ = drop_non_session_rows(df)
    cleaned["Date"] = pd.to_datetime(cleaned["Date"])
    assert (cleaned["Date"] == "2025-01-01").sum() == 200
