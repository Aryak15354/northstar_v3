"""
Unified State Management System

This module provides the core state management infrastructure for Northstar V3,
implementing temporal protection, event-driven updates, and comprehensive audit trails.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum


class StateEventType(Enum):
    """Types of state events"""
    DATA_UPDATE = "data_update"
    POSITION_CHANGE = "position_change"
    RISK_UPDATE = "risk_update"
    PERFORMANCE_UPDATE = "performance_update"
    SYSTEM_EVENT = "system_event"


@dataclass
class StateEvent:
    """Immutable state event record"""
    event_id: str
    event_type: StateEventType
    timestamp: datetime
    source: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class TemporalGuard:
    """
    Temporal protection system preventing future data access
    """
    
    def __init__(self, current_time: datetime):
        self.current_time = current_time
    
    def validate_access(self, data_timestamp: datetime) -> bool:
        """Validate that data access is not from the future"""
        return data_timestamp <= self.current_time
    
    def update_current_time(self, new_time: datetime) -> None:
        """Update current time (must be monotonically increasing)"""
        if new_time < self.current_time:
            raise ValueError("Time cannot move backwards")
        self.current_time = new_time


class StateSnapshot:
    """
    Immutable point-in-time state snapshot
    """
    
    def __init__(self, timestamp: datetime, state_data: Dict[str, Any]):
        self.timestamp = timestamp
        self.state_data = state_data.copy()  # Defensive copy
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from snapshot"""
        return self.state_data.get(key, default)
    
    def keys(self) -> List[str]:
        """Get all keys in snapshot"""
        return list(self.state_data.keys())


class EventBus:
    """
    Event bus for coordinating state changes
    """
    
    def __init__(self):
        self._subscribers: Dict[StateEventType, List[callable]] = {}
        self._event_history: List[StateEvent] = []
    
    def subscribe(self, event_type: StateEventType, callback: callable) -> None:
        """Subscribe to state events"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
    
    def publish(self, event: StateEvent) -> None:
        """Publish state event to subscribers"""
        self._event_history.append(event)
        
        if event.event_type in self._subscribers:
            for callback in self._subscribers[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    # Log error but don't stop other subscribers
                    print(f"Error in event subscriber: {e}")
    
    def get_event_history(self, 
                         event_type: Optional[StateEventType] = None,
                         since: Optional[datetime] = None) -> List[StateEvent]:
        """Get filtered event history"""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        return events


class UnifiedState:
    """
    Central state management system with temporal protection
    
    This is the single source of truth for all system state, providing:
    - Temporal integrity with no-lookahead protection
    - Event-driven state updates with audit trails
    - Point-in-time state snapshots
    - Rollback capabilities for error recovery
    """
    
    def __init__(self, initial_time: datetime):
        self._temporal_guard = TemporalGuard(initial_time)
        self._event_bus = EventBus()
        self._current_state: Dict[str, Any] = {}
        self._state_history: List[StateSnapshot] = []
        self._audit_trail: List[Dict[str, Any]] = []
    
    @property
    def current_time(self) -> datetime:
        """Get current system time"""
        return self._temporal_guard.current_time
    
    def advance_time(self, new_time: datetime) -> None:
        """Advance system time (must be monotonically increasing)"""
        old_time = self.current_time
        self._temporal_guard.update_current_time(new_time)
        
        # Create audit record
        self._audit_trail.append({
            'action': 'time_advance',
            'old_time': old_time,
            'new_time': new_time,
            'timestamp': new_time
        })
    
    def update_state(self, key: str, value: Any, source: str = "system") -> None:
        """Update state value with audit trail"""
        old_value = self._current_state.get(key)
        self._current_state[key] = value
        
        # Create state event
        event = StateEvent(
            event_id=f"{key}_{self.current_time.isoformat()}",
            event_type=StateEventType.DATA_UPDATE,
            timestamp=self.current_time,
            source=source,
            data={'key': key, 'old_value': old_value, 'new_value': value}
        )
        
        # Publish event
        self._event_bus.publish(event)
        
        # Create audit record
        self._audit_trail.append({
            'action': 'state_update',
            'key': key,
            'old_value': old_value,
            'new_value': value,
            'source': source,
            'timestamp': self.current_time
        })
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get current state value"""
        return self._current_state.get(key, default)
    
    def create_snapshot(self) -> StateSnapshot:
        """Create immutable point-in-time snapshot"""
        snapshot = StateSnapshot(self.current_time, self._current_state)
        self._state_history.append(snapshot)
        return snapshot
    
    def get_historical_snapshot(self, timestamp: datetime) -> Optional[StateSnapshot]:
        """Get historical state snapshot closest to timestamp"""
        # Validate temporal access
        if not self._temporal_guard.validate_access(timestamp):
            raise ValueError(f"Cannot access future state: {timestamp}")
        
        # Find closest snapshot
        closest_snapshot = None
        for snapshot in self._state_history:
            if snapshot.timestamp <= timestamp:
                if not closest_snapshot or snapshot.timestamp > closest_snapshot.timestamp:
                    closest_snapshot = snapshot
        
        return closest_snapshot
    
    def subscribe_to_events(self, event_type: StateEventType, callback: callable) -> None:
        """Subscribe to state events"""
        self._event_bus.subscribe(event_type, callback)
    
    def get_audit_trail(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get audit trail records"""
        if since is None:
            return self._audit_trail.copy()
        
        return [record for record in self._audit_trail 
                if record['timestamp'] >= since]
    
    def rollback_to_snapshot(self, snapshot: StateSnapshot) -> None:
        """Rollback state to previous snapshot (emergency use only)"""
        if snapshot.timestamp > self.current_time:
            raise ValueError("Cannot rollback to future snapshot")
        
        # Restore state
        self._current_state = snapshot.state_data.copy()
        
        # Create audit record
        self._audit_trail.append({
            'action': 'rollback',
            'target_timestamp': snapshot.timestamp,
            'rollback_timestamp': self.current_time
        })
        
        # Publish rollback event
        event = StateEvent(
            event_id=f"rollback_{self.current_time.isoformat()}",
            event_type=StateEventType.SYSTEM_EVENT,
            timestamp=self.current_time,
            source="system",
            data={'action': 'rollback', 'target_timestamp': snapshot.timestamp}
        )
        self._event_bus.publish(event)


class StateManager(ABC):
    """
    Abstract base class for state management components
    """
    
    def __init__(self, unified_state: UnifiedState):
        self.unified_state = unified_state
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize state manager"""
        pass
    
    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """Update managed state"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate current state"""
        pass


# Example usage and interfaces (not full implementations)
class PortfolioStateManager(StateManager):
    """Portfolio state management"""
    
    def initialize(self) -> None:
        """Initialize portfolio state"""
        self.unified_state.update_state('portfolio_positions', {}, 'portfolio_manager')
        self.unified_state.update_state('portfolio_cash', 0.0, 'portfolio_manager')
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update portfolio state"""
        if 'positions' in data:
            self.unified_state.update_state('portfolio_positions', data['positions'], 'portfolio_manager')
        if 'cash' in data:
            self.unified_state.update_state('portfolio_cash', data['cash'], 'portfolio_manager')
    
    def validate(self) -> bool:
        """Validate portfolio state consistency"""
        positions = self.unified_state.get_state('portfolio_positions', {})
        cash = self.unified_state.get_state('portfolio_cash', 0.0)
        
        # Basic validation logic
        return isinstance(positions, dict) and isinstance(cash, (int, float))


class RiskStateManager(StateManager):
    """Risk metrics state management"""
    
    def initialize(self) -> None:
        """Initialize risk state"""
        self.unified_state.update_state('portfolio_var', 0.0, 'risk_manager')
        self.unified_state.update_state('risk_limits', {}, 'risk_manager')
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update risk state"""
        if 'var' in data:
            self.unified_state.update_state('portfolio_var', data['var'], 'risk_manager')
        if 'limits' in data:
            self.unified_state.update_state('risk_limits', data['limits'], 'risk_manager')
    
    def validate(self) -> bool:
        """Validate risk state consistency"""
        var = self.unified_state.get_state('portfolio_var', 0.0)
        limits = self.unified_state.get_state('risk_limits', {})
        
        # Basic validation logic
        return isinstance(var, (int, float)) and isinstance(limits, dict)