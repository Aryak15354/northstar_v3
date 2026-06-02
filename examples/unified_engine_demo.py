"""
Unified Volatility Engine Demo

Demonstrates how to use the UnifiedVolatilityEngine to run a complete trading cycle.
"""

from datetime import datetime
import numpy as np
from src.volatility.unified_engine import UnifiedVolatilityEngine
from src.volatility.state_engine import VolatilityStateEngine
from src.volatility.strategy_generator import StrategyGenerator, TargetGreeks
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.dispersion_module import DispersionModule
from src.volatility.gamma_scalper import GammaScalper
from src.volatility.volatility_capital_allocator import CapitalAllocator
from src.volatility.monte_carlo_engine import MonteCarloEngine
from src.volatility.regime_detector import RegimeDetector
from src.volatility.execution_interface import ExecutionInterface
from src.volatility.performance_monitor import PerformanceMonitor


def create_unified_engine():
    """Create and initialize the unified volatility engine"""
    
    # Initialize all components
    state_engine = VolatilityStateEngine()
    strategy_generator = StrategyGenerator()
    greeks_aggregator = GreeksAggregator()
    risk_authority = UnifiedRiskAuthority()
    dispersion_module = DispersionModule()
    gamma_scalper = GammaScalper()
    capital_allocator = CapitalAllocator()
    monte_carlo_engine = MonteCarloEngine()
    regime_detector = RegimeDetector()
    execution_interface = ExecutionInterface()
    performance_monitor = PerformanceMonitor()
    
    # Create unified engine
    engine = UnifiedVolatilityEngine(
        state_engine=state_engine,
        strategy_generator=strategy_generator,
        greeks_aggregator=greeks_aggregator,
        risk_authority=risk_authority,
        dispersion_module=dispersion_module,
        gamma_scalper=gamma_scalper,
        capital_allocator=capital_allocator,
        monte_carlo_engine=monte_carlo_engine,
        regime_detector=regime_detector,
        execution_interface=execution_interface,
        performance_monitor=performance_monitor
    )
    
    return engine


def create_sample_market_data():
    """Create sample market data for demonstration"""
    return {
        "option_chain": {
            "SPY": [
                # Sample option data
                {"strike": 450, "expiry": "2024-03-15", "type": "call", "iv": 0.15},
                {"strike": 450, "expiry": "2024-03-15", "type": "put", "iv": 0.16},
            ]
        },
        "spot_prices": {
            "SPY": 450.0,
            "QQQ": 380.0,
            "IWM": 200.0
        },
        "returns": np.random.randn(100, 3) * 0.01  # 100 days, 3 assets
    }


def demo_basic_trading_cycle():
    """Demonstrate a basic trading cycle"""
    print("=" * 60)
    print("Unified Volatility Engine - Basic Trading Cycle Demo")
    print("=" * 60)
    
    # Create engine
    print("\n1. Initializing unified volatility engine...")
    engine = create_unified_engine()
    
    # Create market data
    print("2. Creating sample market data...")
    market_data = create_sample_market_data()
    
    # Define target Greeks
    print("3. Defining target Greeks exposure...")
    target_greeks = TargetGreeks(
        delta=0.0,          # Delta-neutral
        gamma=20.0,         # Long gamma
        vega=100.0,         # Long vega
        theta=-10.0,        # Negative theta (cost of long options)
        delta_tolerance=0.1,
        gamma_tolerance=0.1,
        vega_tolerance=0.1,
        theta_tolerance=0.1
    )
    
    # Run trading cycle
    print("4. Running trading cycle...")
    result = engine.run_trading_cycle(market_data, target_greeks)
    
    # Display results
    print("\n" + "=" * 60)
    print("Trading Cycle Results")
    print("=" * 60)
    print(f"Timestamp: {result.timestamp}")
    print(f"Regime: {result.state.regime if result.state else 'N/A'}")
    print(f"Strategies Generated: {len(result.strategies_generated)}")
    print(f"Strategies Approved: {len(result.strategies_approved)}")
    print(f"Orders Submitted: {len(result.orders_submitted)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.portfolio_greeks:
        print("\nPortfolio Greeks:")
        print(f"  Delta: {result.portfolio_greeks.delta:.2f}")
        print(f"  Gamma: {result.portfolio_greeks.gamma:.2f}")
        print(f"  Vega: {result.portfolio_greeks.vega:.2f}")
        print(f"  Theta: {result.portfolio_greeks.theta:.2f}")
    
    if result.capital_allocation:
        print("\nCapital Allocation:")
        for strategy, capital in result.capital_allocation.items():
            print(f"  {strategy}: ${capital:,.2f}")
    
    if result.performance_metrics:
        print("\nPerformance Metrics:")
        for metric, value in result.performance_metrics.items():
            print(f"  {metric}: {value}")
    
    return engine, result


def demo_regime_change_handling():
    """Demonstrate regime change handling"""
    print("\n" + "=" * 60)
    print("Regime Change Handling Demo")
    print("=" * 60)
    
    engine = create_unified_engine()
    market_data = create_sample_market_data()
    
    # Run initial cycle
    print("\n1. Running initial trading cycle (low-vol regime)...")
    result1 = engine.run_trading_cycle(market_data)
    print(f"   Initial regime: {result1.state.regime if result1.state else 'N/A'}")
    
    # Simulate regime change
    print("\n2. Simulating regime change to crisis...")
    if result1.state:
        engine.handle_regime_change("low_vol", "crisis", result1.state)
        print("   Regime change handled - emergency protocols activated")
    
    return engine


def demo_event_driven_updates():
    """Demonstrate event-driven communication"""
    print("\n" + "=" * 60)
    print("Event-Driven Communication Demo")
    print("=" * 60)
    
    engine = create_unified_engine()
    
    # Register event listeners
    print("\n1. Registering event listeners...")
    
    from src.volatility.unified_engine import EventType
    
    def on_regime_change(event):
        print(f"   [EVENT] Regime changed: {event.data}")
    
    def on_risk_alert(event):
        print(f"   [ALERT] Risk alert: {event.data}")
    
    engine.register_event_listener(EventType.REGIME_CHANGE, on_regime_change)
    engine.register_event_listener(EventType.RISK_ALERT, on_risk_alert)
    
    print("   Event listeners registered")
    
    # Run cycle to trigger events
    print("\n2. Running trading cycle to trigger events...")
    market_data = create_sample_market_data()
    result = engine.run_trading_cycle(market_data)
    
    return engine


def demo_component_health_monitoring():
    """Demonstrate component health monitoring"""
    print("\n" + "=" * 60)
    print("Component Health Monitoring Demo")
    print("=" * 60)
    
    engine = create_unified_engine()
    
    # Get component health
    print("\n1. Checking component health...")
    health = engine.get_component_health()
    
    print("\nComponent Health Status:")
    for component, status in health.items():
        print(f"  {component}: {status['status']} "
              f"(errors: {status['recent_errors']})")
    
    # Get system status
    print("\n2. Getting overall system status...")
    status = engine.get_system_status()
    
    print("\nSystem Status:")
    print(f"  Running: {status['running']}")
    print(f"  Timestamp: {status['timestamp']}")
    
    return engine


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("UNIFIED VOLATILITY ENGINE DEMONSTRATION")
    print("=" * 60)
    
    try:
        # Demo 1: Basic trading cycle
        engine1, result1 = demo_basic_trading_cycle()
        
        # Demo 2: Regime change handling
        engine2 = demo_regime_change_handling()
        
        # Demo 3: Event-driven updates
        engine3 = demo_event_driven_updates()
        
        # Demo 4: Component health monitoring
        engine4 = demo_component_health_monitoring()
        
        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
