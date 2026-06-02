from src.intelligence.news_brain.news_signal_state import ShockSeverity, ShockType
from src.intelligence.shock_engine.rebalance_instruction import InstructionType
from src.intelligence.shock_engine.shock_response_engine import ShockResponseEngine
from tests.intelligence.helpers import build_state


def test_rebalance_reduces_aviation_on_oil_shock():
    engine = ShockResponseEngine({})
    state = build_state(ShockType.OIL_SUPPLY_DISRUPTION, shock_severity=ShockSeverity.SEVERE, vix_level=24.0)
    positions = [
        {"symbol": "INDIGO", "sector": "Services", "weight": 0.05, "adv": 0.50},
    ]
    instructions = engine.get_rebalance_instructions(state, positions)
    assert any(item.instruction_type == InstructionType.REDUCE_EQUITY and item.symbol == "INDIGO" for item in instructions)


def test_hedge_issued_when_rebalance_insufficient():
    engine = ShockResponseEngine({})
    state = build_state(ShockType.OIL_SUPPLY_DISRUPTION, shock_severity=ShockSeverity.SEVERE, vix_level=24.0)
    positions = [
        {"symbol": "INDIGO", "sector": "Services", "weight": 0.05, "adv": 0.01},
    ]
    instructions = engine.get_rebalance_instructions(state, positions)
    assert any(item.instruction_type == InstructionType.HEDGE_WITH_OPTIONS and item.symbol == "INDIGO" for item in instructions)


def test_beneficiary_increase_instruction():
    engine = ShockResponseEngine({})
    state = build_state(ShockType.OIL_SUPPLY_DISRUPTION, shock_severity=ShockSeverity.SEVERE, vix_level=24.0)
    positions = [
        {"symbol": "ONGC", "sector": "Oil Gas & Consumable Fuels", "weight": 0.02, "adv": 1.0},
    ]
    instructions = engine.get_rebalance_instructions(state, positions)
    assert any(item.instruction_type == InstructionType.INCREASE_EQUITY and item.symbol == "ONGC" for item in instructions)


def test_no_action_on_no_shock():
    engine = ShockResponseEngine({})
    state = build_state(ShockType.NONE, shock_severity=ShockSeverity.NONE, vix_level=14.0)
    positions = [
        {"symbol": "INFY", "sector": "Information Technology", "weight": 0.03, "adv": 1.0},
    ]
    plan = engine.evaluate(state, positions)
    assert plan.rebalance_instructions == []
    assert plan.options_instructions == []

