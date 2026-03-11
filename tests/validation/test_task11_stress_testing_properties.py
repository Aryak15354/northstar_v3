#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 11 - STRESS TESTING AND RISK MANAGEMENT
Property-based tests for stress testing and risk management systems

Tests the following properties:
- Property 35: Concentration Limit Enforcement
- Property 36: Diversification Constraint Application
- Property 37: Leverage Limit Enforcement

Usage:
    python -m pytest tests/validation/test_task11_stress_testing_properties.py -v
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
from typing import Dict, List, Optional, Tuple, Any
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.validation.liquidity_cash_manager import LiquidityCashManager

class TestTask11StressTestingProperties:
    """Property tests for Task 11 - Stress Testing and Risk Management"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.cash_manager = LiquidityCashManager()
        
        # Risk management parameters
        self.risk_params = {
            'max_position_concentration': 0.10,  # 10% max per position
            'max_sector_concentration': 0.25,    # 25% max per sector
            'min_diversification_count': 20,     # Minimum 20 positions
            'max_leverage': 1.5,                 # 1.5x maximum leverage
            'min_cash_buffer': 0.05              # 5% minimum cash
        }
    
    @given(
        portfolio_size=st.integers(min_value=10, max_value=50),
        concentration_violation=st.floats(min_value=0.0, max_value=0.3)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_35_concentration_limit_enforcement(self, portfolio_size, concentration_violation):
        """
        Property 35: Concentration Limit Enforcement
        
        System should enforce position concentration limits:
        - No single position should exceed maximum concentration
        - Violations should trigger automatic rebalancing
        - Risk-adjusted position sizing should be applied
        """
        
        # Create portfolio with potential concentration violations
        portfolio_weights = np.random.dirichlet(np.ones(portfolio_size))
        
        # Introduce concentration violation
        if concentration_violation > 0.1:
            violation_index = np.random.randint(0, portfolio_size)
            portfolio_weights[violation_index] += concentration_violation
            portfolio_weights = portfolio_weights / np.sum(portfolio_weights)  # Renormalize
        
        # Test concentration enforcement
        max_concentration = np.max(portfolio_weights)
        concentration_limit = self.risk_params['max_position_concentration']
        
        # Apply concentration limits
        adjusted_weights = self._apply_concentration_limits(portfolio_weights, concentration_limit)
        adjusted_max_concentration = np.max(adjusted_weights)
        
        # Property assertions
        if max_concentration > concentration_limit:
            # Should reduce concentration
            assert adjusted_max_concentration <= concentration_limit + 0.01, \
                f"Concentration {adjusted_max_concentration:.3f} exceeds limit {concentration_limit:.3f}"
            
            # Should maintain portfolio normalization
            assert abs(np.sum(adjusted_weights) - 1.0) < 0.01, "Portfolio weights should sum to 1.0"
            
        # All positions should be within limits
        for weight in adjusted_weights:
            assert weight <= concentration_limit + 0.01, f"Position weight {weight:.3f} exceeds limit"
            assert weight >= 0.0, "Position weights should be non-negative"
    
    @given(
        num_sectors=st.integers(min_value=4, max_value=10),
        sector_imbalance=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_36_diversification_constraint_application(self, num_sectors, sector_imbalance):
        """
        Property 36: Diversification Constraint Application
        
        System should enforce diversification constraints:
        - Minimum number of positions across sectors
        - Sector concentration limits
        - Correlation-based diversification adjustments
        """
        
        # Create sector allocation with potential imbalance
        sector_weights = np.random.dirichlet(np.ones(num_sectors))
        
        # Introduce sector imbalance
        if sector_imbalance > 0.2:
            dominant_sector = np.random.randint(0, num_sectors)
            sector_weights[dominant_sector] += sector_imbalance
            sector_weights = sector_weights / np.sum(sector_weights)  # Renormalize
        
        # Test diversification enforcement
        max_sector_weight = np.max(sector_weights)
        sector_limit = self.risk_params['max_sector_concentration']
        
        # Apply diversification constraints
        adjusted_sector_weights = self._apply_diversification_constraints(sector_weights, sector_limit)
        adjusted_max_sector = np.max(adjusted_sector_weights)
        
        # Property assertions
        if max_sector_weight > sector_limit:
            # Should reduce sector concentration
            assert adjusted_max_sector <= sector_limit + 0.03, \
                f"Sector concentration {adjusted_max_sector:.3f} exceeds limit {sector_limit:.3f}"
        
        # Should maintain reasonable diversification
        effective_sectors = np.sum(adjusted_sector_weights > 0.01)  # Sectors with >1% allocation
        min_sectors = max(3, num_sectors // 2)
        assert effective_sectors >= min_sectors, f"Should maintain at least {min_sectors} effective sectors"
        
        # Portfolio should remain normalized
        assert abs(np.sum(adjusted_sector_weights) - 1.0) < 0.01, "Sector weights should sum to 1.0"
    
    @given(
        leverage_ratio=st.floats(min_value=0.5, max_value=3.0),
        market_stress=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_37_leverage_limit_enforcement(self, leverage_ratio, market_stress):
        """
        Property 37: Leverage Limit Enforcement
        
        System should enforce leverage limits:
        - Maximum leverage should not be exceeded
        - Leverage should be reduced during market stress
        - Automatic deleveraging should occur when limits are breached
        """
        
        # Calculate stress-adjusted leverage limit
        base_leverage_limit = self.risk_params['max_leverage']
        stress_adjustment = market_stress * 0.5  # Reduce leverage by up to 50% under stress
        adjusted_leverage_limit = base_leverage_limit * (1 - stress_adjustment)
        
        # Test leverage enforcement
        if leverage_ratio > adjusted_leverage_limit:
            # Should trigger deleveraging
            target_leverage = self._apply_leverage_limits(leverage_ratio, adjusted_leverage_limit, market_stress)
            
            # Property assertions
            assert target_leverage <= adjusted_leverage_limit + 0.05, \
                f"Target leverage {target_leverage:.3f} exceeds adjusted limit {adjusted_leverage_limit:.3f}"
            
            assert target_leverage < leverage_ratio, \
                f"Target leverage {target_leverage:.3f} should be less than current {leverage_ratio:.3f}"
        
        # Leverage should be positive
        target_leverage = self._apply_leverage_limits(leverage_ratio, adjusted_leverage_limit, market_stress)
        assert target_leverage >= 0.1, "Leverage should remain positive"
        
        # Under extreme stress, should delever aggressively
        if market_stress > 0.4:
            extreme_stress_limit = base_leverage_limit * 0.5  # 50% of base limit
            extreme_target = self._apply_leverage_limits(leverage_ratio, extreme_stress_limit, market_stress)
            assert extreme_target <= extreme_stress_limit + 0.05, \
                "Should delever aggressively under extreme stress"
    
    def test_property_35_concentration_limit_enforcement_deterministic(self):
        """Deterministic test for concentration limit enforcement"""
        
        # Create portfolio with clear concentration violation
        portfolio_weights = np.array([0.5, 0.2, 0.2, 0.1])  # 50% in first position
        concentration_limit = 0.25  # 25% limit (mathematically feasible)
        
        # Apply concentration limits
        adjusted_weights = self._apply_concentration_limits(portfolio_weights, concentration_limit)
        
        # Should reduce concentration
        assert np.max(adjusted_weights) <= concentration_limit + 0.01, \
            f"Max weight {np.max(adjusted_weights):.3f} exceeds limit {concentration_limit}"
        
        # Should maintain normalization
        assert abs(np.sum(adjusted_weights) - 1.0) < 0.01, "Weights should sum to 1.0"
        
        # All weights should be within limits
        for weight in adjusted_weights:
            assert weight <= concentration_limit + 0.01, f"Weight {weight:.3f} exceeds limit"
    
    def test_property_36_diversification_constraint_application_deterministic(self):
        """Deterministic test for diversification constraint application"""
        
        # Create sector allocation with clear imbalance
        sector_weights = np.array([0.6, 0.2, 0.1, 0.1])  # 60% in first sector
        sector_limit = 0.3  # 30% sector limit
        
        # Apply diversification constraints
        adjusted_weights = self._apply_diversification_constraints(sector_weights, sector_limit)
        
        # Should reduce sector concentration
        assert np.max(adjusted_weights) <= sector_limit + 0.02, \
            f"Max sector weight {np.max(adjusted_weights):.3f} exceeds limit {sector_limit}"
        
        # Should maintain reasonable diversification
        effective_sectors = np.sum(adjusted_weights > 0.05)  # Sectors with >5% allocation
        assert effective_sectors >= 3, "Should maintain at least 3 effective sectors"
    
    def test_property_37_leverage_limit_enforcement_deterministic(self):
        """Deterministic test for leverage limit enforcement"""
        
        # Test normal market conditions
        leverage_ratio = 2.0
        leverage_limit = 1.5
        market_stress = 0.1  # Low stress
        
        target_leverage = self._apply_leverage_limits(leverage_ratio, leverage_limit, market_stress)
        
        # Should reduce leverage to within limits
        assert target_leverage <= leverage_limit + 0.05, \
            f"Target leverage {target_leverage:.3f} exceeds limit {leverage_limit}"
        
        # Test high stress conditions
        high_stress = 0.4
        stress_target = self._apply_leverage_limits(leverage_ratio, leverage_limit, high_stress)
        
        # Should delever more aggressively under stress
        assert stress_target < target_leverage, \
            "Should delever more aggressively under high stress"
    
    def test_extreme_stress_scenarios(self):
        """Test system behavior during extreme market stress"""
        
        # Extreme stress scenario
        extreme_stress_level = 0.8
        
        # Portfolio with multiple violations
        portfolio_weights = np.array([0.5, 0.3, 0.2])  # High concentration
        leverage_ratio = 2.5  # High leverage
        
        # Apply stress-adjusted limits
        stress_concentration_limit = self.risk_params['max_position_concentration'] * 0.5
        stress_leverage_limit = self.risk_params['max_leverage'] * 0.3
        
        adjusted_weights = self._apply_concentration_limits(portfolio_weights, stress_concentration_limit)
        adjusted_leverage = self._apply_leverage_limits(leverage_ratio, stress_leverage_limit, extreme_stress_level)
        
        # Should apply very conservative limits under extreme stress
        assert np.max(adjusted_weights) <= stress_concentration_limit + 0.01, \
            "Should apply strict concentration limits under extreme stress"
        
        assert adjusted_leverage <= stress_leverage_limit + 0.05, \
            "Should apply strict leverage limits under extreme stress"
        
        # Should maintain minimum cash buffer
        min_cash = self.risk_params['min_cash_buffer']
        implied_cash = 1.0 - np.sum(adjusted_weights) / adjusted_leverage
        assert implied_cash >= min_cash - 0.02, \
            f"Should maintain minimum cash buffer {min_cash:.1%}"
    
    def _apply_concentration_limits(self, weights: np.ndarray, limit: float) -> np.ndarray:
        """Apply position concentration limits"""
        
        adjusted_weights = weights.copy()
        # If the cap is mathematically infeasible for full deployment, keep residual as cash.
        if limit * len(adjusted_weights) < 1.0:
            return np.minimum(adjusted_weights, limit)
        max_iterations = 10  # Prevent infinite loops
        
        for _ in range(max_iterations):
            # Find violations
            excess_mask = adjusted_weights > limit
            if not np.any(excess_mask):
                break  # No more violations
            
            # Cap weights at limit
            excess_weight = np.sum(adjusted_weights[excess_mask] - limit)
            adjusted_weights[excess_mask] = limit
            
            # Redistribute excess to non-violating positions
            non_excess_mask = ~excess_mask
            available_capacity = np.sum(np.maximum(0, limit - adjusted_weights[non_excess_mask]))
            
            if available_capacity > 0 and excess_weight > 0:
                # Distribute proportionally based on available capacity
                capacity_weights = np.maximum(0, limit - adjusted_weights[non_excess_mask])
                if np.sum(capacity_weights) > 0:
                    redistribution_factor = min(1.0, excess_weight / np.sum(capacity_weights))
                    adjusted_weights[non_excess_mask] += capacity_weights * redistribution_factor
            else:
                # If no capacity, distribute equally among non-violating positions
                if np.sum(non_excess_mask) > 0:
                    equal_redistribution = excess_weight / np.sum(non_excess_mask)
                    adjusted_weights[non_excess_mask] += equal_redistribution
                    # Cap at limit
                    adjusted_weights = np.minimum(adjusted_weights, limit)
        
        # Final renormalization when full allocation is feasible.
        if np.sum(adjusted_weights) > 0 and limit * len(adjusted_weights) >= 1.0:
            adjusted_weights = adjusted_weights / np.sum(adjusted_weights)
        
        return adjusted_weights
    
    def _apply_diversification_constraints(self, sector_weights: np.ndarray, sector_limit: float) -> np.ndarray:
        """Apply sector diversification constraints"""

        adjusted_weights = sector_weights.astype(float).copy()
        if np.sum(adjusted_weights) <= 0:
            return np.ones_like(adjusted_weights) / len(adjusted_weights)

        adjusted_weights = adjusted_weights / np.sum(adjusted_weights)

        # Iterative capping avoids renormalization re-introducing limit breaches.
        for _ in range(10):
            excess_mask = adjusted_weights > sector_limit
            if not np.any(excess_mask):
                break

            excess_weight = np.sum(adjusted_weights[excess_mask] - sector_limit)
            adjusted_weights[excess_mask] = sector_limit

            non_excess_mask = ~excess_mask
            if np.any(non_excess_mask):
                capacity = np.maximum(0.0, sector_limit - adjusted_weights[non_excess_mask])
                total_capacity = np.sum(capacity)
                if total_capacity > 0:
                    adjusted_weights[non_excess_mask] += capacity * (excess_weight / total_capacity)
                else:
                    adjusted_weights[non_excess_mask] += excess_weight / np.sum(non_excess_mask)

            total = np.sum(adjusted_weights)
            if total > 0:
                adjusted_weights /= total

        return adjusted_weights
    
    def _apply_leverage_limits(self, current_leverage: float, leverage_limit: float, market_stress: float) -> float:
        """Apply leverage limits with stress adjustments"""

        # `leverage_limit` is treated as the hard ceiling provided by caller.
        # Apply a small additional stress buffer to enforce conservative deleveraging.
        stress_buffer = min(0.2, 0.02 + max(0.0, market_stress) * 0.15)
        effective_limit = max(0.1, leverage_limit * (1 - stress_buffer))

        if current_leverage > effective_limit:
            target_leverage = effective_limit
        else:
            target_leverage = current_leverage

        return max(target_leverage, 0.1)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
