#!/usr/bin/env python3
"""
Temporal Isolation - Ensures Observer Never Influences Live Decisions

This module provides temporal isolation mechanisms to ensure the Intelligence
Observer can never influence live trading decisions through timing or synchronization.

TEMPORAL ISOLATION PRINCIPLES:
1. Observer runs on separate schedule from execution
2. Observer outputs are never synchronous with trading
3. Minimum time delays enforced between observation and execution
4. Observer cannot see real-time execution state
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging

class IsolationLevel(Enum):
    """Levels of temporal isolation"""
    STRICT = "strict"      # Maximum isolation (4+ hours)
    STANDARD = "standard"  # Standard isolation (1+ hours)
    MINIMAL = "minimal"    # Minimal isolation (15+ minutes)

@dataclass
class TemporalBarrier:
    """Temporal barrier configuration"""
    barrier_type: str
    min_delay_hours: float
    last_execution_time: Optional[datetime] = None
    
    def is_barrier_active(self) -> bool:
        """Check if temporal barrier is active"""
        if self.last_execution_time is None:
            return False
        
        elapsed = datetime.now() - self.last_execution_time
        return elapsed.total_seconds() / 3600 < self.min_delay_hours
    
    def time_until_clear(self) -> float:
        """Get hours until barrier clears"""
        if not self.is_barrier_active():
            return 0.0
        
        elapsed = datetime.now() - self.last_execution_time
        remaining = self.min_delay_hours - (elapsed.total_seconds() / 3600)
        return max(0.0, remaining)

class TemporalIsolation:
    """
    Temporal Isolation Manager
    
    This class ensures the Intelligence Observer maintains proper temporal
    isolation from live trading decisions and execution.
    """
    
    def __init__(self, isolation_level: IsolationLevel = IsolationLevel.STANDARD):
        self.name = "Temporal Isolation Manager"
        self.version = "1.0.0"
        self.isolation_level = isolation_level
        
        # Isolation configuration based on level
        self.isolation_config = {
            IsolationLevel.STRICT: {
                'min_observation_delay': 4.0,    # 4 hours
                'min_output_delay': 2.0,         # 2 hours
                'execution_blackout': 6.0        # 6 hours after execution
            },
            IsolationLevel.STANDARD: {
                'min_observation_delay': 1.0,    # 1 hour
                'min_output_delay': 0.5,         # 30 minutes
                'execution_blackout': 2.0        # 2 hours after execution
            },
            IsolationLevel.MINIMAL: {
                'min_observation_delay': 0.25,   # 15 minutes
                'min_output_delay': 0.1,         # 6 minutes
                'execution_blackout': 0.5        # 30 minutes after execution
            }
        }
        
        # Temporal barriers
        self.barriers: Dict[str, TemporalBarrier] = {
            'observation': TemporalBarrier(
                'observation',
                self.isolation_config[isolation_level]['min_observation_delay']
            ),
            'output': TemporalBarrier(
                'output',
                self.isolation_config[isolation_level]['min_output_delay']
            ),
            'execution_blackout': TemporalBarrier(
                'execution_blackout',
                self.isolation_config[isolation_level]['execution_blackout']
            )
        }
        
        # Isolation state
        self.last_observation_time: Optional[datetime] = None
        self.last_output_time: Optional[datetime] = None
        self.isolation_violations = 0
        
        print(f"⏰ {self.name} v{self.version}")
        print(f"🔒 Isolation Level: {isolation_level.value}")
        print(f"⏱️  Min Observation Delay: {self.barriers['observation'].min_delay_hours} hours")
    
    def can_observe_now(self) -> bool:
        """Check if observation is allowed now"""
        
        # Check observation barrier
        if self.barriers['observation'].is_barrier_active():
            return False
        
        # Check execution blackout
        if self.barriers['execution_blackout'].is_barrier_active():
            return False
        
        return True
    
    def can_output_now(self) -> bool:
        """Check if intelligence output is allowed now"""
        
        # Check output barrier
        if self.barriers['output'].is_barrier_active():
            return False
        
        # Check execution blackout
        if self.barriers['execution_blackout'].is_barrier_active():
            return False
        
        return True
    
    def record_observation(self):
        """Record that an observation occurred"""
        
        if not self.can_observe_now():
            self.isolation_violations += 1
            raise RuntimeError("Temporal isolation violation: Observation not allowed now")
        
        self.last_observation_time = datetime.now()
        self.barriers['observation'].last_execution_time = datetime.now()
    
    def record_output(self):
        """Record that intelligence output was generated"""
        
        if not self.can_output_now():
            self.isolation_violations += 1
            raise RuntimeError("Temporal isolation violation: Output not allowed now")
        
        self.last_output_time = datetime.now()
        self.barriers['output'].last_execution_time = datetime.now()
    
    def record_system_execution(self):
        """Record that system execution occurred (triggers blackout)"""
        
        self.barriers['execution_blackout'].last_execution_time = datetime.now()
        
        print(f"🚫 Execution blackout activated for {self.barriers['execution_blackout'].min_delay_hours} hours")
    
    def get_isolation_status(self) -> Dict[str, Any]:
        """Get current isolation status"""
        
        return {
            'isolation_level': self.isolation_level.value,
            'can_observe': self.can_observe_now(),
            'can_output': self.can_output_now(),
            'barriers': {
                name: {
                    'active': barrier.is_barrier_active(),
                    'time_until_clear': barrier.time_until_clear(),
                    'min_delay_hours': barrier.min_delay_hours
                }
                for name, barrier in self.barriers.items()
            },
            'last_observation': self.last_observation_time.isoformat() if self.last_observation_time else None,
            'last_output': self.last_output_time.isoformat() if self.last_output_time else None,
            'isolation_violations': self.isolation_violations
        }
    
    def wait_for_observation_window(self, timeout_hours: float = 24.0) -> bool:
        """Wait for next observation window"""
        
        start_time = datetime.now()
        timeout_time = start_time + timedelta(hours=timeout_hours)
        
        while datetime.now() < timeout_time:
            if self.can_observe_now():
                return True
            
            # Sleep for 1 minute before checking again
            time.sleep(60)
        
        return False
    
    def wait_for_output_window(self, timeout_hours: float = 24.0) -> bool:
        """Wait for next output window"""
        
        start_time = datetime.now()
        timeout_time = start_time + timedelta(hours=timeout_hours)
        
        while datetime.now() < timeout_time:
            if self.can_output_now():
                return True
            
            # Sleep for 1 minute before checking again
            time.sleep(60)
        
        return False
    
    def enforce_temporal_isolation(self, func: Callable) -> Callable:
        """Decorator to enforce temporal isolation on functions"""
        
        def wrapper(*args, **kwargs):
            # Check if function is observation-related
            if 'observe' in func.__name__.lower() or 'analyze' in func.__name__.lower():
                if not self.can_observe_now():
                    raise RuntimeError(f"Temporal isolation: {func.__name__} blocked by observation barrier")
                self.record_observation()
            
            # Check if function is output-related
            elif 'output' in func.__name__.lower() or 'generate' in func.__name__.lower():
                if not self.can_output_now():
                    raise RuntimeError(f"Temporal isolation: {func.__name__} blocked by output barrier")
                self.record_output()
            
            return func(*args, **kwargs)
        
        return wrapper
    
    def get_next_observation_window(self) -> datetime:
        """Get next available observation window"""
        
        if self.can_observe_now():
            return datetime.now()
        
        # Find the latest barrier clear time
        latest_clear_time = datetime.now()
        
        for barrier in self.barriers.values():
            if barrier.is_barrier_active() and barrier.last_execution_time:
                clear_time = barrier.last_execution_time + timedelta(hours=barrier.min_delay_hours)
                if clear_time > latest_clear_time:
                    latest_clear_time = clear_time
        
        return latest_clear_time
    
    def get_next_output_window(self) -> datetime:
        """Get next available output window"""
        
        if self.can_output_now():
            return datetime.now()
        
        # Find the latest barrier clear time
        latest_clear_time = datetime.now()
        
        for barrier_name in ['output', 'execution_blackout']:
            barrier = self.barriers[barrier_name]
            if barrier.is_barrier_active() and barrier.last_execution_time:
                clear_time = barrier.last_execution_time + timedelta(hours=barrier.min_delay_hours)
                if clear_time > latest_clear_time:
                    latest_clear_time = clear_time
        
        return latest_clear_time

# Global temporal isolation instance
_temporal_isolation = None

def get_temporal_isolation() -> TemporalIsolation:
    """Get global temporal isolation instance"""
    global _temporal_isolation
    
    if _temporal_isolation is None:
        _temporal_isolation = TemporalIsolation()
    
    return _temporal_isolation

def enforce_temporal_isolation(func: Callable) -> Callable:
    """Decorator to enforce temporal isolation"""
    isolation = get_temporal_isolation()
    return isolation.enforce_temporal_isolation(func)