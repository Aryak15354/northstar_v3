# Requirements Document

## Introduction

Transform Northstar V3 from a distributed collection of intelligent scripts into a single living investment organism with a unified nervous system. The system will maintain all existing functionality while introducing a central state manager that serves as the brainstem, coordinating all organs through a single source of truth.

## Glossary

- **Living_System**: The transformed Northstar V3 that operates as a single autonomous organism
- **Nervous_System**: The core infrastructure (state, orchestrator, clock, memory, events) that coordinates all organs
- **Unified_State**: The single source of truth that all organs read from and write to
- **Organ**: A wrapped existing component that follows the read-think-write contract
- **Market_Clock**: Time management system that makes time a first-class citizen
- **Spinal_Cord**: Risk management system with absolute authority over all other organs
- **Brain_Window**: Dashboard system that only displays state without computing truth
- **Heartbeat**: The continuous execution loop that keeps the organism alive

## Requirements

### Requirement 1: Unified Nervous System

**User Story:** As a system architect, I want a unified nervous system that coordinates all components, so that the system operates as a single coherent organism rather than disconnected scripts.

#### Acceptance Criteria

1. THE Living_System SHALL implement a core nervous system with state, orchestrator, clock, memory, and events components
2. WHEN any component needs data, THE component SHALL read exclusively from Unified_State
3. WHEN any component produces output, THE component SHALL write exclusively to Unified_State
4. THE Nervous_System SHALL prevent direct communication between organs
5. THE Unified_State SHALL serve as the single source of truth for all system data

### Requirement 2: Organ Transformation

**User Story:** As a system maintainer, I want existing components wrapped as organs with standardized contracts, so that all functionality is preserved while enabling unified coordination.

#### Acceptance Criteria

1. WHEN wrapping existing components, THE Living_System SHALL preserve all existing functionality
2. THE Living_System SHALL implement a standard organ interface with read_state, think, and write_state methods
3. WHEN an organ executes, THE organ SHALL follow the read-think-write pattern
4. THE Living_System SHALL wrap all major V3 components as organs without modifying their internal code
5. THE Living_System SHALL maintain backward compatibility with existing component interfaces

### Requirement 3: Time as First-Class Citizen

**User Story:** As a trading system, I want time to be a first-class citizen that drives all system behavior, so that the system can age, adapt, and respond to market cycles naturally.

#### Acceptance Criteria

1. THE Market_Clock SHALL emit market time events including pre-open, open, intraday, close, overnight, and weekly rebalance
2. WHEN market time changes, THE organs SHALL react appropriately to time-based events
3. THE Living_System SHALL track pulse changes, regime drift, conviction decay, position aging, and risk fatigue over time
4. THE Unified_State SHALL maintain time-indexed history for all state components
5. THE Living_System SHALL enable temporal queries like "when did we last believe this" and "how did we behave in this regime"

### Requirement 4: Absolute Risk Authority

**User Story:** As a risk manager, I want risk management to have absolute authority over all system decisions, so that the system can survive extreme market conditions and protect capital.

#### Acceptance Criteria

1. WHEN risk systems detect emergency conditions, THE Spinal_Cord SHALL set Unified_State to LOCKED status
2. WHEN Unified_State is LOCKED, THE Living_System SHALL prevent capital allocator, portfolio governor, and execution organs from operating
3. THE Spinal_Cord SHALL have authority levels: EMERGENCY (absolute), SYSTEM, PORTFOLIO, and POSITION
4. THE Living_System SHALL enforce that no organ can override emergency risk signals
5. THE Spinal_Cord SHALL operate as a reflex system, not just a module

### Requirement 5: State Memory Integration

**User Story:** As an intelligent system, I want unified access to historical state memory, so that the system can be anticipatory rather than reactive.

#### Acceptance Criteria

1. THE Unified_State SHALL integrate regime memory, strategy regret, narrative memory, and portfolio history
2. WHEN querying historical patterns, THE Living_System SHALL provide unified access to all memory types
3. THE Living_System SHALL enable anticipatory behavior based on historical state patterns
4. THE Unified_State SHALL maintain searchable history for regime patterns, strategy performance, and market behavior
5. THE Living_System SHALL support temporal pattern matching across all state dimensions

### Requirement 6: Brain Window Dashboard

**User Story:** As a user, I want the dashboard to be a window into the system's brain, so that I can observe the system's thinking without the dashboard computing its own version of truth.

#### Acceptance Criteria

1. THE Brain_Window SHALL read exclusively from Unified_State for all data display
2. WHEN displaying information, THE Brain_Window SHALL never compute truth independently
3. THE Brain_Window SHALL provide visualization of Unified_State components
4. THE Brain_Window SHALL support sending intents (rebalance, override, pause) to the system
5. THE Brain_Window SHALL operate like Bloomberg terminals that display but don't compute

### Requirement 7: Continuous Organism Heartbeat

**User Story:** As a living system, I want a continuous heartbeat that keeps the organism alive and responsive, so that the system operates autonomously without manual intervention.

#### Acceptance Criteria

1. THE Heartbeat SHALL implement a continuous execution loop while markets are alive
2. WHEN the Heartbeat executes, THE system SHALL tick the clock, run all organs, save state, and refresh dashboard
3. THE Living_System SHALL operate autonomously during market hours
4. THE Heartbeat SHALL handle organ failures gracefully without stopping the organism
5. THE Living_System SHALL maintain continuous operation with automatic recovery capabilities

### Requirement 8: Zero-Rewrite Migration

**User Story:** As a system maintainer, I want to transform the system without rewriting existing code, so that the migration preserves all functionality while minimizing risk.

#### Acceptance Criteria

1. THE Living_System SHALL wrap existing components without modifying their internal implementation
2. WHEN migrating components, THE system SHALL preserve all existing interfaces and outputs
3. THE Living_System SHALL maintain compatibility with existing scripts and workflows
4. THE migration SHALL add new functionality without removing existing capabilities
5. THE Living_System SHALL enable gradual migration with rollback capabilities

### Requirement 9: Event-Driven Architecture

**User Story:** As a system observer, I want to track what changes when and why, so that the system provides full auditability and explainability.

#### Acceptance Criteria

1. THE Living_System SHALL implement an event bus that tracks all state changes
2. WHEN any organ modifies state, THE system SHALL emit events describing the changes
3. THE Living_System SHALL maintain an audit trail of all decisions and state modifications
4. THE event system SHALL enable real-time monitoring of organ behavior
5. THE Living_System SHALL provide explainability for all investment decisions through event history

### Requirement 10: Organ Health Monitoring

**User Story:** As a system administrator, I want to monitor the health of all organs, so that I can detect and resolve issues before they affect system performance.

#### Acceptance Criteria

1. THE Living_System SHALL monitor the health and performance of all organs
2. WHEN an organ fails or performs poorly, THE system SHALL detect and report the issue
3. THE Living_System SHALL provide organ-level diagnostics and performance metrics
4. THE system SHALL support organ isolation and recovery without affecting other organs
5. THE Living_System SHALL maintain system-wide health metrics based on organ performance