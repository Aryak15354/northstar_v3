"""
Kill Switch System - Emergency Risk Protection

This module implements automatic position liquidation and emergency risk controls
with immediate stakeholder notification and comprehensive audit logging.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import threading
import time


class KillSwitchTrigger(Enum):
    """Types of kill switch triggers"""
    VAR_BREACH = "var_breach"
    DRAWDOWN_LIMIT = "drawdown_limit"
    CONCENTRATION_RISK = "concentration_risk"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    SYSTEM_FAILURE = "system_failure"
    MANUAL_OVERRIDE = "manual_override"
    REGULATORY_REQUIREMENT = "regulatory_requirement"
    MARKET_CONDITIONS = "market_conditions"
    OPERATIONAL_RISK = "operational_risk"


class KillSwitchStatus(Enum):
    """Kill switch system status"""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class KillSwitchEvent:
    """Kill switch event record"""
    event_id: str
    trigger_type: KillSwitchTrigger
    timestamp: datetime
    severity: str
    description: str
    triggered_by: str
    current_metrics: Dict[str, float]
    threshold_breached: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class LiquidationOrder:
    """Liquidation order specification"""
    symbol: str
    quantity: float
    order_type: str
    urgency: str
    max_market_impact: float
    time_limit: Optional[int] = None  # seconds


@dataclass
class LiquidationResult:
    """Result of liquidation execution"""
    order_id: str
    symbol: str
    quantity_requested: float
    quantity_executed: float
    average_price: float
    market_impact: float
    execution_time: float
    status: str
    error_message: Optional[str] = None


class NotificationChannel(ABC):
    """Abstract base class for notification channels"""
    
    @abstractmethod
    def send_notification(self, event: KillSwitchEvent, recipients: List[str]) -> bool:
        """Send kill switch notification"""
        pass


class EmailNotification(NotificationChannel):
    """Email notification channel"""
    
    def send_notification(self, event: KillSwitchEvent, recipients: List[str]) -> bool:
        """Send email notification (mock implementation)"""
        # In practice, this would integrate with email service
        logging.critical(f"EMAIL ALERT: Kill switch triggered - {event.description}")
        logging.critical(f"Recipients: {', '.join(recipients)}")
        return True


class SMSNotification(NotificationChannel):
    """SMS notification channel"""
    
    def send_notification(self, event: KillSwitchEvent, recipients: List[str]) -> bool:
        """Send SMS notification (mock implementation)"""
        # In practice, this would integrate with SMS service
        logging.critical(f"SMS ALERT: Kill switch triggered - {event.description}")
        logging.critical(f"Recipients: {', '.join(recipients)}")
        return True


class SlackNotification(NotificationChannel):
    """Slack notification channel"""
    
    def send_notification(self, event: KillSwitchEvent, recipients: List[str]) -> bool:
        """Send Slack notification (mock implementation)"""
        # In practice, this would integrate with Slack API
        logging.critical(f"SLACK ALERT: Kill switch triggered - {event.description}")
        logging.critical(f"Channels: {', '.join(recipients)}")
        return True


class LiquidationEngine(ABC):
    """Abstract base class for liquidation execution"""
    
    @abstractmethod
    def execute_liquidation(self, orders: List[LiquidationOrder]) -> List[LiquidationResult]:
        """Execute liquidation orders"""
        pass
    
    @abstractmethod
    def estimate_liquidation_impact(self, orders: List[LiquidationOrder]) -> Dict[str, float]:
        """Estimate market impact of liquidation"""
        pass


class MockLiquidationEngine(LiquidationEngine):
    """Mock liquidation engine for demonstration"""
    
    def execute_liquidation(self, orders: List[LiquidationOrder]) -> List[LiquidationResult]:
        """Mock liquidation execution"""
        results = []
        
        for order in orders:
            # Simulate execution with some slippage
            executed_quantity = order.quantity * 0.95  # 5% execution shortfall
            market_impact = min(abs(order.quantity) * 0.001, order.max_market_impact)
            
            result = LiquidationResult(
                order_id=f"KILL_{order.symbol}_{int(time.time())}",
                symbol=order.symbol,
                quantity_requested=order.quantity,
                quantity_executed=executed_quantity,
                average_price=100.0,  # Mock price
                market_impact=market_impact,
                execution_time=2.5,  # Mock execution time
                status="EXECUTED"
            )
            results.append(result)
        
        return results
    
    def estimate_liquidation_impact(self, orders: List[LiquidationOrder]) -> Dict[str, float]:
        """Mock impact estimation"""
        impact_estimates = {}
        for order in orders:
            impact_estimates[order.symbol] = min(abs(order.quantity) * 0.001, order.max_market_impact)
        return impact_estimates


class KillSwitch:
    """
    Automatic position liquidation system
    
    The KillSwitch provides emergency risk protection through automatic position
    liquidation when critical risk thresholds are breached. It includes:
    - Real-time risk monitoring
    - Automatic trigger detection
    - Emergency liquidation execution
    - Stakeholder notification
    - Comprehensive audit logging
    """
    
    def __init__(self, 
                 liquidation_engine: LiquidationEngine,
                 notification_channels: List[NotificationChannel],
                 stakeholder_contacts: Dict[str, List[str]]):
        
        self.liquidation_engine = liquidation_engine
        self.notification_channels = notification_channels
        self.stakeholder_contacts = stakeholder_contacts
        
        self.status = KillSwitchStatus.ACTIVE
        self.event_history: List[KillSwitchEvent] = []
        self.liquidation_history: List[LiquidationResult] = []
        
        self.logger = logging.getLogger(__name__)
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        # Kill switch configuration
        self.triggers: Dict[KillSwitchTrigger, Dict] = {
            KillSwitchTrigger.VAR_BREACH: {
                'threshold': 0.05,  # 5% VaR limit
                'enabled': True,
                'severity': 'CRITICAL'
            },
            KillSwitchTrigger.DRAWDOWN_LIMIT: {
                'threshold': 0.10,  # 10% drawdown limit
                'enabled': True,
                'severity': 'CRITICAL'
            },
            KillSwitchTrigger.CONCENTRATION_RISK: {
                'threshold': 0.20,  # 20% single position limit
                'enabled': True,
                'severity': 'HIGH'
            },
            KillSwitchTrigger.LIQUIDITY_CRISIS: {
                'threshold': 0.50,  # 50% liquidity threshold
                'enabled': True,
                'severity': 'CRITICAL'
            }
        }
    
    def start_monitoring(self, portfolio_monitor: Callable) -> None:
        """Start continuous risk monitoring"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self.logger.warning("Kill switch monitoring already running")
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitor_risk_levels,
            args=(portfolio_monitor,),
            daemon=True
        )
        self._monitoring_thread.start()
        self.logger.info("Kill switch monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop risk monitoring"""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5.0)
        self.logger.info("Kill switch monitoring stopped")
    
    def _monitor_risk_levels(self, portfolio_monitor: Callable) -> None:
        """Continuous risk level monitoring"""
        while not self._stop_monitoring.is_set():
            try:
                # Get current portfolio metrics
                metrics = portfolio_monitor()
                
                # Check each trigger condition
                for trigger_type, config in self.triggers.items():
                    if config['enabled'] and self._check_trigger_condition(trigger_type, metrics, config):
                        self._execute_kill_switch(trigger_type, metrics, config)
                        break  # Only trigger once per monitoring cycle
                
                # Sleep before next check
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error in kill switch monitoring: {e}")
                time.sleep(5.0)  # Longer sleep on error
    
    def _check_trigger_condition(self, trigger_type: KillSwitchTrigger, 
                                metrics: Dict[str, float], config: Dict) -> bool:
        """Check if trigger condition is met"""
        if trigger_type == KillSwitchTrigger.VAR_BREACH:
            return metrics.get('portfolio_var', 0.0) > config['threshold']
        
        elif trigger_type == KillSwitchTrigger.DRAWDOWN_LIMIT:
            return metrics.get('current_drawdown', 0.0) > config['threshold']
        
        elif trigger_type == KillSwitchTrigger.CONCENTRATION_RISK:
            max_position = max(metrics.get('position_concentrations', {}).values(), default=0.0)
            return max_position > config['threshold']
        
        elif trigger_type == KillSwitchTrigger.LIQUIDITY_CRISIS:
            return metrics.get('portfolio_liquidity', 1.0) < config['threshold']
        
        return False
    
    def trigger_kill_switch(self, trigger_type: KillSwitchTrigger, 
                           reason: str, triggered_by: str = "manual",
                           current_metrics: Optional[Dict[str, float]] = None) -> str:
        """Manually trigger kill switch"""
        if self.status == KillSwitchStatus.TRIGGERED:
            self.logger.warning("Kill switch already triggered")
            return "ALREADY_TRIGGERED"
        
        event = KillSwitchEvent(
            event_id=f"KILL_{int(time.time())}",
            trigger_type=trigger_type,
            timestamp=datetime.now(),
            severity="CRITICAL",
            description=reason,
            triggered_by=triggered_by,
            current_metrics=current_metrics or {}
        )
        
        return self._execute_kill_switch_from_event(event)
    
    def _execute_kill_switch(self, trigger_type: KillSwitchTrigger, 
                           metrics: Dict[str, float], config: Dict) -> str:
        """Execute kill switch from monitoring"""
        event = KillSwitchEvent(
            event_id=f"KILL_{int(time.time())}",
            trigger_type=trigger_type,
            timestamp=datetime.now(),
            severity=config['severity'],
            description=f"Automatic trigger: {trigger_type.value}",
            triggered_by="system",
            current_metrics=metrics,
            threshold_breached=str(config['threshold'])
        )
        
        return self._execute_kill_switch_from_event(event)
    
    def _execute_kill_switch_from_event(self, event: KillSwitchEvent) -> str:
        """Execute kill switch from event"""
        try:
            # Update status
            self.status = KillSwitchStatus.TRIGGERED
            self.event_history.append(event)
            
            self.logger.critical(f"KILL SWITCH TRIGGERED: {event.description}")
            
            # Immediate stakeholder notification
            self._notify_stakeholders(event)
            
            # Execute emergency liquidation
            self.status = KillSwitchStatus.EXECUTING
            liquidation_results = self._execute_emergency_liquidation(event)
            
            # Update status based on results
            if all(result.status == "EXECUTED" for result in liquidation_results):
                self.status = KillSwitchStatus.COMPLETED
                self.logger.info("Kill switch execution completed successfully")
            else:
                self.status = KillSwitchStatus.FAILED
                self.logger.error("Kill switch execution failed or partially failed")
            
            # Final notification with results
            self._notify_execution_complete(event, liquidation_results)
            
            return event.event_id
            
        except Exception as e:
            self.status = KillSwitchStatus.FAILED
            self.logger.error(f"Kill switch execution failed: {e}")
            return "EXECUTION_FAILED"
    
    def _notify_stakeholders(self, event: KillSwitchEvent) -> None:
        """Send immediate notifications to all stakeholders"""
        for channel in self.notification_channels:
            try:
                # Notify all stakeholder groups for critical events
                all_contacts = []
                for contact_list in self.stakeholder_contacts.values():
                    all_contacts.extend(contact_list)
                
                channel.send_notification(event, all_contacts)
                
            except Exception as e:
                self.logger.error(f"Failed to send notification via {channel.__class__.__name__}: {e}")
    
    def _execute_emergency_liquidation(self, event: KillSwitchEvent) -> List[LiquidationResult]:
        """Execute emergency portfolio liquidation"""
        # In practice, this would get current positions from portfolio system
        # For now, we'll create mock liquidation orders
        
        liquidation_orders = self._create_liquidation_orders(event)
        
        self.logger.info(f"Executing emergency liquidation: {len(liquidation_orders)} orders")
        
        # Execute liquidation
        results = self.liquidation_engine.execute_liquidation(liquidation_orders)
        self.liquidation_history.extend(results)
        
        return results
    
    def _create_liquidation_orders(self, event: KillSwitchEvent) -> List[LiquidationOrder]:
        """Create liquidation orders based on trigger type"""
        # Mock implementation - would get real positions in practice
        orders = []
        
        if event.trigger_type == KillSwitchTrigger.CONCENTRATION_RISK:
            # Liquidate concentrated positions only
            orders.append(LiquidationOrder(
                symbol="CONCENTRATED_STOCK",
                quantity=-1000,  # Sell 1000 shares
                order_type="MARKET",
                urgency="HIGH",
                max_market_impact=0.02
            ))
        else:
            # Full portfolio liquidation for critical triggers
            mock_positions = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
            for symbol in mock_positions:
                orders.append(LiquidationOrder(
                    symbol=symbol,
                    quantity=-500,  # Sell 500 shares each
                    order_type="MARKET",
                    urgency="CRITICAL",
                    max_market_impact=0.05
                ))
        
        return orders
    
    def _notify_execution_complete(self, event: KillSwitchEvent, 
                                 results: List[LiquidationResult]) -> None:
        """Notify stakeholders of execution completion"""
        total_executed = sum(result.quantity_executed for result in results)
        total_impact = sum(result.market_impact for result in results)
        
        completion_event = KillSwitchEvent(
            event_id=f"{event.event_id}_COMPLETE",
            trigger_type=event.trigger_type,
            timestamp=datetime.now(),
            severity="INFO",
            description=f"Kill switch execution completed. Liquidated {total_executed:.0f} shares with {total_impact:.2%} market impact",
            triggered_by="system",
            current_metrics={"total_executed": total_executed, "total_impact": total_impact}
        )
        
        self._notify_stakeholders(completion_event)
    
    def get_status(self) -> Dict[str, any]:
        """Get current kill switch status"""
        return {
            'status': self.status.value,
            'last_event': self.event_history[-1] if self.event_history else None,
            'total_events': len(self.event_history),
            'total_liquidations': len(self.liquidation_history),
            'triggers_enabled': {k.value: v['enabled'] for k, v in self.triggers.items()},
            'monitoring_active': self._monitoring_thread and self._monitoring_thread.is_alive()
        }
    
    def reset_kill_switch(self, authorized_by: str) -> bool:
        """Reset kill switch to active status (requires authorization)"""
        if self.status in [KillSwitchStatus.COMPLETED, KillSwitchStatus.FAILED]:
            self.status = KillSwitchStatus.ACTIVE
            
            reset_event = KillSwitchEvent(
                event_id=f"RESET_{int(time.time())}",
                trigger_type=KillSwitchTrigger.MANUAL_OVERRIDE,
                timestamp=datetime.now(),
                severity="INFO",
                description=f"Kill switch reset by {authorized_by}",
                triggered_by=authorized_by,
                current_metrics={}
            )
            
            self.event_history.append(reset_event)
            self.logger.info(f"Kill switch reset by {authorized_by}")
            return True
        
        return False
    
    def update_trigger_config(self, trigger_type: KillSwitchTrigger, 
                            config: Dict) -> None:
        """Update trigger configuration"""
        if trigger_type in self.triggers:
            self.triggers[trigger_type].update(config)
            self.logger.info(f"Updated trigger config for {trigger_type.value}")
    
    def disable_trigger(self, trigger_type: KillSwitchTrigger) -> None:
        """Disable specific trigger"""
        if trigger_type in self.triggers:
            self.triggers[trigger_type]['enabled'] = False
            self.logger.warning(f"Disabled kill switch trigger: {trigger_type.value}")
    
    def enable_trigger(self, trigger_type: KillSwitchTrigger) -> None:
        """Enable specific trigger"""
        if trigger_type in self.triggers:
            self.triggers[trigger_type]['enabled'] = True
            self.logger.info(f"Enabled kill switch trigger: {trigger_type.value}")
    
    def get_event_history(self, limit: Optional[int] = None) -> List[KillSwitchEvent]:
        """Get kill switch event history"""
        if limit:
            return self.event_history[-limit:]
        return self.event_history.copy()
    
    def get_liquidation_history(self, limit: Optional[int] = None) -> List[LiquidationResult]:
        """Get liquidation execution history"""
        if limit:
            return self.liquidation_history[-limit:]
        return self.liquidation_history.copy()