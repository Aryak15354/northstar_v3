"""Validation tests for Screener scrape and processed pipeline outputs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.load_screener_to_pipeline import build_pipeline_files
from src.research.feature_factory import FeatureFactory

EXPECTED_LOG_COLUMNS = {
    "ticker",
    "url_used",
    "status",
    "sections_scraped",
    "rows_scraped_total",
    "error_message",
    "timestamp",
    "duration_seconds",
}


def _month_period(month: str, year: int) -> str:
    return f"{month} {year}"


def _q_end_from_label(label: str) -> pd.Timestamp:
    parts = str(label).split("-")
    q = int(parts[0].replace("Q", ""))
    y = int(parts[1])
    month = q * 3
    return pd.Timestamp(year=y, month=month, day=1) + pd.offsets.MonthEnd(0)


@pytest.fixture()
def screener_fixture(tmp_path: Path) -> dict[str, Path]:
    raw_root = tmp_path / "data" / "raw" / "screener"
    (raw_root / "metadata").mkdir(parents=True, exist_ok=True)
    (raw_root / "financials").mkdir(parents=True, exist_ok=True)
    (raw_root / "shareholding").mkdir(parents=True, exist_ok=True)

    ticker = "ABC.NS"
    slug = "ABC"

    (raw_root / "metadata" / f"{slug}_metadata.json").write_text(
        json.dumps(
            {
                "ticker": ticker,
                "company_name": "ABC Industries",
                "bse_code": "123456",
                "nse_code": "ABC",
                "sector": "Industrials",
                "industry": "Capital Goods",
                "about_text": "ABC builds mission-critical industrial systems.",
                "website": "https://abc.example.com",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (raw_root / "metadata" / f"{slug}_key_ratios.json").write_text("{}", encoding="utf-8")
    (raw_root / "metadata" / f"{slug}_peers.json").write_text("[]", encoding="utf-8")
    (raw_root / "metadata" / f"{slug}_pros_cons.json").write_text('{"pros": [], "cons": []}', encoding="utf-8")

    years = [2020, 2021, 2022, 2023, 2024]
    annual_periods = [_month_period("Mar", y) for y in years]
    quarterly_periods = [_month_period("Jun", 2024), _month_period("Sep", 2024), _month_period("Dec", 2024), _month_period("Mar", 2025)]

    def _write_long(path: Path, rows: list[dict[str, object]]) -> None:
        pd.DataFrame(rows, columns=["ticker", "metric", "period", "value"]).to_csv(path, index=False)

    annual_pl_rows: list[dict[str, object]] = []
    for i, period in enumerate(annual_periods):
        annual_pl_rows.extend(
            [
                {"ticker": ticker, "metric": "Revenue", "period": period, "value": 1000.0 + (50.0 * i)},
                {"ticker": ticker, "metric": "Net Profit", "period": period, "value": 120.0 + (10.0 * i)},
                {"ticker": ticker, "metric": "EPS", "period": period, "value": 8.0 + (0.5 * i)},
            ]
        )
    _write_long(raw_root / "financials" / f"{slug}_annual_pl.csv", annual_pl_rows)

    annual_bs_rows: list[dict[str, object]] = []
    for i, period in enumerate(annual_periods):
        annual_bs_rows.extend(
            [
                {"ticker": ticker, "metric": "Share Capital", "period": period, "value": 100.0},
                {"ticker": ticker, "metric": "Reserves", "period": period, "value": 500.0 + (40.0 * i)},
                {"ticker": ticker, "metric": "Total Assets", "period": period, "value": 2000.0 + (100.0 * i)},
            ]
        )
    _write_long(raw_root / "financials" / f"{slug}_annual_bs.csv", annual_bs_rows)

    annual_cf_rows: list[dict[str, object]] = []
    for i, period in enumerate(annual_periods):
        annual_cf_rows.extend(
            [
                {"ticker": ticker, "metric": "Cash from Operating Activity", "period": period, "value": 180.0 + (20.0 * i)},
                {"ticker": ticker, "metric": "Cash from Investing Activity", "period": period, "value": -90.0 - (5.0 * i)},
                {"ticker": ticker, "metric": "Net Cash Flow", "period": period, "value": 40.0 + (3.0 * i)},
            ]
        )
    _write_long(raw_root / "financials" / f"{slug}_annual_cf.csv", annual_cf_rows)

    annual_ratios_rows: list[dict[str, object]] = []
    for i, period in enumerate(annual_periods):
        annual_ratios_rows.extend(
            [
                {"ticker": ticker, "metric": "Debtor Days", "period": period, "value": 50.0 - i},
                {"ticker": ticker, "metric": "Inventory Days", "period": period, "value": 40.0 - (0.8 * i)},
                {"ticker": ticker, "metric": "Days Payable", "period": period, "value": 20.0 + (0.5 * i)},
                {"ticker": ticker, "metric": "Cash Conversion Cycle", "period": period, "value": 70.0 - (1.3 * i)},
                {"ticker": ticker, "metric": "Working Capital Days", "period": period, "value": 35.0 - (0.7 * i)},
            ]
        )
    _write_long(raw_root / "financials" / f"{slug}_annual_ratios.csv", annual_ratios_rows)

    quarterly_rows: list[dict[str, object]] = []
    for i, period in enumerate(quarterly_periods):
        quarterly_rows.extend(
            [
                {"ticker": ticker, "metric": "Sales", "period": period, "value": 250.0 + (8.0 * i)},
                {"ticker": ticker, "metric": "Operating Profit", "period": period, "value": 45.0 + (2.0 * i)},
                {"ticker": ticker, "metric": "EPS", "period": period, "value": 2.0 + (0.1 * i)},
            ]
        )
    _write_long(raw_root / "financials" / f"{slug}_quarterly_pl.csv", quarterly_rows)

    shareholding_rows: list[dict[str, object]] = []
    promoter_values = [52.0, 52.6, 53.0, 53.4]
    fii_values = [15.0, 15.3, 15.2, 15.8]
    dii_values = [18.0, 18.1, 18.5, 18.2]
    public_values = [14.0, 13.6, 13.0, 12.4]
    govt_values = [1.0, 0.4, 0.3, 0.2]
    holders = [250000, 252000, 255000, 260000]
    for i, period in enumerate(quarterly_periods):
        shareholding_rows.extend(
            [
                {"ticker": ticker, "metric": "Promoters%", "period": period, "value": promoter_values[i]},
                {"ticker": ticker, "metric": "FIIs%", "period": period, "value": fii_values[i]},
                {"ticker": ticker, "metric": "DIIs%", "period": period, "value": dii_values[i]},
                {"ticker": ticker, "metric": "Public%", "period": period, "value": public_values[i]},
                {"ticker": ticker, "metric": "Government%", "period": period, "value": govt_values[i]},
                {"ticker": ticker, "metric": "No of Shareholders", "period": period, "value": holders[i]},
            ]
        )
    _write_long(raw_root / "shareholding" / f"{slug}_shareholding.csv", shareholding_rows)

    pd.DataFrame(
        [
            {
                "ticker": ticker,
                "url_used": "https://www.screener.in/company/ABC/consolidated/",
                "status": "success",
                "sections_scraped": "A,B,C,D,E,F,G,H,I,J",
                "rows_scraped_total": 123,
                "error_message": "",
                "timestamp": "2026-03-08T12:00:00Z",
                "duration_seconds": 8.1,
            }
        ]
    ).to_csv(raw_root / "scrape_log.csv", index=False)

    processed_root = tmp_path / "data" / "processed"
    build_pipeline_files(raw_dir=raw_root, output_dir=processed_root)

    return {"raw_root": raw_root, "processed_root": processed_root, "ticker": Path(slug)}


def test_scrape_log_exists_and_columns(screener_fixture: dict[str, Path]) -> None:
    log_path = screener_fixture["raw_root"] / "scrape_log.csv"
    assert log_path.exists()
    log = pd.read_csv(log_path)
    assert EXPECTED_LOG_COLUMNS.issubset(set(log.columns))


def test_at_least_one_ticker_has_all_core_files(screener_fixture: dict[str, Path]) -> None:
    raw_root = screener_fixture["raw_root"]
    slug = screener_fixture["ticker"].name
    expected = [
        raw_root / "metadata" / f"{slug}_metadata.json",
        raw_root / "financials" / f"{slug}_quarterly_pl.csv",
        raw_root / "financials" / f"{slug}_annual_pl.csv",
        raw_root / "financials" / f"{slug}_annual_bs.csv",
        raw_root / "financials" / f"{slug}_annual_cf.csv",
        raw_root / "financials" / f"{slug}_annual_ratios.csv",
        raw_root / "shareholding" / f"{slug}_shareholding.csv",
    ]
    assert all(p.exists() for p in expected)


def test_annual_fundamentals_have_no_future_availability_dates(screener_fixture: dict[str, Path]) -> None:
    annual = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_annual.csv")
    avail = pd.to_datetime(annual["availability_date"], errors="coerce")
    now_naive = pd.Timestamp.utcnow().tz_localize(None)
    assert bool((avail <= now_naive).all())


def test_quarterly_fundamentals_have_no_future_availability_dates(screener_fixture: dict[str, Path]) -> None:
    quarterly = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_quarterly.csv")
    avail = pd.to_datetime(quarterly["availability_date"], errors="coerce")
    now_naive = pd.Timestamp.utcnow().tz_localize(None)
    assert bool((avail <= now_naive).all())


def test_shareholding_percentages_sum_near_100(screener_fixture: dict[str, Path]) -> None:
    share = pd.read_csv(screener_fixture["processed_root"] / "screener_shareholding.csv")
    total = (
        pd.to_numeric(share["promoter_pct"], errors="coerce")
        + pd.to_numeric(share["fii_pct"], errors="coerce")
        + pd.to_numeric(share["dii_pct"], errors="coerce")
        + pd.to_numeric(share["public_pct"], errors="coerce")
        + pd.to_numeric(share["govt_pct"], errors="coerce")
    )
    assert bool(((total - 100.0).abs() <= 5.0).all())


def test_numeric_columns_contain_no_string_values(screener_fixture: dict[str, Path]) -> None:
    paths = [
        screener_fixture["processed_root"] / "screener_fundamentals_annual.csv",
        screener_fixture["processed_root"] / "screener_fundamentals_quarterly.csv",
        screener_fixture["processed_root"] / "screener_shareholding.csv",
    ]
    non_numeric_cols = {"ticker", "fiscal_year", "quarter", "availability_date"}
    for path in paths:
        df = pd.read_csv(path)
        for col in [c for c in df.columns if c not in non_numeric_cols]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{path.name}:{col} must be numeric"


def test_annual_year_range_at_least_five_years_for_successful_tickers(screener_fixture: dict[str, Path]) -> None:
    annual = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_annual.csv")
    spans = annual.groupby("ticker", sort=False)["fiscal_year"].nunique()
    assert bool((spans >= 5).all())


def test_promoter_change_feature_is_not_identical_to_promoter_pct(screener_fixture: dict[str, Path]) -> None:
    annual = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_annual.csv")
    share = pd.read_csv(screener_fixture["processed_root"] / "screener_shareholding.csv")

    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    prices = pd.DataFrame(
        {
            "Date": dates,
            "ticker": ["ABC.NS"] * len(dates),
            "Close": np.linspace(100.0, 130.0, num=len(dates)),
            "Volume": np.linspace(1000.0, 2000.0, num=len(dates)),
        }
    )

    panel = FeatureFactory(
        target_horizon_days=1,
        use_screener_extended_features=True,
    ).build_features(
        prices=prices,
        screener_annual=annual,
        screener_shareholding=share,
    )

    assert "screener_promoter_pct" in panel.columns
    assert "screener_promoter_change_1q" in panel.columns
    assert "screener_promoter_pct_cs_z" in panel.columns
    assert "screener_promoter_pct_cs_rank" in panel.columns

    valid = panel[["screener_promoter_pct", "screener_promoter_change_1q"]].dropna()
    assert not valid.empty
    assert not np.allclose(
        valid["screener_promoter_pct"].to_numpy(),
        valid["screener_promoter_change_1q"].to_numpy(),
    )


def test_pit_lag_availability_after_period_end(screener_fixture: dict[str, Path]) -> None:
    annual = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_annual.csv")
    annual_av = pd.to_datetime(annual["availability_date"], errors="coerce")
    annual_end = pd.to_datetime(annual["fiscal_year"].astype(str) + "-12-31", errors="coerce")
    assert bool((annual_av > annual_end).all())

    quarterly = pd.read_csv(screener_fixture["processed_root"] / "screener_fundamentals_quarterly.csv")
    q_end = quarterly["quarter"].map(_q_end_from_label)
    q_av = pd.to_datetime(quarterly["availability_date"], errors="coerce")
    assert bool((q_av > q_end).all())

    share = pd.read_csv(screener_fixture["processed_root"] / "screener_shareholding.csv")
    s_end = share["quarter"].map(_q_end_from_label)
    s_av = pd.to_datetime(share["availability_date"], errors="coerce")
    assert bool((s_av > s_end).all())
