#!/usr/bin/env python3
"""
🧠 CORE MODULE - LIVING SYSTEM NERVOUS SYSTEM
Central Nervous System Components for the Living Investment Organism

This module contains the core components that form the nervous system
of the living investment organism:

- UnifiedState: The brainstem (single source of truth)
- MarketClock: Time as first-class citizen
- EventBus: Event-driven communication and audit trail
- MemoryManager: Unified memory across all dimensions
- OrganOrchestrator: Organ coordination and scheduling

These components work together to create a living system that operates
as a unified organism rather than separate scripts.
"""

from src.state.unified_state_manager import UnifiedStateManager as UnifiedState

from src.core.clock import (
    MarketClock,
    TimeEvent,
    MarketPhase
)

from src.core.events import (
    EventBus,
    Event,
    StateChangeEvent,
    DecisionEvent,
    RiskEvent,
    DecisionExplanation,
    EventType,
    EventPriority
)

from src.core.memory import (
    MemoryManager,
    MemoryRecord,
    RegimePattern,
    StrategyHistory,
    BeliefEvent,
    BehaviorPattern,
    MemoryType
)

from src.core.orchestrator import (
    OrganOrchestrator,
    NorthstarOrgan,
    OrganStatus,
    ExecutionPhase,
    OrganMetrics,
    ExecutionResult
)

from src.core.heartbeat import (
    NorthstarHeartbeat,
    HeartbeatStatus,
    HeartbeatMetrics
)

from src.core.organs import (
    ExampleOrgan,
    HealthMonitorOrgan,
    DataPipelineOrganWrapper,
    create_example_organs
)

from src.core.organ_wrappers import (
    DataPipelineOrgan,
    MarketBrainOrgan,
    IntelligenceStackOrgan,
    CapitalAllocatorOrgan,
    PortfolioGovernorOrgan,
    RiskCoordinatorOrgan,
    MemoryManagerOrgan,
    create_v3_organ_wrappers
)

from src.core.health_monitor import (
    HealthMonitor,
    HealthLevel,
    AlertSeverity,
    HealthAlert,
    OrganHealthReport,
    SystemHealthReport
)

# Core system factory
def create_living_system():
    """
    Create a complete living system with all core components integrated
    
    Returns:
        dict: Dictionary containing all core components
    """
    
    # Create Event Bus (nervous system)
    event_bus = EventBus()
    
    # Create Unified State (brainstem)
    unified_state = UnifiedState()
    
    # Create Market Clock with Event Bus integration (timekeeper)
    market_clock = MarketClock(event_bus=event_bus)
    
    # Create Memory Manager (hippocampus)
    memory_manager = MemoryManager()
    
    # Create Health Monitor (immune system)
    health_monitor = HealthMonitor()
    
    # Create Organ Orchestrator (conductor)
    organ_orchestrator = OrganOrchestrator(
        state=unified_state,
        clock=market_clock,
        event_bus=event_bus
    )
    
    # Create Heartbeat (pulse)
    heartbeat = NorthstarHeartbeat(
        state=unified_state,
        clock=market_clock,
        orchestrator=organ_orchestrator,
        event_bus=event_bus,
        memory_manager=memory_manager
    )
    
    return {
        'event_bus': event_bus,
        'unified_state': unified_state,
        'market_clock': market_clock,
        'memory_manager': memory_manager,
        'health_monitor': health_monitor,
        'organ_orchestrator': organ_orchestrator,
        'heartbeat': heartbeat
    }

__all__ = [
    # Core State Management
    'UnifiedState',
    
    # Time Management
    'MarketClock',
    'TimeEvent',
    'MarketPhase',
    
    # Event System
    'EventBus',
    'Event',
    'StateChangeEvent',
    'DecisionEvent',
    'RiskEvent',
    'DecisionExplanation',
    'EventType',
    'EventPriority',
    
    # Memory System
    'MemoryManager',
    'MemoryRecord',
    'RegimePattern',
    'StrategyHistory',
    'BeliefEvent',
    'BehaviorPattern',
    'MemoryType',
    
    # Orchestration
    'OrganOrchestrator',
    'NorthstarOrgan',
    'OrganStatus',
    'ExecutionPhase',
    'OrganMetrics',
    'ExecutionResult',
    
    # Heartbeat
    'NorthstarHeartbeat',
    'HeartbeatStatus',
    'HeartbeatMetrics',
    
    # Example Organs
    'ExampleOrgan',
    'HealthMonitorOrgan', 
    'DataPipelineOrganWrapper',
    'create_example_organs',
    
    # V3 Component Wrappers
    'DataPipelineOrgan',
    'MarketBrainOrgan',
    'IntelligenceStackOrgan',
    'CapitalAllocatorOrgan',
    'PortfolioGovernorOrgan',
    'RiskCoordinatorOrgan',
    'MemoryManagerOrgan',
    'create_v3_organ_wrappers',
    
    # Health Monitoring
    'HealthMonitor',
    'HealthLevel',
    'AlertSeverity',
    'HealthAlert',
    'OrganHealthReport',
    'SystemHealthReport',
    
    # Factory Function
    'create_living_system'
]