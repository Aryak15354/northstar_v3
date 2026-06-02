#!/usr/bin/env python3

from __future__ import annotations

import pandas as pd

from src.dashboard.data import data_manager


def test_load_latest_chain_cache_merges_freshest_file_per_symbol(tmp_path, monkeypatch) -> None:
    cache_dir = tmp_path / "data" / "options" / "chains_cache"
    cache_dir.mkdir(parents=True)

    older_nifty = pd.DataFrame(
        [
            {
                "timestamp": "2026-03-19T15:00:00+05:30",
                "strike": 22000,
                "option_type": "CE",
                "underlying_price": 22500.0,
                "iv": 0.19,
            }
        ]
    )
    latest_nifty = pd.DataFrame(
        [
            {
                "timestamp": "2026-03-19T15:30:00+05:30",
                "strike": 22100,
                "option_type": "CE",
                "underlying_price": 22600.0,
                "iv": 0.21,
            }
        ]
    )
    latest_banknifty = pd.DataFrame(
        [
            {
                "timestamp": "2026-03-19T15:31:00+05:30",
                "strike": 48000,
                "option_type": "PE",
                "underlying_price": 47800.0,
                "iv": 0.24,
            }
        ]
    )

    older_nifty.to_parquet(cache_dir / "NIFTY_20260319_150000.parquet", index=False)
    latest_nifty.to_parquet(cache_dir / "NIFTY_20260319_153000.parquet", index=False)
    latest_banknifty.to_parquet(cache_dir / "BANKNIFTY_20260319_153100.parquet", index=False)

    monkeypatch.setattr(data_manager, "PROJECT_ROOT", tmp_path)

    result = data_manager._load_latest_chain_cache(["NIFTY", "BANKNIFTY"])

    assert set(result["symbol"]) == {"NIFTY", "BANKNIFTY"}
    assert result.loc[result["symbol"] == "NIFTY", "strike"].tolist() == [22100]
    assert result.loc[result["symbol"] == "BANKNIFTY", "strike"].tolist() == [48000]
    assert result["option_type"].tolist() == ["P", "C"] or result["option_type"].tolist() == ["C", "P"]
    assert "date" in result.columns
    assert "moneyness" in result.columns

