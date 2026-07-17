from datetime import datetime

from src.options.strategy_library.strategy_executor import StrategyExecutor


def test_strategy_executor_builds_defined_risk_spread() -> None:
    order = StrategyExecutor().build(
        "bear_put_spread",
        underlying="NIFTY",
        spot_price=22000,
        sizing_lots=2,
        as_of_datetime=datetime(2026, 1, 2, 9, 30),
    )

    assert order["strategy"] == "bear_put_spread"
    assert len(order["legs"]) == 2
    assert {leg["action"] for leg in order["legs"]} == {"BUY", "SELL"}
    assert all(leg["quantity"] == 2 for leg in order["legs"])
