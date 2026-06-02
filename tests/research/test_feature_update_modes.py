from __future__ import annotations

import pandas as pd

from src.research.feature_factory import FeatureFactory


def test_reduced_sentiment_mode_keeps_only_audited_columns() -> None:
    factory = FeatureFactory(
        config={
            "sentiment_feature_mode": "reduced",
            "feature_groups": {
                "company_sentiment_nlp": {
                    "reduced_keep": [
                        "sent_northstar_score",
                        "sentiment_polarity",
                        "agreement_score",
                    ]
                },
                "market_sentiment_macro_overlay": {
                    "reduced_keep": [
                        "macro_sentiment_polarity",
                        "mkt_sent_polarity",
                    ]
                },
            },
        }
    )
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-20")],
            "ticker": ["AAA.NS"],
            "close": [100.0],
            "sent_northstar_score": [0.9],
            "sentiment_polarity": [0.2],
            "agreement_score": [0.4],
            "sentiment_5d_mean": [0.3],
            "event_positive_flag": [1.0],
            "macro_sentiment_polarity": [0.1],
            "macro_sentiment_bias": [0.5],
            "mkt_sent_polarity": [0.2],
            "mkt_sent_policy_weight": [0.3],
        }
    )

    reduced = factory.apply_sentiment_feature_mode(frame)

    assert "sent_northstar_score" in reduced.columns
    assert "sentiment_polarity" in reduced.columns
    assert "agreement_score" in reduced.columns
    assert "macro_sentiment_polarity" in reduced.columns
    assert "mkt_sent_polarity" in reduced.columns
    assert "sentiment_5d_mean" not in reduced.columns
    assert "event_positive_flag" not in reduced.columns
    assert "macro_sentiment_bias" not in reduced.columns
    assert "mkt_sent_policy_weight" not in reduced.columns
    assert "close" in reduced.columns


def test_rbi_dbie_macro_merge_adds_requested_columns(monkeypatch) -> None:
    dates = pd.bdate_range("2026-01-01", periods=90)
    panel = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA.NS"] * len(dates),
            "close": [100.0] * len(dates),
        }
    )
    raw = pd.DataFrame(
        {
            "period_date": dates[::5],
            "release_date": dates[::5],
            "weekly_core_Policy Repo Rate (%)": [6.50 + 0.01 * i for i in range(len(dates[::5]))],
            "weekly_core_10-Year G-Sec Yield (FBIL) (%)": [7.20 + 0.02 * i for i in range(len(dates[::5]))],
            "weekly_core_91-Day Treasury Bill (Primary) Yield (%)": [6.80 + 0.01 * i for i in range(len(dates[::5]))],
            "monthly_core_Consumer Price Index (2012=100)": [140.0 + 0.5 * i for i in range(len(dates[::5]))],
        }
    )

    def _fake_load_rbi_data(self, as_of_date, indicators=None):  # noqa: ANN001
        return raw.copy()

    monkeypatch.setattr("src.ingestion.macro_loader.MacroLoader.load_rbi_data", _fake_load_rbi_data)

    factory = FeatureFactory(config={"use_macro_features": True})
    enriched = factory._merge_rbi_dbie_macro_features(panel)

    for column in [
        "rbi_repo_rate_level",
        "rbi_repo_rate_ts_z",
        "rbi_repo_rate_change_13w",
        "yield_curve_slope",
        "yield_curve_slope_ts_z",
        "cpi_surprise",
        "cpi_surprise_ts_z",
    ]:
        assert column in enriched.columns

    assert enriched["rbi_repo_rate_level"].notna().any()
    assert enriched["yield_curve_slope"].notna().any()
    assert enriched["cpi_surprise"].notna().any()
