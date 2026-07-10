from pathlib import Path

import pandas as pd

from src.data.artifact_contracts import resolve_artifact, validate_contract
from src.data.price_access import read_prices_legacy


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_equity_prices_contract_resolves_to_canonical_store():
    path = resolve_artifact("equity_prices_daily", project_root=PROJECT_ROOT)

    assert path == PROJECT_ROOT / "data/canonical/prices/equity_prices_daily.parquet"


def test_core_data_contracts_are_present_and_structured():
    for name in ["equity_prices_daily", "company_sentiment_daily", "bulk_deals"]:
        result = validate_contract(name, project_root=PROJECT_ROOT)

        assert result.ok, result.problems
        assert result.rows > 0
        assert result.latest is not None


def test_read_prices_legacy_filters_canonical_store():
    df = read_prices_legacy(
        project_root=PROJECT_ROOT,
        columns=["Date", "Close", "ticker"],
        tickers=["RELIANCE.NS"],
        start_date="2026-03-01",
        end_date="2026-03-31",
    )

    assert not df.empty
    assert {"Date", "Close", "ticker"}.issubset(df.columns)
    assert "date" not in df.columns
    assert set(df["ticker"].unique()) == {"RELIANCE.NS"}
    assert df["Date"].min() >= pd.Timestamp("2026-03-01")
    assert df["Date"].max() <= pd.Timestamp("2026-03-31")
