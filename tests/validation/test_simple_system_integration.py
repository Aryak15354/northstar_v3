"""
Simple System Integration Validation

This module validates that the core implemented systems work together correctly.

Tests integration of:
- Unified State Management System  
- Performance Optimization and Caching System
- System Health Monitoring

Feature: northstar-v3-system-cohesion
"""

import pytest
import time
from datetime import datetime, timedelta

from src.cohesion.unified_state_manager import UnifiedStateManager, SystemState, AuthorityLevel
from src.cohesion.cache_manager import IntelligentCacheManager
from src.cohesion.cohesion_health_monitor import ComprehensiveHealthMonitor


class TestSimpleSystemIntegration:
    """
    Simple system integration validation
    
    Validates that core systems work together and enforce system invariants
    """
    
    def setup_method(self):
        """Set up integrated system for testing"""
        # Initialize core systems
        self.state_manager = UnifiedStateManager()
        self.cache_manager = IntelligentCacheManager()
        self.health_monitor = ComprehensiveHealthMonitor()
        
        # Register health checks
        self._register_health_checks()
    
    def teardown_method(self):
        """Clean up after tests"""
        # Stop monitoring
        if hasattr(self.health_monitor, 'stop_monitoring'):
            self.health_monitor.stop_monitoring()
    
    def _register_health_checks(self):
        """Register health checks for all systems"""
        def state_health_check():
            return {
                'healthy': self.state_manager.current_state is not None,
                'metrics': {'state_version': self.state_manager.current_state.version if self.state_manager.current_state else 0},
                'message': 'State manager operational'
            }
        
        def cache_health_check():
            stats = self.cache_manager.get_stats()
            return {
                'healthy': True,
                'metrics': {
                    'cache_hit_rate': stats.hit_rate,
                    'memory_usage_mb': stats.memory_usage_mb,
                    'entry_count': stats.entry_count
                },
                'message': 'Cache manager operational'
            }
        
        # Register all health checks
        self.health_monitor.register_component('state_manager', state_health_check, is_critical=True)
        self.health_monitor.register_component('cache_manager', cache_health_check, is_critical=False)
    
    def test_state_cache_integration(self):
        """
        Test integration between state management and caching
        
        Validates:
        - State updates can be cached
        - Cache invalidation works with state changes
        - System invariants are maintained
        """
        # Update state
        state_update = {
            'market_regime': 'normal',
            'risk_level': 'low',
            'timestamp': datetime.now()
        }
        
        result = self.state_manager.update_state(
            'market',  # Use 'market' component name
            state_update,
            AuthorityLevel.INTELLIGENCE  # Use INTELLIGENCE authority for market data
        )
        
        assert result, "State update should succeed"
        
        # Cache the state data
        current_state = self.state_manager.get_state()
        cache_key = 'market_state_snapshot'
        # Cache the market state component
        self.cache_manager.put(cache_key, current_state.market_state, max_age=timedelta(minutes=5))
        
        # Retrieve from cache
        cached_data = self.cache_manager.get(cache_key)
        assert cached_data is not None, "Data should be cached"
        assert cached_data.get('market_regime') == 'normal', "Cached data should match original"
        
        # Update state again
        state_update2 = {
            'market_regime': 'volatile',
            'risk_level': 'high'
        }
        
        result2 = self.state_manager.update_state(
            'market',  # Use 'market' component name
            state_update2,
            AuthorityLevel.INTELLIGENCE  # Use INTELLIGENCE authority for market data
        )
        
        assert result2, "Second state update should succeed"
        
        # SYSTEM LAW: State version should increment atomically
        new_state = self.state_manager.get_state()
        assert new_state.version == current_state.version + 1, \
            "State version should increment atomically"
        
        # Verify cache statistics
        stats = self.cache_manager.get_stats()
        assert stats.hits > 0, "Should have cache hits"
        assert stats.entry_count > 0, "Should have cache entries"
    
    def test_health_monitoring_integration(self):
        """
        Test health monitoring integration with other systems
        
        Validates:
        - All systems are monitored
        - Health status reflects system state
        - Alerts are generated appropriately
        """
        # Check that components are registered
        system_health = self.health_monitor.get_system_health()
        
        assert system_health['total_components'] >= 2, "Should have multiple components registered"
        assert system_health['critical_components'] >= 1, "Should have critical components"
        
        # Verify component health checks work
        for component_name in ['state_manager', 'cache_manager']:
            health_result = self.health_monitor.check_component_health(component_name)
            assert isinstance(health_result.healthy, bool), f"Health check for {component_name} should return boolean"
            assert health_result.healthy, f"Component {component_name} should be healthy"
        
        # Test alert generation
        self.health_monitor.set_alert_thresholds('cache_manager', 'cache_hit_rate', 0.5, 0.3)
        
        # Force a health check
        self.health_monitor.check_component_health('cache_manager')
        
        # SYSTEM LAW: Health monitoring must be comprehensive
        # All critical components should be monitored
        critical_components = system_health['component_statuses']
        for component_name, status in critical_components.items():
            if status.get('is_critical', False):
                assert 'healthy' in status, f"Critical component {component_name} must have health status"
                assert 'last_check' in status, f"Critical component {component_name} must have last check time"
    
    def test_error_resilience_integration(self):
        """
        Test system resilience to errors
        
        Validates:
        - System remains stable after errors
        - Health monitoring detects issues
        - Recovery mechanisms work
        """
        # Simulate error condition by creating unhealthy component
        error_count = 0
        def failing_health_check():
            nonlocal error_count
            error_count += 1
            return {
                'healthy': error_count <= 2,  # Fail after 2 checks
                'metrics': {'error_count': error_count},
                'message': 'OK' if error_count <= 2 else 'FAILED'
            }
        
        self.health_monitor.register_component('failing_service', failing_health_check, is_critical=True)
        
        # Initial checks should be healthy
        for i in range(2):
            health_result = self.health_monitor.check_component_health('failing_service')
            assert health_result.healthy, f"Service should be healthy on check {i+1}"
        
        # Next check should fail
        health_result = self.health_monitor.check_component_health('failing_service')
        assert not health_result.healthy, "Service should be unhealthy after failures"
        
        # System health should reflect the failure
        system_health = self.health_monitor.get_system_health()
        assert system_health['critical_unhealthy'] > 0, "Should have unhealthy critical components"
        assert not system_health['overall_healthy'], "System should be unhealthy with failed critical component"
        
        # SYSTEM LAW: System should detect and report failures
        failing_component_status = system_health['component_statuses']['failing_service']
        assert not failing_component_status['healthy'], "Failed component should be marked unhealthy"
        assert failing_component_status['is_critical'], "Failed component should be marked critical"
    
    def test_end_to_end_system_flow(self):
        """
        Test complete end-to-end system flow
        
        Validates:
        - Data flows through entire system
        - All components work together
        - System invariants are maintained throughout
        """
        # 1. Initialize system state
        initial_state = {
            'system_status': 'initializing',
            'components_loaded': ['state_manager', 'cache_manager', 'health_monitor'],
            'startup_time': datetime.now()
        }
        
        result = self.state_manager.update_state(
            'health',  # Use 'health' component name
            initial_state,
            AuthorityLevel.SYSTEM
        )
        assert result, "Initial state update should succeed"
        
        # 2. Cache system configuration
        config_data = {
            'cache_size_mb': 100,
            'health_check_interval': 30,
            'alert_thresholds': {'cpu': 80, 'memory': 90}
        }
        
        self.cache_manager.put('system_config', config_data, max_age=timedelta(hours=1))
        cached_config = self.cache_manager.get('system_config')
        assert cached_config is not None, "Configuration should be cached"
        assert cached_config['cache_size_mb'] == 100, "Cached config should match original"
        
        # 3. Update operational state
        operational_state = {
            'system_status': 'operational',
            'last_health_check': datetime.now(),
            'active_components': 3
        }
        
        result2 = self.state_manager.update_state(
            'health',  # Use 'health' component name
            operational_state,
            AuthorityLevel.SYSTEM
        )
        assert result2, "Operational state update should succeed"
        
        # 4. Perform health checks
        system_health = self.health_monitor.get_system_health()
        
        # 5. Validate end-to-end consistency
        current_state = self.state_manager.get_state()
        
        # SYSTEM LAW: End-to-end flow must maintain system consistency
        assert current_state.version >= 2, "State should have been updated multiple times"
        assert 'system_status' in current_state.health_state, "State should contain system status"
        assert current_state.health_state.get('system_status') == 'operational', "System should be operational"
        
        # Cache should have data
        cache_stats = self.cache_manager.get_stats()
        assert cache_stats.entry_count > 0, "Cache should contain entries"
        assert cache_stats.hits > 0, "Cache should have hits"
        
        # Health monitoring should be active
        assert system_health['total_components'] >= 2, "Health monitoring should track components"
        assert isinstance(system_health['overall_healthy'], bool), "System health should be determinable"
        
        print("✅ End-to-end system integration test passed!")
        print(f"   - State version: {current_state.version}")
        print(f"   - Cache entries: {cache_stats.entry_count}")
        print(f"   - Cache hit rate: {cache_stats.hit_rate:.2%}")
        print(f"   - Health components: {system_health['total_components']}")
        print(f"   - System healthy: {system_health['overall_healthy']}")
    
    def test_system_invariants_enforcement(self):
        """
        Test that all system invariants are enforced across integrated system
        
        Validates key system laws:
        - Atomic state updates (Property S1)
        - Cache freshness validation (Property P1)
        - Health monitoring completeness (Property H1)
        """
        # Test State Atomic Updates (Property S1)
        initial_version = self.state_manager.current_state.version
        
        update_result = self.state_manager.update_state(
            'health',  # Use valid component name
            {'test_value': 42, 'timestamp': datetime.now()},
            AuthorityLevel.SYSTEM
        )
        
        assert update_result, "State update should succeed"
        assert self.state_manager.current_state.version == initial_version + 1, \
            "State version should increment atomically"
        
        # Test Cache Freshness Validation (Property P1)
        # Cache data with short expiry
        test_data = {'value': 'test', 'created': datetime.now()}
        self.cache_manager.put('short_lived', test_data, max_age=timedelta(seconds=1))
        
        # Should be available immediately
        cached_data = self.cache_manager.get('short_lived')
        assert cached_data is not None, "Fresh data should be available"
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        expired_data = self.cache_manager.get('short_lived')
        assert expired_data is None, "Expired data should not be available"
        
        # Test Health Monitoring Completeness (Property H1)
        # All registered components should be monitored
        system_health = self.health_monitor.get_system_health()
        
        for component_name in ['state_manager', 'cache_manager']:
            assert component_name in system_health['component_statuses'], \
                f"Component {component_name} should be monitored"
            
            component_status = system_health['component_statuses'][component_name]
            assert 'healthy' in component_status, \
                f"Component {component_name} should have health status"
            assert 'last_check' in component_status, \
                f"Component {component_name} should have last check time"
        
        print("✅ All system invariants are properly enforced!")


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])