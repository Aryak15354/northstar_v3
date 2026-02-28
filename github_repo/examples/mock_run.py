"""
Mock System Run - Demonstration of Northstar V3 Architecture

This script demonstrates the core system components working together
with sanitized data and mock implementations.
"""

import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.state import UnifiedState, PortfolioStateManager, RiskStateManager
from risk.risk_coordinator import (
    RiskCoordinator, RiskLimit, RiskLevel, Trade, Position, Portfolio
)
from risk.kill_switch import (
    KillSwitch, KillSwitchTrigger, MockLiquidationEngine,
    EmailNotification, SMSNotification
)
from validation.performance_tracker import (
    PerformanceTracker, Return, PerformancePeriod
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_portfolio() -> Portfolio:
    """Create mock portfolio for demonstration"""
    positions = [
        Position(
            symbol="MOCK_TECH",
            quantity=1000,
            market_value=150000,
            unrealized_pnl=5000,
            sector="Technology",
            country="US",
            currency="USD"
        ),
        Position(
            symbol="MOCK_FINANCE",
            quantity=800,
            market_value=120000,
            unrealized_pnl=-2000,
            sector="Finance",
            country="US",
            currency="USD"
        ),
        Position(
            symbol="MOCK_HEALTHCARE",
            quantity=600,
            market_value=90000,
            unrealized_pnl=3000,
            sector="Healthcare",
            country="US",
            currency="USD"
        )
    ]
    
    return Portfolio(
        positions=positions,
        cash=40000,
        total_value=400000,
        timestamp=datetime.now()
    )


def create_risk_limits() -> List[RiskLimit]:
    """Create mock risk limits"""
    return [
        RiskLimit(
            name="max_position_size",
            level=RiskLevel.POSITION,
            limit_type="percentage",
            threshold=0.10,  # 10% max position size
            warning_threshold=0.08
        ),
        RiskLimit(
            name="max_sector_concentration",
            level=RiskLevel.POSITION,
            limit_type="percentage",
            threshold=0.30,  # 30% max sector concentration
            warning_threshold=0.25
        ),
        RiskLimit(
            name="max_portfolio_var",
            level=RiskLevel.PORTFOLIO,
            limit_type="absolute",
            threshold=20000,  # $20k daily VaR limit
            warning_threshold=15000
        ),
        RiskLimit(
            name="max_leverage",
            level=RiskLevel.PORTFOLIO,
            limit_type="ratio",
            threshold=2.0,  # 2x max leverage
            warning_threshold=1.8
        ),
        RiskLimit(
            name="max_drawdown",
            level=RiskLevel.SYSTEM,
            limit_type="percentage",
            threshold=0.15,  # 15% max drawdown
            warning_threshold=0.12
        )
    ]


def demonstrate_unified_state():
    """Demonstrate unified state management"""
    logger.info("=== Demonstrating Unified State Management ===")
    
    # Initialize unified state
    current_time = datetime.now()
    unified_state = UnifiedState(current_time)
    
    # Initialize state managers
    portfolio_manager = PortfolioStateManager(unified_state)
    risk_manager = RiskStateManager(unified_state)
    
    portfolio_manager.initialize()
    risk_manager.initialize()
    
    # Update some state
    unified_state.update_state('market_open', True, 'market_data')
    unified_state.update_state('last_price_update', current_time, 'market_data')
    
    # Create snapshot
    snapshot = unified_state.create_snapshot()
    logger.info(f"Created snapshot at {snapshot.timestamp}")
    
    # Advance time and update more state
    new_time = current_time + timedelta(minutes=5)
    unified_state.advance_time(new_time)
    unified_state.update_state('portfolio_value', 400000, 'portfolio_manager')
    
    # Show audit trail
    audit_trail = unified_state.get_audit_trail()
    logger.info(f"Audit trail contains {len(audit_trail)} records")
    
    return unified_state


def demonstrate_risk_management():
    """Demonstrate risk management system"""
    logger.info("=== Demonstrating Risk Management ===")
    
    # Create risk coordinator
    risk_limits = create_risk_limits()
    risk_coordinator = RiskCoordinator(risk_limits)
    
    # Create mock portfolio and trade
    portfolio = create_mock_portfolio()
    trade = Trade(
        symbol="MOCK_TECH",
        quantity=500,  # Buy 500 more shares
        price=150.0,
        side="buy",
        trade_type="market",
        timestamp=datetime.now(),
        metadata={"sector": "Technology"}
    )
    
    # Calculate risk metrics
    risk_metrics = risk_coordinator.calculate_risk_metrics(portfolio)
    logger.info(f"Portfolio gross exposure: {risk_metrics.gross_exposure:.2%}")
    logger.info(f"Portfolio leverage: {risk_metrics.leverage:.2f}")
    
    # Validate trade
    decision, violations = risk_coordinator.validate_trade(trade, portfolio, risk_metrics)
    logger.info(f"Trade validation result: {decision.value}")
    
    if violations:
        logger.warning(f"Found {len(violations)} risk violations:")
        for violation in violations:
            logger.warning(f"  - {violation.description}")
    
    # Get risk summary
    risk_summary = risk_coordinator.get_risk_summary(portfolio)
    logger.info(f"Overall risk status: {risk_summary['status']}")
    logger.info(f"Risk score: {risk_summary['risk_score']:.1f}/100")
    
    return risk_coordinator, portfolio


def demonstrate_kill_switch():
    """Demonstrate kill switch system"""
    logger.info("=== Demonstrating Kill Switch System ===")
    
    # Create kill switch components
    liquidation_engine = MockLiquidationEngine()
    notification_channels = [
        EmailNotification(),
        SMSNotification()
    ]
    stakeholder_contacts = {
        'risk_managers': ['risk@example.com', '+1234567890'],
        'portfolio_managers': ['pm@example.com', '+0987654321'],
        'executives': ['ceo@example.com', '+1122334455']
    }
    
    # Initialize kill switch
    kill_switch = KillSwitch(
        liquidation_engine=liquidation_engine,
        notification_channels=notification_channels,
        stakeholder_contacts=stakeholder_contacts
    )
    
    # Check status
    status = kill_switch.get_status()
    logger.info(f"Kill switch status: {status['status']}")
    
    # Simulate manual trigger
    event_id = kill_switch.trigger_kill_switch(
        trigger_type=KillSwitchTrigger.MANUAL_OVERRIDE,
        reason="Demonstration of kill switch functionality",
        triggered_by="demo_user",
        current_metrics={'portfolio_var': 25000, 'leverage': 2.5}
    )
    
    logger.info(f"Kill switch triggered with event ID: {event_id}")
    
    # Check final status
    final_status = kill_switch.get_status()
    logger.info(f"Final kill switch status: {final_status['status']}")
    
    # Reset for next demo
    kill_switch.reset_kill_switch("demo_user")
    
    return kill_switch


def demonstrate_performance_tracking():
    """Demonstrate performance tracking"""
    logger.info("=== Demonstrating Performance Tracking ===")
    
    # Initialize performance tracker
    current_time = datetime.now()
    performance_tracker = PerformanceTracker(current_time)
    
    # Add some mock performance data
    base_date = date.today() - timedelta(days=30)
    
    for i in range(30):
        return_date = base_date + timedelta(days=i)
        
        # Generate mock returns (random walk)
        portfolio_return = 0.001 * (i % 5 - 2)  # Simple pattern
        benchmark_return = 0.0008 * (i % 3 - 1)
        
        return_data = Return(
            date=return_date,
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            active_return=portfolio_return - benchmark_return,
            gross_return=portfolio_return,
            net_return=portfolio_return * 0.99  # Assume 1% fee impact
        )
        
        performance_tracker.record_performance(return_data)
    
    # Calculate performance summary
    summary = performance_tracker.get_performance_summary(PerformancePeriod.MONTHLY)
    
    if summary['status'] == 'SUCCESS':
        perf_summary = summary['summary']
        logger.info(f"Monthly total return: {perf_summary.total_return:.2%}")
        logger.info(f"Monthly active return: {perf_summary.active_return:.2%}")
        logger.info(f"Sharpe ratio: {perf_summary.risk_metrics.sharpe_ratio:.2f}")
        logger.info(f"Max drawdown: {perf_summary.risk_metrics.max_drawdown:.2%}")
    else:
        logger.error(f"Performance calculation failed: {summary['error']}")
    
    return performance_tracker


def demonstrate_integrated_system():
    """Demonstrate integrated system operation"""
    logger.info("=== Demonstrating Integrated System ===")
    
    # Initialize all components
    unified_state = demonstrate_unified_state()
    risk_coordinator, portfolio = demonstrate_risk_management()
    kill_switch = demonstrate_kill_switch()
    performance_tracker = demonstrate_performance_tracking()
    
    logger.info("All system components initialized and demonstrated successfully")
    
    # Simulate a trading day workflow
    logger.info("Simulating trading day workflow...")
    
    # 1. Market open - update state
    unified_state.update_state('market_status', 'OPEN', 'market_data')
    
    # 2. Receive new trade signal
    new_trade = Trade(
        symbol="MOCK_ENERGY",
        quantity=300,
        price=80.0,
        side="buy",
        trade_type="limit",
        timestamp=datetime.now(),
        metadata={"sector": "Energy"}
    )
    
    # 3. Risk validation
    risk_metrics = risk_coordinator.calculate_risk_metrics(portfolio)
    decision, violations = risk_coordinator.validate_trade(new_trade, portfolio, risk_metrics)
    
    if decision.value == "approved":
        logger.info("Trade approved by risk system")
        # Would execute trade here
        unified_state.update_state('last_trade', new_trade.symbol, 'execution_system')
    else:
        logger.warning(f"Trade rejected: {decision.value}")
    
    # 4. Update performance
    daily_return = Return(
        date=date.today(),
        portfolio_return=0.0025,
        benchmark_return=0.0020,
        active_return=0.0005,
        gross_return=0.0025,
        net_return=0.0024
    )
    performance_tracker.record_performance(daily_return)
    
    # 5. End of day summary
    logger.info("End of day system status:")
    logger.info(f"  - Unified state events: {len(unified_state.get_audit_trail())}")
    logger.info(f"  - Risk status: {risk_coordinator.get_risk_summary(portfolio)['status']}")
    logger.info(f"  - Kill switch status: {kill_switch.get_status()['status']}")
    logger.info(f"  - Performance records: {len(performance_tracker.performance_history)}")


def main():
    """Main demonstration function"""
    logger.info("Starting Northstar V3 System Demonstration")
    logger.info("=" * 60)
    
    try:
        # Run individual component demonstrations
        demonstrate_unified_state()
        print()
        
        demonstrate_risk_management()
        print()
        
        demonstrate_kill_switch()
        print()
        
        demonstrate_performance_tracking()
        print()
        
        # Run integrated demonstration
        demonstrate_integrated_system()
        
        logger.info("=" * 60)
        logger.info("Northstar V3 System Demonstration Completed Successfully")
        
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    main()