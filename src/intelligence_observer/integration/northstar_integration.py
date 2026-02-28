#!/usr/bin/env python3
"""
Northstar V3 Integration Layer - Intelligence Observer

This module integrates the Intelligence Observer with the existing Northstar V3
architecture through the EventBus and UnifiedState systems while maintaining
strict authority boundaries.

INTEGRATION PRINCIPLES:
1. Observer subscribes to events but never emits decision events
2. Observer reads state but never modifies core system state
3. Observer respects system lock states and emergency conditions
4. Observer operates as a standard NorthstarOrgan with lifecycle
5. Observer maintains complete audit trail of observations
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import logging
import threading
import warnings
warnings.filterwarnings('ignore')

# Import Northstar V3 core components
try:
    from src.core.state import UnifiedState, AuthorityLevel, RiskStatus
    from src.core.events import EventBus, Event, EventType, EventPriority
    from src.core.orchestrator import NorthstarOrgan, OrganStatus, ExecutionResult, ExecutionPhase
    from src.core.clock import MarketClock, TimeEvent
except ImportError as e:
    print(f"⚠️ Northstar V3 core imports not available: {e}")
    # Create minimal stubs for testing
    class UnifiedState: pass
    class EventBus: pass
    class NorthstarOrgan: pass
    class MarketClock: pass

from ..observer_core.observer_scheduler import ObserverScheduler
from ..observer_core.snapshot_builder import SnapshotBuilder
from ..observer_core.observer_context import ObserverSnapshot
from ..guardrails.authority_firewall import get_authority_firewall, check_observer_authority
from ..audit.observer_audit_log import ObserverAuditLog

@dataclass
class ObserverEvent:
    """Observer-specific event for audit trail"""
    observation_type: str
    observation_data: Dict[str, Any]
    confidence: float
    timestamp: datetime
    
    def to_event(self) -> Event:
        """Convert to standard Event for EventBus"""
        return Event(
            event_id=f"OBSERVER_{self.observation_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=self.timestamp,
            event_type=EventType.SYSTEM_EVENT,
            source="intelligence_observer",
            priority=EventPriority.LOW,  # Observer events are always low priority
            data={
                'observation_type': self.observation_type,
                'observation_data': self.observation_data,
                'confidence': self.confidence,
                'authority_level': 'read_only'
            },
            tags=['intelligence', 'observer', 'read_only']
        )

class IntelligenceObserverOrgan(NorthstarOrgan):
    """
    Intelligence Observer as Northstar Organ
    
    This class integrates the Intelligence Observer into the Northstar V3
    living system architecture while maintaining strict authority boundaries.
    """
    
    def __init__(self):
        super().__init__("Intelligence Observer")
        
        self.version = "1.0.0"
        self.is_critical = False  # Observer is never critical for system operation
        
        # Core components
        self.scheduler = ObserverScheduler()
        self.snapshot_builder = SnapshotBuilder()
        self.authority_firewall = get_authority_firewall()
        self.audit_log = ObserverAuditLog()
        
        # Integration state
        self.event_bus: Optional[EventBus] = None
        self.unified_state: Optional[UnifiedState] = None
        self.market_clock: Optional[MarketClock] = None
        
        # Observer state
        self.last_observation_time: Optional[datetime] = None
        self.observation_count = 0
        self.subscribed_events: List[EventType] = [
            EventType.STATE_UPDATE,
            EventType.DECISION,
            EventType.RISK_EVENT,
            EventType.SYSTEM_EVENT
        ]
        
        # Configuration
        self.config = {
            'observation_interval_hours': 24.0,  # Daily observations
            'max_observations_per_day': 5,
            'emergency_observation_cooldown': 4.0,  # 4 hours after emergency
            'respect_system_locks': True
        }
        
        print(f"🧠 {self.name} v{self.version} - Northstar V3 Integration")
        print(f"🔒 Authority Level: READ-ONLY")
        print(f"⚖️  Critical for Operation: {self.is_critical}")
    
    def initialize(self, event_bus: EventBus, unified_state: UnifiedState, 
                  market_clock: MarketClock) -> bool:
        """Initialize Observer with Northstar V3 components"""
        
        try:
            # Store references (read-only)
            self.event_bus = event_bus
            self.unified_state = unified_state
            self.market_clock = market_clock
            
            # Subscribe to relevant events
            if hasattr(self.event_bus, 'subscribe'):
                for event_type in self.subscribed_events:
                    self.event_bus.subscribe(event_type, self._handle_system_event)
            
            # Start observer scheduler
            self.scheduler.start_scheduler()
            
            # Log initialization
            self.audit_log.log_event("observer_initialized", {
                "timestamp": datetime.now().isoformat(),
                "subscribed_events": [et.value for et in self.subscribed_events],
                "authority_firewall_active": True
            })
            
            print(f"✅ {self.name} initialized and integrated with Northstar V3")
            return True
            
        except Exception as e:
            print(f"❌ {self.name} initialization failed: {e}")
            self.status = OrganStatus.FAILED
            return False
    
    def read_state(self, state: UnifiedState) -> None:
        """Read required data from unified state (READ-ONLY)"""
        
        try:
            # Validate authority
            if not self.authority_firewall.check_function_call("read_state", self.name):
                raise PermissionError("Authority firewall blocked state read")
            
            # Store state reference for snapshot building
            self.unified_state = state
            
            # Log state access
            self.audit_log.log_event("state_read", {
                "timestamp": datetime.now().isoformat(),
                "state_available": state is not None,
                "access_type": "read_only"
            })
            
        except Exception as e:
            print(f"⚠️ {self.name} state read error: {e}")
            raise
    
    def think(self) -> Any:
        """Process observations and generate intelligence (NO DECISIONS)"""
        
        try:
            # Check if observer is suspended
            if self.authority_firewall.observer_suspended:
                return {
                    'status': 'suspended',
                    'reason': 'Authority violations detected',
                    'violation_count': self.authority_firewall.violation_count
                }
            
            # Check system lock state
            if self._should_respect_system_locks():
                return {
                    'status': 'deferred',
                    'reason': 'System locks active - respecting emergency state'
                }
            
            # Check observation frequency limits
            if not self._can_observe_now():
                return {
                    'status': 'rate_limited',
                    'reason': 'Observation frequency limits exceeded'
                }
            
            # Build observation snapshot
            snapshot = self.snapshot_builder.build_snapshot()
            
            if snapshot is None:
                return {
                    'status': 'failed',
                    'reason': 'Unable to build observation snapshot'
                }
            
            # Generate observations (this is where intelligence happens)
            observations = self._generate_observations(snapshot)
            
            # Update observation tracking
            self.last_observation_time = datetime.now()
            self.observation_count += 1
            
            return {
                'status': 'success',
                'snapshot_id': snapshot.snapshot_id,
                'observations': observations,
                'observation_count': len(observations)
            }
            
        except Exception as e:
            print(f"❌ {self.name} thinking error: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def write_state(self, state: UnifiedState) -> None:
        """Write observations to state (AUDIT TRAIL ONLY)"""
        
        try:
            # CRITICAL: Observer never modifies core system state
            # Only writes to observer-specific audit trail
            
            # Validate we're not trying to modify core state
            if not self.authority_firewall.check_function_call("write_state", self.name):
                raise PermissionError("Authority firewall blocked state write")
            
            # Observer only writes to its own audit trail
            # This would be implemented as observer-specific state section
            # that has no impact on trading decisions
            
            self.audit_log.log_event("state_write_attempt", {
                "timestamp": datetime.now().isoformat(),
                "action": "audit_trail_only",
                "core_state_modified": False
            })
            
        except Exception as e:
            print(f"⚠️ {self.name} state write error: {e}")
            raise
    
    def _handle_system_event(self, event: Event) -> None:
        """Handle system events for observation purposes"""
        
        try:
            # Log event observation
            self.audit_log.log_event("system_event_observed", {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "source": event.source,
                "timestamp": event.timestamp.isoformat(),
                "observer_action": "logged_only"
            })
            
            # Observer never takes action based on events
            # Just logs for pattern analysis
            
        except Exception as e:
            print(f"⚠️ {self.name} event handling error: {e}")
    
    def _should_respect_system_locks(self) -> bool:
        """Check if system locks should be respected"""
        
        if not self.config['respect_system_locks']:
            return False
        
        try:
            # Check if unified state indicates emergency or lock conditions
            if self.unified_state and hasattr(self.unified_state, 'risk_state'):
                risk_state = getattr(self.unified_state, 'risk_state', None)
                
                if risk_state and hasattr(risk_state, 'status'):
                    if risk_state.status in [RiskStatus.EMERGENCY, RiskStatus.CRITICAL]:
                        return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking system locks: {e}")
            return True  # Err on side of caution
    
    def _can_observe_now(self) -> bool:
        """Check if observation is allowed now based on frequency limits"""
        
        now = datetime.now()
        
        # Check daily observation limit
        if self.last_observation_time:
            time_since_last = now - self.last_observation_time
            
            # Minimum interval between observations
            min_interval = timedelta(hours=self.config['observation_interval_hours'])
            if time_since_last < min_interval:
                return False
            
            # Daily observation count limit
            if self.last_observation_time.date() == now.date():
                if self.observation_count >= self.config['max_observations_per_day']:
                    return False
        
        return True
    
    def _generate_observations(self, snapshot: ObserverSnapshot) -> List[Dict[str, Any]]:
        """Generate intelligence observations from snapshot"""
        
        observations = []
        
        try:
            # Run on-demand analysis through scheduler
            analysis_result = self.scheduler.run_on_demand_analysis()
            
            if analysis_result.get('success'):
                # Convert analysis results to observations
                results = analysis_result.get('results', [])
                
                for result in results:
                    observation = {
                        'type': result['type'],
                        'category': result['category'],
                        'artifact_id': result['artifact'].get('score_id') or result['artifact'].get('alert_id') or result['artifact'].get('narrative_id'),
                        'confidence': result['artifact'].get('confidence', 0.5),
                        'timestamp': datetime.now().isoformat(),
                        'summary': self._extract_observation_summary(result)
                    }
                    
                    observations.append(observation)
                    
                    # Emit observer event for audit trail
                    observer_event = ObserverEvent(
                        observation_type=f"{result['category']}_{result['type']}",
                        observation_data=observation,
                        confidence=observation['confidence'],
                        timestamp=datetime.now()
                    )
                    
                    if self.event_bus and hasattr(self.event_bus, 'emit'):
                        self.event_bus.emit(observer_event.to_event())
            
        except Exception as e:
            print(f"⚠️ Error generating observations: {e}")
        
        return observations
    
    def _extract_observation_summary(self, result: Dict[str, Any]) -> str:
        """Extract human-readable summary from analysis result"""
        
        artifact = result['artifact']
        
        if result['type'] == 'score':
            return f"{artifact.get('score_name', 'Unknown Score')}: {artifact.get('value', 0):.0f}/100"
        elif result['type'] == 'alert':
            return f"Alert: {artifact.get('message', 'Unknown alert')}"
        elif result['type'] == 'narrative':
            return f"Narrative: {artifact.get('title', 'Unknown narrative')}"
        else:
            return "Unknown observation type"
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get Observer health metrics"""
        
        return {
            'status': self.status.value,
            'observation_count': self.observation_count,
            'last_observation': self.last_observation_time.isoformat() if self.last_observation_time else None,
            'authority_violations': self.authority_firewall.violation_count,
            'observer_suspended': self.authority_firewall.observer_suspended,
            'scheduler_running': self.scheduler.is_running,
            'integration_status': {
                'event_bus_connected': self.event_bus is not None,
                'unified_state_connected': self.unified_state is not None,
                'market_clock_connected': self.market_clock is not None
            }
        }
    
    def shutdown(self):
        """Shutdown Observer gracefully"""
        
        try:
            # Stop scheduler
            self.scheduler.stop_scheduler()
            
            # Unsubscribe from events
            if self.event_bus and hasattr(self.event_bus, 'unsubscribe'):
                for event_type in self.subscribed_events:
                    try:
                        self.event_bus.unsubscribe(event_type, self._handle_system_event)
                    except:
                        pass
            
            # Log shutdown
            self.audit_log.log_event("observer_shutdown", {
                "timestamp": datetime.now().isoformat(),
                "total_observations": self.observation_count,
                "final_status": self.status.value
            })
            
            print(f"🔄 {self.name} shutdown completed")
            
        except Exception as e:
            print(f"⚠️ {self.name} shutdown error: {e}")

class ObserverIntegrationManager:
    """
    Manager for Intelligence Observer integration with Northstar V3
    
    This class handles the integration lifecycle and provides a clean
    interface for the main system to interact with the Observer.
    """
    
    def __init__(self):
        self.name = "Observer Integration Manager"
        self.version = "1.0.0"
        
        self.observer_organ: Optional[IntelligenceObserverOrgan] = None
        self.integration_active = False
        
        print(f"🔗 {self.name} v{self.version}")
    
    def integrate_with_northstar(self, event_bus: EventBus, unified_state: UnifiedState, 
                               market_clock: MarketClock) -> bool:
        """Integrate Observer with Northstar V3 system"""
        
        try:
            # Create Observer organ
            self.observer_organ = IntelligenceObserverOrgan()
            
            # Initialize with Northstar components
            success = self.observer_organ.initialize(event_bus, unified_state, market_clock)
            
            if success:
                self.integration_active = True
                print(f"✅ Intelligence Observer integrated with Northstar V3")
                return True
            else:
                print(f"❌ Intelligence Observer integration failed")
                return False
                
        except Exception as e:
            print(f"❌ Observer integration error: {e}")
            return False
    
    def get_observer_organ(self) -> Optional[IntelligenceObserverOrgan]:
        """Get the Observer organ for registration with orchestrator"""
        return self.observer_organ
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status"""
        
        status = {
            'integration_active': self.integration_active,
            'observer_available': self.observer_organ is not None
        }
        
        if self.observer_organ:
            status.update(self.observer_organ.get_health_metrics())
        
        return status
    
    def shutdown_integration(self):
        """Shutdown Observer integration"""
        
        if self.observer_organ:
            self.observer_organ.shutdown()
        
        self.integration_active = False
        print(f"🔄 Observer integration shutdown completed")

# Global integration manager instance
_integration_manager = None

def get_integration_manager() -> ObserverIntegrationManager:
    """Get global integration manager instance"""
    global _integration_manager
    
    if _integration_manager is None:
        _integration_manager = ObserverIntegrationManager()
    
    return _integration_manager

def integrate_intelligence_observer(event_bus: EventBus, unified_state: UnifiedState, 
                                  market_clock: MarketClock) -> bool:
    """
    Main integration function for Northstar V3
    
    Call this from your main system initialization to integrate the Observer.
    """
    
    manager = get_integration_manager()
    return manager.integrate_with_northstar(event_bus, unified_state, market_clock)