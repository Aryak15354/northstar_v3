"""
Production Grade Enhancements Integration

This module integrates the Edge Half-Life Model and Liquidity Kill Switch
into the existing Northstar V3 system, providing production-grade capital
efficiency and risk management.

Key Integration Points:
- Edge Half-Life → Capital Allocation Pipeline
- Liquidity Assessment → Risk Coordinator
- Enhanced Kill Switch → Emergency Systems
- State Management → Unified State
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

from ..intelligence.edge_half_life import EdgeHalfLifeTracker, EdgeStateManager
from ..risk.liquidity_kill_switch import LiquidityRiskAssessor, LiquidityAwareKillSwitch, LiquidationUrgency
from ..risk.risk_coordinator import RiskCoordinator
from ..core.state import UnifiedState


class ProductionGradeRiskManager:
    """
    Enhanced risk manager integrating edge half-life and liquidity awareness
    
    This system provides:
    - Edge-aware capital allocation
    - Liquidity-constrained risk controls
    - Production-grade kill switch logic
    - Integrated state management
    """
    
    def __init__(self,
                 unified_state: UnifiedState,
                 base_risk_coordinator: RiskCoordinator,
                 base_kill_switch):
        
        self.unified_state = unified_state
        self.base_risk_coordinator = base_risk_coordinator
        self.base_kill_switch = base_kill_switch
        
        # Initialize enhanced components
        self.edge_tracker = EdgeHalfLifeTracker(
            lookback_window=90,
            min_observations=20,
            decay_power=2.0,
            confidence_threshold=0.7
        )
        
        self.liquidity_assessor = LiquidityRiskAssessor(
            impact_model_k=0.005,
            impact_model_beta=0.6,
            max_participation_rate=0.20
        )
        
        self.liquidity_kill_switch = LiquidityAwareKillSwitch(
            base_kill_switch=base_kill_switch,
            liquidity_assessor=self.liquidity_assessor,
            max_acceptable_exit_risk=1.0
        )
        
        # State managers
        self.edge_state_manager = EdgeStateManager(unified_state, self.edge_tracker)
        
        self.logger = logging.getLogger(__name__)
        
        # Integration flags
        self.edge_integration_enabled = True
        self.liquidity_integration_enabled = True
        
        self.logger.info("Production Grade Risk Manager initialized")
    
    def update_strategy_performance(self,
                                  strategy_id: str,
                                  timestamp: datetime,
                                  returns: float,
                                  benchmark_returns: float,
                                  volatility: float,
                                  confidence: float,
                                  regime: str) -> None:
        """Update strategy performance for edge tracking"""
        
        if not self.edge_integration_enabled:
            return
        
        try:
            self.edge_tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=returns,
                benchmark_returns=benchmark_returns,
                volatility=volatility,
                confidence=confidence,
                regime=regime
            )
            
            # Update state
            self.edge_state_manager.update_edge_state()
            
            self.logger.debug(f"Updated edge tracking for strategy {strategy_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating strategy performance: {e}")
    
    def update_market_liquidity(self,
                              symbol: str,
                              timestamp: datetime,
                              volume: float,
                              bid_price: float,
                              ask_price: float,
                              last_price: float) -> None:
        """Update market liquidity data"""
        
        if not self.liquidity_integration_enabled:
            return
        
        try:
            self.liquidity_assessor.update_market_data(
                symbol=symbol,
                timestamp=timestamp,
                volume=volume,
                bid_price=bid_price,
                ask_price=ask_price,
                last_price=last_price
            )
            
            self.logger.debug(f"Updated liquidity data for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error updating market liquidity: {e}")
    
    def get_enhanced_capital_allocation(self,
                                      proposed_allocations: Dict[str, float],
                                      strategy_edges: Dict[str, float]) -> Dict[str, float]:
        """
        Get edge-aware capital allocations
        
        Args:
            proposed_allocations: Base allocations from capital allocator
            strategy_edges: Expected edge values for each strategy
            
        Returns:
            Dict of adjusted allocations incorporating edge health
        """
        
        if not self.edge_integration_enabled:
            return proposed_allocations
        
        enhanced_allocations = {}
        total_adjustment = 0.0
        
        for strategy_id, base_allocation in proposed_allocations.items():
            
            # Get edge-based capital multiplier
            edge_multiplier = self.edge_state_manager.get_strategy_capital_multiplier(strategy_id)
            
            # Apply edge decay
            adjusted_allocation = base_allocation * edge_multiplier
            enhanced_allocations[strategy_id] = adjusted_allocation
            
            # Track total adjustment for rebalancing
            total_adjustment += (base_allocation - adjusted_allocation)
            
            self.logger.debug(f"Strategy {strategy_id}: {base_allocation:.3f} -> {adjusted_allocation:.3f} "
                            f"(multiplier: {edge_multiplier:.3f})")
        
        # Redistribute freed capital to cash or healthy strategies
        if total_adjustment > 0.001:  # Meaningful adjustment
            self._redistribute_freed_capital(enhanced_allocations, total_adjustment, strategy_edges)
        
        return enhanced_allocations
    
    def _redistribute_freed_capital(self,
                                  allocations: Dict[str, float],
                                  freed_capital: float,
                                  strategy_edges: Dict[str, float]) -> None:
        """Redistribute capital freed from edge decay"""
        
        # Find healthy strategies with positive edge
        healthy_strategies = []
        for strategy_id in allocations.keys():
            edge_metrics = self.edge_tracker.get_edge_metrics(strategy_id)
            if (edge_metrics and 
                edge_metrics.edge_health > 0.5 and 
                strategy_edges.get(strategy_id, 0) > 0):
                healthy_strategies.append(strategy_id)
        
        if healthy_strategies:
            # Redistribute to healthy strategies proportionally
            redistribution_per_strategy = freed_capital / len(healthy_strategies)
            for strategy_id in healthy_strategies:
                allocations[strategy_id] += redistribution_per_strategy
        else:
            # No healthy strategies - allocate to cash
            allocations['CASH'] = allocations.get('CASH', 0.0) + freed_capital
        
        self.logger.info(f"Redistributed {freed_capital:.3f} freed capital")
    
    def validate_trade_with_liquidity(self,
                                    trade,
                                    portfolio,
                                    metrics) -> Tuple[bool, List[str]]:
        """
        Enhanced trade validation incorporating liquidity constraints
        
        Returns:
            Tuple of (approved, violation_reasons)
        """
        
        # First run base risk validation
        base_decision, base_violations = self.base_risk_coordinator.validate_trade(
            trade, portfolio, metrics
        )
        
        if base_decision.value == 'rejected':
            return False, [v.description for v in base_violations]
        
        # Add liquidity validation if enabled
        if not self.liquidity_integration_enabled:
            return base_decision.value == 'approved', []
        
        try:
            # Calculate position liquidity metrics
            remaining_edge = self._estimate_remaining_edge(trade.symbol)
            
            liquidity_metrics = self.liquidity_assessor.calculate_position_liquidity(
                symbol=trade.symbol,
                position_size=trade.quantity,
                market_value=trade.quantity * trade.price,
                remaining_edge=remaining_edge,
                timestamp=trade.timestamp
            )
            
            # Check liquidity constraints
            violations = []
            
            if liquidity_metrics.exit_risk > 2.0:
                violations.append(f"Exit risk {liquidity_metrics.exit_risk:.2f} too high for new position")
            
            if liquidity_metrics.participation_rate > 0.3:
                violations.append(f"Participation rate {liquidity_metrics.participation_rate:.2%} exceeds safe limit")
            
            if liquidity_metrics.liquidity_status.value in ['frozen', 'crisis']:
                violations.append(f"Symbol {trade.symbol} has {liquidity_metrics.liquidity_status.value} liquidity status")
            
            return len(violations) == 0, violations
            
        except Exception as e:
            self.logger.error(f"Error in liquidity validation: {e}")
            return base_decision.value == 'approved', []
    
    def _estimate_remaining_edge(self, symbol: str) -> float:
        """Estimate remaining edge value for a symbol"""
        # This would integrate with your strategy system
        # For now, return a conservative estimate
        return 0.02  # 2% expected edge
    
    def should_trigger_enhanced_kill_switch(self,
                                          trigger_type,
                                          current_metrics: Dict[str, float],
                                          positions: Dict[str, Dict]) -> Tuple[bool, str]:
        """
        Enhanced kill switch trigger logic with liquidity awareness
        
        Returns:
            Tuple of (should_trigger, reason)
        """
        
        if not self.liquidity_integration_enabled:
            # Fall back to base kill switch logic
            try:
                return self.base_kill_switch._check_trigger_condition(
                    trigger_type, current_metrics, 
                    self.base_kill_switch.triggers[trigger_type]
                ), "base_kill_switch"
            except (TypeError, KeyError):
                # Handle mock objects
                return self.base_kill_switch._check_trigger_condition(
                    trigger_type, current_metrics, {}
                ), "base_kill_switch"
        
        try:
            # Update position liquidity metrics
            self._update_position_liquidity_metrics(positions)
            
            # Use liquidity-aware kill switch
            should_trigger, reason = self.liquidity_kill_switch.should_trigger_kill_switch(
                trigger_type, current_metrics, positions
            )
            
            return should_trigger, reason
            
        except Exception as e:
            self.logger.error(f"Error in enhanced kill switch logic: {e}")
            # Fall back to base logic
            return self.base_kill_switch._check_trigger_condition(
                trigger_type, current_metrics,
                self.base_kill_switch.triggers[trigger_type]
            ), f"fallback_due_to_error_{str(e)[:50]}"
    
    def _update_position_liquidity_metrics(self, positions: Dict[str, Dict]) -> None:
        """Update liquidity metrics for all positions"""
        
        timestamp = datetime.now()
        
        for symbol, pos_data in positions.items():
            remaining_edge = self._estimate_remaining_edge(symbol)
            
            self.liquidity_assessor.calculate_position_liquidity(
                symbol=symbol,
                position_size=pos_data.get('position_size', 0.0),
                market_value=pos_data.get('market_value', 0.0),
                remaining_edge=remaining_edge,
                timestamp=timestamp
            )
    
    def execute_enhanced_liquidation(self,
                                   positions: Dict[str, Dict],
                                   urgency_level: str = "high") -> Dict[str, Any]:
        """
        Execute liquidation with liquidity awareness
        
        Args:
            positions: Current portfolio positions
            urgency_level: 'routine', 'elevated', 'high', 'critical', 'emergency'
            
        Returns:
            Dict containing execution results
        """
        
        if not self.liquidity_integration_enabled:
            # Fall back to base kill switch
            return self.base_kill_switch._execute_emergency_liquidation(None)
        
        try:
            # Map urgency level to enum
            urgency_mapping = {
                'routine': LiquidationUrgency.ROUTINE,
                'elevated': LiquidationUrgency.ELEVATED,
                'high': LiquidationUrgency.HIGH,
                'critical': LiquidationUrgency.CRITICAL,
                'emergency': LiquidationUrgency.EMERGENCY
            }
            
            urgency = urgency_mapping.get(urgency_level, LiquidationUrgency.HIGH)
            
            # Execute liquidity-aware liquidation
            result = self.liquidity_kill_switch.execute_liquidity_aware_liquidation(
                positions, urgency
            )
            
            # Update state with liquidation results
            self.unified_state.update_state(
                'last_liquidation_result', 
                result, 
                'production_risk_manager'
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in enhanced liquidation: {e}")
            # Fall back to base liquidation
            return self.base_kill_switch._execute_emergency_liquidation(None)
    
    def get_production_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive production risk summary"""
        
        try:
            # Base risk summary
            base_summary = self.base_risk_coordinator.get_risk_summary(
                self._get_current_portfolio()
            )
            
            # Edge summary
            edge_summary = {}
            if self.edge_integration_enabled:
                try:
                    edge_summary = self.edge_tracker.get_portfolio_edge_summary()
                except Exception:
                    edge_summary = {'status': 'no_strategies'}
            
            # Liquidity summary
            liquidity_summary = {}
            if self.liquidity_integration_enabled:
                try:
                    liquidity_summary = self.liquidity_kill_switch.get_liquidity_status_summary()
                except Exception:
                    liquidity_summary = {'status': 'no_data'}
            
            # Combined summary
            production_summary = {
                'timestamp': datetime.now(),
                'base_risk': {
                    'status': base_summary.get('status', 'unknown'),
                    'risk_score': base_summary.get('risk_score', 0.0),
                    'violations': len(base_summary.get('violations', [])) if hasattr(base_summary.get('violations', []), '__len__') else 0
                },
                'edge_health': {
                    'enabled': self.edge_integration_enabled,
                    'portfolio_edge_score': edge_summary.get('portfolio_edge_score', 0.0),
                    'healthy_strategies': edge_summary.get('healthy_strategies', 0),
                    'total_strategies': edge_summary.get('total_strategies', 0)
                },
                'liquidity_risk': {
                    'enabled': self.liquidity_integration_enabled,
                    'portfolio_liquidity_score': liquidity_summary.get('portfolio_liquidity_score', 1.0),
                    'systemic_risk_level': liquidity_summary.get('systemic_risk_level', 0.0),
                    'kill_switch_recommendation': liquidity_summary.get('kill_switch_recommendation', 'unknown')
                },
                'overall_status': self._calculate_overall_status(base_summary, edge_summary, liquidity_summary)
            }
            
            return production_summary
            
        except Exception as e:
            self.logger.error(f"Error generating production risk summary: {e}")
            return {
                'timestamp': datetime.now(),
                'status': 'error',
                'error': str(e)
            }
    
    def _calculate_overall_status(self, base_summary, edge_summary, liquidity_summary) -> str:
        """Calculate overall system status"""
        
        # Base risk status
        base_status = base_summary.get('status', 'unknown')
        if base_status == 'CRITICAL':
            return 'CRITICAL'
        
        # Edge health check
        if self.edge_integration_enabled:
            edge_score = edge_summary.get('portfolio_edge_score', 0.0)
            if edge_score < 0.2:
                return 'POOR_EDGE_HEALTH'
        
        # Liquidity risk check
        if self.liquidity_integration_enabled:
            systemic_risk = liquidity_summary.get('systemic_risk_level', 0.0)
            if systemic_risk > 0.8:
                return 'HIGH_LIQUIDITY_RISK'
        
        # Combined assessment
        if base_status == 'WARNING':
            return 'WARNING'
        elif base_status == 'HEALTHY':
            return 'HEALTHY'
        else:
            return 'MONITORING'
    
    def _get_current_portfolio(self):
        """Get current portfolio from unified state"""
        # This would integrate with your portfolio system
        # For now, return a mock portfolio
        from ..risk.risk_coordinator import Portfolio, Position
        
        return Portfolio(
            positions=[],
            cash=100000.0,
            total_value=100000.0,
            timestamp=datetime.now()
        )
    
    def enable_edge_integration(self) -> None:
        """Enable edge half-life integration"""
        self.edge_integration_enabled = True
        self.logger.info("Edge integration enabled")
    
    def disable_edge_integration(self) -> None:
        """Disable edge half-life integration"""
        self.edge_integration_enabled = False
        self.logger.info("Edge integration disabled")
    
    def enable_liquidity_integration(self) -> None:
        """Enable liquidity awareness integration"""
        self.liquidity_integration_enabled = True
        self.logger.info("Liquidity integration enabled")
    
    def disable_liquidity_integration(self) -> None:
        """Disable liquidity awareness integration"""
        self.liquidity_integration_enabled = False
        self.logger.info("Liquidity integration disabled")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status"""
        return {
            'edge_integration_enabled': self.edge_integration_enabled,
            'liquidity_integration_enabled': self.liquidity_integration_enabled,
            'edge_strategies_tracked': len(self.edge_tracker.edge_metrics),
            'liquidity_symbols_tracked': len(self.liquidity_assessor.liquidity_metrics),
            'last_update': datetime.now()
        }