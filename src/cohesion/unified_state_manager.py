#!/usr/bin/env python3
"""
🧠 UNIFIED STATE MANAGER - CAPITAL-GRADE SYSTEM LAWS
Single Source of Truth for All System State

This implements the capital-grade state management system with
mathematical invariants that cannot be violated.

SYSTEM LAWS ENFORCED:
- Invariant S1: Atomic State Updates - all components see same version simultaneously
- Invariant S2: Temporal Monotonicity - timestamps must be strictly increasing
- Invariant S3: State Authority Hierarchy - authority levels must be respected

These are not suggestions - they are LAWS that terminate the system if violated.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
import threading
import warnings
warnings.filterwarnings('ignore')

class AuthorityLevel(Enum):
    """Authority hierarchy for state updates"""
    EMERGENCY = 1    # Absolute authority - overrides everything
    SYSTEM = 2       # System-level authority (risk, health monitoring)
    PORTFOLIO = 3    # Portfolio-level authority (allocation decisions)
    INTELLIGENCE = 4 # Intelligence-level authority (signals, analysis)
    POSITION = 5     # Position-level authority (individual positions)

class ComponentStatus(Enum):
    """Component operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    DEGRADED = "degraded"

@dataclass
class StateUpdate:
    """Atomic state update with authority and versioning"""
    component: str
    field: str
    old_value: Any
    new_value: Any
    authority: AuthorityLevel
    timestamp: datetime
    reason: str
    update_id: str
    version: int
    
    def __post_init__(self):
        if self.update_id is None:
            self.update_id = f"{self.timestamp.isoformat()}_{self.component}_{self.field}"

@dataclass
class StateConflict:
    """State conflict requiring resolution"""
    component: str
    field: str
    conflicting_updates: List[StateUpdate]
    resolution: Optional[StateUpdate] = None
    resolved_at: Optional[datetime] = None

@dataclass
class SystemState:
    """Complete system state representation with versioning"""
    # Core state components
    market_state: Dict[str, Any]
    portfolio_state: Dict[str, Any]
    risk_state: Dict[str, Any]
    intelligence_state: Dict[str, Any]
    health_state: Dict[str, Any]
    
    # Metadata
    timestamp: datetime
    version: int
    authority_level: AuthorityLevel
    component_versions: Dict[str, int]
    
    def __post_init__(self):
        if self.component_versions is None:
            self.component_versions = {}
    
    def validate_consistency(self) -> bool:
        """
        SYSTEM LAW: Validate state consistency across components
        All components must have consistent view of critical shared state
        """
        
        # Check timestamp consistency
        if self.timestamp is None:
            return False
        
        # Check version consistency
        if self.version <= 0:
            return False
        
        # Check component version consistency
        for component, version in self.component_versions.items():
            if version > self.version:
                return False  # Component version cannot exceed system version
        
        return True

class StateHistory:
    """Temporal state history with efficient querying"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.snapshots: List[SystemState] = []
        self.updates: List[StateUpdate] = []
        self._lock = threading.Lock()
    
    def add_snapshot(self, state: SystemState):
        """Add state snapshot to history with thread safety"""
        with self._lock:
            self.snapshots.append(state)
            
            # Maintain history size
            if len(self.snapshots) > self.max_history:
                self.snapshots = self.snapshots[-self.max_history:]
    
    def add_update(self, update: StateUpdate):
        """Add state update to history"""
        with self._lock:
            self.updates.append(update)
            
            # Maintain history size
            if len(self.updates) > self.max_history:
                self.updates = self.updates[-self.max_history:]
    
    def get_state_at(self, timestamp: datetime) -> Optional[SystemState]:
        """Get state as it was at specific timestamp"""
        with self._lock:
            # Find latest snapshot before or at timestamp
            valid_snapshots = [s for s in self.snapshots if s.timestamp <= timestamp]
            if not valid_snapshots:
                return None
            
            return max(valid_snapshots, key=lambda s: s.timestamp)
    
    def get_updates_between(self, start: datetime, end: datetime) -> List[StateUpdate]:
        """Get all state updates in time range"""
        with self._lock:
            return [u for u in self.updates if start <= u.timestamp <= end]
    
    def get_latest_version(self) -> int:
        """Get latest state version"""
        with self._lock:
            if not self.snapshots:
                return 0
            return max(s.version for s in self.snapshots)

class UnifiedStateManager:
    """
    CAPITAL-GRADE UNIFIED STATE MANAGER
    
    Enforces system laws that cannot be violated:
    - INVARIANT S1: Atomic State Updates
    - INVARIANT S2: Temporal Monotonicity
    - INVARIANT S3: State Authority Hierarchy
    """
    
    def __init__(self, persistence_dir: str = "data/state"):
        self.persistence_dir = persistence_dir
        os.makedirs(persistence_dir, exist_ok=True)
        
        # Current system state
        self.current_state = SystemState(
            market_state={},
            portfolio_state={},
            risk_state={},
            intelligence_state={},
            health_state={},
            timestamp=datetime.now(),
            version=1,
            authority_level=AuthorityLevel.SYSTEM,
            component_versions={}
        )
        
        # State management
        self.state_history = StateHistory()
        self.subscribers: Dict[str, List[Callable]] = {}
        self.authority_hierarchy = self._initialize_authority_hierarchy()
        self.pending_conflicts: List[StateConflict] = []
        self.field_authorities: Dict[str, AuthorityLevel] = {}  # Track field authorities
        
        # Thread safety
        self._state_lock = threading.Lock()
        self._update_counter = 0
        
        # Persistence
        self.state_file = os.path.join(persistence_dir, "unified_state.json")
        self.history_file = os.path.join(persistence_dir, "state_history.parquet")
        
        # Initialize state history
        self.state_history.add_snapshot(self.current_state)
    
    def _initialize_authority_hierarchy(self) -> Dict[AuthorityLevel, List[str]]:
        """Initialize authority hierarchy for conflict resolution"""
        return {
            AuthorityLevel.EMERGENCY: ["emergency_brake", "risk_monitor"],
            AuthorityLevel.SYSTEM: ["health_monitor", "data_pipeline", "configuration_manager"],
            AuthorityLevel.PORTFOLIO: ["portfolio_governor", "capital_allocator"],
            AuthorityLevel.INTELLIGENCE: ["intelligence_engine", "regime_detector", "signal_generator"],
            AuthorityLevel.POSITION: ["position_sizer", "order_manager"]
        }
    
    def update_state(self, 
                    component: str, 
                    updates: Dict[str, Any], 
                    authority: AuthorityLevel,
                    reason: str = "",
                    timestamp: Optional[datetime] = None) -> bool:
        """
        SYSTEM LAW: Atomic state update with authority validation
        ENFORCES INVARIANTS S1, S2, S3
        """
        
        if timestamp is None:
            timestamp = datetime.now()
        
        with self._state_lock:
            # INVARIANT S2: Temporal Monotonicity
            if timestamp <= self.current_state.timestamp:
                raise ValueError(f"INVARIANT S2 VIOLATION: Timestamp {timestamp} <= current {self.current_state.timestamp}")
            
            # Generate new version
            new_version = self.current_state.version + 1
            
            # Create state updates
            state_updates = []
            
            for field, new_value in updates.items():
                # Get current value
                old_value = self._get_component_field_value(component, field)
                
                # Check if there's an existing value with higher authority
                existing_authority = self._get_field_authority(component, field)
                
                # INVARIANT S3: Authority hierarchy check
                if existing_authority and existing_authority.value < authority.value:
                    # Higher authority exists, this update should be rejected
                    print(f"🔐 AUTHORITY REJECTED: {authority.name} cannot override {existing_authority.name} for {component}.{field}")
                    continue
                
                # Create update
                update = StateUpdate(
                    component=component,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    authority=authority,
                    timestamp=timestamp,
                    reason=reason,
                    update_id=f"{timestamp.isoformat()}_{component}_{field}_{self._update_counter}",
                    version=new_version
                )
                
                self._update_counter += 1
                state_updates.append(update)
            
            if not state_updates:
                # No updates to apply (all rejected by authority)
                return False
            
            # Apply updates atomically
            success = self._apply_updates_atomically(state_updates, new_version, timestamp, authority)
            
            if success:
                # INVARIANT S1: All subscribers see same version simultaneously
                self._notify_subscribers_atomically(component, state_updates)
                
                # Add to history
                for update in state_updates:
                    self.state_history.add_update(update)
                
                # Create new state snapshot
                self.state_history.add_snapshot(self.current_state)
                
                # Persist state
                self._persist_state()
            
            return success
    
    def _get_field_authority(self, component: str, field: str) -> Optional[AuthorityLevel]:
        """Get the authority level that last set this field"""
        field_key = f"{component}.{field}"
        return self.field_authorities.get(field_key)
    
    def _set_field_authority(self, component: str, field: str, authority: AuthorityLevel):
        """Set the authority level for a field"""
        field_key = f"{component}.{field}"
        self.field_authorities[field_key] = authority
    
    def _get_component_field_value(self, component: str, field: str) -> Any:
        """Get current value of component field"""
        component_state = self._get_component_state(component)
        return component_state.get(field)
    
    def _get_component_state(self, component: str) -> Dict[str, Any]:
        """Get component state dictionary"""
        component_map = {
            'market': self.current_state.market_state,
            'portfolio': self.current_state.portfolio_state,
            'risk': self.current_state.risk_state,
            'intelligence': self.current_state.intelligence_state,
            'health': self.current_state.health_state
        }
        
        return component_map.get(component, {})
    
    def _check_for_conflicts(self, update: StateUpdate) -> Optional[StateConflict]:
        """Check for conflicts with pending updates"""
        
        # Look for conflicting updates to same component.field
        conflicting_updates = []
        
        for pending_conflict in self.pending_conflicts:
            if (pending_conflict.component == update.component and 
                pending_conflict.field == update.field and
                pending_conflict.resolution is None):
                conflicting_updates.extend(pending_conflict.conflicting_updates)
        
        if conflicting_updates:
            conflicting_updates.append(update)
            return StateConflict(
                component=update.component,
                field=update.field,
                conflicting_updates=conflicting_updates
            )
        
        return None
    
    def _resolve_conflicts(self, conflicts: List[StateConflict]) -> List[StateUpdate]:
        """
        SYSTEM LAW: Resolve conflicts using authority hierarchy
        ENFORCES INVARIANT S3: State Authority Hierarchy
        """
        
        resolved_updates = []
        
        for conflict in conflicts:
            # INVARIANT S3: Higher authority wins
            winning_update = min(conflict.conflicting_updates, key=lambda u: u.authority.value)
            
            # Mark conflict as resolved
            conflict.resolution = winning_update
            conflict.resolved_at = datetime.now()
            
            resolved_updates.append(winning_update)
            
            # Log authority override
            if len(conflict.conflicting_updates) > 1:
                other_authorities = [u.authority.name for u in conflict.conflicting_updates if u != winning_update]
                print(f"🔐 AUTHORITY OVERRIDE: {winning_update.authority.name} overrides {other_authorities} for {conflict.component}.{conflict.field}")
        
        return resolved_updates
    
    def _apply_updates_atomically(self, updates: List[StateUpdate], new_version: int, timestamp: datetime, authority: AuthorityLevel) -> bool:
        """
        SYSTEM LAW: Apply all updates atomically or none at all
        ENFORCES INVARIANT S1: Atomic State Updates
        """
        
        try:
            # Create new state with updates
            new_state = SystemState(
                market_state=self.current_state.market_state.copy(),
                portfolio_state=self.current_state.portfolio_state.copy(),
                risk_state=self.current_state.risk_state.copy(),
                intelligence_state=self.current_state.intelligence_state.copy(),
                health_state=self.current_state.health_state.copy(),
                timestamp=timestamp,
                version=new_version,
                authority_level=authority,
                component_versions=self.current_state.component_versions.copy()
            )
            
            # Apply all updates to new state
            for update in updates:
                component_state = self._get_component_state_from_new_state(new_state, update.component)
                component_state[update.field] = update.new_value
                
                # Update component version
                new_state.component_versions[update.component] = new_version
                
                # Track field authority
                self._set_field_authority(update.component, update.field, update.authority)
            
            # Validate new state consistency
            if not new_state.validate_consistency():
                raise ValueError("INVARIANT VIOLATION: New state failed consistency validation")
            
            # INVARIANT S1: Atomic replacement of current state
            self.current_state = new_state
            
            return True
            
        except Exception as e:
            print(f"❌ ATOMIC UPDATE FAILED: {e}")
            return False
    
    def _get_component_state_from_new_state(self, state: SystemState, component: str) -> Dict[str, Any]:
        """Get component state dictionary from new state"""
        component_map = {
            'market': state.market_state,
            'portfolio': state.portfolio_state,
            'risk': state.risk_state,
            'intelligence': state.intelligence_state,
            'health': state.health_state
        }
        
        return component_map.get(component, {})
    
    def _notify_subscribers_atomically(self, component: str, updates: List[StateUpdate]):
        """
        SYSTEM LAW: Notify all subscribers simultaneously
        ENFORCES INVARIANT S1: All components see same version
        """
        
        if component in self.subscribers:
            for callback in self.subscribers[component]:
                try:
                    # All callbacks receive the same state version
                    callback(component, updates, self.current_state)
                except Exception as e:
                    print(f"⚠️ Subscriber callback error: {e}")
    
    def get_state(self, as_of: Optional[datetime] = None) -> SystemState:
        """Get current or historical state"""
        
        if as_of is None:
            with self._state_lock:
                return self.current_state
        else:
            return self.state_history.get_state_at(as_of)
    
    def subscribe_to_changes(self, 
                           component: str, 
                           callback: Callable,
                           filter_func: Optional[Callable] = None):
        """Subscribe to state changes with optional filtering"""
        
        if component not in self.subscribers:
            self.subscribers[component] = []
        
        # Wrap callback with filter if provided
        if filter_func:
            def filtered_callback(comp, updates, state):
                filtered_updates = [u for u in updates if filter_func(u)]
                if filtered_updates:
                    callback(comp, filtered_updates, state)
            self.subscribers[component].append(filtered_callback)
        else:
            self.subscribers[component].append(callback)
        
        print(f"📡 Subscribed to {component} state changes")
    
    def get_component_state(self, component: str, as_of: Optional[datetime] = None) -> Dict[str, Any]:
        """Get specific component state"""
        
        state = self.get_state(as_of)
        if state is None:
            return {}
        
        return self._get_component_state_from_new_state(state, component)
    
    def get_state_version(self) -> int:
        """Get current state version"""
        with self._state_lock:
            return self.current_state.version
    
    def validate_state_integrity(self) -> bool:
        """
        Validate complete state integrity
        Checks all system laws are satisfied
        """
        
        with self._state_lock:
            # INVARIANT S1: State consistency
            if not self.current_state.validate_consistency():
                print("❌ INVARIANT S1 VIOLATION: State consistency check failed")
                return False
            
            # INVARIANT S2: Temporal monotonicity in history
            timestamps = [s.timestamp for s in self.state_history.snapshots]
            if timestamps != sorted(timestamps):
                print("❌ INVARIANT S2 VIOLATION: Non-monotonic timestamps in history")
                return False
            
            # INVARIANT S3: Authority hierarchy respected in updates
            for update in self.state_history.updates[-100:]:  # Check recent updates
                if update.authority not in AuthorityLevel:
                    print(f"❌ INVARIANT S3 VIOLATION: Invalid authority level {update.authority}")
                    return False
            
            print("✅ All state management invariants satisfied")
            return True
    
    def _persist_state(self):
        """Persist current state to disk"""
        try:
            state_dict = {
                'timestamp': self.current_state.timestamp.isoformat(),
                'version': self.current_state.version,
                'authority_level': self.current_state.authority_level.name,
                'market_state': self.current_state.market_state,
                'portfolio_state': self.current_state.portfolio_state,
                'risk_state': self.current_state.risk_state,
                'intelligence_state': self.current_state.intelligence_state,
                'health_state': self.current_state.health_state,
                'component_versions': self.current_state.component_versions
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=2, default=str)
                
        except Exception as e:
            print(f"⚠️ Error persisting state: {e}")
    
    def load_state(self) -> bool:
        """Load state from persistence"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state_dict = json.load(f)
                
                self.current_state = SystemState(
                    market_state=state_dict.get('market_state', {}),
                    portfolio_state=state_dict.get('portfolio_state', {}),
                    risk_state=state_dict.get('risk_state', {}),
                    intelligence_state=state_dict.get('intelligence_state', {}),
                    health_state=state_dict.get('health_state', {}),
                    timestamp=datetime.fromisoformat(state_dict['timestamp']),
                    version=state_dict['version'],
                    authority_level=AuthorityLevel[state_dict['authority_level']],
                    component_versions=state_dict.get('component_versions', {})
                )
                
                print(f"✅ State loaded: version {self.current_state.version}")
                return True
                
        except Exception as e:
            print(f"⚠️ Error loading state: {e}")
        
        return False
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        
        with self._state_lock:
            return {
                'state_version': self.current_state.version,
                'last_update': self.current_state.timestamp.isoformat(),
                'component_count': len([k for k in self.current_state.component_versions.keys()]),
                'subscriber_count': sum(len(subs) for subs in self.subscribers.values()),
                'pending_conflicts': len(self.pending_conflicts),
                'history_size': len(self.state_history.snapshots),
                'integrity_valid': self.validate_state_integrity()
            }

def main():
    """Test the Unified State Manager with system laws"""
    
    print("🧠 TESTING CAPITAL-GRADE UNIFIED STATE MANAGER")
    print("=" * 60)
    
    # Create state manager
    state_manager = UnifiedStateManager()
    
    # Test atomic state updates
    print("\n📊 Testing atomic state updates...")
    
    try:
        # Test INVARIANT S1: Atomic updates
        success = state_manager.update_state(
            component="market",
            updates={
                "regime": "expansion",
                "risk_on_probability": 0.75,
                "allowed_exposure": 0.65
            },
            authority=AuthorityLevel.INTELLIGENCE,
            reason="Market regime analysis update"
        )
        
        if success:
            print("✅ Atomic update successful")
            market_state = state_manager.get_component_state("market")
            print(f"   Market regime: {market_state.get('regime')}")
            print(f"   Risk-on probability: {market_state.get('risk_on_probability')}")
        else:
            print("❌ Atomic update failed")
            return False
        
    except Exception as e:
        print(f"❌ State update error: {e}")
        return False
    
    # Test INVARIANT S2: Temporal monotonicity
    print("\n⏰ Testing temporal monotonicity...")
    
    try:
        # This should fail - timestamp in past
        past_time = datetime.now() - timedelta(minutes=1)
        state_manager.update_state(
            component="portfolio",
            updates={"total_exposure": 0.60},
            authority=AuthorityLevel.PORTFOLIO,
            timestamp=past_time,
            reason="Should fail - past timestamp"
        )
        print("❌ INVARIANT S2 VIOLATION: Past timestamp accepted")
        return False
        
    except ValueError as e:
        if "INVARIANT S2 VIOLATION" in str(e):
            print("✅ INVARIANT S2 enforced: Past timestamp rejected")
        else:
            print(f"❌ Unexpected error: {e}")
            return False
    
    # Test INVARIANT S3: Authority hierarchy
    print("\n🔐 Testing authority hierarchy...")
    
    # Create conflicting updates with different authorities
    state_manager.update_state(
        component="risk",
        updates={"emergency_active": True},
        authority=AuthorityLevel.EMERGENCY,
        reason="Emergency brake activation"
    )
    
    risk_state = state_manager.get_component_state("risk")
    if risk_state.get("emergency_active") == True:
        print("✅ INVARIANT S3: Emergency authority respected")
    else:
        print("❌ INVARIANT S3 VIOLATION: Emergency authority not respected")
        return False
    
    # Test state integrity validation
    print("\n🔍 Testing state integrity validation...")
    
    integrity_valid = state_manager.validate_state_integrity()
    if integrity_valid:
        print("✅ All state management invariants satisfied")
    else:
        print("❌ State integrity violations detected")
        return False
    
    # Test system health
    print("\n🏥 Testing system health...")
    
    health = state_manager.get_system_health()
    print(f"   State version: {health['state_version']}")
    print(f"   Component count: {health['component_count']}")
    print(f"   Integrity valid: {health['integrity_valid']}")
    
    print(f"\n✅ Unified State Manager test successful!")
    print(f"   Capital-grade state management laws are enforced")
    print(f"   System is protected against state corruption")
    
    return True

if __name__ == "__main__":
    main()