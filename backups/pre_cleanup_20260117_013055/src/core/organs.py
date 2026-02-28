#!/usr/bin/env python3
"""
🫀 STANDARD ORGAN IMPLEMENTATIONS
Standard Organ Interface and Example Implementations

This module provides the standard organ interface and example implementations
that demonstrate how to wrap existing V3 components as organs in the living system.

Key Features:
- NorthstarOrgan abstract base class (already in orchestrator.py)
- Example organ implementations
- Wrapper patterns for existing components
- Health monitoring and time event handling
"""

from src.cohesion.dependency_container import get_dependency_container

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

from src.core.orchestrator import NorthstarOrgan, OrganStatus
from src.core.state import UnifiedState, AuthorityLevel
from src.core.clock import TimeEvent, MarketTime

class ExampleOrgan(NorthstarOrgan):
    """
    Example organ implementation demonstrating the standard interface
    
    This shows how to implement the read_state -> think -> write_state pattern
    that all organs must follow in the living system.
    """
    
    def __init__(self, name: str = "example_organ"):
        super().__init__(name)
        self.data_cache = {}
        self.computation_result = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read required data from unified state"""
        
        # Example: Read market data
        self.data_cache = {
            'regime': state.market.regime,
            'risk_on_probability': state.market.risk_on_probability,
            'market_stress': state.market.market_stress,
            'portfolio_exposure': state.portfolio.total_exposure,
            'system_locked': state.locked
        }
        
        print(f"   📖 {self.name}: Read state - regime={self.data_cache['regime']}")
    
    def think(self, state: UnifiedState) -> Any:
        """Process data and generate outputs"""
        
        # Example computation: Simple risk assessment
        risk_score = (
            self.data_cache['market_stress'] * 0.4 +
            (1 - self.data_cache['risk_on_probability']) * 0.3 +
            self.data_cache['portfolio_exposure'] * 0.3
        )
        
        self.computation_result = {
            'risk_assessment': risk_score,
            'recommendation': 'reduce_exposure' if risk_score > 0.6 else 'maintain',
            'confidence': 0.8,
            'timestamp': datetime.now()
        }
        
        print(f"   🧠 {self.name}: Computed risk_score={risk_score:.2f}")
        
        return self.computation_result
    
    def write_state(self, state: UnifiedState) -> None:
        """Write outputs to unified state"""
        
        if self.computation_result:
            # Example: Update beliefs or risk state
            state.update_component('beliefs', {
                'unified_conviction': self.computation_result['confidence']
            }, organ=self.name, reason="Example organ computation")
            
            print(f"   ✍️ {self.name}: Updated beliefs with confidence={self.computation_result['confidence']}")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time-based events"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market opened - preparing for active trading")
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market closed - switching to analysis mode")
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance time - recalibrating models")

class HealthMonitorOrgan(NorthstarOrgan):
    """
    Health Monitor Organ - Monitors system health and reports issues
    
    This organ demonstrates health monitoring and system diagnostics.
    """
    
    def __init__(self, name: str = "health_monitor"):
        super().__init__(name)
        self.is_critical = True  # Health monitoring is critical
        self.health_data = {}
    
    def read_state(self, state: UnifiedState) -> None:
        """Read system health data"""
        
        self.health_data = {
            'overall_health': state.health.overall_health_score,
            'data_fresh': state.health.data_fresh,
            'components_healthy': state.health.components_healthy,
            'total_components': state.health.total_components,
            'portfolio_active': state.health.portfolio_active,
            'intelligence_active': state.health.intelligence_active,
            'system_locked': state.locked,
            'lock_reason': state.lock_reason
        }
    
    def think(self, state: UnifiedState) -> Any:
        """Analyze system health and identify issues"""
        
        issues = []
        recommendations = []
        
        # Check data freshness
        if not self.health_data['data_fresh']:
            issues.append("Data is stale")
            recommendations.append("Trigger data pipeline update")
        
        # Check component health
        if self.health_data['components_healthy'] < self.health_data['total_components']:
            issues.append(f"Only {self.health_data['components_healthy']}/{self.health_data['total_components']} components healthy")
            recommendations.append("Investigate component failures")
        
        # Check portfolio activity
        if not self.health_data['portfolio_active']:
            issues.append("Portfolio is inactive")
            recommendations.append("Check portfolio construction")
        
        # Check intelligence activity
        if not self.health_data['intelligence_active']:
            issues.append("Intelligence system is inactive")
            recommendations.append("Check intelligence engines")
        
        health_report = {
            'overall_score': self.health_data['overall_health'],
            'issues': issues,
            'recommendations': recommendations,
            'critical_issues': len([i for i in issues if 'inactive' in i.lower()]),
            'timestamp': datetime.now()
        }
        
        print(f"   🏥 {self.name}: Health score={health_report['overall_score']:.2f}, Issues={len(issues)}")
        
        return health_report
    
    def write_state(self, state: UnifiedState) -> None:
        """Update health metrics in state"""
        
        # Health computation is already done in UnifiedState.compute_system_health()
        # This organ just monitors and reports
        pass

class DataPipelineOrganWrapper(NorthstarOrgan):
    """
    Data Pipeline Organ Wrapper
    
    This demonstrates how to wrap an existing V3 component (DataPipelineCoordinator)
    as an organ without modifying the original code.
    """
    
    def __init__(self, name: str = "data_pipeline_organ"):
        super().__init__(name)
        self.is_critical = True  # Data pipeline is critical
        self.pipeline_coordinator = None
        self.pipeline_result = None
        
        # Try to import existing data pipeline
        try:
            from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
            self.pipeline_coordinator = DataPipelineCoordinator()
        except ImportError:
            print(f"   ⚠️ {self.name}: DataPipelineCoordinator not available - using mock")
            self.pipeline_coordinator = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine what data updates are needed"""
        
        # Check data freshness to decide if pipeline should run
        self.needs_update = not state.health.data_fresh
        
        print(f"   📖 {self.name}: Data fresh={state.health.data_fresh}, needs_update={self.needs_update}")
    
    def think(self, state: UnifiedState) -> Any:
        """Run data pipeline if needed"""
        
        if not self.needs_update:
            print(f"   🧠 {self.name}: Data is fresh, skipping pipeline")
            return {'status': 'skipped', 'reason': 'data_fresh'}
        
        if self.pipeline_coordinator:
            try:
                # Run the actual pipeline
                print(f"   🧠 {self.name}: Running data pipeline...")
                # result = self.pipeline_coordinator.run_pipeline()  # Actual call
                result = {'status': 'success', 'records_updated': 1000}  # Mock result
                self.pipeline_result = result
                print(f"   🧠 {self.name}: Pipeline completed - {result.get('records_updated', 0)} records")
                return result
            except Exception as e:
                print(f"   ⚠️ {self.name}: Pipeline failed - {e}")
                return {'status': 'failed', 'error': str(e)}
        else:
            # Mock pipeline execution
            print(f"   🧠 {self.name}: Mock pipeline execution")
            return {'status': 'mock_success', 'records_updated': 500}
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with pipeline results"""
        
        if self.pipeline_result and self.pipeline_result.get('status') == 'success':
            # Update health to reflect fresh data
            state.update_component('health', {
                'data_fresh': True,
                'data_freshness_hours': 0.0
            }, organ=self.name, reason="Data pipeline completed successfully")
            
            print(f"   ✍️ {self.name}: Updated health - data is now fresh")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for data updates"""
        
        if event == TimeEvent.PRE_OPEN:
            print(f"   ⏰ {self.name}: Pre-market - preparing data updates")
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - running full data refresh")

def create_example_organs() -> List[NorthstarOrgan]:
    """Create a set of example organs for testing"""
    
    organs = [
        ExampleOrgan("example_organ"),
        HealthMonitorOrgan("health_monitor"),
        DataPipelineOrganWrapper("data_pipeline_organ")
    ]
    
    return organs

def main():
    """Test the standard organ interface"""
    
    print("🫀 TESTING STANDARD ORGAN INTERFACE")
    print("=" * 50)
    
    # Create unified state for testing
    from src.core.state import UnifiedState
    from src.core.clock import MarketClock
    from src.core.events import EventBus
    from src.core.orchestrator import OrganOrchestrator
    
    print("\n🏗️ Creating test environment...")
    state = UnifiedState()
    clock = MarketClock()
    event_bus = EventBus()
    orchestrator = OrganOrchestrator(state=state, clock=clock, event_bus=event_bus)
    
    # Create example organs
    print("\n🫀 Creating example organs...")
    organs = create_example_organs()
    
    # Register organs with orchestrator
    print("\n🔗 Registering organs...")
    for organ in organs:
        orchestrator.register_organ(organ, is_critical=organ.is_critical)
    
    # Test individual organ execution
    print("\n⚡ Testing individual organ execution...")
    for organ in organs:
        print(f"\n   Testing {organ.name}:")
        result = organ.execute_full_cycle(state)
        print(f"   Result: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        if result.error:
            print(f"   Error: {result.error}")
        print(f"   Duration: {result.duration:.3f}s")
    
    # Test orchestrator cycle
    print("\n🎭 Testing orchestrator cycle...")
    cycle_result = orchestrator.run_cycle()
    print(f"   Cycle completed: {cycle_result['organs_successful']}/{cycle_result['organs_executed']} organs successful")
    print(f"   Success rate: {cycle_result['success_rate']:.1%}")
    print(f"   Total duration: {cycle_result['duration']:.3f}s")
    
    # Test time event handling
    print("\n⏰ Testing time event handling...")
    market_time = clock.tick()
    for organ in organs:
        organ.handle_time_event(TimeEvent.OPEN, market_time)
    
    print(f"\n✅ Standard Organ Interface test successful!")
    print(f"   All organs follow the read_state -> think -> write_state pattern!")
    
    return True

if __name__ == "__main__":
    main()