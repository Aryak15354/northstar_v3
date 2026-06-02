from __future__ import annotations

import pandas as pd

import scripts.export_sentiment_to_v3 as export_module


def test_prepare_ticker_output_repairs_same_day_availability() -> None:
    df = pd.DataFrame(
        {
            "ticker": ["TCS.NS"],
            "date": [pd.Timestamp("2026-03-25")],
            "availability_date": [pd.Timestamp("2026-03-25")],
            "sentiment_polarity": [0.2],
            "sentiment_conviction": [0.7],
            "sentiment_surprise": [0.1],
            "sentiment_uncertainty": [0.3],
            "news_volume": [2],
            "source": ["nse"],
        }
    )

    out = export_module._prepare_ticker_output(df)

    assert out.loc[0, "availability_date"] == pd.Timestamp("2026-03-26")
    ok, issues = export_module._validate_ticker(out)
    assert ok, issues


def test_prepare_market_output_repairs_weekend_availability_to_next_business_day() -> None:
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-21")],  # Saturday
            "availability_date": [pd.Timestamp("2026-03-21")],
            "india_market_polarity": [0.1],
            "india_market_conviction": [0.8],
            "india_market_uncertainty": [0.2],
            "global_risk_sentiment": [0.05],
            "news_volume_total": [10],
        }
    )

    out = export_module._prepare_market_output(df)

    assert out.loc[0, "availability_date"] == pd.Timestamp("2026-03-23")
    ok, issues = export_module._validate_market(out)
    assert ok, issues
