"""
Shadow Portfolio Dashboard

Real-time dashboard for monitoring shadow portfolio performance and Phase 3
intelligence integration. Displays:
- Shadow portfolio positions and performance
- Phase 3 regime classifications and transitions
- NO_EDGE state activations and effects
- Shadow vs live performance divergence tracking

This dashboard provides operational visibility into shadow portfolio execution
and Phase 3 intelligence effectiveness in real-time.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import deque, defaultdict
import numpy as np
import pandas as pd
import json

from src.validation.phase3_intelligence_monitor import Phase3IntelligenceMonitor
from src.validation.enhanced_shadow_portfolio_state import EnhancedShadowPortfolioState
from src.validation.phase3_integration_layer import Phase3IntegrationLayer
from src.core.events import EventBus
from src.core.state import UnifiedState

logger = logging.getLogger(__name__)

@dataclass
class PortfolioPosition:
    """Individual portfolio position data"""
    symbol: str
    weight: float
    value: float
    shares: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    regime_context: Optional[str] = None
    tailwind_score: float = 0.0
    confidence_score: float = 0.0

@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics"""
    total_return: float = 0.0
    daily_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_duration: float = 0.0

@dataclass
class RegimeTransitionEvent:
    """Regime transition event data"""
    timestamp: datetime
    from_regime: str
    to_regime: str
    confidence_before: float
    confidence_after: float
    portfolio_impact: float
    positions_affected: List[str]

@dataclass
class NoEdgeActivation:
    """NO_EDGE state activation event"""
    timestamp: datetime
    activation_type: str  # 'enter' or 'exit'
    triggers: List[str]
    duration: int  # periods in NO_EDGE state
    portfolio_exposure_before: float
    portfolio_exposure_after: float
    positions_reduced: List[str]

@dataclass
class DashboardSnapshot:
    """Complete dashboard state snapshot"""
    timestamp: datetime
    portfolio_positions: List[PortfolioPosition]
    performance_metrics: PerformanceMetrics
    current_regime: Optional[str]
    regime_confidence: float
    no_edge_active: bool
    no_edge_duration: int
    recent_transitions: List[RegimeTransitionEvent]
    recent_no_edge_events: List[NoEdgeActivation]
    shadow_vs_live_divergence: float
    health_score: float
    alerts: List[str]

class ShadowPortfolioDashboard:
    """
    Real-time dashboard for shadow portfolio monitoring
    
    Provides comprehensive visibility into:
    - Current portfolio positions and performance
    - Phase 3 regime state and transitions
    - NO_EDGE activations and portfolio impact
    - Performance divergence from live portfolio
    - Real-time alerts and diagnostics
    """
    
    def __init__(self,
                 intelligence_monitor: Phase3IntelligenceMonitor,
                 integration_layer: Phase3IntegrationLayer,
                 event_bus: EventBus,
                 unified_state: UnifiedState,
                 live_portfolio_reference: Optional[Any] = None,
                 dashboard_window: int = 1000):
        """
        Initialize shadow portfolio dashboard
        
        Args:
            intelligence_monitor: Phase 3 intelligence monitor
            integration_layer: Phase 3 integration layer
            event_bus: System event bus
            unified_state: System unified state
            live_portfolio_reference: Reference to live portfolio for comparison
            dashboard_window: Number of snapshots to maintain in history
        """
        self.intelligence_monitor = intelligence_monitor
        self.integration_layer = integration_layer
        self.event_bus = event_bus
        self.unified_state = unified_state
        self.live_portfolio_reference = live_portfolio_reference
        self.dashboard_window = dashboard_window
        
        # Dashboard state
        self.current_positions: Dict[str, PortfolioPosition] = {}
        self.performance_metrics = PerformanceMetrics()
        self.portfolio_history: deque = deque(maxlen=dashboard_window)
        self.regime_transitions: deque = deque(maxlen=100)
        self.no_edge_events: deque = deque(maxlen=100)
        
        # Performance tracking
        self.portfolio_values: deque = deque(maxlen=dashboard_window)
        self.daily_returns: deque = deque(maxlen=dashboard_window)
        self.drawdown_history: deque = deque(maxlen=dashboard_window)
        
        # Divergence tracking
        self.shadow_values: deque = deque(maxlen=dashboard_window)
        self.live_values: deque = deque(maxlen=dashboard_window)
        self.divergence_history: deque = deque(maxlen=dashboard_window)
        
        # Alert thresholds
        self.divergence_threshold = 0.05  # 5% divergence triggers alert
        self.drawdown_threshold = 0.10  # 10% drawdown triggers alert
        self.no_edge_duration_threshold = 10  # 10 periods triggers alert
        
        # State tracking
        self.last_regime = None
        self.last_no_edge_state = False
        self.total_updates = 0
        
        logger.info("ShadowPortfolioDashboard initialized")
    
    def update_dashboard(self, shadow_portfolio_state: EnhancedShadowPortfolioState) -> DashboardSnapshot:
        """
        Update dashboard with latest shadow portfolio state
        
        Args:
            shadow_portfolio_state: Latest shadow portfolio state
            
        Returns:
            Complete dashboard snapshot
        """
        try:
            timestamp = datetime.now()
            self.total_updates += 1
            
            # Update portfolio positions
            self._update_portfolio_positions(shadow_portfolio_state)
            
            # Update performance metrics
            self._update_performance_metrics(shadow_portfolio_state)
            
            # Track regime transitions
            self._track_regime_transitions(shadow_portfolio_state)
            
            # Track NO_EDGE events
            self._track_no_edge_events(shadow_portfolio_state)
            
            # Calculate divergence from live portfolio
            divergence = self._calculate_portfolio_divergence(shadow_portfolio_state)
            
            # Get current intelligence state
            intelligence_snapshot = self.intelligence_monitor.get_current_snapshot()
            
            # Generate alerts
            alerts = self._generate_alerts(shadow_portfolio_state, intelligence_snapshot, divergence)
            
            # Create dashboard snapshot
            snapshot = DashboardSnapshot(
                timestamp=timestamp,
                portfolio_positions=list(self.current_positions.values()),
                performance_metrics=self.performance_metrics,
                current_regime=intelligence_snapshot.regime_state.current_regime if intelligence_snapshot else None,
                regime_confidence=intelligence_snapshot.regime_state.confidence_score if intelligence_snapshot else 0.0,
                no_edge_active=intelligence_snapshot.no_edge_state.is_no_edge if intelligence_snapshot else False,
                no_edge_duration=intelligence_snapshot.no_edge_state.no_edge_duration if intelligence_snapshot else 0,
                recent_transitions=list(self.regime_transitions)[-5:],  # Last 5 transitions
                recent_no_edge_events=list(self.no_edge_events)[-5:],  # Last 5 events
                shadow_vs_live_divergence=divergence,
                health_score=intelligence_snapshot.overall_health_score if intelligence_snapshot else 0.0,
                alerts=alerts
            )
            
            # Store snapshot
            self.portfolio_history.append(snapshot)
            
            # Emit dashboard update event
            self.event_bus.emit('shadow_portfolio_dashboard_updated', {
                'snapshot': snapshot,
                'divergence': divergence,
                'alerts': alerts
            })
            
            logger.debug(f"Shadow portfolio dashboard updated - Positions: {len(self.current_positions)}, "
                        f"Performance: {self.performance_metrics.total_return:.3f}, "
                        f"Divergence: {divergence:.3f}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error updating shadow portfolio dashboard: {e}")
            raise
    
    def _update_portfolio_positions(self, shadow_state: EnhancedShadowPortfolioState):
        """Update current portfolio positions"""
        try:
            # Get intelligence context
            intelligence_snapshot = self.intelligence_monitor.get_current_snapshot()
            current_regime = intelligence_snapshot.regime_state.current_regime if intelligence_snapshot else None
            
            # Update positions from shadow state
            new_positions = {}
            
            for symbol, allocation in shadow_state.current_allocations.items():
                if symbol == 'CASH':
                    continue
                    
                # Get position details
                current_price = shadow_state.current_prices.get(symbol, 0.0)
                shares = shadow_state.position_shares.get(symbol, 0.0)
                entry_price = shadow_state.entry_prices.get(symbol, current_price)
                
                # Calculate values
                position_value = shares * current_price
                unrealized_pnl = (current_price - entry_price) * shares
                
                # Get Phase 3 context
                tailwind_score = 0.0
                confidence_score = 0.0
                
                if intelligence_snapshot:
                    tailwinds = intelligence_snapshot.tailwind_state.current_tailwinds
                    confidences = intelligence_snapshot.anticipatory_state.confidence_scores
                    
                    # Aggregate tailwind score (simplified)
                    if tailwinds:
                        tailwind_score = np.mean(list(tailwinds.values()))
                    
                    confidence_score = confidences.get(symbol, 0.0)
                
                # Create position object
                position = PortfolioPosition(
                    symbol=symbol,
                    weight=allocation,
                    value=position_value,
                    shares=shares,
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=shadow_state.realized_pnl.get(symbol, 0.0),
                    regime_context=current_regime,
                    tailwind_score=tailwind_score,
                    confidence_score=confidence_score
                )
                
                new_positions[symbol] = position
            
            self.current_positions = new_positions
            
        except Exception as e:
            logger.warning(f"Error updating portfolio positions: {e}")
    
    def _update_performance_metrics(self, shadow_state: EnhancedShadowPortfolioState):
        """Update portfolio performance metrics"""
        try:
            # Calculate current portfolio value
            total_value = sum(pos.value for pos in self.current_positions.values())
            cash_value = shadow_state.current_allocations.get('CASH', 0.0) * shadow_state.total_value
            portfolio_value = total_value + cash_value
            
            # Store portfolio value
            self.portfolio_values.append(portfolio_value)
            
            # Calculate daily return
            daily_return = 0.0
            if len(self.portfolio_values) >= 2:
                prev_value = self.portfolio_values[-2]
                if prev_value > 0:
                    daily_return = (portfolio_value - prev_value) / prev_value
            
            self.daily_returns.append(daily_return)
            
            # Calculate total return
            if self.portfolio_values:
                initial_value = self.portfolio_values[0]
                total_return = (portfolio_value - initial_value) / initial_value if initial_value > 0 else 0.0
            else:
                total_return = 0.0
            
            # Calculate volatility (annualized)
            volatility = 0.0
            if len(self.daily_returns) >= 10:
                returns_array = np.array(list(self.daily_returns))
                volatility = np.std(returns_array) * np.sqrt(252)  # Annualized
            
            # Calculate Sharpe ratio (assuming 0% risk-free rate)
            sharpe_ratio = 0.0
            if volatility > 0 and len(self.daily_returns) >= 10:
                avg_return = np.mean(list(self.daily_returns))
                sharpe_ratio = (avg_return * 252) / volatility  # Annualized
            
            # Calculate maximum drawdown
            max_drawdown = 0.0
            if len(self.portfolio_values) >= 2:
                values = np.array(list(self.portfolio_values))
                peak = np.maximum.accumulate(values)
                drawdown = (values - peak) / peak
                max_drawdown = np.min(drawdown)
                
                # Store current drawdown
                current_drawdown = drawdown[-1]
                self.drawdown_history.append(current_drawdown)
            
            # Calculate win rate and profit factor
            win_rate = 0.0
            profit_factor = 0.0
            total_trades = 0
            
            if self.daily_returns:
                positive_returns = [r for r in self.daily_returns if r > 0]
                negative_returns = [r for r in self.daily_returns if r < 0]
                
                total_trades = len([r for r in self.daily_returns if abs(r) > 0.001])  # Significant moves
                
                if total_trades > 0:
                    win_rate = len(positive_returns) / total_trades
                
                if negative_returns:
                    gross_profit = sum(positive_returns)
                    gross_loss = abs(sum(negative_returns))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
            
            # Update performance metrics
            self.performance_metrics = PerformanceMetrics(
                total_return=total_return,
                daily_return=daily_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                total_trades=total_trades,
                avg_trade_duration=1.0  # Placeholder - would need trade tracking
            )
            
        except Exception as e:
            logger.warning(f"Error updating performance metrics: {e}")
    
    def _track_regime_transitions(self, shadow_state: EnhancedShadowPortfolioState):
        """Track regime transitions and their portfolio impact"""
        try:
            intelligence_snapshot = self.intelligence_monitor.get_current_snapshot()
            if not intelligence_snapshot:
                return
            
            current_regime = intelligence_snapshot.regime_state.current_regime
            current_confidence = intelligence_snapshot.regime_state.confidence_score
            
            # Check for regime transition
            if (self.last_regime and 
                self.last_regime != current_regime and 
                current_regime is not None):
                
                # Calculate portfolio impact (simplified)
                portfolio_impact = 0.0
                if len(self.daily_returns) >= 2:
                    portfolio_impact = self.daily_returns[-1]  # Recent return as proxy
                
                # Identify affected positions
                positions_affected = list(self.current_positions.keys())
                
                # Create transition event
                transition = RegimeTransitionEvent(
                    timestamp=datetime.now(),
                    from_regime=self.last_regime,
                    to_regime=current_regime,
                    confidence_before=getattr(self, 'last_regime_confidence', 0.0),
                    confidence_after=current_confidence,
                    portfolio_impact=portfolio_impact,
                    positions_affected=positions_affected
                )
                
                self.regime_transitions.append(transition)
                
                logger.info(f"Regime transition detected: {self.last_regime} -> {current_regime}, "
                           f"Impact: {portfolio_impact:.3f}")
            
            # Update tracking state
            self.last_regime = current_regime
            self.last_regime_confidence = current_confidence
            
        except Exception as e:
            logger.warning(f"Error tracking regime transitions: {e}")
    
    def _track_no_edge_events(self, shadow_state: EnhancedShadowPortfolioState):
        """Track NO_EDGE state activations and portfolio impact"""
        try:
            intelligence_snapshot = self.intelligence_monitor.get_current_snapshot()
            if not intelligence_snapshot:
                return
            
            current_no_edge = intelligence_snapshot.no_edge_state.is_no_edge
            no_edge_duration = intelligence_snapshot.no_edge_state.no_edge_duration
            triggers = intelligence_snapshot.no_edge_state.activation_triggers
            
            # Check for NO_EDGE state change
            if current_no_edge != self.last_no_edge_state:
                
                # Calculate portfolio exposure
                total_exposure = sum(
                    abs(pos.weight) for pos in self.current_positions.values()
                    if pos.symbol != 'CASH'
                )
                
                # Identify positions that might be reduced
                positions_reduced = []
                if current_no_edge:  # Entering NO_EDGE
                    # Positions with low confidence might be reduced
                    positions_reduced = [
                        pos.symbol for pos in self.current_positions.values()
                        if pos.confidence_score < 0.5
                    ]
                
                # Create NO_EDGE event
                no_edge_event = NoEdgeActivation(
                    timestamp=datetime.now(),
                    activation_type='enter' if current_no_edge else 'exit',
                    triggers=triggers,
                    duration=no_edge_duration,
                    portfolio_exposure_before=getattr(self, 'last_portfolio_exposure', total_exposure),
                    portfolio_exposure_after=total_exposure,
                    positions_reduced=positions_reduced
                )
                
                self.no_edge_events.append(no_edge_event)
                
                logger.info(f"NO_EDGE state {'activated' if current_no_edge else 'deactivated'}, "
                           f"Duration: {no_edge_duration}, Triggers: {triggers}")
            
            # Update tracking state
            self.last_no_edge_state = current_no_edge
            self.last_portfolio_exposure = sum(
                abs(pos.weight) for pos in self.current_positions.values()
                if pos.symbol != 'CASH'
            )
            
        except Exception as e:
            logger.warning(f"Error tracking NO_EDGE events: {e}")
    
    def _calculate_portfolio_divergence(self, shadow_state: EnhancedShadowPortfolioState) -> float:
        """Calculate divergence between shadow and live portfolios"""
        try:
            if not self.live_portfolio_reference:
                return 0.0
            
            # Get current shadow portfolio value
            shadow_value = sum(pos.value for pos in self.current_positions.values())
            cash_value = shadow_state.current_allocations.get('CASH', 0.0) * shadow_state.total_value
            shadow_total = shadow_value + cash_value
            
            # Store shadow value
            self.shadow_values.append(shadow_total)
            
            # Get live portfolio value (placeholder - would need actual implementation)
            live_value = getattr(self.live_portfolio_reference, 'total_value', shadow_total)
            self.live_values.append(live_value)
            
            # Calculate divergence
            if len(self.shadow_values) >= 2 and len(self.live_values) >= 2:
                shadow_return = (self.shadow_values[-1] - self.shadow_values[-2]) / self.shadow_values[-2]
                live_return = (self.live_values[-1] - self.live_values[-2]) / self.live_values[-2]
                divergence = abs(shadow_return - live_return)
            else:
                divergence = 0.0
            
            self.divergence_history.append(divergence)
            
            return divergence
            
        except Exception as e:
            logger.warning(f"Error calculating portfolio divergence: {e}")
            return 0.0
    
    def _generate_alerts(self, 
                        shadow_state: EnhancedShadowPortfolioState,
                        intelligence_snapshot: Optional[Any],
                        divergence: float) -> List[str]:
        """Generate dashboard alerts based on current conditions"""
        alerts = []
        
        try:
            # High divergence alert
            if divergence > self.divergence_threshold:
                alerts.append(f"High portfolio divergence: {divergence:.3f} > {self.divergence_threshold}")
            
            # Drawdown alert
            if (self.drawdown_history and 
                self.drawdown_history[-1] < -self.drawdown_threshold):
                alerts.append(f"High drawdown: {self.drawdown_history[-1]:.3f}")
            
            # Extended NO_EDGE alert
            if (intelligence_snapshot and 
                intelligence_snapshot.no_edge_state.no_edge_duration > self.no_edge_duration_threshold):
                alerts.append(f"Extended NO_EDGE state: {intelligence_snapshot.no_edge_state.no_edge_duration} periods")
            
            # Low regime confidence alert
            if (intelligence_snapshot and 
                intelligence_snapshot.regime_state.confidence_score < 0.3):
                alerts.append(f"Low regime confidence: {intelligence_snapshot.regime_state.confidence_score:.3f}")
            
            # Position concentration alert
            if self.current_positions:
                max_position = max(pos.weight for pos in self.current_positions.values())
                if max_position > 0.4:  # 40% concentration
                    alerts.append(f"High position concentration: {max_position:.3f}")
            
            # Performance alert
            if self.performance_metrics.sharpe_ratio < -1.0:
                alerts.append(f"Poor risk-adjusted performance: Sharpe {self.performance_metrics.sharpe_ratio:.2f}")
            
            # Add intelligence anomalies
            if intelligence_snapshot and intelligence_snapshot.anomaly_flags:
                for anomaly in intelligence_snapshot.anomaly_flags:
                    alerts.append(f"Intelligence anomaly: {anomaly}")
            
        except Exception as e:
            logger.warning(f"Error generating alerts: {e}")
            alerts.append(f"Alert generation error: {str(e)}")
        
        return alerts
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get comprehensive dashboard summary"""
        try:
            current_snapshot = self.portfolio_history[-1] if self.portfolio_history else None
            
            if not current_snapshot:
                return {"status": "no_data"}
            
            # Calculate summary statistics
            position_count = len(current_snapshot.portfolio_positions)
            total_value = sum(pos.value for pos in current_snapshot.portfolio_positions)
            
            # Recent performance
            recent_returns = list(self.daily_returns)[-10:] if self.daily_returns else []
            recent_avg_return = np.mean(recent_returns) if recent_returns else 0.0
            
            # Regime stability
            regime_changes = len([t for t in self.regime_transitions if 
                                (datetime.now() - t.timestamp).days <= 7])
            
            return {
                "status": "active",
                "timestamp": current_snapshot.timestamp,
                "portfolio": {
                    "position_count": position_count,
                    "total_value": total_value,
                    "cash_allocation": current_snapshot.portfolio_positions[0].weight if current_snapshot.portfolio_positions else 0.0,
                    "top_positions": [
                        {"symbol": pos.symbol, "weight": pos.weight, "pnl": pos.unrealized_pnl}
                        for pos in sorted(current_snapshot.portfolio_positions, 
                                        key=lambda x: abs(x.weight), reverse=True)[:5]
                    ]
                },
                "performance": {
                    "total_return": current_snapshot.performance_metrics.total_return,
                    "daily_return": current_snapshot.performance_metrics.daily_return,
                    "recent_avg_return": recent_avg_return,
                    "volatility": current_snapshot.performance_metrics.volatility,
                    "sharpe_ratio": current_snapshot.performance_metrics.sharpe_ratio,
                    "max_drawdown": current_snapshot.performance_metrics.max_drawdown,
                    "win_rate": current_snapshot.performance_metrics.win_rate
                },
                "intelligence": {
                    "current_regime": current_snapshot.current_regime,
                    "regime_confidence": current_snapshot.regime_confidence,
                    "no_edge_active": current_snapshot.no_edge_active,
                    "no_edge_duration": current_snapshot.no_edge_duration,
                    "health_score": current_snapshot.health_score,
                    "recent_regime_changes": regime_changes
                },
                "risk": {
                    "divergence": current_snapshot.shadow_vs_live_divergence,
                    "current_drawdown": self.drawdown_history[-1] if self.drawdown_history else 0.0,
                    "alert_count": len(current_snapshot.alerts),
                    "active_alerts": current_snapshot.alerts
                },
                "activity": {
                    "total_updates": self.total_updates,
                    "regime_transitions": len(self.regime_transitions),
                    "no_edge_events": len(self.no_edge_events),
                    "recent_transitions": [
                        {
                            "from": t.from_regime,
                            "to": t.to_regime,
                            "timestamp": t.timestamp,
                            "impact": t.portfolio_impact
                        }
                        for t in list(self.regime_transitions)[-3:]
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating dashboard summary: {e}")
            return {"status": "error", "error": str(e)}
    
    def export_dashboard_data(self, format: str = 'json') -> Union[str, Dict[str, Any]]:
        """Export dashboard data for external analysis"""
        try:
            data = {
                "metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "total_snapshots": len(self.portfolio_history),
                    "dashboard_window": self.dashboard_window
                },
                "current_state": self.get_dashboard_summary(),
                "historical_performance": [
                    {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "total_return": snapshot.performance_metrics.total_return,
                        "daily_return": snapshot.performance_metrics.daily_return,
                        "regime": snapshot.current_regime,
                        "regime_confidence": snapshot.regime_confidence,
                        "no_edge_active": snapshot.no_edge_active,
                        "health_score": snapshot.health_score,
                        "divergence": snapshot.shadow_vs_live_divergence,
                        "alert_count": len(snapshot.alerts)
                    }
                    for snapshot in list(self.portfolio_history)[-100:]  # Last 100 snapshots
                ],
                "regime_transitions": [
                    {
                        "timestamp": t.timestamp.isoformat(),
                        "from_regime": t.from_regime,
                        "to_regime": t.to_regime,
                        "confidence_before": t.confidence_before,
                        "confidence_after": t.confidence_after,
                        "portfolio_impact": t.portfolio_impact,
                        "positions_affected": t.positions_affected
                    }
                    for t in self.regime_transitions
                ],
                "no_edge_events": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "activation_type": e.activation_type,
                        "triggers": e.triggers,
                        "duration": e.duration,
                        "exposure_before": e.portfolio_exposure_before,
                        "exposure_after": e.portfolio_exposure_after,
                        "positions_reduced": e.positions_reduced
                    }
                    for e in self.no_edge_events
                ]
            }
            
            if format.lower() == 'json':
                return json.dumps(data, indent=2, default=str)
            else:
                return data
                
        except Exception as e:
            logger.error(f"Error exporting dashboard data: {e}")
            return {"error": str(e)}
    
    def reset_dashboard(self):
        """Reset dashboard state (for testing)"""
        self.current_positions.clear()
        self.performance_metrics = PerformanceMetrics()
        self.portfolio_history.clear()
        self.regime_transitions.clear()
        self.no_edge_events.clear()
        self.portfolio_values.clear()
        self.daily_returns.clear()
        self.drawdown_history.clear()
        self.shadow_values.clear()
        self.live_values.clear()
        self.divergence_history.clear()
        
        self.last_regime = None
        self.last_no_edge_state = False
        self.total_updates = 0
        
        logger.info("Shadow portfolio dashboard reset")