from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.kaggle.week_2026_03_29.common import (
    build_plan_regime_labels,
    stabilize_sparse_event_features,
)


def _write_regime_reference_tables(base: Path) -> None:
    target = base / "data" / "canonical" / "reference" / "regimes"
    target.mkdir(parents=True, exist_ok=True)

    major = pd.DataFrame(
        [
            {
                "event_id": "E016",
                "regime_type": "MACRO_BEAR",
                "event_name": "2022 Global Rate Hike Bear Market",
                "start_date": "2021-10-18",
                "end_date": "2022-06-17",
                "severity_score_1_10": 7,
            },
            {
                "event_id": "E018",
                "regime_type": "STRONG_BULL",
                "event_name": "2023-2024 India Bull Market (Pre-Election)",
                "start_date": "2023-04-01",
                "end_date": "2024-09-26",
                "severity_score_1_10": 7,
            },
            {
                "event_id": "E019",
                "regime_type": "ELECTION_VOLATILITY",
                "event_name": "2024 Election Shock & Recovery",
                "start_date": "2024-06-04",
                "end_date": "2024-06-24",
                "severity_score_1_10": 7,
            },
        ]
    )
    major.to_parquet(target / "nse_regime_events_major.parquet", index=False)

    subtle = pd.DataFrame(
        [
            {
                "period_id": "S023",
                "subtle_type": "LATE_CYCLE_TOPPING",
                "period_name": "Pre-Rate-Hike Topping Phase (Aug-Oct 2021)",
                "start_date": "2021-08-01",
                "end_date": "2021-10-18",
            },
            {
                "period_id": "S025",
                "subtle_type": "POLICY_ADJUSTMENT",
                "period_name": "Post-Rate-Hike Adjustment Phase (Jul-Dec 2022)",
                "start_date": "2022-06-17",
                "end_date": "2023-01-23",
            },
            {
                "period_id": "S029",
                "subtle_type": "PRE_ELECTION_EUPHORIA",
                "period_name": "India Pre-Election Euphoria Phase (Jan-May 2024)",
                "start_date": "2024-01-01",
                "end_date": "2024-06-03",
            },
        ]
    )
    subtle.to_parquet(target / "nse_regime_periods_subtle.parquet", index=False)


def test_build_plan_regime_labels_narrows_long_rate_and_election_overlays(tmp_path: Path) -> None:
    _write_regime_reference_tables(tmp_path)

    dates = pd.date_range("2021-09-03", "2024-07-05", freq="W-FRI")
    weekly_panel = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA.NS"] * len(dates),
            "close": np.linspace(100.0, 160.0, len(dates)),
            "target_weekly_return": np.sin(np.linspace(0.0, 6.0, len(dates))) * 0.02,
        }
    )

    regimes = build_plan_regime_labels(weekly_panel, tmp_path).set_index("date")

    assert regimes.loc[pd.Timestamp("2021-10-15"), "plan_regime_id"] == "R7"
    assert regimes.loc[pd.Timestamp("2022-03-18"), "plan_regime_id"] != "R7"

    assert regimes.loc[pd.Timestamp("2023-04-07"), "plan_regime_id"] != "R8"
    assert regimes.loc[pd.Timestamp("2024-05-17"), "plan_regime_id"] == "R8"
    assert regimes.loc[pd.Timestamp("2024-06-07"), "plan_regime_id"] == "R8"


def test_stabilize_sparse_event_features_forward_fills_within_ticker_only() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2024-01-05",
                    "2024-01-12",
                    "2024-01-19",
                    "2024-01-05",
                    "2024-01-12",
                ]
            ),
            "ticker": ["AAA.NS", "AAA.NS", "AAA.NS", "BBB.NS", "BBB.NS"],
            "eps_sue_decay": [1.5, np.nan, np.nan, np.nan, 2.0],
            "rev_sue": [np.nan, -0.5, np.nan, 0.7, np.nan],
        }
    )

    stabilized, derived, audit_rows = stabilize_sparse_event_features(frame, ["eps_sue_decay", "rev_sue"])

    assert "eps_sue_decay_raw_available" in derived
    assert "rev_sue_raw_available" in derived

    aaa = stabilized[stabilized["ticker"] == "AAA.NS"].sort_values("date")
    bbb = stabilized[stabilized["ticker"] == "BBB.NS"].sort_values("date")

    assert aaa["eps_sue_decay"].tolist() == [1.5, 1.5, 1.5]
    assert np.isnan(bbb["eps_sue_decay"].iloc[0])
    assert bbb["eps_sue_decay"].iloc[1] == 2.0

    assert np.isnan(aaa["rev_sue"].iloc[0])
    assert aaa["rev_sue"].iloc[1:].tolist() == [-0.5, -0.5]
    assert bbb["rev_sue"].tolist() == [pytest.approx(0.7), pytest.approx(0.7)]

    assert aaa["eps_sue_decay_raw_available"].tolist() == [1.0, 0.0, 0.0]
    assert bbb["eps_sue_decay_raw_available"].tolist() == [0.0, 1.0]

    audit = {row["feature"]: row for row in audit_rows}
    assert audit["eps_sue_decay"]["coverage_after"] > audit["eps_sue_decay"]["coverage_before"]
    assert audit["rev_sue"]["coverage_after"] > audit["rev_sue"]["coverage_before"]
