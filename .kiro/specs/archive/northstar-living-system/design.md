# Design Document

## Overview

This design transforms Northstar V3 from a distributed collection of intelligent scripts into a single living investment organism with a unified nervous system. The transformation follows a zero-rewrite migration approach that wraps existing components as organs while introducing a central nervous system that coordinates all operations through a single source of truth.

The living system architecture is inspired by how institutional hedge funds like Bridgewater, Two Sigma, and Renaissance operate their investment operating systems - with a central state manager serving as the brainstem that coordinates all subsystems.

## Architecture

### Current State Analysis

Northstar V3 currently operates as a sophisticated distributed system with:
- **7 Coordinators**: Master Orchestrator, Data Pipeline, System, Market Brain, Intelligence, Portfolio, Risk
- **100+ Components**: Individual scripts and modules across 5 phases
- **Multiple State Sources**: Each subsystem maintains its own state and data files
- **Direct Communication**: Components communicate directly with each other
- **Batch Processing**: System runs in discrete update cycles

### Target Living System Architecture

The living system transforms this into:

```
┌─────────────────────────────────────────────────────────────┐
│                    LIVING ORGANISM                          │
├─────────────────────────────────────────────────────────────┤
│                  NERVOUS SYSTEM (Core)                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Unified     │ │ Market      │ │ Event       │          │
│  │ State       │ │ Clock       │ │ Bus         │          │
│  │ (Brainstem) │ │ (Time)      │ │ (Audit)     │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│  ┌─────────────┐ ┌─────────────┐                          │
│  │ Memory      │ │ Orchestrator│                          │
│  │ (History)   │ │ (Scheduler) │                          │
│  └─────────────┘ └─────────────┘                          │
├─────────────────────────────────────────────────────────────┤
│                     ORGANS (Wrapped Components)            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Data        │ │ Market      │ │ Intelligence│          │
│  │ Pipeline    │ │ Brain       │ │ Stack       │          │
│  │ Organ       │ │ Organ       │ │ Organ       │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Capital     │ │ Portfolio   │ │ Risk        │          │
│  │ Allocator   │ │ Governor    │ │ Coordinator │          │
│  │ Organ       │ │ Organ       │ │ (Spinal Cord)│         │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                    BRAIN WINDOW (Dashboard)                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Read-Only Display of Unified State                      ││
│  │ Intent Sending (Rebalance, Override, Pause)            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Core Principles

1. **Single Source of Truth**: All data flows through Unified State
2. **Organ Isolation**: No direct communication between organs
3. **Time-Driven**: Market Clock drives all system behavior
4. **Risk Authority**: Risk has absolute authority over all decisions
5. **Event-Driven**: All changes are tracked through event bus
6. **Zero-Rewrite**: Existing code is wrapped, not modified

## Components and Interfaces

### Core Nervous System

#### Unified State Manager (Brainstem)

The enhanced Unified State Manager becomes the central nervous system:

```python
class UnifiedState:
    """Single source of truth for all system data"""
    
    # Core state components
    market: MarketState
    macro: MacroState
    regime: RegimeState
    pulse: PulseState
    beliefs: BeliefState
    confidence: ConfidenceState
    strategies: StrategyState
    capital: CapitalState
    portfolio: PortfolioState
    risk: RiskState
    health: HealthState
    memory: MemoryState
    
    # System control
    locked: bool = False
    time: MarketTime
    
    # Event tracking
    events: List[StateEvent]
    history: StateHistory
```

#### Market Clock

Time becomes a first-class citizen:

```python
class MarketClock:
    """Market time management and event emission"""
    
    def tick(self) -> MarketTime:
        """Advance market time and emit events"""
        
    def emit_time_event(self, event_type: TimeEvent):
        """Emit time-based events to all organs"""
        
    def is_market_alive(self) -> bool:
        """Check if markets are active"""

class TimeEvent(Enum):
    PRE_OPEN = "pre_open"
    OPEN = "open"
    INTRADAY = "intraday"
    CLOSE = "close"
    OVERNIGHT = "overnight"
    WEEKLY_REBALANCE = "weekly_rebalance"
```

#### Event Bus

All state changes are tracked:

```python
class EventBus:
    """Event tracking and audit trail"""
    
    def emit_event(self, event: StateEvent):
        """Emit state change event"""
        
    def get_audit_trail(self, filters: Dict) -> List[StateEvent]:
        """Get filtered audit trail"""
        
    def explain_decision(self, decision_id: str) -> DecisionExplanation:
        """Explain investment decision through event history"""
```

#### Memory Manager

Unified access to all historical patterns:

```python
class MemoryManager:
    """Unified memory access across all dimensions"""
    
    def query_regime_patterns(self, regime: str) -> List[RegimePattern]:
        """Query historical regime patterns"""
        
    def query_strategy_performance(self, strategy: str) -> StrategyHistory:
        """Query strategy historical performance"""
        
    def when_did_we_believe(self, belief: str) -> List[BeliefEvent]:
        """Temporal belief queries"""
        
    def how_did_we_behave(self, condition: str) -> List[BehaviorPattern]:
        """Behavioral pattern queries"""
```

### Organ Interface

All existing components are wrapped with a standard interface:

```python
class NorthstarOrgan(ABC):
    """Standard interface for all system organs"""
    
    @abstractmethod
    def read_state(self, state: UnifiedState) -> None:
        """Read required data from unified state"""
        
    @abstractmethod
    def think(self, state: UnifiedState) -> Any:
        """Process data and generate outputs"""
        
    @abstractmethod
    def write_state(self, state: UnifiedState) -> None:
        """Write outputs to unified state"""
        
    def get_health_metrics(self) -> HealthMetrics:
        """Return organ health metrics"""
        
    def handle_time_event(self, event: TimeEvent) -> None:
        """React to time-based events"""
```

### Organ Implementations

#### Data Pipeline Organ

Wraps existing data collection systems:

```python
class DataPipelineOrgan(NorthstarOrgan):
    """Wraps existing data pipeline coordinator"""
    
    def __init__(self):
        # Import existing coordinator without modification
        from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
        self.coordinator = DataPipelineCoordinator()
    
    def read_state(self, state: UnifiedState):
        # Read data collection requirements from state
        self.data_requirements = state.get_data_requirements()
    
    def think(self, state: UnifiedState):
        # Use existing coordinator logic unchanged
        return self.coordinator.collect_all_data()
    
    def write_state(self, state: UnifiedState):
        # Write collected data to unified state
        state.market.update(self.collected_data)
        state.macro.update(self.macro_data)
```

#### Market Brain Organ

Wraps existing market brain orchestrator:

```python
class MarketBrainOrgan(NorthstarOrgan):
    """Wraps existing market brain orchestrator"""
    
    def __init__(self):
        from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
        self.brain = MarketBrainOrchestrator()
    
    def read_state(self, state: UnifiedState):
        self.market_data = state.market
        self.macro_data = state.macro
    
    def think(self, state: UnifiedState):
        # Use existing brain logic unchanged
        return self.brain.run_complete_market_brain()
    
    def write_state(self, state: UnifiedState):
        state.regime.update(self.brain_output["regime"])
        state.pulse.update(self.brain_output["pulse"])
```

#### Risk Coordinator Organ (Spinal Cord)

Risk becomes the spinal cord with absolute authority:

```python
class RiskCoordinatorOrgan(NorthstarOrgan):
    """Risk organ with absolute authority (spinal cord)"""
    
    AUTHORITY_LEVELS = {
        'EMERGENCY': 1,    # Absolute authority
        'SYSTEM': 2,       # System-level authority
        'PORTFOLIO': 3,    # Portfolio-level authority
        'POSITION': 4      # Position-level authority
    }
    
    def write_state(self, state: UnifiedState):
        # Risk has special authority to lock the system
        if self.emergency_detected:
            state.locked = True
            state.risk.emergency_active = True
            
        # Write risk metrics
        state.risk.update(self.risk_metrics)
```

### Orchestrator (Organ Scheduler)

The orchestrator becomes a simple organ scheduler:

```python
class OrganOrchestrator:
    """Schedules and coordinates organ execution"""
    
    def __init__(self):
        self.organs = [
            DataPipelineOrgan(),
            MarketBrainOrgan(),
            IntelligenceStackOrgan(),
            CapitalAllocatorOrgan(),
            PortfolioGovernorOrgan(),
            RiskCoordinatorOrgan()
        ]
    
    def run_cycle(self, state: UnifiedState):
        """Run one complete organ cycle"""
        
        for organ in self.organs:
            # Skip if system is locked and organ is not risk
            if state.locked and not isinstance(organ, RiskCoordinatorOrgan):
                continue
                
            try:
                organ.read_state(state)
                organ.think(state)
                organ.write_state(state)
            except Exception as e:
                self.handle_organ_failure(organ, e)
```

### Heartbeat (Continuous Organism)

The main execution loop becomes a heartbeat:

```python
class NorthstarHeartbeat:
    """Continuous execution heartbeat"""
    
    def __init__(self):
        self.clock = MarketClock()
        self.orchestrator = OrganOrchestrator()
        self.state = UnifiedState()
        self.event_bus = EventBus()
    
    def run(self):
        """Main heartbeat loop"""
        
        while self.clock.is_market_alive():
            try:
                # Tick the clock
                current_time = self.clock.tick()
                
                # Run all organs
                self.orchestrator.run_cycle(self.state)
                
                # Save state
                self.state.save()
                
                # Refresh dashboard
                self.refresh_dashboard()
                
                # Sleep until next cycle
                self.sleep_until_next_cycle()
                
            except Exception as e:
                self.handle_system_error(e)
```

## Data Models

### State Models

```python
@dataclass
class MarketState:
    regime: str
    risk_on_probability: float
    allowed_exposure: float
    volatility_regime: str
    market_stress: float
    last_updated: datetime

@dataclass
class IntelligenceState:
    beliefs: Dict[str, float]
    confidence: Dict[str, float]
    conviction: float
    narratives: List[str]
    last_updated: datetime

@dataclass
class PortfolioState:
    weights: Dict[str, float]
    exposure: float
    positions: int
    performance: Dict[str, float]
    last_updated: datetime

@dataclass
class RiskState:
    status: str  # normal, elevated, critical
    emergency_active: bool
    stress_level: float
    kill_switches: Dict[str, bool]
    last_updated: datetime
```

### Event Models

```python
@dataclass
class StateEvent:
    timestamp: datetime
    organ: str
    event_type: str
    old_value: Any
    new_value: Any
    reason: str
    authority_level: int

@dataclass
class DecisionExplanation:
    decision_id: str
    timestamp: datetime
    contributing_events: List[StateEvent]
    reasoning_chain: List[str]
    confidence: float
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, here are the key correctness properties for the living system:

### Property 1: Unified State Access Control
*For any* component data access operation, the component should read exclusively from Unified_State and never access other components directly
**Validates: Requirements 1.2, 1.4**

### Property 2: Unified State Write Control  
*For any* component output operation, the component should write exclusively to Unified_State and never write to other components directly
**Validates: Requirements 1.3, 1.5**

### Property 3: Organ Execution Pattern
*For any* organ execution cycle, the organ should follow the read-think-write pattern in that exact order
**Validates: Requirements 2.3**

### Property 4: Backward Compatibility Preservation
*For any* existing component interface or output, wrapping the component should preserve the interface and produce equivalent outputs
**Validates: Requirements 2.1, 2.5, 8.1, 8.2**

### Property 5: Time Event Response
*For any* market time change event, all organs should react appropriately to the time-based event according to their time-sensitive behaviors
**Validates: Requirements 3.2**

### Property 6: State History Indexing
*For any* state component change, the change should be recorded with proper time indexing in the unified state history
**Validates: Requirements 3.4**

### Property 7: Emergency Lock Authority
*For any* emergency condition detected by risk systems, the Unified_State should be set to LOCKED status and prevent non-risk organs from operating
**Validates: Requirements 4.1, 4.2**

### Property 8: Risk Authority Enforcement
*For any* emergency risk signal, no organ should be able to override the signal regardless of the organ's other priorities
**Validates: Requirements 4.4**

### Property 9: Risk Reflex Response
*For any* risk event, the Spinal_Cord should respond with reflex-like speed (sub-second response time) rather than batch processing delays
**Validates: Requirements 4.5**

### Property 10: Memory Query Unification
*For any* historical pattern query, the Living_System should provide unified access to all memory types (regime, strategy, narrative, portfolio) through a single interface
**Validates: Requirements 5.2**

### Property 11: Anticipatory Behavior
*For any* historical state pattern that has occurred before, the Living_System should make anticipatory decisions based on the pattern rather than purely reactive decisions
**Validates: Requirements 5.3**

### Property 12: Pattern Matching Capability
*For any* temporal pattern matching query across different state dimensions, the system should return consistent and accurate pattern matches
**Validates: Requirements 5.5**

### Property 13: Dashboard State-Only Access
*For any* dashboard data display operation, the Brain_Window should read exclusively from Unified_State and never compute truth independently
**Validates: Requirements 6.1, 6.2, 6.5**

### Property 14: Heartbeat Execution Completeness
*For any* heartbeat execution cycle, the system should tick the clock, run all organs, save state, and refresh dashboard in that order
**Validates: Requirements 7.2**

### Property 15: Autonomous Operation
*For any* market hours period, the Living_System should operate autonomously without requiring manual intervention
**Validates: Requirements 7.3**

### Property 16: Graceful Failure Handling
*For any* organ failure during heartbeat execution, the heartbeat should continue operating and handle the failure gracefully without stopping the organism
**Validates: Requirements 7.4**

### Property 17: Continuous Recovery
*For any* system failure or disruption, the Living_System should automatically recover and maintain continuous operation
**Validates: Requirements 7.5**

### Property 18: Migration Compatibility
*For any* existing script or workflow, the Living_System should maintain compatibility and allow the script/workflow to function unchanged
**Validates: Requirements 8.3**

### Property 19: Feature Addition Without Removal
*For any* existing system capability, the migration should preserve the capability while adding new functionality
**Validates: Requirements 8.4**

### Property 20: State Change Event Emission
*For any* organ state modification, the system should emit events describing the changes with proper attribution and timing
**Validates: Requirements 9.2**

### Property 21: Audit Trail Completeness
*For any* system decision or state modification, the change should be recorded in the audit trail with sufficient detail for explainability
**Validates: Requirements 9.3**

### Property 22: Decision Explainability
*For any* investment decision made by the system, the decision should be explainable through the event history and reasoning chain
**Validates: Requirements 9.5**

### Property 23: Organ Failure Detection
*For any* organ failure or poor performance, the system should detect and report the issue with appropriate diagnostic information
**Validates: Requirements 10.2**

### Property 24: Organ Isolation
*For any* organ isolation or recovery operation, other organs should continue to function normally without being affected
**Validates: Requirements 10.4**

### Property 25: Health Metric Calculation
*For any* change in organ performance, the system-wide health metrics should be updated to reflect the change based on organ performance data
**Validates: Requirements 10.5**

## Error Handling

### Organ Failure Recovery

The living system implements graceful degradation:

1. **Organ Isolation**: Failed organs are isolated without affecting others
2. **Fallback Mechanisms**: Critical organs have fallback implementations
3. **Health Monitoring**: Continuous monitoring detects issues early
4. **Automatic Recovery**: System attempts automatic recovery before alerting

### Risk Authority Override

Risk management has absolute authority:

1. **Emergency Lock**: Risk can lock the entire system instantly
2. **Authority Levels**: Clear hierarchy prevents override conflicts
3. **Reflex Response**: Sub-second response to critical conditions
4. **Fail-Safe Defaults**: System defaults to safe state on failures

### State Consistency

Unified state maintains consistency:

1. **Atomic Updates**: State changes are atomic and consistent
2. **Event Ordering**: Events are properly ordered and timestamped
3. **Rollback Capability**: System can rollback to previous consistent state
4. **Validation**: All state changes are validated before persistence

## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing:

**Unit Tests**:
- Test specific organ wrapper implementations
- Test core nervous system components
- Test error conditions and edge cases
- Test integration points between organs and state

**Property-Based Tests**:
- Test universal properties across all organs and state changes
- Test system behavior under random conditions
- Test temporal properties and time-based behaviors
- Test emergency conditions and recovery scenarios

### Property-Based Testing Configuration

- **Testing Framework**: Use Hypothesis for Python property-based testing
- **Test Iterations**: Minimum 100 iterations per property test
- **Test Tagging**: Each property test references its design document property
- **Tag Format**: **Feature: northstar-living-system, Property {number}: {property_text}**

### Testing Categories

1. **Organ Interface Tests**: Verify all organs implement the standard interface
2. **State Access Tests**: Verify unified state access patterns
3. **Time Behavior Tests**: Verify time-driven behaviors
4. **Risk Authority Tests**: Verify risk override capabilities
5. **Memory Integration Tests**: Verify historical pattern access
6. **Dashboard Integration Tests**: Verify read-only dashboard behavior
7. **Heartbeat Tests**: Verify continuous operation
8. **Migration Tests**: Verify backward compatibility
9. **Event System Tests**: Verify event emission and audit trails
10. **Health Monitoring Tests**: Verify organ health tracking

Each category includes both unit tests for specific examples and property tests for universal behaviors.