#!/usr/bin/env python3
"""
Demo script for Gap 6: Portfolio Governor

This script demonstrates how the Portfolio Governor makes capital structure decisions
based on multi-dimensional regime state.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.portfolio.governor import PortfolioGovernor
from src.portfolio.capital_structure import CapitalStructureRegime
from src.core.state import UnifiedState
from src.sentiment.sentiment_state import SentimentRegime
from src.alternative_data.alternative_state import EconomicActivityRegime
from src.pnl.pnl_state import PnLState
from unittest.mock import Mock


def create_mock_crisis_engine(crisis_prob: float = 0.05):
    """Create a mock crisis engine."""
    engine = Mock()
    engine.state = Mock()
    engine.state.crisis_probability = crisis_prob
    return engine


def demo_scenario(name: str, unified_state, crisis_prob: float):
    """Run a demo scenario."""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{'='*70}")
    
    # Create governor
    crisis_engine = create_mock_crisis_engine(crisis_prob)
    governor = PortfolioGovernor(
        crisis_engine=crisis_engine,
        config={'starting_capital_inr': 10_000_000},
        data_dir="data"
    )
    
    # Compute capital structure
    structure = governor.compute_capital_structure(unified_state)
    
    # Print results
    print(f"\nInput Regime Signals:")
    print(f"  Market Regime: {unified_state.market.regime}")
    print(f"  Volatility Regime: {unified_state.market.volatility_regime}")
    print(f"  Macro Regime: {unified_state.macro.regime}")
    print(f"  Sentiment Regime: {unified_state.sentiment.market_sentiment_regime}")
    print(f"  Economic Activity: {unified_state.alternative_data.economic_activity_regime}")
    print(f"  Crisis Probability: {crisis_prob:.1%}")
    print(f"  Current Drawdown: {unified_state.pnl_state.current_drawdown_pct:.1f}%")
    
    print(f"\nGovernor Decision:")
    print(f"  Capital Structure Regime: {structure.capital_structure_regime.value}")
    print(f"  Confidence: {structure.confidence:.0%}")
    
    print(f"\nCapital Allocation:")
    print(f"  Equity:  {structure.equity_fraction:>6.1%}  (₹{structure.equity_budget_inr:>12,.0f})")
    print(f"  Options: {structure.options_fraction:>6.1%}  (₹{structure.options_budget_inr:>12,.0f})")
    print(f"  Cash:    {structure.cash_fraction:>6.1%}  (₹{structure.cash_reserve_inr:>12,.0f})")
    print(f"  Total:   100.0%  (₹{structure.total_capital_inr:>12,.0f})")
    
    if structure.modifiers_applied:
        print(f"\nModifiers Applied:")
        for modifier in structure.modifiers_applied:
            print(f"  • {modifier}")
    
    print(f"\nRationale:")
    print(f"  {structure.primary_rationale}")
    
    print(f"\nGovernance Explanation:")
    explanation = governor.get_governance_explanation(structure)
    print(f"  {explanation}")


def main():
    """Run all demo scenarios."""
    print("="*70)
    print("GAP 6: PORTFOLIO GOVERNOR DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how the Portfolio Governor makes capital structure")
    print("decisions based on multi-dimensional regime state.")
    
    # Scenario 1: Bull Market - Full Deployment
    state1 = UnifiedState()
    state1.market.regime = 'BULL'
    state1.market.volatility_regime = 'NORMAL_VOL'
    state1.macro.regime = 'EXPANSION'
    state1.sentiment.market_sentiment_regime = SentimentRegime.OPTIMISM
    state1.alternative_data.economic_activity_regime = EconomicActivityRegime.EXPANSION
    state1.pnl_state = PnLState()
    state1.pnl_state.current_nav_inr = 10_000_000
    state1.pnl_state.current_drawdown_pct = 0.0
    
    demo_scenario("Bull Market - All Systems Go", state1, crisis_prob=0.05)
    
    # Scenario 2: Mixed Signals - Cautious
    state2 = UnifiedState()
    state2.market.regime = 'SIDEWAYS'
    state2.market.volatility_regime = 'ELEVATED_VOL'
    state2.macro.regime = 'NEUTRAL'
    state2.sentiment.market_sentiment_regime = SentimentRegime.NEUTRAL
    state2.alternative_data.economic_activity_regime = EconomicActivityRegime.SLOWING
    state2.pnl_state = PnLState()
    state2.pnl_state.current_nav_inr = 10_000_000
    state2.pnl_state.current_drawdown_pct = -5.0
    
    demo_scenario("Mixed Signals - Cautious Stance", state2, crisis_prob=0.18)
    
    # Scenario 3: Bear Market with Drawdown - Defensive
    state3 = UnifiedState()
    state3.market.regime = 'BEAR'
    state3.market.volatility_regime = 'HIGH_VOL'
    state3.macro.regime = 'SLOWING'
    state3.sentiment.market_sentiment_regime = SentimentRegime.FEAR
    state3.alternative_data.economic_activity_regime = EconomicActivityRegime.SLOWING
    state3.pnl_state = PnLState()
    state3.pnl_state.current_nav_inr = 9_000_000
    state3.pnl_state.current_drawdown_pct = -12.0
    
    demo_scenario("Bear Market with Drawdown", state3, crisis_prob=0.28)
    
    # Scenario 4: Crisis - Capital Preservation
    state4 = UnifiedState()
    state4.market.regime = 'CRISIS'
    state4.market.volatility_regime = 'EXTREME_VOL'
    state4.macro.regime = 'CONTRACTION'
    state4.sentiment.market_sentiment_regime = SentimentRegime.PANIC
    state4.alternative_data.economic_activity_regime = EconomicActivityRegime.CONTRACTION
    state4.pnl_state = PnLState()
    state4.pnl_state.current_nav_inr = 8_500_000
    state4.pnl_state.current_drawdown_pct = -18.0
    
    demo_scenario("Crisis Mode - Capital Preservation", state4, crisis_prob=0.55)
    
    # Scenario 5: Recovery Phase
    state5 = UnifiedState()
    state5.market.regime = 'SIDEWAYS'
    state5.market.volatility_regime = 'NORMAL_VOL'
    state5.macro.regime = 'RECOVERY'
    state5.sentiment.market_sentiment_regime = SentimentRegime.NEUTRAL
    state5.alternative_data.economic_activity_regime = EconomicActivityRegime.RECOVERING
    state5.pnl_state = PnLState()
    state5.pnl_state.current_nav_inr = 9_800_000
    state5.pnl_state.current_drawdown_pct = -2.0  # Recovering from drawdown
    
    demo_scenario("Recovery Phase - Gradual Re-risking", state5, crisis_prob=0.08)
    
    print(f"\n{'='*70}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'='*70}")
    print("\nKey Takeaways:")
    print("1. The Governor synthesizes multiple regime signals into a single decision")
    print("2. Capital structure automatically adjusts to regime conditions")
    print("3. Modifiers provide additional risk management (drawdown, recovery, crisis)")
    print("4. Hard limits ensure minimum cash and maximum exposure constraints")
    print("5. Every decision is auditable with clear rationale")


if __name__ == '__main__':
    main()
