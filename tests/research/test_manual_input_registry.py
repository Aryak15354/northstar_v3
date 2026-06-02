from pathlib import Path

import pandas as pd

from src.research.manual_input_registry import (
    build_legacy_universe,
    load_excel_sheet,
    merge_universe_sources,
)


def test_load_excel_sheet_detects_offset_header(tmp_path: Path) -> None:
    workbook = tmp_path / "major.xlsx"
    raw = pd.DataFrame(
        [
            ["Northstar title", None, None],
            ["Section row", None, None],
            ["EVENT_ID", "EVENT_NAME", "START_DATE"],
            ["E001", "Test Event", "2026-01-01"],
        ]
    )
    with pd.ExcelWriter(workbook) as writer:
        raw.to_excel(writer, sheet_name="NSE_Regime_Events", index=False, header=False)

    frame = load_excel_sheet(
        workbook,
        "NSE_Regime_Events",
        required_columns=["EVENT_ID", "EVENT_NAME", "START_DATE"],
        filter_col="event_id",
        filter_regex=r"E\d{3}",
    )

    assert list(frame.columns) == ["event_id", "event_name", "start_date"]
    assert frame.to_dict("records") == [{"event_id": "E001", "event_name": "Test Event", "start_date": "2026-01-01"}]


def test_merge_universe_sources_preserves_enriched_fields() -> None:
    csv_df = pd.DataFrame(
        [
            {
                "Company Name": "Alpha Ltd.",
                "NSE Symbol": "ALPHA",
                "ISIN": "INE000A01011",
                "NIFTY500 Broad Sector": "Financial Services",
                "Subsector": "Lending",
                "HQ City": "Mumbai",
                "Conglomerate / Group": "Alpha Group",
                "International Brand / MNC Subsidiary": "No",
                "Commodity Sensitivities": "Gold",
                "Sector & Macro Sensitivities": "Rates",
                "Key Interconnections & Peers": "Peer A",
                "Data Enrichment Status": "Full",
            }
        ]
    )
    workbook_df = pd.DataFrame(
        [
            {
                "Company Name": "Alpha Ltd.",
                "NSE Symbol": "ALPHA",
                "ISIN": "INE000A01011",
                "NIFTY500 Broad Sector": "Financial Services",
                "Subsector": "Lending",
                "HQ City": "Mumbai",
                "Conglomerate / Group": "Alpha Group",
                "Intl Brand / MNC": "No",
                "Commodity Sensitivities": "Gold",
                "Sector & Macro Sensitivities": "Rates",
                "Key Interconnections & Peers": "Peer A",
            }
        ]
    )

    merged, comparison = merge_universe_sources(csv_df, workbook_df)
    legacy = build_legacy_universe(merged)

    assert len(merged) == 1
    assert merged.loc[0, "ticker"] == "ALPHA.NS"
    assert merged.loc[0, "data_enrichment_status"] == "Full"
    assert legacy.loc[0, "Symbol"] == "ALPHA"
    assert legacy.loc[0, "Industry"] == "Financial Services"
    assert comparison["workbook_only_symbols"] == []
    assert comparison["csv_only_symbols"] == []
