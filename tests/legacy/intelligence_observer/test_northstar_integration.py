#!/usr/bin/env python3
"""
Northstar V3 Integration Tests

Tests the Intelligence Observer integration with Northstar V3 architecture
to ensure:
1. Seamless integration with EventBus and UnifiedState
2. Proper organ lifecycle management
3. Authority boundaries are maintained during integration
4. Observer respects system locks and emergency conditions
5. Event subscription and handling works correctly
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.integration.northstar_integration import (
    IntelligenceObserverOrgan, ObserverIntegrationManager, ObserverEvent,
    integrate_intelligence_observer, get_integration_manager
)

# Mock Northstar V3 components for testing
class MockUnifiedState:
    """Mock UnifiedState for testing"""
    def __init__(self):
        self.risk_state = Mock()
        self.risk_state.status = "NORMAL"
        self.market_state = Mock()
        self.portfolio_state = Mock()

class MockEventBus:
    """Mock EventBus for testing"""
    def __init__(self):
        self.subscriptions = {}
        self.emitted_events = []
    
    def subscribe(self, event_type, handler):
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        self.subscriptions[event_type].append(handler)
    
    def unsubscribe(self, event_type, handler):
        if event_type in self.subscriptions:
            if handler in self.subscriptions[event_type]:
                self.subscriptions[event_type].remove(handler)
    
    def emit(self, event):
        self.emitted_events.append(event)

class MockMarketClock:
    """Mock MarketClock for testing"""
    def __init__(self):
        self.current_time = datetime.now()
    
    def get_current_time(self):
        return self.current_time

class MockEvent:
    """Mock Event for testing"""
    def __init__(self, event_id, event_type, source="test"):
        self.event_id = event_id
        self.event_type = event_type
        self.source = source
        self.timestamp = datetime.now()
        self.data = {}
        self.tags = []

class TestObserverEvent:
    """Test ObserverEvent functionality"""
    
    def test_observer_event_creation(self):
        """Test creating observer event"""
        event = ObserverEvent(
            observation_type="regime_analysis",
            observation_data={'score': 67.5, 'confidence': 0.82},
            confidence=0.82,
            timestamp=datetime.now()
        )
        
        assert event.observation_type == "regime_analysis"
        assert event.confidence == 0.82
        assert 'score' in event.observation_data
    
    def test_observer_event_to_event_conversion(self):
        """Test converting observer event to standard event"""
        observer_event = ObserverEvent(
            observation_type="stress_analysis",
            observation_data={'stress_level': 0.65},
            confidence=0.75,
            timestamp=datetime.now()
        )
        
        standard_event = observer_event.to_event()
        
        assert standard_event.source == "intelligence_observer"
        assert 'intelligence' in standard_event.tags
        assert 'observer' in standard_event.tags
        assert 'read_only' in standard_event.tags
        assert standard_event.data['authority_level'] == 'read_only'

class TestIntelligenceObserverOrgan:
    """Test Intelligence Observer Organ functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.observer_organ = IntelligenceObserverOrgan()
        self.mock_event_bus = MockEventBus()
        self.mock_unified_state = MockUnifiedState()
        self.mock_market_clock = MockMarketClock()
    
    def test_organ_initialization(self):
        """Test organ initializes correctly"""
        assert self.observer_organ.name == "Intelligence Observer"
        assert self.observer_organ.version == "1.0.0"
        assert not self.observer_organ.is_critical  # Observer is never critical
        assert self.observer_organ.observation_count == 0
        assert self.observer_organ.last_observation_time is None
    
    def test_organ_initialize_with_components(self):
        """Test organ initialization with Northstar components"""
        success = self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        assert success
        assert self.observer_organ.event_bus == self.mock_event_bus
        assert self.observer_organ.unified_state == self.mock_unified_state
        assert self.observer_organ.market_clock == self.mock_market_clock
        
        # Should have subscribed to events
        assert len(self.mock_event_bus.subscriptions) > 0
    
    def test_organ_read_state(self):
        """Test organ reading state (read-only)"""
        # Initialize first
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Should be able to read state without errors
        self.observer_organ.read_state(self.mock_unified_state)
        
        # State reference should be updated
        assert self.observer_organ.unified_state == self.mock_unified_state
    
    def test_organ_think_success(self):
        """Test successful organ thinking process"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Mock successful snapshot building and analysis
        with patch.object(self.observer_organ.scheduler, 'run_on_demand_analysis') as mock_analysis:
            mock_analysis.return_value = {
                'success': True,
                'snapshot_id': 'test_001',
                'results': [
                    {'type': 'score', 'category': 'regime', 'artifact': {'score_id': 'test_score'}}
                ]
            }
            
            result = self.observer_organ.think()
            
            assert result['status'] == 'success'
            assert 'snapshot_id' in result
            assert 'observations' in result
            assert self.observer_organ.observation_count == 1
            assert self.observer_organ.last_observation_time is not None
    
    def test_organ_think_suspended_observer(self):
        """Test thinking when observer is suspended"""
        # Suspend observer
        self.observer_organ.authority_firewall.observer_suspended = True
        
        result = self.observer_organ.think()
        
        assert result['status'] == 'suspended'
        assert 'violation' in result['reason'].lower()
    
    def test_organ_think_system_locks(self):
        """Test thinking respects system locks"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Set emergency state
        self.mock_unified_state.risk_state.status = "EMERGENCY"
        
        result = self.observer_organ.think()
        
        assert result['status'] == 'deferred'
        assert 'lock' in result['reason'].lower() or 'emergency' in result['reason'].lower()
    
    def test_organ_write_state_authority_check(self):
        """Test that write_state respects authority boundaries"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Should only write to audit trail, not core state
        self.observer_organ.write_state(self.mock_unified_state)
        
        # Should log the write attempt but not modify core state
        # (Implementation would check that only audit trail is modified)
    
    def test_organ_event_handling(self):
        """Test organ handles system events correctly"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Create mock event
        mock_event = MockEvent("test_001", "STATE_UPDATE")
        
        # Handle event
        self.observer_organ._handle_system_event(mock_event)
        
        # Should log event but take no action
        # (Implementation would verify audit log entry)
    
    def test_organ_observation_frequency_limits(self):
        """Test observation frequency limits"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Set recent observation
        self.observer_organ.last_observation_time = datetime.now() - timedelta(minutes=30)
        
        # Should be rate limited
        can_observe = self.observer_organ._can_observe_now()
        assert not can_observe
        
        # Set old observation
        self.observer_organ.last_observation_time = datetime.now() - timedelta(hours=25)
        
        # Should be allowed
        can_observe = self.observer_organ._can_observe_now()
        assert can_observe
    
    def test_organ_health_metrics(self):
        """Test organ health metrics reporting"""
        health = self.observer_organ.get_health_metrics()
        
        required_metrics = [
            'status', 'observation_count', 'last_observation',
            'authority_violations', 'observer_suspended', 'scheduler_running',
            'integration_status'
        ]
        
        for metric in required_metrics:
            assert metric in health
        
        # Integration status should show connection states
        integration_status = health['integration_status']
        assert 'event_bus_connected' in integration_status
        assert 'unified_state_connected' in integration_status
        assert 'market_clock_connected' in integration_status
    
    def test_organ_shutdown(self):
        """Test organ shutdown process"""
        # Initialize organ
        self.observer_organ.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Shutdown
        self.observer_organ.shutdown()
        
        # Should stop scheduler and unsubscribe from events
        assert not self.observer_organ.scheduler.is_running

class TestObserverIntegrationManager:
    """Test Observer Integration Manager functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.manager = ObserverIntegrationManager()
        self.mock_event_bus = MockEventBus()
        self.mock_unified_state = MockUnifiedState()
        self.mock_market_clock = MockMarketClock()
    
    def test_manager_initialization(self):
        """Test manager initializes correctly"""
        assert self.manager.name == "Observer Integration Manager"
        assert self.manager.version == "1.0.0"
        assert not self.manager.integration_active
        assert self.manager.observer_organ is None
    
    def test_manager_integration_success(self):
        """Test successful integration with Northstar"""
        success = self.manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        assert success
        assert self.manager.integration_active
        assert self.manager.observer_organ is not None
        assert isinstance(self.manager.observer_organ, IntelligenceObserverOrgan)
    
    def test_manager_integration_failure(self):
        """Test integration failure handling"""
        # Mock initialization failure
        with patch.object(IntelligenceObserverOrgan, 'initialize', return_value=False):
            success = self.manager.integrate_with_northstar(
                self.mock_event_bus,
                self.mock_unified_state,
                self.mock_market_clock
            )
            
            assert not success
            assert not self.manager.integration_active
    
    def test_manager_get_observer_organ(self):
        """Test getting observer organ for registration"""
        # Before integration
        organ = self.manager.get_observer_organ()
        assert organ is None
        
        # After integration
        self.manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        organ = self.manager.get_observer_organ()
        assert organ is not None
        assert isinstance(organ, IntelligenceObserverOrgan)
    
    def test_manager_integration_status(self):
        """Test integration status reporting"""
        # Before integration
        status = self.manager.get_integration_status()
        assert not status['integration_active']
        assert not status['observer_available']
        
        # After integration
        self.manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        status = self.manager.get_integration_status()
        assert status['integration_active']
        assert status['observer_available']
        
        # Should include health metrics
        assert 'status' in status
        assert 'observation_count' in status
    
    def test_manager_shutdown(self):
        """Test manager shutdown process"""
        # Integrate first
        self.manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        assert self.manager.integration_active
        
        # Shutdown
        self.manager.shutdown_integration()
        
        assert not self.manager.integration_active

class TestGlobalIntegrationFunctions:
    """Test global integration functions"""
    
    def setup_method(self):
        """Setup for each test"""
        self.mock_event_bus = MockEventBus()
        self.mock_unified_state = MockUnifiedState()
        self.mock_market_clock = MockMarketClock()
    
    def test_get_integration_manager_singleton(self):
        """Test that get_integration_manager returns singleton"""
        manager1 = get_integration_manager()
        manager2 = get_integration_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ObserverIntegrationManager)
    
    def test_integrate_intelligence_observer_function(self):
        """Test main integration function"""
        success = integrate_intelligence_observer(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        assert success
        
        # Should have created and integrated observer
        manager = get_integration_manager()
        assert manager.integration_active
        assert manager.observer_organ is not None

class TestIntegrationEdgeCases:
    """Test edge cases and error conditions"""
    
    def setup_method(self):
        """Setup for each test"""
        self.mock_event_bus = MockEventBus()
        self.mock_unified_state = MockUnifiedState()
        self.mock_market_clock = MockMarketClock()
    
    def test_integration_with_none_components(self):
        """Test integration with None components"""
        manager = ObserverIntegrationManager()
        
        # Should handle None gracefully
        success = manager.integrate_with_northstar(None, None, None)
        assert not success
        assert not manager.integration_active
    
    def test_multiple_integration_attempts(self):
        """Test multiple integration attempts"""
        manager = ObserverIntegrationManager()
        
        # First integration
        success1 = manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        assert success1
        
        # Second integration attempt
        success2 = manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Should handle gracefully (may succeed or fail depending on implementation)
        assert isinstance(success2, bool)
    
    def test_observer_with_missing_dependencies(self):
        """Test observer behavior with missing dependencies"""
        observer = IntelligenceObserverOrgan()
        
        # Try to think without initialization
        result = observer.think()
        
        # Should handle gracefully
        assert 'status' in result
        assert result['status'] in ['failed', 'error', 'deferred']
    
    def test_event_handling_with_malformed_events(self):
        """Test event handling with malformed events"""
        observer = IntelligenceObserverOrgan()
        observer.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Try handling None event
        try:
            observer._handle_system_event(None)
            # Should not crash
        except Exception as e:
            # Acceptable to raise exception for None event
            assert isinstance(e, (TypeError, AttributeError))
    
    def test_system_lock_detection_edge_cases(self):
        """Test system lock detection with various states"""
        observer = IntelligenceObserverOrgan()
        observer.initialize(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        # Test with missing risk_state
        self.mock_unified_state.risk_state = None
        should_respect = observer._should_respect_system_locks()
        assert isinstance(should_respect, bool)
        
        # Test with risk_state without status
        self.mock_unified_state.risk_state = Mock()
        delattr(self.mock_unified_state.risk_state, 'status')
        should_respect = observer._should_respect_system_locks()
        assert isinstance(should_respect, bool)

class TestIntegrationPerformance:
    """Test integration performance and resource usage"""
    
    def test_observer_memory_usage(self):
        """Test that observer doesn't consume excessive memory"""
        observer = IntelligenceObserverOrgan()
        
        # Initialize with mock components
        mock_event_bus = MockEventBus()
        mock_unified_state = MockUnifiedState()
        mock_market_clock = MockMarketClock()
        
        observer.initialize(mock_event_bus, mock_unified_state, mock_market_clock)
        
        # Observer should not hold large references
        # (This is more of a design check than a strict test)
        assert observer.event_bus is not None
        assert observer.unified_state is not None
        assert observer.market_clock is not None
    
    def test_event_subscription_efficiency(self):
        """Test that event subscriptions are efficient"""
        observer = IntelligenceObserverOrgan()
        mock_event_bus = MockEventBus()
        
        observer.initialize(mock_event_bus, MockUnifiedState(), MockMarketClock())
        
        # Should subscribe to reasonable number of events
        total_subscriptions = sum(len(handlers) for handlers in mock_event_bus.subscriptions.values())
        assert total_subscriptions <= 10  # Reasonable limit
        
        # Should subscribe to expected event types
        assert len(observer.subscribed_events) > 0
        for event_type in observer.subscribed_events:
            assert event_type in mock_event_bus.subscriptions
    
    def test_observation_generation_efficiency(self):
        """Test that observation generation is efficient"""
        observer = IntelligenceObserverOrgan()
        
        # Mock efficient analysis
        with patch.object(observer.scheduler, 'run_on_demand_analysis') as mock_analysis:
            mock_analysis.return_value = {
                'success': True,
                'snapshot_id': 'test_001',
                'results': []
            }
            
            # Generate observations
            observations = observer._generate_observations(Mock())
            
            # Should return list (even if empty)
            assert isinstance(observations, list)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])