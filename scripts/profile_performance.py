#!/usr/bin/env python3
"""
Performance Profiling Script for Unified Volatility Engine

Profiles critical paths:
- Greeks computation (target <50ms)
- State update propagation (target <100ms)
- Monte Carlo simulation (parallel execution)

Requirements: 3.1, 1.2
"""

import time
import cProfile
import pstats
import io
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple
import multiprocessing as mp
from functools import partial
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import components to profile
from src.volatility.greeks_aggregator import (
    GreeksAggregator, Position, PortfolioGreeks, GreeksLimits
)
from src.volatility.state_engine import (
    VolatilityStateEngine, VolatilityState, RegimeState, PortfolioGreeks as StatePortfolioGreeks
)
from src.volatility.monte_carlo_engine import (
    MonteCarloEngine, HestonParams
)
from src.volatility.strategy_generator import (
    StrategyGenerator, TargetGreeks, Constraints, MarketState
)


class PerformanceProfiler:
    """Performance profiling and optimization for critical paths"""
    
    def __init__(self):
        self.results = {}
    
    def profile_greeks_computation(self, num_positions: int = 100) -> Dict:
        """
        Profile Greeks computation performance.
        Target: <50ms for portfolio Greeks calculation
        """
        print(f"\n{'='*60}")
        print(f"📊 Profiling Greeks Computation ({num_positions} positions)")
        print(f"{'='*60}")
        
        # Create test positions
        positions = self._create_test_positions(num_positions)
        aggregator = GreeksAggregator()
        
        # Warm-up run
        _ = aggregator.compute_portfolio_greeks(positions)
        
        # Profile with cProfile
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Timed runs
        times = []
        for _ in range(100):
            start = time.perf_counter()
            greeks = aggregator.compute_portfolio_greeks(positions)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        profiler.disable()
        
        # Analyze results
        avg_time = np.mean(times)
        p50_time = np.percentile(times, 50)
        p95_time = np.percentile(times, 95)
        p99_time = np.percentile(times, 99)
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  P50: {p50_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms")
        print(f"  P99: {p99_time:.2f}ms")
        print(f"  Target: <50ms")
        
        if p95_time < 50:
            print(f"  ✅ PASS - P95 within target")
        else:
            print(f"  ❌ FAIL - P95 exceeds target by {p95_time - 50:.2f}ms")
        
        # Print hotspots
        print(f"\n🔥 Top Hotspots:")
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(10)
        print(s.getvalue())
        
        self.results['greeks_computation'] = {
            'num_positions': num_positions,
            'avg_time_ms': avg_time,
            'p50_time_ms': p50_time,
            'p95_time_ms': p95_time,
            'p99_time_ms': p99_time,
            'target_ms': 50,
            'passes': p95_time < 50
        }
        
        return self.results['greeks_computation']
    
    def profile_state_updates(self, num_updates: int = 100) -> Dict:
        """
        Profile state update propagation performance.
        Target: <100ms for state update propagation
        """
        print(f"\n{'='*60}")
        print(f"📊 Profiling State Update Propagation ({num_updates} updates)")
        print(f"{'='*60}")
        
        # Create state engine
        engine = VolatilityStateEngine(persistence_dir="data/test_profile")
        
        # Warm-up
        test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
        engine.update_portfolio_greeks(test_greeks)
        
        # Profile with cProfile
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Timed runs
        times = []
        for i in range(num_updates):
            # Create varying updates
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
        
        profiler.disable()
        
        # Analyze results
        avg_time = np.mean(times)
        p50_time = np.percentile(times, 50)
        p95_time = np.percentile(times, 95)
        p99_time = np.percentile(times, 99)
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  P50: {p50_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms")
        print(f"  P99: {p99_time:.2f}ms")
        print(f"  Target: <100ms")
        
        if p95_time < 100:
            print(f"  ✅ PASS - P95 within target")
        else:
            print(f"  ❌ FAIL - P95 exceeds target by {p95_time - 100:.2f}ms")
        
        # Print hotspots
        print(f"\n🔥 Top Hotspots:")
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(10)
        print(s.getvalue())
        
        self.results['state_updates'] = {
            'num_updates': num_updates,
            'avg_time_ms': avg_time,
            'p50_time_ms': p50_time,
            'p95_time_ms': p95_time,
            'p99_time_ms': p99_time,
            'target_ms': 100,
            'passes': p95_time < 100
        }
        
        return self.results['state_updates']
    
    def profile_monte_carlo_serial(self, num_paths: int = 10000, horizon_days: int = 30) -> Dict:
        """Profile Monte Carlo simulation (serial execution)"""
        print(f"\n{'='*60}")
        print(f"📊 Profiling Monte Carlo (Serial) - {num_paths} paths, {horizon_days} days")
        print(f"{'='*60}")
        
        # Create engine
        underlyings = ['SPY', 'QQQ', 'IWM']
        engine = MonteCarloEngine(underlyings=underlyings)
        
        spot_prices = {'SPY': 450.0, 'QQQ': 380.0, 'IWM': 200.0}
        volatilities = {'SPY': 0.20, 'QQQ': 0.25, 'IWM': 0.30}
        
        # Warm-up
        _ = engine.simulate_portfolio(
            spot_prices=spot_prices,
            volatilities=volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=horizon_days,
            num_paths=1000,
            seed=42
        )
        
        # Timed run
        start = time.perf_counter()
        result = engine.simulate_portfolio(
            spot_prices=spot_prices,
            volatilities=volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=horizon_days,
            num_paths=num_paths,
            seed=42
        )
        elapsed = time.perf_counter() - start
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Paths per second: {num_paths / elapsed:.0f}")
        print(f"  Time per path: {elapsed / num_paths * 1000:.2f}ms")
        
        self.results['monte_carlo_serial'] = {
            'num_paths': num_paths,
            'horizon_days': horizon_days,
            'total_time_s': elapsed,
            'paths_per_second': num_paths / elapsed,
            'time_per_path_ms': elapsed / num_paths * 1000
        }
        
        return self.results['monte_carlo_serial']
    
    def profile_monte_carlo_parallel(self, num_paths: int = 10000, horizon_days: int = 30, num_workers: int = None) -> Dict:
        """
        Profile Monte Carlo simulation with parallel execution.
        Implements multiprocessing for path generation.
        """
        if num_workers is None:
            num_workers = mp.cpu_count()
        
        print(f"\n{'='*60}")
        print(f"📊 Profiling Monte Carlo (Parallel) - {num_paths} paths, {horizon_days} days, {num_workers} workers")
        print(f"{'='*60}")
        
        # Create engine
        underlyings = ['SPY', 'QQQ', 'IWM']
        engine = MonteCarloEngine(underlyings=underlyings)
        
        spot_prices = {'SPY': 450.0, 'QQQ': 380.0, 'IWM': 200.0}
        volatilities = {'SPY': 0.20, 'QQQ': 0.25, 'IWM': 0.30}
        
        # Split paths across workers
        paths_per_worker = num_paths // num_workers
        
        # Worker function
        def simulate_chunk(worker_id, paths, seed_offset):
            chunk_engine = MonteCarloEngine(underlyings=underlyings)
            return chunk_engine.simulate_portfolio(
                spot_prices=spot_prices,
                volatilities=volatilities,
                initial_portfolio_value=1000000.0,
                horizon_days=horizon_days,
                num_paths=paths,
                seed=42 + seed_offset
            )
        
        # Timed parallel run
        start = time.perf_counter()
        
        with mp.Pool(processes=num_workers) as pool:
            results = pool.starmap(
                simulate_chunk,
                [(i, paths_per_worker, i * 1000) for i in range(num_workers)]
            )
        
        elapsed = time.perf_counter() - start
        
        # Combine results (simplified - just use first result for metrics)
        combined_result = results[0]
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Paths per second: {num_paths / elapsed:.0f}")
        print(f"  Time per path: {elapsed / num_paths * 1000:.2f}ms")
        print(f"  Workers: {num_workers}")
        
        # Compare to serial
        if 'monte_carlo_serial' in self.results:
            serial_time = self.results['monte_carlo_serial']['total_time_s']
            speedup = serial_time / elapsed
            print(f"  Speedup vs serial: {speedup:.2f}x")
        
        self.results['monte_carlo_parallel'] = {
            'num_paths': num_paths,
            'horizon_days': horizon_days,
            'num_workers': num_workers,
            'total_time_s': elapsed,
            'paths_per_second': num_paths / elapsed,
            'time_per_path_ms': elapsed / num_paths * 1000,
            'speedup': speedup if 'monte_carlo_serial' in self.results else None
        }
        
        return self.results['monte_carlo_parallel']
    
    def profile_strategy_generation(self, num_generations: int = 50) -> Dict:
        """Profile strategy generation performance"""
        print(f"\n{'='*60}")
        print(f"📊 Profiling Strategy Generation ({num_generations} generations)")
        print(f"{'='*60}")
        
        # Create generator
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
        
        # Timed runs
        times = []
        for _ in range(num_generations):
            start = time.perf_counter()
            strategies = generator.generate(target, constraints, state)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        # Analyze results
        avg_time = np.mean(times)
        p50_time = np.percentile(times, 50)
        p95_time = np.percentile(times, 95)
        
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  P50: {p50_time:.2f}ms")
        print(f"  P95: {p95_time:.2f}ms")
        
        self.results['strategy_generation'] = {
            'num_generations': num_generations,
            'avg_time_ms': avg_time,
            'p50_time_ms': p50_time,
            'p95_time_ms': p95_time
        }
        
        return self.results['strategy_generation']
    
    def _create_test_positions(self, num_positions: int) -> List[Position]:
        """Create test positions for profiling"""
        positions = []
        base_date = datetime.now().date()
        
        for i in range(num_positions):
            # Vary parameters
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
    
    def generate_report(self) -> str:
        """Generate performance report"""
        report = []
        report.append("\n" + "="*60)
        report.append("📊 PERFORMANCE PROFILING REPORT")
        report.append("="*60)
        
        for component, metrics in self.results.items():
            report.append(f"\n{component.upper().replace('_', ' ')}:")
            for key, value in metrics.items():
                if isinstance(value, float):
                    report.append(f"  {key}: {value:.2f}")
                else:
                    report.append(f"  {key}: {value}")
        
        report.append("\n" + "="*60)
        report.append("SUMMARY:")
        
        # Check if targets are met
        if 'greeks_computation' in self.results:
            if self.results['greeks_computation']['passes']:
                report.append("  ✅ Greeks computation: PASS")
            else:
                report.append("  ❌ Greeks computation: FAIL")
        
        if 'state_updates' in self.results:
            if self.results['state_updates']['passes']:
                report.append("  ✅ State updates: PASS")
            else:
                report.append("  ❌ State updates: FAIL")
        
        if 'monte_carlo_parallel' in self.results:
            speedup = self.results['monte_carlo_parallel'].get('speedup')
            if speedup and speedup > 2.0:
                report.append(f"  ✅ Monte Carlo parallelization: {speedup:.2f}x speedup")
            else:
                report.append(f"  ⚠️  Monte Carlo parallelization: {speedup:.2f}x speedup (target >2x)")
        
        report.append("="*60)
        
        return "\n".join(report)


def main():
    """Run performance profiling"""
    print("🚀 Starting Performance Profiling")
    print("="*60)
    
    profiler = PerformanceProfiler()
    
    # Profile Greeks computation
    profiler.profile_greeks_computation(num_positions=100)
    
    # Profile state updates
    profiler.profile_state_updates(num_updates=100)
    
    # Profile Monte Carlo (serial)
    profiler.profile_monte_carlo_serial(num_paths=10000, horizon_days=30)
    
    # Profile Monte Carlo (parallel)
    profiler.profile_monte_carlo_parallel(num_paths=10000, horizon_days=30)
    
    # Profile strategy generation
    profiler.profile_strategy_generation(num_generations=50)
    
    # Generate report
    report = profiler.generate_report()
    print(report)
    
    # Save report
    with open('reports/performance_profile.txt', 'w') as f:
        f.write(report)
    
    print("\n✅ Performance profiling complete!")
    print(f"📄 Report saved to: reports/performance_profile.txt")


if __name__ == "__main__":
    main()
