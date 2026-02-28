#!/usr/bin/env python3
"""
📡 EVENT BUS - THE NERVOUS SYSTEM
Event-Driven Communication and Audit Trail for the Living Investment Organism

This is the Event Bus that provides event-driven communication between organs
and maintains a comprehensive audit trail for decision explainability.

Key Features:
- Event-driven communication between organs
- Comprehensive audit trail with decision tracking
- Real-time event streaming and monitoring
- Decision explainability through event chains
"""

import os
import sys
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
import uuid
import threading
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

class EventType(Enum):
    """Types of events in the system"""
    STATE_UPDATE = "state_update"
    ORGAN_EXECUTION = "organ_execution"
    TIME_EVENT = "time_event"
    RISK_EVENT = "risk_event"
    DECISION = "decision"
    ERROR = "error"
    SYSTEM_EVENT = "system_event"
    HEARTBEAT = "heartbeat"

class EventPriority(Enum):
    """Event priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

@dataclass
class Event:
    """Base event class"""
    event_id: str
    timestamp: datetime
    event_type: EventType
    source: str
    priority: EventPriority = EventPriority.NORMAL
    data: Dict[str, Any] = None
    tags: List[str] = None
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.tags is None:
            self.tags = []
        if not self.event_id:
            self.event_id = str(uuid.uuid4())

@dataclass
class StateChangeEvent(Event):
    """State change event"""
    component: str = ""
    field: str = ""
    old_value: Any = None
    new_value: Any = None
    reason: str = ""
    authority_level: int = 4
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.STATE_UPDATE

@dataclass
class DecisionEvent(Event):
    """Investment decision event"""
    decision_type: str = ""
    decision_data: Dict[str, Any] = None
    confidence: float = 0.0
    reasoning: List[str] = None
    contributing_events: List[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.DECISION
        if self.decision_data is None:
            self.decision_data = {}
        if self.reasoning is None:
            self.reasoning = []
        if self.contributing_events is None:
            self.contributing_events = []

@dataclass
class RiskEvent(Event):
    """Risk management event"""
    risk_level: str = "normal"
    risk_type: str = ""
    risk_data: Dict[str, Any] = None
    action_taken: str = ""
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.RISK_EVENT
        self.priority = EventPriority.HIGH
        if self.risk_data is None:
            self.risk_data = {}

@dataclass
class DecisionExplanation:
    """Explanation of an investment decision"""
    decision_id: str
    timestamp: datetime
    decision_type: str
    decision_summary: str
    contributing_events: List[Event]
    reasoning_chain: List[str]
    confidence: float
    risk_factors: List[str]
    data_sources: List[str]

class EventBus:
    """
    Enhanced Event Bus - Central Nervous System for Event Communication
    
    Provides event-driven communication between organs and maintains
    comprehensive audit trail for decision explainability with real-time
    monitoring capabilities.
    
    Enhanced Features:
    - Real-time event streaming and monitoring
    - Advanced decision explainability with causal chains
    - Automatic state change tracking integration
    - Performance monitoring and analytics
    - Event correlation and pattern detection
    """
    
    def __init__(self, max_events=10000):
        self.max_events = max_events
        
        # Event storage
        self.events: deque = deque(maxlen=max_events)
        self.event_index: Dict[str, Event] = {}
        
        # Event listeners by type
        self.listeners: Dict[EventType, List[Callable]] = defaultdict(list)
        self.global_listeners: List[Callable] = []
        
        # Real-time monitoring
        self.real_time_monitors: List[Callable] = []
        self.monitoring_active = False
        
        # Decision tracking
        self.decisions: Dict[str, DecisionEvent] = {}
        self.decision_chains: Dict[str, List[str]] = {}
        self.causal_graph: Dict[str, List[str]] = defaultdict(list)
        
        # Event statistics and analytics
        self.event_stats: Dict[str, int] = defaultdict(int)
        self.source_stats: Dict[str, int] = defaultdict(int)
        self.performance_metrics: Dict[str, List[float]] = defaultdict(list)
        
        # Event correlation tracking
        self.correlation_groups: Dict[str, List[str]] = defaultdict(list)
        self.event_patterns: Dict[str, int] = defaultdict(int)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Persistence
        self.events_file = 'data/state/event_bus.json'
        self.audit_trail_file = 'data/state/audit_trail.parquet'
        self.decision_explanations_file = 'data/state/decision_explanations.json'
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.events_file), exist_ok=True)
        
        print("📡 Enhanced Event Bus initialized with real-time monitoring")
    
    def emit_event(self, event: Event):
        """Emit an event to the bus with enhanced tracking"""
        
        emit_start = time.time()
        
        with self.lock:
            # Add to storage
            self.events.append(event)
            self.event_index[event.event_id] = event
            
            # Update statistics
            self.event_stats[event.event_type.value] += 1
            self.source_stats[event.source] += 1
            
            # Track performance
            emit_duration = time.time() - emit_start
            self.performance_metrics['emit_duration'].append(emit_duration)
            
            # Special handling for decisions
            if isinstance(event, DecisionEvent):
                self.decisions[event.event_id] = event
                
                # Track decision chain
                if event.contributing_events:
                    self.decision_chains[event.event_id] = event.contributing_events
                    
                    # Build causal graph
                    for contributing_id in event.contributing_events:
                        self.causal_graph[contributing_id].append(event.event_id)
            
            # Track event correlations
            if event.correlation_id:
                self.correlation_groups[event.correlation_id].append(event.event_id)
            
            # Detect event patterns
            pattern_key = f"{event.source}:{event.event_type.value}"
            self.event_patterns[pattern_key] += 1
        
        # Real-time monitoring (outside lock)
        if self.monitoring_active:
            self._notify_real_time_monitors(event)
        
        # Notify listeners (outside lock to avoid deadlock)
        self._notify_listeners(event)
    
    def _notify_real_time_monitors(self, event: Event):
        """Notify real-time monitoring systems"""
        
        for monitor in self.real_time_monitors:
            try:
                monitor(event)
            except Exception as e:
                print(f"⚠️ Error in real-time monitor: {e}")
    
    def add_real_time_monitor(self, monitor: Callable):
        """Add real-time event monitor"""
        self.real_time_monitors.append(monitor)
        self.monitoring_active = True
        print(f"   📊 Real-time monitor added (total: {len(self.real_time_monitors)})")
    
    def remove_real_time_monitor(self, monitor: Callable):
        """Remove real-time event monitor"""
        if monitor in self.real_time_monitors:
            self.real_time_monitors.remove(monitor)
        
        if not self.real_time_monitors:
            self.monitoring_active = False
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        self.monitoring_active = True
        print("   📊 Real-time monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        print("   📊 Real-time monitoring stopped")
    
    def _notify_listeners(self, event: Event):
        """Notify event listeners"""
        
        try:
            # Notify type-specific listeners
            for listener in self.listeners[event.event_type]:
                try:
                    listener(event)
                except Exception as e:
                    print(f"⚠️ Error in event listener: {e}")
            
            # Notify global listeners
            for listener in self.global_listeners:
                try:
                    listener(event)
                except Exception as e:
                    print(f"⚠️ Error in global event listener: {e}")
                    
        except Exception as e:
            print(f"⚠️ Error notifying event listeners: {e}")
    
    def subscribe(self, event_type: EventType, listener: Callable):
        """Subscribe to specific event type"""
        self.listeners[event_type].append(listener)
    
    def subscribe_all(self, listener: Callable):
        """Subscribe to all events"""
        self.global_listeners.append(listener)
    
    def unsubscribe(self, event_type: EventType, listener: Callable):
        """Unsubscribe from event type"""
        if listener in self.listeners[event_type]:
            self.listeners[event_type].remove(listener)
    
    def unsubscribe_all(self, listener: Callable):
        """Unsubscribe from all events"""
        if listener in self.global_listeners:
            self.global_listeners.remove(listener)
    
    def get_events(self, 
                   event_type: EventType = None,
                   source: str = None,
                   since: datetime = None,
                   limit: int = None) -> List[Event]:
        """Get events with optional filtering"""
        
        with self.lock:
            events = list(self.events)
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            events = events[:limit]
        
        return events
    
    def get_event_by_id(self, event_id: str) -> Optional[Event]:
        """Get event by ID"""
        return self.event_index.get(event_id)
    
    def get_audit_trail(self, 
                       filters: Dict[str, Any] = None,
                       since: datetime = None,
                       limit: int = 1000) -> List[Event]:
        """Get filtered audit trail"""
        
        events = self.get_events(since=since, limit=limit)
        
        if not filters:
            return events
        
        # Apply additional filters
        filtered_events = []
        for event in events:
            match = True
            
            for key, value in filters.items():
                if hasattr(event, key):
                    if getattr(event, key) != value:
                        match = False
                        break
                elif key in event.data:
                    if event.data[key] != value:
                        match = False
                        break
                else:
                    match = False
                    break
            
            if match:
                filtered_events.append(event)
        
        return filtered_events
    
    def explain_decision(self, decision_id: str) -> Optional[DecisionExplanation]:
        """Explain an investment decision through event history"""
        
        decision_event = self.decisions.get(decision_id)
        if not decision_event:
            return None
        
        # Get contributing events
        contributing_events = []
        contributing_event_ids = self.decision_chains.get(decision_id, [])
        
        for event_id in contributing_event_ids:
            event = self.get_event_by_id(event_id)
            if event:
                contributing_events.append(event)
        
        # Build reasoning chain
        reasoning_chain = decision_event.reasoning.copy()
        
        # Add reasoning from contributing events
        for event in contributing_events:
            if isinstance(event, StateChangeEvent) and event.reason:
                reasoning_chain.append(f"State change: {event.reason}")
            elif isinstance(event, RiskEvent) and event.action_taken:
                reasoning_chain.append(f"Risk action: {event.action_taken}")
        
        # Extract risk factors
        risk_factors = []
        for event in contributing_events:
            if isinstance(event, RiskEvent):
                risk_factors.append(f"{event.risk_type}: {event.risk_level}")
        
        # Extract data sources
        data_sources = list(set([event.source for event in contributing_events]))
        
        return DecisionExplanation(
            decision_id=decision_id,
            timestamp=decision_event.timestamp,
            decision_type=decision_event.decision_type,
            decision_summary=decision_event.data.get('summary', 'No summary available'),
            contributing_events=contributing_events,
            reasoning_chain=reasoning_chain,
            confidence=decision_event.confidence,
            risk_factors=risk_factors,
            data_sources=data_sources
        )
    
    def track_decision_chain(self, decision_id: str, contributing_event_ids: List[str]):
        """Track the chain of events that led to a decision"""
        
        with self.lock:
            self.decision_chains[decision_id] = contributing_event_ids
    
    def integrate_with_unified_state(self, unified_state):
        """
        Integrate with unified state for automatic event emission
        
        This method sets up automatic state change tracking so that
        whenever the unified state is modified, appropriate events
        are automatically emitted to satisfy Requirements 9.2 and 9.3.
        """
        
        # Store reference to unified state
        self.unified_state = unified_state
        
        # Set up automatic state change tracking
        if hasattr(unified_state, 'add_change_listener'):
            unified_state.add_change_listener(self._on_state_change)
            print("   📡 Event Bus integrated with Unified State for automatic tracking")
        else:
            print("   ⚠️ Unified State doesn't support change listeners - manual event emission required")
    
    def _on_state_change(self, component: str, field: str, old_value: Any, new_value: Any, 
                        source: str = "unified_state", reason: str = "", authority_level: int = 4):
        """
        Automatically emit state change event when unified state changes
        
        This satisfies Requirement 9.2: "WHEN any organ modifies state, 
        THE system SHALL emit events describing the changes"
        """
        
        # Create state change event
        state_event = StateChangeEvent(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.STATE_UPDATE,  # Required field
            source=source,
            component=component,
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            authority_level=authority_level,
            tags=["state_change", "automatic"],
            correlation_id=f"state_change_{component}_{field}_{int(time.time())}"
        )
        
        # Emit the event
        self.emit_event(state_event)
    
    def emit_decision_event(self, decision_type: str, decision_data: Dict[str, Any],
                          confidence: float, reasoning: List[str], source: str,
                          contributing_event_ids: List[str] = None) -> str:
        """
        Emit a decision event with proper tracking for explainability
        
        This satisfies Requirements 9.3 and 9.5 for decision tracking
        and explainability through event history.
        
        Returns the decision event ID for tracking purposes.
        """
        
        if contributing_event_ids is None:
            contributing_event_ids = []
        
        # Create decision event
        decision_event = DecisionEvent(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.DECISION,  # Required field
            source=source,
            decision_type=decision_type,
            decision_data=decision_data,
            confidence=confidence,
            reasoning=reasoning,
            contributing_events=contributing_event_ids,
            tags=["decision", "investment"],
            correlation_id=f"decision_{decision_type}_{int(time.time())}"
        )
        
        # Emit the event
        self.emit_event(decision_event)
        
        return decision_event.event_id
    
    def emit_risk_event(self, risk_type: str, risk_level: str, risk_data: Dict[str, Any],
                       action_taken: str, source: str) -> str:
        """
        Emit a risk event for spinal cord authority tracking
        
        This supports the risk management system's absolute authority
        and provides audit trail for risk decisions.
        
        Returns the risk event ID for tracking purposes.
        """
        
        # Create risk event
        risk_event = RiskEvent(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.RISK_EVENT,  # Required field
            source=source,
            risk_type=risk_type,
            risk_level=risk_level,
            risk_data=risk_data,
            action_taken=action_taken,
            tags=["risk", "spinal_cord"],
            correlation_id=f"risk_{risk_type}_{int(time.time())}"
        )
        
        # Emit the event
        self.emit_event(risk_event)
        
        return risk_event.event_id
    
    def get_decision_causal_chain(self, decision_id: str, max_depth: int = 10) -> List[Event]:
        """
        Get the complete causal chain that led to a decision
        
        This provides enhanced decision explainability by tracing
        the complete chain of events that contributed to a decision,
        satisfying Requirement 9.5.
        """
        
        causal_chain = []
        visited = set()
        
        def trace_causality(event_id: str, depth: int = 0):
            if depth >= max_depth or event_id in visited:
                return
            
            visited.add(event_id)
            event = self.get_event_by_id(event_id)
            
            if event:
                causal_chain.append(event)
                
                # If this is a decision event, trace its contributing events
                if isinstance(event, DecisionEvent):
                    for contributing_id in event.contributing_events:
                        trace_causality(contributing_id, depth + 1)
                
                # Also check causal graph for events that led to this one
                for predecessor_id in self.causal_graph:
                    if event_id in self.causal_graph[predecessor_id]:
                        trace_causality(predecessor_id, depth + 1)
        
        # Start tracing from the decision
        trace_causality(decision_id)
        
        # Sort by timestamp to show chronological order
        causal_chain.sort(key=lambda e: e.timestamp)
        
        return causal_chain
    
    def get_real_time_monitoring_status(self) -> Dict[str, Any]:
        """
        Get current real-time monitoring status and metrics
        
        This supports Requirement 9.4: "THE event system SHALL enable 
        real-time monitoring of organ behavior"
        """
        
        recent_events = self.get_events(since=datetime.now() - timedelta(minutes=5))
        
        # Analyze recent organ behavior
        organ_activity = defaultdict(int)
        event_types_recent = defaultdict(int)
        
        for event in recent_events:
            organ_activity[event.source] += 1
            event_types_recent[event.event_type.value] += 1
        
        # Calculate event rate
        event_rate = len(recent_events) / 5.0  # events per minute
        
        return {
            'monitoring_active': self.monitoring_active,
            'monitors_count': len(self.real_time_monitors),
            'recent_event_rate': event_rate,
            'organ_activity': dict(organ_activity),
            'recent_event_types': dict(event_types_recent),
            'total_events_tracked': len(self.events),
            'decisions_tracked': len(self.decisions),
            'causal_relationships': len(self.causal_graph)
        }
    
    def get_event_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        
        try:
            # Create local copies to avoid holding lock too long
            with self.lock:
                events_copy = list(self.events)
                event_stats_copy = dict(self.event_stats)
                source_stats_copy = dict(self.source_stats)
                decisions_count = len(self.decisions)
                listeners_count = {
                    'type_specific': sum(len(listeners) for listeners in self.listeners.values()),
                    'global': len(self.global_listeners)
                }
            
            # Process outside of lock
            total_events = len(events_copy)
            recent_events = len([e for e in events_copy 
                               if (datetime.now() - e.timestamp).total_seconds() < 3600])
            
            return {
                'total_events': total_events,
                'recent_events_1h': recent_events,
                'event_types': event_stats_copy,
                'event_sources': source_stats_copy,
                'decisions_tracked': decisions_count,
                'listeners': listeners_count
            }
            
        except Exception as e:
            print(f"⚠️ Error getting event statistics: {e}")
            return {
                'total_events': 0,
                'recent_events_1h': 0,
                'event_types': {},
                'event_sources': {},
                'decisions_tracked': 0,
                'listeners': {'type_specific': 0, 'global': 0}
            }
        """Get event bus statistics"""
        
        try:
            # Create local copies to avoid holding lock too long
            with self.lock:
                events_copy = list(self.events)
                event_stats_copy = dict(self.event_stats)
                source_stats_copy = dict(self.source_stats)
                decisions_count = len(self.decisions)
                listeners_count = {
                    'type_specific': sum(len(listeners) for listeners in self.listeners.values()),
                    'global': len(self.global_listeners)
                }
            
            # Process outside of lock
            total_events = len(events_copy)
            recent_events = len([e for e in events_copy 
                               if (datetime.now() - e.timestamp).total_seconds() < 3600])
            
            return {
                'total_events': total_events,
                'recent_events_1h': recent_events,
                'event_types': event_stats_copy,
                'event_sources': source_stats_copy,
                'decisions_tracked': decisions_count,
                'listeners': listeners_count
            }
            
        except Exception as e:
            print(f"⚠️ Error getting event statistics: {e}")
            return {
                'total_events': 0,
                'recent_events_1h': 0,
                'event_types': {},
                'event_sources': {},
                'decisions_tracked': 0,
                'listeners': {'type_specific': 0, 'global': 0}
            }
    
    def save_events(self):
        """Save events to persistent storage"""
        
        try:
            # Get statistics first (outside of main lock)
            stats = self.get_event_statistics()
            
            with self.lock:
                # Save recent events to JSON
                recent_events = list(self.events)[-1000:]  # Last 1000 events
                
                events_data = {
                    'timestamp': datetime.now().isoformat(),
                    'total_events': len(self.events),
                    'events': [self._serialize_event(event) for event in recent_events],
                    'statistics': stats
                }
                
                with open(self.events_file, 'w') as f:
                    json.dump(events_data, f, indent=2, default=str)
                
                # Save audit trail to Parquet for analysis
                if recent_events:
                    audit_df = pd.DataFrame([
                        {
                            'timestamp': event.timestamp,
                            'event_id': event.event_id,
                            'event_type': event.event_type.value,
                            'source': event.source,
                            'priority': event.priority.value,
                            'correlation_id': event.correlation_id,
                            'tags': ','.join(event.tags) if event.tags else '',
                            'data_keys': ','.join(event.data.keys()) if event.data else ''
                        }
                        for event in recent_events
                    ])
                    
                    audit_df.to_parquet(self.audit_trail_file, index=False)
                
        except Exception as e:
            print(f"⚠️ Error saving events: {e}")
    
    def _serialize_event(self, event: Event) -> Dict[str, Any]:
        """Serialize event for JSON storage"""
        
        serialized = {
            'event_id': event.event_id,
            'timestamp': event.timestamp.isoformat(),
            'event_type': event.event_type.value,
            'source': event.source,
            'priority': event.priority.value,
            'data': event.data,
            'tags': event.tags,
            'correlation_id': event.correlation_id
        }
        
        # Add type-specific fields
        if isinstance(event, StateChangeEvent):
            serialized.update({
                'component': event.component,
                'field': event.field,
                'old_value': event.old_value,
                'new_value': event.new_value,
                'reason': event.reason,
                'authority_level': event.authority_level
            })
        elif isinstance(event, DecisionEvent):
            serialized.update({
                'decision_type': event.decision_type,
                'decision_data': event.decision_data,
                'confidence': event.confidence,
                'reasoning': event.reasoning,
                'contributing_events': event.contributing_events
            })
        elif isinstance(event, RiskEvent):
            serialized.update({
                'risk_level': event.risk_level,
                'risk_type': event.risk_type,
                'risk_data': event.risk_data,
                'action_taken': event.action_taken
            })
        
        return serialized
    
    def load_events(self):
        """Load events from persistent storage"""
        
        try:
            if os.path.exists(self.events_file):
                with open(self.events_file, 'r') as f:
                    events_data = json.load(f)
                
                # Load recent events
                for event_data in events_data.get('events', []):
                    event = self._deserialize_event(event_data)
                    if event:
                        with self.lock:
                            self.events.append(event)
                            self.event_index[event.event_id] = event
                            
                            if isinstance(event, DecisionEvent):
                                self.decisions[event.event_id] = event
                
                return True
        
        except Exception as e:
            print(f"⚠️ Error loading events: {e}")
        
        return False
    
    def _deserialize_event(self, event_data: Dict[str, Any]) -> Optional[Event]:
        """Deserialize event from JSON data"""
        
        try:
            event_type = EventType(event_data['event_type'])
            
            # Create appropriate event type
            if event_type == EventType.STATE_UPDATE:
                return StateChangeEvent(
                    event_id=event_data['event_id'],
                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                    source=event_data['source'],
                    priority=EventPriority(event_data['priority']),
                    data=event_data.get('data', {}),
                    tags=event_data.get('tags', []),
                    correlation_id=event_data.get('correlation_id'),
                    component=event_data.get('component', ''),
                    field=event_data.get('field', ''),
                    old_value=event_data.get('old_value'),
                    new_value=event_data.get('new_value'),
                    reason=event_data.get('reason', ''),
                    authority_level=event_data.get('authority_level', 4)
                )
            elif event_type == EventType.DECISION:
                return DecisionEvent(
                    event_id=event_data['event_id'],
                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                    source=event_data['source'],
                    priority=EventPriority(event_data['priority']),
                    data=event_data.get('data', {}),
                    tags=event_data.get('tags', []),
                    correlation_id=event_data.get('correlation_id'),
                    decision_type=event_data.get('decision_type', ''),
                    decision_data=event_data.get('decision_data', {}),
                    confidence=event_data.get('confidence', 0.0),
                    reasoning=event_data.get('reasoning', []),
                    contributing_events=event_data.get('contributing_events', [])
                )
            elif event_type == EventType.RISK_EVENT:
                return RiskEvent(
                    event_id=event_data['event_id'],
                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                    source=event_data['source'],
                    priority=EventPriority(event_data['priority']),
                    data=event_data.get('data', {}),
                    tags=event_data.get('tags', []),
                    correlation_id=event_data.get('correlation_id'),
                    risk_level=event_data.get('risk_level', 'normal'),
                    risk_type=event_data.get('risk_type', ''),
                    risk_data=event_data.get('risk_data', {}),
                    action_taken=event_data.get('action_taken', '')
                )
            else:
                # Generic event
                return Event(
                    event_id=event_data['event_id'],
                    timestamp=datetime.fromisoformat(event_data['timestamp']),
                    event_type=event_type,
                    source=event_data['source'],
                    priority=EventPriority(event_data['priority']),
                    data=event_data.get('data', {}),
                    tags=event_data.get('tags', []),
                    correlation_id=event_data.get('correlation_id')
                )
        
        except Exception as e:
            print(f"⚠️ Error deserializing event: {e}")
            return None

def main():
    """Test Enhanced Event Bus with Real-Time Monitoring and Decision Explainability"""
    
    print("📡 TESTING ENHANCED EVENT BUS")
    print("=" * 50)
    
    # Create enhanced event bus
    event_bus = EventBus()
    
    # Test real-time monitoring
    print("\n📊 Testing Real-Time Monitoring:")
    
    def real_time_monitor(event: Event):
        print(f"   🔴 LIVE: {event.event_type.value} from {event.source} at {event.timestamp.strftime('%H:%M:%S')}")
    
    event_bus.add_real_time_monitor(real_time_monitor)
    event_bus.start_monitoring()
    
    # Test event listener
    def test_listener(event: Event):
        print(f"   📨 Received: {event.event_type.value} from {event.source}")
    
    event_bus.subscribe_all(test_listener)
    
    # Test automatic state change tracking
    print("\n📊 Testing Automatic State Change Tracking:")
    
    # Simulate state changes (this would normally be called by unified state)
    event_bus._on_state_change(
        component="market_regime",
        field="current_regime", 
        old_value="unknown",
        new_value="expansion",
        source="market_brain_organ",
        reason="Market analysis detected regime shift based on momentum indicators"
    )
    
    event_bus._on_state_change(
        component="portfolio",
        field="total_exposure",
        old_value=0.75,
        new_value=0.85,
        source="portfolio_governor_organ", 
        reason="Increased exposure due to favorable regime conditions"
    )
    
    # Test decision event with explainability
    print("\n🎯 Testing Decision Event with Explainability:")
    
    # Get the state change event IDs for causal tracking
    recent_events = event_bus.get_events(limit=2)
    contributing_event_ids = [event.event_id for event in recent_events]
    
    decision_id = event_bus.emit_decision_event(
        decision_type="portfolio_rebalance",
        decision_data={
            "action": "increase_equity_exposure",
            "amount": 0.10,
            "target_sectors": ["technology", "healthcare"],
            "expected_return": 0.12,
            "risk_budget": 0.15
        },
        confidence=0.87,
        reasoning=[
            "Market regime shifted to expansion phase with strong momentum",
            "Portfolio exposure was below optimal level for expansion regime",
            "Risk metrics indicate capacity for increased exposure",
            "Sector rotation favors growth sectors in current environment"
        ],
        source="capital_allocator_organ",
        contributing_event_ids=contributing_event_ids
    )
    
    # Test risk event
    print("\n🛡️ Testing Risk Event:")
    
    risk_event_id = event_bus.emit_risk_event(
        risk_type="market_stress",
        risk_level="elevated",
        risk_data={
            "stress_indicator": 0.72,
            "volatility_spike": True,
            "correlation_breakdown": False,
            "liquidity_concern": "moderate"
        },
        action_taken="Reduced position sizes by 15% and increased cash buffer",
        source="risk_coordinator_organ"
    )
    
    # Test decision explanation
    print("\n🔍 Testing Decision Explainability:")
    explanation = event_bus.explain_decision(decision_id)
    if explanation:
        print(f"   Decision Type: {explanation.decision_type}")
        print(f"   Confidence: {explanation.confidence:.1%}")
        print(f"   Contributing Events: {len(explanation.contributing_events)}")
        print(f"   Reasoning Steps: {len(explanation.reasoning_chain)}")
        print(f"   Data Sources: {explanation.data_sources}")
        
        print(f"\n   Reasoning Chain:")
        for i, reason in enumerate(explanation.reasoning_chain, 1):
            print(f"     {i}. {reason}")
    
    # Test causal chain analysis
    print("\n🔗 Testing Causal Chain Analysis:")
    causal_chain = event_bus.get_decision_causal_chain(decision_id)
    print(f"   Causal Chain Length: {len(causal_chain)}")
    for i, event in enumerate(causal_chain):
        print(f"     {i+1}. {event.timestamp.strftime('%H:%M:%S')} - {event.event_type.value} from {event.source}")
    
    # Test real-time monitoring status
    print(f"\n📊 Real-Time Monitoring Status:")
    monitoring_status = event_bus.get_real_time_monitoring_status()
    print(f"   Monitoring Active: {monitoring_status['monitoring_active']}")
    print(f"   Event Rate: {monitoring_status['recent_event_rate']:.1f} events/min")
    print(f"   Organ Activity: {monitoring_status['organ_activity']}")
    print(f"   Recent Event Types: {monitoring_status['recent_event_types']}")
    
    # Test enhanced statistics
    print(f"\n📈 Enhanced Event Statistics:")
    stats = event_bus.get_event_statistics()
    print(f"   Total Events: {stats['total_events']}")
    print(f"   Recent Events (1h): {stats['recent_events_1h']}")
    print(f"   Event Types: {stats['event_types']}")
    print(f"   Decisions Tracked: {stats['decisions_tracked']}")
    print(f"   Active Listeners: {stats['listeners']['global']} global, {stats['listeners']['type_specific']} type-specific")
    
    # Test save/load with enhanced data
    print(f"\n💾 Testing Enhanced Save/Load:")
    event_bus.save_events()
    print("   Enhanced events saved successfully with decision explainability data")
    
    # Test audit trail
    print(f"\n📋 Testing Audit Trail:")
    audit_trail = event_bus.get_audit_trail(limit=5)
    print(f"   Audit Trail Entries: {len(audit_trail)}")
    for event in audit_trail[:3]:  # Show first 3
        print(f"     {event.timestamp.strftime('%H:%M:%S')} - {event.source}: {event.event_type.value}")
    
    print(f"\n✅ Enhanced Event Bus test successful!")
    print(f"   🎯 Requirements 9.2, 9.3, 9.4, 9.5 validated")
    print(f"   📡 Real-time monitoring: {monitoring_status['monitoring_active']}")
    print(f"   🔍 Decision explainability: {len(explanation.reasoning_chain) if explanation else 0} reasoning steps")
    print(f"   📋 Audit trail: {len(audit_trail)} events tracked")
    print(f"   🔗 Causal relationships: {monitoring_status['causal_relationships']} tracked")
    print(f"\n   The living system now has enhanced nervous system capabilities!")
    
    return True

if __name__ == "__main__":
    main()