from datetime import datetime

from src.options.strategy_library.strategy_executor import StrategyExecutor


def test_bear_put_spread_builds_two_put_legs():
    executor = StrategyExecutor()
    built = executor.build("bear_put_spread", "NIFTY", spot_price=22500.0, sizing_lots=2, as_of_datetime=datetime(2026, 3, 19))
    assert len(built["legs"]) == 2
    assert {leg["instrument_type"] for leg in built["legs"]} == {"PUT"}


def test_delta_hedge_synthetic_builds_futures_and_put():
    executor = StrategyExecutor()
    built = executor.build("delta_hedge_synthetic", "NIFTY", spot_price=22500.0, sizing_lots=4, as_of_datetime=datetime(2026, 3, 19))
    instrument_types = [leg["instrument_type"] for leg in built["legs"]]
    assert "FUTURES" in instrument_types
    assert "PUT" in instrument_types


def test_call_backspread_respects_ratio():
    executor = StrategyExecutor()
    built = executor.build("call_backspread", "BANKNIFTY", spot_price=48000.0, sizing_lots=3, as_of_datetime=datetime(2026, 3, 19))
    quantities = [leg["quantity"] for leg in built["legs"]]
    assert quantities == [3, 6]

