"""Tests for coverage-report-v2 verdicts — the trust gate that must catch the
silent-corruption classes the 2026-07 hand-audit found (silent zeros, source
fill, era boundaries, dead columns) while leaving honest factors OK."""

import numpy as np
import pandas as pd

from scripts.kaggle.coverage_report_v2 import analyze


def _panel():
    dates = pd.date_range("2019-01-04", "2026-03-13", freq="W-FRI")
    n_t = 100
    rng = np.random.default_rng(0)
    rows = []
    for dt in dates:
        for t in range(n_t):
            rows.append({"date": dt, "ticker": f"T{t:03d}"})
    df = pd.DataFrame(rows)
    N = len(df)
    yr = df["date"].dt.year
    # OK: continuous, well covered, varies per date
    df["good_factor"] = rng.normal(0, 1, N)
    # SILENT_ZERO: a cs_z that is exactly 0 for most rows (NaN→0 imputation)
    z = rng.normal(0, 1, N)
    z[: int(0.95 * N)] = 0.0
    df["thing_cs_z"] = z
    # SOURCE_FILLED: a per-ticker factor collapsed to a dominant 0 (only a few
    # tickers per date carry a real value) — high coverage, few distinct/date,
    # one value dominates.
    sf = np.zeros(N)
    hit = rng.random(N) < 0.02   # ~2 real values per date -> few distinct/date
    sf[hit] = rng.normal(0, 1, int(hit.sum()))
    df["source_filled"] = sf
    # MACRO broadcast: same value for every ticker on a date, but varies over
    # time — legit, must be OK (not SOURCE_FILLED).
    date_val = {d: v for d, v in zip(dates, rng.normal(0, 1, len(dates)))}
    df["macro_broadcast"] = df["date"].map(date_val)
    # SPARSE: honest low coverage that genuinely varies (young factor) -> kept
    sp = np.full(N, np.nan)
    sp[(yr >= 2026).values] = rng.normal(0, 1, int((yr >= 2026).sum()))
    df["young_factor"] = sp
    # ERA_BOUNDARY: NaN before 2024, real after (but decent overall coverage)
    era = rng.normal(0, 1, N)
    era[(yr < 2024).values] = np.nan
    df["era_factor"] = era
    # DEAD: constant (single value)
    df["dead_factor"] = 1.0
    # binary flag: must NOT be SOURCE_FILLED despite few distinct values
    df["has_data_available"] = rng.integers(0, 2, N).astype(float)
    return df


def test_verdicts():
    rep = analyze(_panel()).set_index("factor")["verdict"].to_dict()
    assert rep["good_factor"] == "OK"
    assert rep["thing_cs_z"] == "SILENT_ZERO"
    assert rep["source_filled"] == "SOURCE_FILLED"
    assert rep["macro_broadcast"] == "OK"        # legit per-date broadcast, not corruption
    assert rep["young_factor"] == "SPARSE"        # honest low coverage, kept (not a fail)
    assert rep["era_factor"] == "ERA_BOUNDARY"
    assert rep["dead_factor"] == "DEAD"
    assert rep["has_data_available"] == "OK"      # binary flag exempt from SOURCE_FILLED
