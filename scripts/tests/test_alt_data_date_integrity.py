"""Regression tests for alternative-data date integrity (B2 fix).

NSE/BSE feeds are historical. A prior parser interpreted day-first strings as
month-first, producing future-dated rows that silently vanished from PIT
queries. These tests lock in the repair + hard invariant.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.canonicalize_alternative_data import _repair_future_swapped


def test_repair_unswaps_future_dates_to_past():
    # 08-Jul-2026 was corrupted to 2026-08-07 (day/month swapped).
    s = pd.Series(pd.to_datetime(["2026-08-07", "2026-09-07"]))
    out = _repair_future_swapped(s)
    assert out.iloc[0] == pd.Timestamp("2026-07-08")
    assert out.iloc[1] == pd.Timestamp("2026-07-09")


def test_repair_leaves_valid_past_dates_untouched():
    s = pd.Series(pd.to_datetime(["2025-03-15", "2024-11-30"]))
    out = _repair_future_swapped(s)
    assert list(out) == list(s)


def test_repair_nulls_irreparable_future_dates():
    # A future date whose swap is also invalid/future must become NaT.
    far_future = pd.Timestamp.now().normalize() + pd.Timedelta(days=400)
    s = pd.Series([far_future])
    out = _repair_future_swapped(s)
    assert pd.isna(out.iloc[0])


def test_repair_handles_empty_and_nat():
    s = pd.Series([pd.NaT, pd.NaT])
    out = _repair_future_swapped(s)
    assert out.isna().all()


@pytest.mark.parametrize(
    "path",
    [
        "data/processed/alternative/promoter_pledge_all.parquet",
        "data/processed/alternative/announcements_all.parquet",
    ],
)
def test_stored_artifacts_have_no_future_dates(path):
    fp = PROJECT_ROOT / path
    if not fp.exists():
        pytest.skip(f"{path} not present")
    df = pd.read_parquet(fp, columns=["date"])
    dates = pd.to_datetime(df["date"], errors="coerce")
    today = pd.Timestamp.now().normalize()
    n_future = int((dates.dt.normalize() > today).sum())
    assert n_future == 0, f"{path} has {n_future} future-dated rows"
