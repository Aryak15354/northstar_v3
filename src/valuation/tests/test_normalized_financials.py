from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from src.valuation.core.normalized_financials import FinancialNormalizer


def _write_long_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _rows(ticker: str, period: str, metrics: dict[str, float]) -> list[dict]:
    return [
        {"ticker": ticker, "metric": metric, "period": period, "value": value}
        for metric, value in metrics.items()
    ]


def test_financial_normalizer_correct_source():
    assert str(FinancialNormalizer.SCREENER_DATA_PATH).endswith("data/raw/vendors/screener/financials")


def test_financial_normalizer_pit_compliance(tmp_path):
    raw_dir = tmp_path / "financials"
    ticker = "TEST"
    annual_pl = []
    annual_pl += _rows(
        ticker,
        "Mar 2023",
        {
            "Sales": 1000,
            "Net Profit": 100,
            "Operating Profit": 150,
            "Interest": 10,
            "Depreciation": 20,
            "Tax %": 25,
        },
    )
    annual_pl += _rows(
        ticker,
        "Mar 2024",
        {
            "Sales": 1100,
            "Net Profit": 120,
            "Operating Profit": 170,
            "Interest": 12,
            "Depreciation": 24,
            "Tax %": 26,
        },
    )
    annual_bs = []
    annual_bs += _rows(
        ticker,
        "Mar 2023",
        {
            "Equity Capital": 10,
            "Reserves": 400,
            "Borrowings": 150,
            "Other Liabilities": 200,
            "Fixed Assets": 300,
            "CWIP": 25,
            "Investments": 40,
            "Other Assets": 185,
            "Total Assets": 550,
            "Total Liabilities": 550,
        },
    )
    annual_bs += _rows(
        ticker,
        "Mar 2024",
        {
            "Equity Capital": 10,
            "Reserves": 450,
            "Borrowings": 140,
            "Other Liabilities": 220,
            "Fixed Assets": 320,
            "CWIP": 30,
            "Investments": 45,
            "Other Assets": 205,
            "Total Assets": 600,
            "Total Liabilities": 600,
        },
    )
    annual_cf = []
    annual_cf += _rows(
        ticker,
        "Mar 2023",
        {
            "Cash from Operating Activity": 130,
            "Cash from Investing Activity": -70,
            "Cash from Financing Activity": -20,
            "Net Cash Flow": 40,
        },
    )
    annual_cf += _rows(
        ticker,
        "Mar 2024",
        {
            "Cash from Operating Activity": 150,
            "Cash from Investing Activity": -80,
            "Cash from Financing Activity": -25,
            "Net Cash Flow": 45,
        },
    )

    _write_long_csv(raw_dir / "TEST_annual_pl.csv", annual_pl)
    _write_long_csv(raw_dir / "TEST_annual_bs.csv", annual_bs)
    _write_long_csv(raw_dir / "TEST_annual_cf.csv", annual_cf)

    normalizer = FinancialNormalizer(
        {
            "screener_data_path": str(raw_dir),
            "screener_metadata_path": str(tmp_path / "metadata"),
            "reporting_lag_days": 75,
        }
    )

    april = normalizer.load("TEST.NS", datetime(2024, 4, 15), "annual")
    assert not april.empty
    assert april["period_end"].max() == pd.Timestamp("2023-03-31")

    june = normalizer.load("TEST.NS", datetime(2024, 6, 15), "annual")
    assert not june.empty
    assert june["period_end"].max() == pd.Timestamp("2024-03-31")


def test_financial_normalizer_supports_kaggle_safe_screener_filenames(tmp_path):
    raw_dir = tmp_path / "financials"
    meta_dir = tmp_path / "metadata"
    ticker = "M&M.NS"

    annual_pl = _rows(
        ticker,
        "Mar 2024",
        {
            "Sales": 1100,
            "Net Profit": 120,
            "Operating Profit": 170,
            "Interest": 12,
            "Depreciation": 24,
            "Tax %": 26,
        },
    )
    annual_bs = _rows(
        ticker,
        "Mar 2024",
        {
            "Equity Capital": 10,
            "Reserves": 450,
            "Borrowings": 140,
            "Other Liabilities": 220,
            "Fixed Assets": 320,
            "CWIP": 30,
            "Investments": 45,
            "Other Assets": 205,
            "Total Assets": 600,
            "Total Liabilities": 600,
        },
    )
    annual_cf = _rows(
        ticker,
        "Mar 2024",
        {
            "Cash from Operating Activity": 150,
            "Cash from Investing Activity": -80,
            "Cash from Financing Activity": -25,
            "Net Cash Flow": 45,
        },
    )

    _write_long_csv(raw_dir / "M_x26_M_annual_pl.csv", annual_pl)
    _write_long_csv(raw_dir / "M_x26_M_annual_bs.csv", annual_bs)
    _write_long_csv(raw_dir / "M_x26_M_annual_cf.csv", annual_cf)
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "M_x26_M_key_ratios.json").write_text(json.dumps({"Current Price": 100.0}), encoding="utf-8")

    normalizer = FinancialNormalizer(
        {
            "screener_data_path": str(raw_dir),
            "screener_metadata_path": str(meta_dir),
            "reporting_lag_days": 75,
        }
    )

    loaded = normalizer.load("M&M.NS", datetime(2024, 6, 15), "annual")

    assert not loaded.empty
    assert loaded["ticker"].iloc[0] == "M&M.NS"


def test_metadata_snapshot_not_broadcast_into_history():
    """N1: the current-day Screener key-ratios snapshot must land ONLY on the
    most-recent statement row, never broadcast/backfilled across historical
    periods (which would leak today's price/ratios into years of history)."""
    fn = FinancialNormalizer({})
    long = pd.DataFrame(
        {
            "ticker": ["AAA.NS"] * 4,
            "period": ["Mar-2019", "Mar-2019", "Mar-2024", "Mar-2024"],
            "metric": ["Sales", "Net Profit", "Sales", "Net Profit"],
            "value": [100.0, 10.0, 200.0, 20.0],
        }
    )
    fn._load_metadata_key_ratios = lambda ticker: {
        "current_price": 999.0,
        "roce_pct": 42.0,
        "shares_outstanding": 5.0,
    }
    wide = fn._normalize_loaded_frame(long, "annual").sort_values("period_end").reset_index(drop=True)
    assert wide["period_end"].dt.year.tolist() == [2019, 2024]
    # Historical row carries no current-day snapshot.
    assert pd.isna(wide["current_price"].iloc[0])
    assert pd.isna(wide["roce_pct"].iloc[0])
    # Latest row does.
    assert wide["current_price"].iloc[-1] == 999.0
    assert wide["roce_pct"].iloc[-1] == 42.0
