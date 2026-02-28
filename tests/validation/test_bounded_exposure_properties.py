"""
Property-Based Tests for Bounded Exposure Calculator

Tests that exposure calculations always produce bounded values.
"""

import pytest
import math
from hypothesis import given, strategies as st, settings

from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator, BoundedExposure


@settings(max_examples=100, deadline=None)
@given(
    risk_on=st.one_of(
        st.floats(min_value=-10.0, max_value=10.0),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf'))
    ),
    stress=st.one_of(
        st.floats(min_value=-10.0, max_value=10.0),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf'))
    ),
    regime=st.sampled_from(['early-expansion', 'late-expansion', 'early-contraction', 'late-contraction', 'unknown'])
)
def test_property_exposure_bounds(risk_on, stress, regime):
    """
    Property 1: Exposure Bounds
    
    For any risk_on, stress_score, and regime values, the calculated 
    allowed_exposure must be in the range [0.0, 1.0], with NaN mapped 
    to 0.0 and infinity mapped to 1.0.
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4
    Feature: system-integrity-repair, Property 1: Exposure Bounds
    """
    calc = BoundedExposureCalculator()
    
    result = calc.calculate_allowed_exposure(risk_on, stress, regime)
    
    # Property: result must always be in [0.0, 1.0]
    assert 0.0 <= result.value <= 1.0, f"Exposure {result.value} out of bounds!"
    assert isinstance(result, BoundedExposure)
    assert isinstance(result.value, float)
    assert not math.isnan(result.value), "Result should never be NaN"
    assert not math.isinf(result.value), "Result should never be infinity"


@settings(max_examples=100, deadline=None)
@given(
    portfolio_vol=st.one_of(
        st.floats(min_value=-10.0, max_value=10.0),
        st.just(float('nan')),
        st.just(float('inf')),
        st.just(float('-inf'))
    ),
    target_vol=st.floats(min_value=0.01, max_value=1.0)
)
def test_property_risk_scaled_exposure_bounds(portfolio_vol, target_vol):
    """
    Property 1: Risk-Scaled Exposure Bounds
    
    For any portfolio volatility and target volatility, the risk-scaled
    exposure must be in the range [0.0, 1.0].
    
    Validates: Requirements 2.1, 2.2, 2.3, 2.4
    Feature: system-integrity-repair, Property 1: Exposure Bounds
    """
    calc = BoundedExposureCalculator()
    
    result = calc.calculate_risk_scaled_exposure(portfolio_vol, target_vol)
    
    # Property: result must always be in [0.0, 1.0]
    assert 0.0 <= result.value <= 1.0
    assert not math.isnan(result.value)
    assert not math.isinf(result.value)


@settings(max_examples=100, deadline=None)
@given(
    allowed=st.floats(min_value=0.0, max_value=1.0),
    risk_scaled=st.floats(min_value=0.0, max_value=1.0)
)
def test_property_combined_exposure_minimum(allowed, risk_scaled):
    """
    Property 5: Exposure Minimum Selection
    
    For any allowed_exposure and risk_scaled_exposure values, the 
    Portfolio Governor's final_exposure must equal min(allowed_exposure, risk_scaled_exposure).
    
    Validates: Requirements 5.3
    Feature: system-integrity-repair, Property 5: Exposure Minimum Selection
    """
    calc = BoundedExposureCalculator()
    
    result = calc.combine_exposures(allowed, risk_scaled)
    
    # Property: result must equal minimum of inputs
    expected = min(allowed, risk_scaled)
    assert abs(result.value - expected) < 1e-10, f"Expected {expected}, got {result.value}"
    assert 0.0 <= result.value <= 1.0


# Unit tests for specific edge cases

def test_nan_handling():
    """Test that NaN is mapped to 0.0"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(float('nan'), "test")
    assert result.value == 0.0
    assert result.was_bounded
    assert "NaN" in result.bound_reason


def test_positive_infinity_handling():
    """Test that positive infinity is mapped to 1.0"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(float('inf'), "test")
    assert result.value == 1.0
    assert result.was_bounded
    assert "infinity" in result.bound_reason.lower()


def test_negative_infinity_handling():
    """Test that negative infinity is mapped to 0.0"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(float('-inf'), "test")
    assert result.value == 0.0
    assert result.was_bounded


def test_negative_value_handling():
    """Test that negative values are bounded to 0.0"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(-0.5, "test")
    assert result.value == 0.0
    assert result.was_bounded
    assert "Negative" in result.bound_reason


def test_excessive_value_handling():
    """Test that values > 1.0 are bounded to 1.0"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(3.387, "test")  # The actual bug value!
    assert result.value == 1.0
    assert result.was_bounded
    assert "Excessive" in result.bound_reason


def test_normal_value_not_bounded():
    """Test that normal values pass through unchanged"""
    calc = BoundedExposureCalculator()
    result = calc._apply_bounds(0.5, "test")
    assert result.value == 0.5
    assert not result.was_bounded
    assert result.bound_reason is None


def test_violation_count_tracking():
    """Test that violations are counted"""
    calc = BoundedExposureCalculator()
    assert calc.get_violation_count() == 0
    
    calc._apply_bounds(float('nan'), "test1")
    assert calc.get_violation_count() == 1
    
    calc._apply_bounds(2.0, "test2")
    assert calc.get_violation_count() == 2
    
    calc.reset_violation_count()
    assert calc.get_violation_count() == 0
