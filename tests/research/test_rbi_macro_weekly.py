"""Leak-safety regression tests for the weekly RBI macro panel builder.

The one property that must never break: a Friday may only see a macro reading
that had genuinely been published by then (period_date + publication_lag). A
regression here silently inflates every downstream macro IC.
"""

import numpy as np
import pandas as pd
import pytest

import scripts.kaggle.build_rbi_macro_weekly as b


def test_transforms_are_backward_only():
    s = pd.Series(np.arange(60.0), index=pd.date_range("2020-01-03", periods=60, freq="W-FRI"))
    tf = b._transforms(s)
    # chg4w at position i uses i and i-4 only
    assert tf["chg4w"].iloc[10] == s.iloc[10] - s.iloc[6]
    # z-score has no value before the minimum-history window
    assert tf["z"].iloc[: b.MIN_Z_OBS - 1].isna().all()


def test_publication_lag_prevents_lookahead(monkeypatch, tmp_path):
    """A monthly series stamped at month-start must not appear on a Friday that
    precedes its (start + monthly lag) publication date."""
    # synthetic long-format store: one monthly series, distinct value per month
    dates = pd.date_range("2021-01-01", periods=18, freq="MS")
    src = pd.DataFrame({
        "date": dates,
        "frequency": "monthly",
        "indicator_slug": "synth_cpi",
        "unit": "index",
        "value": 100.0 + np.arange(len(dates)),  # strictly increasing, unique
    })
    p = tmp_path / "rbi_macro_long.parquet"
    src.to_parquet(p, index=False)
    monkeypatch.setattr(b, "SRC", p)

    wide, manifest = b.build(start="2021-01-01")
    lag = b.FREQ_LAG_DAYS["monthly"]

    lvl = wide[["date", "synth_cpi"]].dropna()
    for _, row in lvl.iterrows():
        fri, val = row["date"], row["synth_cpi"]
        # the value shown must correspond to a source row already published
        published = src[src["date"] + pd.Timedelta(days=lag) <= fri]
        assert not published.empty
        assert abs(val - published["value"].iloc[-1]) < 1e-9
        # and must never equal a not-yet-published future value
        future = src[src["date"] + pd.Timedelta(days=lag) > fri]
        assert val not in set(np.round(future["value"], 6))

    # staleness is never negative (no future information)
    assert (wide["synth_cpi_age_weeks"].dropna() >= 0).all()


def test_slug_override_applies(monkeypatch):
    monkeypatch.setattr(b, "SLUG_LAG_OVERRIDES", {"x": 3})
    assert b.lag_days_for("x", "monthly") == 3
    assert b.lag_days_for("y", "weekly") == b.FREQ_LAG_DAYS["weekly"]
