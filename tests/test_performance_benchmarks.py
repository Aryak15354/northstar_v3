#!/usr/bin/env python3
"""
Performance Benchmark Suite for Unified Volatility Engine

Creates benchmark suite for all critical operations with:
- Performance baselines
- Regression testing for performance
- Automated pass/fail criteria

Requirements: 3.1, 1.2
"""

import pytest
import time
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict

from src.volatility.greeks_aggregator import (
    GreeksAggregator, Position, PortfolioGreeks, GreeksLimits
)
from src.volatility.state_engine import (
    VolatilityStateEngine, PortfolioGreeks as StatePortfolioGreeks
)
from src.volatility.monte_carlo_engine import MonteCarloEngine
from src.volatility.strategy_generator import (
    StrategyGenerator, TargetGreeks, Constraints, MarketState
)


# Performance baselines (in milliseconds)
PERFORMANCE_BASELINES = {
    'greeks_computation_100_positions': {
        'p50': 20.0,
        'p95': 50.0,
        'p99': 75.0
    },
    'greeks_computation_500_positions': {
        'p50': 100.0,
        'p95': 250.0,
        'p99': 350.0
    },
    'state_update': {
        'p50': 1.0,
        'p95': 100.0,
        'p99': 150.0
    },
    'strategy_generation': {
        'p50': 100.0,
        'p95': 500.0,
        'p99': 750.0
    },
    'monte_carlo_1000_paths': {
        'total_seconds': 5.0
    }
}


def create_test_positions(num_positions: int) -> List[Position]:
    """Create test positions for benchmarking"""
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


def benchmark_operation(operation_func, num_runs: int = 100) -> Dict[str, float]:
    """
    Benchmark an operation and return timing statistics.
    
    Returns:
        Dict with avg_ms, p50_ms, p95_ms, p99_ms
    """
    times = []
    
    for _ in range(num_runs):
        start = time.perf_counter()
        operation_func()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    return {
        'avg_ms': np.mean(times),
        'p50_ms': np.percentile(times, 50),
        'p95_ms': np.percentile(times, 95),
        'p99_ms': np.percentile(times, 99),
        'min_ms': np.min(times),
        'max_ms': np.max(times)
    }


class TestGreeksComputationBenchmarks:
    """Benchmark Greeks computation performance"""
    
    def test_greeks_100_positions_benchmark(self):
        """
        Benchmark Greeks computation with 100 positions.
        
        Baseline: P95 < 50ms
        """
        positions = create_test_positions(100)
        aggregator = GreeksAggregator()
        
        # Warm-up
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Benchmark
        results = benchmark_operation(
            lambda: aggregator.compute_portfolio_greeks(positions),
            num_runs=100
        )
        
        baseline = PERFORMANCE_BASELINES['greeks_computation_100_positions']
        
        print(f"\n📊 Greeks Computation (100 positions):")
        print(f"  P50: {results['p50_ms']:.2f}ms (baseline: {baseline['p50']}ms)")
        print(f"  P95: {results['p95_ms']:.2f}ms (baseline: {baseline['p95']}ms)")
        print(f"  P99: {results['p99_ms']:.2f}ms (baseline: {baseline['p99']}ms)")
        
        # Assert against baselines
        assert results['p50_ms'] < baseline['p50'], \
            f"P50 {results['p50_ms']:.2f}ms exceeds baseline {baseline['p50']}ms"
        assert results['p95_ms'] < baseline['p95'], \
            f"P95 {results['p95_ms']:.2f}ms exceeds baseline {baseline['p95']}ms"
        assert results['p99_ms'] < baseline['p99'], \
            f"P99 {results['p99_ms']:.2f}ms exceeds baseline {baseline['p99']}ms"
    
    def test_greeks_500_positions_benchmark(self):
        """
        Benchmark Greeks computation with 500 positions.
        
        Baseline: P95 < 250ms
        """
        positions = create_test_positions(500)
        aggregator = GreeksAggregator()
        
        # Warm-up
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Benchmark
        results = benchmark_operation(
            lambda: aggregator.compute_portfolio_greeks(positions),
            num_runs=50
        )
        
        baseline = PERFORMANCE_BASELINES['greeks_computation_500_positions']
        
        print(f"\n📊 Greeks Computation (500 positions):")
        print(f"  P50: {results['p50_ms']:.2f}ms (baseline: {baseline['p50']}ms)")
        print(f"  P95: {results['p95_ms']:.2f}ms (baseline: {baseline['p95']}ms)")
        print(f"  P99: {results['p99_ms']:.2f}ms (baseline: {baseline['p99']}ms)")
        
        # Assert against baselines
        assert results['p50_ms'] < baseline['p50'], \
            f"P50 {results['p50_ms']:.2f}ms exceeds baseline {baseline['p50']}ms"
        assert results['p95_ms'] < baseline['p95'], \
            f"P95 {results['p95_ms']:.2f}ms exceeds baseline {baseline['p95']}ms"
    
    def test_greeks_scaling(self):
        """Test that Greeks computation scales linearly with position count"""
        sizes = [50, 100, 200]
        times = []
        
        aggregator = GreeksAggregator()
        
        for size in sizes:
            positions = create_test_positions(size)
            
            # Warm-up
            _ = aggregator.compute_portfolio_greeks(positions)
            
            # Benchmark
            results = benchmark_operation(
                lambda: aggregator.compute_portfolio_greeks(positions),
                num_runs=50
            )
            times.append(results['p50_ms'])
        
        print(f"\n📊 Greeks Computation Scaling:")
        for size, time_ms in zip(sizes, times):
            print(f"  {size} positions: {time_ms:.2f}ms ({time_ms/size:.3f}ms per position)")
        
        # Check linear scaling (time per position should be roughly constant)
        time_per_position = [t/s for t, s in zip(times, sizes)]
        scaling_variance = np.std(time_per_position) / np.mean(time_per_position)
        
        print(f"  Scaling variance: {scaling_variance:.2%}")
        
        # Assert scaling is reasonable (variance < 50%)
        assert scaling_variance < 0.5, \
            f"Scaling variance {scaling_variance:.2%} indicates non-linear scaling"


class TestStateUpdateBenchmarks:
    """Benchmark state update performance"""
    
    def test_state_update_benchmark(self):
        """
        Benchmark state update propagation.
        
        Baseline: P95 < 100ms
        """
        engine = VolatilityStateEngine(persistence_dir="data/test_benchmark")
        
        # Warm-up
        test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
        engine.update_portfolio_greeks(test_greeks)
        
        # Benchmark
        counter = [0]
        def update_operation():
            test_greeks = StatePortfolioGreeks(
                delta=100.0 + counter[0],
                gamma=5.0 + counter[0] * 0.1,
                vega=200.0 + counter[0] * 2
            )
            counter[0] += 1
            engine.update_portfolio_greeks(test_greeks)
        
        results = benchmark_operation(update_operation, num_runs=100)
        
        baseline = PERFORMANCE_BASELINES['state_update']
        
        print(f"\n📊 State Update:")
        print(f"  P50: {results['p50_ms']:.2f}ms (baseline: {baseline['p50']}ms)")
        print(f"  P95: {results['p95_ms']:.2f}ms (baseline: {baseline['p95']}ms)")
        print(f"  P99: {results['p99_ms']:.2f}ms (baseline: {baseline['p99']}ms)")
        
        # Assert against baselines
        assert results['p50_ms'] < baseline['p50'], \
            f"P50 {results['p50_ms']:.2f}ms exceeds baseline {baseline['p50']}ms"
        assert results['p95_ms'] < baseline['p95'], \
            f"P95 {results['p95_ms']:.2f}ms exceeds baseline {baseline['p95']}ms"


class TestStrategyGenerationBenchmarks:
    """Benchmark strategy generation performance"""
    
    def test_strategy_generation_benchmark(self):
        """
        Benchmark strategy generation.
        
        Baseline: P95 < 500ms
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
        
        # Benchmark
        results = benchmark_operation(
            lambda: generator.generate(target, constraints, state),
            num_runs=50
        )
        
        baseline = PERFORMANCE_BASELINES['strategy_generation']
        
        print(f"\n📊 Strategy Generation:")
        print(f"  P50: {results['p50_ms']:.2f}ms (baseline: {baseline['p50']}ms)")
        print(f"  P95: {results['p95_ms']:.2f}ms (baseline: {baseline['p95']}ms)")
        print(f"  P99: {results['p99_ms']:.2f}ms (baseline: {baseline['p99']}ms)")
        
        # Assert against baselines
        assert results['p50_ms'] < baseline['p50'], \
            f"P50 {results['p50_ms']:.2f}ms exceeds baseline {baseline['p50']}ms"
        assert results['p95_ms'] < baseline['p95'], \
            f"P95 {results['p95_ms']:.2f}ms exceeds baseline {baseline['p95']}ms"


class TestMonteCarloPerformanceBenchmarks:
    """Benchmark Monte Carlo simulation performance"""
    
    def test_monte_carlo_1000_paths_benchmark(self):
        """
        Benchmark Monte Carlo simulation with 1000 paths.
        
        Baseline: < 5 seconds total
        """
        underlyings = ['SPY', 'QQQ', 'IWM']
        engine = MonteCarloEngine(underlyings=underlyings)
        
        spot_prices = {'SPY': 450.0, 'QQQ': 380.0, 'IWM': 200.0}
        volatilities = {'SPY': 0.20, 'QQQ': 0.25, 'IWM': 0.30}
        
        # Warm-up
        _ = engine.simulate_portfolio(
            spot_prices=spot_prices,
            volatilities=volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=30,
            num_paths=100,
            seed=42
        )
        
        # Benchmark
        start = time.perf_counter()
        result = engine.simulate_portfolio(
            spot_prices=spot_prices,
            volatilities=volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=30,
            num_paths=1000,
            seed=42
        )
        elapsed = time.perf_counter() - start
        
        baseline = PERFORMANCE_BASELINES['monte_carlo_1000_paths']
        
        print(f"\n📊 Monte Carlo (1000 paths, 30 days):")
        print(f"  Total time: {elapsed:.2f}s (baseline: {baseline['total_seconds']}s)")
        print(f"  Paths per second: {1000 / elapsed:.0f}")
        
        # Assert against baseline
        assert elapsed < baseline['total_seconds'], \
            f"Time {elapsed:.2f}s exceeds baseline {baseline['total_seconds']}s"


class TestPerformanceRegression:
    """Test for performance regressions"""
    
    def test_no_performance_regression(self):
        """
        Comprehensive regression test across all operations.
        
        This test ensures no operation has regressed beyond acceptable limits.
        """
        print(f"\n{'='*60}")
        print("📊 PERFORMANCE REGRESSION TEST")
        print(f"{'='*60}")
        
        regressions = []
        
        # Test Greeks computation
        positions = create_test_positions(100)
        aggregator = GreeksAggregator()
        _ = aggregator.compute_portfolio_greeks(positions)
        
        results = benchmark_operation(
            lambda: aggregator.compute_portfolio_greeks(positions),
            num_runs=50
        )
        
        baseline = PERFORMANCE_BASELINES['greeks_computation_100_positions']
        if results['p95_ms'] > baseline['p95']:
            regressions.append(
                f"Greeks computation P95 {results['p95_ms']:.2f}ms > baseline {baseline['p95']}ms"
            )
        
        # Test state updates
        engine = VolatilityStateEngine(persistence_dir="data/test_regression")
        test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
        engine.update_portfolio_greeks(test_greeks)
        
        counter = [0]
        def update_operation():
            test_greeks = StatePortfolioGreeks(
                delta=100.0 + counter[0],
                gamma=5.0,
                vega=200.0
            )
            counter[0] += 1
            engine.update_portfolio_greeks(test_greeks)
        
        results = benchmark_operation(update_operation, num_runs=50)
        
        baseline = PERFORMANCE_BASELINES['state_update']
        if results['p95_ms'] > baseline['p95']:
            regressions.append(
                f"State update P95 {results['p95_ms']:.2f}ms > baseline {baseline['p95']}ms"
            )
        
        # Report results
        if regressions:
            print("\n❌ PERFORMANCE REGRESSIONS DETECTED:")
            for regression in regressions:
                print(f"  - {regression}")
            pytest.fail(f"Performance regressions detected: {len(regressions)}")
        else:
            print("\n✅ NO PERFORMANCE REGRESSIONS DETECTED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
