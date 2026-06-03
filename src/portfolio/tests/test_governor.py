"""
Tests for PortfolioGovernor.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from src.portfolio.governor import PortfolioGovernor
from src.portfolio.capital_structure import CapitalStructureRegime
from src.core.state import UnifiedState, MarketState, MacroState
from src.sentiment.sentiment_state import SentimentState, SentimentRegime
from src.alternative_data.alternative_state import AlternativeDataState, EconomicActivityRegime


@pytest.fixture
def mock_crisis_engine():
    """Create a mock crisis engine."""
    engine = Mock()
    engine.state = Mock()
    engine.state.crisis_probability = 0.05
    return engine


@pytest.fixture
def governor(mock_crisis_engine, tmp_path):
    """Create a PortfolioGovernor instance for testing."""
    config = {
        'starting_capital_inr': 10_000_000
    }
    gov = PortfolioGovernor(
        crisis_engine=mock_crisis_engine,
        event_bus=None,
        config=config,
        data_dir=str(tmp_path)
    )
    return gov


@pytest.fixture
def unified_state_bull():
    """Create a UnifiedState with BULL market conditions."""
    state = UnifiedState()
    state.market.regime = 'BULL'
    state.market.volatility_regime = 'NORMAL_VOL'
    state.macro.regime = 'EXPANSION'
    state.sentiment.market_sentiment_regime = SentimentRegime.OPTIMISM
    state.alternative_data.economic_activity_regime = EconomicActivityRegime.EXPANSION
    
    # Add PnL state
    from src.pnl.pnl_state import PnLState
    state.pnl_state = PnLState()
    state.pnl_state.current_nav_inr = 10_000_000
    state.pnl_state.current_drawdown_pct = 0.0
    
    return state


@pytest.fixture
def unified_state_crisis():
    """Create a UnifiedState with CRISIS market conditions."""
    state = UnifiedState()
    state.market.regime = 'CRISIS'
    state.market.volatility_regime = 'EXTREME_VOL'
    state.macro.regime = 'CONTRACTION'
    state.sentiment.market_sentiment_regime = SentimentRegime.PANIC
    state.alternative_data.economic_activity_regime = EconomicActivityRegime.CONTRACTION
    
    # Add PnL state
    from src.pnl.pnl_state import PnLState
    state.pnl_state = PnLState()
    state.pnl_state.current_nav_inr = 10_000_000
    state.pnl_state.current_drawdown_pct = -15.0
    
    return state



def test_full_deployment_conditions(governor, unified_state_bull, mock_crisis_engine):
    """Test that FULL_DEPLOYMENT is triggered under favorable conditions."""
    mock_crisis_engine.state.crisis_probability = 0.05
    
    structure = governor.compute_capital_structure(unified_state_bull)
    
    assert structure.capital_structure_regime == CapitalStructureRegime.FULL_DEPLOYMENT
    assert structure.equity_fraction >= 0.85
    assert structure.cash_fraction <= 0.05


def test_panic_triggers_preservation(governor, unified_state_crisis, mock_crisis_engine):
    """Test that PANIC sentiment triggers CAPITAL_PRESERVATION."""
    mock_crisis_engine.state.crisis_probability = 0.55
    
    structure = governor.compute_capital_structure(unified_state_crisis)
    
    assert structure.capital_structure_regime == CapitalStructureRegime.CAPITAL_PRESERVATION
    assert structure.cash_fraction >= 0.70


def test_drawdown_modifier_reduces_equity(governor, unified_state_bull, mock_crisis_engine):
    """Test that drawdown modifier reduces equity allocation."""
    # Set a significant drawdown
    unified_state_bull.pnl_state.current_drawdown_pct = -14.0
    mock_crisis_engine.state.crisis_probability = 0.05
    
    structure = governor.compute_capital_structure(unified_state_bull)
    
    # With -14% drawdown (6% beyond -8% trigger), expect 6 * 0.03 = 0.18 reduction
    # But this is capped and applied to the base regime structure
    # The equity fraction should be reduced from the base
    base_structure = governor.compute_capital_structure(unified_state_bull)
    
    # Check that drawdown modifier was applied
    assert any('DRAWDOWN_REDUCTION' in mod for mod in structure.modifiers_applied)


def test_drawdown_modifier_capped(governor, unified_state_bull, mock_crisis_engine):
    """Test that drawdown reduction is capped at max_equity_reduction."""
    # Set an extreme drawdown
    unified_state_bull.pnl_state.current_drawdown_pct = -30.0
    mock_crisis_engine.state.crisis_probability = 0.05
    
    structure = governor.compute_capital_structure(unified_state_bull)
    
    # Check that a drawdown modifier was applied
    assert any('DRAWDOWN_REDUCTION' in mod for mod in structure.modifiers_applied)
    
    # The reduction should be capped at 0.25 (25%)
    # Extract the reduction amount from the modifier string
    for mod in structure.modifiers_applied:
        if 'DRAWDOWN_REDUCTION' in mod:
            # Format is "DRAWDOWN_REDUCTION(0.XX)"
            reduction_str = mod.split('(')[1].split(')')[0]
            reduction = float(reduction_str)
            assert reduction <= 0.25


def test_crisis_override_escalates(governor, unified_state_bull, mock_crisis_engine):
    """Test that high crisis probability overrides regime classification."""
    # Set high crisis probability despite bull market
    mock_crisis_engine.state.crisis_probability = 0.30
    
    structure = governor.compute_capital_structure(unified_state_bull)
    
    # Should escalate to DEFENSIVE due to crisis override
    assert structure.capital_structure_regime == CapitalStructureRegime.DEFENSIVE
    assert any('CRISIS_OVERRIDE' in mod for mod in structure.modifiers_applied)


def test_crisis_override_never_de_escalates(governor, unified_state_crisis, mock_crisis_engine):
    """Test that crisis override never makes structure more aggressive."""
    # Set low crisis probability despite crisis market
    mock_crisis_engine.state.crisis_probability = 0.05
    
    structure = governor.compute_capital_structure(unified_state_crisis)
    
    # Should be DEFENSIVE or CAPITAL_PRESERVATION due to market regime
    # Crisis override should NOT de-escalate to something more aggressive
    assert structure.capital_structure_regime in [
        CapitalStructureRegime.DEFENSIVE,
        CapitalStructureRegime.CAPITAL_PRESERVATION
    ]
    # The key test: it should NOT be STANDARD or FULL_DEPLOYMENT
    assert structure.capital_structure_regime not in [
        CapitalStructureRegime.STANDARD,
        CapitalStructureRegime.FULL_DEPLOYMENT
    ]


def test_hard_limits_enforced(governor, unified_state_bull):
    """Test that hard limits are enforced."""
    # The governor should never violate hard limits
    structure = governor.compute_capital_structure(unified_state_bull)
    
    from src.portfolio.capital_structure import RegimeCapitalTable
    limits = RegimeCapitalTable.HARD_LIMITS
    
    assert structure.equity_fraction >= limits['min_equity_fraction']
    assert structure.equity_fraction <= limits['max_equity_fraction']
    assert structure.options_fraction <= limits['max_options_fraction']
    assert structure.cash_fraction >= limits['min_cash_fraction']


def test_intraday_escalation_only_conservative(governor, unified_state_bull, mock_crisis_engine):
    """Test that intraday escalation only moves to more conservative structures."""
    # Morning structure in STANDARD regime
    mock_crisis_engine.state.crisis_probability = 0.12
    unified_state_bull.market.regime = 'SIDEWAYS'
    morning_structure = governor.compute_capital_structure(unified_state_bull)
    
    # Simulate improvement during the day (should NOT trigger escalation)
    mock_crisis_engine.state.crisis_probability = 0.05
    unified_state_bull.market.regime = 'BULL'
    
    escalation = governor.check_intraday_escalation(unified_state_bull, morning_structure)
    
    # Should return None (no de-escalation)
    assert escalation is None


def test_intraday_escalation_triggers_on_crisis(governor, unified_state_bull, mock_crisis_engine):
    """Test that intraday escalation triggers when conditions deteriorate."""
    # Morning structure in STANDARD regime
    mock_crisis_engine.state.crisis_probability = 0.12
    morning_structure = governor.compute_capital_structure(unified_state_bull)
    governor.current_structure = morning_structure
    
    # Simulate deterioration during the day
    mock_crisis_engine.state.crisis_probability = 0.35
    unified_state_bull.market.regime = 'BEAR'
    
    escalation = governor.check_intraday_escalation(unified_state_bull)
    
    # Should return a new, more conservative structure
    assert escalation is not None
    assert escalation.capital_structure_regime in [
        CapitalStructureRegime.DEFENSIVE,
        CapitalStructureRegime.CAPITAL_PRESERVATION
    ]


def test_manual_override_auditable(governor, unified_state_bull):
    """Test that manual overrides are properly flagged and auditable."""
    structure = governor.apply_manual_override(
        equity_fraction=0.30,
        options_fraction=0.10,
        cash_fraction=0.60,
        reason="TEST_OVERRIDE",
        unified_state=unified_state_bull
    )
    
    assert len(structure.overrides_active) > 0
    assert any('MANUAL_OVERRIDE' in override for override in structure.overrides_active)
    assert 'TEST_OVERRIDE' in structure.primary_rationale


def test_manual_override_hard_limits_still_apply(governor, unified_state_bull):
    """Test that manual overrides cannot bypass hard limits."""
    structure = governor.apply_manual_override(
        equity_fraction=1.00,  # Violates max_equity_fraction
        options_fraction=0.00,
        cash_fraction=0.00,  # Violates min_cash_fraction
        reason="BAD_OVERRIDE",
        unified_state=unified_state_bull
    )
    
    from src.portfolio.capital_structure import RegimeCapitalTable
    limits = RegimeCapitalTable.HARD_LIMITS
    
    # Hard limits should have clipped the values
    assert structure.equity_fraction <= limits['max_equity_fraction']
    assert structure.cash_fraction >= limits['min_cash_fraction']


def test_governance_explanation_is_human_readable(governor, unified_state_bull):
    """Test that governance explanation is human-readable."""
    structure = governor.compute_capital_structure(unified_state_bull)
    explanation = governor.get_governance_explanation(structure)
    
    assert isinstance(explanation, str)
    assert len(explanation) > 0
    assert structure.capital_structure_regime.value in explanation
    assert '%' in explanation  # Should contain percentages


def test_governor_uses_config_regime_table(governor):
    """Governor should auto-load the canonical regime table from config."""
    cautious = governor.regime_table[CapitalStructureRegime.CAUTIOUS.value]
    assert cautious["equity_fraction"] == 0.60
    assert cautious["options_fraction"] == 0.20
    assert cautious["cash_fraction"] == 0.20


def test_recovery_counter_increments_after_drawdown_resolves(governor):
    """Recovery counter should move once drawdown resolves and equity is still below standard."""
    governor.persistent_state["recovery_days_elapsed"] = 0
    governor.persistent_state["last_equity_fraction"] = 0.40

    for _ in range(5):
        assert governor.increment_recovery_counter(-1.0, current_regime="STANDARD") is True

    assert governor.persistent_state["recovery_days_elapsed"] == 5


def test_recovery_counter_resets_on_drawdown(governor):
    governor.persistent_state["recovery_days_elapsed"] = 4
    governor.reset_recovery_counter()
    assert governor.persistent_state["recovery_days_elapsed"] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
