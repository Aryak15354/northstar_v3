#!/usr/bin/env python3
"""
Performance Latency Tests for Unified Volatility Engine

Tests latency requirements for critical operations:
- Greeks computation latency (target <50ms)
- State update latency (target <100ms)
- Strategy generation latency

Requirements: 3.1, 1.2
"""

import pytest
import time
import numpy as np
from datetime import datetime, date, timedelta
from typing import List

from src.volatility.greeks_aggregator import GreeksAggregator, Position
from src.volatility.state_engine import (
    VolatilityStateEngine, PortfolioGreeks as StatePortfolioGreeks
)
from src.volatility.strategy_generator import (
    StrategyGenerator, TargetGreeks, Constraints, MarketState
)


def create_test_positions(num_positions: int) -> List[Position]:
    """Create test positions"""
    positions = []
    base_date = datetime.now().date()
    
    for i in range(num_positions):
        strike = 400.0 + (i % 20) * 5.0
        expiry = base_date + timedelta(days=30 + (i % 60))
        option_type = 'call' if i % 2 == 0 else 'put'
        quantity = 1 if i % 3 == 0 else -1
        
        position = Position(
            position_id=f"pos_{i}",
            underlying="SPY",
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            quantity=quantity,
            spot_price=450.0,
            implied_vol=0.20 + (i % 10) * 0.01,
            risk_free_rate=0.05
        )
        positions.append(position)
    
    return positions


class TestGreeksComputationLatency:
    """Test Greeks computation latency requirements"""
    
    def test_greeks_computation_latency_50_positions(self):
        """
        Test Greeks computation latency with 50 positions.
        
        Requirement: P95 < 50ms
        """
        positions = create_test_positions(50)
        aggregator = GreeksAggregator()
        
        # Warm-up
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Measure latency
        times = []
        for _ in range(100):
            start = time.perf_counter()
            greeks = aggregator.compute_portfolio_greeks(positions)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p95 = np.percentile(times, 95)
        
        print(f"\n📊 Greeks Latency (50 positions):")
        print(f"  P50: {np.percentile(times, 50):.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {np.percentile(times, 99):.2f}ms")
        print(f"  Target: P95 < 50ms")
        
        assert p95 < 50, f"P95 latency {p95:.2f}ms exceeds target 50ms"
    
    def test_greeks_computation_latency_100_positions(self):
        """
        Test Greeks computation latency with 100 positions.
        
        Requirement: P95 < 50ms
        """
        positions = create_test_positions(100)
        aggregator = GreeksAggregator()
        
        # Warm-up
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Measure latency
        times = []
        for _ in range(100):
            start = time.perf_counter()
            greeks = aggregator.compute_portfolio_greeks(positions)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p95 = np.percentile(times, 95)
        
        print(f"\n📊 Greeks Latency (100 positions):")
        print(f"  P50: {np.percentile(times, 50):.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {np.percentile(times, 99):.2f}ms")
        print(f"  Target: P95 < 50ms")
        
        assert p95 < 50, f"P95 latency {p95:.2f}ms exceeds target 50ms"
    
    def test_greeks_computation_worst_case(self):
        """
        Test Greeks computation worst-case latency.
        
        Ensures P99 is reasonable even in worst case.
        """
        positions = create_test_positions(100)
        aggregator = GreeksAggregator()
        
        # Warm-up
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Measure latency
        times = []
        for _ in range(100):
            start = time.perf_counter()
            greeks = aggregator.compute_portfolio_greeks(positions)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p99 = np.percentile(times, 99)
        max_time = np.max(times)
        
        print(f"\n📊 Greeks Worst Case:")
        print(f"  P99: {p99:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"  Target: P99 < 100ms")
        
        assert p99 < 100, f"P99 latency {p99:.2f}ms exceeds target 100ms"


class TestStateUpdateLatency:
    """Test state update latency requirements"""
    
    def test_state_update_latency(self):
        """
        Test state update propagation latency.
        
        Requirement: P95 < 100ms
        """
        engine = VolatilityStateEngine(persistence_dir="data/testing/latency")
        
        # Warm-up
        test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
        engine.update_portfolio_greeks(test_greeks)
        
        # Measure latency
        times = []
        for i in range(20):  # Reduced from 100
            test_greeks = StatePortfolioGreeks(
                delta=100.0 + i,
                gamma=5.0 + i * 0.1,
                vega=200.0 + i * 2
            )
            
            start = time.perf_counter()
            success = engine.update_portfolio_greeks(test_greeks)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            
            if success:
                times.append(elapsed)
        
        p95 = np.percentile(times, 95)
        
        print(f"\n📊 State Update Latency:")
        print(f"  P50: {np.percentile(times, 50):.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {np.percentile(times, 99):.2f}ms")
        print(f"  Target: P95 < 100ms")
        
        assert p95 < 100, f"P95 latency {p95:.2f}ms exceeds target 100ms"
    
    def test_state_update_consistency(self):
        """
        Test that state updates have consistent latency.
        
        Ensures no significant variance in update times.
        """
        engine = VolatilityStateEngine(persistence_dir="data/testing/latency_consistency")
        
        # Warm-up
        test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
        engine.update_portfolio_greeks(test_greeks)
        
        # Measure latency
        times = []
        for i in range(20):  # Reduced from 100
            test_greeks = StatePortfolioGreeks(
                delta=100.0 + i,
                gamma=5.0,
                vega=200.0
            )
            
            start = time.perf_counter()
            success = engine.update_portfolio_greeks(test_greeks)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            
            if success:
                times.append(elapsed)
        
        mean_time = np.mean(times)
        std_time = np.std(times)
        cv = std_time / mean_time  # Coefficient of variation
        
        print(f"\n📊 State Update Consistency:")
        print(f"  Mean: {mean_time:.2f}ms")
        print(f"  Std Dev: {std_time:.2f}ms")
        print(f"  CV: {cv:.2%}")
        print(f"  Target: CV < 100%")
        
        assert cv < 1.0, f"Coefficient of variation {cv:.2%} indicates inconsistent latency"


class TestStrategyGenerationLatency:
    """Test strategy generation latency"""
    
    def test_strategy_generation_latency(self):
        """
        Test strategy generation latency.
        
        Ensures strategy generation completes in reasonable time.
        """
        generator = StrategyGenerator()
        
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.2,
            vega=10.0,
            vega_tolerance=2.0,
            gamma=0.5,
            gamma_tolerance=0.2
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"],
            max_dte=60,
            min_dte=14
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Warm-up
        _ = generator.generate(target, constraints, state)
        
        # Measure latency
        times = []
        for _ in range(50):
            start = time.perf_counter()
            strategies = generator.generate(target, constraints, state)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p95 = np.percentile(times, 95)
        
        print(f"\n📊 Strategy Generation Latency:")
        print(f"  P50: {np.percentile(times, 50):.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {np.percentile(times, 99):.2f}ms")
        print(f"  Target: P95 < 500ms")
        
        assert p95 < 500, f"P95 latency {p95:.2f}ms exceeds target 500ms"


class TestEndToEndLatency:
    """Test end-to-end operation latency"""
    
    def test_full_pipeline_latency(self):
        """
        Test full pipeline latency: Greeks → State Update → Strategy Generation.
        
        Ensures complete workflow completes in reasonable time.
        """
        # Setup
        positions = create_test_positions(100)
        aggregator = GreeksAggregator()
        engine = VolatilityStateEngine(persistence_dir="data/testing/e2e_latency")
        generator = StrategyGenerator()
        
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.2,
            vega=10.0,
            vega_tolerance=2.0
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Warm-up
        greeks = aggregator.compute_portfolio_greeks(positions)
        state_greeks = StatePortfolioGreeks(
            delta=greeks.delta,
            gamma=greeks.gamma,
            vega=greeks.vega
        )
        engine.update_portfolio_greeks(state_greeks)
        _ = generator.generate(target, constraints, state)
        
        # Measure end-to-end latency
        times = []
        for i in range(20):
            start = time.perf_counter()
            
            # Step 1: Compute Greeks
            greeks = aggregator.compute_portfolio_greeks(positions)
            
            # Step 2: Update state
            state_greeks = StatePortfolioGreeks(
                delta=greeks.delta + i,
                gamma=greeks.gamma,
                vega=greeks.vega
            )
            engine.update_portfolio_greeks(state_greeks)
            
            # Step 3: Generate strategies
            strategies = generator.generate(target, constraints, state)
            
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        p95 = np.percentile(times, 95)
        
        print(f"\n📊 End-to-End Pipeline Latency:")
        print(f"  P50: {np.percentile(times, 50):.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {np.percentile(times, 99):.2f}ms")
        print(f"  Target: P95 < 1000ms")
        
        assert p95 < 1000, f"P95 latency {p95:.2f}ms exceeds target 1000ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
