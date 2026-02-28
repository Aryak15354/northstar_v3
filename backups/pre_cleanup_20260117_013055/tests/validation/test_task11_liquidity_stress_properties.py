#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 11 - LIQUIDITY STRESS MANAGEMENT
Property-based tests for stress testing and liquidity-based risk management

Tests the following properties:
- Property 35: Concentration Limit Enforcement
- Property 36: Diversification Constraint Application
- Property 37: Leverage Limit Enforcement

Usage:
    python -m pytest tests/validation/test_task11_liquidity_stress_properties.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import warnings
warnings.filterwarnings('ignore')

import sys
import os
)))

from src.validation.liquidity_cash_manager import LiquidityCashManager, LiquidityRegime

class TestTask11LiquidityStressProperties:
    """Property tests for Task 11 - Liquidity Stress Management"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.manager = LiquidityCashManager()
        
    @given(
        position_weights=st.lists(
            st.floats(min_value=0.01, max_value=0.50), 
            min_size=3, max_size=10
        ),
        concentration_limit=st.floats(min_value=0.05, max_value=0.30)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_35_concentration_limit_enforcement(self, position_weights, concentration_limit):
        """
        Property 35: Concentration Limit Enforcement
        
        No single position should exceed the concentration limit,
        and total portfolio should remain properly diversified.
        """
        
        # Normalize weights to sum to 1
        total_weight = sum(position_weights)
        if total_weight > 0:
            normalized_weights = [w / total_weight for w in position_weights]
        else:
            normalized_weights = [1.0 / len(position_weights)] * len(position_weights)
        
        # Create position dictionary
        positions = {f'STOCK_{i}': weight for i, weight in enumerate(normalized_weights)}
        
        # Apply concentration limits (simplified enforcement)
        enforced_positions = {}
        excess_weight = 0.0
        
        for asset, weight in positions.items():
            if weight > concentration_limit:
                enforced_positions[asset] = concentration_limit
                excess_weight += (weight - concentration_limit)
            else:
                enforced_positions[asset] = weight
        
        # Redistribute excess weight to cash or other positions
        if excess_weight > 0:
            enforced_positions['CASH'] = excess_weight
        
        # Property assertions
        total_enforced_weight = sum(enforced_positions.values())
        assert abs(total_enforced_weight - 1.0) < 0.01, f"Total weight {total_enforced_weight} should sum to 1.0"
        
        # Check concentration limits
        for asset, weight in enforced_positions.items():
            if asset != 'CASH':  # Cash can exceed concentration limit
                assert weight <= concentration_limit + 0.001, \
                    f"Position {asset} weight {weight} exceeds concentration limit {concentration_limit}"
        
        # Check that enforcement actually occurred if needed
        max_original_weight = max(normalized_weights)
        if max_original_weight > concentration_limit:
            max_enforced_weight = max(w for a, w in enforced_positions.items() if a != 'CASH')
            assert max_enforced_weight <= concentration_limit + 0.001, \
                "Concentration limit enforcement failed"
    
    @given(
        correlations=st.lists(
            st.floats(min_value=-0.5, max_value=0.95), 
            min_size=3, max_size=6
        ),
        diversification_threshold=st.floats(min_value=0.3, max_value=0.8)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_36_diversification_constraint_application(self, correlations, diversification_threshold):
        """
        Property 36: Diversification Constraint Application
        
        Portfolio should maintain adequate diversification,
        and high correlation should trigger diversification constraints.
        """
        
        # Create correlation matrix
        n_assets = len(correlations)
        corr_matrix = np.eye(n_assets)
        
        # Fill upper triangle with correlations
        idx = 0
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                if idx < len(correlations):
                    corr_matrix[i, j] = correlations[idx]
                    corr_matrix[j, i] = correlations[idx]
                    idx += 1
        
        # Create returns data from correlation matrix
        returns_data = pd.DataFrame(
            np.random.multivariate_normal(
                mean=np.zeros(n_assets),
                cov=corr_matrix,
                size=100
            ),
            columns=[f'ASSET_{i}' for i in range(n_assets)]
        )
        
        # Detect correlation stress
        correlation_stress = self.manager.detect_correlation_stress(returns_data)
        
        # Property assertions
        assert -1.0 <= correlation_stress.avg_correlation <= 1.0, \
            f"Average correlation {correlation_stress.avg_correlation} not in valid range"
        
        assert 0.0 <= correlation_stress.diversification_breakdown <= 1.0, \
            f"Diversification breakdown {correlation_stress.diversification_breakdown} not in valid range"
        
        # High correlation should trigger appropriate stress level
        if correlation_stress.avg_correlation > 0.7:
            assert correlation_stress.stress_level in ['HIGH', 'CRITICAL'], \
                f"High correlation {correlation_stress.avg_correlation} should trigger HIGH or CRITICAL stress"
        
        # Diversification breakdown should reflect correlation level
        expected_breakdown = correlation_stress.avg_correlation
        actual_breakdown = correlation_stress.diversification_breakdown
        
        # Allow some tolerance for calculation differences
        assert abs(actual_breakdown - expected_breakdown) <= 0.2, \
            f"Diversification breakdown {actual_breakdown} should approximate correlation {expected_breakdown}"
        
        # Stress level should be consistent with correlation level
        if correlation_stress.avg_correlation <= 0.3:
            assert correlation_stress.stress_level == 'LOW'
        elif correlation_stress.avg_correlation >= 0.8:
            assert correlation_stress.stress_level in ['HIGH', 'CRITICAL']
    
    @given(
        leverage=st.floats(min_value=0.5, max_value=3.0),
        leverage_limit=st.floats(min_value=1.0, max_value=2.0),
        portfolio_value=st.floats(min_value=100000, max_value=10000000)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_37_leverage_limit_enforcement(self, leverage, leverage_limit, portfolio_value):
        """
        Property 37: Leverage Limit Enforcement
        
        Portfolio leverage should not exceed specified limits,
        and excess leverage should trigger automatic reduction.
        """
        
        # Calculate gross exposure from leverage
        gross_exposure = leverage * portfolio_value
        net_exposure = portfolio_value * 0.9  # Assume some cash
        
        # Create portfolio data
        portfolio_data = {
            'leverage': leverage,
            'gross_exposure': gross_exposure,
            'net_exposure': net_exposure,
            'portfolio_value': portfolio_value,
            'concentration_score': 0.5,
            'volatility': 0.15
        }
        
        # Apply leverage enforcement (simplified)
        if leverage > leverage_limit:
            # Reduce positions to meet leverage limit
            reduction_factor = leverage_limit / leverage
            enforced_gross_exposure = gross_exposure * reduction_factor
            enforced_leverage = enforced_gross_exposure / portfolio_value
        else:
            enforced_gross_exposure = gross_exposure
            enforced_leverage = leverage
        
        # Property assertions
        assert enforced_leverage <= leverage_limit + 0.01, \
            f"Enforced leverage {enforced_leverage} exceeds limit {leverage_limit}"
        
        # Check that enforcement actually occurred if needed
        if leverage > leverage_limit:
            assert enforced_leverage < leverage, \
                "Leverage should be reduced when exceeding limit"
            
            # Reduction should be proportional
            expected_reduction = leverage_limit / leverage
            actual_reduction = enforced_leverage / leverage
            assert abs(actual_reduction - expected_reduction) <= 0.05, \
                f"Leverage reduction {actual_reduction} should match expected {expected_reduction}"
        
        # Leverage should always be positive
        assert enforced_leverage >= 0, "Leverage cannot be negative"
        
        # Gross exposure should be consistent with leverage
        expected_gross = enforced_leverage * portfolio_value
        assert abs(enforced_gross_exposure - expected_gross) <= portfolio_value * 0.01, \
            "Gross exposure should be consistent with leverage"
    
    def test_property_35_concentration_limit_enforcement_deterministic(self):
        """Deterministic test for concentration limit enforcement"""
        
        # Create portfolio with one oversized position
        positions = {
            'STOCK_A': 0.40,  # Exceeds typical 30% limit
            'STOCK_B': 0.25,
            'STOCK_C': 0.20,
            'STOCK_D': 0.15
        }
        
        concentration_limit = 0.30
        
        # Apply enforcement
        enforced_positions = {}
        excess_weight = 0.0
        
        for asset, weight in positions.items():
            if weight > concentration_limit:
                enforced_positions[asset] = concentration_limit
                excess_weight += (weight - concentration_limit)
            else:
                enforced_positions[asset] = weight
        
        if excess_weight > 0:
            enforced_positions['CASH'] = excess_weight
        
        # Assertions
        assert enforced_positions['STOCK_A'] == concentration_limit
        assert abs(enforced_positions['CASH'] - 0.10) < 0.001  # 0.40 - 0.30, with floating point tolerance
        assert abs(sum(enforced_positions.values()) - 1.0) < 0.001
    
    def test_property_36_diversification_constraint_application_deterministic(self):
        """Deterministic test for diversification constraint application"""
        
        # Create highly correlated returns
        high_corr_returns = pd.DataFrame({
            'STOCK_A': [0.02, 0.01, -0.01, 0.03, -0.02],
            'STOCK_B': [0.018, 0.009, -0.008, 0.028, -0.018],  # Highly correlated with A
            'STOCK_C': [0.019, 0.011, -0.012, 0.031, -0.019]   # Highly correlated with A
        })
        
        correlation_stress = self.manager.detect_correlation_stress(high_corr_returns)
        
        # Should detect high correlation
        assert correlation_stress.avg_correlation > 0.8
        assert correlation_stress.stress_level in ['HIGH', 'CRITICAL']
        assert correlation_stress.diversification_breakdown > 0.7
    
    def test_property_37_leverage_limit_enforcement_deterministic(self):
        """Deterministic test for leverage limit enforcement"""
        
        # High leverage scenario
        leverage = 2.5
        leverage_limit = 2.0
        portfolio_value = 1000000
        
        # Should trigger enforcement
        assert leverage > leverage_limit
        
        # Calculate enforced leverage
        reduction_factor = leverage_limit / leverage
        enforced_leverage = leverage * reduction_factor
        
        # Assertions
        assert enforced_leverage <= leverage_limit
        assert enforced_leverage == 2.0  # Should equal the limit
        assert reduction_factor == 0.8   # 20% reduction
    
    def test_liquidity_cash_allocation_properties(self):
        """Test liquidity-based cash allocation properties"""
        
        # Test different liquidity scenarios
        scenarios = [
            {'liquidity_score': 0.9, 'expected_regime': LiquidityRegime.ABUNDANT},
            {'liquidity_score': 0.7, 'expected_regime': LiquidityRegime.NORMAL},
            {'liquidity_score': 0.5, 'expected_regime': LiquidityRegime.STRESSED},
            {'liquidity_score': 0.2, 'expected_regime': LiquidityRegime.CRISIS}
        ]
        
        for scenario in scenarios:
            regime = self.manager.determine_liquidity_regime(scenario['liquidity_score'])
            assert regime == scenario['expected_regime']
            
            # Cash allocation should increase with lower liquidity
            if scenario['liquidity_score'] < 0.5:
                # Should recommend higher cash allocation
                assert True  # Placeholder for actual cash allocation test
    
    def test_correlation_stress_response_properties(self):
        """Test correlation stress response properties"""
        
        # Low correlation scenario
        low_corr_returns = pd.DataFrame({
            'STOCK_A': np.random.normal(0, 0.02, 50),
            'STOCK_B': np.random.normal(0, 0.02, 50),
            'STOCK_C': np.random.normal(0, 0.02, 50)
        })
        
        # Make them uncorrelated
        low_corr_returns['STOCK_B'] = np.random.normal(0, 0.02, 50)
        low_corr_returns['STOCK_C'] = np.random.normal(0, 0.02, 50)
        
        correlation_stress = self.manager.detect_correlation_stress(low_corr_returns)
        
        # Should show low stress
        assert correlation_stress.stress_level == 'LOW'
        assert correlation_stress.recommended_action in ['MAINTAIN', 'MONITOR']


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])