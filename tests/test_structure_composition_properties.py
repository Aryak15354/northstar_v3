#!/usr/bin/env python3
"""
Property-Based Tests for Structure Composition

Tests universal properties that should hold for composed option structures.

Property 7: Composed Greeks are additive
- For any two option structures, the Greeks of the composed structure
  should equal the sum of individual Greeks

**Validates: Requirements 2.4**
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, date
import numpy as np

from src.volatility.strategy_generator import (
    StrategyGenerator, TargetGreeks, Constraints, MarketState, OptionStructure
)
from src.volatility.strategy_ast import (
    Call, Put, Straddle, Strangle, OptionType
)
from src.volatility.greeks_aggregator import Greeks


# Hypothesis strategies for generating test data

@st.composite
def simple_option_structure_strategy(draw, state: MarketState):
    """Generate a simple option structure (call, put, or straddle)"""
    generator = StrategyGenerator()
    
    strike = draw(st.floats(
        min_value=state.spot_price * 0.8,
        max_value=state.spot_price * 1.2
    ))
    strike = round(strike / 5) * 5  # Round to nearest 5
    
    expiry = (state.timestamp + timedelta(days=draw(st.integers(min_value=14, max_value=60)))).date()
    quantity = draw(st.integers(min_value=1, max_value=5))
    
    structure_type = draw(st.sampled_from(['call', 'put', 'straddle']))
    
    if structure_type == 'call':
        ast = Call(strike=strike, expiry=expiry, quantity=quantity, underlying="SPY")
    elif structure_type == 'put':
        ast = Put(strike=strike, expiry=expiry, quantity=quantity, underlying="SPY")
    else:  # straddle
        ast = Straddle(strike=strike, expiry=expiry, quantity=quantity, underlying="SPY")
    
    structure = OptionStructure(
        ast=ast,
        greeks=Greeks.zero(),
        price=0.0,
        underlying="SPY",
        expiry=expiry,
        legs=ast.get_legs()
    )
    
    # Price and compute Greeks
    structure.price = generator._price_structure(structure, state)
    structure.greeks = generator._compute_structure_greeks(structure, state)
    
    return structure


@st.composite
def market_state_strategy(draw):
    """Generate random but realistic market state"""
    spot_price = draw(st.floats(min_value=400.0, max_value=500.0))
    implied_vol = draw(st.floats(min_value=0.15, max_value=0.30))
    risk_free_rate = draw(st.floats(min_value=0.03, max_value=0.07))
    
    return MarketState(
        spot_price=spot_price,
        implied_vol=implied_vol,
        risk_free_rate=risk_free_rate,
        timestamp=datetime.now()
    )


class TestStructureCompositionProperties:
    """Property-based tests for structure composition"""
    
    @given(state=market_state_strategy())
    @settings(max_examples=30, deadline=5000)
    def test_property_7_composed_greeks_are_additive(self, state: MarketState):
        """
        Property 7: Composed Greeks are additive
        
        For any two option structures, the Greeks of the composed structure
        should equal the sum of individual Greeks.
        
        **Validates: Requirements 2.4**
        """
        # Generate two simple structures using the draw function properly
        generator = StrategyGenerator()
        
        # Create structure 1
        strike1 = round(state.spot_price / 5) * 5
        expiry1 = (state.timestamp + timedelta(days=30)).date()
        ast1 = Call(strike=strike1, expiry=expiry1, quantity=1, underlying="SPY")
        structure1 = OptionStructure(
            ast=ast1, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry1, legs=ast1.get_legs()
        )
        structure1.price = generator._price_structure(structure1, state)
        structure1.greeks = generator._compute_structure_greeks(structure1, state)
        
        # Create structure 2
        strike2 = round(state.spot_price * 1.05 / 5) * 5
        expiry2 = (state.timestamp + timedelta(days=30)).date()
        ast2 = Put(strike=strike2, expiry=expiry2, quantity=1, underlying="SPY")
        structure2 = OptionStructure(
            ast=ast2, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry2, legs=ast2.get_legs()
        )
        structure2.price = generator._price_structure(structure2, state)
        structure2.greeks = generator._compute_structure_greeks(structure2, state)
        
        # Compose them
        composed = generator.compose_structures([structure1, structure2], state)
        
        # Check that composed Greeks equal sum of individual Greeks
        expected_delta = structure1.greeks.delta + structure2.greeks.delta
        expected_gamma = structure1.greeks.gamma + structure2.greeks.gamma
        expected_vega = structure1.greeks.vega + structure2.greeks.vega
        expected_theta = structure1.greeks.theta + structure2.greeks.theta
        expected_rho = structure1.greeks.rho + structure2.greeks.rho
        
        # Allow small numerical tolerance
        tolerance = 1e-6
        
        assert abs(composed.greeks.delta - expected_delta) < tolerance, (
            f"Delta not additive: {composed.greeks.delta} != {expected_delta}"
        )
        assert abs(composed.greeks.gamma - expected_gamma) < tolerance, (
            f"Gamma not additive: {composed.greeks.gamma} != {expected_gamma}"
        )
        assert abs(composed.greeks.vega - expected_vega) < tolerance, (
            f"Vega not additive: {composed.greeks.vega} != {expected_vega}"
        )
        assert abs(composed.greeks.theta - expected_theta) < tolerance, (
            f"Theta not additive: {composed.greeks.theta} != {expected_theta}"
        )
        assert abs(composed.greeks.rho - expected_rho) < tolerance, (
            f"Rho not additive: {composed.greeks.rho} != {expected_rho}"
        )
    
    @given(state=market_state_strategy())
    @settings(max_examples=20, deadline=5000)
    def test_composed_price_is_additive(self, state: MarketState):
        """
        Test that composed structure price equals sum of individual prices.
        """
        # Generate two simple structures
        generator = StrategyGenerator()
        
        # Create structure 1
        strike1 = round(state.spot_price / 5) * 5
        expiry1 = (state.timestamp + timedelta(days=30)).date()
        ast1 = Call(strike=strike1, expiry=expiry1, quantity=1, underlying="SPY")
        structure1 = OptionStructure(
            ast=ast1, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry1, legs=ast1.get_legs()
        )
        structure1.price = generator._price_structure(structure1, state)
        structure1.greeks = generator._compute_structure_greeks(structure1, state)
        
        # Create structure 2
        strike2 = round(state.spot_price * 1.05 / 5) * 5
        expiry2 = (state.timestamp + timedelta(days=30)).date()
        ast2 = Put(strike=strike2, expiry=expiry2, quantity=1, underlying="SPY")
        structure2 = OptionStructure(
            ast=ast2, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry2, legs=ast2.get_legs()
        )
        structure2.price = generator._price_structure(structure2, state)
        structure2.greeks = generator._compute_structure_greeks(structure2, state)
        
        # Compose them
        composed = generator.compose_structures([structure1, structure2], state)
        
        # Check that composed price equals sum of individual prices
        expected_price = structure1.price + structure2.price
        
        # Allow small numerical tolerance
        tolerance = 1e-6
        
        assert abs(composed.price - expected_price) < tolerance, (
            f"Price not additive: {composed.price} != {expected_price}"
        )
    
    @given(state=market_state_strategy())
    @settings(max_examples=20, deadline=5000)
    def test_composed_legs_include_all_individual_legs(self, state: MarketState):
        """
        Test that composed structure includes all legs from individual structures.
        """
        # Generate two simple structures
        generator = StrategyGenerator()
        
        # Create structure 1 (straddle - 2 legs)
        strike1 = round(state.spot_price / 5) * 5
        expiry1 = (state.timestamp + timedelta(days=30)).date()
        ast1 = Straddle(strike=strike1, expiry=expiry1, quantity=1, underlying="SPY")
        structure1 = OptionStructure(
            ast=ast1, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry1, legs=ast1.get_legs()
        )
        structure1.price = generator._price_structure(structure1, state)
        structure1.greeks = generator._compute_structure_greeks(structure1, state)
        
        # Create structure 2 (call - 1 leg)
        strike2 = round(state.spot_price * 1.05 / 5) * 5
        expiry2 = (state.timestamp + timedelta(days=30)).date()
        ast2 = Call(strike=strike2, expiry=expiry2, quantity=1, underlying="SPY")
        structure2 = OptionStructure(
            ast=ast2, greeks=Greeks.zero(), price=0.0,
            underlying="SPY", expiry=expiry2, legs=ast2.get_legs()
        )
        structure2.price = generator._price_structure(structure2, state)
        structure2.greeks = generator._compute_structure_greeks(structure2, state)
        
        # Compose them
        composed = generator.compose_structures([structure1, structure2], state)
        
        # Check that composed structure has all legs
        expected_num_legs = len(structure1.legs) + len(structure2.legs)
        assert len(composed.legs) == expected_num_legs, (
            f"Composed structure has {len(composed.legs)} legs, expected {expected_num_legs}"
        )
    
    def test_compose_empty_list_raises_error(self):
        """
        Test that composing an empty list raises an error.
        """
        generator = StrategyGenerator()
        state = MarketState(spot_price=450.0, implied_vol=0.20, risk_free_rate=0.05)
        
        with pytest.raises(ValueError, match="Cannot compose empty structure list"):
            generator.compose_structures([], state)
    
    def test_compose_single_structure(self):
        """
        Test that composing a single structure returns equivalent structure.
        """
        state = MarketState(spot_price=450.0, implied_vol=0.20, risk_free_rate=0.05)
        
        # Create a simple call
        ast = Call(strike=450.0, expiry=(datetime.now() + timedelta(days=30)).date(), quantity=1, underlying="SPY")
        structure = OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying="SPY",
            expiry=ast.expiry,
            legs=ast.get_legs()
        )
        
        # Price and compute Greeks
        generator = StrategyGenerator()
        structure.price = generator._price_structure(structure, state)
        structure.greeks = generator._compute_structure_greeks(structure, state)
        
        # Compose single structure
        composed = generator.compose_structures([structure], state)
        
        # Should have same Greeks and price
        tolerance = 1e-6
        assert abs(composed.greeks.delta - structure.greeks.delta) < tolerance
        assert abs(composed.greeks.vega - structure.greeks.vega) < tolerance
        assert abs(composed.price - structure.price) < tolerance
    
    def test_compose_three_structures(self):
        """
        Test that composing three structures works correctly.
        """
        state = MarketState(spot_price=450.0, implied_vol=0.20, risk_free_rate=0.05)
        expiry = (datetime.now() + timedelta(days=30)).date()
        
        # Create three simple structures
        structures = []
        for i, strike in enumerate([440.0, 450.0, 460.0]):
            ast = Call(strike=strike, expiry=expiry, quantity=1, underlying="SPY")
            structure = OptionStructure(
                ast=ast,
                greeks=Greeks.zero(),
                price=0.0,
                underlying="SPY",
                expiry=expiry,
                legs=ast.get_legs()
            )
            structures.append(structure)
        
        # Price and compute Greeks
        generator = StrategyGenerator()
        for structure in structures:
            structure.price = generator._price_structure(structure, state)
            structure.greeks = generator._compute_structure_greeks(structure, state)
        
        # Compose all three
        composed = generator.compose_structures(structures, state)
        
        # Check additivity
        expected_delta = sum(s.greeks.delta for s in structures)
        expected_vega = sum(s.greeks.vega for s in structures)
        expected_price = sum(s.price for s in structures)
        
        tolerance = 1e-6
        assert abs(composed.greeks.delta - expected_delta) < tolerance
        assert abs(composed.greeks.vega - expected_vega) < tolerance
        assert abs(composed.price - expected_price) < tolerance
        assert len(composed.legs) == 3  # Three calls


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
