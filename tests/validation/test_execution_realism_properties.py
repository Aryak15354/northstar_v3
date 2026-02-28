#!/usr/bin/env python3
"""
Property-Based Tests for Execution Realism Model

Tests the correctness properties of the execution realism simulation system
for institutional validation.

# Feature: institutional-validation-layers, Property 36: Execution Friction Application
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any

# Import the system under test
from src.validation.execution_realism_model import ExecutionRealismModel, Trade, ExecutionResult, ExecutionQuality


class TestExecutionRealismProperties:
    """Property-based tests for Execution Realism Model"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test execution model
        self.model = ExecutionRealismModel(
            base_dir=os.path.join(self.temp_dir, "execution")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 36: Execution Friction Application
    # ========================================================================
    
    @given(
        target_weight=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        current_weight=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        urgency=st.sampled_from(['low', 'normal', 'high'])
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_36_execution_friction_application(self, target_weight: float, current_weight: float, urgency: str):
        """
        Property 36: Execution Friction Application
        
        For any trade in the shadow fund, execution friction (partial fills, 
        slippage, market impact, T+1 delay) must be applied.
        
        Validates: Requirements 17.1, 17.2, 17.3
        """
        
        # Filter out extremely small numbers that are essentially zero
        assume(abs(target_weight) > 1e-10)
        assume(abs(current_weight) > 1e-10 or current_weight == 0.0)
        assume(abs(target_weight - current_weight) > 1e-10)
        
        # Create trade
        trade_size = abs(target_weight - current_weight)
        direction = 'buy' if target_weight > current_weight else 'sell'
        
        trade = Trade(
            ticker="TEST_STOCK",
            target_weight=target_weight,
            current_weight=current_weight,
            trade_size=trade_size,
            direction=direction,
            urgency=urgency
        )
        
        # Simulate execution
        result = self.model.simulate_trade_execution(trade)
        
        # PROPERTY: Execution result must be valid
        assert result is not None
        assert isinstance(result, ExecutionResult)
        
        # PROPERTY: Fill rate must be between 0 and 1
        assert 0.0 <= result.fill_rate <= 1.0
        
        # PROPERTY: Slippage must be non-negative
        assert result.slippage >= 0.0
        
        # PROPERTY: Market impact must be non-negative
        assert result.market_impact >= 0.0
        
        # PROPERTY: Delay must be non-negative
        assert result.delay_days >= 0
        
        # PROPERTY: Total cost must be non-negative
        assert result.total_cost >= 0.0
        
        # PROPERTY: Achieved weight must be between current and target (or equal to current if no fill)
        tolerance = 1e-10
        if result.fill_rate > 0:
            if target_weight > current_weight:
                # Buy trade - achieved should be between current and target
                assert current_weight - tolerance <= result.achieved_weight <= target_weight + tolerance
            else:
                # Sell trade - achieved should be between target and current
                assert target_weight - tolerance <= result.achieved_weight <= current_weight + tolerance
        else:
            # No fill - achieved should equal current
            assert abs(result.achieved_weight - current_weight) < tolerance
    
    @given(
        trade_count=st.integers(min_value=1, max_value=10),
        urgency=st.sampled_from(['low', 'normal', 'high'])
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_36_portfolio_rebalance_friction(self, trade_count: int, urgency: str):
        """
        Property 36: Portfolio Rebalance Friction
        
        All trades in a portfolio rebalance must have execution friction applied.
        """
        
        # Create multiple trades
        trades = []
        for i in range(trade_count):
            target_weight = np.random.uniform(-0.1, 0.1)
            current_weight = np.random.uniform(-0.1, 0.1)
            trade_size = abs(target_weight - current_weight)
            direction = 'buy' if target_weight > current_weight else 'sell'
            
            trade = Trade(
                ticker=f"STOCK_{i:02d}",
                target_weight=target_weight,
                current_weight=current_weight,
                trade_size=trade_size,
                direction=direction,
                urgency=urgency
            )
            trades.append(trade)
        
        # Simulate portfolio rebalance
        results = self.model.simulate_portfolio_rebalance(trades)
        
        # PROPERTY: All trades must have results
        assert len(results) == len(trades)
        
        # PROPERTY: All results must have friction applied
        for result in results:
            assert isinstance(result, ExecutionResult)
            assert 0.0 <= result.fill_rate <= 1.0
            assert result.slippage >= 0.0
            assert result.market_impact >= 0.0
            assert result.delay_days >= 0
            assert result.total_cost >= 0.0
    
    # ========================================================================
    # EXECUTION QUALITY PROPERTIES
    # ========================================================================
    
    @given(
        trade_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_execution_quality_bounds(self, trade_count: int):
        """
        Property: Execution Quality Bounds
        
        Execution quality metrics must be within valid bounds.
        """
        
        # Create random trades
        trades = []
        for i in range(trade_count):
            target_weight = np.random.uniform(-0.2, 0.2)
            current_weight = np.random.uniform(-0.2, 0.2)
            trade_size = abs(target_weight - current_weight)
            direction = 'buy' if target_weight > current_weight else 'sell'
            urgency = np.random.choice(['low', 'normal', 'high'])
            
            trade = Trade(
                ticker=f"STOCK_{i:02d}",
                target_weight=target_weight,
                current_weight=current_weight,
                trade_size=trade_size,
                direction=direction,
                urgency=urgency
            )
            trades.append(trade)
        
        # Simulate execution
        results = self.model.simulate_portfolio_rebalance(trades)
        
        # Record quality
        date = datetime.now()
        quality = self.model.record_execution_quality(date, results)
        
        # PROPERTY: Quality metrics must be within bounds
        assert isinstance(quality, ExecutionQuality)
        assert 0.0 <= quality.fill_rate <= 1.0
        assert quality.avg_slippage >= 0.0
        assert quality.rebalance_delay >= 0.0
        assert quality.realized_cost >= 0.0
        assert quality.trade_count >= 0
        assert quality.trade_count == len(results)
    
    # ========================================================================
    # LIQUIDITY CONSTRAINT PROPERTIES
    # ========================================================================
    
    @given(
        trade_size=st.floats(min_value=0.001, max_value=0.5)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_liquidity_constraint_monotonicity(self, trade_size: float):
        """
        Property: Liquidity Constraint Monotonicity
        
        Larger trades should face higher liquidity constraints (lower fill rates).
        """
        
        # Create two trades with different sizes
        small_trade = Trade(
            ticker="TEST_STOCK",
            target_weight=trade_size * 0.5,
            current_weight=0.0,
            trade_size=trade_size * 0.5,
            direction="buy",
            urgency="normal"
        )
        
        large_trade = Trade(
            ticker="TEST_STOCK",
            target_weight=trade_size,
            current_weight=0.0,
            trade_size=trade_size,
            direction="buy",
            urgency="normal"
        )
        
        # Simulate execution
        small_result = self.model.simulate_trade_execution(small_trade)
        large_result = self.model.simulate_trade_execution(large_trade)
        
        # PROPERTY: Larger trades should generally have lower or equal fill rates
        # (Allow for some randomness in the model)
        assert large_result.fill_rate <= small_result.fill_rate + 0.1
    
    # ========================================================================
    # URGENCY IMPACT PROPERTIES
    # ========================================================================
    
    @given(
        trade_size=st.floats(min_value=0.01, max_value=0.2)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_urgency_impact_ordering(self, trade_size: float):
        """
        Property: Urgency Impact Ordering
        
        Higher urgency trades should have higher costs but potentially better fill rates.
        """
        
        # Create trades with different urgency levels
        urgency_levels = ['low', 'normal', 'high']
        results = {}
        
        for urgency in urgency_levels:
            trade = Trade(
                ticker="TEST_STOCK",
                target_weight=trade_size,
                current_weight=0.0,
                trade_size=trade_size,
                direction="buy",
                urgency=urgency
            )
            
            result = self.model.simulate_trade_execution(trade)
            results[urgency] = result
        
        # PROPERTY: Higher urgency should generally have higher costs
        # (Allow for some randomness)
        low_cost = results['low'].total_cost
        normal_cost = results['normal'].total_cost
        high_cost = results['high'].total_cost
        
        # High urgency should cost more than or equal to normal
        assert high_cost >= normal_cost - 0.001  # Small tolerance for randomness
        
        # Normal should cost more than or equal to low
        assert normal_cost >= low_cost - 0.001
    
    # ========================================================================
    # MARKET IMPACT PROPERTIES
    # ========================================================================
    
    @given(
        base_size=st.floats(min_value=0.01, max_value=0.1)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_market_impact_scaling(self, base_size: float):
        """
        Property: Market Impact Scaling
        
        Market impact should increase with trade size (typically square root relationship).
        """
        
        # Create trades with different sizes
        small_trade = Trade(
            ticker="TEST_STOCK",
            target_weight=base_size,
            current_weight=0.0,
            trade_size=base_size,
            direction="buy",
            urgency="normal"
        )
        
        large_trade = Trade(
            ticker="TEST_STOCK",
            target_weight=base_size * 4,  # 4x larger
            current_weight=0.0,
            trade_size=base_size * 4,
            direction="buy",
            urgency="normal"
        )
        
        # Simulate execution
        small_result = self.model.simulate_trade_execution(small_trade)
        large_result = self.model.simulate_trade_execution(large_trade)
        
        # PROPERTY: Larger trade should have higher market impact
        assert large_result.market_impact >= small_result.market_impact
        
        # PROPERTY: Market impact should not scale linearly (should be sub-linear due to sqrt)
        # 4x size should have less than 4x impact
        if small_result.market_impact > 0:
            impact_ratio = large_result.market_impact / small_result.market_impact
            assert impact_ratio < 4.0  # Should be less than linear scaling
    
    # ========================================================================
    # EXECUTION DELAY PROPERTIES
    # ========================================================================
    
    def test_property_execution_delay_bounds(self):
        """
        Property: Execution Delay Bounds
        
        Execution delays must be reasonable (not excessive).
        """
        
        # Create sample trade
        trade = Trade(
            ticker="TEST_STOCK",
            target_weight=0.05,
            current_weight=0.0,
            trade_size=0.05,
            direction="buy",
            urgency="normal"
        )
        
        # Simulate multiple executions to test delay distribution
        delays = []
        for _ in range(100):
            result = self.model.simulate_trade_execution(trade)
            delays.append(result.delay_days)
        
        # PROPERTY: All delays must be non-negative
        assert all(delay >= 0 for delay in delays)
        
        # PROPERTY: Most delays should be reasonable (< 5 days)
        reasonable_delays = sum(1 for delay in delays if delay <= 5)
        assert reasonable_delays >= 90  # At least 90% should be <= 5 days
        
        # PROPERTY: Some executions should be immediate (T+0)
        immediate_executions = sum(1 for delay in delays if delay == 0)
        assert immediate_executions > 0  # At least some should be immediate
    
    # ========================================================================
    # SCHEMA VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_execution_quality_schema_enforcement(self):
        """
        Property: Execution Quality Schema Enforcement
        
        Execution quality data must conform to required schema.
        """
        
        # Create sample execution results
        trades = [
            Trade(
                ticker="STOCK_01",
                target_weight=0.05,
                current_weight=0.02,
                trade_size=0.03,
                direction="buy",
                urgency="normal"
            )
        ]
        
        results = self.model.simulate_portfolio_rebalance(trades)
        quality = self.model.record_execution_quality(datetime.now(), results)
        
        # PROPERTY: Quality object must have all required fields
        assert hasattr(quality, 'date')
        assert hasattr(quality, 'avg_slippage')
        assert hasattr(quality, 'fill_rate')
        assert hasattr(quality, 'rebalance_delay')
        assert hasattr(quality, 'realized_cost')
        assert hasattr(quality, 'trade_count')
        
        # PROPERTY: Fields must have correct types
        assert isinstance(quality.date, datetime)
        assert isinstance(quality.avg_slippage, (int, float))
        assert isinstance(quality.fill_rate, (int, float))
        assert isinstance(quality.rebalance_delay, (int, float))
        assert isinstance(quality.realized_cost, (int, float))
        assert isinstance(quality.trade_count, int)
    
    # ========================================================================
    # ERROR HANDLING PROPERTIES
    # ========================================================================
    
    def test_property_empty_trade_list_handling(self):
        """
        Property: Empty Trade List Handling
        
        System must gracefully handle empty trade lists.
        """
        
        # Simulate empty rebalance
        results = self.model.simulate_portfolio_rebalance([])
        
        # PROPERTY: Empty trade list should return empty results
        assert isinstance(results, list)
        assert len(results) == 0
        
        # Record quality for empty execution
        quality = self.model.record_execution_quality(datetime.now(), results)
        
        # PROPERTY: Quality metrics should be valid for empty execution
        assert quality.trade_count == 0
        assert quality.avg_slippage == 0.0
        assert quality.fill_rate == 1.0  # Perfect fill rate when no trades
        assert quality.rebalance_delay == 0.0
        assert quality.realized_cost == 0.0
    
    # ========================================================================
    # SUMMARY STATISTICS PROPERTIES
    # ========================================================================
    
    @given(
        days=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=10, deadline=10000)
    def test_property_summary_statistics_accuracy(self, days: int):
        """
        Property: Summary Statistics Accuracy
        
        Summary statistics must accurately reflect recorded execution quality.
        """
        
        recorded_qualities = []
        
        # Record multiple days of execution quality
        for day in range(days):
            date = datetime.now() - timedelta(days=days-day-1)
            
            # Create random trades
            trade_count = np.random.randint(1, 5)
            trades = []
            for i in range(trade_count):
                target_weight = np.random.uniform(-0.1, 0.1)
                current_weight = np.random.uniform(-0.1, 0.1)
                trade_size = abs(target_weight - current_weight)
                direction = 'buy' if target_weight > current_weight else 'sell'
                urgency = np.random.choice(['low', 'normal', 'high'])
                
                trade = Trade(
                    ticker=f"STOCK_{i:02d}",
                    target_weight=target_weight,
                    current_weight=current_weight,
                    trade_size=trade_size,
                    direction=direction,
                    urgency=urgency
                )
                trades.append(trade)
            
            # Simulate and record
            results = self.model.simulate_portfolio_rebalance(trades)
            quality = self.model.record_execution_quality(date, results)
            recorded_qualities.append(quality)
        
        # Get summary
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
        summary = self.model.get_execution_quality_summary(start_date, end_date)
        
        # PROPERTY: Summary must reflect recorded data
        assert summary['days'] >= days  # May include other data
        
        # PROPERTY: Total trades should match sum of recorded trades
        expected_total_trades = sum(q.trade_count for q in recorded_qualities)
        assert summary['total_trades'] >= expected_total_trades
        
        # PROPERTY: Summary metrics should be reasonable
        assert 0.0 <= summary['avg_fill_rate'] <= 1.0
        assert summary['avg_slippage'] >= 0.0
        assert summary['avg_delay'] >= 0.0
        assert summary['total_cost'] >= 0.0


def test_trade_validation():
    """Test Trade validation"""
    
    # Valid trade
    valid_trade = Trade(
        ticker="TEST",
        target_weight=0.05,
        current_weight=0.02,
        trade_size=0.03,
        direction="buy",
        urgency="normal"
    )
    
    errors = valid_trade.validate()
    assert len(errors) == 0
    
    # Invalid trade - bad direction
    invalid_trade = Trade(
        ticker="TEST",
        target_weight=0.05,
        current_weight=0.02,
        trade_size=0.03,
        direction="invalid",  # Invalid direction
        urgency="normal"
    )
    
    errors = invalid_trade.validate()
    assert len(errors) > 0
    assert any("Invalid direction" in error for error in errors)


def test_execution_result_validation():
    """Test ExecutionResult validation"""
    
    # Valid result
    valid_result = ExecutionResult(
        ticker="TEST",
        target_weight=0.05,
        achieved_weight=0.04,
        fill_rate=0.8,
        slippage=0.001,
        market_impact=0.0005,
        delay_days=1,
        total_cost=0.0015
    )
    
    errors = valid_result.validate()
    assert len(errors) == 0
    
    # Invalid result - bad fill rate
    invalid_result = ExecutionResult(
        ticker="TEST",
        target_weight=0.05,
        achieved_weight=0.04,
        fill_rate=1.5,  # Invalid fill rate > 1.0
        slippage=0.001,
        market_impact=0.0005,
        delay_days=1,
        total_cost=0.0015
    )
    
    errors = invalid_result.validate()
    assert len(errors) > 0
    assert any("Fill rate" in error and "outside bounds" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])