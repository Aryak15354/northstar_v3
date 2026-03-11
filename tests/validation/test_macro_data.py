"""Validation tests for macro signal modules and feature wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.research.feature_factory import FeatureFactory
from src.signals.macro.cea_power import apply_power_pit_lag
from src.signals.macro.macro_regime import MacroRegimeBuilder
from src.signals.macro.sector_mapper import SectorMapper


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _make_gst_df() -> pd.DataFrame:
    months = pd.date_range("2023-01-31", periods=18, freq="M")
    rows = []
    for i, dt in enumerate(months):
        rows.append(
            {
                "date": dt,
                "category": "Automobile",
                "state": "Maharashtra",
                "eway_bills_generated": 1000 + i * 40,
                "eway_bill_value_crore": 500 + i * 20,
            }
        )
        rows.append(
            {
                "date": dt,
                "category": "Iron and Steel",
                "state": "Gujarat",
                "eway_bills_generated": 700 + i * 25,
                "eway_bill_value_crore": 350 + i * 12,
            }
        )
    return pd.DataFrame(rows)


def _make_power_df() -> pd.DataFrame:
    days = pd.date_range("2023-01-31", periods=18, freq="M")
    return pd.DataFrame(
        {
            "date": days,
            "region": ["All India"] * len(days),
            "energy_met_mu": np.linspace(4000.0, 4800.0, len(days)),
            "peak_met_gw": np.linspace(180.0, 220.0, len(days)),
            "energy_requirement_mu": np.linspace(4020.0, 4825.0, len(days)),
            "deficit_pct": np.linspace(0.5, 0.2, len(days)),
        }
    )


def _make_metadata_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AUTO.NS", "STEEL.NS"],
            "sector": ["Automobiles", "Steel"],
            "industry": ["Automobiles", "Metals & Mining"],
            "state": ["Maharashtra", "Gujarat"],
        }
    )


def _make_prices() -> pd.DataFrame:
    dates = pd.date_range("2024-02-01", periods=30, freq="D")
    return pd.DataFrame(
        {
            "Date": list(dates) * 2,
            "ticker": ["AUTO.NS"] * len(dates) + ["STEEL.NS"] * len(dates),
            "Close": np.linspace(100.0, 115.0, len(dates)).tolist()
            + np.linspace(80.0, 92.0, len(dates)).tolist(),
            "Volume": [1000] * (2 * len(dates)),
        }
    )


def test_module_structure_exists() -> None:
    root = _repo_root()
    expected = [
        root / "src/signals/macro/__init__.py",
        root / "src/signals/macro/gst_ewaybill.py",
        root / "src/signals/macro/cea_power.py",
        root / "src/signals/macro/macro_regime.py",
        root / "src/signals/macro/sector_mapper.py",
    ]
    for path in expected:
        assert path.exists(), f"missing expected macro module: {path}"


def test_sector_mapper_maps_automobile_sector_to_gst_category() -> None:
    mapper = SectorMapper()
    md = _make_metadata_df()
    cats = mapper.get_relevant_gst_categories("AUTO.NS", metadata_df=md)
    assert "Automobile" in cats


def test_macro_regime_builder_market_rows_are_one_per_date() -> None:
    builder = MacroRegimeBuilder()
    market = builder.build_market_features(_make_gst_df(), _make_power_df())
    assert not market.empty
    assert len(market) == int(market["date"].nunique())
    assert market["ticker"].astype(str).eq("MARKET").all()


def test_macro_outputs_have_pit_safe_availability_dates() -> None:
    builder = MacroRegimeBuilder()
    mapper = SectorMapper()
    out = builder.build_combined_features(
        _make_gst_df(),
        _make_power_df(),
        mapper,
        _make_metadata_df(),
    )
    assert not out.empty

    dt = pd.to_datetime(out["date"], errors="coerce")
    av = pd.to_datetime(out["availability_date"], errors="coerce")
    mask = dt.notna() & av.notna()
    assert (av[mask] > dt[mask]).all()


def test_gst_availability_has_conservative_lag() -> None:
    builder = MacroRegimeBuilder()
    gst = builder._prep_gst(_make_gst_df())
    lag = pd.to_datetime(gst["availability_date"], errors="coerce") - pd.to_datetime(gst["date"], errors="coerce")
    assert (lag.dt.days >= 15).all()


def test_power_availability_is_date_plus_one() -> None:
    raw = pd.DataFrame({"date": pd.to_datetime(["2024-01-05", "2024-01-06"])})
    out = apply_power_pit_lag(raw)
    expected = pd.to_datetime(["2024-01-06", "2024-01-07"])
    assert (pd.to_datetime(out["availability_date"], errors="coerce") == expected).all()


def test_macro_regime_label_domain_is_valid() -> None:
    builder = MacroRegimeBuilder()
    market = builder.build_market_features(_make_gst_df(), _make_power_df())
    labels = set(market["macro_regime_label"].dropna().astype(str).unique())
    assert labels.issubset({"expansion", "neutral", "contraction"})


def test_sector_features_differ_across_sectors_same_date() -> None:
    builder = MacroRegimeBuilder()
    mapper = SectorMapper()
    sector = builder.build_sector_features(_make_gst_df(), mapper, _make_metadata_df())
    assert not sector.empty

    latest = pd.to_datetime(sector["date"], errors="coerce").max()
    sub = sector[pd.to_datetime(sector["date"], errors="coerce") == latest]
    vals = pd.to_numeric(sub["sector_gst_yoy"], errors="coerce").dropna()
    assert len(sub["ticker"].unique()) >= 2
    assert vals.nunique() >= 2


def test_market_features_are_same_for_all_tickers_per_date_when_merged(tmp_path: Path) -> None:
    builder = MacroRegimeBuilder(output_path=str(tmp_path / "macro_regime_features.parquet"))
    mapper = SectorMapper()
    macro_df = builder.build_combined_features(_make_gst_df(), _make_power_df(), mapper, _make_metadata_df())

    ff = FeatureFactory(
        config={
            "use_macro_features": True,
            "macro_features_path": str(tmp_path / "macro_regime_features.parquet"),
        }
    )
    panel = ff.build_features(prices=_make_prices(), sector_lookup={"AUTO.NS": "Automobiles", "STEEL.NS": "Steel"})

    assert "macro_activity_composite" in panel.columns
    by_date = panel.groupby("date", sort=False)["macro_activity_composite"].nunique(dropna=False)
    assert (by_date <= 1).all()


def test_macro_features_disabled_means_no_macro_columns() -> None:
    ff = FeatureFactory(config={"use_macro_features": False})
    panel = ff.build_features(prices=_make_prices())

    macro_cols = {
        "power_yoy_growth",
        "gst_yoy_growth",
        "macro_activity_composite",
        "macro_regime_label",
        "sector_gst_yoy",
        "sector_activity_zscore",
    }
    assert macro_cols.isdisjoint(set(panel.columns))


def test_market_features_use_time_series_normalization_not_cross_sectional(tmp_path: Path) -> None:
    builder = MacroRegimeBuilder(output_path=str(tmp_path / "macro_regime_features.parquet"))
    mapper = SectorMapper()
    builder.build_combined_features(_make_gst_df(), _make_power_df(), mapper, _make_metadata_df())

    ff = FeatureFactory(
        config={
            "use_macro_features": True,
            "macro_features_path": str(tmp_path / "macro_regime_features.parquet"),
        }
    )
    panel = ff.build_features(prices=_make_prices(), sector_lookup={"AUTO.NS": "Automobiles", "STEEL.NS": "Steel"})

    assert "macro_activity_composite_ts_z" in panel.columns
    assert "macro_activity_composite_cs_z" not in panel.columns
