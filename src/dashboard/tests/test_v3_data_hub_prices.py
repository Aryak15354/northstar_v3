from pathlib import Path

from src.dashboard.v3_data_hub import V3DataHub


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_prices_filtered_reads_canonical_prices_with_legacy_columns():
    hub = V3DataHub(project_root=PROJECT_ROOT)

    df = hub.prices_filtered(["RELIANCE.NS"], columns=["Date", "Close", "ticker"])

    assert df is not None
    assert not df.empty
    assert {"Date", "Close", "ticker"}.issubset(df.columns)
    assert "date" not in df.columns
    assert "close" not in df.columns
    assert set(df["ticker"].unique()) == {"RELIANCE.NS"}
