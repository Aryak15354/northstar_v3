"""
Production Grade Enhancements Demo

This script demonstrates how to use the Edge Half-Life Model and 
Liquidity-Aware Kill Switch in a production trading system.

Key Features Demonstrated:
- Edge persistence tracking and capital decay
- Liquidity risk assessment and position sizing
- Enhanced kill switch with liquidity awareness
- Integration with existing risk management
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import production grade components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.intelligence.edge_half_life import EdgeHalfLifeTracker, EdgeStateManager
from src.risk.liquidity_kill_switch import LiquidityRiskAssessor, LiquidityAwareKillSwitch, LiquidationUrgency
from src.integration.production_grade_enhancements import ProductionGradeRiskManager
from src.core.state import UnifiedState


def create_mock_unified_state():
    """Create a mock unified state for demonstration"""
    class MockUnifiedState:
        def __init__(self):
            self.state = {}
        
        def update_state(self, key, value, source):
            self.state[key] = value
            logger.debug(f"State updated: {key} by {source}")
        
        def get_state(self, key, default=None):
            return self.state.get(key, default)
    
    return MockUnifiedState()


def create_mock_risk_components():
    """Create mock risk coordinator and kill switch"""
    class MockRiskCoordinator:
        def validate_trade(self, trade, portfolio, metrics):
            from src.risk.risk_coordinator import RiskDecision
            return RiskDecision.APPROVED, []
        
        def get_risk_summary(self, portfolio):
            return {
                'status': 'HEALTHY',
                'risk_score': 20.0,
                'violations': []
            }
    
    class MockKillSwitch:
        def _check_trigger_condition(self, trigger_type, metrics, config):
            # Simulate trigger based on drawdown
            return metrics.get('current_drawdown', 0.0) > 0.10
        
        def _execute_emergency_liquidation(self, event):
            return [{'symbol': 'MOCK', 'status': 'EXECUTED'}]
    
    return MockRiskCoordinator(), MockKillSwitch()


def demonstrate_edge_half_life_tracking():
    """Demonstrate edge half-life tracking and capital decay"""
    print("\n" + "="*60)
    print("EDGE HALF-LIFE TRACKING DEMONSTRATION")
    print("="*60)
    
    # Initialize edge tracker
    edge_tracker = EdgeHalfLifeTracker(
        lookback_window=60,
        min_observations=15,
        decay_power=2.0,
        confidence_threshold=0.7
    )
    
    # Simulate strategy performance over time
    strategy_id = "momentum_strategy"
    base_timestamp = datetime(2024, 1, 1)
    
    print(f"\nSimulating performance for {strategy_id}...")
    
    # Phase 1: Strong performance (first 20 days)
    print("Phase 1: Strong performance period")
    for i in range(20):
        timestamp = base_timestamp + timedelta(days=i)
        returns = 0.08 - (i * 0.0005)  # Gradual decline from 8%
        
        edge_tracker.update_performance(
            strategy_id=strategy_id,
            timestamp=timestamp,
            returns=returns,
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.9,
            regime="bull"
        )
        
        if i == 19:  # Show metrics after phase 1
            metrics = edge_tracker.get_edge_metrics(strategy_id)
            if metrics:
                print(f"  Edge Health: {metrics.edge_health:.3f}")
                print(f"  Status: {metrics.status.value}")
                print(f"  Capital Multiplier: {edge_tracker.get_capital_multiplier(strategy_id):.3f}")
    
    # Phase 2: Declining performance (next 25 days)
    print("\nPhase 2: Declining performance period")
    for i in range(20, 45):
        timestamp = base_timestamp + timedelta(days=i)
        returns = 0.08 - (i * 0.001)  # Faster decline
        
        edge_tracker.update_performance(
            strategy_id=strategy_id,
            timestamp=timestamp,
            returns=returns,
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.8,
            regime="bull"
        )
    
    # Show final metrics
    metrics = edge_tracker.get_edge_metrics(strategy_id)
    if metrics:
        print(f"\nFinal Edge Metrics:")
        print(f"  Edge Health: {metrics.edge_health:.3f}")
        print(f"  Half-Life (days): {metrics.half_life_days:.1f}")
        print(f"  Status: {metrics.status.value}")
        print(f"  Capital Multiplier: {edge_tracker.get_capital_multiplier(strategy_id):.3f}")
        print(f"  Should Exit: {edge_tracker.should_exit_strategy(strategy_id)}")
    
    # Portfolio summary
    portfolio_summary = edge_tracker.get_portfolio_edge_summary()
    print(f"\nPortfolio Edge Summary:")
    print(f"  Portfolio Edge Score: {portfolio_summary.get('portfolio_edge_score', 0):.3f}")
    print(f"  Healthy Strategies: {portfolio_summary.get('healthy_strategies', 0)}")
    
    return edge_tracker


def demonstrate_liquidity_risk_assessment():
    """Demonstrate liquidity risk assessment"""
    print("\n" + "="*60)
    print("LIQUIDITY RISK ASSESSMENT DEMONSTRATION")
    print("="*60)
    
    # Initialize liquidity assessor
    liquidity_assessor = LiquidityRiskAssessor(
        impact_model_k=0.005,
        impact_model_beta=0.6,
        max_participation_rate=0.20
    )
    
    # Simulate market data for different liquidity profiles
    symbols = {
        "LIQUID_STOCK": {"volume": 1000000, "spread": 0.001},
        "MEDIUM_STOCK": {"volume": 200000, "spread": 0.005},
        "ILLIQUID_STOCK": {"volume": 50000, "spread": 0.02}
    }
    
    base_timestamp = datetime(2024, 1, 1)
    
    print("\nUpdating market data for 20 days...")
    
    # Add 20 days of market data
    for i in range(20):
        timestamp = base_timestamp + timedelta(days=i)
        
        for symbol, params in symbols.items():
            volume = params["volume"] * (0.8 + 0.4 * np.random.random())  # Add noise
            spread = params["spread"]
            
            liquidity_assessor.update_market_data(
                symbol=symbol,
                timestamp=timestamp,
                volume=volume,
                bid_price=100.0 - spread/2,
                ask_price=100.0 + spread/2,
                last_price=100.0
            )
    
    # Calculate position liquidity for different position sizes
    positions = {
        "LIQUID_STOCK": {"size": 50000, "value": 5000000},
        "MEDIUM_STOCK": {"size": 100000, "value": 10000000},
        "ILLIQUID_STOCK": {"size": 25000, "value": 2500000}
    }
    
    print("\nPosition Liquidity Analysis:")
    print("-" * 40)
    
    timestamp = base_timestamp + timedelta(days=19)
    
    for symbol, pos_data in positions.items():
        metrics = liquidity_assessor.calculate_position_liquidity(
            symbol=symbol,
            position_size=pos_data["size"],
            market_value=pos_data["value"],
            remaining_edge=0.03,  # 3% expected edge
            timestamp=timestamp
        )
        
        print(f"\n{symbol}:")
        print(f"  Position Size: {pos_data['size']:,}")
        print(f"  Participation Rate: {metrics.participation_rate:.1%}")
        print(f"  Impact Cost: {metrics.impact_cost:.2%}")
        print(f"  Exit Risk: {metrics.exit_risk:.2f}")
        print(f"  Liquidity Status: {metrics.liquidity_status.value}")
        print(f"  Days to Liquidate: {metrics.days_to_liquidate:.1f}")
    
    # Portfolio liquidity state
    portfolio_positions = {
        symbol: {"market_value": pos_data["value"], "position_size": pos_data["size"]}
        for symbol, pos_data in positions.items()
    }
    
    portfolio_state = liquidity_assessor.calculate_portfolio_liquidity_state(
        portfolio_positions, timestamp
    )
    
    print(f"\nPortfolio Liquidity State:")
    print(f"  Total Positions: {portfolio_state.total_positions}")
    print(f"  Normal Positions: {portfolio_state.normal_positions}")
    print(f"  Dangerous Positions: {portfolio_state.dangerous_positions}")
    print(f"  Frozen Positions: {portfolio_state.frozen_positions}")
    print(f"  Portfolio Liquidity Score: {portfolio_state.portfolio_liquidity_score:.2f}")
    print(f"  Systemic Risk Level: {portfolio_state.systemic_risk_level:.2f}")
    print(f"  Max Safe Liquidation %: {portfolio_state.max_safe_liquidation_pct:.1%}")
    
    return liquidity_assessor


def demonstrate_enhanced_kill_switch():
    """Demonstrate liquidity-aware kill switch"""
    print("\n" + "="*60)
    print("ENHANCED KILL SWITCH DEMONSTRATION")
    print("="*60)
    
    # Create mock base kill switch
    class MockBaseKillSwitch:
        def __init__(self):
            self.triggers = {}
        
        def _check_trigger_condition(self, trigger_type, metrics, config):
            return metrics.get('current_drawdown', 0.0) > 0.10
    
    # Initialize components
    liquidity_assessor = LiquidityRiskAssessor()
    base_kill_switch = MockBaseKillSwitch()
    
    enhanced_kill_switch = LiquidityAwareKillSwitch(
        base_kill_switch=base_kill_switch,
        liquidity_assessor=liquidity_assessor,
        max_acceptable_exit_risk=1.0
    )
    
    # Test scenarios
    scenarios = [
        {
            "name": "Normal Market Conditions",
            "drawdown": 0.12,  # Above kill switch threshold
            "positions": {
                "LIQUID_1": {"market_value": 1000000, "position_size": 10000}
            },
            "liquidity_risk": 0.3  # Low systemic risk
        },
        {
            "name": "Liquidity Crisis",
            "drawdown": 0.12,  # Above kill switch threshold
            "positions": {
                "ILLIQUID_1": {"market_value": 5000000, "position_size": 100000},
                "ILLIQUID_2": {"market_value": 3000000, "position_size": 75000}
            },
            "liquidity_risk": 0.9  # High systemic risk
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print("-" * 30)
        
        # Mock portfolio liquidity state
        from src.risk.liquidity_kill_switch import PortfolioLiquidityState
        
        portfolio_state = PortfolioLiquidityState(
            timestamp=datetime.now(),
            total_positions=len(scenario['positions']),
            normal_positions=1 if scenario['liquidity_risk'] < 0.5 else 0,
            dangerous_positions=0 if scenario['liquidity_risk'] < 0.5 else 1,
            frozen_positions=0 if scenario['liquidity_risk'] < 0.5 else len(scenario['positions']) - 1,
            portfolio_liquidity_score=1.0 - scenario['liquidity_risk'],
            systemic_risk_level=scenario['liquidity_risk'],
            max_safe_liquidation_pct=1.0 - scenario['liquidity_risk']
        )
        
        # Mock the assessor's calculate_portfolio_liquidity_state method
        liquidity_assessor.calculate_portfolio_liquidity_state = lambda pos, ts: portfolio_state
        
        # Test kill switch trigger
        from unittest.mock import Mock
        trigger_type = Mock(value='drawdown_limit')
        
        should_trigger, reason = enhanced_kill_switch.should_trigger_kill_switch(
            trigger_type=trigger_type,
            current_metrics={'current_drawdown': scenario['drawdown']},
            positions=scenario['positions']
        )
        
        print(f"  Drawdown: {scenario['drawdown']:.1%}")
        print(f"  Systemic Risk: {scenario['liquidity_risk']:.1%}")
        print(f"  Should Trigger Kill Switch: {should_trigger}")
        print(f"  Reason: {reason}")
        
        if should_trigger:
            # Test liquidation execution
            result = enhanced_kill_switch.execute_liquidity_aware_liquidation(
                scenario['positions'], 
                LiquidationUrgency.HIGH if scenario['liquidity_risk'] < 0.7 else LiquidationUrgency.EMERGENCY
            )
            
            print(f"  Liquidation Strategy: {result['strategy_type']}")
            print(f"  Execution Success: {result['success']}")
            if 'total_market_impact' in result:
                print(f"  Market Impact: {result['total_market_impact']:.2%}")


def demonstrate_production_integration():
    """Demonstrate full production integration"""
    print("\n" + "="*60)
    print("PRODUCTION INTEGRATION DEMONSTRATION")
    print("="*60)
    
    # Initialize components
    unified_state = create_mock_unified_state()
    risk_coordinator, kill_switch = create_mock_risk_components()
    
    # Create production grade risk manager
    production_manager = ProductionGradeRiskManager(
        unified_state=unified_state,
        base_risk_coordinator=risk_coordinator,
        base_kill_switch=kill_switch
    )
    
    print("\nProduction Grade Risk Manager initialized")
    print(f"Edge Integration: {production_manager.edge_integration_enabled}")
    print(f"Liquidity Integration: {production_manager.liquidity_integration_enabled}")
    
    # Simulate daily operations
    base_timestamp = datetime(2024, 1, 1, 9, 30)
    
    # 1. Update market data
    print("\n1. Updating market liquidity data...")
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA"]
    
    for i, symbol in enumerate(symbols):
        production_manager.update_market_liquidity(
            symbol=symbol,
            timestamp=base_timestamp + timedelta(minutes=i),
            volume=1000000 - (i * 100000),  # Decreasing liquidity
            bid_price=100.0 - 0.05,
            ask_price=100.0 + 0.05,
            last_price=100.0
        )
    
    # 2. Update strategy performance
    print("2. Updating strategy performance...")
    strategies = ["momentum", "mean_reversion", "pairs_trading", "arbitrage"]
    
    for i, strategy in enumerate(strategies):
        production_manager.update_strategy_performance(
            strategy_id=strategy,
            timestamp=base_timestamp + timedelta(minutes=30 + i),
            returns=0.06 - (i * 0.01),  # Decreasing performance
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.9 - (i * 0.05),
            regime="bull"
        )
    
    # 3. Test enhanced capital allocation
    print("3. Testing enhanced capital allocation...")
    
    proposed_allocations = {
        "momentum": 0.3,
        "mean_reversion": 0.3,
        "pairs_trading": 0.2,
        "arbitrage": 0.2
    }
    
    strategy_edges = {
        "momentum": 0.05,
        "mean_reversion": 0.04,
        "pairs_trading": 0.03,
        "arbitrage": 0.02
    }
    
    enhanced_allocations = production_manager.get_enhanced_capital_allocation(
        proposed_allocations, strategy_edges
    )
    
    print("\nCapital Allocation Results:")
    print("Strategy          Proposed    Enhanced    Change")
    print("-" * 50)
    
    for strategy in proposed_allocations:
        proposed = proposed_allocations[strategy]
        enhanced = enhanced_allocations.get(strategy, 0.0)
        change = enhanced - proposed
        
        print(f"{strategy:<15} {proposed:>8.1%} {enhanced:>10.1%} {change:>+8.1%}")
    
    if 'CASH' in enhanced_allocations:
        print(f"{'CASH':<15} {'0.0%':>8} {enhanced_allocations['CASH']:>10.1%} {enhanced_allocations['CASH']:>+8.1%}")
    
    # 4. Get production risk summary
    print("\n4. Production risk summary...")
    
    summary = production_manager.get_production_risk_summary()
    
    print(f"\nRisk Summary:")
    print(f"  Overall Status: {summary['overall_status']}")
    print(f"  Base Risk Status: {summary['base_risk']['status']}")
    print(f"  Base Risk Score: {summary['base_risk']['risk_score']:.1f}")
    
    if summary['edge_health']['enabled']:
        print(f"  Portfolio Edge Score: {summary['edge_health']['portfolio_edge_score']:.3f}")
        print(f"  Healthy Strategies: {summary['edge_health']['healthy_strategies']}/{summary['edge_health']['total_strategies']}")
    
    if summary['liquidity_risk']['enabled']:
        print(f"  Portfolio Liquidity Score: {summary['liquidity_risk']['portfolio_liquidity_score']:.3f}")
        print(f"  Systemic Risk Level: {summary['liquidity_risk']['systemic_risk_level']:.3f}")
    
    # 5. Integration status
    print("\n5. Integration status...")
    
    status = production_manager.get_integration_status()
    print(f"  Edge Strategies Tracked: {status['edge_strategies_tracked']}")
    print(f"  Liquidity Symbols Tracked: {status['liquidity_symbols_tracked']}")
    
    return production_manager


def main():
    """Main demonstration function"""
    print("NORTHSTAR V3 - PRODUCTION GRADE ENHANCEMENTS DEMO")
    print("=" * 60)
    print("This demo shows how Edge Half-Life and Liquidity Kill Switch")
    print("transform your system from impressive to capital-efficient.")
    
    try:
        # Run demonstrations
        edge_tracker = demonstrate_edge_half_life_tracking()
        liquidity_assessor = demonstrate_liquidity_risk_assessment()
        demonstrate_enhanced_kill_switch()
        production_manager = demonstrate_production_integration()
        
        print("\n" + "="*60)
        print("DEMO COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Takeaways:")
        print("1. Edge Half-Life prevents capital allocation to decaying strategies")
        print("2. Liquidity assessment prevents forced liquidation at bad prices")
        print("3. Enhanced kill switch considers exit costs vs remaining edge")
        print("4. Production integration provides unified risk management")
        print("\nYour system now knows when NOT to trade - where real money is made.")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()