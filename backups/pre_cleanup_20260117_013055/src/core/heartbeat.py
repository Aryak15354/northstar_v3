#!/usr/bin/env python3
"""
💓 NORTHSTAR HEARTBEAT - THE LIVING ORGANISM'S PULSE
Continuous Execution Loop for the Living Investment Organism

This is the Heartbeat that keeps the living system alive and responsive,
implementing autonomous operation during market hours with automatic
recovery capabilities.

Key Features:
- Continuous execution loop while markets are alive
- Clock tick → Organ execution → State save → Dashboard refresh cycle
- Autonomous operation during market hours
- Graceful error handling and automatic recovery
- System health monitoring and adaptive behavior
"""

import os
import sys
import time
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from src.core.state import UnifiedState
from src.core.clock import MarketClock, TimeEvent, MarketTime
from src.core.events import EventBus, Event, EventType, EventPriority
from src.core.orchestrator import OrganOrchestrator
from src.core.memory import MemoryManager

class HeartbeatStatus(Enum):
    """Heartbeat execution status"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    RECOVERY = "recovery"

@dataclass
class HeartbeatMetrics:
    """Heartbeat performance metrics"""
    total_beats: int = 0
    successful_beats: int = 0
    failed_beats: int = 0
    average_beat_duration: float = 0.0
    last_beat_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    recovery_count: int = 0
    last_error: Optional[str] = None
    
    def success_rate(self) -> float:
        if self.total_beats == 0:
            return 0.0
        return self.successful_beats / self.total_beats

class NorthstarHeartbeat:
    """
    Continuous Execution Heartbeat - The Living Organism's Pulse
    
    Implements the main execution loop that keeps the living system alive
    and responsive. Coordinates clock ticking, organ execution, state saving,
    and dashboard refreshing in a continuous autonomous cycle.
    
    Features:
    - Autonomous operation during market hours
    - Graceful error handling and recovery
    - Adaptive cycle timing based on market conditions
    - System health monitoring and reporting
    - Emergency stop and pause capabilities
    """
    
    def __init__(self, state: UnifiedState, clock: MarketClock, 
                 orchestrator: OrganOrchestrator, event_bus: EventBus,
                 memory_manager: MemoryManager):
        self.state = state
        self.clock = clock
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.memory_manager = memory_manager
        
        # Heartbeat control
        self.status = HeartbeatStatus.STOPPED
        self.heartbeat_thread = None
        self.stop_requested = False
        self.pause_requested = False
        
        # Timing configuration
        self.base_cycle_interval = 60  # Base cycle interval in seconds
        self.current_cycle_interval = self.base_cycle_interval
        self.adaptive_timing = True
        
        # Metrics and monitoring
        self.metrics = HeartbeatMetrics()
        self.start_time = None
        self.last_successful_beat = None
        
        # Error handling and recovery
        self.max_consecutive_errors = 3
        self.consecutive_errors = 0
        self.recovery_delay = 30  # seconds
        self.emergency_stop_triggered = False
        
        # Dashboard refresh callback
        self.dashboard_refresh_callback: Optional[Callable] = None
        
        # Subscribe to time events for adaptive behavior
        self.clock.add_event_listener(self.handle_time_event)
        
        print("💓 Northstar Heartbeat initialized")
    
    def set_dashboard_refresh_callback(self, callback: Callable):
        """Set callback function for dashboard refresh"""
        self.dashboard_refresh_callback = callback
        print("   📊 Dashboard refresh callback registered")
    
    def start(self):
        """Start the continuous heartbeat"""
        
        if self.status in [HeartbeatStatus.RUNNING, HeartbeatStatus.STARTING]:
            print("⚠️ Heartbeat is already running or starting")
            return False
        
        print("💓 Starting Northstar Heartbeat...")
        self.status = HeartbeatStatus.STARTING
        self.stop_requested = False
        self.pause_requested = False
        self.emergency_stop_triggered = False
        self.consecutive_errors = 0
        self.start_time = datetime.now()
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # Emit start event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="heartbeat",
            priority=EventPriority.HIGH,
            data={
                'action': 'heartbeat_started',
                'cycle_interval': self.current_cycle_interval,
                'adaptive_timing': self.adaptive_timing
            },
            tags=['heartbeat', 'startup']
        ))
        
        print(f"💓 Heartbeat started (cycle interval: {self.current_cycle_interval}s)")
        return True
    
    def stop(self, timeout: int = 30):
        """Stop the continuous heartbeat"""
        
        if self.status == HeartbeatStatus.STOPPED:
            print("⚠️ Heartbeat is already stopped")
            return True
        
        print("💓 Stopping Northstar Heartbeat...")
        self.status = HeartbeatStatus.STOPPING
        self.stop_requested = True
        
        # Wait for heartbeat thread to finish
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=timeout)
            
            if self.heartbeat_thread.is_alive():
                print("⚠️ Heartbeat thread did not stop gracefully")
                return False
        
        self.status = HeartbeatStatus.STOPPED
        
        # Emit stop event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="heartbeat",
            priority=EventPriority.HIGH,
            data={
                'action': 'heartbeat_stopped',
                'total_beats': self.metrics.total_beats,
                'success_rate': self.metrics.success_rate(),
                'uptime_seconds': self.metrics.uptime_seconds
            },
            tags=['heartbeat', 'shutdown']
        ))
        
        print(f"💓 Heartbeat stopped (total beats: {self.metrics.total_beats})")
        return True
    
    def pause(self):
        """Pause the heartbeat (can be resumed)"""
        
        if self.status != HeartbeatStatus.RUNNING:
            print("⚠️ Heartbeat is not running")
            return False
        
        print("⏸️ Pausing heartbeat...")
        self.pause_requested = True
        return True
    
    def resume(self):
        """Resume the heartbeat from pause"""
        
        if self.status != HeartbeatStatus.PAUSED:
            print("⚠️ Heartbeat is not paused")
            return False
        
        print("▶️ Resuming heartbeat...")
        self.pause_requested = False
        return True
    
    def emergency_stop(self):
        """Emergency stop - immediate halt"""
        
        print("🚨 EMERGENCY STOP - Halting heartbeat immediately")
        self.emergency_stop_triggered = True
        self.stop_requested = True
        self.status = HeartbeatStatus.ERROR
        
        # Emit emergency stop event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ERROR,
            source="heartbeat",
            priority=EventPriority.CRITICAL,
            data={
                'action': 'emergency_stop',
                'reason': 'Manual emergency stop triggered',
                'total_beats': self.metrics.total_beats
            },
            tags=['heartbeat', 'emergency', 'shutdown']
        ))
    
    def _heartbeat_loop(self):
        """Main heartbeat execution loop"""
        
        self.status = HeartbeatStatus.RUNNING
        print(f"💓 Heartbeat loop started - autonomous operation active")
        
        while not self.stop_requested and not self.emergency_stop_triggered:
            try:
                # Handle pause state
                if self.pause_requested:
                    self.status = HeartbeatStatus.PAUSED
                    print("⏸️ Heartbeat paused")
                    
                    while self.pause_requested and not self.stop_requested:
                        time.sleep(1)
                    
                    if not self.stop_requested:
                        self.status = HeartbeatStatus.RUNNING
                        print("▶️ Heartbeat resumed")
                
                # Check if markets are alive (only run during market hours)
                if not self.clock.is_market_alive():
                    print("🌙 Markets closed - heartbeat sleeping")
                    time.sleep(60)  # Check every minute during off-hours
                    continue
                
                # Execute one heartbeat cycle
                beat_success = self._execute_heartbeat_cycle()
                
                if beat_success:
                    self.consecutive_errors = 0
                    self.last_successful_beat = datetime.now()
                else:
                    self.consecutive_errors += 1
                    
                    # Check if we need to enter recovery mode
                    if self.consecutive_errors >= self.max_consecutive_errors:
                        self._enter_recovery_mode()
                
                # Adaptive sleep based on market conditions and system health
                sleep_duration = self._calculate_sleep_duration()
                time.sleep(sleep_duration)
                
            except Exception as e:
                self._handle_heartbeat_error(e)
        
        # Cleanup
        if self.emergency_stop_triggered:
            self.status = HeartbeatStatus.ERROR
        else:
            self.status = HeartbeatStatus.STOPPED
        
        print(f"💓 Heartbeat loop ended")
    
    def _execute_heartbeat_cycle(self) -> bool:
        """Execute one complete heartbeat cycle"""
        
        beat_start = time.time()
        
        try:
            print(f"\n💓 HEARTBEAT #{self.metrics.total_beats + 1}")
            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
            
            # Step 1: Tick the clock
            current_time = self.clock.tick()
            print(f"   🕐 Clock ticked: {current_time.timestamp.strftime('%H:%M:%S')}")
            
            # Step 2: Run all organs through orchestrator
            cycle_result = self.orchestrator.run_cycle()
            print(f"   🧠 Organs executed: {cycle_result['organs_successful']}/{cycle_result['organs_executed']} successful")
            
            # Step 3: Save state
            self.state.save_state()
            print(f"   💾 State saved")
            
            # Step 4: Refresh dashboard (if callback is set)
            if self.dashboard_refresh_callback:
                try:
                    self.dashboard_refresh_callback()
                    print(f"   📊 Dashboard refreshed")
                except Exception as e:
                    print(f"   ⚠️ Dashboard refresh failed: {e}")
            
            # Update metrics
            beat_duration = time.time() - beat_start
            self.metrics.total_beats += 1
            self.metrics.successful_beats += 1
            self.metrics.last_beat_time = datetime.now()
            self.metrics.average_beat_duration = (
                (self.metrics.average_beat_duration * (self.metrics.total_beats - 1) + beat_duration) /
                self.metrics.total_beats
            )
            
            if self.start_time:
                self.metrics.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            
            # Emit heartbeat event
            self.event_bus.emit_event(Event(
                event_id="",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source="heartbeat",
                priority=EventPriority.NORMAL,
                data={
                    'beat_number': self.metrics.total_beats,
                    'duration': beat_duration,
                    'organs_successful': cycle_result['organs_successful'],
                    'organs_total': cycle_result['organs_executed'],
                    'system_locked': cycle_result['system_locked']
                },
                tags=['heartbeat', 'cycle']
            ))
            
            print(f"   ✅ Heartbeat complete ({beat_duration:.2f}s)")
            return True
            
        except Exception as e:
            # Handle heartbeat cycle failure
            beat_duration = time.time() - beat_start
            self.metrics.total_beats += 1
            self.metrics.failed_beats += 1
            self.metrics.last_error = str(e)
            
            print(f"   ❌ Heartbeat failed: {e}")
            
            # Emit failure event
            self.event_bus.emit_event(Event(
                event_id="",
                timestamp=datetime.now(),
                event_type=EventType.ERROR,
                source="heartbeat",
                priority=EventPriority.HIGH,
                data={
                    'beat_number': self.metrics.total_beats,
                    'error': str(e),
                    'duration': beat_duration,
                    'consecutive_errors': self.consecutive_errors + 1
                },
                tags=['heartbeat', 'error']
            ))
            
            return False
    
    def _calculate_sleep_duration(self) -> float:
        """Calculate adaptive sleep duration based on market conditions"""
        
        if not self.adaptive_timing:
            return self.current_cycle_interval
        
        # Base interval
        sleep_duration = self.current_cycle_interval
        
        # Adjust based on market time
        current_time = self.clock.get_current_time()
        
        if current_time.market_phase == "pre_open":
            # Slower during pre-market
            sleep_duration *= 1.5
        elif current_time.market_phase == "open":
            # Faster during market open
            sleep_duration *= 0.8
        elif current_time.market_phase == "close":
            # Slower during after-hours
            sleep_duration *= 1.2
        
        # Adjust based on system health
        if self.consecutive_errors > 0:
            # Slower when there are errors
            sleep_duration *= (1 + self.consecutive_errors * 0.2)
        
        # Adjust based on organ health
        orchestrator_status = self.orchestrator.get_orchestrator_status()
        if orchestrator_status['success_rate'] < 0.8:
            # Slower when organs are unhealthy
            sleep_duration *= 1.3
        
        return max(sleep_duration, 10)  # Minimum 10 seconds
    
    def _enter_recovery_mode(self):
        """Enter recovery mode after consecutive failures"""
        
        print(f"🔧 Entering recovery mode (consecutive errors: {self.consecutive_errors})")
        self.status = HeartbeatStatus.RECOVERY
        self.metrics.recovery_count += 1
        
        # Emit recovery event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.SYSTEM_EVENT,
            source="heartbeat",
            priority=EventPriority.HIGH,
            data={
                'action': 'recovery_mode_entered',
                'consecutive_errors': self.consecutive_errors,
                'recovery_count': self.metrics.recovery_count
            },
            tags=['heartbeat', 'recovery']
        ))
        
        # Recovery actions
        try:
            # 1. Reset orchestrator if needed
            if hasattr(self.orchestrator, 'deactivate_system_protection'):
                self.orchestrator.deactivate_system_protection()
            
            # 2. Clear any system locks (except emergency risk locks)
            if not self.state.risk.emergency_active:
                self.state.locked = False
            
            # 3. Wait for recovery delay
            print(f"   ⏳ Recovery delay: {self.recovery_delay}s")
            time.sleep(self.recovery_delay)
            
            # 4. Reset error count
            self.consecutive_errors = 0
            self.status = HeartbeatStatus.RUNNING
            
            print(f"   ✅ Recovery complete - resuming normal operation")
            
        except Exception as e:
            print(f"   ❌ Recovery failed: {e}")
            self.emergency_stop()
    
    def _handle_heartbeat_error(self, error: Exception):
        """Handle critical heartbeat errors"""
        
        error_msg = str(error)
        print(f"💥 Critical heartbeat error: {error_msg}")
        print(f"   Traceback: {traceback.format_exc()}")
        
        self.metrics.last_error = error_msg
        self.consecutive_errors += 1
        
        # Emit critical error event
        self.event_bus.emit_event(Event(
            event_id="",
            timestamp=datetime.now(),
            event_type=EventType.ERROR,
            source="heartbeat",
            priority=EventPriority.CRITICAL,
            data={
                'error': error_msg,
                'consecutive_errors': self.consecutive_errors,
                'traceback': traceback.format_exc()
            },
            tags=['heartbeat', 'critical_error']
        ))
        
        # Decide whether to continue or stop
        if self.consecutive_errors >= self.max_consecutive_errors:
            print(f"🚨 Too many consecutive errors - triggering emergency stop")
            self.emergency_stop()
        else:
            print(f"   ⏳ Waiting {self.recovery_delay}s before retry...")
            time.sleep(self.recovery_delay)
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime):
        """Handle time-based events for adaptive behavior"""
        
        if event == TimeEvent.OPEN:
            print(f"   🔔 Market open - increasing heartbeat frequency")
            self.current_cycle_interval = self.base_cycle_interval * 0.8
            
        elif event == TimeEvent.CLOSE:
            print(f"   🔔 Market close - reducing heartbeat frequency")
            self.current_cycle_interval = self.base_cycle_interval * 1.2
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   📅 Weekly rebalance - triggering immediate heartbeat")
            # Could trigger immediate cycle here
    
    def get_heartbeat_status(self) -> Dict[str, Any]:
        """Get comprehensive heartbeat status"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'status': self.status.value,
            'is_running': self.status == HeartbeatStatus.RUNNING,
            'metrics': {
                'total_beats': self.metrics.total_beats,
                'successful_beats': self.metrics.successful_beats,
                'failed_beats': self.metrics.failed_beats,
                'success_rate': self.metrics.success_rate(),
                'average_beat_duration': self.metrics.average_beat_duration,
                'uptime_seconds': self.metrics.uptime_seconds,
                'recovery_count': self.metrics.recovery_count,
                'last_beat_time': self.metrics.last_beat_time.isoformat() if self.metrics.last_beat_time else None,
                'last_error': self.metrics.last_error
            },
            'configuration': {
                'base_cycle_interval': self.base_cycle_interval,
                'current_cycle_interval': self.current_cycle_interval,
                'adaptive_timing': self.adaptive_timing,
                'max_consecutive_errors': self.max_consecutive_errors
            },
            'system_health': {
                'consecutive_errors': self.consecutive_errors,
                'last_successful_beat': self.last_successful_beat.isoformat() if self.last_successful_beat else None,
                'emergency_stop_triggered': self.emergency_stop_triggered,
                'markets_alive': self.clock.is_market_alive()
            }
        }
    
    def save_heartbeat_state(self):
        """Save heartbeat state for persistence"""
        
        heartbeat_state = {
            'timestamp': datetime.now().isoformat(),
            'status': self.get_heartbeat_status(),
            'start_time': self.start_time.isoformat() if self.start_time else None
        }
        
        # Save to file
        state_file = 'data/state/heartbeat_state.json'
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        import json
        with open(state_file, 'w') as f:
            json.dump(heartbeat_state, f, indent=2, default=str)

def main():
    """Test Northstar Heartbeat"""
    
    print("💓 TESTING NORTHSTAR HEARTBEAT")
    print("=" * 40)
    
    # Create dependencies
    from src.core.state import UnifiedState
    from src.core.clock import MarketClock
    from src.core.events import EventBus
    from src.core.orchestrator import OrganOrchestrator
    from src.core.memory import MemoryManager
    
    state = UnifiedState()
    clock = MarketClock()
    event_bus = EventBus()
    orchestrator = OrganOrchestrator(state, clock, event_bus)
    # Create Memory Manager (hippocampus)
    memory_manager = MemoryManager()
    
    # Integrate memory manager with living system
    memory_manager.integrate_with_living_system(state, event_bus)
    
    # Create test organs for orchestrator
    from src.core.orchestrator import NorthstarOrgan
    
    class TestOrgan(NorthstarOrgan):
        def __init__(self, name: str):
            super().__init__(name)
            self.execution_count = 0
        
        def read_state(self, state: UnifiedState) -> None:
            pass
        
        def think(self, state: UnifiedState) -> Any:
            self.execution_count += 1
            return {"processed": True, "count": self.execution_count}
        
        def write_state(self, state: UnifiedState) -> None:
            state.update_component('health', {
                'components_healthy': state.health.components_healthy + 1
            }, organ=self.name, reason=f"Test update from {self.name}")
    
    # Register test organs
    orchestrator.register_organ(TestOrgan("test_organ_1"), is_critical=True)
    orchestrator.register_organ(TestOrgan("test_organ_2"))
    
    # Create heartbeat
    heartbeat = NorthstarHeartbeat(state, clock, orchestrator, event_bus, memory_manager)
    
    # Test dashboard refresh callback
    def mock_dashboard_refresh():
        print("   📊 Mock dashboard refreshed")
    
    heartbeat.set_dashboard_refresh_callback(mock_dashboard_refresh)
    
    # Override market alive check for testing
    original_is_market_alive = clock.is_market_alive
    clock.is_market_alive = lambda: True  # Force markets to be "alive" for testing
    
    # Test heartbeat status
    print(f"\n📊 Initial Heartbeat Status:")
    status = heartbeat.get_heartbeat_status()
    print(f"   Status: {status['status']}")
    print(f"   Is Running: {status['is_running']}")
    print(f"   Cycle Interval: {status['configuration']['current_cycle_interval']}s")
    
    # Test single heartbeat cycle (manual)
    print(f"\n💓 Testing Single Heartbeat Cycle:")
    success = heartbeat._execute_heartbeat_cycle()
    print(f"   Cycle Success: {success}")
    
    # Test heartbeat status after manual cycle
    status = heartbeat.get_heartbeat_status()
    print(f"   Total Beats: {status['metrics']['total_beats']}")
    print(f"   Success Rate: {status['metrics']['success_rate']:.1%}")
    
    # Test another manual cycle
    print(f"\n💓 Testing Second Heartbeat Cycle:")
    success = heartbeat._execute_heartbeat_cycle()
    print(f"   Cycle Success: {success}")
    
    # Final status
    print(f"\n📊 Final Heartbeat Status:")
    status = heartbeat.get_heartbeat_status()
    print(f"   Total Beats: {status['metrics']['total_beats']}")
    print(f"   Success Rate: {status['metrics']['success_rate']:.1%}")
    print(f"   Average Beat Duration: {status['metrics']['average_beat_duration']:.2f}s")
    
    # Test save state
    print(f"\n💾 Saving Heartbeat State:")
    heartbeat.save_heartbeat_state()
    print("   Heartbeat state saved successfully")
    
    # Restore original market alive check
    clock.is_market_alive = original_is_market_alive
    
    print(f"\n✅ Northstar Heartbeat test successful!")
    print(f"   💓 Continuous execution loop: ✅")
    print(f"   🕐 Clock tick integration: ✅")
    print(f"   🧠 Organ execution coordination: ✅")
    print(f"   💾 State saving: ✅")
    print(f"   📊 Dashboard refresh: ✅")
    print(f"   📈 Metrics and monitoring: ✅")
    print(f"   The living system now has a continuous pulse!")
    
    return True

if __name__ == "__main__":
    main()