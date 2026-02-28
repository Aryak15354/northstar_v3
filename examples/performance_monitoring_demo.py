"""
Performance Monitoring Demo

Demonstrates the performance monitoring and attribution capabilities
of the Unified Volatility Engine.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime, date, timedelta
from src.volatility.performance_monitor import PerformanceMonitor
from src.volatility.greeks_aggregator import (
    GreeksAggregator,
    PortfolioGreeks,
    Position
)


def main():
    print("=" * 60)
    print("Performance Monitoring Demo")
    print("=" * 60)
    
    # Initialize monitor
    monitor = PerformanceMonitor()
    aggregator = GreeksAggregator()
    
    # Create sample positions
    positions = [
        Position(
            position_id="SPY_CALL_1",
            underlying="SPY",
            option_type="call",
            strike=450.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        ),
        Position(
            position_id="SPY_PUT_1",
            underlying="SPY",
            option_type="put",
            strike=450.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
    ]
    
    # Compute initial Greeks
    initial_greeks = aggregator.compute_portfolio_greeks(positions)
    
    print("\n1. Initial Portfolio Greeks")
    print("-" * 60)
    print(f"Delta: {initial_greeks.delta:.2f}")
    print(f"Gamma: {initial_greeks.gamma:.4f}")
    print(f"Vega: {initial_greeks.vega:.2f}")
    print(f"Theta: {initial_greeks.theta:.2f}")
    
    # Simulate market move
    print("\n2. Greeks P&L Decomposition")
    print("-" * 60)
    
    spot_change = 5.0  # $5 move up
    vol_change = 0.02  # 2% vol increase
    time_elapsed = 1.0  # 1 day
    
    # Update positions with new market data
    for pos in positions:
        pos.spot_price += spot_change
        pos.implied_vol += vol_change
    
    current_greeks = aggregator.compute_portfolio_greeks(positions)
    
    # Compute P&L decomposition
    pnl = monitor.compute_greeks_pnl(
        current_greeks,
        initial_greeks,
        spot_change,
        vol_change,
        time_elapsed
    )
    
    print(f"Spot Change: ${spot_change:.2f}")
    print(f"Vol Change: {vol_change*100:.1f}%")
    print(f"Time Elapsed: {time_elapsed:.1f} days")
    print()
    print(f"Delta P&L: ${pnl.delta_pnl:.2f}")
    print(f"Gamma P&L: ${pnl.gamma_pnl:.2f}")
    print(f"Vega P&L: ${pnl.vega_pnl:.2f}")
    print(f"Theta P&L: ${pnl.theta_pnl:.2f}")
    print(f"Total P&L: ${pnl.total_pnl:.2f}")
    
    # Simulate performance tracking
    print("\n3. Performance Attribution")
    print("-" * 60)
    
    np.random.seed(42)
    portfolio_returns = np.random.normal(0.001, 0.02, 100)
    market_returns = np.random.normal(0.0008, 0.015, 100)
    
    attribution = monitor.compute_performance_attribution(
        portfolio_returns.tolist(),
        market_returns.tolist()
    )
    
    print(f"Alpha (Strategy Skill): {attribution.alpha*100:.4f}%")
    print(f"Beta (Market Exposure): {attribution.beta:.2f}")
    print(f"Total Return: {attribution.total_return*100:.2f}%")
    print(f"Sharpe Ratio: {attribution.sharpe_ratio:.2f}")
    print(f"Sortino Ratio: {attribution.sortino_ratio:.2f}")
    print(f"Max Drawdown: {attribution.max_drawdown*100:.2f}%")
    print(f"Win Rate: {attribution.win_rate*100:.1f}%")
    
    # Regime-conditional performance
    print("\n4. Regime-Conditional Performance")
    print("-" * 60)
    
    low_vol_returns = [0.01, 0.02, 0.015, 0.01, 0.02, 0.018]
    high_vol_returns = [-0.02, 0.03, -0.01, 0.04, -0.015, 0.02]
    
    low_vol_perf = monitor.track_regime_performance("low_vol", low_vol_returns)
    high_vol_perf = monitor.track_regime_performance("high_vol", high_vol_returns)
    
    print("Low Volatility Regime:")
    print(f"  Total Return: {low_vol_perf.total_return*100:.2f}%")
    print(f"  Sharpe Ratio: {low_vol_perf.sharpe_ratio:.2f}")
    print(f"  Win Rate: {low_vol_perf.win_rate*100:.1f}%")
    print(f"  Num Trades: {low_vol_perf.num_trades}")
    
    print("\nHigh Volatility Regime:")
    print(f"  Total Return: {high_vol_perf.total_return*100:.2f}%")
    print(f"  Sharpe Ratio: {high_vol_perf.sharpe_ratio:.2f}")
    print(f"  Win Rate: {high_vol_perf.win_rate*100:.1f}%")
    print(f"  Num Trades: {high_vol_perf.num_trades}")
    
    # Performance degradation detection
    print("\n5. Performance Degradation Detection")
    print("-" * 60)
    
    # Build historical returns
    for ret in np.random.normal(0.002, 0.01, 60):
        monitor.record_return(ret)
    
    # Recent returns are worse
    recent_returns = np.random.normal(-0.001, 0.015, 20).tolist()
    
    degradations = monitor.detect_performance_degradation(recent_returns)
    
    if degradations:
        print(f"Detected {len(degradations)} performance degradation(s):")
        for deg in degradations:
            print(f"\n  Metric: {deg.metric}")
            print(f"  Current: {deg.current_value:.4f}")
            print(f"  Historical Avg: {deg.historical_avg:.4f}")
            print(f"  Deviation: {deg.deviation_pct:.1f}%")
            print(f"  Severity: {deg.severity}")
            print(f"  Recommendation: {deg.recommendation}")
    else:
        print("No performance degradation detected")
    
    # Performance summary
    print("\n6. Overall Performance Summary")
    print("-" * 60)
    
    summary = monitor.get_performance_summary()
    
    print(f"Total Return: {summary['total_return']*100:.2f}%")
    print(f"Average Return: {summary['avg_return']*100:.4f}%")
    print(f"Volatility: {summary['volatility']*100:.2f}%")
    print(f"Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    print(f"Win Rate: {summary['win_rate']*100:.1f}%")
    print(f"Observations: {summary['num_observations']}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
