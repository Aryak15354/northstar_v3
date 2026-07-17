from datetime import datetime

from src.intelligence.news_brain.news_signal_state import (
    MarketIntelligenceState,
    ShockDirection,
    ShockSeverity,
    ShockType,
)
from src.options.strategy_library.strategy_selector import StrategySelector


def test_strategy_selector_returns_bearish_shock_hedges() -> None:
    state = MarketIntelligenceState(
        computed_at=datetime(2026, 1, 2, 9, 30),
        primary_shock_type=ShockType.GEOPOLITICAL_CONFLICT,
        shock_severity=ShockSeverity.HIGH,
        shock_direction=ShockDirection.BEARISH,
        shock_confidence=0.8,
    )

    selected = StrategySelector().select(state, {"vix_level": 24.0, "iv_rank": 60.0})

    assert selected
    assert selected[0]["strategy"] in {"bear_put_spread", "ratio_put_spread", "protective_put"}
    assert all(item["allocation_pct"] >= 0 for item in selected)
