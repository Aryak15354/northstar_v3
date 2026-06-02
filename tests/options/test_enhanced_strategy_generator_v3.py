from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd

from src.options.enhanced_strategy_generator_v3 import EnhancedStrategyGeneratorV3
from src.options.strategy_generator import StrategyType


def _chain_with_short_and_valid_expiry(spot: float) -> pd.DataFrame:
    today = date.today()
    short_expiry = today + timedelta(days=2)
    valid_expiry = today + timedelta(days=33)
    rows = []
    for expiry in [short_expiry, valid_expiry]:
        for strike in [90.0, 95.0, 100.0, 105.0, 110.0]:
            rows.append(
                {
                    "strike": strike,
                    "option_type": "CE",
                    "expiry": expiry,
                    "premium": 5.0,
                    "underlying_price": spot,
                    "oi": 1_000,
                    "volume": 500,
                    "delta": 0.55 if strike <= spot else 0.35,
                    "gamma": 0.01,
                    "theta": -0.2,
                    "vega": 0.3,
                    "instrument_key": f"CE::{expiry.isoformat()}::{strike}",
                }
            )
            rows.append(
                {
                    "strike": strike,
                    "option_type": "PE",
                    "expiry": expiry,
                    "premium": 5.0,
                    "underlying_price": spot,
                    "oi": 1_000,
                    "volume": 500,
                    "delta": -0.45 if strike >= spot else -0.65,
                    "gamma": 0.01,
                    "theta": -0.2,
                    "vega": 0.3,
                    "instrument_key": f"PE::{expiry.isoformat()}::{strike}",
                }
            )
    return pd.DataFrame(rows)


def test_generator_prefers_expiry_that_meets_min_days_to_expiry() -> None:
    config = SimpleNamespace(
        eligibility=SimpleNamespace(min_days_to_expiry=5),
    )
    generator = EnhancedStrategyGeneratorV3(config)
    chain = _chain_with_short_and_valid_expiry(spot=100.0)

    strategies = generator.generate_strategy(
        regime="rising_vol_buy",
        underlying="TATASTEEL",
        option_chain=chain,
        spot_price=100.0,
        preferred_strategy="long_straddle",
    )

    assert strategies
    assert strategies[0].strategy_type == StrategyType.LONG_STRADDLE
    assert strategies[0].days_to_expiry >= 5
    assert strategies[0].expiry_date.date() == date.today() + timedelta(days=33)
