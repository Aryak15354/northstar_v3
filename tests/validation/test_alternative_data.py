"""Validation tests for alternative-data signal module."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.research.feature_factory import FeatureFactory
from src.signals.bulk_deals import compute_bulk_deal_features
from src.signals.credit_ratings import rating_to_numeric
from src.signals.feature_builder import AlternativeFeatureBuilder
from src.signals.promoter_pledge import compute_pledge_features
from src.signals.signal_loader import AlternativeDataLoader


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _simple_prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    return pd.DataFrame(
        {
            "Date": list(dates) * 2,
            "ticker": ["AAA.NS"] * len(dates) + ["BBB.NS"] * len(dates),
            "Close": np.linspace(100.0, 110.0, len(dates)).tolist()
            + np.linspace(200.0, 220.0, len(dates)).tolist(),
            "Volume": [1000] * (2 * len(dates)),
        }
    )


def test_module_structure_exists() -> None:
    root = _repo_root()
    expected = [
        root / "src/signals/__init__.py",
        root / "src/signals/bulk_deals.py",
        root / "src/signals/promoter_pledge.py",
        root / "src/signals/earnings_dates.py",
        root / "src/signals/credit_ratings.py",
        root / "src/signals/order_announcements.py",
        root / "src/signals/signal_loader.py",
        root / "src/signals/feature_builder.py",
    ]
    for path in expected:
        assert path.exists(), f"missing expected module: {path}"


def test_loader_initializes_without_data_files(tmp_path: Path) -> None:
    alt_dir = tmp_path / "alternative"
    alt_dir.mkdir(parents=True, exist_ok=True)
    loader = AlternativeDataLoader({"alternative_data_path": str(alt_dir)})
    assert set(loader.FAMILY_PATHS).issubset(set(loader.frames))


def test_bulk_deal_features_are_pit_safe_by_one_day_shift() -> None:
    deals = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "nse_ticker": ["AAA.NS"],
            "deal_type": ["BUY"],
            "quantity": [100.0],
            "price": [10.0],
            "client_name": ["GLOBAL MUTUAL FUND"],
        }
    )
    prices = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
            "ticker": ["AAA.NS", "AAA.NS"],
            "market_cap": [10_000.0, 10_000.0],
        }
    )

    out = compute_bulk_deal_features(deals, prices)
    assert len(out) == 2

    d0 = out.loc[out["date"] == pd.Timestamp("2024-01-02")].iloc[0]
    d1 = out.loc[out["date"] == pd.Timestamp("2024-01-03")].iloc[0]

    # Deal on 2024-01-02 becomes available on 2024-01-03, so no same-day leakage.
    assert float(d0["bulk_buy_volume_5d"] or 0.0) == 0.0
    assert float(d1["bulk_buy_volume_5d"] or 0.0) == 100.0


def test_pledge_features_apply_quarter_plus_45d_availability() -> None:
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-03-31")],
            "nse_ticker": ["AAA.NS"],
            "pledge_pct": [31.0],
        }
    )
    out = compute_pledge_features(df)
    assert not out.empty
    assert out.loc[0, "availability_date"] == pd.Timestamp("2024-05-15")
    assert out.loc[0, "availability_date"] > out.loc[0, "date"]


def test_rating_numeric_conversion_covers_all_grades() -> None:
    expected = {
        "AAA": 10.0,
        "AA+": 9.0,
        "AA": 8.0,
        "AA-": 7.0,
        "A+": 6.0,
        "A": 5.0,
        "A-": 4.0,
        "BBB+": 3.0,
        "BBB": 2.0,
        "BBB-": 1.0,
        "BB+": 0.0,
    }
    for grade, score in expected.items():
        assert rating_to_numeric(grade) == score


def test_loader_no_future_leakage_with_asof_merge(tmp_path: Path) -> None:
    alt_dir = tmp_path / "alternative"
    alt_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "ticker": ["AAA.NS"],
            "availability_date": [pd.Timestamp("2024-01-03")],
            "bulk_net_volume_5d": [123.0],
        }
    ).to_csv(alt_dir / "bulk_deals_all.csv", index=False)

    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
            "ticker": ["AAA.NS", "AAA.NS"],
        }
    )

    loader = AlternativeDataLoader({"alternative_data_path": str(alt_dir)})
    out = loader.get_features_as_of_frame(frame)

    assert pd.isna(out.loc[0, "bulk_net_volume_5d"])
    assert float(out.loc[1, "bulk_net_volume_5d"]) == 123.0


def test_feature_builder_creates_cs_variants_for_all_features() -> None:
    cols = AlternativeFeatureBuilder.feature_columns()
    dates = [pd.Timestamp("2024-01-01")] * 3 + [pd.Timestamp("2024-01-02")] * 3
    frame = pd.DataFrame({"date": dates})
    for i, c in enumerate(cols):
        frame[c] = np.arange(len(frame), dtype=float) + i

    out = AlternativeFeatureBuilder.normalize(frame)
    for c in cols:
        assert f"{c}_cs_z" in out.columns
        assert f"{c}_cs_rank" in out.columns


def test_feature_factory_flag_off_has_no_alternative_columns() -> None:
    prices = _simple_prices()
    ff = FeatureFactory(config={"use_alternative_features": False})
    panel = ff.build_features(prices=prices)

    alt_cols = set(AlternativeFeatureBuilder.feature_columns())
    assert alt_cols.isdisjoint(set(panel.columns))


def test_graceful_degradation_missing_files_returns_nan_features(tmp_path: Path) -> None:
    alt_dir = tmp_path / "alternative"
    alt_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-05")],
            "ticker": ["AAA.NS", "BBB.NS"],
        }
    )
    loader = AlternativeDataLoader({"alternative_data_path": str(alt_dir)})
    out = loader.get_features_as_of_frame(frame)

    for c in AlternativeFeatureBuilder.feature_columns():
        assert c in out.columns
        assert out[c].isna().all()
