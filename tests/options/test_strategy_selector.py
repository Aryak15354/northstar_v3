from src.intelligence.news_brain.news_signal_state import ShockSeverity, ShockType
from src.options.strategy_library.strategy_selector import StrategySelector
from tests.intelligence.helpers import build_state


def test_bear_spread_selected_on_high_severity():
    selector = StrategySelector({})
    state = build_state(ShockType.OIL_SUPPLY_DISRUPTION, shock_severity=ShockSeverity.HIGH, vix_level=22.0)
    selected = selector.select(state, current_iv_surface={"vix": 22.0, "iv_rank": 58.0, "nifty_intraday_fall_pct": 2.5})
    assert "bear_put_spread" in {item["strategy"] for item in selected}


def test_straddle_rejected_high_iv():
    selector = StrategySelector({})
    state = build_state(ShockType.BANKING_STRESS, shock_severity=ShockSeverity.SEVERE, vix_level=28.0)
    selected = selector.select(state, current_iv_surface={"vix": 28.0, "iv_rank": 75.0, "nifty_intraday_fall_pct": 3.0})
    assert "long_straddle" not in {item["strategy"] for item in selected}


def test_call_selected_for_beneficiary():
    selector = StrategySelector({})
    state = build_state(ShockType.INR_DEPRECIATION, shock_severity=ShockSeverity.HIGH, vix_level=16.0)
    selected = selector.select(state, current_iv_surface={"vix": 16.0, "iv_rank": 32.0, "nifty_intraday_fall_pct": 1.5})
    call_trades = [item for item in selected if item["strategy"] == "long_call"]
    assert call_trades
    assert call_trades[0]["underlying"] in {"INFY", "TCS", "HCLTECH", "WIPRO", "LTIM", "MPHASIS", "PERSISTENT", "COFORGE", "KPITTECH"}


def test_iron_condor_only_when_no_shock():
    selector = StrategySelector({})
    state = build_state(ShockType.FII_OUTFLOW, shock_severity=ShockSeverity.MODERATE, vix_level=21.0)
    selected = selector.select(state, current_iv_surface={"vix": 21.0, "iv_rank": 55.0, "nifty_intraday_fall_pct": 1.5})
    assert "iron_condor" not in {item["strategy"] for item in selected}


def test_crisis_alpha_triggered():
    selector = StrategySelector({})
    state = build_state(ShockType.GLOBAL_RECESSION, shock_severity=ShockSeverity.SEVERE, vix_level=29.0)
    selected = selector.select(state, current_iv_surface={"vix": 29.0, "iv_rank": 80.0, "nifty_intraday_fall_pct": 3.0})
    trades = [item for item in selected if item["strategy"] == "vix_spike_put_spread"]
    assert trades
    assert trades[0]["urgency"] == "immediate"


def test_strategy_sizing_respects_limits():
    selector = StrategySelector(
        {
            "strategy_library": {
                "max_concurrent_strategies": 3,
                "position_sizing": {
                    "max_per_strategy_pct": 2.0,
                    "max_total_options_pct": 4.0,
                },
            }
        }
    )
    state = build_state(ShockType.NONE, shock_severity=ShockSeverity.NONE, vix_level=18.0)
    selected = selector.select(state, current_iv_surface={"vix": 18.0, "iv_rank": 50.0, "nifty_intraday_fall_pct": 0.0})
    assert sum(item["allocation_pct"] for item in selected) <= 4.0 + 1e-9

