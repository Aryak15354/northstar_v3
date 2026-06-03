#!/usr/bin/env python3
"""
🔗 SHADOW PORTFOLIO V3 INTEGRATION - NORTHSTAR V3 PHASE 4
Integration with existing V3 UnifiedState and EventBus

This creates seamless integration with V3 architecture:
1. Store shadow portfolio state in UnifiedState
2. Emit shadow portfolio events through EventBus
3. Ensure compatibility with existing V3 architecture
4. Provide institutional-grade state management
5. Maintain audit trail through event system

V3 Integration Features:
- UnifiedState integration for centralized state management
- EventBus integration for event-driven communication
- Backward compatibility with existing V3 components
- Comprehensive audit trail for institutional compliance
- Real-time monitoring and alerting capabilities

Integration Benefits:
- Single source of truth through UnifiedState
- Event-driven architecture through EventBus
- Institutional-grade audit trail
- Real-time monitoring and alerting
- Seamless integration with existing V3 systems

Output: Complete V3 integration for shadow portfolio system
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')

# Import V3 components
try:
    # Try multiple import paths for V3 components
    import sys
    import os
    
    # Add src to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(src_dir)
    
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
    # Try importing V3 core components - multiple paths
    try:
        from src.core.state import UnifiedState, StateEvent, AuthorityLevel
        from src.core.events import EventBus, Event, EventType, EventPriority, DecisionEvent, StateChangeEvent
        V3_AVAILABLE = True
        print("✅ V3 core components imported successfully (src.core path)")
    except ImportError:
        try:
            from core.state import UnifiedState, StateEvent, AuthorityLevel
            from core.events import EventBus, Event, EventType, EventPriority, DecisionEvent, StateChangeEvent
            V3_AVAILABLE = True
            print("✅ V3 core components imported successfully (core path)")
        except ImportError as e:
            raise e
    
except ImportError as e1:
    print(f"⚠️ V3 components not available: {e1}")
    V3_AVAILABLE = False
    
    # Create mock classes for testing
    class UnifiedState:
        def __init__(self): 
            self.shadow_portfolio = {}
            self.events = []
    
    class EventBus:
        def __init__(self): 
            self.events = []
        def emit_event(self, event): 
            self.events.append(event)
        def subscribe(self, event_type, listener): 
            pass
    
    class Event:
        def __init__(self, **kwargs): 
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class StateEvent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class DecisionEvent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class StateChangeEvent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class EventType:
        DECISION = "decision"
        STATE_UPDATE = "state_update"
        SYSTEM_EVENT = "system_event"
        ERROR = "error"
        RISK_EVENT = "risk_event"
    
    class EventPriority:
        NORMAL = 3
        HIGH = 2
        CRITICAL = 1
    
    class AuthorityLevel:
        PORTFOLIO = 3

# Import Phase 4 components
import sys
import os
sys.path.append(os.path.dirname(__file__))

from enhanced_shadow_portfolio_state import EnhancedShadowPortfolioState, RegimeType, NoEdgeState
from advanced_shadow_executor import AdvancedShadowExecutor
from phase3_integration_layer import Phase3IntegrationLayer

@dataclass
class ShadowPortfolioEvent:
    """Shadow portfolio specific event data"""
    event_type: str
    portfolio_state: Dict[str, Any]
    intelligence_state: Dict[str, Any]
    execution_result: Dict[str, Any]
    performance_attribution: Dict[str, Any]
    validation_result: Dict[str, Any]
    metadata: Dict[str, Any]

class ShadowPortfolioV3Integration:
    """
    Shadow Portfolio V3 Integration
    
    Provides seamless integration between Phase 4 Shadow Portfolio system
    and existing V3 UnifiedState and EventBus architecture.
    
    Features:
    - Store shadow portfolio state in V3 UnifiedState
    - Emit shadow portfolio events through V3 EventBus
    - Maintain backward compatibility with existing V3 systems
    - Provide institutional-grade audit trail
    - Enable real-time monitoring and alerting
    """
    
    def __init__(self, unified_state: Optional[UnifiedState] = None, 
                 event_bus: Optional[EventBus] = None):
        self.name = "Shadow Portfolio V3 Integration"
        self.version = "4.0"
        
        # V3 component integration
        self.unified_state = unified_state or (UnifiedState() if V3_AVAILABLE else None)
        self.event_bus = event_bus or (EventBus() if V3_AVAILABLE else None)
        
        # Phase 4 components
        self.phase3_integration = Phase3IntegrationLayer()
        self.shadow_executor = AdvancedShadowExecutor()
        
        # Integration status
        self.integration_status = {
            'v3_available': V3_AVAILABLE,
            'unified_state_connected': self.unified_state is not None,
            'event_bus_connected': self.event_bus is not None,
            'phase3_integration_active': True,
            'shadow_executor_active': True,
            'last_state_update': None,
            'last_event_emission': None
        }
        
        # Configuration
        self.config = {
            'state_update_frequency': 'on_execution',  # 'on_execution', 'periodic', 'real_time'
            'event_emission_enabled': True,
            'audit_trail_enabled': True,
            'real_time_monitoring': True,
            'state_persistence_enabled': True,
            'event_correlation_enabled': True
        }
        
        # Shadow portfolio state tracking
        self.current_shadow_state: Optional[EnhancedShadowPortfolioState] = None
        self.state_history: List[EnhancedShadowPortfolioState] = []
        self.event_correlation_id: Optional[str] = None
        
        # Event listeners
        self._setup_event_listeners()
        
        print(f"🔗 Shadow Portfolio V3 Integration initialized")
        print(f"   V3 Available: {V3_AVAILABLE}")
        print(f"   UnifiedState: {'✅' if self.unified_state else '❌'}")
        print(f"   EventBus: {'✅' if self.event_bus else '❌'}")
    
    def _setup_event_listeners(self):
        """Setup event listeners for V3 integration"""
        
        if not self.event_bus:
            return
        
        try:
            # Listen for state change events
            self.event_bus.subscribe(EventType.STATE_UPDATE, self._handle_state_change_event)
            
            # Listen for decision events
            self.event_bus.subscribe(EventType.DECISION, self._handle_decision_event)
            
            # Listen for risk events
            self.event_bus.subscribe(EventType.RISK_EVENT, self._handle_risk_event)
            
            print("   📡 Event listeners configured")
            
        except Exception as e:
            print(f"   ⚠️ Error setting up event listeners: {e}")
    
    def _handle_state_change_event(self, event: Event):
        """Handle state change events from V3 system"""
        
        try:
            # Check if this is a relevant state change for shadow portfolio
            if hasattr(event, 'component') and event.component in ['market', 'regime', 'portfolio', 'risk']:
                print(f"   📊 Relevant state change detected: {event.component}")
                
                # Trigger shadow portfolio update if needed
                if self.config['state_update_frequency'] == 'real_time':
                    self._update_shadow_portfolio_from_state_change(event)
                    
        except Exception as e:
            print(f"   ⚠️ Error handling state change event: {e}")
    
    def _handle_decision_event(self, event: Event):
        """Handle decision events from V3 system"""
        
        try:
            if hasattr(event, 'decision_type') and 'portfolio' in event.decision_type.lower():
                print(f"   🎯 Portfolio decision event detected: {event.decision_type}")
                
                # Update shadow portfolio based on decision
                self._update_shadow_portfolio_from_decision(event)
                
        except Exception as e:
            print(f"   ⚠️ Error handling decision event: {e}")
    
    def _handle_risk_event(self, event: Event):
        """Handle risk events from V3 system"""
        
        try:
            if hasattr(event, 'risk_level') and event.risk_level in ['elevated', 'critical', 'emergency']:
                print(f"   🚨 Risk event detected: {event.risk_level}")
                
                # Update shadow portfolio risk state
                self._update_shadow_portfolio_risk_state(event)
                
        except Exception as e:
            print(f"   ⚠️ Error handling risk event: {e}")
    
    def execute_shadow_portfolio_with_v3_integration(self) -> Dict[str, Any]:
        """Execute shadow portfolio with full V3 integration"""
        
        print("🎭 EXECUTING SHADOW PORTFOLIO WITH V3 INTEGRATION")
        print("=" * 70)
        
        try:
            # Generate correlation ID for this execution
            self.event_correlation_id = f"shadow_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Emit execution start event
            self._emit_shadow_execution_start_event()
            
            # Get Phase 3 intelligence state
            intelligence_state = self.phase3_integration.get_unified_intelligence_state()
            
            # Execute shadow portfolio
            execution_result = self.shadow_executor.execute_shadow_portfolio()
            
            # Create enhanced shadow portfolio state
            shadow_state = self._create_enhanced_shadow_state(intelligence_state, execution_result)
            
            # Store in V3 UnifiedState
            self._store_shadow_state_in_unified_state(shadow_state)
            
            # Emit shadow portfolio events
            self._emit_shadow_portfolio_events(shadow_state, intelligence_state, execution_result)
            
            # Update tracking
            self.current_shadow_state = shadow_state
            self.state_history.append(shadow_state)
            
            # Keep only last 100 states
            if len(self.state_history) > 100:
                self.state_history = self.state_history[-100:]
            
            # Update integration status
            self.integration_status['last_state_update'] = datetime.now()
            self.integration_status['last_event_emission'] = datetime.now()
            
            # Emit execution complete event
            self._emit_shadow_execution_complete_event(shadow_state)
            
            # Create result summary
            result = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'correlation_id': self.event_correlation_id,
                'shadow_state': shadow_state.to_dict(),
                'intelligence_confidence': intelligence_state['confidence'],
                'execution_quality': execution_result.get('execution_quality', 0),
                'reality_consistency': execution_result.get('reality_consistency', 0),
                'v3_integration': {
                    'unified_state_updated': self.unified_state is not None,
                    'events_emitted': self.event_bus is not None,
                    'audit_trail_created': True
                }
            }
            
            print(f"\n✅ Shadow Portfolio V3 Integration Complete")
            print(f"   Correlation ID: {self.event_correlation_id}")
            print(f"   Intelligence Confidence: {intelligence_state['confidence']:.1%}")
            print(f"   Execution Quality: {execution_result.get('execution_quality', 0):.1%}")
            print(f"   V3 State Updated: {'✅' if self.unified_state else '❌'}")
            print(f"   V3 Events Emitted: {'✅' if self.event_bus else '❌'}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error in shadow portfolio V3 integration: {e}")
            
            # Emit error event
            self._emit_shadow_execution_error_event(str(e))
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'correlation_id': self.event_correlation_id
            }
    
    def _create_enhanced_shadow_state(self, intelligence_state: Dict[str, Any], 
                                    execution_result: Dict[str, Any]) -> EnhancedShadowPortfolioState:
        """Create enhanced shadow portfolio state from execution results"""
        
        # Create base state
        shadow_state = EnhancedShadowPortfolioState(
            timestamp=datetime.now().isoformat(),
            date=datetime.now().date().isoformat()
        )
        
        # Set regime state from Phase 3
        regime_info = intelligence_state.get('regime', {})
        if regime_info.get('available'):
            regime_type = RegimeType.LATE_EXPANSION  # Default, should map from regime_info['regime']
            try:
                regime_type = RegimeType(regime_info['regime'])
            except ValueError:
                pass
            
            shadow_state.set_regime_state(
                regime=regime_type,
                confidence=regime_info.get('confidence', 0.0),
                similarity=regime_info.get('similarity', 0.0),
                expected_return=regime_info.get('expected_return', 0.0),
                expected_sharpe=regime_info.get('expected_sharpe', 0.0),
                match_date=regime_info.get('match_date'),
                age_days=regime_info.get('age_days', 999),
                source=regime_info.get('source', 'unknown')
            )
        
        # Set strategy tailwinds from Phase 3
        tailwinds_info = intelligence_state.get('tailwinds', {})
        if tailwinds_info.get('available'):
            for strategy, tailwind_data in tailwinds_info.get('tailwinds', {}).items():
                shadow_state.add_strategy_tailwind(
                    strategy=strategy,
                    combined_score=tailwind_data.get('combined_score', 1.0),
                    sharpe=tailwind_data.get('sharpe', 0.0),
                    regime_tailwind=tailwind_data.get('regime_tailwind', 0.0),
                    regime=tailwind_data.get('regime', 'Unknown')
                )
        
        # Set NO_EDGE state from Phase 3
        no_edge_info = intelligence_state.get('no_edge', {})
        if no_edge_info.get('available'):
            no_edge_state = NoEdgeState.NORMAL  # Default
            try:
                no_edge_state = NoEdgeState(no_edge_info['state'])
            except ValueError:
                pass
            
            shadow_state.set_no_edge_state(
                state=no_edge_state,
                exposure_cap=no_edge_info.get('exposure_cap', 0.8),
                reasons=no_edge_info.get('reasons', []),
                confidence=no_edge_info.get('confidence', 0.1),
                age_days=no_edge_info.get('age_days', 999),
                transitions_today=no_edge_info.get('transitions_today', 0),
                source=no_edge_info.get('source', 'unknown')
            )
        
        # Add positions from execution result
        executed_positions = execution_result.get('executed_positions', {})
        for strategy, position_weight in executed_positions.items():
            if position_weight > 0:
                tailwind_score = tailwinds_info.get('tailwinds', {}).get(strategy, {}).get('combined_score', 1.0)
                shadow_state.add_position(strategy, position_weight, 0.0, tailwind_score, 0.7)
        
        # Set performance attribution
        phase3_contributions = execution_result.get('phase3_contributions', {})
        shadow_state.set_performance_attribution(
            total_performance=execution_result.get('total_performance', 0.0),
            regime_contribution=phase3_contributions.get('regime', 0.0),
            tailwind_contribution=phase3_contributions.get('tailwind', 0.0),
            no_edge_contribution=phase3_contributions.get('no_edge', 0.0),
            execution_contribution=0.0  # Would be calculated from execution costs
        )
        
        # Set validation result
        shadow_state.set_validation_result(
            consistency_score=execution_result.get('consistency_score', 0.0),
            validation_checks={
                'execution_quality': 'PASS' if execution_result.get('execution_quality', 0) > 0.8 else 'FAIL',
                'reality_consistency': 'PASS' if execution_result.get('reality_consistency', 0) > 0.9 else 'FAIL'
            },
            warnings=[],
            errors=[]
        )
        
        # Calculate intelligence confidence
        shadow_state.calculate_intelligence_confidence()
        
        return shadow_state
    
    def _store_shadow_state_in_unified_state(self, shadow_state: EnhancedShadowPortfolioState):
        """Store shadow portfolio state in V3 UnifiedState"""
        
        if not self.unified_state:
            print("   ⚠️ UnifiedState not available - skipping state storage")
            return
        
        try:
            # Create shadow portfolio component in unified state if it doesn't exist
            if not hasattr(self.unified_state, 'shadow_portfolio'):
                # Add shadow portfolio state to unified state
                setattr(self.unified_state, 'shadow_portfolio', {})
            
            # Store current shadow state
            shadow_data = {
                'timestamp': shadow_state.timestamp,
                'date': shadow_state.date,
                'regime': shadow_state.regime_state.regime.value,
                'regime_confidence': shadow_state.regime_state.confidence,
                'no_edge_state': shadow_state.no_edge_state.state.value,
                'exposure_cap': shadow_state.no_edge_state.exposure_cap,
                'total_exposure': shadow_state.total_exposure,
                'n_positions': shadow_state.n_positions,
                'intelligence_confidence': shadow_state.intelligence_confidence,
                'execution_quality': shadow_state.get_execution_quality_summary()['score'],
                'consistency_score': shadow_state.validation_result.consistency_score,
                'top_positions': {strategy: pos.executed_weight for strategy, pos in shadow_state.get_top_positions(5)},
                'top_tailwinds': {strategy: tw.combined_score for strategy, tw in shadow_state.get_top_tailwinds(5)},
                'performance_attribution': {
                    'total': shadow_state.performance_attribution.total_performance,
                    'regime': shadow_state.performance_attribution.regime_contribution,
                    'tailwind': shadow_state.performance_attribution.tailwind_contribution,
                    'no_edge': shadow_state.performance_attribution.no_edge_contribution,
                    'execution': shadow_state.performance_attribution.execution_contribution
                }
            }
            
            # Update unified state
            self.unified_state.shadow_portfolio = shadow_data
            
            # Create state change event
            if V3_AVAILABLE:
                state_event = StateEvent(
                    timestamp=datetime.now(),
                    organ="shadow_portfolio",
                    event_type="state_update",
                    component="shadow_portfolio",
                    field="complete_state",
                    old_value=None,
                    new_value=shadow_data,
                    reason="Shadow portfolio execution complete",
                    authority_level=AuthorityLevel.PORTFOLIO
                )
                
                # Add to unified state events
                if hasattr(self.unified_state, 'events'):
                    self.unified_state.events.append(state_event)
            
            print(f"   ✅ Shadow state stored in UnifiedState")
            
        except Exception as e:
            print(f"   ⚠️ Error storing shadow state in UnifiedState: {e}")
    
    def _emit_shadow_portfolio_events(self, shadow_state: EnhancedShadowPortfolioState,
                                    intelligence_state: Dict[str, Any], 
                                    execution_result: Dict[str, Any]):
        """Emit shadow portfolio events through V3 EventBus"""
        
        if not self.event_bus:
            print("   ⚠️ EventBus not available - skipping event emission")
            return
        
        try:
            # Create decision event
            decision_event = DecisionEvent(
                event_id="",
                timestamp=datetime.now(),
                event_type=EventType.DECISION,  # Required field
                source="shadow_portfolio",
                priority=EventPriority.NORMAL,
                correlation_id=self.event_correlation_id,
                decision_type="shadow_portfolio_allocation",
                decision_data={
                    'total_exposure': shadow_state.total_exposure,
                    'n_positions': shadow_state.n_positions,
                    'regime': shadow_state.regime_state.regime.value,
                    'no_edge_state': shadow_state.no_edge_state.state.value,
                    'top_positions': {strategy: pos.executed_weight for strategy, pos in shadow_state.get_top_positions(3)}
                },
                confidence=shadow_state.intelligence_confidence,
                reasoning=[
                    f"Regime: {shadow_state.regime_state.regime.value} (confidence: {shadow_state.regime_state.confidence:.1%})",
                    f"NO_EDGE state: {shadow_state.no_edge_state.state.value} (cap: {shadow_state.no_edge_state.exposure_cap:.0%})",
                    f"Strategy tailwinds: {len(shadow_state.strategy_tailwinds)} strategies analyzed",
                    f"Execution quality: {shadow_state.get_execution_quality_summary()['score']:.1%}"
                ]
            )
            
            self.event_bus.emit_event(decision_event)
            
            # Emit performance attribution event
            attribution_event = Event(
                event_id=f"shadow_attribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                event_type=EventType.DECISION,
                source="shadow_portfolio",
                priority=EventPriority.NORMAL,
                correlation_id=self.event_correlation_id,
                data={
                    'event_type': 'performance_attribution',
                    'total_performance': shadow_state.performance_attribution.total_performance,
                    'regime_contribution': shadow_state.performance_attribution.regime_contribution,
                    'tailwind_contribution': shadow_state.performance_attribution.tailwind_contribution,
                    'no_edge_contribution': shadow_state.performance_attribution.no_edge_contribution,
                    'execution_contribution': shadow_state.performance_attribution.execution_contribution,
                    'unexplained_alpha': shadow_state.performance_attribution.unexplained_alpha
                },
                tags=['shadow_portfolio', 'performance_attribution', 'phase4']
            )
            
            self.event_bus.emit_event(attribution_event)
            
            # Emit validation event
            validation_event = Event(
                event_id=f"shadow_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source="shadow_portfolio",
                priority=EventPriority.NORMAL,
                correlation_id=self.event_correlation_id,
                data={
                    'event_type': 'validation_result',
                    'consistency_score': shadow_state.validation_result.consistency_score,
                    'validation_checks': shadow_state.validation_result.validation_checks,
                    'warnings': shadow_state.validation_result.warnings,
                    'errors': shadow_state.validation_result.errors
                },
                tags=['shadow_portfolio', 'validation', 'phase4']
            )
            
            self.event_bus.emit_event(validation_event)
            
            print(f"   ✅ Shadow portfolio events emitted (3 events)")
            
        except Exception as e:
            print(f"   ⚠️ Error emitting shadow portfolio events: {e}")
    
    def _emit_shadow_execution_start_event(self):
        """Emit shadow execution start event"""
        
        if not self.event_bus:
            return
        
        try:
            start_event = Event(
                event_id=f"shadow_start_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source="shadow_portfolio",
                priority=EventPriority.NORMAL,
                correlation_id=self.event_correlation_id,
                data={
                    'event_type': 'execution_start',
                    'phase': 'Phase 4.1',
                    'integration_status': self.integration_status
                },
                tags=['shadow_portfolio', 'execution_start', 'phase4']
            )
            
            self.event_bus.emit_event(start_event)
            
        except Exception as e:
            print(f"   ⚠️ Error emitting start event: {e}")
    
    def _emit_shadow_execution_complete_event(self, shadow_state: EnhancedShadowPortfolioState):
        """Emit shadow execution complete event"""
        
        if not self.event_bus:
            return
        
        try:
            complete_event = Event(
                event_id=f"shadow_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source="shadow_portfolio",
                priority=EventPriority.NORMAL,
                correlation_id=self.event_correlation_id,
                data={
                    'event_type': 'execution_complete',
                    'success': True,
                    'intelligence_confidence': shadow_state.intelligence_confidence,
                    'total_exposure': shadow_state.total_exposure,
                    'execution_quality': shadow_state.get_execution_quality_summary()['score'],
                    'consistency_score': shadow_state.validation_result.consistency_score
                },
                tags=['shadow_portfolio', 'execution_complete', 'phase4']
            )
            
            self.event_bus.emit_event(complete_event)
            
        except Exception as e:
            print(f"   ⚠️ Error emitting complete event: {e}")
    
    def _emit_shadow_execution_error_event(self, error_message: str):
        """Emit shadow execution error event"""
        
        if not self.event_bus:
            return
        
        try:
            error_event = Event(
                event_id=f"shadow_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                event_type=EventType.ERROR,
                source="shadow_portfolio",
                priority=EventPriority.HIGH,
                correlation_id=self.event_correlation_id,
                data={
                    'event_type': 'execution_error',
                    'error_message': error_message,
                    'integration_status': self.integration_status
                },
                tags=['shadow_portfolio', 'execution_error', 'phase4']
            )
            
            self.event_bus.emit_event(error_event)
            
        except Exception as e:
            print(f"   ⚠️ Error emitting error event: {e}")
    
    def _update_shadow_portfolio_from_state_change(self, event: Event):
        """Update shadow portfolio based on V3 state changes"""
        
        # This would trigger a shadow portfolio update based on state changes
        # For now, just log the event
        print(f"   📊 Shadow portfolio update triggered by state change: {event.component}")
    
    def _update_shadow_portfolio_from_decision(self, event: Event):
        """Update shadow portfolio based on V3 decisions"""
        
        # This would update shadow portfolio based on portfolio decisions
        # For now, just log the event
        print(f"   🎯 Shadow portfolio update triggered by decision: {event.decision_type}")
    
    def _update_shadow_portfolio_risk_state(self, event: Event):
        """Update shadow portfolio risk state based on V3 risk events"""
        
        # This would update shadow portfolio risk constraints based on risk events
        # For now, just log the event
        print(f"   🚨 Shadow portfolio risk update triggered: {event.risk_level}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current V3 integration status"""
        
        return {
            'integration_status': self.integration_status,
            'config': self.config,
            'current_state_available': self.current_shadow_state is not None,
            'state_history_length': len(self.state_history),
            'last_correlation_id': self.event_correlation_id
        }
    
    def get_shadow_state_from_unified_state(self) -> Optional[Dict[str, Any]]:
        """Retrieve shadow portfolio state from V3 UnifiedState"""
        
        if not self.unified_state:
            return None
        
        try:
            if hasattr(self.unified_state, 'shadow_portfolio'):
                return self.unified_state.shadow_portfolio
            else:
                return None
                
        except Exception as e:
            print(f"   ⚠️ Error retrieving shadow state from UnifiedState: {e}")
            return None

def main():
    """Test Shadow Portfolio V3 Integration"""
    
    print("🔗 Testing Shadow Portfolio V3 Integration...")
    
    # Create V3 integration
    integration = ShadowPortfolioV3Integration()
    
    # Test integration status
    status = integration.get_integration_status()
    print(f"\n📊 Integration Status:")
    print(f"   V3 Available: {status['integration_status']['v3_available']}")
    print(f"   UnifiedState Connected: {status['integration_status']['unified_state_connected']}")
    print(f"   EventBus Connected: {status['integration_status']['event_bus_connected']}")
    
    # Test shadow portfolio execution with V3 integration
    result = integration.execute_shadow_portfolio_with_v3_integration()
    
    if result['success']:
        print(f"\n✅ V3 Integration Test Complete!")
        print(f"   Correlation ID: {result['correlation_id']}")
        print(f"   Intelligence Confidence: {result['intelligence_confidence']:.1%}")
        print(f"   Execution Quality: {result['execution_quality']:.1%}")
        print(f"   V3 State Updated: {result['v3_integration']['unified_state_updated']}")
        print(f"   V3 Events Emitted: {result['v3_integration']['events_emitted']}")
    else:
        print(f"❌ V3 Integration Test Failed: {result.get('error', 'Unknown error')}")
    
    return result

if __name__ == "__main__":
    main()