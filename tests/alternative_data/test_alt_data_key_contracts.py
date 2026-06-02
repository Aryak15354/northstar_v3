from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.alternative_data.alt_data_keys import (
    BULK_ACCUMULATION_BREADTH,
    BULK_DISTRIBUTION_BREADTH,
    BULK_NET_FLOW,
    BULK_SIGNAL_NUMERIC,
    CREDIT_NET_MOMENTUM,
    CREDIT_STRESS_FLAG,
    CREDIT_UPGRADE_RATIO,
    POWER_DEVIATION_SEASONAL,
    POWER_INDUSTRIAL_PROXY,
    POWER_YOY_GROWTH,
)
from src.alternative_data.alternative_feature_block import AlternativeFeatureBlock
from src.alternative_data.alternative_pipeline_runner import (
    AlternativePipelineRunner,
    _numeric_to_smart_money_signal,
)
from src.alternative_data.alternative_state import SmartMoneySignal


def _runner() -> AlternativePipelineRunner:
    return object.__new__(AlternativePipelineRunner)


def test_feature_block_keys_match_runner_expectations() -> None:
    runner = _runner()
    features = {
        CREDIT_UPGRADE_RATIO: 0.6,
        CREDIT_NET_MOMENTUM: 0.1,
        CREDIT_STRESS_FLAG: 0.0,
        BULK_NET_FLOW: 0.2,
        BULK_ACCUMULATION_BREADTH: 0.6,
        BULK_DISTRIBUTION_BREADTH: 0.4,
        BULK_SIGNAL_NUMERIC: 1,
        POWER_YOY_GROWTH: 0.3,
        POWER_DEVIATION_SEASONAL: 0.25,
        POWER_INDUSTRIAL_PROXY: 0.4,
    }
    fresh_detail = {"is_fresh": True, "latest_date": datetime(2026, 3, 21), "df": pd.DataFrame()}

    credit = runner._build_credit_signal(features, datetime(2026, 3, 21), fresh_detail)
    power = runner._build_power_signal(features, datetime(2026, 3, 21), fresh_detail)
    smart_money = runner._build_smart_money_state(features, datetime(2026, 3, 21), fresh_detail)

    assert credit.market_upgrade_ratio == 0.6
    assert credit.net_credit_momentum == 0.1
    assert power.deviation_from_seasonal == 0.25
    assert smart_money.net_institutional_flow_score == 0.2
    assert smart_money.distribution_breadth == 0.4


def test_distribution_breadth_nonzero_when_sells_dominate() -> None:
    bulk_df = pd.DataFrame({"signed_qty": [-100, -200, -150, 50, -80]})
    accumulation_breadth, distribution_breadth, net_breadth = AlternativeFeatureBlock._compute_bulk_breadths(bulk_df)

    assert accumulation_breadth == 0.2
    assert distribution_breadth == 0.8
    assert net_breadth == -0.6


def test_smart_money_signal_not_inverted() -> None:
    result = _numeric_to_smart_money_signal(2)
    assert result in (
        SmartMoneySignal.MILD_ACCUMULATION,
        SmartMoneySignal.STRONG_ACCUMULATION,
    )
    assert result == SmartMoneySignal.STRONG_ACCUMULATION
