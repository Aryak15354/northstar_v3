"""Tests for the shared panel-math helpers (src/core/panel_math.py)."""

import numpy as np
import pandas as pd

from src.core.panel_math import (
    coalesce_rowwise,
    group_rank_centered,
    group_zscore,
    normalize_ticker,
    sector_string,
)


def test_group_zscore_missing_stays_nan():
    values = pd.Series([1.0, 2.0, np.nan, 4.0])
    groups = pd.Series(["d1", "d1", "d1", "d1"])
    z = group_zscore(values, groups)
    assert pd.isna(z.iloc[2])
    assert z.iloc[[0, 1, 3]].notna().all()


def test_group_zscore_degenerate_group_present_is_zero():
    # A group where every present value is identical -> std 0 -> centered 0.
    values = pd.Series([5.0, 5.0, np.nan])
    groups = pd.Series(["d1", "d1", "d1"])
    z = group_zscore(values, groups)
    assert z.iloc[0] == 0.0
    assert z.iloc[1] == 0.0
    assert pd.isna(z.iloc[2])


def test_group_rank_centered_range_and_missing():
    values = pd.Series([1.0, 2.0, 3.0, np.nan])
    groups = pd.Series(["d1", "d1", "d1", "d1"])
    r = group_rank_centered(values, groups)
    assert pd.isna(r.iloc[3])
    present = r.iloc[[0, 1, 2]]
    assert present.min() >= -0.5 - 1e-9
    assert present.max() <= 0.5 + 1e-9


def test_group_rank_centered_degenerate_group():
    values = pd.Series([7.0, 7.0])
    groups = pd.Series(["d1", "d1"])
    r = group_rank_centered(values, groups)
    # pct rank of identical values is 1.0 -> centered 0.5; both present, not NaN.
    assert r.notna().all()


def test_normalize_ticker_missing_inputs():
    assert normalize_ticker(float("nan")) == ""
    assert normalize_ticker(None) == ""
    assert normalize_ticker("") == ""
    assert normalize_ticker(np.nan) == ""
    assert normalize_ticker("nan") == ""


def test_normalize_ticker_valid_inputs():
    assert normalize_ticker("RELIANCE") == "RELIANCE.NS"
    assert normalize_ticker("tcs") == "TCS.NS"
    assert normalize_ticker("INFY.NS") == "INFY.NS"
    assert normalize_ticker("HDFC.BO") == "HDFC.BO"
    assert normalize_ticker("SBIN.BSE") == "SBIN.NS"


def test_sector_string_preserves_nan_fill():
    s = pd.Series(["Banks", np.nan, "IT"])
    out = sector_string(s)
    assert out.iloc[1] == "UNKNOWN"
    assert out.iloc[0] == "Banks"
    # No literal "nan" string leaks through.
    assert "nan" not in set(out.tolist())


def test_coalesce_rowwise_per_row():
    primary = pd.Series([1.0, np.nan, 3.0])
    fallback = pd.Series([9.0, 8.0, 7.0])
    out = coalesce_rowwise(primary, fallback)
    assert list(out) == [1.0, 8.0, 3.0]
