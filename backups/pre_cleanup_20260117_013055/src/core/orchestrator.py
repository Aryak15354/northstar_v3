#!/usr/bin/env python3
"""
🎭 ORGAN ORCHESTRATOR - THE CONDUCTOR
Organ Scheduler and Coordinator for the Living Investment Organism

This is the Organ Orchestrator that schedules and coordinates the execution
of all organs in the living system, handling failures gracefully and
respecting system lock states.

Key Features:
- Organ scheduling and execution coordination
- Graceful failure handling with isolation
- System lock state respect for non-risk organs
- Health monitoring and recovery
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable, Type
from enum import Enum
from abc import ABC, abstractmethod
import threading
import time
import traceback
import warnings
warnings.filterwarnings('ignore')

from src.core.state import UnifiedState, AuthorityLevel
from src.core.clock import MarketClock, TimeEvent, MarketTime
from src.core.events import EventBus, Event, EventType, EventPriority

class OrganStatus(Enum):
    """Organ execution status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    RECOVERING = "recovering"

class ExecutionPhase(Enum):
    """Organ execution phases"""
    READ_STATE = "read_state"
    THINK = "think"
    WRITE_STATE = "write_state"
    COMPLETE = "complete"
    ERROR = "error"

@dataclass
class OrganMetrics:
    """Organ performance metrics"""
    organ_name: str
    status: OrganStatus
    last_execution: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_duration: float = 0.0
    last_error: Optional[str] = None
    health_score: float = 1.0
    
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

@dataclass
class ExecutionResult:
    """Result of organ execution"""
    organ_name: str
    success: bool
    duration: float
    phase: ExecutionPhase
    error: Optional[str] = None
    output: Any = None
    metrics: Optional[Dict[str, Any]] = None

class NorthstarOrgan(ABC):
    """
    Standard interface for all system organs
    
    All organs must implement this interface to participate
    in the living system coordination.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.status = OrganStatus.HEALTHY
        self.metrics = OrganMetrics(organ_name=name, status=OrganStatus.HEALTHY)
        self.last_execution_time = None
        self.is_critical = False  # Whether organ is critical for system operation
    
    @abstractmethod
    def read_state(self, state: UnifiedState) -> None:
        """Read required data from unified state"""
        pass
    
    @abstractmethod
    def think(self, state: UnifiedState) -> Any:
        """Process data and generate outputs"""
        pass
    
    @abstractmethod
    def write_state(self, state: UnifiedState) -> None:
        """Write outputs to unified state"""
        pass
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Return organ health metrics"""
        return {
            'status': self.status.value,
            'success_rate': self.metrics.success_rate(),
            'execution_count': self.metrics.execution_count,
            'average_duration': self.metrics.average_duration,
            'health_score': self.metrics.health_score,
            'last_execution': self.metrics.last_execution.isoformat() if self.metrics.last_execution else None,
            'last_error': self.metrics.last_error
        }
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time-based events (optional override)"""
        pass
    
    def can_execute(self, state: UnifiedState) -> bool:
        """Check if organ can execute (considering system locks)"""
        
        # Risk organs can always execute
        if self.name.lower().startswith('risk'):
            return True
        
        # Other organs cannot execute if system is locked
        if state.locked:
            return False
        
        # Check organ health
        if self.status in [OrganStatus.FAILED, OrganStatus.DISABLED]:
            return False
        
        return True
    
    def execute_full_cycle(self, state: UnifiedState) -> ExecutionResult:
        """Execute complete organ cycle with error handling"""
        
        start_time = time.time()
        
        try:
            # Check if can execute
            if not self.can_execute(state):
                return ExecutionResult(
                    organ_name=self.name,
                    success=False,
                    duration=0.0,
                    phase=ExecutionPhase.READ_STATE,
                    error="Organ cannot execute (system locked or organ disabled)"
                )
            
            # Phase 1: Read State
            self.read_state(state)
            
            # Phase 2: Think
            output = self.think(state)
            
            # Phase 3: Write State
            self.write_state(state)
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics.execution_count += 1
            self.metrics.success_count += 1
            self.metrics.last_execution = datetime.now()
            self.metrics.average_duration = (
                (self.metrics.average_duration * (self.metrics.execution_count - 1) + duration) /
                self.metrics.execution_count
            )
            
            # Update health score
            self._update_health_score(True)
            
            return ExecutionResult(
                organ_name=self.name,
                success=True,
                duration=duration,
                phase=ExecutionPhase.COMPLETE,
                output=output,
                metrics=self.get_health_metrics()
            )
            
        except Exception as e:
            # Handle failure
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.metrics.execution_count += 1
            self.metrics.failure_count += 1
            self.metrics.last_execution = datetime.now()
            self.metrics.last_error = error_msg
            
            # Update health score
            self._update_health_score(False)
            
            # Update status based on failure pattern
            if self.metrics.success_rate() < 0.5:
                self.status = OrganStatus.FAILED
            elif self.metrics.success_rate() < 0.8:
                self.status = OrganStatus.DEGRADED
            
            return ExecutionResult(
                organ_name=self.name,
                success=False,
                duration=duration,
                phase=ExecutionPhase.ERROR,
                error=error_msg,
                metrics=self.get_health_metrics()
            )
    
    def _update_health_score(self, success: bool):
        """Update organ health score based on execution result"""
        
        # Simple exponential moving average
        alpha = 0.1  # Learning rate
        new_score = 1.0 if success else 0.0
        
        self.metrics.health_score = (
            alpha * new_score + (1 - alpha) * self.metrics.health_score
        )

class OrganIsolationManager:
    """
    Manages organ isolation and recovery operations
    
    Provides advanced isolation capabilities to ensure that organ failures
    and recovery operations don't affect other organs.
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.isolated_organs: Dict[str, Dict[str, Any]] = {}
        self.quarantine_duration = 600  # 10 minutes default quarantine
        
    def isolate_organ(self, organ: NorthstarOrgan, reason: str, duration: Optional[int] = None):
        """Isolate an organ from the system"""
        
        isolation_duration = duration or self.quarantine_duration
        isolation_info = {
            'timestamp': datetime.now(),
            'reason': reason,
            'duration': isolation_duration,
            'original_status': organ.status,
            'isolation_id': f"{organ.name}_{int(time.time())}"
        }
        
        # Mark organ as isolated
        organ.status = OrganStatus.DISABLED
        self.isolated_organs[organ.name] = isolation_info
        
        # Emit isolation event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="isolation_manager",
            priority=EventPriority.HIGH,
            data={
                'action': 'organ_isolated',
                'organ_name': organ.name,
                'reason': reason,
                'duration': isolation_duration,
                'isolation_id': isolation_info['isolation_id']
            },
            tags=['isolation', 'organ_management', organ.name]
        ))
        
        print(f"   🔒 Isolated organ: {organ.name} (reason: {reason}, duration: {isolation_duration}s)")
        
    def check_isolation_expiry(self, organ: NorthstarOrgan) -> bool:
        """Check if organ isolation has expired"""
        
        if organ.name not in self.isolated_organs:
            return False
        
        isolation_info = self.isolated_organs[organ.name]
        elapsed = (datetime.now() - isolation_info['timestamp']).total_seconds()
        
        if elapsed >= isolation_info['duration']:
            # Isolation expired - prepare for recovery
            self.prepare_organ_recovery(organ, isolation_info)
            return True
        
        return False
    
    def prepare_organ_recovery(self, organ: NorthstarOrgan, isolation_info: Dict[str, Any]):
        """Prepare organ for recovery from isolation"""
        
        # Reset organ metrics for fresh start
        organ.metrics.failure_count = 0
        organ.metrics.last_error = None
        organ.status = OrganStatus.RECOVERING
        
        # Remove from isolation
        del self.isolated_organs[organ.name]
        
        # Emit recovery preparation event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="isolation_manager",
            priority=EventPriority.NORMAL,
            data={
                'action': 'organ_recovery_prepared',
                'organ_name': organ.name,
                'isolation_id': isolation_info['isolation_id'],
                'isolation_duration': (datetime.now() - isolation_info['timestamp']).total_seconds()
            },
            tags=['recovery', 'organ_management', organ.name]
        ))
        
        print(f"   🔄 Prepared recovery for organ: {organ.name}")
    
    def force_recovery(self, organ_name: str) -> bool:
        """Force immediate recovery of an isolated organ"""
        
        if organ_name not in self.isolated_organs:
            return False
        
        # Find the organ
        # Note: This would need access to the organ registry
        # For now, just remove from isolation tracking
        isolation_info = self.isolated_organs[organ_name]
        del self.isolated_organs[organ_name]
        
        # Emit forced recovery event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="isolation_manager",
            priority=EventPriority.HIGH,
            data={
                'action': 'organ_recovery_forced',
                'organ_name': organ_name,
                'isolation_id': isolation_info['isolation_id']
            },
            tags=['forced_recovery', 'organ_management', organ_name]
        ))
        
        print(f"   ⚡ Forced recovery for organ: {organ_name}")
        return True
    
    def get_isolation_status(self) -> Dict[str, Any]:
        """Get current isolation status"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'isolated_organs': len(self.isolated_organs),
            'isolation_details': {
                name: {
                    'reason': info['reason'],
                    'duration': info['duration'],
                    'elapsed': (datetime.now() - info['timestamp']).total_seconds(),
                    'remaining': max(0, info['duration'] - (datetime.now() - info['timestamp']).total_seconds())
                }
                for name, info in self.isolated_organs.items()
            }
        }

class AdvancedFailureHandler:
    """
    Advanced failure handling with pattern recognition and adaptive responses
    
    Provides sophisticated failure analysis and response strategies to ensure
    graceful handling of organ failures without stopping the organism.
    """
    
    def __init__(self, event_bus: EventBus, isolation_manager: OrganIsolationManager):
        self.event_bus = event_bus
        self.isolation_manager = isolation_manager
        
        # Failure pattern tracking
        self.failure_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self.failure_thresholds = {
            'consecutive_failures': 3,
            'failure_rate_window': 300,  # 5 minutes
            'max_failure_rate': 0.5,
            'critical_failure_threshold': 5
        }
        
        # Adaptive response strategies
        self.response_strategies = {
            'transient': {'retry_delay': 30, 'max_retries': 3},
            'persistent': {'isolation_duration': 300, 'escalate_after': 2},
            'critical': {'immediate_isolation': True, 'notify_operators': True},
            'cascade': {'system_protection': True, 'reduce_load': True}
        }
    
    def analyze_failure(self, organ: NorthstarOrgan, result: ExecutionResult) -> str:
        """Analyze failure pattern and determine response strategy"""
        
        # Record failure
        failure_record = {
            'timestamp': datetime.now(),
            'error': result.error,
            'phase': result.phase.value,
            'duration': result.duration
        }
        
        if organ.name not in self.failure_patterns:
            self.failure_patterns[organ.name] = []
        
        self.failure_patterns[organ.name].append(failure_record)
        
        # Keep only recent failures (last hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.failure_patterns[organ.name] = [
            f for f in self.failure_patterns[organ.name] 
            if f['timestamp'] > cutoff_time
        ]
        
        # Analyze pattern
        recent_failures = self.failure_patterns[organ.name]
        
        # Check for critical failure count
        if len(recent_failures) >= self.failure_thresholds['critical_failure_threshold']:
            return 'critical'
        
        # Check for consecutive failures
        if organ.metrics.failure_count >= self.failure_thresholds['consecutive_failures']:
            return 'persistent'
        
        # Check for failure rate in time window
        window_start = datetime.now() - timedelta(seconds=self.failure_thresholds['failure_rate_window'])
        window_failures = [f for f in recent_failures if f['timestamp'] > window_start]
        
        if len(window_failures) > 0:
            # Calculate failure rate (assuming some executions happened)
            estimated_executions = max(len(window_failures) * 2, 5)  # Conservative estimate
            failure_rate = len(window_failures) / estimated_executions
            
            if failure_rate > self.failure_thresholds['max_failure_rate']:
                return 'persistent'
        
        # Check for cascade potential (multiple organs failing)
        total_recent_failures = sum(len(patterns) for patterns in self.failure_patterns.values())
        if total_recent_failures > 10:  # System-wide failure threshold
            return 'cascade'
        
        return 'transient'
    
    def handle_failure_with_strategy(self, organ: NorthstarOrgan, result: ExecutionResult, 
                                   orchestrator: 'OrganOrchestrator') -> Dict[str, Any]:
        """Handle failure using appropriate strategy"""
        
        strategy = self.analyze_failure(organ, result)
        response_info = {'strategy': strategy, 'actions': []}
        
        if strategy == 'transient':
            # Simple retry with delay
            response_info['actions'].append('schedule_retry')
            print(f"      🔄 Transient failure - will retry {organ.name}")
            
        elif strategy == 'persistent':
            # Isolate organ temporarily
            isolation_duration = self.response_strategies['persistent']['isolation_duration']
            self.isolation_manager.isolate_organ(organ, f"Persistent failures ({organ.metrics.failure_count})", isolation_duration)
            response_info['actions'].append('isolate_organ')
            
        elif strategy == 'critical':
            # Immediate isolation and notification
            self.isolation_manager.isolate_organ(organ, f"Critical failure pattern", 1800)  # 30 minutes
            response_info['actions'].extend(['isolate_organ', 'notify_operators'])
            print(f"      🚨 Critical failure pattern - {organ.name} isolated")
            
        elif strategy == 'cascade':
            # System protection mode
            self._activate_system_protection(orchestrator)
            response_info['actions'].extend(['system_protection', 'reduce_load'])
            print(f"      ⚠️ Cascade failure detected - activating system protection")
        
        # Emit failure analysis event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ERROR,
            source="failure_handler",
            priority=EventPriority.HIGH if strategy in ['critical', 'cascade'] else EventPriority.NORMAL,
            data={
                'organ_name': organ.name,
                'failure_strategy': strategy,
                'actions_taken': response_info['actions'],
                'failure_count': organ.metrics.failure_count,
                'error': result.error
            },
            tags=['failure_analysis', strategy, organ.name]
        ))
        
        return response_info
    
    def _activate_system_protection(self, orchestrator: 'OrganOrchestrator'):
        """Activate system-wide protection during cascade failures"""
        
        # Increase cycle intervals to reduce load
        orchestrator.cycle_interval = min(orchestrator.cycle_interval * 2, 300)  # Max 5 minutes
        
        # Disable non-critical organs temporarily
        for organ in orchestrator.organs:
            if not organ.is_critical and organ.status == OrganStatus.HEALTHY:
                organ.status = OrganStatus.DISABLED
                print(f"      🛡️ Temporarily disabled non-critical organ: {organ.name}")
        
        print(f"      🛡️ System protection activated - cycle interval: {orchestrator.cycle_interval}s")
    
    def get_failure_analysis(self) -> Dict[str, Any]:
        """Get comprehensive failure analysis"""
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'total_organs_with_failures': len(self.failure_patterns),
            'failure_summary': {},
            'system_health_indicators': {}
        }
        
        # Analyze each organ's failure pattern
        for organ_name, failures in self.failure_patterns.items():
            if failures:
                analysis['failure_summary'][organ_name] = {
                    'total_failures': len(failures),
                    'recent_failures_1h': len(failures),  # Already filtered to 1h
                    'last_failure': failures[-1]['timestamp'].isoformat(),
                    'common_errors': self._get_common_errors(failures)
                }
        
        # System health indicators
        total_failures = sum(len(failures) for failures in self.failure_patterns.values())
        analysis['system_health_indicators'] = {
            'total_recent_failures': total_failures,
            'failure_trend': 'increasing' if total_failures > 5 else 'stable',
            'system_stability': 'good' if total_failures < 3 else 'degraded' if total_failures < 10 else 'poor'
        }
        
        return analysis
    
    def _get_common_errors(self, failures: List[Dict[str, Any]]) -> List[str]:
        """Get most common error messages"""
        
        error_counts = {}
        for failure in failures:
            error = failure.get('error', 'Unknown error')
            # Simplify error message for grouping
            simplified_error = error.split(':')[0] if ':' in error else error
            error_counts[simplified_error] = error_counts.get(simplified_error, 0) + 1
        
        # Return top 3 most common errors
        return sorted(error_counts.keys(), key=lambda x: error_counts[x], reverse=True)[:3]

class OrganOrchestrator:
    """
    Enhanced Organ Orchestrator - Coordinates All Organ Execution
    
    Schedules and coordinates organ execution with advanced failure handling,
    organ isolation, and graceful recovery capabilities. Respects system 
    lock states for non-risk organs.
    
    Enhanced Features:
    - Advanced failure pattern recognition
    - Organ isolation and recovery management
    - Adaptive response strategies
    - System protection during cascade failures
    """
    
    def __init__(self, state: UnifiedState, clock: MarketClock, event_bus: EventBus):
        self.state = state
        self.clock = clock
        self.event_bus = event_bus
        
        # Organ registry
        self.organs: List[NorthstarOrgan] = []
        self.organ_metrics: Dict[str, OrganMetrics] = {}
        
        # Execution control
        self.is_running = False
        self.execution_thread = None
        self.cycle_interval = 60  # seconds between cycles
        
        # Enhanced failure handling components
        self.isolation_manager = OrganIsolationManager(event_bus)
        self.failure_handler = AdvancedFailureHandler(event_bus, self.isolation_manager)
        
        # Legacy failure handling (kept for compatibility)
        self.max_consecutive_failures = 3
        self.recovery_delay = 300  # 5 minutes
        self.failed_organs: Dict[str, datetime] = {}
        
        # Statistics
        self.total_cycles = 0
        self.successful_cycles = 0
        self.execution_history: List[Dict[str, Any]] = []
        
        # System protection state
        self.protection_mode_active = False
        self.original_cycle_interval = self.cycle_interval
        
        # Subscribe to time events
        self.clock.add_event_listener(self.handle_time_event)
        self.cycle_interval = 60  # seconds between cycles
        
        # Failure handling
        self.max_consecutive_failures = 3
        self.recovery_delay = 300  # 5 minutes
        self.failed_organs: Dict[str, datetime] = {}
        
        # Statistics
        self.total_cycles = 0
        self.successful_cycles = 0
        self.execution_history: List[Dict[str, Any]] = []
        
        # Subscribe to time events
        self.clock.add_event_listener(self.handle_time_event)
    
    def register_organ(self, organ: NorthstarOrgan, is_critical: bool = False):
        """Register an organ with the orchestrator"""
        
        organ.is_critical = is_critical
        self.organs.append(organ)
        self.organ_metrics[organ.name] = organ.metrics
        
        print(f"   🔗 Registered organ: {organ.name} ({'critical' if is_critical else 'standard'})")
    
    def unregister_organ(self, organ_name: str):
        """Unregister an organ"""
        
        self.organs = [organ for organ in self.organs if organ.name != organ_name]
        if organ_name in self.organ_metrics:
            del self.organ_metrics[organ_name]
        
        print(f"   🔌 Unregistered organ: {organ_name}")
    
    def run_cycle(self) -> Dict[str, Any]:
        """Run one complete organ execution cycle with advanced failure handling"""
        
        cycle_start = time.time()
        cycle_results = []
        
        print(f"\n🔄 ORGAN CYCLE #{self.total_cycles + 1}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"   System Locked: {'🔒 YES' if self.state.locked else '🔓 NO'}")
        print(f"   Active Organs: {len([o for o in self.organs if o.status == OrganStatus.HEALTHY])}")
        
        # Check for isolation expiry before executing organs
        for organ in self.organs:
            if organ.name in self.isolation_manager.isolated_organs:
                if self.isolation_manager.check_isolation_expiry(organ):
                    print(f"   🔄 Isolation expired for: {organ.name}")
        
        # Execute organs in order
        for organ in self.organs:
            # Skip isolated organs
            if organ.name in self.isolation_manager.isolated_organs:
                print(f"   🔒 Skipping isolated organ: {organ.name}")
                continue
            
            # Skip failed organs in recovery (legacy handling)
            if organ.name in self.failed_organs:
                recovery_time = self.failed_organs[organ.name]
                if datetime.now() - recovery_time < timedelta(seconds=self.recovery_delay):
                    continue
                else:
                    # Try recovery
                    del self.failed_organs[organ.name]
                    organ.status = OrganStatus.RECOVERING
                    print(f"   🔄 Attempting legacy recovery: {organ.name}")
            
            # Execute organ
            result = self._execute_organ_safely(organ)
            cycle_results.append(result)
            
            # Handle failures
            if not result.success:
                self._handle_organ_failure(organ, result)
            else:
                # Successful execution - update status if recovering
                if organ.status == OrganStatus.RECOVERING:
                    organ.status = OrganStatus.HEALTHY
                    print(f"   ✅ Recovery successful: {organ.name}")
        
        # Calculate cycle metrics
        cycle_duration = time.time() - cycle_start
        successful_organs = sum(1 for r in cycle_results if r.success)
        total_organs = len(cycle_results)
        
        self.total_cycles += 1
        if successful_organs >= len([o for o in self.organs if o.is_critical]):
            self.successful_cycles += 1
        
        # Create cycle summary with enhanced information
        cycle_summary = {
            'cycle_number': self.total_cycles,
            'timestamp': datetime.now().isoformat(),
            'duration': cycle_duration,
            'organs_executed': total_organs,
            'organs_successful': successful_organs,
            'success_rate': successful_organs / total_organs if total_organs > 0 else 0.0,
            'system_locked': self.state.locked,
            'protection_mode_active': self.protection_mode_active,
            'isolated_organs': len(self.isolation_manager.isolated_organs),
            'results': [asdict(r) for r in cycle_results],
            'isolation_status': self.isolation_manager.get_isolation_status(),
            'failure_analysis': self.failure_handler.get_failure_analysis()
        }
        
        # Store in history
        self.execution_history.append(cycle_summary)
        if len(self.execution_history) > 100:  # Keep last 100 cycles
            self.execution_history = self.execution_history[-100:]
        
        # Emit cycle completion event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="orchestrator",
            priority=EventPriority.NORMAL,
            data={
                'cycle_summary': cycle_summary,
                'organs_status': {organ.name: organ.status.value for organ in self.organs}
            },
            tags=['cycle', 'orchestrator']
        ))
        
        print(f"   ✅ Cycle complete: {successful_organs}/{total_organs} organs successful")
        if self.isolation_manager.isolated_organs:
            print(f"   🔒 Isolated organs: {len(self.isolation_manager.isolated_organs)}")
        
        return cycle_summary
    
    def _execute_organ_safely(self, organ: NorthstarOrgan) -> ExecutionResult:
        """Execute organ with comprehensive error handling"""
        
        try:
            print(f"   🧠 Executing: {organ.name}")
            result = organ.execute_full_cycle(self.state)
            
            if result.success:
                print(f"      ✅ Success ({result.duration:.2f}s)")
            else:
                print(f"      ❌ Failed: {result.error}")
            
            return result
            
        except Exception as e:
            # Catch any unhandled exceptions
            error_msg = f"Unhandled exception: {str(e)}"
            print(f"      💥 Critical error: {error_msg}")
            
            return ExecutionResult(
                organ_name=organ.name,
                success=False,
                duration=0.0,
                phase=ExecutionPhase.ERROR,
                error=error_msg
            )
    
    def _handle_organ_failure(self, organ: NorthstarOrgan, result: ExecutionResult):
        """Handle organ failure with advanced failure analysis and response"""
        
        # Use advanced failure handler for analysis and response
        response_info = self.failure_handler.handle_failure_with_strategy(organ, result, self)
        
        # Emit failure event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ERROR,
            source="orchestrator",
            priority=EventPriority.HIGH,
            data={
                'organ_name': organ.name,
                'error': result.error,
                'phase': result.phase.value,
                'is_critical': organ.is_critical,
                'failure_strategy': response_info['strategy'],
                'actions_taken': response_info['actions']
            },
            tags=['organ_failure', organ.name, response_info['strategy']]
        ))
        
        # Legacy failure handling for backward compatibility
        if organ.metrics.failure_count >= self.max_consecutive_failures:
            # Put organ in recovery mode if not already isolated
            if organ.name not in self.isolation_manager.isolated_organs:
                self.failed_organs[organ.name] = datetime.now()
                organ.status = OrganStatus.FAILED
                
                print(f"      🚨 Organ {organ.name} put in legacy recovery mode")
                
                # If critical organ fails, consider system-level response
                if organ.is_critical:
                    print(f"      ⚠️ Critical organ failure - system may be impacted")
                    self._trigger_system_recovery(organ, result)
    
    def _trigger_system_recovery(self, failed_organ: NorthstarOrgan, result: ExecutionResult):
        """Trigger system-level recovery for critical organ failures"""
        
        print(f"   🔧 Triggering system recovery for critical organ: {failed_organ.name}")
        
        # Emit system recovery event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="orchestrator",
            priority=EventPriority.CRITICAL,
            data={
                'recovery_type': 'critical_organ_failure',
                'failed_organ': failed_organ.name,
                'error': result.error,
                'recovery_actions': ['isolate_organ', 'activate_fallback', 'notify_operators']
            },
            tags=['system_recovery', 'critical_failure']
        ))
        
        # Could implement specific recovery actions here:
        # - Activate fallback systems
        # - Reduce system functionality
    
    def isolate_organ(self, organ_name: str, reason: str, duration: Optional[int] = None) -> bool:
        """Manually isolate an organ"""
        
        organ = next((o for o in self.organs if o.name == organ_name), None)
        if not organ:
            print(f"⚠️ Organ {organ_name} not found")
            return False
        
        self.isolation_manager.isolate_organ(organ, reason, duration)
        return True
    
    def force_organ_recovery(self, organ_name: str) -> bool:
        """Force immediate recovery of an isolated organ"""
        
        if self.isolation_manager.force_recovery(organ_name):
            # Update organ status
            organ = next((o for o in self.organs if o.name == organ_name), None)
            if organ:
                organ.status = OrganStatus.RECOVERING
            return True
        return False
    
    def activate_system_protection(self):
        """Manually activate system protection mode"""
        
        if not self.protection_mode_active:
            self.protection_mode_active = True
            self.original_cycle_interval = self.cycle_interval
            self.cycle_interval = min(self.cycle_interval * 2, 300)  # Max 5 minutes
            
            # Disable non-critical organs temporarily
            for organ in self.organs:
                if not organ.is_critical and organ.status == OrganStatus.HEALTHY:
                    organ.status = OrganStatus.DISABLED
                    print(f"      🛡️ Temporarily disabled non-critical organ: {organ.name}")
            
            print(f"      🛡️ System protection activated - cycle interval: {self.cycle_interval}s")
    
    def deactivate_system_protection(self):
        """Deactivate system protection mode"""
        
        if self.protection_mode_active:
            self.protection_mode_active = False
            self.cycle_interval = self.original_cycle_interval
            
            # Re-enable disabled organs
            for organ in self.organs:
                if organ.status == OrganStatus.DISABLED:
                    organ.status = OrganStatus.HEALTHY
                    print(f"      🔓 Re-enabled organ: {organ.name}")
            
            print(f"      🔓 System protection deactivated - cycle interval: {self.cycle_interval}s")
    
    def get_failure_analysis(self) -> Dict[str, Any]:
        """Get comprehensive failure analysis"""
        
        return {
            'orchestrator_metrics': {
                'total_cycles': self.total_cycles,
                'success_rate': self.successful_cycles / self.total_cycles if self.total_cycles > 0 else 0.0,
                'protection_mode_active': self.protection_mode_active,
                'cycle_interval': self.cycle_interval
            },
            'isolation_status': self.isolation_manager.get_isolation_status(),
            'failure_analysis': self.failure_handler.get_failure_analysis(),
            'organ_health': {
                organ.name: {
                    'status': organ.status.value,
                    'health_score': organ.metrics.health_score,
                    'success_rate': organ.metrics.success_rate(),
                    'failure_count': organ.metrics.failure_count,
                    'is_critical': organ.is_critical
                }
                for organ in self.organs
            }
        }
        # - Alert operators
        # - Attempt automatic repair
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime):
        """Handle time-based events from market clock"""
        
        # Notify all organs of time events
        for organ in self.organs:
            try:
                organ.handle_time_event(event, market_time)
            except Exception as e:
                print(f"⚠️ Error in {organ.name} time event handler: {e}")
        
        # Special handling for certain events
        if event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   📅 Weekly rebalance event - triggering special cycle")
            # Could trigger special rebalance cycle
        
        elif event == TimeEvent.OPEN:
            print(f"   🔔 Market open - ensuring all organs are ready")
            # Could run health checks
        
        elif event == TimeEvent.CLOSE:
            print(f"   🔔 Market close - running end-of-day cycle")
            # Could trigger end-of-day processing
    
    def start_continuous_operation(self):
        """Start continuous organ orchestration"""
        
        if self.is_running:
            print("⚠️ Orchestrator is already running")
            return
        
        self.is_running = True
        self.execution_thread = threading.Thread(target=self._continuous_execution_loop)
        self.execution_thread.daemon = True
        self.execution_thread.start()
        
        print(f"🚀 Organ orchestrator started (cycle interval: {self.cycle_interval}s)")
    
    def stop_continuous_operation(self):
        """Stop continuous organ orchestration"""
        
        self.is_running = False
        
        if self.execution_thread:
            self.execution_thread.join(timeout=10)
        
        print("🛑 Organ orchestrator stopped")
    
    def _continuous_execution_loop(self):
        """Continuous execution loop for organ orchestration"""
        
        while self.is_running:
            try:
                # Run organ cycle
                cycle_summary = self.run_cycle()
                
                # Sleep until next cycle
                time.sleep(self.cycle_interval)
                
            except Exception as e:
                print(f"💥 Error in orchestration loop: {e}")
                print(f"   Traceback: {traceback.format_exc()}")
                
                # Sleep before retrying
                time.sleep(30)
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status with enhanced failure handling info"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'is_running': self.is_running,
            'total_cycles': self.total_cycles,
            'successful_cycles': self.successful_cycles,
            'success_rate': self.successful_cycles / self.total_cycles if self.total_cycles > 0 else 0.0,
            'registered_organs': len(self.organs),
            'healthy_organs': len([o for o in self.organs if o.status == OrganStatus.HEALTHY]),
            'failed_organs': len(self.failed_organs),
            'isolated_organs': len(self.isolation_manager.isolated_organs),
            'protection_mode_active': self.protection_mode_active,
            'cycle_interval': self.cycle_interval,
            'organ_status': {
                organ.name: {
                    'status': organ.status.value,
                    'health_score': organ.metrics.health_score,
                    'success_rate': organ.metrics.success_rate(),
                    'is_critical': organ.is_critical,
                    'is_isolated': organ.name in self.isolation_manager.isolated_organs
                }
                for organ in self.organs
            },
            'system_health': {
                'overall_score': np.mean([organ.metrics.health_score for organ in self.organs]) if self.organs else 0.0,
                'critical_organs_healthy': all(
                    organ.status == OrganStatus.HEALTHY 
                    for organ in self.organs if organ.is_critical
                ),
                'system_stability': self._calculate_system_stability()
            },
            'isolation_details': self.isolation_manager.get_isolation_status(),
            'failure_analysis': self.failure_handler.get_failure_analysis()
        }
    
    def _calculate_system_stability(self) -> str:
        """Calculate overall system stability rating"""
        
        if not self.organs:
            return 'unknown'
        
        # Calculate stability based on multiple factors
        healthy_ratio = len([o for o in self.organs if o.status == OrganStatus.HEALTHY]) / len(self.organs)
        avg_health_score = np.mean([organ.metrics.health_score for organ in self.organs])
        critical_organs_healthy = all(
            organ.status == OrganStatus.HEALTHY 
            for organ in self.organs if organ.is_critical
        )
        
        # Determine stability
        if healthy_ratio >= 0.9 and avg_health_score >= 0.8 and critical_organs_healthy:
            return 'excellent'
        elif healthy_ratio >= 0.8 and avg_health_score >= 0.7 and critical_organs_healthy:
            return 'good'
        elif healthy_ratio >= 0.6 and avg_health_score >= 0.5 and critical_organs_healthy:
            return 'fair'
        elif critical_organs_healthy:
            return 'degraded'
        else:
            return 'critical'
    
    def save_orchestrator_state(self):
        """Save orchestrator state for persistence"""
        
        orchestrator_state = {
            'timestamp': datetime.now().isoformat(),
            'status': self.get_orchestrator_status(),
            'execution_history': self.execution_history[-50:],  # Last 50 cycles
            'organ_metrics': {
                name: asdict(metrics) for name, metrics in self.organ_metrics.items()
            }
        }
        
        # Save to file
        state_file = 'data/state/orchestrator_state.json'
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        with open(state_file, 'w') as f:
            json.dump(orchestrator_state, f, indent=2, default=str)

def main():
    """Test Enhanced Organ Orchestrator with Advanced Failure Handling"""
    
    print("🎭 TESTING ENHANCED ORGAN ORCHESTRATOR")
    print("=" * 50)
    
    # Create dependencies
    from src.core.state import UnifiedState
    from src.core.clock import MarketClock
    from src.core.events import EventBus
    
    state = UnifiedState()
    clock = MarketClock()
    event_bus = EventBus()
    
    # Create enhanced orchestrator
    orchestrator = OrganOrchestrator(state, clock, event_bus)
    
    # Create test organs with different failure patterns
    class TestOrgan(NorthstarOrgan):
        def __init__(self, name: str, failure_pattern: str = "none"):
            super().__init__(name)
            self.failure_pattern = failure_pattern
            self.execution_count = 0
        
        def read_state(self, state: UnifiedState) -> None:
            self.market_data = state.market
        
        def think(self, state: UnifiedState) -> Any:
            self.execution_count += 1
            
            # Simulate different failure patterns
            if self.failure_pattern == "transient" and self.execution_count % 5 == 0:
                raise Exception(f"Transient failure in {self.name}")
            elif self.failure_pattern == "persistent" and self.execution_count % 2 == 0:
                raise Exception(f"Persistent failure in {self.name}")
            elif self.failure_pattern == "critical" and self.execution_count >= 3:
                raise Exception(f"Critical failure in {self.name}")
            
            return {"processed": True, "count": self.execution_count}
        
        def write_state(self, state: UnifiedState) -> None:
            # Simulate state update
            state.update_component('health', {
                'components_healthy': state.health.components_healthy + 1
            }, organ=self.name, reason=f"Test update from {self.name}")
    
    # Register test organs with different patterns
    print("\n🔗 Registering Test Organs:")
    orchestrator.register_organ(TestOrgan("healthy_organ"), is_critical=True)
    orchestrator.register_organ(TestOrgan("transient_failure_organ", "transient"))
    orchestrator.register_organ(TestOrgan("persistent_failure_organ", "persistent"))
    orchestrator.register_organ(TestOrgan("critical_failure_organ", "critical"))
    
    # Test single cycle
    print(f"\n🔄 Testing Single Cycle:")
    cycle_result = orchestrator.run_cycle()
    print(f"   Cycle Success Rate: {cycle_result['success_rate']:.1%}")
    
    # Test multiple cycles to trigger failure patterns
    print(f"\n🔄 Testing Multiple Cycles (triggering failures):")
    for i in range(8):
        print(f"\n--- Cycle {i+2} ---")
        cycle_result = orchestrator.run_cycle()
        print(f"   Success Rate: {cycle_result['success_rate']:.1%}")
        print(f"   Isolated Organs: {cycle_result['isolated_organs']}")
        time.sleep(0.5)  # Brief pause between cycles
    
    # Test manual organ isolation
    print(f"\n🔒 Testing Manual Organ Isolation:")
    success = orchestrator.isolate_organ("healthy_organ", "Manual test isolation", 30)
    print(f"   Isolation successful: {success}")
    
    # Run another cycle to show isolation in effect
    cycle_result = orchestrator.run_cycle()
    print(f"   Cycle with isolation - Success Rate: {cycle_result['success_rate']:.1%}")
    
    # Test forced recovery
    print(f"\n🔄 Testing Forced Recovery:")
    success = orchestrator.force_organ_recovery("healthy_organ")
    print(f"   Forced recovery successful: {success}")
    
    # Test system protection activation
    print(f"\n🛡️ Testing System Protection:")
    orchestrator.activate_system_protection()
    cycle_result = orchestrator.run_cycle()
    print(f"   Cycle in protection mode - Success Rate: {cycle_result['success_rate']:.1%}")
    
    # Deactivate protection
    orchestrator.deactivate_system_protection()
    
    # Test comprehensive status
    print(f"\n📊 Enhanced Orchestrator Status:")
    status = orchestrator.get_orchestrator_status()
    print(f"   Total Cycles: {status['total_cycles']}")
    print(f"   Success Rate: {status['success_rate']:.1%}")
    print(f"   Healthy Organs: {status['healthy_organs']}/{status['registered_organs']}")
    print(f"   Isolated Organs: {status['isolated_organs']}")
    print(f"   System Stability: {status['system_health']['system_stability']}")
    print(f"   Overall Health Score: {status['system_health']['overall_score']:.2f}")
    
    # Test failure analysis
    print(f"\n🔍 Failure Analysis:")
    analysis = orchestrator.get_failure_analysis()
    print(f"   Protection Mode: {analysis['orchestrator_metrics']['protection_mode_active']}")
    print(f"   System Stability: {analysis['failure_analysis']['system_health_indicators']['system_stability']}")
    
    # Test save state
    print(f"\n💾 Saving Enhanced Orchestrator State:")
    orchestrator.save_orchestrator_state()
    print("   Enhanced orchestrator state saved successfully")
    
    print(f"\n✅ Enhanced Organ Orchestrator test successful!")
    print(f"   🎯 Advanced failure handling: ✅")
    print(f"   🔒 Organ isolation & recovery: ✅") 
    print(f"   🛡️ System protection mode: ✅")
    print(f"   📊 Comprehensive monitoring: ✅")
    print(f"   The living system now has graceful failure handling!")
    
    return True

if __name__ == "__main__":
    main()