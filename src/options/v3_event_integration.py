"""
V3 Event Bus Integration for Options Trading

This module integrates options trading events with Northstar V3's event bus system.
All options state changes, regime transitions, trade signals, and kill switch activations
are published to the event bus for:
- Real-time dashboard updates
- Audit trail and replay
- Post-mortem analysis
- Cross-system coordination

Event Types:
- OPTIONS_REGIME_CHANGE: Options regime transitions
- OPTIONS_TRADE_SIGNAL: Trade signals generated
- OPTIONS_POSITION_UPDATE: Position state changes
- OPTIONS_KILL_SWITCH: Kill switch activations
- OPTIONS_GREEKS_BREACH: Portfolio Greeks violations
- OPTIONS_EDGE_DECAY: Strategy edge decay detected

Philosophy: Auditable behavior through immutable event stream.
Every decision is recorded, every action is traceable.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict

# Import V3 event bus
try:
    from src.core.events import EventBus, Event, EventType, EventPriority
    V3_EVENT_BUS_AVAILABLE = True
except ImportError:
    try:
        from core.events import EventBus, Event, EventType, EventPriority
        V3_EVENT_BUS_AVAILABLE = True
    except ImportError:
        # Fallback for testing
        V3_EVENT_BUS_AVAILABLE = False
        
        class EventBus:
            def __init__(self):
                self.events = []
            
            def publish(self, event_type, data):
                self.events.append({'type': event_type, 'data': data, 'timestamp': datetime.now()})
            
            def emit(self, event_type, **kwargs):
                self.events.append({'type': event_type, 'data': kwargs, 'timestamp': datetime.now()})
        
        class Event:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        
        class EventType:
            CUSTOM = "custom"
        
        class EventPriority:
            HIGH = "high"
            NORMAL = "normal"
            LOW = "low"

logger = logging.getLogger("options.events")


class OptionsEventType(Enum):
    """Options-specific event types"""
    REGIME_CHANGE = "options_regime_change"
    TRADE_SIGNAL = "options_trade_signal"
    POSITION_OPENED = "options_position_opened"
    POSITION_UPDATED = "options_position_updated"
    POSITION_CLOSED = "options_position_closed"
    KILL_SWITCH_ACTIVATED = "options_kill_switch_activated"
    KILL_SWITCH_CLEARED = "options_kill_switch_cleared"
    GREEKS_BREACH = "options_greeks_breach"
    EDGE_DECAY = "options_edge_decay"
    STRATEGY_FATIGUE = "options_strategy_fatigue"
    ELIGIBILITY_REJECTED = "options_eligibility_rejected"
    RISK_VALIDATOR_REJECTED = "options_risk_validator_rejected"


@dataclass
class OptionsEvent:
    """Base options event"""
    event_type: OptionsEventType
    timestamp: datetime
    data: Dict[str, Any]
    priority: str = "normal"
    source: str = "options_trading_system"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'priority': self.priority,
            'source': self.source
        }


class OptionsEventPublisher:
    """
    Publishes options trading events to V3 event bus
    
    This class acts as the bridge between options trading components
    and the V3 event bus. It ensures all options events are properly
    formatted and published for system-wide visibility.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize event publisher
        
        Args:
            event_bus: V3 EventBus instance (optional, will create if not provided)
        """
        if event_bus:
            self.event_bus = event_bus
        elif V3_EVENT_BUS_AVAILABLE:
            self.event_bus = EventBus()
        else:
            # Fallback event bus for testing
            self.event_bus = EventBus()
        
        self.events_published = 0
        logger.info("OptionsEventPublisher initialized")
    
    def publish_regime_change(
        self,
        old_regime: str,
        new_regime: str,
        iv_rank: float,
        days_in_old_regime: int,
        reason: str
    ) -> None:
        """
        Publish regime change event
        
        Args:
            old_regime: Previous regime
            new_regime: New regime
            iv_rank: Current IV rank
            days_in_old_regime: Days spent in old regime
            reason: Reason for regime change
        """
        event = OptionsEvent(
            event_type=OptionsEventType.REGIME_CHANGE,
            timestamp=datetime.now(),
            data={
                'old_regime': old_regime,
                'new_regime': new_regime,
                'iv_rank': iv_rank,
                'days_in_old_regime': days_in_old_regime,
                'reason': reason
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.info(f"Regime change: {old_regime} → {new_regime} (IV rank: {iv_rank:.1%})")
    
    def publish_trade_signal(
        self,
        strategy_type: str,
        regime: str,
        max_loss: float,
        max_profit: float,
        edge_score: float,
        legs: List[Dict[str, Any]]
    ) -> None:
        """
        Publish trade signal event
        
        Args:
            strategy_type: Type of strategy (IRON_CONDOR, etc.)
            regime: Current regime
            max_loss: Maximum loss for strategy
            max_profit: Maximum profit for strategy
            edge_score: Estimated edge score
            legs: Strategy legs details
        """
        event = OptionsEvent(
            event_type=OptionsEventType.TRADE_SIGNAL,
            timestamp=datetime.now(),
            data={
                'strategy_type': strategy_type,
                'regime': regime,
                'max_loss': max_loss,
                'max_profit': max_profit,
                'edge_score': edge_score,
                'legs': legs
            },
            priority='normal'
        )
        
        self._publish_event(event)
        logger.info(f"Trade signal: {strategy_type} in {regime} regime (edge: {edge_score:.2f})")
    
    def publish_position_opened(
        self,
        position_id: str,
        strategy_type: str,
        max_loss: float,
        entry_time: datetime,
        legs: List[Dict[str, Any]]
    ) -> None:
        """
        Publish position opened event
        
        Args:
            position_id: Unique position ID
            strategy_type: Type of strategy
            max_loss: Maximum loss
            entry_time: Entry timestamp
            legs: Position legs
        """
        event = OptionsEvent(
            event_type=OptionsEventType.POSITION_OPENED,
            timestamp=datetime.now(),
            data={
                'position_id': position_id,
                'strategy_type': strategy_type,
                'max_loss': max_loss,
                'entry_time': entry_time.isoformat(),
                'legs': legs
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.info(f"Position opened: {position_id} ({strategy_type})")
    
    def publish_position_updated(
        self,
        position_id: str,
        unrealized_pnl: float,
        current_value: float,
        portfolio_greeks: Dict[str, float]
    ) -> None:
        """
        Publish position update event
        
        Args:
            position_id: Position ID
            unrealized_pnl: Current unrealized P&L
            current_value: Current position value
            portfolio_greeks: Portfolio-level Greeks
        """
        event = OptionsEvent(
            event_type=OptionsEventType.POSITION_UPDATED,
            timestamp=datetime.now(),
            data={
                'position_id': position_id,
                'unrealized_pnl': unrealized_pnl,
                'current_value': current_value,
                'portfolio_greeks': portfolio_greeks
            },
            priority='low'
        )
        
        self._publish_event(event)
        logger.debug(f"Position updated: {position_id} (P&L: ₹{unrealized_pnl:,.0f})")
    
    def publish_position_closed(
        self,
        position_id: str,
        strategy_type: str,
        realized_pnl: float,
        net_pnl: float,
        exit_reason: str,
        hold_duration_days: float,
        hold_duration_minutes: Optional[float] = None,
    ) -> None:
        """
        Publish position closed event
        
        Args:
            position_id: Position ID
            strategy_type: Type of strategy
            realized_pnl: Realized P&L (gross)
            net_pnl: Net P&L (after costs and tax)
            exit_reason: Reason for exit
            hold_duration_days: Days held
            hold_duration_minutes: Intraday hold length for evidence filtering
        """
        event = OptionsEvent(
            event_type=OptionsEventType.POSITION_CLOSED,
            timestamp=datetime.now(),
            data={
                'position_id': position_id,
                'strategy_type': strategy_type,
                'realized_pnl': realized_pnl,
                'net_pnl': net_pnl,
                'exit_reason': exit_reason,
                'hold_duration_days': hold_duration_days,
                'hold_duration_minutes': hold_duration_minutes,
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.info(
            f"Position closed: {position_id} ({strategy_type}) - "
            f"Net P&L: ₹{net_pnl:,.0f}, Reason: {exit_reason}"
        )
    
    def publish_kill_switch_activated(
        self,
        kill_switch_type: str,
        reason: str,
        cooldown_until: Optional[datetime] = None,
        triggered_rules: List[str] = None
    ) -> None:
        """
        Publish kill switch activation event
        
        Args:
            kill_switch_type: Type of kill switch
            reason: Reason for activation
            cooldown_until: Cooldown expiry time
            triggered_rules: List of triggered rules
        """
        event = OptionsEvent(
            event_type=OptionsEventType.KILL_SWITCH_ACTIVATED,
            timestamp=datetime.now(),
            data={
                'kill_switch_type': kill_switch_type,
                'reason': reason,
                'cooldown_until': cooldown_until.isoformat() if cooldown_until else None,
                'triggered_rules': triggered_rules or []
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.critical(f"KILL SWITCH ACTIVATED: {kill_switch_type} - {reason}")
    
    def publish_kill_switch_cleared(
        self,
        kill_switch_type: str,
        reason: str
    ) -> None:
        """
        Publish kill switch cleared event
        
        Args:
            kill_switch_type: Type of kill switch
            reason: Reason for clearing
        """
        event = OptionsEvent(
            event_type=OptionsEventType.KILL_SWITCH_CLEARED,
            timestamp=datetime.now(),
            data={
                'kill_switch_type': kill_switch_type,
                'reason': reason
            },
            priority='normal'
        )
        
        self._publish_event(event)
        logger.info(f"Kill switch cleared: {kill_switch_type} - {reason}")
    
    def publish_greeks_breach(
        self,
        greek_type: str,
        current_value: float,
        threshold: float,
        severity: str
    ) -> None:
        """
        Publish portfolio Greeks breach event
        
        Args:
            greek_type: Type of Greek (delta, gamma, vega, theta)
            current_value: Current value
            threshold: Threshold breached
            severity: Severity level
        """
        event = OptionsEvent(
            event_type=OptionsEventType.GREEKS_BREACH,
            timestamp=datetime.now(),
            data={
                'greek_type': greek_type,
                'current_value': current_value,
                'threshold': threshold,
                'severity': severity
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.warning(
            f"Greeks breach: {greek_type} = {current_value:.2f} "
            f"(threshold: {threshold:.2f})"
        )
    
    def publish_edge_decay(
        self,
        strategy_type: str,
        win_rate: float,
        historical_win_rate: float,
        avg_profit: float,
        historical_avg_profit: float
    ) -> None:
        """
        Publish edge decay event
        
        Args:
            strategy_type: Type of strategy
            win_rate: Current win rate
            historical_win_rate: Historical win rate
            avg_profit: Current average profit
            historical_avg_profit: Historical average profit
        """
        event = OptionsEvent(
            event_type=OptionsEventType.EDGE_DECAY,
            timestamp=datetime.now(),
            data={
                'strategy_type': strategy_type,
                'win_rate': win_rate,
                'historical_win_rate': historical_win_rate,
                'avg_profit': avg_profit,
                'historical_avg_profit': historical_avg_profit,
                'decay_percentage': (historical_win_rate - win_rate) / historical_win_rate if historical_win_rate > 0 else 0
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.warning(f"Edge decay detected: {strategy_type} strategy")
    
    def publish_eligibility_rejected(
        self,
        strategy_type: str,
        violations: List[str],
        regime: str
    ) -> None:
        """
        Publish trade eligibility rejection event
        
        Args:
            strategy_type: Type of strategy
            violations: List of violations
            regime: Current regime
        """
        event = OptionsEvent(
            event_type=OptionsEventType.ELIGIBILITY_REJECTED,
            timestamp=datetime.now(),
            data={
                'strategy_type': strategy_type,
                'violations': violations,
                'regime': regime
            },
            priority='normal'
        )
        
        self._publish_event(event)
        logger.info(f"Trade rejected: {strategy_type} - {len(violations)} violations")
    
    def publish_risk_validator_rejected(
        self,
        strategy_type: str,
        violations: List[str],
        decision: str
    ) -> None:
        """
        Publish risk validator rejection event
        
        Args:
            strategy_type: Type of strategy
            violations: List of violations
            decision: Risk decision
        """
        event = OptionsEvent(
            event_type=OptionsEventType.RISK_VALIDATOR_REJECTED,
            timestamp=datetime.now(),
            data={
                'strategy_type': strategy_type,
                'violations': violations,
                'decision': decision
            },
            priority='high'
        )
        
        self._publish_event(event)
        logger.warning(f"Risk validator rejected: {strategy_type} - {decision}")
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """
        Get event publishing statistics
        
        Returns:
            Dict with event statistics
        """
        return {
            'total_events_published': self.events_published,
            'event_bus_available': V3_EVENT_BUS_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }
    
    def _publish_event(self, event: OptionsEvent) -> None:
        """
        Internal method to publish event to event bus
        
        Args:
            event: OptionsEvent to publish
        """
        try:
            # Publish to V3 event bus
            if hasattr(self.event_bus, 'emit'):
                # EventBus.emit() style
                self.event_bus.emit(
                    event_type=event.event_type.value,
                    source=event.source,
                    priority=event.priority,
                    **event.data
                )
            elif hasattr(self.event_bus, 'publish'):
                # EventBus.publish() style
                self.event_bus.publish(
                    event_type=event.event_type.value,
                    data=event.to_dict()
                )
            else:
                # Fallback: store in events list
                self.event_bus.events.append(event.to_dict())
            
            self.events_published += 1
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_type.value}: {e}")


def create_event_publisher(event_bus: Optional[EventBus] = None) -> OptionsEventPublisher:
    """
    Factory function to create event publisher
    
    Args:
        event_bus: V3 EventBus instance (optional)
    
    Returns:
        OptionsEventPublisher instance
    """
    return OptionsEventPublisher(event_bus=event_bus)


if __name__ == "__main__":
    # Test event publisher
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create publisher
    publisher = create_event_publisher()
    
    # Test regime change event
    publisher.publish_regime_change(
        old_regime="LOW_VOL_SELL",
        new_regime="HIGH_VOL_SELL",
        iv_rank=0.85,
        days_in_old_regime=12,
        reason="IV rank exceeded 80%"
    )
    
    # Test trade signal event
    publisher.publish_trade_signal(
        strategy_type="IRON_CONDOR",
        regime="HIGH_VOL_SELL",
        max_loss=5000.0,
        max_profit=2000.0,
        edge_score=0.75,
        legs=[
            {'strike': 25000, 'type': 'CE', 'action': 'SELL'},
            {'strike': 25500, 'type': 'CE', 'action': 'BUY'},
            {'strike': 24500, 'type': 'PE', 'action': 'SELL'},
            {'strike': 24000, 'type': 'PE', 'action': 'BUY'}
        ]
    )
    
    # Test kill switch event
    publisher.publish_kill_switch_activated(
        kill_switch_type="weekly_loss_limit",
        reason="Weekly loss exceeded 2% of capital",
        cooldown_until=datetime.now(),
        triggered_rules=["weekly_loss_limit"]
    )
    
    # Get statistics
    stats = publisher.get_event_statistics()
    print(f"\nEvent Statistics:")
    print(f"  Total Events Published: {stats['total_events_published']}")
    print(f"  Event Bus Available: {stats['event_bus_available']}")
