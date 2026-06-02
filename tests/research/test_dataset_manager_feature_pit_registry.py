from __future__ import annotations

import logging

import pandas as pd
import pytest

from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _dataset_runtime_config
from src.research.dataset_manager import DatasetManager


def _manager_with_registry() -> DatasetManager:
    return DatasetManager(
        config={
            "feature_pit_enforce": True,
            "pit_sentiment_lag_days": 1,
            "pit_financials_plus_days": 2,
            "pit_macro_lag_days": 1,
            "feature_pit_lags": {
                "event_*": "sentiment",
                "narrative_*": "sentiment",
                "topic_*": "sentiment",
                "val_*": "financials",
                "piotroski_fscore*": "financials",
                "earnings_quality_ratio*": "financials",
                "bab": "price",
                "amihud_illiquidity*": "price",
                "max_ret_20d*": "price",
                "rbi_repo_rate*": "macro",
                "yield_curve_slope*": "macro",
                "cpi_surprise*": "macro",
            },
        }
    )


def test_feature_pit_registry_accepts_sentiment_and_valuation_derivatives() -> None:
    manager = _manager_with_registry()

    matched, missing, base_count = manager._enforce_feature_pit_registry(
        [
            "event_positive_flag",
            "narrative_strength",
            "topic_drift",
            "val_composite_score_zscore",
            "val_margin_of_safety_zscore",
            "val_quality_composite",
        ]
    )

    assert missing == []
    assert base_count == 6
    assert matched["event_positive_flag"] == 1.0
    assert matched["narrative_strength"] == 1.0
    assert matched["topic_drift"] == 1.0
    assert matched["val_composite_score_zscore"] == 2.0
    assert matched["val_margin_of_safety_zscore"] == 2.0
    assert matched["val_quality_composite"] == 2.0


def test_feature_pit_registry_still_raises_for_unknown_features() -> None:
    manager = _manager_with_registry()

    with pytest.raises(ValueError, match="feature_pit_lag_missing"):
        manager._enforce_feature_pit_registry(["unknown_factor"])


def test_feature_pit_registry_accepts_gap9_and_rbi_macro_features() -> None:
    manager = _manager_with_registry()

    matched, missing, base_count = manager._enforce_feature_pit_registry(
        [
            "piotroski_fscore",
            "piotroski_fscore_cs_z",
            "earnings_quality_ratio_cs_rank",
            "bab_signal",
            "amihud_illiquidity_cs_z",
            "max_ret_20d_cs_rank",
            "rbi_repo_rate_level",
            "rbi_repo_rate_ts_z",
            "yield_curve_slope",
            "cpi_surprise_ts_z",
        ]
    )

    assert missing == []
    assert base_count == 9
    assert matched["piotroski_fscore"] == 2.0
    assert matched["piotroski_fscore_cs_z"] == 2.0
    assert matched["earnings_quality_ratio_cs_rank"] == 2.0
    assert matched["bab_signal"] == 0.0
    assert matched["amihud_illiquidity_cs_z"] == 0.0
    assert matched["max_ret_20d_cs_rank"] == 0.0
    assert matched["rbi_repo_rate_level"] == 1.0
    assert matched["rbi_repo_rate_ts_z"] == 1.0
    assert matched["yield_curve_slope"] == 1.0
    assert matched["cpi_surprise_ts_z"] == 1.0


def test_feature_correlation_warning_limit_suppresses_extra_pairs(caplog: pytest.LogCaptureFixture) -> None:
    manager = DatasetManager(
        config={
            "feature_budget": 10,
            "feature_budget_enforce": False,
            "feature_correlation_enforce": False,
            "feature_correlation_warn_threshold": 0.7,
            "feature_correlation_reject_threshold": 1.1,
            "feature_correlation_warn_limit": 1,
        }
    )
    frame = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [2.0, 4.0, 6.0, 8.0, 10.0],
            "c": [3.0, 6.0, 9.0, 12.0, 15.0],
        }
    )

    with caplog.at_level(logging.WARNING):
        manager._enforce_feature_budget_and_correlation(frame, list(frame.columns), n_tickers=25)

    warning_lines = [rec.message for rec in caplog.records if "[feature-corr] warning" in rec.message]
    suppressed = [rec.message for rec in caplog.records if "suppressed" in rec.message]
    assert len(warning_lines) == 1
    assert suppressed


def test_weekly_export_registry_rules_cover_macro_sentiment_and_schema_gap_features(tmp_path) -> None:
    cfg = _dataset_runtime_config(
        policy_path=tmp_path / "research_policy.yaml",
        start_date="2019-01-01",
        end_date="2026-03-27",
        lookback_days=3200,
        max_tickers=0,
        max_rows=0,
        low_resource_mode="false",
        profile="full",
    )
    cfg["feature_pit_enforce"] = True
    manager = DatasetManager(config=cfg)

    matched, missing, base_count = manager._enforce_feature_pit_registry(
        [
            "gst_yoy_growth",
            "power_yoy_growth",
            "mkt_sent_conviction",
            "mkt_sent_delta_polarity",
            "regime_code",
            "mom20_x_liquidity",
            "res_mom20_x_liquidity",
            "screener_cfo_to_pat",
            "screener_fii_pct",
            "inrusd_4w_return",
            "days_since_earnings_available",
            "international_revenue_proxy",
            "vol20_x_regime_modifier",
            "yield_curve_slope",
            "rbi_rate_chg",
            "vix_india_4w",
            "stock_x_crude",
            "us_10y_4w",
            "insider_buy_flag_30d",
        ]
    )

    assert missing == []
    assert base_count == 19
    assert matched["gst_yoy_growth"] == 1.0
    assert matched["power_yoy_growth"] == 1.0
    assert matched["mkt_sent_conviction"] == 1.0
    assert matched["mkt_sent_delta_polarity"] == 1.0
    assert matched["regime_code"] == 1.0
    assert matched["mom20_x_liquidity"] == 0.0
    assert matched["res_mom20_x_liquidity"] == 0.0
    assert matched["screener_cfo_to_pat"] == 60.0
    assert matched["screener_fii_pct"] == 2.0
    assert matched["inrusd_4w_return"] == 1.0
    assert matched["days_since_earnings_available"] == 1.0
    assert matched["international_revenue_proxy"] == 0.0
    assert matched["vol20_x_regime_modifier"] == 1.0
    assert matched["yield_curve_slope"] == 1.0
    assert matched["rbi_rate_chg"] == 1.0
    assert matched["vix_india_4w"] == 1.0
    assert matched["stock_x_crude"] == 1.0
    assert matched["us_10y_4w"] == 1.0
    assert matched["insider_buy_flag_30d"] == 1.0
