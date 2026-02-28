"""
Unified Volatility Engine - Main Orchestrator

Coordinates all volatility trading components:
- State management (VolatilityStateEngine)
- Strategy generation (StrategyGenerator)
- Greeks tracking (GreeksAggregator)
- Risk validation (RiskAuthority)
- Dispersion trading (DispersionModule)
- Gamma scalping (GammaScalper)
- Capital allocation (CapitalAllocator)
- Monte Carlo risk (MonteCarloEngine)
- Regime detection (RegimeDetector)
- Execution (ExecutionInterface)
- Performance monitoring (PerformanceMonitor)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import logging

from .state_engine import VolatilityStateEngine, VolatilityState
from .strategy_generator import StrategyGenerator, TargetGreeks
from .greeks_aggregator import GreeksAggregator, PortfolioGreeks
from .risk_authority import UnifiedRiskAuthority, TradeValidationResult
from .dispersion_module import DispersionModule
from .gamma_scalper import GammaScalper
from .capital_allocator import CapitalAllocator
from .monte_carlo_engine import MonteCarloEngine
from .regime_detector import RegimeDetector
from .execution_interface import ExecutionInterface, Order
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the system"""
    STATE_UPDATE = "state_update"
    REGIME_CHANGE = "regime_change"
    STRATEGY_GENERATED = "strategy_generated"
    STRATEGY_APPROVED = "strategy_approved"
    STRATEGY_REJECTED = "strategy_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_FAILED = "order_failed"
    GREEKS_VIOLATION = "greeks_violation"
    RISK_ALERT = "risk_alert"
    EMERGENCY_ACTION = "emergency_action"
    COMPONENT_ERROR = "component_error"


@dataclass
class SystemEvent:
    """Event in the unified engine"""
    event_type: EventType
    timestamp: datetime
    component: str
    data: Dict[str, Any]
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL


@dataclass
class ComponentError:
    """Error at component boundary"""
    component: str
    operation: str
    error: Exception
    timestamp: datetime
    recoverable: bool
    recovery_action: Optional[str] = None


@dataclass
class TradingCycleResult:
    """Result of a complete trading cycle"""
    timestamp: datetime
    state: VolatilityState
    strategies_generated: List[Any]
    strategies_approved: List[Any]
    orders_submitted: List[Order]
    portfolio_greeks: PortfolioGreeks
    capital_allocation: Dict[str, float]
    performance_metrics: Dict[str, float]
    errors: List[str]


class UnifiedVolatilityEngine:
    """
    Main orchestrator for the unified volatility trading system.
    
    Coordinates data flow:
    Market data → State → Regime → Strategy → Risk → Capital → Execution → Performance
    """
    
    def __init__(
        self,
        state_engine: VolatilityStateEngine,
        strategy_generator: StrategyGenerator,
        greeks_aggregator: GreeksAggregator,
        risk_authority: UnifiedRiskAuthority,
        dispersion_module: DispersionModule,
        gamma_scalper: GammaScalper,
        capital_allocator: CapitalAllocator,
        monte_carlo_engine: MonteCarloEngine,
        regime_detector: RegimeDetector,
        execution_interface: ExecutionInterface,
        performance_monitor: PerformanceMonitor
    ):
        self.state_engine = state_engine
        self.strategy_generator = strategy_generator
        self.greeks_aggregator = greeks_aggregator
        self.risk_authority = risk_authority
        self.dispersion_module = dispersion_module
        self.gamma_scalper = gamma_scalper
        self.capital_allocator = capital_allocator
        self.monte_carlo_engine = monte_carlo_engine
        self.regime_detector = regime_detector
        self.execution_interface = execution_interface
        self.performance_monitor = performance_monitor
        
        self._running = False
        self._feedback_history = []  # Track feedback loop data
        self._event_listeners: Dict[EventType, List[Callable]] = {}  # Event-driven updates
        self._error_history: List[ComponentError] = []  # Track component errors
        logger.info("UnifiedVolatilityEngine initialized")
    
    def run_trading_cycle(
        self,
        market_data: Dict[str, Any],
        target_greeks: Optional[TargetGreeks] = None
    ) -> TradingCycleResult:
        """
        Execute a complete trading cycle.
        
        Flow:
        1. Ingest market data → construct state
        2. Detect regime
        3. Generate strategies
        4. Validate with risk authority
        5. Allocate capital
        6. Execute approved trades
        7. Monitor performance
        
        Args:
            market_data: Raw market data (prices, option chains, etc.)
            target_greeks: Optional target exposure profile
            
        Returns:
            TradingCycleResult with complete cycle information
        """
        errors = []
        timestamp = datetime.now()
        
        try:
            # Step 1: Market data ingestion → state construction
            logger.info("Step 1: Constructing volatility state from market data")
            state = self._construct_state(market_data)
            
            # Step 2: Regime detection
            logger.info(f"Step 2: Detecting regime (current: {state.regime})")
            regime = self.regime_detector.detect_regime(state)
            state.regime = regime
            
            # Step 3: Strategy generation
            logger.info("Step 3: Generating strategies")
            strategies = self._generate_strategies(state, target_greeks)
            
            # Step 4: Risk validation
            logger.info(f"Step 4: Validating {len(strategies)} strategies")
            approved_strategies = self._validate_strategies(strategies, state)
            
            # Step 5: Capital allocation
            logger.info("Step 5: Allocating capital")
            allocation = self.capital_allocator.allocate_capital(
                state=state,
                strategies=approved_strategies
            )
            
            # Step 6: Execution
            logger.info(f"Step 6: Executing {len(approved_strategies)} strategies")
            orders = self._execute_strategies(approved_strategies, allocation, state)
            
            # Step 7: Greeks monitoring
            logger.info("Step 7: Computing portfolio Greeks")
            portfolio_greeks = self.greeks_aggregator.compute_portfolio_greeks(state)
            
            # Step 8: Performance attribution
            logger.info("Step 8: Updating performance metrics")
            performance = self.performance_monitor.update_performance(
                state=state,
                orders=orders,
                portfolio_greeks=portfolio_greeks
            )
            
            # Step 9: Feedback loop - update strategy generator with performance
            self._update_feedback_loop(
                state=state,
                strategies=approved_strategies,
                performance=performance,
                portfolio_greeks=portfolio_greeks
            )
            
            return TradingCycleResult(
                timestamp=timestamp,
                state=state,
                strategies_generated=strategies,
                strategies_approved=approved_strategies,
                orders_submitted=orders,
                portfolio_greeks=portfolio_greeks,
                capital_allocation=allocation,
                performance_metrics=performance,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Trading cycle failed: {e}", exc_info=True)
            errors.append(str(e))
            
            # Return partial result with error
            return TradingCycleResult(
                timestamp=timestamp,
                state=None,
                strategies_generated=[],
                strategies_approved=[],
                orders_submitted=[],
                portfolio_greeks=None,
                capital_allocation={},
                performance_metrics={},
                errors=errors
            )
    
    def _construct_state(self, market_data: Dict[str, Any]) -> VolatilityState:
        """Construct unified volatility state from market data"""
        # Update IV surface
        if 'option_chain' in market_data:
            _, error = self._safe_component_call(
                "state_engine",
                "update_iv_surface",
                self.state_engine.update_iv_surface,
                market_data['option_chain']
            )
            if error:
                logger.warning("IV surface update failed, using cached surface")
        
        # Update correlations
        if 'correlation_matrix' in market_data:
            _, error = self._safe_component_call(
                "state_engine",
                "update_correlations",
                self.state_engine.update_correlations,
                market_data['correlation_matrix'],
                market_data.get('implied_corr', 0.5),
                market_data.get('realized_corr', 0.5)
            )
            if error:
                logger.warning("Correlation update failed, using cached correlations")
        
        # Update volatility metrics (includes spot prices indirectly via VIX)
        if 'vix_level' in market_data or 'realized_vol' in market_data:
            _, error = self._safe_component_call(
                "state_engine",
                "update_volatility_metrics",
                self.state_engine.update_volatility_metrics,
                vix_level=market_data.get('vix_level'),
                realized_vol_20d=market_data.get('realized_vol'),
                vol_of_vol=market_data.get('vol_of_vol')
            )
            if error:
                logger.warning("Volatility metrics update failed, using cached values")
        
        # Get complete state
        state, error = self._safe_component_call(
            "state_engine",
            "get_state",
            self.state_engine.get_state
        )
        
        if error:
            raise RuntimeError("Failed to construct volatility state")
        
        # Emit state update event
        self._emit_event(SystemEvent(
            event_type=EventType.STATE_UPDATE,
            timestamp=datetime.now(),
            component="state_engine",
            data={"regime": state.regime},
            severity="INFO"
        ))
        
        return state
    
    def _generate_strategies(
        self,
        state: VolatilityState,
        target_greeks: Optional[TargetGreeks]
    ) -> List[Any]:
        """Generate strategies from multiple sources"""
        strategies = []
        
        try:
            # Generate from target Greeks if provided
            if target_greeks:
                greeks_strategies = self.strategy_generator.generate(
                    target_greeks=target_greeks,
                    state=state
                )
                strategies.extend(greeks_strategies)
            
            # Generate dispersion opportunities
            dispersion_trade = self.dispersion_module.analyze_dispersion_opportunity(state)
            if dispersion_trade:
                strategies.append(dispersion_trade)
            
            # Generate gamma scalping opportunities
            gamma_opportunities = self.gamma_scalper.identify_opportunities(state)
            strategies.extend(gamma_opportunities)
            
            logger.info(f"Generated {len(strategies)} total strategies")
            return strategies
            
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return []
    
    def _validate_strategies(
        self,
        strategies: List[Any],
        state: VolatilityState
    ) -> List[Any]:
        """Validate strategies with risk authority"""
        approved = []
        
        for strategy in strategies:
            try:
                validation = self.risk_authority.validate_trade(
                    trade=strategy,
                    state=state
                )
                
                if validation.approved:
                    approved.append(strategy)
                    logger.debug(f"Strategy approved: {strategy}")
                else:
                    logger.warning(f"Strategy rejected: {validation.reason}")
                    
            except Exception as e:
                logger.error(f"Validation failed for strategy: {e}")
        
        logger.info(f"Approved {len(approved)}/{len(strategies)} strategies")
        return approved
    
    def _execute_strategies(
        self,
        strategies: List[Any],
        allocation: Dict[str, float],
        state: VolatilityState
    ) -> List[Order]:
        """Execute approved strategies"""
        orders = []
        
        for strategy in strategies:
            try:
                # Convert strategy to orders
                strategy_orders = self._strategy_to_orders(strategy, allocation, state)
                
                # Submit orders
                for order in strategy_orders:
                    result = self.execution_interface.submit_order(order)
                    if result.success:
                        orders.append(order)
                        logger.debug(f"Order submitted: {order}")
                    else:
                        logger.warning(f"Order failed: {result.reason}")
                        
            except Exception as e:
                logger.error(f"Execution failed for strategy: {e}")
        
        logger.info(f"Submitted {len(orders)} orders")
        return orders
    
    def _strategy_to_orders(
        self,
        strategy: Any,
        allocation: Dict[str, float],
        state: VolatilityState
    ) -> List[Order]:
        """Convert strategy to executable orders"""
        # This is a simplified implementation
        # Real implementation would handle different strategy types
        orders = []
        
        # Get allocated capital for this strategy type
        strategy_type = getattr(strategy, 'type', 'unknown')
        capital = allocation.get(strategy_type, 0.0)
        
        if capital > 0:
            # Convert strategy to orders based on allocated capital
            # This would be strategy-specific logic
            pass
        
        return orders
    
    def handle_regime_change(self, old_regime: str, new_regime: str, state: VolatilityState):
        """Handle regime transitions"""
        logger.info(f"Regime change detected: {old_regime} → {new_regime}")
        
        # Emit regime change event
        self._emit_event(SystemEvent(
            event_type=EventType.REGIME_CHANGE,
            timestamp=datetime.now(),
            component="regime_detector",
            data={
                "old_regime": old_regime,
                "new_regime": new_regime
            },
            severity="WARNING" if new_regime == "crisis" else "INFO"
        ))
        
        try:
            # Recompute capital allocation for new regime
            allocation, error = self._safe_component_call(
                "capital_allocator",
                "allocate_capital",
                self.capital_allocator.allocate_capital,
                state=state,
                strategies=[]
            )
            
            if error:
                logger.error("Failed to recompute capital allocation")
                return
            
            # Check if emergency actions needed
            if new_regime == "crisis":
                logger.warning("Crisis regime detected - triggering emergency protocols")
                self._handle_crisis_regime(state)
            
            # Re-evaluate existing positions
            portfolio_greeks, error = self._safe_component_call(
                "greeks_aggregator",
                "compute_portfolio_greeks",
                self.greeks_aggregator.compute_portfolio_greeks,
                state
            )
            
            if error:
                logger.error("Failed to compute portfolio Greeks")
                return
            
            # Check if portfolio needs rebalancing
            if self._needs_rebalancing(portfolio_greeks, new_regime):
                logger.info("Portfolio rebalancing required")
                self._rebalance_portfolio(state, new_regime)
                
        except Exception as e:
            logger.error(f"Regime change handling failed: {e}")
    
    def _handle_crisis_regime(self, state: VolatilityState):
        """Emergency actions for crisis regime"""
        # Trigger risk authority emergency protocols
        emergency_action = self.risk_authority.emergency_action(
            state=state,
            trigger_type="REGIME_CRISIS"
        )
        
        if emergency_action:
            logger.critical(f"Emergency action: {emergency_action}")
            # Execute emergency action
            self._execute_emergency_action(emergency_action, state)
    
    def _needs_rebalancing(self, greeks: PortfolioGreeks, regime: str) -> bool:
        """Check if portfolio needs rebalancing for new regime"""
        # Simple heuristic - real implementation would be more sophisticated
        regime_limits = self.risk_authority.get_regime_limits(regime)
        
        if abs(greeks.delta) > regime_limits.max_delta * 0.8:
            return True
        if abs(greeks.vega) > regime_limits.max_vega * 0.8:
            return True
        
        return False
    
    def _rebalance_portfolio(self, state: VolatilityState, regime: str):
        """Rebalance portfolio for new regime"""
        logger.info(f"Rebalancing portfolio for {regime} regime")
        # Implementation would generate rebalancing trades
        pass
    
    def _execute_emergency_action(self, action: Any, state: VolatilityState):
        """Execute emergency risk action"""
        logger.critical(f"Executing emergency action: {action}")
        # Implementation would execute emergency trades/hedges
        pass
    
    def _update_feedback_loop(
        self,
        state: VolatilityState,
        strategies: List[Any],
        performance: Dict[str, float],
        portfolio_greeks: PortfolioGreeks
    ):
        """
        Update feedback loop: Greeks monitoring → performance attribution → strategy adjustment
        
        This creates a closed-loop system where:
        1. Portfolio Greeks are monitored in real-time
        2. Performance is attributed to Greeks contributions
        3. Strategy generator learns from performance
        4. Capital allocator adjusts based on results
        """
        feedback_data = {
            "timestamp": datetime.now(),
            "regime": state.regime,
            "portfolio_greeks": portfolio_greeks,
            "performance": performance,
            "strategies": strategies
        }
        
        self._feedback_history.append(feedback_data)
        
        # Check Greeks vs targets
        greeks_deviation = self._compute_greeks_deviation(portfolio_greeks, state)
        if greeks_deviation > 0.2:  # 20% deviation threshold
            logger.warning(f"Portfolio Greeks deviated {greeks_deviation:.1%} from targets")
            self._adjust_for_greeks_deviation(portfolio_greeks, state)
        
        # Update capital allocator with performance feedback
        self.capital_allocator.update_performance_history(
            regime=state.regime,
            strategies=strategies,
            performance=performance
        )
        
        # Update strategy generator with what worked
        self.strategy_generator.update_from_feedback(
            strategies=strategies,
            performance=performance,
            regime=state.regime
        )
        
        logger.debug("Feedback loop updated")
    
    def _compute_greeks_deviation(
        self,
        current_greeks: PortfolioGreeks,
        state: VolatilityState
    ) -> float:
        """Compute deviation of current Greeks from regime-appropriate targets"""
        # Get target Greeks for current regime
        target_greeks = self.risk_authority.get_target_greeks(state.regime)
        
        # Compute normalized deviation
        delta_dev = abs(current_greeks.delta - target_greeks.delta) / max(abs(target_greeks.delta), 1.0)
        vega_dev = abs(current_greeks.vega - target_greeks.vega) / max(abs(target_greeks.vega), 1.0)
        gamma_dev = abs(current_greeks.gamma - target_greeks.gamma) / max(abs(target_greeks.gamma), 1.0)
        
        # Average deviation
        return (delta_dev + vega_dev + gamma_dev) / 3.0
    
    def _adjust_for_greeks_deviation(
        self,
        current_greeks: PortfolioGreeks,
        state: VolatilityState
    ):
        """Generate adjustment trades to bring Greeks back to targets"""
        logger.info("Generating Greeks adjustment trades")
        
        target_greeks = self.risk_authority.get_target_greeks(state.regime)
        
        # Compute required adjustment
        adjustment = TargetGreeks(
            delta=target_greeks.delta - current_greeks.delta,
            gamma=target_greeks.gamma - current_greeks.gamma,
            vega=target_greeks.vega - current_greeks.vega,
            theta=target_greeks.theta - current_greeks.theta,
            delta_tolerance=0.1,
            gamma_tolerance=0.1,
            vega_tolerance=0.1,
            theta_tolerance=0.1
        )
        
        # Generate adjustment strategies
        adjustment_strategies = self.strategy_generator.generate(
            target_greeks=adjustment,
            state=state
        )
        
        # Validate and execute
        if adjustment_strategies:
            approved = self._validate_strategies(adjustment_strategies, state)
            if approved:
                allocation = {"adjustment": 1.0}  # Full allocation for adjustments
                self._execute_strategies(approved, allocation, state)
    
    def monitor_greeks_continuously(self, state: VolatilityState) -> Dict[str, Any]:
        """
        Continuous Greeks monitoring with real-time alerts
        
        Returns:
            Dict with Greeks status and any alerts
        """
        portfolio_greeks = self.greeks_aggregator.compute_portfolio_greeks(state)
        
        # Check against limits
        violations = self.risk_authority.check_greeks_limits(portfolio_greeks, state)
        
        # Compute Greeks attribution
        greeks_by_strategy = self.greeks_aggregator.compute_greeks_by_strategy(state)
        
        # Detect anomalies
        anomalies = self._detect_greeks_anomalies(portfolio_greeks)
        
        monitoring_result = {
            "timestamp": datetime.now(),
            "portfolio_greeks": portfolio_greeks,
            "violations": violations,
            "greeks_by_strategy": greeks_by_strategy,
            "anomalies": anomalies
        }
        
        # Trigger alerts if needed
        if violations:
            logger.warning(f"Greeks violations detected: {violations}")
        if anomalies:
            logger.warning(f"Greeks anomalies detected: {anomalies}")
        
        return monitoring_result
    
    def _detect_greeks_anomalies(self, greeks: PortfolioGreeks) -> List[str]:
        """Detect anomalous Greeks values that may indicate errors"""
        anomalies = []
        
        # Check for unrealistic values
        if abs(greeks.delta) > 1000:
            anomalies.append(f"Unusually large delta: {greeks.delta}")
        
        if abs(greeks.gamma) > 100:
            anomalies.append(f"Unusually large gamma: {greeks.gamma}")
        
        if abs(greeks.vega) > 1000:
            anomalies.append(f"Unusually large vega: {greeks.vega}")
        
        # Check for inconsistencies
        if hasattr(greeks, 'delta_by_underlying'):
            total_delta = sum(greeks.delta_by_underlying.values())
            if abs(total_delta - greeks.delta) > 0.01:
                anomalies.append("Delta aggregation mismatch")
        
        return anomalies
    
    def get_feedback_history(self, lookback_periods: int = 10) -> List[Dict[str, Any]]:
        """Get recent feedback loop history"""
        return self._feedback_history[-lookback_periods:]
    
    # ========== Event-Driven Communication ==========
    
    def register_event_listener(
        self,
        event_type: EventType,
        callback: Callable[[SystemEvent], None]
    ):
        """Register a callback for specific event types"""
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        self._event_listeners[event_type].append(callback)
        logger.debug(f"Registered listener for {event_type}")
    
    def _emit_event(self, event: SystemEvent):
        """Emit event to all registered listeners"""
        if event.event_type in self._event_listeners:
            for callback in self._event_listeners[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Event listener failed: {e}")
        
        # Log important events
        if event.severity in ["ERROR", "CRITICAL"]:
            logger.error(f"Event: {event.event_type} - {event.data}")
        elif event.severity == "WARNING":
            logger.warning(f"Event: {event.event_type} - {event.data}")
    
    def _safe_component_call(
        self,
        component_name: str,
        operation: str,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[Any, Optional[ComponentError]]:
        """
        Safely call a component method with error handling and recovery.
        
        Returns:
            Tuple of (result, error). If error is None, call succeeded.
        """
        try:
            result = func(*args, **kwargs)
            return result, None
            
        except Exception as e:
            logger.error(f"Component {component_name}.{operation} failed: {e}", exc_info=True)
            
            # Determine if error is recoverable
            recoverable = self._is_recoverable_error(e)
            
            error = ComponentError(
                component=component_name,
                operation=operation,
                error=e,
                timestamp=datetime.now(),
                recoverable=recoverable,
                recovery_action=self._get_recovery_action(component_name, operation, e)
            )
            
            self._error_history.append(error)
            
            # Emit error event
            self._emit_event(SystemEvent(
                event_type=EventType.COMPONENT_ERROR,
                timestamp=datetime.now(),
                component=component_name,
                data={
                    "operation": operation,
                    "error": str(e),
                    "recoverable": recoverable
                },
                severity="ERROR" if recoverable else "CRITICAL"
            ))
            
            # Attempt recovery if possible
            if recoverable and error.recovery_action:
                logger.info(f"Attempting recovery: {error.recovery_action}")
                self._attempt_recovery(error)
            
            return None, error
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable"""
        # Network errors, temporary failures are recoverable
        recoverable_types = (
            ConnectionError,
            TimeoutError,
            ValueError  # Often data validation issues
        )
        
        if isinstance(error, recoverable_types):
            return True
        
        # Check error message for recoverable patterns
        error_msg = str(error).lower()
        recoverable_patterns = ["timeout", "connection", "temporary", "retry"]
        
        return any(pattern in error_msg for pattern in recoverable_patterns)
    
    def _get_recovery_action(
        self,
        component: str,
        operation: str,
        error: Exception
    ) -> Optional[str]:
        """Determine appropriate recovery action"""
        if "state_engine" in component.lower():
            return "restore_last_valid_state"
        elif "execution" in component.lower():
            return "retry_with_backoff"
        elif "strategy" in component.lower():
            return "use_fallback_strategy"
        elif "risk" in component.lower():
            return "use_conservative_limits"
        else:
            return "log_and_continue"
    
    def _attempt_recovery(self, error: ComponentError):
        """Attempt to recover from component error"""
        try:
            if error.recovery_action == "restore_last_valid_state":
                self.state_engine.restore_last_valid_state()
                logger.info("Restored last valid state")
                
            elif error.recovery_action == "retry_with_backoff":
                # Retry logic would go here
                logger.info("Retry scheduled")
                
            elif error.recovery_action == "use_fallback_strategy":
                logger.info("Using fallback strategy generation")
                
            elif error.recovery_action == "use_conservative_limits":
                self.risk_authority.activate_conservative_mode()
                logger.info("Activated conservative risk limits")
                
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
    
    def get_component_health(self) -> Dict[str, Any]:
        """Get health status of all components"""
        health = {}
        
        components = {
            "state_engine": self.state_engine,
            "strategy_generator": self.strategy_generator,
            "greeks_aggregator": self.greeks_aggregator,
            "risk_authority": self.risk_authority,
            "dispersion_module": self.dispersion_module,
            "gamma_scalper": self.gamma_scalper,
            "capital_allocator": self.capital_allocator,
            "monte_carlo_engine": self.monte_carlo_engine,
            "regime_detector": self.regime_detector,
            "execution_interface": self.execution_interface,
            "performance_monitor": self.performance_monitor
        }
        
        for name, component in components.items():
            # Check recent errors for this component
            recent_errors = [
                e for e in self._error_history[-100:]
                if e.component == name
            ]
            
            health[name] = {
                "status": "healthy" if len(recent_errors) == 0 else "degraded",
                "recent_errors": len(recent_errors),
                "last_error": recent_errors[-1].timestamp if recent_errors else None
            }
        
        return health
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        state = self.state_engine.get_state()
        greeks = self.greeks_aggregator.compute_portfolio_greeks(state)
        performance = self.performance_monitor.get_current_metrics()
        
        return {
            "timestamp": datetime.now(),
            "running": self._running,
            "regime": state.regime,
            "portfolio_greeks": greeks,
            "performance": performance,
            "state_quality": state.validation_status
        }
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down UnifiedVolatilityEngine")
        self._running = False
        
        # Persist final state
        self.state_engine.persist_state()
        
        # Close execution interface
        self.execution_interface.close()
        
        logger.info("Shutdown complete")
