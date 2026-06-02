from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

import src.intelligence.news_brain.news_brain as news_brain_module
import src.intelligence.news_brain.layers.company_news_layer as company_layer_module
import src.intelligence.news_brain.layers.market_news_layer as market_layer_module
import src.intelligence.news_brain.layers.macro_news_layer as macro_layer_module
from src.intelligence.news_brain.news_brain import NewsBrain
from src.intelligence.news_brain.news_signal_state import ShockType


def _write_brain_fixture_tree(root: Path) -> None:
    (root / "data/canonical/news").mkdir(parents=True, exist_ok=True)
    (root / "data/canonical/sentiment").mkdir(parents=True, exist_ok=True)
    (root / "data/processed/sentiment").mkdir(parents=True, exist_ok=True)
    (root / "data/processed").mkdir(parents=True, exist_ok=True)
    (root / "data/macro").mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "ticker": ["INFY.NS", "RELIANCE.NS", "HDFCBANK.NS"],
            "Industry": ["Information Technology", "Oil Gas & Consumable Fuels", "Financial Services"],
        }
    ).to_parquet(root / "data/processed/portfolio_weights.parquet", index=False)

    pd.DataFrame(
        {
            "ticker": ["INFY.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%"],
            "source": ["rss"],
            "date": pd.to_datetime(["2026-03-20 09:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:00:00"]),
        }
    ).to_parquet(root / "data/canonical/news/company_news_history.parquet", index=False)

    pd.DataFrame(
        {
            "headline": ["RBI raises repo rate by 25 basis points"],
            "source": ["rss"],
            "date": pd.to_datetime(["2026-03-20 10:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 12:00:00"]),
        }
    ).to_parquet(root / "data/canonical/news/market_news_history.parquet", index=False)

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20"]),
            "india_vix": [19.0],
            "breadth_pct": [48.0],
            "crude_price_change_pct": [1.5],
            "inr_change_pct": [-0.4],
        }
    ).to_parquet(root / "data/processed/market_state.parquet", index=False)

    macro_df = pd.DataFrame(
        {
            "weekly_core_Policy Repo Rate (%)": [6.25, 6.50],
            "daily_other_RBI'S REFERENCE RATE: INR PER USD": [83.0, 83.4],
            "weekly_core_10-Year G-Sec Yield (FBIL) (%)": [7.10, 7.25],
            "daily_other_NSE S&P CNX NIFTY": [22000.0, 21890.0],
        },
        index=pd.to_datetime(["2026-03-19", "2026-03-20"]),
    )
    macro_df.to_parquet(root / "data/macro/comprehensive_rbi_data.parquet")


def test_news_brain_runs_with_actual_nlp_layers_and_temp_canonical_data(tmp_path, monkeypatch):
    _write_brain_fixture_tree(tmp_path)
    monkeypatch.setattr(news_brain_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(company_layer_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(market_layer_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(macro_layer_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(NewsBrain, "_write_snapshot", lambda self, state: None)

    brain = NewsBrain(
        {
            "news_brain": {
                "company_layer": {
                    "sentiment_negative_threshold": -0.30,
                    "sentiment_positive_threshold": 0.30,
                    "sentiment_conviction_threshold": 0.60,
                    "bellwether_tickers": ["INFY"],
                }
            },
            "nlp": {
                "models": {"sentiment": {"device": "cpu", "batch_size": 8, "max_length": 128}},
                "pipeline": {"availability_lag_hours": 2, "min_headline_length": 10, "max_headline_length": 256, "min_confidence": 0.55},
            },
        }
    )

    state = brain.run_cycle(datetime(2026, 3, 20, 13, 0))

    assert state.available is True
    assert state.primary_shock_type == ShockType.RATE_HIKE_RBI
    assert any(signal.ticker == "INFY.NS" for signal in state.company_signals)
    assert any(signal.signal_type == "macro_rate_hike" for signal in state.market_signals + state.macro_signals)
    assert "nlp_pipeline" in state.sources_used
