"""
Tests for CapitalStructure and RegimeCapitalTable.
"""

import pytest
from datetime import datetime
from pathlib import Path

import yaml
from src.portfolio.capital_structure import (
    CapitalStructure,
    CapitalStructureRegime,
    RegimeCapitalTable
)


def test_fractions_sum_to_one():
    """Test that all regime table entries sum to exactly 1.0."""
    for regime, structure in RegimeCapitalTable.REGIME_TABLE.items():
        total = (structure['equity_fraction'] + 
                structure['options_fraction'] + 
                structure['cash_fraction'])
        assert abs(total - 1.0) < 1e-6, f"Regime {regime.value} fractions sum to {total}, not 1.0"


def test_validation_raises_on_bad_fractions():
    """Test that validation raises ValueError when fractions don't sum to 1.0."""
    structure = CapitalStructure(
        equity_fraction=0.75,
        options_fraction=0.15,
        cash_fraction=0.15,  # Total = 1.05
        total_capital_inr=10_000_000,
        equity_budget_inr=7_500_000,
        options_budget_inr=1_500_000,
        cash_reserve_inr=1_500_000,
        capital_structure_regime=CapitalStructureRegime.STANDARD,
        confidence=0.8,
        market_regime='BULL',
        volatility_regime='NORMAL_VOL',
        macro_regime='EXPANSION',
        sentiment_regime='OPTIMISM',
        economic_activity_regime='EXPANSION',
        crisis_probability=0.05,
        current_drawdown_pct=0.0,
        current_nav_inr=10_000_000,
        primary_rationale='Test',
        valid_for_date=datetime.now(),
        expires_at=datetime.now(),
        computed_at=datetime.now()
    )
    
    # Manually set bad fractions
    structure.cash_fraction = 0.20  # Now total = 1.10
    
    with pytest.raises(ValueError, match="sum to"):
        structure.validate()


def test_validation_raises_on_negative_fraction():
    """Test that validation raises ValueError when any fraction is negative."""
    structure = CapitalStructure(
        equity_fraction=0.85,
        options_fraction=0.20,
        cash_fraction=-0.05,  # Negative! But sum is 1.0
        total_capital_inr=10_000_000,
        equity_budget_inr=8_500_000,
        options_budget_inr=2_000_000,
        cash_reserve_inr=-500_000,
        capital_structure_regime=CapitalStructureRegime.STANDARD,
        confidence=0.8,
        market_regime='BULL',
        volatility_regime='NORMAL_VOL',
        macro_regime='EXPANSION',
        sentiment_regime='OPTIMISM',
        economic_activity_regime='EXPANSION',
        crisis_probability=0.05,
        current_drawdown_pct=0.0,
        current_nav_inr=10_000_000,
        primary_rationale='Test',
        valid_for_date=datetime.now(),
        expires_at=datetime.now(),
        computed_at=datetime.now()
    )
    
    with pytest.raises(ValueError, match="negative"):
        structure.validate()


def test_inr_amounts_consistent():
    """Test that INR amounts are consistent with fractions."""
    total_capital = 10_000_000
    equity_frac = 0.75
    options_frac = 0.15
    cash_frac = 0.10
    
    structure = CapitalStructure(
        equity_fraction=equity_frac,
        options_fraction=options_frac,
        cash_fraction=cash_frac,
        total_capital_inr=total_capital,
        equity_budget_inr=equity_frac * total_capital,
        options_budget_inr=options_frac * total_capital,
        cash_reserve_inr=cash_frac * total_capital,
        capital_structure_regime=CapitalStructureRegime.STANDARD,
        confidence=0.8,
        market_regime='BULL',
        volatility_regime='NORMAL_VOL',
        macro_regime='EXPANSION',
        sentiment_regime='OPTIMISM',
        economic_activity_regime='EXPANSION',
        crisis_probability=0.05,
        current_drawdown_pct=0.0,
        current_nav_inr=total_capital,
        primary_rationale='Test',
        valid_for_date=datetime.now(),
        expires_at=datetime.now(),
        computed_at=datetime.now()
    )
    
    structure.validate()
    
    assert structure.equity_budget_inr == 7_500_000
    assert structure.options_budget_inr == 1_500_000
    assert structure.cash_reserve_inr == 1_000_000


def test_regime_table_validate():
    """Test that RegimeCapitalTable.validate_table() passes."""
    # Should not raise
    RegimeCapitalTable.validate_table()


def test_get_regime_structure():
    """Test getting regime structure from table."""
    structure = RegimeCapitalTable.get_regime_structure(CapitalStructureRegime.FULL_DEPLOYMENT)
    assert structure['equity_fraction'] == 0.90
    assert structure['options_fraction'] == 0.08
    assert structure['cash_fraction'] == 0.02


def test_regime_table_matches_config_file():
    """Configured regime table and code-side legacy mirror must stay aligned."""
    config_path = Path(__file__).resolve().parents[3] / "config" / "portfolio_governor_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    regime_table = config["regime_table"]

    for regime in (
        CapitalStructureRegime.CAUTIOUS,
        CapitalStructureRegime.DEFENSIVE,
        CapitalStructureRegime.CAPITAL_PRESERVATION,
    ):
        code_side = RegimeCapitalTable.get_regime_structure(regime)
        file_side = regime_table[regime.value]
        assert code_side["equity_fraction"] == file_side["equity_fraction"]
        assert code_side["options_fraction"] == file_side["options_fraction"]
        assert code_side["cash_fraction"] == file_side["cash_fraction"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
