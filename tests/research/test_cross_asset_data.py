from pathlib import Path

import pandas as pd

from src.research.cross_asset_data import build_coverage_manifest, build_cross_asset_panel, discover_symbols


def test_build_cross_asset_panel_and_manifest(tmp_path: Path) -> None:
    forex_dir = tmp_path / "forex"
    commodities_dir = tmp_path / "commodities"
    forex_dir.mkdir()
    commodities_dir.mkdir()

    pd.DataFrame(
        [
            {"Date": "2026-03-30", "Open": 83.1, "High": 83.3, "Low": 82.9, "Close": 83.2, "Adj Close": 83.2, "Volume": 0, "Symbol": "USDINR=X"},
            {"Date": "2026-03-31", "Open": 83.2, "High": 83.4, "Low": 83.0, "Close": 83.1, "Adj Close": 83.1, "Volume": 0, "Symbol": "USDINR=X"},
        ]
    ).to_csv(forex_dir / "USDINR=X.csv", index=False)

    pd.DataFrame(
        [
            {"Date": "2026-03-30", "Open": 72.1, "High": 73.0, "Low": 71.9, "Close": 72.8, "Adj Close": 72.8, "Volume": 10, "Symbol": "CL=F"},
        ]
    ).to_csv(commodities_dir / "CL=F.csv", index=False)

    panel = build_cross_asset_panel(tmp_path)
    manifest = build_coverage_manifest(tmp_path, as_of=pd.Timestamp("2026-04-01"))

    assert len(panel) == 3
    assert set(panel["asset_class"]) == {"forex", "commodities"}
    assert set(panel["symbol"]) == {"USDINR=X", "CL=F"}
    assert len(manifest["assets"]) == 2
    assert max(asset["stale_days"] for asset in manifest["assets"] if asset["stale_days"] is not None) <= 2


def test_cross_asset_manifest_prefers_symbol_column_over_sanitized_filename(tmp_path: Path) -> None:
    forex_dir = tmp_path / "forex"
    forex_dir.mkdir()

    pd.DataFrame(
        [
            {"Date": "2026-03-31", "Open": 83.2, "High": 83.4, "Low": 83.0, "Close": 83.1, "Adj Close": 83.1, "Volume": 0, "Symbol": "USDINR=X"},
        ]
    ).to_csv(forex_dir / "USDINR_x3d_X.csv", index=False)

    discovered = discover_symbols(tmp_path, ["forex"])
    manifest = build_coverage_manifest(tmp_path, as_of=pd.Timestamp("2026-04-01"))

    assert discovered["forex"] == ["USDINR=X"]
    assert manifest["assets"][0]["symbol"] == "USDINR=X"
