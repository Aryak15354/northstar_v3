#!/usr/bin/env python3
"""
Quick Performance Profiling for Critical Paths

Profiles:
- Greeks computation (target <50ms)
- State update propagation (target <100ms)
"""

import time
import numpy as np
from datetime import datetime, date, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.volatility.greeks_aggregator import GreeksAggregator, Position
from src.volatility.state_engine import VolatilityStateEngine, PortfolioGreeks as StatePortfolioGreeks


def create_test_positions(num_positions: int):
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


def profile_greeks(num_positions=100, num_runs=100):
    """Profile Greeks computation"""
    print(f"\n{'='*60}")
    print(f"📊 Profiling Greeks Computation ({num_positions} positions)")
    print(f"{'='*60}")
    
    positions = create_test_positions(num_positions)
    aggregator = GreeksAggregator()
    
    # Warm-up
    _ = aggregator.compute_portfolio_greeks(positions)
    
    # Timed runs
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        greeks = aggregator.compute_portfolio_greeks(positions)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
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
        status = "PASS"
    else:
        print(f"  ❌ FAIL - P95 exceeds target by {p95_time - 50:.2f}ms")
        status = "FAIL"
    
    return {
        'avg_time_ms': avg_time,
        'p50_time_ms': p50_time,
        'p95_time_ms': p95_time,
        'p99_time_ms': p99_time,
        'target_ms': 50,
        'status': status
    }


def profile_state_updates(num_updates=20):
    """Profile state update propagation"""
    print(f"\n{'='*60}")
    print(f"📊 Profiling State Update Propagation ({num_updates} updates)")
    print(f"{'='*60}")
    
    engine = VolatilityStateEngine(persistence_dir="data/test_profile_quick")
    
    # Warm-up
    test_greeks = StatePortfolioGreeks(delta=100.0, gamma=5.0, vega=200.0)
    engine.update_portfolio_greeks(test_greeks)
    
    # Timed runs
    times = []
    for i in range(num_updates):
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
        
        if i % 5 == 0:
            print(f"  Update {i+1}/{num_updates}: {elapsed:.2f}ms")
    
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
        status = "PASS"
    else:
        print(f"  ❌ FAIL - P95 exceeds target by {p95_time - 100:.2f}ms")
        status = "FAIL"
    
    return {
        'avg_time_ms': avg_time,
        'p50_time_ms': p50_time,
        'p95_time_ms': p95_time,
        'p99_time_ms': p99_time,
        'target_ms': 100,
        'status': status
    }


def main():
    print("🚀 Quick Performance Profiling")
    print("="*60)
    
    # Profile Greeks
    greeks_results = profile_greeks(num_positions=100, num_runs=100)
    
    # Profile State Updates
    state_results = profile_state_updates(num_updates=20)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Greeks Computation: {greeks_results['status']}")
    print(f"  P95: {greeks_results['p95_time_ms']:.2f}ms (target <50ms)")
    print(f"State Updates: {state_results['status']}")
    print(f"  P95: {state_results['p95_time_ms']:.2f}ms (target <100ms)")
    print(f"{'='*60}")
    
    # Save results
    with open('reports/quick_profile.txt', 'w') as f:
        f.write("PERFORMANCE PROFILING RESULTS\n")
        f.write("="*60 + "\n\n")
        f.write(f"Greeks Computation: {greeks_results['status']}\n")
        f.write(f"  Average: {greeks_results['avg_time_ms']:.2f}ms\n")
        f.write(f"  P50: {greeks_results['p50_time_ms']:.2f}ms\n")
        f.write(f"  P95: {greeks_results['p95_time_ms']:.2f}ms\n")
        f.write(f"  P99: {greeks_results['p99_time_ms']:.2f}ms\n")
        f.write(f"  Target: <50ms\n\n")
        f.write(f"State Updates: {state_results['status']}\n")
        f.write(f"  Average: {state_results['avg_time_ms']:.2f}ms\n")
        f.write(f"  P50: {state_results['p50_time_ms']:.2f}ms\n")
        f.write(f"  P95: {state_results['p95_time_ms']:.2f}ms\n")
        f.write(f"  P99: {state_results['p99_time_ms']:.2f}ms\n")
        f.write(f"  Target: <100ms\n")
    
    print("\n✅ Profiling complete! Results saved to reports/quick_profile.txt")


if __name__ == "__main__":
    main()
